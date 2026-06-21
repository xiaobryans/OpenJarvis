"""Jarvis Desktop Operator — macOS permission checks and operator foundation.

Permission checks (programmatic, read-only):
  Accessibility     — ctypes call to AXIsProcessTrusted()
  Screen Recording  — CGWindowListCopyWindowInfo window-list probe
  Microphone        — system_profiler audio hardware check

Operator status:
  available                — accessibility permission granted
  not_configured           — permissions not yet requested/granted
  blocked_by_macos_privacy — permission was explicitly denied
  not_macos                — not running on macOS

All plan functions are dry-run only — they describe what would happen.
No synthetic input, form submission, purchase, account mutation, or destructive
action is performed by any function in this module.

Governance:
  - No browser form submission
  - No purchases
  - No account mutation
  - No destructive actions
  - Permission checks are read-only
  - App/focus/browser are plan-only unless explicitly approved
"""

from __future__ import annotations

import ctypes
import ctypes.util
import platform
import shutil
import subprocess
import time
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Permission / operator status constants
# ---------------------------------------------------------------------------


class PermissionStatus:
    GRANTED = "granted"
    DENIED = "denied"
    NOT_DETERMINED = "not_determined"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class OperatorStatus:
    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    BLOCKED_BY_MACOS_PRIVACY = "blocked_by_macos_privacy"
    NOT_MACOS = "not_macos"


_IS_MACOS = platform.system() == "Darwin"

# Process-level cache for screen-recording permission probe.
# screencapture -x -t png /dev/null triggers a macOS TCC prompt if permission
# is not yet granted.  Without caching, this fires on every run_all_checks()
# call (every 60 s from the Cockpit health poller), spamming the user with
# repeated permission dialogs even when the permission is already granted.
# Cache the result for 5 minutes; the user must restart or wait 5 min for a
# revoked permission to propagate (which is fine — revocation is rare).
_screen_recording_cache: Optional[Dict[str, Any]] = None
_screen_recording_cache_ts: float = 0.0
_SCREEN_RECORDING_CACHE_TTL: float = 300.0  # seconds


# ---------------------------------------------------------------------------
# Accessibility permission check
# ---------------------------------------------------------------------------


def check_accessibility_permission() -> Dict[str, Any]:
    """Check macOS Accessibility permission via AXIsProcessTrusted (ctypes)."""
    if not _IS_MACOS:
        return {
            "permission": "accessibility",
            "status": PermissionStatus.NOT_APPLICABLE,
            "platform": platform.system(),
        }
    try:
        lib_path = ctypes.util.find_library("ApplicationServices")
        if not lib_path:
            raise RuntimeError("ApplicationServices framework not found")
        app_services = ctypes.cdll.LoadLibrary(lib_path)
        ax_is_trusted = app_services.AXIsProcessTrusted
        ax_is_trusted.restype = ctypes.c_bool
        trusted = ax_is_trusted()
        return {
            "permission": "accessibility",
            "status": PermissionStatus.GRANTED if trusted else PermissionStatus.NOT_DETERMINED,
            "trusted": bool(trusted),
            "system_settings_path": (
                "System Settings → Privacy & Security → Accessibility"
            ),
            "process_name": "OpenJarvis / Python",
        }
    except Exception as exc:
        return {
            "permission": "accessibility",
            "status": PermissionStatus.UNKNOWN,
            "error": str(exc),
            "system_settings_path": (
                "System Settings → Privacy & Security → Accessibility"
            ),
        }


# ---------------------------------------------------------------------------
# Screen Recording permission check
# ---------------------------------------------------------------------------


def check_screen_recording_permission() -> Dict[str, Any]:
    """Probe screen recording permission via a zero-byte screencapture test.

    Uses 'screencapture -x -t png /dev/null' which succeeds silently if
    Screen Recording is granted and exits non-zero if denied.  Never writes
    actual image data because /dev/null discards output.

    Result is cached for _SCREEN_RECORDING_CACHE_TTL seconds (default 5 min)
    to prevent repeated macOS TCC prompts when this function is called from
    health-check polling loops (Cockpit polls /v1/system/health every 60 s).
    """
    global _screen_recording_cache, _screen_recording_cache_ts

    # Non-macOS is always not-applicable; skip cache entirely so monkeypatching
    # _IS_MACOS in tests still works correctly.
    if not _IS_MACOS:
        return {
            "permission": "screen_recording",
            "status": PermissionStatus.NOT_APPLICABLE,
            "platform": platform.system(),
        }

    now = time.monotonic()
    if (
        _screen_recording_cache is not None
        and (now - _screen_recording_cache_ts) < _SCREEN_RECORDING_CACHE_TTL
    ):
        return {**_screen_recording_cache, "cached": True}

    screencapture = shutil.which("screencapture")
    if not screencapture:
        result = {
            "permission": "screen_recording",
            "status": PermissionStatus.UNKNOWN,
            "error": "screencapture command not found",
            "system_settings_path": (
                "System Settings → Privacy & Security → Screen Recording"
            ),
        }
        _screen_recording_cache = result
        _screen_recording_cache_ts = now
        return result

    try:
        proc = subprocess.run(
            [screencapture, "-x", "-t", "png", "/dev/null"],
            capture_output=True,
            timeout=5,
        )
        granted = proc.returncode == 0
        result = {
            "permission": "screen_recording",
            "status": PermissionStatus.GRANTED if granted else PermissionStatus.NOT_DETERMINED,
            "has_access": granted,
            "system_settings_path": (
                "System Settings → Privacy & Security → Screen Recording"
            ),
            "process_name": "OpenJarvis / Python",
        }
        _screen_recording_cache = result
        _screen_recording_cache_ts = now
        return result
    except Exception as exc:
        result = {
            "permission": "screen_recording",
            "status": PermissionStatus.UNKNOWN,
            "error": str(exc),
            "system_settings_path": (
                "System Settings → Privacy & Security → Screen Recording"
            ),
        }
        _screen_recording_cache = result
        _screen_recording_cache_ts = now
        return result


# ---------------------------------------------------------------------------
# Microphone permission check
# ---------------------------------------------------------------------------


def check_microphone_permission() -> Dict[str, Any]:
    """Check microphone availability via system_profiler audio hardware detection."""
    if not _IS_MACOS:
        return {
            "permission": "microphone",
            "status": PermissionStatus.NOT_APPLICABLE,
            "platform": platform.system(),
        }
    try:
        result = subprocess.run(
            ["system_profiler", "SPAudioDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and (
            "Input Source Name" in result.stdout
            or "microphone" in result.stdout.lower()
        ):
            return {
                "permission": "microphone",
                "status": PermissionStatus.NOT_DETERMINED,
                "note": (
                    "Audio input hardware detected. "
                    "Permission status requires runtime AVAudioSession check."
                ),
                "system_settings_path": (
                    "System Settings → Privacy & Security → Microphone"
                ),
                "process_name": "OpenJarvis / Python",
                "manual_check": (
                    "Open System Settings → Privacy & Security → Microphone "
                    "and verify OpenJarvis is listed and checked."
                ),
            }
    except Exception:
        pass

    return {
        "permission": "microphone",
        "status": PermissionStatus.UNKNOWN,
        "note": (
            "Cannot programmatically verify microphone permission "
            "without AVAudioSession / pyobjc access."
        ),
        "system_settings_path": "System Settings → Privacy & Security → Microphone",
        "process_name": "OpenJarvis / Python",
        "manual_check": (
            "Open System Settings → Privacy & Security → Microphone "
            "and verify OpenJarvis is listed and checked."
        ),
    }


# ---------------------------------------------------------------------------
# Screenshot status (read-only probe)
# ---------------------------------------------------------------------------


def check_screenshot_status() -> Dict[str, Any]:
    """Check if taking a screenshot would be possible. Does not take a screenshot."""
    if not _IS_MACOS:
        return {
            "screenshot_available": False,
            "blocker": f"Not macOS (platform={platform.system()})",
        }
    screencapture = shutil.which("screencapture")
    screen_perm = check_screen_recording_permission()
    granted = screen_perm["status"] == PermissionStatus.GRANTED
    return {
        "screenshot_available": bool(screencapture) and granted,
        "screencapture_path": screencapture,
        "screen_recording_status": screen_perm["status"],
        "blocker": (
            None if (screencapture and granted)
            else (
                "Screen Recording permission not granted"
                if screencapture
                else "screencapture command not found"
            )
        ),
        "system_settings_path": screen_perm.get("system_settings_path", ""),
    }


# ---------------------------------------------------------------------------
# Full desktop permissions status
# ---------------------------------------------------------------------------


def get_desktop_permissions_status() -> Dict[str, Any]:
    """Aggregate status of all desktop permissions."""
    accessibility = check_accessibility_permission()
    screen_recording = check_screen_recording_permission()
    microphone = check_microphone_permission()
    screenshot = check_screenshot_status()

    if not _IS_MACOS:
        operator_status = OperatorStatus.NOT_MACOS
    elif accessibility["status"] == PermissionStatus.GRANTED:
        operator_status = OperatorStatus.AVAILABLE
    elif accessibility["status"] == PermissionStatus.DENIED:
        operator_status = OperatorStatus.BLOCKED_BY_MACOS_PRIVACY
    else:
        operator_status = OperatorStatus.NOT_CONFIGURED

    setup_instructions = None
    if _IS_MACOS and operator_status != OperatorStatus.AVAILABLE:
        setup_instructions = (
            "1. System Settings → Privacy & Security → Accessibility "
            "→ add OpenJarvis / Terminal / Python\n"
            "2. System Settings → Privacy & Security → Screen Recording "
            "→ add OpenJarvis / Terminal / Python\n"
            "3. System Settings → Privacy & Security → Microphone "
            "→ add OpenJarvis / Terminal / Python\n"
            "4. Restart OpenJarvis after granting permissions."
        )

    return {
        "operator_status": operator_status,
        "platform": platform.system(),
        "permissions": {
            "accessibility": accessibility,
            "screen_recording": screen_recording,
            "microphone": microphone,
        },
        "screenshot": screenshot,
        "actions_available": operator_status == OperatorStatus.AVAILABLE,
        "setup_instructions": setup_instructions,
    }


# ---------------------------------------------------------------------------
# App / browser plans (dry-run — describe only, no execution)
# ---------------------------------------------------------------------------


def plan_open_app(app_name: str) -> Dict[str, Any]:
    """Describe the plan to open an application. Does NOT execute."""
    permissions = get_desktop_permissions_status()
    return {
        "plan": f"open -a '{app_name}'",
        "app_name": app_name,
        "can_execute": permissions["actions_available"],
        "operator_status": permissions["operator_status"],
        "requires_approval": True,
        "dry_run": True,
        "note": "This is a plan only. Explicit approval required to execute.",
    }


def plan_focus_app(app_name: str) -> Dict[str, Any]:
    """Describe the plan to focus an application via AppleScript. Does NOT execute."""
    permissions = get_desktop_permissions_status()
    ax_granted = (
        permissions["permissions"]["accessibility"]["status"] == PermissionStatus.GRANTED
    )
    return {
        "plan": f"osascript -e 'tell application \"{app_name}\" to activate'",
        "app_name": app_name,
        "requires_accessibility": True,
        "accessibility_granted": ax_granted,
        "can_execute": ax_granted,
        "dry_run": True,
        "system_settings_path": (
            "System Settings → Privacy & Security → Accessibility"
            if not ax_granted
            else None
        ),
        "note": "This is a plan only. Explicit approval required to execute.",
    }


def plan_browser_open_url(url: str) -> Dict[str, Any]:
    """Describe the plan to open a URL in the browser. Does NOT execute."""
    # Block private/file URLs
    if any(url.startswith(p) for p in ("file://", "javascript:")):
        return {
            "plan": f"open '{url}'",
            "url": url,
            "can_execute": False,
            "blocked": True,
            "blocker": "Blocked URL scheme (file:// or javascript:// not allowed)",
        }
    return {
        "plan": f"open '{url}'",
        "url": url,
        "can_execute": True,
        "requires_approval": True,
        "dry_run": True,
        "safety_note": (
            "Opens URL only. No form submission, purchase, "
            "account mutation, or login will occur."
        ),
        "note": "This is a plan only. Explicit approval required to execute.",
    }


def browser_read_only_plan(url: str) -> Dict[str, Any]:
    """Plan for read-only browser page inspection (no interaction)."""
    permissions = get_desktop_permissions_status()
    screen_perm = permissions["permissions"]["screen_recording"]
    return {
        "url": url,
        "plan": f"open '{url}' and observe page content (read-only)",
        "can_read": screen_perm["status"] == PermissionStatus.GRANTED,
        "can_interact": False,
        "operator_status": permissions["operator_status"],
        "requires_approval": True,
        "dry_run": True,
        "governance": {
            "form_submit": "always_blocked",
            "purchase": "always_blocked",
            "account_mutation": "always_blocked",
            "login": "explicit_approval_required",
        },
    }


def get_browser_operator_status() -> Dict[str, Any]:
    """Report browser operator readiness."""
    permissions = get_desktop_permissions_status()
    return {
        "browser_operator_status": permissions["operator_status"],
        "can_open_url": True,
        "can_read_page": (
            permissions["permissions"]["screen_recording"]["status"]
            == PermissionStatus.GRANTED
        ),
        "can_submit_form": False,
        "can_purchase": False,
        "can_mutate_account": False,
        "governance": {
            "form_submit": "always_blocked",
            "purchase": "always_blocked",
            "account_mutation": "always_blocked",
        },
    }


def desktop_safe_demo() -> Dict[str, Any]:
    """Demonstrate desktop operator capabilities without executing anything."""
    permissions = get_desktop_permissions_status()
    sr = permissions["permissions"]["screen_recording"]["status"]
    ax = permissions["permissions"]["accessibility"]["status"]
    return {
        "demo_status": "planned",
        "operator_status": permissions["operator_status"],
        "capabilities": {
            "open_url": True,
            "read_page": sr == PermissionStatus.GRANTED,
            "take_screenshot": sr == PermissionStatus.GRANTED,
            "focus_app": ax == PermissionStatus.GRANTED,
            "form_submit": False,
            "purchase": False,
            "account_mutation": False,
        },
        "governance": {
            "form_submit": "always_blocked",
            "purchase": "always_blocked",
            "account_mutation": "always_blocked",
        },
        "note": "No actions executed. Capability overview only.",
    }


__all__ = [
    "PermissionStatus",
    "OperatorStatus",
    "check_accessibility_permission",
    "check_screen_recording_permission",
    "check_microphone_permission",
    "check_screenshot_status",
    "get_desktop_permissions_status",
    "plan_open_app",
    "plan_focus_app",
    "plan_browser_open_url",
    "browser_read_only_plan",
    "get_browser_operator_status",
    "desktop_safe_demo",
]
