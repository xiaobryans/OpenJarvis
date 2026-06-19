"""NUS 1D — Approval Workflow Hardening.

Provides structured approval decision objects with:
  - TTL (time-to-live) expiration
  - Scope constraints (what action/category the approval covers)
  - Explicit denial handling
  - Audit log
  - Cannot override blocked categories (secrets/self-modification/deploy)
    unless future NUS 1F production gate explicitly defines it.

Hard safety constraints:
  - Approval cannot override: self_modification, auto_push, auto_merge, deploy,
    secret_access, safety_policy_change, destructive_delete, production_action.
  - Approval scope is constrained to the specific action type + category.
  - Expired approvals are automatically rejected.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1D_APPROVAL_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Approval status constants
# ---------------------------------------------------------------------------

APPROVAL_PENDING = "pending"
APPROVAL_GRANTED = "granted"
APPROVAL_DENIED = "denied"
APPROVAL_EXPIRED = "expired"
APPROVAL_BLOCKED = "blocked"   # blocked category — approval cannot override

# Default TTL: 1 hour
DEFAULT_TTL_SECONDS = 3600

# Categories that approval CANNOT override (permanently blocked)
_NON_OVERRIDABLE_BLOCKED: FrozenSet[str] = frozenset({
    "self_modification",
    "code_edit",
    "auto_push",
    "auto_merge",
    "deploy",
    "secret_access",
    "safety_policy_change",
    "destructive_delete",
    "production_action",
    "payment_action",
    "financial_action",
})


# ---------------------------------------------------------------------------
# ApprovalDecision
# ---------------------------------------------------------------------------


@dataclass
class ApprovalDecision:
    """Structured approval decision with TTL, scope, and audit trail."""

    decision_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + DEFAULT_TTL_SECONDS)
    ttl_seconds: float = DEFAULT_TTL_SECONDS

    # What this approval covers
    scope_action_type: str = ""
    scope_category: str = ""
    scope_description: str = ""

    # Decision
    status: str = APPROVAL_PENDING
    approved_by: Optional[str] = None
    denied_by: Optional[str] = None
    denial_reason: Optional[str] = None
    granted_at: Optional[float] = None
    denied_at: Optional[float] = None

    # Audit trail
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    # Evidence
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "ttl_seconds": self.ttl_seconds,
            "scope_action_type": self.scope_action_type,
            "scope_category": self.scope_category,
            "scope_description": self.scope_description,
            "status": self.status,
            "approved_by": self.approved_by,
            "denied_by": self.denied_by,
            "denial_reason": self.denial_reason,
            "granted_at": self.granted_at,
            "denied_at": self.denied_at,
            "is_valid": self.is_valid,
            "is_expired": self.is_expired,
            "audit_log": self.audit_log[-20:],
            "evidence": self.evidence,
        }

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Return True if approval is granted and not expired."""
        return self.status == APPROVAL_GRANTED and not self.is_expired

    def _add_audit(self, event: str, actor: str, detail: str = "") -> None:
        self.audit_log.append({
            "event": event,
            "actor": actor,
            "detail": detail,
            "timestamp": time.time(),
        })


# ---------------------------------------------------------------------------
# ApprovalWorkflow
# ---------------------------------------------------------------------------


class ApprovalWorkflow:
    """Manages approval decisions with TTL, scope, denial, and audit.

    Safety: approvals cannot override permanently blocked action categories.
    Expired approvals are automatically rejected.
    """

    def __init__(self) -> None:
        self._decisions: Dict[str, ApprovalDecision] = {}

    # ------------------------------------------------------------------ #
    # Create                                                                #
    # ------------------------------------------------------------------ #

    def create(
        self,
        scope_action_type: str,
        scope_category: str = "",
        scope_description: str = "",
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        evidence: Optional[Dict[str, Any]] = None,
    ) -> ApprovalDecision:
        """Create an approval decision request.

        If scope_action_type is in non-overridable blocked list,
        the decision is immediately set to BLOCKED status.
        """
        # Check if this action type is permanently blocked
        if scope_action_type in _NON_OVERRIDABLE_BLOCKED:
            dec = ApprovalDecision(
                scope_action_type=scope_action_type,
                scope_category=scope_category,
                scope_description=scope_description,
                ttl_seconds=ttl_seconds,
                status=APPROVAL_BLOCKED,
                evidence=evidence or {},
            )
            dec.expires_at = time.time() + ttl_seconds
            dec._add_audit(
                "blocked",
                "system",
                f"action_type={scope_action_type} is in permanently blocked list — approval cannot override.",
            )
            self._decisions[dec.decision_id] = dec
            self._log_event(
                "approval_decision_recorded",
                f"Approval BLOCKED (cannot override): {scope_action_type}",
            )
            return dec

        dec = ApprovalDecision(
            scope_action_type=scope_action_type,
            scope_category=scope_category,
            scope_description=scope_description,
            ttl_seconds=ttl_seconds,
            status=APPROVAL_PENDING,
            evidence=evidence or {},
        )
        dec.expires_at = time.time() + ttl_seconds
        dec._add_audit("created", "system", f"Approval request created for {scope_action_type}")
        self._decisions[dec.decision_id] = dec
        return dec

    # ------------------------------------------------------------------ #
    # Grant / Deny                                                          #
    # ------------------------------------------------------------------ #

    def grant(self, decision_id: str, approved_by: str) -> Dict[str, Any]:
        """Grant an approval decision."""
        dec = self._decisions.get(decision_id)
        if not dec:
            return {"ok": False, "reason": "Decision not found."}
        if dec.status == APPROVAL_BLOCKED:
            return {"ok": False, "reason": "Cannot grant approval for permanently blocked action."}
        if dec.is_expired:
            dec.status = APPROVAL_EXPIRED
            dec._add_audit("expired", "system", "Approval expired before grant.")
            self._log_event("approval_expired", f"Approval expired: {decision_id}")
            return {"ok": False, "reason": "Approval has expired.", "status": APPROVAL_EXPIRED}
        if dec.status != APPROVAL_PENDING:
            return {"ok": False, "reason": f"Cannot grant from status={dec.status}"}
        dec.status = APPROVAL_GRANTED
        dec.approved_by = approved_by
        dec.granted_at = time.time()
        dec._add_audit("granted", approved_by, "Approval granted.")
        self._log_event("approval_decision_recorded", f"Approval granted: {decision_id} by {approved_by}")
        return {"ok": True, "decision_id": decision_id, "status": APPROVAL_GRANTED}

    def deny(self, decision_id: str, denied_by: str, reason: str = "") -> Dict[str, Any]:
        """Deny an approval decision."""
        dec = self._decisions.get(decision_id)
        if not dec:
            return {"ok": False, "reason": "Decision not found."}
        dec.status = APPROVAL_DENIED
        dec.denied_by = denied_by
        dec.denial_reason = reason
        dec.denied_at = time.time()
        dec._add_audit("denied", denied_by, f"Approval denied. Reason: {reason}")
        self._log_event("approval_decision_recorded", f"Approval denied: {decision_id} by {denied_by}")
        return {"ok": True, "decision_id": decision_id, "status": APPROVAL_DENIED}

    # ------------------------------------------------------------------ #
    # Validation                                                            #
    # ------------------------------------------------------------------ #

    def validate(self, decision_id: str) -> Dict[str, Any]:
        """Validate that an approval is currently valid (granted + not expired)."""
        dec = self._decisions.get(decision_id)
        if not dec:
            return {"ok": False, "reason": "Decision not found.", "valid": False}
        if dec.status == APPROVAL_BLOCKED:
            return {"ok": False, "reason": "Approval is blocked — action not approvable.", "valid": False}
        if dec.is_expired:
            if dec.status == APPROVAL_GRANTED:
                dec.status = APPROVAL_EXPIRED
                dec._add_audit("expired", "system", "Approval expired on validation check.")
                self._log_event("approval_expired", f"Approval expired: {decision_id}")
            return {"ok": False, "reason": "Approval has expired.", "valid": False, "status": APPROVAL_EXPIRED}
        if dec.status != APPROVAL_GRANTED:
            return {"ok": False, "reason": f"Approval status={dec.status} (not granted).", "valid": False}
        return {
            "ok": True,
            "valid": True,
            "decision_id": decision_id,
            "approved_by": dec.approved_by,
            "scope_action_type": dec.scope_action_type,
            "expires_at": dec.expires_at,
        }

    def check_scope(self, decision_id: str, requested_action_type: str) -> Dict[str, Any]:
        """Verify that an approval covers the requested action type."""
        dec = self._decisions.get(decision_id)
        if not dec:
            return {"ok": False, "reason": "Decision not found."}
        if not dec.is_valid:
            return {"ok": False, "reason": "Approval is not valid (expired, denied, or blocked)."}
        if dec.scope_action_type != requested_action_type:
            return {
                "ok": False,
                "reason": (
                    f"Approval scope mismatch: approval covers '{dec.scope_action_type}' "
                    f"but requested action is '{requested_action_type}'."
                ),
            }
        return {"ok": True, "scope_valid": True, "decision_id": decision_id}

    # ------------------------------------------------------------------ #
    # Queries                                                               #
    # ------------------------------------------------------------------ #

    def get(self, decision_id: str) -> Optional[ApprovalDecision]:
        return self._decisions.get(decision_id)

    def list_all(self) -> List[ApprovalDecision]:
        return list(self._decisions.values())

    def list_pending(self) -> List[ApprovalDecision]:
        return [d for d in self._decisions.values() if d.status == APPROVAL_PENDING and not d.is_expired]

    def get_audit_log(self, decision_id: str) -> List[Dict[str, Any]]:
        dec = self._decisions.get(decision_id)
        return dec.audit_log if dec else []

    def get_status(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for d in self._decisions.values():
            by_status[d.status] = by_status.get(d.status, 0) + 1
        return {
            "version": NUS1D_APPROVAL_VERSION,
            "decision_count": len(self._decisions),
            "by_status": by_status,
            "pending_count": len(self.list_pending()),
            "non_overridable_blocked_categories": sorted(_NON_OVERRIDABLE_BLOCKED),
            "default_ttl_seconds": DEFAULT_TTL_SECONDS,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1d",
                task_id="approval_workflow",
                event_type=event_type,
                title=f"NUS 1D: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1D approval event log skipped: %s", exc)
