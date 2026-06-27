"""Minimal always-on wake listener for VANTA (runs at login via launchd).

ONE job: detect a deliberate wake trigger and launch/foreground the VANTA app.
No orchestrator, no TTS, no brain — once the app is open its own voice loop
takes over. Tuned to be STRICTER than the in-app loop so normal conversation /
ambient noise never auto-launches the app:

  - voice wake requires RMS above the floor AND an exact ``\\bvanta\\b`` match
  - clap wake requires THREE claps (stricter than the in-app double clap), each
    above WAKE_CLAP_RMS
  - at least LAUNCH_COOLDOWN_S between any two launch attempts
  - if the app is already frontmost/active, do nothing
  - every trigger attempt is logged with a timestamp + cause

  python -m openjarvis.speech.wake_listener
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import datetime

logger = logging.getLogger("vanta.wake_listener")

# The macOS app bundle is "OpenJarvis" (kept for permission stability).
APP_NAME = os.environ.get("VANTA_APP_NAME", "OpenJarvis")
QUIET_AFTER_LAUNCH_S = 30.0
LAUNCH_COOLDOWN_S = 30.0          # minimum gap between any two launch attempts
WAKE_CLAP_RMS = 3500             # stricter than the in-app clap threshold (2500)
WAKE_CLAP_COUNT = 3              # require THREE claps for the background listener
_RATE_DEFAULT = 48000
WAKE_LOG = os.path.expanduser("~/Library/Logs/vanta-wake.log")


def _log_trigger(cause: str, action: str) -> None:
    """Append a timestamped trigger record to the wake log."""
    line = f"{datetime.now().isoformat(timespec='seconds')} TRIGGER cause={cause} action={action}\n"
    try:
        os.makedirs(os.path.dirname(WAKE_LOG), exist_ok=True)
        with open(WAKE_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
    logger.info("trigger cause=%s action=%s", cause, action)


def _app_running(name: str) -> bool:
    try:
        if subprocess.run(["pgrep", "-x", name], capture_output=True).returncode == 0:
            return True
        chk = subprocess.run(
            ["osascript", "-e", f'application "{name}" is running'],
            capture_output=True, text=True,
        )
        return chk.stdout.strip() == "true"
    except Exception:
        return False


def _app_frontmost(name: str) -> bool:
    """True if *name* is the active/frontmost app (so we should NOT relaunch)."""
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to name of first application process whose frontmost is true'],
            capture_output=True, text=True,
        )
        return r.stdout.strip().lower() == name.lower()
    except Exception:
        return False


def launch_or_front(name: str = APP_NAME) -> None:
    """Launch the app if closed, or bring it to the front if running."""
    try:
        if _app_running(name):
            subprocess.run(["osascript", "-e", f'tell application "{name}" to activate'], capture_output=True)
            logger.info("brought %s to front", name)
        else:
            subprocess.run(["open", "-a", name], capture_output=True)
            logger.info("launched %s", name)
    except Exception as exc:
        logger.warning("launch/front failed: %s", exc)


def run() -> int:
    import queue

    import numpy as np
    import sounddevice as sd
    from openjarvis.speech.voice_loop import (
        deepgram_transcribe, _normalize, _WAKE_RE, _pcm_to_wav_bytes, _RMS_GATE,
        CLAP_MIN_GAP_S, CLAP_MAX_GAP_S, CLAP_COOLDOWN_S,
    )

    try:
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
    except Exception:
        pass

    # Background voice floor: stricter than the in-app gate so ambient speech
    # doesn't keep waking Deepgram. Exact \bvanta\b is still required on top.
    voice_floor = max(_RMS_GATE, 900)

    try:
        dev = sd.query_devices(kind="input")
        rate = int(dev.get("default_samplerate") or _RATE_DEFAULT)
    except Exception:
        rate = _RATE_DEFAULT
    logger.info("VANTA wake listener online @ %d Hz (triple clap + exact 'Hey VANTA')", rate)

    q: "queue.Queue[bytes]" = queue.Queue()
    last_launch = {"t": 0.0}

    def _cb(indata, frames, t, status):
        q.put(bytes(indata))

    def _collect(seconds: float) -> bytes:
        want = int(seconds * rate * 2)
        out = b""
        while len(out) < want:
            try:
                out += q.get(timeout=1.0)
            except Exception:
                break
        return out

    def _maybe_wake(cause: str) -> None:
        now = time.monotonic()
        if (now - last_launch["t"]) < LAUNCH_COOLDOWN_S:
            _log_trigger(cause, "suppressed_cooldown")
            return
        if _app_frontmost(APP_NAME):
            _log_trigger(cause, "skipped_already_frontmost")
            last_launch["t"] = now  # treat as handled to honor cooldown
            return
        _log_trigger(cause, "launch_or_front")
        launch_or_front(APP_NAME)
        last_launch["t"] = time.monotonic()
        # Stay quiet so we don't fight the app's own voice loop, then drain.
        time.sleep(QUIET_AFTER_LAUNCH_S)
        while not q.empty():
            try:
                q.get_nowait()
            except Exception:
                break

    spikes: list[float] = []
    last_clap = 0.0
    audio_clock = 0.0
    rolling = b""
    window = int(2.0 * rate * 2)

    with sd.InputStream(samplerate=rate, channels=1, dtype="int16", callback=_cb, blocksize=int(0.1 * rate)):
        while True:
            try:
                chunk = _collect(0.4)
                if not chunk:
                    continue
                rolling = (rolling + chunk)[-window:]
                arr = np.frombuffer(chunk, dtype="int16")
                rms = int(np.sqrt(np.mean(arr.astype("float32") ** 2))) if arr.size else 0

                # ── Trigger B: TRIPLE clap (stricter) ──
                now = time.monotonic()
                if (now - last_clap) >= CLAP_COOLDOWN_S and arr.size:
                    win = max(1, int(0.03 * rate))
                    in_spike = False
                    for i in range(0, arr.size - win, win):
                        seg = arr[i:i + win].astype("float32")
                        srms = float(np.sqrt(np.mean(seg * seg))) if seg.size else 0.0
                        if srms > WAKE_CLAP_RMS and not in_spike:
                            spikes.append(audio_clock + i / rate)
                            in_spike = True
                        elif srms <= WAKE_CLAP_RMS * 0.5:
                            in_spike = False
                    if spikes:
                        newest = spikes[-1]
                        # keep enough history for (WAKE_CLAP_COUNT-1) gaps
                        span = CLAP_MAX_GAP_S * (WAKE_CLAP_COUNT - 1) + 0.1
                        spikes = [t for t in spikes if t >= newest - span]
                    if len(spikes) >= WAKE_CLAP_COUNT:
                        recent = spikes[-WAKE_CLAP_COUNT:]
                        gaps = [recent[k + 1] - recent[k] for k in range(len(recent) - 1)]
                        if all(CLAP_MIN_GAP_S <= g <= CLAP_MAX_GAP_S for g in gaps):
                            last_clap = now
                            spikes = []
                            _maybe_wake(f"{WAKE_CLAP_COUNT}-clap")
                            rolling = b""
                            audio_clock = 0.0
                            continue
                if arr.size:
                    audio_clock += arr.size / rate

                # ── Trigger A: voice "Hey VANTA" — RMS floor AND exact \bvanta\b ──
                if rms <= voice_floor:
                    continue
                heard = _normalize(deepgram_transcribe(_pcm_to_wav_bytes(rolling, rate)))
                if heard and _WAKE_RE.search(heard):
                    _maybe_wake("voice")
                    rolling = b""
                    audio_clock = 0.0
            except KeyboardInterrupt:
                logger.info("wake listener stopped")
                break
            except Exception as exc:
                logger.info("wake listener error: %s", exc)
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
