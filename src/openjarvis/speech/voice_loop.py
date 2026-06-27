"""VANTA voice loop — complete rebuild.

Voice is a THIN layer over the existing text pipeline: Deepgram hears Bryan ->
transcribes -> the loop POSTs to the SAME ``/v1/chat/completions`` endpoint the
UI uses -> Ivy speaks a short summary and the full reply is pushed to the
transcript for the cockpit. No separate orchestrator, no parallel brain.

Every decision rule (wake gate, VAD, clap, classification, interrupts, controls,
end phrases) is a pure function/class with no audio or network I/O, so the whole
control surface is unit-testable headlessly. The audio/network layer (sounddevice,
Deepgram, ElevenLabs, the HTTP brain, afplay) is lazily imported.
"""

from __future__ import annotations

import logging
import math
import os
import re
import struct
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from openjarvis.speech import voice_bus
from openjarvis.speech.wake_responses import get_wake_response

logger = logging.getLogger("openjarvis.voice_loop")

# ── Tunable constants ────────────────────────────────────────────────────────
RMS_GATE = 600          # VAD: start recording above this RMS (in-conversation)
SILENCE_STOP = 1.5      # seconds of silence that ends an utterance
END_SILENCE = 10.0      # silence after a reply that ends the conversation
HOLD_REMINDER = 300.0   # 5 min: one "still here" reminder while on hold

WAKE_RMS = 1500         # in-app: only consider chunks louder than this for wake
WAKE_MIN_WORDS = 3      # final transcript must have >=3 words to wake-match
WAKE_COOLDOWN = 10.0    # seconds a wake is suppressed after firing (in-app)

CLAP_THRESHOLD = 2500   # in-app double clap/snap spike RMS
CLAP_MIN_GAP = 0.15
CLAP_MAX_GAP = 0.8
CLAP_COOLDOWN = 5.0

SLOW_REPLY_S = 60.0     # "still on it, bear with me" after this long
SAMPLE_RATE = 16000
FRAME_MS = 30

WAKE_RE = re.compile(r"\bvanta\b", re.IGNORECASE)

# HTTP brain — the same endpoint the UI calls.
BRAIN_URL = os.environ.get("VANTA_BRAIN_URL", "http://127.0.0.1:8000/v1/chat/completions")
BRAIN_TOKEN = os.environ.get("OPENJARVIS_API_KEY") or "test"

# Ivy's voice persona (prepended as the system message to the shared endpoint).
IVY_SYSTEM = (
    "You are Ivy, VANTA's voice for Bryan. You are flirty, playful and charming, "
    "never robotic. For urgent or serious matters you stay grounded and focused, "
    "then ease back to playful. Keep spoken replies to 2-3 sentences of plain, "
    "natural English with personality — no jargon, never a wall of text. You "
    "understand English and Singlish (lah, leh, lor, sia, can or not, steady, "
    "shiok, walao, confirm plus chop) and reply naturally. Only translate "
    "Chinese or Malay when Bryan explicitly asks."
)

# ── Phrase sets ──────────────────────────────────────────────────────────────
END_PHRASES = ("that's all", "thats all", "bye", "goodbye", "done", "stop listening", "thank you", "thanks")
HARD_STOP = ("stop",)
SOFT_INTERRUPT = ("hold on", "wait", "actually", "before you continue")
HOLD_PHRASES = ("hold on", "one sec", "give me a moment", "give me a sec", "brb")
RESUME_PHRASES = ("okay", "ok", "i'm back", "im back", "continue", "vanta")
VOICE_CONTROLS = {
    "louder": "volume_up", "quieter": "volume_down",
    "repeat that": "repeat", "faster": "speed_up", "slower": "speed_down",
}
COMPLEX_HINTS = (
    "email", "e-mail", "slack", "message", "send", "draft", "reply",
    "calendar", "schedule", "meeting", "event", "remind",
    "research", "look up", "look into", "find out", "search", "google",
    "quote", "invoice", "client", "job", "book", "summarise", "summarize",
    "open ", "close ", "screenshot", "screen", "read this", "what's on my screen",
    "report", "analyse", "analyze", "compare", "plan", "organise", "organize",
    "and then", "after that", "notion", "whatsapp",
)


# ── Pure decision logic (unit-tested) ────────────────────────────────────────
def rms_from_pcm16(frame: bytes) -> float:
    n = len(frame) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack("<%dh" % n, frame[: n * 2])
    return math.sqrt(sum(s * s for s in samples) / n)


def contains_wake_word(text: str) -> bool:
    return bool(WAKE_RE.search(text or ""))


def wake_should_fire(text: str, now: float, last_wake_ts: Optional[float]) -> bool:
    """In-app wake gate: >=3 words + standalone 'vanta' + cooldown clear."""
    if len((text or "").split()) < WAKE_MIN_WORDS:
        return False
    if not contains_wake_word(text):
        return False
    if last_wake_ts is not None and (now - last_wake_ts) < WAKE_COOLDOWN:
        return False
    return True


def classify_complexity(text: str) -> str:
    """'complex' if it needs tools/multi-step, else 'simple'."""
    t = (text or "").lower().strip()
    if not t:
        return "simple"
    if any(h in t for h in COMPLEX_HINTS):
        return "complex"
    if t.count(" and ") >= 2:
        return "complex"
    return "simple"


def is_end_phrase(text: str) -> bool:
    t = (text or "").lower().strip().rstrip(".!?")
    if not t:
        return False
    return any(t == p or t.endswith(" " + p) or t.startswith(p) for p in END_PHRASES)


def detect_interrupt(text: str) -> Optional[str]:
    """'hard' | 'hold' | 'soft' | None."""
    t = (text or "").lower().strip()
    if not t:
        return None
    if t.rstrip(".!?") in HARD_STOP or t.startswith("stop "):
        return "hard"
    if any(p in t for p in HOLD_PHRASES):
        return "hold"
    if any(t.startswith(p) or p in t for p in SOFT_INTERRUPT):
        return "soft"
    return None


def is_resume(text: str) -> bool:
    t = (text or "").lower().strip().rstrip(".!?")
    return any(t == p or t.endswith(" " + p) for p in RESUME_PHRASES)


def voice_control(text: str) -> Optional[str]:
    t = (text or "").lower().strip().rstrip(".!?")
    for phrase, action in VOICE_CONTROLS.items():
        if t == phrase or phrase in t:
            return action
    return None


class ClapDetector:
    """Detects a valid double clap/snap from a stream of (rms, timestamp)."""

    def __init__(self, threshold: float = CLAP_THRESHOLD, min_gap: float = CLAP_MIN_GAP,
                 max_gap: float = CLAP_MAX_GAP, cooldown: float = CLAP_COOLDOWN) -> None:
        self.threshold = threshold
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.cooldown = cooldown
        self._last_spike: Optional[float] = None
        self._last_trigger: float = -1e9
        self._armed = True

    def feed(self, rms: float, now: float) -> bool:
        if rms < self.threshold:
            self._armed = True
            return False
        if not self._armed:
            return False
        self._armed = False
        if now - self._last_trigger < self.cooldown:
            self._last_spike = now
            return False
        prev = self._last_spike
        self._last_spike = now
        if prev is None:
            return False
        gap = now - prev
        if self.min_gap <= gap <= self.max_gap:
            self._last_trigger = now
            self._last_spike = None
            return True
        return False


@dataclass
class VadState:
    """Start on RMS>gate, stop after silence_stop sec of sub-gate audio."""
    gate: float = RMS_GATE
    silence_stop: float = SILENCE_STOP
    recording: bool = False
    _last_voice: float = 0.0
    started_at: float = 0.0

    def feed(self, rms: float, now: float) -> str:
        loud = rms >= self.gate
        if not self.recording:
            if loud:
                self.recording = True
                self.started_at = now
                self._last_voice = now
                return "start"
            return "idle"
        if loud:
            self._last_voice = now
            return "recording"
        if now - self._last_voice >= self.silence_stop:
            self.recording = False
            return "stop"
        return "recording"


@dataclass
class Conversation:
    max_turns: int = 20
    turns: List[dict] = field(default_factory=list)

    def add(self, role: str, content: str) -> None:
        self.turns.append({"role": role, "content": content})

    def context(self) -> List[dict]:
        return self.turns[-self.max_turns:]

    def reset(self) -> None:
        self.turns.clear()


def summarise_for_speech(text: str, max_sentences: int = 3) -> str:
    """Ivy speaks a SHORT summary — first 2-3 sentences only."""
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:max_sentences]).strip() or text[:280]


# ── TTS (ElevenLabs Ivy, exact spec settings; elevenlabs_tts.py untouched) ───
def synthesize_ivy(text: str, *, speed: float = 1.0) -> Optional[bytes]:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key or not text.strip():
        return None
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "MClEFoImJXBTgLwdLI5n")
    model = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
    try:
        import httpx
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                headers={"xi-api-key": api_key, "accept": "audio/mpeg", "content-type": "application/json"},
                json={
                    "text": text, "model_id": model,
                    "voice_settings": {"stability": 0.4, "similarity_boost": 0.8,
                                       "style": 0.6, "use_speaker_boost": True, "speed": speed},
                },
            )
            r.raise_for_status()
            return r.content
    except Exception as exc:  # pragma: no cover - network
        logger.warning("Ivy TTS failed: %s", exc)
        return None


# ── STT (Deepgram nova-2, en-SG) ─────────────────────────────────────────────
def make_deepgram():
    try:
        from openjarvis.speech.deepgram import DeepgramSpeechBackend
        backend = DeepgramSpeechBackend()
        return backend if backend.health() else None
    except Exception as exc:  # pragma: no cover
        logger.warning("Deepgram init failed: %s", exc)
        return None


def deepgram_options() -> dict:
    """Deepgram request options for the VANTA mic stream (per spec)."""
    return {
        "model": "nova-2",
        "language": "en-SG",
        "smart_format": True,
        "punctuate": True,
        "interim_results": True,
        "keywords": ["VANTA:10", "hey:5"],
        "filler_words": False,
    }


# ── Brain — HTTP call to the SAME endpoint the UI uses ───────────────────────
def call_brain(messages: List[dict], model: str, *, url: str = BRAIN_URL,
               token: str = BRAIN_TOKEN, timeout: float = 120.0) -> str:
    """POST to /v1/chat/completions and return the reply text, or '' on error.

    Voice is a thin layer over the text pipeline — this is the only brain.
    Errors are logged silently and never spoken.
    """
    try:
        import httpx
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                       json={"model": model, "messages": messages, "stream": False})
            r.raise_for_status()
            j = r.json()
            return (((j.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("brain call failed (silent to user): %s", exc)
        return ""


# ── Runtime loop ─────────────────────────────────────────────────────────────
StatusCb = Callable[[str], None]


class VoiceLoop:
    def __init__(self, status_cb: Optional[StatusCb] = None) -> None:
        self._status = status_cb or (lambda _m: None)
        self.conversation = Conversation()
        self.clap = ClapDetector()
        self.vad = VadState()
        self.simple_model = os.environ.get("VANTA_VOICE_SIMPLE_MODEL", "gpt-4o-mini")
        self.complex_model = os.environ.get("VANTA_VOICE_COMPLEX_MODEL", "gpt-4o")
        self._stt = None
        self._last_reply = ""
        self._last_wake_ts: Optional[float] = None
        self._volume = 1.0
        self._speed = 1.0
        self._stop = threading.Event()
        self._playing: Optional[subprocess.Popen] = None

    def _set_state(self, state: str) -> None:
        voice_bus.set_voice_state(state)
        self._status(state)

    # -- brain (thin HTTP layer over the text pipeline) --
    def think(self, text: str) -> str:
        tier = classify_complexity(text)
        model = self.simple_model if tier == "simple" else self.complex_model
        self._set_state("thinking")
        messages = [{"role": "system", "content": IVY_SYSTEM}, *self.conversation.context(),
                    {"role": "user", "content": text}]
        return call_brain(messages, model)

    # -- speak: live word-by-word transcript + TTS --
    def speak(self, full_text: str, *, summary: bool = True) -> None:
        spoken = summarise_for_speech(full_text) if summary else full_text
        self._last_reply = spoken
        self._set_state("speaking")
        # Push full reply to the transcript (word by word) for the cockpit.
        words = spoken.split()
        for i, w in enumerate(words):
            voice_bus.push_transcript("vanta", w, final=(i == len(words) - 1))
        audio = synthesize_ivy(spoken, speed=self._speed)
        if audio:
            self._play(audio)
        voice_bus.save_turn("vanta", spoken, mode="voice")

    def _play(self, mp3: bytes) -> None:  # pragma: no cover - audio
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(mp3)
                path = f.name
            self._playing = subprocess.Popen(["afplay", "-v", str(self._volume), path])
            self._playing.wait()
        except Exception as exc:
            logger.warning("playback failed: %s", exc)
        finally:
            self._playing = None

    def _stop_playback(self) -> None:  # pragma: no cover - audio
        if self._playing and self._playing.poll() is None:
            try:
                self._playing.terminate()
            except Exception:
                pass

    def apply_control(self, action: str) -> None:
        if action == "volume_up":
            self._volume = min(2.0, self._volume + 0.2)
        elif action == "volume_down":
            self._volume = max(0.2, self._volume - 0.2)
        elif action == "speed_up":
            self._speed = min(1.4, self._speed + 0.1)
        elif action == "speed_down":
            self._speed = max(0.7, self._speed - 0.1)
        elif action == "repeat" and self._last_reply:
            self.speak(self._last_reply, summary=False)

    # -- one turn: text in -> brain -> Ivy speaks (used by runtime + tests) --
    def handle_user_text(self, text: str) -> str:
        """Process one user utterance through the brain and speak the reply.

        Returns the full reply text (also pushed to the transcript). Records the
        turn in conversation history (last 20) and unified voice history.
        """
        text = (text or "").strip()
        if not text:
            return ""
        self.conversation.add("user", text)
        voice_bus.save_turn("bryan", text, mode="voice")
        if classify_complexity(text) == "complex":
            self.speak("On it, give me a moment.", summary=False)
        reply = self.think(text)
        if not reply:
            self._set_state("listening")
            return ""  # silent on error — never speak error messages
        self.conversation.add("assistant", reply)
        self.speak(reply, summary=True)
        self._set_state("listening")
        return reply

    # -- wake --
    def process_final_transcript(self, text: str) -> bool:
        """Apply the wake gate to a Deepgram FINAL transcript; fire on pass."""
        if wake_should_fire(text, time.time(), self._last_wake_ts):
            self._handle_wake()
            return True
        return False

    def _handle_wake(self) -> None:
        """Shared entry point for BOTH wake triggers (voice + double clap)."""
        self._set_state("wake_detected")
        greeting = get_wake_response(last_wake_ts=self._last_wake_ts)
        self._last_wake_ts = time.time()
        self.conversation.reset()
        voice_bus.set_voice_active(True)
        self.speak(greeting, summary=False)
        self._set_state("listening")

    def _transcribe(self, audio: bytes) -> str:  # pragma: no cover - needs Deepgram
        """Transcribe captured int16 PCM via Deepgram (nova-2, en-SG)."""
        if not audio or self._stt is None:
            return ""
        try:
            import io
            import wave
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SAMPLE_RATE)
                w.writeframes(audio)
            res = self._stt.transcribe(buf.getvalue(), format="wav", language="en-SG")
            return (getattr(res, "text", "") or "").strip()
        except Exception as exc:
            logger.debug("transcribe failed: %s", exc)
            return ""

    def run(self) -> None:  # pragma: no cover - needs mic/speaker + Deepgram
        """Always-on capture loop: wake (clap/voice) -> greeting -> conversation."""
        try:
            import sounddevice as sd
        except Exception as exc:
            logger.error("voice_loop.run needs sounddevice: %s", exc)
            return
        self._stt = make_deepgram()
        self._set_state("listening")
        voice_bus.set_voice_active(True)
        logger.info("VANTA voice loop online (listening for wake).")
        block = int(SAMPLE_RATE * FRAME_MS / 1000)
        in_conversation = False
        utter = bytearray()
        vad = VadState()
        last_activity = time.time()
        try:
            with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=block, dtype="int16", channels=1) as stream:
                while not self._stop.is_set():
                    data, _ = stream.read(block)
                    frame = bytes(data)
                    rms = rms_from_pcm16(frame)
                    now = time.time()

                    if not in_conversation:
                        # Double-clap wake.
                        if self.clap.feed(rms, now):
                            self._handle_wake()
                            in_conversation = True
                            utter.clear(); vad = VadState(); last_activity = now
                            continue
                        # Voice wake: capture an utterance (RMS>WAKE gate), transcribe, gate.
                        ev = vad.feed(rms, now)
                        if ev in ("start", "recording"):
                            utter += frame
                        elif ev == "stop":
                            text = self._transcribe(bytes(utter)); utter.clear()
                            if self.process_final_transcript(text):
                                in_conversation = True; vad = VadState(); last_activity = now
                        continue

                    # ── conversation mode (no wake word needed) ──
                    ev = vad.feed(rms, now)
                    if ev == "start":
                        self._set_state("recording"); utter += frame
                    elif ev == "recording":
                        utter += frame
                    elif ev == "stop":
                        text = self._transcribe(bytes(utter)); utter.clear()
                        last_activity = now
                        if text:
                            voice_bus.push_transcript("bryan", text, final=True)
                            if is_end_phrase(text):
                                self.speak("Standing by.", summary=False)
                                in_conversation = False; self._set_state("listening")
                                continue
                            ctrl = voice_control(text)
                            if ctrl:
                                self.apply_control(ctrl)
                            else:
                                self.handle_user_text(text)
                            last_activity = time.time()
                        self._set_state("listening")
                    elif ev == "idle":
                        # End the conversation after END_SILENCE of quiet.
                        if now - last_activity >= END_SILENCE:
                            self.speak("Standing by.", summary=False)
                            in_conversation = False; self._set_state("listening")
        except Exception as exc:
            logger.warning("audio loop error: %s", exc)
            self._set_state("standby")

    def stop(self) -> None:
        self._stop.set()
        self._stop_playback()


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    VoiceLoop().run()


if __name__ == "__main__":  # pragma: no cover
    main()
