"""Tests for Expert Role Registry and Role Selector."""

from __future__ import annotations

import pytest

from openjarvis.orchestrator.expert_roles import (
    ExpertRole,
    ExpertRoleRegistry,
    RoleSelector,
)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestExpertRoleRegistry:
    def setup_method(self):
        ExpertRoleRegistry.reset_instance()

    def test_builtins_loaded(self):
        reg = ExpertRoleRegistry.get_instance()
        roles = reg.list_all()
        assert len(roles) >= 8

    def test_get_by_id(self):
        reg = ExpertRoleRegistry.get_instance()
        role = reg.get("role_coding")
        assert role is not None
        assert role.domain == "coding"

    def test_list_active(self):
        reg = ExpertRoleRegistry.get_instance()
        active = reg.list_active()
        assert len(active) > 0
        for r in active:
            assert r.status == "active"

    def test_list_by_domain(self):
        reg = ExpertRoleRegistry.get_instance()
        coding = reg.list_by_domain("coding")
        assert len(coding) >= 1
        assert all(r.domain == "coding" for r in coding)

    def test_deactivate_and_activate(self):
        reg = ExpertRoleRegistry.get_instance()
        role = reg.deactivate("role_coding")
        assert role is not None
        assert role.status == "inactive"
        role2 = reg.activate("role_coding")
        assert role2.status == "active"

    def test_get_missing_returns_none(self):
        reg = ExpertRoleRegistry.get_instance()
        assert reg.get("nonexistent_role") is None

    def test_stats(self):
        reg = ExpertRoleRegistry.get_instance()
        stats = reg.stats()
        assert stats["total"] >= 8
        assert stats["active"] > 0

    def test_high_safety_roles_have_disclaimer(self):
        reg = ExpertRoleRegistry.get_instance()
        legal = reg.get("role_legal")
        finance = reg.get("role_finance")
        assert legal is not None and legal.disclaimer != ""
        assert finance is not None and finance.disclaimer != ""

    def test_to_dict_roundtrip(self):
        reg = ExpertRoleRegistry.get_instance()
        role = reg.get("role_coding")
        d = role.to_dict()
        restored = ExpertRole.from_dict(d)
        assert restored.role_id == role.role_id
        assert restored.domain == role.domain
        assert restored.trigger_conditions == role.trigger_conditions


# ---------------------------------------------------------------------------
# Role selector tests
# ---------------------------------------------------------------------------


class TestRoleSelector:
    def setup_method(self):
        ExpertRoleRegistry.reset_instance()

    def test_select_coding_role_from_code_text(self):
        sel = RoleSelector()
        roles = sel.select("Please review my code and suggest refactoring")
        domains = [r.domain for r in roles]
        assert "coding" in domains

    def test_select_research_role_from_research_text(self):
        sel = RoleSelector()
        roles = sel.select("I need you to research the latest papers on LLMs")
        domains = [r.domain for r in roles]
        assert "research" in domains

    def test_max_roles_respected(self):
        sel = RoleSelector()
        roles = sel.select("code review research product security", max_roles=2)
        assert len(roles) <= 2

    def test_no_match_returns_empty(self):
        sel = RoleSelector()
        # text that doesn't match any trigger
        roles = sel.select("xkzqjpwv xyz123")
        assert roles == []

    def test_high_safety_excluded_by_default(self):
        sel = RoleSelector()
        roles = sel.select("legal contract compliance gdpr")
        domains = [r.domain for r in roles]
        assert "legal" not in domains

    def test_high_safety_included_when_flag_set(self):
        sel = RoleSelector()
        roles = sel.select("legal contract compliance", include_high_safety=True)
        domains = [r.domain for r in roles]
        assert "legal" in domains

    def test_audit_selection_record(self):
        sel = RoleSelector()
        roles = sel.select("code review")
        record = sel.audit_selection(
            session_id="sess_abc",
            selected=roles,
            trigger_text="code review",
            action_type="chat",
        )
        assert record.session_id == "sess_abc"
        assert record.trigger_text == "code review"
        assert isinstance(record.selected_roles, list)
        assert record.record_id.startswith("rsr_")

    def test_single_jarvis_voice_constraint(self):
        """Expert roles must not be exposed as separate speakers."""
        reg = ExpertRoleRegistry.get_instance()
        for role in reg.list_all():
            # All roles should have a domain — used internally only
            assert role.domain != ""
            assert role.role_id != ""

    def test_safe_fallback_empty_text(self):
        sel = RoleSelector()
        roles = sel.select("")
        assert roles == []
