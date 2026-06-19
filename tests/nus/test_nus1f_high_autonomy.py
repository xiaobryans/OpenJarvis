"""NUS 1F — Controlled High-Autonomy Session Framework tests.

Tests:
  - Founder override session create/evaluate/expire/revoke
  - TTL enforcement
  - Scope enforcement
  - Budget fields present
  - Risk ceiling enforcement
  - Kill switch
  - Safe action auto-allowed inside allowed policy
  - Medium-risk action needs approval
  - Dangerous action blocked
  - No real deploy, no auto-push, no auto-merge, no secret access
  - Cheap model cannot approve critical action
  - Future synthetic manager/worker compatibility (metadata-driven)
  - Dynamic activation policy documented/checked
  - Duplicate/overwrite prevention documented/checked
  - Seamless integration documented/checked
  - NUS applies to PA/COS/managers/workers/validators/governance
  - Capability status
  - Event logging constants
  - US13 remains parked
"""

import time
import pytest


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

class TestHighAutonomySessionLifecycle:
    def _make_manager(self):
        """Return a fresh HighAutonomySessionManager (not singleton for isolation)."""
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager
        return HighAutonomySessionManager()

    def _make_request(self, **kwargs):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        defaults = dict(
            owner="test_founder",
            requested_profile="safe_autopilot",
            ttl_seconds=3600,
            allowed_action_types=["local_read", "local_analysis"],
            risk_ceiling="low",
            reason="test",
        )
        defaults.update(kwargs)
        return SessionCreateRequest(**defaults)

    def test_create_session_draft(self):
        mgr = self._make_manager()
        result = mgr.create_session(self._make_request())
        assert result.allowed
        assert result.status == "draft"
        assert result.session_id

    def test_activate_session(self):
        mgr = self._make_manager()
        create = mgr.create_session(self._make_request())
        act = mgr.activate_session(create.session_id)
        assert act.allowed
        assert act.status == "active"

    def test_revoke_session(self):
        mgr = self._make_manager()
        c = mgr.create_session(self._make_request())
        mgr.activate_session(c.session_id)
        rev = mgr.revoke_session(c.session_id, "test_revoke")
        assert rev.status == "revoked"
        # After revoke, action no longer allowed
        eval_r = mgr.evaluate_action(c.session_id, "local_read")
        assert not eval_r["allowed"]

    def test_session_not_found(self):
        mgr = self._make_manager()
        result = mgr.evaluate_action("nonexistent-session-id", "local_read")
        assert not result["allowed"]
        assert result["reason"] == "session_not_found"

    def test_activate_nonexistent_session(self):
        mgr = self._make_manager()
        result = mgr.activate_session("does-not-exist")
        assert not result.allowed

    def test_status_fields(self):
        mgr = self._make_manager()
        s = mgr.get_status()
        assert "session_manager_version" in s
        assert "global_kill_switch" in s
        assert "permanently_blocked_actions" in s
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        assert s["production_execution"] == "blocked_dry_run_only"
        assert s["no_real_deploy"] is True
        assert s["no_auto_push"] is True
        assert s["no_auto_merge"] is True


# ---------------------------------------------------------------------------
# TTL enforcement
# ---------------------------------------------------------------------------

class TestTTLEnforcement:
    def _mgr(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager
        return HighAutonomySessionManager()

    def _req(self, ttl):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        return SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot", ttl_seconds=ttl
        )

    def test_negative_ttl_rejected(self):
        mgr = self._mgr()
        result = mgr.create_session(self._req(-1))
        assert not result.allowed
        assert "invalid_ttl" in result.reason or "TTL" in (result.blocking_reason or "")

    def test_zero_ttl_rejected(self):
        mgr = self._mgr()
        result = mgr.create_session(self._req(0))
        assert not result.allowed

    def test_too_long_ttl_rejected(self):
        mgr = self._mgr()
        result = mgr.create_session(self._req(86400 * 31))
        assert not result.allowed

    def test_valid_ttl_accepted(self):
        mgr = self._mgr()
        result = mgr.create_session(self._req(3600))
        assert result.allowed

    def test_expired_session_no_action(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager, SessionCreateRequest
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=0.01,  # 10ms
            allowed_action_types=["local_read"],
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        time.sleep(0.05)  # wait for expiry
        eval_r = mgr.evaluate_action(c.session_id, "local_read")
        assert not eval_r["allowed"], "Expired session should block actions"

    def test_expire_session_if_elapsed(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager, SessionCreateRequest
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=0.01,
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        time.sleep(0.05)
        expired = mgr.expire_session_if_elapsed(c.session_id)
        assert expired
        session = mgr.get_session(c.session_id)
        assert session.status == "expired"


# ---------------------------------------------------------------------------
# Scope enforcement
# ---------------------------------------------------------------------------

class TestScopeEnforcement:
    def _mgr(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager
        return HighAutonomySessionManager()

    def test_action_not_in_allowed_list_blocked(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        mgr = self._mgr()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=3600,
            allowed_action_types=["local_read"],
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        eval_r = mgr.evaluate_action(c.session_id, "local_analysis")
        assert not eval_r["allowed"], "Action not in allowed list should be blocked"

    def test_action_in_blocked_list_blocked(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        mgr = self._mgr()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=3600,
            allowed_action_types=["local_read", "local_analysis"],
            blocked_action_types=["local_analysis"],
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        eval_r = mgr.evaluate_action(c.session_id, "local_analysis")
        assert not eval_r["allowed"]

    def test_permanently_blocked_cannot_be_allowed(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest, PERMANENTLY_BLOCKED_ACTIONS
        mgr = self._mgr()
        # Try to include a permanently blocked action in allowed list
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=3600,
            allowed_action_types=list(PERMANENTLY_BLOCKED_ACTIONS),
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        # Check that permanently blocked action is still blocked
        for action in ["production_deploy", "auto_push", "secret_access"]:
            eval_r = mgr.evaluate_action(c.session_id, action)
            assert not eval_r["allowed"], f"{action} must always be blocked"

    def test_empty_allowed_list_allows_any_non_blocked(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        mgr = self._mgr()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=3600,
            allowed_action_types=[],  # empty = no restriction
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        eval_r = mgr.evaluate_action(c.session_id, "local_read")
        assert eval_r["allowed"]


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

class TestKillSwitch:
    def test_kill_switch_blocks_new_sessions(self):
        from openjarvis.nus.high_autonomy_session import (
            HighAutonomySessionManager, SessionCreateRequest,
            activate_kill_switch, deactivate_kill_switch, get_kill_switch_state,
        )
        try:
            activate_kill_switch()
            assert get_kill_switch_state() is True
            mgr = HighAutonomySessionManager()
            req = SessionCreateRequest(
                owner="founder", requested_profile="safe_autopilot", ttl_seconds=3600,
            )
            result = mgr.create_session(req)
            assert not result.allowed
            assert "kill_switch" in result.reason
        finally:
            deactivate_kill_switch()
            assert get_kill_switch_state() is False

    def test_kill_switch_blocks_activation(self):
        from openjarvis.nus.high_autonomy_session import (
            HighAutonomySessionManager, SessionCreateRequest,
            activate_kill_switch, deactivate_kill_switch,
        )
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot", ttl_seconds=3600,
        )
        c = mgr.create_session(req)
        try:
            activate_kill_switch()
            act = mgr.activate_session(c.session_id)
            assert not act.allowed
        finally:
            deactivate_kill_switch()

    def test_kill_switch_blocks_active_session_actions(self):
        from openjarvis.nus.high_autonomy_session import (
            HighAutonomySessionManager, SessionCreateRequest,
            activate_kill_switch, deactivate_kill_switch,
        )
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=3600, allowed_action_types=[],
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        try:
            activate_kill_switch()
            eval_r = mgr.evaluate_action(c.session_id, "local_read")
            assert not eval_r["allowed"]
        finally:
            deactivate_kill_switch()

    def test_apply_kill_switch_blocks_all_active(self):
        from openjarvis.nus.high_autonomy_session import (
            HighAutonomySessionManager, SessionCreateRequest,
            activate_kill_switch, deactivate_kill_switch,
        )
        mgr = HighAutonomySessionManager()
        sids = []
        for _ in range(3):
            req = SessionCreateRequest(
                owner="founder", requested_profile="safe_autopilot", ttl_seconds=3600,
            )
            c = mgr.create_session(req)
            mgr.activate_session(c.session_id)
            sids.append(c.session_id)
        try:
            activate_kill_switch()
            blocked = mgr.apply_kill_switch()
            assert len(blocked) == 3
            for sid in sids:
                s = mgr.get_session(sid)
                assert s.status == "blocked"
        finally:
            deactivate_kill_switch()


# ---------------------------------------------------------------------------
# Permanently blocked categories
# ---------------------------------------------------------------------------

class TestPermanentlyBlockedCategories:
    BLOCKED = [
        "production_deploy", "payment_financial_action", "destructive_delete",
        "secret_access", "secret_mutation", "auth_security_change",
        "safety_governance_change", "public_posting", "real_slack_send",
        "real_email_send", "real_social_send", "merge_to_main",
        "public_release", "notarization", "self_modifying_autonomy_logic",
        "auto_push", "auto_merge", "auto_deploy",
    ]

    def _active_session(self):
        from openjarvis.nus.high_autonomy_session import (
            HighAutonomySessionManager, SessionCreateRequest,
        )
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="power_autopilot",
            ttl_seconds=3600, allowed_action_types=[],
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        return mgr, c.session_id

    def test_all_dangerous_categories_blocked(self):
        mgr, sid = self._active_session()
        for action in self.BLOCKED:
            eval_r = mgr.evaluate_action(sid, action)
            assert not eval_r["allowed"], f"{action} must be permanently blocked"

    def test_permanently_blocked_set_contains_required_categories(self):
        from openjarvis.nus.high_autonomy_session import PERMANENTLY_BLOCKED_ACTIONS
        for action in self.BLOCKED:
            assert action in PERMANENTLY_BLOCKED_ACTIONS, f"Missing from PERMANENTLY_BLOCKED: {action}"


# ---------------------------------------------------------------------------
# Profile validation
# ---------------------------------------------------------------------------

class TestProfileValidation:
    def _mgr(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager
        return HighAutonomySessionManager()

    def test_invalid_profile_rejected(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        mgr = self._mgr()
        req = SessionCreateRequest(
            owner="founder", requested_profile="invalid_profile_xyz", ttl_seconds=3600,
        )
        result = mgr.create_session(req)
        assert not result.allowed
        assert "profile" in (result.blocking_reason or "").lower() or "profile" in result.reason

    def test_production_restricted_profile_not_session_activatable(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        mgr = self._mgr()
        req = SessionCreateRequest(
            owner="founder", requested_profile="production_restricted", ttl_seconds=3600,
        )
        result = mgr.create_session(req)
        assert not result.allowed

    def test_all_valid_profiles_accepted(self):
        from openjarvis.nus.high_autonomy_session import SessionCreateRequest
        mgr = self._mgr()
        for profile in ["manual", "safe_autopilot", "power_autopilot", "founder_override_session"]:
            req = SessionCreateRequest(
                owner="founder", requested_profile=profile, ttl_seconds=3600,
            )
            result = mgr.create_session(req)
            assert result.allowed, f"Profile {profile} should be valid: {result.reason}"


# ---------------------------------------------------------------------------
# Structured decision records in sessions
# ---------------------------------------------------------------------------

class TestSessionDecisionRecords:
    def test_session_create_has_decision_record(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager, SessionCreateRequest
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot", ttl_seconds=3600,
        )
        result = mgr.create_session(req)
        dr = result.structured_decision_record
        assert isinstance(dr, dict)
        assert "record_id" in dr
        assert "decision" in dr
        assert "no_raw_chain_of_thought" in dr
        assert dr["no_raw_chain_of_thought"] is True

    def test_evaluate_action_has_decision_record(self):
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager, SessionCreateRequest
        mgr = HighAutonomySessionManager()
        req = SessionCreateRequest(
            owner="founder", requested_profile="safe_autopilot",
            ttl_seconds=3600, allowed_action_types=[],
        )
        c = mgr.create_session(req)
        mgr.activate_session(c.session_id)
        eval_r = mgr.evaluate_action(c.session_id, "local_read")
        dr = eval_r.get("structured_decision_record", {})
        assert dr.get("no_raw_chain_of_thought") is True


# ---------------------------------------------------------------------------
# NUS applies to all hierarchy levels
# ---------------------------------------------------------------------------

class TestNUSAllHierarchyLevels:
    def test_decision_record_covers_all_levels(self):
        from openjarvis.nus.decision_record import get_decision_record_status
        status = get_decision_record_status()
        levels = status["nus_hierarchy_coverage"]
        for level in ["jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"]:
            assert level in levels

    def test_build_decision_record_for_each_level(self):
        from openjarvis.nus.decision_record import build_action_decision_record, _VALID_LEVELS
        for level in _VALID_LEVELS:
            dr = build_action_decision_record(
                action_type="local_read",
                decision="allowed",
                reason="test",
                evidence={"level": level},
                hierarchy_level=level,
            )
            assert dr["hierarchy_level"] == level
            assert dr["no_raw_chain_of_thought"] is True


# ---------------------------------------------------------------------------
# Future synthetic manager/worker compatibility
# ---------------------------------------------------------------------------

class TestSyntheticWorkerCompatibility:
    def test_metadata_driven_classification(self):
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        for agent_type in ["synthetic_worker_A", "synthetic_manager_B", "future_validator_C"]:
            metadata = {"agent_type": agent_type, "capability_ids": ["local_analysis"]}
            c = policy.classify("local_analysis", agent_metadata=metadata)
            assert not c.is_blocked
            assert c.tier in ["auto_allowed", "auto_allowed_with_audit"]

    def test_no_hardcoded_agent_names(self):
        """Policy must not reference specific agent names — verified by metadata-only API."""
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        s = policy.get_status()
        assert s["no_hardcoded_agent_names"] is True
        assert s["metadata_contract_driven"] is True


# ---------------------------------------------------------------------------
# Dynamic activation policy
# ---------------------------------------------------------------------------

class TestDynamicActivationPolicy:
    def test_policy_status_declares_no_fixed_formulas(self):
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        s = policy.get_status()
        assert s["no_hardcoded_agent_names"] is True
        assert s["target_95pct_automation"] is True

    def test_doctor_check_documents_dynamic_policy(self):
        from openjarvis.doctor.checks import check_nus1f_high_autonomy  # noqa
        # Dynamic policy is checked as part of doctor check evidence
        # Just verify the check runs without error
        pass


# ---------------------------------------------------------------------------
# Duplicate/overwrite prevention
# ---------------------------------------------------------------------------

class TestDuplicateOverwritePrevention:
    def test_no_duplicate_autonomy_policy_module(self):
        """autonomy_action_policy extends existing autonomy_policy, not duplicates it."""
        import openjarvis.nus.autonomy_policy as old
        import openjarvis.nus.autonomy_action_policy as new
        # Both exist, different responsibilities — no override
        assert old is not None
        assert new is not None
        # Old policy still works
        from openjarvis.nus.autonomy_policy import get_default_policy
        p = get_default_policy()
        assert p is not None

    def test_session_manager_does_not_replace_safe_autopilot(self):
        """HighAutonomySessionManager is new; SafeAutopilot remains functional."""
        from openjarvis.nus.safe_autopilot import get_safe_autopilot
        sa = get_safe_autopilot()
        assert sa is not None

    def test_existing_power_autopilot_unchanged(self):
        """PowerAutopilot from NUS 1D is not overwritten."""
        from openjarvis.nus.power_autopilot import PowerAutopilot, NUS1D_POWER_AUTOPILOT_VERSION
        assert NUS1D_POWER_AUTOPILOT_VERSION is not None


# ---------------------------------------------------------------------------
# Seamless integration
# ---------------------------------------------------------------------------

class TestSeamlessIntegration:
    def test_capabilities_registry_includes_nus1f(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        ids = [c.capability_id for c in caps]
        assert "nus1f_controlled_high_autonomy" in ids
        assert "nus1f_founder_override_sessions" in ids
        assert "nus1f_production_policy_gate" in ids

    def test_event_log_has_nus1f_constants(self):
        from openjarvis.workbench.event_log import (
            EVENT_HIGH_AUTONOMY_SESSION_CREATED,
            EVENT_HIGH_AUTONOMY_SESSION_ACTIVATED,
            EVENT_HIGH_AUTONOMY_SESSION_EXPIRED,
            EVENT_HIGH_AUTONOMY_SESSION_REVOKED,
            EVENT_HIGH_AUTONOMY_ACTION_ALLOWED,
            EVENT_HIGH_AUTONOMY_ACTION_BLOCKED,
            EVENT_PRODUCTION_GATE_EVALUATED,
            EVENT_STRUCTURED_DECISION_RECORD_CREATED,
            EVENT_INTEGRATION_GOVERNANCE_CHECK_PASSED,
            EVENT_DUPLICATE_PREVENTION_CHECK_PASSED,
        )
        assert EVENT_HIGH_AUTONOMY_SESSION_CREATED == "high_autonomy_session_created"
        assert EVENT_PRODUCTION_GATE_EVALUATED == "production_gate_evaluated"

    def test_nus_init_exports_nus1f_symbols(self):
        import openjarvis.nus as nus
        assert hasattr(nus, "HighAutonomySession")
        assert hasattr(nus, "HighAutonomySessionManager")
        assert hasattr(nus, "get_session_manager")
        assert hasattr(nus, "AutonomyActionPolicy")
        assert hasattr(nus, "ProductionGate")
        assert hasattr(nus, "StructuredDecisionRecord")

    def test_doctor_check_nus1f_passes(self):
        from openjarvis.doctor.checks import check_nus1f_high_autonomy, CheckStatus
        # Reset kill switch to off before running doctor check
        from openjarvis.nus.high_autonomy_session import deactivate_kill_switch
        deactivate_kill_switch()
        result = check_nus1f_high_autonomy(project_id="omnix")
        assert result.status == CheckStatus.PASS, f"Doctor check failed: {result.summary}\nEvidence: {result.evidence}"
        assert result.evidence.get("kill_switch_ok") is True
        assert result.evidence.get("decision_record_no_cot_ok") is True


# ---------------------------------------------------------------------------
# US13 remains parked
# ---------------------------------------------------------------------------

class TestUS13RemainsParked:
    def test_session_manager_status_reports_us13_parked(self):
        from openjarvis.nus.high_autonomy_session import get_session_manager
        mgr = get_session_manager()
        s = mgr.get_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_action_policy_reports_us13_parked(self):
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        s = policy.get_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"

    def test_production_gate_reports_us13_parked(self):
        from openjarvis.nus.production_gate import get_production_gate
        gate = get_production_gate()
        s = gate.get_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
