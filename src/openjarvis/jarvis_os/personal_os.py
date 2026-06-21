"""Personal Life OS — Phase C.

Jarvis handles personal planning, admin, and follow-up as an operator.

Features:
  - Personal task intake, prioritization, scheduling hooks, reminders/follow-up state
  - Memory-driven personal context
  - Approval gates for sensitive actions
  - Daily/weekly summary primitives
  - No external sends without approval
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskPriority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_FOLLOWUP = "waiting_followup"


class ReminderType(str, Enum):
    TIME_BASED = "time_based"
    EVENT_BASED = "event_based"
    FOLLOW_UP = "follow_up"


@dataclass
class PersonalTask:
    task_id: str
    title: str
    description: str
    priority: TaskPriority
    status: TaskStatus
    tags: List[str] = field(default_factory=list)
    memory_refs: List[str] = field(default_factory=list)
    reminder: Optional[Dict[str, Any]] = None
    follow_up_state: Optional[Dict[str, Any]] = None
    approval_required: bool = False
    approval_state: Optional[str] = None
    scheduled_at: Optional[float] = None
    due_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        title: str,
        description: str = "",
        priority: str = TaskPriority.MEDIUM,
        tags: Optional[List[str]] = None,
        scheduled_at: Optional[float] = None,
        due_at: Optional[float] = None,
        approval_required: bool = False,
    ) -> "PersonalTask":
        return cls(
            task_id=uuid.uuid4().hex,
            title=title,
            description=description,
            priority=TaskPriority(priority),
            status=TaskStatus.WAITING_APPROVAL if approval_required else TaskStatus.PENDING,
            tags=tags or [],
            approval_required=approval_required,
            approval_state="pending_approval" if approval_required else None,
            scheduled_at=scheduled_at,
            due_at=due_at,
        )

    def set_reminder(self, reminder_type: str, trigger: Any, notes: str = "") -> None:
        self.reminder = {
            "type": reminder_type,
            "trigger": trigger,
            "notes": notes,
            "created_at": time.time(),
        }
        self.updated_at = time.time()

    def set_follow_up(self, follow_up_description: str, due_at: Optional[float] = None) -> None:
        self.follow_up_state = {
            "description": follow_up_description,
            "due_at": due_at,
            "status": "pending",
            "created_at": time.time(),
        }
        self.status = TaskStatus.WAITING_FOLLOWUP
        self.updated_at = time.time()

    def approve(self) -> None:
        if self.approval_required:
            self.approval_state = "approved"
            self.status = TaskStatus.PENDING
            self.updated_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "tags": self.tags,
            "memory_refs": self.memory_refs,
            "reminder": self.reminder,
            "follow_up_state": self.follow_up_state,
            "approval_required": self.approval_required,
            "approval_state": self.approval_state,
            "scheduled_at": self.scheduled_at,
            "due_at": self.due_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class PersonalTaskStore:
    """In-memory personal task store. Persistent backend pluggable."""

    def __init__(self) -> None:
        self._tasks: Dict[str, PersonalTask] = {}

    def add(self, task: PersonalTask) -> str:
        self._tasks[task.task_id] = task
        return task.task_id

    def get(self, task_id: str) -> Optional[PersonalTask]:
        return self._tasks.get(task_id)

    def update_status(self, task_id: str, status: str) -> bool:
        task = self._tasks.get(task_id)
        if task is None:
            return False
        task.status = TaskStatus(status)
        task.updated_at = time.time()
        return True

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[PersonalTask]:
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        if priority:
            tasks = [t for t in tasks if t.priority.value == priority]
        return sorted(tasks, key=lambda t: t.created_at, reverse=True)

    def pending_approvals(self) -> List[PersonalTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.WAITING_APPROVAL]

    def pending_follow_ups(self) -> List[PersonalTask]:
        return [t for t in self._tasks.values() if t.status == TaskStatus.WAITING_FOLLOWUP]


@dataclass
class DailySummary:
    date: str
    tasks_completed: int
    tasks_pending: int
    tasks_high_priority: int
    follow_ups_due: int
    approvals_waiting: int
    memory_items_used: int
    summary_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "tasks_completed": self.tasks_completed,
            "tasks_pending": self.tasks_pending,
            "tasks_high_priority": self.tasks_high_priority,
            "follow_ups_due": self.follow_ups_due,
            "approvals_waiting": self.approvals_waiting,
            "memory_items_used": self.memory_items_used,
            "summary_text": self.summary_text,
        }


def generate_daily_summary(store: PersonalTaskStore) -> DailySummary:
    """Generate a daily summary from the personal task store."""
    from datetime import datetime
    all_tasks = store.list_tasks()
    completed = [t for t in all_tasks if t.status == TaskStatus.DONE]
    pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]
    high = [t for t in all_tasks if t.priority == TaskPriority.HIGH]
    follow_ups = store.pending_follow_ups()
    approvals = store.pending_approvals()

    return DailySummary(
        date=datetime.now().strftime("%Y-%m-%d"),
        tasks_completed=len(completed),
        tasks_pending=len(pending),
        tasks_high_priority=len(high),
        follow_ups_due=len(follow_ups),
        approvals_waiting=len(approvals),
        memory_items_used=sum(len(t.memory_refs) for t in all_tasks),
        summary_text=(
            f"{len(completed)} done, {len(pending)} pending, "
            f"{len(high)} high-priority, {len(follow_ups)} follow-ups, "
            f"{len(approvals)} awaiting approval"
        ),
    )


# Module-level singleton for server use
_store: Optional[PersonalTaskStore] = None


def get_personal_task_store() -> PersonalTaskStore:
    global _store
    if _store is None:
        _store = PersonalTaskStore()
    return _store


__all__ = [
    "TaskPriority",
    "TaskStatus",
    "ReminderType",
    "PersonalTask",
    "PersonalTaskStore",
    "DailySummary",
    "generate_daily_summary",
    "get_personal_task_store",
]
