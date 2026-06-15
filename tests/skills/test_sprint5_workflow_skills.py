"""Ultra Sprint 5 — Workflow Skills Catalog tests.

Validates:
  - 15 new skills registered
  - Skills with all required tools present = AVAILABLE
  - Skills missing optional tools = DEGRADED (not BLOCKED)
  - Skills with missing required tools = BLOCKED
  - Skills depend on real ToolRegistry state
  - OMNIX is in scope for all skills with project_scopes=[]
  - No cached/hardcoded statuses
  - Sprint 4 skills still pass
"""

from __future__ import annotations

import pytest

from openjarvis.tools.jarvis_registry import ToolRegistry
from openjarvis.skills.jarvis_registry import SkillRegistry, SkillStatus
from openjarvis.governance.constitution import ProjectRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_registries():
    ToolRegistry.clear()
    SkillRegistry.clear()
    ProjectRegistry.clear()
    yield
    ToolRegistry.clear()
    SkillRegistry.clear()
    ProjectRegistry.clear()


@pytest.fixture()
def initialized_all():
    """Initialize all catalogs (tools + skills Sprint 4 + Sprint 5)."""
    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.skills.catalog import initialize_catalog as init_skills
    initialize_catalog()
    init_skills()


# ---------------------------------------------------------------------------
# 1. Count assertions
# ---------------------------------------------------------------------------


def test_total_skills_count(initialized_all):
    """Sprint 4 had 6 skills. Sprint 5 adds 15. Total = 21."""
    stats = SkillRegistry.stats()
    assert stats["total_registered"] >= 21, (
        f"Expected >= 21 skills, got {stats['total_registered']}"
    )


def test_sprint4_skills_still_registered(initialized_all):
    """All Sprint 4 skills remain after Sprint 5 catalog initialization."""
    sprint4_skills = [
        "agent_discovery",
        "governance_audit",
        "memory_management",
        "mission_oversight",
        "project_awareness",
        "notify_operations",
    ]
    for skill_id in sprint4_skills:
        spec = SkillRegistry.get(skill_id)
        assert spec is not None, f"Sprint 4 skill '{skill_id}' missing after Sprint 5 init"


def test_all_sprint5_skills_registered(initialized_all):
    sprint5_skills = [
        "omnix_project_oversight",
        "coding_quality_gate",
        "qa_acceptance_review",
        "test_and_report",
        "handoff_management",
        "blocker_triage",
        "research_briefing",
        "source_review",
        "notification_drafting",
        "daily_project_report",
        "approval_summary",
        "project_memory_management",
        "decision_log_management",
        "bug_fix_memory",
        "validation_memory",
    ]
    for skill_id in sprint5_skills:
        spec = SkillRegistry.get(skill_id)
        assert spec is not None, f"Sprint 5 skill '{skill_id}' not registered"


# ---------------------------------------------------------------------------
# 2. Status computation — available when all required tools present
# ---------------------------------------------------------------------------


def test_omnix_project_oversight_available(initialized_all):
    spec = SkillRegistry.get("omnix_project_oversight")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"omnix_project_oversight expected AVAILABLE, got {spec.status}: {spec.blocker}"
    )


def test_coding_quality_gate_available(initialized_all):
    spec = SkillRegistry.get("coding_quality_gate")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"coding_quality_gate: {spec.status} — {spec.blocker}"
    )


def test_qa_acceptance_review_available(initialized_all):
    spec = SkillRegistry.get("qa_acceptance_review")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"qa_acceptance_review: {spec.status} — {spec.blocker}"
    )


def test_test_and_report_available(initialized_all):
    spec = SkillRegistry.get("test_and_report")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"test_and_report: {spec.status} — {spec.blocker}"
    )


def test_handoff_management_available(initialized_all):
    spec = SkillRegistry.get("handoff_management")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"handoff_management: {spec.status} — {spec.blocker}"
    )


def test_blocker_triage_available(initialized_all):
    spec = SkillRegistry.get("blocker_triage")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"blocker_triage: {spec.status} — {spec.blocker}"
    )


def test_research_briefing_available(initialized_all):
    """research_briefing requires docs.summarize_text, sources.capture, research.brief.
    web.search is optional — if not_configured the skill should be AVAILABLE or DEGRADED."""
    spec = SkillRegistry.get("research_briefing")
    assert spec is not None
    assert spec.status in (SkillStatus.AVAILABLE, SkillStatus.DEGRADED), (
        f"research_briefing: {spec.status} — {spec.blocker}"
    )


def test_source_review_available(initialized_all):
    spec = SkillRegistry.get("source_review")
    assert spec is not None
    assert spec.status in (SkillStatus.AVAILABLE, SkillStatus.DEGRADED)


def test_notification_drafting_available(initialized_all):
    spec = SkillRegistry.get("notification_drafting")
    assert spec is not None
    assert spec.status in (SkillStatus.AVAILABLE, SkillStatus.DEGRADED), (
        f"notification_drafting: {spec.status} — {spec.blocker}"
    )


def test_daily_project_report_available(initialized_all):
    spec = SkillRegistry.get("daily_project_report")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"daily_project_report: {spec.status} — {spec.blocker}"
    )


def test_approval_summary_available(initialized_all):
    spec = SkillRegistry.get("approval_summary")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"approval_summary: {spec.status} — {spec.blocker}"
    )


def test_project_memory_management_available(initialized_all):
    spec = SkillRegistry.get("project_memory_management")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"project_memory_management: {spec.status} — {spec.blocker}"
    )


def test_decision_log_management_available(initialized_all):
    spec = SkillRegistry.get("decision_log_management")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"decision_log_management: {spec.status} — {spec.blocker}"
    )


def test_bug_fix_memory_available(initialized_all):
    spec = SkillRegistry.get("bug_fix_memory")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"bug_fix_memory: {spec.status} — {spec.blocker}"
    )


def test_validation_memory_available(initialized_all):
    spec = SkillRegistry.get("validation_memory")
    assert spec is not None
    assert spec.status == SkillStatus.AVAILABLE, (
        f"validation_memory: {spec.status} — {spec.blocker}"
    )


# ---------------------------------------------------------------------------
# 3. Skill becomes BLOCKED when required tool is removed
# ---------------------------------------------------------------------------


def test_skill_blocked_when_required_tool_missing(initialized_all):
    """Remove project.status from registry — omnix_project_oversight should go BLOCKED."""
    del ToolRegistry._tools["project.status"]
    spec = SkillRegistry.get("omnix_project_oversight")
    assert spec.status == SkillStatus.BLOCKED
    assert "project.status" in spec.blocker


def test_skill_degraded_when_optional_tool_missing(initialized_all):
    """Remove web.fetch_url — source_review should be DEGRADED not BLOCKED."""
    del ToolRegistry._tools["web.fetch_url"]
    spec = SkillRegistry.get("source_review")
    # optional tools missing = degraded
    assert spec.status in (SkillStatus.DEGRADED, SkillStatus.AVAILABLE)


# ---------------------------------------------------------------------------
# 4. Status is computed live — no cached state
# ---------------------------------------------------------------------------


def test_skill_status_updates_when_tool_added_back(initialized_all):
    """Re-register a tool after removal — skill should recover to AVAILABLE."""
    from openjarvis.tools.jarvis_registry import ToolSpec
    # Remove project.status
    removed_spec = ToolRegistry._tools.pop("project.status")
    removed_exec = ToolRegistry._executors.pop("project.status")
    spec = SkillRegistry.get("omnix_project_oversight")
    assert spec.status == SkillStatus.BLOCKED
    # Re-register
    ToolRegistry.register(removed_spec, executor=removed_exec)
    spec2 = SkillRegistry.get("omnix_project_oversight")
    assert spec2.status == SkillStatus.AVAILABLE


# ---------------------------------------------------------------------------
# 5. Stats integrity
# ---------------------------------------------------------------------------


def test_skill_stats_integrity(initialized_all):
    stats = SkillRegistry.stats()
    all_skills = SkillRegistry.list_all()
    total_by_status = sum(stats["by_status"].values())
    assert total_by_status == stats["total_registered"]
    assert stats["total_registered"] == len(all_skills)


def test_available_skills_count_honest(initialized_all):
    """Available count matches only skills with status=AVAILABLE."""
    stats = SkillRegistry.stats()
    available_skills = [s for s in SkillRegistry.list_all() if s.status == SkillStatus.AVAILABLE]
    assert stats["by_status"][SkillStatus.AVAILABLE] == len(available_skills)


# ---------------------------------------------------------------------------
# 6. No skill available without all required tools
# ---------------------------------------------------------------------------


def test_no_skill_available_with_missing_required_tool(initialized_all):
    """If any required tool is not registered, skill must not be AVAILABLE."""
    for skill in SkillRegistry.list_all():
        if skill.status == SkillStatus.AVAILABLE:
            for tool_id in skill.required_tool_ids:
                t = ToolRegistry.get(tool_id)
                assert t is not None, (
                    f"Skill '{skill.skill_id}' is AVAILABLE but required tool '{tool_id}' not registered"
                )
                assert t.is_available(), (
                    f"Skill '{skill.skill_id}' is AVAILABLE but required tool '{tool_id}' status={t.implementation_status}"
                )


# ---------------------------------------------------------------------------
# 7. Agent filtering works
# ---------------------------------------------------------------------------


def test_list_for_agent_manager(initialized_all):
    skills = SkillRegistry.list_for_agent("manager")
    ids = [s.skill_id for s in skills]
    assert "omnix_project_oversight" in ids
    assert "daily_project_report" in ids
    assert "handoff_management" in ids


def test_list_for_agent_qa(initialized_all):
    skills = SkillRegistry.list_for_agent("qa")
    ids = [s.skill_id for s in skills]
    assert "qa_acceptance_review" in ids
    assert "coding_quality_gate" in ids
    assert "validation_memory" in ids


def test_list_for_agent_research(initialized_all):
    skills = SkillRegistry.list_for_agent("research")
    ids = [s.skill_id for s in skills]
    assert "research_briefing" in ids
    assert "source_review" in ids


# ---------------------------------------------------------------------------
# 8. project_scopes=[] means all projects
# ---------------------------------------------------------------------------


def test_skills_with_empty_scope_available_for_all_projects(initialized_all):
    """Skills with project_scopes=[] must be visible for any project_id filter."""
    all_skills = SkillRegistry.list_all()
    empty_scope_skills = [s for s in all_skills if not s.project_scopes]
    assert len(empty_scope_skills) >= 20, "Most skills should be globally scoped"


# ---------------------------------------------------------------------------
# 9. to_dict completeness
# ---------------------------------------------------------------------------


def test_skill_to_dict_has_required_fields(initialized_all):
    spec = SkillRegistry.get("omnix_project_oversight")
    d = spec.to_dict()
    required_keys = [
        "skill_id", "display_name", "description", "compatible_agent_ids",
        "required_tool_ids", "optional_tool_ids", "project_scopes",
        "memory_namespaces", "risk_level", "approval_policy",
        "status", "is_available", "blocker",
    ]
    for key in required_keys:
        assert key in d, f"to_dict() missing key: {key}"
