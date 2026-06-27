"""SQLite-backed universal business store — quotes, jobs, clients, payments.

Powers Sprint 3 features 3A (quotes), 3B (jobs), 3C (clients), 3D (invoices).
All amounts are stored in whole cents to avoid float drift. Every public method
is deterministic and side-effect-scoped to the given db file, so the whole store
is unit-testable headlessly.
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_DB = Path.home() / ".openjarvis" / "business.db"

JOB_STATUSES = ("pending", "in_progress", "done", "paid", "cancelled")
OVERDUE_DAYS = 7


def _now() -> float:
    return time.time()


def _short_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def to_cents(amount: float | int | str) -> int:
    """Convert a dollar amount (number or '$1,234.50') to whole cents."""
    if isinstance(amount, (int, float)):
        return int(round(float(amount) * 100))
    s = str(amount).strip().replace("$", "").replace(",", "")
    return int(round(float(s or 0) * 100)) if s else 0


def from_cents(cents: int) -> str:
    return f"${cents / 100:,.2f}"


@dataclass
class BusinessStore:
    """Thin, well-typed wrapper around the business SQLite database."""

    db_path: Path = DEFAULT_DB

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def _init_schema(self) -> None:
        with self._conn() as c:
            c.executescript(
                """
                CREATE TABLE IF NOT EXISTS clients (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, contact TEXT,
                    notes TEXT, created_at REAL
                );
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY, client TEXT, description TEXT,
                    amount_cents INTEGER, timeline TEXT, terms TEXT,
                    created_at REAL
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, client TEXT, description TEXT,
                    price_cents INTEGER, status TEXT, created_at REAL,
                    updated_at REAL
                );
                CREATE TABLE IF NOT EXISTS payments (
                    id TEXT PRIMARY KEY, client TEXT, job_id TEXT,
                    amount_cents INTEGER, owed_cents INTEGER, paid INTEGER,
                    description TEXT, created_at REAL, due_at REAL
                );
                """
            )

    # ── 3C clients ───────────────────────────────────────────────────────────
    def add_client(self, name: str, contact: str = "", notes: str = "") -> Dict[str, Any]:
        cid = _short_id("cli")
        with self._conn() as c:
            c.execute(
                "INSERT INTO clients(id,name,contact,notes,created_at) VALUES(?,?,?,?,?)",
                (cid, name.strip(), contact.strip(), notes.strip(), _now()),
            )
        return {"id": cid, "name": name.strip(), "contact": contact, "notes": notes}

    def add_note(self, client: str, note: str) -> bool:
        with self._conn() as c:
            row = c.execute("SELECT id,notes FROM clients WHERE name=? COLLATE NOCASE", (client,)).fetchone()
            if not row:
                return False
            merged = (row["notes"] + "\n" if row["notes"] else "") + note.strip()
            c.execute("UPDATE clients SET notes=? WHERE id=?", (merged, row["id"]))
        return True

    def client_history(self, client: str) -> Dict[str, Any]:
        with self._conn() as c:
            cli = c.execute("SELECT * FROM clients WHERE name=? COLLATE NOCASE", (client,)).fetchone()
            jobs = c.execute("SELECT * FROM jobs WHERE client=? COLLATE NOCASE ORDER BY created_at DESC", (client,)).fetchall()
            quotes = c.execute("SELECT * FROM quotes WHERE client=? COLLATE NOCASE ORDER BY created_at DESC", (client,)).fetchall()
        return {
            "client": dict(cli) if cli else None,
            "jobs": [dict(r) for r in jobs],
            "quotes": [dict(r) for r in quotes],
        }

    # ── 3A quotes ────────────────────────────────────────────────────────────
    def create_quote(self, description: str, amount: float | str, *, client: str = "",
                      timeline: str = "", terms: str = "") -> Dict[str, Any]:
        qid = _short_id("q")
        cents = to_cents(amount)
        with self._conn() as c:
            c.execute(
                "INSERT INTO quotes(id,client,description,amount_cents,timeline,terms,created_at) VALUES(?,?,?,?,?,?,?)",
                (qid, client.strip(), description.strip(), cents, timeline.strip(), terms.strip(), _now()),
            )
        return {"id": qid, "client": client, "description": description,
                "amount": from_cents(cents), "timeline": timeline, "terms": terms}

    def list_quotes(self, *, client: str = "", limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as c:
            if client:
                rows = c.execute("SELECT * FROM quotes WHERE client=? COLLATE NOCASE ORDER BY created_at DESC LIMIT ?", (client, limit)).fetchall()
            else:
                rows = c.execute("SELECT * FROM quotes ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def render_quote(self, quote: Dict[str, Any], *, contact: str = "") -> str:
        """Render a professional plain-text quote."""
        lines = [
            "QUOTE", "=" * 32,
            f"Ref:        {quote['id']}",
            f"Client:     {quote.get('client') or '—'}",
            f"Job:        {quote.get('description', '')}",
            f"Estimate:   {quote.get('amount', '')}",
            f"Timeline:   {quote.get('timeline') or 'TBD'}",
            f"Terms:      {quote.get('terms') or '50% deposit, balance on completion'}",
        ]
        if contact:
            lines.append(f"Contact:    {contact}")
        return "\n".join(lines)

    # ── 3B jobs ──────────────────────────────────────────────────────────────
    def log_job(self, description: str, *, client: str = "", price: float | str = 0,
                status: str = "pending") -> Dict[str, Any]:
        jid = _short_id("job")
        status = status if status in JOB_STATUSES else "pending"
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO jobs(id,client,description,price_cents,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (jid, client.strip(), description.strip(), to_cents(price), status, now, now),
            )
        return {"id": jid, "client": client, "description": description,
                "price": from_cents(to_cents(price)), "status": status}

    def set_job_status(self, job_query: str, status: str) -> bool:
        if status not in JOB_STATUSES:
            return False
        with self._conn() as c:
            row = c.execute(
                "SELECT id FROM jobs WHERE id=? OR description LIKE ? COLLATE NOCASE ORDER BY created_at DESC LIMIT 1",
                (job_query, f"%{job_query}%"),
            ).fetchone()
            if not row:
                return False
            c.execute("UPDATE jobs SET status=?, updated_at=? WHERE id=?", (status, _now(), row["id"]))
        return True

    def list_jobs(self, *, status: str = "") -> List[Dict[str, Any]]:
        with self._conn() as c:
            if status:
                rows = c.execute("SELECT * FROM jobs WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
            else:
                rows = c.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    # ── 3D invoices / payments ───────────────────────────────────────────────
    def record_owed(self, client: str, amount: float | str, *, description: str = "",
                    job_id: str = "", due_days: int = 14) -> Dict[str, Any]:
        pid = _short_id("inv")
        cents = to_cents(amount)
        now = _now()
        with self._conn() as c:
            c.execute(
                "INSERT INTO payments(id,client,job_id,amount_cents,owed_cents,paid,description,created_at,due_at) "
                "VALUES(?,?,?,?,?,0,?,?,?)",
                (pid, client.strip(), job_id, cents, cents, description.strip(), now, now + due_days * 86400),
            )
        return {"id": pid, "client": client, "owed": from_cents(cents), "description": description}

    def mark_paid(self, client: str, amount: float | str = 0) -> bool:
        """Mark the client's outstanding balance paid (optionally a part amount)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM payments WHERE client=? COLLATE NOCASE AND paid=0 ORDER BY created_at", (client,)
            ).fetchall()
            if not rows:
                return False
            remaining = to_cents(amount) if amount else None
            for r in rows:
                if remaining is None:
                    c.execute("UPDATE payments SET paid=1, owed_cents=0 WHERE id=?", (r["id"],))
                    continue
                owed = r["owed_cents"]
                if remaining <= 0:
                    break
                pay = min(owed, remaining)
                new_owed = owed - pay
                c.execute("UPDATE payments SET owed_cents=?, paid=? WHERE id=?",
                          (new_owed, 1 if new_owed == 0 else 0, r["id"]))
                remaining -= pay
        return True

    def who_owes(self) -> List[Dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT client, SUM(owed_cents) owed, MIN(due_at) due FROM payments WHERE paid=0 GROUP BY client COLLATE NOCASE"
            ).fetchall()
        out = []
        now = _now()
        for r in rows:
            if (r["owed"] or 0) <= 0:
                continue
            overdue = bool(r["due"] and now > r["due"] + OVERDUE_DAYS * 86400)
            out.append({"client": r["client"], "owed": from_cents(r["owed"]),
                        "owed_cents": r["owed"], "overdue": overdue})
        return out

    # ── snapshot ─────────────────────────────────────────────────────────────
    def snapshot(self) -> Dict[str, Any]:
        """Business snapshot: active jobs, pending payment total, weekly done."""
        week_ago = _now() - 7 * 86400
        with self._conn() as c:
            active = c.execute("SELECT COUNT(*) n FROM jobs WHERE status IN ('pending','in_progress')").fetchone()["n"]
            done_week = c.execute("SELECT COUNT(*) n FROM jobs WHERE status IN ('done','paid') AND updated_at>=?", (week_ago,)).fetchone()["n"]
            owed = c.execute("SELECT COALESCE(SUM(owed_cents),0) s FROM payments WHERE paid=0").fetchone()["s"]
        return {
            "active_jobs": active,
            "completed_this_week": done_week,
            "pending_payment": from_cents(owed),
            "pending_payment_cents": owed,
        }


__all__ = ["BusinessStore", "to_cents", "from_cents", "JOB_STATUSES", "DEFAULT_DB"]
