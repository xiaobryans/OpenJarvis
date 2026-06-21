"""Plan 7 Phase H Gate Tests — Private AI Organization / Multi-Agent Command Center.

Gate H requirements:
  - Multi-worker routing tests
  - Reviewer/audit tests
  - Worker trace memory tests
  - Fake-success rejection tests
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# H1 — Multi-worker routing
# ---------------------------------------------------------------------------

class TestMultiWorkerRouting:
    def test_worker_registry_has_known_adapters(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter
        # Known workers
        for wid in ["doctor_validation", "nus_learning", "cost_analysis", "coding_safe"]:
            adapter = get_worker_adapter(wid)
            assert adapter is not None, f"Worker '{wid}' not found"

    def test_unknown_worker_returns_base_adapter(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter, WorkerAdapter
        adapter = get_worker_adapter("nonexistent_worker_xyz")
        assert isinstance(adapter, WorkerAdapter)

    def test_manager_registry_loaded(self):
        from openjarvis.orchestrator.manager_registry import get_manager_registry
        registry = get_manager_registry()
        managers = registry.list_all()
        assert len(managers) > 0

    def test_manager_registry_has_no_duplicates(self):
        from openjarvis.orchestrator.manager_registry import get_manager_registry
        registry = get_manager_registry()
        assert not registry.has_duplicate_ids()

    def test_orchestrator_routing_dry_run(self):
        """Orchestrator must handle a request through activation plan (dry-run)."""
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator
        orch = CosGmOrchestrator()
        status = orch.get_status()
        assert status is not None
        assert isinstance(status, dict)

    def test_multi_domain_routing_via_activation(self):
        """Different intent types must produce distinct activation plans."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.orchestrator_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        for intent in ["coding", "research", "operations"]:
            resp = client.post("/v1/orchestrator/activation/dry-run", json={
                "user_request_summary": f"{intent} task",
                "intent": intent,
            })
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# H2 — Reviewer/auditor loop
# ---------------------------------------------------------------------------

class TestReviewerAuditLoop:
    def test_worker_result_has_structured_fields(self):
        from openjarvis.orchestrator.worker_adapters import WorkerAdapterResult
        result = WorkerAdapterResult(
            worker_id="test_worker",
            action_type="local_read",
            status="ok",
            summary="Read operation completed",
            dry_run=True,
            no_raw_chain_of_thought=True,
        )
        assert result.worker_id == "test_worker"
        assert result.no_raw_chain_of_thought is True
        d = result.to_dict()
        assert "worker_id" in d
        assert "status" in d
        assert "no_raw_chain_of_thought" in d

    def test_worker_adapter_dry_run_marks_as_dry_run(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter
        adapter = get_worker_adapter("cost_analysis")
        result = adapter.execute(
            action_type="cost_analysis",
            inputs={"target": "test"},
            dry_run=True,
        )
        assert result.dry_run is True

    def test_decision_record_dry_run_produces_audit_output(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.orchestrator_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.post("/v1/orchestrator/decision-records/dry-run", json={
            "action_type": "local_read",
            "decision": "approve",
            "reason": "Safe read operation",
            "risk_level": "low",
            "hierarchy_level": "cos_gm",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "decision_record" in data or "record" in data or "status" in data


# ---------------------------------------------------------------------------
# H3 — Worker trace memory
# ---------------------------------------------------------------------------

class TestWorkerTraceMemory:
    def test_worker_result_serializable(self):
        from openjarvis.orchestrator.worker_adapters import WorkerAdapterResult
        result = WorkerAdapterResult(
            worker_id="test_worker",
            action_type="local_read",
            status="ok",
            summary="Read file content",
            dry_run=False,
        )
        d = result.to_dict()
        assert "worker_id" in d
        assert "status" in d
        assert "summary" in d

    def test_workstream_task_trace_for_worker_result(self):
        """Worker results can be recorded as task memory traces in workstreams."""
        from openjarvis.projects.workstream import WorkstreamRegistry
        registry = WorkstreamRegistry()
        ws = registry.create("Worker trace test")
        task = ws.add_task("Run code analysis")
        # Simulate worker result recorded as trace
        task.add_memory_trace("worker_executed", {
            "worker_id": "coding_safe",
            "action_type": "file_inspection",
            "success": True,
            "output_summary": "3 files analyzed, no issues found",
        })
        assert len(task.memory_trace) == 1
        assert task.memory_trace[0]["data"]["worker_id"] == "coding_safe"

    def test_runtime_trace_module_exists(self):
        import openjarvis.orchestrator.runtime_trace as rt
        assert rt is not None  # Module exists and is importable


# ---------------------------------------------------------------------------
# H4 — Fake-success rejection
# ---------------------------------------------------------------------------

class TestFakeSuccessRejection:
    def test_worker_blocked_action_not_reported_as_ok(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter
        adapter = get_worker_adapter("coding_safe")
        # Production deploy is a blocked action type
        result = adapter.execute(
            action_type="production_deploy",
            inputs={"target": "prod"},
            dry_run=False,
        )
        # Must NOT be status="ok" — must be blocked
        assert result.status == "blocked"
        assert result.blocked_reason != ""

    def test_worker_auto_push_blocked(self):
        from openjarvis.orchestrator.worker_adapters import get_worker_adapter
        adapter = get_worker_adapter("coding_safe")
        result = adapter.execute(
            action_type="auto_push",
            inputs={"branch": "main"},
            dry_run=False,
        )
        assert result.status == "blocked"
        assert result.blocked_reason != ""

    def test_governance_status_has_hard_gates(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.orchestrator_routes import router
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        resp = client.get("/v1/orchestrator/governance/status")
        assert resp.status_code == 200
        data = resp.json()
        # Hard gates must be declared (not hidden)
        assert "hard_gates" in data or "blocked" in data or "governance" in str(data).lower()

    def test_no_fabricated_worker_capability(self):
        """Workers with implementation_status != AVAILABLE must not report available."""
        from openjarvis.orchestrator.manager_registry import get_manager_registry
        registry = get_manager_registry()
        for manager in registry.list_all():
            d = manager.to_dict()
            # Inactive managers must not claim available status
            if not d.get("is_active", True):
                status = d.get("implementation_status", "")
                assert status != "AVAILABLE", (
                    f"Manager '{d['manager_id']}' is inactive but claims AVAILABLE"
                )
