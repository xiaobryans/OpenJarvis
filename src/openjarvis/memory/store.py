"""Jarvis Memory Store — SQLite-backed, project-scoped memory foundation.

Memory scopes:
  - global            Bryan/global memory (cross-project)
  - project:<id>      Project-specific memory (e.g. project:omnix)
  - mission:<id>      Mission-scoped memory
  - agent:<id>        Agent-scoped memory
  - tool:<id>         Tool execution memory
  - skill:<id>        Skill usage memory

Memory kinds (raw/archive layer):
  - event             Something that happened (deployment, bug, outage)
  - decision          Accepted/rejected decision or preference
  - preference        Bryan's stated preference
  - casual_note       Informal note or thought
  - rejected_plan     Plan that was considered and rejected
  - observation       Source-linked observation from agent/tool
  - mistake           Mistake made and documented
  - temporary_thought Short-lived context note (may expire)

Memory status:
  - active            Current, valid entry
  - archived          Older entry, preserved for history
  - deprecated        Superseded by newer information
  - deleted           Soft-deleted (excluded from normal retrieval)

Governance:
  - No secrets in memory (sensitive keys are scrubbed on write)
  - Project memories isolated by project_id/namespace
  - Global Bryan memory separate from project memory
  - OMNIX is project_id='omnix', not hardcoded as the only project

Migration path:
  - This is a local SQLite store (~/.jarvis/memory.db)
  - Future sprint can migrate to a vector DB or cloud backend
  - The JarvisMemory API surface is designed to be backend-agnostic
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

_SENSITIVE_KEYS = frozenset({
    "token", "secret", "password", "api_key", "auth", "credential",
    "private_key", "access_key", "bot_token", "chat_id", "key",
    "bearer", "authorization",
})

_SENSITIVE_VALUE_PATTERNS = [
    "xoxb-", "xoxp-",  # Slack tokens
    "sk-",             # OpenAI keys
    "ghp_", "gho_",    # GitHub tokens
    "eyJ",             # JWT (may contain sensitive data)
]


def _looks_like_secret(value: str) -> bool:
    """Heuristic: does this string look like a credential?"""
    if not isinstance(value, str):
        return False
    v = value.strip()
    for prefix in _SENSITIVE_VALUE_PATTERNS:
        if v.startswith(prefix) and len(v) > 20:
            return True
    return False


def _scrub_content(content: str) -> str:
    """Refuse to store content that looks like a raw secret."""
    if _looks_like_secret(content):
        raise ValueError(
            "Memory write refused: content appears to contain a raw secret/token. "
            "Scrub credentials before writing to memory."
        )
    return content


def _scrub_tags(tags: List[str]) -> List[str]:
    return [t for t in tags if not _looks_like_secret(t)]


# ---------------------------------------------------------------------------
# MemoryEntry
# ---------------------------------------------------------------------------


MEMORY_KINDS = frozenset({
    "event", "decision", "preference", "casual_note",
    "rejected_plan", "observation", "mistake", "temporary_thought",
})
MEMORY_STATUSES = frozenset({"active", "archived", "deprecated", "deleted"})


@dataclass
class MemoryEntry:
    """A single persisted memory entry.

    Fields
    ------
    entry_id        Unique ID
    namespace       Scope identifier (e.g. 'global', 'project:omnix')
    content         The actual memory content (scrubbed of secrets)
    source          Where this memory came from (e.g. 'tool', 'agent:manager')
    project_id      Associated project ('' for global memories)
    mission_id      Associated mission (optional)
    agent_id        Associated agent (optional)
    tags            List of string tags for search
    confidence      0.0–1.0 confidence/evidence weight
    created_at      Unix timestamp
    kind            Memory kind — see MEMORY_KINDS
    status          Entry lifecycle status — see MEMORY_STATUSES
    expires_at      Optional Unix timestamp after which entry is considered stale
    """

    entry_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    namespace: str = "global"
    content: str = ""
    source: str = ""
    project_id: str = ""
    mission_id: Optional[str] = None
    agent_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: float = field(default_factory=time.time)
    kind: str = "event"
    status: str = "active"
    expires_at: Optional[float] = None

    def is_expired(self) -> bool:
        """Return True if expires_at is set and in the past."""
        return self.expires_at is not None and time.time() > self.expires_at

    def is_active(self) -> bool:
        """Return True if status is 'active' and not expired."""
        return self.status == "active" and not self.is_expired()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "namespace": self.namespace,
            "content": self.content,
            "source": self.source,
            "project_id": self.project_id,
            "mission_id": self.mission_id,
            "agent_id": self.agent_id,
            "tags": list(self.tags),
            "confidence": self.confidence,
            "created_at": self.created_at,
            "kind": self.kind,
            "status": self.status,
            "expires_at": self.expires_at,
        }


# ---------------------------------------------------------------------------
# JarvisMemory
# ---------------------------------------------------------------------------


class JarvisMemory:
    """Project-scoped SQLite memory store for Jarvis.

    Instances share the same database file. The API is intentionally simple
    to allow future backend substitution (vector DB, cloud, etc.).

    Key properties:
      - project memories isolated by namespace + project_id
      - global memories (project_id='') accessible across projects
      - OMNIX is project_id='omnix' — not the only valid project
      - no secrets stored (ValueError raised on detection)
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
                CREATE TABLE IF NOT EXISTS memory_entries (
                    entry_id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    project_id TEXT NOT NULL DEFAULT '',
                    mission_id TEXT,
                    agent_id TEXT,
                    tags TEXT NOT NULL DEFAULT '[]',
                    confidence REAL NOT NULL DEFAULT 1.0,
                    created_at REAL NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'event',
                    status TEXT NOT NULL DEFAULT 'active',
                    expires_at REAL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_namespace ON memory_entries(namespace)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_project ON memory_entries(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_created ON memory_entries(created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_status ON memory_entries(status)"
            )
            conn.commit()
        self._migrate_db()

    def _migrate_db(self) -> None:
        """Safe ALTER TABLE migrations for databases created before new columns existed."""
        new_columns = [
            ("kind", "TEXT NOT NULL DEFAULT 'event'"),
            ("status", "TEXT NOT NULL DEFAULT 'active'"),
            ("expires_at", "REAL"),
        ]
        with self._connect() as conn:
            for col_name, col_def in new_columns:
                try:
                    conn.execute(
                        f"ALTER TABLE memory_entries ADD COLUMN {col_name} {col_def}"
                    )
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # column already exists — normal for existing databases

    def write(
        self,
        namespace: str,
        content: str,
        *,
        source: str = "",
        tags: Optional[List[str]] = None,
        project_id: str = "",
        mission_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        confidence: float = 1.0,
        kind: str = "event",
        status: str = "active",
        expires_at: Optional[float] = None,
    ) -> MemoryEntry:
        """Write a memory entry. Raises ValueError if content looks like a secret."""
        content = _scrub_content(content)
        safe_tags = _scrub_tags(tags or [])
        if kind not in MEMORY_KINDS:
            kind = "event"
        if status not in MEMORY_STATUSES:
            status = "active"

        entry = MemoryEntry(
            namespace=namespace,
            content=content,
            source=source,
            project_id=project_id,
            mission_id=mission_id,
            agent_id=agent_id,
            tags=safe_tags,
            confidence=max(0.0, min(1.0, confidence)),
            kind=kind,
            status=status,
            expires_at=expires_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_entries
                    (entry_id, namespace, content, source, project_id,
                     mission_id, agent_id, tags, confidence, created_at,
                     kind, status, expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.entry_id,
                    entry.namespace,
                    entry.content,
                    entry.source,
                    entry.project_id,
                    entry.mission_id,
                    entry.agent_id,
                    json.dumps(entry.tags),
                    entry.confidence,
                    entry.created_at,
                    entry.kind,
                    entry.status,
                    entry.expires_at,
                ),
            )
            conn.commit()
        logger.debug(
            "Memory written: ns=%s project=%s kind=%s entry_id=%s",
            namespace, project_id, kind, entry.entry_id,
        )
        return entry

    def store(
        self,
        namespace: str,
        content: str,
        *,
        source: str = "",
        tags: Optional[List[str]] = None,
        project_id: str = "",
        mission_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        confidence: float = 1.0,
        kind: str = "event",
        status: str = "active",
        expires_at: Optional[float] = None,
        entry_id: Optional[str] = None,
    ) -> MemoryEntry:
        """Write a memory entry with optional caller-supplied entry_id.

        Used by memory_continuity proofs and tests that need deterministic IDs.
        Raises ValueError if content looks like a secret.
        """
        content = _scrub_content(content)
        safe_tags = _scrub_tags(tags or [])
        if kind not in MEMORY_KINDS:
            kind = "event"
        if status not in MEMORY_STATUSES:
            status = "active"

        entry = MemoryEntry(
            entry_id=entry_id or uuid.uuid4().hex[:16],
            namespace=namespace,
            content=content,
            source=source,
            project_id=project_id,
            mission_id=mission_id,
            agent_id=agent_id,
            tags=safe_tags,
            confidence=max(0.0, min(1.0, confidence)),
            kind=kind,
            status=status,
            expires_at=expires_at,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memory_entries
                    (entry_id, namespace, content, source, project_id,
                     mission_id, agent_id, tags, confidence, created_at,
                     kind, status, expires_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.entry_id,
                    entry.namespace,
                    entry.content,
                    entry.source,
                    entry.project_id,
                    entry.mission_id,
                    entry.agent_id,
                    json.dumps(entry.tags),
                    entry.confidence,
                    entry.created_at,
                    entry.kind,
                    entry.status,
                    entry.expires_at,
                ),
            )
            conn.commit()
        logger.debug(
            "Memory stored: ns=%s project=%s kind=%s entry_id=%s",
            namespace, project_id, kind, entry.entry_id,
        )
        return entry

    def delete(self, entry_id: str) -> bool:
        """Hard-delete a memory entry by entry_id. Returns True if deleted."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM memory_entries WHERE entry_id=?", (entry_id,)
            )
            conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.debug("Memory deleted: entry_id=%s", entry_id)
        return deleted

    def forget(self, entry_id: str) -> bool:
        """Governance: hard-delete entry. Alias for delete()."""
        return self.delete(entry_id)

    def update(
        self,
        entry_id: str,
        *,
        content: Optional[str] = None,
        status: Optional[str] = None,
        confidence: Optional[float] = None,
        tags: Optional[List[str]] = None,
        expires_at: Optional[float] = None,
    ) -> Optional["MemoryEntry"]:
        """Governance: update fields of an existing entry. Returns updated entry or None."""
        existing = self.get(entry_id)
        if existing is None:
            return None
        new_content = _scrub_content(content) if content is not None else existing.content
        new_status = status if (status in MEMORY_STATUSES) else existing.status
        new_confidence = max(0.0, min(1.0, confidence)) if confidence is not None else existing.confidence
        new_tags = json.dumps(_scrub_tags(tags)) if tags is not None else json.dumps(existing.tags)
        new_expires_at = expires_at if expires_at is not None else existing.expires_at

        with self._connect() as conn:
            conn.execute(
                """UPDATE memory_entries
                   SET content=?, status=?, confidence=?, tags=?, expires_at=?
                   WHERE entry_id=?""",
                (new_content, new_status, new_confidence, new_tags, new_expires_at, entry_id),
            )
            conn.commit()
        return self.get(entry_id)

    def count(
        self,
        *,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """Return count of entries matching the given filters."""
        clauses = []
        params: List[Any] = []
        if namespace is not None:
            clauses.append("namespace=?")
            params.append(namespace)
        if project_id is not None:
            clauses.append("project_id=?")
            params.append(project_id)
        if status is not None:
            clauses.append("status=?")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT COUNT(*) FROM memory_entries {where}", params
            ).fetchone()
        return row[0] if row else 0

    def search(
        self,
        query: str,
        *,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        kind: Optional[str] = None,
        exclude_deleted: bool = True,
        limit: int = 20,
    ) -> List[MemoryEntry]:
        """Keyword search over content + tags.

        Filters by namespace, project_id, status, and/or kind if provided.
        By default excludes deleted entries.
        Results ordered by recency (most recent first).
        """
        limit = max(1, min(limit, 200))
        # Build per-term OR clauses so "OMNIX deployment" matches entries that
        # contain either "omnix" or "deployment" (not requiring exact phrase).
        terms = [t.strip().lower() for t in query.split() if t.strip()] or [query.lower()]
        term_parts = " OR ".join(
            ["(LOWER(content) LIKE ? OR LOWER(tags) LIKE ?)"] * len(terms)
        )
        params: List[Any] = [val for t in terms for val in (f"%{t}%", f"%{t}%")]

        clauses = [f"({term_parts})"]

        if namespace is not None:
            clauses.append("namespace = ?")
            params.append(namespace)
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        elif exclude_deleted:
            clauses.append("status != 'deleted'")
        if kind is not None:
            clauses.append("kind = ?")
            params.append(kind)

        where = " AND ".join(clauses)
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM memory_entries WHERE {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()

        return [self._row_to_entry(r) for r in rows]

    def list_by_namespace(
        self,
        namespace: str,
        *,
        project_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """List entries in a namespace, optionally filtered by project_id."""
        limit = max(1, min(limit, 500))
        if project_id is not None:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM memory_entries WHERE namespace=? AND project_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (namespace, project_id, limit),
                ).fetchall()
        else:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM memory_entries WHERE namespace=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (namespace, limit),
                ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_namespaces(self) -> List[Dict[str, Any]]:
        """List all namespaces with entry counts."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT namespace, project_id, COUNT(*) as count "
                "FROM memory_entries GROUP BY namespace, project_id "
                "ORDER BY namespace"
            ).fetchall()
        return [
            {
                "namespace": r["namespace"],
                "project_id": r["project_id"],
                "count": r["count"],
            }
            for r in rows
        ]

    def get(self, entry_id: str) -> Optional[MemoryEntry]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM memory_entries WHERE entry_id=?", (entry_id,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        try:
            tags = json.loads(row["tags"] or "[]")
        except Exception:
            tags = []
        keys = row.keys()
        return MemoryEntry(
            entry_id=row["entry_id"],
            namespace=row["namespace"],
            content=row["content"],
            source=row["source"] or "",
            project_id=row["project_id"] or "",
            mission_id=row["mission_id"],
            agent_id=row["agent_id"],
            tags=tags,
            confidence=row["confidence"],
            created_at=row["created_at"],
            kind=row["kind"] if "kind" in keys else "event",
            status=row["status"] if "status" in keys else "active",
            expires_at=row["expires_at"] if "expires_at" in keys else None,
        )


__all__ = [
    "JarvisMemory",
    "MemoryEntry",
    "MEMORY_KINDS",
    "MEMORY_STATUSES",
]
