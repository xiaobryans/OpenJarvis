"""Plan 7 Phase A Gate Tests — Universal Jarvis Front Door.

Gate A requirements:
  - Tests for multiple request types entering the same universal front door
  - Tests proving OMNIX is not hardcoded as the universal root
  - Mobile and desktop API compatibility tests
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _make_app():
    """Create minimal test FastAPI app with frontdoor routes."""
    from fastapi import FastAPI
    from openjarvis.server.frontdoor_routes import router
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    return TestClient(_make_app())


# ---------------------------------------------------------------------------
# A1 — All supported intent types enter the same front door
# ---------------------------------------------------------------------------

class TestAllIntentsAccepted:
    INTENTS = [
        "coding",
        "research",
        "project_creation",
        "business_admin",
        "personal_task",
        "memory_question",
        "connector_action",
        "self_upgrade",
        "ui_product_change",
        "long_horizon_goal",
        "finance_admin",
        "multi_agent_task",
        "platform_operation",
    ]

    @pytest.mark.parametrize("intent", INTENTS)
    def test_intent_accepted_by_frontdoor(self, client, intent):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": f"Do something for {intent}",
            "intent": intent,
        })
        assert resp.status_code == 200, f"Intent '{intent}' rejected: {resp.text}"
        data = resp.json()
        assert data["intent"] == intent
        assert data["status"] in ("accepted", "blocked")

    def test_coding_request(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Fix the bug in auth.py",
            "intent": "coding",
            "client_platform": "desktop",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "coding"
        assert data["client_platform"] == "desktop"
        assert "request_id" in data

    def test_personal_task_request(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Remind me to call the doctor next Tuesday",
            "intent": "personal_task",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "personal_task"
        assert data["status"] == "accepted"

    def test_research_request(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Research competitor pricing models",
            "intent": "research",
        })
        assert resp.status_code == 200
        assert resp.json()["intent"] == "research"

    def test_long_horizon_goal_request(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Build a revenue-generating product in 90 days",
            "intent": "long_horizon_goal",
        })
        assert resp.status_code == 200
        assert resp.json()["intent"] == "long_horizon_goal"

    def test_finance_admin_request(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Review last month's expenses",
            "intent": "finance_admin",
        })
        assert resp.status_code == 200
        assert resp.json()["intent"] == "finance_admin"

    def test_self_upgrade_request(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Upgrade the memory OS to support vector similarity",
            "intent": "self_upgrade",
            "risk_level": "medium",
        })
        assert resp.status_code == 200
        assert resp.json()["intent"] == "self_upgrade"


# ---------------------------------------------------------------------------
# A2 — OMNIX not hardcoded as universal root
# ---------------------------------------------------------------------------

class TestOmnixNotRoot:
    def test_submit_without_project_context_succeeds(self, client):
        """Personal/global request with no project_context_id must succeed."""
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "What is the meaning of life?",
            "intent": "memory_question",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_context_id"] is None
        assert data["status"] == "accepted"

    def test_omnix_hardcoded_is_false(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Do something",
            "intent": "personal_task",
        })
        data = resp.json()
        assert data["omnix_hardcoded"] is False

    def test_status_omnix_is_not_default(self, client):
        resp = client.get("/v1/frontdoor/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["omnix_is_default"] is False
        assert data["omnix_is_root"] is False

    def test_intents_endpoint_omnix_not_required(self, client):
        resp = client.get("/v1/frontdoor/intents")
        assert resp.status_code == 200
        data = resp.json()
        assert data["omnix_required"] is False
        assert data["project_context_required"] is False

    def test_non_omnix_project_works(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Manage this new project",
            "intent": "project_creation",
            "project_context_id": "my_custom_project",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_context_id"] == "my_custom_project"
        assert data["omnix_hardcoded"] is False

    def test_omnix_project_still_accepted_as_adapter(self, client):
        """OMNIX project_context_id is accepted — as optional adapter, not root."""
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Continue OMNIX upgrade",
            "intent": "coding",
            "project_context_id": "omnix",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_context_id"] == "omnix"
        assert data["omnix_hardcoded"] is False  # never hardcoded even when used


# ---------------------------------------------------------------------------
# A3 — Mobile and desktop API compatibility
# ---------------------------------------------------------------------------

class TestMobileDesktopCompatibility:
    def test_desktop_platform_accepted(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Run code review",
            "intent": "coding",
            "client_platform": "desktop",
        })
        assert resp.status_code == 200
        assert resp.json()["client_platform"] == "desktop"

    def test_mobile_platform_accepted(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Run code review",
            "intent": "coding",
            "client_platform": "mobile",
        })
        assert resp.status_code == 200
        assert resp.json()["client_platform"] == "mobile"

    def test_api_platform_accepted(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Automation task",
            "intent": "platform_operation",
            "client_platform": "api",
        })
        assert resp.status_code == 200
        assert resp.json()["client_platform"] == "api"

    def test_status_mobile_compatible(self, client):
        resp = client.get("/v1/frontdoor/status")
        data = resp.json()
        assert data["mobile_compatible"] is True
        assert data["desktop_compatible"] is True

    def test_intents_mobile_supported(self, client):
        resp = client.get("/v1/frontdoor/intents")
        data = resp.json()
        assert data["mobile_supported"] is True
        assert data["desktop_supported"] is True

    def test_mobile_personal_task_same_api(self, client):
        """Mobile and desktop use IDENTICAL API surface — same endpoint, same fields."""
        desktop_resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Schedule a call",
            "intent": "personal_task",
            "client_platform": "desktop",
        })
        mobile_resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Schedule a call",
            "intent": "personal_task",
            "client_platform": "mobile",
        })
        d = desktop_resp.json()
        m = mobile_resp.json()
        # Same routing, same structure — only platform field differs
        assert d["intent"] == m["intent"]
        assert d["status"] == m["status"]
        assert d["omnix_hardcoded"] == m["omnix_hardcoded"]
        assert set(d.keys()) == set(m.keys())

    def test_mobile_long_horizon_goal(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Launch a SaaS product",
            "intent": "long_horizon_goal",
            "client_platform": "mobile",
        })
        assert resp.status_code == 200
        assert resp.json()["client_platform"] == "mobile"


# ---------------------------------------------------------------------------
# A4 — Routing pipeline fields
# ---------------------------------------------------------------------------

class TestRoutingPipeline:
    def test_response_has_routing_summary(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Plan my week",
            "intent": "personal_task",
        })
        data = resp.json()
        assert "routing_summary" in data
        assert "memory" in data["routing_summary"]

    def test_response_has_next_actions(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Do research",
            "intent": "research",
        })
        data = resp.json()
        assert "next_actions" in data
        assert len(data["next_actions"]) > 0

    def test_approval_required_for_high_risk(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Deploy to production",
            "intent": "platform_operation",
            "risk_level": "high",
        })
        data = resp.json()
        assert data["approval_required"] is True
        assert "await_approval" in data["next_actions"]

    def test_blocked_risk_level(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Force push to main",
            "intent": "coding",
            "risk_level": "blocked",
        })
        data = resp.json()
        assert data["status"] == "blocked"
        assert data["blocked_reason"] is not None

    def test_low_risk_no_approval_needed(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Read a file",
            "intent": "coding",
            "risk_level": "low",
        })
        data = resp.json()
        assert data["approval_required"] is False

    def test_unknown_intent_rejected(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "Do something",
            "intent": "hack_the_planet",
        })
        assert resp.status_code == 400

    def test_empty_input_rejected(self, client):
        resp = client.post("/v1/frontdoor/submit", json={
            "user_input": "",
            "intent": "personal_task",
        })
        assert resp.status_code == 400

    def test_unique_request_ids(self, client):
        ids = set()
        for _ in range(5):
            resp = client.post("/v1/frontdoor/submit", json={
                "user_input": "Test request",
                "intent": "personal_task",
            })
            ids.add(resp.json()["request_id"])
        assert len(ids) == 5  # all unique
