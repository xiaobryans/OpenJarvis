"""Tests for Rollback / Undo Plans (US9 Phase 5)."""

from __future__ import annotations

import pytest

from openjarvis.autonomy.rollback_plan import (
    ActionRisk,
    RollbackPlan,
    classify_action_risk,
    create_rollback_plan,
    get_rollback_policy_status,
    log_rollback_plan,
)


class TestRiskClassification:
    def test_read_file_is_low(self):
        assert classify_action_risk("read_file") == ActionRisk.LOW

    def test_write_file_is_medium(self):
        assert classify_action_risk("write_file") == ActionRisk.MEDIUM

    def test_slack_send_is_high(self):
        assert classify_action_risk("slack_send") == ActionRisk.HIGH

    def test_production_deploy_is_dangerous(self):
        assert classify_action_risk("production_deploy") == ActionRisk.DANGEROUS

    def test_unknown_action_defaults_medium(self):
        assert classify_action_risk("mystery_action_xyz") == ActionRisk.MEDIUM


class TestCreateRollbackPlan:
    def test_low_risk_plan(self):
        plan = create_rollback_plan("read_file", "Read a config file")
        assert plan.risk_level == ActionRisk.LOW
        assert plan.is_reversible is True
        assert plan.approval_required is False
        assert "[DRY RUN]" in plan.dry_run_preview

    def test_medium_risk_plan(self):
        plan = create_rollback_plan(
            "write_file",
            "Write config",
            current_state={"path": "/tmp/test.txt"},
        )
        assert plan.risk_level == ActionRisk.MEDIUM
        assert plan.is_reversible is True
        assert len(plan.rollback_steps) > 0

    def test_high_risk_plan(self):
        plan = create_rollback_plan("slack_send", "Send a message")
        assert plan.risk_level == ActionRisk.HIGH
        assert plan.approval_required is True

    def test_dangerous_plan_blocked(self):
        plan = create_rollback_plan("production_deploy", "Deploy to prod")
        assert plan.risk_level == ActionRisk.DANGEROUS
        assert plan.approval_required is True
        assert any("DANGEROUS" in s for s in plan.rollback_steps)

    def test_plan_has_id_and_timestamp(self):
        plan = create_rollback_plan("read_file", "test")
        assert plan.plan_id
        assert plan.created_at > 0

    def test_plan_dry_run_preview_not_empty(self):
        plan = create_rollback_plan("git_commit", "Commit code")
        assert plan.dry_run_preview
        assert len(plan.dry_run_preview) > 5

    def test_git_commit_rollback_steps(self):
        plan = create_rollback_plan("git_commit", "Commit", current_state={})
        assert any("revert" in s.lower() or "reset" in s.lower() for s in plan.rollback_steps)


class TestRollbackPolicyStatus:
    def test_policy_is_active(self):
        s = get_rollback_policy_status()
        assert s["policy_active"] is True
        assert s["dry_run_available"] is True
        assert s["dangerous_actions_blocked"] is True
        assert s["automatic_rollback_disabled"] is True

    def test_approval_required_for_high_dangerous(self):
        s = get_rollback_policy_status()
        assert "high" in s["approval_required_for"]
        assert "dangerous" in s["approval_required_for"]


class TestPlanToDictSerialization:
    def test_to_dict_contains_all_fields(self):
        plan = create_rollback_plan("write_file", "test write")
        d = plan.to_dict()
        assert "plan_id" in d
        assert "action" in d
        assert "risk_level" in d
        assert "rollback_steps" in d
        assert "dry_run_preview" in d
        assert "approval_required" in d
