"""Company OS routes — Phase C8.

Provides /v1/company-os/* endpoints for the Company Operating System layer.
NOTE: Does NOT conflict with existing /v1/company-org/* and /v1/continuity/*
endpoints in company_org_routes.py — this uses the /v1/company-os/ prefix.

live_business_execution and unsupervised_decisions are always False.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["company-os"])
__all__ = ["router"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared lane definitions — used by both dashboard and workflow-lanes endpoints
# ---------------------------------------------------------------------------

_WORKFLOW_LANES: List[Dict[str, Any]] = [
    {
        "lane_id": "research",
        "name": "Research & Analysis",
        "active": True,
        "live_web": False,
        "approval_required": True,
    },
    {
        "lane_id": "admin",
        "name": "Admin & Operations",
        "active": True,
        "live_ops": False,
        "approval_required": True,
    },
    {
        "lane_id": "product",
        "name": "Product Development",
        "active": True,
        "live_deploy": False,
        "approval_required": True,
    },
    {
        "lane_id": "coding",
        "name": "Coding & Engineering",
        "active": True,
        "live_exec": False,
        "approval_required": True,
    },
    {
        "lane_id": "legal",
        "name": "Legal & Compliance",
        "active": False,
        "approval_required": True,
        "gate": "External legal counsel required",
    },
    {
        "lane_id": "finance",
        "name": "Finance & Accounting",
        "active": False,
        "approval_required": True,
        "gate": "Financial connector required",
    },
]


def _count_active_lanes() -> int:
    return sum(1 for lane in _WORKFLOW_LANES if lane.get("active", False))


def _read_goals_count() -> int:
    try:
        from openjarvis.orchestrator.goals import get_goal_registry  # type: ignore[import]

        registry = get_goal_registry()
        goals = registry.list_all()
        return len(goals) if isinstance(goals, list) else 0
    except Exception:
        return 0


def _read_tasks_count() -> int:
    try:
        from openjarvis.orchestrator.goals import get_goal_registry  # type: ignore[import]

        registry = get_goal_registry()
        goals = registry.list_all(status="active")
        return len(goals) if isinstance(goals, list) else 0
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class DryRunPlanRequest(BaseModel):
    lane_id: str
    goal: str
    context: Optional[str] = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/v1/company-os/dashboard")
async def company_os_dashboard() -> Dict[str, Any]:
    """Return Company OS dashboard with workflow lanes and store counts."""
    goals_count = _read_goals_count()
    tasks_count = _read_tasks_count()

    return {
        "operating_status": "active_local_only",
        "workflow_lanes": _WORKFLOW_LANES,
        "active_lanes": _count_active_lanes(),
        "live_business_execution": False,
        "sending_external_messages": False,
        "fake_company_operation": False,
        "fake_data": False,
        "goals_count": goals_count,
        "tasks_count": tasks_count,
        "note": (
            "Company OS dashboard. Local task/goal integration only. "
            "No live business execution. Legal/finance require external gates."
        ),
    }


@router.get("/v1/company-os/workflow-lanes")
async def workflow_lanes() -> Dict[str, Any]:
    """Return all workflow lane definitions with gate and approval metadata."""
    return {
        "lanes": _WORKFLOW_LANES,
        "owner_approval_required": True,
        "unsupervised_decisions": False,
        "live_business_execution": False,
        "fake_data": False,
    }


@router.post("/v1/company-os/dry-run-plan")
async def dry_run_plan(body: DryRunPlanRequest) -> Dict[str, Any]:
    """Dry-run an operating plan for a workflow lane — never executes."""
    lane_id = (body.lane_id or "").strip()
    goal = (body.goal or "").strip()

    if not lane_id:
        raise HTTPException(status_code=422, detail="lane_id must be a non-empty string")
    if not goal:
        raise HTTPException(status_code=422, detail="goal must be a non-empty string")

    return {
        "lane_id": lane_id,
        "goal": goal[:300],
        "dry_run": True,
        "executed": False,
        "approval_required": True,
        "owner_approval": True,
        "plan_steps": [
            {
                "step": 1,
                "description": f"Validate goal against '{lane_id}' lane scope",
            },
            {
                "step": 2,
                "description": "Request owner approval for operating plan",
            },
            {
                "step": 3,
                "description": f"Execute: {goal[:100]} (requires explicit approval)",
            },
        ],
        "live_business_execution": False,
        "fake_data": False,
    }


@router.get("/v1/company-os/mission-linkage")
async def mission_linkage() -> Dict[str, Any]:
    """Return cross-system mission/goal/task linkage counts."""
    linked_missions = 0
    linked_goals = 0
    linked_tasks = 0
    sources: List[str] = []

    try:
        from openjarvis.mission.store import MissionStore  # type: ignore[import]

        store = MissionStore()
        missions = store.list_all() if hasattr(store, "list_all") else []
        linked_missions = len(missions) if isinstance(missions, list) else 0
        sources.append("mission_store")
    except Exception:
        pass

    try:
        from openjarvis.orchestrator.goals import get_goal_registry  # type: ignore[import]

        registry = get_goal_registry()
        goals = registry.list_all()
        linked_goals = len(goals) if isinstance(goals, list) else 0
        sources.append("goal_registry")
    except Exception:
        pass

    try:
        from openjarvis.orchestrator.goals import get_goal_registry  # type: ignore[import]

        registry = get_goal_registry()
        tasks = registry.list_all(status="active")
        linked_tasks = len(tasks) if isinstance(tasks, list) else 0
        if "goal_registry" not in sources:
            sources.append("goal_registry")
    except Exception:
        pass

    cross_system_live = len(sources) > 0

    return {
        "linked_missions": linked_missions,
        "linked_goals": linked_goals,
        "linked_tasks": linked_tasks,
        "cross_system_live": cross_system_live,
        "auto_linking": False,
        "fake_data": False,
        "sources": sources,
    }
