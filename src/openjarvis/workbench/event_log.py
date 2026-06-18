"""WorkbenchEventLog — unified SQLite-backed event log for Workbench lifecycle events.

Design rules (non-negotiable):
- Events are purely local audit records; they NEVER trigger external sends.
- No Slack/Telegram/HTTP calls are made from this module under any circumstances.
- Dry-run events are stored with dry_run=True for audit traceability.
- event_type values are deterministic and schema-stable across sessions.

Schema (WorkbenchEvent):
    id:          hex[:16] UUID
    session_id:  Workbench session identifier
    task_id:     Task identifier within the session
    event_type:  stable string key, e.g. 'plan_created', 'execution_started',
                 'subtask_done', 'subtask_failed', 'execution_complete',
                 'approval_required', 'dry_run_gate'
    title:       Short human-readable summary
    detail:      Extended detail (safe to expose over HTTP)
    tone:        'info' | 'success' | 'warning' | 'error'
    dry_run:     True when event occurs inside a dry-run session
    created_at:  Unix timestamp (float)
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_events.db"

EventTone = Literal["info", "success", "warning", "error"]

# Stable event_type constants
EVENT_PLAN_CREATED = "plan_created"
EVENT_EXECUTION_STARTED = "execution_started"
EVENT_SUBTASK_DONE = "subtask_done"
EVENT_SUBTASK_FAILED = "subtask_failed"
EVENT_EXECUTION_COMPLETE = "execution_complete"
EVENT_APPROVAL_REQUIRED = "approval_required"
EVENT_DRY_RUN_GATE = "dry_run_gate"
EVENT_NOTIFICATION_GATED = "notification_gated"
# US17 safety event types
EVENT_SAFETY_BLOCKED = "safety_blocked"
EVENT_VALIDATION_FAILED = "validation_failed"
EVENT_BUDGET_EXCEEDED = "budget_exceeded"
EVENT_PROVIDER_UNAVAILABLE = "provider_unavailable"
EVENT_ROLLBACK_GUIDANCE = "rollback_guidance"


@dataclass
class WorkbenchEvent:
    """A Workbench task lifecycle event (local audit record only)."""

    id: str
    session_id: str
    task_id: str
    event_type: str
    title: str
    detail: str
    tone: str
    dry_run: bool
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "event_type": self.event_type,
            "title": self.title,
            "detail": self.detail,
            "tone": self.tone,
            "dry_run": self.dry_run,
            "at": int(self.created_at * 1000),
            "created_at": self.created_at,
        }


class WorkbenchEventLog:
    """SQLite-backed event log for Workbench task lifecycle events.

    Events are local audit records.  This class NEVER makes external network
    calls and NEVER triggers Slack or Telegram sends.

    Connection policy (non-negotiable):
    - __init__ performs ZERO I/O — safe to construct thousands of instances.
    - Each public method opens one short-lived connection, runs its operation,
      then closes the connection in a finally block.
    - Schema (CREATE TABLE IF NOT EXISTS) is applied lazily inside every
      operation so no separate init step is needed.
    - All operations catch (sqlite3.Error, OSError) and degrade gracefully:
        push()          → always returns the WorkbenchEvent object; storage
                          failure is silently swallowed.
        list_events()   → returns [] on failure.
        list_recent()   → returns [] on failure.
        count_by_type() → returns {} on failure.
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS workbench_events (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            detail TEXT NOT NULL DEFAULT '',
            tone TEXT NOT NULL DEFAULT 'info',
            dry_run INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_evt_session ON workbench_events (session_id);
        CREATE INDEX IF NOT EXISTS idx_evt_task ON workbench_events (task_id);
        CREATE INDEX IF NOT EXISTS idx_evt_type ON workbench_events (event_type);
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        # Zero I/O in __init__ — mkdir and schema init happen lazily on first use.

    def _open(self) -> sqlite3.Connection:
        """Create the parent directory and open a short-lived connection.

        Always call conn.close() in a finally block after calling this.
        Raises sqlite3.Error or OSError on failure — callers must catch.
        """
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(self._SCHEMA)
        return conn

    def push(
        self,
        session_id: str,
        task_id: str,
        event_type: str,
        title: str,
        detail: str = "",
        tone: str = "info",
        dry_run: bool = False,
    ) -> WorkbenchEvent:
        """Record a new Workbench lifecycle event.

        Always returns a WorkbenchEvent.  If SQLite is unavailable the event
        object is still returned (un-persisted) so callers never receive None.
        No external sends ever occur.
        """
        event = WorkbenchEvent(
            id=uuid.uuid4().hex[:16],
            session_id=session_id,
            task_id=task_id,
            event_type=event_type,
            title=title,
            detail=detail,
            tone=tone,
            dry_run=dry_run,
            created_at=time.time(),
        )
        try:
            conn = self._open()
            try:
                conn.execute(
                    """INSERT INTO workbench_events
                       (id, session_id, task_id, event_type, title,
                        detail, tone, dry_run, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        event.id, event.session_id, event.task_id,
                        event.event_type, event.title, event.detail,
                        event.tone, int(event.dry_run), event.created_at,
                    ),
                )
                conn.commit()
            finally:
                conn.close()
        except (sqlite3.Error, OSError):
            pass
        return event

    def list_events(self, session_id: str, limit: int = 50) -> List[WorkbenchEvent]:
        """Return events for a session, newest first.  Returns [] on failure."""
        try:
            conn = self._open()
            try:
                rows = conn.execute(
                    "SELECT * FROM workbench_events WHERE session_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (session_id, limit),
                ).fetchall()
            finally:
                conn.close()
            return [self._row_to_event(r) for r in rows]
        except (sqlite3.Error, OSError):
            return []

    def list_recent(self, limit: int = 20) -> List[WorkbenchEvent]:
        """Return the most recent events across all sessions.  Returns [] on failure."""
        try:
            conn = self._open()
            try:
                rows = conn.execute(
                    "SELECT * FROM workbench_events ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            finally:
                conn.close()
            return [self._row_to_event(r) for r in rows]
        except (sqlite3.Error, OSError):
            return []

    def count_by_type(self, session_id: str) -> Dict[str, int]:
        """Return event count grouped by event_type for a session.  Returns {} on failure."""
        try:
            conn = self._open()
            try:
                rows = conn.execute(
                    "SELECT event_type, COUNT(*) AS cnt FROM workbench_events "
                    "WHERE session_id=? GROUP BY event_type",
                    (session_id,),
                ).fetchall()
            finally:
                conn.close()
            return {r["event_type"]: r["cnt"] for r in rows}
        except (sqlite3.Error, OSError):
            return {}

    def close(self) -> None:
        """No persistent connection to close — provided for API symmetry with other stores."""
        pass

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> WorkbenchEvent:
        return WorkbenchEvent(
            id=row["id"],
            session_id=row["session_id"],
            task_id=row["task_id"],
            event_type=row["event_type"],
            title=row["title"],
            detail=row["detail"] or "",
            tone=row["tone"],
            dry_run=bool(row["dry_run"]),
            created_at=row["created_at"],
        )


__all__ = [
    "WorkbenchEvent",
    "WorkbenchEventLog",
    "EVENT_PLAN_CREATED",
    "EVENT_EXECUTION_STARTED",
    "EVENT_SUBTASK_DONE",
    "EVENT_SUBTASK_FAILED",
    "EVENT_EXECUTION_COMPLETE",
    "EVENT_APPROVAL_REQUIRED",
    "EVENT_DRY_RUN_GATE",
    "EVENT_NOTIFICATION_GATED",
]
