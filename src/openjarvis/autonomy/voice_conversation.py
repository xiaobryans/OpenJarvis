"""Jarvis Voice Conversation Loop — full back-and-forth voice conversation.

Flow per turn:
  wake-word detected → record command audio → STT → route to Jarvis
  → TTS speaks response → return to wake-word listening

Architecture (no duplicates):
  - Wake-word: WakeWordBridge (isolated .wake_worker_venv subprocess)
  - Recording: sounddevice (main venv, separate stream from worker)
  - STT: existing speech backends via get_stt_status() + STT backend classes
  - Jarvis query: existing engine + security via get_engine() + setup_security()
  - TTS: existing TTS path (macOS say / OpenAI TTS)
  - Safety: setup_security() always called — no approval gates bypassed

"Always-on" means wake-word detection only. Audio is only recorded and
transcribed AFTER the wake word fires, not continuously.
"""

from __future__ import annotations

import io
import logging
import os
import subprocess
import threading
import wave
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


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
    """Full Jarvis voice conversation loop.

    Always-on means: wake-word detection is always-on.
    Audio is only recorded AFTER a wake-word fires, not continuously.

    States:
      idle       — loop not started
      listening  — waiting for wake-word (normal always-on state)
      recording  — microphone recording after wake-word fired
      transcribing — STT running on recorded audio
      processing — routing text through Jarvis engine
      speaking   — TTS playing response
    """

    def __init__(
        self,
        record_seconds: float = 5.0,
        language: str = "en",
        auto_restart: bool = False,
        debug: bool = False,
        on_state_change: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._record_seconds = record_seconds
        self._language = language
        self._auto_restart = auto_restart
        self._debug = debug
        self._on_state_change = on_state_change

        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        self._bridge = WakeWordBridge()

        self._state = "idle"
        self._lock = threading.Lock()
        self._turns = 0

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _set_state(self, state: str) -> None:
        with self._lock:
            self._state = state
        if self._on_state_change:
            try:
                self._on_state_change(state)
            except Exception as exc:
                logger.debug("on_state_change raised: %s", exc)

    def _on_wake(self, event: Any) -> None:
        """Wake-word callback — transitions from listening to recording.

        Ignores the event if a turn is already being processed, preventing
        double-triggers during STT / engine / TTS.
        """
        with self._lock:
            if self._state != "listening":
                logger.debug(
                    "Wake-word ignored (state=%s — already processing)", self._state
                )
                return
            self._state = "recording"

        model = getattr(event, "model", "unknown")
        score = getattr(event, "score", 0.0)
        logger.info("Wake word fired: model=%s score=%.3f — starting command recording", model, score)
        threading.Thread(target=self._process_turn, daemon=True, name="jarvis-voice-turn").start()

    def _process_turn(self) -> None:
        """One conversation turn: record → STT → Jarvis → TTS → back to listening."""
        try:
            # 1. Record command audio
            self._set_state("recording")
            audio = record_command_audio(
                duration_seconds=self._record_seconds,
                sample_rate=16000,
            )

            # 2. STT — uses existing speech backend path
            self._set_state("transcribing")
            try:
                text = transcribe_command(audio, language=self._language)
            except Exception as exc:
                logger.error("STT failed: %s", exc)
                return
            if not text.strip():
                logger.info("Empty STT transcript — skipping turn")
                return
            logger.info("Command: %r", text)

            # 3. Route through normal Jarvis path (with security)
            self._set_state("processing")
            try:
                response = query_jarvis_text(text)
            except Exception as exc:
                logger.error("Jarvis query failed: %s", exc)
                response = "I encountered an error processing your request."

            if not response.strip():
                logger.warning("Empty response from Jarvis")
                return
            logger.info("Response: %r", response[:120])

            # 4. TTS — uses existing TTS path
            self._set_state("speaking")
            try:
                speak_response(response)
            except Exception as exc:
                logger.error("TTS failed: %s", exc)

            with self._lock:
                self._turns += 1

        except Exception as exc:
            logger.error("Voice turn error: %s", exc)
        finally:
            # Always return to listening after each turn
            self._set_state("listening")

    # ------------------------------------------------------------------ #
    # Public interface                                                       #
    # ------------------------------------------------------------------ #

    def start(
        self,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """Start the wake-word bridge and register the conversation callback.

        Returns the bridge start result dict (ok, worker_pid, socket, ...).
        """
        self._bridge.register_callback(self._on_wake)
        result = self._bridge.start(auto_restart=self._auto_restart, debug=debug or self._debug)
        if result.get("ok"):
            self._set_state("listening")
        return result

    def stop(self) -> None:
        """Stop the wake-word bridge and conversation loop."""
        self._bridge.stop()
        self._set_state("idle")

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
            "bridge": self._bridge.status(),
        }


__all__ = [
    "VoiceConversationLoop",
    "record_command_audio",
    "transcribe_command",
    "query_jarvis_text",
    "speak_response",
]
