"""Long-Horizon Goal Execution REST Routes — B12.

Routes:
  GET  /v1/long-horizon/goals                          — all goals with execution tracking
  GET  /v1/long-horizon/goals/{goal_id}/checkpoint     — checkpoint/status for a specific goal
  GET  /v1/long-horizon/summary                        — quick aggregate summary
  POST /v1/long-horizon/goals/{goal_id}/plan-step      — add a planned step (dry-run only)

Governance:
  - auto_execute: False — no autonomous execution under any circumstance
  - approval_required: True — every execution step gates on explicit approval
  - No secrets in any response
  - No external calls
  - fake_data: False in all responses
  - plan-step is dry-run only — nothing is executed or persisted
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for long_horizon routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["long-horizon"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PlanStepRequest(BaseModel):
    step_type: str = Field(..., description="milestone | action")
    title: str = Field(..., min_length=1)
    description: str = ""
    requires_approval: bool = True


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _goal_to_execution_view(goal: Any) -> Dict[str, Any]:
    """Convert a goal object to the execution tracking dict."""
    gd = goal.to_dict() if hasattr(goal, "to_dict") else {}
    milestones = list(goal.milestones) if hasattr(goal, "milestones") else []
    next_actions = list(goal.next_actions) if hasattr(goal, "next_actions") else []
    follow_up_queue = list(goal.follow_up_queue) if hasattr(goal, "follow_up_queue") else []
    continuation_state = goal.continuation_state if hasattr(goal, "continuation_state") else None

    milestones_total = len(milestones)
    milestones_completed = sum(
        1 for m in milestones
        if (m.status.value if hasattr(m, "status") else m.get("status", "")) == "completed"
    )
    milestones_pending = milestones_total - milestones_completed

    next_actions_total = len(next_actions)
    next_actions_pending = sum(
        1 for a in next_actions
        if (a.status.value if hasattr(a, "status") else a.get("status", "")) not in ("completed", "failed")
    )

    has_continuation_state = bool(
        continuation_state and (
            continuation_state.to_dict() if hasattr(continuation_state, "to_dict") else continuation_state
        )
    )

    return {
        "goal_id": gd.get("goal_id", getattr(goal, "goal_id", "")),
        "title": gd.get("title", ""),
        "description": gd.get("description", ""),
        "horizon": gd.get("horizon", ""),
        "status": gd.get("status", ""),
        "owner": gd.get("owner", ""),
        "tags": gd.get("tags", []),
        "milestones_total": milestones_total,
        "milestones_completed": milestones_completed,
        "milestones_pending": milestones_pending,
        "next_actions_total": next_actions_total,
        "next_actions_pending": next_actions_pending,
        "has_continuation_state": has_continuation_state,
        "follow_up_count": len(follow_up_queue),
        "auto_execute": False,
        "approval_required_for_actions": True,
        "execution_honesty": (
            "All goal execution steps require explicit approval. No autonomous execution."
        ),
    }


def _milestone_to_dict(m: Any) -> Dict[str, Any]:
    if hasattr(m, "to_dict"):
        d = m.to_dict()
    else:
        d = dict(m) if isinstance(m, dict) else {}
    return {
        "milestone_id": d.get("milestone_id", ""),
        "title": d.get("title", ""),
        "status": d.get("status", ""),
        "completion_criteria": d.get("completion_criteria", ""),
    }


def _action_to_dict(a: Any) -> Dict[str, Any]:
    if hasattr(a, "to_dict"):
        d = a.to_dict()
    else:
        d = dict(a) if isinstance(a, dict) else {}
    return {
        "action_id": d.get("action_id", ""),
        "title": d.get("title", ""),
        "action_type": d.get("action_type", ""),
        "requires_approval": d.get("requires_approval", True),
        "status": d.get("status", ""),
    }


def _followup_to_dict(f: Any) -> Dict[str, Any]:
    if isinstance(f, dict):
        return {"description": f.get("description", ""), "due_at": f.get("due_at")}
    return {"description": str(f), "due_at": None}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/long-horizon/goals")
async def list_long_horizon_goals() -> Dict[str, Any]:
    """Return all goals with execution status and checkpoint tracking.

    auto_execute is always False. Every milestone and action requires
    explicit approval before execution.
    """
    try:
        from openjarvis.orchestrator.goals import GoalStatus, get_goal_registry

        registry = get_goal_registry()
        goals = registry.list_all()
    except Exception as exc:
        logger.debug("Goal registry unavailable: %s", type(exc).__name__)
        goals = []

    goal_views: List[Dict[str, Any]] = []
    active_count = 0
    paused_count = 0
    completed_count = 0

    for g in goals:
        try:
            view = _goal_to_execution_view(g)
            goal_views.append(view)
            status = view.get("status", "")
            if status == "active":
                active_count += 1
            elif status == "paused":
                paused_count += 1
            elif status == "completed":
                completed_count += 1
        except Exception as exc:
            logger.debug("Skipping goal due to error: %s", type(exc).__name__)

    return {
        "goals": goal_views,
        "count": len(goal_views),
        "active_count": active_count,
        "paused_count": paused_count,
        "completed_count": completed_count,
        "auto_execute": False,
        "fake_data": False,
        "note": (
            "Long-horizon goals. All milestones and next actions require "
            "explicit approval before execution."
        ),
    }


@router.get("/v1/long-horizon/goals/{goal_id}/checkpoint")
async def goal_checkpoint(goal_id: str) -> Dict[str, Any]:
    """Return checkpoint and execution status for a specific goal.

    Returns 404 if the goal is not found. Continuation state is metadata
    only — no secret values are included.
    """
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        registry = get_goal_registry()
        goal = registry.get(goal_id)
    except Exception as exc:
        logger.debug("Goal registry unavailable: %s", type(exc).__name__)
        goal = None

    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")

    gd = goal.to_dict() if hasattr(goal, "to_dict") else {}
    status = gd.get("status", "")

    milestones = [_milestone_to_dict(m) for m in (goal.milestones if hasattr(goal, "milestones") else [])]
    next_actions = [_action_to_dict(a) for a in (goal.next_actions if hasattr(goal, "next_actions") else [])]
    follow_up_queue = [_followup_to_dict(f) for f in (goal.follow_up_queue if hasattr(goal, "follow_up_queue") else [])]

    continuation_state_raw = goal.continuation_state if hasattr(goal, "continuation_state") else None
    if continuation_state_raw is not None and hasattr(continuation_state_raw, "to_dict"):
        continuation_state = continuation_state_raw.to_dict()
    elif isinstance(continuation_state_raw, dict):
        continuation_state = continuation_state_raw
    else:
        continuation_state = {}

    return {
        "goal_id": goal_id,
        "found": True,
        "title": gd.get("title"),
        "status": status,
        "milestones": milestones,
        "next_actions": next_actions,
        "continuation_state": continuation_state,
        "follow_up_queue": follow_up_queue,
        "can_resume": status == "paused",
        "can_pause": status == "active",
        "auto_execute": False,
        "approval_required": True,
        "fake_data": False,
    }


@router.get("/v1/long-horizon/summary")
async def long_horizon_summary() -> Dict[str, Any]:
    """Return a quick aggregate summary of all long-horizon goals."""
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        registry = get_goal_registry()
        goals = registry.list_all()
    except Exception:
        goals = []

    total = len(goals)
    active = paused = completed = abandoned = 0
    total_pending_milestones = 0
    total_pending_actions = 0

    for g in goals:
        try:
            gd = g.to_dict() if hasattr(g, "to_dict") else {}
            status = gd.get("status", "")
            if status == "active":
                active += 1
            elif status == "paused":
                paused += 1
            elif status == "completed":
                completed += 1
            elif status == "abandoned":
                abandoned += 1

            milestones = list(g.milestones) if hasattr(g, "milestones") else []
            for m in milestones:
                ms = m.status.value if hasattr(m, "status") else m.get("status", "")
                if ms not in ("completed", "failed"):
                    total_pending_milestones += 1

            next_actions = list(g.next_actions) if hasattr(g, "next_actions") else []
            for a in next_actions:
                as_ = a.status.value if hasattr(a, "status") else a.get("status", "")
                if as_ not in ("completed", "failed"):
                    total_pending_actions += 1
        except Exception:
            pass

    return {
        "total_goals": total,
        "active": active,
        "paused": paused,
        "completed": completed,
        "abandoned": abandoned,
        "total_pending_milestones": total_pending_milestones,
        "total_pending_actions": total_pending_actions,
        "approval_required_for_execution": True,
        "auto_execute": False,
        "fake_data": False,
    }


@router.post("/v1/long-horizon/goals/{goal_id}/plan-step")
async def plan_step(goal_id: str, body: PlanStepRequest) -> Dict[str, Any]:
    """Add a planned step (milestone or action) for a goal — DRY-RUN ONLY.

    This endpoint does NOT execute or persist anything. It returns a planning
    confirmation that the step was received. All execution requires explicit
    approval through the appropriate goals routes.
    """
    valid_step_types = {"milestone", "action"}
    if body.step_type not in valid_step_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid step_type '{body.step_type}'. Must be one of: {sorted(valid_step_types)}",
        )

    # Verify goal exists (read-only check)
    goal_found = False
    try:
        from openjarvis.orchestrator.goals import get_goal_registry

        registry = get_goal_registry()
        goal = registry.get(goal_id)
        goal_found = goal is not None
    except Exception:
        goal_found = False

    if not goal_found:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")

    return {
        "goal_id": goal_id,
        "step_planned": True,
        "step_type": body.step_type,
        "title": body.title,
        "executed": False,
        "approval_required": True,
        "gate": "All steps require explicit approval before execution",
        "fake_data": False,
    }


__all__ = ["router"]
