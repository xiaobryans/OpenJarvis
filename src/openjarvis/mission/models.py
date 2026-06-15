"""Mission Control data models — Mission, Task, MissionEvent, SpecialistAgentSpec.

These are canonical data contracts for the Jarvis Mission Control foundation.
No real agent execution happens here; these are pure data types.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MissionStatus(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    RUNNING = "running"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentStatus(str, Enum):
    IDLE = "idle"
    ASSIGNED = "assigned"
    RUNNING = "running"
    BLOCKED = "blocked"
    DISABLED = "disabled"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------


@dataclass
class Mission:
    """A top-level objective tracked in Mission Control.

    Status lifecycle:
        queued → planning → running → completed / failed / cancelled
        Any state can transition to awaiting_approval or blocked.
    """

    id: str = field(default_factory=_new_id)
    title: str = ""
    objective: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: MissionStatus = MissionStatus.QUEUED
    owner: str = "Bryan"
    risk_level: RiskLevel = RiskLevel.LOW
    summary: str = ""
    linked_task_ids: List[str] = field(default_factory=list)
    linked_event_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "objective": self.objective,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status.value,
            "owner": self.owner,
            "risk_level": self.risk_level.value,
            "summary": self.summary,
            "linked_task_ids": list(self.linked_task_ids),
            "linked_event_ids": list(self.linked_event_ids),
        }


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------


@dataclass
class Task:
    """A unit of work within a mission assigned to a specialist agent.

    Tasks are created by the MissionRouter and are NOT marked completed
    until the relevant specialist agent actually executes and confirms.
    """

    id: str = field(default_factory=_new_id)
    mission_id: str = ""
    title: str = ""
    description: str = ""
    assigned_agent_id: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: int = 5
    dependencies: List[str] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    result: str = ""
    summary: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "title": self.title,
            "description": self.description,
            "assigned_agent_id": self.assigned_agent_id,
            "status": self.status.value,
            "priority": self.priority,
            "dependencies": list(self.dependencies),
            "risk_level": self.risk_level.value,
            "result": self.result,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# MissionEvent
# ---------------------------------------------------------------------------


@dataclass
class MissionEvent:
    """A persisted event record linked to a mission (and optionally a task/agent).

    Severity levels: debug / info / warning / error / critical
    """

    event_id: str = field(default_factory=_new_id)
    mission_id: str = ""
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    event_type: str = ""
    severity: str = "info"
    message: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "message": self.message,
            "payload": dict(self.payload),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# SpecialistAgentSpec
# ---------------------------------------------------------------------------


@dataclass
class SpecialistAgentSpec:
    """Configuration record for a specialist agent in the registry.

    This is NOT a running worker or a BaseAgent subclass.  It is the
    registry definition the MissionRouter uses to assign tasks and
    enforce permission/escalation policy.
    """

    agent_id: str
    display_name: str
    role: str
    capabilities: List[str] = field(default_factory=list)
    preferred_model: str = ""
    model_policy: str = "default"
    allowed_tools: List[str] = field(default_factory=list)
    permission_level: str = "standard"
    can_auto_execute_low_risk: bool = True
    escalation_rules: Dict[str, Any] = field(default_factory=dict)
    status: AgentStatus = AgentStatus.IDLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "role": self.role,
            "capabilities": list(self.capabilities),
            "preferred_model": self.preferred_model,
            "model_policy": self.model_policy,
            "allowed_tools": list(self.allowed_tools),
            "permission_level": self.permission_level,
            "can_auto_execute_low_risk": self.can_auto_execute_low_risk,
            "escalation_rules": dict(self.escalation_rules),
            "status": self.status.value,
        }


__all__ = [
    "AgentStatus",
    "Mission",
    "MissionEvent",
    "MissionStatus",
    "RiskLevel",
    "SpecialistAgentSpec",
    "Task",
    "TaskStatus",
    "_new_id",
]
