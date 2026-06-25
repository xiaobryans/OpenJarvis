"""Follow-Up Center Routes — Phase B1 safe Jarvis OS expansion.

Aggregates follow-up items from all Jarvis OS sources into a single unified view:
  - Life-OS personal tasks (status=waiting_followup or active follow_up_state)
  - Long-horizon goals (follow_up_queue items)

Routes:
  GET  /v1/follow-up-center              — unified list of all follow-up items
  GET  /v1/follow-up-center/summary      — count summary by source/status
  POST /v1/follow-up-center/tasks/{task_id}/complete — mark a life-os task done
  POST /v1/follow-up-center/tasks/{task_id}/snooze   — snooze a task follow-up

Design rules:
  - Read-only aggregation from existing stores — no new storage required.
  - Write actions preserve existing approval gates (approval_required tasks
    are NOT auto-completed; they return the approval_route instead).
  - No secret values returned.
  - No fake data. Empty list when no items exist — never fabricated items.
  - No connector credential dependency.
  - No voice, no iOS initialization, no signing/notarization.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["follow-up-center"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SnoozeRequest(BaseModel):
    snooze_until: float = Field(..., description="Unix timestamp to snooze until")
    reason: str = Field("", description="Optional reason for snooze")


# ---------------------------------------------------------------------------
# Source probes — each returns a list of normalized FollowUpItem dicts
# ---------------------------------------------------------------------------

_VALID_STATUSES = {
    "due",
    "upcoming",
    "waiting_approval",
    "waiting_followup",
    "snoozed",
    "completed",
    "unknown",
}


def _classify_due(due_at: Optional[float]) -> str:
    """Classify timing: due/upcoming/unknown based on due timestamp."""
    if due_at is None:
        return "upcoming"
    now = time.time()
    if due_at <= now:
        return "due"
    return "upcoming"


def _probe_life_os_follow_ups() -> List[Dict[str, Any]]:
    """Return life-os tasks with waiting_followup status or active follow_up_state."""
    items: List[Dict[str, Any]] = []
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()

        # Group 1: tasks explicitly marked as waiting_followup
        waiting = store.pending_follow_ups()
        for task in waiting:
            d = task.to_dict() if hasattr(task, "to_dict") else {}
            fu = d.get("follow_up_state") or {}
            due_at = fu.get("due_at") if isinstance(fu, dict) else None
            items.append(
                {
                    "item_id": f"task:{task.task_id}",
                    "source": "life_os_task",
                    "source_id": task.task_id,
                    "title": task.title,
                    "description": fu.get("description", task.description) if isinstance(fu, dict) else task.description,
                    "status": "waiting_approval" if task.approval_required else _classify_due(due_at),
                    "due_at": due_at,
                    "priority": task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                    "tags": task.tags,
                    "approval_required": task.approval_required,
                    "approval_route": f"/v1/life-os/tasks/{task.task_id}/approve" if task.approval_required else None,
                    "source_route": f"/v1/life-os/tasks/{task.task_id}",
                    "follow_up_state": fu,
                    "created_at": task.created_at,
                }
            )

        # Group 2: tasks with active follow_up_state but not waiting_followup status
        all_tasks = store.list_tasks()
        waiting_ids = {t.task_id for t in waiting}
        for task in all_tasks:
            if task.task_id in waiting_ids:
                continue
            d = task.to_dict() if hasattr(task, "to_dict") else {}
            fu = d.get("follow_up_state")
            if not fu or not isinstance(fu, dict):
                continue
            if fu.get("status") == "completed":
                continue
            due_at = fu.get("due_at")
            items.append(
                {
                    "item_id": f"task:{task.task_id}",
                    "source": "life_os_task",
                    "source_id": task.task_id,
                    "title": task.title,
                    "description": fu.get("description", task.description),
                    "status": "waiting_approval" if task.approval_required else _classify_due(due_at),
                    "due_at": due_at,
                    "priority": task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                    "tags": task.tags,
                    "approval_required": task.approval_required,
                    "approval_route": f"/v1/life-os/tasks/{task.task_id}/approve" if task.approval_required else None,
                    "source_route": f"/v1/life-os/tasks/{task.task_id}",
                    "follow_up_state": fu,
                    "created_at": task.created_at,
                }
            )
    except Exception as exc:
        logger.debug("life-os follow-up probe failed: %s", exc)
    return items


def _probe_goal_follow_ups() -> List[Dict[str, Any]]:
    """Return goal follow-up queue items from the goal registry."""
    items: List[Dict[str, Any]] = []
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        registry = get_goal_registry()
        goals = registry.list_goals()
        for goal in goals:
            for fu in goal.follow_up_queue:
                if not isinstance(fu, dict):
                    continue
                if fu.get("completed"):
                    continue
                due_at = fu.get("due_at")
                items.append(
                    {
                        "item_id": f"goal:{goal.goal_id}:followup:{fu.get('follow_up_id', fu.get('id', 'unknown'))}",
                        "source": "goal",
                        "source_id": goal.goal_id,
                        "title": f"[{goal.title}] {fu.get('description', 'Follow-up')}",
                        "description": fu.get("description", ""),
                        "status": _classify_due(due_at),
                        "due_at": due_at,
                        "priority": "medium",
                        "tags": goal.tags,
                        "approval_required": False,
                        "approval_route": None,
                        "source_route": f"/v1/goals/{goal.goal_id}",
                        "follow_up_state": fu,
                        "created_at": fu.get("created_at", goal.created_at),
                    }
                )
    except Exception as exc:
        logger.debug("goal follow-up probe failed: %s", exc)
    return items


def _aggregate_items() -> List[Dict[str, Any]]:
    """Aggregate all follow-up items from all sources, sorted by due_at then created_at."""
    items: List[Dict[str, Any]] = []
    items.extend(_probe_life_os_follow_ups())
    items.extend(_probe_goal_follow_ups())

    def sort_key(item: Dict[str, Any]) -> tuple:
        due = item.get("due_at") or float("inf")
        created = item.get("created_at") or 0.0
        return (due, created)

    items.sort(key=sort_key)
    return items


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/follow-up-center")
async def list_follow_ups(
    source: str = "",
    status: str = "",
    limit: int = 100,
) -> Dict[str, Any]:
    """Return all follow-up items aggregated from all Jarvis OS sources.

    Query params:
      source — filter by source (life_os_task | goal)
      status — filter by status (due | upcoming | waiting_approval | snoozed | completed)
      limit  — max items returned (default 100)
    """
    items = _aggregate_items()

    if source:
        items = [i for i in items if i["source"] == source]
    if status:
        items = [i for i in items if i["status"] == status]

    items = items[:limit]

    due_count = sum(1 for i in items if i["status"] == "due")
    pending_approval = sum(1 for i in items if i["status"] == "waiting_approval")

    return {
        "items": items,
        "count": len(items),
        "due_count": due_count,
        "pending_approval_count": pending_approval,
        "sources_probed": ["life_os_task", "goal"],
        "fake_data": False,
        "automation_honesty": True,
        "note": (
            "Aggregated read-only view. Write actions (complete/snooze) route "
            "through existing approval-gated endpoints."
        ),
    }


@router.get("/v1/follow-up-center/summary")
async def follow_up_summary() -> Dict[str, Any]:
    """Return count summary broken down by source and status."""
    items = _aggregate_items()

    by_source: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for item in items:
        src = item["source"]
        st = item["status"]
        by_source[src] = by_source.get(src, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1

    return {
        "total": len(items),
        "by_source": by_source,
        "by_status": by_status,
        "due": by_status.get("due", 0),
        "upcoming": by_status.get("upcoming", 0),
        "waiting_approval": by_status.get("waiting_approval", 0),
        "snoozed": by_status.get("snoozed", 0),
        "fake_data": False,
    }


@router.post("/v1/follow-up-center/tasks/{task_id}/complete")
async def complete_task_follow_up(task_id: str) -> Dict[str, Any]:
    """Mark a life-os task follow-up as completed.

    Preserves approval gates:
    - If task.approval_required=True: returns the approval_route instead of auto-completing.
    - If task.approval_required=False: marks status=done via the store.
    """
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store, TaskStatus

        store = get_personal_task_store()
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        if task.approval_required:
            return {
                "action": "approval_required",
                "task_id": task_id,
                "message": "This task requires approval before completion.",
                "approval_route": f"/v1/life-os/tasks/{task_id}/approve",
                "completed": False,
            }

        success = store.update_status(task_id, TaskStatus.DONE.value)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update task status")

        return {
            "action": "completed",
            "task_id": task_id,
            "status": "done",
            "completed": True,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("complete_task_follow_up failed: %s", exc)
        raise HTTPException(status_code=503, detail="Task store unavailable")


@router.post("/v1/follow-up-center/tasks/{task_id}/snooze")
async def snooze_task_follow_up(task_id: str, body: SnoozeRequest) -> Dict[str, Any]:
    """Snooze a life-os task follow-up until a given timestamp.

    Updates follow_up_state.snooze_until and sets status to 'snoozed'.
    Does not bypass approval gates — approval_required tasks must still be approved
    through the standard approval route before being completed.
    """
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        fu = task.follow_up_state or {}
        fu["snooze_until"] = body.snooze_until
        fu["snooze_reason"] = body.reason
        fu["snoozed_at"] = time.time()
        fu["status"] = "snoozed"
        task.follow_up_state = fu
        task.updated_at = time.time()

        if hasattr(store, "save"):
            store.save(task)

        return {
            "action": "snoozed",
            "task_id": task_id,
            "snooze_until": body.snooze_until,
            "reason": body.reason,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("snooze_task_follow_up failed: %s", exc)
        raise HTTPException(status_code=503, detail="Task store unavailable")
