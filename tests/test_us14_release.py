"""US14 Release & Distribution Hardening — scoped tests.

Covers:
  1. secret_scan_text finds no secrets in clean artifact text
  2. secret_scan_text finds secrets in dirty artifact text
  3. Version metadata fields present and correct types
  4. pyproject.toml version readable and semver-like
  5. tauri.conf.json version readable and semver-like
  6. redact_log_text removes secrets before any log export
  7. CredentialStripper does not crash on large input
  8. doctor_routes _get_app_version() falls back gracefully
  9. _get_git_commit() returns 7-char hex or 'unknown'
  10. _get_git_branch() returns non-empty string or 'unknown'
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# 1–2. secret_scan_text — clean vs dirty artifact
# ---------------------------------------------------------------------------


class TestSecretScanArtifact:
    def test_clean_artifact_no_findings(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        clean = (
            "OpenJarvis v1.0.2\n"
            "Build: localhost-get-tool / dc94532\n"
            "Status: ready\n"
            "No secrets in this bundle.\n"
        )
        findings = secret_scan_text(clean)
        assert findings == []

    def test_dirty_artifact_flagged(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        dirty = "JARVIS_OPENAI_API_KEY=sk-aaaabbbbccccddddeeee1234 export it!"
        findings = secret_scan_text(dirty)
        assert len(findings) >= 1

    def test_finding_preview_not_full_secret(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        secret = "sk-" + "a" * 30
        findings = secret_scan_text(f"key={secret}")
        assert any(f["match_preview"] != secret for f in findings)

    def test_large_input_no_crash(self):
        from openjarvis.security.credential_stripper import secret_scan_text

        large = "safe log line\n" * 10_000
        result = secret_scan_text(large)
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 3. Version metadata fields
# ---------------------------------------------------------------------------


class TestVersionMetadata:
    def test_get_app_version_is_string(self):
        from openjarvis.server.doctor_routes import _get_app_version

        v = _get_app_version()
        assert isinstance(v, str)

    def test_get_app_version_not_empty(self):
        from openjarvis.server.doctor_routes import _get_app_version

        assert _get_app_version() != ""

    def test_get_git_commit_str(self):
        from openjarvis.server.doctor_routes import _get_git_commit

        c = _get_git_commit()
        assert isinstance(c, str)
        assert c != ""

    def test_get_git_branch_str(self):
        from openjarvis.server.doctor_routes import _get_git_branch

        b = _get_git_branch()
        assert isinstance(b, str)
        assert b != ""

    def test_git_commit_looks_like_sha_or_unknown(self):
        from openjarvis.server.doctor_routes import _get_git_commit

        c = _get_git_commit()
        assert c == "unknown" or re.match(r"^[0-9a-f]{4,40}$", c), (
            f"git_commit unexpected format: {c!r}"
        )

    def test_git_branch_no_newlines(self):
        from openjarvis.server.doctor_routes import _get_git_branch

        b = _get_git_branch()
        assert "\n" not in b
        assert "\r" not in b


# ---------------------------------------------------------------------------
# 4. pyproject.toml version
# ---------------------------------------------------------------------------


class TestPyprojectVersion:
    def test_pyproject_toml_exists(self):
        assert (_REPO_ROOT / "pyproject.toml").exists()

    def test_pyproject_version_semver_like(self):
        import re as _re

        content = (_REPO_ROOT / "pyproject.toml").read_text()
        match = _re.search(r'^version\s*=\s*"([^"]+)"', content, _re.MULTILINE)
        assert match is not None, "version not found in pyproject.toml"
        version = match.group(1)
        assert _re.match(r"^\d+\.\d+", version), (
            f"version {version!r} does not look like semver"
        )


# ---------------------------------------------------------------------------
# 5. tauri.conf.json version
# ---------------------------------------------------------------------------


class TestTauriVersion:
    def test_tauri_conf_exists(self):
        assert (_REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json").exists()

    def test_tauri_version_semver_like(self):
        import json, re as _re

        conf = json.loads(
            (_REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json").read_text()
        )
        version = conf.get("version", "")
        assert version, "version key missing from tauri.conf.json"
        assert _re.match(r"^\d+\.\d+", version), (
            f"tauri version {version!r} does not look like semver"
        )

    def test_tauri_signing_identity_set(self):
        import json

        conf = json.loads(
            (_REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json").read_text()
        )
        identity = (
            conf.get("bundle", {})
            .get("macOS", {})
            .get("signingIdentity")
        )
        assert identity is not None, "macOS signingIdentity not set in tauri.conf.json"


# ---------------------------------------------------------------------------
# 6. redact_log_text for export safety
# ---------------------------------------------------------------------------


class TestRedactBeforeExport:
    def test_export_bundle_redacted(self):
        from openjarvis.security.credential_stripper import redact_log_text

        bundle = (
            "2026-06-18 10:00:00 [info] Starting up\n"
            "2026-06-18 10:00:01 [info] api_key=sk-abcdefghijklmnopqrst12345\n"
            "2026-06-18 10:00:02 [info] Ready\n"
        )
        redacted = redact_log_text(bundle)
        assert "sk-abcdefghijklmnopqrst12345" not in redacted
        assert "[REDACTED:" in redacted
        assert "Starting up" in redacted
        assert "Ready" in redacted

    def test_no_secrets_in_clean_export(self):
        from openjarvis.security.credential_stripper import (
            redact_log_text,
            secret_scan_text,
        )

        dirty = "token=" + "x" + "oxb-" + "123456789012-123456789012-abcdefghijklmnopqrst"
        safe = redact_log_text(dirty)
        findings = secret_scan_text(safe)
        assert len(findings) == 0, (
            f"Secrets still present after redact_log_text: {findings}"
        )


# ---------------------------------------------------------------------------
# 7. CredentialStripper large input
# ---------------------------------------------------------------------------


class TestCredentialStripperRobustness:
    def test_large_input_no_crash(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        large = "safe text line\n" * 50_000
        result = CredentialStripper().strip(large)
        assert isinstance(result, str)

    def test_strip_returns_same_type(self):
        from openjarvis.security.credential_stripper import CredentialStripper

        assert isinstance(CredentialStripper().strip("hello"), str)
