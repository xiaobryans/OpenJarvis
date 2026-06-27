"""VANTA self-improvement log — what VANTA built, fixed, researched, and what's
pending. SQLite-backed, surfaced by voice ("what did you improve this week",
"show change log", "what's pending") and on the Mission Control panel via
GET /v1/improvement-log.

Each entry: timestamp, category, description, outcome, initiator.
Categories: improvement | bug_fix | research | pending.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB = Path.home() / ".openjarvis" / "improvement_log.db"
CATEGORIES = ("improvement", "bug_fix", "research", "pending")


@dataclass
class ImprovementLog:
    db_path: Path = DEFAULT_DB

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS improvements("
                "id TEXT PRIMARY KEY, ts REAL, category TEXT, description TEXT, "
                "outcome TEXT, initiator TEXT)"
            )

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def add(self, category: str, description: str, *, outcome: str = "",
            initiator: str = "vanta", now: Optional[float] = None) -> Dict[str, Any]:
        category = category if category in CATEGORIES else "improvement"
        eid = f"imp-{uuid.uuid4().hex[:8]}"
        ts = now if now is not None else time.time()
        with self._conn() as c:
            c.execute(
                "INSERT INTO improvements(id,ts,category,description,outcome,initiator) VALUES(?,?,?,?,?,?)",
                (eid, ts, category, description.strip(), outcome.strip(), initiator.strip()),
            )
        return {"id": eid, "ts": ts, "category": category, "description": description.strip(),
                "outcome": outcome.strip(), "initiator": initiator.strip()}

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM improvements ORDER BY ts DESC LIMIT ?", (max(1, limit),)).fetchall()
        return [dict(r) for r in rows]

    def pending(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM improvements WHERE category='pending' ORDER BY ts DESC").fetchall()
        return [dict(r) for r in rows]

    def weekly_counts(self, now: Optional[float] = None) -> Dict[str, int]:
        """Counts per category over the last 7 days (for the Mission Control panel)."""
        since = (now if now is not None else time.time()) - 7 * 86400
        counts = {c: 0 for c in CATEGORIES}
        with self._conn() as c:
            for row in c.execute(
                "SELECT category, COUNT(*) n FROM improvements WHERE ts>=? GROUP BY category", (since,)
            ).fetchall():
                if row["category"] in counts:
                    counts[row["category"]] = row["n"]
        return counts


__all__ = ["ImprovementLog", "CATEGORIES", "DEFAULT_DB"]
