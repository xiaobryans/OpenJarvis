"""NUS 1D — Eval Gates, Rollback, Approval Workflow, Power Autopilot Boundary tests.

Tests:
  - eval gate pass/fail
  - fail closed on missing evidence
  - rollback required for mutation
  - approval TTL/scope/deny
  - approval cannot override blocked categories
  - power_autopilot remains bounded
  - kill-switch behavior
  - doctor check passes
  - US13 remains parked
  - no self-modification, no auto-push/merge/deploy
"""

from __future__ import annotations

import time

import pytest


# ---------------------------------------------------------------------------
# 1. Eval Gate — pass / fail / fail-closed
# ---------------------------------------------------------------------------


class TestEvalGatePassFail:
    def test_pass_all_required(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_PASS
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="Run pytest tests/nus/",
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert report.all_passed, f"Failed gates: {report.failed_gates}"
        assert report.overall_outcome == GATE_PASS

    def test_fail_closed_missing_validation_plan(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_FAIL_CLOSED
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="",  # missing
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert report.overall_outcome == GATE_FAIL_CLOSED
        assert not report.all_passed

    def test_fail_closed_missing_safety_gate(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_FAIL_CLOSED
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="Run pytest",
            safety_gate_result=None,  # missing
        )
        report = run_eval_gate(c)
        assert report.overall_outcome == GATE_FAIL_CLOSED

    def test_fail_closed_missing_risk_level(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_FAIL_CLOSED
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="",  # invalid
            validation_plan="Run pytest",
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert report.overall_outcome == GATE_FAIL_CLOSED

    def test_blocked_action_fails_fast(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_FAIL_CLOSED
        c = EvalCandidate(
            action_type="deploy",
            risk_level="high",
            validation_plan="Run tests",
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert not report.all_passed
        # Blocked gate detected
        blocked_gates = [r for r in report.gate_results if r.gate_name == "blocked_action" and not r.passed]
        assert len(blocked_gates) >= 1

    @pytest.mark.parametrize("action", [
        "self_modification", "auto_push", "auto_merge", "deploy",
        "secret_access", "safety_policy_change", "production_action",
    ])
    def test_all_dangerous_fail_eval_gate(self, action):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        c = EvalCandidate(
            action_type=action,
            risk_level="critical",
            validation_plan="irrelevant",
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert not report.all_passed

    def test_rollback_required_for_mutation(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_FAIL_CLOSED
        c = EvalCandidate(
            action_type="file_write",
            risk_level="medium",
            validation_plan="Run lint",
            rollback_plan="",  # missing for mutation → fail closed
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert report.overall_outcome == GATE_FAIL_CLOSED

    def test_rollback_not_required_for_read(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_PASS
        c = EvalCandidate(
            action_type="local_read",
            risk_level="low",
            validation_plan="Run pytest",
            rollback_plan="",  # not required for reads
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert report.all_passed

    def test_capability_fail_when_not_ready(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="Run pytest",
            capability_id="some_capability",
            capability_ready=False,  # not ready
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert not report.all_passed

    def test_capability_fail_closed_when_none(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate, GATE_FAIL_CLOSED
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="Run pytest",
            capability_id="some_capability",
            capability_ready=None,  # None → fail closed
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        assert report.overall_outcome == GATE_FAIL_CLOSED

    def test_report_serializes(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        c = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="tests",
            safety_gate_result="pass",
        )
        report = run_eval_gate(c)
        d = report.to_dict()
        assert "report_id" in d
        assert "gate_results" in d
        assert "overall_outcome" in d


# ---------------------------------------------------------------------------
# 2. Rollback Enforcement
# ---------------------------------------------------------------------------


class TestRollbackEnforcement:
    def test_requires_rollback_for_mutation(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        assert e.requires_rollback("file_write") is True
        assert e.requires_rollback("auto_commit") is True
        assert e.requires_rollback("config_change") is True
        assert e.requires_rollback("schema_migration") is True

    def test_no_rollback_for_read(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        assert e.requires_rollback("local_read") is False
        assert e.requires_rollback("local_analysis") is False

    def test_create_plan(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        plan = e.create_plan(
            action_type="file_write",
            description="Revert status.json change",
            steps=["git checkout -- path/to/status.json"],
        )
        assert plan.plan_id
        assert plan.action_type == "file_write"
        assert plan.requires_approval_to_execute is True

    def test_check_precondition_pass(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        plan = e.create_plan("file_write", "Revert", ["git checkout -- f"])
        result = e.check_precondition("file_write", plan)
        assert result["ok"] is True

    def test_check_precondition_fail_closed_no_plan(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        result = e.check_precondition("file_write", None)
        assert result["ok"] is False
        assert result.get("fail_closed") is True

    def test_check_precondition_read_no_plan_ok(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        result = e.check_precondition("local_read", None)
        assert result["ok"] is True

    def test_real_rollback_execution_blocked(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        plan = e.create_plan("file_write", "Revert", [])
        result = e.execute_rollback(plan.plan_id)
        assert result["ok"] is False
        assert result.get("blocked") is True

    def test_dry_run_available(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        plan = e.create_plan("file_write", "Revert", ["git checkout"])
        result = e.execute_dry_run(plan.plan_id)
        assert result["ok"] is True
        assert result.get("dry_run") is True

    def test_destructive_rollback_requires_approval(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        plan = e.create_plan(
            action_type="file_write",
            description="Delete temp file",
            rollback_type="delete_file",
            is_destructive=True,
        )
        assert plan.is_destructive is True
        assert plan.requires_approval_to_execute is True
        assert plan.is_approved is False

    def test_approve_rollback_execution(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        e = RollbackEnforcer()
        plan = e.create_plan("file_write", "Revert", is_destructive=False)
        plan.approve_execution("bryan")
        assert plan.is_approved is True


# ---------------------------------------------------------------------------
# 3. Approval Workflow — TTL / Scope / Deny / Blocked Override
# ---------------------------------------------------------------------------


class TestApprovalWorkflow:
    def test_create_pending(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow, APPROVAL_PENDING
        wf = ApprovalWorkflow()
        dec = wf.create("file_write", "local", "Write status file")
        assert dec.status == APPROVAL_PENDING

    def test_grant(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow, APPROVAL_GRANTED
        wf = ApprovalWorkflow()
        dec = wf.create("file_write")
        result = wf.grant(dec.decision_id, "bryan")
        assert result["ok"] is True
        assert wf.get(dec.decision_id).status == APPROVAL_GRANTED

    def test_deny(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow, APPROVAL_DENIED
        wf = ApprovalWorkflow()
        dec = wf.create("file_write")
        result = wf.deny(dec.decision_id, "bryan", "Not needed now")
        assert result["ok"] is True
        assert wf.get(dec.decision_id).status == APPROVAL_DENIED
        assert wf.get(dec.decision_id).denial_reason == "Not needed now"

    def test_ttl_expiry(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow, APPROVAL_GRANTED
        wf = ApprovalWorkflow()
        dec = wf.create("file_write", ttl_seconds=0.001)
        time.sleep(0.01)
        valid = wf.validate(dec.decision_id)
        assert valid["valid"] is False

    def test_scope_constraint(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow
        wf = ApprovalWorkflow()
        dec = wf.create("file_write")
        wf.grant(dec.decision_id, "bryan")
        # Correct scope
        r1 = wf.check_scope(dec.decision_id, "file_write")
        assert r1["ok"] is True
        # Wrong scope
        r2 = wf.check_scope(dec.decision_id, "deploy")
        assert r2["ok"] is False

    def test_blocked_action_cannot_be_approved(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow, APPROVAL_BLOCKED
        wf = ApprovalWorkflow()
        for action in ("self_modification", "deploy", "auto_push", "secret_access"):
            dec = wf.create(action)
            assert dec.status == APPROVAL_BLOCKED
            result = wf.grant(dec.decision_id, "bryan")
            assert result["ok"] is False

    def test_audit_log_populated(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow
        wf = ApprovalWorkflow()
        dec = wf.create("file_write")
        wf.grant(dec.decision_id, "bryan")
        log = wf.get_audit_log(dec.decision_id)
        assert len(log) >= 2  # created + granted
        events = [e["event"] for e in log]
        assert "created" in events
        assert "granted" in events

    def test_expired_approval_not_valid(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow
        wf = ApprovalWorkflow()
        dec = wf.create("file_write", ttl_seconds=0.001)
        wf.grant(dec.decision_id, "bryan")
        time.sleep(0.02)
        valid = wf.validate(dec.decision_id)
        assert valid["valid"] is False

    def test_get_status_structure(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow
        wf = ApprovalWorkflow()
        s = wf.get_status()
        assert "version" in s
        assert "non_overridable_blocked_categories" in s
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 4. Power Autopilot — bounded, kill-switch, blocked
# ---------------------------------------------------------------------------


class TestPowerAutopilot:
    def test_kill_switch_on_by_default(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot(kill_switch=True)
        dec = pa.evaluate("local_analysis", eval_gate_result="pass")
        assert dec.decision == "kill_switch_disabled"

    def test_safe_local_with_gate_pass(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot(kill_switch=False)
        dec = pa.evaluate("local_analysis", eval_gate_result="pass")
        assert dec.decision == "auto_allowed"

    def test_safe_local_without_gate_fail(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot(kill_switch=False, require_eval_gate=True)
        dec = pa.evaluate("local_analysis", eval_gate_result=None)
        assert dec.decision == "needs_eval_gate"

    @pytest.mark.parametrize("action", [
        "deploy", "auto_push", "auto_merge", "secret_access",
        "self_modification", "safety_policy_change", "external_send",
        "browser_automation",
    ])
    def test_dangerous_always_blocked(self, action):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot(kill_switch=False)
        dec = pa.evaluate(action, eval_gate_result="pass")
        assert dec.decision == "blocked", f"{action} should be blocked in power_autopilot"

    def test_medium_risk_needs_all_preconditions(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot(kill_switch=False)
        # No eval gate, no rollback, no approval → needs_approval
        dec = pa.evaluate("file_write")
        assert dec.decision == "needs_approval"
        assert dec.requires_rollback is True
        assert dec.requires_approval is True

    def test_medium_risk_dry_run_with_all_preconditions(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot(kill_switch=False)
        dec = pa.evaluate(
            "file_write",
            eval_gate_result="pass",
            rollback_plan_id="plan_001",
            approval_decision_id="approval_001",
        )
        assert dec.decision == "dry_run_allowed"

    def test_activation_status_controlled(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot()
        status = pa.get_status()
        assert "not_broadly_activated" in status["activation_status"]

    def test_us13_parked(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        pa = PowerAutopilot()
        assert pa.get_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 5. Safety proof
# ---------------------------------------------------------------------------


class TestNUS1DSafetyProof:
    def test_no_self_modification(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        c = EvalCandidate(action_type="self_modification", risk_level="critical",
                          validation_plan="x", safety_gate_result="pass")
        report = run_eval_gate(c)
        assert not report.all_passed

    def test_no_auto_push(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        c = EvalCandidate(action_type="auto_push", risk_level="critical",
                          validation_plan="x", safety_gate_result="pass")
        report = run_eval_gate(c)
        assert not report.all_passed

    def test_no_deploy(self):
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        c = EvalCandidate(action_type="deploy", risk_level="critical",
                          validation_plan="x", safety_gate_result="pass")
        report = run_eval_gate(c)
        assert not report.all_passed

    def test_eval_gate_status_structure(self):
        from openjarvis.nus.eval_gate import get_eval_gate_status
        s = get_eval_gate_status()
        assert s["fail_closed"] is True
        assert s["safety_gates_active"] is True
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"


# ---------------------------------------------------------------------------
# 6. Doctor check
# ---------------------------------------------------------------------------


class TestNUS1DDoctorCheck:
    def test_doctor_check_passes(self):
        from openjarvis.doctor.checks import check_nus1d_eval_rollback, CheckStatus
        result = check_nus1d_eval_rollback()
        assert result.check_id == "nus1d_eval_rollback"
        assert result.status == CheckStatus.PASS, f"Doctor check failed: {result.summary}"

    def test_doctor_check_in_all_checks(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        names = [fn.__name__ for fn in _ALL_CHECK_FNS]
        assert "check_nus1d_eval_rollback" in names


# ---------------------------------------------------------------------------
# 7. US13 parked
# ---------------------------------------------------------------------------


class TestUS13Parked1D:
    def test_eval_gate_us13_parked(self):
        from openjarvis.nus.eval_gate import get_eval_gate_status
        assert get_eval_gate_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_rollback_us13_parked(self):
        from openjarvis.nus.rollback import RollbackEnforcer
        assert RollbackEnforcer().get_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_approval_us13_parked(self):
        from openjarvis.nus.approval_workflow import ApprovalWorkflow
        assert ApprovalWorkflow().get_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_power_autopilot_us13_parked(self):
        from openjarvis.nus.power_autopilot import PowerAutopilot
        assert PowerAutopilot().get_status()["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
