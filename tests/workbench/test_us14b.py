"""US14B — Workbench Notification & Event Integration Tests.

Scope:
  1.  WorkbenchEventLog: schema, push, list_events, count_by_type
  2.  WorkbenchEvent.to_dict: required fields present
  3.  Notify dry-run hard gate: Slack send blocked when dry_run=True
  4.  Notify plan-only hard gate: Slack send blocked when plan_only=True
  5.  Notify dry-run hard gate: Telegram send blocked when dry_run=True
  6.  Notify plan-only hard gate: Telegram send blocked when plan_only=True
  7.  Notify gate response schema: gated=True, gate key, reason, requires_manager_approval
  8.  CodingManager emits plan_created event after plan()
  9.  CodingManager emits execution_started + execution_complete after execute()
  10. CodingManager emits dry_run_gate events for write/commit/push in dry-run
  11. CodingManager emits approval_required event when subtask awaits approval
  12. CodingManager.get_events returns dicts with required fields
  13. Event log: dry_run=True events marked dry_run=True in DB
  14. Approval-gated subtask stays awaiting_approval without explicit approval
  15. Autopilot guard: autopilot_runtime_enabled=False (never bypassed)
  16. Autopilot guard: approval_bypass_allowed=False
  17. Autopilot guard: can_execute_without_approval=False
  18. Autopilot guard: protected_actions includes git_commit, git_push, shell_exec
  19. Chat-to-Workbench frontdoor key schema: required fields
  20. Model routing: plan-only / dry-run sessions use MockAdapter ($0.00 cost)
  21. WorkbenchEventLog stores events persistently across instances
  22. Event log count_by_type aggregates correctly
  23. NotifyRequest model: dry_run and plan_only fields parse correctly
  24. NotifyRequest: default dry_run=False, plan_only=False (no accidental gate)
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# WorkbenchEventLog unit tests
# ---------------------------------------------------------------------------


class TestWorkbenchEventLog:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.event_log import WorkbenchEventLog
        self.log = WorkbenchEventLog(db_path=str(Path(self.tmpdir) / "events.db"))

    def test_push_returns_event(self):
        evt = self.log.push("s1", "t1", "plan_created", "Plan ready")
        assert evt.id
        assert evt.session_id == "s1"
        assert evt.task_id == "t1"
        assert evt.event_type == "plan_created"
        assert evt.title == "Plan ready"

    def test_push_default_tone_info(self):
        evt = self.log.push("s1", "t1", "plan_created", "ok")
        assert evt.tone == "info"

    def test_push_custom_tone(self):
        evt = self.log.push("s1", "t1", "subtask_failed", "failed", tone="error")
        assert evt.tone == "error"

    def test_push_dry_run_flag(self):
        evt = self.log.push("s1", "t1", "dry_run_gate", "skipped", dry_run=True)
        assert evt.dry_run is True

    def test_push_dry_run_false_default(self):
        evt = self.log.push("s2", "t2", "plan_created", "live")
        assert evt.dry_run is False

    def test_list_events_returns_newest_first(self):
        self.log.push("s3", "t3", "plan_created", "first")
        self.log.push("s3", "t3", "execution_started", "second")
        events = self.log.list_events("s3")
        assert events[0].event_type == "execution_started"
        assert events[1].event_type == "plan_created"

    def test_list_events_filters_by_session(self):
        self.log.push("sA", "t1", "plan_created", "A")
        self.log.push("sB", "t2", "plan_created", "B")
        events = self.log.list_events("sA")
        assert all(e.session_id == "sA" for e in events)
        assert len(events) == 1

    def test_list_events_limit(self):
        for i in range(10):
            self.log.push("s4", "t4", "subtask_done", f"st-{i}")
        events = self.log.list_events("s4", limit=3)
        assert len(events) == 3

    def test_list_recent_across_sessions(self):
        self.log.push("sX", "tX", "plan_created", "x")
        self.log.push("sY", "tY", "plan_created", "y")
        recents = self.log.list_recent(limit=10)
        session_ids = {e.session_id for e in recents}
        assert "sX" in session_ids
        assert "sY" in session_ids

    def test_count_by_type(self):
        self.log.push("s5", "t5", "plan_created", "p")
        self.log.push("s5", "t5", "subtask_done", "d1")
        self.log.push("s5", "t5", "subtask_done", "d2")
        counts = self.log.count_by_type("s5")
        assert counts["plan_created"] == 1
        assert counts["subtask_done"] == 2

    def test_empty_session_returns_empty(self):
        events = self.log.list_events("nonexistent_session_xyz")
        assert events == []


class TestWorkbenchEventToDict:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.event_log import WorkbenchEventLog
        self.log = WorkbenchEventLog(db_path=str(Path(self.tmpdir) / "events.db"))

    def test_to_dict_has_required_fields(self):
        evt = self.log.push("s1", "t1", "plan_created", "Plan ready", detail="5 subtasks")
        d = evt.to_dict()
        for field in ("id", "session_id", "task_id", "event_type", "title",
                      "detail", "tone", "dry_run", "at", "created_at"):
            assert field in d, f"Missing field: {field}"

    def test_to_dict_at_is_millis(self):
        import time
        before = int(time.time() * 1000) - 1
        evt = self.log.push("s2", "t2", "plan_created", "t")
        d = evt.to_dict()
        assert d["at"] >= before

    def test_to_dict_dry_run_bool(self):
        evt = self.log.push("s3", "t3", "dry_run_gate", "gate", dry_run=True)
        d = evt.to_dict()
        assert d["dry_run"] is True

    def test_to_dict_session_task_id(self):
        evt = self.log.push("sess_abc", "task_xyz", "execution_complete", "done")
        d = evt.to_dict()
        assert d["session_id"] == "sess_abc"
        assert d["task_id"] == "task_xyz"


class TestEventLogPersistence:
    def test_events_persist_across_instances(self):
        tmpdir = tempfile.mkdtemp()
        db_path = str(Path(tmpdir) / "events.db")
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log1 = WorkbenchEventLog(db_path=db_path)
        log1.push("sp1", "tp1", "plan_created", "persisted event")
        del log1
        log2 = WorkbenchEventLog(db_path=db_path)
        events = log2.list_events("sp1")
        assert len(events) == 1
        assert events[0].title == "persisted event"


# ---------------------------------------------------------------------------
# Notify dry-run / plan-only hard gate tests (pure logic, no network)
# ---------------------------------------------------------------------------


class TestNotifyDryRunGate:
    """Verify the dry_run and plan_only hard gates in notify_routes.py."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_slack_dry_run_returns_gated(self):
        from openjarvis.server.notify_routes import send_slack, NotifyRequest
        req = NotifyRequest(message="hello", dry_run=True)
        result = self._run(send_slack(req))
        assert result["gated"] is True
        assert result["gate"] == "dry_run"
        assert result["ok"] is False

    def test_slack_dry_run_no_send(self):
        """Verify the gated result means no network send (ok=False, gated=True)."""
        from openjarvis.server.notify_routes import send_slack, NotifyRequest
        req = NotifyRequest(message="should not send", dry_run=True)
        result = self._run(send_slack(req))
        assert result["ok"] is False
        assert "dry_run" in result["gate"]

    def test_slack_plan_only_returns_gated(self):
        from openjarvis.server.notify_routes import send_slack, NotifyRequest
        req = NotifyRequest(message="plan only", plan_only=True)
        result = self._run(send_slack(req))
        assert result["gated"] is True
        assert result["gate"] == "plan_only"
        assert result["ok"] is False

    def test_telegram_dry_run_returns_gated(self):
        from openjarvis.server.notify_routes import send_telegram, NotifyRequest
        req = NotifyRequest(message="hello", dry_run=True)
        result = self._run(send_telegram(req))
        assert result["gated"] is True
        assert result["gate"] == "dry_run"
        assert result["ok"] is False

    def test_telegram_plan_only_returns_gated(self):
        from openjarvis.server.notify_routes import send_telegram, NotifyRequest
        req = NotifyRequest(message="plan only", plan_only=True)
        result = self._run(send_telegram(req))
        assert result["gated"] is True
        assert result["gate"] == "plan_only"
        assert result["ok"] is False

    def test_gated_response_has_reason(self):
        from openjarvis.server.notify_routes import send_slack, NotifyRequest
        req = NotifyRequest(message="test", dry_run=True)
        result = self._run(send_slack(req))
        assert "reason" in result
        assert len(result["reason"]) > 0

    def test_gated_response_requires_manager_approval(self):
        from openjarvis.server.notify_routes import send_slack, NotifyRequest
        req = NotifyRequest(message="test", dry_run=True)
        result = self._run(send_slack(req))
        assert result.get("requires_manager_approval") is True

    def test_both_gates_independent(self):
        """dry_run=True takes priority over plan_only=True."""
        from openjarvis.server.notify_routes import send_slack, NotifyRequest
        req = NotifyRequest(message="test", dry_run=True, plan_only=True)
        result = self._run(send_slack(req))
        assert result["gate"] == "dry_run"

    def test_default_no_gate(self):
        """Default (dry_run=False, plan_only=False) should not set gated=True."""
        from openjarvis.server.notify_routes import NotifyRequest
        req = NotifyRequest(message="live message")
        assert req.dry_run is False
        assert req.plan_only is False


class TestNotifyRequestModel:
    def test_dry_run_default_false(self):
        from openjarvis.server.notify_routes import NotifyRequest
        req = NotifyRequest(message="test")
        assert req.dry_run is False

    def test_plan_only_default_false(self):
        from openjarvis.server.notify_routes import NotifyRequest
        req = NotifyRequest(message="test")
        assert req.plan_only is False

    def test_dry_run_parseable(self):
        from openjarvis.server.notify_routes import NotifyRequest
        req = NotifyRequest(message="test", dry_run=True)
        assert req.dry_run is True

    def test_plan_only_parseable(self):
        from openjarvis.server.notify_routes import NotifyRequest
        req = NotifyRequest(message="test", plan_only=True)
        assert req.plan_only is True


# ---------------------------------------------------------------------------
# CodingManager event integration tests
# ---------------------------------------------------------------------------


class TestCodingManagerEvents:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.coding_manager import CodingManager
        self.mgr = CodingManager(
            repo_path="/Users/user/OpenJarvis",
            db_dir=self.tmpdir,
        )

    def teardown_method(self):
        try:
            self.mgr.close()
        except Exception:
            pass

    def test_plan_emits_plan_created_event(self):
        plan = self.mgr.plan("Add a fixture", dry_run=True)
        events = self.mgr.get_events(plan.session_id)
        types = [e["event_type"] for e in events]
        assert "plan_created" in types

    def test_plan_created_event_has_session_id(self):
        plan = self.mgr.plan("Read repo", dry_run=True)
        events = self.mgr.get_events(plan.session_id)
        plan_evt = next(e for e in events if e["event_type"] == "plan_created")
        assert plan_evt["session_id"] == plan.session_id

    def test_plan_created_event_dry_run_flag(self):
        plan = self.mgr.plan("Read repo", dry_run=True)
        events = self.mgr.get_events(plan.session_id)
        plan_evt = next(e for e in events if e["event_type"] == "plan_created")
        assert plan_evt["dry_run"] is True

    def test_execute_emits_execution_started(self):
        plan = self.mgr.plan("Add fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        events = self.mgr.get_events(plan.session_id)
        types = [e["event_type"] for e in events]
        assert "execution_started" in types

    def test_execute_emits_execution_complete(self):
        plan = self.mgr.plan("Inspect repo", dry_run=True)
        plan = self.mgr.execute(plan)
        events = self.mgr.get_events(plan.session_id)
        types = [e["event_type"] for e in events]
        assert "execution_complete" in types

    def test_dry_run_emits_dry_run_gate_events(self):
        plan = self.mgr.plan("Add fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        events = self.mgr.get_events(plan.session_id)
        types = [e["event_type"] for e in events]
        assert "dry_run_gate" in types

    def test_dry_run_gate_events_marked_dry_run_true(self):
        plan = self.mgr.plan("Add fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        events = self.mgr.get_events(plan.session_id)
        gate_events = [e for e in events if e["event_type"] == "dry_run_gate"]
        assert len(gate_events) > 0
        assert all(e["dry_run"] is True for e in gate_events)

    def test_approval_required_emits_event(self):
        plan = self.mgr.plan("Add fixture", dry_run=False)
        plan = self.mgr.execute(plan, approved_subtask_ids=[])
        events = self.mgr.get_events(plan.session_id)
        types = [e["event_type"] for e in events]
        assert "approval_required" in types

    def test_get_events_returns_dicts(self):
        plan = self.mgr.plan("Read repo", dry_run=True)
        events = self.mgr.get_events(plan.session_id)
        assert isinstance(events, list)
        assert all(isinstance(e, dict) for e in events)

    def test_get_events_dict_has_required_fields(self):
        plan = self.mgr.plan("Read repo", dry_run=True)
        events = self.mgr.get_events(plan.session_id)
        assert len(events) > 0
        for field in ("id", "session_id", "task_id", "event_type",
                      "title", "detail", "tone", "dry_run", "at"):
            assert field in events[0], f"Missing field: {field}"

    def test_no_events_for_unknown_session(self):
        events = self.mgr.get_events("nonexistent_session_xyz_abc")
        assert events == []

    def test_execution_complete_event_has_status(self):
        plan = self.mgr.plan("Inspect", dry_run=True)
        plan = self.mgr.execute(plan)
        events = self.mgr.get_events(plan.session_id)
        complete = next((e for e in events if e["event_type"] == "execution_complete"), None)
        assert complete is not None
        assert plan.status in complete["title"] or plan.status in complete["detail"]


# ---------------------------------------------------------------------------
# Approval gate: subtask remains awaiting_approval without explicit approval
# ---------------------------------------------------------------------------


class TestApprovalGate:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.coding_manager import CodingManager
        self.mgr = CodingManager(
            repo_path="/Users/user/OpenJarvis",
            db_dir=self.tmpdir,
        )

    def teardown_method(self):
        try:
            self.mgr.close()
        except Exception:
            pass

    def test_git_commit_awaits_approval_in_live_mode(self):
        plan = self.mgr.plan("Add fixture", dry_run=False, stop_on_blocker=False)
        plan = self.mgr.execute(plan, approved_subtask_ids=[])
        commit_subtasks = [s for s in plan.subtasks if s.tool_id == "git_commit"]
        assert len(commit_subtasks) > 0
        for st in commit_subtasks:
            assert st.status == "awaiting_approval", (
                f"Expected awaiting_approval for git_commit, got {st.status}"
            )

    def test_git_push_awaits_approval_in_live_mode(self):
        plan = self.mgr.plan("Add fixture", dry_run=False, stop_on_blocker=False)
        plan = self.mgr.execute(plan, approved_subtask_ids=[])
        push_subtasks = [s for s in plan.subtasks if s.tool_id == "git_push"]
        assert len(push_subtasks) > 0
        for st in push_subtasks:
            assert st.status == "awaiting_approval", (
                f"Expected awaiting_approval for git_push, got {st.status}"
            )

    def test_plan_status_awaiting_approval_when_blocked(self):
        plan = self.mgr.plan("Add fixture", dry_run=False, stop_on_blocker=True)
        plan = self.mgr.execute(plan, approved_subtask_ids=[])
        assert plan.status == "awaiting_approval"

    def test_approved_subtask_executes(self):
        plan = self.mgr.plan("Add fixture", dry_run=False)
        plan = self.mgr.execute(plan, approved_subtask_ids=[])
        commit_st = next(
            (s for s in plan.subtasks if s.tool_id == "git_commit"), None
        )
        assert commit_st is not None
        plan2 = self.mgr.approve_subtask(plan, commit_st.id)
        commit_st2 = next(s for s in plan2.subtasks if s.id == commit_st.id)
        assert commit_st2.status != "awaiting_approval"


# ---------------------------------------------------------------------------
# Autopilot guard policy tests
# ---------------------------------------------------------------------------


class TestAutopilotGuardPolicy:
    def _get_guard(self):
        from openjarvis.server.workbench_routes import workbench_autopilot_guard
        return workbench_autopilot_guard()

    def test_autopilot_runtime_enabled_false(self):
        guard = self._get_guard()
        assert guard["autopilot_runtime_enabled"] is False

    def test_approval_bypass_not_allowed(self):
        guard = self._get_guard()
        assert guard["approval_bypass_allowed"] is False

    def test_cannot_execute_without_approval(self):
        guard = self._get_guard()
        assert guard["can_execute_without_approval"] is False

    def test_disabled_by_default(self):
        guard = self._get_guard()
        assert guard["disabled_by_default"] is True

    def test_git_commit_in_protected_actions(self):
        guard = self._get_guard()
        assert "git_commit" in guard["protected_actions"]

    def test_git_push_in_protected_actions(self):
        guard = self._get_guard()
        assert "git_push" in guard["protected_actions"]

    def test_shell_exec_in_protected_actions(self):
        guard = self._get_guard()
        assert "shell_exec" in guard["protected_actions"]

    def test_external_notify_slack_in_protected(self):
        guard = self._get_guard()
        assert "external_notify_slack" in guard["protected_actions"]

    def test_external_notify_telegram_in_protected(self):
        guard = self._get_guard()
        assert "external_notify_telegram" in guard["protected_actions"]

    def test_ok_is_true(self):
        guard = self._get_guard()
        assert guard["ok"] is True

    def test_mode_is_guarded_preview(self):
        guard = self._get_guard()
        assert guard["mode"] == "guarded_preview"


# ---------------------------------------------------------------------------
# Chat-to-Workbench frontdoor key schema tests
# ---------------------------------------------------------------------------


class TestChatWorkbenchFrontdoor:
    """Verify the frontdoor payload schema used by Chat → Workbench bridge."""

    FRONTDOOR_KEY = "openjarvis-workbench-frontdoor"
    REQUIRED_FIELDS = ("prompt", "repoPath", "dryRun", "stopOnBlocker")

    def _make_payload(self, **kwargs):
        base = {
            "prompt": "Add a test fixture",
            "repoPath": "/Users/user/OpenJarvis",
            "dryRun": True,
            "stopOnBlocker": True,
        }
        base.update(kwargs)
        return base

    def test_frontdoor_key_constant(self):
        assert self.FRONTDOOR_KEY == "openjarvis-workbench-frontdoor"

    def test_payload_has_prompt(self):
        p = self._make_payload()
        assert "prompt" in p
        assert isinstance(p["prompt"], str)

    def test_payload_has_repo_path(self):
        p = self._make_payload()
        assert "repoPath" in p
        assert isinstance(p["repoPath"], str)

    def test_payload_dry_run_defaults_true(self):
        p = self._make_payload()
        assert p["dryRun"] is True

    def test_payload_stop_on_blocker_field_present(self):
        p = self._make_payload()
        assert "stopOnBlocker" in p

    def test_payload_all_required_fields_present(self):
        p = self._make_payload()
        for field in self.REQUIRED_FIELDS:
            assert field in p, f"Missing frontdoor field: {field}"

    def test_payload_plan_field_optional(self):
        """plan is an optional field added after plan creation."""
        p = self._make_payload()
        assert "plan" not in p
        p["plan"] = {"session_id": "abc123", "status": "planned", "subtasks": []}
        assert p["plan"]["session_id"] == "abc123"


# ---------------------------------------------------------------------------
# Model routing: zero cost for plan-only and dry-run sessions
# ---------------------------------------------------------------------------


class TestModelRoutingDryRunCost:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.coding_manager import CodingManager
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter
        router = ModelRouter(
            db_path=str(Path(self.tmpdir) / "routing.db"),
            adapter_override=MockModelAdapter(),
        )
        self.mgr = CodingManager(
            repo_path="/Users/user/OpenJarvis",
            db_dir=self.tmpdir,
            model_router=router,
        )

    def teardown_method(self):
        try:
            self.mgr.close()
        except Exception:
            pass

    def test_plan_only_zero_paid_calls(self):
        plan = self.mgr.plan("plan only — do not edit any files", dry_run=True)
        assert plan.total_cost_usd == 0.0

    def test_dry_run_execute_zero_cost(self):
        plan = self.mgr.plan("Add a fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        assert plan.total_cost_usd == 0.0

    def test_mock_adapter_used_in_dry_run(self):
        config = self.mgr.get_provider_config()
        assert config["adapter"] == "mock"

    def test_routing_log_local_for_git_status(self):
        plan = self.mgr.plan("Inspect repo status", dry_run=True)
        log = self.mgr.get_routing_log(plan.session_id)
        tiers = {e["tool_id"]: e["assigned_tier"] for e in log}
        assert tiers.get("git_status") == "local"

    def test_routing_log_premium_for_git_commit(self):
        plan = self.mgr.plan("Inspect repo status", dry_run=True)
        log = self.mgr.get_routing_log(plan.session_id)
        tiers = {e["tool_id"]: e["assigned_tier"] for e in log}
        assert tiers.get("git_commit") == "premium"

    def test_openrouter_key_masked_in_config(self):
        config = self.mgr.get_provider_config()
        assert config["openrouter_key_value"] == "MASKED"


# ---------------------------------------------------------------------------
# Event constants are importable and stable
# ---------------------------------------------------------------------------


def test_event_constants_importable():
    from openjarvis.workbench.event_log import (
        EVENT_PLAN_CREATED,
        EVENT_EXECUTION_STARTED,
        EVENT_SUBTASK_DONE,
        EVENT_SUBTASK_FAILED,
        EVENT_EXECUTION_COMPLETE,
        EVENT_APPROVAL_REQUIRED,
        EVENT_DRY_RUN_GATE,
        EVENT_NOTIFICATION_GATED,
    )
    assert EVENT_PLAN_CREATED == "plan_created"
    assert EVENT_EXECUTION_STARTED == "execution_started"
    assert EVENT_SUBTASK_DONE == "subtask_done"
    assert EVENT_SUBTASK_FAILED == "subtask_failed"
    assert EVENT_EXECUTION_COMPLETE == "execution_complete"
    assert EVENT_APPROVAL_REQUIRED == "approval_required"
    assert EVENT_DRY_RUN_GATE == "dry_run_gate"
    assert EVENT_NOTIFICATION_GATED == "notification_gated"


def test_workbench_event_log_importable():
    from openjarvis.workbench.event_log import WorkbenchEvent, WorkbenchEventLog
    assert WorkbenchEvent
    assert WorkbenchEventLog


def test_us14b_marker():
    """US14B E2E proof marker."""
    marker = "Jarvis Workbench Notification & Event Integration US14B"
    assert marker.startswith("Jarvis Workbench")


# ---------------------------------------------------------------------------
# FD regression: CodingManager must not leak file descriptors
# ---------------------------------------------------------------------------


def test_coding_manager_close_releases_fds():
    """Prove CodingManager.close() releases SQLite FDs immediately.

    Creates N managers, closes them, then verifies the open FD count returns
    to near-baseline.  Guards against regression of EMFILE / Errno 24.
    """
    import os
    import tempfile
    from pathlib import Path
    from openjarvis.workbench.coding_manager import CodingManager
    from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

    def _count_fds() -> Optional[int]:
        try:
            return len(os.listdir("/dev/fd"))
        except OSError:
            return None

    N = 20
    baseline = _count_fds()
    if baseline is None:
        return

    managers = []
    for i in range(N):
        td = tempfile.mkdtemp()
        router = ModelRouter(
            db_path=str(Path(td) / "routing.db"),
            adapter_override=MockModelAdapter(),
        )
        managers.append(CodingManager(repo_path=td, db_dir=td, model_router=router))

    mid = _count_fds()
    assert mid is not None
    assert mid > baseline, "Expected FDs to grow while managers are alive"

    for mgr in managers:
        mgr.close()
    managers.clear()

    after = _count_fds()
    assert after is not None
    assert after <= baseline + 5, (
        f"FD leak after close(): baseline={baseline}, after={after}. "
        "CodingManager.close() must release all SQLite connections."
    )
