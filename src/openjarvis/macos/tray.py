"""VANTA menu-bar icon + global hotkey agent (macOS).

Run as a SEPARATE process (rumps owns the main thread):
    python -m openjarvis.macos.tray

Menu bar:
  * title shows VANTA online/offline (polls /health)
  * Open VANTA            -> launch / foreground the app
  * Voice: ON/OFF         -> toggle the in-app voice session
  * Restart Server        -> relaunch the backend
  * Quit VANTA            -> quit the app + this agent

Global hotkey Cmd+Shift+V (pynput, system-wide) launches/foregrounds VANTA.
GUI libs (rumps, pynput) are imported lazily inside main() so this module
imports cleanly in a headless test environment.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading

from openjarvis.macos.app_control import APP_NAME, HOTKEY, launch_or_foreground, quit_cmd

logger = logging.getLogger("openjarvis.macos.tray")


def _server_port() -> str:
    return (os.environ.get("JARVIS_PORT") or os.environ.get("OPENJARVIS_PORT") or "8000").strip()


def server_online() -> bool:
    try:
        import httpx
        return httpx.get(f"http://127.0.0.1:{_server_port()}/health", timeout=1.5).status_code == 200
    except Exception:
        return False


def voice_active() -> bool:
    try:
        import httpx
        r = httpx.get(f"http://127.0.0.1:{_server_port()}/v1/voice/state", timeout=1.5)
        return bool(r.json().get("active")) if r.status_code == 200 else False
    except Exception:
        return False


def _voice_session(action: str) -> None:
    """action: 'start' | 'stop' — best-effort toggle of the in-app voice session."""
    try:
        import httpx
        httpx.post(f"http://127.0.0.1:{_server_port()}/v1/voice/session/{action}",
                   headers={"Authorization": "Bearer test"}, timeout=4)
    except Exception as exc:
        logger.warning("voice %s failed: %s", action, exc)


def _restart_server() -> None:
    """Best-effort: stop the running server and relaunch the app (which serves)."""
    try:
        subprocess.run(["pkill", "-f", "jarvis serve"], capture_output=True)
    except Exception:
        pass
    subprocess.run(["open", "-a", APP_NAME], capture_output=True)


def main() -> None:  # pragma: no cover - GUI main loop, needs a Mac session
    try:
        import rumps
        from pynput import keyboard
    except Exception as exc:
        logger.error("tray agent needs rumps + pynput: %s", exc)
        return

    app = rumps.App("VANTA", title="◇ VANTA", quit_button=None)
    status_item = rumps.MenuItem("Status: …")
    voice_item = rumps.MenuItem("Voice: …", callback=lambda s: on_voice(s))

    def on_open(_):
        launch_or_foreground()

    def on_voice(_):
        _voice_session("stop" if voice_active() else "start")

    def on_restart(_):
        _restart_server()

    def on_quit(_):
        subprocess.run(quit_cmd(), capture_output=True)
        rumps.quit_application()

    app.menu = [
        status_item,
        None,
        rumps.MenuItem("Open VANTA", callback=on_open),
        voice_item,
        rumps.MenuItem("Restart Server", callback=on_restart),
        None,
        rumps.MenuItem("Quit VANTA", callback=on_quit),
    ]

    @rumps.timer(10)
    def _poll(_):
        online = server_online()
        app.title = "◇ VANTA" if online else "◇ VANTA (off)"
        status_item.title = f"Status: {'online' if online else 'offline'}"
        voice_item.title = f"Voice: {'ON' if voice_active() else 'OFF'} (toggle)"

    # Global hotkey (system-wide) in a background thread.
    def _start_hotkey():
        try:
            keyboard.GlobalHotKeys({HOTKEY: launch_or_foreground}).run()
        except Exception as exc:
            logger.warning("hotkey listener failed (Input Monitoring permission?): %s", exc)

    threading.Thread(target=_start_hotkey, name="vanta-hotkey", daemon=True).start()
    app.run()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    main()
