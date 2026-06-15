"""REST endpoints for Mission Control — missions, tasks, and mission events.

Follows the same singleton-store pattern as approval_routes.py.
All data comes from real MissionStore persistence; no fake data is injected.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

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


__all__ = ["router"]
