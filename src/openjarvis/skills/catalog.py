"""Jarvis Skill Catalog — registers real skills mapped to real tools.

Skills are compound capabilities. Each skill's status is computed from
real ToolRegistry availability — no fake count inflation.
"""

from __future__ import annotations

import logging

from openjarvis.skills.jarvis_registry import SkillRegistry, SkillSpec, SkillStatus

logger = logging.getLogger(__name__)

_SKILL_DEFS = [
    SkillSpec(
        skill_id="mission_oversight",
        display_name="Mission Oversight",
        description=(
            "Full mission lifecycle management: list, retrieve, run passes, "
            "inspect tasks and events. Core daily driver for Jarvis."
        ),
        compatible_agent_ids=["manager", "architect", "qa"],
        required_tool_ids=[
            "mission.list",
            "mission.get",
            "mission.run_pass",
            "task.get",
            "event.list_recent",
        ],
        optional_tool_ids=[
            "task.update_status",
            "notify.status",
        ],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="medium",
        approval_policy="auto",
        examples=[
            "List all active missions",
            "Run a pass on mission abc123",
            "Get recent events for triage",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="governance_audit",
        display_name="Governance Audit",
        description=(
            "Run governance gate checks on proposed actions, verify approval "
            "requirements, and audit agent behavior against policy."
        ),
        compatible_agent_ids=["manager", "architect", "qa", "testing_bug"],
        required_tool_ids=["governance.gate_check"],
        optional_tool_ids=["agent.list"],
        project_scopes=[],
        memory_namespaces=["global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Check if 'real_slack_send' is hard-gated",
            "Verify agent 'deployment' requires approval",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="project_awareness",
        display_name="Project Awareness",
        description=(
            "Inspect the ProjectRegistry to understand active projects, "
            "memory namespaces, and cross-project scope."
        ),
        compatible_agent_ids=["manager", "architect", "research"],
        required_tool_ids=["project.list", "project.get"],
        optional_tool_ids=["agent.list"],
        project_scopes=[],
        memory_namespaces=["global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "List all active projects",
            "Get OMNIX project profile",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="memory_management",
        display_name="Memory Management",
        description=(
            "Write and search project-scoped Jarvis memory. "
            "Isolates entries by project namespace."
        ),
        compatible_agent_ids=["manager", "architect", "research", "docs_report"],
        required_tool_ids=["memory.write", "memory.search"],
        optional_tool_ids=[],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global", "agent:manager"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Write a note to project:omnix namespace",
            "Search memory for 'deployment blocker'",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="notify_operations",
        display_name="Notify Operations",
        description=(
            "Check notification channel status and send mission summaries "
            "via Slack or Telegram (explicit approval required for sends)."
        ),
        compatible_agent_ids=["manager"],
        required_tool_ids=["notify.status"],
        optional_tool_ids=["slack.notify_mission", "telegram.notify_mission"],
        project_scopes=[],
        memory_namespaces=[],
        risk_level="medium",
        approval_policy="requires_approval",
        examples=[
            "Check if Slack is configured",
            "Send mission summary to Slack (explicit approval required)",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="agent_discovery",
        display_name="Agent Discovery",
        description=(
            "Discover available specialist agents, their capabilities, "
            "tools, and permission levels."
        ),
        compatible_agent_ids=["manager"],
        required_tool_ids=["agent.list"],
        optional_tool_ids=[],
        project_scopes=[],
        memory_namespaces=[],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "List all specialist agents",
            "Find which agents can handle a coding task",
        ],
        status=SkillStatus.AVAILABLE,
    ),
]


def _is_already_initialized() -> bool:
    return SkillRegistry.get("mission_oversight") is not None


def initialize_catalog() -> None:
    """Register all catalog skills into SkillRegistry.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_already_initialized():
        return
    for spec in _SKILL_DEFS:
        SkillRegistry.register(spec)
    # Sprint 5 workflow skills — registered after Sprint 4 base skills
    from openjarvis.skills.workflow_catalog import initialize_workflow_skills_catalog
    initialize_workflow_skills_catalog()
    stats = SkillRegistry.stats()
    logger.info(
        "Skill catalog initialized: %d total, %d available",
        stats["total_registered"],
        stats["available"],
    )


__all__ = ["initialize_catalog"]
