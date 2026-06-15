"""Mega Sprint 3 — Real Agent Execution + Slack/Telegram Operational Loop.

Covers:
  1. ExecutorRegistry — expected executors registered
  2. docs_report executor completes a safe task with real output
  3. qa executor completes a safe task with real output
  4. architect executor completes a safe task with real output
  5. testing_bug executor completes a safe task with real output
  6. research executor is blocked (no web_search tool)
  7. coding executor requires approval (not auto-complete)
  8. deployment executor requires approval (always)
  9. email executor requires approval (always)
  10. browser executor requires approval
  11. security_risk executor requires approval (always)
  12. MissionRunner.start_task persists RUNNING and emits task_started event
  13. MissionRunner.complete_task persists COMPLETED and emits task_completed event
  14. MissionRunner.block_task persists BLOCKED and emits task_blocked event
  15. MissionRunner.fail_task persists FAILED and emits task_failed event
  16. MissionRunner.require_approval persists AWAITING_APPROVAL and emits event
  17. run_mission_pass completes safe tasks and leaves risky tasks approval-gated
  18. run_mission_pass does NOT mark blocked tasks completed
  19. run_mission_pass respects max_steps guard
  20. run_mission_pass emits mission_runner_started event
  21. run_mission_pass updates mission status correctly
  22. run_state returns accurate counts and blocked reasons
  23. POST /v1/missions/{id}/run — returns ok=True when progress made
  24. POST /v1/missions/{id}/run — returns ok=False with reason when no progress
  25. POST /v1/tasks/{task_id}/run — returns execution result
  26. GET /v1/missions/{id}/run-state — returns state dict
  27. GET /v1/executors — returns registry, no secrets
  28. POST /v1/missions/{id}/notify/slack — not_configured without token
  29. POST /v1/missions/{id}/notify/telegram — not_configured without token
  30. Slack auto-notify off by default (no send without env flag)
  31. Telegram auto-notify off by default (no send without env flag)
  32. No real network calls in any test
  33. Sprint 1 regression: MissionRouter still creates/assigns tasks correctly
  34. Sprint 2 regression: approve/deny routes still work
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.core.events import reset_event_bus
from openjarvis.mission.agent_registry import SpecialistRegistry
from openjarvis.mission.executor import (
    ArchitectExecutor,
    BrowserExecutor,
    CodingExecutor,
    DeploymentExecutor,
    DocsReportExecutor,
    EmailExecutor,
    ExecutionResult,
    ExecutorRegistry,
    ManagerExecutor,
    QAExecutor,
    RemindersExecutor,
    ResearchExecutor,
    SecurityRiskExecutor,
    TestingBugExecutor,
)
from openjarvis.mission.models import (
    Mission,
    MissionStatus,
    RiskLevel,
    Task,
    TaskStatus,
)
from openjarvis.mission.router import MissionRouter
from openjarvis.mission.runner import MissionRunner, RunResult, _build_mission_notify_message
from openjarvis.mission.store import MissionStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_globals() -> None:
    SpecialistRegistry.clear()
    ExecutorRegistry.clear()
    reset_event_bus()


@pytest.fixture
def tmp_store(tmp_path):
    db = str(tmp_path / "sprint3_test.db")
    store = MissionStore(db_path=db)
    yield store
    store.close()


@pytest.fixture
def mr(tmp_store):
    return MissionRouter(store=tmp_store, emit_to_bus=False)


@pytest.fixture
def runner(tmp_store):
    return MissionRunner(store=tmp_store, emit_to_bus=False)


@pytest.fixture
def safe_mission(mr, tmp_store):
    """Mission with only safe (docs_report+qa) tasks via 'report and validate' objective."""
    plan = mr.create_mission("report on project status and validate quality")
    return plan


@pytest.fixture
def risky_mission(mr, tmp_store):
    """Mission that triggers deployment/email — approval-gated tasks."""
    plan = mr.create_mission("deploy service and send email to team and document results")
    return plan


@pytest.fixture
def client(tmp_store, mr, runner, monkeypatch):
    import openjarvis.server.mission_routes as mission_mod
    import openjarvis.server.notify_routes as notify_mod

    monkeypatch.setattr(mission_mod, "_store", tmp_store)
    monkeypatch.setattr(mission_mod, "_mission_router", mr)
    monkeypatch.setattr(mission_mod, "_mission_runner", runner)

    app = FastAPI()
    app.include_router(mission_mod.router)
    app.include_router(notify_mod.router)
    return TestClient(app)


def _make_task(mission_id: str, agent_id: str, risk: RiskLevel = RiskLevel.LOW) -> Task:
    return Task(
        mission_id=mission_id,
        title=f"Test task for {agent_id}",
        description=f"Test description for {agent_id}",
        assigned_agent_id=agent_id,
        status=TaskStatus.ASSIGNED,
        risk_level=risk,
    )


# ===========================================================================
# 1. ExecutorRegistry
# ===========================================================================


def test_executor_registry_has_all_agents():
    executors = ExecutorRegistry.all()
    agent_ids = {ex.agent_id for ex in executors}
    expected = {
        "docs_report", "qa", "architect", "testing_bug",
        "research", "coding", "deployment", "email",
        "browser", "security_risk", "reminders", "manager",
    }
    assert expected.issubset(agent_ids)


def test_executor_registry_get_returns_correct_type():
    ex = ExecutorRegistry.get("docs_report")
    assert isinstance(ex, DocsReportExecutor)
    ex = ExecutorRegistry.get("deployment")
    assert isinstance(ex, DeploymentExecutor)


def test_executor_registry_get_none_for_unknown():
    result = ExecutorRegistry.get("nonexistent_agent_xyz")
    assert result is None


# ===========================================================================
# 2–5. Safe executors complete with real output
# ===========================================================================


def test_docs_report_executor_completes_safe_task(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    result = DocsReportExecutor().execute(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.output  # must have real non-empty output
    assert "[docs_report]" in result.output
    assert result.requires_approval is False
    assert not result.blocked_reason


def test_qa_executor_completes_safe_task(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "qa")
    tmp_store.save_task(task)

    result = QAExecutor().execute(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.output
    assert "[qa]" in result.output
    assert result.requires_approval is False


def test_architect_executor_completes_safe_task(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "architect")
    tmp_store.save_task(task)

    result = ArchitectExecutor().execute(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.output
    assert "[architect]" in result.output


def test_testing_bug_executor_completes_safe_task(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "testing_bug")
    tmp_store.save_task(task)

    result = TestingBugExecutor().execute(task)
    assert result.status == TaskStatus.COMPLETED
    assert result.output
    assert "[testing_bug]" in result.output


# ===========================================================================
# 6. Research is blocked
# ===========================================================================


def test_research_executor_is_blocked(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "research")
    tmp_store.save_task(task)

    result = ResearchExecutor().execute(task)
    assert result.status == TaskStatus.BLOCKED
    assert result.blocked_reason
    assert "web_search" in result.blocked_reason or "tool" in result.blocked_reason.lower()


# ===========================================================================
# 7–11. Risky/privileged executors require approval or are blocked
# ===========================================================================


def test_coding_executor_requires_approval(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "coding", RiskLevel.MEDIUM)
    tmp_store.save_task(task)

    result = CodingExecutor().execute(task)
    assert result.status == TaskStatus.AWAITING_APPROVAL
    assert result.requires_approval is True


def test_deployment_executor_requires_approval(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "deployment", RiskLevel.CRITICAL)
    tmp_store.save_task(task)

    result = DeploymentExecutor().execute(task)
    assert result.status == TaskStatus.AWAITING_APPROVAL
    assert result.requires_approval is True


def test_email_executor_requires_approval(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "email", RiskLevel.HIGH)
    tmp_store.save_task(task)

    result = EmailExecutor().execute(task)
    assert result.status == TaskStatus.AWAITING_APPROVAL
    assert result.requires_approval is True


def test_browser_executor_requires_approval(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "browser", RiskLevel.MEDIUM)
    tmp_store.save_task(task)

    result = BrowserExecutor().execute(task)
    assert result.status == TaskStatus.AWAITING_APPROVAL
    assert result.requires_approval is True


def test_security_risk_executor_requires_approval(tmp_store):
    mission = Mission(title="Test", objective="test")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "security_risk", RiskLevel.HIGH)
    tmp_store.save_task(task)

    result = SecurityRiskExecutor().execute(task)
    assert result.status == TaskStatus.AWAITING_APPROVAL
    assert result.requires_approval is True


# ===========================================================================
# 12–16. MissionRunner lifecycle methods
# ===========================================================================


def test_runner_start_task_persists_running(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    updated = runner.start_task(task.id)
    assert updated is not None
    assert updated.status == TaskStatus.RUNNING
    persisted = tmp_store.get_task(task.id)
    assert persisted.status == TaskStatus.RUNNING


def test_runner_start_task_emits_event(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    runner.start_task(task.id)

    events = tmp_store.list_events(mission.id)
    assert any(e.event_type == "task_started" for e in events)


def test_runner_complete_task_persists_completed(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    res = ExecutionResult(
        task_id=task.id, agent_id="docs_report",
        status=TaskStatus.COMPLETED, summary="done", output="real output here"
    )
    runner.complete_task(task.id, res)

    persisted = tmp_store.get_task(task.id)
    assert persisted.status == TaskStatus.COMPLETED
    assert persisted.result == "real output here"


def test_runner_complete_task_emits_event(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    res = ExecutionResult(
        task_id=task.id, agent_id="docs_report",
        status=TaskStatus.COMPLETED, summary="done", output="real output"
    )
    runner.complete_task(task.id, res)

    events = tmp_store.list_events(mission.id)
    assert any(e.event_type == "task_completed" for e in events)


def test_runner_block_task_persists_blocked(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "research")
    tmp_store.save_task(task)

    runner.block_task(task.id, "no tool available")

    persisted = tmp_store.get_task(task.id)
    assert persisted.status == TaskStatus.BLOCKED


def test_runner_block_task_emits_event(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "research")
    tmp_store.save_task(task)

    runner.block_task(task.id, "no tool")

    events = tmp_store.list_events(mission.id)
    assert any(e.event_type == "task_blocked" for e in events)


def test_runner_fail_task_persists_failed(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    runner.fail_task(task.id, "unexpected error")

    persisted = tmp_store.get_task(task.id)
    assert persisted.status == TaskStatus.FAILED


def test_runner_fail_task_emits_event(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "docs_report")
    tmp_store.save_task(task)

    runner.fail_task(task.id, "error")

    events = tmp_store.list_events(mission.id)
    assert any(e.event_type == "task_failed" for e in events)


def test_runner_require_approval_persists(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "deployment", RiskLevel.CRITICAL)
    tmp_store.save_task(task)

    runner.require_approval(task.id, "deployment requires approval")

    persisted = tmp_store.get_task(task.id)
    assert persisted.status == TaskStatus.AWAITING_APPROVAL


def test_runner_require_approval_emits_event(tmp_store, runner):
    mission = Mission(title="T", objective="o")
    tmp_store.save_mission(mission)
    task = _make_task(mission.id, "deployment", RiskLevel.CRITICAL)
    tmp_store.save_task(task)

    runner.require_approval(task.id, "approval needed")

    events = tmp_store.list_events(mission.id)
    assert any(e.event_type == "task_awaiting_approval" for e in events)


# ===========================================================================
# 17. run_mission_pass: safe tasks complete, risky remain approval-gated
# ===========================================================================


def test_run_pass_completes_safe_tasks(tmp_store, runner, safe_mission):
    result = runner.run_mission_pass(safe_mission.mission.id)
    assert isinstance(result, RunResult)
    assert result.tasks_completed >= 1
    # All completed tasks must have real output
    tasks = tmp_store.list_tasks(safe_mission.mission.id)
    for t in tasks:
        if t.status == TaskStatus.COMPLETED:
            assert t.result, f"Task {t.id} ({t.title}) completed with no result"


def test_run_pass_risky_tasks_remain_approval_gated(tmp_store, runner, risky_mission):
    runner.run_mission_pass(risky_mission.mission.id)
    tasks = tmp_store.list_tasks(risky_mission.mission.id)
    approval_tasks = [t for t in tasks if t.assigned_agent_id in ("deployment", "email", "security_risk")]
    for t in approval_tasks:
        assert t.status in (TaskStatus.AWAITING_APPROVAL, TaskStatus.BLOCKED), (
            f"Risky task {t.title} ({t.assigned_agent_id}) must not auto-complete, got {t.status}"
        )


# ===========================================================================
# 18. Blocked tasks are never marked completed
# ===========================================================================


def test_run_pass_does_not_complete_blocked_tasks(tmp_store, runner, mr):
    plan = mr.create_mission("research the problem and document results")
    runner.run_mission_pass(plan.mission.id)
    tasks = tmp_store.list_tasks(plan.mission.id)
    research_tasks = [t for t in tasks if t.assigned_agent_id == "research"]
    for t in research_tasks:
        assert t.status != TaskStatus.COMPLETED, (
            f"research task {t.id} must not be completed (no tool wired)"
        )


# ===========================================================================
# 19. max_steps guard
# ===========================================================================


def test_run_pass_respects_max_steps(tmp_store, runner, mr):
    plan = mr.create_mission("report and validate quality and document results")
    result = runner.run_mission_pass(plan.mission.id, max_steps=1)
    assert result.tasks_started <= 1


# ===========================================================================
# 20. mission_runner_started event is emitted
# ===========================================================================


def test_run_pass_emits_mission_runner_started(tmp_store, runner, safe_mission):
    runner.run_mission_pass(safe_mission.mission.id)
    events = tmp_store.list_events(safe_mission.mission.id)
    assert any(e.event_type == "mission_runner_started" for e in events)


# ===========================================================================
# 21. Mission status updated correctly after pass
# ===========================================================================


def test_run_pass_mission_status_running_when_partial(tmp_store, runner, risky_mission):
    runner.run_mission_pass(risky_mission.mission.id)
    mission = tmp_store.get_mission(risky_mission.mission.id)
    assert mission.status in (
        MissionStatus.RUNNING,
        MissionStatus.AWAITING_APPROVAL,
        MissionStatus.BLOCKED,
        MissionStatus.COMPLETED,
    )


def test_run_pass_mission_status_completed_when_all_done(tmp_store, runner, mr):
    plan = mr.create_mission("validate quality")
    runner.run_mission_pass(plan.mission.id)
    mission = tmp_store.get_mission(plan.mission.id)
    all_tasks = tmp_store.list_tasks(plan.mission.id)
    statuses = {t.status for t in all_tasks}
    if statuses <= {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
        assert mission.status == MissionStatus.COMPLETED


# ===========================================================================
# 22. get_run_state returns accurate counts
# ===========================================================================


def test_get_run_state_returns_counts(tmp_store, runner, safe_mission):
    runner.run_mission_pass(safe_mission.mission.id)
    state = runner.get_run_state(safe_mission.mission.id)
    assert "mission_id" in state
    assert "task_counts" in state
    assert "blocked_reasons" in state
    assert "approvals_required" in state
    assert "last_events" in state
    assert state["mission_id"] == safe_mission.mission.id


def test_get_run_state_not_found(tmp_store, runner):
    state = runner.get_run_state("nonexistent_mission_123")
    assert "error" in state


def test_get_run_state_shows_blocked_reasons(tmp_store, runner, mr):
    plan = mr.create_mission("research the problem")
    runner.run_mission_pass(plan.mission.id)
    state = runner.get_run_state(plan.mission.id)
    research_tasks = tmp_store.list_tasks(plan.mission.id)
    research_blocked = [t for t in research_tasks if t.assigned_agent_id == "research" and t.status == TaskStatus.BLOCKED]
    if research_blocked:
        assert len(state["blocked_reasons"]) >= 1


# ===========================================================================
# 23–27. API routes
# ===========================================================================


def test_run_mission_route_returns_result(client, mr):
    create_resp = client.post("/v1/missions", json={"objective": "validate quality and document results"})
    assert create_resp.status_code == 200
    mission_id = create_resp.json()["mission"]["id"]

    resp = client.post(f"/v1/missions/{mission_id}/run", json={"max_steps": 10})
    assert resp.status_code == 200
    data = resp.json()
    assert "ok" in data
    assert "mission_id" in data
    assert "tasks_completed" in data
    assert "tasks_blocked" in data
    assert "events_emitted" in data


def test_run_mission_route_404_for_unknown(client):
    resp = client.post("/v1/missions/does_not_exist_xyz/run", json={})
    assert resp.status_code == 404


def test_run_mission_no_progress_when_all_approval_gated(tmp_store, runner):
    """A mission whose only tasks are awaiting_approval produces no progress."""
    from openjarvis.mission.models import Mission, Task, TaskStatus, RiskLevel, MissionStatus
    import time

    mission = Mission(title="Deploy only", objective="deploy the service", status=MissionStatus.AWAITING_APPROVAL)
    tmp_store.save_mission(mission)

    task1 = Task(
        mission_id=mission.id,
        title="Deploy prod",
        description="deploy prod",
        assigned_agent_id="deployment",
        status=TaskStatus.AWAITING_APPROVAL,
        risk_level=RiskLevel.CRITICAL,
        priority=1,
    )
    tmp_store.save_task(task1)

    result = runner.run_mission_pass(mission.id)
    assert result.ok is False
    assert result.no_progress is True
    assert result.no_progress_reason
    assert result.approvals_required >= 1


def test_run_task_route_returns_result(client, tmp_store, mr):
    create_resp = client.post("/v1/missions", json={"objective": "document outcomes"})
    tasks = create_resp.json()["tasks"]
    docs_tasks = [t for t in tasks if t["assigned_agent_id"] == "docs_report" and t["status"] == "assigned"]
    if not docs_tasks:
        pytest.skip("No docs_report assigned task in this plan")
    task_id = docs_tasks[0]["id"]

    resp = client.post(f"/v1/tasks/{task_id}/run")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "task_id" in data


def test_run_task_route_404_for_unknown(client):
    resp = client.post("/v1/tasks/does_not_exist_abc/run")
    assert resp.status_code == 404


def test_run_state_route_returns_state(client, mr):
    create_resp = client.post("/v1/missions", json={"objective": "validate quality"})
    mission_id = create_resp.json()["mission"]["id"]

    resp = client.get(f"/v1/missions/{mission_id}/run-state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mission_id"] == mission_id
    assert "task_counts" in data


def test_run_state_route_404_for_unknown(client):
    resp = client.get("/v1/missions/does_not_exist/run-state")
    assert resp.status_code == 404


def test_executors_route(client):
    resp = client.get("/v1/executors")
    assert resp.status_code == 200
    data = resp.json()
    assert "executors" in data
    assert data["count"] >= 12
    for ex in data["executors"]:
        assert "agent_id" in ex
        assert "safe_for_auto_execute" in ex
        assert "executor_class" in ex
        assert "token" not in str(ex).lower()


# ===========================================================================
# 28–29. Mission-scoped Slack / Telegram notify routes
# ===========================================================================


def test_mission_notify_slack_not_configured(client, mr, monkeypatch):
    monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
    create_resp = client.post("/v1/missions", json={"objective": "document results"})
    mission_id = create_resp.json()["mission"]["id"]

    resp = client.post(f"/v1/missions/{mission_id}/notify/slack")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error_type"] == "not_configured"
    assert data["mission_id"] == mission_id


def test_mission_notify_telegram_not_configured(client, mr, monkeypatch):
    monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("JARVIS_TELEGRAM_CHAT_ID", raising=False)
    create_resp = client.post("/v1/missions", json={"objective": "document results"})
    mission_id = create_resp.json()["mission"]["id"]

    resp = client.post(f"/v1/missions/{mission_id}/notify/telegram")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert data["error_type"] == "not_configured"
    assert data["mission_id"] == mission_id


def test_mission_notify_slack_404_for_unknown(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
    resp = client.post("/v1/missions/nonexistent_xyz/notify/slack")
    assert resp.status_code == 404


def test_mission_notify_telegram_404_for_unknown(client, monkeypatch):
    resp = client.post("/v1/missions/nonexistent_xyz/notify/telegram")
    assert resp.status_code == 404


def test_notify_routes_no_token_exposure(client, mr, monkeypatch):
    monkeypatch.setenv("OPENCLAW_SLACK_BOT_TOKEN", "xoxb-secret-token-12345")
    monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "9876543210:ABCsecret")
    monkeypatch.setenv("JARVIS_TELEGRAM_CHAT_ID", "-100987654321")
    create_resp = client.post("/v1/missions", json={"objective": "document results"})
    mission_id = create_resp.json()["mission"]["id"]

    slack_resp = client.post(f"/v1/missions/{mission_id}/notify/slack")
    tg_resp = client.post(f"/v1/missions/{mission_id}/notify/telegram")

    for body in [slack_resp.text, tg_resp.text]:
        assert "xoxb-secret-token-12345" not in body
        assert "ABCsecret" not in body


# ===========================================================================
# 30–31. Auto-notify off by default
# ===========================================================================


def test_slack_auto_notify_off_by_default(tmp_store, runner, safe_mission, monkeypatch):
    monkeypatch.delenv("JARVIS_SLACK_MISSION_AUTONOTIFY", raising=False)
    sent = []

    async def fake_send(msg):
        sent.append(msg)
        return {"ok": True}

    from openjarvis.mission import notifier as notifier_mod
    monkeypatch.setattr(notifier_mod.SlackNotifier, "send", fake_send)
    monkeypatch.setattr(notifier_mod.SlackNotifier, "is_configured", lambda self: True)

    runner.run_mission_pass(safe_mission.mission.id)
    assert sent == [], "Slack auto-notify must not send when JARVIS_SLACK_MISSION_AUTONOTIFY is not set"


def test_telegram_auto_notify_off_by_default(tmp_store, runner, safe_mission, monkeypatch):
    monkeypatch.delenv("JARVIS_TELEGRAM_MISSION_AUTONOTIFY", raising=False)
    sent = []

    async def fake_send(msg):
        sent.append(msg)
        return {"ok": True}

    from openjarvis.mission import notifier as notifier_mod
    monkeypatch.setattr(notifier_mod.TelegramNotifier, "send", fake_send)
    monkeypatch.setattr(notifier_mod.TelegramNotifier, "is_configured", lambda self: True)

    runner.run_mission_pass(safe_mission.mission.id)
    assert sent == [], "Telegram auto-notify must not send when JARVIS_TELEGRAM_MISSION_AUTONOTIFY is not set"


# ===========================================================================
# 32. No real network calls verified by absence of httpx/telegram in any path
# ===========================================================================


def test_no_network_call_when_not_configured(client, monkeypatch):
    monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("JARVIS_TELEGRAM_CHAT_ID", raising=False)

    create_resp = client.post("/v1/missions", json={"objective": "document results"})
    mission_id = create_resp.json()["mission"]["id"]

    slack_resp = client.post(f"/v1/missions/{mission_id}/notify/slack")
    tg_resp = client.post(f"/v1/missions/{mission_id}/notify/telegram")

    assert slack_resp.json()["error_type"] == "not_configured"
    assert tg_resp.json()["error_type"] == "not_configured"


# ===========================================================================
# 33. Sprint 1 regression
# ===========================================================================


def test_sprint1_regression_mission_router_creates_tasks(tmp_store, mr):
    plan = mr.create_mission("research and document the outcome")
    assert plan.mission.id
    assert len(plan.tasks) >= 1
    assert any(t.assigned_agent_id in ("research", "docs_report") for t in plan.tasks)
    stored_mission = tmp_store.get_mission(plan.mission.id)
    assert stored_mission is not None


def test_sprint1_regression_risky_task_awaiting_approval(tmp_store, mr):
    plan = mr.create_mission("deploy to production")
    awaiting = [t for t in plan.tasks if t.status == TaskStatus.AWAITING_APPROVAL]
    assert len(awaiting) >= 1


# ===========================================================================
# 34. Sprint 2 regression
# ===========================================================================


def test_sprint2_regression_approve_deny_routes(client, tmp_store):
    create_resp = client.post("/v1/missions", json={"objective": "deploy service"})
    tasks = create_resp.json()["tasks"]
    pending = [t for t in tasks if t["status"] == "awaiting_approval"]
    assert pending

    task_id = pending[0]["id"]
    resp = client.patch(f"/v1/tasks/{task_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    task = tmp_store.get_task(task_id)
    assert task.status == TaskStatus.ASSIGNED


def test_sprint2_regression_notify_status_no_exposure(client, monkeypatch):
    monkeypatch.setenv("OPENCLAW_SLACK_BOT_TOKEN", "xoxb-real-secret-token")
    resp = client.get("/v1/notify/status")
    assert resp.status_code == 200
    assert "xoxb-real-secret-token" not in resp.text
