"""Tool Execution Log — SQLite-backed persistence of every tool execution attempt.

Every execution through ToolExecutionGateway is logged here regardless of outcome
(success / blocked / not_configured / failed).  No secrets are stored.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jarvis" / "tool_executions.db"


def _scrub_inputs(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Remove any keys that look like secrets from inputs before logging."""
    _SENSITIVE = frozenset({
        "token", "secret", "password", "api_key", "auth", "credential",
        "private_key", "access_key", "bot_token", "chat_id", "key",
    })
    return {
        k: "<redacted>" if any(s in k.lower() for s in _SENSITIVE) else v
        for k, v in inputs.items()
    }


# ---------------------------------------------------------------------------
# ToolExecutionResult
# ---------------------------------------------------------------------------


class ExecutionOutcome:
    SUCCESS = "success"
    BLOCKED = "blocked"
    NOT_CONFIGURED = "not_configured"
    FAILED = "failed"
    HARD_GATE = "hard_gate"


@dataclass
class ToolExecutionResult:
    """Structured result returned by ToolExecutionGateway."""

    tool_id: str
    outcome: str
    ok: bool
    output: Any = None
    error: str = ""
    error_type: str = ""
    governance_verdict: str = ""
    execution_ms: float = 0.0
    log_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    project_id: str = ""
    mission_id: Optional[str] = None
    task_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "tool_id": self.tool_id,
            "outcome": self.outcome,
            "ok": self.ok,
            "output": self.output,
            "error": self.error,
            "error_type": self.error_type,
            "governance_verdict": self.governance_verdict,
            "execution_ms": self.execution_ms,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# ToolExecutionLog — SQLite persistence
# ---------------------------------------------------------------------------


@dataclass
class ToolExecutionLogEntry:
    log_id: str
    tool_id: str
    outcome: str
    ok: bool
    inputs_scrubbed: Dict[str, Any]
    output_summary: str
    error: str
    error_type: str
    governance_verdict: str
    execution_ms: float
    project_id: str
    mission_id: Optional[str]
    task_id: Optional[str]
    created_at: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id": self.log_id,
            "tool_id": self.tool_id,
            "outcome": self.outcome,
            "ok": self.ok,
            "inputs_scrubbed": self.inputs_scrubbed,
            "output_summary": self.output_summary,
            "error": self.error,
            "error_type": self.error_type,
            "governance_verdict": self.governance_verdict,
            "execution_ms": self.execution_ms,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "task_id": self.task_id,
            "created_at": self.created_at,
        }


class ToolExecutionLog:
    """SQLite-backed log of every tool execution attempt.

    Database is created at ~/.jarvis/tool_executions.db by default.
    Each entry is scrubbed of secrets before write.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_executions (
                    log_id TEXT PRIMARY KEY,
                    tool_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    inputs_scrubbed TEXT NOT NULL DEFAULT '{}',
                    output_summary TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '',
                    error_type TEXT NOT NULL DEFAULT '',
                    governance_verdict TEXT NOT NULL DEFAULT '',
                    execution_ms REAL NOT NULL DEFAULT 0.0,
                    project_id TEXT NOT NULL DEFAULT '',
                    mission_id TEXT,
                    task_id TEXT,
                    created_at REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_te_tool_id ON tool_executions(tool_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_te_created ON tool_executions(created_at)"
            )
            conn.commit()

    def save(
        self,
        result: ToolExecutionResult,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist execution result. Scrubs secrets from inputs before write."""
        scrubbed = _scrub_inputs(inputs or {})
        output_summary = ""
        if result.output is not None:
            try:
                raw = json.dumps(result.output)
                output_summary = raw[:500]
            except Exception:
                output_summary = str(result.output)[:500]

        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_executions
                    (log_id, tool_id, outcome, ok, inputs_scrubbed, output_summary,
                     error, error_type, governance_verdict, execution_ms,
                     project_id, mission_id, task_id, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    result.log_id,
                    result.tool_id,
                    result.outcome,
                    1 if result.ok else 0,
                    json.dumps(scrubbed),
                    output_summary,
                    result.error,
                    result.error_type,
                    result.governance_verdict,
                    result.execution_ms,
                    result.project_id,
                    result.mission_id,
                    result.task_id,
                    result.created_at,
                ),
            )
            conn.commit()
        logger.debug(
            "Logged tool execution: tool=%s outcome=%s log_id=%s",
            result.tool_id, result.outcome, result.log_id,
        )

    def list_recent(self, limit: int = 50) -> List[ToolExecutionLogEntry]:
        limit = max(1, min(limit, 500))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_executions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_by_tool(self, tool_id: str, limit: int = 50) -> List[ToolExecutionLogEntry]:
        limit = max(1, min(limit, 500))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_executions WHERE tool_id=? ORDER BY created_at DESC LIMIT ?",
                (tool_id, limit),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_by_outcome(self, outcome: str, limit: int = 50) -> List[ToolExecutionLogEntry]:
        limit = max(1, min(limit, 500))
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tool_executions WHERE outcome=? ORDER BY created_at DESC LIMIT ?",
                (outcome, limit),
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> ToolExecutionLogEntry:
        try:
            inputs_scrubbed = json.loads(row["inputs_scrubbed"] or "{}")
        except Exception:
            inputs_scrubbed = {}
        return ToolExecutionLogEntry(
            log_id=row["log_id"],
            tool_id=row["tool_id"],
            outcome=row["outcome"],
            ok=bool(row["ok"]),
            inputs_scrubbed=inputs_scrubbed,
            output_summary=row["output_summary"] or "",
            error=row["error"] or "",
            error_type=row["error_type"] or "",
            governance_verdict=row["governance_verdict"] or "",
            execution_ms=row["execution_ms"] or 0.0,
            project_id=row["project_id"] or "",
            mission_id=row["mission_id"],
            task_id=row["task_id"],
            created_at=row["created_at"],
        )


__all__ = [
    "ExecutionOutcome",
    "ToolExecutionLog",
    "ToolExecutionLogEntry",
    "ToolExecutionResult",
]
