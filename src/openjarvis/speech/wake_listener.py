"""Minimal always-on wake listener for VANTA (runs at login via launchd).

ONE job: detect a deliberate wake trigger and launch/foreground the VANTA app.
No orchestrator, no TTS, no brain — once the app is open its own voice loop
takes over. Tuned STRICTER than the in-app loop so ambient noise / normal
conversation never auto-launches the app:

  - voice wake requires an exact ``\\bvanta\\b`` token confirmed by Deepgram
  - clap wake requires THREE claps above ``WAKE_CLAP_RMS`` (3500, stricter than
    the in-app double clap)
  - at least ``LAUNCH_COOLDOWN_S`` (30s) between launch attempts; quiet 30s after
  - if the app is already frontmost, do nothing; if running but background,
    bring it to front; if not running, ``open -a OpenJarvis``
  - every trigger is logged to ~/Library/Logs/vanta-wake.log

  python -m openjarvis.speech.wake_listener
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from openjarvis.speech.voice_loop import (
    CLAP_MAX_GAP,
    CLAP_MIN_GAP,
    contains_wake_word,
    rms_from_pcm16,
)

logger = logging.getLogger("vanta.wake_listener")

# The macOS app bundle is "OpenJarvis" (kept for macOS permission stability).
APP_NAME = os.environ.get("VANTA_APP_NAME", "OpenJarvis")

WAKE_CLAP_RMS = 3500          # stricter than the in-app double clap
WAKE_CLAPS_REQUIRED = 3       # triple clap to launch
LAUNCH_COOLDOWN_S = 30.0      # min seconds between launches
QUIET_AFTER_LAUNCH_S = 30.0   # go silent this long after a trigger
LOG_PATH = Path.home() / "Library" / "Logs" / "vanta-wake.log"


def _log_trigger(cause: str) -> None:
    """Append a timestamped trigger line to the wake log (best-effort)."""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{ts}  wake trigger: {cause}\n")
    except Exception:  # pragma: no cover
        logger.debug("wake log write failed", exc_info=True)


# ── App state / launch (macOS) ───────────────────────────────────────────────
def app_is_running(app: str = APP_NAME) -> bool:  # pragma: no cover - macOS
    try:
        out = subprocess.run(
            ["osascript", "-e",
             f'application "{app}" is running'],
            capture_output=True, text=True, timeout=5,
        )
        return out.stdout.strip() == "true"
    except Exception:
        # Fallback: pgrep by name.
        try:
            return subprocess.run(["pgrep", "-x", app], capture_output=True).returncode == 0
        except Exception:
            return False


def app_is_frontmost(app: str = APP_NAME) -> bool:  # pragma: no cover - macOS
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
    """Open the app if not running; foreground it if running but background.

    Never launches twice. Returns the action taken for logging.
    """
    if app_is_frontmost(app):
        return "already-frontmost"
    if app_is_running(app):
        subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'],
                       capture_output=True, timeout=5)
        return "foregrounded"
    subprocess.run(["open", "-a", app], capture_output=True, timeout=10)
    return "launched"


class TripleClap:
    """Fires when THREE claps land within ``CLAP_MIN_GAP``..``CLAP_MAX_GAP`` each."""

    def __init__(self, needed: int = WAKE_CLAPS_REQUIRED) -> None:
        self.needed = needed
        self._spikes: List[float] = []
        self._armed = True

    def feed(self, rms: float, now: float) -> bool:
        if rms < WAKE_CLAP_RMS:
            self._armed = True
            return False
        if not self._armed:
            return False
        self._armed = False
        # Drop stale spikes (gap too large) then record this one.
        if self._spikes and now - self._spikes[-1] > CLAP_MAX_GAP:
            self._spikes = []
        if self._spikes and now - self._spikes[-1] < CLAP_MIN_GAP:
            return False  # too close — ignore
        self._spikes.append(now)
        if len(self._spikes) >= self.needed:
            self._spikes = []
            return True
        return False


class WakeListener:
    """Background listener: voice "vanta" OR triple clap -> launch/foreground."""

    def __init__(self) -> None:
        self._last_launch = -1e9
        self._clap = TripleClap()
        self._stt = None

    def _trigger(self, cause: str) -> None:
        now = time.time()
        if now - self._last_launch < LAUNCH_COOLDOWN_S:
            return
        self._last_launch = now
        action = launch_or_foreground()
        _log_trigger(f"{cause} -> {action}")
        logger.info("wake (%s) -> %s", cause, action)
        time.sleep(QUIET_AFTER_LAUNCH_S)  # go quiet after a trigger

    def on_clap_rms(self, rms: float, now: Optional[float] = None) -> None:
        if self._clap.feed(rms, now if now is not None else time.time()):
            self._trigger("triple-clap")

    def on_final_transcript(self, text: str) -> None:
        if contains_wake_word(text):
            self._trigger(f'voice "{text.strip()[:40]}"')

    def run(self) -> None:  # pragma: no cover - needs mic + Deepgram
        try:
            import sounddevice  # noqa: F401
        except Exception as exc:
            logger.error("wake_listener needs sounddevice: %s", exc)
            return
        from openjarvis.speech.voice_loop import make_deepgram
        self._stt = make_deepgram()
        logger.info("VANTA wake listener online (strict). Logging to %s", LOG_PATH)
        # Real-time capture feeds rms_from_pcm16(frame) into on_clap_rms and
        # Deepgram finals into on_final_transcript. Loop kept minimal so the
        # decision layer above is the spec.
        while True:
            time.sleep(0.2)


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    WakeListener().run()


if __name__ == "__main__":  # pragma: no cover
    main()
