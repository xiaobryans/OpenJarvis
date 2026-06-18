"""US15 bounded repair loop — validation failure → bounded retry/escalation → stop-on-blocker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.workbench.model_router import EscalationAction, ModelRouter


@dataclass
class RepairAttempt:
    attempt: int
    action: str
    reason: str
    subtask_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt": self.attempt,
            "action": self.action,
            "reason": self.reason,
            "subtask_id": self.subtask_id,
        }


@dataclass
class RepairLoopState:
    max_attempts: int = 3
    attempts: List[RepairAttempt] = field(default_factory=list)
    stopped: bool = False
    stop_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_attempts": self.max_attempts,
            "attempts": [a.to_dict() for a in self.attempts],
            "stopped": self.stopped,
            "stop_reason": self.stop_reason,
            "attempt_count": len(self.attempts),
        }


class BoundedRepairLoop:
    """Bounded repair loop with stop-on-blocker semantics."""

    def __init__(self, max_attempts: int = 3) -> None:
        self.max_attempts = max(1, max_attempts)
        self.state = RepairLoopState(max_attempts=self.max_attempts)

    def can_retry(self) -> bool:
        return not self.state.stopped and len(self.state.attempts) < self.max_attempts

    def record_stop(self, reason: str) -> RepairLoopState:
        self.state.stopped = True
        self.state.stop_reason = reason
        return self.state

    def decide(
        self,
        *,
        router: ModelRouter,
        subtask_id: str,
        tool_id: str,
        session_id: str,
        task_id: str,
        validation_failed: bool,
        terminal_error: bool,
        error_message: str = "",
    ) -> Dict[str, Any]:
        """Decide next repair action using ModelRouter escalation policy."""
        if not self.can_retry():
            self.record_stop("max_attempts_exceeded")
            return {
                "action": EscalationAction.HOLD.value,
                "retry": False,
                "state": self.state.to_dict(),
                "reason": self.state.stop_reason or "max_attempts_exceeded",
            }

        err = error_message or ("validation_failed" if validation_failed else "terminal_error")
        routing = router.route(
            subtask_id=subtask_id,
            tool_id=tool_id,
            description=err,
            session_id=session_id,
            task_id=task_id,
        )
        decision = router.decide_escalation(
            routing,
            error=err,
            attempt=len(self.state.attempts) + 1,
        )
        action = decision.action.value if hasattr(decision.action, "value") else str(decision.action)
        self.state.attempts.append(
            RepairAttempt(
                attempt=len(self.state.attempts) + 1,
                action=action,
                reason=decision.reason,
                subtask_id=subtask_id,
            )
        )
        if action == EscalationAction.HOLD.value:
            self.record_stop(decision.reason)

        return {
            "action": action,
            "retry": action in (EscalationAction.RETRY_SAME.value, EscalationAction.ESCALATE.value),
            "state": self.state.to_dict(),
            "reason": decision.reason,
            "tier": getattr(decision, "new_tier", None),
        }


__all__ = ["BoundedRepairLoop", "RepairAttempt", "RepairLoopState"]
