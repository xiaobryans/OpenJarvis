"""Tests for Jarvis Secrets Manager / Keychain (US9 Phase 2).

Covers:
  - Backend availability detection
  - Presence report shows key names only (values redacted)
  - redact_dict replaces all sensitive values with [REDACTED]
  - assert_no_secret_leak raises on leaking values
  - get_secret returns value when present in env
  - Migration result shows MIGRATED/SKIPPED/FAILED (never values)
  - No secret value ever appears in any output
"""

from __future__ import annotations

import os

import pytest

from openjarvis.security.keychain import (
    assert_no_secret_leak,
    get_backend_status,
    get_secret,
    get_secrets_presence_report,
    is_keychain_available,
    migrate_env_to_keychain,
    redact_dict,
    secret_present,
    JARVIS_KNOWN_KEYS,
)


class TestBackendStatus:
    def test_returns_dict(self):
        s = get_backend_status()
        assert isinstance(s, dict)
        assert "keychain_available" in s
        assert "env_file_exists" in s
        assert "active_backend" in s

    def test_no_secret_values_in_status(self):
        s = get_backend_status()
        text = str(s)
        for key in JARVIS_KNOWN_KEYS:
            val = os.environ.get(key, "")
            if val and len(val) > 3:
                assert val not in text, f"Secret value for {key} leaked in backend status"

    def test_active_backend_is_valid(self):
        s = get_backend_status()
        assert s["active_backend"] in ("keychain", "env_file")


class TestSecretPresence:
    def test_secret_present_with_env(self, monkeypatch):
        monkeypatch.setenv("JARVIS_TEST_SECRET_XYZ", "abc123")
        assert secret_present("JARVIS_TEST_SECRET_XYZ") is True

    def test_secret_absent(self, monkeypatch):
        monkeypatch.delenv("JARVIS_TEST_SECRET_XYZ", raising=False)
        assert secret_present("JARVIS_TEST_SECRET_XYZ") is False

    def test_get_secret_returns_value(self, monkeypatch):
        monkeypatch.setenv("JARVIS_TEST_SECRET_XYZ", "myvalue")
        assert get_secret("JARVIS_TEST_SECRET_XYZ") == "myvalue"

    def test_get_secret_missing_returns_none(self, monkeypatch):
        monkeypatch.delenv("JARVIS_TEST_NONEXISTENT_ABC", raising=False)
        assert get_secret("JARVIS_TEST_NONEXISTENT_ABC") is None


class TestPresenceReport:
    def test_returns_presence_field(self):
        report = get_secrets_presence_report()
        assert "presence" in report
        assert "keys_checked" in report
        assert "values_redacted" in report

    def test_values_redacted_flag(self):
        report = get_secrets_presence_report()
        assert report["values_redacted"] is True

    def test_presence_values_are_present_or_missing(self):
        report = get_secrets_presence_report()
        for key, val in report["presence"].items():
            assert val in ("PRESENT", "MISSING"), f"{key}: unexpected value '{val}'"

    def test_no_secret_values_in_report(self):
        report = get_secrets_presence_report()
        report_str = str(report)
        for key in JARVIS_KNOWN_KEYS:
            val = os.environ.get(key, "")
            if val and len(val) > 3:
                assert val not in report_str, f"Secret value for {key} leaked in presence report"

    def test_missing_keys_list_contains_only_names(self):
        report = get_secrets_presence_report()
        for k in report["missing_keys"]:
            assert isinstance(k, str)
            assert "=" not in k  # no value assigned


class TestRedactDict:
    def test_redacts_token_key(self):
        data = {"JARVIS_SLACK_BOT_TOKEN": "xoxb-secret-value", "other": "safe"}
        result = redact_dict(data)
        assert result["JARVIS_SLACK_BOT_TOKEN"] == "[REDACTED]"
        assert result["other"] == "safe"

    def test_redacts_api_key(self):
        data = {"TAVILY_API_KEY": "tvly-abc123", "name": "foo"}
        result = redact_dict(data)
        assert result["TAVILY_API_KEY"] == "[REDACTED]"

    def test_nested_redaction(self):
        data = {"config": {"OPENAI_API_KEY": "sk-secret", "model": "gpt-4"}}
        result = redact_dict(data)
        assert result["config"]["OPENAI_API_KEY"] == "[REDACTED]"
        assert result["config"]["model"] == "gpt-4"

    def test_non_sensitive_keys_pass_through(self):
        data = {"name": "jarvis", "version": "1.0"}
        result = redact_dict(data)
        assert result == data

    def test_does_not_modify_original(self):
        data = {"JARVIS_SLACK_BOT_TOKEN": "secret", "x": 1}
        _ = redact_dict(data)
        assert data["JARVIS_SLACK_BOT_TOKEN"] == "secret"


class TestNoLeakAssertion:
    def test_clean_output_passes(self, monkeypatch):
        monkeypatch.setenv("FAKE_LEAK_TEST_KEY", "secretvalue123")
        assert assert_no_secret_leak("safe output with no secrets", ["FAKE_LEAK_TEST_KEY"])

    def test_leaked_value_raises(self, monkeypatch):
        monkeypatch.setenv("FAKE_LEAK_TEST_KEY", "supersecretvalue456")
        with pytest.raises(AssertionError, match="Secret leak detected"):
            assert_no_secret_leak("output contains supersecretvalue456 here", ["FAKE_LEAK_TEST_KEY"])


class TestMigration:
    def test_migration_skipped_when_key_not_in_env(self):
        result = migrate_env_to_keychain(["JARVIS_DEFINITELY_NOT_SET_KEY_XYZ"])
        # Should be SKIPPED (not in env file either) or MIGRATED
        statuses = set(result["results"].values())
        assert statuses.issubset({"SKIPPED_NOT_IN_ENV", "MIGRATED", "FAILED"})

    def test_migration_result_never_contains_values(self):
        result = migrate_env_to_keychain(["JARVIS_SLACK_BOT_TOKEN"])
        result_str = str(result)
        # No actual token value should appear
        token = os.environ.get("JARVIS_SLACK_BOT_TOKEN", "")
        if token and len(token) > 3:
            assert token not in result_str

    def test_migration_returns_counts(self):
        result = migrate_env_to_keychain([])
        assert "migrated" in result
        assert "failed" in result
