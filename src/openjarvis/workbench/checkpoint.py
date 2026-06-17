"""Checkpoint store — task memory and accepted checkpoint persistence.

Persists:
  - Accepted checkpoints (verified milestones that don't need re-verification)
  - Task notes/memory (key facts about an ongoing coding task)
  - Blocker records (stop-on-blocker evidence)
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_checkpoints.db"


@dataclass
class Checkpoint:
    id: str
    session_id: str
    task_id: str
    label: str
    evidence: str
    verdict: str
    notes: Dict[str, Any]
    created_at: float
    is_blocker: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "label": self.label,
            "evidence": self.evidence,
            "verdict": self.verdict,
            "notes": self.notes,
            "created_at": self.created_at,
            "is_blocker": self.is_blocker,
        }


class CheckpointStore:
    """SQLite-backed task memory and checkpoint persistence."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS workbench_checkpoints (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                label TEXT NOT NULL,
                evidence TEXT NOT NULL DEFAULT '',
                verdict TEXT NOT NULL DEFAULT 'ACCEPT',
                notes_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                is_blocker INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_ckpt_session ON workbench_checkpoints (session_id);
            CREATE INDEX IF NOT EXISTS idx_ckpt_task ON workbench_checkpoints (task_id);

            CREATE TABLE IF NOT EXISTS workbench_task_memory (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_mem_task_key
                ON workbench_task_memory (task_id, key);
        """)
        self._conn.commit()

    def save_checkpoint(
        self,
        session_id: str,
        task_id: str,
        label: str,
        evidence: str,
        verdict: str = "ACCEPT",
        notes: Optional[Dict[str, Any]] = None,
        is_blocker: bool = False,
    ) -> Checkpoint:
        cp_id = uuid.uuid4().hex[:16]
        now = time.time()
        self._conn.execute(
            """INSERT INTO workbench_checkpoints
               (id, session_id, task_id, label, evidence, verdict, notes_json, created_at, is_blocker)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (cp_id, session_id, task_id, label, evidence, verdict,
             json.dumps(notes or {}), now, int(is_blocker)),
        )
        self._conn.commit()
        return Checkpoint(
            id=cp_id,
            session_id=session_id,
            task_id=task_id,
            label=label,
            evidence=evidence,
            verdict=verdict,
            notes=notes or {},
            created_at=now,
            is_blocker=is_blocker,
        )

    def list_checkpoints(self, session_id: str) -> List[Checkpoint]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_checkpoints WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_cp(r) for r in rows]

    def get_blockers(self, session_id: str) -> List[Checkpoint]:
        rows = self._conn.execute(
            "SELECT * FROM workbench_checkpoints WHERE session_id=? AND is_blocker=1 ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [self._row_to_cp(r) for r in rows]

    def set_memory(self, session_id: str, task_id: str, key: str, value: str) -> None:
        now = time.time()
        entry_id = uuid.uuid4().hex[:16]
        self._conn.execute(
            """INSERT INTO workbench_task_memory
               (id, session_id, task_id, key, value, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(task_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
            (entry_id, session_id, task_id, key, value, now, now),
        )
        self._conn.commit()

    def get_memory(self, task_id: str, key: str) -> Optional[str]:
        row = self._conn.execute(
            "SELECT value FROM workbench_task_memory WHERE task_id=? AND key=?",
            (task_id, key),
        ).fetchone()
        return row["value"] if row else None

    def get_all_memory(self, task_id: str) -> Dict[str, str]:
        rows = self._conn.execute(
            "SELECT key, value FROM workbench_task_memory WHERE task_id=?",
            (task_id,),
        ).fetchall()
        return {r["key"]: r["value"] for r in rows}

    @staticmethod
    def _row_to_cp(row: sqlite3.Row) -> Checkpoint:
        return Checkpoint(
            id=row["id"],
            session_id=row["session_id"],
            task_id=row["task_id"],
            label=row["label"],
            evidence=row["evidence"],
            verdict=row["verdict"],
            notes=json.loads(row["notes_json"] or "{}"),
            created_at=row["created_at"],
            is_blocker=bool(row["is_blocker"]),
        )


__all__ = ["CheckpointStore", "Checkpoint"]
