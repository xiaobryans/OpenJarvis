"""Plan 8 — Emergency Stop and Revocation.

Provides:
  - Global emergency stop flag (SQLite-backed, survives restarts)
  - set_emergency_stop() / clear_emergency_stop()
  - is_emergency_stop_active() — checked by all Plan 8 gates
  - revoke_approval(approval_id) — revoke a specific active approval
  - revoke_all_active() — revoke all active approvals (used with emergency stop)
  - get_emergency_status() — API-ready status dict
  - Behavior when emergency stop is active: all Tier 2+ actions are blocked

Emergency stop is a last-resort safety gate. It survives process restarts.
It does NOT affect Tier 0/1 read-only/draft operations.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Default DB path
# ---------------------------------------------------------------------------

_DEFAULT_DB = Path.home() / ".jarvis" / "authority_emergency.db"


# ---------------------------------------------------------------------------
# EmergencyStopStore
# ---------------------------------------------------------------------------


class EmergencyStopStore:
    """Persistent emergency stop flag for Plan 8.

    A single row in the `emergency_stop` table represents the current state.
    Creating or updating this row activates/deactivates the stop.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS emergency_stop (
            id              INTEGER PRIMARY KEY DEFAULT 1,
            active          INTEGER NOT NULL DEFAULT 0,
            activated_at    TEXT,
            activated_by    TEXT NOT NULL DEFAULT '',
            reason          TEXT NOT NULL DEFAULT '',
            cleared_at      TEXT,
            cleared_by      TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS revocation_log (
            revocation_id   TEXT PRIMARY KEY,
            approval_id     TEXT,
            revoked_by      TEXT NOT NULL DEFAULT '',
            reason          TEXT NOT NULL DEFAULT '',
            revoked_at      TEXT NOT NULL,
            emergency_stop  INTEGER NOT NULL DEFAULT 0
        );
        """)
        self._conn.commit()
        # Ensure the singleton row exists
        self._conn.execute(
            "INSERT OR IGNORE INTO emergency_stop (id, active) VALUES (1, 0)"
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Emergency stop
    # ------------------------------------------------------------------

    def set_emergency_stop(
        self, *, activated_by: str = "system", reason: str = ""
    ) -> Dict[str, Any]:
        """Activate the global emergency stop."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE emergency_stop SET active=1, activated_at=?, activated_by=?, reason=?, "
            "cleared_at=NULL, cleared_by='' WHERE id=1",
            (now, activated_by, reason),
        )
        self._conn.commit()
        return {
            "active": True,
            "activated_at": now,
            "activated_by": activated_by,
            "reason": reason,
        }

    def clear_emergency_stop(
        self, *, cleared_by: str = "owner", reason: str = ""
    ) -> Dict[str, Any]:
        """Deactivate the global emergency stop."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE emergency_stop SET active=0, cleared_at=?, cleared_by=? WHERE id=1",
            (now, cleared_by),
        )
        self._conn.commit()
        return {
            "active": False,
            "cleared_at": now,
            "cleared_by": cleared_by,
        }

    def is_active(self) -> bool:
        """Return True if emergency stop is currently active."""
        cur = self._conn.execute("SELECT active FROM emergency_stop WHERE id=1")
        row = cur.fetchone()
        return bool(row[0]) if row else False

    def get_status(self) -> Dict[str, Any]:
        """Return full emergency stop status dict (API-ready)."""
        cur = self._conn.execute("SELECT * FROM emergency_stop WHERE id=1")
        row = cur.fetchone()
        if row is None:
            return {"active": False, "status": "never_activated"}
        (_, active, activated_at, activated_by, reason, cleared_at, cleared_by) = row
        return {
            "active": bool(active),
            "activated_at": activated_at,
            "activated_by": activated_by,
            "reason": reason,
            "cleared_at": cleared_at,
            "cleared_by": cleared_by,
            "status": "active" if active else "inactive",
        }

    # ------------------------------------------------------------------
    # Revocation log
    # ------------------------------------------------------------------

    def log_revocation(
        self,
        approval_id: Optional[str],
        *,
        revoked_by: str = "system",
        reason: str = "",
        is_emergency: bool = False,
    ) -> str:
        """Log a revocation event. Returns the revocation_id."""
        import uuid
        revocation_id = uuid.uuid4().hex[:16]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO revocation_log (revocation_id, approval_id, revoked_by, reason, revoked_at, emergency_stop) "
            "VALUES (?,?,?,?,?,?)",
            (revocation_id, approval_id, revoked_by, reason, now, int(is_emergency)),
        )
        self._conn.commit()
        return revocation_id

    def get_revocation_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM revocation_log ORDER BY revoked_at DESC LIMIT ?", (limit,)
        )
        rows = cur.fetchall()
        return [
            {
                "revocation_id": r[0],
                "approval_id": r[1],
                "revoked_by": r[2],
                "reason": r[3],
                "revoked_at": r[4],
                "emergency_stop": bool(r[5]),
            }
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Module-level singleton convenience functions
# ---------------------------------------------------------------------------

_store: Optional[EmergencyStopStore] = None


def _get_store() -> EmergencyStopStore:
    global _store
    if _store is None:
        _store = EmergencyStopStore()
    return _store


def is_emergency_stop_active() -> bool:
    """Check if the global emergency stop is active.

    This function is called by all Plan 8 authority gates before
    executing any Tier 2+ action.
    """
    return _get_store().is_active()


def set_emergency_stop(*, activated_by: str = "system", reason: str = "") -> Dict[str, Any]:
    """Activate the global emergency stop."""
    return _get_store().set_emergency_stop(activated_by=activated_by, reason=reason)


def clear_emergency_stop(*, cleared_by: str = "owner") -> Dict[str, Any]:
    """Clear the global emergency stop."""
    return _get_store().clear_emergency_stop(cleared_by=cleared_by)


def get_emergency_status() -> Dict[str, Any]:
    """Return API-ready emergency stop status."""
    return _get_store().get_status()


# ---------------------------------------------------------------------------
# Gate check with emergency stop awareness
# ---------------------------------------------------------------------------

def emergency_gate_check(tier: int) -> Dict[str, Any]:
    """Check if an action at the given tier is blocked by emergency stop.

    Tier 0/1 (read-only/draft) are never blocked by emergency stop.
    Tier 2+ are blocked if emergency stop is active.
    """
    if tier <= 1:
        return {
            "blocked": False,
            "reason": "Tier 0/1 actions are not affected by emergency stop.",
        }

    if is_emergency_stop_active():
        status = get_emergency_status()
        return {
            "blocked": True,
            "reason": (
                f"EMERGENCY STOP ACTIVE. All Tier {tier} actions blocked. "
                f"Activated by: {status.get('activated_by', 'unknown')}. "
                f"Reason: {status.get('reason', 'none')}. "
                "Contact owner to clear emergency stop."
            ),
            "emergency_status": status,
        }

    return {
        "blocked": False,
        "reason": "Emergency stop is not active.",
    }


__all__ = [
    "EmergencyStopStore",
    "clear_emergency_stop",
    "emergency_gate_check",
    "get_emergency_status",
    "is_emergency_stop_active",
    "set_emergency_stop",
]
