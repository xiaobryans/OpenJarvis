"""Plan 7 Phase I Gate Tests — Self-Upgrade / Major Coding Execution.

Gate I requirements:
  - Staged execution and rollback metadata tests
  - Confirmation gate tests
  - Provider truthfulness tests
  - Mobile/desktop parity for upgrade requests
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from openjarvis.server.self_upgrade_routes import router
    from openjarvis.orchestrator.self_upgrade import get_self_upgrade_store, SelfUpgradePlanStore
    import openjarvis.orchestrator.self_upgrade as _m
    _m._store = SelfUpgradePlanStore()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# I1 — Staged execution and rollback metadata
# ---------------------------------------------------------------------------

class TestStagedExecution:
    def test_create_upgrade_plan(self, client):
        resp = client.post("/v1/self-upgrade/request", json={
            "title": "Upgrade memory OS schema",
            "description": "Add 'status' column migration",
            "source_request": "Add status tracking to memory entries",
            "client_platform": "desktop",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is True
        plan = data["plan"]
        assert "plan_id" in plan
        assert plan["client_platform"] == "desktop"

    def test_add_steps_to_plan(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Multi-step upgrade",
            "source_request": "Upgrade the auth module",
        }).json()["plan"]["plan_id"]
        for i, (title, risk) in enumerate([
            ("Read existing files", "low"),
            ("Write new auth.py", "medium"),
            ("Run tests", "low"),
        ]):
            resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
                "title": title,
                "risk": risk,
                "validation_command": f"pytest tests/test_{i}.py",
            })
            assert resp.status_code == 200
        detail = client.get(f"/v1/self-upgrade/plans/{plan_id}").json()["plan"]
        assert detail["step_count"] == 3

    def test_step_lifecycle(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Lifecycle plan",
            "source_request": "Fix bug",
        }).json()["plan"]["plan_id"]
        step_id = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Read file",
            "risk": "low",
        }).json()["step"]["step_id"]
        # Start
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/start")
        assert resp.json()["status"] == "in_progress"
        # Complete
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/complete")
        assert resp.json()["status"] == "done"

    def test_rollback_metadata_created(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Rollback test",
            "source_request": "Upgrade with rollback",
        }).json()["plan"]["plan_id"]
        step_id = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Make change",
            "risk": "medium",
            "rollback_command": "git checkout -- src/openjarvis/auth.py",
        }).json()["step"]["step_id"]
        client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/complete")
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/rollback")
        assert resp.status_code == 200
        rb = resp.json()["rollback"]
        assert "rollback_id" in rb
        assert "steps_to_rollback" in rb
        assert "rollback_commands" in rb

    def test_fail_step_records_reason(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Fail test",
            "source_request": "Upgrade that fails",
        }).json()["plan"]["plan_id"]
        step_id = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Failing step",
            "risk": "low",
        }).json()["step"]["step_id"]
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/fail", json={
            "reason": "pytest: 3 tests failed",
        })
        assert resp.json()["status"] == "failed"
        assert "pytest" in resp.json()["failure_reason"]

    def test_memory_refs_for_past_failures(self, client):
        resp = client.post("/v1/self-upgrade/request", json={
            "title": "Plan with failure memory",
            "source_request": "Retry failed upgrade",
            "memory_refs": ["past_failure:auth_upgrade_2024", "past_failure:schema_migration"],
        })
        plan = resp.json()["plan"]
        assert "past_failure:auth_upgrade_2024" in plan["memory_refs"]

    def test_mobile_can_create_upgrade_plan(self, client):
        resp = client.post("/v1/self-upgrade/request", json={
            "title": "Mobile-initiated upgrade",
            "source_request": "Fix auth bug",
            "client_platform": "mobile",
        })
        assert resp.status_code == 200
        assert resp.json()["plan"]["client_platform"] == "mobile"


# ---------------------------------------------------------------------------
# I2 — Confirmation gate tests
# ---------------------------------------------------------------------------

class TestConfirmationGates:
    def test_high_risk_step_sets_confirmation_required(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Confirm gate test",
            "source_request": "Deploy to production",
        }).json()["plan"]["plan_id"]
        client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Deploy step",
            "risk": "high",
            "requires_confirmation": True,
        })
        detail = client.get(f"/v1/self-upgrade/plans/{plan_id}").json()["plan"]
        assert detail["confirmation_required"] is True
        assert detail["confirmed"] is False

    def test_high_risk_step_blocked_without_confirmation(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Blocked until confirmed",
            "source_request": "Destructive upgrade",
        }).json()["plan"]["plan_id"]
        step_id = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Destructive step",
            "risk": "destructive",
            "requires_confirmation": True,
        }).json()["step"]["step_id"]
        # Start without confirmation — must be blocked
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/start")
        assert resp.status_code == 403

    def test_confirm_plan_allows_execution(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Confirm then execute",
            "source_request": "Safe upgrade needing confirm",
        }).json()["plan"]["plan_id"]
        step_id = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Risky but confirmed step",
            "risk": "high",
            "requires_confirmation": True,
        }).json()["step"]["step_id"]
        # Confirm first
        client.post(f"/v1/self-upgrade/plans/{plan_id}/confirm")
        # Now start should work
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_low_risk_no_confirmation_needed(self, client):
        plan_id = client.post("/v1/self-upgrade/request", json={
            "title": "Low risk plan",
            "source_request": "Read-only inspection",
        }).json()["plan"]["plan_id"]
        step_id = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps", json={
            "title": "Read files",
            "risk": "low",
            "requires_confirmation": False,
        }).json()["step"]["step_id"]
        # No confirmation needed for low risk
        resp = client.post(f"/v1/self-upgrade/plans/{plan_id}/steps/{step_id}/start")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# I3 — Provider truthfulness tests
# ---------------------------------------------------------------------------

class TestProviderTruthfulness:
    def test_provider_status_endpoint_exists(self, client):
        resp = client.get("/v1/self-upgrade/provider-status")
        assert resp.status_code == 200

    def test_provider_status_is_truthful(self, client):
        resp = client.get("/v1/self-upgrade/provider-status")
        data = resp.json()
        assert data["truthful"] is True
        assert data["mock_or_live_distinction_maintained"] is True

    def test_providers_listed(self, client):
        resp = client.get("/v1/self-upgrade/provider-status")
        providers = resp.json()["providers"]
        assert len(providers) > 0
        for p in providers:
            assert "provider_name" in p
            assert "status" in p
            assert "is_live" in p
            assert "is_mock" in p
            assert "notes" in p

    def test_no_provider_claims_available_without_key(self, client):
        """If env key is missing, provider must not claim AVAILABLE."""
        import os
        resp = client.get("/v1/self-upgrade/provider-status")
        providers = resp.json()["providers"]
        for p in providers:
            if not p["is_live"]:
                assert p["status"] != "available", (
                    f"Provider {p['provider_name']} not live but claims available"
                )
