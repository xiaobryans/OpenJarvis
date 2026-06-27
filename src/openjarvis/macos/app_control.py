"""macOS app-control helpers + tray-agent spawner.

Pure command builders are unit-testable; the spawner launches the menu-bar +
hotkey agent (``openjarvis.macos.tray``) as a SEPARATE process, because rumps
needs the main thread and the API server already owns it.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from typing import List

logger = logging.getLogger("openjarvis.macos")

APP_NAME = os.environ.get("VANTA_APP_NAME", "OpenJarvis")
APP_PROCESS = os.environ.get("VANTA_APP_PROCESS", "openjarvis-desktop")  # pgrep -x target
# pynput global hotkey: Cmd+Shift+V.
HOTKEY = "<cmd>+<shift>+v"


# ── pure command builders (testable) ─────────────────────────────────────────
def open_app_cmd(app: str = APP_NAME) -> List[str]:
    return ["open", "-a", app]


def activate_cmd(app: str = APP_NAME) -> List[str]:
    return ["osascript", "-e", f'tell application "{app}" to activate']


def quit_cmd(app: str = APP_NAME) -> List[str]:
    return ["osascript", "-e", f'tell application "{app}" to quit']


def pgrep_cmd(process: str = APP_PROCESS) -> List[str]:
    return ["pgrep", "-x", process]


# ── runtime helpers (macOS) ──────────────────────────────────────────────────
def app_running(process: str = APP_PROCESS) -> bool:  # pragma: no cover - macOS
    try:
        return subprocess.run(pgrep_cmd(process), capture_output=True).returncode == 0
    except Exception:
        return False


def app_frontmost(app: str = APP_NAME) -> bool:  # pragma: no cover - macOS
    try:
        out = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first application process whose frontmost is true'],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() == app
    except Exception:
        return False


def launch_or_foreground(app: str = APP_NAME) -> str:  # pragma: no cover - macOS
    """Launch the app if not running; foreground if running but background;
    do nothing if already frontmost. Returns the action taken."""
    if app_running():
        if app_frontmost(app):
            return "already-frontmost"
        subprocess.run(activate_cmd(app), capture_output=True, timeout=5)
        return "foregrounded"
    subprocess.run(open_app_cmd(app), capture_output=True, timeout=10)
    return "launched"


# ── tray/hotkey agent spawner ────────────────────────────────────────────────
def tray_disabled() -> bool:
    return (os.environ.get("VANTA_TRAY") or "").strip().lower() == "off"


def tray_running() -> bool:  # pragma: no cover - macOS
    try:
        out = subprocess.run(["pgrep", "-f", "openjarvis.macos.tray"], capture_output=True)
        return out.returncode == 0
    except Exception:
        return False


def start_tray_agent() -> bool:
    """Spawn the menu-bar + global-hotkey agent as a separate process.

    Returns True if a process was spawned. macOS only; opt out with
    ``VANTA_TRAY=off``. Never raises into server startup.
    """
    try:
        if sys.platform != "darwin" or tray_disabled():
            return False
        if tray_running():
            return False
        subprocess.Popen(
            [sys.executable, "-m", "openjarvis.macos.tray"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return True
    except Exception as exc:
        logger.warning("could not start tray agent: %s", exc)
        return False


__all__ = [
    "APP_NAME", "APP_PROCESS", "HOTKEY",
    "open_app_cmd", "activate_cmd", "quit_cmd", "pgrep_cmd",
    "app_running", "app_frontmost", "launch_or_foreground",
    "start_tray_agent", "tray_disabled", "tray_running",
]
