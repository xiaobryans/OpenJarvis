"""Mega Sprint 2 — Mission Control: store methods, new API routes, notifier.

Covers:
  1. MissionStore.list_all_tasks_by_status  (cross-mission, status filter)
  2. MissionStore.update_task_status        (persist + return value)
  3. MissionStore.list_recent_events        (cross-mission, DESC order, limit)
  4. GET  /v1/tasks/pending-approval        (empty and populated)
  5. PATCH /v1/tasks/{task_id}/approve      (status → assigned, event, mission advance)
  6. PATCH /v1/tasks/{task_id}/deny         (status → cancelled, event, mission advance)
  7. GET  /v1/agents                        (12 agents from SpecialistRegistry)
  8. GET  /v1/events/recent                 (cross-mission, limit)
  9. GET  /v1/notify/status                 (no tokens exposed)
 10. POST /v1/notify/slack                  (not configured → ok:false, no network call)
 11. POST /v1/notify/telegram               (not configured → ok:false, no network call)

No real Slack or Telegram network calls are made.  All tests use isolated stores.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.core.events import reset_event_bus
from openjarvis.mission.agent_registry import SpecialistRegistry, _EXPECTED_AGENT_IDS
from openjarvis.mission.models import MissionStatus, TaskStatus
from openjarvis.mission.router import MissionRouter
from openjarvis.mission.store import MissionStore


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_globals() -> None:
    SpecialistRegistry.clear()
    reset_event_bus()


@pytest.fixture
def tmp_store(tmp_path):
    db = str(tmp_path / "sprint2_test.db")
    store = MissionStore(db_path=db)
    yield store
    store.close()


@pytest.fixture
def mr(tmp_store):
    return MissionRouter(store=tmp_store, emit_to_bus=False)


@pytest.fixture
def client(tmp_store, mr, monkeypatch):
    """TestClient backed by a fresh in-memory store; module singletons patched."""
    import openjarvis.server.mission_routes as mission_mod
    import openjarvis.server.notify_routes as notify_mod  # noqa: F401 — ensure import

    monkeypatch.setattr(mission_mod, "_store", tmp_store)
    monkeypatch.setattr(mission_mod, "_mission_router", mr)

    app = FastAPI()
    app.include_router(mission_mod.router)
    app.include_router(notify_mod.router)
    return TestClient(app)


@pytest.fixture
def deploy_mission(mr, tmp_store):
    """Create a mission with deploy+email objective so awaiting_approval tasks exist."""
    plan = mr.create_mission("research, code, deploy, send email, and document results")
    return plan


# ===========================================================================
# 1. MissionStore.list_all_tasks_by_status
# ===========================================================================


def test_list_all_tasks_by_status_empty(tmp_store):
    tasks = tmp_store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    assert tasks == []


def test_list_all_tasks_by_status_found(tmp_store, deploy_mission):
    pending = tmp_store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    assert len(pending) >= 2
    assert all(t.status == TaskStatus.AWAITING_APPROVAL for t in pending)


def test_list_all_tasks_by_status_cross_mission(tmp_store, mr):
    mr.create_mission("deploy the service")
    mr.create_mission("deploy another service")
    pending = tmp_store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    mission_ids = {t.mission_id for t in pending}
    assert len(mission_ids) == 2


def test_list_all_tasks_by_status_assigned_only(tmp_store, mr):
    plan = mr.create_mission("research and document something")
    assigned = tmp_store.list_all_tasks_by_status(TaskStatus.ASSIGNED)
    assert len(assigned) >= 1
    assert all(t.status == TaskStatus.ASSIGNED for t in assigned)


# ===========================================================================
# 2. MissionStore.update_task_status
# ===========================================================================


def test_update_task_status_approve(tmp_store, deploy_mission):
    pending = tmp_store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    assert pending
    task = pending[0]
    result = tmp_store.update_task_status(task.id, TaskStatus.ASSIGNED)
    assert result is True
    fetched = tmp_store.get_task(task.id)
    assert fetched is not None
    assert fetched.status == TaskStatus.ASSIGNED


def test_update_task_status_deny(tmp_store, deploy_mission):
    pending = tmp_store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    assert pending
    task = pending[0]
    result = tmp_store.update_task_status(task.id, TaskStatus.CANCELLED)
    assert result is True
    fetched = tmp_store.get_task(task.id)
    assert fetched.status == TaskStatus.CANCELLED


def test_update_task_status_not_found(tmp_store):
    result = tmp_store.update_task_status("nonexistent_id_abc123", TaskStatus.ASSIGNED)
    assert result is False


def test_update_task_status_updates_timestamp(tmp_store, deploy_mission):
    import time
    pending = tmp_store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    task = pending[0]
    old_updated_at = task.updated_at
    time.sleep(0.01)
    tmp_store.update_task_status(task.id, TaskStatus.ASSIGNED)
    fetched = tmp_store.get_task(task.id)
    assert fetched.updated_at >= old_updated_at


# ===========================================================================
# 3. MissionStore.list_recent_events
# ===========================================================================


def test_list_recent_events_empty(tmp_store):
    events = tmp_store.list_recent_events()
    assert events == []


def test_list_recent_events_populated(tmp_store, mr):
    mr.create_mission("research and document outcomes")
    events = tmp_store.list_recent_events()
    assert len(events) >= 1


def test_list_recent_events_cross_mission(tmp_store, mr):
    mr.create_mission("research task one")
    mr.create_mission("research task two")
    events = tmp_store.list_recent_events(limit=200)
    mission_ids = {e.mission_id for e in events}
    assert len(mission_ids) == 2


def test_list_recent_events_desc_order(tmp_store, mr):
    mr.create_mission("research the first")
    mr.create_mission("research the second")
    events = tmp_store.list_recent_events(limit=200)
    assert len(events) >= 2
    for i in range(len(events) - 1):
        assert events[i].created_at >= events[i + 1].created_at


def test_list_recent_events_limit(tmp_store, mr):
    mr.create_mission("research alpha")
    mr.create_mission("research beta")
    mr.create_mission("research gamma")
    events = tmp_store.list_recent_events(limit=3)
    assert len(events) <= 3


# ===========================================================================
# 4. GET /v1/tasks/pending-approval
# ===========================================================================


def test_pending_approval_empty(client):
    resp = client.get("/v1/tasks/pending-approval")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["tasks"] == []


def test_pending_approval_populated(client):
    client.post(
        "/v1/missions",
        json={"objective": "deploy the service and send email to team"},
    )
    resp = client.get("/v1/tasks/pending-approval")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 2
    assert all(t["status"] == "awaiting_approval" for t in data["tasks"])


# ===========================================================================
# 5. PATCH /v1/tasks/{task_id}/approve
# ===========================================================================


def test_approve_task(client, tmp_store):
    create_resp = client.post(
        "/v1/missions",
        json={"objective": "deploy the service"},
    )
    assert create_resp.status_code == 200
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]
    assert pending, "Expected at least one awaiting_approval task from deploy objective"

    task_id = pending[0]["id"]
    resp = client.patch(f"/v1/tasks/{task_id}/approve")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "assigned"
    assert body["task_id"] == task_id

    task = tmp_store.get_task(task_id)
    assert task.status == TaskStatus.ASSIGNED


def test_approve_nonexistent_task(client):
    resp = client.patch("/v1/tasks/does_not_exist_xyz/approve")
    assert resp.status_code == 404


def test_approve_clears_mission_awaiting_status(client, tmp_store):
    """When the last awaiting_approval task for a mission is approved, the
    mission status should advance from awaiting_approval to running."""
    create_resp = client.post(
        "/v1/missions",
        json={"objective": "deploy service"},
    )
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]

    for t in pending:
        resp = client.patch(f"/v1/tasks/{t['id']}/approve")
        assert resp.status_code == 200

    mission_id = create_resp.json()["mission"]["id"]
    mission = tmp_store.get_mission(mission_id)
    assert mission.status == MissionStatus.RUNNING


def test_approve_emits_event(client, tmp_store):
    create_resp = client.post(
        "/v1/missions",
        json={"objective": "deploy the feature"},
    )
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]
    task_id = pending[0]["id"]
    mission_id = create_resp.json()["mission"]["id"]

    client.patch(f"/v1/tasks/{task_id}/approve")

    events = tmp_store.list_events(mission_id)
    event_types = [e.event_type for e in events]
    assert "task_approved" in event_types


# ===========================================================================
# 6. PATCH /v1/tasks/{task_id}/deny
# ===========================================================================


def test_deny_task(client, tmp_store):
    create_resp = client.post(
        "/v1/missions",
        json={"objective": "deploy the service"},
    )
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]
    assert pending

    task_id = pending[0]["id"]
    resp = client.patch(f"/v1/tasks/{task_id}/deny")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "cancelled"

    task = tmp_store.get_task(task_id)
    assert task.status == TaskStatus.CANCELLED


def test_deny_nonexistent_task(client):
    resp = client.patch("/v1/tasks/does_not_exist_abc/deny")
    assert resp.status_code == 404


def test_deny_emits_event(client, tmp_store):
    create_resp = client.post(
        "/v1/missions",
        json={"objective": "deploy the feature"},
    )
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]
    task_id = pending[0]["id"]
    mission_id = create_resp.json()["mission"]["id"]

    client.patch(f"/v1/tasks/{task_id}/deny")

    events = tmp_store.list_events(mission_id)
    event_types = [e.event_type for e in events]
    assert "task_cancelled" in event_types


def test_deny_all_clears_mission_awaiting_status(client, tmp_store):
    """Denying all awaiting_approval tasks should also advance mission status."""
    create_resp = client.post(
        "/v1/missions",
        json={"objective": "deploy service"},
    )
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]

    for t in pending:
        resp = client.patch(f"/v1/tasks/{t['id']}/deny")
        assert resp.status_code == 200

    mission_id = create_resp.json()["mission"]["id"]
    mission = tmp_store.get_mission(mission_id)
    assert mission.status == MissionStatus.RUNNING


# ===========================================================================
# 7. GET /v1/agents
# ===========================================================================


def test_agents_returns_12(client):
    resp = client.get("/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 12
    assert len(data["agents"]) == 12


def test_agents_expected_ids(client):
    resp = client.get("/v1/agents")
    agent_ids = {a["agent_id"] for a in resp.json()["agents"]}
    assert agent_ids == _EXPECTED_AGENT_IDS


def test_agents_required_fields(client):
    resp = client.get("/v1/agents")
    for a in resp.json()["agents"]:
        assert "agent_id" in a
        assert "display_name" in a
        assert "role" in a
        assert "status" in a
        assert "permission_level" in a


# ===========================================================================
# 8. GET /v1/events/recent
# ===========================================================================


def test_recent_events_empty(client):
    resp = client.get("/v1/events/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 0
    assert data["events"] == []


def test_recent_events_populated(client):
    client.post("/v1/missions", json={"objective": "research and document outcomes"})
    resp = client.get("/v1/events/recent?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] > 0


def test_recent_events_limit_respected(client):
    client.post("/v1/missions", json={"objective": "research the thing"})
    client.post("/v1/missions", json={"objective": "research another thing"})
    resp = client.get("/v1/events/recent?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()["events"]) <= 2


def test_recent_events_limit_capped_at_500(client):
    resp = client.get("/v1/events/recent?limit=9999")
    assert resp.status_code == 200


# ===========================================================================
# 9. GET /v1/notify/status
# ===========================================================================


def test_notify_status_unconfigured(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("JARVIS_TELEGRAM_CHAT_ID", raising=False)
    resp = client.get("/v1/notify/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "slack" in data
    assert "telegram" in data
    assert data["slack"]["configured"] is False
    assert data["telegram"]["configured"] is False


def test_notify_status_no_token_exposure(client, monkeypatch):
    monkeypatch.setenv("OPENCLAW_SLACK_BOT_TOKEN", "xoxb-real-looking-token-12345")
    monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "1234567890:ABCdef-fake-token")
    monkeypatch.setenv("JARVIS_TELEGRAM_CHAT_ID", "-100123456789")
    resp = client.get("/v1/notify/status")
    body = resp.text
    assert "xoxb-real-looking-token-12345" not in body
    assert "ABCdef-fake-token" not in body


# ===========================================================================
# 10. POST /v1/notify/slack — no real network call, not configured
# ===========================================================================


def test_notify_slack_not_configured(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
    resp = client.post("/v1/notify/slack", json={"message": "test message"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error_type"] == "not_configured"


def test_notify_slack_placeholder_token_not_configured(client, monkeypatch):
    monkeypatch.setenv("OPENCLAW_SLACK_BOT_TOKEN", "xoxb-your-token-here")
    resp = client.post("/v1/notify/slack", json={"message": "test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["error_type"] == "not_configured"


def test_notify_slack_empty_message_rejected(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
    resp = client.post("/v1/notify/slack", json={"message": ""})
    assert resp.status_code == 422


# ===========================================================================
# 11. POST /v1/notify/telegram — no real network call, not configured
# ===========================================================================


def test_notify_telegram_not_configured(client, monkeypatch):
    monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("JARVIS_TELEGRAM_CHAT_ID", raising=False)
    resp = client.post("/v1/notify/telegram", json={"message": "test message"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error_type"] == "not_configured"


def test_notify_telegram_partial_config_not_configured(client, monkeypatch):
    monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "1234567890:ABCdef")
    monkeypatch.delenv("JARVIS_TELEGRAM_CHAT_ID", raising=False)
    resp = client.post("/v1/notify/telegram", json={"message": "test"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["error_type"] == "not_configured"


def test_notify_telegram_empty_message_rejected(client, monkeypatch):
    resp = client.post("/v1/notify/telegram", json={"message": ""})
    assert resp.status_code == 422
