"""Jarvis Autonomy Catalog — Ultra Sprint 6 autonomy/watchdog/alert/mobile tools.

Tools (14 total, all available):
  autonomy category (2):
    autonomy.get_status       — get project autonomy mode + policy status
    autonomy.set_mode         — set autonomy mode (governance-enforced)

  watchdog category (3):
    watchdog.run_project_pack — run all 8 watchdogs for a project
    watchdog.run_once         — run a single watchdog by id
    watchdog.list_ids         — list all registered watchdog ids

  alert category (7):
    alert.create              — create an alert record
    alert.list                — list alerts for a project
    alert.acknowledge         — acknowledge an alert
    alert.resolve             — resolve an alert
    alert.draft_slack_update  — draft Slack message (never sends)
    alert.draft_telegram_update — draft Telegram message (never sends)
    alert.daily_digest        — generate plain-text daily digest

  mobile category (1):
    mobile.status             — mobile-readable compact status endpoint

  voice category (1):
    voice.parse_intent        — text-based intent parser (keyword matching only;
                                 real STT is planned but not implemented)

Governance:
  - All alert draft tools: send_status=not_sent, approval_required=True
  - autonomy.set_mode: validates mode string; governance hard gates always enforced
  - watchdog tools: observe only, no system modifications
  - voice.parse_intent: honest text-only parser; no fake AI voice
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _exec_autonomy_get_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.modes import AutonomyPolicy
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    return AutonomyPolicy.get_status(project_id)


def _exec_autonomy_set_mode(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.modes import AutonomyMode, AutonomyPolicy
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    mode_str = inputs.get("mode", "observe_only")
    set_by = inputs.get("set_by", ctx.get("agent_id", "api"))
    reason = inputs.get("reason", "")
    try:
        mode = AutonomyMode(mode_str)
    except ValueError:
        valid = [m.value for m in AutonomyMode]
        raise ValueError(f"Invalid mode '{mode_str}'. Valid modes: {valid}")
    entry = AutonomyPolicy.set_mode(
        project_id, mode, set_by=set_by, reason=reason
    )
    return {
        "ok": True,
        "project_id": project_id,
        "mode": entry.mode.value,
        "set_by": entry.set_by,
        "set_at": entry.set_at,
        "reason": entry.reason,
        "hard_gates_always_blocked": True,
        "real_send_always_blocked": True,
    }


def _exec_watchdog_run_project_pack(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.watchdogs import WatchdogRunner
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    results = WatchdogRunner.run_project_pack(project_id)
    summary = WatchdogRunner.summarize(results)
    return {
        "project_id": project_id,
        "watchdogs_run": len(results),
        "summary": summary,
        "results": [r.to_dict() for r in results],
        "ran_at": time.time(),
    }


def _exec_watchdog_run_once(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.watchdogs import WatchdogRunner
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    watchdog_id = inputs.get("watchdog_id", "")
    if not watchdog_id:
        raise ValueError("watchdog_id is required")
    result = WatchdogRunner.run_once(watchdog_id, project_id)
    return result.to_dict()


def _exec_watchdog_list_ids(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.watchdogs import WatchdogRunner
    ids = WatchdogRunner.list_watchdog_ids()
    return {"watchdog_ids": ids, "count": len(ids)}


def _exec_alert_create(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import AlertSeverity, get_alert_store
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    title = inputs.get("title", "")
    evidence = inputs.get("evidence", "")
    if not title:
        raise ValueError("title is required")
    if not evidence:
        raise ValueError("evidence is required")
    severity = inputs.get("severity", AlertSeverity.INFO)
    recommendation = inputs.get("recommendation", "")
    source_watchdog_id = inputs.get("source_watchdog_id", "")
    store = get_alert_store()
    record = store.create(
        project_id=project_id,
        title=title,
        evidence=evidence,
        severity=severity,
        recommendation=recommendation,
        source_watchdog_id=source_watchdog_id,
    )
    return {"ok": True, "alert": record.to_dict()}


def _exec_alert_list(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import get_alert_store
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    status = inputs.get("status")
    limit = int(inputs.get("limit", 50))
    store = get_alert_store()
    alerts = store.list(project_id=project_id, status=status, limit=limit)
    return {
        "project_id": project_id,
        "alerts": [a.to_dict() for a in alerts],
        "count": len(alerts),
    }


def _exec_alert_acknowledge(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import get_alert_store
    alert_id = inputs.get("alert_id", "")
    if not alert_id:
        raise ValueError("alert_id is required")
    store = get_alert_store()
    record = store.acknowledge(alert_id)
    if record is None:
        return {"ok": False, "error": f"Alert '{alert_id}' not found"}
    return {"ok": True, "alert": record.to_dict()}


def _exec_alert_resolve(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import get_alert_store
    alert_id = inputs.get("alert_id", "")
    if not alert_id:
        raise ValueError("alert_id is required")
    store = get_alert_store()
    record = store.resolve(alert_id)
    if record is None:
        return {"ok": False, "error": f"Alert '{alert_id}' not found"}
    return {"ok": True, "alert": record.to_dict()}


def _exec_alert_draft_slack(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import get_alert_store
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    alert_ids: Optional[List[str]] = inputs.get("alert_ids")
    store = get_alert_store()
    return store.draft_slack_update(project_id, alert_ids=alert_ids)


def _exec_alert_draft_telegram(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import get_alert_store
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    alert_ids: Optional[List[str]] = inputs.get("alert_ids")
    store = get_alert_store()
    return store.draft_telegram_update(project_id, alert_ids=alert_ids)


def _exec_alert_daily_digest(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.autonomy.alerts import get_alert_store
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"
    store = get_alert_store()
    return store.daily_digest(project_id)


def _exec_mobile_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact mobile-readable status payload for a project."""
    project_id = inputs.get("project_id") or ctx.get("project_id") or "omnix"

    from openjarvis.autonomy.modes import AutonomyPolicy
    from openjarvis.autonomy.alerts import get_alert_store, AlertStatus
    from openjarvis.autonomy.watchdogs import WatchdogRunner

    autonomy = AutonomyPolicy.get_status(project_id)

    # Tool counts
    tool_counts: Dict[str, int] = {}
    try:
        from openjarvis.tools.catalog import initialize_catalog
        from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
        initialize_catalog()
        stats = ToolRegistry.stats()
        tool_counts = {
            "total": stats["total_registered"],
            "available": stats["available"],
            "not_configured": stats["by_status"].get(ToolStatus.NOT_CONFIGURED, 0),
            "degraded": stats["by_status"].get(ToolStatus.DEGRADED, 0),
        }
    except Exception:
        tool_counts = {"error": "tool registry unavailable"}

    # Skill counts
    skill_counts: Dict[str, int] = {}
    try:
        from openjarvis.skills.catalog import initialize_catalog as _init_skills
        from openjarvis.skills.jarvis_registry import SkillRegistry, SkillStatus
        _init_skills()
        all_skills = SkillRegistry.list_all()
        skill_counts = {
            "total": len(all_skills),
            "available": sum(1 for s in all_skills if s.status == SkillStatus.AVAILABLE),
            "degraded": sum(1 for s in all_skills if s.status == SkillStatus.DEGRADED),
        }
    except Exception:
        skill_counts = {"error": "skill registry unavailable"}

    # Alert summary
    store = get_alert_store()
    open_alerts = store.list(project_id=project_id, status=AlertStatus.OPEN, limit=50)
    severities: Dict[str, int] = {}
    for a in open_alerts:
        severities[a.severity] = severities.get(a.severity, 0) + 1
    highest = "none"
    for sev in ["critical", "error", "warning", "info"]:
        if severities.get(sev, 0) > 0:
            highest = sev
            break

    # Last watchdog run — just list ids (not re-running here)
    watchdog_ids = WatchdogRunner.list_watchdog_ids()

    return {
        "project_id": project_id,
        "autonomy_mode": autonomy["mode"],
        "can_observe": autonomy["can_observe"],
        "can_propose": autonomy["can_propose"],
        "tools": tool_counts,
        "skills": skill_counts,
        "alerts": {
            "open": len(open_alerts),
            "highest_severity": highest,
            "severity_breakdown": severities,
        },
        "watchdogs": {
            "registered": len(watchdog_ids),
            "ids": watchdog_ids,
        },
        "mobile_payload_version": "1.0",
        "generated_at": time.time(),
    }


def _exec_voice_parse_intent(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Text-based keyword intent parser — honest foundation only.

    This is NOT AI-powered voice recognition. It parses text using keyword
    matching. Real speech-to-text (STT) integration is planned but not yet
    implemented. Blocker: no STT engine wired.
    """
    text = inputs.get("text", "").strip()
    if not text:
        raise ValueError("text is required")
    text_lower = text.lower()
    _INTENTS: Dict[str, List[str]] = {
        "mission_status": ["mission status", "how are missions", "missions", "what's running"],
        "run_watchdogs": ["run watchdogs", "check watchdogs", "watchdog", "health check"],
        "show_alerts": ["show alerts", "alerts", "any alerts", "what problems"],
        "autonomy_status": ["autonomy", "auto mode", "autonomy status"],
        "tool_status": ["tool status", "available tools", "what tools"],
        "daily_digest": ["daily digest", "digest", "summary", "what happened today"],
        "help": ["help", "what can you do", "commands", "what are you"],
    }
    matched_intent = "unknown"
    confidence = 0.0
    for intent, keywords in _INTENTS.items():
        for kw in keywords:
            if kw in text_lower:
                matched_intent = intent
                confidence = 0.8
                break
        if matched_intent != "unknown":
            break
    return {
        "intent": matched_intent,
        "confidence": confidence,
        "raw_text": text,
        "input_type": "text",
        "voice_status": "not_implemented",
        "blocker": (
            "Real voice recognition requires speech-to-text (STT) integration. "
            "This executor processes text input only using keyword matching."
        ),
        "planned_upgrade": "STT integration (e.g. whisper.cpp or cloud STT API)",
    }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_AUTONOMY_TOOL_DEFS: List[tuple] = [
    (
        ToolSpec(
            tool_id="autonomy.get_status",
            display_name="Get Autonomy Status",
            description="Return current autonomy mode and policy status for a project.",
            category="autonomy",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "mode": {"type": "string"},
                    "can_observe": {"type": "boolean"},
                    "can_propose": {"type": "boolean"},
                    "safe_execute_enabled": {"type": "boolean"},
                    "hard_gates_always_blocked": {"type": "boolean"},
                },
            },
            required_permissions=["read:autonomy"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_autonomy_get_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_autonomy_get_status,
    ),
    (
        ToolSpec(
            tool_id="autonomy.set_mode",
            display_name="Set Autonomy Mode",
            description=(
                "Set project autonomy mode. Hard gates remain enforced regardless of mode. "
                "Real sends/deploys/destructive actions are never auto-allowed."
            ),
            category="autonomy",
            input_schema={
                "type": "object",
                "required": ["mode"],
                "properties": {
                    "project_id": {"type": "string"},
                    "mode": {
                        "type": "string",
                        "enum": ["off", "observe_only", "propose_only",
                                 "safe_execute_approved", "blocked", "requires_approval"],
                    },
                    "set_by": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "mode": {"type": "string"},
                    "hard_gates_always_blocked": {"type": "boolean"},
                },
            },
            required_permissions=["write:autonomy"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_autonomy_set_mode",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_autonomy_set_mode,
    ),
    (
        ToolSpec(
            tool_id="watchdog.run_project_pack",
            display_name="Run Watchdog Pack",
            description="Run all 8 watchdogs for a project. Observe-only — no modifications.",
            category="watchdog",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {
                    "watchdogs_run": {"type": "integer"},
                    "summary": {"type": "object"},
                    "results": {"type": "array"},
                },
            },
            required_permissions=["read:watchdog"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_watchdog_run_project_pack",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_watchdog_run_project_pack,
    ),
    (
        ToolSpec(
            tool_id="watchdog.run_once",
            display_name="Run Single Watchdog",
            description="Run a single watchdog by ID. Observe-only — no modifications.",
            category="watchdog",
            input_schema={
                "type": "object",
                "required": ["watchdog_id"],
                "properties": {
                    "watchdog_id": {"type": "string"},
                    "project_id": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "status": {"type": "string"},
                    "evidence": {"type": "string"},
                },
            },
            required_permissions=["read:watchdog"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_watchdog_run_once",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_watchdog_run_once,
    ),
    (
        ToolSpec(
            tool_id="watchdog.list_ids",
            display_name="List Watchdog IDs",
            description="List all registered watchdog IDs.",
            category="watchdog",
            input_schema={"type": "object", "properties": {}},
            output_schema={
                "type": "object",
                "properties": {
                    "watchdog_ids": {"type": "array", "items": {"type": "string"}},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:watchdog"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_watchdog_list_ids",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_watchdog_list_ids,
    ),
    (
        ToolSpec(
            tool_id="alert.create",
            display_name="Create Alert",
            description="Create a project-scoped alert record with evidence and severity.",
            category="alert",
            input_schema={
                "type": "object",
                "required": ["title", "evidence"],
                "properties": {
                    "project_id": {"type": "string"},
                    "title": {"type": "string"},
                    "evidence": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["info", "warning", "error", "critical"],
                    },
                    "recommendation": {"type": "string"},
                    "source_watchdog_id": {"type": "string"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}, "alert": {"type": "object"}},
            },
            required_permissions=["write:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_create",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_create,
    ),
    (
        ToolSpec(
            tool_id="alert.list",
            display_name="List Alerts",
            description="List alerts for a project, optionally filtered by status.",
            category="alert",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["open", "acknowledged", "resolved"],
                    },
                    "limit": {"type": "integer"},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "alerts": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_list",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_list,
    ),
    (
        ToolSpec(
            tool_id="alert.acknowledge",
            display_name="Acknowledge Alert",
            description="Mark an alert as acknowledged. Does not resolve it.",
            category="alert",
            input_schema={
                "type": "object",
                "required": ["alert_id"],
                "properties": {"alert_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}, "alert": {"type": "object"}},
            },
            required_permissions=["write:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_acknowledge",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_acknowledge,
    ),
    (
        ToolSpec(
            tool_id="alert.resolve",
            display_name="Resolve Alert",
            description="Resolve an alert.",
            category="alert",
            input_schema={
                "type": "object",
                "required": ["alert_id"],
                "properties": {"alert_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}, "alert": {"type": "object"}},
            },
            required_permissions=["write:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_resolve",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_resolve,
    ),
    (
        ToolSpec(
            tool_id="alert.draft_slack_update",
            display_name="Draft Slack Alert Update",
            description=(
                "Draft a Slack message for open alerts. "
                "NEVER sends. send_status=not_sent always. Requires explicit approval to send."
            ),
            category="alert",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "alert_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "draft_text": {"type": "string"},
                    "send_status": {"type": "string"},
                    "approval_required": {"type": "boolean"},
                },
            },
            required_permissions=["read:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_draft_slack",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_draft_slack,
    ),
    (
        ToolSpec(
            tool_id="alert.draft_telegram_update",
            display_name="Draft Telegram Alert Update",
            description=(
                "Draft a Telegram message for open alerts. "
                "NEVER sends. send_status=not_sent always. Requires explicit approval to send."
            ),
            category="alert",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "alert_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
            output_schema={
                "type": "object",
                "properties": {
                    "draft_text": {"type": "string"},
                    "send_status": {"type": "string"},
                    "approval_required": {"type": "boolean"},
                },
            },
            required_permissions=["read:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_draft_telegram",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_draft_telegram,
    ),
    (
        ToolSpec(
            tool_id="alert.daily_digest",
            display_name="Alert Daily Digest",
            description="Generate a plain-text daily digest of alerts for a project.",
            category="alert",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {
                    "digest_text": {"type": "string"},
                    "open_count": {"type": "integer"},
                    "acknowledged_count": {"type": "integer"},
                },
            },
            required_permissions=["read:alerts"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_alert_daily_digest",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_alert_daily_digest,
    ),
    (
        ToolSpec(
            tool_id="mobile.status",
            display_name="Mobile Status",
            description=(
                "Mobile-readable compact status payload: autonomy mode, tool counts, "
                "skill counts, alert summary, watchdog registry."
            ),
            category="mobile",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "autonomy_mode": {"type": "string"},
                    "tools": {"type": "object"},
                    "alerts": {"type": "object"},
                    "watchdogs": {"type": "object"},
                },
            },
            required_permissions=["read:status"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mobile_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mobile_status,
    ),
    (
        ToolSpec(
            tool_id="voice.parse_intent",
            display_name="Voice Intent Parser",
            description=(
                "Text-based keyword intent parser. HONEST FOUNDATION ONLY. "
                "Processes text input via keyword matching. "
                "Real speech-to-text (STT) is planned but not implemented. "
                "Blocker: no STT engine integrated."
            ),
            category="voice",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "confidence": {"type": "number"},
                    "voice_status": {"type": "string"},
                    "blocker": {"type": "string"},
                },
            },
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_parse_intent",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_parse_intent,
    ),
]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _is_autonomy_initialized() -> bool:
    return ToolRegistry.get("autonomy.get_status") is not None


def initialize_autonomy_catalog() -> None:
    """Register all Sprint 6 autonomy/watchdog/alert/mobile/voice tools.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_autonomy_initialized():
        return
    for spec, executor in _AUTONOMY_TOOL_DEFS:
        ToolRegistry.register(spec, executor=executor)
    stats = ToolRegistry.stats()
    logger.info(
        "Autonomy catalog initialized: total=%d available=%d unavailable=%d",
        stats["total_registered"],
        stats["available"],
        stats["unavailable"],
    )


__all__ = ["initialize_autonomy_catalog"]
