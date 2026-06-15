"""Notification foundation — Slack and Telegram notifiers for Mission Control.

Design rules (non-negotiable):
- Never prints or logs token values.
- send() never raises; always returns a result dict.
- is_configured() returns False for placeholder / empty tokens.
- Auto-send on mission events is NOT wired here; only explicit API calls trigger sends.
- Slack: uses httpx (already a project dependency) to call chat.postMessage directly.
- Telegram: uses python-telegram-bot (already a project dependency, >=22.6).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_SLACK_TOKEN_ENV = "OPENCLAW_SLACK_BOT_TOKEN"
_SLACK_CHANNEL_ENV = "OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL"
_SLACK_DEFAULT_CHANNEL = "C0BAF08SQTB"

_TELEGRAM_TOKEN_ENV = "JARVIS_TELEGRAM_BOT_TOKEN"
_TELEGRAM_CHAT_ID_ENV = "JARVIS_TELEGRAM_CHAT_ID"

_PLACEHOLDER_PREFIXES = ("xoxb-your", "your-token", "placeholder", "")


def _is_placeholder(value: Optional[str]) -> bool:
    if not value:
        return True
    v = value.strip().lower()
    return any(v.startswith(p) for p in _PLACEHOLDER_PREFIXES if p)


# ---------------------------------------------------------------------------
# SlackNotifier
# ---------------------------------------------------------------------------


class SlackNotifier:
    """Posts messages to Slack via the chat.postMessage API using httpx.

    Configuration is read from environment variables on every instantiation so
    that tests can monkeypatch os.environ without restarting the process.
    """

    def __init__(self) -> None:
        self._token: Optional[str] = os.environ.get(_SLACK_TOKEN_ENV, "").strip() or None
        self._channel: str = (
            os.environ.get(_SLACK_CHANNEL_ENV, "").strip()
            or _SLACK_DEFAULT_CHANNEL
        )

    def is_configured(self) -> bool:
        return bool(self._token) and not _is_placeholder(self._token)

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "channel": self._channel if self.is_configured() else None,
            "ready": self.is_configured(),
        }

    async def send(self, message: str) -> Dict[str, Any]:
        """Post *message* to the configured Slack channel.

        Returns a result dict; never raises.
        """
        if not self.is_configured():
            return {
                "ok": False,
                "error_type": "not_configured",
                "error": "Slack not configured — set OPENCLAW_SLACK_BOT_TOKEN",
            }
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={"channel": self._channel, "text": message},
                )
                data = resp.json()
                if data.get("ok"):
                    return {
                        "ok": True,
                        "method": "slack_api",
                        "channel": self._channel,
                    }
                return {
                    "ok": False,
                    "method": "slack_api",
                    "error_type": "api_error",
                    "error": data.get("error", "unknown_slack_error"),
                }
        except Exception as exc:
            logger.warning("Slack send failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "method": "slack_api",
                "error_type": "send_failed",
                "error": type(exc).__name__,
            }


# ---------------------------------------------------------------------------
# TelegramNotifier
# ---------------------------------------------------------------------------


class TelegramNotifier:
    """Sends messages to a Telegram chat via python-telegram-bot (>=22.6).

    Configuration is read from environment variables on every instantiation.
    """

    def __init__(self) -> None:
        self._token: Optional[str] = os.environ.get(_TELEGRAM_TOKEN_ENV, "").strip() or None
        self._chat_id: Optional[str] = os.environ.get(_TELEGRAM_CHAT_ID_ENV, "").strip() or None

    def is_configured(self) -> bool:
        return bool(self._token) and bool(self._chat_id)

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured(),
            "chat_id": self._chat_id if self.is_configured() else None,
            "ready": self.is_configured(),
        }

    async def send(self, message: str) -> Dict[str, Any]:
        """Send *message* to the configured Telegram chat.

        Returns a result dict; never raises.
        """
        if not self.is_configured():
            return {
                "ok": False,
                "error_type": "not_configured",
                "error": (
                    "Telegram not configured — set JARVIS_TELEGRAM_BOT_TOKEN "
                    "and JARVIS_TELEGRAM_CHAT_ID"
                ),
            }
        try:
            from telegram import Bot

            async with Bot(token=self._token) as bot:
                await bot.send_message(
                    chat_id=self._chat_id,
                    text=message,
                    parse_mode="HTML",
                )
            return {
                "ok": True,
                "method": "telegram_bot",
                "chat_id": self._chat_id,
            }
        except Exception as exc:
            logger.warning("Telegram send failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "method": "telegram_bot",
                "error_type": "send_failed",
                "error": type(exc).__name__,
            }


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def get_notification_status() -> Dict[str, Any]:
    """Return combined Slack + Telegram configuration status.

    Safe to expose over HTTP: no token values are included.
    """
    return {
        "slack": SlackNotifier().status(),
        "telegram": TelegramNotifier().status(),
    }


__all__ = [
    "SlackNotifier",
    "TelegramNotifier",
    "get_notification_status",
]
