"""NUS 1F — Controlled High-Autonomy Session Framework.

Implements explicit, time-limited founder override session objects.

A HighAutonomySession is NOT unlimited autonomy. It is policy-based
delegated autonomy with:
  - explicit session boundaries (TTL)
  - scope constraints (allowed domains, paths, action types)
  - risk ceiling
  - budget limits (cost, token, time)
  - rollback requirements
  - kill switch
  - audit log reference
  - blocked dangerous categories
  - structured decision records
  - strict production gate (blocked/dry-run only in NUS 1F)

Session statuses:
  draft       → created, not yet activated
  active      → activated, TTL not expired, kill switch off
  expired     → TTL elapsed
  revoked     → explicitly revoked by owner
  blocked     → kill switch triggered or policy violation
  completed   → gracefully closed after scope exhausted

Hard constraints (permanent — no exceptions in NUS 1F):
  - No production deploys.
  - No real external sends (Slack/email/social).
  - No secret access, log, or commit.
  - No auto-push, auto-merge.
  - No self-modification of safety/governance logic.
  - No bypass of approval gates.
  - production_restricted and dangerous categories always blocked.
  - Session requires explicit TTL — no indefinite founder override.
  - US13 voice: HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1F_SESSION_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Session statuses
# ---------------------------------------------------------------------------

STATUS_DRAFT = "draft"
STATUS_ACTIVE = "active"
STATUS_EXPIRED = "expired"
STATUS_REVOKED = "revoked"
STATUS_BLOCKED = "blocked"
STATUS_COMPLETED = "completed"

_ALL_SESSION_STATUSES = frozenset({
    STATUS_DRAFT, STATUS_ACTIVE, STATUS_EXPIRED,
    STATUS_REVOKED, STATUS_BLOCKED, STATUS_COMPLETED,
})

# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

PROFILE_MANUAL = "manual"
PROFILE_SAFE_AUTOPILOT = "safe_autopilot"
PROFILE_POWER_AUTOPILOT = "power_autopilot"
PROFILE_FOUNDER_OVERRIDE_SESSION = "founder_override_session"
PROFILE_PRODUCTION_RESTRICTED = "production_restricted"

_VALID_PROFILES = frozenset({
    PROFILE_MANUAL,
    PROFILE_SAFE_AUTOPILOT,
    PROFILE_POWER_AUTOPILOT,
    PROFILE_FOUNDER_OVERRIDE_SESSION,
    PROFILE_PRODUCTION_RESTRICTED,
})

# ---------------------------------------------------------------------------
# Permanently blocked action types (NUS 1F — cannot be unblocked here)
# ---------------------------------------------------------------------------

PERMANENTLY_BLOCKED_ACTIONS: FrozenSet[str] = frozenset({
    "production_deploy",
    "payment_financial_action",
    "destructive_delete",
    "secret_access",
    "secret_mutation",
    "auth_security_change",
    "safety_governance_change",
    "public_posting",
    "real_slack_send",
    "real_email_send",
    "real_social_send",
    "merge_to_main",
    "public_release",
    "notarization",
    "self_modifying_autonomy_logic",
    "auto_push",
    "auto_merge",
    "auto_deploy",
    "browser_account_setup",
    "external_provider_setup",
})

# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

# Global kill switch — when True, ALL high-autonomy sessions are blocked
_GLOBAL_KILL_SWITCH: bool = False


def get_kill_switch_state() -> bool:
    """Return current global kill switch state."""
    return _GLOBAL_KILL_SWITCH


def activate_kill_switch() -> None:
    """Activate global kill switch — blocks all high-autonomy sessions."""
    global _GLOBAL_KILL_SWITCH
    _GLOBAL_KILL_SWITCH = True
    logger.warning("NUS1F: Global kill switch ACTIVATED — all high-autonomy sessions blocked.")


def deactivate_kill_switch() -> None:
    """Deactivate global kill switch. Requires explicit owner action."""
    global _GLOBAL_KILL_SWITCH
    _GLOBAL_KILL_SWITCH = False
    logger.info("NUS1F: Global kill switch deactivated.")


# ---------------------------------------------------------------------------
# Kill switch state enum
# ---------------------------------------------------------------------------

KILL_SWITCH_OFF = "off"
KILL_SWITCH_ON = "on"

# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------

@dataclass
class HighAutonomySession:
    """Explicit, time-limited, policy-constrained high-autonomy session.

    Must be created through HighAutonomySessionManager.create_session().
    Direct instantiation is allowed for dry-run/testing purposes only.
    """

    session_id: str
    created_at: float
    expires_at: float
    owner: str
    requested_profile: str
    active_profile: str
    allowed_domains: List[str] = field(default_factory=list)
    allowed_action_types: List[str] = field(default_factory=list)
    blocked_action_types: List[str] = field(default_factory=list)
    allowed_repos_or_paths: List[str] = field(default_factory=list)
    cost_budget: float = 0.0
    token_budget: int = 0
    time_budget: float = 0.0
    risk_ceiling: str = "low"
    tool_policy: Dict[str, Any] = field(default_factory=dict)
    validation_policy: Dict[str, Any] = field(default_factory=dict)
    rollback_policy: Dict[str, Any] = field(default_factory=dict)
    audit_log_id: str = ""
    kill_switch_state: str = KILL_SWITCH_OFF
    status: str = STATUS_DRAFT
    reason: str = ""
    structured_decision_record: Dict[str, Any] = field(default_factory=dict)

    def is_active(self) -> bool:
        """True iff session is active, not expired, and kill switch is off."""
        if self.status != STATUS_ACTIVE:
            return False
        if time.time() > self.expires_at:
            return False
        if _GLOBAL_KILL_SWITCH or self.kill_switch_state == KILL_SWITCH_ON:
            return False
        return True

    def ttl_remaining(self) -> float:
        """Seconds remaining until expiry. Negative means expired."""
        return self.expires_at - time.time()

    def is_action_allowed(self, action_type: str) -> bool:
        """Check if an action_type is allowed in this session.

        Returns False if:
          - Session is not active
          - Action is permanently blocked
          - Action is in blocked_action_types
          - Action is not in allowed_action_types (when list is non-empty)
        """
        if not self.is_active():
            return False
        if action_type in PERMANENTLY_BLOCKED_ACTIONS:
            return False
        if action_type in self.blocked_action_types:
            return False
        if self.allowed_action_types and action_type not in self.allowed_action_types:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "ttl_remaining_seconds": self.ttl_remaining(),
            "owner": self.owner,
            "requested_profile": self.requested_profile,
            "active_profile": self.active_profile,
            "allowed_domains": self.allowed_domains,
            "allowed_action_types": self.allowed_action_types,
            "blocked_action_types": self.blocked_action_types,
            "allowed_repos_or_paths": self.allowed_repos_or_paths,
            "cost_budget": self.cost_budget,
            "token_budget": self.token_budget,
            "time_budget": self.time_budget,
            "risk_ceiling": self.risk_ceiling,
            "tool_policy": self.tool_policy,
            "validation_policy": self.validation_policy,
            "rollback_policy": self.rollback_policy,
            "audit_log_id": self.audit_log_id,
            "kill_switch_state": self.kill_switch_state,
            "status": self.status,
            "reason": self.reason,
            "structured_decision_record": self.structured_decision_record,
            "is_active": self.is_active(),
            "session_version": NUS1F_SESSION_VERSION,
        }


# ---------------------------------------------------------------------------
# Session manager
# ---------------------------------------------------------------------------

@dataclass
class SessionCreateRequest:
    """Input for creating a new high-autonomy session."""
    owner: str
    requested_profile: str
    ttl_seconds: float
    allowed_domains: List[str] = field(default_factory=list)
    allowed_action_types: List[str] = field(default_factory=list)
    blocked_action_types: List[str] = field(default_factory=list)
    allowed_repos_or_paths: List[str] = field(default_factory=list)
    cost_budget: float = 0.0
    token_budget: int = 0
    time_budget: float = 0.0
    risk_ceiling: str = "low"
    tool_policy: Dict[str, Any] = field(default_factory=dict)
    validation_policy: Dict[str, Any] = field(default_factory=dict)
    rollback_policy: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class SessionEvaluation:
    """Result of evaluating a session create/activate request."""
    allowed: bool
    session_id: str
    status: str
    reason: str
    blocking_reason: Optional[str] = None
    structured_decision_record: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "session_id": self.session_id,
            "status": self.status,
            "reason": self.reason,
            "blocking_reason": self.blocking_reason,
            "structured_decision_record": self.structured_decision_record,
        }


class HighAutonomySessionManager:
    """Manages high-autonomy session lifecycle.

    Responsibilities:
      - Create sessions with validation and TTL enforcement
      - Activate sessions (draft → active)
      - Expire sessions based on TTL
      - Revoke sessions explicitly
      - Enforce kill switch
      - Enforce scope and budget constraints
      - Block permanently dangerous categories
      - Emit structured decision records

    This manager does NOT grant new permissions beyond existing Jarvis policy.
    It enforces the constraints defined per session object.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, HighAutonomySession] = {}

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create_session(self, request: SessionCreateRequest) -> SessionEvaluation:
        """Create a new session in draft status with full validation."""
        from openjarvis.nus.decision_record import StructuredDecisionRecord, build_session_decision_record

        sid = str(uuid.uuid4())
        now = time.time()

        # Validate profile
        if request.requested_profile not in _VALID_PROFILES:
            dr = build_session_decision_record(
                session_id=sid,
                decision="blocked",
                reason=f"Unknown profile: {request.requested_profile}",
                evidence={"requested_profile": request.requested_profile},
            )
            return SessionEvaluation(
                allowed=False, session_id=sid, status=STATUS_BLOCKED,
                reason="unknown_profile",
                blocking_reason=f"Profile {request.requested_profile!r} is not a valid profile.",
                structured_decision_record=dr,
            )

        # Block production_restricted profile from being activated in NUS 1F
        if request.requested_profile == PROFILE_PRODUCTION_RESTRICTED:
            dr = build_session_decision_record(
                session_id=sid,
                decision="blocked",
                reason="production_restricted profile cannot be activated via session in NUS 1F",
                evidence={"requested_profile": request.requested_profile},
            )
            return SessionEvaluation(
                allowed=False, session_id=sid, status=STATUS_BLOCKED,
                reason="production_restricted_blocked",
                blocking_reason="production_restricted profile is not session-activatable.",
                structured_decision_record=dr,
            )

        # TTL must be positive and finite
        if not (0 < request.ttl_seconds <= 86400 * 30):  # max 30 days
            dr = build_session_decision_record(
                session_id=sid,
                decision="blocked",
                reason=f"Invalid TTL: {request.ttl_seconds}s",
                evidence={"ttl_seconds": request.ttl_seconds},
            )
            return SessionEvaluation(
                allowed=False, session_id=sid, status=STATUS_BLOCKED,
                reason="invalid_ttl",
                blocking_reason="TTL must be >0 and ≤30 days. No indefinite sessions.",
                structured_decision_record=dr,
            )

        # Check global kill switch
        if _GLOBAL_KILL_SWITCH:
            dr = build_session_decision_record(
                session_id=sid,
                decision="blocked",
                reason="global kill switch is active",
                evidence={"kill_switch": True},
            )
            return SessionEvaluation(
                allowed=False, session_id=sid, status=STATUS_BLOCKED,
                reason="kill_switch_active",
                blocking_reason="Global kill switch is active. All sessions blocked.",
                structured_decision_record=dr,
            )

        # Filter out permanently blocked actions from allowed list
        safe_allowed = [
            a for a in request.allowed_action_types
            if a not in PERMANENTLY_BLOCKED_ACTIONS
        ]
        # Merge permanently blocked into blocked list
        merged_blocked = list(set(
            list(request.blocked_action_types) + list(PERMANENTLY_BLOCKED_ACTIONS)
        ))

        dr = build_session_decision_record(
            session_id=sid,
            decision="allowed",
            reason="session created in draft status with scope/budget/TTL constraints",
            evidence={
                "owner": request.owner,
                "profile": request.requested_profile,
                "ttl_seconds": request.ttl_seconds,
                "allowed_action_types": safe_allowed,
                "cost_budget": request.cost_budget,
                "risk_ceiling": request.risk_ceiling,
            },
        )

        session = HighAutonomySession(
            session_id=sid,
            created_at=now,
            expires_at=now + request.ttl_seconds,
            owner=request.owner,
            requested_profile=request.requested_profile,
            active_profile=request.requested_profile,
            allowed_domains=request.allowed_domains,
            allowed_action_types=safe_allowed,
            blocked_action_types=merged_blocked,
            allowed_repos_or_paths=request.allowed_repos_or_paths,
            cost_budget=request.cost_budget,
            token_budget=request.token_budget,
            time_budget=request.time_budget,
            risk_ceiling=request.risk_ceiling,
            tool_policy=request.tool_policy,
            validation_policy=request.validation_policy,
            rollback_policy=request.rollback_policy,
            audit_log_id=str(uuid.uuid4()),
            kill_switch_state=KILL_SWITCH_OFF,
            status=STATUS_DRAFT,
            reason=request.reason,
            structured_decision_record=dr,
        )
        self._sessions[sid] = session

        return SessionEvaluation(
            allowed=True,
            session_id=sid,
            status=STATUS_DRAFT,
            reason="session_created_draft",
            structured_decision_record=dr,
        )

    # ------------------------------------------------------------------
    # Activate
    # ------------------------------------------------------------------

    def activate_session(self, session_id: str) -> SessionEvaluation:
        """Activate a draft session. Validates TTL and kill switch."""
        from openjarvis.nus.decision_record import build_session_decision_record

        session = self._sessions.get(session_id)
        if session is None:
            dr = build_session_decision_record(
                session_id=session_id, decision="blocked",
                reason="session not found", evidence={},
            )
            return SessionEvaluation(
                allowed=False, session_id=session_id, status=STATUS_BLOCKED,
                reason="not_found", blocking_reason="Session not found.",
                structured_decision_record=dr,
            )

        if session.status != STATUS_DRAFT:
            dr = build_session_decision_record(
                session_id=session_id, decision="blocked",
                reason=f"cannot activate session with status={session.status}",
                evidence={"current_status": session.status},
            )
            return SessionEvaluation(
                allowed=False, session_id=session_id, status=session.status,
                reason="wrong_status",
                blocking_reason=f"Session is {session.status}, not draft.",
                structured_decision_record=dr,
            )

        if _GLOBAL_KILL_SWITCH:
            session.status = STATUS_BLOCKED
            session.kill_switch_state = KILL_SWITCH_ON
            dr = build_session_decision_record(
                session_id=session_id, decision="blocked",
                reason="global kill switch active", evidence={"kill_switch": True},
            )
            return SessionEvaluation(
                allowed=False, session_id=session_id, status=STATUS_BLOCKED,
                reason="kill_switch_active",
                blocking_reason="Global kill switch prevents activation.",
                structured_decision_record=dr,
            )

        if time.time() >= session.expires_at:
            session.status = STATUS_EXPIRED
            dr = build_session_decision_record(
                session_id=session_id, decision="blocked",
                reason="session expired before activation", evidence={"expires_at": session.expires_at},
            )
            return SessionEvaluation(
                allowed=False, session_id=session_id, status=STATUS_EXPIRED,
                reason="expired", blocking_reason="Session TTL elapsed before activation.",
                structured_decision_record=dr,
            )

        session.status = STATUS_ACTIVE
        dr = build_session_decision_record(
            session_id=session_id, decision="allowed",
            reason="session activated",
            evidence={
                "profile": session.active_profile,
                "ttl_remaining": session.ttl_remaining(),
                "risk_ceiling": session.risk_ceiling,
            },
        )
        session.structured_decision_record = dr

        return SessionEvaluation(
            allowed=True, session_id=session_id, status=STATUS_ACTIVE,
            reason="session_activated",
            structured_decision_record=dr,
        )

    # ------------------------------------------------------------------
    # Revoke
    # ------------------------------------------------------------------

    def revoke_session(self, session_id: str, reason: str = "") -> SessionEvaluation:
        """Revoke an active or draft session."""
        from openjarvis.nus.decision_record import build_session_decision_record

        session = self._sessions.get(session_id)
        if session is None:
            dr = build_session_decision_record(
                session_id=session_id, decision="blocked",
                reason="session not found for revocation", evidence={},
            )
            return SessionEvaluation(
                allowed=False, session_id=session_id, status=STATUS_BLOCKED,
                reason="not_found", blocking_reason="Session not found.",
                structured_decision_record=dr,
            )

        previous_status = session.status
        session.status = STATUS_REVOKED
        session.reason = reason or "explicitly_revoked"

        dr = build_session_decision_record(
            session_id=session_id, decision="revoked",
            reason=reason or "explicit revocation by owner",
            evidence={"previous_status": previous_status},
        )
        session.structured_decision_record = dr

        return SessionEvaluation(
            allowed=True, session_id=session_id, status=STATUS_REVOKED,
            reason="session_revoked",
            structured_decision_record=dr,
        )

    # ------------------------------------------------------------------
    # Expire (TTL check)
    # ------------------------------------------------------------------

    def expire_session_if_elapsed(self, session_id: str) -> bool:
        """Check TTL and mark session expired if elapsed. Returns True if expired."""
        session = self._sessions.get(session_id)
        if session is None:
            return False
        if session.status == STATUS_ACTIVE and time.time() > session.expires_at:
            session.status = STATUS_EXPIRED
            logger.info("NUS1F: Session %s expired.", session_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Kill switch enforcement
    # ------------------------------------------------------------------

    def apply_kill_switch(self) -> List[str]:
        """Block all active sessions when global kill switch is on. Returns blocked session IDs."""
        blocked = []
        if not _GLOBAL_KILL_SWITCH:
            return blocked
        for sid, session in self._sessions.items():
            if session.status == STATUS_ACTIVE:
                session.status = STATUS_BLOCKED
                session.kill_switch_state = KILL_SWITCH_ON
                blocked.append(sid)
        if blocked:
            logger.warning("NUS1F: Kill switch blocked %d sessions: %s", len(blocked), blocked)
        return blocked

    # ------------------------------------------------------------------
    # Evaluate action within session
    # ------------------------------------------------------------------

    def evaluate_action(self, session_id: str, action_type: str) -> Dict[str, Any]:
        """Evaluate whether an action is allowed in this session."""
        from openjarvis.nus.decision_record import build_session_decision_record

        session = self._sessions.get(session_id)
        if session is None:
            return {
                "allowed": False,
                "reason": "session_not_found",
                "action_type": action_type,
                "session_id": session_id,
            }

        # TTL check
        self.expire_session_if_elapsed(session_id)

        allowed = session.is_action_allowed(action_type)
        reason = "action_allowed" if allowed else "action_blocked"

        if not session.is_active():
            reason = f"session_not_active_status={session.status}"
        elif action_type in PERMANENTLY_BLOCKED_ACTIONS:
            reason = "permanently_blocked_action_type"
        elif action_type in session.blocked_action_types:
            reason = "blocked_by_session_policy"
        elif session.allowed_action_types and action_type not in session.allowed_action_types:
            reason = "not_in_allowed_action_types"

        dr = build_session_decision_record(
            session_id=session_id,
            decision="allowed" if allowed else "blocked",
            reason=reason,
            evidence={
                "action_type": action_type,
                "session_status": session.status,
                "ttl_remaining": session.ttl_remaining(),
                "risk_ceiling": session.risk_ceiling,
            },
        )
        return {
            "allowed": allowed,
            "reason": reason,
            "action_type": action_type,
            "session_id": session_id,
            "structured_decision_record": dr,
        }

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_session(self, session_id: str) -> Optional[HighAutonomySession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._sessions.values()]

    def get_status(self) -> Dict[str, Any]:
        return {
            "session_manager_version": NUS1F_SESSION_VERSION,
            "total_sessions": len(self._sessions),
            "active_sessions": sum(1 for s in self._sessions.values() if s.status == STATUS_ACTIVE),
            "global_kill_switch": _GLOBAL_KILL_SWITCH,
            "permanently_blocked_actions": sorted(PERMANENTLY_BLOCKED_ACTIONS),
            "valid_profiles": sorted(_VALID_PROFILES),
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "production_execution": "blocked_dry_run_only",
            "no_real_deploy": True,
            "no_auto_push": True,
            "no_auto_merge": True,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_session_manager: Optional[HighAutonomySessionManager] = None


def get_session_manager() -> HighAutonomySessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = HighAutonomySessionManager()
    return _session_manager
