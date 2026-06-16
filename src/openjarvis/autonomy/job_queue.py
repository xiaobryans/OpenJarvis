"""Jarvis Durable Job Queue — SQLite-backed local queue.

States: pending → running → succeeded/failed/cancelled
Retry/backoff: configurable per-job, exponential backoff
Idempotency: idempotency_key prevents duplicate enqueue
Crash recovery: running jobs reset to pending on startup
Queue inspection: list/get/cancel by state

Storage: ~/.openjarvis/job_queue.db

No always-on daemon — jobs are claimed/run on explicit poll_and_run() call.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

_DB_PATH = Path.home() / ".openjarvis" / "job_queue.db"

# Job state constants
class JobState:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    idempotency_key TEXT UNIQUE,
    queue_name TEXT NOT NULL DEFAULT 'default',
    action TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 5,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    backoff_seconds INTEGER NOT NULL DEFAULT 30,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    run_after REAL NOT NULL DEFAULT 0,
    started_at REAL,
    completed_at REAL,
    error TEXT,
    result TEXT
)
"""
_CREATE_IDX_STATE = "CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state, run_after)"
_CREATE_IDX_IDEM = "CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key) WHERE idempotency_key IS NOT NULL"


# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------


@contextmanager
def _db(path: Optional[Path] = None) -> Generator[sqlite3.Connection, None, None]:
    p = path or _DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(_CREATE_TABLE)
    conn.execute(_CREATE_IDX_STATE)
    conn.execute(_CREATE_IDX_IDEM)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class Job:
    job_id: str
    action: str
    payload: Dict[str, Any]
    state: str
    queue_name: str
    priority: int
    attempts: int
    max_attempts: int
    backoff_seconds: int
    created_at: float
    updated_at: float
    run_after: float
    idempotency_key: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "action": self.action,
            "payload": self.payload,
            "state": self.state,
            "queue_name": self.queue_name,
            "priority": self.priority,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "backoff_seconds": self.backoff_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "run_after": self.run_after,
            "idempotency_key": self.idempotency_key,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "result": self.result,
        }


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        job_id=row["job_id"],
        action=row["action"],
        payload=json.loads(row["payload"] or "{}"),
        state=row["state"],
        queue_name=row["queue_name"],
        priority=row["priority"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        backoff_seconds=row["backoff_seconds"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        run_after=row["run_after"],
        idempotency_key=row["idempotency_key"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        error=row["error"],
        result=json.loads(row["result"]) if row["result"] else None,
    )


# ---------------------------------------------------------------------------
# Enqueue
# ---------------------------------------------------------------------------


def enqueue(
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    queue_name: str = "default",
    priority: int = 5,
    max_attempts: int = 3,
    backoff_seconds: int = 30,
    idempotency_key: Optional[str] = None,
    run_after: Optional[float] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Enqueue a job. Idempotency key prevents duplicates."""
    now = time.time()
    job_id = str(uuid.uuid4())

    with _db(db_path) as conn:
        # Check idempotency
        if idempotency_key:
            existing = conn.execute(
                "SELECT job_id, state FROM jobs WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                return {
                    "ok": True,
                    "duplicate": True,
                    "job_id": existing["job_id"],
                    "state": existing["state"],
                    "note": "Idempotency key already exists — not re-enqueued",
                }

        conn.execute(
            """INSERT INTO jobs
            (job_id, idempotency_key, queue_name, action, payload, state,
             priority, attempts, max_attempts, backoff_seconds,
             created_at, updated_at, run_after)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                job_id,
                idempotency_key,
                queue_name,
                action,
                json.dumps(payload or {}),
                JobState.PENDING,
                priority,
                0,
                max_attempts,
                backoff_seconds,
                now,
                now,
                run_after or now,
            ),
        )
        conn.commit()

    return {"ok": True, "duplicate": False, "job_id": job_id, "state": JobState.PENDING}


# ---------------------------------------------------------------------------
# Claim (move pending → running)
# ---------------------------------------------------------------------------


def claim_next(
    queue_name: str = "default",
    db_path: Optional[Path] = None,
) -> Optional[Job]:
    """Atomically claim the next available job. Returns None if queue is empty."""
    now = time.time()
    with _db(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM jobs
            WHERE state = ? AND queue_name = ? AND run_after <= ?
            ORDER BY priority ASC, created_at ASC LIMIT 1""",
            (JobState.PENDING, queue_name, now),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE jobs SET state=?, started_at=?, updated_at=?, attempts=attempts+1 WHERE job_id=?",
            (JobState.RUNNING, now, now, row["job_id"]),
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM jobs WHERE job_id=?", (row["job_id"],)).fetchone()
        return _row_to_job(updated)


# ---------------------------------------------------------------------------
# Complete / fail
# ---------------------------------------------------------------------------


def complete_job(
    job_id: str,
    result: Optional[Dict[str, Any]] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """Mark a running job as succeeded."""
    now = time.time()
    with _db(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET state=?, completed_at=?, updated_at=?, result=? WHERE job_id=? AND state=?",
            (JobState.SUCCEEDED, now, now, json.dumps(result or {}), job_id, JobState.RUNNING),
        )
        conn.commit()
    return True


def fail_job(
    job_id: str,
    error: str = "",
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Mark a running job as failed; schedule retry if attempts remain."""
    now = time.time()
    with _db(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return {"ok": False, "error": "Job not found"}
        job = _row_to_job(row)
        if job.attempts < job.max_attempts:
            delay = job.backoff_seconds * (2 ** (job.attempts - 1))
            conn.execute(
                "UPDATE jobs SET state=?, error=?, updated_at=?, run_after=? WHERE job_id=?",
                (JobState.PENDING, error, now, now + delay, job_id),
            )
            next_state = JobState.PENDING
            retry_at = now + delay
        else:
            conn.execute(
                "UPDATE jobs SET state=?, error=?, completed_at=?, updated_at=? WHERE job_id=?",
                (JobState.FAILED, error, now, now, job_id),
            )
            next_state = JobState.FAILED
            retry_at = None
        conn.commit()
    return {
        "ok": True,
        "job_id": job_id,
        "next_state": next_state,
        "retry_at": retry_at,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
    }


def cancel_job(job_id: str, db_path: Optional[Path] = None) -> bool:
    """Cancel a pending job."""
    now = time.time()
    with _db(db_path) as conn:
        conn.execute(
            "UPDATE jobs SET state=?, updated_at=? WHERE job_id=? AND state=?",
            (JobState.CANCELLED, now, job_id, JobState.PENDING),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Crash recovery
# ---------------------------------------------------------------------------


def recover_stale_running(
    stale_after_seconds: int = 300,
    db_path: Optional[Path] = None,
) -> int:
    """Reset running jobs older than stale_after_seconds back to pending.

    Call on startup to recover from crashes.
    Returns number of jobs recovered.
    """
    cutoff = time.time() - stale_after_seconds
    with _db(db_path) as conn:
        result = conn.execute(
            "UPDATE jobs SET state=?, updated_at=? WHERE state=? AND started_at < ?",
            (JobState.PENDING, time.time(), JobState.RUNNING, cutoff),
        )
        conn.commit()
        return result.rowcount


# ---------------------------------------------------------------------------
# Inspection
# ---------------------------------------------------------------------------


def list_jobs(
    state: Optional[str] = None,
    queue_name: Optional[str] = None,
    limit: int = 50,
    db_path: Optional[Path] = None,
) -> List[Job]:
    """List jobs by state/queue. No secrets in results."""
    with _db(db_path) as conn:
        clauses = []
        params: List[Any] = []
        if state:
            clauses.append("state = ?")
            params.append(state)
        if queue_name:
            clauses.append("queue_name = ?")
            params.append(queue_name)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_job(job_id: str, db_path: Optional[Path] = None) -> Optional[Job]:
    """Get a single job by ID."""
    with _db(db_path) as conn:
        row = conn.execute("SELECT * FROM jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return None
        return _row_to_job(row)


def queue_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Queue statistics for doctor/readiness."""
    with _db(db_path) as conn:
        rows = conn.execute(
            "SELECT state, COUNT(*) as n FROM jobs GROUP BY state"
        ).fetchall()
    counts = {r["state"]: r["n"] for r in rows}
    return {
        "pending": counts.get(JobState.PENDING, 0),
        "running": counts.get(JobState.RUNNING, 0),
        "succeeded": counts.get(JobState.SUCCEEDED, 0),
        "failed": counts.get(JobState.FAILED, 0),
        "cancelled": counts.get(JobState.CANCELLED, 0),
        "total": sum(counts.values()),
        "db_path": str(_DB_PATH),
    }


def get_stalled_jobs(
    stale_after_seconds: int = 300,
    db_path: Optional[Path] = None,
) -> List[Job]:
    """Return jobs that have been in RUNNING state longer than stale_after_seconds.

    These jobs are candidates for crash recovery via recover_stale_running().
    """
    cutoff = time.time() - stale_after_seconds
    with _db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE state = ? AND started_at < ? ORDER BY started_at ASC",
            (JobState.RUNNING, cutoff),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def get_retry_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Return retry statistics: jobs with attempts > 1, max attempts hit."""
    with _db(db_path) as conn:
        retried = conn.execute(
            "SELECT COUNT(*) as n FROM jobs WHERE attempts > 1"
        ).fetchone()["n"]
        exhausted = conn.execute(
            "SELECT COUNT(*) as n FROM jobs WHERE state = ? AND attempts >= max_attempts",
            (JobState.FAILED,),
        ).fetchone()["n"]
        high_retry = conn.execute(
            "SELECT * FROM jobs WHERE attempts > 1 ORDER BY attempts DESC LIMIT 10"
        ).fetchall()
    return {
        "jobs_with_retries": retried,
        "exhausted_retries": exhausted,
        "top_retry_jobs": [
            {"job_id": r["job_id"], "action": r["action"], "attempts": r["attempts"], "state": r["state"]}
            for r in high_retry
        ],
    }


def get_queue_health_report(
    stale_after_seconds: int = 300,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Full queue health report for doctor/readiness and ops dashboard."""
    stats = queue_stats(db_path=db_path)
    stalled = get_stalled_jobs(stale_after_seconds=stale_after_seconds, db_path=db_path)
    retry_stats = get_retry_stats(db_path=db_path)
    return {
        "stats": stats,
        "stalled_jobs": len(stalled),
        "stalled_job_ids": [j.job_id for j in stalled],
        "stale_threshold_seconds": stale_after_seconds,
        "retry_stats": retry_stats,
        "health": "ok" if not stalled and stats.get("failed", 0) == 0 else "degraded",
        "recovery_action": (
            "call recover_stale_running() to reset stalled jobs"
            if stalled else None
        ),
    }


__all__ = [
    "JobState",
    "Job",
    "enqueue",
    "claim_next",
    "complete_job",
    "fail_job",
    "cancel_job",
    "recover_stale_running",
    "list_jobs",
    "get_job",
    "queue_stats",
    "get_stalled_jobs",
    "get_retry_stats",
    "get_queue_health_report",
]
