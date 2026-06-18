"""Jarvis Voice Conversation Loop — full assistant-grade voice conversation.

Flow per session:
  wake-word detected
    → immediate time-based greeting (TTS)
    → active conversation session:
        record command → STT → check stop phrase → route to Jarvis → TTS
        → follow-up listening (no wake-word needed for next turn)
        → repeat until timeout or stop phrase
    → return to wake-word-only listening

Architecture (no duplicates):
  - Wake-word: WakeWordBridge (isolated .wake_worker_venv subprocess)
  - Recording: sounddevice (main venv, separate stream from worker)
  - STT: existing speech backends via get_stt_status() + STT backend classes
  - Jarvis query: existing engine + security via get_engine() + setup_security()
  - TTS: existing TTS path (macOS say / OpenAI TTS)
  - Safety: setup_security() always called — no approval gates bypassed
  - Events: SSE-ready event queue for UI state/transcript/latency streaming

"Always-on" means wake-word detection only.  Audio is only recorded
and transcribed AFTER the wake-word fires or during the active
conversation session — never continuously.

Platform support:
  macOS (founder platform): SUPPORTED
    - Wake-word: .wake_worker_venv / openwakeword
    - TTS: macOS built-in 'say' command
  Windows/Linux: NOT_PROVEN — require equivalent wake-word + TTS setup.
"""

from __future__ import annotations

import collections
import io
import logging
import os
import queue
import subprocess
import threading
import time
import wave
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stop phrases — end the active session and return to wake-word-only listening
# ---------------------------------------------------------------------------

STOP_PHRASES: List[str] = [
    "stop listening",
    "stop",
    "cancel",
    "that's all",
    "thats all",
    "go back to sleep",
    "go to sleep",
    "goodbye",
    "goodbye jarvis",
    "sleep",
    "exit",
    "quit",
]


# ---------------------------------------------------------------------------
# Time-of-day greeting
# ---------------------------------------------------------------------------


def time_of_day_greeting(name: str = "Bryan") -> str:
    """Return a time-appropriate greeting for the user.

    Uses local wall-clock time so Bryan hears the correct greeting
    regardless of server timezone.
    """
    hour = time.localtime().tm_hour
    if 5 <= hour < 12:
        period = "morning"
    elif 12 <= hour < 17:
        period = "afternoon"
    elif 17 <= hour < 21:
        period = "evening"
    else:
        period = "night"

    greetings = {
        "morning": f"Good morning {name}, what do you need?",
        "afternoon": f"Good afternoon {name}, what are you looking to do?",
        "evening": f"Good evening {name}, how can I help?",
        "night": f"Hi {name}, I'm here. What do you need?",
    }
    return greetings[period]


# ---------------------------------------------------------------------------
# Audio recording
# ---------------------------------------------------------------------------


def record_command_audio(
    duration_seconds: float = 5.0,
    sample_rate: int = 16000,
) -> bytes:
    """Record ``duration_seconds`` of microphone audio and return WAV bytes.

    Uses sounddevice (main-venv dependency). Blocks until recording is done.
    Returns raw WAV bytes suitable for the STT backends.
    """
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise ImportError(
            f"sounddevice/numpy not available in main venv: {exc}. "
            "Both are listed in pyproject.toml dependencies."
        ) from exc

    frames = int(duration_seconds * sample_rate)
    logger.debug("Recording %.1fs of audio (%d frames @ %dHz)", duration_seconds, frames, sample_rate)

    recording = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 bytes per sample
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())

    audio_bytes = buf.getvalue()
    logger.debug("Recorded %d bytes (%.1f kB)", len(audio_bytes), len(audio_bytes) / 1024)
    return audio_bytes


# ---------------------------------------------------------------------------
# STT — uses existing speech backends via voice_pipeline status check
# ---------------------------------------------------------------------------


def transcribe_command(audio_bytes: bytes, language: str = "en") -> str:
    """Transcribe WAV audio bytes using the configured STT backend.

    Reuses the existing STT path (get_stt_status → faster_whisper /
    openai_whisper / deepgram). Does NOT introduce a new STT system.
    Language defaults to 'en' to prevent Malay/Indonesian misdetection
    on short clips (same fix as the packaged-app STT path in api_routes.py).
    """
    from openjarvis.autonomy.voice_pipeline import STTEngine, get_stt_status

    stt = get_stt_status()
    engine = stt.get("stt_status", STTEngine.NOT_CONFIGURED)

    logger.debug("Transcribing via STT engine=%s language=%s bytes=%d", engine, language, len(audio_bytes))

    if engine == STTEngine.FASTER_WHISPER:
        from openjarvis.speech.faster_whisper import FasterWhisperBackend
        backend = FasterWhisperBackend()
        result = backend.transcribe(audio_bytes, format="wav", language=language)
        text = result.text.strip()
        logger.info("STT transcript: %r", text)
        return text

    if engine == STTEngine.OPENAI_WHISPER:
        from openjarvis.speech.openai_whisper import OpenAIWhisperBackend
        backend = OpenAIWhisperBackend()
        result = backend.transcribe(audio_bytes, format="wav", language=language)
        text = result.text.strip()
        logger.info("STT transcript: %r", text)
        return text

    if engine == STTEngine.DEEPGRAM:
        from openjarvis.speech.deepgram import DeepgramBackend
        backend = DeepgramBackend()
        result = backend.transcribe(audio_bytes, format="wav", language=language)
        text = result.text.strip()
        logger.info("STT transcript: %r", text)
        return text

    raise RuntimeError(
        f"STT not configured (status={engine!r}). "
        "Install faster-whisper or set OPENAI_API_KEY / DEEPGRAM_API_KEY."
    )


# ---------------------------------------------------------------------------
# Jarvis query — uses existing engine + security infrastructure
# ---------------------------------------------------------------------------


def query_jarvis_text(text: str) -> str:
    """Route ``text`` through the normal Jarvis chat/model/action path.

    Reuses: load_config(), get_engine(), setup_security(), engine.generate()
    and the configured default_agent if set.  Does NOT create a duplicate
    planner, memory system, or agent loop.

    Safety: setup_security() is called unconditionally so all approval gates
    and capability policies remain active.
    """
    try:
        from openjarvis.core.config import load_config
        from openjarvis.core.events import EventBus
        from openjarvis.core.types import Message, Role
        from openjarvis.engine import discover_engines, discover_models, get_engine
        from openjarvis.security import setup_security
    except ImportError as exc:
        logger.error("Required module not available: %s", exc)
        return f"Error: required module not available ({exc})"

    config = load_config()
    bus = EventBus(record_history=False)

    resolved = get_engine(config, None)
    if resolved is None:
        return (
            "No inference engine available. "
            "Start Ollama or set OPENAI_API_KEY / ANTHROPIC_API_KEY."
        )

    engine_name, engine = resolved

    # Security — MUST run before any inference; preserves all approval gates
    sec = setup_security(config, engine, bus)
    engine = sec.engine

    # Resolve model
    model_name = getattr(config.intelligence, "default_model", None)
    if not model_name:
        try:
            all_engines = discover_engines(config)
            all_models = discover_models(all_engines)
            models = all_models.get(engine_name, [])
            if models:
                model_name = models[0]
        except Exception as _disc_exc:
            logger.debug("Model discovery failed: %s", _disc_exc)
    if not model_name:
        model_name = getattr(config.intelligence, "fallback_model", None)

    temperature = getattr(config.intelligence, "temperature", 0.7)
    max_tokens = getattr(config.intelligence, "max_tokens", 512)

    # If a default agent is configured, use it (preserves agent tools/routing)
    agent_name = (getattr(config.agent, "default_agent", None) or "").strip()
    if agent_name:
        try:
            from openjarvis.cli._tool_names import resolve_tool_names
            from openjarvis.cli.ask import _run_agent

            tool_names = resolve_tool_names(
                None,
                getattr(config.tools, "enabled", None),
                getattr(config.agent, "tools", None),
            )
            result = _run_agent(
                agent_name, text, engine, model_name,
                tool_names, config, bus, temperature, max_tokens,
                capability_policy=sec.capability_policy,
            )
            return result.content
        except Exception as exc:
            logger.warning(
                "Agent %r failed (%s) — falling back to direct engine mode",
                agent_name, exc,
            )

    # Direct engine mode
    messages = [Message(role=Role.USER, content=text)]
    try:
        result = engine.generate(
            messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return result.get("content", "")
    except Exception as exc:
        logger.error("engine.generate failed: %s", exc)
        return f"I encountered an error processing your request: {exc}"


# ---------------------------------------------------------------------------
# TTS — uses existing TTS path from voice_pipeline
# ---------------------------------------------------------------------------


def speak_response(text: str) -> None:
    """Speak ``text`` using the configured TTS engine.

    Reuses the existing TTS path (get_tts_status → macOS say / OpenAI TTS).
    Runs synchronously so the loop waits for speech to finish before
    returning to wake-word listening.
    """
    from openjarvis.autonomy.voice_pipeline import TTSEngine, get_tts_status

    tts = get_tts_status()
    engine = tts.get("tts_status", TTSEngine.NOT_CONFIGURED)

    logger.debug("TTS speak: engine=%s text=%r", engine, text[:80])

    if engine == TTSEngine.MACOS_SAY:
        try:
            subprocess.run(["say", text], check=False, timeout=60)
        except Exception as exc:
            logger.warning("macOS say failed: %s", exc)
        return

    if engine == TTSEngine.OPENAI_TTS:
        try:
            import tempfile
            import os as _os
            from openai import OpenAI
            api_key = _os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                logger.warning("OpenAI TTS: OPENAI_API_KEY not set — skipping")
                return
            client = OpenAI(api_key=api_key)
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="alloy",
                input=text,
            ) as response:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_path = tmp.name
                    for chunk in response.iter_bytes(chunk_size=4096):
                        tmp.write(chunk)
            subprocess.run(["afplay", tmp_path], check=False, timeout=60)
            _os.unlink(tmp_path)
        except Exception as exc:
            logger.warning("OpenAI TTS failed: %s", exc)
        return

    logger.warning("TTS not configured (status=%r) — response not spoken", engine)


# ---------------------------------------------------------------------------
# Voice Conversation Loop
# ---------------------------------------------------------------------------


class VoiceConversationLoop:
    """Full Jarvis voice conversation loop with session mode.

    Privacy model (always-on = wake-word only):
      WAKE_LISTENING    — waiting for "hey jarvis" (mic open for wake-word only)
      WAKE_DETECTED     — wake-word just fired
      ACKNOWLEDGING     — speaking time-based greeting (TTS)
      ACTIVE_CONVERSATION — session open; follow-up turns need no wake-word
      RECORDING         — microphone recording the user's command
      TRANSCRIBING      — STT running on recorded audio
      THINKING          — routing text through Jarvis engine
      SPEAKING          — TTS playing response
      FOLLOW_UP_LISTENING — brief pause between session turns
      IDLE              — loop not started / stopped
    """

    def __init__(
        self,
        record_seconds: float = 5.0,
        language: str = "en",
        auto_restart: bool = False,
        debug: bool = False,
        on_state_change: Optional[Callable[[str], None]] = None,
        session_timeout: float = 30.0,
        stop_phrases: Optional[List[str]] = None,
        user_name: str = "Bryan",
    ) -> None:
        self._record_seconds = record_seconds
        self._language = language
        self._auto_restart = auto_restart
        self._debug = debug
        self._on_state_change = on_state_change
        self._session_timeout = session_timeout
        self._stop_phrases = {p.lower() for p in (stop_phrases or STOP_PHRASES)}
        self._user_name = user_name

        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        self._bridge = WakeWordBridge()

        self._state = "idle"
        self._lock = threading.Lock()
        self._turns = 0

        # Event queue — SSE consumers subscribe to this
        self._event_subscribers: List[queue.Queue] = []
        self._events_history: collections.deque = collections.deque(maxlen=200)

    # ------------------------------------------------------------------ #
    # Event bus (SSE-ready)                                                 #
    # ------------------------------------------------------------------ #

    def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit a structured event to all subscribers and history."""
        event.setdefault("ts", time.time())
        self._events_history.append(event)
        with self._lock:
            subs = list(self._event_subscribers)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass

    def _emit_latency(self, stage: str, value_ms: float) -> None:
        self._emit_event({"type": "latency", "stage": stage, "value_ms": round(value_ms, 1)})

    def subscribe_events(self) -> queue.Queue:
        """Subscribe to the event stream. Returns a queue; consume until None sentinel."""
        q: queue.Queue = queue.Queue(maxsize=512)
        with self._lock:
            self._event_subscribers.append(q)
        return q

    def unsubscribe_events(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._event_subscribers.remove(q)
            except ValueError:
                pass

    def get_events_history(self) -> List[Dict[str, Any]]:
        return list(self._events_history)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _set_state(self, state: str) -> None:
        with self._lock:
            self._state = state
        self._emit_event({"type": "state", "state": state})
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception as exc:
                logger.debug("on_state_change raised: %s", exc)

    def _is_stop_phrase(self, text: str) -> bool:
        """Return True if the transcript exactly matches a session-stop phrase."""
        t = text.lower().strip().rstrip(".,!?")
        return t in self._stop_phrases

    def _on_wake(self, event: Any) -> None:
        """Wake-word callback — transitions from wake_listening to recording.

        Ignores the event if a session is already in progress (double-trigger
        prevention during STT / engine / TTS processing).
        """
        with self._lock:
            if self._state not in ("listening", "wake_listening"):
                logger.debug(
                    "Wake-word ignored (state=%s — already processing)", self._state
                )
                return
            self._state = "recording"

        model = getattr(event, "model", "unknown")
        score = getattr(event, "score", 0.0)
        logger.info("Wake word fired: model=%s score=%.3f", model, score)
        self._emit_event({
            "type": "state",
            "state": "wake_detected",
            "model": str(model),
            "score": float(score),
        })
        threading.Thread(
            target=self._process_turn,
            daemon=True,
            name="jarvis-voice-turn",
        ).start()

    def _process_turn(self) -> None:
        """Full conversation session: greeting → [record→STT→Jarvis→TTS] loop.

        A single call handles the entire session (greeting + all follow-up turns
        until timeout or stop phrase).  This method is called in a daemon thread.
        Always returns to state='listening' in the finally block.
        """
        try:
            # ---------------------------------------------------------- #
            # 1. Immediate acknowledgement (TTS greeting before recording) #
            # ---------------------------------------------------------- #
            _wake_ts = time.time()
            self._set_state("acknowledging")
            try:
                greet = time_of_day_greeting(self._user_name)
                speak_response(greet)
                logger.info("Acknowledged: %r", greet)
            except Exception as exc:
                logger.debug("Acknowledgement TTS failed (non-fatal): %s", exc)
            _ack_done_ts = time.time()
            self._emit_latency("wake_to_ack_ms", (_ack_done_ts - _wake_ts) * 1000)

            # ---------------------------------------------------------- #
            # 2. Active conversation session loop                          #
            # ---------------------------------------------------------- #
            self._set_state("active_conversation")
            session_deadline = time.time() + self._session_timeout
            first_turn = True

            while True:
                if not first_turn:
                    # Follow-up turn — no wake-word needed
                    self._set_state("follow_up_listening")
                    if time.time() > session_deadline:
                        logger.info("Session timeout — returning to wake listening")
                        break
                    # Brief pause to give user a moment to start speaking
                    time.sleep(0.4)
                first_turn = False

                # ------------------------------------------------------ #
                # 3. Record command audio                                   #
                # ------------------------------------------------------ #
                _rec_start = time.time()
                self._set_state("recording")
                self._emit_event({
                    "type": "interim_transcript",
                    "text": f"Recording... ({self._record_seconds:.0f}s)",
                })
                try:
                    audio = record_command_audio(
                        duration_seconds=self._record_seconds,
                        sample_rate=16000,
                    )
                except Exception as exc:
                    logger.error("Recording failed: %s", exc)
                    break
                _rec_end = time.time()
                self._emit_latency("wake_to_record_start_ms", (_rec_start - _wake_ts) * 1000)

                # ------------------------------------------------------ #
                # 4. STT — existing speech backend path                    #
                # ------------------------------------------------------ #
                _stt_start = time.time()
                self._set_state("transcribing")
                self._emit_event({"type": "interim_transcript", "text": "Transcribing..."})
                try:
                    text = transcribe_command(audio, language=self._language)
                except Exception as exc:
                    logger.error("STT failed: %s", exc)
                    break
                _stt_end = time.time()
                self._emit_latency("stt_duration_ms", (_stt_end - _stt_start) * 1000)
                self._emit_latency("speech_end_to_stt_final_ms", (_stt_end - _rec_end) * 1000)

                if not text.strip():
                    logger.info("Empty transcript — ending session")
                    break

                logger.info("Transcript: %r", text)
                self._emit_event({"type": "transcript", "text": text})

                # ------------------------------------------------------ #
                # 5. Stop-phrase check                                     #
                # ------------------------------------------------------ #
                if self._is_stop_phrase(text):
                    logger.info("Stop phrase detected: %r", text)
                    try:
                        speak_response("Going back to sleep. Say 'hey jarvis' when you need me.")
                    except Exception:
                        pass
                    self._emit_event({"type": "state", "state": "session_ended", "reason": "stop_phrase"})
                    break

                # ------------------------------------------------------ #
                # 6. Route through normal Jarvis path (with security)      #
                # ------------------------------------------------------ #
                _model_start = time.time()
                self._set_state("thinking")
                try:
                    response = query_jarvis_text(text)
                except Exception as exc:
                    logger.error("Jarvis query failed: %s", exc)
                    response = "I encountered an error processing your request."
                _model_end = time.time()
                self._emit_latency("model_duration_ms", (_model_end - _model_start) * 1000)

                if not response.strip():
                    response = "I don't have a response for that."
                logger.info("Response: %r", response[:120])
                self._emit_event({"type": "response", "text": response})

                # ------------------------------------------------------ #
                # 7. TTS — existing TTS path                               #
                # ------------------------------------------------------ #
                _tts_start = time.time()
                self._set_state("speaking")
                try:
                    speak_response(response)
                except Exception as exc:
                    logger.error("TTS failed: %s", exc)
                _tts_end = time.time()
                self._emit_latency("tts_start_ms", (_tts_start - _model_end) * 1000)
                self._emit_latency("total_turn_ms", (_tts_end - _wake_ts) * 1000)

                with self._lock:
                    self._turns += 1

                # Reset session deadline after each successful response
                session_deadline = time.time() + self._session_timeout

        except Exception as exc:
            logger.error("Voice session error: %s", exc)
            self._emit_event({"type": "error", "message": str(exc)})
        finally:
            # Always return to wake-word-only listening after session ends
            self._set_state("listening")

    # ------------------------------------------------------------------ #
    # Public interface                                                       #
    # ------------------------------------------------------------------ #

    def start(self, debug: bool = False) -> Dict[str, Any]:
        """Start wake-word bridge and register the conversation callback."""
        self._bridge.register_callback(self._on_wake)
        result = self._bridge.start(auto_restart=self._auto_restart, debug=debug or self._debug)
        if result.get("ok"):
            self._set_state("listening")
        return result

    def stop(self) -> None:
        """Stop the wake-word bridge and conversation loop."""
        self._bridge.stop()
        self._set_state("idle")
        # Sentinel to unblock SSE consumers
        self._emit_event({"type": "stopped"})

    def status(self) -> Dict[str, Any]:
        """Return loop state + bridge status."""
        with self._lock:
            state = self._state
            turns = self._turns
        return {
            "loop_state": state,
            "turns_completed": turns,
            "record_seconds": self._record_seconds,
            "language": self._language,
            "session_timeout": self._session_timeout,
            "bridge": self._bridge.status(),
        }


__all__ = [
    "VoiceConversationLoop",
    "STOP_PHRASES",
    "time_of_day_greeting",
    "record_command_audio",
    "transcribe_command",
    "query_jarvis_text",
    "speak_response",
]
