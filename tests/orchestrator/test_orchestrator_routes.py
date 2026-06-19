"""Tests for Post-NUS Orchestrator API Routes (dry-run/read-only)."""

from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
    from openjarvis.server.app import create_app
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


pytestmark = pytest.mark.skipif(
    not _FASTAPI_AVAILABLE,
    reason="fastapi/httpx not available",
)


@pytest.fixture(scope="module")
def client():
    from fastapi import FastAPI
    from openjarvis.server.orchestrator_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestOrchestratorStatus:
    def test_status_ok(self, client):
        resp = client.get("/v1/orchestrator/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dry_run_only"] is True
        assert data["us13_voice_parked"] is True
        assert data["manager_count"] > 0
        assert data["worker_count"] > 0

    def test_status_no_raw_cot(self, client):
        resp = client.get("/v1/orchestrator/status")
        data = resp.json()
        assert data["no_raw_chain_of_thought"] is True

    def test_status_blocked_actions_listed(self, client):
        resp = client.get("/v1/orchestrator/status")
        data = resp.json()
        assert "production_deploy" in data["blocked_actions"]


class TestManagerListRoute:
    def test_managers_listed(self, client):
        resp = client.get("/v1/orchestrator/managers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 17
        ids = [m["manager_id"] for m in data["managers"]]
        assert "coding_manager" in ids
        assert "governance_safety_manager" in ids

    def test_managers_have_required_fields(self, client):
        resp = client.get("/v1/orchestrator/managers")
        data = resp.json()
        for m in data["managers"]:
            assert "manager_id" in m
            assert "name" in m
            assert "department" in m
            assert "responsibility" in m
            assert "risk_ceiling" in m
            assert "status" in m


class TestWorkerListRoute:
    def test_workers_listed(self, client):
        resp = client.get("/v1/orchestrator/workers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 30
        ids = [w["worker_id"] for w in data["workers"]]
        assert "backend_worker" in ids
        assert "policy_gate_worker" in ids

    def test_workers_have_required_fields(self, client):
        resp = client.get("/v1/orchestrator/workers")
        data = resp.json()
        for w in data["workers"]:
            assert "worker_id" in w
            assert "manager_id" in w
            assert "department" in w
            assert "skills" in w


class TestActivationDryRunRoute:
    def test_dry_run_returns_plan(self, client):
        resp = client.post("/v1/orchestrator/activation/dry-run", json={
            "user_request_summary": "fix backend bug",
            "intent": "debug",
            "risk_level": "low",
            "complexity_level": "simple",
            "domains_required": ["debugging"],
            "required_skills": ["debugging"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dry_run"] is True
        plan = data["plan"]
        assert "selected_managers" in plan
        assert "activation_reasons" in plan
        assert "skip_reasons" in plan
        assert plan["no_raw_chain_of_thought"] is True

    def test_dry_run_does_not_execute_real_code(self, client):
        """Activation dry-run returns structured plan only — no real execution."""
        resp = client.post("/v1/orchestrator/activation/dry-run", json={
            "user_request_summary": "deploy to production",
            "intent": "deploy",
            "risk_level": "blocked",
        })
        assert resp.status_code == 200
        data = resp.json()
        plan = data["plan"]
        # Governance plan must block production_deploy
        gov_plan = plan.get("governance_plan", {})
        assert "production_deploy" in gov_plan.get("blocked_actions", [])


class TestRoutingDryRunRoute:
    def test_routing_returns_recommendation(self, client):
        resp = client.post("/v1/orchestrator/routing/dry-run", json={
            "intent": "implement",
            "risk_level": "medium",
            "complexity_level": "moderate",
            "action_type": "file_edit",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dry_run"] is True
        assert "recommended_tier" in data
        assert data["cheap_blocked_for_critical_approval"] is True

    def test_high_risk_routes_to_premium(self, client):
        resp = client.post("/v1/orchestrator/routing/dry-run", json={
            "intent": "deploy",
            "risk_level": "high",
            "complexity_level": "complex",
            "action_type": "deploy",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["recommended_tier"] == "premium"


class TestDecisionRecordDryRunRoute:
    def test_creates_record(self, client):
        resp = client.post("/v1/orchestrator/decision-records/dry-run", json={
            "action_type": "orchestration_plan",
            "decision": "dry_run",
            "reason": "test_doctor_check",
            "risk_level": "low",
            "hierarchy_level": "cos_gm",
            "nus_learning_tags": ["test", "orchestration"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["dry_run"] is True
        assert data["no_raw_chain_of_thought"] is True
        record = data["decision_record"]
        assert "record_id" in record
        assert record.get("no_raw_chain_of_thought") is True

    def test_hierarchy_level_accepted(self, client):
        for level in ["jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"]:
            resp = client.post("/v1/orchestrator/decision-records/dry-run", json={
                "action_type": "test",
                "decision": "dry_run",
                "reason": f"test_{level}",
                "hierarchy_level": level,
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["hierarchy_level"] == level


class TestGovernanceStatusRoute:
    def test_governance_status(self, client):
        resp = client.get("/v1/orchestrator/governance/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dry_run_only"] is True
        assert "production_deploy" in data["permanently_blocked_actions"]
        assert "auto_push" in data["permanently_blocked_actions"]
        assert "auto_merge" in data["permanently_blocked_actions"]
        assert data["us13_voice_parked"] is True
        assert data["hard_gates_active"] is True

    def test_us13_parked_message(self, client):
        resp = client.get("/v1/orchestrator/governance/status")
        data = resp.json()
        assert "HOLD/UNSAFE/PARKED" in data["us13_voice_status"]

    def test_all_hierarchy_levels_listed(self, client):
        resp = client.get("/v1/orchestrator/governance/status")
        data = resp.json()
        required_levels = {"jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"}
        listed = set(data["hierarchy_levels"])
        assert required_levels == listed
