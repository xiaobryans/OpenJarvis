"""REST endpoints for Mission Control — missions, tasks, and mission events.

Follows the same singleton-store pattern as approval_routes.py.
All data comes from real MissionStore persistence; no fake data is injected.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from openjarvis.core.events import EventType, get_event_bus
from openjarvis.mission.agent_registry import SpecialistRegistry
from openjarvis.mission.models import (
    MissionEvent,
    MissionStatus,
    RiskLevel,
    TaskStatus,
)
from openjarvis.mission.router import MissionRouter
from openjarvis.mission.store import MissionStore

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except ImportError:
    raise ImportError("fastapi and pydantic are required for mission routes")

logger = logging.getLogger(__name__)

router = APIRouter()

_store: Optional[MissionStore] = None
_mission_router: Optional[MissionRouter] = None


def _get_store() -> MissionStore:
    global _store
    if _store is None:
        _store = MissionStore()
    return _store


def _get_router() -> MissionRouter:
    global _mission_router
    if _mission_router is None:
        _mission_router = MissionRouter(store=_get_store())
    return _mission_router


class CreateMissionRequest(BaseModel):
    objective: str
    title: str = ""
    owner: str = "Bryan"


@router.get("/v1/missions")
async def list_missions() -> Dict[str, Any]:
    store = _get_store()
    missions = store.list_missions()
    return {"missions": [m.to_dict() for m in missions], "count": len(missions)}


@router.post("/v1/missions")
async def create_mission(req: CreateMissionRequest) -> Dict[str, Any]:
    if not req.objective.strip():
        raise HTTPException(status_code=400, detail="objective must not be empty")
    mr = _get_router()
    plan = mr.create_mission(req.objective, owner=req.owner, title=req.title)
    return {
        "mission": plan.mission.to_dict(),
        "tasks": [t.to_dict() for t in plan.tasks],
        "events": [e.to_dict() for e in plan.events],
        "planning_method": plan.planning_method,
    }


@router.get("/v1/missions/{mission_id}")
async def get_mission(mission_id: str) -> Dict[str, Any]:
    store = _get_store()
    mission = store.get_mission(mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    tasks = store.list_tasks(mission_id)
    return {
        "mission": mission.to_dict(),
        "tasks": [t.to_dict() for t in tasks],
    }


@router.get("/v1/missions/{mission_id}/tasks")
async def list_mission_tasks(mission_id: str) -> Dict[str, Any]:
    store = _get_store()
    if store.get_mission(mission_id) is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    tasks = store.list_tasks(mission_id)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


@router.get("/v1/missions/{mission_id}/events")
async def list_mission_events(mission_id: str) -> Dict[str, Any]:
    store = _get_store()
    if store.get_mission(mission_id) is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    events = store.list_events(mission_id)
    return {"events": [e.to_dict() for e in events], "count": len(events)}


@router.get("/v1/tasks/pending-approval")
async def list_pending_approval_tasks() -> Dict[str, Any]:
    store = _get_store()
    tasks = store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


def _emit_task_event(
    store: MissionStore,
    event_type: EventType,
    mission_id: str,
    task_id: str,
    agent_id: str,
    message: str,
    payload: Dict[str, Any],
    severity: str = "info",
) -> MissionEvent:
    evt = MissionEvent(
        mission_id=mission_id,
        task_id=task_id,
        agent_id=agent_id,
        event_type=event_type.value,
        severity=severity,
        message=message,
        payload=payload,
    )
    store.save_event(evt)
    try:
        bus = get_event_bus()
        bus.publish(
            event_type,
            data={"mission_id": mission_id, "task_id": task_id, "agent_id": agent_id},
        )
    except Exception as exc:
        logger.debug("Event bus publish skipped: %s", exc)
    return evt


def _maybe_advance_mission_status(store: MissionStore, mission_id: str) -> None:
    """If no awaiting_approval tasks remain for the mission and the mission
    itself is still awaiting_approval, advance it to running and emit a status
    change event."""
    pending = store.list_all_tasks_by_status(TaskStatus.AWAITING_APPROVAL)
    still_pending = any(t.mission_id == mission_id for t in pending)
    if still_pending:
        return
    mission = store.get_mission(mission_id)
    if mission is None or mission.status != MissionStatus.AWAITING_APPROVAL:
        return
    store.update_mission_status(mission_id, MissionStatus.RUNNING)
    status_evt = MissionEvent(
        mission_id=mission_id,
        event_type=EventType.MISSION_STATUS_CHANGED.value,
        severity="info",
        message="All pending approvals cleared — mission status → running",
        payload={"status": "running", "reason": "all_approvals_cleared"},
    )
    store.save_event(status_evt)
    try:
        bus = get_event_bus()
        bus.publish(
            EventType.MISSION_STATUS_CHANGED,
            data={"mission_id": mission_id, "status": "running"},
        )
    except Exception as exc:
        logger.debug("Event bus publish skipped: %s", exc)


@router.patch("/v1/tasks/{task_id}/approve")
async def approve_task(task_id: str) -> Dict[str, Any]:
    store = _get_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    updated = store.update_task_status(task_id, TaskStatus.ASSIGNED)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    _emit_task_event(
        store,
        EventType.TASK_APPROVED,
        mission_id=task.mission_id,
        task_id=task_id,
        agent_id=task.assigned_agent_id,
        message=f"Task approved by owner: {task.title}",
        payload={"approved_by": "owner", "previous_status": task.status.value},
    )
    _maybe_advance_mission_status(store, task.mission_id)
    logger.info("Task %s approved, mission %s", task_id, task.mission_id)
    return {"task_id": task_id, "status": "assigned", "ok": True}


@router.patch("/v1/tasks/{task_id}/deny")
async def deny_task(task_id: str) -> Dict[str, Any]:
    store = _get_store()
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    updated = store.update_task_status(task_id, TaskStatus.CANCELLED)
    if not updated:
        raise HTTPException(status_code=404, detail="Task not found")
    _emit_task_event(
        store,
        EventType.TASK_CANCELLED,
        mission_id=task.mission_id,
        task_id=task_id,
        agent_id=task.assigned_agent_id,
        message=f"Task denied by owner: {task.title}",
        payload={"denied_by": "owner", "previous_status": task.status.value},
        severity="warning",
    )
    _maybe_advance_mission_status(store, task.mission_id)
    logger.info("Task %s denied, mission %s", task_id, task.mission_id)
    return {"task_id": task_id, "status": "cancelled", "ok": True}


@router.get("/v1/agents")
async def list_agents() -> Dict[str, Any]:
    agents = SpecialistRegistry.all()
    return {"agents": [a.to_dict() for a in agents], "count": len(agents)}


@router.get("/v1/events/recent")
async def list_recent_events(limit: int = 100) -> Dict[str, Any]:
    effective_limit = max(1, min(limit, 500))
    store = _get_store()
    events = store.list_recent_events(limit=effective_limit)
    return {"events": [e.to_dict() for e in events], "count": len(events)}


__all__ = ["router"]
