"""Minimal always-on wake listener for VANTA (runs at login via launchd).

ONE job: detect a wake trigger — a voice "Hey VANTA" or a double clap — and
launch/foreground the VANTA app. No orchestrator, no TTS, no brain; once the app
is open its own voice loop takes over. It reuses only the lightweight *detection*
helpers from voice_loop (Deepgram transcribe, wake regex, clap constants) — none
of the brain/TTS code runs here.

To avoid two voice loops fighting over the mic, after launching the app this
listener goes quiet for QUIET_AFTER_LAUNCH_S, then resumes (so it recovers if the
app is closed or crashes).

  python -m openjarvis.speech.wake_listener
"""

from __future__ import annotations

import logging
import os
import subprocess
import time

logger = logging.getLogger("vanta.wake_listener")

# The macOS app bundle is "OpenJarvis" (kept for permission stability).
APP_NAME = os.environ.get("VANTA_APP_NAME", "OpenJarvis")
QUIET_AFTER_LAUNCH_S = 30.0
_RATE_DEFAULT = 48000


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


def launch_or_front(name: str = APP_NAME) -> None:
    """Launch the app if closed, or bring it to the front if already running."""
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
        CLAP_RMS_THRESHOLD, CLAP_MIN_GAP_S, CLAP_MAX_GAP_S, CLAP_COOLDOWN_S,
    )

    try:
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
    except Exception:
        pass

    try:
        dev = sd.query_devices(kind="input")
        rate = int(dev.get("default_samplerate") or _RATE_DEFAULT)
    except Exception:
        rate = _RATE_DEFAULT
    logger.info("VANTA wake listener online @ %d Hz (double clap + 'Hey VANTA')", rate)

    q: "queue.Queue[bytes]" = queue.Queue()

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

    def _wake(reason: str) -> None:
        logger.info("WAKE (%s) — launching/fronting %s", reason, APP_NAME)
        launch_or_front(APP_NAME)
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
    window = int(3.0 * rate * 2)

    with sd.InputStream(samplerate=rate, channels=1, dtype="int16", callback=_cb, blocksize=int(0.1 * rate)):
        while True:
            try:
                chunk = _collect(1.2)
                if not chunk:
                    continue
                rolling = (rolling + chunk)[-window:]
                arr = np.frombuffer(chunk, dtype="int16")
                rms = int(np.sqrt(np.mean(arr.astype("float32") ** 2))) if arr.size else 0

                # ── Trigger B: double clap ──
                now = time.monotonic()
                if (now - last_clap) >= CLAP_COOLDOWN_S and arr.size:
                    win = max(1, int(0.03 * rate))
                    in_spike = False
                    for i in range(0, arr.size - win, win):
                        seg = arr[i:i + win].astype("float32")
                        srms = float(np.sqrt(np.mean(seg * seg))) if seg.size else 0.0
                        if srms > CLAP_RMS_THRESHOLD and not in_spike:
                            spikes.append(audio_clock + i / rate)
                            in_spike = True
                        elif srms <= CLAP_RMS_THRESHOLD * 0.5:
                            in_spike = False
                    if spikes:
                        newest = spikes[-1]
                        spikes = [t for t in spikes if t >= newest - (CLAP_MAX_GAP_S + 0.05)]
                    if len(spikes) >= 2 and CLAP_MIN_GAP_S <= (spikes[-1] - spikes[-2]) <= CLAP_MAX_GAP_S:
                        last_clap = now
                        spikes = []
                        _wake("double-clap")
                        rolling = b""
                        audio_clock = 0.0
                        continue
                if arr.size:
                    audio_clock += arr.size / rate

                # ── Trigger A: voice "Hey VANTA" (RMS-gated) ──
                if rms <= _RMS_GATE:
                    continue
                heard = _normalize(deepgram_transcribe(_pcm_to_wav_bytes(rolling, rate)))
                if heard and _WAKE_RE.search(heard):
                    _wake("voice")
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
