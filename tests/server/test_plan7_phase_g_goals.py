"""Plan 7 Phase G Gate Tests — Long-Horizon Autonomous Goal Execution.

Gate G requirements:
  - Goal create → milestone → pause → reload → resume tests
  - Failure/retry tests
  - Approval gate tests
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from openjarvis.server.goals_routes import router
    from openjarvis.orchestrator.goals import get_goal_registry, GoalRegistry
    import openjarvis.orchestrator.goals as _m
    _m._registry = GoalRegistry()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# G1 — Goal create → milestone → pause → reload → resume
# ---------------------------------------------------------------------------

class TestGoalLifecycle:
    def test_create_goal(self, client):
        resp = client.post("/v1/goals", json={
            "title": "Build SaaS revenue stream",
            "description": "Reach $10k MRR in 90 days",
            "horizon": "90d",
            "tags": ["business", "revenue"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is True
        goal = data["goal"]
        assert goal["title"] == "Build SaaS revenue stream"
        assert goal["status"] == "active"
        assert goal["horizon"] == "90d"
        assert goal["memory_namespace"].startswith("goal:")

    def test_add_milestone(self, client):
        create_resp = client.post("/v1/goals", json={"title": "Goal with milestones", "horizon": "30d"})
        goal_id = create_resp.json()["goal"]["goal_id"]
        resp = client.post(f"/v1/goals/{goal_id}/milestones", json={
            "title": "Launch MVP",
            "description": "Get first paying customer",
            "completion_criteria": "At least 1 paying customer",
        })
        assert resp.status_code == 200
        m = resp.json()["milestone"]
        assert m["title"] == "Launch MVP"
        assert m["status"] == "pending"
        assert "milestone_id" in m

    def test_complete_milestone(self, client):
        create_resp = client.post("/v1/goals", json={"title": "Complete milestone goal"})
        goal_id = create_resp.json()["goal"]["goal_id"]
        m_resp = client.post(f"/v1/goals/{goal_id}/milestones", json={"title": "M1"})
        mid = m_resp.json()["milestone"]["milestone_id"]
        resp = client.post(f"/v1/goals/{goal_id}/milestones/{mid}/complete")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_pause_goal_saves_continuation_state(self, client):
        create_resp = client.post("/v1/goals", json={"title": "Pausable goal"})
        goal_id = create_resp.json()["goal"]["goal_id"]
        client.post(f"/v1/goals/{goal_id}/milestones", json={"title": "First milestone"})
        resp = client.post(f"/v1/goals/{goal_id}/pause", json={
            "reason": "Waiting for external data",
            "context": {"last_step": "market_research"},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paused"
        assert data["continuation_state"] is not None
        assert data["continuation_state"]["pause_reason"] == "Waiting for external data"

    def test_reload_continuation_state(self, client):
        """After pause, continuation state must be loadable."""
        create_resp = client.post("/v1/goals", json={"title": "Reload test goal"})
        goal_id = create_resp.json()["goal"]["goal_id"]
        client.post(f"/v1/goals/{goal_id}/pause", json={"reason": "Test pause"})
        resp = client.get(f"/v1/goals/{goal_id}/continuation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_continuation"] is True
        assert data["status"] == "paused"
        assert data["continuation_state"]["pause_reason"] == "Test pause"

    def test_resume_paused_goal(self, client):
        """Resume must move goal from paused → active and return continuation state."""
        create_resp = client.post("/v1/goals", json={"title": "Resume test goal"})
        goal_id = create_resp.json()["goal"]["goal_id"]
        client.post(f"/v1/goals/{goal_id}/pause", json={"reason": "Step 2 waiting"})
        resp = client.post(f"/v1/goals/{goal_id}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["resumed"] is True
        assert data["continuation_state"] is not None

    def test_full_lifecycle_create_milestone_pause_resume(self, client):
        """Full lifecycle: create → add milestones → add action → pause → resume."""
        # Create
        goal_id = client.post("/v1/goals", json={"title": "Full lifecycle", "horizon": "90d"}).json()["goal"]["goal_id"]
        # Add milestones
        m1 = client.post(f"/v1/goals/{goal_id}/milestones", json={"title": "M1: Research"}).json()["milestone"]["milestone_id"]
        m2 = client.post(f"/v1/goals/{goal_id}/milestones", json={"title": "M2: Build"}).json()["milestone"]["milestone_id"]
        # Complete first milestone
        client.post(f"/v1/goals/{goal_id}/milestones/{m1}/complete")
        # Add next action
        client.post(f"/v1/goals/{goal_id}/actions", json={"title": "Build prototype", "action_type": "execute"})
        # Pause
        pause_resp = client.post(f"/v1/goals/{goal_id}/pause", json={"reason": "Waiting for team"})
        assert pause_resp.json()["status"] == "paused"
        # Resume
        resume_resp = client.post(f"/v1/goals/{goal_id}/resume")
        assert resume_resp.json()["status"] == "active"
        # Verify detail
        detail = client.get(f"/v1/goals/{goal_id}").json()["goal"]
        assert detail["milestone_count"] == 2
        assert detail["next_action_count"] == 1


# ---------------------------------------------------------------------------
# G2 — Failure/retry tests
# ---------------------------------------------------------------------------

class TestFailureAndRetry:
    def test_fail_milestone(self, client):
        goal_id = client.post("/v1/goals", json={"title": "Fail test"}).json()["goal"]["goal_id"]
        mid = client.post(f"/v1/goals/{goal_id}/milestones", json={"title": "Risky milestone"}).json()["milestone"]["milestone_id"]
        resp = client.post(f"/v1/goals/{goal_id}/milestones/{mid}/fail", json={"reason": "API rate limit exceeded"})
        assert resp.json()["status"] == "failed"

    def test_retry_action_increments_count(self, client):
        goal_id = client.post("/v1/goals", json={"title": "Retry test"}).json()["goal"]["goal_id"]
        aid = client.post(f"/v1/goals/{goal_id}/actions", json={"title": "Flaky action"}).json()["action"]["action_id"]
        resp = client.post(f"/v1/goals/{goal_id}/actions/{aid}/retry", json={"failure_reason": "Timeout"})
        assert resp.json()["retry_count"] == 1
        assert resp.json()["can_retry"] is True
        assert resp.json()["last_failed_reason"] == "Timeout"

    def test_retry_max_exceeded(self, client):
        goal_id = client.post("/v1/goals", json={"title": "Max retry test"}).json()["goal"]["goal_id"]
        aid = client.post(f"/v1/goals/{goal_id}/actions", json={"title": "Keep failing"}).json()["action"]["action_id"]
        # Retry 3 times (max_retries=3 default)
        for i in range(3):
            client.post(f"/v1/goals/{goal_id}/actions/{aid}/retry", json={"failure_reason": f"Fail {i}"})
        # 4th retry should say can_retry=False
        resp = client.post(f"/v1/goals/{goal_id}/actions/{aid}/retry", json={"failure_reason": "Final fail"})
        assert resp.json()["can_retry"] is False

    def test_follow_up_added_to_goal(self, client):
        goal_id = client.post("/v1/goals", json={"title": "Follow-up goal"}).json()["goal"]["goal_id"]
        resp = client.post(f"/v1/goals/{goal_id}/follow-up", json={
            "description": "Check with investor about funding",
        })
        assert resp.status_code == 200
        fu = resp.json()["follow_up"]
        assert fu["status"] == "pending"
        assert "id" in fu


# ---------------------------------------------------------------------------
# G3 — Approval gate tests
# ---------------------------------------------------------------------------

class TestGoalApprovalGates:
    def test_risky_action_requires_approval(self, client):
        goal_id = client.post("/v1/goals", json={"title": "Approval gate goal"}).json()["goal"]["goal_id"]
        resp = client.post(f"/v1/goals/{goal_id}/actions", json={
            "title": "Deploy to production",
            "action_type": "execute",
            "requires_approval": True,
        })
        action = resp.json()["action"]
        assert action["requires_approval"] is True

    def test_non_risky_action_no_approval(self, client):
        goal_id = client.post("/v1/goals", json={"title": "No approval goal"}).json()["goal"]["goal_id"]
        resp = client.post(f"/v1/goals/{goal_id}/actions", json={
            "title": "Read documentation",
            "action_type": "research",
            "requires_approval": False,
        })
        action = resp.json()["action"]
        assert action["requires_approval"] is False

    def test_goal_via_frontdoor_long_horizon_intent(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from openjarvis.server.frontdoor_routes import router
        app = FastAPI()
        app.include_router(router)
        fd_client = TestClient(app)
        resp = fd_client.post("/v1/frontdoor/submit", json={
            "user_input": "Build $10k MRR SaaS business in 90 days",
            "intent": "long_horizon_goal",
            "risk_level": "medium",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] == "long_horizon_goal"
        assert data["status"] == "accepted"

    def test_list_goals_by_status(self, client):
        client.post("/v1/goals", json={"title": "Active goal 1"})
        client.post("/v1/goals", json={"title": "Active goal 2"})
        resp = client.get("/v1/goals?status=active")
        goals = resp.json()["goals"]
        assert len(goals) >= 2
        assert all(g["status"] == "active" for g in goals)
