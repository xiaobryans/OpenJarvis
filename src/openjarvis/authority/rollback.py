"""Plan 8 — Rollback/Recovery Model.

Manages rollback metadata for all Plan 8 actions. Three categories:

1. File edits: diff/backup path / restore path where feasible
2. Task/goal/action state: previous state snapshot
3. External systems: documents whether rollback is supported, manual, or impossible

Irreversible actions require higher-tier approval and explicit irreversible warning.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Rollback method enumeration
# ---------------------------------------------------------------------------


class RollbackMethod(str, Enum):
    AUTOMATIC = "automatic"         # Can be fully undone by Jarvis automatically
    MANUAL = "manual"               # Can be undone but requires human action
    IMPOSSIBLE = "impossible"       # Cannot be undone (irreversible)
    BEST_EFFORT = "best_effort"     # Partial undo possible
    DOCUMENTED = "documented"       # External system: documented how to undo
    NOT_APPLICABLE = "not_applicable"  # Read-only / draft, nothing to undo


# ---------------------------------------------------------------------------
# RollbackRecord dataclass
# ---------------------------------------------------------------------------


@dataclass
class RollbackRecord:
    """Rollback/recovery metadata for a single action.

    Stored persistently so recovery information survives process restarts.
    """

    rollback_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    action_id: str = ""
    action_type: str = ""
    target: str = ""                    # primary affected path/resource/system

    # File edit rollback
    backup_path: str = ""               # absolute path to backup file (if created)
    diff_forward: str = ""              # patch to apply the change
    diff_reverse: str = ""              # patch to undo the change (reverse diff)
    original_content_hash: str = ""     # sha256 of original content

    # State snapshot
    previous_state_json: str = ""       # JSON snapshot of previous state (no secrets)

    # Rollback policy
    rollback_supported: bool = True
    rollback_method: RollbackMethod = RollbackMethod.MANUAL
    rollback_instructions: str = ""     # Human-readable instructions for manual rollback

    # External system rollback metadata
    external_system: str = ""           # e.g. "github", "stripe", "vercel"
    external_rollback_url: str = ""     # URL to manual rollback doc/console

    # Irreversible
    irreversible_warning: str = ""
    human_confirmation_id: str = ""     # ID of the human who approved irreversible action

    # Metadata
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None  # when backup/snapshot can be purged
    used: bool = False
    used_at: Optional[float] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "backup_path": self.backup_path,
            "diff_forward": self.diff_forward,
            "diff_reverse": self.diff_reverse,
            "original_content_hash": self.original_content_hash,
            "previous_state_json": self.previous_state_json,
            "rollback_supported": self.rollback_supported,
            "rollback_method": self.rollback_method.value,
            "rollback_instructions": self.rollback_instructions,
            "external_system": self.external_system,
            "external_rollback_url": self.external_rollback_url,
            "irreversible_warning": self.irreversible_warning,
            "human_confirmation_id": self.human_confirmation_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "used": self.used,
            "used_at": self.used_at,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "RollbackRecord":
        (
            rollback_id, action_id, action_type, target,
            backup_path, diff_forward, diff_reverse, original_content_hash,
            previous_state_json, rollback_supported, rollback_method,
            rollback_instructions, external_system, external_rollback_url,
            irreversible_warning, human_confirmation_id,
            created_at, expires_at, used, used_at,
        ) = row
        return cls(
            rollback_id=rollback_id,
            action_id=action_id or "",
            action_type=action_type or "",
            target=target or "",
            backup_path=backup_path or "",
            diff_forward=diff_forward or "",
            diff_reverse=diff_reverse or "",
            original_content_hash=original_content_hash or "",
            previous_state_json=previous_state_json or "",
            rollback_supported=bool(rollback_supported),
            rollback_method=RollbackMethod(rollback_method or "manual"),
            rollback_instructions=rollback_instructions or "",
            external_system=external_system or "",
            external_rollback_url=external_rollback_url or "",
            irreversible_warning=irreversible_warning or "",
            human_confirmation_id=human_confirmation_id or "",
            created_at=float(created_at or 0),
            expires_at=float(expires_at) if expires_at else None,
            used=bool(used),
            used_at=float(used_at) if used_at else None,
        )


# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------

_DEFAULT_DB = Path.home() / ".jarvis" / "authority_rollback.db"


# ---------------------------------------------------------------------------
# RollbackStore
# ---------------------------------------------------------------------------


class RollbackStore:
    """SQLite-backed rollback record store for Plan 8 trusted delegation."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS rollback_records (
            rollback_id             TEXT PRIMARY KEY,
            action_id               TEXT NOT NULL DEFAULT '',
            action_type             TEXT NOT NULL DEFAULT '',
            target                  TEXT NOT NULL DEFAULT '',
            backup_path             TEXT NOT NULL DEFAULT '',
            diff_forward            TEXT NOT NULL DEFAULT '',
            diff_reverse            TEXT NOT NULL DEFAULT '',
            original_content_hash   TEXT NOT NULL DEFAULT '',
            previous_state_json     TEXT NOT NULL DEFAULT '',
            rollback_supported      INTEGER NOT NULL DEFAULT 1,
            rollback_method         TEXT NOT NULL DEFAULT 'manual',
            rollback_instructions   TEXT NOT NULL DEFAULT '',
            external_system         TEXT NOT NULL DEFAULT '',
            external_rollback_url   TEXT NOT NULL DEFAULT '',
            irreversible_warning    TEXT NOT NULL DEFAULT '',
            human_confirmation_id   TEXT NOT NULL DEFAULT '',
            created_at              REAL NOT NULL,
            expires_at              REAL,
            used                    INTEGER NOT NULL DEFAULT 0,
            used_at                 REAL
        );
        CREATE INDEX IF NOT EXISTS idx_rollback_action_id
            ON rollback_records (action_id);
        """)
        self._conn.commit()

    def save(self, record: RollbackRecord) -> RollbackRecord:
        self._conn.execute(
            """INSERT OR REPLACE INTO rollback_records (
                rollback_id, action_id, action_type, target,
                backup_path, diff_forward, diff_reverse, original_content_hash,
                previous_state_json, rollback_supported, rollback_method,
                rollback_instructions, external_system, external_rollback_url,
                irreversible_warning, human_confirmation_id,
                created_at, expires_at, used, used_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                record.rollback_id, record.action_id, record.action_type, record.target,
                record.backup_path, record.diff_forward, record.diff_reverse,
                record.original_content_hash, record.previous_state_json,
                int(record.rollback_supported), record.rollback_method.value,
                record.rollback_instructions, record.external_system,
                record.external_rollback_url, record.irreversible_warning,
                record.human_confirmation_id, record.created_at,
                record.expires_at, int(record.used), record.used_at,
            ),
        )
        self._conn.commit()
        return record

    def get(self, rollback_id: str) -> Optional[RollbackRecord]:
        cur = self._conn.execute(
            "SELECT * FROM rollback_records WHERE rollback_id=?", (rollback_id,)
        )
        row = cur.fetchone()
        return RollbackRecord.from_row(row) if row else None

    def get_by_action(self, action_id: str) -> Optional[RollbackRecord]:
        cur = self._conn.execute(
            "SELECT * FROM rollback_records WHERE action_id=? ORDER BY created_at DESC LIMIT 1",
            (action_id,),
        )
        row = cur.fetchone()
        return RollbackRecord.from_row(row) if row else None

    def mark_used(self, rollback_id: str) -> bool:
        self._conn.execute(
            "UPDATE rollback_records SET used=1, used_at=? WHERE rollback_id=?",
            (time.time(), rollback_id),
        )
        self._conn.commit()
        return True

    def list_recent(self, limit: int = 50) -> List[RollbackRecord]:
        cur = self._conn.execute(
            "SELECT * FROM rollback_records WHERE used=0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return [RollbackRecord.from_row(r) for r in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Policy helpers
# ---------------------------------------------------------------------------


def rollback_for_action_type(action_type: str) -> RollbackMethod:
    """Return the appropriate RollbackMethod for a known action type."""
    action = action_type.lower()
    _IMPOSSIBLE = frozenset({
        "email_send", "external_send", "billing_change", "stripe_change",
        "destructive_irreversible_delete", "aws_infra_change",
        "credential_write", "account_mutation",
    })
    _MANUAL = frozenset({
        "production_deploy", "vercel_deploy", "staging_deploy",
        "slack_send", "git_push",
    })
    _AUTOMATIC = frozenset({
        "file_write", "file_edit", "git_commit", "git_add",
        "local_note_write", "local_state_change",
    })
    _NOT_APPLICABLE = frozenset({
        "read", "explain", "plan", "search", "draft", "simulate", "dry_run", "preview",
    })

    if action in _IMPOSSIBLE:
        return RollbackMethod.IMPOSSIBLE
    if action in _MANUAL:
        return RollbackMethod.MANUAL
    if action in _AUTOMATIC:
        return RollbackMethod.AUTOMATIC
    if action in _NOT_APPLICABLE:
        return RollbackMethod.NOT_APPLICABLE
    return RollbackMethod.BEST_EFFORT


__all__ = [
    "RollbackMethod",
    "RollbackRecord",
    "RollbackStore",
    "rollback_for_action_type",
]
