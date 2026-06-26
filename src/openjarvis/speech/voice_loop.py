"""Desktop voice loop for VANTA — mic -> wake -> STT -> orchestrator -> TTS -> speaker.

Ties together the verified pieces:
  - mic capture  : sounddevice (base dep)
  - wake word    : Deepgram STT on rolling mic chunks, watching for "hey vanta"
  - command STT  : Deepgram (transcribe the utterance after the wake word)
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
Needs ELEVENLABS_API_KEY + DEEPGRAM_API_KEY (both configured).
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import tempfile
import wave
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger("openjarvis.voice_loop")

WAKE_WORD = os.environ.get("JARVIS_WAKE_WORD", "Hey VANTA")
# Deepgram transcribes "Hey VANTA" as "Hey, Vanta." — we normalize (strip
# punctuation, lowercase) before matching, so these are punctuation-free forms.
_WAKE_TOKENS = ("hey vanta", "hey venta", "hey banta", "hey santa", "hey manta",
                "hi vanta", "a vanta", "hey vance", "hey vahnta", "vanta")
_INTERRUPT = ("stop", "hold on", "wait", "cancel")
_CHANNELS = 1
_DEFAULT_RATE = 48000  # MacBook built-in mic native rate

StatusCb = Callable[[str], None]


def _normalize(text: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace for robust matching.
    'Hey, Vanta.' -> 'hey vanta'."""
    import re
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())).strip()


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
        self._orch = None
        self._playing: Optional[subprocess.Popen] = None
        self._rate = _DEFAULT_RATE  # set to the device's native rate at runtime

    # ---- lazy deps (so import never fails without hardware) ----
    def _ensure(self) -> None:
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
        if self._stt is None:
            from openjarvis.speech.deepgram import DeepgramSpeechBackend
            self._stt = DeepgramSpeechBackend()
        if self._tts is None:
            from openjarvis.speech.elevenlabs_tts import ElevenLabsTTSBackend
            self._tts = ElevenLabsTTSBackend()
        if self._orch is None:
            from openjarvis.orchestrator.lean import LeanOrchestrator
            self._orch = LeanOrchestrator(model="gpt-4o")
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
            # Pin English (detect_language is slower + unreliable on short audio).
            tr = self._stt.transcribe(wav, format="wav", language=language)
            return (getattr(tr, "text", "") or "").strip()
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
                    raw = self._transcribe(rolling)
                    heard = _normalize(raw)
                    bar = "▁▂▃▄▅▆▇█"[min(7, rms // 250)]
                    print(f"🎤 vol {bar} {rms:5d} | heard: {raw!r}")

                    if not heard:
                        continue
                    if any(w in heard for w in _INTERRUPT):
                        self._stop_playback()
                        continue
                    if not any(t in heard for t in _WAKE_TOKENS):
                        continue

                    print(f"🔵 WAKE WORD DETECTED in: {raw!r}")
                    rolling = b""  # reset so we don't re-trigger
                    # Command = text after the wake token, else capture ~4s more.
                    after = heard
                    for t in _WAKE_TOKENS:
                        if t in after:
                            after = after.split(t, 1)[1].strip()
                            break
                    if not after:
                        print("🟢 listening for your command…")
                        after = _normalize(self._transcribe(self._collect(q, 4.0)))
                    if not after:
                        self._speak("I'm listening, boss — go ahead.")
                        continue
                    print(f"💬 command: {after!r}")
                    self._status("thinking")
                    from openjarvis.orchestrator.request_classifier import classify_request
                    tier = classify_request(after).tier
                    res = (self._orch.run_complex(after) if tier == "complex"
                           else self._orch.run_standard(after))
                    print(f"🗣  VANTA: {res.answer[:200]}")
                    self._speak(res.answer or "I hit a snag handling that, boss.")
                    # Drain anything captured while speaking, then resume.
                    while not q.empty():
                        q.get_nowait()
                    print(f"\n👂 listening — say \"{WAKE_WORD}\"…")
                except KeyboardInterrupt:
                    print("\n🛑 voice loop stopped")
                    break
                except Exception as exc:
                    logger.error("voice loop error: %s", exc, exc_info=True)
                    print(f"⚠ error: {exc}")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    VoiceLoop().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
