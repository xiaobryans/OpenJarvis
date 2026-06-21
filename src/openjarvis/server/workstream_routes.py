"""Business/Operator Workstream REST Routes — Phase D.

Routes:
  POST /v1/workstreams                          — create workstream
  GET  /v1/workstreams                          — list workstreams
  GET  /v1/workstreams/{ws_id}                  — get workstream detail
  POST /v1/workstreams/{ws_id}/tasks            — add task to workstream
  POST /v1/workstreams/{ws_id}/tasks/{task_id}/status — update task status
  POST /v1/workstreams/{ws_id}/decisions        — record decision
  GET  /v1/workstreams/{ws_id}/decisions        — list decisions
  GET  /v1/workstreams/{ws_id}/handoff          — generate handoff report
  POST /v1/workstreams/{ws_id}/tasks/{task_id}/trace — add memory trace entry
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from openjarvis.projects.workstream import (
    DecisionType,
    TaskExecutionStatus,
    get_workstream_registry,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workstreams"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateWorkstreamRequest(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = ""
    owner: str = "bryan"
    tags: List[str] = Field(default_factory=list)


class AddTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = ""
    assignee: Optional[str] = None


class UpdateTaskStatusRequest(BaseModel):
    status: str


class RecordDecisionRequest(BaseModel):
    title: str = Field(..., min_length=1)
    decision: str = Field(..., min_length=1)
    rationale: str = ""
    decision_type: str = Field("business", description="architectural | business | technical | operational | approval")
    made_by: str = "bryan"
    affected_tasks: List[str] = Field(default_factory=list)
    alternatives_considered: List[str] = Field(default_factory=list)
    memory_refs: List[str] = Field(default_factory=list)


class AddMemoryTraceRequest(BaseModel):
    event: str = Field(..., min_length=1)
    data: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/v1/workstreams")
async def create_workstream(body: CreateWorkstreamRequest) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws = registry.create(
        name=body.name,
        description=body.description,
        owner=body.owner,
        tags=body.tags,
    )
    return {"workstream": ws.to_dict(), "created": True}


@router.get("/v1/workstreams")
async def list_workstreams(status: Optional[str] = None) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws_list = registry.list_all(status=status)
    return {"workstreams": [w.to_dict() for w in ws_list], "count": len(ws_list)}


@router.get("/v1/workstreams/{ws_id}")
async def get_workstream(ws_id: str) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    detail = ws.to_dict()
    detail["tasks"] = [t.to_dict() for t in ws.tasks.values()]
    detail["decisions"] = [d.to_dict() for d in ws.decisions]
    return {"workstream": detail}


@router.post("/v1/workstreams/{ws_id}/tasks")
async def add_task(ws_id: str, body: AddTaskRequest) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    task = ws.add_task(body.title, body.description, body.assignee)
    return {"task": task.to_dict(), "created": True}


@router.post("/v1/workstreams/{ws_id}/tasks/{task_id}/status")
async def update_task_status(ws_id: str, task_id: str, body: UpdateTaskStatusRequest) -> Dict[str, Any]:
    valid = {s.value for s in TaskExecutionStatus}
    if body.status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    task = ws.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    task.status = TaskExecutionStatus(body.status)
    return {"task_id": task_id, "status": body.status, "updated": True}


@router.post("/v1/workstreams/{ws_id}/decisions")
async def record_decision(ws_id: str, body: RecordDecisionRequest) -> Dict[str, Any]:
    valid_types = {t.value for t in DecisionType}
    if body.decision_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid decision_type: {body.decision_type}")
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    rec = ws.record_decision(
        title=body.title,
        decision=body.decision,
        rationale=body.rationale,
        decision_type=body.decision_type,
        made_by=body.made_by,
    )
    rec.affected_tasks = body.affected_tasks
    rec.alternatives_considered = body.alternatives_considered
    rec.memory_refs = body.memory_refs
    return {"decision": rec.to_dict(), "created": True}


@router.get("/v1/workstreams/{ws_id}/decisions")
async def list_decisions(ws_id: str) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    return {"decisions": [d.to_dict() for d in ws.decisions], "count": len(ws.decisions)}


@router.get("/v1/workstreams/{ws_id}/handoff")
async def generate_handoff(ws_id: str) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    report = ws.generate_handoff()
    return {"handoff": report.to_dict()}


@router.post("/v1/workstreams/{ws_id}/tasks/{task_id}/trace")
async def add_memory_trace(ws_id: str, task_id: str, body: AddMemoryTraceRequest) -> Dict[str, Any]:
    registry = get_workstream_registry()
    ws = registry.get(ws_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Workstream {ws_id} not found")
    task = ws.tasks.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    task.add_memory_trace(body.event, body.data)
    return {"task_id": task_id, "trace_count": len(task.memory_trace)}


__all__ = ["router"]
