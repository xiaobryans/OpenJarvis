"""Tests for macOS app control + global-hotkey config (Tasks 2/3).

GUI bits (rumps/pynput menu bar + listener) need a real Mac session and are not
exercised here; the pure command builders, the hotkey binding, and the tray
spawner's guards are.
"""

from __future__ import annotations

import importlib

from openjarvis.macos import app_control as ac


def test_hotkey_is_cmd_shift_v():
    assert ac.HOTKEY == "<cmd>+<shift>+v"


def test_command_builders():
    assert ac.open_app_cmd("OpenJarvis") == ["open", "-a", "OpenJarvis"]
    assert ac.activate_cmd("OpenJarvis") == ["osascript", "-e", 'tell application "OpenJarvis" to activate']
    assert ac.quit_cmd("OpenJarvis")[-1].endswith('to quit')
    assert ac.pgrep_cmd("openjarvis-desktop") == ["pgrep", "-x", "openjarvis-desktop"]


def test_app_process_target_matches_built_binary():
    # The Tauri bundle's executable is 'openjarvis-desktop' (pgrep -x target).
    assert ac.APP_PROCESS == "openjarvis-desktop"
    assert ac.APP_NAME == "OpenJarvis"


def test_tray_disabled_env(monkeypatch):
    monkeypatch.setenv("VANTA_TRAY", "off")
    assert ac.tray_disabled() is True
    monkeypatch.setenv("VANTA_TRAY", "on")
    assert ac.tray_disabled() is False


def test_start_tray_agent_skips_off_platform(monkeypatch):
    # Non-darwin (the test runner) -> spawner returns False, never raises.
    monkeypatch.setattr(ac.sys, "platform", "linux")
    assert ac.start_tray_agent() is False


def test_tray_module_imports_without_gui():
    # tray.py must import without rumps/pynput present (lazy imports in main()).
    m = importlib.import_module("openjarvis.macos.tray")
    assert hasattr(m, "main")
    assert callable(m.server_online)


def test_wake_listener_removed():
    # Task 1: the always-on background mic listener is gone.
    import importlib.util
    assert importlib.util.find_spec("openjarvis.speech.wake_listener") is None
