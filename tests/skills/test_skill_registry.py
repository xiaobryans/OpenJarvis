"""Ultra Sprint 4 — Skill Registry tests.

Covers:
  1.  SkillRegistry registers skills
  2.  Skill becomes available when all required tools available
  3.  Skill becomes blocked when required tool missing
  4.  Skill becomes not_configured when required tool not_configured
  5.  Skill becomes degraded when optional tool missing
  6.  Agent/tool discovery: list_for_agent filters correctly
  7.  Skill catalog initializes correctly
  8.  mission_oversight skill exists and maps to real tools
  9.  governance_audit skill maps to governance.gate_check
  10. memory_management skill maps to memory.write + memory.search
  11. project_awareness skill maps to project.list + project.get
  12. notify_operations skill has notify.status as required tool
  13. SkillSpec.to_dict() has all required fields
  14. SkillRegistry.stats() reports accurate counts
  15. Planned skill status is never auto-computed to available
"""

from __future__ import annotations

import pytest

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus
from openjarvis.skills.jarvis_registry import SkillRegistry, SkillSpec, SkillStatus
from openjarvis.governance.constitution import ProjectRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset():
    ToolRegistry.clear()
    SkillRegistry.clear()
    ProjectRegistry.clear()
    yield
    ToolRegistry.clear()
    SkillRegistry.clear()
    ProjectRegistry.clear()


def _make_tool(tool_id: str, status: str = ToolStatus.AVAILABLE, configured: bool = True) -> ToolSpec:
    return ToolSpec(
        tool_id=tool_id,
        display_name=tool_id,
        description="test tool",
        category="test",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        required_permissions=[],
        risk_level="low",
        project_scope=[],
        enabled=True,
        configured=configured,
        approval_required=False,
        owning_agent_id="manager",
        executor_ref="noop",
        implementation_status=status,
        blocker="" if status == ToolStatus.AVAILABLE else "not available",
    )


def _noop(inputs, context=None):
    return {}


def _make_skill(
    skill_id: str,
    required: list,
    optional: list = None,
    agents: list = None,
    status: str = SkillStatus.AVAILABLE,
) -> SkillSpec:
    return SkillSpec(
        skill_id=skill_id,
        display_name=skill_id,
        description="test skill",
        compatible_agent_ids=agents or [],
        required_tool_ids=required,
        optional_tool_ids=optional or [],
        project_scopes=[],
        memory_namespaces=[],
        risk_level="low",
        approval_policy="auto",
        examples=[],
        status=status,
    )


# ---------------------------------------------------------------------------
# 1–6: Registry logic
# ---------------------------------------------------------------------------


def test_skill_registers():
    SkillRegistry.register(_make_skill("s.basic", required=[], status=SkillStatus.AVAILABLE))
    assert SkillRegistry.get("s.basic") is not None


def test_skill_available_when_required_tools_available():
    ToolRegistry.register(_make_tool("t.a"), executor=_noop)
    SkillRegistry.register(_make_skill("s.avail", required=["t.a"], status=SkillStatus.AVAILABLE))
    skill = SkillRegistry.get("s.avail")
    assert skill.status == SkillStatus.AVAILABLE
    assert skill.is_available()


def test_skill_blocked_when_required_tool_missing():
    SkillRegistry.register(_make_skill("s.block", required=["t.missing"], status=SkillStatus.AVAILABLE))
    skill = SkillRegistry.get("s.block")
    assert skill.status == SkillStatus.BLOCKED
    assert "t.missing" in skill.blocker
    assert not skill.is_available()


def test_skill_not_configured_when_required_tool_not_configured():
    nc_tool = _make_tool("t.nc", status=ToolStatus.NOT_CONFIGURED, configured=False)
    ToolRegistry.register(nc_tool, executor=_noop)
    SkillRegistry.register(_make_skill("s.nc", required=["t.nc"], status=SkillStatus.AVAILABLE))
    skill = SkillRegistry.get("s.nc")
    assert skill.status == SkillStatus.NOT_CONFIGURED
    assert "t.nc" in skill.blocker


def test_skill_degraded_when_optional_tool_missing():
    ToolRegistry.register(_make_tool("t.req"), executor=_noop)
    SkillRegistry.register(_make_skill(
        "s.degraded", required=["t.req"], optional=["t.opt_missing"],
        status=SkillStatus.AVAILABLE,
    ))
    skill = SkillRegistry.get("s.degraded")
    assert skill.status == SkillStatus.DEGRADED
    assert "t.opt_missing" in skill.blocker


def test_skill_fully_available_all_tools_present():
    ToolRegistry.register(_make_tool("t.r1"), executor=_noop)
    ToolRegistry.register(_make_tool("t.r2"), executor=_noop)
    ToolRegistry.register(_make_tool("t.o1"), executor=_noop)
    SkillRegistry.register(_make_skill(
        "s.full", required=["t.r1", "t.r2"], optional=["t.o1"],
        status=SkillStatus.AVAILABLE,
    ))
    skill = SkillRegistry.get("s.full")
    assert skill.status == SkillStatus.AVAILABLE
    assert skill.blocker == ""


def test_list_for_agent_filters_by_agent():
    SkillRegistry.register(_make_skill("s.all", required=[], agents=[], status=SkillStatus.AVAILABLE))
    SkillRegistry.register(_make_skill("s.mgr", required=[], agents=["manager"], status=SkillStatus.AVAILABLE))
    SkillRegistry.register(_make_skill("s.arch", required=[], agents=["architect"], status=SkillStatus.AVAILABLE))

    manager_skills = SkillRegistry.list_for_agent("manager")
    skill_ids = {s.skill_id for s in manager_skills}
    assert "s.mgr" in skill_ids
    assert "s.all" in skill_ids
    assert "s.arch" not in skill_ids


def test_planned_skill_stays_planned():
    SkillRegistry.register(_make_skill("s.plan", required=["t.anything"], status=SkillStatus.PLANNED))
    skill = SkillRegistry.get("s.plan")
    assert skill.status == SkillStatus.PLANNED


# ---------------------------------------------------------------------------
# 7–12: Skill catalog integration
# ---------------------------------------------------------------------------


@pytest.fixture()
def full_catalog():
    """Initialize both tool and skill catalogs for integration tests."""
    from openjarvis.tools.catalog import initialize_catalog as init_tools
    from openjarvis.skills.catalog import initialize_catalog as init_skills
    init_tools()
    init_skills()


def test_skill_catalog_initializes(full_catalog):
    skills = SkillRegistry.list_all()
    assert len(skills) >= 6


def test_mission_oversight_skill_exists(full_catalog):
    skill = SkillRegistry.get("mission_oversight")
    assert skill is not None
    assert "mission.list" in skill.required_tool_ids
    assert "mission.get" in skill.required_tool_ids
    assert "mission.run_pass" in skill.required_tool_ids


def test_governance_audit_skill_maps_to_gate_check(full_catalog):
    skill = SkillRegistry.get("governance_audit")
    assert skill is not None
    assert "governance.gate_check" in skill.required_tool_ids


def test_memory_management_skill_maps_to_memory_tools(full_catalog):
    skill = SkillRegistry.get("memory_management")
    assert skill is not None
    assert "memory.write" in skill.required_tool_ids
    assert "memory.search" in skill.required_tool_ids


def test_project_awareness_skill_maps_to_project_tools(full_catalog):
    skill = SkillRegistry.get("project_awareness")
    assert skill is not None
    assert "project.list" in skill.required_tool_ids
    assert "project.get" in skill.required_tool_ids


def test_notify_operations_skill_has_notify_status(full_catalog):
    skill = SkillRegistry.get("notify_operations")
    assert skill is not None
    assert "notify.status" in skill.required_tool_ids


# ---------------------------------------------------------------------------
# 13–15: Structure and stats
# ---------------------------------------------------------------------------


def test_skill_spec_to_dict_has_required_fields():
    skill = _make_skill("s.dict", required=[], status=SkillStatus.AVAILABLE)
    d = skill.to_dict()
    for key in [
        "skill_id", "display_name", "description", "compatible_agent_ids",
        "required_tool_ids", "optional_tool_ids", "project_scopes",
        "memory_namespaces", "risk_level", "approval_policy", "examples",
        "status", "is_available", "blocker", "created_at",
    ]:
        assert key in d, f"Missing key: {key}"


def test_skill_registry_stats_accurate(full_catalog):
    stats = SkillRegistry.stats()
    assert stats["total_registered"] >= 6
    assert stats["available"] <= stats["total_registered"]
    available_list = SkillRegistry.list_available()
    assert stats["available"] == len(available_list)
