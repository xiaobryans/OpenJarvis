"""Notification queue consumer skeleton — B5C readiness gate.

Reads from NotificationQueue.list_pending() and routes to external
provider adapters (Slack, Telegram, mobile push) — but ONLY when a
configured adapter is present.

Design rules (non-negotiable):
- No live external sends are performed unless a provider adapter is explicitly
  injected by the caller (test: mock adapters; Fargate: real adapters).
- No secret values stored, logged, or returned in dispatch results.
- No env var names in public-facing dispatch summaries.
- Provider adapters are never instantiated by this module — they are injected
  by the caller (Fargate worker or test fixture).
- Safe to call without Fargate: all dispatches return NOT_CONFIGURED.
- This module is the B5C consumer side. B5B (enqueueing) is in notification_queue.py.
- Approval gates are never bypassed by this dispatcher — delivery is observational
  only; approval decisions are never made or revoked here.

Usage (Fargate worker loop):
    dispatcher = NotificationDispatcher(providers=[slack_adapter, telegram_adapter])
    result = dispatcher.dispatch_pending(queue)

Usage (when no providers configured — returns NOT_CONFIGURED for all events):
    dispatcher = NotificationDispatcher(providers=[])
    result = dispatcher.dispatch_pending(queue)
    # result.delivered == 0, result.not_configured == N
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dispatch status constants
# ---------------------------------------------------------------------------

DISPATCH_STATUS_NOT_CONFIGURED = "NOT_CONFIGURED"
DISPATCH_STATUS_CONFIGURED_NOT_DEPLOYED = "CONFIGURED_NOT_DEPLOYED"
DISPATCH_STATUS_BLOCKED = "BLOCKED"
DISPATCH_STATUS_SENT = "sent"
DISPATCH_STATUS_FAILED = "failed"
DISPATCH_STATUS_SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Provider adapter interface (injectable — no instantiation in this module)
# ---------------------------------------------------------------------------


class NotificationProviderAdapter(ABC):
    """Abstract provider adapter for external notification delivery.

    Implement this interface for each external provider (Slack, Telegram, push).
    Adapters are injected into NotificationDispatcher by the caller.

    Design: no secret values are accessed in this interface definition.
    Token handling is the responsibility of concrete adapter implementations.
    Adapters must never reveal token values, account IDs, or webhook URLs.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Return a safe provider class identifier (never a token/account ID)."""

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if this provider is ready to send notifications."""

    @abstractmethod
    def send(self, event_id: str, action_type: str, risk_level: str, message: str) -> bool:
        """Send a notification. Return True on success.

        Must never raise — return False on any failure.
        Must never log secret values, token values, or account IDs.
        The approval decision is NOT made here — only notification is sent.
        """


# ---------------------------------------------------------------------------
# Dispatch result types
# ---------------------------------------------------------------------------


@dataclass
class EventDispatchResult:
    """Result of dispatching a single notification event."""

    event_id: str
    provider_id: str
    status: str      # DISPATCH_STATUS_* constant
    detail: str


@dataclass
class DispatchResult:
    """Aggregate result of a dispatch_pending() call."""

    event_results: List[EventDispatchResult] = field(default_factory=list)
    delivered: int = 0
    not_configured: int = 0
    failed: int = 0
    skipped: int = 0
    total_events: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "delivered": self.delivered,
            "not_configured": self.not_configured,
            "failed": self.failed,
            "skipped": self.skipped,
        }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


class NotificationDispatcher:
    """Reads from NotificationQueue and routes to configured provider adapters.

    No live sends unless at least one provider adapter is configured and injected.
    Events without a configured provider are marked NOT_CONFIGURED.

    Approval gate safety: this class never approves or denies approval requests.
    It only sends notification messages. Approval decision must go through
    ApprovalEngine / ApprovalStore via the proper auth-gated approval routes.
    """

    def __init__(self, providers: Optional[List[NotificationProviderAdapter]] = None) -> None:
        self._providers: List[NotificationProviderAdapter] = providers or []

    @property
    def configured_providers(self) -> List[NotificationProviderAdapter]:
        """Return providers that report is_configured == True."""
        return [p for p in self._providers if p.is_configured]

    def dispatch_pending(self, queue: Any) -> DispatchResult:
        """Read all pending events from queue and dispatch to configured providers.

        No live sends if no providers are configured.
        Returns aggregate DispatchResult — safe to call without Fargate.
        Approval gates are not modified by this method.
        """
        result = DispatchResult()

        try:
            pending = queue.list_pending()
        except Exception as exc:
            logger.warning("Failed to list pending notification events: %s", exc)
            return result

        result.total_events = len(pending)
        configured = self.configured_providers

        for event in pending:
            event_id = getattr(event, "event_id", "unknown")
            action_type = getattr(event, "action_type", "")
            risk_level = getattr(event, "risk_level", "low")
            message = f"Pending approval: {action_type} (risk={risk_level})"

            if not configured:
                result.event_results.append(EventDispatchResult(
                    event_id=event_id,
                    provider_id="none",
                    status=DISPATCH_STATUS_NOT_CONFIGURED,
                    detail=(
                        "No external notification providers configured — "
                        "requires Fargate deployment with live provider tokens"
                    ),
                ))
                result.not_configured += 1
                continue

            any_sent = False
            for adapter in configured:
                try:
                    ok = adapter.send(event_id, action_type, risk_level, message)
                    status = DISPATCH_STATUS_SENT if ok else DISPATCH_STATUS_FAILED
                except Exception as exc:
                    logger.warning(
                        "Provider %s raised during send for event %s: %s",
                        adapter.provider_id, event_id[:8], exc,
                    )
                    ok = False
                    status = DISPATCH_STATUS_FAILED

                result.event_results.append(EventDispatchResult(
                    event_id=event_id,
                    provider_id=adapter.provider_id,
                    status=status,
                    detail="delivered" if ok else "provider error",
                ))
                if ok:
                    any_sent = True

            if any_sent:
                result.delivered += 1
            else:
                result.failed += 1

        return result

    def get_status(self) -> Dict[str, Any]:
        """Return safe status summary — no secret values, no env var names."""
        configured_count = len(self.configured_providers)
        total = len(self._providers)
        if not configured_count:
            status = DISPATCH_STATUS_NOT_CONFIGURED
            detail = (
                "No external notification providers configured — "
                "requires Fargate deployment with live provider tokens."
            )
        elif configured_count < total:
            status = "PARTIAL"
            detail = f"{configured_count} of {total} provider(s) configured."
        else:
            status = "READY"
            detail = f"{configured_count} provider(s) configured and ready."
        return {
            "total_providers_registered": total,
            "providers_configured": configured_count,
            "status": status,
            "detail": detail,
        }


# ---------------------------------------------------------------------------
# Convenience: B5C external delivery status (presence-only)
# ---------------------------------------------------------------------------


def get_external_delivery_status() -> Dict[str, Any]:
    """Return B5C external notification delivery status.

    Presence-only check — no env var names or token values in response.
    Returns NOT_CONFIGURED or CONFIGURED_NOT_DEPLOYED until live Fargate
    worker with provider adapters is deployed.
    """
    # Presence-only checks — canonical and legacy env var names supported
    has_telegram = bool(
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        or os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "").strip()
    )
    has_slack = bool(
        os.environ.get("SLACK_BOT_TOKEN", "").strip()
        or os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "").strip()
    )
    providers_available = sum([has_telegram, has_slack])

    if providers_available == 0:
        return {
            "status": DISPATCH_STATUS_NOT_CONFIGURED,
            "providers_available": 0,
            "fargate_worker_required": True,
            "detail": (
                "No external notification provider tokens configured — "
                "external delivery blocked."
            ),
        }
    return {
        "status": DISPATCH_STATUS_CONFIGURED_NOT_DEPLOYED,
        "providers_available": providers_available,
        "fargate_worker_required": True,
        "detail": (
            "External provider tokens present but Fargate worker is not deployed — "
            "auto-trigger blocked. Deploy Fargate worker to enable B5C delivery."
        ),
    }


__all__ = [
    "NotificationProviderAdapter",
    "NotificationDispatcher",
    "DispatchResult",
    "EventDispatchResult",
    "get_external_delivery_status",
    "DISPATCH_STATUS_NOT_CONFIGURED",
    "DISPATCH_STATUS_CONFIGURED_NOT_DEPLOYED",
    "DISPATCH_STATUS_BLOCKED",
    "DISPATCH_STATUS_SENT",
    "DISPATCH_STATUS_FAILED",
    "DISPATCH_STATUS_SKIPPED",
]
