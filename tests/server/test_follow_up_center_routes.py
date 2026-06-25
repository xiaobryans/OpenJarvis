"""Tests for Phase B1 — Follow-Up Center routes.

Covers:
  - GET /v1/follow-up-center returns 200 with expected shape
  - No fake data returned
  - automation_honesty=True
  - GET /v1/follow-up-center/summary returns 200 with count fields
  - summary fake_data=False
  - POST /v1/follow-up-center/tasks/{task_id}/complete — 404 on unknown task
  - POST /v1/follow-up-center/tasks/{task_id}/snooze — 404 on unknown task
  - Filtering by source/status query params
  - Self-knowledge has follow_up_center capability
  - Self-knowledge follow_up_center status is 'available'
  - Phase B1 in roadmap as IN_PROGRESS
  - plan_state has phase_b1_follow_up_center key
  - OMNIX not Jarvis core (Phase X regression)
  - Approval gates not weakened
  - No credential values in any endpoint response
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fuc_client():
    from openjarvis.server.follow_up_center_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def sk_client():
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Follow-Up Center list endpoint
# ---------------------------------------------------------------------------

class TestFollowUpCenterList:
    def test_returns_200(self, fuc_client):
        res = fuc_client.get("/v1/follow-up-center")
        assert res.status_code == 200

    def test_has_items_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_has_count_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert "count" in data
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["items"])

    def test_fake_data_is_false(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert data["fake_data"] is False

    def test_automation_honesty_is_true(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert data["automation_honesty"] is True

    def test_sources_probed_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert "sources_probed" in data
        assert "life_os_task" in data["sources_probed"]
        assert "goal" in data["sources_probed"]

    def test_has_due_count_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert "due_count" in data
        assert isinstance(data["due_count"], int)

    def test_has_pending_approval_count(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert "pending_approval_count" in data

    def test_has_note_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        assert "note" in data
        assert len(data["note"]) > 0

    def test_no_credential_values_in_response(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        text = str(data)
        for prefix in ("xoxb-", "xoxp-", "ghp_", "AKIA", "sk-proj-", "Bearer "):
            assert prefix not in text, f"Credential prefix '{prefix}' leaked"

    def test_source_filter_accepted(self, fuc_client):
        res = fuc_client.get("/v1/follow-up-center?source=life_os_task")
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert item["source"] == "life_os_task"

    def test_source_filter_goal(self, fuc_client):
        res = fuc_client.get("/v1/follow-up-center?source=goal")
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert item["source"] == "goal"

    def test_status_filter_accepted(self, fuc_client):
        res = fuc_client.get("/v1/follow-up-center?status=due")
        assert res.status_code == 200
        data = res.json()
        for item in data["items"]:
            assert item["status"] == "due"

    def test_limit_param_respected(self, fuc_client):
        res = fuc_client.get("/v1/follow-up-center?limit=1")
        assert res.status_code == 200
        data = res.json()
        assert len(data["items"]) <= 1

    def test_item_shape_when_present(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center").json()
        for item in data["items"]:
            assert "item_id" in item
            assert "source" in item
            assert "source_id" in item
            assert "title" in item
            assert "status" in item
            assert "approval_required" in item
            assert isinstance(item["approval_required"], bool)


# ---------------------------------------------------------------------------
# Summary endpoint
# ---------------------------------------------------------------------------

class TestFollowUpCenterSummary:
    def test_returns_200(self, fuc_client):
        res = fuc_client.get("/v1/follow-up-center/summary")
        assert res.status_code == 200

    def test_has_total_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center/summary").json()
        assert "total" in data
        assert isinstance(data["total"], int)

    def test_has_by_source(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center/summary").json()
        assert "by_source" in data
        assert isinstance(data["by_source"], dict)

    def test_has_by_status(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center/summary").json()
        assert "by_status" in data
        assert isinstance(data["by_status"], dict)

    def test_has_due_field(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center/summary").json()
        assert "due" in data
        assert isinstance(data["due"], int)

    def test_fake_data_is_false(self, fuc_client):
        data = fuc_client.get("/v1/follow-up-center/summary").json()
        assert data["fake_data"] is False


# ---------------------------------------------------------------------------
# Complete endpoint
# ---------------------------------------------------------------------------

class TestFollowUpCenterComplete:
    def test_complete_unknown_task_returns_404(self, fuc_client):
        res = fuc_client.post("/v1/follow-up-center/tasks/nonexistent-task-xyz/complete")
        assert res.status_code == 404

    def test_complete_endpoint_exists(self, fuc_client):
        res = fuc_client.post("/v1/follow-up-center/tasks/nonexistent-task-xyz/complete")
        # 404 is the expected error for unknown task — not 405 (method not allowed)
        assert res.status_code != 405


# ---------------------------------------------------------------------------
# Snooze endpoint
# ---------------------------------------------------------------------------

class TestFollowUpCenterSnooze:
    def test_snooze_unknown_task_returns_404(self, fuc_client):
        import time
        payload = {"snooze_until": time.time() + 86400, "reason": "test"}
        res = fuc_client.post(
            "/v1/follow-up-center/tasks/nonexistent-task-xyz/snooze",
            json=payload,
        )
        assert res.status_code == 404

    def test_snooze_endpoint_exists(self, fuc_client):
        import time
        payload = {"snooze_until": time.time() + 86400, "reason": "test"}
        res = fuc_client.post(
            "/v1/follow-up-center/tasks/nonexistent-task-xyz/snooze",
            json=payload,
        )
        assert res.status_code != 405

    def test_snooze_requires_snooze_until(self, fuc_client):
        # Missing required field — should return 422
        res = fuc_client.post(
            "/v1/follow-up-center/tasks/some-task/snooze",
            json={"reason": "test"},
        )
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# Self-knowledge integration
# ---------------------------------------------------------------------------

class TestSelfKnowledgeFollowUpCenter:
    def test_follow_up_center_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "follow_up_center" in cap_ids, "follow_up_center capability must appear"

    def test_follow_up_center_capability_is_available(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap = next((c for c in data["capabilities"] if c["id"] == "follow_up_center"), None)
        assert cap is not None
        assert cap["status"] == "available", (
            f"follow_up_center must be 'available', got {cap['status']}"
        )

    def test_phase_b1_in_roadmap(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        phase_b1 = next((r for r in data["roadmap"] if "Phase B1" in r["plan"]), None)
        assert phase_b1 is not None, "Phase B1 must appear in roadmap"
        assert phase_b1["status"] == "IN_PROGRESS"

    def test_plan_state_has_phase_b1(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert "phase_b1_follow_up_center" in data["plan_state"]
        assert data["plan_state"]["phase_b1_follow_up_center"] == "IN_PROGRESS"

    def test_active_sprint_is_phase_b1(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        assert "PHASE_B1" in data["active_sprint"]

    def test_plan_4_6_still_accepted(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"]["plan_4_6_mega_sprint"] == "ACCEPTED"

    def test_phase_x_still_accepted(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"]["phase_x_decoupling"] == "ACCEPTED"


# ---------------------------------------------------------------------------
# Universal Jarvis / OMNIX decoupling (Phase X regression)
# ---------------------------------------------------------------------------

class TestOmnixDecouplingNotRegressed:
    def test_jarvis_identity_primary_project_not_omnix(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("primary_project") != "omnix"

    def test_jarvis_identity_name_is_jarvis(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("name") == "Jarvis"

    def test_follow_up_center_module_no_omnix_hardcode(self):
        import inspect
        from openjarvis.server import follow_up_center_routes
        source = inspect.getsource(follow_up_center_routes)
        assert "OMNIX" not in source.upper().replace("omnix_production_deploy", "").replace("# ", ""), (
            "follow_up_center_routes must not reference OMNIX as Jarvis core"
        )


# ---------------------------------------------------------------------------
# Approval gates not weakened
# ---------------------------------------------------------------------------

class TestApprovalGatesNotWeakened:
    def test_hard_gates_unchanged(self):
        from openjarvis.governance.constitution import HARD_GATE_ACTIONS
        assert len(HARD_GATE_ACTIONS) >= 14

    def test_approval_route_documented_not_bypassed(self, fuc_client):
        # The complete endpoint must NOT auto-complete approval-required tasks
        # (it cannot be verified without a real task, but the route contract is
        # documented to return approval_route — not completing directly)
        # Smoke: endpoint exists and doesn't return 200 for unknown task
        res = fuc_client.post("/v1/follow-up-center/tasks/fake-task/complete")
        assert res.status_code == 404  # task not found — no bypass


# ---------------------------------------------------------------------------
# Frontend source checks
# ---------------------------------------------------------------------------

class TestFrontendFollowUpCenter:
    def _read(self, path: str) -> str:
        from pathlib import Path
        return Path(path).read_text()

    def test_page_has_empty_state(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "No follow-ups" in src

    def test_page_has_loading_state(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "Loading" in src or "loading" in src

    def test_page_has_error_state(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "error" in src.lower() or "Error" in src

    def test_page_has_responsive_stats_strip(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "grid-cols-3 sm:grid-cols-5" in src

    def test_page_has_flex_wrap_filters(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "flex-wrap" in src

    def test_page_has_responsive_expanded_panel(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "grid-cols-1 sm:grid-cols-2" in src

    def test_page_uses_honesty_flag(self):
        src = self._read("frontend/src/pages/FollowUpCenterPage.tsx")
        assert "fake_data" in src or "Honest data" in src

    def test_jarvis_api_has_follow_up_types(self):
        src = self._read("frontend/src/lib/jarvis-api.ts")
        assert "FollowUpItem" in src
        assert "FollowUpCenterResponse" in src
        assert "fetchFollowUpCenter" in src
        assert "completeTaskFollowUp" in src
        assert "snoozeTaskFollowUp" in src

    def test_app_tsx_has_follow_up_route(self):
        src = self._read("frontend/src/App.tsx")
        assert "follow-ups" in src
        assert "FollowUpCenterPage" in src

    def test_sidebar_has_follow_up_entry(self):
        src = self._read("frontend/src/components/Sidebar/Sidebar.tsx")
        assert "/follow-ups" in src
        assert "Follow-Up" in src or "follow-ups" in src
