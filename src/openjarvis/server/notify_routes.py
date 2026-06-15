"""Notification REST endpoints — Slack and Telegram status + explicit send.

Rules:
- GET /v1/notify/status: never exposes token values; reports configured booleans only.
- POST /v1/notify/slack: only sends when Bryan explicitly calls this endpoint.
- POST /v1/notify/telegram: same.
- Both send endpoints always return HTTP 200 with a result dict (never 500).
- Auto-send on mission events is NOT wired here.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from openjarvis.mission.notifier import (
    SlackNotifier,
    TelegramNotifier,
    get_notification_status,
)

try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for notify routes")

logger = logging.getLogger(__name__)

router = APIRouter()


class NotifyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)


@router.get("/v1/notify/status")
async def notify_status() -> Dict[str, Any]:
    """Return Slack and Telegram configuration status.

    No token values are included in the response.
    """
    return get_notification_status()


@router.post("/v1/notify/slack")
async def send_slack(req: NotifyRequest) -> Dict[str, Any]:
    """Explicitly send a message to Slack.

    Always returns HTTP 200; check the 'ok' field in the response body.
    Only sends if OPENCLAW_SLACK_BOT_TOKEN is configured and non-placeholder.
    """
    try:
        result = await SlackNotifier().send(req.message)
    except Exception as exc:
        logger.warning("Unexpected error in send_slack: %s", exc)
        result = {"ok": False, "error_type": "unexpected", "error": type(exc).__name__}
    return result


@router.post("/v1/notify/telegram")
async def send_telegram(req: NotifyRequest) -> Dict[str, Any]:
    """Explicitly send a message to Telegram.

    Always returns HTTP 200; check the 'ok' field in the response body.
    Only sends if JARVIS_TELEGRAM_BOT_TOKEN and JARVIS_TELEGRAM_CHAT_ID are configured.
    """
    try:
        result = await TelegramNotifier().send(req.message)
    except Exception as exc:
        logger.warning("Unexpected error in send_telegram: %s", exc)
        result = {"ok": False, "error_type": "unexpected", "error": type(exc).__name__}
    return result


__all__ = ["router"]
