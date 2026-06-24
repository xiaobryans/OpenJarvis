"""Internal approval notification event queue — B5B closure.

Creates an in-process SQLite-backed queue for internal notification events.
An event is enqueued whenever a PENDING approval is created (tier 2+).

Design rules (non-negotiable):
- No secret values stored or exposed.
- No env var names, token names, private paths, OAuth contents, or provider
  account identifiers in stored events.
- Safe metadata only: event_id, approval_id, action_type, action_category,
  risk_level, created_at, channel_target_class, status.
- External delivery (Slack / Telegram / email / push) is NOT performed here.
  External delivery remains gated behind B5C (provider configuration).
- Events with status "queued" are ready for delivery once a configured
  external provider becomes available (B5C).
- Events with status "delivery_blocked" mean no external provider is
  configured at enqueue time — still persisted for auditing.
- This module is import-safe: if SQLite init fails the error is logged and
  callers receive None; approval creation must NOT be blocked.

Channel target classes (safe strings, never provider names or tokens):
  "mobile"           — target: mobile push (PWA / app)
  "in_app"           — target: in-app notification center
  "external_pending" — target: external channel (Slack/Telegram) once available
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jarvis" / "notification_events.db"

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

STATUS_QUEUED = "queued"
STATUS_DELIVERY_BLOCKED = "delivery_blocked"
STATUS_SENT = "sent"
STATUS_FAILED = "failed"

CHANNEL_MOBILE = "mobile"
CHANNEL_IN_APP = "in_app"
CHANNEL_EXTERNAL_PENDING = "external_pending"


# ---------------------------------------------------------------------------
# NotificationEvent dataclass — safe metadata only
# ---------------------------------------------------------------------------


@dataclass
class NotificationEvent:
    """A single internal notification event for a pending approval.

    Contains only safe metadata.  No secret values, no token names,
    no private paths, no OAuth contents, no provider account identifiers.
    """

    event_id: str
    approval_id: str
    action_type: str
    action_category: str          # "destructive" | "external" | "spend" | "read" | "unknown"
    risk_level: str               # "low" | "medium" | "high" | "critical"
    created_at: str               # ISO8601 UTC
    channel_target_class: str     # CHANNEL_* constant — target class, never token/provider
    status: str                   # STATUS_* constant

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "approval_id": self.approval_id,
            "action_type": self.action_type,
            "action_category": self.action_category,
            "risk_level": self.risk_level,
            "created_at": self.created_at,
            "channel_target_class": self.channel_target_class,
            "status": self.status,
        }

    @classmethod
    def from_row(cls, row: tuple) -> "NotificationEvent":
        event_id, approval_id, action_type, action_category, risk_level, created_at, channel_target_class, status = row
        return cls(
            event_id=event_id,
            approval_id=approval_id,
            action_type=action_type,
            action_category=action_category,
            risk_level=risk_level,
            created_at=created_at or "",
            channel_target_class=channel_target_class,
            status=status,
        )


# ---------------------------------------------------------------------------
# NotificationQueue
# ---------------------------------------------------------------------------

# Category inference from action type keywords
_CATEGORY_MAP: Dict[str, str] = {
    "delete": "destructive",
    "remove": "destructive",
    "drop": "destructive",
    "destroy": "destructive",
    "push": "external",
    "send": "external",
    "email": "external",
    "slack": "external",
    "telegram": "external",
    "webhook": "external",
    "deploy": "external",
    "publish": "external",
    "spend": "spend",
    "charge": "spend",
    "payment": "spend",
    "buy": "spend",
    "purchase": "spend",
    "read": "read",
    "get": "read",
    "list": "read",
    "fetch": "read",
}


def _infer_category(action_type: str) -> str:
    at = action_type.lower()
    for keyword, category in _CATEGORY_MAP.items():
        if keyword in at:
            return category
    return "unknown"


class NotificationQueue:
    """SQLite-backed internal notification event queue.

    Safe to use in tests — no external side effects.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_table()

    def _create_table(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS approval_notification_events (
            event_id             TEXT PRIMARY KEY,
            approval_id          TEXT NOT NULL,
            action_type          TEXT NOT NULL DEFAULT '',
            action_category      TEXT NOT NULL DEFAULT 'unknown',
            risk_level           TEXT NOT NULL DEFAULT 'low',
            created_at           TEXT NOT NULL,
            channel_target_class TEXT NOT NULL DEFAULT 'in_app',
            status               TEXT NOT NULL DEFAULT 'queued'
        );

        CREATE INDEX IF NOT EXISTS idx_notif_approval_id
            ON approval_notification_events (approval_id);
        CREATE INDEX IF NOT EXISTS idx_notif_status
            ON approval_notification_events (status);
        """)
        self._conn.commit()

    def enqueue(
        self,
        approval_id: str,
        action_type: str,
        risk_level: str,
        *,
        action_category: Optional[str] = None,
        channel_target_class: str = CHANNEL_IN_APP,
        initial_status: str = STATUS_QUEUED,
    ) -> NotificationEvent:
        """Enqueue an internal notification event for a pending approval.

        All stored fields are safe metadata.  No secret values.
        Returns the created event.
        """
        event_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        category = action_category or _infer_category(action_type)

        event = NotificationEvent(
            event_id=event_id,
            approval_id=approval_id,
            action_type=action_type,
            action_category=category,
            risk_level=risk_level,
            created_at=now,
            channel_target_class=channel_target_class,
            status=initial_status,
        )
        self._conn.execute(
            """INSERT OR REPLACE INTO approval_notification_events
               (event_id, approval_id, action_type, action_category,
                risk_level, created_at, channel_target_class, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.approval_id,
                event.action_type,
                event.action_category,
                event.risk_level,
                event.created_at,
                event.channel_target_class,
                event.status,
            ),
        )
        self._conn.commit()
        logger.debug(
            "Notification event %s enqueued for approval %s (action=%s risk=%s)",
            event_id[:8],
            approval_id[:8],
            action_type,
            risk_level,
        )
        return event

    def list_pending(self) -> List[NotificationEvent]:
        """Return all queued (undelivered) notification events."""
        rows = self._conn.execute(
            "SELECT event_id, approval_id, action_type, action_category, "
            "risk_level, created_at, channel_target_class, status "
            "FROM approval_notification_events WHERE status IN (?, ?) "
            "ORDER BY created_at DESC",
            (STATUS_QUEUED, STATUS_DELIVERY_BLOCKED),
        ).fetchall()
        return [NotificationEvent.from_row(r) for r in rows]

    def list_all(self, limit: int = 100) -> List[NotificationEvent]:
        """Return all notification events (any status)."""
        rows = self._conn.execute(
            "SELECT event_id, approval_id, action_type, action_category, "
            "risk_level, created_at, channel_target_class, status "
            "FROM approval_notification_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [NotificationEvent.from_row(r) for r in rows]

    def mark_delivery_status(self, event_id: str, status: str) -> bool:
        """Update the delivery status of a notification event."""
        cur = self._conn.execute(
            "UPDATE approval_notification_events SET status=? WHERE event_id=?",
            (status, event_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def count_queued(self) -> int:
        """Return count of queued (undelivered) events."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM approval_notification_events WHERE status IN (?, ?)",
            (STATUS_QUEUED, STATUS_DELIVERY_BLOCKED),
        ).fetchone()
        return row[0] if row else 0

    def close(self) -> None:
        self._conn.close()


# ---------------------------------------------------------------------------
# Module-level singleton (soft — failure never blocks approval creation)
# ---------------------------------------------------------------------------

_queue_instance: Optional[NotificationQueue] = None


def _get_queue(db_path: Optional[Path] = None) -> Optional[NotificationQueue]:
    """Return the module-level NotificationQueue singleton.

    Returns None if initialization fails (e.g., in read-only filesystem).
    Failure is logged but never propagated — approval creation must not break.
    """
    global _queue_instance
    if _queue_instance is None:
        try:
            _queue_instance = NotificationQueue(db_path)
        except Exception as exc:
            logger.warning("NotificationQueue init failed: %s", exc)
            return None
    return _queue_instance


def enqueue_approval_notification(
    approval_id: str,
    action_type: str,
    risk_level: str,
    *,
    channel_target_class: str = CHANNEL_IN_APP,
    db_path: Optional[Path] = None,
) -> Optional[NotificationEvent]:
    """Enqueue an internal notification event for a new pending approval.

    Safe: no external side effects, no secret values, never raises.
    Returns the created event or None if the queue is unavailable.
    """
    try:
        q = _get_queue(db_path)
        if q is None:
            return None
        return q.enqueue(
            approval_id=approval_id,
            action_type=action_type,
            risk_level=risk_level,
            channel_target_class=channel_target_class,
        )
    except Exception as exc:
        logger.warning("enqueue_approval_notification failed: %s", exc)
        return None


def is_queue_ready(db_path: Optional[Path] = None) -> bool:
    """Return True if the notification queue is initialized and accessible."""
    try:
        q = _get_queue(db_path)
        return q is not None
    except Exception:
        return False


__all__ = [
    "NotificationEvent",
    "NotificationQueue",
    "enqueue_approval_notification",
    "is_queue_ready",
    "STATUS_QUEUED",
    "STATUS_DELIVERY_BLOCKED",
    "STATUS_SENT",
    "STATUS_FAILED",
    "CHANNEL_MOBILE",
    "CHANNEL_IN_APP",
    "CHANNEL_EXTERNAL_PENDING",
]
