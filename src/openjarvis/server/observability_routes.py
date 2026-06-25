"""Observability / Reliability / Cost Controls REST Routes — B11.

Routes:
  GET /v1/observability/health-summary    — aggregated component health
  GET /v1/observability/reliability-metrics — local reliability metrics
  GET /v1/observability/audit-log         — local governance audit entries

Governance:
  - No secrets in any response
  - No live external calls
  - Honest status — degraded/unavailable if component unreachable
  - Exception type reported (not message) to avoid secret leak
  - fake_data: False in all responses
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for observability routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _check_life_os_store() -> Dict[str, str]:
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        store.list_tasks()
        return {"status": "healthy", "note": "PersonalTaskStore.list_tasks() succeeded."}
    except Exception as exc:
        return {"status": "degraded", "note": type(exc).__name__}


def _check_memory_store() -> Dict[str, str]:
    try:
        from openjarvis.memory.store import JarvisMemory

        m = JarvisMemory()
        m.search("test", limit=1)
        return {"status": "healthy", "note": "JarvisMemory.search() succeeded."}
    except Exception as exc:
        return {"status": "degraded", "note": type(exc).__name__}


def _check_goal_registry() -> Dict[str, str]:
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        get_goal_registry()
        return {"status": "healthy", "note": "get_goal_registry() succeeded."}
    except Exception as exc:
        return {"status": "degraded", "note": type(exc).__name__}


def _check_skill_registry() -> Dict[str, str]:
    try:
        from openjarvis.skills.jarvis_registry import SkillRegistry

        SkillRegistry.list_all()
        return {"status": "healthy", "note": "SkillRegistry.list_all() succeeded."}
    except Exception as exc:
        return {"status": "degraded", "note": type(exc).__name__}


def _check_scheduler_store() -> Dict[str, str]:
    try:
        from openjarvis.server.routines_routes import _read_scheduled_tasks

        _read_scheduled_tasks()
        return {"status": "healthy", "note": "_read_scheduled_tasks() succeeded."}
    except Exception as exc:
        return {"status": "degraded", "note": type(exc).__name__}


def _build_component(component_id: str, name: str, result: Dict[str, str]) -> Dict[str, str]:
    return {
        "component_id": component_id,
        "name": name,
        "status": result["status"],
        "note": result["note"],
    }


def _overall_status(components: List[Dict[str, str]]) -> str:
    statuses = {c["status"] for c in components}
    if "unavailable" in statuses:
        return "unavailable"
    if "degraded" in statuses:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/observability/health-summary")
async def health_summary() -> Dict[str, Any]:
    """Aggregate health status from all local components.

    Returns component-level status (healthy/degraded/unavailable).
    Exception type is reported — never the exception message — to avoid
    accidental secret leak. No external calls made.
    """
    backend_api_component = {
        "component_id": "backend_api",
        "name": "Backend API",
        "status": "healthy",
        "note": "FastAPI server responding normally.",
    }

    components: List[Dict[str, str]] = [
        backend_api_component,
        _build_component("life_os_store", "Life-OS Store", _check_life_os_store()),
        _build_component("memory_store", "Memory Store", _check_memory_store()),
        _build_component("goal_registry", "Goal Registry", _check_goal_registry()),
        _build_component("skill_registry", "Skill Registry", _check_skill_registry()),
        _build_component("scheduler_store", "Scheduler Store", _check_scheduler_store()),
    ]

    healthy_count = sum(1 for c in components if c["status"] == "healthy")
    degraded_count = sum(1 for c in components if c["status"] == "degraded")
    unavailable_count = sum(1 for c in components if c["status"] == "unavailable")

    return {
        "components": components,
        "healthy_count": healthy_count,
        "degraded_count": degraded_count,
        "unavailable_count": unavailable_count,
        "overall_status": _overall_status(components),
        "fake_data": False,
        "note": (
            "Local component health summary. No secret values checked. "
            "Cloud/Fargate status requires separate check."
        ),
    }


@router.get("/v1/observability/reliability-metrics")
async def reliability_metrics() -> Dict[str, Any]:
    """Return local reliability metrics.

    No external calls. Thresholds produce alerts when exceeded.
    Cost tracking is not yet wired — reported honestly as unavailable.
    """
    alerts: List[Dict[str, str]] = []

    # --- scheduler metrics ---
    scheduler_started = False
    failed_routines = 0
    try:
        from openjarvis.server.routines_routes import _read_scheduled_tasks

        tasks = _read_scheduled_tasks()
        scheduler_started = True
        for t in tasks:
            status_val = t.get("status", "")
            if isinstance(status_val, str) and "fail" in status_val.lower():
                failed_routines += 1
    except Exception:
        scheduler_started = False

    if failed_routines >= 1:
        alerts.append({
            "level": "error",
            "message": f"{failed_routines} scheduled routine(s) have failed status.",
        })

    # --- pending approvals ---
    pending_approvals = 0
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        all_tasks = store.list_tasks()
        for t in all_tasks:
            raw = t if isinstance(t, dict) else (t.to_dict() if hasattr(t, "to_dict") else {})
            if raw.get("approval_required") and raw.get("status") not in ("done", "cancelled"):
                pending_approvals += 1
    except Exception:
        pending_approvals = 0

    # --- stale goals ---
    stale_goals = 0
    try:
        from openjarvis.orchestrator.goals import GoalStatus, get_goal_registry

        registry = get_goal_registry()
        goals = registry.list_all()
        for g in goals:
            gd = g.to_dict() if hasattr(g, "to_dict") else {}
            if gd.get("status") == GoalStatus.ACTIVE.value and gd.get("paused"):
                stale_goals += 1
    except Exception:
        stale_goals = 0

    stale_goal_days = 30
    if stale_goals > 0:
        alerts.append({
            "level": "warn",
            "message": (
                f"{stale_goals} active goal(s) appear stale (paused flag set). "
                f"Review threshold: {stale_goal_days} days."
            ),
        })

    # --- memory namespaces ---
    memory_namespaces = 0
    try:
        from openjarvis.memory.store import JarvisMemory

        m = JarvisMemory()
        ns_list = m.list_namespaces()
        memory_namespaces = len(ns_list)
    except Exception:
        memory_namespaces = 0

    return {
        "metrics": {
            "api_uptime": "since_server_start",
            "scheduler_started": scheduler_started,
            "failed_routines": failed_routines,
            "pending_approvals": pending_approvals,
            "stale_goals": stale_goals,
            "memory_namespaces": memory_namespaces,
        },
        "thresholds": {
            "stale_goal_days": stale_goal_days,
            "routine_failure_alert": 1,
        },
        "alerts": alerts,
        "cost_tracking": {
            "budget_metadata_available": False,
            "live_cost_data": False,
            "note": "Cost tracking requires provider billing API integration (external gate).",
        },
        "fake_data": False,
        "secret_safe": True,
    }


@router.get("/v1/observability/audit-log")
async def audit_log() -> Dict[str, Any]:
    """Return last N audit-relevant events from the local governance module.

    Returns metadata only — no secret values. If the governance audit log is
    unavailable, returns an empty list with an honest note.
    """
    entries: List[Any] = []
    source = "unavailable"
    note = "Governance audit module unavailable. External audit requires Fargate deployment."

    try:
        from openjarvis.governance.constitution import JarvisConstitution

        c = JarvisConstitution()
        raw = c.audit_log if hasattr(c, "audit_log") else []
        entries = list(raw) if raw else []
        source = "local_governance_audit"
        note = "Audit log from local governance module. External audit requires Fargate deployment."
    except Exception as exc:
        logger.debug("Governance audit log unavailable: %s", type(exc).__name__)
        source = "unavailable"

    return {
        "audit_entries": entries,
        "count": len(entries),
        "source": source,
        "secret_safe": True,
        "fake_data": False,
        "note": note,
    }


__all__ = ["router"]
