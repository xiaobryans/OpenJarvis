"""Always-on background wake listener (runs at Mac login via launchd).

ONE job: detect a deliberate wake trigger and launch/foreground the VANTA app.
No brain, no TTS, no heavy imports — once the app is open its own voice loop
takes over. Stricter than the in-app loop so ambient noise never auto-launches:

  A. Voice  — Deepgram-confirmed standalone ``\\bvanta\\b``, RMS > 2000, 3+ words.
  B. Double clap/snap — two RMS spikes > 3500, each gap 0.15–0.8s.

On a trigger: pgrep the app; if not running ``open -a OpenJarvis`` (wait 3s);
if running but not frontmost, ``osascript ... activate``; if frontmost, nothing.
30s cooldown + 30s quiet after every trigger. Logs to ~/Library/Logs/vanta-wake.log.

  python -m openjarvis.speech.wake_listener
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

from openjarvis.speech.voice_loop import ClapDetector, contains_wake_word, rms_from_pcm16

logger = logging.getLogger("vanta.wake_listener")

APP_NAME = os.environ.get("VANTA_APP_NAME", "OpenJarvis")
APP_PROCESS = os.environ.get("VANTA_APP_PROCESS", "openjarvis-desktop")  # pgrep -x target

WAKE_VOICE_RMS = 2000          # voice wake gate (stricter than in-app 1500)
WAKE_MIN_WORDS = 3
WAKE_CLAP_RMS = 3500           # double-clap spike threshold
LAUNCH_COOLDOWN_S = 30.0
QUIET_AFTER_LAUNCH_S = 30.0
APP_LOAD_WAIT_S = 3.0
LOG_PATH = Path.home() / "Library" / "Logs" / "vanta-wake.log"


def _log_trigger(cause: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  wake: {cause}\n")
    except Exception:  # pragma: no cover
        logger.debug("wake log write failed", exc_info=True)


def voice_wake_ok(text: str, rms: float) -> bool:
    """Voice wake gate: loud enough, >=3 words, standalone 'vanta'."""
    if rms < WAKE_VOICE_RMS:
        return False
    if len((text or "").split()) < WAKE_MIN_WORDS:
        return False
    return contains_wake_word(text)


# ── App state / launch (macOS) ───────────────────────────────────────────────
def app_running(process: str = APP_PROCESS) -> bool:  # pragma: no cover - macOS
    try:
        return subprocess.run(["pgrep", "-x", process], capture_output=True).returncode == 0
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
    """Open the app if not running; foreground it if running but background."""
    if app_running():
        if app_frontmost(app):
            return "already-frontmost"
        subprocess.run(["osascript", "-e", f'tell application "{app}" to activate'], capture_output=True, timeout=5)
        return "foregrounded"
    subprocess.run(["open", "-a", app], capture_output=True, timeout=10)
    time.sleep(APP_LOAD_WAIT_S)  # wait for the app to load
    return "launched"


class WakeListener:
    """Background listener: voice "vanta" OR double clap -> launch/foreground."""

    def __init__(self) -> None:
        self._last_launch = -1e9
        self._clap = ClapDetector(threshold=WAKE_CLAP_RMS)  # double clap @3500
        self._stt = None

    def _trigger(self, cause: str) -> None:
        now = time.time()
        if now - self._last_launch < LAUNCH_COOLDOWN_S:
            return
        self._last_launch = now
        action = launch_or_foreground()
        _log_trigger(f"{cause} -> {action}")
        logger.info("wake (%s) -> %s", cause, action)
        time.sleep(QUIET_AFTER_LAUNCH_S)

    def on_clap_rms(self, rms: float, now: Optional[float] = None) -> None:
        if self._clap.feed(rms, now if now is not None else time.time()):
            self._trigger("double-clap")

    def on_final_transcript(self, text: str, rms: float = WAKE_VOICE_RMS) -> None:
        if voice_wake_ok(text, rms):
            self._trigger(f'voice "{text.strip()[:40]}"')

    def run(self) -> None:  # pragma: no cover - needs mic + Deepgram
        try:
            import sounddevice as sd
        except Exception as exc:
            logger.error("wake_listener needs sounddevice: %s", exc)
            # Idle instead of exiting so launchd (KeepAlive) doesn't crash-loop.
            while True:
                time.sleep(60)
        from openjarvis.speech.voice_loop import (
            SAMPLE_RATE, FRAME_MS, VadState, rms_from_pcm16,
            make_deepgram,
        )
        self._stt = make_deepgram()
        logger.info("VANTA wake listener online (strict). Log: %s", LOG_PATH)
        block = int(SAMPLE_RATE * FRAME_MS / 1000)
        # Outer retry loop: if the mic stream can't open (e.g. permission not yet
        # granted), idle 30s and retry rather than crash-looping under launchd.
        while True:
            vad = VadState(gate=WAKE_VOICE_RMS)   # only capture loud speech for wake
            utter = bytearray()
            peak = 0.0
            try:
                with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=block, dtype="int16", channels=1) as stream:
                    while True:
                        data, _ = stream.read(block)
                        frame = bytes(data)
                        rms = rms_from_pcm16(frame)
                        now = time.time()
                        self.on_clap_rms(rms, now)               # double-clap path
                        ev = vad.feed(rms, now)                   # voice-wake path
                        if ev in ("start", "recording"):
                            utter += frame
                            peak = max(peak, rms)
                        elif ev == "stop":
                            text = ""
                            if self._stt is not None and utter:
                                try:
                                    import io
                                    import wave
                                    buf = io.BytesIO()
                                    with wave.open(buf, "wb") as w:
                                        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
                                        w.writeframes(bytes(utter))
                                    res = self._stt.transcribe(buf.getvalue(), format="wav", language="en-SG")
                                    text = (getattr(res, "text", "") or "").strip()
                                except Exception:
                                    text = ""
                            self.on_final_transcript(text, peak)
                            utter.clear(); peak = 0.0
            except Exception as exc:
                logger.warning("wake_listener mic stream error (retry 30s): %s", exc)
                time.sleep(30)


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    WakeListener().run()


if __name__ == "__main__":  # pragma: no cover
    main()
