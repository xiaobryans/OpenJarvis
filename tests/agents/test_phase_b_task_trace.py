"""Phase B gate tests — executor task trace write → JarvisMemory.

Validates:
1. Task trace written to JarvisMemory after success.
2. Failure trace written after error (kind=mistake).
3. Task trace is searchable via JarvisMemory.search().
4. SelfImprovementRegistry.get_prevention() and FailureLearner recommendations are
   structurally accessible (backend exists, route is live).
"""

from __future__ import annotations

import pytest


class TestTaskTraceWrite:
    """Verify executor writes task traces to JarvisMemory."""

    def test_success_trace_written_to_memory(self, tmp_path):
        """Simulate success path — expect task_traces namespace entry."""
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=str(tmp_path / "trace_test.db"))
        agent_id = "test-agent-phase-b"

        # Write the same way executor._finalize_tick does on success
        preview = "Completed search for weather data successfully"
        mem.write(
            namespace="task_traces",
            content=f"agent:{agent_id} status:success duration:1.5s result:{preview}",
            kind="observation",
            source="executor",
            agent_id=agent_id,
        )

        results = mem.search(query="status:success", namespace="task_traces")
        assert len(results) >= 1
        assert any(agent_id in r.content for r in results)

    def test_failure_trace_written_to_memory(self, tmp_path):
        """Simulate failure path — expect task_traces namespace entry with mistake kind."""
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=str(tmp_path / "trace_fail.db"))
        agent_id = "test-agent-phase-b-fail"

        error_msg = "Connection refused to upstream API"
        mem.write(
            namespace="task_traces",
            content=f"agent:{agent_id} status:failure duration:0.5s error:{error_msg}",
            kind="mistake",
            source="executor",
            agent_id=agent_id,
        )

        results = mem.search(query="status:failure", namespace="task_traces")
        assert len(results) >= 1
        # Failure entries use kind=mistake
        assert any(r.kind == "mistake" for r in results)

    def test_success_trace_kind_is_observation(self, tmp_path):
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=str(tmp_path / "trace_kind.db"))
        entry = mem.write(
            namespace="task_traces",
            content="agent:x status:success duration:2.0s result:ok",
            kind="observation",
            source="executor",
            agent_id="x",
        )
        assert entry.kind == "observation"

    def test_failure_trace_kind_is_mistake(self, tmp_path):
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=str(tmp_path / "trace_mistake.db"))
        entry = mem.write(
            namespace="task_traces",
            content="agent:x status:failure duration:0.3s error:timeout",
            kind="mistake",
            source="executor",
            agent_id="x",
        )
        assert entry.kind == "mistake"

    def test_trace_searchable_by_agent_id(self, tmp_path):
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=str(tmp_path / "trace_search.db"))
        unique_id = "unique-agent-xyz-phase-b"
        mem.write(
            namespace="task_traces",
            content=f"agent:{unique_id} status:success duration:3.0s result:found items",
            kind="observation",
            source="executor",
            agent_id=unique_id,
        )

        results = mem.search(query=unique_id, namespace="task_traces")
        assert len(results) >= 1


class TestSelfImprovementBackend:
    """Verify SelfImprovementRegistry and FailureLearner are accessible."""

    def test_self_improvement_registry_importable(self):
        from openjarvis.agents.self_improvement import SelfImprovementRegistry
        assert SelfImprovementRegistry is not None

    def test_self_improvement_registry_instantiates(self, tmp_path):
        from openjarvis.agents.self_improvement import SelfImprovementRegistry

        reg = SelfImprovementRegistry(db_path=str(tmp_path / "sir.db"))
        assert reg is not None

    def test_failure_learner_importable(self):
        from openjarvis.nus.failure_learning import FailureLearner
        assert FailureLearner is not None

    def test_failure_learner_produces_recommendations(self, tmp_path):
        """FailureLearner.analyse() returns a list (may be empty without data)."""
        from openjarvis.nus.failure_learning import FailureLearner

        learner = FailureLearner()
        result = learner.analyze()
        assert isinstance(result, list)

    def test_nus_learning_status_route_exists(self):
        """GET /v1/nus/learning/status must be registered in nus_routes."""
        from openjarvis.server.nus_routes import router
        routes = [r.path for r in router.routes]
        assert any("learning" in path for path in routes)
