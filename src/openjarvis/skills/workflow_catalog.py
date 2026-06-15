"""Jarvis Skill Workflow Catalog — Ultra Sprint 5 workflow skills.

15 new skills mapped to real Sprint 5 workflow tools.
Status is computed live from ToolRegistry — no cached/hardcoded state.
No fake count inflation.
"""

from __future__ import annotations

import logging

from openjarvis.skills.jarvis_registry import SkillRegistry, SkillSpec, SkillStatus

logger = logging.getLogger(__name__)

_WORKFLOW_SKILL_DEFS = [
    # ---- Phase B skills ----
    SkillSpec(
        skill_id="omnix_project_oversight",
        display_name="OMNIX Project Oversight",
        description=(
            "Full project supervision for OMNIX (Project 1): status check, "
            "handoff read, repo branch/commits, and project mission report. "
            "Works through project_id — supports future projects."
        ),
        compatible_agent_ids=["manager", "architect", "qa"],
        required_tool_ids=[
            "project.status",
            "project.handoff_read",
            "repo.status",
            "repo.branch_info",
            "mission.project_report",
        ],
        optional_tool_ids=[
            "repo.recent_commits",
            "report.generate_status",
        ],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Get OMNIX project status including repo and handoff",
            "Check what branch and HEAD the OMNIX repo is on",
            "List missions for OMNIX project",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="coding_quality_gate",
        display_name="Coding Quality Gate",
        description=(
            "Code quality and change inspection: repo status, diff summary, "
            "test discovery and targeted runs, acceptance evidence check."
        ),
        compatible_agent_ids=["manager", "architect", "testing_bug", "qa"],
        required_tool_ids=[
            "repo.status",
            "repo.diff_summary",
            "tests.discover",
            "tests.run_targeted",
            "qa.check_acceptance_evidence",
        ],
        optional_tool_ids=[
            "tests.report_summary",
            "governance.classify_report",
        ],
        project_scopes=[],
        memory_namespaces=["project:omnix"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Check if repo is clean and all tests pass",
            "Run targeted tests for a changed module",
            "Verify acceptance evidence for a PR",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="qa_acceptance_review",
        display_name="QA Acceptance Review",
        description=(
            "Structured QA review: check acceptance evidence, classify governance "
            "verdicts, build blocker reports for missing items."
        ),
        compatible_agent_ids=["qa", "manager", "testing_bug"],
        required_tool_ids=[
            "qa.check_acceptance_evidence",
            "governance.classify_report",
            "governance.build_blocker_report",
        ],
        optional_tool_ids=["governance.gate_check"],
        project_scopes=[],
        memory_namespaces=["global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Run QA acceptance review for Ultra Sprint 5",
            "Classify a proposed action's governance category",
            "Build a blocker report for a missing dependency",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="test_and_report",
        display_name="Test and Report",
        description=(
            "Discover, run, and report on targeted tests. "
            "Safe: pytest only, within project repo, 120s timeout."
        ),
        compatible_agent_ids=["testing_bug", "qa", "manager"],
        required_tool_ids=[
            "tests.discover",
            "tests.run_targeted",
            "tests.report_summary",
        ],
        optional_tool_ids=["memory.record_validation"],
        project_scopes=[],
        memory_namespaces=["project:omnix"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Discover all test files in the repo",
            "Run tests/tools/test_tool_registry.py and summarize results",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="handoff_management",
        display_name="Handoff Management",
        description=(
            "Read and update project handoff documentation. "
            "Writes only to registered handoff_paths — safe draft updates."
        ),
        compatible_agent_ids=["manager", "docs_report", "architect"],
        required_tool_ids=[
            "project.handoff_read",
            "project.handoff_update_plan",
        ],
        optional_tool_ids=["memory.record_decision"],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Read the OMNIX handoff document",
            "Append a draft plan update to the handoff",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="blocker_triage",
        display_name="Blocker Triage",
        description=(
            "Triage and document blockers: classify actions, build structured "
            "blocker reports, record in project memory."
        ),
        compatible_agent_ids=["manager", "architect", "testing_bug"],
        required_tool_ids=[
            "governance.build_blocker_report",
            "governance.classify_report",
            "memory.record_blocker",
        ],
        optional_tool_ids=["governance.gate_check"],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Build a blocker report for a missing API key",
            "Record a deployment blocker in OMNIX project memory",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    # ---- Phase C skills ----
    SkillSpec(
        skill_id="research_briefing",
        display_name="Research Briefing",
        description=(
            "Research, summarize and brief: summarize text, write research briefs "
            "to memory, capture sources. web.search is optional (requires TAVILY_API_KEY)."
        ),
        compatible_agent_ids=["research", "manager"],
        required_tool_ids=[
            "docs.summarize_text",
            "sources.capture",
            "research.brief",
        ],
        optional_tool_ids=["web.search", "web.fetch_url"],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Summarize a document and save to project memory",
            "Write a research brief on a technical topic",
            "Capture a URL source for later retrieval",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="source_review",
        display_name="Source Review",
        description=(
            "Review and capture sources: fetch URLs, summarize content, "
            "store in project memory."
        ),
        compatible_agent_ids=["research", "manager"],
        required_tool_ids=[
            "docs.summarize_text",
            "sources.capture",
        ],
        optional_tool_ids=["web.fetch_url", "browser.open_url"],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Fetch a URL and summarize its content",
            "Capture a document source into OMNIX memory",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    # ---- Phase D skills ----
    SkillSpec(
        skill_id="notification_drafting",
        display_name="Notification Drafting",
        description=(
            "Draft Slack and Telegram messages for review. "
            "Does NOT send — use explicit approval for actual sends."
        ),
        compatible_agent_ids=["manager"],
        required_tool_ids=[
            "notify.status",
            "slack.draft_update",
            "telegram.draft_alert",
        ],
        optional_tool_ids=["slack.notify_mission", "telegram.notify_mission"],
        project_scopes=[],
        memory_namespaces=[],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Draft a Slack status update for OMNIX",
            "Draft a Telegram alert for a blocked mission",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="daily_project_report",
        display_name="Daily Project Report",
        description=(
            "Generate daily status reports and digests: project status, "
            "mission digest, memory summary."
        ),
        compatible_agent_ids=["manager", "docs_report"],
        required_tool_ids=[
            "report.generate_status",
            "report.generate_daily_digest",
        ],
        optional_tool_ids=["memory.project_summary"],
        project_scopes=[],
        memory_namespaces=["project:omnix"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Generate today's OMNIX project status report",
            "Generate a daily digest of active and blocked missions",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="approval_summary",
        display_name="Approval Summary",
        description=(
            "Summarize pending approvals from the ApprovalStore. "
            "Supports governance gate checks on queued items."
        ),
        compatible_agent_ids=["manager"],
        required_tool_ids=["approval.queue_summary"],
        optional_tool_ids=["governance.gate_check"],
        project_scopes=[],
        memory_namespaces=[],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "List all pending approval queue items",
            "Check which queued actions are hard-gated",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    # ---- Phase E skills ----
    SkillSpec(
        skill_id="project_memory_management",
        display_name="Project Memory Management",
        description=(
            "Read and manage project-scoped memory: summarize, list recent entries, "
            "search across namespaces."
        ),
        compatible_agent_ids=["manager", "architect", "research", "docs_report"],
        required_tool_ids=[
            "memory.project_summary",
            "memory.list_recent_project_entries",
            "memory.write",
        ],
        optional_tool_ids=["memory.search"],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "List recent memory entries for OMNIX project",
            "Summarize all entries in the project:omnix namespace",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="decision_log_management",
        display_name="Decision Log Management",
        description=(
            "Record and retrieve project decisions in memory. "
            "Structured [DECISION] entries for auditability."
        ),
        compatible_agent_ids=["manager", "architect"],
        required_tool_ids=[
            "memory.record_decision",
            "memory.search",
        ],
        optional_tool_ids=["memory.project_summary"],
        project_scopes=[],
        memory_namespaces=["project:omnix", "global"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Record a technical architecture decision for OMNIX",
            "Search for past decisions about 'deployment'",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="bug_fix_memory",
        display_name="Bug and Fix Memory",
        description=(
            "Record bugs and fixes in project-scoped memory. "
            "Structured [BUG] and [FIX] entries for regression tracking."
        ),
        compatible_agent_ids=["testing_bug", "manager", "architect"],
        required_tool_ids=[
            "memory.record_bug",
            "memory.record_fix",
            "memory.search",
        ],
        optional_tool_ids=["memory.record_blocker"],
        project_scopes=[],
        memory_namespaces=["project:omnix"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Record a bug found in the tool registry",
            "Record the fix applied and link to the bug",
        ],
        status=SkillStatus.AVAILABLE,
    ),
    SkillSpec(
        skill_id="validation_memory",
        display_name="Validation Memory",
        description=(
            "Record validation and acceptance results in memory. "
            "Links QA evidence to project-scoped [VALIDATION] entries."
        ),
        compatible_agent_ids=["qa", "manager", "testing_bug"],
        required_tool_ids=[
            "memory.record_validation",
            "qa.check_acceptance_evidence",
        ],
        optional_tool_ids=["memory.search"],
        project_scopes=[],
        memory_namespaces=["project:omnix"],
        risk_level="low",
        approval_policy="auto",
        examples=[
            "Record Ultra Sprint 5 ACCEPT validation in OMNIX memory",
            "Check acceptance evidence and store result",
        ],
        status=SkillStatus.AVAILABLE,
    ),
]


def _is_workflow_skills_initialized() -> bool:
    return SkillRegistry.get("omnix_project_oversight") is not None


def initialize_workflow_skills_catalog() -> None:
    """Register all Sprint 5 workflow skills into SkillRegistry.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_workflow_skills_initialized():
        return
    for spec in _WORKFLOW_SKILL_DEFS:
        SkillRegistry.register(spec)
    stats = SkillRegistry.stats()
    logger.info(
        "Workflow skills catalog initialized: total=%d available=%d",
        stats["total_registered"],
        stats["available"],
    )


__all__ = ["initialize_workflow_skills_catalog"]
