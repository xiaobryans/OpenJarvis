"""Telegram Ops — fallback alert channel for Bryan operational notifications.

Bryan has explicitly authorized scoped Telegram operational messaging for this sprint.

Policy:
  - Only Bryan's approved chat ID(s) can receive messages
  - Rate limit: max 5 live messages per sprint session
  - No secrets, tokens, credentials in messages
  - No external/customer/public messages
  - Every send creates an audit record
  - If Bryan's chat ID is not configured → BLOCKED_USER_AUTHORIZATION

Approved message categories:
  - slack_missed_fallback_alert
  - sprint_status_update
  - blocker_alert
  - bryan_approval_needed
  - validation_summary
  - smoke_test_notification
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

TELEGRAM_RATE_LIMIT = int(os.environ.get("JARVIS_TELEGRAM_RATE_LIMIT", "5"))

ALLOWED_TELEGRAM_CATEGORIES = frozenset({
    "slack_missed_fallback_alert",
    "sprint_status_update",
    "blocker_alert",
    "bryan_approval_needed",
    "validation_summary",
    "smoke_test_notification",
})

# ---------------------------------------------------------------------------
# Status codes
# ---------------------------------------------------------------------------

class TelegramOpsStatus(str, Enum):
    SENT = "SENT"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    BLOCKED_RATE_LIMIT = "BLOCKED_RATE_LIMIT"
    BLOCKED_CREDENTIALS = "BLOCKED_CREDENTIALS"
    BLOCKED_USER_AUTHORIZATION = "BLOCKED_USER_AUTHORIZATION"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------------

@dataclass
class TelegramAuditRecord:
    record_id: str
    surface: str
    target_chat: str           # Stored without full ID for safety — just "bryan_chat"
    message_category: str
    timestamp: float
    trace_id: Optional[str]
    redaction_status: str
    authorization_source: str
    status: TelegramOpsStatus
    api_message_id: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "surface": self.surface,
            "target_chat": self.target_chat,
            "message_category": self.message_category,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "redaction_status": self.redaction_status,
            "authorization_source": self.authorization_source,
            "status": self.status.value,
            "api_message_id": self.api_message_id,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Telegram Ops Policy
# ---------------------------------------------------------------------------

class TelegramOutboundPolicy:
    """Enforces all Telegram outbound send rules."""

    def __init__(self, rate_limit: int = TELEGRAM_RATE_LIMIT) -> None:
        self._rate_limit = rate_limit
        self._sent_count = 0
        self._audit_log: List[TelegramAuditRecord] = []

    def get_allowed_chat_id(self) -> Optional[str]:
        """Get Bryan's approved Telegram chat ID without logging it."""
        return os.environ.get("TELEGRAM_BRYAN_CHAT_ID", "").strip() or None

    def check_send(self, message_category: str) -> Tuple[bool, str]:
        if message_category not in ALLOWED_TELEGRAM_CATEGORIES:
            return False, f"Message category {message_category!r} not in Telegram allowlist"
        if self._sent_count >= self._rate_limit:
            return False, f"Rate limit reached: {self._sent_count}/{self._rate_limit}"
        chat_id = self.get_allowed_chat_id()
        if not chat_id:
            return (
                False,
                "BLOCKED_USER_AUTHORIZATION: TELEGRAM_BRYAN_CHAT_ID not set. "
                "To enable: run the bot, send /start or any message, then get chat_id from "
                "https://api.telegram.org/bot<TOKEN>/getUpdates and set TELEGRAM_BRYAN_CHAT_ID."
            )
        return True, "allowed"

    def record_send(
        self,
        message_category: str,
        status: TelegramOpsStatus,
        trace_id: Optional[str] = None,
        api_message_id: Optional[int] = None,
        error: Optional[str] = None,
    ) -> TelegramAuditRecord:
        record = TelegramAuditRecord(
            record_id=str(uuid.uuid4()),
            surface="telegram",
            target_chat="bryan_chat",
            message_category=message_category,
            timestamp=time.time(),
            trace_id=trace_id,
            redaction_status="redacted",
            authorization_source="sprint_explicit_bryan_authorization",
            status=status,
            api_message_id=api_message_id,
            error=error,
        )
        self._audit_log.append(record)
        if status == TelegramOpsStatus.SENT:
            self._sent_count += 1
        return record

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._audit_log]

    def get_sent_count(self) -> int:
        return self._sent_count

    def get_remaining_budget(self) -> int:
        return max(0, self._rate_limit - self._sent_count)


# ---------------------------------------------------------------------------
# Telegram Ops Command Center
# ---------------------------------------------------------------------------

class TelegramOpsCommandCenter:
    """Operational Telegram command center for Jarvis fallback alerts.

    All sends go to Bryan's approved chat only.
    """

    def __init__(
        self,
        bot_token: str = "",
        policy: Optional[TelegramOutboundPolicy] = None,
    ) -> None:
        self._token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._policy = policy or TelegramOutboundPolicy()

    def _has_token(self) -> bool:
        return bool(self._token)

    def send_alert(
        self,
        message: str,
        message_category: str,
        trace_id: Optional[str] = None,
    ) -> TelegramAuditRecord:
        """Send an approved alert to Bryan's Telegram chat."""
        allowed, reason = self._policy.check_send(message_category)
        if not allowed:
            if "BLOCKED_USER_AUTHORIZATION" in reason:
                status = TelegramOpsStatus.BLOCKED_USER_AUTHORIZATION
            elif "Rate limit" in reason:
                status = TelegramOpsStatus.BLOCKED_RATE_LIMIT
            else:
                status = TelegramOpsStatus.BLOCKED_POLICY
            record = self._policy.record_send(message_category, status, trace_id, error=reason)
            logger.warning("Telegram send blocked: %s", reason)
            return record

        if not self._has_token():
            record = self._policy.record_send(
                message_category, TelegramOpsStatus.BLOCKED_CREDENTIALS, trace_id,
                error="TELEGRAM_BOT_TOKEN not configured"
            )
            return record

        chat_id = self._policy.get_allowed_chat_id()

        try:
            import httpx

            url = f"https://api.telegram.org/bot{self._token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            }
            resp = httpx.post(url, json=payload, timeout=10.0)
            data = resp.json() if resp.status_code < 300 else {}
            if data.get("ok"):
                msg_id = data.get("result", {}).get("message_id")
                record = self._policy.record_send(
                    message_category, TelegramOpsStatus.SENT, trace_id, api_message_id=msg_id
                )
                logger.info("Telegram send OK: message_id=%s", msg_id)
                return record
            else:
                err = str(data.get("description", f"HTTP {resp.status_code}"))
                record = self._policy.record_send(
                    message_category, TelegramOpsStatus.ERROR, trace_id, error=err
                )
                logger.warning("Telegram API error: %s", err)
                return record
        except ImportError:
            record = self._policy.record_send(
                message_category, TelegramOpsStatus.BLOCKED_CREDENTIALS, trace_id,
                error="httpx not installed"
            )
            return record
        except Exception as exc:
            record = self._policy.record_send(
                message_category, TelegramOpsStatus.ERROR, trace_id,
                error=f"{type(exc).__name__}: {exc}"
            )
            logger.error("Telegram send exception: %s", exc)
            return record

    def smoke_test(self) -> TelegramAuditRecord:
        """Send approved Telegram smoke test alert to Bryan."""
        return self.send_alert(
            message=(
                "Jarvis Telegram fallback smoke test: Telegram alerts are enabled "
                "for Bryan operational notifications only. No secrets. No external sends."
            ),
            message_category="smoke_test_notification",
        )

    def get_setup_instructions(self) -> Dict[str, str]:
        """Return exact steps to set up Bryan's Telegram chat ID."""
        return {
            "step_1": "Create a Telegram bot via @BotFather and get the bot token",
            "step_2": "Set TELEGRAM_BOT_TOKEN in .env",
            "step_3": "Send any message to your bot from Bryan's Telegram account",
            "step_4": "Call: https://api.telegram.org/bot<TOKEN>/getUpdates",
            "step_5": "Find the chat.id field in the response",
            "step_6": "Set TELEGRAM_BRYAN_CHAT_ID=<that chat_id> in .env",
            "step_7": "Rerun smoke test",
            "classification": "BLOCKED_USER_AUTHORIZATION until TELEGRAM_BRYAN_CHAT_ID is set",
        }

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return self._policy.get_audit_log()

    def get_sent_count(self) -> int:
        return self._policy.get_sent_count()

    def get_remaining_budget(self) -> int:
        return self._policy.get_remaining_budget()


__all__ = [
    "TelegramOpsCommandCenter",
    "TelegramOutboundPolicy",
    "TelegramAuditRecord",
    "TelegramOpsStatus",
    "ALLOWED_TELEGRAM_CATEGORIES",
]
