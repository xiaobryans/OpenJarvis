"""Tests for Slack Ops Command Center — policy, rate limits, guardrails, audit."""

from __future__ import annotations

import os
from unittest import mock

import pytest

from openjarvis.channels.slack_ops import (
    ALLOWED_MESSAGE_CATEGORIES,
    PROTECTED_CHANNELS,
    REQUIRED_CHANNELS,
    ChannelCleanupPlan,
    OpsStatus,
    SlackAuditRecord,
    SlackOpsCommandCenter,
    SlackOutboundPolicy,
    format_agent_message,
)


class TestSlackOutboundPolicy:
    def test_allowed_channel_and_category_passes(self):
        policy = SlackOutboundPolicy(rate_limit=10)
        allowed, reason = policy.check_send("jarvis-ops", "sprint_status_update")
        assert allowed is True

    def test_disallowed_channel_blocked(self):
        policy = SlackOutboundPolicy(rate_limit=10)
        allowed, reason = policy.check_send("random-channel-xyz", "sprint_status_update")
        assert allowed is False
        assert "allowlist" in reason

    def test_disallowed_category_blocked(self):
        policy = SlackOutboundPolicy(rate_limit=10)
        allowed, reason = policy.check_send("jarvis-ops", "send_customer_email")
        assert allowed is False

    def test_protected_channel_blocked(self):
        policy = SlackOutboundPolicy(rate_limit=10)
        allowed, reason = policy.check_send("general", "sprint_status_update")
        assert allowed is False
        assert "protected" in reason.lower()

    def test_blocked_surface_blocked(self):
        policy = SlackOutboundPolicy(rate_limit=10)
        allowed, reason = policy.check_send("jarvis-ops", "sprint_status_update", surface="gmail")
        assert allowed is False
        assert "blocked" in reason.lower()

    def test_rate_limit_enforced(self):
        policy = SlackOutboundPolicy(rate_limit=2)
        policy.record_send("jarvis-ops", "sprint_status_update", OpsStatus.SENT)
        policy.record_send("jarvis-ops", "sprint_status_update", OpsStatus.SENT)
        allowed, reason = policy.check_send("jarvis-ops", "sprint_status_update")
        assert allowed is False
        assert "Rate limit" in reason

    def test_protected_channel_delete_blocked(self):
        policy = SlackOutboundPolicy()
        allowed, reason = policy.check_channel_delete("general")
        assert allowed is False
        assert "protected" in reason.lower()

    def test_non_protected_channel_delete_allowed(self):
        policy = SlackOutboundPolicy()
        allowed, reason = policy.check_channel_delete("jarvis-debug")
        assert allowed is True

    def test_workspace_delete_blocked_without_flag(self):
        policy = SlackOutboundPolicy()
        with mock.patch.dict(os.environ, {"BRYAN_APPROVES_SLACK_WORKSPACE_DELETE": ""}):
            allowed, reason = policy.check_workspace_delete("T123", "TestWorkspace")
        assert allowed is False
        assert "BLOCKED_USER_AUTHORIZATION" in reason

    def test_workspace_delete_allowed_with_flag(self):
        policy = SlackOutboundPolicy()
        with mock.patch.dict(os.environ, {"BRYAN_APPROVES_SLACK_WORKSPACE_DELETE": "true"}):
            allowed, reason = policy.check_workspace_delete("T123", "TestWorkspace")
        assert allowed is True

    def test_audit_log_written_on_record(self):
        policy = SlackOutboundPolicy()
        policy.record_send("jarvis-ops", "sprint_status_update", OpsStatus.SENT)
        log = policy.get_audit_log()
        assert len(log) == 1
        entry = log[0]
        assert entry["status"] == "SENT"
        assert entry["target_channel"] == "jarvis-ops"

    def test_sent_count_increments_only_on_sent(self):
        policy = SlackOutboundPolicy()
        policy.record_send("jarvis-ops", "sprint_status_update", OpsStatus.SENT)
        policy.record_send("jarvis-ops", "sprint_status_update", OpsStatus.BLOCKED_POLICY)
        assert policy.get_sent_count() == 1

    def test_remaining_budget_decrements(self):
        policy = SlackOutboundPolicy(rate_limit=5)
        policy.record_send("jarvis-ops", "sprint_status_update", OpsStatus.SENT)
        assert policy.get_remaining_budget() == 4


class TestSlackOpsCommandCenter:
    def test_blocked_without_token(self):
        # Patch credential loader to return empty token for isolation
        with mock.patch("openjarvis.channels.credentials.get_slack_bot_token", return_value=("", "MISSING")):
            center = SlackOpsCommandCenter(bot_token="")
            record = center.send_ops_message(
                "jarvis-ops", "test msg", "sprint_status_update"
            )
        assert record.status in (OpsStatus.BLOCKED_CREDENTIALS, OpsStatus.BLOCKED_POLICY)

    def test_smoke_test_blocked_channel_protected(self):
        center = SlackOpsCommandCenter(bot_token="fake-token")
        # Trying to smoke test #general should be blocked (protected)
        with mock.patch.object(center._policy, "check_send", return_value=(False, "protected")):
            record = center.send_ops_message("general", "test", "smoke_test_notification")
        assert record.status == OpsStatus.BLOCKED_POLICY

    def test_audit_log_accessible(self):
        center = SlackOpsCommandCenter(bot_token="")
        with mock.patch.dict(os.environ, {"SLACK_BOT_TOKEN": ""}):
            center.send_ops_message("jarvis-ops", "test", "sprint_status_update")
        log = center.get_audit_log()
        assert len(log) >= 1

    def test_generate_cleanup_plan(self):
        center = SlackOpsCommandCenter()
        existing = ["general", "random", "jarvis-ops", "old-omnix-test"]
        plan = center.generate_cleanup_plan(existing_channels=existing)
        assert isinstance(plan, ChannelCleanupPlan)
        # Required channels not in existing should be in to_create
        for req in REQUIRED_CHANNELS:
            if req not in existing:
                assert req in plan.channels_to_create
        # Protected channels should be skipped
        assert "general" in plan.protected_channels_skipped or "general" in plan.channels_to_keep

    def test_format_agent_message_manager(self):
        msg = format_agent_message("Jarvis Coding Manager", "Assigning task to repo-inspector.")
        assert msg.startswith("[Jarvis Coding Manager]")
        assert "Assigning task" in msg

    def test_format_agent_message_worker(self):
        msg = format_agent_message("Jarvis Coding Manager", "Found 3 files.", worker_name="repo-inspector")
        assert "[Worker: repo-inspector]" in msg

    def test_gmail_surface_blocked(self):
        center = SlackOpsCommandCenter(bot_token="fake")
        record = center.send_ops_message(
            "jarvis-ops", "email content", "sprint_status_update", 
        )
        # Check that gmail surface is blocked at policy level
        policy = SlackOutboundPolicy()
        allowed, reason = policy.check_send("jarvis-ops", "sprint_status_update", surface="gmail")
        assert allowed is False


class TestRequiredChannels:
    def test_all_required_channels_in_allowlist(self):
        policy = SlackOutboundPolicy()
        for ch in REQUIRED_CHANNELS:
            allowed, _ = policy.check_send(ch, "sprint_status_update")
            assert allowed is True, f"#{ch} should be allowed but was blocked"

    def test_protected_channels_not_writable(self):
        policy = SlackOutboundPolicy()
        for ch in PROTECTED_CHANNELS:
            allowed, _ = policy.check_send(ch, "sprint_status_update")
            assert allowed is False, f"#{ch} is protected and should be blocked"
