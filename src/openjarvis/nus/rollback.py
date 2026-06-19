"""NUS 1D — Rollback Plan Enforcement.

Defines structured rollback plan objects and enforces their presence
before any mutation-class action can proceed.

Rules:
  - Rollback required for: file_write, code_edit, auto_commit, config_change,
    schema_migration, package_install, dependency_update.
  - Rollback proof required before low-risk auto-commit is considered.
  - No destructive rollback execution unless explicitly approved (approval object required).
  - Tests must use temp dirs only.

Hard safety constraints:
  - No real execution of rollback unless user explicitly approves it.
  - No self-modification, no deploy, no auto-push.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1D_ROLLBACK_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Mutation action categories requiring rollback
# ---------------------------------------------------------------------------

_MUTATION_ACTIONS: FrozenSet[str] = frozenset({
    "file_write",
    "code_edit",
    "auto_commit",
    "config_change",
    "schema_migration",
    "package_install",
    "dependency_update",
})

# Destructive rollback requires explicit approval (never auto-executed)
_DESTRUCTIVE_ROLLBACK_TYPES: FrozenSet[str] = frozenset({
    "revert_commit",
    "delete_file",
    "restore_from_backup",
    "schema_revert",
})


# ---------------------------------------------------------------------------
# RollbackPlan
# ---------------------------------------------------------------------------


@dataclass
class RollbackPlan:
    """Structured rollback plan for a mutation action.

    Must be created before any mutation proceeds.
    Destructive rollbacks require explicit approval before execution.
    """

    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)
    action_type: str = ""
    rollback_type: str = "revert"       # e.g. revert, restore, undo, dry_run
    description: str = ""
    steps: List[str] = field(default_factory=list)
    affected_paths: List[str] = field(default_factory=list)
    reversible: bool = True
    requires_approval_to_execute: bool = True
    is_destructive: bool = False
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "created_at": self.created_at,
            "action_type": self.action_type,
            "rollback_type": self.rollback_type,
            "description": self.description,
            "steps": self.steps,
            "affected_paths": self.affected_paths[:10],
            "reversible": self.reversible,
            "requires_approval_to_execute": self.requires_approval_to_execute,
            "is_destructive": self.is_destructive,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RollbackPlan":
        return cls(
            plan_id=d.get("plan_id", uuid.uuid4().hex[:12]),
            created_at=d.get("created_at", time.time()),
            action_type=d.get("action_type", ""),
            rollback_type=d.get("rollback_type", "revert"),
            description=d.get("description", ""),
            steps=d.get("steps", []),
            affected_paths=d.get("affected_paths", []),
            reversible=d.get("reversible", True),
            requires_approval_to_execute=d.get("requires_approval_to_execute", True),
            is_destructive=d.get("is_destructive", False),
            approved_by=d.get("approved_by"),
            approved_at=d.get("approved_at"),
            evidence=d.get("evidence", {}),
        )

    @property
    def is_approved(self) -> bool:
        return self.approved_by is not None and self.approved_at is not None

    def approve_execution(self, approved_by: str) -> None:
        """Explicitly approve rollback execution. Required before any destructive rollback."""
        if self.is_destructive and not approved_by:
            raise ValueError("Destructive rollbacks require an explicit approver.")
        self.approved_by = approved_by
        self.approved_at = time.time()
        self._log_event("rollback_plan_created", f"Rollback plan approved by {approved_by}")

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1d",
                task_id="rollback",
                event_type=event_type,
                title=f"NUS 1D: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1D rollback event log skipped: %s", exc)


# ---------------------------------------------------------------------------
# RollbackEnforcer
# ---------------------------------------------------------------------------


class RollbackEnforcer:
    """Enforces rollback plan presence before any mutation action proceeds.

    Safety: never executes rollback without explicit approval.
    """

    def __init__(self) -> None:
        self._plans: Dict[str, RollbackPlan] = {}

    def requires_rollback(self, action_type: str) -> bool:
        """Return True if the action type requires a rollback plan."""
        return action_type in _MUTATION_ACTIONS

    def create_plan(
        self,
        action_type: str,
        description: str,
        steps: Optional[List[str]] = None,
        affected_paths: Optional[List[str]] = None,
        rollback_type: str = "revert",
        reversible: bool = True,
        is_destructive: bool = False,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> RollbackPlan:
        """Create and register a rollback plan."""
        plan = RollbackPlan(
            action_type=action_type,
            rollback_type=rollback_type,
            description=description,
            steps=steps or [],
            affected_paths=affected_paths or [],
            reversible=reversible,
            requires_approval_to_execute=True,
            is_destructive=is_destructive or rollback_type in _DESTRUCTIVE_ROLLBACK_TYPES,
            evidence=evidence or {},
        )
        self._plans[plan.plan_id] = plan
        self._log_event("rollback_plan_created", f"Plan created: {plan.plan_id} action={action_type}")
        return plan

    def check_precondition(self, action_type: str, rollback_plan: Optional[RollbackPlan]) -> Dict[str, Any]:
        """Check that rollback preconditions are met before a mutation action.

        Returns dict with ok=True/False and reason.
        Fails closed if rollback is required but plan is missing.
        """
        if not self.requires_rollback(action_type):
            return {"ok": True, "reason": f"action_type={action_type} does not require rollback."}

        if rollback_plan is None:
            return {
                "ok": False,
                "reason": (
                    f"action_type={action_type} requires rollback plan — none provided. "
                    "Fail closed: mutation cannot proceed without rollback plan."
                ),
                "fail_closed": True,
            }

        if not rollback_plan.description:
            return {
                "ok": False,
                "reason": "Rollback plan description is empty — fail closed.",
                "fail_closed": True,
            }

        return {
            "ok": True,
            "plan_id": rollback_plan.plan_id,
            "action_type": action_type,
            "rollback_type": rollback_plan.rollback_type,
            "reversible": rollback_plan.reversible,
        }

    def execute_dry_run(self, plan_id: str) -> Dict[str, Any]:
        """Simulate rollback dry-run (never actually executes). Returns dry-run result."""
        plan = self._plans.get(plan_id)
        if not plan:
            return {"ok": False, "reason": "Rollback plan not found."}
        return {
            "ok": True,
            "dry_run": True,
            "plan_id": plan_id,
            "action_type": plan.action_type,
            "rollback_type": plan.rollback_type,
            "description": plan.description,
            "steps": plan.steps,
            "note": "NUS 1D: dry-run only — no actual rollback executed.",
        }

    def execute_rollback(self, plan_id: str) -> Dict[str, Any]:
        """Block real rollback execution — requires explicit approval + NUS 1F gate.

        This method always returns blocked in NUS 1D.
        Real execution requires NUS 1F production gate + explicit approval.
        """
        plan = self._plans.get(plan_id)
        if plan and plan.is_destructive and not plan.is_approved:
            return {
                "ok": False,
                "reason": "Destructive rollback requires explicit approval before execution.",
                "blocked": True,
            }
        return {
            "ok": False,
            "reason": "Real rollback execution is blocked in NUS 1D. Requires NUS 1F production gate.",
            "blocked": True,
            "dry_run_available": True,
        }

    def get_plan(self, plan_id: str) -> Optional[RollbackPlan]:
        return self._plans.get(plan_id)

    def list_plans(self) -> List[RollbackPlan]:
        return list(self._plans.values())

    def get_status(self) -> Dict[str, Any]:
        return {
            "version": NUS1D_ROLLBACK_VERSION,
            "plan_count": len(self._plans),
            "mutation_actions_requiring_rollback": sorted(_MUTATION_ACTIONS),
            "destructive_rollback_types": sorted(_DESTRUCTIVE_ROLLBACK_TYPES),
            "real_execution_blocked": True,
            "dry_run_available": True,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1d",
                task_id="rollback",
                event_type=event_type,
                title=f"NUS 1D: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1D rollback event log skipped: %s", exc)
