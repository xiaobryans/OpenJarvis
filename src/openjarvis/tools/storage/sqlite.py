"""SQLite/FTS5 memory backend — zero-dependency default.

Uses the native Rust accelerator when it is built into the venv; otherwise
falls back to a pure-Python implementation built on the stdlib ``sqlite3``
module's FTS5 + bm25 (available in CPython's bundled SQLite). Both paths persist
to the same on-disk database and present the identical ``MemoryBackend``
interface, so memory works with or without the Rust extension — there is no
hard Rust dependency.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.events import EventType, get_event_bus
from openjarvis.core.registry import MemoryRegistry
from openjarvis.tools.storage._stubs import (
    MemoryBackend,
    MemoryBackendUnavailable,
    RetrievalResult,
)

logger = logging.getLogger("openjarvis.memory")


def _check_fts5(conn: sqlite3.Connection) -> bool:
    """Return True if the SQLite build includes FTS5."""
    try:
        opts = conn.execute("PRAGMA compile_options").fetchall()
        return any("FTS5" in o[0].upper() for o in opts)
    except sqlite3.Error:
        return False


def _fts_match_query(query: str) -> str:
    """Build a safe FTS5 MATCH expression from arbitrary user text.

    FTS5 MATCH has its own syntax (quotes, AND/OR/NEAR, column filters, ``*``),
    so raw user input can raise ``sqlite3.OperationalError``. We tokenize into
    alphanumeric terms, double-quote each (FTS5 string literals), and OR them
    so any term can match.
    """
    import re

    terms = re.findall(r"\w+", query.lower())
    if not terms:
        return ""
    return " OR ".join(f'"{t}"' for t in terms)


class _PyFTSImpl:
    """Pure-Python FTS5 memory engine mirroring the Rust impl's method surface.

    Method signatures intentionally match ``openjarvis_rust.SQLiteMemory`` so
    :class:`SQLiteMemory` can call ``self._impl`` uniformly regardless of which
    backend is active. ``retrieve`` returns a JSON string in the same shape the
    Rust path emits, so ``retrieval_results_from_json`` parses both identically.
    """

    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        if not _check_fts5(self._conn):
            raise MemoryBackendUnavailable(
                "Pure-Python memory needs an SQLite build with FTS5 (CPython "
                "bundles it; this interpreter's SQLite lacks it)."
            )
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id         TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                source     TEXT NOT NULL DEFAULT '',
                metadata   TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_pyfts
            USING fts5(doc_id UNINDEXED, content, source,
                       tokenize='porter unicode61');
            """
        )
        self._conn.commit()

    def store(self, content: str, source: str = "", meta_json: Optional[str] = None) -> str:
        # Match the Rust impl's id format (canonical 36-char hyphenated UUID).
        doc_id = str(uuid.uuid4())
        with self._lock:
            self._conn.execute(
                "INSERT INTO documents(id, content, source, metadata, created_at) "
                "VALUES (?,?,?,?,?)",
                (doc_id, content, source or "", meta_json or "{}", time.time()),
            )
            self._conn.execute(
                "INSERT INTO documents_pyfts(doc_id, content, source) VALUES (?,?,?)",
                (doc_id, content, source or ""),
            )
            self._conn.commit()
        return doc_id

    def retrieve(self, query: str, top_k: int = 5) -> str:
        match = _fts_match_query(query)
        if not match:
            return "[]"
        with self._lock:
            try:
                rows = self._conn.execute(
                    "SELECT f.doc_id, f.content, f.source, "
                    "       bm25(documents_pyfts) AS rank, d.metadata "
                    "FROM documents_pyfts f "
                    "LEFT JOIN documents d ON d.id = f.doc_id "
                    "WHERE documents_pyfts MATCH ? "
                    "ORDER BY rank LIMIT ?",
                    (match, int(top_k)),
                ).fetchall()
            except sqlite3.OperationalError:
                return "[]"
        items = []
        for _doc_id, content, source, rank, metadata in rows:
            # bm25 returns smaller (more negative) = better; map to a positive
            # relevance score in (0, 1] while preserving the query's ordering.
            score = 1.0 / (1.0 + abs(float(rank)))
            items.append(
                {
                    "content": content,
                    "score": score,
                    "source": source or "",
                    "metadata": metadata or "{}",
                }
            )
        return json.dumps(items)

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self._conn.execute("DELETE FROM documents_pyfts WHERE doc_id = ?", (doc_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def clear(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM documents")
            self._conn.execute("DELETE FROM documents_pyfts")
            self._conn.commit()

    def count(self) -> int:
        with self._lock:
            return int(
                self._conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            )


@MemoryRegistry.register("sqlite")
class SQLiteMemory(MemoryBackend):
    """Full-text search memory backend using SQLite FTS5.

    Uses the built-in ``sqlite3`` module — no extra dependencies.
    """

    backend_id: str = "sqlite"

    def __init__(self, db_path: str | Path = "") -> None:
        if not db_path:
            from openjarvis.core.config import DEFAULT_CONFIG_DIR

            db_path = str(DEFAULT_CONFIG_DIR / "memory.db")

        self._db_path = str(db_path)

        from openjarvis._rust_bridge import get_rust_module

        # Prefer the native Rust accelerator when it is built into the venv.
        # When it is absent, fall back to the pure-Python FTS5 engine rather
        # than failing — memory must work with or without the extension (no
        # hard Rust dependency). Both paths expose the same ``self._impl``
        # method surface, so the rest of this class is backend-agnostic.
        try:
            _rust = get_rust_module()
            self._impl = _rust.SQLiteMemory(self._db_path)
            self._pure_python = False
        except ImportError:
            logger.info(
                "Native openjarvis_rust extension not present; using the "
                "pure-Python FTS5 memory engine for '%s'.",
                self._db_path,
            )
            self._impl = _PyFTSImpl(self._db_path)
            self._pure_python = True
        # Backward-compat alias: existing code/tests may reference _rust_impl.
        self._rust_impl = self._impl
        self._conn = None  # type: ignore[assignment]

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                id       TEXT PRIMARY KEY,
                content  TEXT NOT NULL,
                source   TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
            USING fts5(
                content,
                source,
                tokenize='porter unicode61'
            );
        """)

    def store(
        self,
        content: str,
        *,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist *content* and return a unique document id."""
        meta_json = json.dumps(metadata) if metadata else None
        doc_id = self._rust_impl.store(content, source, meta_json)
        bus = get_event_bus()
        bus.publish(
            EventType.MEMORY_STORE,
            {
                "backend": self.backend_id,
                "doc_id": doc_id,
                "source": source,
            },
        )
        return doc_id

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        **kwargs: Any,
    ) -> List[RetrievalResult]:
        """Search via FTS5 MATCH with BM25 ranking — always via Rust backend."""
        if not query.strip():
            return []

        from openjarvis._rust_bridge import retrieval_results_from_json

        results = retrieval_results_from_json(
            self._rust_impl.retrieve(query, top_k),
        )
        bus = get_event_bus()
        bus.publish(
            EventType.MEMORY_RETRIEVE,
            {
                "backend": self.backend_id,
                "query": query,
                "num_results": len(results),
            },
        )
        return results

    def delete(self, doc_id: str) -> bool:
        """Delete a document by id — always via Rust backend."""
        return self._rust_impl.delete(doc_id)

    def clear(self) -> None:
        """Remove all stored documents — always via Rust backend."""
        self._rust_impl.clear()

    def count(self) -> int:
        """Return the number of stored documents — always via Rust backend."""
        return self._rust_impl.count()

    def close(self) -> None:
        """Close the database connection."""
        pass


__all__ = ["SQLiteMemory"]
