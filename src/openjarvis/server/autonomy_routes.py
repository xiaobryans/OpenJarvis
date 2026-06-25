"""Autonomy, watchdog, alert, and mobile status REST routes.

Routes:
  GET  /v1/autonomy/status           — autonomy status for a project
  POST /v1/autonomy/mode             — set autonomy mode for a project
  GET  /v1/watchdogs                 — run watchdogs and return results for a project
  POST /v1/watchdogs/run             — explicitly run watchdog pack (or single watchdog)
  GET  /v1/alerts                    — list alerts for a project
  POST /v1/alerts/{alert_id}/ack     — acknowledge an alert
  POST /v1/alerts/{alert_id}/resolve — resolve an alert
  GET  /v1/mobile/status             — mobile-readable compact status

Governance:
  - No real Slack/Telegram sends from any endpoint here
  - Hard gates enforced by AutonomyPolicy regardless of mode
  - Watchdogs observe only — no modifications from run endpoints
  - Alert drafts are draft_text only; approval required to send
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for autonomy routes")


def _is_cloud_runtime() -> bool:
    """Return True when this server is running in a cloud/always-on environment."""
    return bool(os.environ.get("CLOUD_RUNTIME_DEPLOYMENT") or
                os.environ.get("ECS_CONTAINER_METADATA_URI") or
                os.environ.get("ECS_CONTAINER_METADATA_URI_V4"))


def _runtime_deployment() -> str:
    if os.environ.get("CLOUD_RUNTIME_DEPLOYMENT"):
        return os.environ["CLOUD_RUNTIME_DEPLOYMENT"]
    if os.environ.get("ECS_CONTAINER_METADATA_URI") or os.environ.get("ECS_CONTAINER_METADATA_URI_V4"):
        return "aws-ecs-fargate"
    return "localhost_only"


def _runtime_always_on_status(gist_configured: bool) -> str:
    if _is_cloud_runtime():
        region = os.environ.get("AWS_DEFAULT_REGION", os.environ.get("OMNIX_WORKBENCH_AWS_REGION", "unknown"))
        return (
            f"AVAILABLE — Jarvis FastAPI backend running in AWS ECS Fargate ({region}). "
            "MacBook does not need to be on. Real AI (OpenAI), real S3 memory sync, real auth enabled."
        )
    return (
        "BLOCKED — no cloud runtime detected. "
        "Jarvis API server must be running on the MacBook. "
        "Deploy to AWS ECS (Dockerfile.full) to enable true MacBook-off runtime."
    )


def _runtime_mode() -> str:
    """Return one of: cloud | local_lan.

    'cloud'     — server is running in a cloud/always-on environment (ECS Fargate).
    'local_lan' — server is running on the MacBook; MacBook must be on for AI access.

    'continuity_only' and 'unavailable' are client-side states that cannot be
    reported by a running server instance.
    """
    return "cloud" if _is_cloud_runtime() else "local_lan"


def _cloud_url() -> Optional[str]:
    """Return the configured cloud backend URL for mobile client discovery, or None."""
    return os.environ.get("JARVIS_CLOUD_URL") or None

from openjarvis.autonomy.alerts import AlertSeverity, get_alert_store
from openjarvis.autonomy.modes import AutonomyMode, AutonomyPolicy
from openjarvis.autonomy.watchdogs import WatchdogRunner

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SetModeRequest(BaseModel):
    project_id: str = "default"
    mode: str = Field(
        ...,
        description="One of: off, observe_only, propose_only, safe_execute_approved, blocked, requires_approval",
    )
    set_by: str = "api"
    reason: str = ""


class RunWatchdogRequest(BaseModel):
    project_id: str = "default"
    watchdog_id: Optional[str] = None


class CreateAlertRequest(BaseModel):
    project_id: str = "default"
    title: str
    evidence: str
    severity: str = AlertSeverity.INFO
    recommendation: str = ""
    source_watchdog_id: str = ""


# ---------------------------------------------------------------------------
# Autonomy routes
# ---------------------------------------------------------------------------


@router.get("/v1/autonomy/status")
async def get_autonomy_status(project_id: str = "default") -> Dict[str, Any]:
    """Return autonomy mode and policy status for a project.

    Always shows: mode, can_observe, can_propose, hard_gates_always_blocked.
    """
    return {
        "autonomy": AutonomyPolicy.get_status(project_id),
        "all_modes": [m.value for m in AutonomyMode],
        "default_mode": AutonomyMode.OBSERVE_ONLY.value,
    }


@router.post("/v1/autonomy/mode")
async def set_autonomy_mode(req: SetModeRequest) -> Dict[str, Any]:
    """Set the autonomy mode for a project.

    Hard gates are always enforced regardless of mode.
    Real sends/deploys/destructive actions are never auto-allowed.
    """
    try:
        mode = AutonomyMode(req.mode)
    except ValueError:
        valid = [m.value for m in AutonomyMode]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{req.mode}'. Valid modes: {valid}",
        )
    entry = AutonomyPolicy.set_mode(
        req.project_id, mode, set_by=req.set_by, reason=req.reason
    )
    return {
        "ok": True,
        "project_id": req.project_id,
        "mode": entry.mode.value,
        "set_by": entry.set_by,
        "reason": entry.reason,
        "hard_gates_always_blocked": True,
        "real_send_always_blocked": True,
        "note": (
            "Autonomy mode set. Hard-gated actions (real Slack/Telegram send, deploys, "
            "destructive ops) remain blocked regardless of mode."
        ),
    }


# ---------------------------------------------------------------------------
# Watchdog routes
# ---------------------------------------------------------------------------


@router.get("/v1/watchdogs")
async def list_watchdogs(project_id: str = "default") -> Dict[str, Any]:
    """Return available watchdog IDs and run the pack for a project.

    Watchdogs observe only. No system modifications.
    """
    results = WatchdogRunner.run_project_pack(project_id)
    summary = WatchdogRunner.summarize(results)
    return {
        "project_id": project_id,
        "watchdog_ids": WatchdogRunner.list_watchdog_ids(),
        "results": [r.to_dict() for r in results],
        "summary": summary,
    }


@router.post("/v1/watchdogs/run")
async def run_watchdogs(req: RunWatchdogRequest) -> Dict[str, Any]:
    """Run watchdog pack (or single watchdog if watchdog_id provided).

    Watchdogs observe only. No system modifications.
    """
    if req.watchdog_id:
        result = WatchdogRunner.run_once(req.watchdog_id, req.project_id)
        return {
            "project_id": req.project_id,
            "watchdog_id": req.watchdog_id,
            "result": result.to_dict(),
        }
    results = WatchdogRunner.run_project_pack(req.project_id)
    summary = WatchdogRunner.summarize(results)
    return {
        "project_id": req.project_id,
        "watchdogs_run": len(results),
        "summary": summary,
        "results": [r.to_dict() for r in results],
    }


# ---------------------------------------------------------------------------
# Alert routes
# ---------------------------------------------------------------------------


@router.get("/v1/alerts")
async def list_alerts(
    project_id: str = "default",
    status: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """List alerts for a project."""
    store = get_alert_store()
    alerts = store.list(project_id=project_id, status=status, limit=max(1, min(limit, 200)))
    return {
        "project_id": project_id,
        "alerts": [a.to_dict() for a in alerts],
        "count": len(alerts),
    }


@router.post("/v1/alerts")
async def create_alert(req: CreateAlertRequest) -> Dict[str, Any]:
    """Create a project-scoped alert record."""
    valid_severities = [AlertSeverity.INFO, AlertSeverity.WARNING, AlertSeverity.ERROR, AlertSeverity.CRITICAL]
    if req.severity not in valid_severities:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity '{req.severity}'. Valid: {valid_severities}",
        )
    store = get_alert_store()
    record = store.create(
        project_id=req.project_id,
        title=req.title,
        evidence=req.evidence,
        severity=req.severity,
        recommendation=req.recommendation,
        source_watchdog_id=req.source_watchdog_id,
    )
    return {"ok": True, "alert": record.to_dict()}


@router.post("/v1/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: str) -> Dict[str, Any]:
    """Acknowledge an alert (does not resolve it)."""
    store = get_alert_store()
    record = store.acknowledge(alert_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return {"ok": True, "alert": record.to_dict()}


@router.post("/v1/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str) -> Dict[str, Any]:
    """Resolve an alert."""
    store = get_alert_store()
    record = store.resolve(alert_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return {"ok": True, "alert": record.to_dict()}


# ---------------------------------------------------------------------------
# Mobile status route
# ---------------------------------------------------------------------------


@router.get("/v1/mobile/status")
async def mobile_status(project_id: str = "default") -> Dict[str, Any]:
    """Mobile-readable compact status payload.

    Returns: autonomy_mode, tool counts, skill counts, alert summary, watchdog registry.
    No real sends. No system modifications.
    """
    import time

    autonomy = AutonomyPolicy.get_status(project_id)

    tool_counts: Dict[str, Any] = {}
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
    except Exception as exc:
        tool_counts = {"error": str(exc)}

    skill_counts: Dict[str, Any] = {}
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
    except Exception as exc:
        skill_counts = {"error": str(exc)}

    store = get_alert_store()
    open_alerts = store.list(project_id=project_id, status="open", limit=50)
    severities: Dict[str, int] = {}
    for a in open_alerts:
        severities[a.severity] = severities.get(a.severity, 0) + 1
    highest = "none"
    for sev in ["critical", "error", "warning", "info"]:
        if severities.get(sev, 0) > 0:
            highest = sev
            break

    watchdog_ids = WatchdogRunner.list_watchdog_ids()

    # Continuity status
    continuity_status: Dict[str, Any] = {}
    try:
        from openjarvis.mobile.continuity_backend import (
            LocalFileBackend,
            GitHubGistBackend,
        )
        local_status = LocalFileBackend().get_status()
        gist_status = GitHubGistBackend().get_status()
        continuity_status = {
            "local_backend": local_status.backend_name,
            "local_macbook_off_capable": local_status.macbook_off_capable,
            "gist_backend": gist_status.backend_name,
            "gist_macbook_off_capable": gist_status.macbook_off_capable,
            "gist_available": gist_status.availability == "available",
        }
    except Exception as exc:
        continuity_status = {"error": str(exc)}

    return {
        "project_id": project_id,
        "autonomy_mode": autonomy["mode"],
        "can_observe": autonomy["can_observe"],
        "can_propose": autonomy["can_propose"],
        "hard_gates_always_blocked": True,
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
        "continuity": continuity_status,
        "mobile_payload_version": "1.0",
        "generated_at": time.time(),
    }


@router.get("/v1/mobile/continuity/status")
async def continuity_status() -> Dict[str, Any]:
    """Return continuity backend readiness.

    IMPORTANT: Two distinct capabilities are reported separately:

    1. state_sync_macbook_off_capable — saved state (memory, tasks, approvals) can
       be retrieved from GitHub Gist even when the MacBook is off.  REAL when
       GITHUB_TOKEN is configured with gist scope.

    2. runtime_macbook_off_capable — the Jarvis API server is reachable when the
       MacBook is off. BLOCKED for local dev: no cloud runtime is deployed.
       Requires deploying the FastAPI backend to a cloud host (Fly.io, Railway,
       EC2, etc.) to be real.

    GitHub Gist backend is available when GITHUB_TOKEN is set (gist scope required).
    Local-only when token is absent.
    """
    try:
        from openjarvis.mobile.continuity_backend import (
            LocalFileBackend,
            GitHubGistBackend,
        )
        local = LocalFileBackend().get_status()
        gist = GitHubGistBackend().get_status()
        gist_configured = bool(gist.env_vars_present)
        return {
            "backends": [
                {
                    "name": local.backend_name,
                    "availability": local.availability,
                    "macbook_off_capable": local.macbook_off_capable,
                    "notes": local.notes,
                },
                {
                    "name": gist.backend_name,
                    "availability": gist.availability,
                    "macbook_off_capable": gist.macbook_off_capable,
                    "setup_steps": gist.setup_steps,
                    "notes": gist.notes if hasattr(gist, "notes") else "",
                },
            ],
            "active_backend": (
                gist.backend_name if gist.macbook_off_capable and gist_configured
                else local.backend_name
            ),
            "cross_device_ready": gist.macbook_off_capable and gist_configured,
            # --- Honest capability split ---
            "state_sync_macbook_off_capable": gist_configured,
            "runtime_macbook_off_capable": _is_cloud_runtime(),
            "runtime_deployment": _runtime_deployment(),
            "runtime_always_on_status": _runtime_always_on_status(gist_configured),
            # --- Runtime mode (local_lan | cloud) ---
            # 'continuity_only' and 'unavailable' are client-side states only.
            "runtime_mode": _runtime_mode(),
            "cloud_url": _cloud_url(),
        }
    except Exception as exc:
        return {"error": str(exc), "backends": []}


__all__ = ["router"]
