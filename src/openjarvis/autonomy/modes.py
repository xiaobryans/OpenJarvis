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
  - Autonomy state is per-project (project_id) and persisted to SQLite
    (~/.jarvis/autonomy_modes.db); survives server restarts
  - No mode allows: real Slack/Telegram/email send, deploy, browser mutation, AWS change
  - Mode changes are recorded in the AutonomyPolicy audit log

No fake autonomy:
  - observe_only: watchdogs observe and report only — no execution
  - propose_only: draft proposals only — no execution
  - safe_execute_approved: hard gates still blocked, destructive actions still blocked
  - No mode bypasses governance gate_check()
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


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


_DEFAULT_DB_PATH = Path.home() / ".jarvis" / "autonomy_modes.db"


class AutonomyPolicy:
    """Project-aware autonomy mode manager.

    Stores mode per project_id. Default is observe_only.
    Hard gates from governance constitution are always enforced regardless of mode.

    Persisted to SQLite (~/.jarvis/autonomy_modes.db) — survives server restarts.
    In-memory cache avoids redundant DB reads within a single process.
    """

    _modes: Dict[str, AutonomyModeEntry] = {}
    _history: List[AutonomyModeEntry] = []
    _db_path: Path = _DEFAULT_DB_PATH
    _db_initialized: bool = False

    # ------------------------------------------------------------------
    # SQLite helpers
    # ------------------------------------------------------------------

    @classmethod
    @contextmanager
    def _connect(cls) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(cls._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    @classmethod
    def _init_db(cls) -> None:
        if cls._db_initialized:
            return
        try:
            cls._db_path.parent.mkdir(parents=True, exist_ok=True)
            with cls._connect() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS autonomy_modes (
                        project_id TEXT PRIMARY KEY,
                        mode TEXT NOT NULL,
                        set_by TEXT NOT NULL DEFAULT 'system',
                        set_at REAL NOT NULL,
                        reason TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS autonomy_mode_history (
                        rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        set_by TEXT NOT NULL DEFAULT 'system',
                        set_at REAL NOT NULL,
                        reason TEXT NOT NULL DEFAULT ''
                    )
                """)
                conn.commit()
            cls._db_initialized = True
        except Exception:
            pass

    @classmethod
    def _load_from_db(cls, project_id: str) -> Optional[AutonomyModeEntry]:
        """Load a project's persisted mode from SQLite. Returns None on miss/error."""
        try:
            cls._init_db()
            with cls._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM autonomy_modes WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
            if row is None:
                return None
            try:
                mode = AutonomyMode(row["mode"])
            except ValueError:
                mode = _DEFAULT_MODE
            return AutonomyModeEntry(
                project_id=row["project_id"],
                mode=mode,
                set_by=row["set_by"],
                set_at=row["set_at"],
                reason=row["reason"],
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def get_mode(cls, project_id: str) -> AutonomyMode:
        """Return the current autonomy mode for a project. Default: observe_only.

        Checks in-memory cache first; loads from SQLite on miss.
        """
        if project_id not in cls._modes:
            persisted = cls._load_from_db(project_id)
            if persisted is not None:
                cls._modes[project_id] = persisted
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
        """Set the autonomy mode for a project. Persists to SQLite + audit history."""
        entry = AutonomyModeEntry(
            project_id=project_id,
            mode=mode,
            set_by=set_by,
            reason=reason,
        )
        cls._modes[project_id] = entry
        cls._history.append(entry)
        try:
            cls._init_db()
            with cls._connect() as conn:
                conn.execute(
                    """INSERT OR REPLACE INTO autonomy_modes
                       (project_id, mode, set_by, set_at, reason)
                       VALUES (?,?,?,?,?)""",
                    (project_id, mode.value, set_by, entry.set_at, reason),
                )
                conn.execute(
                    """INSERT INTO autonomy_mode_history
                       (project_id, mode, set_by, set_at, reason)
                       VALUES (?,?,?,?,?)""",
                    (project_id, mode.value, set_by, entry.set_at, reason),
                )
                conn.commit()
        except Exception:
            pass
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
        """Reset — for tests only. Clears in-memory state and SQLite rows."""
        cls._modes.clear()
        cls._history.clear()
        try:
            if cls._db_path.exists():
                with cls._connect() as conn:
                    conn.execute("DELETE FROM autonomy_modes")
                    conn.execute("DELETE FROM autonomy_mode_history")
                    conn.commit()
        except Exception:
            pass
        cls._db_initialized = False


__all__ = [
    "AutonomyMode",
    "AutonomyModeEntry",
    "AutonomyPolicy",
]
