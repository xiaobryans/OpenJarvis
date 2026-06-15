"""Tests for autonomy modes — AutonomyMode + AutonomyPolicy.

Covers:
  - Default mode is observe_only (safe by default)
  - All 6 modes can be set and read back
  - Hard-gated actions are NEVER auto-allowed at any mode
  - can_auto_execute() enforces governance hard gates
  - can_observe() / can_propose() reflect mode correctly
  - get_status() returns honest status dict
  - Mode history is recorded
  - clear() resets state for test isolation
"""

from __future__ import annotations

import pytest

from openjarvis.autonomy.modes import AutonomyMode, AutonomyPolicy


@pytest.fixture(autouse=True)
def reset_policy():
    AutonomyPolicy.clear()
    yield
    AutonomyPolicy.clear()


class TestDefaultMode:
    def test_default_is_observe_only(self):
        mode = AutonomyPolicy.get_mode("omnix")
        assert mode == AutonomyMode.OBSERVE_ONLY

    def test_default_for_unknown_project(self):
        mode = AutonomyPolicy.get_mode("new_project_xyz")
        assert mode == AutonomyMode.OBSERVE_ONLY

    def test_get_status_default_project(self):
        status = AutonomyPolicy.get_status("omnix")
        assert status["mode"] == "observe_only"
        assert status["can_observe"] is True
        assert status["can_propose"] is False
        assert status["safe_execute_enabled"] is False
        assert status["hard_gates_always_blocked"] is True
        assert status["real_send_always_blocked"] is True


class TestSetMode:
    def test_set_observe_only(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.OBSERVE_ONLY

    def test_set_off(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OFF)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.OFF

    def test_set_propose_only(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.PROPOSE_ONLY)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.PROPOSE_ONLY

    def test_set_safe_execute_approved(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.SAFE_EXECUTE_APPROVED)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.SAFE_EXECUTE_APPROVED

    def test_set_blocked(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.BLOCKED)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.BLOCKED

    def test_set_requires_approval(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.REQUIRES_APPROVAL)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.REQUIRES_APPROVAL

    def test_mode_is_project_scoped(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.SAFE_EXECUTE_APPROVED)
        AutonomyPolicy.set_mode("project_b", AutonomyMode.OFF)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.SAFE_EXECUTE_APPROVED
        assert AutonomyPolicy.get_mode("project_b") == AutonomyMode.OFF

    def test_set_mode_records_history(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY, set_by="test", reason="unit test")
        history = AutonomyPolicy.get_history("omnix")
        assert len(history) == 1
        assert history[0]["mode"] == "observe_only"
        assert history[0]["set_by"] == "test"
        assert history[0]["reason"] == "unit test"

    def test_set_mode_multiple_times_keeps_last(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OFF)
        AutonomyPolicy.set_mode("omnix", AutonomyMode.PROPOSE_ONLY)
        assert AutonomyPolicy.get_mode("omnix") == AutonomyMode.PROPOSE_ONLY

    def test_history_tracks_all_changes(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OFF)
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY)
        AutonomyPolicy.set_mode("omnix", AutonomyMode.PROPOSE_ONLY)
        history = AutonomyPolicy.get_history("omnix")
        assert len(history) == 3


class TestCanAutoExecute:
    """Prove unsafe actions cannot auto-run at ANY mode."""

    HARD_GATE_ACTIONS = [
        "real_slack_send",
        "real_telegram_send",
        "real_email_send",
        "omnix_production_deploy",
        "vercel_deploy",
        "aws_infrastructure_change",
        "destructive_filesystem_op",
        "destructive_git_op",
        "browser_form_submit",
        "browser_purchase",
        "production_data_change",
        "secrets_exposure",
    ]

    ALL_MODES = list(AutonomyMode)

    def test_hard_gate_blocked_at_every_mode(self):
        """Hard-gated actions must be blocked at every autonomy mode."""
        for mode in self.ALL_MODES:
            AutonomyPolicy.set_mode("omnix", mode)
            for action in self.HARD_GATE_ACTIONS:
                result = AutonomyPolicy.can_auto_execute("omnix", action)
                assert result is False, (
                    f"FAIL: mode={mode.value} action={action} should be blocked but was allowed"
                )

    def test_off_blocks_all_actions(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OFF)
        assert AutonomyPolicy.can_auto_execute("omnix", "mission.list", "low") is False

    def test_observe_only_blocks_all_execution(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY)
        assert AutonomyPolicy.can_auto_execute("omnix", "mission.list", "low") is False

    def test_propose_only_blocks_all_execution(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.PROPOSE_ONLY)
        assert AutonomyPolicy.can_auto_execute("omnix", "mission.list", "low") is False

    def test_blocked_blocks_all_execution(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.BLOCKED)
        assert AutonomyPolicy.can_auto_execute("omnix", "mission.list", "low") is False

    def test_requires_approval_blocks_all_execution(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.REQUIRES_APPROVAL)
        assert AutonomyPolicy.can_auto_execute("omnix", "mission.list", "low") is False

    def test_safe_execute_allows_low_risk_non_hard_gate(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.SAFE_EXECUTE_APPROVED)
        assert AutonomyPolicy.can_auto_execute("omnix", "mission.list", "low") is True

    def test_safe_execute_blocks_high_risk(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.SAFE_EXECUTE_APPROVED)
        assert AutonomyPolicy.can_auto_execute("omnix", "some.action", "high") is False

    def test_safe_execute_still_blocks_hard_gates(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.SAFE_EXECUTE_APPROVED)
        for action in self.HARD_GATE_ACTIONS:
            assert AutonomyPolicy.can_auto_execute("omnix", action, "low") is False


class TestCanObservePropose:
    def test_off_cannot_observe(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OFF)
        assert AutonomyPolicy.can_observe("omnix") is False

    def test_observe_only_can_observe(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY)
        assert AutonomyPolicy.can_observe("omnix") is True

    def test_propose_only_can_observe_and_propose(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.PROPOSE_ONLY)
        assert AutonomyPolicy.can_observe("omnix") is True
        assert AutonomyPolicy.can_propose("omnix") is True

    def test_observe_only_cannot_propose(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY)
        assert AutonomyPolicy.can_propose("omnix") is False

    def test_safe_execute_can_observe_and_propose(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.SAFE_EXECUTE_APPROVED)
        assert AutonomyPolicy.can_observe("omnix") is True
        assert AutonomyPolicy.can_propose("omnix") is True

    def test_blocked_can_observe_but_not_propose(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.BLOCKED)
        assert AutonomyPolicy.can_observe("omnix") is True
        assert AutonomyPolicy.can_propose("omnix") is False


class TestListAllModes:
    def test_list_all_empty_initially(self):
        assert AutonomyPolicy.list_all_modes() == []

    def test_list_all_returns_set_modes(self):
        AutonomyPolicy.set_mode("omnix", AutonomyMode.OBSERVE_ONLY)
        AutonomyPolicy.set_mode("project_b", AutonomyMode.OFF)
        modes = AutonomyPolicy.list_all_modes()
        ids = [m["project_id"] for m in modes]
        assert "omnix" in ids
        assert "project_b" in ids
