"""Cost ledger for Jarvis Coding Workbench — per-task and per-session tracking.

Tracks:
  - Cost per subtask/job
  - Cost per session (top-level coding task)
  - Worker tier breakdowns (local, cloud-cheap, cloud-high-trust)
  - Running totals
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_cost.db"

# Approximate model cost tiers (USD per 1K tokens, blended input+output estimate)
MODEL_COST_TIERS: Dict[str, float] = {
    "local": 0.0,
    "qwen": 0.0001,
    "deepseek": 0.00014,
    "gemini-flash": 0.00015,
    "gemini-pro": 0.00035,
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.00250,
    "claude-haiku": 0.00025,
    "claude-sonnet": 0.00300,
    "claude-opus": 0.01500,
}


@dataclass
class CostEntry:
    id: str
    session_id: str
    task_id: str
    job_id: str
    worker_tier: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    description: str
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "job_id": self.job_id,
            "worker_tier": self.worker_tier,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "description": self.description,
            "created_at": self.created_at,
        }


class CostLedger:
    """SQLite-backed cost ledger for workbench tasks."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS workbench_cost (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                job_id TEXT NOT NULL DEFAULT '',
                worker_tier TEXT NOT NULL DEFAULT 'local',
                model TEXT NOT NULL DEFAULT 'local',
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0.0,
                description TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_cost_session ON workbench_cost (session_id);
            CREATE INDEX IF NOT EXISTS idx_cost_task ON workbench_cost (task_id);
        """)
        self._conn.commit()

    @staticmethod
    def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in USD for a model call."""
        key = model.lower()
        rate = 0.0
        for tier_key, tier_rate in MODEL_COST_TIERS.items():
            if tier_key in key:
                rate = tier_rate
                break
        total_tokens = input_tokens + output_tokens
        return round((total_tokens / 1000) * rate, 8)

    def record(
        self,
        session_id: str,
        task_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        description: str = "",
        job_id: str = "",
        worker_tier: str = "local",
    ) -> CostEntry:
        entry_id = uuid.uuid4().hex[:16]
        now = time.time()
        cost_usd = self.estimate_cost(model, input_tokens, output_tokens)
        self._conn.execute(
            """INSERT INTO workbench_cost
               (id, session_id, task_id, job_id, worker_tier, model,
                input_tokens, output_tokens, cost_usd, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, session_id, task_id, job_id, worker_tier, model,
             input_tokens, output_tokens, cost_usd, description, now),
        )
        self._conn.commit()
        return CostEntry(
            id=entry_id,
            session_id=session_id,
            task_id=task_id,
            job_id=job_id,
            worker_tier=worker_tier,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            description=description,
            created_at=now,
        )

    def session_total(self, session_id: str) -> Dict[str, Any]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_cost WHERE session_id=?", (session_id,)
        ).fetchall()
        total_usd = sum(r["cost_usd"] for r in rows)
        total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in rows)
        by_tier: Dict[str, float] = {}
        for r in rows:
            tier = r["worker_tier"]
            by_tier[tier] = by_tier.get(tier, 0.0) + r["cost_usd"]
        return {
            "session_id": session_id,
            "total_usd": round(total_usd, 6),
            "total_tokens": total_tokens,
            "entry_count": len(rows),
            "by_tier": {k: round(v, 6) for k, v in by_tier.items()},
        }

    def task_total(self, task_id: str) -> Dict[str, Any]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_cost WHERE task_id=?", (task_id,)
        ).fetchall()
        total_usd = sum(r["cost_usd"] for r in rows)
        total_tokens = sum(r["input_tokens"] + r["output_tokens"] for r in rows)
        return {
            "task_id": task_id,
            "total_usd": round(total_usd, 6),
            "total_tokens": total_tokens,
            "entry_count": len(rows),
        }

    def list_entries(self, session_id: str) -> List[CostEntry]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_cost WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_recent(self, limit: int = 50) -> List[CostEntry]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_cost ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> CostEntry:
        return CostEntry(
            id=row["id"],
            session_id=row["session_id"],
            task_id=row["task_id"],
            job_id=row["job_id"] or "",
            worker_tier=row["worker_tier"],
            model=row["model"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cost_usd=row["cost_usd"],
            description=row["description"],
            created_at=row["created_at"],
        )


__all__ = ["CostLedger", "CostEntry", "MODEL_COST_TIERS"]
