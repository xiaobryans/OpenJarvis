"""Jarvis Alert Store — SQLite-backed, project-scoped alert records.

Alert capabilities:
  create          — create a new alert with evidence and severity
  list            — list alerts for a project
  acknowledge     — mark alert acknowledged (action still needed)
  resolve         — mark alert resolved
  draft_slack_update    — draft a Slack message (NEVER sends; requires approval)
  draft_telegram_update — draft a Telegram message (NEVER sends; requires approval)
  daily_digest    — generate a plain-text daily digest

Governance rules:
  - Drafts are produced; real sends require explicit approval (never auto-sent here)
  - Alerts are project-scoped
  - Evidence and severity are required fields
  - No auto-send under any circumstances from this module
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jarvis" / "alerts.db"


class AlertSeverity:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus:
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


@dataclass
class AlertRecord:
    """A single alert entry."""

    alert_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    project_id: str = ""
    severity: str = AlertSeverity.INFO
    title: str = ""
    evidence: str = ""
    recommendation: str = ""
    source_watchdog_id: str = ""
    status: str = AlertStatus.OPEN
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    acknowledged_at: Optional[float] = None
    resolved_at: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "project_id": self.project_id,
            "severity": self.severity,
            "title": self.title,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "source_watchdog_id": self.source_watchdog_id,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "acknowledged_at": self.acknowledged_at,
            "resolved_at": self.resolved_at,
        }


class AlertStore:
    """SQLite-backed alert store. Project-scoped. No auto-send."""

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
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL DEFAULT '',
                    severity TEXT NOT NULL DEFAULT 'info',
                    title TEXT NOT NULL DEFAULT '',
                    evidence TEXT NOT NULL DEFAULT '',
                    recommendation TEXT NOT NULL DEFAULT '',
                    source_watchdog_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL,
                    acknowledged_at REAL,
                    resolved_at REAL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_al_project ON alerts(project_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_al_status ON alerts(status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_al_created ON alerts(created_at)"
            )
            conn.commit()

    def create(
        self,
        project_id: str,
        title: str,
        evidence: str,
        *,
        severity: str = AlertSeverity.INFO,
        recommendation: str = "",
        source_watchdog_id: str = "",
    ) -> AlertRecord:
        """Create a new alert record."""
        now = time.time()
        record = AlertRecord(
            project_id=project_id,
            severity=severity,
            title=title,
            evidence=evidence,
            recommendation=recommendation,
            source_watchdog_id=source_watchdog_id,
            status=AlertStatus.OPEN,
            created_at=now,
            updated_at=now,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alerts
                    (alert_id, project_id, severity, title, evidence, recommendation,
                     source_watchdog_id, status, created_at, updated_at,
                     acknowledged_at, resolved_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    record.alert_id, record.project_id, record.severity,
                    record.title, record.evidence, record.recommendation,
                    record.source_watchdog_id, record.status,
                    record.created_at, record.updated_at,
                    record.acknowledged_at, record.resolved_at,
                ),
            )
            conn.commit()
        logger.info(
            "Alert created: %s [%s] %s", record.alert_id, record.severity, record.title
        )
        return record

    def list(
        self,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[AlertRecord]:
        """List alerts, optionally filtered by project_id and/or status."""
        limit = max(1, min(limit, 200))
        clauses: List[str] = []
        params: List[Any] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM alerts {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get(self, alert_id: str) -> Optional[AlertRecord]:
        """Return a single alert by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)
            ).fetchone()
        return self._row_to_record(row) if row else None

    def acknowledge(self, alert_id: str) -> Optional[AlertRecord]:
        """Acknowledge an alert. Does not resolve it."""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "UPDATE alerts SET status=?, acknowledged_at=?, updated_at=? WHERE alert_id=?",
                (AlertStatus.ACKNOWLEDGED, now, now, alert_id),
            )
            conn.commit()
        logger.info("Alert acknowledged: %s", alert_id)
        return self.get(alert_id)

    def resolve(self, alert_id: str) -> Optional[AlertRecord]:
        """Resolve an alert."""
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                "UPDATE alerts SET status=?, resolved_at=?, updated_at=? WHERE alert_id=?",
                (AlertStatus.RESOLVED, now, now, alert_id),
            )
            conn.commit()
        logger.info("Alert resolved: %s", alert_id)
        return self.get(alert_id)

    def draft_slack_update(
        self,
        project_id: str,
        alert_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Draft a Slack message for open alerts. NEVER sends. Requires explicit approval."""
        alerts = self.list(project_id=project_id, status=AlertStatus.OPEN, limit=10)
        if alert_ids:
            alerts = [a for a in alerts if a.alert_id in alert_ids]
        _EMOJI = {"info": "ℹ️", "warning": "⚠️", "error": "🔴", "critical": "🚨"}
        lines = [f"*Jarvis Alert Digest — Project: {project_id}*"]
        if not alerts:
            lines.append("✅ No open alerts.")
        else:
            for a in alerts:
                em = _EMOJI.get(a.severity, "📋")
                lines.append(f"{em} [{a.severity.upper()}] {a.title}")
                lines.append(f"  Evidence: {a.evidence[:150]}")
                if a.recommendation:
                    lines.append(f"  Recommendation: {a.recommendation[:150]}")
        return {
            "draft_text": "\n".join(lines),
            "send_status": "not_sent",
            "approval_required": True,
            "send_instruction": (
                "To send, call slack.notify_mission with explicit_approved=True"
            ),
            "alert_count": len(alerts),
            "project_id": project_id,
        }

    def draft_telegram_update(
        self,
        project_id: str,
        alert_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Draft a Telegram message for open alerts. NEVER sends. Requires explicit approval."""
        alerts = self.list(project_id=project_id, status=AlertStatus.OPEN, limit=10)
        if alert_ids:
            alerts = [a for a in alerts if a.alert_id in alert_ids]
        _EMOJI = {"info": "ℹ️", "warning": "⚠️", "error": "🔴", "critical": "🚨"}
        lines = [f"🤖 Jarvis Alerts — {project_id}"]
        if not alerts:
            lines.append("✅ No open alerts")
        else:
            for a in alerts:
                em = _EMOJI.get(a.severity, "📋")
                lines.append(f"{em} {a.title} [{a.severity}]")
                lines.append(f"  {a.evidence[:120]}")
        return {
            "draft_text": "\n".join(lines),
            "send_status": "not_sent",
            "approval_required": True,
            "send_instruction": (
                "To send, call telegram.notify_mission with explicit_approved=True"
            ),
            "alert_count": len(alerts),
            "project_id": project_id,
        }

    def daily_digest(self, project_id: str) -> Dict[str, Any]:
        """Generate a plain-text daily digest of alerts for a project."""
        open_alerts = self.list(project_id=project_id, status=AlertStatus.OPEN, limit=50)
        ack_alerts = self.list(project_id=project_id, status=AlertStatus.ACKNOWLEDGED, limit=50)
        severities: Dict[str, int] = {}
        for a in open_alerts:
            severities[a.severity] = severities.get(a.severity, 0) + 1
        lines = [
            f"# Jarvis Daily Digest — Project: {project_id}",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}",
            "",
            f"## Open Alerts: {len(open_alerts)}",
        ]
        for sev in ["critical", "error", "warning", "info"]:
            count = severities.get(sev, 0)
            if count:
                lines.append(f"  - {sev.upper()}: {count}")
        if open_alerts:
            lines.append("")
            lines.append("### Open Alert Details")
            for a in open_alerts[:10]:
                lines.append(f"- [{a.severity.upper()}] {a.title}")
                lines.append(f"  {a.evidence[:100]}")
        lines.append(f"\n## Acknowledged (pending resolution): {len(ack_alerts)}")
        return {
            "digest_text": "\n".join(lines),
            "open_count": len(open_alerts),
            "acknowledged_count": len(ack_alerts),
            "severity_breakdown": severities,
            "project_id": project_id,
        }

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> AlertRecord:
        return AlertRecord(
            alert_id=row["alert_id"],
            project_id=row["project_id"] or "",
            severity=row["severity"] or AlertSeverity.INFO,
            title=row["title"] or "",
            evidence=row["evidence"] or "",
            recommendation=row["recommendation"] or "",
            source_watchdog_id=row["source_watchdog_id"] or "",
            status=row["status"] or AlertStatus.OPEN,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            acknowledged_at=row["acknowledged_at"],
            resolved_at=row["resolved_at"],
        )


_store: Optional[AlertStore] = None


def get_alert_store() -> AlertStore:
    """Return module-level singleton AlertStore."""
    global _store
    if _store is None:
        _store = AlertStore()
    return _store


__all__ = [
    "AlertRecord",
    "AlertSeverity",
    "AlertStatus",
    "AlertStore",
    "get_alert_store",
]
