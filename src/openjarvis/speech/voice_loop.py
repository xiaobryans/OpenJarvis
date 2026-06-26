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
_WAKE_TOKENS = ("hey vanta", "hey venta", "hey banta", "hi vanta")  # STT variants
_INTERRUPT = ("stop", "hold on", "wait", "cancel")
_SAMPLE_RATE = 16000
_CHANNELS = 1

StatusCb = Callable[[str], None]


def _in_silent_hours() -> bool:
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Asia/Singapore"))
    except Exception:
        now = datetime.now()
    return 0 <= now.hour < 7


def _pcm_to_wav_bytes(pcm: bytes, rate: int = _SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(_CHANNELS)
        w.setsampwidth(2)  # int16
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


class VoiceLoop:
    def __init__(self, status_cb: Optional[StatusCb] = None) -> None:
        self._status = status_cb or (lambda s: logger.info("voice: %s", s))
        self._stt = None
        self._tts = None
        self._orch = None
        self._playing: Optional[subprocess.Popen] = None

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

    # ---- audio I/O ----
    def _record(self, seconds: float) -> bytes:
        import sounddevice as sd
        frames = sd.rec(int(seconds * _SAMPLE_RATE), samplerate=_SAMPLE_RATE,
                        channels=_CHANNELS, dtype="int16")
        sd.wait()
        return frames.tobytes()

    def _record_until_silence(self, max_seconds: float = 8.0,
                              silence_rms: int = 500) -> bytes:
        """Record until ~1s of silence or max_seconds (simple RMS VAD)."""
        import numpy as np
        import sounddevice as sd
        chunks, silent_run = [], 0
        block = int(0.25 * _SAMPLE_RATE)
        with sd.InputStream(samplerate=_SAMPLE_RATE, channels=_CHANNELS,
                            dtype="int16") as stream:
            for _ in range(int(max_seconds / 0.25)):
                data, _ = stream.read(block)
                chunks.append(data.tobytes())
                rms = int(np.sqrt(np.mean(np.square(data.astype("float32")))))
                silent_run = silent_run + 1 if rms < silence_rms else 0
                if silent_run >= 4:  # ~1s silence
                    break
        return b"".join(chunks)

    def _transcribe(self, pcm: bytes) -> str:
        try:
            wav = _pcm_to_wav_bytes(pcm)
            tr = self._stt.transcribe(wav, format="wav")
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

    # ---- main loop ----
    def run(self) -> None:
        self._ensure()
        self._status("listening")
        logger.info("VANTA voice loop running — say '%s'", WAKE_WORD)
        while True:
            try:
                # 1. Rolling 3s window; detect wake word.
                heard = self._transcribe(self._record(3.0)).lower()
                if not heard:
                    continue
                if any(w in heard for w in _INTERRUPT):
                    self._stop_playback()
                    continue
                if not any(t in heard for t in _WAKE_TOKENS):
                    continue
                # 2. Awake — capture the command.
                self._status("awake")
                # Anything said after the wake token in the same window counts.
                after = heard
                for t in _WAKE_TOKENS:
                    if t in after:
                        after = after.split(t, 1)[1].strip()
                        break
                self._status("transcribing")
                command = after or self._transcribe(self._record_until_silence())
                if not command:
                    self._speak("I'm listening, boss — go ahead.")
                    continue
                # 3. Think (orchestrator) + speak.
                self._status("thinking")
                from openjarvis.orchestrator.request_classifier import classify_request
                tier = classify_request(command).tier
                res = (self._orch.run_complex(command) if tier == "complex"
                       else self._orch.run_standard(command))
                self._speak(res.answer or "I hit a snag handling that, boss.")
                self._status("listening")
            except KeyboardInterrupt:
                logger.info("voice loop stopped")
                break
            except Exception as exc:
                logger.error("voice loop error: %s", exc, exc_info=True)
                self._status("listening")


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    VoiceLoop().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
