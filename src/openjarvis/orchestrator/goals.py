"""Long-Horizon Autonomous Goal Execution — Phase G.

Provides:
  - Durable goal records with milestones
  - Next actions and continuation state
  - Failure/retry tracking
  - Proactive follow-up queue
  - Memory-driven resumption
  - Human approval gates for risky steps
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class GoalStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NextActionType(str, Enum):
    EXECUTE = "execute"
    RESEARCH = "research"
    APPROVE = "approve"
    WAIT = "wait"
    RETRY = "retry"


@dataclass
class Milestone:
    milestone_id: str
    goal_id: str
    title: str
    description: str
    status: MilestoneStatus
    target_date: Optional[float]
    completion_criteria: str
    memory_refs: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None

    def complete(self) -> None:
        self.status = MilestoneStatus.COMPLETED
        self.completed_at = time.time()

    def fail(self, reason: str = "") -> None:
        self.status = MilestoneStatus.FAILED
        if reason:
            self.memory_refs.append(f"failure:{reason[:100]}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "target_date": self.target_date,
            "completion_criteria": self.completion_criteria,
            "memory_refs": self.memory_refs,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


@dataclass
class NextAction:
    action_id: str
    goal_id: str
    action_type: NextActionType
    title: str
    description: str
    requires_approval: bool
    retry_count: int = 0
    max_retries: int = 3
    last_failed_reason: Optional[str] = None
    scheduled_at: Optional[float] = None

    def increment_retry(self, failure_reason: str = "") -> bool:
        """Returns True if retry is allowed, False if max retries exceeded."""
        self.retry_count += 1
        self.last_failed_reason = failure_reason
        return self.retry_count <= self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "goal_id": self.goal_id,
            "action_type": self.action_type.value,
            "title": self.title,
            "description": self.description,
            "requires_approval": self.requires_approval,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "last_failed_reason": self.last_failed_reason,
            "scheduled_at": self.scheduled_at,
        }


@dataclass
class ContinuationState:
    """State for resuming a paused/interrupted goal."""
    last_milestone_id: Optional[str]
    last_action_id: Optional[str]
    context_snapshot: Dict[str, Any]
    memory_refs: List[str]
    paused_at: float = field(default_factory=time.time)
    pause_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "last_milestone_id": self.last_milestone_id,
            "last_action_id": self.last_action_id,
            "context_snapshot": self.context_snapshot,
            "memory_refs": self.memory_refs,
            "paused_at": self.paused_at,
            "pause_reason": self.pause_reason,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ContinuationState":
        return cls(
            last_milestone_id=d.get("last_milestone_id"),
            last_action_id=d.get("last_action_id"),
            context_snapshot=d.get("context_snapshot", {}),
            memory_refs=d.get("memory_refs", []),
            paused_at=d.get("paused_at", time.time()),
            pause_reason=d.get("pause_reason", ""),
        )


@dataclass
class Goal:
    goal_id: str
    title: str
    description: str
    status: GoalStatus
    horizon: str  # "7d", "30d", "90d", "ongoing"
    owner: str
    milestones: List[Milestone] = field(default_factory=list)
    next_actions: List[NextAction] = field(default_factory=list)
    follow_up_queue: List[Dict[str, Any]] = field(default_factory=list)
    continuation_state: Optional[ContinuationState] = None
    memory_namespace: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        title: str,
        description: str = "",
        horizon: str = "30d",
        owner: str = "bryan",
        tags: Optional[List[str]] = None,
    ) -> "Goal":
        gid = uuid.uuid4().hex
        return cls(
            goal_id=gid,
            title=title,
            description=description,
            status=GoalStatus.ACTIVE,
            horizon=horizon,
            owner=owner,
            tags=tags or [],
            memory_namespace=f"goal:{gid}",
        )

    def add_milestone(
        self,
        title: str,
        description: str = "",
        completion_criteria: str = "",
        target_date: Optional[float] = None,
    ) -> Milestone:
        m = Milestone(
            milestone_id=uuid.uuid4().hex,
            goal_id=self.goal_id,
            title=title,
            description=description,
            status=MilestoneStatus.PENDING,
            target_date=target_date,
            completion_criteria=completion_criteria,
        )
        self.milestones.append(m)
        self.updated_at = time.time()
        return m

    def add_next_action(
        self,
        title: str,
        action_type: str = NextActionType.EXECUTE,
        description: str = "",
        requires_approval: bool = False,
    ) -> NextAction:
        a = NextAction(
            action_id=uuid.uuid4().hex,
            goal_id=self.goal_id,
            action_type=NextActionType(action_type),
            title=title,
            description=description,
            requires_approval=requires_approval,
        )
        self.next_actions.append(a)
        self.updated_at = time.time()
        return a

    def pause(self, reason: str = "", context: Optional[Dict[str, Any]] = None) -> None:
        """Pause the goal and save continuation state."""
        last_m_id = self.milestones[-1].milestone_id if self.milestones else None
        last_a_id = self.next_actions[-1].action_id if self.next_actions else None
        self.continuation_state = ContinuationState(
            last_milestone_id=last_m_id,
            last_action_id=last_a_id,
            context_snapshot=context or {},
            memory_refs=[f"goal:{self.goal_id}"],
            pause_reason=reason,
        )
        self.status = GoalStatus.PAUSED
        self.updated_at = time.time()

    def resume(self) -> Optional[ContinuationState]:
        """Resume from paused state. Returns continuation state."""
        if self.status != GoalStatus.PAUSED:
            return None
        self.status = GoalStatus.ACTIVE
        self.updated_at = time.time()
        return self.continuation_state

    def add_follow_up(self, description: str, due_at: Optional[float] = None) -> Dict[str, Any]:
        item = {
            "id": uuid.uuid4().hex,
            "description": description,
            "due_at": due_at,
            "status": "pending",
            "created_at": time.time(),
        }
        self.follow_up_queue.append(item)
        self.updated_at = time.time()
        return item

    def get_milestone(self, milestone_id: str) -> Optional[Milestone]:
        return next((m for m in self.milestones if m.milestone_id == milestone_id), None)

    def get_next_action(self, action_id: str) -> Optional[NextAction]:
        return next((a for a in self.next_actions if a.action_id == action_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "horizon": self.horizon,
            "owner": self.owner,
            "milestone_count": len(self.milestones),
            "next_action_count": len(self.next_actions),
            "follow_up_count": len(self.follow_up_queue),
            "has_continuation_state": self.continuation_state is not None,
            "memory_namespace": self.memory_namespace,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class GoalRegistry:
    """In-memory goal registry."""

    def __init__(self) -> None:
        self._goals: Dict[str, Goal] = {}

    def create(
        self,
        title: str,
        description: str = "",
        horizon: str = "30d",
        owner: str = "bryan",
        tags: Optional[List[str]] = None,
    ) -> Goal:
        goal = Goal.create(title=title, description=description, horizon=horizon, owner=owner, tags=tags)
        self._goals[goal.goal_id] = goal
        return goal

    def get(self, goal_id: str) -> Optional[Goal]:
        return self._goals.get(goal_id)

    def list_all(self, status: Optional[str] = None) -> List[Goal]:
        goals = list(self._goals.values())
        if status:
            goals = [g for g in goals if g.status.value == status]
        return sorted(goals, key=lambda g: g.created_at, reverse=True)


# Module-level singleton
_registry: Optional[GoalRegistry] = None


def get_goal_registry() -> GoalRegistry:
    global _registry
    if _registry is None:
        _registry = GoalRegistry()
    return _registry


__all__ = [
    "GoalStatus",
    "MilestoneStatus",
    "NextActionType",
    "Milestone",
    "NextAction",
    "ContinuationState",
    "Goal",
    "GoalRegistry",
    "get_goal_registry",
]
