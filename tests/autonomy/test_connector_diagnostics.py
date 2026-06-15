"""Tests for ConnectorDiagnostics — Slack/Telegram/Web/GitHub/OpenClaw (US8 Phase H).

Covers:
  - get_slack_status returns valid status and never prints tokens
  - get_telegram_status returns valid status and never prints tokens
  - draft_slack_test_send always send_status=not_sent
  - draft_telegram_test_send always send_status=not_sent
  - get_web_search_status returns not_configured when no keys
  - get_github_status returns git_available field
  - get_github_local_remote_info returns ok or error dict
  - get_openclaw_status returns not_configured when vars unset
  - read_openclaw_handoff_summary returns ok=False when OPENCLAW_HANDOFF_PATH unset
  - token values never appear in any output
"""

from __future__ import annotations

import os

import pytest

from openjarvis.autonomy.connector_diagnostics import (
    ConnectorStatus,
    draft_slack_test_send,
    draft_telegram_test_send,
    get_github_local_remote_info,
    get_github_status,
    get_openclaw_status,
    get_slack_status,
    get_telegram_approval_preview,
    get_telegram_command_status,
    get_telegram_status,
    get_web_search_status,
    read_openclaw_handoff_summary,
)

VALID_STATUSES = {
    ConnectorStatus.CONFIGURED,
    ConnectorStatus.NOT_CONFIGURED,
    ConnectorStatus.READY_PENDING_TEST,
    ConnectorStatus.DEGRADED,
}


class TestSlackStatus:
    def test_returns_connector_field(self):
        r = get_slack_status()
        assert r["connector"] == "slack"

    def test_returns_valid_status(self):
        r = get_slack_status()
        assert r["status"] in VALID_STATUSES

    def test_not_configured_when_no_env(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_SLACK_TEST_CHANNEL_ID", raising=False)
        r = get_slack_status()
        assert r["status"] == ConnectorStatus.NOT_CONFIGURED
        assert r["bot_token_present"] is False

    def test_token_value_not_in_output(self, monkeypatch):
        fake_token = "xoxb-SUPERSECRET123"
        monkeypatch.setenv("JARVIS_SLACK_BOT_TOKEN", fake_token)
        r = get_slack_status()
        # Serialize to string and check no token value
        output_str = str(r)
        assert fake_token not in output_str

    def test_missing_env_vars_listed(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_SLACK_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_SLACK_BOT_TOKEN", raising=False)
        r = get_slack_status()
        assert len(r["missing_env_vars"]) >= 1

    def test_real_send_allowed_false(self):
        r = get_slack_status()
        assert r["real_send_allowed"] is False

    def test_has_required_env_vars_list(self):
        r = get_slack_status()
        assert "required_env_vars" in r
        assert len(r["required_env_vars"]) >= 1


class TestSlackDraftSend:
    def test_send_status_always_not_sent(self):
        r = draft_slack_test_send("test message")
        assert r["send_status"] == "not_sent"

    def test_approval_required_true(self):
        r = draft_slack_test_send("test message")
        assert r["approval_required"] is True

    def test_draft_text_present(self):
        r = draft_slack_test_send("hello")
        assert "draft_text" in r
        assert "DRAFT" in r["draft_text"] or "draft" in r["draft_text"].lower()

    def test_note_present(self):
        r = draft_slack_test_send("hello")
        assert "note" in r


class TestTelegramStatus:
    def test_returns_connector_field(self):
        r = get_telegram_status()
        assert r["connector"] == "telegram"

    def test_returns_valid_status(self):
        r = get_telegram_status()
        assert r["status"] in VALID_STATUSES

    def test_not_configured_when_no_env(self, monkeypatch):
        monkeypatch.delenv("JARVIS_TELEGRAM_BOT_TOKEN", raising=False)
        monkeypatch.delenv("JARVIS_TELEGRAM_CHAT_ID", raising=False)
        r = get_telegram_status()
        assert r["status"] == ConnectorStatus.NOT_CONFIGURED

    def test_token_value_not_in_output(self, monkeypatch):
        fake_token = "123456:SUPERSECRET-TOKEN"
        monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", fake_token)
        r = get_telegram_status()
        assert fake_token not in str(r)

    def test_real_send_allowed_false(self):
        r = get_telegram_status()
        assert r["real_send_allowed"] is False

    def test_configured_when_both_vars_set(self, monkeypatch):
        monkeypatch.setenv("JARVIS_TELEGRAM_BOT_TOKEN", "bot123:fake")
        monkeypatch.setenv("JARVIS_TELEGRAM_CHAT_ID", "12345")
        r = get_telegram_status()
        assert r["configured"] is True
        assert r["status"] in (
            ConnectorStatus.CONFIGURED, ConnectorStatus.READY_PENDING_TEST
        )


class TestTelegramDraftSend:
    def test_send_status_always_not_sent(self):
        r = draft_telegram_test_send("test")
        assert r["send_status"] == "not_sent"

    def test_approval_required_true(self):
        r = draft_telegram_test_send("test")
        assert r["approval_required"] is True


class TestTelegramCommandStatus:
    def test_returns_command_field(self):
        r = get_telegram_command_status("/status")
        assert r["command"] == "/status"

    def test_preview_only_true(self):
        r = get_telegram_command_status("/status")
        assert r["preview_only"] is True

    def test_would_execute_false(self):
        r = get_telegram_command_status("/status")
        assert r["would_execute"] is False


class TestTelegramApprovalPreview:
    def test_send_status_not_sent(self):
        r = get_telegram_approval_preview("test_action", "description")
        assert r["send_status"] == "not_sent"

    def test_draft_message_present(self):
        r = get_telegram_approval_preview("test_action")
        assert "draft_message" in r
        assert "test_action" in r["draft_message"]

    def test_preview_only_true(self):
        r = get_telegram_approval_preview("test_action")
        assert r["preview_only"] is True


class TestWebSearchStatus:
    def test_not_configured_when_no_keys(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        r = get_web_search_status()
        assert r["status"] == ConnectorStatus.NOT_CONFIGURED
        assert r["provider"] is None

    def test_configured_with_tavily(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "fake-tavily-key")
        r = get_web_search_status()
        assert r["status"] == ConnectorStatus.CONFIGURED
        assert r["provider"] == "tavily"

    def test_key_value_not_in_output(self, monkeypatch):
        fake_key = "tavily-SUPERSECRET-KEY"
        monkeypatch.setenv("TAVILY_API_KEY", fake_key)
        r = get_web_search_status()
        assert fake_key not in str(r)

    def test_returns_setup_options_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        monkeypatch.delenv("SERPER_API_KEY", raising=False)
        monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
        r = get_web_search_status()
        assert "setup_options" in r or "missing_env_vars" in r


class TestGitHubStatus:
    def test_returns_connector_field(self):
        r = get_github_status()
        assert r["connector"] == "github"

    def test_returns_git_available_field(self):
        r = get_github_status()
        assert "git_available" in r
        assert isinstance(r["git_available"], bool)

    def test_read_only_true(self):
        r = get_github_status()
        assert r["read_only"] is True

    def test_merges_always_blocked(self):
        r = get_github_status()
        assert r["merges"] == "always_blocked"

    def test_token_value_not_in_output(self, monkeypatch):
        fake_token = "ghp_SUPERSECRETOKEN123"
        monkeypatch.setenv("GITHUB_TOKEN", fake_token)
        r = get_github_status()
        assert fake_token not in str(r)


class TestGitHubLocalRemoteInfo:
    def test_returns_dict(self):
        r = get_github_local_remote_info()
        assert isinstance(r, dict)

    def test_has_ok_field(self):
        r = get_github_local_remote_info()
        assert "ok" in r

    def test_read_only_on_success(self):
        r = get_github_local_remote_info()
        if r["ok"]:
            assert r.get("read_only") is True


class TestOpenClawStatus:
    def test_not_configured_when_no_env(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_WORKSPACE_PATH", raising=False)
        monkeypatch.delenv("OPENCLAW_HANDOFF_PATH", raising=False)
        r = get_openclaw_status()
        assert r["status"] == ConnectorStatus.NOT_CONFIGURED

    def test_returns_connector_field(self):
        r = get_openclaw_status()
        assert r["connector"] == "openclaw"

    def test_read_only_true(self):
        r = get_openclaw_status()
        assert r["read_only"] is True

    def test_mutations_allowed_false(self):
        r = get_openclaw_status()
        assert r["mutations_allowed"] is False

    def test_missing_env_vars_listed(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_WORKSPACE_PATH", raising=False)
        monkeypatch.delenv("OPENCLAW_HANDOFF_PATH", raising=False)
        r = get_openclaw_status()
        assert len(r["missing_env_vars"]) >= 1


class TestOpenClawHandoffRead:
    def test_ok_false_when_path_not_set(self, monkeypatch):
        monkeypatch.delenv("OPENCLAW_HANDOFF_PATH", raising=False)
        r = read_openclaw_handoff_summary()
        assert r["ok"] is False
        assert "blocker" in r

    def test_ok_false_when_path_not_exists(self, monkeypatch):
        monkeypatch.setenv("OPENCLAW_HANDOFF_PATH", "/nonexistent/path/handoff.md")
        r = read_openclaw_handoff_summary()
        assert r["ok"] is False
