"""Distilled Memory Layer — durable summaries, patterns, and decisions.

Raw/archive memory stores individual events and observations.
Distilled memory stores synthesised, higher-level knowledge derived from raw
entries: learned patterns, accepted decisions, preference summaries, etc.

Design:
  - Separate SQLite table (`distilled_entries`) in the same DB file as raw
    memory.  No new file path needed.
  - Durable: survives process restarts, new instances.
  - Reloadable: fresh DistilledMemory(db_path) reads the same data.
  - Source-linked: each distilled entry records which raw entry_ids contributed.
  - No model calls required to write distilled entries — callers synthesise
    and pass the content.

What is NOT in this sprint:
  - Automatic distillation from raw entries (planned, not yet implemented).
  - Semantic deduplication of distilled entries (planned).
  - Approval workflow before accepting a distilled entry (planned).
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

_DEFAULT_DB = Path.home() / ".jarvis" / "memory.db"

DISTILLED_KINDS = frozenset({
    "summary",    # compressed summary of many events
    "decision",   # Bryan-level decision now stored as durable truth
    "pattern",    # recurring behaviour/outcome pattern
    "preference", # explicit preference (model choice, workflow, style)
    "lesson",     # lesson learned from a mistake or rejected plan
})


@dataclass
class DistilledEntry:
    """A single distilled memory entry.

    Fields
    ------
    entry_id        Unique ID
    content         The distilled summary/pattern/decision
    kind            See DISTILLED_KINDS
    project_id      Associated project ('' for global)
    namespace       Logical namespace, e.g. 'distilled:decisions'
    source_ids      Raw memory entry_ids that contributed to this distillation
    tags            Search tags
    confidence      0.0–1.0
    created_at      Unix timestamp
    updated_at      Unix timestamp (updated on edit)
    """

    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    content: str = ""
    kind: str = "summary"
    project_id: str = ""
    namespace: str = "distilled"
    source_ids: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "kind": self.kind,
            "project_id": self.project_id,
            "namespace": self.namespace,
            "source_ids": list(self.source_ids),
            "tags": list(self.tags),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class DistilledMemory:
    """Durable distilled memory — summaries, decisions, and patterns.

    Uses the same SQLite file as JarvisMemory (separate table).
    All instances sharing the same db_path share the same data.
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
                CREATE TABLE IF NOT EXISTS distilled_entries (
                    entry_id    TEXT PRIMARY KEY,
                    content     TEXT NOT NULL,
                    kind        TEXT NOT NULL DEFAULT 'summary',
                    project_id  TEXT NOT NULL DEFAULT '',
                    namespace   TEXT NOT NULL DEFAULT 'distilled',
                    source_ids  TEXT NOT NULL DEFAULT '[]',
                    tags        TEXT NOT NULL DEFAULT '[]',
                    confidence  REAL NOT NULL DEFAULT 1.0,
                    created_at  REAL NOT NULL,
                    updated_at  REAL NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dist_project "
                "ON distilled_entries(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dist_kind "
                "ON distilled_entries(kind)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_dist_ns "
                "ON distilled_entries(namespace)"
            )
            conn.commit()

    def write(
        self,
        content: str,
        *,
        kind: str = "summary",
        project_id: str = "",
        namespace: str = "distilled",
        source_ids: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        entry_id: Optional[str] = None,
    ) -> DistilledEntry:
        """Write a distilled entry. Returns the created DistilledEntry."""
        if not content.strip():
            raise ValueError("Distilled memory content must not be empty.")
        if kind not in DISTILLED_KINDS:
            kind = "summary"
        now = time.time()
        entry = DistilledEntry(
            entry_id=entry_id or uuid.uuid4().hex[:16],
            content=content.strip(),
            kind=kind,
            project_id=project_id,
            namespace=namespace,
            source_ids=source_ids or [],
            tags=tags or [],
            confidence=max(0.0, min(1.0, confidence)),
            created_at=now,
            updated_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO distilled_entries
                    (entry_id, content, kind, project_id, namespace,
                     source_ids, tags, confidence, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.entry_id,
                    entry.content,
                    entry.kind,
                    entry.project_id,
                    entry.namespace,
                    json.dumps(entry.source_ids),
                    json.dumps(entry.tags),
                    entry.confidence,
                    entry.created_at,
                    entry.updated_at,
                ),
            )
            conn.commit()
        logger.debug(
            "Distilled entry written: kind=%s project=%s entry_id=%s",
            kind, project_id, entry.entry_id,
        )
        return entry

    def get(self, entry_id: str) -> Optional[DistilledEntry]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM distilled_entries WHERE entry_id=?", (entry_id,)
            ).fetchone()
        return self._row_to_entry(row) if row else None

    def search(
        self,
        query: str,
        *,
        project_id: Optional[str] = None,
        kind: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 20,
    ) -> List[DistilledEntry]:
        """Keyword search over distilled content + tags."""
        limit = max(1, min(limit, 200))
        terms = [t.strip().lower() for t in query.split() if t.strip()] or [query.lower()]
        term_parts = " OR ".join(
            ["(LOWER(content) LIKE ? OR LOWER(tags) LIKE ?)"] * len(terms)
        )
        clauses = [f"({term_parts})"]
        params: List[Any] = [val for t in terms for val in (f"%{t}%", f"%{t}%")]
        if project_id is not None:
            clauses.append("project_id=?")
            params.append(project_id)
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        if namespace is not None:
            clauses.append("namespace=?")
            params.append(namespace)
        where = " AND ".join(clauses)
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM distilled_entries WHERE {where} "
                "ORDER BY updated_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_by_kind(
        self,
        kind: str,
        *,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[DistilledEntry]:
        """List all distilled entries of a given kind."""
        limit = max(1, min(limit, 500))
        if project_id is not None:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM distilled_entries WHERE kind=? AND project_id=? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (kind, project_id, limit),
                ).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM distilled_entries WHERE kind=? "
                    "ORDER BY updated_at DESC LIMIT ?",
                    (kind, limit),
                ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def delete(self, entry_id: str) -> bool:
        """Hard-delete a distilled entry. Returns True if deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM distilled_entries WHERE entry_id=?", (entry_id,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def count(
        self,
        *,
        project_id: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> int:
        """Return count of distilled entries matching filters."""
        clauses: List[str] = []
        params: List[Any] = []
        if project_id is not None:
            clauses.append("project_id=?")
            params.append(project_id)
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM distilled_entries {where}", params
            ).fetchone()
        return row[0] if row else 0

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> DistilledEntry:
        try:
            source_ids = json.loads(row["source_ids"] or "[]")
        except Exception:
            source_ids = []
        try:
            tags = json.loads(row["tags"] or "[]")
        except Exception:
            tags = []
        return DistilledEntry(
            entry_id=row["entry_id"],
            content=row["content"],
            kind=row["kind"],
            project_id=row["project_id"] or "",
            namespace=row["namespace"] or "distilled",
            source_ids=source_ids,
            tags=tags,
            confidence=row["confidence"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


__all__ = ["DistilledEntry", "DistilledMemory", "DISTILLED_KINDS"]
