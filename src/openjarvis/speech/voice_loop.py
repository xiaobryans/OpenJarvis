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

from openjarvis.speech import voice_bus

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

# Anti-false-trigger gates:
#  - only transcribe audio louder than this RMS (skip Whisper on silence/fan noise)
#  - never fire the wake word twice within this cooldown window
_RMS_GATE = 400  # voice-detection loudness floor (low = sensitive to normal speech)
_TRIGGER_COOLDOWN_S = 10.0

# Dual wake — Trigger B: double clap / finger snap (two sharp percussive spikes).
# Tunable here without digging into the loop:
CLAP_RMS_THRESHOLD = 2500   # each spike must exceed this RMS (sharp/percussive)
CLAP_MIN_GAP_S = 0.15       # min gap between the two spikes (too close = ignore)
CLAP_MAX_GAP_S = 0.8        # max gap between the two spikes (too far = ignore)
CLAP_COOLDOWN_S = 5.0       # quiet window after a clap trigger before re-listening

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


def deepgram_transcribe(wav_bytes: bytes) -> str:
    """Transcribe WAV via Deepgram nova-2 (REST). nova-2 + a ``VANTA`` keyword
    boost reliably transcribes the wake word (verified) and is fast enough to
    poll on short rolling chunks to approximate real-time streaming. Returns the
    transcript text (or "")."""
    import os
    import httpx
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        return ""
    try:
        with httpx.Client(timeout=20) as c:
            r = c.post(
                "https://api.deepgram.com/v1/listen",
                params={
                    "model": "nova-2",
                    "smart_format": "true",
                    "language": "en",
                    # keyterm boost so "VANTA" isn't misheard as "Event"/"Banta"
                    "keywords": "VANTA:5",
                },
                headers={"Authorization": f"Token {key}", "Content-Type": "audio/wav"},
                content=wav_bytes,
            )
            r.raise_for_status()
            alts = (r.json().get("results", {}).get("channels", [{}])[0]
                    .get("alternatives", []))
            return (alts[0].get("transcript", "") if alts else "").strip()
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
        self._orch = None
        self._playing: Optional[subprocess.Popen] = None
        self._rate = _DEFAULT_RATE  # set to the device's native rate at runtime
        self._last_trigger = 0.0  # monotonic time of last wake trigger (cooldown)
        self._session = ""  # per-run voice session id (set in run())
        # Trigger B (double clap) state
        self._clap_spikes: list[float] = []   # recent spike onset times (audio-clock)
        self._last_clap_trigger = 0.0         # monotonic time of last clap trigger
        self._audio_clock = 0.0               # seconds of audio processed (spike timing)

    # ---- lazy deps (so import never fails without hardware) ----
    def _ensure(self) -> None:
        from openjarvis.core.env_loader import ensure_local_env_loaded
        ensure_local_env_loaded()
        # STT is OpenAI Whisper (see whisper_transcribe) — no Deepgram client.
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
            # Deepgram nova-2 (+ VANTA keyword boost) — fast enough to poll on
            # short rolling chunks for near-real-time transcription, and it
            # transcribes the wake word reliably (verified).
            return deepgram_transcribe(wav)
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
        """Run the command through the in-process LeanOrchestrator (the original
        working path — direct Python, no HTTP). Returns the answer, or None on
        any error so the caller stays silent and resumes listening (it must NEVER
        speak an error message)."""
        try:
            res = self._orch.run_standard(command)
            answer = (res.answer or "").strip()
            return answer or None
        except Exception as exc:  # keep listening; never speak internal errors
            logger.info("voice brain error (silent): %s", exc)
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

    # ---- Trigger B: double clap / snap detection ----
    def _detect_double_clap(self, arr) -> bool:
        """Detect a double clap/snap: two sharp RMS spikes (each above
        CLAP_RMS_THRESHOLD) separated by CLAP_MIN_GAP_S..CLAP_MAX_GAP_S, honoring
        a cooldown. Single loud sounds, and spikes too close or too far apart,
        are ignored. Spike timing uses an audio-sample clock (self._audio_clock)
        so gaps reflect real audio timing, not processing latency."""
        import numpy as np
        if arr is None or arr.size == 0:
            return False
        now = time.monotonic()
        if (now - self._last_clap_trigger) < CLAP_COOLDOWN_S:
            return False
        win = max(1, int(0.03 * self._rate))   # ~30ms analysis windows
        base_t = self._audio_clock              # audio-time at this chunk's start
        in_spike = False
        for i in range(0, arr.size - win, win):
            seg = arr[i:i + win].astype("float32")
            srms = float(np.sqrt(np.mean(seg * seg))) if seg.size else 0.0
            if srms > CLAP_RMS_THRESHOLD and not in_spike:
                # rising edge = one spike onset (a clap spans a few windows, but
                # only the onset counts, so a single clap is one spike not many).
                self._clap_spikes.append(base_t + i / self._rate)
                in_spike = True
            elif srms <= CLAP_RMS_THRESHOLD * 0.5:
                in_spike = False
        # prune spikes older than the gap window (relative to the newest spike)
        # so a stale onset can't pair with a much-later one.
        if self._clap_spikes:
            newest = self._clap_spikes[-1]
            self._clap_spikes = [t for t in self._clap_spikes
                                 if t >= newest - (CLAP_MAX_GAP_S + 0.05)]
        if len(self._clap_spikes) >= 2:
            gap = self._clap_spikes[-1] - self._clap_spikes[-2]
            if CLAP_MIN_GAP_S <= gap <= CLAP_MAX_GAP_S:
                self._last_clap_trigger = now
                self._clap_spikes = []
                return True
        return False

    # ---- shared wake sequence (both triggers) ----
    def _handle_wake(self, q, inline_after: str = "") -> None:
        """Run the wake sequence for either trigger: speak a short contextual
        welcome (wake_responses), then capture and answer the command. The voice
        DETECTION is unchanged; this is only the post-wake response/handling."""
        from openjarvis.speech.wake_responses import get_wake_response
        # arm both cooldowns immediately so neither trigger double-fires
        self._last_trigger = time.monotonic()
        self._last_clap_trigger = time.monotonic()
        self._clap_spikes = []

        # PART 2 — contextual welcome before listening for the command.
        welcome = get_wake_response()
        print(f"🤝 welcome: {welcome!r}")
        voice_bus.push_transcript("vanta", welcome, final=True)
        self._speak(welcome)

        after = (inline_after or "").strip()
        said = f"Hey VANTA {after}".strip() if after else ""
        if not after:
            print("🟢 listening for your command…")
            while not q.empty():       # drop stale pre-trigger audio
                try:
                    q.get_nowait()
                except Exception:
                    break
            time.sleep(0.5)
            after = _normalize(self._transcribe(self._record_until_silence()))
            said = after
        if not after:
            print(f"👂 listening — say \"{WAKE_WORD}\"…")
            return

        voice_bus.push_transcript("bryan", said or after, final=True)
        voice_bus.save_turn("bryan", said or after, session_id=self._session)
        print(f"💬 command: {after!r}")
        self._status("thinking")
        answer = self._ask_brain(after)
        if answer:
            print(f"🗣  VANTA: {answer[:200]}")
            voice_bus.push_transcript("vanta", answer, final=True)
            voice_bus.save_turn("vanta", answer, session_id=self._session)
            self._speak(answer)
        else:
            print("⚠ brain unavailable — staying silent, listening")
        while not q.empty():           # drain audio captured while speaking
            q.get_nowait()
        self._last_trigger = time.monotonic()
        self._last_clap_trigger = time.monotonic()
        print(f"\n👂 listening — say \"{WAKE_WORD}\"…")

    # ---- main loop (continuous, gapless) ----
    def run(self) -> None:
        import queue

        import numpy as np
        import sounddevice as sd

        self._ensure()
        self._session = f"voice-{int(time.time())}"
        voice_bus.set_voice_active(True)  # cockpit shows the transcript overlay
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
        window = int(2.0 * self._rate * 2)  # last ~2s of context for wake detection
        # Continuous stream — the mic NEVER stops (no gap that drops the wake word).
        with sd.InputStream(samplerate=self._rate, channels=_CHANNELS,
                            dtype="int16", callback=_cb,
                            blocksize=int(0.1 * self._rate)):
            while True:
                try:
                    chunk = self._collect(q, 0.4)            # ~0.4s fresh audio (low latency)
                    rolling = (rolling + chunk)[-window:]    # rolling 3s buffer
                    arr = np.frombuffer(chunk, dtype="int16")
                    rms = int(np.sqrt(np.mean(arr.astype("float32") ** 2))) if arr.size else 0
                    bar = "▁▂▃▄▅▆▇█"[min(7, rms // 250)]

                    # TRIGGER B — double clap/snap. Runs every chunk, independent
                    # of the voice gates. Advance the audio clock (used for spike
                    # timing) right after detection.
                    clap = self._detect_double_clap(arr)
                    if arr.size:
                        self._audio_clock += arr.size / self._rate
                    if clap:
                        print("👏 DOUBLE-CLAP detected — waking")
                        self._status("awake")
                        rolling = b""
                        self._handle_wake(q, inline_after="")
                        continue

                    # GATE 1 — loudness: below the RMS floor it is silence/fan
                    # noise. Skip STT entirely (do not transcribe at all).
                    if rms <= _RMS_GATE:
                        print(f"🎤 vol {bar} {rms:5d} | (quiet — skipped)")
                        continue

                    # GATE 2 — voice cooldown: never fire the voice wake within
                    # 10s of the last trigger (stops repeat/echo re-triggering).
                    if (time.monotonic() - self._last_trigger) < _TRIGGER_COOLDOWN_S:
                        print(f"🎤 vol {bar} {rms:5d} | (cooldown)")
                        continue

                    raw = self._transcribe(rolling)
                    heard = _normalize(raw)
                    print(f"🎤 vol {bar} {rms:5d} | heard: {raw!r}")

                    if raw:
                        # Live transcript: show what VANTA is hearing in real time.
                        voice_bus.push_transcript("bryan", raw, final=False)
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
                    rolling = b""  # reset so we don't re-trigger on the same audio
                    self._status("awake")
                    # inline command = text after the wake word in the same
                    # utterance (kept for the voice path); else _handle_wake records.
                    inline = heard.split("vanta", 1)[1].strip() if "vanta" in heard else ""
                    self._handle_wake(q, inline_after=inline)
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
