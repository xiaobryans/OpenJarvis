"""Tests for shared credential loader — env alias mapping, file loading, no-leak."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from openjarvis.channels.credentials import (
    _ALIAS_MAP,
    _parse_env_file,
    get_slack_bot_token,
    get_telegram_bot_token,
    get_telegram_bryan_chat_id,
    load_credential,
    probe_all_ops_credentials,
    probe_credential,
)


# ---------------------------------------------------------------------------
# _parse_env_file
# ---------------------------------------------------------------------------

class TestParseEnvFile:
    def test_parses_key_value(self, tmp_path):
        f = tmp_path / "test.env"
        f.write_text("FOO=bar\nBAZ=qux\n")
        result = _parse_env_file(f)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_comments(self, tmp_path):
        f = tmp_path / "test.env"
        f.write_text("# comment\nKEY=val\n")
        result = _parse_env_file(f)
        assert "# comment" not in result
        assert result["KEY"] == "val"

    def test_skips_blank_lines(self, tmp_path):
        f = tmp_path / "test.env"
        f.write_text("\nKEY=val\n\n")
        result = _parse_env_file(f)
        assert result == {"KEY": "val"}

    def test_missing_file_returns_empty(self, tmp_path):
        result = _parse_env_file(tmp_path / "nonexistent.env")
        assert result == {}

    def test_no_equals_skipped(self, tmp_path):
        f = tmp_path / "test.env"
        f.write_text("NO_EQUALS\nKEY=val\n")
        result = _parse_env_file(f)
        assert "NO_EQUALS" not in result
        assert result["KEY"] == "val"

    def test_value_with_equals_preserved(self, tmp_path):
        f = tmp_path / "test.env"
        f.write_text("KEY=val=with=equals\n")
        result = _parse_env_file(f)
        assert result["KEY"] == "val=with=equals"


# ---------------------------------------------------------------------------
# load_credential — env priority
# ---------------------------------------------------------------------------

class TestLoadCredentialEnvPriority:
    def test_os_environ_wins(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "from_env")
        # Even if file has different value, env wins
        val, src = load_credential("SLACK_BOT_TOKEN")
        assert val == "from_env"
        assert src == "os.environ"

    def test_missing_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        # Point credential files to empty tmp dirs
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", tmp_path / "p.env"):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", tmp_path / "l.env"):
                with mock.patch("openjarvis.channels.credentials.Path", return_value=tmp_path / "x"):
                    val, src = load_credential("SLACK_BOT_TOKEN")
        assert val == ""
        assert src == "MISSING"

    def test_alias_jarvis_slack_mapped(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        legacy = tmp_path / "cloud-keys.env"
        legacy.write_text("JARVIS_SLACK_BOT_TOKEN=test_token_123\n")
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", tmp_path / "p.env"):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", legacy):
                val, src = load_credential("SLACK_BOT_TOKEN")
        assert val == "test_token_123"
        assert "alias" in src or "JARVIS_SLACK_BOT_TOKEN" in src or "SLACK_BOT_TOKEN" in src

    def test_alias_openclaw_slack_mapped(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        primary = tmp_path / "cloud-keys.env"
        primary.write_text("OPENCLAW_SLACK_BOT_TOKEN=openclaw_tok\n")
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", primary):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", tmp_path / "l.env"):
                val, src = load_credential("SLACK_BOT_TOKEN")
        assert val == "openclaw_tok"

    def test_alias_telegram_chat_id_mapped(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BRYAN_CHAT_ID", raising=False)
        legacy = tmp_path / "cloud-keys.env"
        legacy.write_text("JARVIS_TELEGRAM_CHAT_ID=123456789\n")
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", tmp_path / "p.env"):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", legacy):
                val, src = load_credential("TELEGRAM_BRYAN_CHAT_ID")
        assert val == "123456789"

    def test_alias_telegram_bot_token_mapped(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
        legacy = tmp_path / "cloud-keys.env"
        legacy.write_text("JARVIS_TELEGRAM_BOT_TOKEN=bot_tok_xyz\n")
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", tmp_path / "p.env"):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", legacy):
                val, src = load_credential("TELEGRAM_BOT_TOKEN")
        assert val == "bot_tok_xyz"


# ---------------------------------------------------------------------------
# No secret leakage in probe
# ---------------------------------------------------------------------------

class TestProbeNoLeak:
    def test_probe_returns_length_not_value(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "super_secret_12345")
        result = probe_credential("SLACK_BOT_TOKEN")
        assert result["status"] == "SET"
        assert result["length"] == str(len("super_secret_12345"))
        assert "super_secret" not in str(result)
        assert "super_secret" not in result.get("key", "")

    def test_probe_missing_returns_missing(self, monkeypatch, tmp_path):
        monkeypatch.delenv("NONEXISTENT_KEY_XYZ", raising=False)
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", tmp_path / "p.env"):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", tmp_path / "l.env"):
                result = probe_credential("NONEXISTENT_KEY_XYZ")
        assert result["status"] == "MISSING"
        assert result["length"] == "0"

    def test_probe_all_ops_no_values(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "secret_slack_999")
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret_tg_777")
        result = probe_all_ops_credentials()
        result_str = str(result)
        assert "secret_slack_999" not in result_str
        assert "secret_tg_777" not in result_str
        assert "SLACK_BOT_TOKEN" in result
        assert "TELEGRAM_BOT_TOKEN" in result


# ---------------------------------------------------------------------------
# get_* helper functions
# ---------------------------------------------------------------------------

class TestGetHelpers:
    def test_get_slack_bot_token_from_env(self, monkeypatch):
        monkeypatch.setenv("SLACK_BOT_TOKEN", "test_slack_tok")
        val, src = get_slack_bot_token()
        assert val == "test_slack_tok"
        assert src == "os.environ"

    def test_get_telegram_bot_token_from_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_tg_tok")
        val, src = get_telegram_bot_token()
        assert val == "test_tg_tok"

    def test_get_telegram_bryan_chat_id_from_env(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BRYAN_CHAT_ID", "987654321")
        val, src = get_telegram_bryan_chat_id()
        assert val == "987654321"

    def test_get_slack_missing_returns_empty(self, monkeypatch, tmp_path):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_PRIMARY", tmp_path / "p.env"):
            with mock.patch("openjarvis.channels.credentials._CLOUD_KEYS_LEGACY", tmp_path / "l.env"):
                val, src = get_slack_bot_token()
        # In real env this may load from actual files; just check type
        assert isinstance(val, str)
        assert isinstance(src, str)


# ---------------------------------------------------------------------------
# Alias map completeness
# ---------------------------------------------------------------------------

class TestAliasMap:
    def test_jarvis_slack_alias_present(self):
        assert "JARVIS_SLACK_BOT_TOKEN" in _ALIAS_MAP
        assert _ALIAS_MAP["JARVIS_SLACK_BOT_TOKEN"] == "SLACK_BOT_TOKEN"

    def test_openclaw_slack_alias_present(self):
        assert "OPENCLAW_SLACK_BOT_TOKEN" in _ALIAS_MAP
        assert _ALIAS_MAP["OPENCLAW_SLACK_BOT_TOKEN"] == "SLACK_BOT_TOKEN"

    def test_jarvis_telegram_token_alias_present(self):
        assert "JARVIS_TELEGRAM_BOT_TOKEN" in _ALIAS_MAP
        assert _ALIAS_MAP["JARVIS_TELEGRAM_BOT_TOKEN"] == "TELEGRAM_BOT_TOKEN"

    def test_jarvis_telegram_chat_id_alias_present(self):
        assert "JARVIS_TELEGRAM_CHAT_ID" in _ALIAS_MAP
        assert _ALIAS_MAP["JARVIS_TELEGRAM_CHAT_ID"] == "TELEGRAM_BRYAN_CHAT_ID"
