"""Personal Life OS REST Routes — Phase C.

Routes:
  POST /v1/life-os/tasks              — create personal task
  GET  /v1/life-os/tasks              — list personal tasks
  GET  /v1/life-os/tasks/{task_id}    — get single task
  POST /v1/life-os/tasks/{task_id}/status — update task status
  POST /v1/life-os/tasks/{task_id}/remind — set reminder
  POST /v1/life-os/tasks/{task_id}/follow-up — set follow-up state
  POST /v1/life-os/tasks/{task_id}/approve — approve sensitive task
  GET  /v1/life-os/summary/daily      — daily summary
  GET  /v1/life-os/approvals/pending  — list tasks awaiting approval

Design:
  - No external sends without approval (enforced at task creation)
  - Memory-driven context attached to tasks
  - All sensitive actions gate on approval_required=True
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openjarvis.jarvis_os.personal_os import (
    PersonalTask,
    TaskPriority,
    TaskStatus,
    generate_daily_summary,
    get_personal_task_store,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["life-os"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    priority: str = Field("medium", description="high | medium | low")
    tags: List[str] = Field(default_factory=list)
    scheduled_at: Optional[float] = None
    due_at: Optional[float] = None
    approval_required: bool = False
    memory_refs: List[str] = Field(default_factory=list)


class UpdateStatusRequest(BaseModel):
    status: str = Field(..., description="pending | in_progress | done | cancelled | waiting_approval | waiting_followup")


class SetReminderRequest(BaseModel):
    reminder_type: str = Field("time_based", description="time_based | event_based | follow_up")
    trigger: Any = Field(..., description="Trigger value (timestamp, event name, etc.)")
    notes: str = ""


class SetFollowUpRequest(BaseModel):
    description: str = Field(...)
    due_at: Optional[float] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/v1/life-os/tasks")
async def create_task(body: CreateTaskRequest) -> Dict[str, Any]:
    """Create a personal task. Sensitive tasks are approval-gated."""
    if body.priority not in ("high", "medium", "low"):
        raise HTTPException(status_code=400, detail=f"Invalid priority: {body.priority}")

    store = get_personal_task_store()
    task = PersonalTask.create(
        title=body.title,
        description=body.description,
        priority=body.priority,
        tags=body.tags,
        scheduled_at=body.scheduled_at,
        due_at=body.due_at,
        approval_required=body.approval_required,
    )
    task.memory_refs = body.memory_refs
    store.add(task)
    return {"task": task.to_dict(), "created": True}


@router.get("/v1/life-os/tasks")
async def list_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    store = get_personal_task_store()
    tasks = store.list_tasks(status=status, priority=priority)
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


@router.get("/v1/life-os/tasks/{task_id}")
async def get_task(task_id: str) -> Dict[str, Any]:
    store = get_personal_task_store()
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return {"task": task.to_dict()}


@router.post("/v1/life-os/tasks/{task_id}/status")
async def update_status(task_id: str, body: UpdateStatusRequest) -> Dict[str, Any]:
    valid_statuses = {s.value for s in TaskStatus}
    if body.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    store = get_personal_task_store()
    ok = store.update_status(task_id, body.status)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return {"task_id": task_id, "status": body.status, "updated": True}


@router.post("/v1/life-os/tasks/{task_id}/remind")
async def set_reminder(task_id: str, body: SetReminderRequest) -> Dict[str, Any]:
    store = get_personal_task_store()
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    task.set_reminder(body.reminder_type, body.trigger, body.notes)
    return {"task_id": task_id, "reminder": task.reminder}


@router.post("/v1/life-os/tasks/{task_id}/follow-up")
async def set_follow_up(task_id: str, body: SetFollowUpRequest) -> Dict[str, Any]:
    store = get_personal_task_store()
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    task.set_follow_up(body.description, body.due_at)
    return {"task_id": task_id, "follow_up_state": task.follow_up_state}


@router.post("/v1/life-os/tasks/{task_id}/approve")
async def approve_task(task_id: str) -> Dict[str, Any]:
    """Approve a sensitive task. Moves it from waiting_approval → pending."""
    store = get_personal_task_store()
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    if not task.approval_required:
        raise HTTPException(status_code=400, detail="Task does not require approval")
    task.approve()
    return {"task_id": task_id, "status": task.status.value, "approval_state": task.approval_state}


@router.get("/v1/life-os/summary/daily")
async def daily_summary() -> Dict[str, Any]:
    store = get_personal_task_store()
    summary = generate_daily_summary(store)
    return {"summary": summary.to_dict()}


@router.get("/v1/life-os/approvals/pending")
async def pending_approvals() -> Dict[str, Any]:
    store = get_personal_task_store()
    tasks = store.pending_approvals()
    return {"tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


__all__ = ["router"]
