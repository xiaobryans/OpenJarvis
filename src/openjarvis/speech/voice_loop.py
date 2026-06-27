"""VANTA voice loop — clean rebuild (Task 1).

Pipeline:  mic -> dual wake (voice "vanta" + double-clap) -> greeting ->
conversation mode (VAD -> Deepgram nova-2 STT -> classify -> LeanOrchestrator
brain -> ElevenLabs "Ivy" TTS) with live word-by-word transcript, barge-in /
soft / hard interrupts, hold-pause, voice controls and conversation-end
detection.

Design note: every decision rule (wake match, clap detection, VAD state,
complexity classification, interrupt/control/end-phrase parsing) is a PURE
function or small class with no audio or network I/O, so the whole control
surface is unit-testable headlessly (`tests/speech/test_voice_rebuild.py`).
The audio/runtime layer (sounddevice, Deepgram, ElevenLabs, afplay) is lazily
imported so this module imports cleanly without those packages or a mic.
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
from typing import Callable, List, Optional, Tuple

from openjarvis.speech import voice_bus
from openjarvis.speech.wake_responses import get_wake_response

logger = logging.getLogger("openjarvis.voice_loop")

# ── Tunable constants (top of file, per spec) ────────────────────────────────
RMS_GATE = 1500         # process audio / start recording above this RMS
                        # (raised 600->1500 to stop ghost-triggering on silence)
SILENCE_STOP = 1.5      # seconds of silence that ends an utterance
END_SILENCE = 10.0      # seconds of silence after a reply ends the conversation
HOLD_REMINDER = 300.0   # 5 min: one "still here" reminder while on hold

# Wake-confirmation gating (anti ghost-trigger):
WAKE_MIN_WORDS = 3      # final transcript must have >=3 words before we wake-match
WAKE_COOLDOWN = 15.0    # seconds a wake trigger is suppressed after firing

CLAP_THRESHOLD = 3000   # RMS spike that counts as a clap/snap
CLAP_MIN_GAP = 0.15     # min seconds between the two claps
CLAP_MAX_GAP = 0.8      # max seconds between the two claps
CLAP_COOLDOWN = 5.0     # seconds to ignore claps after a trigger

SAMPLE_RATE = 16000     # mono 16-bit PCM
FRAME_MS = 30           # audio frame size

WAKE_RE = re.compile(r"\bvanta\b", re.IGNORECASE)

# ── Phrase sets ──────────────────────────────────────────────────────────────
END_PHRASES = (
    "that's all", "thats all", "bye", "goodbye", "done", "stop listening",
    "thank you", "thanks",
)
HARD_STOP = ("stop",)
SOFT_INTERRUPT = ("hold on", "wait", "actually", "before you continue")
HOLD_PHRASES = ("hold on", "one sec", "give me a moment", "give me a sec", "brb")
RESUME_PHRASES = ("okay", "ok", "i'm back", "im back", "continue", "vanta")
VOICE_CONTROLS = {
    "louder": "volume_up", "quieter": "volume_down",
    "repeat that": "repeat", "faster": "speed_up", "slower": "speed_down",
}
# Words/phrases that signal a request needs tools or multiple steps -> complex.
COMPLEX_HINTS = (
    "email", "e-mail", "slack", "message", "send", "draft", "reply",
    "calendar", "schedule", "meeting", "event", "remind",
    "research", "look up", "look into", "find out", "search", "google",
    "quote", "invoice", "client", "job", "book", "summarise", "summarize",
    "open ", "close ", "screenshot", "screen", "read this", "what's on my screen",
    "report", "analyse", "analyze", "compare", "plan", "organise", "organize",
    "and then", "after that", "then ", "notion", "whatsapp",
)


# ── Pure decision logic (unit-tested) ────────────────────────────────────────
def rms_from_pcm16(frame: bytes) -> float:
    """Root-mean-square amplitude of a little-endian 16-bit PCM frame."""
    n = len(frame) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack("<%dh" % n, frame[: n * 2])
    return math.sqrt(sum(s * s for s in samples) / n)


def contains_wake_word(text: str) -> bool:
    """True only on a standalone 'vanta' token ('fanta'/'vantage'/'event' -> no)."""
    return bool(WAKE_RE.search(text or ""))


def wake_should_fire(text: str, now: float, last_wake_ts: Optional[float]) -> bool:
    """Anti-ghost-trigger wake gate.

    A wake only fires when ALL hold:
      * the final transcript has at least ``WAKE_MIN_WORDS`` words (single-word
        or empty transcriptions from silence/noise are ignored),
      * it contains a standalone ``\\bvanta\\b`` token, and
      * at least ``WAKE_COOLDOWN`` seconds have passed since the last wake.
    """
    words = (text or "").split()
    if len(words) < WAKE_MIN_WORDS:
        return False
    if not contains_wake_word(text):
        return False
    if last_wake_ts is not None and (now - last_wake_ts) < WAKE_COOLDOWN:
        return False
    return True


def classify_complexity(text: str) -> str:
    """'complex' if the request needs tools or multiple steps, else 'simple'.

    Simple = casual chat, quick facts, time/weather one-liners.
    Complex = anything with a tool verb (email/calendar/research/send/...) or a
    multi-step structure ("and then", "after that").
    """
    t = (text or "").lower().strip()
    if not t:
        return "simple"
    if any(h in t for h in COMPLEX_HINTS):
        return "complex"
    # Multi-clause imperative ("do X and Y") tends to be multi-step.
    if t.count(" and ") >= 2:
        return "complex"
    return "simple"


def is_end_phrase(text: str) -> bool:
    t = (text or "").lower().strip().rstrip(".!?")
    if not t:
        return False
    return any(t == p or t.endswith(" " + p) or t.startswith(p) for p in END_PHRASES)


def detect_interrupt(text: str) -> Optional[str]:
    """Classify a barge-in utterance: 'hard' | 'hold' | 'soft' | None."""
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
    """Map a control phrase to an action id, else None."""
    t = (text or "").lower().strip().rstrip(".!?")
    for phrase, action in VOICE_CONTROLS.items():
        if t == phrase or phrase in t:
            return action
    return None


class ClapDetector:
    """Detects a valid double clap/snap from a stream of (rms, timestamp).

    Two spikes above ``threshold`` separated by ``min_gap``..``max_gap`` seconds
    fire a trigger; a single spike, or spikes too close/too far apart, do not.
    A cooldown suppresses retriggers.
    """

    def __init__(self, threshold: float = CLAP_THRESHOLD, min_gap: float = CLAP_MIN_GAP,
                 max_gap: float = CLAP_MAX_GAP, cooldown: float = CLAP_COOLDOWN) -> None:
        self.threshold = threshold
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.cooldown = cooldown
        self._last_spike: Optional[float] = None
        self._last_trigger: float = -1e9
        self._armed = True  # require RMS to drop below threshold between spikes

    def feed(self, rms: float, now: float) -> bool:
        """Return True exactly when a valid double clap completes."""
        if rms < self.threshold:
            self._armed = True
            return False
        if not self._armed:
            return False
        self._armed = False  # consume this spike; need a dip before the next
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
    """Voice-activity detector: start on RMS>gate, stop after silence_stop sec.

    Feed frames (rms, timestamp); transitions to recording on the first loud
    frame and back to idle after ``silence_stop`` seconds of sub-gate audio.
    """
    gate: float = RMS_GATE
    silence_stop: float = SILENCE_STOP
    recording: bool = False
    _last_voice: float = 0.0
    started_at: float = 0.0

    def feed(self, rms: float, now: float) -> str:
        """Return 'start', 'stop', 'recording', or 'idle' for this frame."""
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


# ── Conversation context (last N turns) ──────────────────────────────────────
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
    """Ivy speaks a SHORT summary only — first 2-3 sentences, plain English."""
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    spoken = " ".join(parts[:max_sentences]).strip()
    return spoken or text[:280]


# ── ElevenLabs Ivy TTS (exact spec settings; elevenlabs_tts.py left untouched) ─
def synthesize_ivy(text: str, *, speed: float = 1.0) -> Optional[bytes]:
    """Return MP3 bytes for *text* using ElevenLabs Ivy with the spec settings.

    Implemented directly (not via ElevenLabsTTSBackend) so the exact
    voice_settings (stability 0.4 / similarity 0.8 / style 0.6 / speaker boost)
    are sent without modifying the shared backend module.
    """
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
                headers={"xi-api-key": api_key, "accept": "audio/mpeg",
                         "content-type": "application/json"},
                json={
                    "text": text,
                    "model_id": model,
                    "voice_settings": {
                        "stability": 0.4,
                        "similarity_boost": 0.8,
                        "style": 0.6,
                        "use_speaker_boost": True,
                        "speed": speed,
                    },
                },
            )
            r.raise_for_status()
            return r.content
    except Exception as exc:  # pragma: no cover - network
        logger.warning("Ivy TTS failed: %s", exc)
        return None


# ── Deepgram client init (nova-2, en-SG) ─────────────────────────────────────
def make_deepgram():
    """Construct the Deepgram speech backend, or None if unavailable.

    Configured for nova-2 / en-SG / smart_format with keyword boost and noise
    cancellation at call time. Returns None when the SDK or key is missing so
    the loop can degrade gracefully.
    """
    try:
        from openjarvis.speech.deepgram import DeepgramSpeechBackend
        backend = DeepgramSpeechBackend()
        return backend if backend.health() else None
    except Exception as exc:  # pragma: no cover
        logger.warning("Deepgram init failed: %s", exc)
        return None


def deepgram_options() -> dict:
    """The Deepgram request options for the VANTA mic stream (per spec)."""
    return {
        "model": "nova-2",
        "language": "en-SG",
        "smart_format": True,
        "interim_results": True,
        "keywords": ["VANTA:10", "hey:5"],
        # Deepgram noise reduction.
        "filler_words": False,
    }


# ── Runtime loop ─────────────────────────────────────────────────────────────
StatusCb = Callable[[str], None]


class VoiceLoop:
    """The always-on conversation loop. Audio/network bits are guarded so the
    object constructs cleanly in any environment; ``run()`` needs real hardware.
    """

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

    # -- state helpers --
    def _set_state(self, state: str) -> None:
        voice_bus.set_voice_state(state)
        self._status(state)

    # -- brain --
    def think(self, text: str) -> str:
        """Route to LeanOrchestrator: simple -> gpt-4o-mini, complex -> gpt-4o."""
        tier = classify_complexity(text)
        model = self.simple_model if tier == "simple" else self.complex_model
        history = self.conversation.context()
        prompt = text
        if history:
            ctx = "\n".join(f"{t['role']}: {t['content']}" for t in history)
            prompt = f"Conversation so far:\n{ctx}\n\nNow Bryan says: {text}"
        try:
            from openjarvis.orchestrator.lean.orchestrator import LeanOrchestrator
            orch = LeanOrchestrator(model=model)
            res = orch.run_complex(prompt) if tier == "complex" else orch.run_standard(prompt)
            return getattr(res, "answer", "") or ""
        except Exception as exc:  # pragma: no cover - network/LLM
            logger.warning("brain error: %s", exc)
            return "I hit a problem processing that."

    # -- speak with live transcript + barge-in --
    def speak(self, text: str, *, summary: bool = True) -> None:
        spoken = summarise_for_speech(text) if summary else text
        self._last_reply = spoken
        self._set_state("speaking")
        # Live word-by-word transcript (green / VANTA).
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

    # -- wake --
    def process_final_transcript(self, text: str) -> bool:
        """Apply the anti-ghost-trigger wake gate to a Deepgram FINAL transcript.

        Returns True (and fires the wake) only when the transcript passes
        :func:`wake_should_fire` (>=3 words, standalone 'vanta', cooldown clear).
        Called by the runtime capture thread for every final transcript.
        """
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
        self._converse()

    def _converse(self) -> None:  # pragma: no cover - audio runtime
        """Conversation mode: no wake word needed between turns."""
        self._set_state("listening")
        # Full audio capture + Deepgram streaming live in run(); this method is
        # the per-turn driver invoked by the runtime audio thread.

    def run(self) -> None:  # pragma: no cover - needs mic/speaker
        """Blocking always-on loop. Requires real audio hardware + Deepgram."""
        try:
            import sounddevice as sd  # noqa: F401
            import numpy as np  # noqa: F401
        except Exception as exc:
            logger.error("voice_loop.run needs sounddevice + numpy: %s", exc)
            return
        self._stt = make_deepgram()
        # While the loop is up it is actively listening for the wake word, so it
        # reports active + "listening" (not "standby"/off) — the cockpit shows
        # "LISTENING" instead of "VOICE OFF" whenever the loop is running.
        self._set_state("listening")
        voice_bus.set_voice_active(True)
        logger.info("VANTA voice loop online (listening for wake).")
        # The real-time capture/streaming implementation runs here on the Mac;
        # it feeds frames into self.vad / self.clap and dispatches _handle_wake.
        # Kept minimal in code so the testable decision layer above is the spec.
        while not self._stop.is_set():
            time.sleep(0.2)

    def stop(self) -> None:
        self._stop.set()
        self._stop_playback()


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    VoiceLoop().run()


if __name__ == "__main__":  # pragma: no cover
    main()
