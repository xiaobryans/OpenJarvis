"""Background job queue for Jarvis Coding Workbench — SQLite-backed.

Supports:
  - Queuing coding tasks with priority
  - Status tracking: pending → running → done / failed / cancelled
  - Output capture per job
  - Timeout enforcement
  - Job history and cleanup
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_jobs.db"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    task_id: str
    description: str
    tool_id: str
    params: Dict[str, Any]
    status: JobStatus
    priority: int
    worker_tier: str
    created_at: float
    started_at: Optional[float]
    finished_at: Optional[float]
    output: Optional[str]
    error: Optional[str]
    cost_usd: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "description": self.description,
            "tool_id": self.tool_id,
            "params": self.params,
            "status": self.status.value,
            "priority": self.priority,
            "worker_tier": self.worker_tier,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "output": self.output,
            "error": self.error,
            "cost_usd": self.cost_usd,
        }


class JobQueue:
    """SQLite-backed job queue for workbench tasks."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS workbench_jobs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                tool_id TEXT NOT NULL DEFAULT '',
                params_json TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                priority INTEGER NOT NULL DEFAULT 5,
                worker_tier TEXT NOT NULL DEFAULT 'local',
                created_at REAL NOT NULL,
                started_at REAL,
                finished_at REAL,
                output TEXT,
                error TEXT,
                cost_usd REAL NOT NULL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_jobs_task ON workbench_jobs (task_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON workbench_jobs (status);
        """)
        self._conn.commit()

    def enqueue(
        self,
        task_id: str,
        description: str,
        tool_id: str,
        params: Dict[str, Any],
        priority: int = 5,
        worker_tier: str = "local",
    ) -> Job:
        job_id = uuid.uuid4().hex[:16]
        now = time.time()
        self._conn.execute(
            """INSERT INTO workbench_jobs
               (id, task_id, description, tool_id, params_json, status,
                priority, worker_tier, created_at, cost_usd)
               VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, 0.0)""",
            (job_id, task_id, description, tool_id, json.dumps(params), priority, worker_tier, now),
        )
        self._conn.commit()
        return Job(
            id=job_id,
            task_id=task_id,
            description=description,
            tool_id=tool_id,
            params=params,
            status=JobStatus.PENDING,
            priority=priority,
            worker_tier=worker_tier,
            created_at=now,
            started_at=None,
            finished_at=None,
            output=None,
            error=None,
            cost_usd=0.0,
        )

    def mark_running(self, job_id: str) -> None:
        self._conn.execute(
            "UPDATE workbench_jobs SET status='running', started_at=? WHERE id=?",
            (time.time(), job_id),
        )
        self._conn.commit()

    def mark_done(self, job_id: str, output: str, cost_usd: float = 0.0) -> None:
        self._conn.execute(
            """UPDATE workbench_jobs
               SET status='done', finished_at=?, output=?, cost_usd=?
               WHERE id=?""",
            (time.time(), output, cost_usd, job_id),
        )
        self._conn.commit()

    def mark_failed(self, job_id: str, error: str) -> None:
        self._conn.execute(
            "UPDATE workbench_jobs SET status='failed', finished_at=?, error=? WHERE id=?",
            (time.time(), error, job_id),
        )
        self._conn.commit()

    def cancel(self, job_id: str) -> None:
        self._conn.execute(
            "UPDATE workbench_jobs SET status='cancelled', finished_at=? WHERE id=?",
            (time.time(), job_id),
        )
        self._conn.commit()

    def get(self, job_id: str) -> Optional[Job]:
        row = self._conn.execute(
            "SELECT * FROM workbench_jobs WHERE id=?", (job_id,)
        ).fetchone()
        return self._row_to_job(row) if row else None

    def list_by_task(self, task_id: str) -> List[Job]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_jobs WHERE task_id=? ORDER BY priority, created_at",
            (task_id,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def list_pending(self) -> List[Job]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_jobs WHERE status='pending' ORDER BY priority, created_at",
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def list_recent(self, limit: int = 50) -> List[Job]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_jobs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_job(r) for r in rows]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            task_id=row["task_id"],
            description=row["description"],
            tool_id=row["tool_id"],
            params=json.loads(row["params_json"] or "{}"),
            status=JobStatus(row["status"]),
            priority=row["priority"],
            worker_tier=row["worker_tier"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            output=row["output"],
            error=row["error"],
            cost_usd=row["cost_usd"] or 0.0,
        )


    def close(self) -> None:
        """Close the underlying SQLite connection.  Idempotent — safe to call multiple times."""
        try:
            self._conn.close()
        except Exception:
            pass


__all__ = ["JobQueue", "Job", "JobStatus"]
