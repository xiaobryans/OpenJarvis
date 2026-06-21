"""Plan 8 — Durable Audit Store.

SQLite-backed audit log for all trusted delegation actions. Records:
  - requested action
  - risk classification
  - approval decision
  - execution status
  - actor/source
  - timestamps
  - affected resource
  - rollback metadata
  - error/retry information
  - connector/provider used
  - NO secret values stored

Audit records are immutable once written. Search/query via list_* methods.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------

_DEFAULT_DB = Path.home() / ".jarvis" / "authority_audit.db"

# ---------------------------------------------------------------------------
# Sensitive key scrubber (same as policies.py)
# ---------------------------------------------------------------------------

_SENSITIVE_KEYS = frozenset({
    "token", "secret", "password", "api_key", "auth", "credential",
    "private_key", "access_key", "bot_token", "chat_id", "key",
    "bearer", "oauth_token", "refresh_token", "id_token",
})


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 5:
        return value
    if isinstance(value, dict):
        return {
            k: "<redacted>" if any(s in k.lower() for s in _SENSITIVE_KEYS) else _scrub(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(i, depth + 1) for i in value]
    if isinstance(value, str):
        # Redact obvious secret patterns in string values
        import re
        patterns = [
            r"(ghp_[A-Za-z0-9]{36})",
            r"(gho_[A-Za-z0-9]{36})",
            r"(sk-[A-Za-z0-9]{32,})",
            r"(xoxb-[A-Za-z0-9\-]+)",
            r"(AKIA[A-Z0-9]{16})",
            r"(Bearer\s+[A-Za-z0-9\-._~+/]+=*)",
        ]
        for p in patterns:
            value = re.sub(p, "<redacted>", value, flags=re.IGNORECASE)
    return value


# ---------------------------------------------------------------------------
# AuditEntry dataclass
# ---------------------------------------------------------------------------


@dataclass
class AuditEntry:
    """A single immutable audit log record."""

    audit_id: str
    ts: float                           # Unix timestamp
    action_type: str
    actor: str                          # agent_id or "user"
    tier: int                           # AuthorityTier value
    risk_level: str                     # low | medium | high | critical
    approval_decision: str              # auto_allow | granted | denied | pending | revoked | blocked
    execution_status: str               # not_started | dry_run | success | failed | blocked
    affected_resource: str              # primary affected resource/path/system
    rollback_metadata: str              # JSON or description
    error_info: str                     # error trace (no secrets)
    retry_count: int                    # number of retries
    connector: str                      # provider/connector used
    approval_id: Optional[str]
    audit_trace_id: str
    context: Dict[str, Any]             # scrubbed context

    def iso_ts(self) -> str:
        return datetime.fromtimestamp(self.ts, tz=timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "ts": self.ts,
            "iso_ts": self.iso_ts(),
            "action_type": self.action_type,
            "actor": self.actor,
            "tier": self.tier,
            "risk_level": self.risk_level,
            "approval_decision": self.approval_decision,
            "execution_status": self.execution_status,
            "affected_resource": self.affected_resource,
            "rollback_metadata": self.rollback_metadata,
            "error_info": self.error_info,
            "retry_count": self.retry_count,
            "connector": self.connector,
            "approval_id": self.approval_id,
            "audit_trace_id": self.audit_trace_id,
            "context": self.context,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "AuditEntry":
        (
            audit_id, ts, action_type, actor, tier, risk_level,
            approval_decision, execution_status, affected_resource,
            rollback_metadata, error_info, retry_count, connector,
            approval_id, audit_trace_id, context_json,
        ) = row
        return cls(
            audit_id=audit_id,
            ts=float(ts),
            action_type=action_type,
            actor=actor,
            tier=int(tier),
            risk_level=risk_level,
            approval_decision=approval_decision,
            execution_status=execution_status,
            affected_resource=affected_resource or "",
            rollback_metadata=rollback_metadata or "",
            error_info=error_info or "",
            retry_count=int(retry_count or 0),
            connector=connector or "",
            approval_id=approval_id,
            audit_trace_id=audit_trace_id or "",
            context=json.loads(context_json or "{}"),
        )


# ---------------------------------------------------------------------------
# AuditStore
# ---------------------------------------------------------------------------


class AuditStore:
    """SQLite-backed durable audit log for Plan 8 trusted delegation.

    Records are written once and never updated (append-only semantics).
    Secrets are scrubbed before storage.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS authority_audit (
            audit_id            TEXT PRIMARY KEY,
            ts                  REAL NOT NULL,
            action_type         TEXT NOT NULL,
            actor               TEXT NOT NULL DEFAULT '',
            tier                INTEGER NOT NULL DEFAULT 0,
            risk_level          TEXT NOT NULL DEFAULT 'low',
            approval_decision   TEXT NOT NULL DEFAULT 'pending',
            execution_status    TEXT NOT NULL DEFAULT 'not_started',
            affected_resource   TEXT NOT NULL DEFAULT '',
            rollback_metadata   TEXT NOT NULL DEFAULT '',
            error_info          TEXT NOT NULL DEFAULT '',
            retry_count         INTEGER NOT NULL DEFAULT 0,
            connector           TEXT NOT NULL DEFAULT '',
            approval_id         TEXT,
            audit_trace_id      TEXT NOT NULL DEFAULT '',
            context_json        TEXT NOT NULL DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_audit_ts
            ON authority_audit (ts DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action_type
            ON authority_audit (action_type);
        CREATE INDEX IF NOT EXISTS idx_audit_actor
            ON authority_audit (actor);
        CREATE INDEX IF NOT EXISTS idx_audit_execution_status
            ON authority_audit (execution_status);
        """)
        self._conn.commit()

    def record(
        self,
        action_type: str,
        actor: str,
        *,
        tier: int = 0,
        risk_level: str = "low",
        approval_decision: str = "pending",
        execution_status: str = "not_started",
        affected_resource: str = "",
        rollback_metadata: str = "",
        error_info: str = "",
        retry_count: int = 0,
        connector: str = "",
        approval_id: Optional[str] = None,
        audit_trace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Write a scrubbed audit entry. Returns the created entry."""
        entry = AuditEntry(
            audit_id=uuid.uuid4().hex,
            ts=time.time(),
            action_type=action_type,
            actor=actor,
            tier=tier,
            risk_level=risk_level,
            approval_decision=approval_decision,
            execution_status=execution_status,
            affected_resource=affected_resource,
            rollback_metadata=rollback_metadata,
            error_info=_scrub(error_info) if isinstance(error_info, str) else "",
            retry_count=retry_count,
            connector=connector,
            approval_id=approval_id,
            audit_trace_id=audit_trace_id or uuid.uuid4().hex[:16],
            context=_scrub(context or {}),
        )
        self._conn.execute(
            """INSERT INTO authority_audit (
                audit_id, ts, action_type, actor, tier, risk_level,
                approval_decision, execution_status, affected_resource,
                rollback_metadata, error_info, retry_count, connector,
                approval_id, audit_trace_id, context_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                entry.audit_id, entry.ts, entry.action_type, entry.actor,
                entry.tier, entry.risk_level, entry.approval_decision,
                entry.execution_status, entry.affected_resource,
                entry.rollback_metadata, entry.error_info, entry.retry_count,
                entry.connector, entry.approval_id, entry.audit_trace_id,
                json.dumps(entry.context),
            ),
        )
        self._conn.commit()
        return entry

    def get(self, audit_id: str) -> Optional[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM authority_audit WHERE audit_id=?", (audit_id,)
        )
        row = cur.fetchone()
        return AuditEntry.from_row(row) if row else None

    def list_recent(self, limit: int = 50) -> List[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM authority_audit ORDER BY ts DESC LIMIT ?", (limit,)
        )
        return [AuditEntry.from_row(r) for r in cur.fetchall()]

    def list_by_action(self, action_type: str, limit: int = 50) -> List[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM authority_audit WHERE action_type=? ORDER BY ts DESC LIMIT ?",
            (action_type, limit),
        )
        return [AuditEntry.from_row(r) for r in cur.fetchall()]

    def list_by_actor(self, actor: str, limit: int = 50) -> List[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM authority_audit WHERE actor=? ORDER BY ts DESC LIMIT ?",
            (actor, limit),
        )
        return [AuditEntry.from_row(r) for r in cur.fetchall()]

    def list_blocked(self, limit: int = 50) -> List[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM authority_audit WHERE execution_status=? ORDER BY ts DESC LIMIT ?",
            ("blocked", limit),
        )
        return [AuditEntry.from_row(r) for r in cur.fetchall()]

    def list_failed(self, limit: int = 50) -> List[AuditEntry]:
        cur = self._conn.execute(
            "SELECT * FROM authority_audit WHERE execution_status=? ORDER BY ts DESC LIMIT ?",
            ("failed", limit),
        )
        return [AuditEntry.from_row(r) for r in cur.fetchall()]

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM authority_audit")
        row = cur.fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        self._conn.close()


__all__ = [
    "AuditEntry",
    "AuditStore",
    "_scrub",
]
