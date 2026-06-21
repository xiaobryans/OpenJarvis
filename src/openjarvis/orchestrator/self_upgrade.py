"""Self-Upgrade / Major Coding Execution — Phase I.

Provides:
  - Staged self-upgrade plan creation
  - Step-by-step execution state
  - Rollback metadata
  - Confirmation gates for risky/destructive/release actions
  - Provider truthfulness (no fake model/provider claims)
  - Memory usage for past failures
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class UpgradeStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SKIPPED = "skipped"


class UpgradeRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DESTRUCTIVE = "destructive"


class ProviderStatus(str, Enum):
    AVAILABLE = "available"
    MOCK = "mock"
    LOCAL = "local"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    NOT_CONFIGURED = "not_configured"


@dataclass
class UpgradeStep:
    step_id: str
    plan_id: str
    order: int
    title: str
    description: str
    status: UpgradeStepStatus
    risk: UpgradeRisk
    requires_confirmation: bool
    rollback_command: Optional[str]
    validation_command: Optional[str]
    files_to_modify: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    retry_count: int = 0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def start(self) -> None:
        self.status = UpgradeStepStatus.IN_PROGRESS
        self.started_at = time.time()

    def complete(self) -> None:
        self.status = UpgradeStepStatus.DONE
        self.completed_at = time.time()

    def fail(self, reason: str) -> None:
        self.status = UpgradeStepStatus.FAILED
        self.failure_reason = reason
        self.completed_at = time.time()

    def rollback(self) -> None:
        self.status = UpgradeStepStatus.ROLLED_BACK

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "plan_id": self.plan_id,
            "order": self.order,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "risk": self.risk.value,
            "requires_confirmation": self.requires_confirmation,
            "rollback_command": self.rollback_command,
            "validation_command": self.validation_command,
            "files_to_modify": self.files_to_modify,
            "failure_reason": self.failure_reason,
            "retry_count": self.retry_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class RollbackMetadata:
    plan_id: str
    rollback_id: str
    reason: str
    steps_to_rollback: List[str]
    rollback_commands: List[str]
    can_auto_rollback: bool
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "rollback_id": self.rollback_id,
            "reason": self.reason,
            "steps_to_rollback": self.steps_to_rollback,
            "rollback_commands": self.rollback_commands,
            "can_auto_rollback": self.can_auto_rollback,
            "created_at": self.created_at,
        }


@dataclass
class ModelProviderTruth:
    """Truthful declaration of model/provider status. No fake claims allowed."""
    provider_name: str
    status: ProviderStatus
    model_id: Optional[str]
    is_live: bool
    is_mock: bool
    notes: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_name": self.provider_name,
            "status": self.status.value,
            "model_id": self.model_id,
            "is_live": self.is_live,
            "is_mock": self.is_mock,
            "notes": self.notes,
        }


@dataclass
class SelfUpgradePlan:
    plan_id: str
    title: str
    description: str
    source_request: str  # Original request (mobile or desktop)
    client_platform: str
    steps: List[UpgradeStep] = field(default_factory=list)
    rollback_metadata: Optional[RollbackMetadata] = None
    provider_status: Optional[ModelProviderTruth] = None
    memory_refs: List[str] = field(default_factory=list)  # Past failure references
    confirmation_required: bool = False
    confirmed: bool = False
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        title: str,
        description: str,
        source_request: str,
        client_platform: str = "desktop",
    ) -> "SelfUpgradePlan":
        pid = uuid.uuid4().hex
        return cls(
            plan_id=pid,
            title=title,
            description=description,
            source_request=source_request,
            client_platform=client_platform,
        )

    def add_step(
        self,
        title: str,
        description: str = "",
        risk: str = UpgradeRisk.LOW,
        requires_confirmation: bool = False,
        rollback_command: Optional[str] = None,
        validation_command: Optional[str] = None,
        files_to_modify: Optional[List[str]] = None,
    ) -> UpgradeStep:
        step = UpgradeStep(
            step_id=uuid.uuid4().hex,
            plan_id=self.plan_id,
            order=len(self.steps) + 1,
            title=title,
            description=description,
            status=UpgradeStepStatus.PENDING,
            risk=UpgradeRisk(risk),
            requires_confirmation=requires_confirmation,
            rollback_command=rollback_command,
            validation_command=validation_command,
            files_to_modify=files_to_modify or [],
        )
        if requires_confirmation or UpgradeRisk(risk) in (UpgradeRisk.HIGH, UpgradeRisk.DESTRUCTIVE):
            self.confirmation_required = True
        self.steps.append(step)
        self.updated_at = time.time()
        return step

    def create_rollback_metadata(self) -> RollbackMetadata:
        rollback_steps = [s.step_id for s in self.steps if s.status == UpgradeStepStatus.DONE]
        rollback_cmds = [s.rollback_command for s in self.steps if s.rollback_command]
        rb = RollbackMetadata(
            plan_id=self.plan_id,
            rollback_id=uuid.uuid4().hex,
            reason="User-requested or validation-failed rollback",
            steps_to_rollback=rollback_steps,
            rollback_commands=rollback_cmds,
            can_auto_rollback=bool(rollback_cmds),
        )
        self.rollback_metadata = rb
        return rb

    def confirm(self) -> None:
        self.confirmed = True
        self.updated_at = time.time()

    def get_step(self, step_id: str) -> Optional[UpgradeStep]:
        return next((s for s in self.steps if s.step_id == step_id), None)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "description": self.description,
            "source_request": self.source_request,
            "client_platform": self.client_platform,
            "step_count": len(self.steps),
            "confirmation_required": self.confirmation_required,
            "confirmed": self.confirmed,
            "memory_refs": self.memory_refs,
            "has_rollback_metadata": self.rollback_metadata is not None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SelfUpgradePlanStore:
    """In-memory plan store."""

    def __init__(self) -> None:
        self._plans: Dict[str, SelfUpgradePlan] = {}

    def add(self, plan: SelfUpgradePlan) -> str:
        self._plans[plan.plan_id] = plan
        return plan.plan_id

    def get(self, plan_id: str) -> Optional[SelfUpgradePlan]:
        return self._plans.get(plan_id)

    def list_all(self) -> List[SelfUpgradePlan]:
        return sorted(self._plans.values(), key=lambda p: p.created_at, reverse=True)


_store: Optional[SelfUpgradePlanStore] = None


def get_self_upgrade_store() -> SelfUpgradePlanStore:
    global _store
    if _store is None:
        _store = SelfUpgradePlanStore()
    return _store


__all__ = [
    "UpgradeStepStatus",
    "UpgradeRisk",
    "ProviderStatus",
    "UpgradeStep",
    "RollbackMetadata",
    "ModelProviderTruth",
    "SelfUpgradePlan",
    "SelfUpgradePlanStore",
    "get_self_upgrade_store",
]
