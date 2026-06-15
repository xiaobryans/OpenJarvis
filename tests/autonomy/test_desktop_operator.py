"""Tests for DesktopOperator — macOS permissions and operator foundation (US8 Phase E).

Covers:
  - check_accessibility_permission returns valid status
  - check_screen_recording_permission returns valid status
  - check_microphone_permission returns valid status
  - check_screenshot_status returns screenshot_available field
  - get_desktop_permissions_status aggregates all permissions
  - operator_status is one of: available/not_configured/blocked_by_macos_privacy/not_macos
  - plan_open_app returns dry_run=True and plan field
  - plan_focus_app returns dry_run=True
  - plan_browser_open_url returns dry_run or blocked
  - plan_browser_open_url blocks file:// URLs
  - browser_read_only_plan returns governance block fields
  - get_browser_operator_status returns form_submit=False
  - desktop_safe_demo returns no-execution note
"""

from __future__ import annotations

import pytest

from openjarvis.autonomy.desktop_operator import (
    OperatorStatus,
    PermissionStatus,
    browser_read_only_plan,
    check_accessibility_permission,
    check_microphone_permission,
    check_screenshot_status,
    check_screen_recording_permission,
    desktop_safe_demo,
    get_browser_operator_status,
    get_desktop_permissions_status,
    plan_browser_open_url,
    plan_focus_app,
    plan_open_app,
)


VALID_STATUSES = {
    PermissionStatus.GRANTED,
    PermissionStatus.DENIED,
    PermissionStatus.NOT_DETERMINED,
    PermissionStatus.UNKNOWN,
    PermissionStatus.NOT_APPLICABLE,
}

VALID_OPERATOR_STATUSES = {
    OperatorStatus.AVAILABLE,
    OperatorStatus.NOT_CONFIGURED,
    OperatorStatus.BLOCKED_BY_MACOS_PRIVACY,
    OperatorStatus.NOT_MACOS,
}


class TestAccessibilityPermission:
    def test_returns_permission_field(self):
        r = check_accessibility_permission()
        assert r["permission"] == "accessibility"

    def test_returns_valid_status(self):
        r = check_accessibility_permission()
        assert r["status"] in VALID_STATUSES

    def test_has_system_settings_path_on_macos(self):
        import platform
        r = check_accessibility_permission()
        if platform.system() == "Darwin":
            assert "system_settings_path" in r

    def test_not_applicable_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.autonomy.desktop_operator._IS_MACOS", False
        )
        r = check_accessibility_permission()
        assert r["status"] == PermissionStatus.NOT_APPLICABLE


class TestScreenRecordingPermission:
    def test_returns_permission_field(self):
        r = check_screen_recording_permission()
        assert r["permission"] == "screen_recording"

    def test_returns_valid_status(self):
        r = check_screen_recording_permission()
        assert r["status"] in VALID_STATUSES

    def test_not_applicable_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.autonomy.desktop_operator._IS_MACOS", False
        )
        r = check_screen_recording_permission()
        assert r["status"] == PermissionStatus.NOT_APPLICABLE


class TestMicrophonePermission:
    def test_returns_permission_field(self):
        r = check_microphone_permission()
        assert r["permission"] == "microphone"

    def test_returns_valid_status(self):
        r = check_microphone_permission()
        assert r["status"] in VALID_STATUSES

    def test_not_applicable_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.autonomy.desktop_operator._IS_MACOS", False
        )
        r = check_microphone_permission()
        assert r["status"] == PermissionStatus.NOT_APPLICABLE


class TestScreenshotStatus:
    def test_returns_screenshot_available_field(self):
        r = check_screenshot_status()
        assert "screenshot_available" in r
        assert isinstance(r["screenshot_available"], bool)

    def test_not_available_on_non_macos(self, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.autonomy.desktop_operator._IS_MACOS", False
        )
        r = check_screenshot_status()
        assert r["screenshot_available"] is False


class TestDesktopPermissionsStatus:
    def test_returns_operator_status(self):
        r = get_desktop_permissions_status()
        assert "operator_status" in r
        assert r["operator_status"] in VALID_OPERATOR_STATUSES

    def test_returns_platform_field(self):
        r = get_desktop_permissions_status()
        assert "platform" in r

    def test_returns_all_permissions(self):
        r = get_desktop_permissions_status()
        perms = r["permissions"]
        assert "accessibility" in perms
        assert "screen_recording" in perms
        assert "microphone" in perms

    def test_returns_actions_available_field(self):
        r = get_desktop_permissions_status()
        assert "actions_available" in r
        assert isinstance(r["actions_available"], bool)

    def test_not_macos_returns_not_macos_status(self, monkeypatch):
        monkeypatch.setattr(
            "openjarvis.autonomy.desktop_operator._IS_MACOS", False
        )
        r = get_desktop_permissions_status()
        assert r["operator_status"] == OperatorStatus.NOT_MACOS


class TestPlanOpenApp:
    def test_returns_plan_field(self):
        r = plan_open_app("Safari")
        assert "plan" in r
        assert "Safari" in r["plan"]

    def test_dry_run_true(self):
        r = plan_open_app("Safari")
        assert r["dry_run"] is True

    def test_requires_approval(self):
        r = plan_open_app("Safari")
        assert r["requires_approval"] is True

    def test_returns_note(self):
        r = plan_open_app("Safari")
        assert "note" in r


class TestPlanFocusApp:
    def test_returns_plan_field(self):
        r = plan_focus_app("Safari")
        assert "plan" in r
        assert "Safari" in r["plan"]

    def test_dry_run_true(self):
        r = plan_focus_app("Safari")
        assert r["dry_run"] is True

    def test_requires_accessibility(self):
        r = plan_focus_app("Safari")
        assert r["requires_accessibility"] is True


class TestPlanBrowserOpenURL:
    def test_returns_plan_field(self):
        r = plan_browser_open_url("https://example.com")
        assert "plan" in r
        assert "example.com" in r["plan"]

    def test_dry_run_true(self):
        r = plan_browser_open_url("https://example.com")
        assert r["dry_run"] is True

    def test_file_scheme_blocked(self):
        r = plan_browser_open_url("file:///etc/passwd")
        assert r["blocked"] is True
        assert r["can_execute"] is False

    def test_javascript_scheme_blocked(self):
        r = plan_browser_open_url("javascript:alert(1)")
        assert r["blocked"] is True

    def test_https_url_not_blocked(self):
        r = plan_browser_open_url("https://openai.com")
        assert r.get("blocked", False) is False

    def test_https_url_has_safety_note(self):
        r = plan_browser_open_url("https://openai.com")
        assert "safety_note" in r or "note" in r


class TestBrowserOperatorStatus:
    def test_form_submit_always_false(self):
        r = get_browser_operator_status()
        assert r["can_submit_form"] is False

    def test_purchase_always_false(self):
        r = get_browser_operator_status()
        assert r["can_purchase"] is False

    def test_governance_fields_present(self):
        r = get_browser_operator_status()
        assert "governance" in r
        assert r["governance"]["form_submit"] == "always_blocked"
        assert r["governance"]["purchase"] == "always_blocked"


class TestDesktopSafeDemo:
    def test_returns_demo_status(self):
        r = desktop_safe_demo()
        assert "demo_status" in r

    def test_form_submit_false(self):
        r = desktop_safe_demo()
        assert r["capabilities"]["form_submit"] is False

    def test_purchase_false(self):
        r = desktop_safe_demo()
        assert r["capabilities"]["purchase"] is False

    def test_note_present(self):
        r = desktop_safe_demo()
        assert "note" in r


class TestBrowserReadOnlyPlan:
    def test_returns_url_field(self):
        r = browser_read_only_plan("https://example.com")
        assert r["url"] == "https://example.com"

    def test_can_interact_false(self):
        r = browser_read_only_plan("https://example.com")
        assert r["can_interact"] is False

    def test_governance_fields_present(self):
        r = browser_read_only_plan("https://example.com")
        assert "governance" in r
        assert r["governance"]["form_submit"] == "always_blocked"
