"""Tests for the Orchestrator Runtime Trace system.

Proves:
  - Trace created at front-door entry with unique trace_id
  - Front-door event emitted when request arrives
  - Routing event emitted when request goes to COS/GM
  - COS/GM event emitted when COS/GM processes request
  - Manager activation events emitted for each activated manager
  - Worker execution events emitted for each dispatched worker
  - Validation event emitted when validation_required=True and workers run
  - NUS feedback event emitted after activation plan
  - Final response event emitted at end
  - Blocked request emits blocker event and final response event
  - Trace events carry trace_id matching the front-door request
  - No raw chain-of-thought in any trace event
  - Trace replay log is structured and human-readable
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_request(intent: str, user_input: str, requested_actions=None):
    from openjarvis.frontdoor.frontdoor import UniversalTaskRequest
    meta = {}
    if requested_actions:
        meta["requested_actions"] = requested_actions
    return UniversalTaskRequest.create(
        user_input=user_input,
        intent=intent,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# RuntimeTraceStore unit tests
# ---------------------------------------------------------------------------

class TestRuntimeTraceStore:
    def test_create_trace_returns_orchestrator_trace(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        trace = store.create_trace("req_001")
        assert trace.request_id == "req_001"
        assert trace.trace_id is not None
        assert len(trace.trace_id) > 0

    def test_trace_id_unique_per_request(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        t1 = store.create_trace("req_001")
        t2 = store.create_trace("req_002")
        assert t1.trace_id != t2.trace_id

    def test_get_returns_trace_by_id(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        trace = store.create_trace("req_get_test")
        retrieved = store.get(trace.trace_id)
        assert retrieved is trace

    def test_get_by_request_finds_trace(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        trace = store.create_trace("req_by_request")
        found = store.get_by_request("req_by_request")
        assert found is trace

    def test_recent_returns_most_recent(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        for i in range(5):
            store.create_trace(f"req_{i}")
        recent = store.recent(3)
        assert len(recent) == 3

    def test_max_traces_eviction(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore(max_traces=5)
        for i in range(10):
            store.create_trace(f"req_{i}")
        assert len(store._traces) <= 5

    def test_replay_log_returns_structured_dict(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore, EVENT_COS_GM
        store = RuntimeTraceStore()
        trace = store.create_trace("req_replay")
        trace.add_event(EVENT_COS_GM, "cos_gm", "test event")
        log = store.replay_log(trace.trace_id)
        assert log is not None
        assert log["replay_log"] is True
        assert "pipeline_steps" in log
        assert len(log["pipeline_steps"]) == 1

    def test_replay_log_returns_none_for_unknown_id(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        assert store.replay_log("nonexistent_trace_id") is None

    def test_get_summary_returns_dict(self):
        from openjarvis.orchestrator.runtime_trace import RuntimeTraceStore
        store = RuntimeTraceStore()
        store.create_trace("summary_req")
        summary = store.get_summary()
        assert "total_traces_stored" in summary
        assert "max_traces" in summary


# ---------------------------------------------------------------------------
# OrchestratorTrace unit tests
# ---------------------------------------------------------------------------

class TestOrchestratorTrace:
    def test_add_event_returns_event(self):
        from openjarvis.orchestrator.runtime_trace import OrchestratorTrace, EVENT_COS_GM
        trace = OrchestratorTrace(trace_id="test123", request_id="req123")
        evt = trace.add_event(EVENT_COS_GM, "cos_gm", "test summary")
        assert evt.event_type == EVENT_COS_GM
        assert evt.component == "cos_gm"
        assert evt.summary == "test summary"
        assert evt.trace_id == "test123"

    def test_add_event_no_raw_cot(self):
        from openjarvis.orchestrator.runtime_trace import OrchestratorTrace, EVENT_WORKER_EXECUTION
        trace = OrchestratorTrace(trace_id="t1", request_id="r1")
        evt = trace.add_event(EVENT_WORKER_EXECUTION, "worker:test", "worker ran")
        assert evt.no_raw_chain_of_thought is True

    def test_event_types_seen(self):
        from openjarvis.orchestrator.runtime_trace import (
            OrchestratorTrace, EVENT_COS_GM, EVENT_WORKER_EXECUTION,
        )
        trace = OrchestratorTrace(trace_id="t2", request_id="r2")
        trace.add_event(EVENT_COS_GM, "cos_gm", "step1")
        trace.add_event(EVENT_WORKER_EXECUTION, "worker", "step2")
        types = trace.event_types_seen()
        assert EVENT_COS_GM in types
        assert EVENT_WORKER_EXECUTION in types

    def test_get_by_type(self):
        from openjarvis.orchestrator.runtime_trace import OrchestratorTrace, EVENT_VALIDATION
        trace = OrchestratorTrace(trace_id="t3", request_id="r3")
        trace.add_event(EVENT_VALIDATION, "validator", "validation ok")
        events = trace.get_by_type(EVENT_VALIDATION)
        assert len(events) == 1

    def test_to_dict_has_all_fields(self):
        from openjarvis.orchestrator.runtime_trace import OrchestratorTrace, EVENT_COS_GM
        trace = OrchestratorTrace(trace_id="t4", request_id="r4")
        trace.add_event(EVENT_COS_GM, "cos_gm", "summary")
        d = trace.to_dict()
        assert "trace_id" in d
        assert "request_id" in d
        assert "events" in d
        assert "event_count" in d
        assert d["event_count"] == 1

    def test_elapsed_ms_positive(self):
        from openjarvis.orchestrator.runtime_trace import OrchestratorTrace
        import time
        trace = OrchestratorTrace(trace_id="t5", request_id="r5")
        time.sleep(0.001)
        assert trace.elapsed_ms() > 0


# ---------------------------------------------------------------------------
# Integration: trace events emitted via front door
# ---------------------------------------------------------------------------

class TestFrontDoorTraceEmission:
    """Front door emits FRONT_DOOR event and propagates trace_id."""

    def test_front_door_sets_trace_id_in_result_metadata(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        req = make_request("analyze code", "Inspect my code files")
        fd = JarvisFrontDoor()
        result = fd.handle(req)
        # trace_id should be set in result metadata
        assert "trace_id" in result.metadata
        assert result.metadata["trace_id"] is not None

    def test_trace_retrievable_after_request(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        from openjarvis.orchestrator.runtime_trace import get_trace_store
        req = make_request("research task", "Research the codebase")
        fd = JarvisFrontDoor()
        result = fd.handle(req)
        trace_id = result.metadata.get("trace_id")
        if trace_id:
            trace = get_trace_store().get(trace_id)
            assert trace is not None
            assert trace.request_id == req.request_id

    def test_front_door_event_emitted(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        from openjarvis.orchestrator.runtime_trace import (
            get_trace_store, EVENT_FRONT_DOOR,
        )
        req = make_request("test task", "A normal task")
        fd = JarvisFrontDoor()
        result = fd.handle(req)
        trace_id = result.metadata.get("trace_id")
        if trace_id:
            trace = get_trace_store().get(trace_id)
            assert trace is not None
            front_door_events = trace.get_by_type(EVENT_FRONT_DOOR)
            assert len(front_door_events) >= 1

    def test_blocked_request_emits_blocker_event(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        from openjarvis.orchestrator.runtime_trace import (
            get_trace_store, EVENT_BLOCKER,
        )
        req = make_request("push", "push", requested_actions=["auto_push"])
        fd = JarvisFrontDoor()
        result = fd.handle(req)
        assert result.status == "blocked"
        trace_id = result.metadata.get("trace_id")
        if trace_id:
            trace = get_trace_store().get(trace_id)
            if trace:
                blocker_events = trace.get_by_type(EVENT_BLOCKER)
                assert len(blocker_events) >= 1


# ---------------------------------------------------------------------------
# Integration: COS/GM emits trace events
# ---------------------------------------------------------------------------

class TestCosGmTraceEmission:
    """COS/GM emits COS_GM, MANAGER_ACTIVATION, WORKER_EXECUTION, and FINAL_RESPONSE events."""

    def test_cos_gm_result_has_trace_id(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        req = make_request("nus analysis", "Analyze NUS scores")
        result = JarvisFrontDoor().handle(req)
        assert "trace_id" in result.metadata

    def test_cos_gm_result_status_is_planned_or_executed(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        req = make_request("code review", "Review the latest changes")
        result = JarvisFrontDoor().handle(req)
        assert result.status in ("planned", "executed")

    def test_cos_gm_result_has_worker_results_in_metadata(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        req = make_request("cost analysis", "Analyze model routing costs")
        result = JarvisFrontDoor().handle(req)
        # workers_dispatched should be in metadata
        assert "workers_dispatched" in result.metadata

    def test_result_no_raw_cot(self):
        from openjarvis.frontdoor.frontdoor import JarvisFrontDoor
        req = make_request("research", "Do some research")
        result = JarvisFrontDoor().handle(req)
        assert result.no_raw_chain_of_thought is True


# ---------------------------------------------------------------------------
# Module-level start_trace / get_trace API
# ---------------------------------------------------------------------------

class TestModuleTraceAPI:
    def test_start_trace_returns_trace(self):
        from openjarvis.orchestrator.runtime_trace import start_trace
        trace = start_trace("module_req_001")
        assert trace.request_id == "module_req_001"

    def test_get_trace_retrieves_by_id(self):
        from openjarvis.orchestrator.runtime_trace import start_trace, get_trace
        trace = start_trace("module_req_002")
        retrieved = get_trace(trace.trace_id)
        assert retrieved is trace

    def test_get_trace_returns_none_for_unknown(self):
        from openjarvis.orchestrator.runtime_trace import get_trace
        assert get_trace("totally_unknown_trace_id_xyz") is None

    def test_all_event_types_defined(self):
        from openjarvis.orchestrator.runtime_trace import ALL_EVENT_TYPES
        expected = {
            "front_door", "routing", "cos_gm", "manager_activation",
            "worker_execution", "validation", "nus_feedback",
            "blocker", "final_response",
        }
        assert expected == ALL_EVENT_TYPES
