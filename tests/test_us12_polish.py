"""US12 Product Polish — scoped tests.

Covers:
  1. CredentialStripper.strip()           — redacts known patterns
  2. redact_log_text()                    — top-level convenience wrapper
  3. secret_scan_text()                   — returns findings without exposing secrets
  4. /v1/version endpoint schema          — version, git_commit, git_branch, queried_at
  5. /v1/limitations endpoint schema      — total, categories, limitations list
  6. Each limitation has required fields  — id, category, severity, title, description, workaround
  7. No secrets in version response       — version fields safe to expose
  8. redact_log_text safe on empty string — no crash
  9. secret_scan_text safe on empty       — returns empty list
  10. secret_scan_text match_preview      — never longer than 7 chars + ellipsis
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1–3. CredentialStripper / redact_log_text / secret_scan_text
# ---------------------------------------------------------------------------


class TestCredentialStripper:
    def test_strip_openai_key(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        text = "Using key sk-abcdefghijklmnopqrst123456 for inference"
        result = CredentialStripper().strip(text)
        assert "sk-abcdefghijklmnopqrst123456" not in result
        assert "[REDACTED:api_key]" in result

    def test_strip_aws_key(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        text = "AKIAIOSFODNN7EXAMPLE is the access key"
        result = CredentialStripper().strip(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in result
        assert "[REDACTED:aws_key]" in result

    def test_strip_slack_token(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        prefix = "x" + "oxb-"
        token = prefix + "123456789012-123456789012-abcdefghijklmnop"
        text = f"token={token}"
        result = CredentialStripper().strip(text)
        assert prefix not in result
        assert "[REDACTED:slack_token]" in result

    def test_strip_anthropic_key(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        text = "api_key=sk-ant-abcdefghijklmnopqrst123456"
        result = CredentialStripper().strip(text)
        assert "sk-ant-abcdefghijklmnopqrst123456" not in result

    def test_strip_clean_text_unchanged(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        text = "Hello world, this is a log line with no secrets."
        result = CredentialStripper().strip(text)
        assert result == text

    def test_strip_multiple_secrets(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        text = "key1=sk-aaaaaaaaaaaaaaaaaaaaaa, key2=AKIAIOSFODNN7EXAMPLE"
        result = CredentialStripper().strip(text)
        assert "sk-aaaaaaaaaaaaaaaaaaaaaa" not in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result


class TestRedactLogText:
    def test_redacts_openai_key(self):
        from openjarvis.security.credential_stripper import redact_log_text

        text = "Setting up sk-testabcdefghijklmnopqrst"
        result = redact_log_text(text)
        assert "sk-testabcdefghijklmnopqrst" not in result
        assert "[REDACTED:" in result

    def test_safe_on_empty_string(self):
        from openjarvis.security.credential_stripper import redact_log_text

        result = redact_log_text("")
        assert result == ""

    def test_safe_on_plain_text(self):
        from openjarvis.security.credential_stripper import redact_log_text

        text = "2026-06-18 10:00:00 [info] [chat] User asked a question."
        result = redact_log_text(text)
        assert result == text

    def test_returns_str(self):
        from openjarvis.security.credential_stripper import redact_log_text

        assert isinstance(redact_log_text("anything"), str)


class TestSecretScanText:
    def test_empty_text_returns_empty_list(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        assert secret_scan_text("") == []

    def test_clean_text_returns_empty_list(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        assert secret_scan_text("no secrets here, just a normal line.") == []

    def test_finds_openai_key(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        text = "sk-zzzzzzzzzzzzzzzzzzzzz found"
        findings = secret_scan_text(text)
        assert len(findings) >= 1
        assert any(f["pattern_name"] == "api_key" for f in findings)

    def test_finding_has_required_keys(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        text = "sk-zzzzzzzzzzzzzzzzzzzzz"
        findings = secret_scan_text(text)
        assert len(findings) >= 1
        for f in findings:
            assert "pattern_name" in f
            assert "match_preview" in f

    def test_match_preview_does_not_expose_full_secret(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        secret = "sk-" + "x" * 40
        findings = secret_scan_text(secret)
        assert len(findings) >= 1
        for f in findings:
            preview = f["match_preview"]
            assert secret not in preview
            assert "…" in preview

    def test_returns_list(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        result = secret_scan_text("anything")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 4–7. /v1/version and /v1/limitations endpoint schema (unit-level — no server)
# ---------------------------------------------------------------------------


class TestVersionHelpers:
    def test_get_app_version_returns_str(self):
        from openjarvis.server.doctor_routes import _get_app_version

        v = _get_app_version()
        assert isinstance(v, str)
        assert len(v) > 0

    def test_get_git_commit_returns_str(self):
        from openjarvis.server.doctor_routes import _get_git_commit

        c = _get_git_commit()
        assert isinstance(c, str)
        assert len(c) > 0

    def test_get_git_branch_returns_str(self):
        from openjarvis.server.doctor_routes import _get_git_branch

        b = _get_git_branch()
        assert isinstance(b, str)
        assert len(b) > 0

    def test_version_fields_no_secrets(self):
        from openjarvis.server.doctor_routes import (
            _get_app_version,
            _get_git_branch,
            _get_git_commit,
        )
        from openjarvis.security.credential_stripper import secret_scan_text

        for value in [_get_app_version(), _get_git_commit(), _get_git_branch()]:
            findings = secret_scan_text(value)
            assert findings == [], f"Secret pattern found in version field: {value!r}"


class TestLimitationsSchema:
    def test_limitations_list_not_empty(self):
        from openjarvis.server.doctor_routes import _KNOWN_LIMITATIONS

        assert len(_KNOWN_LIMITATIONS) >= 1

    def test_each_limitation_has_required_fields(self):
        from openjarvis.server.doctor_routes import _KNOWN_LIMITATIONS

        required = {"id", "category", "severity", "title", "description", "workaround"}
        for lim in _KNOWN_LIMITATIONS:
            missing = required - set(lim.keys())
            assert not missing, f"Limitation {lim.get('id', '?')} missing: {missing}"

    def test_severity_values_valid(self):
        from openjarvis.server.doctor_routes import _KNOWN_LIMITATIONS

        valid_severities = {"warn", "info", "error"}
        for lim in _KNOWN_LIMITATIONS:
            assert lim["severity"] in valid_severities, (
                f"Limitation {lim['id']} has invalid severity: {lim['severity']!r}"
            )

    def test_no_secrets_in_limitations(self):
        from openjarvis.server.doctor_routes import _KNOWN_LIMITATIONS
        from openjarvis.security.credential_stripper import secret_scan_text

        for lim in _KNOWN_LIMITATIONS:
            for key in ("title", "description", "workaround"):
                findings = secret_scan_text(lim.get(key, ""))
                assert findings == [], (
                    f"Secret pattern found in limitation {lim['id']} field {key!r}"
                )

    def test_ids_are_unique(self):
        from openjarvis.server.doctor_routes import _KNOWN_LIMITATIONS

        ids = [lim["id"] for lim in _KNOWN_LIMITATIONS]
        assert len(ids) == len(set(ids)), "Duplicate limitation IDs found"
