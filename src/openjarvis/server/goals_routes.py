"""Long-Horizon Goal REST Routes — Phase G.

Routes:
  POST /v1/goals                              — create goal
  GET  /v1/goals                              — list goals
  GET  /v1/goals/{goal_id}                    — get goal detail
  POST /v1/goals/{goal_id}/milestones         — add milestone
  POST /v1/goals/{goal_id}/milestones/{mid}/complete — complete milestone
  POST /v1/goals/{goal_id}/milestones/{mid}/fail     — fail milestone
  POST /v1/goals/{goal_id}/actions            — add next action
  POST /v1/goals/{goal_id}/actions/{aid}/retry       — retry failed action
  POST /v1/goals/{goal_id}/pause              — pause goal (save continuation state)
  POST /v1/goals/{goal_id}/resume             — resume paused goal
  POST /v1/goals/{goal_id}/follow-up          — add follow-up
  GET  /v1/goals/{goal_id}/continuation       — get continuation state
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openjarvis.orchestrator.goals import (
    GoalStatus,
    MilestoneStatus,
    NextActionType,
    get_goal_registry,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["goals"])


class CreateGoalRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    horizon: str = Field("30d", description="7d | 30d | 90d | ongoing")
    owner: str = "bryan"
    tags: List[str] = Field(default_factory=list)


class AddMilestoneRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    completion_criteria: str = ""
    target_date: Optional[float] = None


class FailMilestoneRequest(BaseModel):
    reason: str = ""


class AddNextActionRequest(BaseModel):
    title: str = Field(..., min_length=1)
    action_type: str = Field("execute")
    description: str = ""
    requires_approval: bool = False


class RetryActionRequest(BaseModel):
    failure_reason: str = ""


class PauseGoalRequest(BaseModel):
    reason: str = ""
    context: Dict[str, Any] = Field(default_factory=dict)


class AddFollowUpRequest(BaseModel):
    description: str = Field(..., min_length=1)
    due_at: Optional[float] = None


@router.post("/v1/goals")
async def create_goal(body: CreateGoalRequest) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.create(
        title=body.title,
        description=body.description,
        horizon=body.horizon,
        owner=body.owner,
        tags=body.tags,
    )
    return {"goal": goal.to_dict(), "created": True}


@router.get("/v1/goals")
async def list_goals(status: Optional[str] = None) -> Dict[str, Any]:
    registry = get_goal_registry()
    goals = registry.list_all(status=status)
    return {"goals": [g.to_dict() for g in goals], "count": len(goals)}


@router.get("/v1/goals/{goal_id}")
async def get_goal(goal_id: str) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    detail = goal.to_dict()
    detail["milestones"] = [m.to_dict() for m in goal.milestones]
    detail["next_actions"] = [a.to_dict() for a in goal.next_actions]
    detail["follow_up_queue"] = goal.follow_up_queue
    return {"goal": detail}


@router.post("/v1/goals/{goal_id}/milestones")
async def add_milestone(goal_id: str, body: AddMilestoneRequest) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    milestone = goal.add_milestone(
        title=body.title,
        description=body.description,
        completion_criteria=body.completion_criteria,
        target_date=body.target_date,
    )
    return {"milestone": milestone.to_dict(), "created": True}


@router.post("/v1/goals/{goal_id}/milestones/{mid}/complete")
async def complete_milestone(goal_id: str, mid: str) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    milestone = goal.get_milestone(mid)
    if milestone is None:
        raise HTTPException(status_code=404, detail=f"Milestone {mid} not found")
    milestone.complete()
    return {"milestone_id": mid, "status": milestone.status.value}


@router.post("/v1/goals/{goal_id}/milestones/{mid}/fail")
async def fail_milestone(goal_id: str, mid: str, body: FailMilestoneRequest) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    milestone = goal.get_milestone(mid)
    if milestone is None:
        raise HTTPException(status_code=404, detail=f"Milestone {mid} not found")
    milestone.fail(body.reason)
    return {"milestone_id": mid, "status": milestone.status.value}


@router.post("/v1/goals/{goal_id}/actions")
async def add_next_action(goal_id: str, body: AddNextActionRequest) -> Dict[str, Any]:
    valid = {t.value for t in NextActionType}
    if body.action_type not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid action_type: {body.action_type}")
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    action = goal.add_next_action(
        title=body.title,
        action_type=body.action_type,
        description=body.description,
        requires_approval=body.requires_approval,
    )
    return {"action": action.to_dict(), "created": True}


@router.post("/v1/goals/{goal_id}/actions/{aid}/retry")
async def retry_action(goal_id: str, aid: str, body: RetryActionRequest) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    action = goal.get_next_action(aid)
    if action is None:
        raise HTTPException(status_code=404, detail=f"Action {aid} not found")
    can_retry = action.increment_retry(body.failure_reason)
    return {
        "action_id": aid,
        "retry_count": action.retry_count,
        "max_retries": action.max_retries,
        "can_retry": can_retry,
        "last_failed_reason": action.last_failed_reason,
    }


@router.post("/v1/goals/{goal_id}/pause")
async def pause_goal(goal_id: str, body: PauseGoalRequest) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    goal.pause(reason=body.reason, context=body.context)
    return {
        "goal_id": goal_id,
        "status": goal.status.value,
        "continuation_state": goal.continuation_state.to_dict() if goal.continuation_state else None,
    }


@router.post("/v1/goals/{goal_id}/resume")
async def resume_goal(goal_id: str) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    cont = goal.resume()
    return {
        "goal_id": goal_id,
        "status": goal.status.value,
        "resumed": cont is not None,
        "continuation_state": cont.to_dict() if cont else None,
    }


@router.post("/v1/goals/{goal_id}/follow-up")
async def add_follow_up(goal_id: str, body: AddFollowUpRequest) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    item = goal.add_follow_up(body.description, body.due_at)
    return {"follow_up": item}


@router.get("/v1/goals/{goal_id}/continuation")
async def get_continuation(goal_id: str) -> Dict[str, Any]:
    registry = get_goal_registry()
    goal = registry.get(goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    return {
        "goal_id": goal_id,
        "status": goal.status.value,
        "continuation_state": goal.continuation_state.to_dict() if goal.continuation_state else None,
        "has_continuation": goal.continuation_state is not None,
    }


__all__ = ["router"]
