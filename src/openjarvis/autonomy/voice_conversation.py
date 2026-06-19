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
import re
import subprocess
import threading
import time
import wave
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Fast cloud models already supported by OpenJarvis, ordered by preferred
# voice latency.  The packaged app injects configured cloud keys into the
# backend process, so ``get_engine(..., "cloud", model=...)`` remains the
# single source of truth for whether each path is actually available.
_VOICE_FAST_MODELS = (
    ("gpt-4o-mini", "openai"),
    ("claude-haiku-4-5", "anthropic"),
    ("gemini-2.5-flash", "google"),
    ("openrouter/auto", "openrouter"),
)

# ---------------------------------------------------------------------------
# Stop phrases — end the active session and return to wake-word-only listening
# ---------------------------------------------------------------------------

STOP_PHRASES: List[str] = [
    "stop listening",
    "stop",
    "cancel",
    "never mind",
    "nevermind",
    "pause",
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


def _env_float(key: str, default: float) -> float:
    """Read a float from env with a safe fallback."""
    try:
        return float(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Voice recording config — read from env; code-level defaults are safe values.
# Override in .env:
#   JARVIS_VOICE_MIN_RECORD_SECONDS  — don't endpoint before this (default 1.0)
#   JARVIS_VOICE_SILENCE_STOP_MS     — consecutive silence to end turn (default 4000)
#   JARVIS_VOICE_MAX_RECORD_SECONDS  — emergency cap, NOT the normal end (default 120)
#   JARVIS_VOICE_SILENCE_RMS         — RMS below this level = silence (default 150)
# ---------------------------------------------------------------------------

_DEFAULT_MIN_RECORD_SECONDS: float = 1.0
_DEFAULT_SILENCE_STOP_MS: float = 4000.0
_DEFAULT_MAX_RECORD_SECONDS: float = 120.0
# Raised from 150 → 300: typical laptop fan/HVAC ambient is 100-250 RMS (int16).
# A threshold of 300 ensures ambient noise is always classified as silence while
# still comfortably detecting normal conversational speech (800-3000 RMS).
# Override via JARVIS_VOICE_SILENCE_RMS if your environment differs.
_DEFAULT_SILENCE_RMS: float = 300.0

_VAD_CHUNK_MS: int = 100  # analyse audio in 100 ms windows

# Adaptive noise-floor calibration — first N chunks are used to measure
# ambient noise before applying the speech/silence threshold.
_NOISE_CALIB_CHUNKS: int = 5          # 500 ms calibration window
_NOISE_CALIB_MULTIPLIER: float = 2.5  # effective_threshold ≥ noise_floor × this


def record_command_audio(
    duration_seconds: float = 5.0,
    sample_rate: int = 16000,
) -> bytes:
    """Fixed-duration recording — kept for backward compat / tests.

    Prefer ``record_command_audio_vad`` for interactive use — it ends on
    silence and does not impose a hard cap below ``max_seconds``.
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
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())

    audio_bytes = buf.getvalue()
    logger.debug("Recorded %d bytes (%.1f kB)", len(audio_bytes), len(audio_bytes) / 1024)
    return audio_bytes


def record_command_audio_vad(
    min_seconds: float = _DEFAULT_MIN_RECORD_SECONDS,
    silence_stop_ms: float = _DEFAULT_SILENCE_STOP_MS,
    max_seconds: float = _DEFAULT_MAX_RECORD_SECONDS,
    sample_rate: int = 16000,
    silence_rms_threshold: float = _DEFAULT_SILENCE_RMS,
    on_state: Optional[Callable[[str], None]] = None,
    abort_event: Optional[threading.Event] = None,
    on_calibrated: Optional[Callable[[float, float], None]] = None,
) -> Tuple[bytes, str]:
    """Record with adaptive VAD-based silence endpointing.

    The first ``_NOISE_CALIB_CHUNKS`` × 100 ms are used to measure the
    ambient noise floor.  The effective silence threshold is then set to
    ``max(silence_rms_threshold, noise_floor × _NOISE_CALIB_MULTIPLIER)``.
    This prevents fixed-threshold failures when real-world ambient noise
    (fans, HVAC, keyboard) exceeds the static default of 150 RMS.

    Normal turn-ending condition: ``silence_stop_ms`` of consecutive audio
    below the *effective* threshold after at least ``min_seconds`` elapsed.

    Emergency cap: ``max_seconds`` (default 120 s). This fires only if the
    user keeps talking without any silence gap — it is NOT the normal end.

    Parameters
    ----------
    min_seconds:
        Minimum recording duration before silence-based ending is considered.
        Prevents premature cutoff on brief ambient noise at session start.
    silence_stop_ms:
        Consecutive milliseconds of sub-threshold audio that end the turn.
        Default 4000 ms — tolerates natural thinking pauses.
    max_seconds:
        Emergency cap. 120 s by default. Normal turns end much earlier.
    silence_rms_threshold:
        Floor for the effective threshold. Default 150.
        Actual threshold used = max(this, noise_floor × multiplier).
        Tune via JARVIS_VOICE_SILENCE_RMS.
    on_state:
        Optional callback invoked with ``"recording"`` (speech) or
        ``"waiting_for_silence"`` (post-speech silence accumulating).
    abort_event:
        Optional ``threading.Event``. When set, recording stops immediately
        and returns ``stop_reason="manually_ended"`` with whatever audio
        was captured so far.  Used by the "End & send" UI button.
    on_calibrated:
        Optional callback fired after calibration with
        ``(noise_floor_rms, effective_threshold)``.

    Returns
    -------
    (wav_bytes, stop_reason)
        ``stop_reason`` is one of:
        - ``"silence_endpointed"`` — ended normally on silence
        - ``"max_duration"``       — hit the 120 s emergency cap
        - ``"pre_speech_timeout"`` — no speech detected within max_seconds
        - ``"manually_ended"``     — abort_event was set ("End & send")
    """
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise ImportError(
            f"sounddevice/numpy not available in main venv: {exc}. "
            "Both are listed in pyproject.toml dependencies."
        ) from exc

    chunk_samples = int(sample_rate * _VAD_CHUNK_MS / 1000)
    silence_chunks_needed = max(1, int(silence_stop_ms / _VAD_CHUNK_MS))
    max_chunks = int(max_seconds * 1000 / _VAD_CHUNK_MS)
    min_chunks = max(1, int(min_seconds * 1000 / _VAD_CHUNK_MS))

    all_chunks: List[Any] = []
    silence_consecutive: int = 0
    speech_detected: bool = False
    stop_reason: str = "max_duration"
    noise_floor_rms: float = 0.0
    effective_threshold: float = silence_rms_threshold

    stream = sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="int16",
        blocksize=chunk_samples,
    )
    stream.start()
    try:
        # ── Phase 1: Calibration + early speech detection ─────────────────
        # Read the first N chunks. Run speech detection with the STATIC
        # threshold so early speech (user starts talking immediately) is
        # never missed.  Only sub-threshold (quiet) chunks contribute to
        # the noise floor estimate so that speech-level audio doesn't
        # artificially inflate the adaptive threshold.
        calib_n = min(_NOISE_CALIB_CHUNKS, max_chunks)
        calib_quiet_rmss: List[float] = []  # only quiet chunks for noise floor

        for _ in range(calib_n):
            if abort_event is not None and abort_event.is_set():
                stop_reason = "manually_ended"
                break
            data, _overflowed = stream.read(chunk_samples)
            all_chunks.append(data.copy())
            chunk_flat = data.flatten().astype(np.float64)
            rms = float(np.sqrt(np.mean(chunk_flat ** 2)))

            # Use STATIC threshold for speech detection during calibration
            if rms >= silence_rms_threshold:
                speech_detected = True
                silence_consecutive = 0
                if on_state is not None:
                    on_state("recording")
            else:
                silence_consecutive += 1
                calib_quiet_rmss.append(rms)   # quiet chunk → noise floor data

        if stop_reason != "manually_ended":
            # Noise floor from quiet-only calibration chunks.
            # If ALL calibration was speech, fall back to static threshold
            # (can't estimate ambient — user may have started talking immediately).
            if calib_quiet_rmss:
                noise_floor_rms = float(np.percentile(calib_quiet_rmss, 75))
                adaptive = noise_floor_rms * _NOISE_CALIB_MULTIPLIER
                effective_threshold = max(silence_rms_threshold, adaptive)
            else:
                noise_floor_rms = 0.0
                effective_threshold = silence_rms_threshold
            logger.info(
                "VAD calibrated: noise_floor=%.1f rms  static_thresh=%.0f "
                "adaptive=%.1f  effective=%.1f  silence_stop=%.0fms  max=%.1fs",
                noise_floor_rms, silence_rms_threshold,
                noise_floor_rms * _NOISE_CALIB_MULTIPLIER,
                effective_threshold, silence_stop_ms, max_seconds,
            )
            if on_calibrated is not None:
                on_calibrated(noise_floor_rms, effective_threshold)

        # ── Phase 2: Main recording loop (adaptive threshold) ─────────────
        for chunk_idx in range(calib_n, max_chunks):
            if abort_event is not None and abort_event.is_set():
                stop_reason = "manually_ended"
                break

            data, _overflowed = stream.read(chunk_samples)
            all_chunks.append(data.copy())

            chunk_flat = data.flatten().astype(np.float64)
            rms = float(np.sqrt(np.mean(chunk_flat ** 2)))

            if rms >= effective_threshold:
                speech_detected = True
                silence_consecutive = 0
                if on_state is not None:
                    on_state("recording")
                logger.debug("VAD chunk %d: rms=%.0f >= thresh=%.0f → speech", chunk_idx, rms, effective_threshold)
            else:
                silence_consecutive += 1
                logger.debug(
                    "VAD chunk %d: rms=%.0f < thresh=%.0f → silence %d/%d",
                    chunk_idx, rms, effective_threshold, silence_consecutive, silence_chunks_needed,
                )
                if speech_detected and silence_consecutive >= 3 and on_state is not None:
                    on_state("waiting_for_silence")

            # Only endpoint after min_seconds elapsed AND speech was heard
            if chunk_idx >= min_chunks and speech_detected:
                if silence_consecutive >= silence_chunks_needed:
                    stop_reason = "silence_endpointed"
                    break

    finally:
        stream.stop()
        stream.close()

    if not speech_detected and stop_reason not in ("manually_ended",):
        stop_reason = "pre_speech_timeout"

    if not all_chunks:
        # Degenerate: aborted before any audio was captured
        audio_array = np.zeros((chunk_samples,), dtype=np.int16)
    else:
        audio_array = np.concatenate(all_chunks, axis=0)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_array.tobytes())

    elapsed_s = len(all_chunks) * _VAD_CHUNK_MS / 1000.0
    logger.info(
        "VAD finished: %.1fs — stop=%s  speech=%s  silence=%d/%d  "
        "noise_floor=%.1f  effective_thresh=%.1f",
        elapsed_s, stop_reason, speech_detected,
        silence_consecutive, silence_chunks_needed,
        noise_floor_rms, effective_threshold,
    )
    return buf.getvalue(), stop_reason


# ---------------------------------------------------------------------------
# Speech / silence gate — reject ambient noise and STT hallucinations
# ---------------------------------------------------------------------------

# int16 mono @ 16 kHz — conservative; real speech usually exceeds both.
_MIN_SPEECH_RMS = 250.0
_MIN_SPEECH_PEAK = 700

# Cloud STT confidence when the backend exposes it (e.g. Deepgram).
_MIN_STT_CONFIDENCE = 0.55

# Whisper avg_logprob is log-probability; closer to 0 is stronger.
_MIN_SEGMENT_AVG_LOGPROB = -0.95

# Known silence/noise hallucinations from Whisper-class models on quiet clips.
_STT_HALLUCINATION_FRAGMENTS: Tuple[str, ...] = (
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "like and subscribe",
    "subtitles by",
    "subtitle by",
    "transcribed by",
    "copyright",
    "all rights reserved",
    "music playing",
    "applause",
    "[blank_audio]",
    "[silence]",
    "www.",
    "http://",
    "https://",
)

_STT_NOISE_EXACT: frozenset[str] = frozenset({
    ".",
    "..",
    "...",
    "a",
    "ah",
    "hmm",
    "hm",
    "i",
    "music",
    "oh",
    "ok",
    "okay",
    "silence",
    "so",
    "thank you",
    "thanks",
    "the",
    "um",
    "uh",
    "you",
})


@dataclass(frozen=True)
class VoiceTranscriptDecision:
    """Whether a captured clip + STT output may route to model/TTS."""

    accepted: bool
    text: str
    reason: str


def wav_audio_stats(wav_bytes: bytes) -> Tuple[float, int]:
    """Return (RMS, peak) for int16 PCM inside a WAV container."""
    try:
        import numpy as np
    except ImportError as exc:
        raise ImportError(
            f"numpy not available in main venv: {exc}. "
            "It is listed in pyproject.toml dependencies."
        ) from exc

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
    except Exception:
        return 0.0, 0
    if not frames:
        return 0.0, 0
    samples = np.frombuffer(frames, dtype=np.int16)
    if samples.size == 0:
        return 0.0, 0
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    peak = int(np.max(np.abs(samples)))
    return rms, peak


def audio_has_speech_energy(wav_bytes: bytes) -> Tuple[bool, float, int]:
    """Return whether the clip likely contains speech-level energy."""
    rms, peak = wav_audio_stats(wav_bytes)
    return (rms >= _MIN_SPEECH_RMS or peak >= _MIN_SPEECH_PEAK), rms, peak


def _normalize_transcript_for_gate(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s']", " ", t)
    return " ".join(t.split())


def _best_segment_logprob(result: Any) -> Optional[float]:
    probs = [
        seg.confidence
        for seg in getattr(result, "segments", [])
        if getattr(seg, "confidence", None) is not None
    ]
    if not probs:
        return None
    return max(probs)


def evaluate_voice_transcript(
    text: str,
    result: Any,
    *,
    wav_bytes: bytes,
    is_stop_phrase: bool = False,
) -> VoiceTranscriptDecision:
    """Decide if STT output represents real speech worth routing.

    Stop phrases are checked separately and bypass hallucination rejection.
    """
    cleaned = text.strip()
    if not cleaned:
        return VoiceTranscriptDecision(False, "", "empty_transcript")

    normalized = _normalize_transcript_for_gate(cleaned)
    if not normalized:
        return VoiceTranscriptDecision(False, "", "empty_transcript")

    if is_stop_phrase:
        return VoiceTranscriptDecision(True, cleaned, "stop_phrase")

    has_energy, rms, peak = audio_has_speech_energy(wav_bytes)
    if not has_energy:
        logger.info(
            "Discarding clip with insufficient speech energy (rms=%.1f peak=%d)",
            rms,
            peak,
        )
        return VoiceTranscriptDecision(False, "", "low_audio_energy")

    if normalized in _STT_NOISE_EXACT:
        return VoiceTranscriptDecision(False, "", "noise_fragment")

    for fragment in _STT_HALLUCINATION_FRAGMENTS:
        if fragment in normalized:
            return VoiceTranscriptDecision(False, "", "hallucination_fragment")

    stt_confidence = getattr(result, "confidence", None)
    if stt_confidence is not None and stt_confidence < _MIN_STT_CONFIDENCE:
        return VoiceTranscriptDecision(False, "", "low_stt_confidence")

    best_logprob = _best_segment_logprob(result)
    if best_logprob is not None and best_logprob < _MIN_SEGMENT_AVG_LOGPROB:
        return VoiceTranscriptDecision(False, "", "low_segment_confidence")

    return VoiceTranscriptDecision(True, cleaned, "accepted")


# ---------------------------------------------------------------------------
# STT — uses existing speech backends via voice_pipeline status check
# ---------------------------------------------------------------------------


def transcribe_command_result(
    audio_bytes: bytes,
    language: str = "en",
) -> Any:
    """Transcribe WAV audio bytes using the configured STT backend.

    Returns the backend ``TranscriptionResult`` so voice routing can apply
    confidence/no-speech gates before model/TTS.
    """
    from openjarvis.autonomy.voice_pipeline import STTEngine, get_stt_status

    stt = get_stt_status()
    engine = stt.get("stt_status", STTEngine.NOT_CONFIGURED)

    logger.debug(
        "Transcribing via STT engine=%s language=%s bytes=%d",
        engine,
        language,
        len(audio_bytes),
    )

    if engine == STTEngine.FASTER_WHISPER:
        from openjarvis.speech.faster_whisper import FasterWhisperBackend

        backend = FasterWhisperBackend()
        return backend.transcribe(audio_bytes, format="wav", language=language)

    if engine == STTEngine.OPENAI_WHISPER:
        from openjarvis.speech.openai_whisper import OpenAIWhisperBackend

        backend = OpenAIWhisperBackend()
        return backend.transcribe(audio_bytes, format="wav", language=language)

    if engine == STTEngine.DEEPGRAM:
        from openjarvis.speech.deepgram import DeepgramSpeechBackend

        backend = DeepgramSpeechBackend()
        return backend.transcribe(audio_bytes, format="wav", language=language)

    raise RuntimeError(
        f"STT not configured (status={engine!r}). "
        "Install faster-whisper or set OPENAI_API_KEY / DEEPGRAM_API_KEY."
    )


def transcribe_command(audio_bytes: bytes, language: str = "en") -> str:
    """Transcribe WAV audio bytes using the configured STT backend.

    Reuses the existing STT path (get_stt_status → faster_whisper /
    openai_whisper / deepgram). Does NOT introduce a new STT system.
    Language defaults to 'en' to prevent Malay/Indonesian misdetection
    on short clips (same fix as the packaged-app STT path in api_routes.py).
    """
    result = transcribe_command_result(audio_bytes, language=language)
    text = result.text.strip()
    logger.info("STT transcript: %r", text)
    return text


# ---------------------------------------------------------------------------
# Jarvis query — uses existing engine + security infrastructure
# ---------------------------------------------------------------------------


def query_jarvis_text(
    text: str,
    *,
    on_route: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> str:
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

    configured_model = getattr(config.intelligence, "default_model", None) or None
    preferred_engine = (
        getattr(config.intelligence, "preferred_engine", None) or None
    )
    resolved = get_engine(
        config,
        preferred_engine,
        model=configured_model,
    )
    if resolved is None:
        return (
            "No inference engine available. "
            "Start Ollama or set OPENAI_API_KEY / ANTHROPIC_API_KEY."
        )

    engine_name, engine = resolved

    # Voice latency policy: trivial/simple spoken questions should not wait
    # tens of seconds on CPU Ollama when the packaged app already has a fast
    # cloud provider configured.  This is deliberately voice-only and uses
    # the existing engine registry; normal chat/model routing is unchanged.
    from openjarvis.learning.routing.complexity import score_complexity

    complexity = score_complexity(text)
    route_path = "jarvis_default"
    provider = engine_name
    model_name = configured_model
    if complexity.tier in ("trivial", "simple"):
        for fast_model, fast_provider in _VOICE_FAST_MODELS:
            fast_resolved = get_engine(config, "cloud", model=fast_model)
            if fast_resolved is None or fast_resolved[0] != "cloud":
                continue
            engine_name, engine = fast_resolved
            model_name = fast_model
            provider = fast_provider
            route_path = "voice_fast_cloud"
            break

    # Security — MUST run before any inference; preserves all approval gates
    sec = setup_security(config, engine, bus)
    engine = sec.engine

    # Resolve model
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

    route = {
        "model": model_name or "",
        "provider": provider,
        "engine": engine_name,
        "path": route_path,
        "complexity_tier": complexity.tier,
    }
    logger.info(
        "Voice route selected: provider=%s engine=%s model=%s path=%s tier=%s",
        route["provider"],
        route["engine"],
        route["model"],
        route["path"],
        route["complexity_tier"],
    )
    if on_route is not None:
        try:
            on_route(route)
        except Exception as exc:
            logger.debug("Voice route callback failed (non-fatal): %s", exc)

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


class _TTSPlayback:
    """Tracks the active TTS subprocess so sessions can cancel pending speech."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: Optional[subprocess.Popen] = None

    def cancel(self) -> None:
        with self._lock:
            proc = self._proc
            self._proc = None
        if proc is None or proc.poll() is not None:
            return
        try:
            proc.terminate()
            proc.wait(timeout=0.5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _set_proc(self, proc: Optional[subprocess.Popen]) -> None:
        with self._lock:
            self._proc = proc

    def _wait_proc(self, proc: subprocess.Popen, timeout: float) -> None:
        try:
            proc.wait(timeout=timeout)
        finally:
            with self._lock:
                if self._proc is proc:
                    self._proc = None


def speak_response(
    text: str,
    *,
    playback: Optional[_TTSPlayback] = None,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> bool:
    """Speak ``text`` using the configured TTS engine.

    TTS priority (Voice Safety Sprint):
      Deepgram Aura (primary) → macOS say → OpenAI TTS → not_configured
    Override with JARVIS_TTS_PROVIDER env var.
    Runs synchronously so the loop waits for speech to finish before
    returning to wake-word listening.

    Returns False when cancelled before or during playback.
    """
    if cancel_check is not None and cancel_check():
        return False

    from openjarvis.autonomy.voice_pipeline import TTSEngine, get_tts_status

    tts = get_tts_status()
    engine = tts.get("tts_status", TTSEngine.NOT_CONFIGURED)

    logger.debug("TTS speak: engine=%s text=%r", engine, text[:80])

    if engine == TTSEngine.DEEPGRAM:
        import tempfile
        import os as _os
        try:
            from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
            api_key = _os.environ.get("DEEPGRAM_API_KEY", "")
            if not api_key:
                logger.warning("Deepgram TTS: DEEPGRAM_API_KEY not set — skipping")
                return False
            if cancel_check is not None and cancel_check():
                return False
            backend = DeepgramTTSBackend(api_key=api_key)
            result = backend.synthesize(text, output_format="mp3")
            if not result.audio:
                logger.warning("Deepgram TTS returned empty audio")
                return False
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp_path = tmp.name
                tmp.write(result.audio)
            if cancel_check is not None and cancel_check():
                _os.unlink(tmp_path)
                return False
            proc = subprocess.Popen(["afplay", tmp_path])
            if playback is not None:
                playback._set_proc(proc)
            try:
                if playback is not None:
                    playback._wait_proc(proc, 60.0)
                else:
                    proc.wait(timeout=60)
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Deepgram TTS failed: %s", exc)
        return not (cancel_check is not None and cancel_check())

    if engine == TTSEngine.MACOS_SAY:
        try:
            proc = subprocess.Popen(["say", text])
            if playback is not None:
                playback._set_proc(proc)
            if cancel_check is not None and cancel_check():
                proc.terminate()
                if playback is not None:
                    playback._set_proc(None)
                return False
            if playback is not None:
                playback._wait_proc(proc, 60.0)
            else:
                proc.wait(timeout=60)
        except Exception as exc:
            logger.warning("macOS say failed: %s", exc)
        return not (cancel_check is not None and cancel_check())

    if engine == TTSEngine.OPENAI_TTS:
        try:
            import tempfile
            import os as _os
            from openai import OpenAI
            api_key = _os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                logger.warning("OpenAI TTS: OPENAI_API_KEY not set — skipping")
                return False
            if cancel_check is not None and cancel_check():
                return False
            client = OpenAI(api_key=api_key)
            with client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice="alloy",
                input=text,
            ) as response:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                    tmp_path = tmp.name
                    for chunk in response.iter_bytes(chunk_size=4096):
                        if cancel_check is not None and cancel_check():
                            _os.unlink(tmp_path)
                            return False
                        tmp.write(chunk)
            if cancel_check is not None and cancel_check():
                _os.unlink(tmp_path)
                return False
            proc = subprocess.Popen(["afplay", tmp_path])
            if playback is not None:
                playback._set_proc(proc)
            try:
                if playback is not None:
                    playback._wait_proc(proc, 60.0)
                else:
                    proc.wait(timeout=60)
            finally:
                _os.unlink(tmp_path)
        except Exception as exc:
            logger.warning("OpenAI TTS failed: %s", exc)
        return not (cancel_check is not None and cancel_check())

    logger.warning(
        "TTS not configured (status=%r) — response not spoken. "
        "Set DEEPGRAM_API_KEY for primary Deepgram TTS.",
        engine,
    )
    return False


def play_acknowledgement_cue() -> None:
    """Play a short local wake cue before recording begins.

    The cue is intentionally local and bounded: a full TTS greeting can spend
    10–30 seconds synthesizing/speaking before the microphone opens.  Tink is
    roughly half a second on macOS, keeping wake acknowledgement audible
    without allowing TTS/network latency onto the recording critical path.
    """
    sound = "/System/Library/Sounds/Tink.aiff"
    try:
        subprocess.run(
            ["afplay", sound],
            check=False,
            timeout=1.5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        logger.debug("Wake acknowledgement cue failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Voice runtime / status query router
#
# Intercepts known runtime/status queries BEFORE routing to the LLM.
# Returns a direct answer from real Jarvis runtime state.
# Does not leak API keys, tokens, or env values.
# ---------------------------------------------------------------------------

# Patterns that should be answered from runtime state, not the LLM.
_RUNTIME_QUERY_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bvoice provider\b",
        r"\busing deepgram\b",
        r"\bvoice status\b",
        r"\bsafe status check\b",
        r"\bstatus check\b",
        r"\bbackend\b.*\bconnected\b",
        r"\bconnected\b.*\bbackend\b",
        r"\bwhat can you do\b",
        r"\bcapabilit",
        r"\bstt\b.*\bprovider\b",
        r"\btts\b.*\bprovider\b",
        r"\bwhat.*provider\b",
        r"\bprovider.*what\b",
        r"\bvoice.*working\b",
        r"\bworking.*voice\b",
        # Fallback provider questions
        r"\bfallback\b.*\b(provider|voice|stt|tts|deepgram|fails?|down)\b",
        r"\b(provider|stt|tts|deepgram)\b.*\bfallback\b",
        r"\bif deepgram\b",
        r"\bdeepgram fail",
    ]
)


def _build_voice_runtime_answer() -> str:
    """Return a short, factual voice/provider/status answer.

    Reads from real runtime state. Never leaks keys or token values.
    """
    try:
        from openjarvis.autonomy.voice_pipeline import get_stt_status, get_tts_status, get_voice_status
        stt = get_stt_status()
        tts = get_tts_status()
        voice = get_voice_status()

        stt_name = stt.get("stt_status", "unknown")
        tts_name = tts.get("tts_status", "unknown")
        stt_primary = stt.get("primary", False)
        tts_primary = tts.get("primary", False)
        stt_configured = stt.get("is_configured", False)
        tts_configured = tts.get("is_configured", False)

        stt_line = (
            f"STT (speech-to-text): {stt_name}"
            + (" — primary, configured" if stt_primary and stt_configured else
               " — configured" if stt_configured else " — not configured")
        )
        tts_line = (
            f"TTS (text-to-speech): {tts_name}"
            + (" — primary, configured" if tts_primary and tts_configured else
               " — configured" if tts_configured else " — not configured")
        )

        fallback_line = ""
        fallback = voice.get("fallback_providers")
        if fallback:
            fallback_line = f" Fallbacks available: {', '.join(str(f) for f in fallback[:3])}."
        else:
            # Report known fallbacks from the STT/TTS discovery path
            known_fallbacks = []
            from openjarvis.speech._discovery import _DEFAULT_DISCOVERY_ORDER
            for p in _DEFAULT_DISCOVERY_ORDER:
                if p != stt_name:
                    known_fallbacks.append(p)
                    if len(known_fallbacks) >= 2:
                        break
            if known_fallbacks:
                fallback_line = f" STT fallbacks (in order): {', '.join(known_fallbacks)}."

        return (
            f"Voice is active. {stt_line}. {tts_line}.{fallback_line}"
            f" Wake-word hotkey: Cmd+Shift+Space. Backend: connected."
        )
    except Exception as exc:
        logger.debug("Runtime query answer failed: %s", exc)
        return "Voice backend is active. STT and TTS are configured. I cannot retrieve detailed provider status right now."


def handle_voice_runtime_query(text: str) -> Optional[str]:
    """If ``text`` is a runtime/status question, return a direct answer.

    Returns ``None`` if the query is not a runtime question — caller should
    then route to ``query_jarvis_text`` as normal.

    Safe-only: only reads runtime state, never executes destructive actions.
    """
    if not text:
        return None
    for pattern in _RUNTIME_QUERY_PATTERNS:
        if pattern.search(text):
            logger.info("Runtime query intercepted: %r — answering from runtime state", text[:80])
            return _build_voice_runtime_answer()
    return None


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
        record_seconds: float = _DEFAULT_MAX_RECORD_SECONDS,
        language: str = "en",
        auto_restart: bool = False,
        debug: bool = False,
        on_state_change: Optional[Callable[[str], None]] = None,
        session_timeout: float = 30.0,
        stop_phrases: Optional[List[str]] = None,
        user_name: str = "Bryan",
        # Silence/endpointing — read from env if not supplied explicitly
        min_record_seconds: Optional[float] = None,
        silence_stop_ms: Optional[float] = None,
        max_record_seconds: Optional[float] = None,
        silence_rms_threshold: Optional[float] = None,
    ) -> None:
        # ``record_seconds`` is kept as an API parameter for backward compat
        # but now represents the emergency max cap (not the normal end condition).
        # The normal end condition is silence-based via the VAD.
        self._record_seconds = record_seconds  # kept for status reporting
        self._min_record_seconds = min_record_seconds if min_record_seconds is not None else _env_float(
            "JARVIS_VOICE_MIN_RECORD_SECONDS", _DEFAULT_MIN_RECORD_SECONDS
        )
        self._silence_stop_ms = silence_stop_ms if silence_stop_ms is not None else _env_float(
            "JARVIS_VOICE_SILENCE_STOP_MS", _DEFAULT_SILENCE_STOP_MS
        )
        self._max_record_seconds = max_record_seconds if max_record_seconds is not None else _env_float(
            "JARVIS_VOICE_MAX_RECORD_SECONDS", _DEFAULT_MAX_RECORD_SECONDS
        )
        self._silence_rms_threshold = silence_rms_threshold if silence_rms_threshold is not None else _env_float(
            "JARVIS_VOICE_SILENCE_RMS", _DEFAULT_SILENCE_RMS
        )
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
        self._wake_detected_monotonic: Optional[float] = None
        self._session_id = 0
        self._active_session_id: Optional[int] = None
        self._session_deadline: float = 0.0
        self._tts = _TTSPlayback()
        # Hotkey-only mode: set when wake-word bridge fails at start().
        # Session is still usable via trigger() (hotkey/mic-button path).
        self._hotkey_mode: bool = False
        self._wake_failure_reason: Optional[str] = None

        # Abort event for the "End & send" UI button — set to force-stop
        # the current VAD recording loop and submit whatever audio was captured.
        self._recording_abort: threading.Event = threading.Event()

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

    def _is_session_live(self, session_id: int) -> bool:
        """Return True while ``session_id`` is the authorized active session."""
        with self._lock:
            return self._active_session_id == session_id

    def _session_allows_model_and_tts(
        self,
        session_id: int,
        *,
        is_first_turn: bool,
    ) -> bool:
        """Hard privacy gate: model/TTS only after wake or valid follow-up."""
        with self._lock:
            if self._active_session_id != session_id:
                return False
            if is_first_turn:
                return True
            return time.time() <= self._session_deadline

    def _extend_session_deadline(self, session_id: int) -> None:
        with self._lock:
            if self._active_session_id == session_id:
                self._session_deadline = time.time() + self._session_timeout

    def _end_session(self, session_id: int, reason: str) -> None:
        """Invalidate session, cancel pending TTS, return to wake-only mode."""
        with self._lock:
            if self._active_session_id != session_id:
                return
            self._active_session_id = None
            self._session_deadline = 0.0
            self._wake_detected_monotonic = None
        self._tts.cancel()
        self._emit_event({"type": "state", "state": "session_ended", "reason": reason})

    def _cancel_check(self, session_id: int) -> Callable[[], bool]:
        return lambda: not self._is_session_live(session_id)

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
            if self._active_session_id is not None:
                logger.debug(
                    "Wake-word ignored (session=%s already active)",
                    self._active_session_id,
                )
                return
            self._session_id += 1
            session_id = self._session_id
            self._active_session_id = session_id
            self._session_deadline = time.time() + self._session_timeout
            self._state = "recording"
            self._wake_detected_monotonic = time.monotonic()

        model = getattr(event, "model", "unknown")
        score = getattr(event, "score", 0.0)
        trigger_source = getattr(event, "source", "unknown")
        logger.info(
            "Wake word fired: model=%s score=%.3f source=%s",
            model, score, trigger_source,
        )
        self._emit_event({
            "type": "state",
            "state": "wake_detected",
            "model": str(model),
            "score": float(score),
            "trigger_source": trigger_source,
        })
        threading.Thread(
            target=self._process_turn,
            args=(session_id, trigger_source),
            daemon=True,
            name="jarvis-voice-turn",
        ).start()

    def _process_turn(self, session_id: int, trigger_source: str = "wake_word") -> None:
        """Full conversation session: greeting → [record→STT→Jarvis→TTS] loop.

        A single call handles the entire session (greeting + all follow-up turns
        until timeout or stop phrase).  This method is called in a daemon thread.
        Always returns to state='listening' in the finally block.
        """
        if not self._is_session_live(session_id):
            logger.warning(
                "Voice turn aborted — session %s is not authorized", session_id
            )
            return
        end_reason = "completed"
        try:
            # ---------------------------------------------------------- #
            # 1. Immediate acknowledgement (short local cue before recording) #
            # ---------------------------------------------------------- #
            with self._lock:
                _wake_ts = self._wake_detected_monotonic or time.monotonic()
            self._set_state("acknowledging")
            play_acknowledgement_cue()
            logger.info("Acknowledged wake word with short local cue")
            _ack_done_ts = time.monotonic()
            self._emit_latency("wake_to_ack_ms", (_ack_done_ts - _wake_ts) * 1000)

            if not self._is_session_live(session_id):
                logger.info("Session ended during acknowledgement — aborting turn")
                return

            # ---------------------------------------------------------- #
            # 2. Active conversation session loop                          #
            # ---------------------------------------------------------- #
            self._set_state("active_conversation")
            first_turn = True

            while True:
                is_first_turn = first_turn
                if not is_first_turn:
                    # Follow-up turn — no wake-word needed, but session must
                    # still be explicitly active and within its timeout.
                    self._set_state("follow_up_listening")
                    if not self._session_allows_model_and_tts(
                        session_id, is_first_turn=False
                    ):
                        logger.info(
                            "Follow-up session expired — returning to wake listening"
                        )
                        break
                    _turn_start = time.monotonic()
                    # Brief pause to give user a moment to start speaking
                    time.sleep(0.4)
                    if not self._is_session_live(session_id):
                        break
                else:
                    # Include acknowledgement in the first turn so
                    # wake-to-record can never exceed total-turn latency.
                    _turn_start = _wake_ts
                first_turn = False

                if not self._is_session_live(session_id):
                    break

                # ------------------------------------------------------ #
                # 3. Record command audio (VAD-based silence endpointing)   #
                # ------------------------------------------------------ #
                _rec_start = time.monotonic()
                self._set_state("recording")
                self._emit_event({
                    "type": "interim_transcript",
                    "text": "Speak freely — ends automatically on silence",
                })
                # Calibration results stored via callback so they can be included
                # in the vad SSE event after recording completes.
                _calib: dict = {}
                def _on_calibrated(noise_floor: float, effective_threshold: float) -> None:
                    _calib["noise_floor_rms"] = round(noise_floor, 1)
                    _calib["effective_threshold"] = round(effective_threshold, 1)

                self._recording_abort.clear()
                try:
                    audio, vad_stop_reason = record_command_audio_vad(
                        min_seconds=self._min_record_seconds,
                        silence_stop_ms=self._silence_stop_ms,
                        max_seconds=self._max_record_seconds,
                        sample_rate=16000,
                        silence_rms_threshold=self._silence_rms_threshold,
                        on_state=lambda s: self._set_state(s),
                        abort_event=self._recording_abort,
                        on_calibrated=_on_calibrated,
                    )
                    logger.info("VAD stop reason: %s", vad_stop_reason)
                except Exception as exc:
                    logger.error("Recording failed: %s", exc)
                    break
                _rec_end = time.monotonic()
                # Emit non-secret VAD diagnostics for UI truth-state and debugging.
                self._emit_event({
                    "type": "vad",
                    "stop_reason": vad_stop_reason,
                    "duration_s": round(_rec_end - _rec_start, 2),
                    "trigger_source": trigger_source,
                    "silence_stop_ms": self._silence_stop_ms,
                    "noise_floor_rms": _calib.get("noise_floor_rms"),
                    "effective_threshold": _calib.get("effective_threshold"),
                })
                if is_first_turn:
                    self._emit_latency(
                        "wake_to_record_start_ms",
                        (_rec_start - _wake_ts) * 1000,
                    )

                if not self._is_session_live(session_id):
                    break

                # ------------------------------------------------------ #
                # 4. STT — existing speech backend path                    #
                # ------------------------------------------------------ #
                _stt_start = time.monotonic()
                self._set_state("transcribing")
                self._emit_event({"type": "interim_transcript", "text": "Transcribing..."})
                try:
                    stt_result = transcribe_command_result(
                        audio, language=self._language
                    )
                    text = stt_result.text.strip()
                except Exception as exc:
                    logger.error("STT failed: %s", exc)
                    break
                _stt_end = time.monotonic()
                self._emit_latency("stt_duration_ms", (_stt_end - _stt_start) * 1000)
                self._emit_latency("speech_end_to_stt_final_ms", (_stt_end - _rec_end) * 1000)

                is_stop = self._is_stop_phrase(text) if text else False
                decision = evaluate_voice_transcript(
                    text,
                    stt_result,
                    wav_bytes=audio,
                    is_stop_phrase=is_stop,
                )
                if not decision.accepted:
                    logger.info(
                        "Non-speech capture discarded (%s) — not routing to model/TTS",
                        decision.reason,
                    )
                    if is_first_turn:
                        logger.info("No speech after wake — ending session")
                        break
                    self._set_state("follow_up_listening")
                    continue

                if not self._session_allows_model_and_tts(
                    session_id, is_first_turn=is_first_turn
                ):
                    logger.info(
                        "Model/TTS blocked — session %s no longer authorized",
                        session_id,
                    )
                    break

                text = decision.text
                logger.info("Transcript: %r", text)
                self._emit_event({"type": "transcript", "text": text})

                # ------------------------------------------------------ #
                # 5. Stop-phrase check                                     #
                # ------------------------------------------------------ #
                if is_stop:
                    logger.info("Stop phrase detected: %r", text)
                    end_reason = "stop_phrase"
                    self._tts.cancel()
                    try:
                        speak_response(
                            "Going back to sleep. Say 'hey jarvis' when you need me.",
                            playback=self._tts,
                            cancel_check=self._cancel_check(session_id),
                        )
                    except Exception:
                        pass
                    break

                # ------------------------------------------------------ #
                # 6. Route through normal Jarvis path (with security)      #
                # ------------------------------------------------------ #
                if not self._session_allows_model_and_tts(
                    session_id, is_first_turn=is_first_turn
                ):
                    logger.info(
                        "Model route blocked — session %s no longer authorized",
                        session_id,
                    )
                    break

                _model_start = time.monotonic()
                self._set_state("thinking")
                # ------------------------------------------------------ #
                # 6a. Runtime/status shortcut — answer from real state      #
                #     before touching the LLM.                              #
                # ------------------------------------------------------ #
                runtime_answer = handle_voice_runtime_query(text)
                try:
                    if runtime_answer is not None:
                        response = runtime_answer
                    else:
                        response = query_jarvis_text(
                            text,
                            on_route=lambda route: self._emit_event(
                                {"type": "route", **route}
                            ),
                        )
                except Exception as exc:
                    logger.error("Jarvis query failed: %s", exc)
                    response = "I encountered an error processing your request."
                _model_end = time.monotonic()
                self._emit_latency("model_duration_ms", (_model_end - _model_start) * 1000)

                if not self._session_allows_model_and_tts(
                    session_id, is_first_turn=is_first_turn
                ):
                    logger.info(
                        "TTS blocked — session %s ended during model inference",
                        session_id,
                    )
                    break

                if not response.strip():
                    response = "I don't have a response for that."
                logger.info("Response: %r", response[:120])
                self._emit_event({"type": "response", "text": response})

                # ------------------------------------------------------ #
                # 7. TTS — existing TTS path                               #
                # ------------------------------------------------------ #
                _tts_start = time.monotonic()
                self._set_state("speaking")
                try:
                    speak_response(
                        response,
                        playback=self._tts,
                        cancel_check=self._cancel_check(session_id),
                    )
                except Exception as exc:
                    logger.error("TTS failed: %s", exc)
                _tts_end = time.monotonic()
                self._emit_latency("tts_start_ms", (_tts_start - _model_end) * 1000)
                self._emit_latency("total_turn_ms", (_tts_end - _turn_start) * 1000)

                if not self._is_session_live(session_id):
                    break

                with self._lock:
                    self._turns += 1

                # Reset session deadline after each successful response
                self._extend_session_deadline(session_id)

        except Exception as exc:
            logger.error("Voice session error: %s", exc)
            self._emit_event({"type": "error", "message": str(exc)})
        finally:
            # Always invalidate session and return to wake-word-only listening
            self._end_session(session_id, reason=end_reason)
            self._set_state("listening")

    # ------------------------------------------------------------------ #
    # Public interface                                                       #
    # ------------------------------------------------------------------ #

    def start(self, debug: bool = False) -> Dict[str, Any]:
        """Start wake-word bridge and register the conversation callback.

        If the wake-word bridge fails (worker venv missing, socket error, etc.)
        the session still starts in hotkey-only mode.  The caller can check
        ``result["wake_mode"]`` == "hotkey_only" to surface a degraded-mode
        indicator without blocking the user from recording via trigger().
        """
        self._bridge.register_callback(self._on_wake)
        result = self._bridge.start(auto_restart=self._auto_restart, debug=debug or self._debug)
        if result.get("ok"):
            with self._lock:
                self._hotkey_mode = False
                self._wake_failure_reason = None
            self._set_state("listening")
            return result

        # Wake-word bridge failed — fall back to hotkey-only mode.
        # The session is still usable: trigger() fires _on_wake directly.
        wake_err = result.get("error", "unknown wake-word error")
        logger.warning(
            "Wake-word bridge failed (%s) — session starting in hotkey-only mode",
            wake_err,
        )
        with self._lock:
            self._hotkey_mode = True
            self._wake_failure_reason = wake_err
        self._set_state("listening")
        return {
            "ok": True,
            "wake_mode": "hotkey_only",
            "wake_failure_reason": wake_err,
            "worker_pid": None,
            "socket": None,
        }

    def end_recording(self) -> Dict[str, Any]:
        """Force-end the current VAD recording turn and submit captured audio.

        Sets the abort_event that record_command_audio_vad checks per-chunk.
        Returns immediately; STT and response happen asynchronously as normal.

        Use from the "End & send" UI button when silence detection is unreliable
        (noisy room, soft speaker, held note).  Returns stop_reason=manually_ended
        in the vad SSE event.
        """
        self._recording_abort.set()
        return {"ok": True, "action": "end_recording"}

    def trigger(self, source: str = "manual_button") -> Dict[str, Any]:
        """Manually trigger a voice recording turn (mic-button / manual path).

        Works whether wake-word is active or not.  Safe to call from the
        POST /v1/voice/session/trigger endpoint.

        Parameters
        ----------
        source:
            Non-secret label for diagnostics — e.g. "manual_button", "hotkey".
        """
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent
        event = WakeWordTriggerEvent(
            model="manual_trigger",
            score=1.0,
            ts=time.monotonic(),
            source=source,
        )
        self._on_wake(event)
        return {"ok": True, "triggered_at": time.time(), "source": source}

    def stop(self) -> None:
        """Stop the wake-word bridge and conversation loop."""
        with self._lock:
            session_id = self._active_session_id
        if session_id is not None:
            self._end_session(session_id, reason="stopped")
        self._bridge.stop()
        self._set_state("idle")
        # Sentinel to unblock SSE consumers
        self._emit_event({"type": "stopped"})

    def status(self) -> Dict[str, Any]:
        """Return loop state + bridge status."""
        with self._lock:
            state = self._state
            turns = self._turns
            hotkey_mode = self._hotkey_mode
            wake_failure = self._wake_failure_reason
        return {
            "loop_state": state,
            "turns_completed": turns,
            "record_seconds": self._record_seconds,
            "max_record_seconds": self._max_record_seconds,
            "min_record_seconds": self._min_record_seconds,
            "silence_stop_ms": self._silence_stop_ms,
            "language": self._language,
            "session_timeout": self._session_timeout,
            "wake_mode": "hotkey_only" if hotkey_mode else "wake_word",
            "wake_failure_reason": wake_failure,
            "bridge": self._bridge.status(),
        }


__all__ = [
    "VoiceConversationLoop",
    "STOP_PHRASES",
    "VoiceTranscriptDecision",
    "time_of_day_greeting",
    "record_command_audio",
    "record_command_audio_vad",
    "handle_voice_runtime_query",
    "wav_audio_stats",
    "audio_has_speech_energy",
    "evaluate_voice_transcript",
    "transcribe_command",
    "transcribe_command_result",
    "query_jarvis_text",
    "play_acknowledgement_cue",
    "speak_response",
    "_DEFAULT_MIN_RECORD_SECONDS",
    "_DEFAULT_SILENCE_STOP_MS",
    "_DEFAULT_MAX_RECORD_SECONDS",
]
