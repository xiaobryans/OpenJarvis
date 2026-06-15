"""Tests for AutomationPolicy — 7-level automation ladder (US8 Phase C).

Covers:
  - Hard gate actions are always_blocked and cannot be overridden
  - Auto-allowed actions (Level 1-4) can_proceed without approval
  - Approval request/approve/reject full lifecycle
  - Expired approval cannot be reused
  - Standing policy overrides work for non-hard-gate actions
  - Hard gate policy cannot be changed
  - run_autopilot_once returns simulated results
  - get_policy_summary returns all expected keys
  - list_pending returns only pending records
"""

from __future__ import annotations

import time

import pytest

from openjarvis.autonomy.automation_policy import (
    ApprovalStatus,
    AutomationLevel,
    AutomationPolicy,
    StandingPolicyMode,
)


@pytest.fixture(autouse=True)
def clean_policy():
    AutomationPolicy.clear_for_tests()
    yield
    AutomationPolicy.clear_for_tests()


class TestHardGates:
    def test_production_deploy_always_blocked(self):
        ev = AutomationPolicy.evaluate("production_deploy")
        assert ev["blocked"] is True
        assert ev["standing_policy"] == StandingPolicyMode.ALWAYS_BLOCKED

    def test_secrets_mutation_always_blocked(self):
        ev = AutomationPolicy.evaluate("secrets_mutation")
        assert ev["blocked"] is True

    def test_browser_purchase_always_blocked(self):
        ev = AutomationPolicy.evaluate("browser_purchase")
        assert ev["blocked"] is True

    def test_all_hard_gates_are_level_7(self):
        hard_gates = [
            "production_deploy", "aws_infrastructure_change", "billing_change",
            "stripe_change", "vercel_deploy", "supabase_change",
            "secrets_mutation", "env_mutation", "browser_form_submit",
            "browser_purchase", "destructive_delete", "open_public_endpoint",
            "tailscale_funnel", "persistent_daemon_install",
        ]
        for action in hard_gates:
            ev = AutomationPolicy.evaluate(action)
            assert ev["blocked"] is True, f"{action} should be blocked"
            assert ev["automation_level"] == AutomationLevel.DANGEROUS_PRODUCTION, (
                f"{action} should be level 7"
            )

    def test_hard_gate_policy_cannot_be_changed(self):
        with pytest.raises(ValueError, match="Hard-gated"):
            AutomationPolicy.set_standing_policy(
                "production_deploy", StandingPolicyMode.AUTO_ALLOWED
            )

    def test_cannot_request_approval_for_blocked_action(self):
        with pytest.raises(ValueError, match="always_blocked"):
            AutomationPolicy.request_approval("production_deploy", "test")


class TestAutoAllowedActions:
    def test_read_only_check_can_proceed(self):
        ev = AutomationPolicy.evaluate("read_only_check")
        assert ev["can_proceed"] is True
        assert ev["blocked"] is False
        assert ev["requires_approval"] is False

    def test_watchdog_run_can_proceed(self):
        ev = AutomationPolicy.evaluate("watchdog_run")
        assert ev["can_proceed"] is True

    def test_draft_report_can_proceed(self):
        ev = AutomationPolicy.evaluate("draft_report")
        assert ev["can_proceed"] is True

    def test_doctor_run_can_proceed(self):
        ev = AutomationPolicy.evaluate("doctor_run")
        assert ev["can_proceed"] is True

    def test_get_status_can_proceed(self):
        ev = AutomationPolicy.evaluate("get_status")
        assert ev["can_proceed"] is True

    def test_automation_policy_get_can_proceed(self):
        ev = AutomationPolicy.evaluate("automation_policy_get")
        assert ev["can_proceed"] is True


class TestApprovalLifecycle:
    def test_request_approval_returns_record(self):
        record = AutomationPolicy.request_approval(
            "git_push_to_fork", "push to fork", "omnix"
        )
        assert record.approval_id
        assert record.status == ApprovalStatus.PENDING
        assert record.challenge_token
        assert record.expires_at > time.time()

    def test_approve_changes_status(self):
        record = AutomationPolicy.request_approval(
            "git_push_to_fork", "push to fork", "omnix"
        )
        approved = AutomationPolicy.approve(record.approval_id, "bryan")
        assert approved.status == ApprovalStatus.APPROVED
        assert approved.decided_by == "bryan"

    def test_reject_changes_status(self):
        record = AutomationPolicy.request_approval(
            "git_push_to_fork", "push", "omnix"
        )
        rejected = AutomationPolicy.reject(record.approval_id, "bryan")
        assert rejected.status == ApprovalStatus.REJECTED

    def test_approve_unknown_id_raises(self):
        with pytest.raises(ValueError, match="not found"):
            AutomationPolicy.approve("nonexistent-id")

    def test_reject_unknown_id_raises(self):
        with pytest.raises(ValueError, match="not found"):
            AutomationPolicy.reject("nonexistent-id")

    def test_approve_already_rejected_raises(self):
        record = AutomationPolicy.request_approval(
            "git_push_to_fork", "push", "omnix"
        )
        AutomationPolicy.reject(record.approval_id)
        with pytest.raises(ValueError, match="not pending"):
            AutomationPolicy.approve(record.approval_id)

    def test_expired_approval_cannot_be_reused(self):
        record = AutomationPolicy.request_approval(
            "git_push_to_fork", "push", "omnix", ttl_seconds=0
        )
        time.sleep(0.01)
        with pytest.raises(ValueError, match="expired"):
            AutomationPolicy.approve(record.approval_id)

    def test_list_pending_returns_pending_only(self):
        r1 = AutomationPolicy.request_approval("git_push_to_fork", "p1", "omnix")
        r2 = AutomationPolicy.request_approval("git_push_to_fork", "p2", "omnix")
        AutomationPolicy.approve(r1.approval_id)

        pending = AutomationPolicy.list_pending("omnix")
        ids = [p.approval_id for p in pending if p.status == ApprovalStatus.PENDING]
        assert r2.approval_id in ids
        assert r1.approval_id not in ids


class TestStandingPolicyOverride:
    def test_can_set_explicit_click_for_non_hard_gate(self):
        AutomationPolicy.set_standing_policy(
            "git_push_to_fork", StandingPolicyMode.EXPLICIT_CLICK_REQUIRED
        )
        ev = AutomationPolicy.evaluate("git_push_to_fork")
        assert ev["standing_policy"] == StandingPolicyMode.EXPLICIT_CLICK_REQUIRED
        assert ev["requires_approval"] is True

    def test_can_set_voice_approval_for_non_hard_gate(self):
        AutomationPolicy.set_standing_policy(
            "draft_slack_message", StandingPolicyMode.VOICE_APPROVAL_ALLOWED
        )
        ev = AutomationPolicy.evaluate("draft_slack_message")
        assert ev["standing_policy"] == StandingPolicyMode.VOICE_APPROVAL_ALLOWED

    def test_invalid_policy_mode_raises(self):
        with pytest.raises(ValueError, match="Invalid policy mode"):
            AutomationPolicy.set_standing_policy("git_push_to_fork", "fly_by_night")


class TestAutopilotAndSummary:
    def test_run_autopilot_once_returns_simulated(self):
        result = AutomationPolicy.run_autopilot_once("omnix")
        assert result["simulated"] is True
        assert result["run_type"] == "autopilot_once"
        assert len(result["actions_evaluated"]) >= 3
        for action in result["actions_evaluated"]:
            assert action["simulated"] is True

    def test_get_policy_summary_keys(self):
        summary = AutomationPolicy.get_policy_summary()
        assert "hard_gate_action_classes" in summary
        assert "auto_allowed_action_classes" in summary
        assert "levels" in summary
        assert len(summary["levels"]) == 7

    def test_evaluate_returns_all_required_fields(self):
        ev = AutomationPolicy.evaluate("read_only_check", "test", "omnix")
        required_keys = [
            "action_class", "automation_level", "standing_policy",
            "requires_approval", "blocked", "can_proceed", "project_id",
        ]
        for k in required_keys:
            assert k in ev, f"Missing key: {k}"
