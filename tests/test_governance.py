"""Governance Constitution + Policy Enforcement Tests.

Covers:
  1.  Hard gates always return UNSAFE — no policy exception overrides
  2.  Always-approval agents require approval regardless of risk level
  3.  High/critical risk level requires approval
  4.  Low/medium risk + non-gated agent is SAFE
  5.  ACCEPT requires concrete verified evidence — not assumption alone
  6.  HOLD when evidence is missing
  7.  HOLD when evidence is insufficient
  8.  HOLD when evidence list is empty
  9.  UNSAFE action classification via gate_check
  10. REQUIRES_APPROVAL action classification via gate_check
  11. SAFE action classification via gate_check
  12. validate_completion rejects empty output
  13. validate_completion rejects whitespace-only output
  14. validate_completion accepts non-empty output
  15. OMNIX is registered as Project 1 in ProjectRegistry
  16. ProjectRegistry supports multiple concurrent projects
  17. OMNIX is not the whole system — a second project can be added
  18. ProjectRegistry.get_default() returns OMNIX (priority=1)
  19. ProjectProfile has all required fields
  20. OMNIX deploy_gates include production-critical actions
  21. project_gate_check blocks project-specific deploy gates
  22. project_gate_check allows non-gated actions
  23. audit_log scrubs sensitive keys
  24. audit_log never exposes token/secret values
  25. completion_refusal_reason returns non-empty governance string
  26. insufficient_data_message returns standard phrase
  27. build_blocker produces structured Blocker with all fields
  28. Blocker.can_continue_partially is explicit
  29. governance wired into router: router uses governance requires_approval
  30. governance wired into runner: runner refuses COMPLETED with empty output
  31. Sprint 1+2+3 regression: mission tests still pass (key samples)
"""

from __future__ import annotations

import pytest

from openjarvis.governance.constitution import (
    ALWAYS_APPROVAL_AGENTS,
    APPROVAL_REQUIRED_RISK_LEVELS,
    HARD_GATE_ACTIONS,
    OMNIX_PROJECT,
    ActionCategory,
    Blocker,
    Evidence,
    EvidenceStatus,
    ProjectProfile,
    ProjectRegistry,
    Verdict,
)
from openjarvis.governance.policies import (
    audit_log,
    build_blocker,
    check_action_category,
    classify_verdict,
    completion_refusal_reason,
    gate_check,
    insufficient_data_message,
    is_hard_gate,
    is_sufficient_evidence,
    project_gate_check,
    requires_approval,
    validate_completion,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registry():
    ProjectRegistry.clear()
    yield
    ProjectRegistry.clear()


# ===========================================================================
# 1–4. Risk / Approval Gate checks
# ===========================================================================


def test_hard_gate_actions_are_non_negotiable():
    for action in HARD_GATE_ACTIONS:
        assert is_hard_gate(action), f"{action} must be a hard gate"


def test_hard_gate_check_returns_unsafe():
    for action in HARD_GATE_ACTIONS:
        result = gate_check(action, agent_id="docs_report", risk_level="low")
        assert result["verdict"] == Verdict.UNSAFE.value, (
            f"gate_check('{action}') must return UNSAFE"
        )
        assert not result["allowed"]
        assert result["requires_approval"] is True


def test_always_approval_agents_require_approval_at_any_risk():
    for agent in ALWAYS_APPROVAL_AGENTS:
        for risk in ("low", "medium", "high", "critical"):
            assert requires_approval(risk, agent), (
                f"Agent '{agent}' must always require approval (risk={risk})"
            )


def test_high_risk_requires_approval_for_any_agent():
    for risk in ("high", "critical"):
        assert requires_approval(risk, "docs_report")
        assert requires_approval(risk, "qa")
        assert requires_approval(risk, "architect")


def test_low_medium_risk_safe_agent_does_not_require_approval():
    for risk in ("low", "medium"):
        for agent in ("docs_report", "qa", "architect", "testing_bug"):
            assert not requires_approval(risk, agent), (
                f"Agent '{agent}' at risk '{risk}' should not require approval"
            )


def test_check_action_category_hard_gate():
    result = check_action_category("real_slack_send")
    assert result == ActionCategory.HARD_GATE


def test_check_action_category_requires_approval():
    result = check_action_category("deploy_something", risk_level="critical", agent_id="deployment")
    assert result == ActionCategory.REQUIRES_APPROVAL


def test_check_action_category_safe():
    result = check_action_category("generate_report", risk_level="low", agent_id="docs_report")
    assert result == ActionCategory.SAFE


# ===========================================================================
# 5–8. Verdict classification — ACCEPT requires verified evidence
# ===========================================================================


def test_accept_requires_verified_evidence():
    evidence = [
        Evidence("Test suite passed", EvidenceStatus.VERIFIED, source="pytest"),
        Evidence("Build artifact exists", EvidenceStatus.VERIFIED, source="filesystem"),
    ]
    assert classify_verdict(evidence) == Verdict.ACCEPT


def test_accept_not_returned_on_assumption_alone():
    evidence = [
        Evidence("Assumed tests passed", EvidenceStatus.ASSUMED),
    ]
    result = classify_verdict(evidence)
    assert result != Verdict.ACCEPT, "ACCEPT must not be returned on assumption alone"
    assert result == Verdict.HOLD


def test_hold_when_evidence_missing():
    evidence = [
        Evidence("Verified output", EvidenceStatus.VERIFIED),
        Evidence("Missing config file", EvidenceStatus.MISSING),
    ]
    assert classify_verdict(evidence) == Verdict.HOLD


def test_hold_when_evidence_insufficient():
    evidence = [
        Evidence("Partial output", EvidenceStatus.INSUFFICIENT),
    ]
    assert classify_verdict(evidence) == Verdict.HOLD


def test_hold_when_evidence_list_empty():
    assert classify_verdict([]) == Verdict.HOLD


def test_is_sufficient_evidence_requires_all_verified():
    good = [Evidence("A", EvidenceStatus.VERIFIED), Evidence("B", EvidenceStatus.VERIFIED)]
    bad = [Evidence("A", EvidenceStatus.VERIFIED), Evidence("B", EvidenceStatus.ASSUMED)]
    empty = []
    assert is_sufficient_evidence(good) is True
    assert is_sufficient_evidence(bad) is False
    assert is_sufficient_evidence(empty) is False


# ===========================================================================
# 9–11. gate_check full classification
# ===========================================================================


def test_gate_check_hard_gate():
    result = gate_check("aws_infrastructure_change")
    assert result["verdict"] == Verdict.UNSAFE.value
    assert result["category"] == ActionCategory.HARD_GATE.value
    assert not result["allowed"]


def test_gate_check_requires_approval():
    result = gate_check("run_deployment_pipeline", risk_level="critical", agent_id="deployment")
    assert result["verdict"] == Verdict.HOLD.value
    assert result["category"] == ActionCategory.REQUIRES_APPROVAL.value
    assert not result["allowed"]
    assert result["requires_approval"] is True


def test_gate_check_safe():
    result = gate_check("generate_report", risk_level="low", agent_id="docs_report")
    assert result["verdict"] == Verdict.ACCEPT.value
    assert result["category"] == ActionCategory.SAFE.value
    assert result["allowed"] is True
    assert result["requires_approval"] is False


# ===========================================================================
# 12–14. validate_completion — no fake work
# ===========================================================================


def test_validate_completion_rejects_empty():
    assert validate_completion("") is False


def test_validate_completion_rejects_whitespace():
    assert validate_completion("   ") is False
    assert validate_completion("\n\t") is False


def test_validate_completion_accepts_real_output():
    assert validate_completion("[docs_report] Report generated.") is True
    assert validate_completion("any non-empty content") is True


# ===========================================================================
# 15–20. ProjectRegistry — multi-project, OMNIX as Project 1
# ===========================================================================


def test_omnix_is_registered_as_project_1():
    projects = ProjectRegistry.list_projects()
    ids = [p.project_id for p in projects]
    assert "omnix" in ids


def test_omnix_has_priority_1():
    omnix = ProjectRegistry.get("omnix")
    assert omnix is not None
    assert omnix.priority == 1


def test_project_registry_supports_multiple_projects():
    ProjectRegistry.register(ProjectProfile(
        project_id="project_b",
        display_name="Project B",
        priority=2,
    ))
    ProjectRegistry.register(ProjectProfile(
        project_id="project_c",
        display_name="Project C",
        priority=3,
    ))
    projects = ProjectRegistry.list_active()
    ids = {p.project_id for p in projects}
    assert "omnix" in ids
    assert "project_b" in ids
    assert "project_c" in ids
    assert len(ids) >= 3


def test_omnix_is_not_the_whole_system():
    """Architecture must support ≥2 concurrent projects."""
    ProjectRegistry.register(ProjectProfile(
        project_id="future_startup",
        display_name="Future Startup",
        priority=2,
    ))
    projects = ProjectRegistry.list_active()
    assert len(projects) >= 2
    # OMNIX is a project, not the system
    default = ProjectRegistry.get_default()
    assert default.project_id == "omnix"
    # The system also knows about future_startup
    other = ProjectRegistry.get("future_startup")
    assert other is not None
    assert other.project_id == "future_startup"


def test_get_default_returns_omnix():
    default = ProjectRegistry.get_default()
    assert default.project_id == "omnix"


def test_project_profile_has_all_required_fields():
    p = ProjectRegistry.get("omnix")
    assert p is not None
    assert p.project_id
    assert p.display_name
    assert isinstance(p.repo_path, str)
    assert isinstance(p.docs_paths, list)
    assert isinstance(p.handoff_paths, list)
    assert isinstance(p.slack_channels, list)
    assert isinstance(p.telegram_chat_ids, list)
    assert isinstance(p.telegram_alert_rules, dict)
    assert isinstance(p.deploy_gates, list)
    assert isinstance(p.test_commands, list)
    assert isinstance(p.forbidden_paths, list)
    assert isinstance(p.agent_assignments, dict)
    assert isinstance(p.priority, int)
    assert isinstance(p.memory_namespace, str)
    assert isinstance(p.active, bool)


def test_omnix_deploy_gates_include_critical_actions():
    omnix = ProjectRegistry.get("omnix")
    assert omnix is not None
    gates = omnix.deploy_gates
    assert "omnix_production_deploy" in gates
    assert "aws_infrastructure_change" in gates
    assert "billing_change" in gates


def test_project_memory_namespace_isolated():
    ProjectRegistry.register(ProjectProfile(
        project_id="proj_x", display_name="X", priority=5,
    ))
    omnix = ProjectRegistry.get("omnix")
    proj_x = ProjectRegistry.get("proj_x")
    assert omnix.memory_namespace != proj_x.memory_namespace
    assert omnix.memory_namespace == "project:omnix"
    assert proj_x.memory_namespace == "project:proj_x"


# ===========================================================================
# 21–22. project_gate_check
# ===========================================================================


def test_project_gate_check_blocks_deploy_gate():
    result = project_gate_check("omnix", "omnix_production_deploy")
    assert not result["allowed"]
    assert result["verdict"] == Verdict.UNSAFE.value


def test_project_gate_check_allows_non_gated_action():
    result = project_gate_check("omnix", "generate_report")
    assert result["allowed"]
    assert result["verdict"] == Verdict.ACCEPT.value


def test_project_gate_check_returns_hold_for_unknown_project():
    result = project_gate_check("nonexistent_project_xyz", "some_action")
    assert not result["allowed"]
    assert result["verdict"] == Verdict.HOLD.value


# ===========================================================================
# 23–24. audit_log scrubs secrets
# ===========================================================================


def test_audit_log_scrubs_sensitive_keys():
    record = audit_log(
        "send_message",
        "docs_report",
        "ACCEPT",
        context={
            "bot_token": "xoxb-secret-12345",
            "chat_id": "123456",
            "message": "hello",
            "api_key": "sk-secret",
        },
    )
    ctx = record["context"]
    assert ctx["bot_token"] == "<redacted>"
    assert ctx["api_key"] == "<redacted>"
    assert ctx["message"] == "hello"


def test_audit_log_never_exposes_secret():
    record = audit_log(
        "deploy",
        "deployment",
        "UNSAFE",
        context={"token": "super-secret-value", "env": "production"},
    )
    import json
    serialized = json.dumps(record)
    assert "super-secret-value" not in serialized


# ===========================================================================
# 25–28. Utility helpers
# ===========================================================================


def test_completion_refusal_reason_is_non_empty():
    msg = completion_refusal_reason()
    assert isinstance(msg, str)
    assert len(msg) > 20
    assert "COMPLETED" in msg or "complete" in msg.lower()


def test_insufficient_data_message_standard_phrase():
    msg = insufficient_data_message()
    assert "Insufficient data" in msg

    msg_ctx = insufficient_data_message("test results missing")
    assert "test results missing" in msg_ctx
    assert "Insufficient data" in msg_ctx


def test_build_blocker_all_fields():
    b = build_blocker(
        blocker="web_search tool not wired",
        why_it_matters="research agent cannot fetch external data",
        unblock_path="implement WebSearchTool, register in ExecutorRegistry",
        can_continue_partially=True,
        partial_scope="documentation tasks can still proceed",
    )
    assert isinstance(b, Blocker)
    assert b.blocker == "web_search tool not wired"
    assert b.why_it_matters
    assert b.unblock_path
    assert b.can_continue_partially is True
    assert b.partial_scope


def test_blocker_can_continue_partially_is_explicit():
    b = build_blocker(
        blocker="email tool missing",
        why_it_matters="cannot send notifications",
        unblock_path="configure SMTP credentials",
    )
    assert b.can_continue_partially is False
    assert b.partial_scope == ""


# ===========================================================================
# 29. Governance wired into router
# ===========================================================================


def test_governance_wired_into_router(tmp_path):
    """router._requires_approval delegates to governance policy."""
    from openjarvis.mission.router import _requires_approval as router_requires
    from openjarvis.mission.models import RiskLevel

    # hard-gated agents
    assert router_requires(RiskLevel.LOW, "deployment") is True
    assert router_requires(RiskLevel.LOW, "email") is True
    assert router_requires(RiskLevel.LOW, "security_risk") is True

    # high/critical risk
    assert router_requires(RiskLevel.HIGH, "docs_report") is True
    assert router_requires(RiskLevel.CRITICAL, "qa") is True

    # safe: low/medium + safe agent
    assert router_requires(RiskLevel.LOW, "docs_report") is False
    assert router_requires(RiskLevel.MEDIUM, "qa") is False


def test_governance_router_consistent_with_governance_policy():
    """router._requires_approval and policies.requires_approval must agree."""
    from openjarvis.mission.router import _requires_approval as router_req
    from openjarvis.mission.models import RiskLevel

    test_cases = [
        (RiskLevel.LOW, "docs_report"),
        (RiskLevel.LOW, "deployment"),
        (RiskLevel.HIGH, "qa"),
        (RiskLevel.CRITICAL, "architect"),
        (RiskLevel.MEDIUM, "coding"),
        (RiskLevel.LOW, "security_risk"),
    ]
    for risk, agent in test_cases:
        gov = requires_approval(risk.value, agent)
        rtr = router_req(risk, agent)
        assert gov == rtr, (
            f"Governance and router disagree on ({risk.value}, {agent}): "
            f"governance={gov}, router={rtr}"
        )


# ===========================================================================
# 30. Governance wired into runner
# ===========================================================================


def test_runner_refuses_completed_with_empty_output(tmp_path):
    """MissionRunner._persist_result refuses COMPLETED if output is empty."""
    from openjarvis.mission.models import Mission, Task, TaskStatus, RiskLevel
    from openjarvis.mission.executor import ExecutionResult
    from openjarvis.mission.runner import MissionRunner
    from openjarvis.mission.store import MissionStore

    db = str(tmp_path / "runner_gov_test.db")
    store = MissionStore(db_path=db)
    runner = MissionRunner(store=store, emit_to_bus=False)

    mission = Mission(title="T", objective="o")
    store.save_mission(mission)
    task = Task(
        mission_id=mission.id,
        title="Empty output task",
        description="test",
        assigned_agent_id="docs_report",
        status=TaskStatus.RUNNING,
        risk_level=RiskLevel.LOW,
    )
    store.save_task(task)

    fake_result = ExecutionResult(
        task_id=task.id,
        agent_id="docs_report",
        status=TaskStatus.COMPLETED,
        summary="done",
        output="",
    )
    result = runner._persist_result(task, fake_result)

    assert result.status == TaskStatus.BLOCKED, (
        "Runner must refuse COMPLETED with empty output — governance enforcement"
    )
    persisted = store.get_task(task.id)
    assert persisted.status == TaskStatus.BLOCKED
    store.close()


def test_runner_accepts_completed_with_real_output(tmp_path):
    """MissionRunner._persist_result accepts COMPLETED if output is non-empty."""
    from openjarvis.mission.models import Mission, Task, TaskStatus, RiskLevel
    from openjarvis.mission.executor import ExecutionResult
    from openjarvis.mission.runner import MissionRunner
    from openjarvis.mission.store import MissionStore

    db = str(tmp_path / "runner_gov_ok.db")
    store = MissionStore(db_path=db)
    runner = MissionRunner(store=store, emit_to_bus=False)

    mission = Mission(title="T", objective="o")
    store.save_mission(mission)
    task = Task(
        mission_id=mission.id,
        title="Real output task",
        description="test",
        assigned_agent_id="docs_report",
        status=TaskStatus.RUNNING,
        risk_level=RiskLevel.LOW,
    )
    store.save_task(task)

    good_result = ExecutionResult(
        task_id=task.id,
        agent_id="docs_report",
        status=TaskStatus.COMPLETED,
        summary="done",
        output="[docs_report] Real deterministic output produced.",
    )
    result = runner._persist_result(task, good_result)

    assert result.status == TaskStatus.COMPLETED
    store.close()


# ===========================================================================
# 31. Sprint 1+2+3 regression samples (lightweight)
# ===========================================================================


def test_sprint_regression_router_creates_mission(tmp_path):
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.router import MissionRouter

    store = MissionStore(db_path=str(tmp_path / "r.db"))
    mr = MissionRouter(store=store, emit_to_bus=False)
    plan = mr.create_mission("validate quality and document results")
    assert plan.mission.id
    assert len(plan.tasks) >= 1
    store.close()


def test_sprint_regression_deployment_still_approval_gated(tmp_path):
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.router import MissionRouter
    from openjarvis.mission.models import TaskStatus

    store = MissionStore(db_path=str(tmp_path / "d.db"))
    mr = MissionRouter(store=store, emit_to_bus=False)
    plan = mr.create_mission("deploy to production")
    approval_tasks = [t for t in plan.tasks if t.status == TaskStatus.AWAITING_APPROVAL]
    assert approval_tasks, "Deployment must still be approval-gated after governance wiring"
    store.close()


def test_sprint_regression_safe_task_completes(tmp_path):
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.router import MissionRouter
    from openjarvis.mission.runner import MissionRunner
    from openjarvis.mission.models import TaskStatus

    store = MissionStore(db_path=str(tmp_path / "s.db"))
    mr = MissionRouter(store=store, emit_to_bus=False)
    runner = MissionRunner(store=store, emit_to_bus=False)
    plan = mr.create_mission("document project status")
    runner.run_mission_pass(plan.mission.id)
    tasks = store.list_tasks(plan.mission.id)
    completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    assert completed, "Safe docs_report task must still complete after governance wiring"
    for t in completed:
        assert t.result, "Completed task must have non-empty result (governance enforcement)"
    store.close()
