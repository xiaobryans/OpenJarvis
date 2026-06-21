"""Plan 7 Phase C Gate Tests — Personal Life OS.

Gate C requirements:
  - Personal task lifecycle tests
  - Memory-informed planning tests
  - Approval/follow-up tests
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from openjarvis.server.life_os_routes import router
    from openjarvis.jarvis_os.personal_os import get_personal_task_store, PersonalTaskStore
    # Fresh store per test
    import openjarvis.jarvis_os.personal_os as _m
    _m._store = PersonalTaskStore()
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# C1 — Personal task lifecycle
# ---------------------------------------------------------------------------

class TestPersonalTaskLifecycle:
    def test_create_task(self, client):
        resp = client.post("/v1/life-os/tasks", json={
            "title": "Call dentist",
            "description": "Schedule annual checkup",
            "priority": "medium",
            "tags": ["health"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["created"] is True
        assert data["task"]["title"] == "Call dentist"
        assert data["task"]["status"] == "pending"
        assert "task_id" in data["task"]

    def test_create_high_priority_task(self, client):
        resp = client.post("/v1/life-os/tasks", json={
            "title": "Renew passport",
            "priority": "high",
            "tags": ["admin", "urgent"],
        })
        assert resp.status_code == 200
        assert resp.json()["task"]["priority"] == "high"

    def test_list_tasks_returns_created(self, client):
        client.post("/v1/life-os/tasks", json={"title": "Task Alpha", "priority": "low"})
        client.post("/v1/life-os/tasks", json={"title": "Task Beta", "priority": "high"})
        resp = client.get("/v1/life-os/tasks")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        titles = [t["title"] for t in tasks]
        assert "Task Alpha" in titles
        assert "Task Beta" in titles

    def test_get_single_task(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={"title": "Get me", "priority": "medium"})
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.get(f"/v1/life-os/tasks/{task_id}")
        assert resp.status_code == 200
        assert resp.json()["task"]["task_id"] == task_id

    def test_get_nonexistent_task_404(self, client):
        resp = client.get("/v1/life-os/tasks/does_not_exist")
        assert resp.status_code == 404

    def test_update_task_status_to_in_progress(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={"title": "Start me", "priority": "medium"})
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.post(f"/v1/life-os/tasks/{task_id}/status", json={"status": "in_progress"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "in_progress"

    def test_update_task_status_to_done(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={"title": "Finish me", "priority": "low"})
        task_id = create_resp.json()["task"]["task_id"]
        client.post(f"/v1/life-os/tasks/{task_id}/status", json={"status": "in_progress"})
        resp = client.post(f"/v1/life-os/tasks/{task_id}/status", json={"status": "done"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    def test_invalid_priority_rejected(self, client):
        resp = client.post("/v1/life-os/tasks", json={"title": "Bad priority", "priority": "extreme"})
        assert resp.status_code == 400

    def test_empty_title_rejected(self, client):
        resp = client.post("/v1/life-os/tasks", json={"title": "", "priority": "medium"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# C2 — Memory-informed planning
# ---------------------------------------------------------------------------

class TestMemoryInformedPlanning:
    def test_task_accepts_memory_refs(self, client):
        resp = client.post("/v1/life-os/tasks", json={
            "title": "Prepare quarterly review",
            "priority": "high",
            "memory_refs": ["mem_q3_notes", "mem_kpi_targets"],
        })
        assert resp.status_code == 200
        task = resp.json()["task"]
        assert "mem_q3_notes" in task["memory_refs"]
        assert "mem_kpi_targets" in task["memory_refs"]

    def test_task_memory_refs_preserved_on_retrieve(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={
            "title": "Memory task",
            "priority": "low",
            "memory_refs": ["mem_context_abc"],
        })
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.get(f"/v1/life-os/tasks/{task_id}")
        assert "mem_context_abc" in resp.json()["task"]["memory_refs"]

    def test_filter_by_priority(self, client):
        client.post("/v1/life-os/tasks", json={"title": "High task", "priority": "high"})
        client.post("/v1/life-os/tasks", json={"title": "Low task", "priority": "low"})
        resp = client.get("/v1/life-os/tasks?priority=high")
        tasks = resp.json()["tasks"]
        assert all(t["priority"] == "high" for t in tasks)

    def test_daily_summary_reflects_tasks(self, client):
        client.post("/v1/life-os/tasks", json={"title": "Task 1", "priority": "high"})
        client.post("/v1/life-os/tasks", json={"title": "Task 2", "priority": "low"})
        resp = client.get("/v1/life-os/summary/daily")
        assert resp.status_code == 200
        summary = resp.json()["summary"]
        assert summary["tasks_high_priority"] >= 1
        assert "date" in summary
        assert "summary_text" in summary

    def test_task_with_scheduled_at(self, client):
        import time
        resp = client.post("/v1/life-os/tasks", json={
            "title": "Scheduled task",
            "priority": "medium",
            "scheduled_at": time.time() + 86400,
        })
        assert resp.status_code == 200
        task = resp.json()["task"]
        assert task["scheduled_at"] is not None


# ---------------------------------------------------------------------------
# C3 — Approval / follow-up
# ---------------------------------------------------------------------------

class TestApprovalAndFollowUp:
    def test_sensitive_task_created_in_waiting_approval_state(self, client):
        resp = client.post("/v1/life-os/tasks", json={
            "title": "Send invoice to client",
            "priority": "high",
            "approval_required": True,
        })
        assert resp.status_code == 200
        task = resp.json()["task"]
        assert task["status"] == "waiting_approval"
        assert task["approval_required"] is True
        assert task["approval_state"] == "pending_approval"

    def test_approve_sensitive_task_moves_to_pending(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={
            "title": "Sensitive action",
            "priority": "high",
            "approval_required": True,
        })
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.post(f"/v1/life-os/tasks/{task_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"
        assert resp.json()["approval_state"] == "approved"

    def test_approve_non_approval_task_rejected(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={
            "title": "Normal task",
            "priority": "low",
            "approval_required": False,
        })
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.post(f"/v1/life-os/tasks/{task_id}/approve")
        assert resp.status_code == 400

    def test_pending_approvals_endpoint(self, client):
        client.post("/v1/life-os/tasks", json={"title": "Needs approval", "priority": "high", "approval_required": True})
        resp = client.get("/v1/life-os/approvals/pending")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 1

    def test_set_reminder(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={"title": "Remind me", "priority": "medium"})
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.post(f"/v1/life-os/tasks/{task_id}/remind", json={
            "reminder_type": "time_based",
            "trigger": 1750000000.0,
            "notes": "Check email before this",
        })
        assert resp.status_code == 200
        reminder = resp.json()["reminder"]
        assert reminder["type"] == "time_based"
        assert reminder["notes"] == "Check email before this"

    def test_set_follow_up(self, client):
        create_resp = client.post("/v1/life-os/tasks", json={"title": "Follow up on contract", "priority": "high"})
        task_id = create_resp.json()["task"]["task_id"]
        resp = client.post(f"/v1/life-os/tasks/{task_id}/follow-up", json={
            "description": "Check if contract was signed",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["follow_up_state"]["status"] == "pending"
        assert "description" in data["follow_up_state"]

    def test_no_external_send_without_approval(self, client):
        """External send action is blocked — must require approval_required=True."""
        # An external send type task should require approval
        resp = client.post("/v1/life-os/tasks", json={
            "title": "Send email to client",
            "priority": "medium",
            "approval_required": True,
        })
        task = resp.json()["task"]
        assert task["status"] == "waiting_approval"  # gated, not sent

    def test_daily_summary_counts_approvals_and_follow_ups(self, client):
        client.post("/v1/life-os/tasks", json={"title": "Approve me", "priority": "high", "approval_required": True})
        create_resp = client.post("/v1/life-os/tasks", json={"title": "Follow up on me", "priority": "medium"})
        task_id = create_resp.json()["task"]["task_id"]
        client.post(f"/v1/life-os/tasks/{task_id}/follow-up", json={"description": "Call back"})
        resp = client.get("/v1/life-os/summary/daily")
        summary = resp.json()["summary"]
        assert summary["approvals_waiting"] >= 1
        assert summary["follow_ups_due"] >= 1
