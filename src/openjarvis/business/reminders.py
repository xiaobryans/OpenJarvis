"""Smart reminders (3F) — SQLite-backed, with light relative-time parsing.

"remind me about X tomorrow" / "in 2 hours" / "in 30 minutes". Due reminders are
surfaced on the morning briefing and via the reminder tool. Pure parsing is
unit-testable; storage is scoped to an explicit db path.
"""

from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB = Path.home() / ".openjarvis" / "reminders.db"

_REL_UNITS = {"minute": 60, "min": 60, "hour": 3600, "hr": 3600, "day": 86400, "week": 604800}


def parse_when(text: str, now: Optional[float] = None) -> Optional[float]:
    """Parse a relative time phrase to an absolute epoch, or None if unparseable.

    Handles: 'in N minutes/hours/days/weeks', 'tomorrow' (+1 day), 'tonight'
    (today 20:00-ish => +6h heuristic), 'next week' (+7 days).
    """
    now = now if now is not None else time.time()
    t = (text or "").lower().strip()
    m = re.search(r"in\s+(\d+)\s*(minute|min|hour|hr|day|week)s?", t)
    if m:
        return now + int(m.group(1)) * _REL_UNITS[m.group(2)]
    if "tomorrow" in t:
        return now + 86400
    if "next week" in t:
        return now + 7 * 86400
    if "tonight" in t:
        return now + 6 * 3600
    if "in an hour" in t:
        return now + 3600
    return None


@dataclass
class ReminderStore:
    db_path: Path = DEFAULT_DB

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS reminders("
                "id TEXT PRIMARY KEY, text TEXT, due_at REAL, created_at REAL, done INTEGER DEFAULT 0)"
            )

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def add(self, text: str, *, when: str = "", due_at: Optional[float] = None,
            now: Optional[float] = None) -> Dict[str, Any]:
        now = now if now is not None else time.time()
        due = due_at if due_at is not None else parse_when(when or text, now)
        rid = f"rem-{uuid.uuid4().hex[:8]}"
        with self._conn() as c:
            c.execute("INSERT INTO reminders(id,text,due_at,created_at,done) VALUES(?,?,?,?,0)",
                      (rid, text.strip(), due, now))
        return {"id": rid, "text": text.strip(), "due_at": due}

    def due(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        now = now if now is not None else time.time()
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM reminders WHERE done=0 AND due_at IS NOT NULL AND due_at<=? ORDER BY due_at", (now,)
            ).fetchall()
        return [dict(r) for r in rows]

    def pending(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute("SELECT * FROM reminders WHERE done=0 ORDER BY COALESCE(due_at, 1e18)").fetchall()
        return [dict(r) for r in rows]

    def complete(self, rid: str) -> bool:
        with self._conn() as c:
            cur = c.execute("UPDATE reminders SET done=1 WHERE id=?", (rid,))
            return cur.rowcount > 0


__all__ = ["ReminderStore", "parse_when", "DEFAULT_DB"]
