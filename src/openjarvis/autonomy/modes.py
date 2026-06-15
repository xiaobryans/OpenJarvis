"""Jarvis Autonomy Mode Policy — project-aware autonomy levels.

Modes (most restricted → most permissive):
  off                   — completely inactive; no observation, no action
  observe_only          — watchdogs observe/report only; no proposals or execution (DEFAULT)
  propose_only          — may draft proposals/recommendations; no auto-execution
  safe_execute_approved — may auto-execute pre-approved, explicitly safe (risk=low) actions
  blocked               — autonomy suspended pending explicit owner decision
  requires_approval     — any action requires explicit approval before execution

Governance rules enforced at this layer:
  - Hard-gated actions (real sends, deploys, mutations) are NEVER auto-allowed at any mode
  - safe_execute_approved only permits risk_level=low, non-hard-gate tool actions
  - Autonomy state is per-project (project_id) and in-process (resets on restart)
  - No mode allows: real Slack/Telegram/email send, deploy, browser mutation, AWS change
  - Mode changes are recorded in the AutonomyPolicy audit log

No fake autonomy:
  - observe_only: watchdogs observe and report only — no execution
  - propose_only: draft proposals only — no execution
  - safe_execute_approved: hard gates still blocked, destructive actions still blocked
  - No mode bypasses governance gate_check()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AutonomyMode(str, Enum):
    """Project-aware autonomy level."""

    OFF = "off"
    OBSERVE_ONLY = "observe_only"
    PROPOSE_ONLY = "propose_only"
    SAFE_EXECUTE_APPROVED = "safe_execute_approved"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"


_DEFAULT_MODE = AutonomyMode.OBSERVE_ONLY

_AUTO_EXECUTE_BLOCKED: frozenset = frozenset({
    "real_slack_send",
    "real_telegram_send",
    "real_email_send",
    "omnix_production_deploy",
    "vercel_deploy",
    "aws_infrastructure_change",
    "supabase_change",
    "stripe_change",
    "billing_change",
    "provider_routing_change",
    "secrets_exposure",
    "open_public_endpoint",
    "tailscale_funnel",
    "destructive_filesystem_op",
    "destructive_git_op",
    "browser_form_submit",
    "browser_purchase",
    "browser_delete",
    "browser_send",
    "browser_account_mutation",
    "production_data_change",
})


@dataclass
class AutonomyModeEntry:
    """A single project's autonomy mode with audit trail."""

    project_id: str
    mode: AutonomyMode
    set_by: str = "system"
    set_at: float = field(default_factory=time.time)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "mode": self.mode.value,
            "set_by": self.set_by,
            "set_at": self.set_at,
            "reason": self.reason,
        }


class AutonomyPolicy:
    """Project-aware autonomy mode manager.

    Stores mode per project_id. Default is observe_only.
    Hard gates from governance constitution are always enforced regardless of mode.

    In-process only — resets on server restart.
    Future sprint: persist to SQLite for restart durability.
    """

    _modes: Dict[str, AutonomyModeEntry] = {}
    _history: List[AutonomyModeEntry] = []

    @classmethod
    def get_mode(cls, project_id: str) -> AutonomyMode:
        """Return the current autonomy mode for a project. Default: observe_only."""
        entry = cls._modes.get(project_id)
        return entry.mode if entry else _DEFAULT_MODE

    @classmethod
    def set_mode(
        cls,
        project_id: str,
        mode: AutonomyMode,
        *,
        set_by: str = "system",
        reason: str = "",
    ) -> AutonomyModeEntry:
        """Set the autonomy mode for a project. Records in audit history."""
        entry = AutonomyModeEntry(
            project_id=project_id,
            mode=mode,
            set_by=set_by,
            reason=reason,
        )
        cls._modes[project_id] = entry
        cls._history.append(entry)
        return entry

    @classmethod
    def can_auto_execute(
        cls,
        project_id: str,
        action_type: str,
        risk_level: str = "low",
    ) -> bool:
        """Return True only if current mode permits auto-execution of this action.

        Governance rules (non-negotiable):
          1. Actions in _AUTO_EXECUTE_BLOCKED are NEVER auto-allowed at any mode
          2. Governance is_hard_gate() is ALWAYS checked — no bypass
          3. OFF, BLOCKED, REQUIRES_APPROVAL, OBSERVE_ONLY, PROPOSE_ONLY → no auto-execute
          4. SAFE_EXECUTE_APPROVED → low-risk non-hard-gate only
        """
        if action_type in _AUTO_EXECUTE_BLOCKED:
            return False

        try:
            from openjarvis.governance.policies import is_hard_gate
            if is_hard_gate(action_type):
                return False
        except ImportError:
            return False

        mode = cls.get_mode(project_id)

        if mode in (
            AutonomyMode.OFF,
            AutonomyMode.BLOCKED,
            AutonomyMode.REQUIRES_APPROVAL,
            AutonomyMode.OBSERVE_ONLY,
            AutonomyMode.PROPOSE_ONLY,
        ):
            return False

        if mode == AutonomyMode.SAFE_EXECUTE_APPROVED:
            return risk_level == "low"

        return False

    @classmethod
    def can_propose(cls, project_id: str) -> bool:
        """Return True if current mode allows drafting proposals."""
        mode = cls.get_mode(project_id)
        return mode in (
            AutonomyMode.PROPOSE_ONLY,
            AutonomyMode.SAFE_EXECUTE_APPROVED,
        )

    @classmethod
    def can_observe(cls, project_id: str) -> bool:
        """Return True if current mode allows watchdog observation/reporting."""
        mode = cls.get_mode(project_id)
        return mode != AutonomyMode.OFF

    @classmethod
    def get_status(cls, project_id: str) -> Dict[str, Any]:
        """Return full autonomy status for a project."""
        mode = cls.get_mode(project_id)
        entry = cls._modes.get(project_id)
        return {
            "project_id": project_id,
            "mode": mode.value,
            "can_observe": cls.can_observe(project_id),
            "can_propose": cls.can_propose(project_id),
            "safe_execute_enabled": mode == AutonomyMode.SAFE_EXECUTE_APPROVED,
            "hard_gates_always_blocked": True,
            "real_send_always_blocked": True,
            "set_by": entry.set_by if entry else "default",
            "set_at": entry.set_at if entry else None,
            "reason": entry.reason if entry else "default safe mode (observe_only)",
        }

    @classmethod
    def list_all_modes(cls) -> List[Dict[str, Any]]:
        """Return autonomy modes for all projects that have an explicitly set mode."""
        return [e.to_dict() for e in cls._modes.values()]

    @classmethod
    def get_history(cls, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return mode change history, optionally filtered by project_id."""
        if project_id:
            return [e.to_dict() for e in cls._history if e.project_id == project_id]
        return [e.to_dict() for e in cls._history]

    @classmethod
    def clear(cls) -> None:
        """Reset — for tests only."""
        cls._modes.clear()
        cls._history.clear()


__all__ = [
    "AutonomyMode",
    "AutonomyModeEntry",
    "AutonomyPolicy",
]
