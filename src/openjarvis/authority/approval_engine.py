"""Plan 8 — Approval Engine.

Implements the full approval mode system for trusted delegation:
  - AUTO_ALLOW: safe/low-risk (Tier 0-1) only
  - ONE_TIME: single-use approval
  - PER_SESSION: valid for current session duration
  - SCOPED: valid for specific resource/action scope
  - STEP_UP: sensitive/high-risk, re-verification required
  - DENY: blocked
  - REVOKED: previously approved, now revoked
  - EMERGENCY_STOP: global block active

Approval records are stored in SQLite (same DB as ApprovalStore, extended table).
No secret values are stored in approval records.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.authority.tiers import AuthorityTier


# ---------------------------------------------------------------------------
# Approval mode enumeration
# ---------------------------------------------------------------------------


class ApprovalMode(str, Enum):
    AUTO_ALLOW = "auto_allow"       # Tier 0-1 safe actions, no prompt needed
    ONE_TIME = "one_time"           # Single-use approval for this exact action
    PER_SESSION = "per_session"     # Valid until session ends or expiry
    SCOPED = "scoped"               # Valid for a defined scope (resource + action type)
    STEP_UP = "step_up"             # Sensitive/high-risk: requires re-verification
    DENY = "deny"                   # Explicitly denied
    REVOKED = "revoked"             # Was approved, now revoked by owner
    EMERGENCY_STOP = "emergency_stop"  # Global emergency stop is active


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"
    USED = "used"           # ONE_TIME after execution
    BLOCKED = "blocked"     # Emergency stop active


# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------

_DEFAULT_DB = Path.home() / ".jarvis" / "authority_approvals.db"


# ---------------------------------------------------------------------------
# ApprovalRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRecord:
    """A single approval decision record.

    No secret values are stored here. Only names/scopes/IDs are stored.
    """

    approval_id: str
    requester: str                          # agent_id or user identifier
    action_type: str
    action_preview: str                     # human-readable description
    risk_level: str                         # low | medium | high | critical
    tier: int                               # AuthorityTier value
    affected_systems: List[str]
    affected_files: List[str]
    affected_accounts: List[str]
    estimated_spend: float                  # 0.0 if none
    rollback_plan: str                      # text description
    scope: str                              # "" = global, else scope key
    mode: ApprovalMode
    status: ApprovalStatus
    audit_trace_id: str
    created_at: str
    granted_at: Optional[str]
    expires_at: Optional[str]               # ISO8601 or None
    context: Dict[str, Any]                 # scrubbed context, no secrets
    error_reason: str = ""
    revocation_reason: str = ""

    def is_active(self) -> bool:
        """Return True if this approval is currently usable."""
        if self.status != ApprovalStatus.GRANTED:
            return False
        if self.expires_at:
            expiry = datetime.fromisoformat(self.expires_at)
            if datetime.now(timezone.utc) > expiry:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "requester": self.requester,
            "action_type": self.action_type,
            "action_preview": self.action_preview,
            "risk_level": self.risk_level,
            "tier": self.tier,
            "affected_systems": self.affected_systems,
            "affected_files": self.affected_files,
            "affected_accounts": self.affected_accounts,
            "estimated_spend": self.estimated_spend,
            "rollback_plan": self.rollback_plan,
            "scope": self.scope,
            "mode": self.mode.value,
            "status": self.status.value,
            "audit_trace_id": self.audit_trace_id,
            "created_at": self.created_at,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "context": self.context,
            "error_reason": self.error_reason,
            "revocation_reason": self.revocation_reason,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "ApprovalRecord":
        (
            approval_id, requester, action_type, action_preview,
            risk_level, tier, affected_systems_json, affected_files_json,
            affected_accounts_json, estimated_spend, rollback_plan, scope,
            mode, status, audit_trace_id, created_at, granted_at, expires_at,
            context_json, error_reason, revocation_reason,
        ) = row
        return cls(
            approval_id=approval_id,
            requester=requester,
            action_type=action_type,
            action_preview=action_preview,
            risk_level=risk_level,
            tier=int(tier),
            affected_systems=json.loads(affected_systems_json or "[]"),
            affected_files=json.loads(affected_files_json or "[]"),
            affected_accounts=json.loads(affected_accounts_json or "[]"),
            estimated_spend=float(estimated_spend or 0.0),
            rollback_plan=rollback_plan or "",
            scope=scope or "",
            mode=ApprovalMode(mode),
            status=ApprovalStatus(status),
            audit_trace_id=audit_trace_id or "",
            created_at=created_at or "",
            granted_at=granted_at,
            expires_at=expires_at,
            context=json.loads(context_json or "{}"),
            error_reason=error_reason or "",
            revocation_reason=revocation_reason or "",
        )


# ---------------------------------------------------------------------------
# ApprovalEngine
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset({
    "token", "secret", "password", "api_key", "auth", "credential",
    "private_key", "access_key", "bot_token", "chat_id", "key",
})


def _scrub_context(ctx: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
    if depth > 4:
        return {}
    return {
        k: "<redacted>" if any(s in k.lower() for s in _SENSITIVE_KEYS)
        else (_scrub_context(v, depth + 1) if isinstance(v, dict) else v)
        for k, v in ctx.items()
    }


class ApprovalEngine:
    """SQLite-backed approval engine for Plan 8 trusted delegation.

    Manages approval records for all authority tiers. Auto-allows Tier 0/1.
    Requires explicit approval for Tier 2+. Supports revocation and emergency stop.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS authority_approvals (
            approval_id         TEXT PRIMARY KEY,
            requester           TEXT NOT NULL,
            action_type         TEXT NOT NULL,
            action_preview      TEXT NOT NULL DEFAULT '',
            risk_level          TEXT NOT NULL DEFAULT 'low',
            tier                INTEGER NOT NULL DEFAULT 0,
            affected_systems    TEXT NOT NULL DEFAULT '[]',
            affected_files      TEXT NOT NULL DEFAULT '[]',
            affected_accounts   TEXT NOT NULL DEFAULT '[]',
            estimated_spend     REAL NOT NULL DEFAULT 0.0,
            rollback_plan       TEXT NOT NULL DEFAULT '',
            scope               TEXT NOT NULL DEFAULT '',
            mode                TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'pending',
            audit_trace_id      TEXT NOT NULL DEFAULT '',
            created_at          TEXT NOT NULL,
            granted_at          TEXT,
            expires_at          TEXT,
            context_json        TEXT NOT NULL DEFAULT '{}',
            error_reason        TEXT NOT NULL DEFAULT '',
            revocation_reason   TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_approvals_status
            ON authority_approvals (status);
        CREATE INDEX IF NOT EXISTS idx_approvals_action_type
            ON authority_approvals (action_type);
        CREATE INDEX IF NOT EXISTS idx_approvals_requester
            ON authority_approvals (requester);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core approval operations
    # ------------------------------------------------------------------

    def request_approval(
        self,
        action_type: str,
        requester: str,
        *,
        tier: int = 0,
        risk_level: str = "low",
        action_preview: str = "",
        affected_systems: Optional[List[str]] = None,
        affected_files: Optional[List[str]] = None,
        affected_accounts: Optional[List[str]] = None,
        estimated_spend: float = 0.0,
        rollback_plan: str = "",
        scope: str = "",
        expires_in_seconds: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRecord:
        """Create an approval record for a proposed action.

        For Tier 0/1 actions, approval is automatically granted (AUTO_ALLOW).
        For Tier 2+, record is created with PENDING status awaiting user grant.
        For Tier 5, record is created with BLOCKED status (prohibited).
        """
        now = datetime.now(timezone.utc).isoformat()
        approval_id = uuid.uuid4().hex
        audit_trace_id = uuid.uuid4().hex[:16]

        expires_at: Optional[str] = None
        if expires_in_seconds is not None:
            expires_at = datetime.fromtimestamp(
                time.time() + expires_in_seconds, tz=timezone.utc
            ).isoformat()

        # Determine mode and initial status
        if tier <= AuthorityTier.TIER_1.value:
            mode = ApprovalMode.AUTO_ALLOW
            status = ApprovalStatus.GRANTED
            granted_at: Optional[str] = now
        elif tier >= AuthorityTier.TIER_5.value:
            mode = ApprovalMode.DENY
            status = ApprovalStatus.BLOCKED
            granted_at = None
        elif tier >= AuthorityTier.TIER_4.value:
            mode = ApprovalMode.STEP_UP
            status = ApprovalStatus.PENDING
            granted_at = None
        else:
            mode = ApprovalMode.ONE_TIME
            status = ApprovalStatus.PENDING
            granted_at = None

        record = ApprovalRecord(
            approval_id=approval_id,
            requester=requester,
            action_type=action_type,
            action_preview=action_preview or action_type,
            risk_level=risk_level,
            tier=tier,
            affected_systems=affected_systems or [],
            affected_files=affected_files or [],
            affected_accounts=affected_accounts or [],
            estimated_spend=estimated_spend,
            rollback_plan=rollback_plan,
            scope=scope,
            mode=mode,
            status=status,
            audit_trace_id=audit_trace_id,
            created_at=now,
            granted_at=granted_at,
            expires_at=expires_at,
            context=_scrub_context(context or {}),
        )

        self._upsert(record)
        return record

    def grant(self, approval_id: str, *, expires_in_seconds: Optional[int] = 3600) -> bool:
        """Grant a pending approval. Returns True if successful."""
        record = self.get(approval_id)
        if record is None or record.status != ApprovalStatus.PENDING:
            return False
        now = datetime.now(timezone.utc).isoformat()
        expires_at: Optional[str] = None
        if expires_in_seconds is not None:
            expires_at = datetime.fromtimestamp(
                time.time() + expires_in_seconds, tz=timezone.utc
            ).isoformat()
        self._conn.execute(
            "UPDATE authority_approvals SET status=?, granted_at=?, expires_at=? WHERE approval_id=?",
            (ApprovalStatus.GRANTED.value, now, expires_at, approval_id),
        )
        self._conn.commit()
        return True

    def deny(self, approval_id: str, *, reason: str = "") -> bool:
        """Deny a pending approval."""
        record = self.get(approval_id)
        if record is None:
            return False
        self._conn.execute(
            "UPDATE authority_approvals SET status=?, error_reason=? WHERE approval_id=?",
            (ApprovalStatus.DENIED.value, reason, approval_id),
        )
        self._conn.commit()
        return True

    def revoke(self, approval_id: str, *, reason: str = "") -> bool:
        """Revoke a granted approval."""
        record = self.get(approval_id)
        if record is None:
            return False
        self._conn.execute(
            "UPDATE authority_approvals SET status=?, mode=?, revocation_reason=? WHERE approval_id=?",
            (
                ApprovalStatus.REVOKED.value,
                ApprovalMode.REVOKED.value,
                reason,
                approval_id,
            ),
        )
        self._conn.commit()
        return True

    def revoke_all_active(self, *, reason: str = "emergency_stop") -> int:
        """Revoke all currently granted approvals. Returns count revoked."""
        cur = self._conn.execute(
            "UPDATE authority_approvals SET status=?, mode=?, revocation_reason=? "
            "WHERE status=?",
            (
                ApprovalStatus.REVOKED.value,
                ApprovalMode.REVOKED.value,
                reason,
                ApprovalStatus.GRANTED.value,
            ),
        )
        self._conn.commit()
        return cur.rowcount

    def mark_used(self, approval_id: str) -> bool:
        """Mark a ONE_TIME approval as used after execution."""
        self._conn.execute(
            "UPDATE authority_approvals SET status=? WHERE approval_id=? AND mode=?",
            (ApprovalStatus.USED.value, approval_id, ApprovalMode.ONE_TIME.value),
        )
        self._conn.commit()
        return True

    def expire_stale(self) -> int:
        """Expire any approvals past their expiry time. Returns count expired."""
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "UPDATE authority_approvals SET status=? "
            "WHERE status=? AND expires_at IS NOT NULL AND expires_at < ?",
            (ApprovalStatus.EXPIRED.value, ApprovalStatus.GRANTED.value, now),
        )
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, approval_id: str) -> Optional[ApprovalRecord]:
        cur = self._conn.execute(
            "SELECT * FROM authority_approvals WHERE approval_id=?", (approval_id,)
        )
        row = cur.fetchone()
        return ApprovalRecord.from_row(row) if row else None

    def list_pending(self) -> List[ApprovalRecord]:
        self.expire_stale()
        cur = self._conn.execute(
            "SELECT * FROM authority_approvals WHERE status=? ORDER BY created_at DESC",
            (ApprovalStatus.PENDING.value,),
        )
        return [ApprovalRecord.from_row(r) for r in cur.fetchall()]

    def list_active(self) -> List[ApprovalRecord]:
        self.expire_stale()
        cur = self._conn.execute(
            "SELECT * FROM authority_approvals WHERE status=? ORDER BY granted_at DESC",
            (ApprovalStatus.GRANTED.value,),
        )
        return [ApprovalRecord.from_row(r) for r in cur.fetchall()]

    def list_revoked(self) -> List[ApprovalRecord]:
        cur = self._conn.execute(
            "SELECT * FROM authority_approvals WHERE status IN (?,?) "
            "ORDER BY created_at DESC LIMIT 100",
            (ApprovalStatus.REVOKED.value, ApprovalStatus.DENIED.value),
        )
        return [ApprovalRecord.from_row(r) for r in cur.fetchall()]

    def list_all(self, limit: int = 200) -> List[ApprovalRecord]:
        cur = self._conn.execute(
            "SELECT * FROM authority_approvals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [ApprovalRecord.from_row(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _upsert(self, record: ApprovalRecord) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO authority_approvals (
                approval_id, requester, action_type, action_preview,
                risk_level, tier, affected_systems, affected_files,
                affected_accounts, estimated_spend, rollback_plan, scope,
                mode, status, audit_trace_id, created_at, granted_at,
                expires_at, context_json, error_reason, revocation_reason
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record.approval_id,
                record.requester,
                record.action_type,
                record.action_preview,
                record.risk_level,
                record.tier,
                json.dumps(record.affected_systems),
                json.dumps(record.affected_files),
                json.dumps(record.affected_accounts),
                record.estimated_spend,
                record.rollback_plan,
                record.scope,
                record.mode.value,
                record.status.value,
                record.audit_trace_id,
                record.created_at,
                record.granted_at,
                record.expires_at,
                json.dumps(record.context),
                record.error_reason,
                record.revocation_reason,
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


__all__ = [
    "ApprovalEngine",
    "ApprovalMode",
    "ApprovalRecord",
    "ApprovalStatus",
]
