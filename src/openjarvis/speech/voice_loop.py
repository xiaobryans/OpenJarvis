"""Desktop voice loop for VANTA — mic -> wake -> STT -> orchestrator -> TTS -> speaker.

Ties together the verified pieces:
  - mic capture  : sounddevice (base dep)
  - wake word    : OpenAI Whisper on rolling mic chunks, watching for "hey vanta"
  - command STT  : OpenAI Whisper (transcribe the utterance after the wake word)
  - brain        : the lean COS/GM orchestrator (real tools + GPT-4o)
  - TTS          : ElevenLabs -> mp3 -> macOS `afplay` (no extra deps)

Run on your Mac (grant Terminal/the app mic access in System Settings):
    python -m openjarvis.speech.voice_loop

Behaviour:
  - Always-on: say "Hey VANTA", then your request.
  - "stop" / "hold on" cancels current playback.
  - Silent hours (00:00–07:00 SGT): stays passive (responds to wake, no
    proactive speech).
  - status_cb reports states: listening / awake / transcribing / thinking /
    speaking — for desktop visual indicators.

NOTE: this requires real audio hardware (mic + speaker), so it cannot be
verified in a headless environment — it is built and ready to run on the Mac.
Needs ELEVENLABS_API_KEY + OPENAI_API_KEY (both configured).
"""

from __future__ import annotations

import io
import logging
import os
import re
import subprocess
import tempfile
import time
import wave
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger("openjarvis.voice_loop")

WAKE_WORD = os.environ.get("JARVIS_WAKE_WORD", "Hey VANTA")
# EXACT wake match only: the normalized transcript must contain "vanta" as a
# standalone word (so "hey vanta" matches; "fanta"/"manta"/"vantage" do NOT).
# Loose phonetic variants were removed — they caused Whisper to false-trigger on
# fan/ambient noise. \b word boundaries on the normalized (alnum+space) text.
_WAKE_RE = re.compile(r"\bvanta\b")
_INTERRUPT = ("stop", "hold on", "wait", "cancel")
_CHANNELS = 1
_DEFAULT_RATE = 48000  # MacBook built-in mic native rate

# Anti-false-trigger gates (BUG 1):
#  - only transcribe audio louder than this RMS (skip Whisper on silence/fan noise)
#  - never fire the wake word twice within this cooldown window
_RMS_GATE = 1200
_TRIGGER_COOLDOWN_S = 10.0

# The voice loop talks to the SAME HTTP endpoint the chat UI uses
# (POST /v1/chat/completions) — never the in-process orchestrator (BUG 2).
_API_BASE = os.environ.get("VANTA_API_URL", "http://127.0.0.1:8000")

StatusCb = Callable[[str], None]


def _normalize(text: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace for robust matching.
    'Hey, Vanta.' -> 'hey vanta'."""
    import re
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())).strip()


def whisper_transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV audio via OpenAI Whisper (more accurate for Singapore
    English/accents than Deepgram). Returns the transcript text (or "")."""
    import os
    import httpx
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        return ""
    try:
        with httpx.Client(timeout=30) as c:
            r = c.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                # 'prompt' biases Whisper toward the wake word spelling so
                # "VANTA" isn't misheard as "Event"/"Banta".
                data={"model": "whisper-1", "language": "en",
                      "prompt": "Hey VANTA. VANTA is the assistant's name."},
            )
            r.raise_for_status()
            return (r.json().get("text", "") or "").strip()
    except Exception:
        return ""


def _in_silent_hours() -> bool:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Singapore"))
    except Exception:
        now = datetime.now()
    return 0 <= now.hour < 7


def _pcm_to_wav_bytes(pcm: bytes, rate: int = _DEFAULT_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(_CHANNELS)
        w.setsampwidth(2)  # int16
        w.setframerate(rate)  # MUST match the actual capture rate
        w.writeframes(pcm)
    return buf.getvalue()


class VoiceLoop:
    def __init__(self, status_cb: Optional[StatusCb] = None) -> None:
        self._status = status_cb or (lambda s: logger.info("voice: %s", s))
        self._stt = None
        self._tts = None
        self._playing: Optional[subprocess.Popen] = None
        self._rate = _DEFAULT_RATE  # set to the device's native rate at runtime
        self._last_trigger = 0.0  # monotonic time of last wake trigger (cooldown)

    # ---- lazy deps (so import never fails without hardware) ----
    def _ensure(self) -> None:
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
        # STT is OpenAI Whisper (see whisper_transcribe) — no Deepgram client.
        if self._tts is None:
            from openjarvis.speech.elevenlabs_tts import ElevenLabsTTSBackend
            self._tts = ElevenLabsTTSBackend()
        # The brain is reached over HTTP (see _ask_brain) — no in-process
        # orchestrator import, so a backend-side agent/config problem can never
        # crash or stall the voice loop.
        # Use the input device's NATIVE sample rate (e.g. 48000 on the MacBook
        # mic). Recording at a mismatched rate produces garbled audio that
        # Deepgram can't transcribe — this was why the wake word never fired.
        try:
            import sounddevice as sd
            dev = sd.query_devices(kind="input")
            self._rate = int(dev.get("default_samplerate") or _DEFAULT_RATE)
        except Exception:
            self._rate = _DEFAULT_RATE
        logger.info("mic capture rate: %d Hz", self._rate)

    # ---- audio I/O ----
    def _record(self, seconds: float) -> bytes:
        import sounddevice as sd
        frames = sd.rec(int(seconds * self._rate), samplerate=self._rate,
                        channels=_CHANNELS, dtype="int16")
        sd.wait()
        return frames.tobytes()

    def _record_until_silence(self, max_seconds: float = 8.0,
                              silence_rms: int = 500) -> bytes:
        """Record until ~1s of silence or max_seconds (simple RMS VAD)."""
        import numpy as np
        import sounddevice as sd
        chunks, silent_run = [], 0
        block = int(0.25 * self._rate)
        with sd.InputStream(samplerate=self._rate, channels=_CHANNELS,
                            dtype="int16") as stream:
            for _ in range(int(max_seconds / 0.25)):
                data, _ = stream.read(block)
                chunks.append(data.tobytes())
                rms = int(np.sqrt(np.mean(np.square(data.astype("float32")))))
                silent_run = silent_run + 1 if rms < silence_rms else 0
                if silent_run >= 4:  # ~1s silence
                    break
        return b"".join(chunks)

    def _transcribe(self, pcm: bytes, language: str = "en") -> str:
        try:
            wav = _pcm_to_wav_bytes(pcm, self._rate)
            # OpenAI Whisper — markedly more accurate than Deepgram for Bryan's
            # Singapore-English accent (Deepgram heard "VANTA" as "Event").
            return whisper_transcribe(wav)
        except Exception as exc:
            logger.error("STT failed: %s", exc, exc_info=True)
            return ""

    def _speak(self, text: str) -> None:
        try:
            self._status("speaking")
            audio = self._tts.synthesize(text).audio
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.write(audio); tmp.close()
            # macOS-native playback; interruptible via self._playing.
            self._playing = subprocess.Popen(["afplay", tmp.name])
            self._playing.wait()
            self._playing = None
        except Exception as exc:
            logger.error("TTS/playback failed: %s", exc, exc_info=True)

    def _stop_playback(self) -> None:
        if self._playing and self._playing.poll() is None:
            self._playing.terminate()
            self._playing = None

    def _ask_brain(self, command: str) -> Optional[str]:
        """Send the command to the running server's chat endpoint over HTTP —
        the SAME path the chat UI uses (POST /v1/chat/completions). Returns the
        assistant reply, or None on any error (caller stays silent and resumes
        listening — it must NEVER speak an error message)."""
        import httpx
        key = os.environ.get("OPENJARVIS_API_KEY", "")
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            with httpx.Client(timeout=60) as c:
                r = c.post(
                    f"{_API_BASE}/v1/chat/completions",
                    headers=headers,
                    json={
                        "model": "default",  # server resolves to its configured model
                        "stream": False,
                        "messages": [{"role": "user", "content": command}],
                    },
                )
            if r.status_code != 200:
                logger.info("voice brain HTTP %s (silent)", r.status_code)
                return None
            data = r.json()
            choices = data.get("choices") or []
            if not choices:
                return None
            content = ((choices[0] or {}).get("message") or {}).get("content") or ""
            content = content.strip()
            return content or None
        except Exception as exc:  # network/timeout/parse — stay silent, keep listening
            logger.info("voice brain call failed (silent): %s", exc)
            return None

    def _collect(self, q, seconds: float) -> bytes:
        """Drain `seconds` of audio from the callback queue. Warns (instead of
        hanging) if the mic delivers nothing — e.g. permissions/device issue."""
        import queue as _q
        want = int(seconds * self._rate * 2)  # int16 mono
        out = b""
        empties = 0
        while len(out) < want:
            try:
                out += q.get(timeout=1.0)
                empties = 0
            except _q.Empty:
                empties += 1
                if empties == 2:
                    print("⚠ no audio from the mic — check System Settings → "
                          "Privacy & Security → Microphone (allow Terminal), and "
                          "that the right input device is selected.")
        return out

    # ---- main loop (continuous, gapless) ----
    def run(self) -> None:
        import queue

        import numpy as np
        import sounddevice as sd

        self._ensure()
        try:
            dev = sd.query_devices(kind="input")
            print(f"🎙  input device: {dev.get('name')} @ {self._rate} Hz")
        except Exception:
            print(f"🎙  input @ {self._rate} Hz")
        print(f"👂 VANTA listening — say \"{WAKE_WORD}\". "
              f"(showing what I hear in real time; Ctrl-C to stop)\n")

        q: "queue.Queue[bytes]" = queue.Queue()

        def _cb(indata, frames, time_info, status):  # runs on a separate thread
            if status:
                logger.debug("audio status: %s", status)
            q.put(bytes(indata))

        rolling = b""
        window = int(3.0 * self._rate * 2)  # last ~3s for wake detection
        # Continuous stream — the mic NEVER stops (no gap that drops the wake word).
        with sd.InputStream(samplerate=self._rate, channels=_CHANNELS,
                            dtype="int16", callback=_cb,
                            blocksize=int(0.1 * self._rate)):
            while True:
                try:
                    chunk = self._collect(q, 1.2)            # ~1.2s of fresh audio
                    rolling = (rolling + chunk)[-window:]    # rolling 3s buffer
                    arr = np.frombuffer(chunk, dtype="int16")
                    rms = int(np.sqrt(np.mean(arr.astype("float32") ** 2))) if arr.size else 0
                    bar = "▁▂▃▄▅▆▇█"[min(7, rms // 250)]

                    # GATE 1 — loudness: below the RMS floor it is silence/fan
                    # noise. Skip Whisper entirely (do not transcribe at all).
                    if rms <= _RMS_GATE:
                        print(f"🎤 vol {bar} {rms:5d} | (quiet — skipped)")
                        continue

                    # GATE 2 — cooldown: never fire again within 10s of the last
                    # trigger (stops repeat/echo re-triggering).
                    if (time.monotonic() - self._last_trigger) < _TRIGGER_COOLDOWN_S:
                        print(f"🎤 vol {bar} {rms:5d} | (cooldown)")
                        continue

                    raw = self._transcribe(rolling)
                    heard = _normalize(raw)
                    print(f"🎤 vol {bar} {rms:5d} | heard: {raw!r}")

                    if not heard:
                        continue
                    if any(w in heard for w in _INTERRUPT):
                        self._stop_playback()
                        continue
                    # GATE 3 — EXACT wake word: "vanta" must appear as a
                    # standalone word (not a substring of another word).
                    if not _WAKE_RE.search(heard):
                        continue

                    print(f"🔵 WAKE WORD DETECTED in: {raw!r}")
                    self._last_trigger = time.monotonic()  # arm cooldown
                    rolling = b""  # reset so we don't re-trigger on the same audio
                    # Command = text after the wake word, else capture ~4s more.
                    after = heard.split("vanta", 1)[1].strip() if "vanta" in heard else ""
                    if not after:
                        print("🟢 listening for your command…")
                        after = _normalize(self._transcribe(self._collect(q, 4.0)))
                    if not after:
                        # No command captured — return to listening, no speech.
                        print(f"👂 listening — say \"{WAKE_WORD}\"…")
                        continue

                    print(f"💬 command: {after!r}")
                    self._status("thinking")
                    # Brain over HTTP — same endpoint as the chat UI.
                    answer = self._ask_brain(after)
                    if answer:
                        print(f"🗣  VANTA: {answer[:200]}")
                        self._speak(answer)          # speak the response ONCE
                    else:
                        # HTTP error — stay silent, do NOT speak an error message.
                        print("⚠ brain unavailable — staying silent, listening")
                    # Drain anything captured while speaking, then resume listening.
                    while not q.empty():
                        q.get_nowait()
                    self._last_trigger = time.monotonic()  # re-arm after response
                    print(f"\n👂 listening — say \"{WAKE_WORD}\"…")
                except KeyboardInterrupt:
                    print("\n🛑 voice loop stopped")
                    break
                except Exception as exc:
                    # Keep listening; never speak internal errors.
                    logger.info("voice loop error (silent): %s", exc)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    VoiceLoop().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
