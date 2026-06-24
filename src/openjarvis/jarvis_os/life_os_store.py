"""SQLite-backed Personal Task Store for Life-OS (B7 local persistence).

Replaces the in-memory ``PersonalTaskStore`` in ``personal_os.py`` with a
real SQLite backend so tasks survive server restarts.

Cloud sync (B7 full closure) requires a deployed Fargate worker — see
``life_os_cloud_sync_status.py`` for honest layer tracking.  This module
closes the *local-persistence* gap only.

Hard rules:
- No cloud calls here.
- No secret values read or returned.
- No bucket names, account IDs, or credential paths in responses.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB_DIR = Path.home() / ".openjarvis"
_DEFAULT_DB_NAME = "life_os_tasks.db"


def _db_path() -> Path:
    """Return the SQLite database path, honouring OPENJARVIS_LIFE_OS_DB env var."""
    override = os.environ.get("OPENJARVIS_LIFE_OS_DB", "").strip()
    if override:
        return Path(override)
    return _DEFAULT_DB_DIR / _DEFAULT_DB_NAME


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS personal_tasks (
    task_id      TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    priority     TEXT NOT NULL DEFAULT 'medium',
    status       TEXT NOT NULL DEFAULT 'pending',
    tags         TEXT NOT NULL DEFAULT '[]',
    memory_refs  TEXT NOT NULL DEFAULT '[]',
    reminder     TEXT,
    follow_up_state TEXT,
    approval_required INTEGER NOT NULL DEFAULT 0,
    approval_state TEXT,
    scheduled_at REAL,
    due_at       REAL,
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
"""


# ---------------------------------------------------------------------------
# SQLite-backed store
# ---------------------------------------------------------------------------


class SQLitePersonalTaskStore:
    """SQLite-backed personal task store.

    Thread-safety: each call opens and closes its own connection so the
    store is safe to use from multiple threads or async workers via
    ``run_in_executor``.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _db_path()
        self._ensure_db()

    def _ensure_db(self) -> None:
        """Create the database directory and schema if not present."""
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            with self._connect() as con:
                con.execute(_CREATE_TABLE)
                con.commit()
        except Exception as exc:
            logger.warning("life_os_store: could not initialise SQLite DB: %s", exc)

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        con = sqlite3.connect(str(self._db_path), timeout=10)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    # ------------------------------------------------------------------
    # Public interface — mirrors PersonalTaskStore in personal_os.py
    # ------------------------------------------------------------------

    def add(self, task: Any) -> str:
        """Persist a PersonalTask and return its task_id."""
        row = _task_to_row(task)
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO personal_tasks
                (task_id, title, description, priority, status, tags,
                 memory_refs, reminder, follow_up_state, approval_required,
                 approval_state, scheduled_at, due_at, created_at, updated_at)
                VALUES
                (:task_id,:title,:description,:priority,:status,:tags,
                 :memory_refs,:reminder,:follow_up_state,:approval_required,
                 :approval_state,:scheduled_at,:due_at,:created_at,:updated_at)
                """,
                row,
            )
            con.commit()
        return task.task_id

    def get(self, task_id: str) -> Optional[Any]:
        """Return a PersonalTask by ID, or None if not found."""
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM personal_tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        return _row_to_task(dict(row)) if row else None

    def update_status(self, task_id: str, status: str) -> bool:
        """Update a task's status. Returns False if task not found."""
        with self._connect() as con:
            cur = con.execute(
                "UPDATE personal_tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (status, time.time(), task_id),
            )
            con.commit()
        return cur.rowcount > 0

    def list_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
    ) -> List[Any]:
        """Return all tasks, optionally filtered."""
        query = "SELECT * FROM personal_tasks"
        params: List[Any] = []
        conditions: List[str] = []
        if status:
            conditions.append("status = ?")
            params.append(status)
        if priority:
            conditions.append("priority = ?")
            params.append(priority)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY created_at DESC"

        with self._connect() as con:
            rows = con.execute(query, params).fetchall()
        return [_row_to_task(dict(r)) for r in rows]

    def pending_approvals(self) -> List[Any]:
        """Return tasks waiting for approval."""
        return self.list_tasks(status="waiting_approval")

    def pending_follow_ups(self) -> List[Any]:
        """Return tasks waiting for follow-up."""
        return self.list_tasks(status="waiting_followup")

    def task_count(self) -> int:
        """Return total number of tasks stored."""
        with self._connect() as con:
            row = con.execute("SELECT COUNT(*) FROM personal_tasks").fetchone()
        return row[0] if row else 0

    def db_exists(self) -> bool:
        """Return True if the SQLite file exists."""
        try:
            return self._db_path.exists() and self._db_path.is_file()
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Row ↔ PersonalTask conversion helpers
# ---------------------------------------------------------------------------


def _task_to_row(task: Any) -> Dict[str, Any]:
    """Convert a PersonalTask dataclass to a SQLite row dict."""
    return {
        "task_id": task.task_id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority.value if hasattr(task.priority, "value") else task.priority,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "tags": json.dumps(task.tags or []),
        "memory_refs": json.dumps(task.memory_refs or []),
        "reminder": json.dumps(task.reminder) if task.reminder else None,
        "follow_up_state": json.dumps(task.follow_up_state) if task.follow_up_state else None,
        "approval_required": int(bool(task.approval_required)),
        "approval_state": task.approval_state,
        "scheduled_at": task.scheduled_at,
        "due_at": task.due_at,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def _row_to_task(row: Dict[str, Any]) -> Any:
    """Convert a SQLite row dict back to a PersonalTask dataclass."""
    from openjarvis.jarvis_os.personal_os import PersonalTask, TaskPriority, TaskStatus

    return PersonalTask(
        task_id=row["task_id"],
        title=row["title"],
        description=row["description"],
        priority=TaskPriority(row["priority"]),
        status=TaskStatus(row["status"]),
        tags=json.loads(row["tags"] or "[]"),
        memory_refs=json.loads(row["memory_refs"] or "[]"),
        reminder=json.loads(row["reminder"]) if row.get("reminder") else None,
        follow_up_state=json.loads(row["follow_up_state"]) if row.get("follow_up_state") else None,
        approval_required=bool(row["approval_required"]),
        approval_state=row.get("approval_state"),
        scheduled_at=row.get("scheduled_at"),
        due_at=row.get("due_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Store type info (for cloud sync status)
# ---------------------------------------------------------------------------

STORE_TYPE_SQLITE = "sqlite"
STORE_TYPE_IN_MEMORY = "in_memory"


def get_store_type() -> str:
    """Return STORE_TYPE_SQLITE always (this module is the SQLite backend)."""
    return STORE_TYPE_SQLITE


__all__ = [
    "SQLitePersonalTaskStore",
    "get_store_type",
    "STORE_TYPE_SQLITE",
    "STORE_TYPE_IN_MEMORY",
    "_db_path",
]
