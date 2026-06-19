"""Tests for the Execution Capability Registry.

Proves:
  - All permanently-blocked actions are classified as blocked
  - Safe local actions are classified as available
  - Provider-gated actions report correct blocker type
  - Unknown actions return blocked (not silent)
  - Registry summary is structured and complete
  - Capability records have all required fields
  - Coding proof path actions are registered
  - Provider status check returns structured result
"""

from __future__ import annotations

import pytest


class TestExecutionCapabilityRegistryStructure:
    """Registry has all required structure and fields."""

    def test_registry_creates_successfully(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        registry = get_capability_registry()
        assert registry is not None

    def test_singleton_returns_same_instance(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        r1 = get_capability_registry()
        r2 = get_capability_registry()
        assert r1 is r2

    def test_status_summary_has_required_fields(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        summary = get_capability_registry().get_status_summary()
        assert "total_actions" in summary
        assert "available_count" in summary
        assert "blocked_count" in summary
        assert "degraded_count" in summary
        assert "available_actions" in summary
        assert "blocked_actions" in summary
        assert "provider_status" in summary

    def test_total_actions_nonzero(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        summary = get_capability_registry().get_status_summary()
        assert summary["total_actions"] > 10

    def test_available_count_nonzero(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        summary = get_capability_registry().get_status_summary()
        assert summary["available_count"] > 0

    def test_blocked_count_nonzero(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        summary = get_capability_registry().get_status_summary()
        assert summary["blocked_count"] > 0

    def test_capability_record_to_dict_has_all_fields(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        registry = get_capability_registry()
        rec = registry.get("local_analysis")
        assert rec is not None
        d = rec.to_dict()
        required_fields = [
            "action_name", "capability_type", "risk_level",
            "approval_required", "rollback_support",
            "provider_keys_required", "current_status",
        ]
        for f in required_fields:
            assert f in d, f"Missing field: {f}"


class TestPermanentlyBlockedActions:
    """All hard-gate actions are classified as blocked in the registry."""

    @pytest.mark.parametrize("action", [
        "auto_push",
        "auto_merge",
        "production_deploy",
        "external_send",
        "secret_access",
        "us13_voice",
    ])
    def test_permanently_blocked_action(self, action):
        from openjarvis.orchestrator.capability_registry import (
            get_capability_registry, BLOCKER_SAFETY,
        )
        registry = get_capability_registry()
        rec = registry.get(action)
        assert rec is not None, f"Action '{action}' not in registry"
        assert rec.is_blocked(), f"Action '{action}' should be blocked"
        assert rec.blocker_type == BLOCKER_SAFETY

    @pytest.mark.parametrize("action", [
        "auto_push",
        "auto_merge",
        "production_deploy",
        "external_send",
        "secret_access",
        "us13_voice",
    ])
    def test_permanently_blocked_risk_level(self, action):
        from openjarvis.orchestrator.capability_registry import (
            get_capability_registry, RISK_BLOCKED,
        )
        registry = get_capability_registry()
        rec = registry.get(action)
        assert rec.risk_level == RISK_BLOCKED


class TestAvailableLocalActions:
    """Safe local actions are available without provider keys."""

    @pytest.mark.parametrize("action", [
        "local_file_read",
        "local_analysis",
        "doctor_run",
        "local_validation",
        "nus_dry_run",
        "routing_dry_run",
        "policy_check",
        "risk_assessment",
        "connector_dry_run",
    ])
    def test_local_action_available(self, action):
        from openjarvis.orchestrator.capability_registry import get_capability_registry, STATUS_AVAILABLE
        rec = get_capability_registry().get(action)
        assert rec is not None, f"Action '{action}' not in registry"
        assert rec.current_status == STATUS_AVAILABLE
        assert rec.is_available()

    @pytest.mark.parametrize("action", [
        "local_file_read",
        "local_analysis",
        "doctor_run",
        "local_validation",
        "nus_dry_run",
        "routing_dry_run",
    ])
    def test_local_action_needs_no_provider(self, action):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get(action)
        assert rec.provider_keys_required == []
        assert not rec.requires_provider()


class TestCodingProofPathActions:
    """Coding proof path actions are registered with correct classifications."""

    def test_coding_task_classify_registered(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get("coding_task_classify")
        assert rec is not None
        assert rec.is_available()

    def test_coding_file_inspect_registered(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get("coding_file_inspect")
        assert rec is not None
        assert rec.is_available()

    def test_coding_patch_propose_requires_provider(self):
        from openjarvis.orchestrator.capability_registry import (
            get_capability_registry, BLOCKER_PROVIDER,
        )
        rec = get_capability_registry().get("coding_patch_propose")
        assert rec is not None
        assert rec.requires_provider()
        assert rec.blocker_type == BLOCKER_PROVIDER

    def test_coding_test_run_available(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get("coding_test_run")
        assert rec is not None
        assert rec.is_available()

    def test_coding_diff_report_available(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get("coding_diff_report")
        assert rec is not None
        assert rec.is_available()

    def test_coding_rollback_available_requires_approval(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get("coding_rollback")
        assert rec is not None
        assert rec.is_available()
        assert rec.approval_required is True

    def test_coding_repair_loop_provider_gated(self):
        from openjarvis.orchestrator.capability_registry import (
            get_capability_registry, BLOCKER_PROVIDER,
        )
        rec = get_capability_registry().get("coding_repair_loop")
        assert rec is not None
        assert rec.blocker_type == BLOCKER_PROVIDER


class TestProviderStatusCheck:
    """Provider status check returns structured result."""

    def test_provider_status_has_all_providers(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        status = get_capability_registry().check_provider_status()
        assert "openai" in status
        assert "anthropic" in status
        assert "openrouter" in status

    def test_provider_status_fields_complete(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        status = get_capability_registry().check_provider_status()
        for provider, info in status.items():
            assert "env_var" in info
            assert "present" in info
            assert "status" in info
            assert isinstance(info["present"], bool)


class TestUnknownActionBlocked:
    """Unknown actions are blocked, not silently available."""

    def test_unknown_action_returns_blocked(self):
        from openjarvis.orchestrator.capability_registry import (
            get_capability_registry, BLOCKER_IMPLEMENTATION,
        )
        registry = get_capability_registry()
        rec = registry.get_or_blocked("totally_unknown_action_xyz_123")
        assert rec.is_blocked()
        assert rec.blocker_type == BLOCKER_IMPLEMENTATION

    def test_get_returns_none_for_unknown(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        rec = get_capability_registry().get("nonexistent_action_abc")
        assert rec is None

    def test_blockers_for_daily_driver_is_list(self):
        from openjarvis.orchestrator.capability_registry import get_capability_registry
        blockers = get_capability_registry().get_blockers_for_daily_driver()
        assert isinstance(blockers, list)
        # There should be provider blockers without API keys
        provider_blockers = [b for b in blockers if b.get("blocker_type") == "BLOCKED_PROVIDER"]
        assert len(provider_blockers) > 0
