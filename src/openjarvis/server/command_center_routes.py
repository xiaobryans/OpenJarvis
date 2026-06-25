"""Command Center Routes — Phase B4 unified Task/Project/Goal OS view.

Aggregates items from all Jarvis OS sources into one command-center dashboard:
  - Life-OS personal tasks (pending / in_progress)
  - Long-horizon goals (active)
  - Projects from registry

Routes:
  GET /v1/command-center         — unified aggregated dashboard
  GET /v1/command-center/summary — count summary by source/status

Design rules:
  - Read-only aggregation from existing stores.
  - No fake data. Honest empty state.
  - No connector credential dependency.
  - No autonomous execution.
  - Approval gates unaffected (read-only).
  - No secret values.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["command-center"])


def _gather_tasks() -> List[Dict[str, Any]]:
    """Gather pending/in-progress life-os tasks."""
    items: List[Dict[str, Any]] = []
    try:
        from openjarvis.jarvis_os.personal_os import get_personal_task_store

        store = get_personal_task_store()
        tasks = store.list_tasks()
        for task in tasks:
            d = task.to_dict() if hasattr(task, "to_dict") else {}
            status = d.get("status", "unknown")
            if status in ("done", "cancelled"):
                continue
            items.append(
                {
                    "item_id": f"task:{task.task_id}",
                    "source": "life_os_task",
                    "source_id": task.task_id,
                    "title": task.title,
                    "description": task.description,
                    "status": status,
                    "priority": task.priority.value if hasattr(task.priority, "value") else str(task.priority),
                    "tags": task.tags,
                    "approval_required": task.approval_required,
                    "due_at": task.due_at,
                    "source_route": f"/v1/life-os/tasks/{task.task_id}",
                    "linked_goal": None,
                }
            )
    except Exception as exc:
        logger.debug("task gather failed: %s", exc)
    return items


def _gather_goals() -> List[Dict[str, Any]]:
    """Gather active goals."""
    items: List[Dict[str, Any]] = []
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        registry = get_goal_registry()
        goals = registry.list_goals()
        for goal in goals:
            d = goal.to_dict() if hasattr(goal, "to_dict") else {}
            status = d.get("status", "unknown")
            if status in ("completed", "abandoned"):
                continue
            milestones = d.get("milestones", [])
            pending_milestones = [m for m in milestones if m.get("status") == "pending"]
            next_actions = d.get("next_actions", [])
            pending_actions = [a for a in next_actions if a.get("status") not in ("completed", "failed")]
            items.append(
                {
                    "item_id": f"goal:{goal.goal_id}",
                    "source": "goal",
                    "source_id": goal.goal_id,
                    "title": goal.title,
                    "description": goal.description,
                    "status": status,
                    "priority": "high",
                    "tags": goal.tags,
                    "approval_required": False,
                    "due_at": None,
                    "source_route": f"/v1/goals/{goal.goal_id}",
                    "horizon": goal.horizon,
                    "pending_milestones": len(pending_milestones),
                    "pending_actions": len(pending_actions),
                    "follow_up_count": len(goal.follow_up_queue),
                }
            )
    except Exception as exc:
        logger.debug("goal gather failed: %s", exc)
    return items


def _gather_projects() -> List[Dict[str, Any]]:
    """Gather active projects from registry."""
    items: List[Dict[str, Any]] = []
    try:
        from openjarvis.governance.constitution import ProjectRegistry

        registry = ProjectRegistry.all_projects()
        for proj in registry:
            if not proj.is_active:
                continue
            items.append(
                {
                    "item_id": f"project:{proj.project_id}",
                    "source": "project",
                    "source_id": proj.project_id,
                    "title": proj.name,
                    "description": proj.description,
                    "status": "active",
                    "priority": "high" if proj.priority == 1 else "medium",
                    "tags": [],
                    "approval_required": False,
                    "due_at": None,
                    "source_route": f"/v1/projects/{proj.project_id}",
                }
            )
    except Exception as exc:
        logger.debug("project gather failed: %s", exc)
    return items


@router.get("/v1/command-center")
async def get_command_center(
    source: str = "",
    status: str = "",
    limit: int = 100,
) -> Dict[str, Any]:
    """Unified Task/Project/Goal command center dashboard.

    Query params:
      source — filter by source (life_os_task | goal | project)
      status — filter by status
      limit  — max items (default 100)
    """
    items: List[Dict[str, Any]] = []
    items.extend(_gather_tasks())
    items.extend(_gather_goals())
    items.extend(_gather_projects())

    if source:
        items = [i for i in items if i["source"] == source]
    if status:
        items = [i for i in items if i["status"] == status]

    items = items[:limit]

    by_source: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for item in items:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1

    return {
        "items": items,
        "count": len(items),
        "by_source": by_source,
        "by_status": by_status,
        "sources_probed": ["life_os_task", "goal", "project"],
        "fake_data": False,
        "note": "Unified read-only view of tasks, goals, and projects.",
    }


@router.get("/v1/command-center/summary")
async def get_command_center_summary() -> Dict[str, Any]:
    """Count summary across all command-center sources."""
    tasks = _gather_tasks()
    goals = _gather_goals()
    projects = _gather_projects()

    return {
        "tasks": {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t["status"] == "pending"),
            "in_progress": sum(1 for t in tasks if t["status"] == "in_progress"),
            "waiting_approval": sum(1 for t in tasks if t["status"] == "waiting_approval"),
        },
        "goals": {
            "total": len(goals),
            "active": sum(1 for g in goals if g["status"] == "active"),
            "paused": sum(1 for g in goals if g["status"] == "paused"),
        },
        "projects": {
            "total": len(projects),
            "active": sum(1 for p in projects if p["status"] == "active"),
        },
        "grand_total": len(tasks) + len(goals) + len(projects),
        "fake_data": False,
    }
