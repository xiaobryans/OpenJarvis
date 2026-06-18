"""US15/US16 context caching hooks for stable workbench instructions and repo maps."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

_DEFAULT_DB = Path.home() / ".openjarvis" / "workbench_context_cache.db"

# Stable keys suitable for prompt/context reuse across coding sessions.
CACHE_KEYS = (
    "repo_map",
    "policy_governance",
    "tool_schemas",
    "architecture_docs",
    "validation_profiles",
)


class ContextCache:
    """SQLite-backed cache for stable workbench context blobs."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS context_cache (
                cache_key TEXT NOT NULL,
                repo_path TEXT NOT NULL DEFAULT '.',
                content_hash TEXT NOT NULL,
                payload TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (cache_key, repo_path)
            );
        """)
        self._conn.commit()

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def get(self, cache_key: str, repo_path: str = ".") -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT payload, content_hash, updated_at FROM context_cache "
            "WHERE cache_key=? AND repo_path=?",
            (cache_key, repo_path),
        ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row[0])
        except json.JSONDecodeError:
            return None
        return {
            "cache_key": cache_key,
            "repo_path": repo_path,
            "content_hash": row[1],
            "updated_at": row[2],
            "payload": payload,
        }

    def put(self, cache_key: str, payload: Any, repo_path: str = ".") -> Dict[str, Any]:
        content = json.dumps(payload, sort_keys=True, default=str)
        content_hash = self._hash(content)
        now = time.time()
        self._conn.execute(
            """INSERT INTO context_cache (cache_key, repo_path, content_hash, payload, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(cache_key, repo_path) DO UPDATE SET
                 content_hash=excluded.content_hash,
                 payload=excluded.payload,
                 updated_at=excluded.updated_at""",
            (cache_key, repo_path, content_hash, content, now),
        )
        self._conn.commit()
        return {"cache_key": cache_key, "repo_path": repo_path, "content_hash": content_hash, "updated_at": now}

    def invalidate(self, cache_key: str, repo_path: str = ".") -> bool:
        cur = self._conn.execute(
            "DELETE FROM context_cache WHERE cache_key=? AND repo_path=?",
            (cache_key, repo_path),
        )
        self._conn.commit()
        return cur.rowcount > 0


def warm_repo_map_cache(repo_path: str = ".", cache: Optional[ContextCache] = None) -> Dict[str, Any]:
    """Cache repo map for reuse in planning prompts."""
    from openjarvis.workbench.repo_index import build_repo_index

    c = cache or ContextCache()
    index = build_repo_index(repo_path)
    payload = index.to_dict()
    meta = c.put("repo_map", payload, repo_path=repo_path)
    return {"ok": True, "meta": meta, "file_count": len(index.files)}


__all__ = ["ContextCache", "CACHE_KEYS", "warm_repo_map_cache"]
