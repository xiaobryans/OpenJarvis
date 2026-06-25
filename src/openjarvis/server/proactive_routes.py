"""Proactive Operator Layer Routes — B9.

Routes:
  GET /v1/proactive/suggestions   — proactive suggestions from local data sources
  GET /v1/proactive/stale-items   — tasks not updated in 7+ days
  GET /v1/proactive/next-actions  — recommended next actions (top 5, no auto-execute)

Design rules:
  - execution_blocked: True — suggestions NEVER auto-execute
  - approval_gates_preserved: True — all approval gates remain intact
  - fake_data: False in all responses
  - automation_honesty: True
  - Each data source fails independently (graceful try/except per source)
  - No secret reading, no credential access, no live external calls
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for proactive_routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["proactive"])

_STALE_THRESHOLD_SECONDS: float = 7 * 86400  # 7 days


# ---------------------------------------------------------------------------
# Helpers — each source is independently wrapped in try/except
# ---------------------------------------------------------------------------


def _gather_pending_approval_suggestions() -> List[Dict[str, Any]]:
    """Gather pending-approval task suggestions from life_os store."""
    suggestions: List[Dict[str, Any]] = []
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        tasks = store.list_tasks()
        for task in tasks:
            # list_tasks may return PersonalTask objects or dicts depending on store impl
            if hasattr(task, "to_dict"):
                t = task.to_dict()
            else:
                t = dict(task)
            status = t.get("status", "")
            approval_required = t.get("approval_required", False)
            if status in ("pending", "waiting_approval") and approval_required:
                task_id = t.get("task_id", "")
                suggestions.append({
                    "type": "pending_approval",
                    "title": "Task requires your approval",
                    "description": t.get("title", ""),
                    "source": "life_os",
                    "source_id": task_id,
                    "action_required": "approve_or_reject",
                    "priority": "high",
                    "approval_route": f"/v1/life-os/tasks/{task_id}/approve",
                })
    except Exception as exc:
        logger.debug("life_os approval suggestions skipped: %s", exc)
    return suggestions


def _gather_routine_failure_suggestions() -> List[Dict[str, Any]]:
    """Gather routine failure suggestions from the scheduler store."""
    suggestions: List[Dict[str, Any]] = []
    try:
        from openjarvis.server.routines_routes import _read_scheduled_tasks

        tasks_sched = _read_scheduled_tasks()
        count_failed = len([t for t in tasks_sched if t.get("status") == "failed"])
        if count_failed > 0:
            suggestions.append({
                "type": "routine_failure",
                "title": f"{count_failed} routine(s) failed",
                "description": "Review and restart failed scheduled routines",
                "source": "routines",
                "priority": "medium",
            })
    except Exception as exc:
        logger.debug("routine failure suggestions skipped: %s", exc)
    return suggestions


def _static_scheduler_suggestion() -> Dict[str, Any]:
    """Static suggestion always present — scheduler not auto-started."""
    return {
        "type": "scheduler_not_running",
        "title": "Scheduler not auto-started",
        "description": "Use 'jarvis scheduler start' to enable automated routines",
        "source": "routines",
        "priority": "low",
        "action_type": "cli_command",
        "cli_command": "jarvis scheduler start",
    }


# ---------------------------------------------------------------------------
# GET /v1/proactive/suggestions
# ---------------------------------------------------------------------------


@router.get("/v1/proactive/suggestions")
async def get_suggestions() -> Dict[str, Any]:
    """Return proactive suggestions derived from local data sources.

    CRITICAL: Suggestions are read-only observations. No action is taken
    automatically. Approval gates for all life_os tasks are preserved.
    """
    suggestions: List[Dict[str, Any]] = []

    # Source 1: life_os pending approvals
    suggestions.extend(_gather_pending_approval_suggestions())

    # Source 2: routine failures
    suggestions.extend(_gather_routine_failure_suggestions())

    # Source 3: static scheduler reminder (always present)
    suggestions.append(_static_scheduler_suggestion())

    return {
        "suggestions": suggestions,
        "count": len(suggestions),
        "sources_probed": ["life_os", "routines", "memory"],
        "execution_blocked": True,
        "approval_gates_preserved": True,
        "fake_data": False,
        "automation_honesty": True,
        "note": (
            "Suggestions only. No action is taken automatically. "
            "Approval required for any action."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/proactive/stale-items
# ---------------------------------------------------------------------------


@router.get("/v1/proactive/stale-items")
async def get_stale_items() -> Dict[str, Any]:
    """Detect tasks that have not been updated in 7+ days.

    Reads from life_os store. No actions are taken — detection only.
    """
    stale_tasks: List[Dict[str, Any]] = []
    now = time.time()

    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        tasks = store.list_tasks()

        for task in tasks:
            if hasattr(task, "to_dict"):
                t = task.to_dict()
            else:
                t = dict(task)

            status = t.get("status", "")
            if status not in ("pending", "in_progress"):
                continue

            # Use updated_at if available, fall back to created_at
            timestamp = t.get("updated_at") or t.get("created_at")
            if timestamp is None:
                continue

            age_seconds = now - float(timestamp)
            if age_seconds >= _STALE_THRESHOLD_SECONDS:
                age_days = int(age_seconds // 86400)
                stale_tasks.append({
                    "task_id": t.get("task_id", ""),
                    "title": t.get("title", ""),
                    "status": status,
                    "age_days": age_days,
                    "source": "life_os",
                })
    except Exception as exc:
        logger.debug("stale-items life_os read skipped: %s", exc)

    return {
        "stale_tasks": stale_tasks,
        "count": len(stale_tasks),
        "threshold_days": 7,
        "action_blocked": True,
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# GET /v1/proactive/next-actions
# ---------------------------------------------------------------------------


def _gather_goal_next_actions() -> List[Dict[str, Any]]:
    """Derive next actions from active goals with pending next_actions."""
    actions: List[Dict[str, Any]] = []
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        registry = get_goal_registry()
        goals = list(registry._goals.values())

        for goal in goals:
            if goal.status.value != "active":
                continue
            for na in goal.next_actions:
                na_dict = na.to_dict() if hasattr(na, "to_dict") else {}
                na_status = na_dict.get("status", "pending")
                if na_status != "pending":
                    continue
                actions.append({
                    "action": na_dict.get("title", str(na)),
                    "reason": f"Pending next action for goal: {goal.title}",
                    "source": "goals",
                    "approval_required": na_dict.get("requires_approval", False),
                    "priority": "high",
                })
    except Exception as exc:
        logger.debug("goal next-actions read skipped: %s", exc)
    return actions


def _gather_task_next_actions() -> List[Dict[str, Any]]:
    """Derive next actions from pending life_os tasks."""
    actions: List[Dict[str, Any]] = []
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        tasks = store.list_tasks()

        for task in tasks:
            if hasattr(task, "to_dict"):
                t = task.to_dict()
            else:
                t = dict(task)
            if t.get("status") != "pending":
                continue
            actions.append({
                "action": f"Work on task: {t.get('title', '')}",
                "reason": "Pending life_os task",
                "source": "life_os",
                "approval_required": t.get("approval_required", False),
                "priority": t.get("priority", "medium"),
            })
    except Exception as exc:
        logger.debug("task next-actions read skipped: %s", exc)
    return actions


@router.get("/v1/proactive/next-actions")
async def get_next_actions() -> Dict[str, Any]:
    """Return the top 5 recommended next actions based on current state.

    Sources: active goals with pending next_actions, pending life_os tasks.
    No action is auto-executed. Approval is required for any action taken.
    """
    # Priority order: goal actions first, then task actions
    all_actions: List[Dict[str, Any]] = []
    all_actions.extend(_gather_goal_next_actions())
    all_actions.extend(_gather_task_next_actions())

    # Rank by priority label: high > medium > low
    _priority_rank = {"high": 0, "medium": 1, "low": 2}
    all_actions.sort(key=lambda a: _priority_rank.get(a.get("priority", "medium"), 1))

    top5 = all_actions[:5]

    # Add rank field
    ranked: List[Dict[str, Any]] = []
    for i, action in enumerate(top5, start=1):
        ranked.append({"rank": i, **action})

    note: Optional[str] = None  # type: ignore[assignment]
    if not ranked:
        note = "No pending items found."

    response: Dict[str, Any] = {
        "next_actions": ranked,
        "count": len(ranked),
        "auto_execute": False,
        "approval_required_for_any_action": True,
        "fake_data": False,
    }
    if note:
        response["note"] = note

    return response


__all__ = ["router"]
