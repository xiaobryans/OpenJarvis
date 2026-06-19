"""NUS 1F — Structured Decision Records tests.

Tests:
  - Structured decision records emitted
  - No raw chain-of-thought field
  - Schema covers all hierarchy levels
  - Action decision records
  - Session decision records
  - Autonomy action policy tiers and model constraints
  - 95% automation policy completeness
"""

import pytest


class TestStructuredDecisionRecordSchema:
    def test_build_action_record_fields(self):
        from openjarvis.nus.decision_record import build_action_decision_record
        dr = build_action_decision_record(
            action_type="local_read",
            decision="allowed",
            reason="test_reason",
            evidence={"test_key": "test_value"},
        )
        required_fields = [
            "record_id", "created_at", "schema_version", "decision",
            "reason", "rationale", "action_type", "hierarchy_level",
            "nus_learning_tags", "no_raw_chain_of_thought",
        ]
        for f in required_fields:
            assert f in dr, f"Missing field: {f}"

    def test_no_raw_chain_of_thought(self):
        from openjarvis.nus.decision_record import build_action_decision_record
        dr = build_action_decision_record(
            action_type="local_analysis", decision="allowed",
            reason="test", evidence={},
        )
        assert dr["no_raw_chain_of_thought"] is True
        assert "raw_chain_of_thought" not in dr

    def test_blocked_record_has_blocking_reason(self):
        from openjarvis.nus.decision_record import build_action_decision_record
        dr = build_action_decision_record(
            action_type="production_deploy",
            decision="blocked",
            reason="permanently_blocked",
            evidence={},
        )
        assert dr["decision"] == "blocked"
        assert dr["blocking_reason"] == "permanently_blocked"

    def test_allowed_record_no_blocking_reason(self):
        from openjarvis.nus.decision_record import build_action_decision_record
        dr = build_action_decision_record(
            action_type="local_read", decision="allowed",
            reason="safe_action", evidence={},
        )
        assert dr["blocking_reason"] == ""

    def test_nus_learning_tags_present(self):
        from openjarvis.nus.decision_record import build_action_decision_record
        dr = build_action_decision_record(
            action_type="local_read", decision="allowed",
            reason="test", evidence={},
        )
        assert isinstance(dr["nus_learning_tags"], list)
        assert len(dr["nus_learning_tags"]) > 0

    def test_schema_version_present(self):
        from openjarvis.nus.decision_record import (
            build_action_decision_record, NUS1F_DECISION_RECORD_VERSION,
        )
        dr = build_action_decision_record(
            action_type="local_read", decision="allowed",
            reason="test", evidence={},
        )
        assert dr["schema_version"] == NUS1F_DECISION_RECORD_VERSION


class TestDecisionRecordHierarchyLevels:
    def test_all_levels_accepted(self):
        from openjarvis.nus.decision_record import build_action_decision_record, _VALID_LEVELS
        for level in _VALID_LEVELS:
            dr = build_action_decision_record(
                action_type="local_read", decision="allowed",
                reason="test", evidence={},
                hierarchy_level=level,
            )
            assert dr["hierarchy_level"] == level

    def test_invalid_level_defaults_to_jarvis_pa(self):
        from openjarvis.nus.decision_record import build_action_decision_record, LEVEL_JARVIS_PA
        dr = build_action_decision_record(
            action_type="local_read", decision="allowed",
            reason="test", evidence={},
            hierarchy_level="unknown_level_xyz",
        )
        assert dr["hierarchy_level"] == LEVEL_JARVIS_PA

    def test_status_covers_all_levels(self):
        from openjarvis.nus.decision_record import get_decision_record_status
        status = get_decision_record_status()
        coverage = status["nus_hierarchy_coverage"]
        for level in ["jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"]:
            assert level in coverage

    def test_status_generic_flag(self):
        from openjarvis.nus.decision_record import get_decision_record_status
        status = get_decision_record_status()
        assert status["generic_for_all_levels"] is True
        assert status["future_proof"] is True
        assert status["no_raw_chain_of_thought"] is True


class TestSessionDecisionRecord:
    def test_build_session_record(self):
        from openjarvis.nus.decision_record import build_session_decision_record
        dr = build_session_decision_record(
            session_id="test-session-123",
            decision="allowed",
            reason="session_test",
            evidence={"profile": "safe_autopilot"},
        )
        assert dr["session_id"] == "test-session-123"
        assert dr["decision"] == "allowed"
        assert dr["no_raw_chain_of_thought"] is True
        assert "record_id" in dr

    def test_session_revoked_record(self):
        from openjarvis.nus.decision_record import build_session_decision_record
        dr = build_session_decision_record(
            session_id="test-session-456",
            decision="revoked",
            reason="explicit_revocation",
            evidence={"previous_status": "active"},
        )
        assert dr["decision"] == "revoked"

    def test_invalid_decision_defaults_to_blocked(self):
        from openjarvis.nus.decision_record import build_session_decision_record, DECISION_BLOCKED
        dr = build_session_decision_record(
            session_id="test", decision="invalid_xyz",
            reason="test", evidence={},
        )
        assert dr["decision"] == DECISION_BLOCKED


class TestAutonomyActionPolicyTiers:
    def _policy(self):
        from openjarvis.nus.autonomy_action_policy import AutonomyActionPolicy
        return AutonomyActionPolicy()

    def test_auto_allowed_actions(self):
        policy = self._policy()
        for action in ["local_read", "local_analysis", "local_validation", "health_check"]:
            c = policy.classify(action)
            assert c.tier == "auto_allowed", f"{action} should be auto_allowed: {c.tier}"
            assert not c.requires_approval
            assert not c.is_blocked

    def test_auto_allowed_with_audit_actions(self):
        policy = self._policy()
        for action in ["scorecard_generation", "telemetry_normalization", "test_run_local"]:
            c = policy.classify(action)
            assert c.tier == "auto_allowed_with_audit", f"{action}: {c.tier}"
            assert c.requires_audit
            assert not c.requires_approval

    def test_dry_run_only_actions(self):
        policy = self._policy()
        for action in ["recommendation_dry_run", "session_create_dry_run", "production_gate_dry_run"]:
            c = policy.classify(action)
            assert c.tier == "dry_run_only", f"{action}: {c.tier}"
            assert c.is_dry_run_safe

    def test_needs_approval_actions(self):
        policy = self._policy()
        for action in ["medium_file_write", "source_code_mutation", "config_update"]:
            c = policy.classify(action)
            assert c.tier == "needs_approval", f"{action}: {c.tier}"
            assert c.requires_approval

    def test_blocked_actions(self):
        policy = self._policy()
        for action in [
            "production_deploy", "auto_push", "auto_merge",
            "secret_access", "real_slack_send", "merge_to_main",
        ]:
            c = policy.classify(action)
            assert c.tier == "blocked", f"{action}: {c.tier}"
            assert c.is_blocked
            assert not c.requires_approval  # blocked, not approval-pending

    def test_unknown_action_defaults_to_needs_approval(self):
        policy = self._policy()
        c = policy.classify("totally_unknown_action_xyz")
        assert c.tier == "needs_approval"
        assert c.requires_approval

    def test_high_risk_override(self):
        policy = self._policy()
        c = policy.classify("docs_metadata_update", risk_level="high")
        assert c.tier == "needs_approval"

    def test_to_dict(self):
        policy = self._policy()
        c = policy.classify("local_read")
        d = c.to_dict()
        assert "action_type" in d
        assert "tier" in d
        assert "is_blocked" in d
        assert "requires_approval" in d


class TestModelTierConstraints:
    def _policy(self):
        from openjarvis.nus.autonomy_action_policy import AutonomyActionPolicy
        return AutonomyActionPolicy()

    def test_any_model_can_do_auto_allowed(self):
        policy = self._policy()
        for tier_model in ["cheap_model", "standard_model", "premium_model"]:
            assert policy.can_model_tier_approve("local_read", tier_model)

    def test_cheap_model_cannot_approve_strict_policy(self):
        policy = self._policy()
        assert not policy.can_model_tier_approve("high_risk_file_write", "cheap_model")
        assert not policy.can_model_tier_approve("governance_policy_update_dry_run", "cheap_model")

    def test_cheap_model_cannot_approve_blocked(self):
        policy = self._policy()
        assert not policy.can_model_tier_approve("production_deploy", "cheap_model")
        assert not policy.can_model_tier_approve("auto_push", "cheap_model")

    def test_premium_model_can_approve_strict_policy(self):
        policy = self._policy()
        assert policy.can_model_tier_approve("high_risk_file_write", "premium_model")

    def test_standard_model_can_approve_needs_approval(self):
        policy = self._policy()
        assert policy.can_model_tier_approve("medium_file_write", "standard_model")

    def test_no_model_can_approve_permanently_blocked(self):
        policy = self._policy()
        for model in ["cheap_model", "standard_model", "premium_model"]:
            assert not policy.can_model_tier_approve("production_deploy", model)
            assert not policy.can_model_tier_approve("secret_access", model)


class TestPolicyStatus:
    def test_policy_status_fields(self):
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        s = policy.get_status()
        assert "policy_version" in s
        assert "tiers" in s
        assert "permanently_blocked_count" in s
        assert s["target_95pct_automation"] is True
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert s["production_execution"] == "blocked_in_nus1f"
        assert s["no_hardcoded_agent_names"] is True
        assert s["metadata_contract_driven"] is True

    def test_all_tiers_in_status(self):
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        s = policy.get_status()
        expected_tiers = {
            "auto_allowed", "auto_allowed_with_audit", "dry_run_only",
            "needs_approval", "strict_policy_controlled", "blocked",
        }
        assert expected_tiers == set(s["tiers"])
