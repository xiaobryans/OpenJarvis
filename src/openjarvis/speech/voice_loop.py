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
from dotenv import load_dotenv
load_dotenv("/Users/user/VANTA/.env")
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
RMS_GATE = 600          # VAD: START recording above this RMS
VAD_STOP_RMS = 400      # VAD: below this counts as silence (hysteresis stop gate)
BARGE_RMS = 800         # barge-in: Bryan speaking over Ivy is detected above this
SILENCE_STOP = 0.8      # seconds of sub-stop-gate silence that ends an utterance
# NOTE: there is intentionally NO maximum recording time — Bryan is never cut off.
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
# Hold/pause (FIX 4): step away, resume later. Soft interrupt (FIX 5): add to the
# current turn. "hold on"/"wait" are treated as hold (checked before soft).
HOLD_PHRASES = ("hold on", "wait", "one sec", "give me a moment", "give me a sec", "brb")
SOFT_INTERRUPT = ("actually", "before you continue")
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


def classify_interrupt(text: str) -> str:
    """Classify a barge-in (Task 2): 'hard' (stop -> drop original), 'soft'
    (hold on/wait/actually/before you continue -> answer both), or 'new'
    (a fresh request -> answer it; the brain still has 20-turn context)."""
    t = (text or "").lower().strip()
    if not t:
        return "new"
    if t.rstrip(".!?") in HARD_STOP or t.startswith("stop "):
        return "hard"
    if any(p in t for p in SOFT_INTERRUPT) or any(p in t for p in HOLD_PHRASES):
        return "soft"
    return "new"


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
    """Hysteresis VAD: START when RMS > start_gate; STOP only when RMS stays
    below stop_gate for silence_stop seconds. NO maximum recording time — Bryan
    is never cut off mid-sentence."""
    start_gate: float = RMS_GATE       # 600
    stop_gate: float = VAD_STOP_RMS    # 400
    silence_stop: float = SILENCE_STOP  # 0.8
    recording: bool = False
    _last_voice: float = 0.0
    started_at: float = 0.0

    def feed(self, rms: float, now: float) -> str:
        if not self.recording:
            if rms > self.start_gate:
                self.recording = True
                self.started_at = now
                self._last_voice = now
                return "start"
            return "idle"
        if rms >= self.stop_gate:          # still talking -> reset the silence timer
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


# ── STT (Deepgram nova-2, deepgram-sdk==3.7.0) ───────────────────────────────
# Confirmed-working v3.7.0 syntax (live-tested on Bryan's machine):
#   DeepgramClient(api_key=key)
#   dg.listen.rest.v("1").transcribe_file({"buffer": pcm}, PrerecordedOptions(...))
# Do NOT use deepgram-sdk v6 (different, breaking API: listen.v1.media...).
def make_deepgram():
    """Construct a Deepgram v3.7.0 client (api_key=...), or None if unavailable."""
    try:
        from deepgram import DeepgramClient
        key = os.getenv("DEEPGRAM_API_KEY")
        if not key:
            print("[VANTA voice] DEEPGRAM_API_KEY not set — STT disabled", flush=True)
            return None
        print("[VANTA voice] Deepgram client ready (nova-2, language=en)", flush=True)
        return DeepgramClient(api_key=key)
    except Exception as exc:  # pragma: no cover
        logger.warning("Deepgram init failed: %s", exc)
        print(f"[VANTA voice] Deepgram init failed: {exc}", flush=True)
        return None


def deepgram_options() -> dict:
    """Deepgram PrerecordedOptions fields for the VANTA mic (nova-2, auto-lang, raw PCM)."""
    return {
        "model": "nova-2",
        "detect_language": True,   # auto-detect — handles Singapore accent better than en
        "sample_rate": 16000,
        "channels": 1,
        "encoding": "linear16",
        "smart_format": True,
        "keywords": ["vanta:10", "hey:5"],
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
        self._out_stream = None  # sounddevice RawOutputStream during streaming TTS
        self._paused = False           # hold/pause mode (FIX 4)
        self._pause_started = 0.0
        self._pause_reminded = False
        self._session_start = 0.0      # pattern tracking (4H)

    def _set_state(self, state: str) -> None:
        voice_bus.set_voice_state(state)
        self._status(state)
        print(f"[STATE] {state}", flush=True)

    # -- brain (thin HTTP layer over the text pipeline) --
    def think(self, text: str) -> str:
        tier = classify_complexity(text)
        model = self.simple_model if tier == "simple" else self.complex_model
        self._set_state("thinking")
        messages = [{"role": "system", "content": IVY_SYSTEM}, *self.conversation.context(),
                    {"role": "user", "content": text}]
        return call_brain(messages, model)

    # -- speak: live word-by-word transcript + TTS (with barge-in) --
    def speak(self, full_text: str, *, summary: bool = True) -> str:
        """Speak the reply. Returns the barge-in transcript if Bryan interrupted
        mid-sentence (Task 2), else "" — callers act on it via classify_interrupt."""
        spoken = summarise_for_speech(full_text) if summary else full_text
        self._last_reply = spoken
        self._set_state("speaking")
        # Push full reply to the transcript (word by word) for the cockpit.
        words = spoken.split()
        for i, w in enumerate(words):
            voice_bus.push_transcript("vanta", w, final=(i == len(words) - 1))
        # FIX 3 + Task 2: stream the audio with concurrent barge-in so Bryan can
        # interrupt mid-sentence. None => streaming unavailable -> mp3+afplay.
        interrupt = self._stream_and_play_ivy(spoken, self._speed)
        if interrupt is None:
            audio = synthesize_ivy(spoken, speed=self._speed)
            if audio:
                self._play(audio)
            interrupt = ""
        voice_bus.save_turn("vanta", spoken, mode="voice")
        return interrupt

    def _eleven_req(self, text: str, speed: float):
        """Build the ElevenLabs streaming request (key, url, headers, body, sr)."""
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "MClEFoImJXBTgLwdLI5n")
        model = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")
        sr = 24000
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?output_format=pcm_{sr}"
        headers = {"xi-api-key": api_key, "accept": "audio/pcm", "content-type": "application/json"}
        body = {"text": text, "model_id": model,
                "voice_settings": {"stability": 0.4, "similarity_boost": 0.8,
                                   "style": 0.6, "use_speaker_boost": True, "speed": speed}}
        return api_key, url, headers, body, sr

    def _stream_and_play_ivy(self, text: str, speed: float):  # -> Optional[str]
        """Play Ivy TTS with barge-in (Task 2). Returns the interrupt transcript
        (or "" if Ivy finished uninterrupted), or None if streaming is unavailable
        so the caller falls back to mp3."""
        api_key = self._eleven_req(text, speed)[0]
        if not api_key or not text.strip():
            return None
        try:
            return self._play_with_bargein(text, speed)
        except Exception as exc:
            print(f"[ERROR] barge-in playback failed ({exc}); sequential fallback", flush=True)
            try:
                return "" if self._stream_play_sequential(text, speed) else None
            except Exception:
                return None

    def _play_with_bargein(self, text: str, speed: float) -> str:  # pragma: no cover - audio/network/threads
        """Concurrent playback: a producer streams PCM into a queue; a playback
        thread writes to the speaker, checking interrupt_event every 50ms; a
        listener thread watches the mic during playback and, on a barge-in
        (RMS > BARGE_RMS), stops playback and captures+transcribes Bryan.
        Returns the interrupt transcript ("" if Ivy finished uninterrupted).
        If a second mic stream can't open, barge-in is skipped (playback continues)."""
        import queue as _queue
        import sounddevice as sd
        import httpx
        _api, url, headers, body, sr = self._eleven_req(text, speed)
        audio_q: "_queue.Queue" = _queue.Queue(maxsize=64)
        result_q: "_queue.Queue" = _queue.Queue()
        interrupt = threading.Event()
        block = int(SAMPLE_RATE * FRAME_MS / 1000)

        def producer():
            try:
                with httpx.Client(timeout=60) as c:
                    with c.stream("POST", url, headers=headers, json=body) as r:
                        r.raise_for_status()
                        first = True
                        for chunk in r.iter_bytes(4096):
                            if interrupt.is_set() or self._stop.is_set() or not chunk:
                                break
                            if first:
                                print("[ELEVENLABS] streaming started", flush=True); first = False
                            scaled = self._scaled(chunk)
                            while not interrupt.is_set() and not self._stop.is_set():
                                try:
                                    audio_q.put(scaled, timeout=0.1); break
                                except _queue.Full:
                                    continue
            except Exception as exc:
                print(f"[ERROR] TTS producer: {exc}", flush=True)
            finally:
                audio_q.put(None)  # sentinel: playback always terminates

        def playback(out):
            while not interrupt.is_set():
                try:
                    chunk = audio_q.get(timeout=0.05)
                except _queue.Empty:
                    continue
                if chunk is None:
                    break
                try:
                    out.write(chunk)
                except Exception:
                    break

        def listener():
            frames = bytearray(); recording = False; silent = 0
            try:
                with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=block, dtype="int16", channels=1) as mic:
                    while not interrupt.is_set():
                        data, _ = mic.read(block)
                        f = bytes(data); rms = rms_from_pcm16(f)
                        if rms > BARGE_RMS and not recording:
                            print(f"[BARGE-IN] detected (rms={int(rms)}) — stopping Ivy", flush=True)
                            recording = True; silent = 0
                        if recording:
                            frames += f
                            if rms < VAD_STOP_RMS:
                                silent += 1
                                if silent * (FRAME_MS / 1000.0) >= SILENCE_STOP:
                                    interrupt.set()
                                    result_q.put(self._transcribe(bytes(frames)))
                                    return
                            else:
                                silent = 0
            except Exception:
                return  # second mic stream unavailable -> no barge-in this turn

        out = sd.RawOutputStream(samplerate=sr, channels=1, dtype="int16")
        out.start(); self._out_stream = out
        threads = [threading.Thread(target=producer, daemon=True),
                   threading.Thread(target=playback, args=(out,), daemon=True),
                   threading.Thread(target=listener, daemon=True)]
        for t in threads:
            t.start()
        threads[1].join()        # wait for playback (finishes on sentinel or interrupt)
        interrupt.set()          # stop the listener if still running
        threads[2].join(timeout=1.0)
        try:
            out.stop(); out.close()
        except Exception:
            pass
        self._out_stream = None
        print("[ELEVENLABS] playback done", flush=True)
        try:
            return (result_q.get_nowait() or "").strip()
        except _queue.Empty:
            return ""

    def _stream_play_sequential(self, text: str, speed: float) -> bool:  # pragma: no cover - audio/network
        """Sequential streaming fallback (no barge-in)."""
        _api, url, headers, body, sr = self._eleven_req(text, speed)
        try:
            import httpx
            import sounddevice as sd
            out = sd.RawOutputStream(samplerate=sr, channels=1, dtype="int16")
            out.start(); self._out_stream = out
            played = False
            try:
                with httpx.Client(timeout=60) as c:
                    with c.stream("POST", url, headers=headers, json=body) as r:
                        r.raise_for_status()
                        for chunk in r.iter_bytes(4096):
                            if self._stop.is_set() or not chunk:
                                break
                            out.write(self._scaled(chunk)); played = True
            finally:
                try:
                    out.stop(); out.close()
                except Exception:
                    pass
                self._out_stream = None
            return played
        except Exception as exc:
            print(f"[ERROR] sequential streaming failed: {exc}", flush=True)
            self._out_stream = None
            return False

    def _scaled(self, pcm: bytes) -> bytes:
        """Apply volume to a raw int16 PCM chunk (no-op at volume 1.0)."""
        if self._volume == 1.0:
            return pcm
        try:
            import numpy as np
            a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * self._volume
            return np.clip(a, -32768, 32767).astype(np.int16).tobytes()
        except Exception:
            return pcm

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
        if self._out_stream is not None:
            try:
                self._out_stream.abort()
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
    def handle_user_text(self, text: str, _depth: int = 0) -> str:
        """Process one user utterance through the brain and speak the reply.

        Returns the full reply text (also pushed to the transcript). Records the
        turn in conversation history (last 20) and unified voice history.

        Task 2 barge-in: speak() returns Bryan's interrupt transcript if he talked
        over Ivy. We classify it — 'hard' (he said "stop") drops the rest and
        waits; 'soft'/'new' answer the interrupt with full 20-turn context (so the
        original request + reply are still available — nothing is lost). _depth
        bounds the recursion so a flurry of interrupts can't run away.
        """
        text = (text or "").strip()
        if not text:
            return ""
        self.conversation.add("user", text)
        voice_bus.save_turn("bryan", text, mode="voice")
        # Continuous proactive task capture (4F) — runs on EVERY turn, not on ask.
        try:
            from openjarvis.proactive.stores import TaskStore
            got = TaskStore().capture_from_text(text)
            if got:
                print(f"[TASKS] auto-captured {len(got)} implied task(s)", flush=True)
        except Exception:
            pass
        tier = classify_complexity(text)
        model = self.simple_model if tier == "simple" else self.complex_model
        print(f"[CLASSIFY] {tier} -> {model}: {text!r}", flush=True)
        if tier == "complex":
            self.speak("On it, give me a moment.", summary=False)
        reply = self.think(text)
        print(f"[BRAIN] reply: {reply[:120]!r}", flush=True)
        if not reply:
            self._set_state("listening")
            return ""  # silent on error — never speak error messages
        self.conversation.add("assistant", reply)
        interrupt = self.speak(reply, summary=True)
        if interrupt and _depth < 3:
            kind = classify_interrupt(interrupt)
            print(f"[BARGE-IN] {kind}: {interrupt!r}", flush=True)
            voice_bus.push_transcript("bryan", interrupt, final=True)
            if kind == "hard":
                # "stop" — drop the rest of the reply, return to listening.
                self._stop_playback()
            else:
                # soft ("hold on", "actually...") or a fresh request — answer it.
                # The 20-turn history still holds the original turn, so context is intact.
                return self.handle_user_text(interrupt, _depth=_depth + 1)
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
        print("[VANTA voice] WAKE DETECTED — greeting + entering conversation", flush=True)
        self._session_start = time.time()   # pattern tracking (4H)
        self._set_state("wake_detected")
        greeting = get_wake_response(last_wake_ts=self._last_wake_ts)
        self._last_wake_ts = time.time()
        self.conversation.reset()
        voice_bus.set_voice_active(True)
        self.speak(greeting, summary=False)
        self._set_state("listening")

    def _record_session(self) -> None:
        """Log this voice session's hour + length for behaviour patterns (4H)."""
        if not self._session_start:
            return
        try:
            from openjarvis.proactive.stores import PatternStore
            dur = max(0.0, time.time() - self._session_start)
            PatternStore().record_session(hour=time.localtime().tm_hour, duration_s=dur)
            print(f"[PATTERN] session logged ({int(dur)}s)", flush=True)
        except Exception:
            pass
        self._session_start = 0.0

    def _transcribe(self, audio: bytes) -> str:  # pragma: no cover - needs Deepgram
        """Transcribe captured int16 PCM via Deepgram v3.7.0 (nova-2, en, linear16)."""
        if not audio or self._stt is None:
            return ""
        try:
            from deepgram import PrerecordedOptions
            options = PrerecordedOptions(
                model="nova-2",
                detect_language=True,     # auto-detect (handles Singapore accent better than en)
                sample_rate=SAMPLE_RATE,  # 16000
                channels=1,
                encoding="linear16",      # raw int16 PCM (no WAV wrapper needed)
                smart_format=True,
                keywords=["vanta:10", "hey:5"],
            )
            res = self._stt.listen.rest.v("1").transcribe_file({"buffer": audio}, options)
            text = (res.results.channels[0].alternatives[0].transcript or "").strip()
            print(f"[DEEPGRAM] transcript: {text!r}", flush=True)
            return text
        except Exception as exc:
            print(f"[ERROR] Deepgram transcribe failed: {exc}", flush=True)
            return ""

    def _handle_turn(self, text: str) -> str:  # pragma: no cover - audio runtime
        """Process one in-conversation utterance. Returns 'end' to leave
        conversation mode, 'hold' to enter pause, else 'continue'. Every branch
        is guarded so a single bad turn never crashes the loop (FIX 5/7)."""
        try:
            if is_end_phrase(text):
                print("[STATE] end-phrase -> Standing by", flush=True)
                self.speak("Standing by.", summary=False)
                return "end"
            kind = detect_interrupt(text)
            if kind == "hard":               # "stop" -> drop, wait for next command
                print("[STATE] hard-interrupt (stop) -> drop + listen", flush=True)
                self._stop_playback()
                return "continue"
            if kind == "hold":               # pause indefinitely
                print("[STATE] hold -> paused", flush=True)
                self._stop_playback()
                self._paused = True
                self._pause_started = time.time()
                self._pause_reminded = False
                self.speak("Take your time.", summary=False)
                return "hold"
            ctrl = voice_control(text)
            if ctrl:
                print(f"[STATE] voice-control: {ctrl}", flush=True)
                self.apply_control(ctrl)
                return "continue"
            # Soft interrupt ("actually…", "before you continue") and normal turns
            # both go to the brain — the last-20-turns context means the original
            # request AND the addition are answered together (nothing dropped).
            self.handle_user_text(text)
            return "continue"
        except Exception as exc:
            print(f"[ERROR] turn handling failed: {exc}", flush=True)
            return "continue"

    def run(self) -> None:  # pragma: no cover - needs mic/speaker + Deepgram
        """Bulletproof always-on state machine (FIX 7): WAKE -> WAKE_DETECTED ->
        LISTENING -> RECORDING -> THINKING -> SPEAKING -> LISTENING, with a
        hold/pause sub-state. ANY error prints [ERROR] and returns to WAKE; the
        outer loop reopens the mic so the loop never crashes and exits."""
        try:
            import sounddevice as sd
        except Exception as exc:
            print(f"[ERROR] voice_loop needs sounddevice: {exc}", flush=True)
            return
        self._stt = make_deepgram()
        print("[VANTA voice] voice loop starting (opening mic)…", flush=True)
        block = int(SAMPLE_RATE * FRAME_MS / 1000)

        while not self._stop.is_set():
            in_conversation = False
            self._paused = False
            utter = bytearray()
            vad = VadState()
            last_activity = time.time()
            _hb = 0
            try:
                with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=block, dtype="int16", channels=1) as stream:
                    # Mic open -> genuinely listening (report active only now, so a
                    # denied permission leaves the UI honestly OFF).
                    self._set_state("listening")
                    voice_bus.set_voice_active(True)
                    print("[VANTA voice] LISTENING — say 'Hey VANTA' or double-clap", flush=True)
                    while not self._stop.is_set():
                        try:
                            data, _ = stream.read(block)
                        except Exception as exc:
                            print(f"[ERROR] mic read failed: {exc}", flush=True)
                            break  # reopen the stream
                        frame = bytes(data)
                        rms = rms_from_pcm16(frame)
                        now = time.time()
                        _hb += 1
                        if _hb % 16 == 0 or rms >= WAKE_RMS:
                            mode = "paused" if self._paused else ("conv" if in_conversation else "wake")
                            print(f"[RMS] {int(rms):5d}  mode={mode}", flush=True)

                        # ── WAKE mode ──
                        if not in_conversation:
                            if self.clap.feed(rms, now):
                                print(f"[STATE] WAKE — double-clap (rms={int(rms)})", flush=True)
                                self._handle_wake()
                                in_conversation = True
                                utter.clear(); vad = VadState(); last_activity = now
                                continue
                            ev = vad.feed(rms, now)
                            if ev in ("start", "recording"):
                                utter += frame
                            elif ev == "stop":
                                text = self._transcribe(bytes(utter)); utter.clear()
                                if self.process_final_transcript(text):
                                    in_conversation = True; vad = VadState(); last_activity = now
                            continue

                        # ── HOLD/PAUSE sub-state (FIX 4) ──
                        if self._paused:
                            ev = vad.feed(rms, now)
                            if ev in ("start", "recording"):
                                utter += frame
                            elif ev == "stop":
                                text = self._transcribe(bytes(utter)); utter.clear()
                                if text and is_resume(text):
                                    print("[STATE] resume from hold -> LISTENING", flush=True)
                                    self._paused = False; self._pause_reminded = False
                                    self._set_state("listening"); last_activity = time.time()
                            elif ev == "idle":
                                if (now - self._pause_started >= HOLD_REMINDER) and not self._pause_reminded:
                                    self._pause_reminded = True
                                    self.speak("Still here when you're ready.", summary=False)
                                    self._set_state("listening")
                            continue

                        # ── conversation mode (no wake word needed, FIX 3) ──
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
                                result = self._handle_turn(text)
                                if result == "end":
                                    self._record_session()
                                    in_conversation = False; vad = VadState()
                                    self._set_state("listening")
                                    continue
                                last_activity = time.time()
                            self._set_state("listening")
                        elif ev == "idle":
                            if now - last_activity >= END_SILENCE:
                                print("[STATE] 10s silence -> Standing by", flush=True)
                                self.speak("Standing by.", summary=False)
                                self._record_session()
                                in_conversation = False; vad = VadState()
                                self._set_state("listening")
            except Exception as exc:
                # ANY failure: log it, drop to WAKE, keep running (reopen mic).
                print(f"[ERROR] voice loop error -> returning to WAKE: {exc}", flush=True)
                self._set_state("standby")
                if self._stop.wait(1.0):
                    break

    def stop(self) -> None:
        self._stop.set()
        self._stop_playback()


def main() -> None:  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    VoiceLoop().run()


if __name__ == "__main__":  # pragma: no cover
    main()
