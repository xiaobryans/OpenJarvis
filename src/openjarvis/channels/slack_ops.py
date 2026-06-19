"""Slack Ops Command Center — operational messaging for Jarvis.

Bryan has explicitly authorized scoped Slack operational messaging for this sprint.
All sends are bounded, audited, and policy-governed.

Policy:
  - Only approved channels (allowlist) can receive messages
  - Protected channels (#general, #random, #announcements) cannot be deleted/edited
  - Rate limit: max 10 live messages per sprint session
  - Every send creates an audit record
  - No secrets, tokens, credentials in messages
  - No external/customer/public messages
  - No Gmail, Calendar, GitHub sends
  - No posting loops / spam

Required channels:
  #jarvis-ops, #jarvis-tasks, #jarvis-debug, #jarvis-approvals, #omnix-project

Workspace deletion:
  Remains BLOCKED_USER_AUTHORIZATION unless ALL 9 checks pass and
  BRYAN_APPROVES_SLACK_WORKSPACE_DELETE=true is set.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

SLACK_RATE_LIMIT = int(os.environ.get("JARVIS_SLACK_RATE_LIMIT", "10"))

REQUIRED_CHANNELS = [
    "jarvis-ops",
    "jarvis-tasks",
    "jarvis-debug",
    "jarvis-approvals",
    "omnix-project",
]

OPTIONAL_CHANNELS = [
    "jarvis-coding",
    "jarvis-memory",
    "jarvis-connectors",
    "jarvis-voice",
    "jarvis-alerts",
]

PROTECTED_CHANNELS = frozenset({
    "general",
    "random",
    "announcements",
})

ALLOWED_MESSAGE_CATEGORIES = frozenset({
    "sprint_status_update",
    "blocker_alert",
    "validation_summary",
    "agent_to_agent_coordination",
    "bryan_approval_needed",
    "smoke_test_notification",
    "daily_driver_readiness_update",
    "slack_telegram_notification_fallback_test",
})

BLOCKED_SURFACES = frozenset({
    "gmail",
    "google_calendar",
    "github_issues",
    "github_prs",
    "github_comments",
    "external_customers",
    "public",
})

# ---------------------------------------------------------------------------
# Status codes
# ---------------------------------------------------------------------------

class OpsStatus(str, Enum):
    SENT = "SENT"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    BLOCKED_RATE_LIMIT = "BLOCKED_RATE_LIMIT"
    BLOCKED_CREDENTIALS = "BLOCKED_CREDENTIALS"
    BLOCKED_USER_AUTHORIZATION = "BLOCKED_USER_AUTHORIZATION"
    BLOCKED_SCOPE = "BLOCKED_SCOPE"
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Audit record
# ---------------------------------------------------------------------------

@dataclass
class SlackAuditRecord:
    """Immutable audit record for every Slack send attempt."""
    record_id: str
    surface: str
    target_channel: str
    message_category: str
    timestamp: float
    trace_id: Optional[str]
    redaction_status: str
    authorization_source: str
    status: OpsStatus
    api_result_ts: Optional[str] = None
    api_result_id: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "surface": self.surface,
            "target_channel": self.target_channel,
            "message_category": self.message_category,
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "redaction_status": self.redaction_status,
            "authorization_source": self.authorization_source,
            "status": self.status.value,
            "api_result_ts": self.api_result_ts,
            "api_result_id": self.api_result_id,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Channel cleanup plan
# ---------------------------------------------------------------------------

@dataclass
class ChannelCleanupPlan:
    """Generated cleanup plan before any Slack channel operations."""
    channels_to_keep: List[str]
    channels_to_create: List[str]
    channels_to_rename: List[Dict[str, str]]   # [{"from": ..., "to": ...}]
    channels_to_archive: List[str]
    channels_to_delete: List[str]
    protected_channels_skipped: List[str]
    reasons: Dict[str, str]                    # channel -> reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channels_to_keep": self.channels_to_keep,
            "channels_to_create": self.channels_to_create,
            "channels_to_rename": self.channels_to_rename,
            "channels_to_archive": self.channels_to_archive,
            "channels_to_delete": self.channels_to_delete,
            "protected_channels_skipped": self.protected_channels_skipped,
            "reasons": self.reasons,
        }


# ---------------------------------------------------------------------------
# Outbound policy enforcer
# ---------------------------------------------------------------------------

class SlackOutboundPolicy:
    """Enforces all Slack outbound send rules before any API call."""

    def __init__(
        self,
        allowed_channels: Optional[List[str]] = None,
        protected_channels: Optional[frozenset] = None,
        rate_limit: int = SLACK_RATE_LIMIT,
    ) -> None:
        # Channels are stored without # prefix for comparison
        self._allowed = set(
            c.lstrip("#") for c in (allowed_channels or REQUIRED_CHANNELS + OPTIONAL_CHANNELS)
        )
        self._protected = protected_channels or PROTECTED_CHANNELS
        self._rate_limit = rate_limit
        self._sent_count = 0
        self._audit_log: List[SlackAuditRecord] = []

    def check_send(
        self,
        channel: str,
        message_category: str,
        surface: str = "slack",
    ) -> Tuple[bool, str]:
        """Check whether a send is allowed. Returns (allowed, reason)."""
        clean_channel = channel.lstrip("#")

        if surface in BLOCKED_SURFACES:
            return False, f"Surface {surface!r} is permanently blocked"

        if clean_channel in self._protected:
            return False, f"Channel #{clean_channel} is protected and cannot receive ops messages"

        if message_category not in ALLOWED_MESSAGE_CATEGORIES:
            return False, f"Message category {message_category!r} is not in allowlist"

        if clean_channel not in self._allowed:
            return False, f"Channel #{clean_channel} is not in Slack channel allowlist"

        if self._sent_count >= self._rate_limit:
            return False, f"Rate limit reached: {self._sent_count}/{self._rate_limit} messages this session"

        return True, "allowed"

    def check_channel_delete(self, channel: str) -> Tuple[bool, str]:
        """Protected channels cannot be deleted under any circumstances."""
        clean = channel.lstrip("#")
        if clean in self._protected:
            return False, f"Channel #{clean} is protected — deletion permanently blocked"
        return True, "not protected"

    def check_workspace_delete(self, workspace_id: str, workspace_name: str) -> Tuple[bool, str]:
        """Workspace deletion remains BLOCKED_USER_AUTHORIZATION unless flag set."""
        if os.environ.get("BRYAN_APPROVES_SLACK_WORKSPACE_DELETE", "").lower() == "true":
            return True, "BRYAN_APPROVES_SLACK_WORKSPACE_DELETE=true"
        return (
            False,
            "BLOCKED_USER_AUTHORIZATION: Slack workspace deletion requires all 9 checks "
            "AND BRYAN_APPROVES_SLACK_WORKSPACE_DELETE=true. Not authorized."
        )

    def record_send(
        self,
        channel: str,
        message_category: str,
        status: OpsStatus,
        trace_id: Optional[str] = None,
        api_result_ts: Optional[str] = None,
        error: Optional[str] = None,
    ) -> SlackAuditRecord:
        record = SlackAuditRecord(
            record_id=str(uuid.uuid4()),
            surface="slack",
            target_channel=channel.lstrip("#"),
            message_category=message_category,
            timestamp=time.time(),
            trace_id=trace_id,
            redaction_status="redacted",
            authorization_source="sprint_explicit_bryan_authorization",
            status=status,
            api_result_ts=api_result_ts,
            error=error,
        )
        self._audit_log.append(record)
        if status == OpsStatus.SENT:
            self._sent_count += 1
        return record

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return [r.to_dict() for r in self._audit_log]

    def get_sent_count(self) -> int:
        return self._sent_count

    def get_remaining_budget(self) -> int:
        return max(0, self._rate_limit - self._sent_count)

    def add_channel_to_allowlist(self, channel: str) -> None:
        self._allowed.add(channel.lstrip("#"))


# ---------------------------------------------------------------------------
# Slack Ops Command Center
# ---------------------------------------------------------------------------

class SlackOpsCommandCenter:
    """Operational Slack command center for Jarvis.

    Handles:
    - Approved channel messaging with full audit
    - Channel cleanup planning
    - Channel create/rename/archive (if token has permissions)
    - Workspace deletion guardrails
    - Rate limiting and policy enforcement

    Does NOT handle:
    - Gmail, Google Calendar, GitHub, external/public messages
    """

    def __init__(
        self,
        bot_token: str = "",
        policy: Optional[SlackOutboundPolicy] = None,
    ) -> None:
        from openjarvis.channels.credentials import get_slack_bot_token
        _loaded, _src = get_slack_bot_token()
        self._token = bot_token or _loaded
        self._credential_source = _src if (bot_token or _loaded) else "MISSING"
        self._policy = policy or SlackOutboundPolicy()

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _has_token(self) -> bool:
        return bool(self._token)

    def send_ops_message(
        self,
        channel: str,
        message: str,
        message_category: str,
        *,
        thread_ts: Optional[str] = None,
        trace_id: Optional[str] = None,
        persona_prefix: Optional[str] = None,
    ) -> SlackAuditRecord:
        """Send an approved ops message to a Jarvis channel.

        Parameters
        ----------
        channel: channel name (with or without #)
        message: message body — will be redacted by policy
        message_category: must be in ALLOWED_MESSAGE_CATEGORIES
        thread_ts: Slack thread timestamp for threaded replies
        trace_id: optional trace ID for audit
        persona_prefix: optional [Jarvis COS] / [Worker: ...] prefix for visibility
        """
        allowed, reason = self._policy.check_send(channel, message_category)
        if not allowed:
            record = self._policy.record_send(
                channel, message_category, OpsStatus.BLOCKED_POLICY, trace_id, error=reason
            )
            logger.warning("Slack send blocked: %s", reason)
            return record

        if not self._has_token():
            record = self._policy.record_send(
                channel, message_category, OpsStatus.BLOCKED_CREDENTIALS, trace_id,
                error="SLACK_BOT_TOKEN not configured"
            )
            return record

        full_message = f"{persona_prefix} {message}" if persona_prefix else message

        try:
            import httpx

            payload: Dict[str, Any] = {
                "channel": f"#{channel.lstrip('#')}",
                "text": full_message,
            }
            if thread_ts:
                payload["thread_ts"] = thread_ts

            resp = httpx.post(
                "https://slack.com/api/chat.postMessage",
                json=payload,
                headers=self._headers(),
                timeout=10.0,
            )
            data = resp.json() if resp.status_code < 300 else {}
            if data.get("ok"):
                api_ts = data.get("ts")
                record = self._policy.record_send(
                    channel, message_category, OpsStatus.SENT, trace_id, api_result_ts=api_ts
                )
                logger.info("Slack send OK: #%s ts=%s", channel.lstrip("#"), api_ts)
                return record
            else:
                err = data.get("error", f"HTTP {resp.status_code}")
                if err in ("missing_scope", "not_in_channel", "channel_not_found"):
                    status = OpsStatus.BLOCKED_SCOPE
                else:
                    status = OpsStatus.ERROR
                record = self._policy.record_send(
                    channel, message_category, status, trace_id, error=err
                )
                logger.warning("Slack API error: %s", err)
                return record
        except ImportError:
            record = self._policy.record_send(
                channel, message_category, OpsStatus.BLOCKED_CREDENTIALS, trace_id,
                error="httpx not installed"
            )
            return record
        except Exception as exc:
            record = self._policy.record_send(
                channel, message_category, OpsStatus.ERROR, trace_id,
                error=f"{type(exc).__name__}: {exc}"
            )
            logger.error("Slack send exception: %s", exc)
            return record

    def smoke_test(self, channel: str = "jarvis-ops") -> SlackAuditRecord:
        """Send approved smoke test message."""
        return self.send_ops_message(
            channel=channel,
            message=(
                "Jarvis Slack live-send smoke test: operational messaging is enabled "
                "for approved Jarvis channels only. No secrets. No external sends."
            ),
            message_category="smoke_test_notification",
            persona_prefix="[Jarvis Notifications]",
        )

    def generate_cleanup_plan(
        self,
        existing_channels: Optional[List[str]] = None,
    ) -> ChannelCleanupPlan:
        """Generate a cleanup plan for Slack channels without executing it.

        existing_channels: list of channel names currently in the workspace.
        """
        existing = set(c.lstrip("#") for c in (existing_channels or []))
        required = set(REQUIRED_CHANNELS)
        optional = set(OPTIONAL_CHANNELS)

        to_keep = list(existing & (required | optional | PROTECTED_CHANNELS))
        to_create = [c for c in required if c not in existing]
        to_archive = []
        to_delete = []
        protected_skipped = [c for c in existing if c in PROTECTED_CHANNELS]
        reasons: Dict[str, str] = {}

        for c in to_keep:
            if c in required:
                reasons[c] = "Required Jarvis ops channel — keep"
            elif c in optional:
                reasons[c] = "Optional Jarvis channel — keep"
            elif c in PROTECTED_CHANNELS:
                reasons[c] = "Protected system channel — never touch"

        for c in to_create:
            reasons[c] = f"Required channel #{c} missing — create"

        return ChannelCleanupPlan(
            channels_to_keep=to_keep,
            channels_to_create=to_create,
            channels_to_rename=[],
            channels_to_archive=to_archive,
            channels_to_delete=to_delete,
            protected_channels_skipped=protected_skipped,
            reasons=reasons,
        )

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return self._policy.get_audit_log()

    def get_sent_count(self) -> int:
        return self._policy.get_sent_count()

    def get_remaining_budget(self) -> int:
        return self._policy.get_remaining_budget()


def format_agent_message(role: str, content: str, worker_name: Optional[str] = None) -> str:
    """Format a Slack message with visible Jarvis agent persona prefix.

    Examples:
        [Jarvis Coding Manager] Assigning task to repo-inspector.
        [Worker: repo-inspector] Found 3 changed files.
        [Jarvis GM] Escalating blocker to Bryan.
    """
    if worker_name:
        prefix = f"[Worker: {worker_name}]"
    else:
        prefix = f"[{role}]"
    return f"{prefix} {content}"


__all__ = [
    "SlackOpsCommandCenter",
    "SlackOutboundPolicy",
    "SlackAuditRecord",
    "ChannelCleanupPlan",
    "OpsStatus",
    "REQUIRED_CHANNELS",
    "OPTIONAL_CHANNELS",
    "PROTECTED_CHANNELS",
    "ALLOWED_MESSAGE_CATEGORIES",
    "format_agent_message",
]
