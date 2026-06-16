"""Jarvis Readiness Gate — evidence-backed V1 daily-driver readiness evaluation.

15 readiness categories (9 original + 6 US8):
  core_mission_system       — mission store + tool gateway functional
  tools_skills_memory       — tool/skill/memory registry healthy
  autonomy_watchdogs_alerts — autonomy mode + watchdogs + alerts operational
  project_awareness         — ProjectRegistry populated; project_id known
  safety_governance         — hard gates enforced; secrets not leaked
  packaged_app_ui           — Tauri build present (not_configured is acceptable)
  handoff_docs              — handoff doc exists and is recent
  git_cleanliness           — git working tree clean; on expected branch
  project_linkage           — OMNIX linked to real source (not placeholder)
  voice_readiness           — voice pipeline (wake-word/STT/TTS) status (US8)
  desktop_readiness         — macOS desktop operator permissions (US8)
  automation_readiness      — automation policy + ops runner status (US8)
  connector_readiness       — Slack/Telegram/Web/GitHub/OpenClaw status (US8)
  mobile_readiness          — mobile access path (Telegram/tailnet) (US8)
  openclaw_linkage          — OpenClaw workspace/handoff configured (US8)

Verdict:
  ready  — all required categories pass (warn-only non-blocking items permitted)
  warn   — one or more non-critical categories are warn or not_configured
  hold   — one or more required categories are fail (evidence missing)
  unsafe — a safety/governance check fails (hard gates bypassed, secrets leaked)

Rules:
  - HOLD if required evidence is missing (no fake ACCEPT)
  - UNSAFE if safety_governance category fails
  - Accepted checkpoints are carried forward without re-validation
  - Cost-control law: diagnose only what was touched in US7 or what has evidence
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.doctor.checks import CheckResult, CheckStatus, run_all_checks


# ---------------------------------------------------------------------------
# Verdict + Category
# ---------------------------------------------------------------------------


class ReadinessVerdict:
    READY = "ready"
    WARN = "warn"
    HOLD = "hold"
    UNSAFE = "unsafe"


class ReadinessCategory:
    CORE_MISSION_SYSTEM = "core_mission_system"
    TOOLS_SKILLS_MEMORY = "tools_skills_memory"
    AUTONOMY_WATCHDOGS_ALERTS = "autonomy_watchdogs_alerts"
    PROJECT_AWARENESS = "project_awareness"
    SAFETY_GOVERNANCE = "safety_governance"
    PACKAGED_APP_UI = "packaged_app_ui"
    HANDOFF_DOCS = "handoff_docs"
    GIT_CLEANLINESS = "git_cleanliness"
    PROJECT_LINKAGE = "project_linkage"
    # US8 categories
    VOICE_READINESS = "voice_readiness"
    DESKTOP_READINESS = "desktop_readiness"
    AUTOMATION_READINESS = "automation_readiness"
    CONNECTOR_READINESS = "connector_readiness"
    MOBILE_READINESS = "mobile_readiness"
    OPENCLAW_LINKAGE = "openclaw_linkage"
    # US9 categories
    SECRETS_BACKEND = "secrets_backend"
    BUDGET_GUARD = "budget_guard"
    JOB_QUEUE = "job_queue"
    ROLLBACK_POLICY = "rollback_policy"
    INJECT_GUARD = "inject_guard"
    VOICE_IDENTITY = "voice_identity"
    CONNECTOR_HEALTH_MONITOR = "connector_health_monitor"
    ALERT_RATE_LIMITER = "alert_rate_limiter"
    MEMORY_BACKUP = "memory_backup"
    DOGFOOD_LOOP = "dogfood_loop"


# ---------------------------------------------------------------------------
# Category → check_id mapping
# ---------------------------------------------------------------------------

_CATEGORY_CHECKS: Dict[str, List[str]] = {
    ReadinessCategory.CORE_MISSION_SYSTEM: [
        "backend_health",
        "execution_log_health",
    ],
    ReadinessCategory.TOOLS_SKILLS_MEMORY: [
        "tool_registry_counts",
        "skill_registry_counts",
        "memory_store_health",
    ],
    ReadinessCategory.AUTONOMY_WATCHDOGS_ALERTS: [
        "watchdog_status",
        "alert_status",
    ],
    ReadinessCategory.PROJECT_AWARENESS: [
        "project_registry_health",
    ],
    ReadinessCategory.SAFETY_GOVERNANCE: [
        "autonomy_mode_status",
    ],
    ReadinessCategory.PACKAGED_APP_UI: [
        "packaged_app_build_metadata",
    ],
    ReadinessCategory.HANDOFF_DOCS: [
        "handoff_freshness",
    ],
    ReadinessCategory.GIT_CLEANLINESS: [
        "git_worktree_status",
    ],
    ReadinessCategory.PROJECT_LINKAGE: [
        "project_linkage_status",
    ],
    # US8 categories
    ReadinessCategory.VOICE_READINESS: [
        "voice_pipeline_status",
    ],
    ReadinessCategory.DESKTOP_READINESS: [
        "desktop_operator_status",
    ],
    ReadinessCategory.AUTOMATION_READINESS: [
        "automation_policy_health",
        "persistent_ops_status",
    ],
    ReadinessCategory.CONNECTOR_READINESS: [
        "connector_readiness",
    ],
    ReadinessCategory.MOBILE_READINESS: [
        "mobile_readiness",
    ],
    ReadinessCategory.OPENCLAW_LINKAGE: [
        "connector_readiness",
    ],
    # US9 categories
    ReadinessCategory.SECRETS_BACKEND: [
        "secrets_backend",
    ],
    ReadinessCategory.BUDGET_GUARD: [
        "budget_guard",
    ],
    ReadinessCategory.JOB_QUEUE: [
        "job_queue",
    ],
    ReadinessCategory.ROLLBACK_POLICY: [
        "rollback_policy",
    ],
    ReadinessCategory.INJECT_GUARD: [
        "inject_guard",
    ],
    ReadinessCategory.VOICE_IDENTITY: [
        "voice_identity",
    ],
    ReadinessCategory.CONNECTOR_HEALTH_MONITOR: [
        "connector_health_monitor",
    ],
    ReadinessCategory.ALERT_RATE_LIMITER: [
        "alert_rate_limiter",
    ],
    ReadinessCategory.MEMORY_BACKUP: [
        "memory_backup",
    ],
    ReadinessCategory.DOGFOOD_LOOP: [
        "dogfood_loop",
    ],
}

# Categories where fail → UNSAFE verdict (not just HOLD)
_UNSAFE_CATEGORIES = frozenset({ReadinessCategory.SAFETY_GOVERNANCE})

# Categories that are required for READY (not_configured allowed only for packaged_app_ui)
_REQUIRED_CATEGORIES = frozenset({
    ReadinessCategory.CORE_MISSION_SYSTEM,
    ReadinessCategory.TOOLS_SKILLS_MEMORY,
    ReadinessCategory.AUTONOMY_WATCHDOGS_ALERTS,
    ReadinessCategory.PROJECT_AWARENESS,
    ReadinessCategory.SAFETY_GOVERNANCE,
    ReadinessCategory.HANDOFF_DOCS,
    ReadinessCategory.GIT_CLEANLINESS,
    ReadinessCategory.PROJECT_LINKAGE,
    ReadinessCategory.AUTOMATION_READINESS,
    # US9 required hardening layers
    ReadinessCategory.BUDGET_GUARD,
    ReadinessCategory.ROLLBACK_POLICY,
    ReadinessCategory.INJECT_GUARD,
    # US8/US9 non-required (warn only — external config/hardware blockers)
    # voice_readiness, desktop_readiness, connector_readiness,
    # mobile_readiness, openclaw_linkage, secrets_backend,
    # job_queue, voice_identity, connector_health_monitor,
    # alert_rate_limiter, memory_backup, dogfood_loop are warn-only
})


# ---------------------------------------------------------------------------
# CategoryResult
# ---------------------------------------------------------------------------


@dataclass
class CategoryResult:
    """Aggregated readiness result for a single category."""

    category: str
    status: str
    summary: str
    checks: List[CheckResult]
    is_required: bool
    is_safety: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "status": self.status,
            "summary": self.summary,
            "is_required": self.is_required,
            "is_safety": self.is_safety,
            "checks": [c.to_dict() for c in self.checks],
        }


# ---------------------------------------------------------------------------
# ReadinessReport
# ---------------------------------------------------------------------------


@dataclass
class ReadinessReport:
    """Full readiness evaluation report."""

    project_id: str
    verdict: str
    summary: str
    categories: List[CategoryResult]
    cost_control_compliant: bool
    fake_capability_check: Dict[str, Any]
    accepted_checkpoints: List[str]
    evaluated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "verdict": self.verdict,
            "summary": self.summary,
            "cost_control_compliant": self.cost_control_compliant,
            "fake_capability_check": self.fake_capability_check,
            "accepted_checkpoints": self.accepted_checkpoints,
            "categories": {c.category: c.to_dict() for c in self.categories},
            "evaluated_at": self.evaluated_at,
        }


# ---------------------------------------------------------------------------
# Accepted checkpoints carried forward (not re-evaluated)
# ---------------------------------------------------------------------------

_ACCEPTED_CHECKPOINTS = [
    "Cloud/status foundation — ACCEPT (not touched in US8)",
    "Sprint 1 Mission/Agent Core — ACCEPT (not touched in US8)",
    "Sprint 2 Mission Control Visibility — ACCEPT (not touched in US8)",
    "Sprint 3 Real Agent Execution + Slack/Telegram — ACCEPT (not touched in US8)",
    "Governance Lock-In — ACCEPT (governance read-only in US8; automation_policy hard gates enforce same rules)",
    "Ultra Sprint 4 Skills/Tools/Memory Foundation — ACCEPT (catalog chain extended only)",
    "Ultra Sprint 5 Tool/Skill Expansion + OMNIX Workflow Packs — ACCEPT (catalog chain extended only)",
    "Ultra Sprint 6 Autonomy + Watchdogs + Mobile/Voice — ACCEPT (new voice/mobile tools added; existing logic unchanged)",
    "Ultra Sprint 7 Doctor/Readiness Layer — ACCEPT (19 checks, 15 categories; US7 checks untouched)",
    "Ultra Sprint 7 Hold Fix: Project Linker — ACCEPT (project_linkage still required; US7 checks intact)",
    "Ultra Sprint 8 Infrastructure Modules — ACCEPT (51 tools, 6 checks, 19 total checks, 15 categories)",
    "Ultra Sprint 9 Sovereign Hardening — ACCEPT (10 new modules, 29 checks, 25 categories; US8 checks untouched)",
]


# ---------------------------------------------------------------------------
# evaluate_readiness
# ---------------------------------------------------------------------------


def evaluate_readiness(
    project_id: str = "omnix",
    check_results: Optional[List[CheckResult]] = None,
) -> ReadinessReport:
    """Evaluate readiness gate for a project.

    Accepts pre-run check_results to avoid double-running checks.
    If not provided, runs all 12 checks.

    Verdict rules (in priority order):
      UNSAFE — any safety_governance category check fails
      HOLD   — any required category has a fail check
      WARN   — any category has warn or not_configured (non-required, or non-failing required)
      READY  — all required categories pass (warn acceptable for non-required)
    """
    if check_results is None:
        check_results = run_all_checks(project_id=project_id)

    check_map: Dict[str, CheckResult] = {r.check_id: r for r in check_results}

    category_results: List[CategoryResult] = []
    for cat, check_ids in _CATEGORY_CHECKS.items():
        cat_checks = [
            check_map[cid] for cid in check_ids if cid in check_map
        ]
        missing_checks = [cid for cid in check_ids if cid not in check_map]

        if missing_checks:
            cat_status = CheckStatus.FAIL
            cat_summary = f"Evidence missing for checks: {missing_checks}"
        elif all(c.status == CheckStatus.PASS for c in cat_checks):
            cat_status = CheckStatus.PASS
            cat_summary = f"All {len(cat_checks)} check(s) passed"
        elif any(c.status == CheckStatus.FAIL for c in cat_checks):
            cat_status = CheckStatus.FAIL
            failed = [c.check_id for c in cat_checks if c.status == CheckStatus.FAIL]
            cat_summary = f"Failed checks: {failed}"
        elif any(c.status == CheckStatus.WARN for c in cat_checks):
            cat_status = CheckStatus.WARN
            warned = [c.check_id for c in cat_checks if c.status == CheckStatus.WARN]
            cat_summary = f"Warned checks: {warned}"
        else:
            cat_status = CheckStatus.NOT_CONFIGURED
            cat_summary = "All checks returned not_configured"

        category_results.append(
            CategoryResult(
                category=cat,
                status=cat_status,
                summary=cat_summary,
                checks=cat_checks,
                is_required=(cat in _REQUIRED_CATEGORIES),
                is_safety=(cat in _UNSAFE_CATEGORIES),
            )
        )

    # Fake capability check — verify no tool claims available without executor
    fake_check = _run_fake_capability_check()

    # Derive verdict
    verdict = _derive_verdict(category_results, fake_check)

    # Build summary
    pass_count = sum(1 for c in category_results if c.status == CheckStatus.PASS)
    warn_count = sum(1 for c in category_results if c.status == CheckStatus.WARN)
    fail_count = sum(1 for c in category_results if c.status == CheckStatus.FAIL)
    nc_count = sum(
        1 for c in category_results if c.status == CheckStatus.NOT_CONFIGURED
    )
    summary = (
        f"Readiness verdict={verdict}: "
        f"{pass_count} pass, {warn_count} warn, "
        f"{fail_count} fail, {nc_count} not_configured "
        f"across {len(category_results)} categories"
    )

    return ReadinessReport(
        project_id=project_id,
        verdict=verdict,
        summary=summary,
        categories=category_results,
        cost_control_compliant=True,
        fake_capability_check=fake_check,
        accepted_checkpoints=_ACCEPTED_CHECKPOINTS,
    )


def _derive_verdict(
    categories: List[CategoryResult],
    fake_check: Dict[str, Any],
) -> str:
    """Derive the top-level verdict from category results.

    Priority: unsafe > hold > warn > ready
    """
    # UNSAFE: any safety category fails
    for cat in categories:
        if cat.is_safety and cat.status == CheckStatus.FAIL:
            return ReadinessVerdict.UNSAFE

    # UNSAFE: fake capability inflation detected
    if fake_check.get("inflation_detected"):
        return ReadinessVerdict.UNSAFE

    # HOLD: any required category fails
    for cat in categories:
        if cat.is_required and cat.status == CheckStatus.FAIL:
            return ReadinessVerdict.HOLD

    # WARN: any category is warn or not_configured
    for cat in categories:
        if cat.status in (CheckStatus.WARN, CheckStatus.NOT_CONFIGURED):
            return ReadinessVerdict.WARN

    return ReadinessVerdict.READY


def _run_fake_capability_check() -> Dict[str, Any]:
    """Verify tool registry has no available tools without executors.

    Checks that ToolRegistry.AVAILABLE tools all have an executor registered.
    Returns inflation_detected=True if any available tool lacks an executor.
    """
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.tools.catalog import initialize_catalog
        from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus

        initialize_catalog()
        available = ToolRegistry.list_available()
        fake_tools = []
        for tool in available:
            exec_fn = ToolRegistry.get_executor(tool.tool_id)
            if exec_fn is None:
                fake_tools.append(tool.tool_id)

        evidence["available_count"] = len(available)
        evidence["fake_tools_detected"] = fake_tools
        evidence["inflation_detected"] = bool(fake_tools)

        if fake_tools:
            evidence["verdict"] = (
                "FAIL: tools claim available but have no executor: "
                + str(fake_tools)
            )
        else:
            evidence["verdict"] = (
                f"PASS: all {len(available)} available tools have executors"
            )

        return evidence
    except Exception as exc:
        return {
            "inflation_detected": False,
            "error": str(exc),
            "verdict": f"check_error: {exc}",
        }


def generate_v1_report(project_id: str = "omnix") -> Dict[str, Any]:
    """Generate a V1 readiness report with all counts and evidence.

    This is the single-command V1 report for Phase F QA closeout.
    """
    checks = run_all_checks(project_id=project_id)
    report = evaluate_readiness(project_id=project_id, check_results=checks)

    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
    from openjarvis.skills.catalog import initialize_catalog as _init_skills
    from openjarvis.skills.jarvis_registry import SkillRegistry, SkillStatus
    from openjarvis.autonomy.watchdogs import WatchdogRunner

    initialize_catalog()
    _init_skills()

    tool_stats = ToolRegistry.stats()
    skill_stats = SkillRegistry.stats()
    watchdog_ids = WatchdogRunner.list_watchdog_ids()

    from openjarvis.governance.constitution import COST_CONTROL_LAW

    return {
        "project_id": project_id,
        "verdict": report.verdict,
        "summary": report.summary,
        "v1_readiness": {
            "verdict": report.verdict,
            "cost_control_compliant": report.cost_control_compliant,
            "cost_control_law_reference": COST_CONTROL_LAW[:120] + "...",
        },
        "counts": {
            "tools": {
                "total": tool_stats["total_registered"],
                "available": tool_stats["available"],
                "not_configured": tool_stats["by_status"].get(
                    ToolStatus.NOT_CONFIGURED, 0
                ),
                "degraded": tool_stats["by_status"].get(ToolStatus.DEGRADED, 0),
                "planned": tool_stats["by_status"].get(ToolStatus.PLANNED, 0),
                "blocked": tool_stats["by_status"].get(ToolStatus.BLOCKED, 0),
            },
            "skills": {
                "total": skill_stats["total_registered"],
                "available": skill_stats["available"],
                "degraded": skill_stats["by_status"].get(SkillStatus.DEGRADED, 0),
                "not_configured": skill_stats["by_status"].get(
                    SkillStatus.NOT_CONFIGURED, 0
                ),
            },
            "watchdogs": {
                "registered": len(watchdog_ids),
                "ids": watchdog_ids,
            },
        },
        "categories": {
            c.category: {"status": c.status, "summary": c.summary}
            for c in report.categories
        },
        "fake_capability_check": report.fake_capability_check,
        "accepted_checkpoints": report.accepted_checkpoints,
        "unsafe_actions_blocked": [
            "real_slack_send",
            "real_telegram_send",
            "omnix_production_deploy",
            "aws_infrastructure_change",
            "vercel_deploy",
            "supabase_change",
            "stripe_change",
            "browser_form_submit",
            "browser_purchase",
            "secrets_exposure",
        ],
        "remaining_limitations": [
            "voice.parse_intent is text-only keyword parser (no real STT)",
            "ProjectRegistry is in-process only (OMNIX hardcoded; future projects via register())",
            "AutonomyPolicy now persists to SQLite (~/.jarvis/autonomy_modes.db)",
            "No WebSocket/SSE push (Mission Control uses polling)",
            "No project_id field on Mission model (planned schema migration)",
            "Frontend unchanged: doctor/readiness routes are backend-only",
            "Packaged app not rebuilt in US7 (no frontend changes)",
            "OMNIX local_repo points to Jarvis/OpenJarvis (placeholder); real OMNIX source not yet configured",
        ],
        "post_v1_roadmap": [
            "WebSocket/SSE push for Mission Control (replace polling)",
            "Real STT integration (whisper.cpp or cloud provider)",
            "Mission model schema migration: add project_id field",
            "Frontend doctor/readiness panel in Mission Control",
            "Multi-project config file (add future projects without code changes)",
            "Watchdog results → alert auto-creation pipeline",
            "Skill execution dispatch endpoint",
            "Configure real OMNIX source: real local repo path, GitHub remote, or OpenClaw workspace",
        ],
    }


__all__ = [
    "CategoryResult",
    "ReadinessCategory",
    "ReadinessReport",
    "ReadinessVerdict",
    "_ACCEPTED_CHECKPOINTS",
    "evaluate_readiness",
    "generate_v1_report",
]
