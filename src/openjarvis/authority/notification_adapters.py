"""Concrete notification provider adapters for B5C external delivery.

Implements NotificationProviderAdapter for Slack and Telegram using env vars
injected by the Fargate task definition (SLACK_BOT_TOKEN, TELEGRAM_BOT_TOKEN).

Design rules (non-negotiable):
- Never logs or returns token values, chat IDs, channel IDs, or account IDs.
- send() never raises — returns False on any error.
- is_configured checks presence of BOTH token AND destination (channel/chat).
- Checks all known env var aliases for each provider (B3 alias support).
- get_configured_adapters() returns only adapters that report is_configured=True.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from openjarvis.authority.notification_dispatcher import NotificationProviderAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Slack adapter
# ---------------------------------------------------------------------------

_SLACK_TOKEN_ALIASES = (
    "SLACK_BOT_TOKEN",          # Fargate-injected (canonical for task def rev 17+)
    "OPENCLAW_SLACK_BOT_TOKEN", # legacy notifier name
    "JARVIS_SLACK_BOT_TOKEN",   # keychain alias
)
_SLACK_CHANNEL_ALIASES = (
    "JARVIS_SLACK_CHANNEL_ID",
    "OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL",
)
_SLACK_DEFAULT_CHANNEL = "C0BAF08SQTB"  # safe hardcoded default; not a secret


class SlackNotificationAdapter(NotificationProviderAdapter):
    """Delivers approval notification events to a Slack channel.

    Token resolution order: SLACK_BOT_TOKEN → OPENCLAW_SLACK_BOT_TOKEN → JARVIS_SLACK_BOT_TOKEN
    Channel resolution order: JARVIS_SLACK_CHANNEL_ID → OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL → default
    """

    @property
    def provider_id(self) -> str:
        return "slack"

    def _get_token(self) -> Optional[str]:
        for alias in _SLACK_TOKEN_ALIASES:
            val = os.environ.get(alias, "").strip()
            if val:
                return val
        return None

    def _get_channel(self) -> str:
        for alias in _SLACK_CHANNEL_ALIASES:
            val = os.environ.get(alias, "").strip()
            if val:
                return val
        return _SLACK_DEFAULT_CHANNEL

    @property
    def is_configured(self) -> bool:
        return bool(self._get_token())

    def send(self, event_id: str, action_type: str, risk_level: str, message: str) -> bool:
        """Post a notification to Slack. Returns True on success, False on any failure."""
        token = self._get_token()
        if not token:
            return False
        channel = self._get_channel()
        text = f":bell: *Jarvis Approval Required* | `{action_type}` | risk={risk_level}\n{message}"
        try:
            import httpx
            import asyncio

            async def _post() -> bool:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={"Authorization": f"Bearer {token}"},
                        json={"channel": channel, "text": text},
                    )
                    data = resp.json()
                    ok = bool(data.get("ok"))
                    if not ok:
                        logger.warning(
                            "Slack delivery failed for event %s: %s",
                            event_id[:8],
                            data.get("error", "unknown"),
                        )
                    return ok

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                        future = ex.submit(asyncio.run, _post())
                        return future.result(timeout=15)
                else:
                    return loop.run_until_complete(_post())
            except RuntimeError:
                return asyncio.run(_post())
        except Exception as exc:
            logger.warning("SlackNotificationAdapter.send raised for event %s: %s", event_id[:8], type(exc).__name__)
            return False


# ---------------------------------------------------------------------------
# Telegram adapter
# ---------------------------------------------------------------------------

_TELEGRAM_TOKEN_ALIASES = (
    "TELEGRAM_BOT_TOKEN",       # Fargate-injected (canonical for task def rev 17+)
    "JARVIS_TELEGRAM_BOT_TOKEN", # B3 alias / legacy
)
_TELEGRAM_CHAT_ID_ALIASES = (
    "JARVIS_TELEGRAM_CHAT_ID",
    "TELEGRAM_NOTIFICATION_CHAT_ID",
)


class TelegramNotificationAdapter(NotificationProviderAdapter):
    """Delivers approval notification events to a Telegram chat.

    Token resolution order: TELEGRAM_BOT_TOKEN → JARVIS_TELEGRAM_BOT_TOKEN
    Chat ID resolution order: JARVIS_TELEGRAM_CHAT_ID → TELEGRAM_NOTIFICATION_CHAT_ID
    """

    @property
    def provider_id(self) -> str:
        return "telegram"

    def _get_token(self) -> Optional[str]:
        for alias in _TELEGRAM_TOKEN_ALIASES:
            val = os.environ.get(alias, "").strip()
            if val:
                return val
        return None

    def _get_chat_id(self) -> Optional[str]:
        for alias in _TELEGRAM_CHAT_ID_ALIASES:
            val = os.environ.get(alias, "").strip()
            if val:
                return val
        return None

    @property
    def is_configured(self) -> bool:
        # Requires BOTH token AND chat ID — cannot deliver without a destination
        return bool(self._get_token()) and bool(self._get_chat_id())

    def send(self, event_id: str, action_type: str, risk_level: str, message: str) -> bool:
        """Send a notification to Telegram. Returns True on success, False on any failure."""
        token = self._get_token()
        chat_id = self._get_chat_id()
        if not token or not chat_id:
            return False
        text = f"<b>Jarvis Approval Required</b>\nAction: <code>{action_type}</code>\nRisk: {risk_level}\n{message}"
        try:
            from telegram import Bot
            import asyncio

            async def _send() -> bool:
                async with Bot(token=token) as bot:
                    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
                return True

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                        future = ex.submit(asyncio.run, _send())
                        return future.result(timeout=15)
                else:
                    return loop.run_until_complete(_send())
            except RuntimeError:
                return asyncio.run(_send())
        except Exception as exc:
            logger.warning("TelegramNotificationAdapter.send raised for event %s: %s", event_id[:8], type(exc).__name__)
            return False


# ---------------------------------------------------------------------------
# Factory: return configured adapters from env
# ---------------------------------------------------------------------------


def get_configured_adapters() -> List[NotificationProviderAdapter]:
    """Return all adapters that report is_configured == True based on env vars.

    Safe: reads only env var presence, never logs token values or channel IDs.
    Call this inside Fargate routes to get the live provider list.
    """
    candidates: List[NotificationProviderAdapter] = [
        SlackNotificationAdapter(),
        TelegramNotificationAdapter(),
    ]
    return [a for a in candidates if a.is_configured]


def get_adapter_status() -> Dict[str, Any]:
    """Return safe status dict for all adapters (no token values or IDs).

    Reports: provider_id, is_configured, token_present, destination_configured.
    """
    slack = SlackNotificationAdapter()
    telegram = TelegramNotificationAdapter()

    slack_token = bool(slack._get_token())
    slack_channel = bool(slack._get_channel())
    tg_token = bool(telegram._get_token())
    tg_chat = bool(telegram._get_chat_id())

    return {
        "slack": {
            "provider_id": "slack",
            "token_present": slack_token,
            "destination_configured": slack_channel,
            "is_configured": slack.is_configured,
        },
        "telegram": {
            "provider_id": "telegram",
            "token_present": tg_token,
            "destination_configured": tg_chat,
            "is_configured": telegram.is_configured,
        },
        "configured_count": sum([slack.is_configured, telegram.is_configured]),
        "total_adapters": 2,
    }


__all__ = [
    "SlackNotificationAdapter",
    "TelegramNotificationAdapter",
    "get_configured_adapters",
    "get_adapter_status",
]
