"""SQLite-backed stores + pure logic for Sprint 4 proactive intelligence."""

from __future__ import annotations

import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_DIR = Path.home() / ".openjarvis"


def _conn(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    return c


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# ── 4A — email triage classification (pure) ──────────────────────────────────
_NOISE_HINTS = ("unsubscribe", "newsletter", "promotion", "% off", "sale ends",
                "no-reply", "noreply", "view in browser", "deal", "coupon")
_URGENT_HINTS = ("urgent", "asap", "today", "immediately", "deadline", "overdue",
                 "action required", "final notice", "payment failed")
_IMPORTANT_HINTS = ("invoice", "contract", "meeting", "proposal", "quote",
                    "interview", "offer", "reply", "follow up", "client")


def classify_email(subject: str, sender: str = "", snippet: str = "") -> str:
    """Classify an email: URGENT | IMPORTANT | INFO | NOISE (4A)."""
    text = f"{subject} {sender} {snippet}".lower()
    if any(h in text for h in _NOISE_HINTS):
        return "NOISE"
    if any(h in text for h in _URGENT_HINTS):
        return "URGENT"
    if any(h in text for h in _IMPORTANT_HINTS):
        return "IMPORTANT"
    return "INFO"


# ── 4F — task extraction from conversation (pure) ────────────────────────────
_TASK_PATTERNS = [
    (re.compile(r"\bi need to\s+(.+)", re.I), "normal"),
    (re.compile(r"\bi should\s+(.+)", re.I), "normal"),
    (re.compile(r"\bremind me to\s+(.+)", re.I), "urgent"),
    (re.compile(r"\bdon'?t let me forget\s+(?:to\s+)?(.+)", re.I), "urgent"),
    (re.compile(r"\bi promised\s+\w+\s+(?:i'?d|i would|to)\s+(.+)", re.I), "normal"),
]


def extract_tasks(text: str) -> List[Dict[str, str]]:
    """Find implied tasks in an utterance (4F). Returns [{text, urgency}]."""
    out: List[Dict[str, str]] = []
    for pat, urgency in _TASK_PATTERNS:
        for m in pat.finditer(text or ""):
            task = m.group(1).strip().rstrip(".!?")
            # Trim at a clause boundary so we don't capture the whole sentence.
            task = re.split(r"\b(?:and then|but|because|so that)\b", task, 1)[0].strip()
            if task:
                out.append({"text": task, "urgency": urgency})
    return out


# ── 4F — task store ──────────────────────────────────────────────────────────
_OVERDUE = {"urgent": 86400, "normal": 3 * 86400, "long": 7 * 86400}


@dataclass
class TaskStore:
    db_path: Path = DB_DIR / "tasks.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, text TEXT, "
                      "urgency TEXT, done INTEGER DEFAULT 0, created_at REAL, source TEXT)")

    def add(self, text: str, *, urgency: str = "normal", source: str = "voice",
            now: Optional[float] = None) -> Dict[str, Any]:
        tid = _id("task")
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO tasks(id,text,urgency,done,created_at,source) VALUES(?,?,?,0,?,?)",
                      (tid, text.strip(), urgency, now or time.time(), source))
        return {"id": tid, "text": text.strip(), "urgency": urgency}

    def capture_from_text(self, text: str, *, now: Optional[float] = None) -> List[Dict[str, Any]]:
        return [self.add(t["text"], urgency=t["urgency"], now=now) for t in extract_tasks(text)]

    def pending(self) -> List[Dict[str, Any]]:
        with _conn(self.db_path) as c:
            return [dict(r) for r in c.execute("SELECT * FROM tasks WHERE done=0 ORDER BY created_at").fetchall()]

    def overdue(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        now = now or time.time()
        return [t for t in self.pending() if now - t["created_at"] >= _OVERDUE.get(t["urgency"], _OVERDUE["normal"])]

    def complete(self, query: str) -> bool:
        with _conn(self.db_path) as c:
            row = c.execute("SELECT id FROM tasks WHERE done=0 AND (id=? OR text LIKE ?) ORDER BY created_at LIMIT 1",
                            (query, f"%{query}%")).fetchone()
            if not row:
                return False
            c.execute("UPDATE tasks SET done=1 WHERE id=?", (row["id"],))
        return True


# ── 4C/4G — research queue + findings ────────────────────────────────────────
@dataclass
class ResearchStore:
    db_path: Path = DB_DIR / "research.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.executescript(
                "CREATE TABLE IF NOT EXISTS queue(id TEXT PRIMARY KEY, topic TEXT, processed INTEGER DEFAULT 0, created_at REAL);"
                "CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, topic TEXT, tag TEXT, summary TEXT, created_at REAL);"
            )

    def enqueue(self, topic: str, now: Optional[float] = None) -> Dict[str, Any]:
        qid = _id("rq")
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO queue(id,topic,processed,created_at) VALUES(?,?,0,?)", (qid, topic.strip(), now or time.time()))
        return {"id": qid, "topic": topic.strip()}

    def queue(self) -> List[Dict[str, Any]]:
        with _conn(self.db_path) as c:
            return [dict(r) for r in c.execute("SELECT * FROM queue WHERE processed=0 ORDER BY created_at").fetchall()]

    def mark_processed(self, qid: str) -> None:
        with _conn(self.db_path) as c:
            c.execute("UPDATE queue SET processed=1 WHERE id=?", (qid,))

    def add_finding(self, topic: str, summary: str, *, tag: str = "AI", now: Optional[float] = None) -> Dict[str, Any]:
        fid = _id("rf")
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO findings(id,topic,tag,summary,created_at) VALUES(?,?,?,?,?)",
                      (fid, topic.strip(), tag, summary.strip(), now or time.time()))
        return {"id": fid, "topic": topic, "tag": tag}

    def overnight(self, limit: int = 10) -> List[Dict[str, Any]]:
        with _conn(self.db_path) as c:
            return [dict(r) for r in c.execute("SELECT * FROM findings ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()]


# ── 4B — anomaly store ───────────────────────────────────────────────────────
@dataclass
class AnomalyStore:
    db_path: Path = DB_DIR / "anomalies.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS anomalies(id TEXT PRIMARY KEY, kind TEXT, "
                      "severity TEXT, description TEXT, created_at REAL)")

    def record(self, kind: str, description: str, *, severity: str = "info", now: Optional[float] = None) -> Dict[str, Any]:
        aid = _id("anom")
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO anomalies(id,kind,severity,description,created_at) VALUES(?,?,?,?,?)",
                      (aid, kind, severity, description.strip(), now or time.time()))
        return {"id": aid, "kind": kind, "severity": severity, "description": description.strip()}

    def recent(self, limit: int = 20, now: Optional[float] = None) -> List[Dict[str, Any]]:
        since = (now or time.time()) - 7 * 86400
        with _conn(self.db_path) as c:
            return [dict(r) for r in c.execute("SELECT * FROM anomalies WHERE created_at>=? ORDER BY created_at DESC LIMIT ?",
                                               (since, limit)).fetchall()]


# ── 4E — relationship check-ins ──────────────────────────────────────────────
_RELATION_DAYS = {"partner": 3, "brother": 5, "parents": 7, "client": 14}


@dataclass
class RelationshipStore:
    db_path: Path = DB_DIR / "relationships.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS people(name TEXT PRIMARY KEY, kind TEXT, "
                      "last_context TEXT, last_seen REAL)")

    def mention(self, name: str, *, kind: str = "client", context: str = "", now: Optional[float] = None) -> None:
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO people(name,kind,last_context,last_seen) VALUES(?,?,?,?) "
                      "ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, "
                      "last_context=COALESCE(NULLIF(excluded.last_context,''), people.last_context), "
                      "last_seen=excluded.last_seen",
                      (name.strip().lower(), kind, context.strip(), now or time.time()))

    def checkups(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """People overdue for a check-in, newest-context first (4E)."""
        now = now or time.time()
        out: List[Dict[str, Any]] = []
        with _conn(self.db_path) as c:
            for r in c.execute("SELECT * FROM people").fetchall():
                days = _RELATION_DAYS.get(r["kind"], 14)
                gap_days = (now - (r["last_seen"] or now)) / 86400
                if gap_days >= days:
                    ctx = r["last_context"] or ""
                    line = f"Haven't checked in with your {r['kind']} ({r['name']}) in {int(gap_days)} days"
                    if ctx:
                        line += f" — last you mentioned {ctx}"
                    out.append({"name": r["name"], "kind": r["kind"], "days": int(gap_days), "line": line + "."})
        return sorted(out, key=lambda x: -x["days"])


# ── 4A — email triage store ──────────────────────────────────────────────────
@dataclass
class EmailTriageStore:
    db_path: Path = DB_DIR / "email_triage.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS triage(id TEXT PRIMARY KEY, subject TEXT, "
                      "sender TEXT, category TEXT, created_at REAL)")

    def record(self, subject: str, sender: str = "", snippet: str = "",
               msg_id: str = "", now: Optional[float] = None) -> Dict[str, Any]:
        cat = classify_email(subject, sender, snippet)
        # Dedup on the Gmail message id when provided (re-runs every 30 min).
        eid = f"eml-{msg_id}" if msg_id else _id("eml")
        with _conn(self.db_path) as c:
            c.execute("INSERT OR IGNORE INTO triage(id,subject,sender,category,created_at) VALUES(?,?,?,?,?)",
                      (eid, subject.strip(), sender.strip(), cat, now or time.time()))
        return {"id": eid, "subject": subject.strip(), "category": cat}

    def actionable(self, now: Optional[float] = None) -> List[Dict[str, Any]]:
        """Only URGENT + IMPORTANT from the last day (noise filtered out)."""
        since = (now or time.time()) - 86400
        with _conn(self.db_path) as c:
            return [dict(r) for r in c.execute(
                "SELECT * FROM triage WHERE category IN ('URGENT','IMPORTANT') AND created_at>=? "
                "ORDER BY CASE category WHEN 'URGENT' THEN 0 ELSE 1 END, created_at DESC", (since,)).fetchall()]


# ── 4D — weekly summary store ────────────────────────────────────────────────
@dataclass
class WeeklySummaryStore:
    db_path: Path = DB_DIR / "weekly_summaries.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS summaries(id TEXT PRIMARY KEY, week_of TEXT, text TEXT, created_at REAL)")

    def save(self, week_of: str, text: str, now: Optional[float] = None) -> Dict[str, Any]:
        sid = _id("wk")
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO summaries(id,week_of,text,created_at) VALUES(?,?,?,?)",
                      (sid, week_of, text.strip(), now or time.time()))
        return {"id": sid, "week_of": week_of}

    def latest(self) -> Optional[Dict[str, Any]]:
        with _conn(self.db_path) as c:
            r = c.execute("SELECT * FROM summaries ORDER BY created_at DESC LIMIT 1").fetchone()
            return dict(r) if r else None


# ── 4H — behaviour pattern store ─────────────────────────────────────────────
@dataclass
class PatternStore:
    db_path: Path = DB_DIR / "behaviour_patterns.db"

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        with _conn(self.db_path) as c:
            c.execute("CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, hour INTEGER, "
                      "duration_s REAL, late_night INTEGER, created_at REAL)")

    def record_session(self, hour: int, duration_s: float, *, now: Optional[float] = None) -> None:
        with _conn(self.db_path) as c:
            c.execute("INSERT INTO sessions(id,hour,duration_s,late_night,created_at) VALUES(?,?,?,?,?)",
                      (_id("ses"), hour, duration_s, 1 if (0 <= hour < 5) else 0, now or time.time()))

    def insights(self) -> Dict[str, Any]:
        with _conn(self.db_path) as c:
            rows = c.execute("SELECT hour, duration_s, late_night FROM sessions").fetchall()
        if not rows:
            return {"sessions": 0, "most_active_hour": None, "avg_minutes": 0, "late_nights": 0}
        from collections import Counter
        hours = Counter(r["hour"] for r in rows)
        avg = sum(r["duration_s"] for r in rows) / len(rows) / 60
        return {
            "sessions": len(rows),
            "most_active_hour": hours.most_common(1)[0][0],
            "avg_minutes": round(avg, 1),
            "late_nights": sum(r["late_night"] for r in rows),
        }


__all__ = [
    "TaskStore", "ResearchStore", "AnomalyStore", "RelationshipStore",
    "EmailTriageStore", "WeeklySummaryStore", "PatternStore",
    "classify_email", "extract_tasks",
]
