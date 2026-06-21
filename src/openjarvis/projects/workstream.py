"""Business/Operator Workstream Registry — Phase D.

Provides:
  - Workstream (project/workstream) creation and management
  - Task execution state within workstreams
  - Decision log recording
  - Follow-up/handoff generation
  - External connector routing (with gates)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class WorkstreamStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    ARCHIVED = "archived"


class TaskExecutionStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    BLOCKED = "blocked"
    AWAITING_HANDOFF = "awaiting_handoff"


class DecisionType(str, Enum):
    ARCHITECTURAL = "architectural"
    BUSINESS = "business"
    TECHNICAL = "technical"
    OPERATIONAL = "operational"
    APPROVAL = "approval"


@dataclass
class WorkstreamTask:
    task_id: str
    title: str
    description: str
    status: TaskExecutionStatus
    assignee: Optional[str]
    memory_trace: List[Dict[str, Any]] = field(default_factory=list)
    connector_actions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def add_memory_trace(self, event: str, data: Dict[str, Any]) -> None:
        self.memory_trace.append({
            "event": event,
            "data": data,
            "ts": time.time(),
        })
        self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assignee": self.assignee,
            "memory_trace": self.memory_trace,
            "connector_actions": self.connector_actions,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DecisionRecord:
    decision_id: str
    workstream_id: str
    decision_type: DecisionType
    title: str
    decision: str
    rationale: str
    made_by: str
    affected_tasks: List[str] = field(default_factory=list)
    alternatives_considered: List[str] = field(default_factory=list)
    memory_refs: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "workstream_id": self.workstream_id,
            "decision_type": self.decision_type.value,
            "title": self.title,
            "decision": self.decision,
            "rationale": self.rationale,
            "made_by": self.made_by,
            "affected_tasks": self.affected_tasks,
            "alternatives_considered": self.alternatives_considered,
            "memory_refs": self.memory_refs,
            "created_at": self.created_at,
        }


@dataclass
class HandoffReport:
    report_id: str
    workstream_id: str
    summary: str
    completed_tasks: List[str]
    pending_tasks: List[str]
    decisions_made: List[str]
    next_actions: List[str]
    blockers: List[str]
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "workstream_id": self.workstream_id,
            "summary": self.summary,
            "completed_tasks": self.completed_tasks,
            "pending_tasks": self.pending_tasks,
            "decisions_made": self.decisions_made,
            "next_actions": self.next_actions,
            "blockers": self.blockers,
            "generated_at": self.generated_at,
        }


@dataclass
class Workstream:
    workstream_id: str
    name: str
    description: str
    status: WorkstreamStatus
    owner: str
    tags: List[str] = field(default_factory=list)
    tasks: Dict[str, WorkstreamTask] = field(default_factory=dict)
    decisions: List[DecisionRecord] = field(default_factory=list)
    memory_namespace: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        owner: str = "bryan",
        tags: Optional[List[str]] = None,
    ) -> "Workstream":
        wid = uuid.uuid4().hex
        return cls(
            workstream_id=wid,
            name=name,
            description=description,
            status=WorkstreamStatus.ACTIVE,
            owner=owner,
            tags=tags or [],
            memory_namespace=f"workstream:{wid}",
        )

    def add_task(
        self,
        title: str,
        description: str = "",
        assignee: Optional[str] = None,
    ) -> WorkstreamTask:
        task = WorkstreamTask(
            task_id=uuid.uuid4().hex,
            title=title,
            description=description,
            status=TaskExecutionStatus.PENDING,
            assignee=assignee,
        )
        self.tasks[task.task_id] = task
        self.updated_at = time.time()
        return task

    def record_decision(
        self,
        title: str,
        decision: str,
        rationale: str,
        decision_type: str = DecisionType.BUSINESS,
        made_by: str = "bryan",
    ) -> DecisionRecord:
        rec = DecisionRecord(
            decision_id=uuid.uuid4().hex,
            workstream_id=self.workstream_id,
            decision_type=DecisionType(decision_type),
            title=title,
            decision=decision,
            rationale=rationale,
            made_by=made_by,
        )
        self.decisions.append(rec)
        self.updated_at = time.time()
        return rec

    def generate_handoff(self) -> HandoffReport:
        completed = [t.title for t in self.tasks.values() if t.status == TaskExecutionStatus.DONE]
        pending = [t.title for t in self.tasks.values() if t.status in (TaskExecutionStatus.PENDING, TaskExecutionStatus.IN_PROGRESS)]
        blocked = [t.title for t in self.tasks.values() if t.status == TaskExecutionStatus.BLOCKED]
        decisions = [d.title for d in self.decisions]

        return HandoffReport(
            report_id=uuid.uuid4().hex,
            workstream_id=self.workstream_id,
            summary=f"Workstream '{self.name}': {len(completed)} done, {len(pending)} pending",
            completed_tasks=completed,
            pending_tasks=pending,
            decisions_made=decisions,
            next_actions=[f"Continue: {t}" for t in pending[:3]],
            blockers=blocked,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workstream_id": self.workstream_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "owner": self.owner,
            "tags": self.tags,
            "task_count": len(self.tasks),
            "decision_count": len(self.decisions),
            "memory_namespace": self.memory_namespace,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WorkstreamRegistry:
    """In-memory workstream registry."""

    def __init__(self) -> None:
        self._workstreams: Dict[str, Workstream] = {}

    def create(self, name: str, description: str = "", owner: str = "bryan", tags: Optional[List[str]] = None) -> Workstream:
        ws = Workstream.create(name=name, description=description, owner=owner, tags=tags)
        self._workstreams[ws.workstream_id] = ws
        return ws

    def get(self, workstream_id: str) -> Optional[Workstream]:
        return self._workstreams.get(workstream_id)

    def list_all(self, status: Optional[str] = None) -> List[Workstream]:
        ws_list = list(self._workstreams.values())
        if status:
            ws_list = [w for w in ws_list if w.status.value == status]
        return sorted(ws_list, key=lambda w: w.created_at, reverse=True)


# Module-level singleton
_registry: Optional[WorkstreamRegistry] = None


def get_workstream_registry() -> WorkstreamRegistry:
    global _registry
    if _registry is None:
        _registry = WorkstreamRegistry()
    return _registry


__all__ = [
    "WorkstreamStatus",
    "TaskExecutionStatus",
    "DecisionType",
    "WorkstreamTask",
    "DecisionRecord",
    "HandoffReport",
    "Workstream",
    "WorkstreamRegistry",
    "get_workstream_registry",
]
