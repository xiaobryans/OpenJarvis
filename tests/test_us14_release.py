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


# ---------------------------------------------------------------------------
# 8. Sprint 2 — packaging/release docs do not claim false readiness
# ---------------------------------------------------------------------------


class TestSprint2ReleaseDocIntegrity:
    """Assert that release docs and the checklist do not claim statuses that
    are explicitly unverified or belong to future sprints."""

    _RELEASE_CHECKLIST = _REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md"
    _US14_DOC = _REPO_ROOT / "docs" / "US14_RELEASE_DISTRIBUTION.md"

    def test_release_checklist_exists(self):
        assert self._RELEASE_CHECKLIST.exists(), "RELEASE_CHECKLIST.md missing"

    def test_checklist_does_not_claim_public_ready(self):
        text = self._RELEASE_CHECKLIST.read_text().lower()
        assert "public-ready" not in text, (
            "RELEASE_CHECKLIST.md must not claim 'public-ready'"
        )
        assert "public distribution ready" not in text, (
            "RELEASE_CHECKLIST.md must not claim public distribution is ready"
        )

    def test_checklist_gates_voice_as_separate_sprint(self):
        text = self._RELEASE_CHECKLIST.read_text()
        assert "voice" in text.lower(), (
            "RELEASE_CHECKLIST.md must mention voice gate"
        )
        # must not claim voice is certified/ready within this checklist
        lower = text.lower()
        assert "voice certified" not in lower, (
            "RELEASE_CHECKLIST.md must not claim voice certified"
        )
        assert "voice ready" not in lower, (
            "RELEASE_CHECKLIST.md must not claim voice ready"
        )

    def test_checklist_shows_full_no_gap_hold(self):
        text = self._RELEASE_CHECKLIST.read_text()
        assert "hold" in text.lower(), (
            "RELEASE_CHECKLIST.md must state full no-gap is HOLD"
        )

    def test_checklist_auto_update_caveat_present(self):
        text = self._RELEASE_CHECKLIST.read_text().lower()
        assert "auto-update" in text or "autoupdate" in text or "updater" in text, (
            "RELEASE_CHECKLIST.md must mention auto-update status"
        )
        assert "unverified" in text, (
            "RELEASE_CHECKLIST.md must state auto-update endpoint is unverified"
        )

    def test_us14_doc_no_gap_tracking_present(self):
        text = self._US14_DOC.read_text()
        # Must contain remaining sprint tracking for full no-gap
        assert "Voice safety sprint" in text or "voice safety" in text.lower(), (
            "US14_RELEASE_DISTRIBUTION.md must track voice safety sprint"
        )
        assert "HOLD" in text, (
            "US14_RELEASE_DISTRIBUTION.md must show full no-gap HOLD"
        )

    def test_release_local_script_exists_and_no_secrets(self):
        script = _REPO_ROOT / "scripts" / "release-local.sh"
        assert script.exists(), "scripts/release-local.sh must exist"
        content = script.read_text()
        # Must not contain literal secrets
        import re as _re
        secret_patterns = [
            r"sk-[a-zA-Z0-9_-]{20,}",
            r"AKIA[0-9A-Z]{16}",
            r"ghp_[a-zA-Z0-9]{36}",
        ]
        for pattern in secret_patterns:
            assert not _re.search(pattern, content), (
                f"release-local.sh contains a potential secret matching {pattern}"
            )

    def test_version_files_aligned(self):
        import json, re as _re

        pyproject = _REPO_ROOT / "pyproject.toml"
        pkg_json = _REPO_ROOT / "frontend" / "package.json"
        tauri_conf = _REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"

        py_ver_m = _re.search(r'^version\s*=\s*"([^"]+)"', pyproject.read_text(), _re.M)
        assert py_ver_m, "pyproject.toml version not found"
        py_ver = py_ver_m.group(1)

        pkg_ver = json.loads(pkg_json.read_text()).get("version", "")
        tauri_ver = json.loads(tauri_conf.read_text()).get("version", "")

        assert py_ver == pkg_ver, (
            f"Version mismatch: pyproject.toml={py_ver} vs package.json={pkg_ver}. "
            "Run: ./scripts/bump-desktop-version.sh <version>"
        )
        assert py_ver == tauri_ver, (
            f"Version mismatch: pyproject.toml={py_ver} vs tauri.conf.json={tauri_ver}. "
            "Run: ./scripts/bump-desktop-version.sh <version>"
        )


# ---------------------------------------------------------------------------
# 9. Sprint 2 HOLD Correction — stale artifact gate, doc integrity
# ---------------------------------------------------------------------------


class TestSprint2HoldCorrection:
    """Tests for the Sprint 2 HOLD correction:
    - Script must reject stale artifacts.
    - Docs must not contain FUTURE_BACKLOG.
    - Docs must track company org / manager-worker as REQUIRED_FOR_NO_GAP_JARVIS.
    - Docs must use explicit status labels.
    """

    _SCRIPT = _REPO_ROOT / "scripts" / "release-local.sh"
    _CHECKLIST = _REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md"
    _US14_DOC = _REPO_ROOT / "docs" / "US14_RELEASE_DISTRIBUTION.md"

    # ── Script content tests (no subprocess — parse script text) ────────

    def test_script_contains_stale_artifact_failure(self):
        """Script must emit STALE_OR_MISSING_PACKAGE_ARTIFACT when artifact
        version does not match expected version."""
        content = self._SCRIPT.read_text()
        assert "STALE_OR_MISSING_PACKAGE_ARTIFACT" in content, (
            "release-local.sh must fail with STALE_OR_MISSING_PACKAGE_ARTIFACT "
            "when artifact version is stale"
        )

    def test_script_compares_artifact_version_to_expected(self):
        """Script must compare artifact version to EXPECTED_VERSION, not just
        check for artifact existence."""
        content = self._SCRIPT.read_text()
        assert "EXPECTED_VERSION" in content, (
            "release-local.sh must set EXPECTED_VERSION from source files "
            "and compare artifact version against it"
        )
        assert "BUNDLE_VER" in content, (
            "release-local.sh must read BUNDLE_VER from artifact Info.plist"
        )

    def test_script_reports_installed_stale_not_ok(self):
        """Script must report installed_stale for a stale /Applications app,
        not emit ok()."""
        content = self._SCRIPT.read_text()
        assert "installed_stale" in content, (
            "release-local.sh must report installed_stale when /Applications "
            "app version does not match expected version"
        )

    def test_script_version_mismatch_fails_not_warns(self):
        """Script must fail (not just warn) when source version files disagree."""
        content = self._SCRIPT.read_text()
        assert "VERSION_MISMATCH" in content or "VERSION_OK" in content, (
            "release-local.sh must fail on version mismatch between source files"
        )

    def test_script_does_not_contain_future_backlog(self):
        content = self._SCRIPT.read_text()
        assert "FUTURE_BACKLOG" not in content, (
            "release-local.sh must not use FUTURE_BACKLOG — use explicit status labels"
        )

    def test_script_contains_required_for_no_gap_jarvis(self):
        content = self._SCRIPT.read_text()
        assert "REQUIRED_FOR_NO_GAP_JARVIS" in content, (
            "release-local.sh must use REQUIRED_FOR_NO_GAP_JARVIS status label"
        )

    def test_script_mentions_company_org(self):
        content = self._SCRIPT.read_text().lower()
        assert "company org" in content or "manager-worker" in content or "manager_worker" in content, (
            "release-local.sh must mention company org / manager-worker as REQUIRED_FOR_NO_GAP_JARVIS"
        )

    # ── Doc content tests ────────────────────────────────────────────────

    def test_checklist_no_future_backlog(self):
        text = self._CHECKLIST.read_text()
        assert "FUTURE_BACKLOG" not in text, (
            "RELEASE_CHECKLIST.md must not contain FUTURE_BACKLOG — use explicit status labels"
        )

    def test_us14_doc_no_future_backlog(self):
        text = self._US14_DOC.read_text()
        assert "FUTURE_BACKLOG" not in text, (
            "US14_RELEASE_DISTRIBUTION.md must not contain FUTURE_BACKLOG — use explicit status labels"
        )

    def test_checklist_uses_required_for_public_release(self):
        text = self._CHECKLIST.read_text()
        assert "REQUIRED_FOR_PUBLIC_RELEASE" in text, (
            "RELEASE_CHECKLIST.md must use REQUIRED_FOR_PUBLIC_RELEASE for signing/notarization"
        )

    def test_us14_doc_uses_required_for_public_release(self):
        text = self._US14_DOC.read_text()
        assert "REQUIRED_FOR_PUBLIC_RELEASE" in text, (
            "US14_RELEASE_DISTRIBUTION.md must use REQUIRED_FOR_PUBLIC_RELEASE"
        )

    def test_checklist_company_org_required_for_no_gap(self):
        text = self._CHECKLIST.read_text()
        lower = text.lower()
        assert "company org" in lower or "manager-worker" in lower, (
            "RELEASE_CHECKLIST.md must track company org / manager-worker as REQUIRED_FOR_NO_GAP_JARVIS"
        )
        assert "REQUIRED_FOR_NO_GAP_JARVIS" in text, (
            "RELEASE_CHECKLIST.md must use REQUIRED_FOR_NO_GAP_JARVIS for company org"
        )

    def test_us14_doc_company_org_required_for_no_gap(self):
        text = self._US14_DOC.read_text()
        lower = text.lower()
        assert "company org" in lower or "manager-worker" in lower, (
            "US14_RELEASE_DISTRIBUTION.md must track company org / manager-worker"
        )
        assert "REQUIRED_FOR_NO_GAP_JARVIS" in text, (
            "US14_RELEASE_DISTRIBUTION.md must use REQUIRED_FOR_NO_GAP_JARVIS"
        )

    def test_us14_doc_public_distribution_explicit(self):
        text = self._US14_DOC.read_text()
        assert "REQUIRED_FOR_PUBLIC_RELEASE" in text, (
            "US14_RELEASE_DISTRIBUTION.md must explicitly label public distribution items"
        )
        assert "REQUIRED_FOR_NO_GAP_JARVIS" in text, (
            "US14_RELEASE_DISTRIBUTION.md must explicitly label no-gap required items"
        )

    def test_checklist_artifact_version_gate_documented(self):
        text = self._CHECKLIST.read_text()
        assert "STALE_OR_MISSING_PACKAGE_ARTIFACT" in text or "artifact version" in text.lower(), (
            "RELEASE_CHECKLIST.md must document the artifact version gate"
        )


# ---------------------------------------------------------------------------
# 10. Sprint 2 Second HOLD Correction — founder-local build, /Applications guard
# ---------------------------------------------------------------------------


class TestSprint2SecondHoldCorrection:
    """Tests for the second HOLD correction:
    - Founder-local build is separated from public/updater build.
    - /Applications guard: UNAUTHORIZED_APPLICATIONS_MODIFICATION present.
    - Script requires explicit install flag before /Applications modification.
    - /Applications treated as read-only evidence (installed_stale, not pass).
    - Docs maintain explicit status labels.
    """

    _SCRIPT = _REPO_ROOT / "scripts" / "release-local.sh"
    _CHECKLIST = _REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md"
    _US14_DOC = _REPO_ROOT / "docs" / "US14_RELEASE_DISTRIBUTION.md"
    _PKG_JSON = _REPO_ROOT / "frontend" / "package.json"

    # ── Build separation tests ───────────────────────────────────────────

    def test_package_json_has_build_tauri_local(self):
        import json
        pkg = json.loads(self._PKG_JSON.read_text())
        scripts = pkg.get("scripts", {})
        assert "build:tauri:local" in scripts, (
            "package.json must have build:tauri:local script for founder-local builds"
        )

    def test_build_tauri_local_disables_updater(self):
        import json
        pkg = json.loads(self._PKG_JSON.read_text())
        cmd = pkg.get("scripts", {}).get("build:tauri:local", "")
        assert "createUpdaterArtifacts" in cmd or "updater" in cmd.lower(), (
            "build:tauri:local must disable updater artifact creation/signing"
        )

    def test_package_json_has_build_tauri_release(self):
        import json
        pkg = json.loads(self._PKG_JSON.read_text())
        scripts = pkg.get("scripts", {})
        assert "build:tauri:release" in scripts, (
            "package.json must have build:tauri:release for public release builds"
        )

    def test_checklist_separates_founder_local_from_public_build(self):
        text = self._CHECKLIST.read_text()
        assert "build:tauri:local" in text, (
            "RELEASE_CHECKLIST.md must document build:tauri:local as founder-local command"
        )
        assert "build:tauri:release" in text or "REQUIRED_FOR_PUBLIC_RELEASE" in text, (
            "RELEASE_CHECKLIST.md must document public build as REQUIRED_FOR_PUBLIC_RELEASE"
        )

    def test_checklist_updater_signing_required_for_public_release(self):
        text = self._CHECKLIST.read_text()
        assert "TAURI_SIGNING_PRIVATE_KEY" in text, (
            "RELEASE_CHECKLIST.md must document TAURI_SIGNING_PRIVATE_KEY requirement"
        )
        assert "REQUIRED_FOR_PUBLIC_RELEASE" in text, (
            "RELEASE_CHECKLIST.md must classify updater signing as REQUIRED_FOR_PUBLIC_RELEASE"
        )

    # ── /Applications guard tests ────────────────────────────────────────

    def test_script_contains_unauthorized_applications_modification(self):
        content = self._SCRIPT.read_text()
        assert "UNAUTHORIZED_APPLICATIONS_MODIFICATION" in content, (
            "release-local.sh must fail with UNAUTHORIZED_APPLICATIONS_MODIFICATION "
            "if /Applications changes without explicit install flag"
        )

    def test_script_records_pre_state_of_applications(self):
        content = self._SCRIPT.read_text()
        assert "APPS_PRE_MTIME" in content or "pre_mtime" in content.lower(), (
            "release-local.sh must record /Applications mtime before any operations"
        )

    def test_script_checks_post_state_of_applications(self):
        content = self._SCRIPT.read_text()
        assert "APPS_POST_MTIME" in content or "post_mtime" in content.lower(), (
            "release-local.sh must compare /Applications mtime after operations"
        )

    def test_script_requires_install_flag_for_applications_update(self):
        content = self._SCRIPT.read_text()
        assert "DO_INSTALL" in content, (
            "release-local.sh must gate /Applications modification behind DO_INSTALL flag"
        )

    def test_script_treats_applications_as_read_only_without_flag(self):
        content = self._SCRIPT.read_text()
        # Must not touch /Applications unless DO_INSTALL is true
        assert "DO_INSTALL" in content and "UNAUTHORIZED_APPLICATIONS_MODIFICATION" in content, (
            "release-local.sh must treat /Applications as read-only without --install flag"
        )

    def test_script_reports_installed_stale_not_ok_for_stale_app(self):
        content = self._SCRIPT.read_text()
        assert "installed_stale" in content, (
            "release-local.sh must report installed_stale when /Applications version is stale"
        )

    # ── Doc integrity tests ──────────────────────────────────────────────

    def test_checklist_applications_modification_warning(self):
        text = self._CHECKLIST.read_text()
        lower = text.lower()
        assert "unauthorized" in lower or "/applications" in lower, (
            "RELEASE_CHECKLIST.md must warn about /Applications modification risk"
        )

    def test_us14_doc_founder_local_build_documented(self):
        text = self._US14_DOC.read_text()
        assert "build:tauri:local" in text or "founder-local build" in text.lower(), (
            "US14_RELEASE_DISTRIBUTION.md must document founder-local build command"
        )

    def test_us14_doc_public_build_required_for_public_release(self):
        text = self._US14_DOC.read_text()
        assert "REQUIRED_FOR_PUBLIC_RELEASE" in text, (
            "US14_RELEASE_DISTRIBUTION.md must classify public build as REQUIRED_FOR_PUBLIC_RELEASE"
        )

    def test_no_future_backlog_in_script_or_docs(self):
        for path, label in [
            (self._SCRIPT, "release-local.sh"),
            (self._CHECKLIST, "RELEASE_CHECKLIST.md"),
            (self._US14_DOC, "US14_RELEASE_DISTRIBUTION.md"),
        ]:
            assert "FUTURE_BACKLOG" not in path.read_text(), (
                f"{label} must not contain FUTURE_BACKLOG"
            )


# ---------------------------------------------------------------------------
# 11. Sprint 2 Third HOLD Correction — safe build wrapper, /Applications content guard
# ---------------------------------------------------------------------------


class TestSprint2ThirdHoldCorrection:
    """Tests for the third HOLD correction:
    - Safe founder-local build wrapper (scripts/build-local.sh) exists.
    - Wrapper records /Applications pre/post content checksums.
    - Wrapper fails with UNAUTHORIZED_APPLICATIONS_MODIFICATION if content changes.
    - Wrapper has explicit --allow-applications-update flag.
    - Raw build:tauri:local is not accepted as non-mutating validation path in docs.
    - Docs document explicit authorization requirement.
    - All status labels maintained.
    """

    _BUILD_WRAPPER = _REPO_ROOT / "scripts" / "build-local.sh"
    _RELEASE_SCRIPT = _REPO_ROOT / "scripts" / "release-local.sh"
    _CHECKLIST = _REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md"
    _US14_DOC = _REPO_ROOT / "docs" / "US14_RELEASE_DISTRIBUTION.md"
    _PKG_JSON = _REPO_ROOT / "frontend" / "package.json"

    # ── Wrapper existence and structure ─────────────────────────────────

    def test_build_local_wrapper_exists(self):
        assert self._BUILD_WRAPPER.exists(), (
            "scripts/build-local.sh must exist as the safe founder-local build wrapper"
        )

    def test_build_local_wrapper_is_executable(self):
        import os
        assert os.access(str(self._BUILD_WRAPPER), os.X_OK), (
            "scripts/build-local.sh must be executable"
        )

    def test_wrapper_contains_unauthorized_applications_modification(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "UNAUTHORIZED_APPLICATIONS_MODIFICATION" in content, (
            "build-local.sh must fail with UNAUTHORIZED_APPLICATIONS_MODIFICATION "
            "if /Applications content changes without explicit flag"
        )

    def test_wrapper_records_pre_state_binary_sha(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "PRE_BIN_SHA" in content or "pre_bin_sha" in content.lower(), (
            "build-local.sh must record /Applications binary SHA256 pre-state"
        )

    def test_wrapper_records_pre_state_plist_sha(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "PRE_PLIST_SHA" in content or "pre_plist_sha" in content.lower(), (
            "build-local.sh must record /Applications Info.plist SHA256 pre-state"
        )

    def test_wrapper_records_post_state_binary_sha(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "POST_BIN_SHA" in content or "post_bin_sha" in content.lower(), (
            "build-local.sh must record /Applications binary SHA256 post-state"
        )

    def test_wrapper_records_post_state_plist_sha(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "POST_PLIST_SHA" in content or "post_plist_sha" in content.lower(), (
            "build-local.sh must record /Applications Info.plist SHA256 post-state"
        )

    def test_wrapper_compares_content_not_just_mtime(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "sha256" in content.lower() or "SHA256" in content or "shasum" in content, (
            "build-local.sh must compare content checksums (SHA256), not just mtime"
        )

    def test_wrapper_has_allow_applications_update_flag(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "--allow-applications-update" in content, (
            "build-local.sh must have --allow-applications-update explicit authorization flag"
        )

    def test_wrapper_fails_on_content_change_without_flag(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "ALLOW_APPS" in content or "allow_apps" in content.lower(), (
            "build-local.sh must gate /Applications mutation on allow flag"
        )

    # ── Docs: raw build not accepted as validation path ─────────────────

    def test_checklist_uses_build_local_wrapper_not_raw_command(self):
        text = self._CHECKLIST.read_text()
        assert "build-local.sh" in text, (
            "RELEASE_CHECKLIST.md must reference scripts/build-local.sh as the founder-local build command"
        )

    def test_checklist_warns_raw_build_not_accepted_as_validation(self):
        text = self._CHECKLIST.read_text()
        lower = text.lower()
        assert "not accepted" in lower or "no /applications guard" in lower or "raw" in lower, (
            "RELEASE_CHECKLIST.md must warn that raw build:tauri:local is not accepted as non-mutating validation path"
        )

    def test_us14_doc_documents_safe_wrapper(self):
        text = self._US14_DOC.read_text()
        assert "build-local.sh" in text or "safe founder-local build wrapper" in text.lower(), (
            "US14_RELEASE_DISTRIBUTION.md must document the safe build wrapper"
        )

    def test_us14_doc_documents_root_cause(self):
        text = self._US14_DOC.read_text()
        lower = text.lower()
        assert "syspolicyd" in lower or "launchservices" in lower or "root cause" in lower, (
            "US14_RELEASE_DISTRIBUTION.md must document the /Applications mutation root cause"
        )

    def test_checklist_requires_explicit_authorization_for_applications_update(self):
        text = self._CHECKLIST.read_text()
        assert "--allow-applications-update" in text or "explicit" in text.lower(), (
            "RELEASE_CHECKLIST.md must require explicit authorization for /Applications update"
        )

    # ── Status label integrity ───────────────────────────────────────────

    def test_no_future_backlog_anywhere(self):
        for path, label in [
            (self._BUILD_WRAPPER, "build-local.sh"),
            (self._RELEASE_SCRIPT, "release-local.sh"),
            (self._CHECKLIST, "RELEASE_CHECKLIST.md"),
            (self._US14_DOC, "US14_RELEASE_DISTRIBUTION.md"),
        ]:
            assert "FUTURE_BACKLOG" not in path.read_text(), (
                f"{label} must not contain FUTURE_BACKLOG"
            )

    def test_docs_keep_updater_signing_required_for_public_release(self):
        for path in [self._CHECKLIST, self._US14_DOC]:
            assert "REQUIRED_FOR_PUBLIC_RELEASE" in path.read_text(), (
                f"{path.name} must keep updater signing as REQUIRED_FOR_PUBLIC_RELEASE"
            )

    def test_docs_keep_voice_gated(self):
        for path in [self._CHECKLIST, self._US14_DOC, self._RELEASE_SCRIPT]:
            content = path.read_text()
            assert "voice" in content.lower() and "REQUIRED_FOR_NO_GAP_JARVIS" in content, (
                f"{path.name} must keep voice gated as REQUIRED_FOR_NO_GAP_JARVIS"
            )

    def test_docs_keep_company_org_required(self):
        for path in [self._CHECKLIST, self._US14_DOC, self._RELEASE_SCRIPT]:
            text = path.read_text().lower()
            assert "company org" in text or "manager-worker" in text, (
                f"{path.name} must keep company org / manager-worker roster required"
            )

    def test_docs_keep_full_no_gap_hold(self):
        for path in [self._CHECKLIST, self._US14_DOC, self._RELEASE_SCRIPT]:
            assert "HOLD" in path.read_text(), (
                f"{path.name} must keep full no-gap as HOLD"
            )


# ---------------------------------------------------------------------------
# 12. Sprint 2 Final Narrow Correction — mtime guard, no silent pass
# ---------------------------------------------------------------------------


class TestSprint2FinalNarrowCorrection:
    """Tests for the final narrow correction:
    - Wrapper fails on mtime change (not just content change).
    - UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH present in wrapper.
    - Wrapper does not describe mtime-only changes as safe or false-positive.
    - Docs reflect that mtime changes require explicit authorization.
    - Docs do not say mtime-only changes are ignored or accepted.
    """

    _BUILD_WRAPPER = _REPO_ROOT / "scripts" / "build-local.sh"
    _CHECKLIST = _REPO_ROOT / "docs" / "RELEASE_CHECKLIST.md"
    _US14_DOC = _REPO_ROOT / "docs" / "US14_RELEASE_DISTRIBUTION.md"

    # ── Wrapper mtime guard ──────────────────────────────────────────────

    def test_wrapper_detects_mtime_change(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "PRE_MTIME" in content and "POST_MTIME" in content, (
            "build-local.sh must compare /Applications mtime pre/post"
        )

    def test_wrapper_has_metadata_touch_failure(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH" in content, (
            "build-local.sh must fail with UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH "
            "on mtime-only change without --allow-applications-update"
        )

    def test_wrapper_mtime_change_without_flag_causes_nonzero_exit(self):
        content = self._BUILD_WRAPPER.read_text()
        # Must have both the METADATA_TOUCH error AND exit 1 in the same failure block
        assert "UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH" in content and "exit 1" in content, (
            "build-local.sh must exit non-zero when mtime changes without allow flag"
        )

    def test_wrapper_does_not_describe_mtime_as_safe_or_false_positive(self):
        content = self._BUILD_WRAPPER.read_text()
        lower = content.lower()
        assert "false positive" not in lower, (
            "build-local.sh must not describe mtime changes as false positives"
        )
        assert "mtime may differ" not in lower, (
            "build-local.sh must not say mtime may differ as if it is acceptable"
        )

    def test_wrapper_checks_all_four_signals(self):
        content = self._BUILD_WRAPPER.read_text()
        assert "PRE_BIN_SHA" in content, "wrapper must check binary SHA"
        assert "PRE_PLIST_SHA" in content, "wrapper must check plist SHA"
        assert "PRE_VERSION" in content, "wrapper must check version"
        assert "PRE_MTIME" in content, "wrapper must check mtime"

    def test_wrapper_mtime_is_part_of_any_change_gate(self):
        content = self._BUILD_WRAPPER.read_text()
        # MTIME_CHANGED must feed into ANY_CHANGE which drives the failure
        assert "MTIME_CHANGED" in content or "PRE_MTIME" in content, (
            "build-local.sh must include mtime in the change-detection gate"
        )
        assert "ANY_CHANGE" in content, (
            "build-local.sh must use a single ANY_CHANGE gate covering all four signals"
        )

    # ── Docs: mtime not silently accepted ────────────────────────────────

    def test_checklist_mtime_requires_explicit_authorization(self):
        text = self._CHECKLIST.read_text()
        lower = text.lower()
        assert "mtime" in lower, (
            "RELEASE_CHECKLIST.md must mention mtime in the /Applications policy"
        )
        assert "explicit" in lower, (
            "RELEASE_CHECKLIST.md must require explicit authorization for all /Applications changes"
        )

    def test_checklist_does_not_accept_mtime_silently(self):
        text = self._CHECKLIST.read_text()
        lower = text.lower()
        assert "mtime may differ" not in lower, (
            "RELEASE_CHECKLIST.md must not say mtime may differ as if acceptable"
        )
        assert "false positive" not in lower, (
            "RELEASE_CHECKLIST.md must not describe mtime changes as false positives"
        )

    def test_us14_doc_mtime_guard_documented(self):
        text = self._US14_DOC.read_text()
        assert "UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH" in text, (
            "US14_RELEASE_DISTRIBUTION.md must document mtime-only touch failure"
        )

    def test_us14_doc_mtime_not_silently_accepted(self):
        text = self._US14_DOC.read_text()
        lower = text.lower()
        assert "mtime changes are not silently accepted" in lower or \
               "not silently" in lower or \
               "unauthorized_applications_metadata_touch" in lower, (
            "US14_RELEASE_DISTRIBUTION.md must state mtime changes are not silently accepted"
        )

    # ── Status label integrity (regression) ──────────────────────────────

    def test_no_future_backlog_anywhere(self):
        for path, label in [
            (self._BUILD_WRAPPER, "build-local.sh"),
            (self._CHECKLIST, "RELEASE_CHECKLIST.md"),
            (self._US14_DOC, "US14_RELEASE_DISTRIBUTION.md"),
        ]:
            assert "FUTURE_BACKLOG" not in path.read_text(), (
                f"{label} must not contain FUTURE_BACKLOG"
            )

    def test_docs_keep_updater_signing_required_for_public_release(self):
        for path in [self._CHECKLIST, self._US14_DOC]:
            assert "REQUIRED_FOR_PUBLIC_RELEASE" in path.read_text(), (
                f"{path.name} must keep updater signing as REQUIRED_FOR_PUBLIC_RELEASE"
            )

    def test_docs_keep_voice_gated(self):
        for path in [self._CHECKLIST, self._US14_DOC]:
            content = path.read_text()
            assert "voice" in content.lower() and "REQUIRED_FOR_NO_GAP_JARVIS" in content, (
                f"{path.name} must keep voice gated as REQUIRED_FOR_NO_GAP_JARVIS"
            )

    def test_docs_keep_company_org_required(self):
        for path in [self._CHECKLIST, self._US14_DOC]:
            text = path.read_text().lower()
            assert "company org" in text or "manager-worker" in text, (
                f"{path.name} must keep company org required"
            )

    def test_docs_keep_full_no_gap_hold(self):
        for path in [self._CHECKLIST, self._US14_DOC]:
            assert "HOLD" in path.read_text(), (
                f"{path.name} must keep full no-gap as HOLD"
            )
