"""VoiceProvider abstraction — unified STT + TTS interface for Jarvis.

Provider selection (priority order):
  1. JARVIS_VOICE_PROVIDER / JARVIS_STT_PROVIDER / JARVIS_TTS_PROVIDER env var (explicit override)
  2. deepgram (primary/default — Bryan has credits)
  3. existing providers (faster-whisper, openai) as fallback

Safety contract:
  - VoiceProvider is STT/TTS transport only.
  - Jarvis remains the brain and safety authority.
  - All transcripts route through the normal Jarvis/COS/router path.
  - VoiceProvider never executes actions; it only converts audio ↔ text.
  - Secrets are never returned in diagnostics.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider name constants
# ---------------------------------------------------------------------------

PROVIDER_DEEPGRAM = "deepgram"
PROVIDER_FASTER_WHISPER = "faster-whisper"
PROVIDER_OPENAI = "openai"
PROVIDER_MACOS_SAY = "macos_say"
PROVIDER_NOT_CONFIGURED = "not_configured"

# Canonical priority list for STT (OpenAI Whisper is primary — more accurate
# than Deepgram for Bryan's accent; Deepgram kept as fallback).
_STT_DISCOVERY_ORDER: List[str] = [
    PROVIDER_OPENAI,
    PROVIDER_FASTER_WHISPER,
    PROVIDER_DEEPGRAM,
]

# Canonical priority list for TTS (deepgram is primary)
_TTS_DISCOVERY_ORDER: List[str] = [
    PROVIDER_DEEPGRAM,
    PROVIDER_MACOS_SAY,
    PROVIDER_OPENAI,
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class STTResult:
    """Normalized STT result from any provider."""

    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration_seconds: float = 0.0
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    fallback_used: bool = False
    fallback_reason: str = ""
    cost_metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TTSResult:
    """Normalized TTS result from any provider."""

    audio: bytes
    format: str = "mp3"
    duration_seconds: float = 0.0
    voice_id: str = ""
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    fallback_used: bool = False
    fallback_reason: str = ""
    cost_metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class VoiceMetrics:
    """Per-turn voice latency and cost metrics."""

    wake_to_recording_ms: float = 0.0
    recording_duration_ms: float = 0.0
    endpointing_delay_ms: float = 0.0
    stt_latency_ms: float = 0.0
    jarvis_routing_ms: float = 0.0
    tts_latency_ms: float = 0.0
    total_turn_ms: float = 0.0
    stt_provider: str = ""
    tts_provider: str = ""
    fallback_used: bool = False
    fallback_reason: str = ""
    transcript_confidence: Optional[float] = None
    cost_estimate: Optional[float] = None
    error_reason: Optional[str] = None


@dataclass
class ProviderHealth:
    """Health check result for a voice provider."""

    provider: str
    stt_available: bool = False
    tts_available: bool = False
    stt_blocker: str = ""
    tts_blocker: str = ""
    # Never include key values, prefixes, or lengths
    key_configured: bool = False
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceProviderConfig:
    """Runtime voice provider configuration derived from env vars."""

    voice_provider: str = PROVIDER_DEEPGRAM       # JARVIS_VOICE_PROVIDER
    stt_provider: str = PROVIDER_OPENAI            # JARVIS_STT_PROVIDER (Whisper primary)
    tts_provider: str = PROVIDER_DEEPGRAM          # JARVIS_TTS_PROVIDER
    stt_fallback: str = PROVIDER_FASTER_WHISPER    # local fallback if Whisper key missing
    tts_fallback: str = PROVIDER_MACOS_SAY         # first non-deepgram TTS
    stt_model: str = "whisper-1"
    tts_model: str = "aura-asteria-en"
    language: str = "en"

    @classmethod
    def from_env(cls) -> "VoiceProviderConfig":
        """Build config from env vars. STT defaults to OpenAI Whisper."""
        cfg = cls()
        voice = os.environ.get("JARVIS_VOICE_PROVIDER", "").strip().lower()
        stt = os.environ.get("JARVIS_STT_PROVIDER", "").strip().lower()
        tts = os.environ.get("JARVIS_TTS_PROVIDER", "").strip().lower()
        if voice:
            cfg.voice_provider = voice
        if stt:
            cfg.stt_provider = stt
        elif voice:
            cfg.stt_provider = voice
        if tts:
            cfg.tts_provider = tts
        elif voice:
            cfg.tts_provider = voice
        cfg.stt_model = os.environ.get("JARVIS_STT_MODEL", cfg.stt_model)
        cfg.tts_model = os.environ.get("JARVIS_TTS_MODEL", cfg.tts_model)
        cfg.language = os.environ.get("JARVIS_VOICE_LANGUAGE", cfg.language)
        return cfg


# ---------------------------------------------------------------------------
# VoiceProvider — unified STT + TTS interface
# ---------------------------------------------------------------------------


class VoiceProvider:
    """Unified voice provider: STT + TTS with fallback chain.

    This is transport only — it converts audio ↔ text.
    Jarvis/COS/router handles all action execution and safety gating.
    """

    def __init__(self, config: Optional[VoiceProviderConfig] = None) -> None:
        self._config = config or VoiceProviderConfig.from_env()

    @property
    def name(self) -> str:
        return self._config.voice_provider

    @property
    def stt_provider(self) -> str:
        return self._config.stt_provider

    @property
    def tts_provider(self) -> str:
        return self._config.tts_provider

    # ------------------------------------------------------------------ #
    # Health                                                                #
    # ------------------------------------------------------------------ #

    def health(self) -> ProviderHealth:
        """Check provider health. Never leaks key values/prefixes/lengths."""
        result = ProviderHealth(provider=self._config.voice_provider)
        result.key_configured = bool(os.environ.get("DEEPGRAM_API_KEY", ""))

        if self._config.stt_provider == PROVIDER_DEEPGRAM:
            result.stt_available = result.key_configured
            if not result.key_configured:
                result.stt_blocker = (
                    "DEEPGRAM_API_KEY not set — add to .env and restart"
                )
        elif self._config.stt_provider == PROVIDER_FASTER_WHISPER:
            try:
                import faster_whisper  # noqa: F401
                result.stt_available = True
            except ImportError:
                result.stt_blocker = "faster-whisper not installed"
        elif self._config.stt_provider == PROVIDER_OPENAI:
            result.stt_available = bool(os.environ.get("OPENAI_API_KEY", ""))
            if not result.stt_available:
                result.stt_blocker = "OPENAI_API_KEY not set"

        if self._config.tts_provider == PROVIDER_DEEPGRAM:
            result.tts_available = result.key_configured
            if not result.key_configured:
                result.tts_blocker = (
                    "DEEPGRAM_API_KEY not set — add to .env and restart"
                )
        elif self._config.tts_provider == PROVIDER_MACOS_SAY:
            import platform, shutil
            result.tts_available = platform.system() == "Darwin" and bool(shutil.which("say"))
            if not result.tts_available:
                result.tts_blocker = "macOS 'say' command not available"
        elif self._config.tts_provider == PROVIDER_OPENAI:
            result.tts_available = bool(os.environ.get("OPENAI_API_KEY", ""))
            if not result.tts_available:
                result.tts_blocker = "OPENAI_API_KEY not set"

        result.diagnostics = {
            "stt_provider": self._config.stt_provider,
            "tts_provider": self._config.tts_provider,
            "stt_model": self._config.stt_model,
            "tts_model": self._config.tts_model,
            "language": self._config.language,
            "stt_available": result.stt_available,
            "tts_available": result.tts_available,
        }
        return result

    # ------------------------------------------------------------------ #
    # STT                                                                   #
    # ------------------------------------------------------------------ #

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> STTResult:
        """Transcribe audio bytes. Falls back if primary provider fails."""
        lang = language or self._config.language
        t0 = time.monotonic()

        result = self._try_transcribe(
            audio,
            format=format,
            language=lang,
            provider=self._config.stt_provider,
        )
        if result is not None:
            result.latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return result

        # Primary failed — try fallback
        logger.warning(
            "STT primary provider %r failed — trying fallback %r",
            self._config.stt_provider,
            self._config.stt_fallback,
        )
        fallback_result = self._try_transcribe(
            audio,
            format=format,
            language=lang,
            provider=self._config.stt_fallback,
        )
        if fallback_result is not None:
            fallback_result.latency_ms = round((time.monotonic() - t0) * 1000, 1)
            fallback_result.fallback_used = True
            fallback_result.fallback_reason = f"primary {self._config.stt_provider} failed"
            return fallback_result

        return STTResult(
            text="",
            provider=self._config.stt_provider,
            error=f"STT failed: primary={self._config.stt_provider} fallback={self._config.stt_fallback} both unavailable",
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    def _try_transcribe(
        self,
        audio: bytes,
        *,
        format: str,
        language: str,
        provider: str,
    ) -> Optional[STTResult]:
        try:
            if provider == PROVIDER_DEEPGRAM:
                return self._transcribe_deepgram(audio, format=format, language=language)
            elif provider == PROVIDER_FASTER_WHISPER:
                return self._transcribe_faster_whisper(audio, format=format, language=language)
            elif provider == PROVIDER_OPENAI:
                return self._transcribe_openai(audio, format=format, language=language)
        except Exception as exc:
            logger.warning("STT provider %r error: %s", provider, exc)
        return None

    def _transcribe_deepgram(
        self,
        audio: bytes,
        *,
        format: str,
        language: str,
    ) -> Optional[STTResult]:
        from openjarvis.speech.deepgram import DeepgramSpeechBackend
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            return None
        backend = DeepgramSpeechBackend(api_key=api_key)
        if not backend.health():
            return None
        result = backend.transcribe(audio, format=format, language=language or None)
        return STTResult(
            text=result.text,
            language=result.language,
            confidence=result.confidence,
            duration_seconds=result.duration_seconds,
            provider=PROVIDER_DEEPGRAM,
            model=self._config.stt_model,
            cost_metadata={"provider": "deepgram", "model": self._config.stt_model},
        )

    def _transcribe_faster_whisper(
        self,
        audio: bytes,
        *,
        format: str,
        language: str,
    ) -> Optional[STTResult]:
        from openjarvis.speech.faster_whisper import FasterWhisperBackend
        backend = FasterWhisperBackend()
        if not backend.health():
            return None
        result = backend.transcribe(audio, format=format, language=language or None)
        return STTResult(
            text=result.text,
            language=result.language,
            confidence=result.confidence,
            duration_seconds=result.duration_seconds,
            provider=PROVIDER_FASTER_WHISPER,
            model="whisper",
        )

    def _transcribe_openai(
        self,
        audio: bytes,
        *,
        format: str,
        language: str,
    ) -> Optional[STTResult]:
        from openjarvis.speech.openai_whisper import OpenAIWhisperBackend
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return None
        backend = OpenAIWhisperBackend(api_key=api_key)
        if not backend.health():
            return None
        result = backend.transcribe(audio, format=format, language=language or None)
        return STTResult(
            text=result.text,
            language=result.language,
            confidence=result.confidence,
            duration_seconds=result.duration_seconds,
            provider=PROVIDER_OPENAI,
            model="whisper-1",
        )

    # ------------------------------------------------------------------ #
    # TTS                                                                   #
    # ------------------------------------------------------------------ #

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        output_format: str = "mp3",
    ) -> TTSResult:
        """Synthesize text to audio. Falls back if primary TTS provider fails."""
        t0 = time.monotonic()

        result = self._try_synthesize(
            text,
            voice_id=voice_id,
            output_format=output_format,
            provider=self._config.tts_provider,
        )
        if result is not None:
            result.latency_ms = round((time.monotonic() - t0) * 1000, 1)
            return result

        logger.warning(
            "TTS primary provider %r failed — trying fallback %r",
            self._config.tts_provider,
            self._config.tts_fallback,
        )
        fallback_result = self._try_synthesize(
            text,
            voice_id=voice_id,
            output_format=output_format,
            provider=self._config.tts_fallback,
        )
        if fallback_result is not None:
            fallback_result.latency_ms = round((time.monotonic() - t0) * 1000, 1)
            fallback_result.fallback_used = True
            fallback_result.fallback_reason = f"primary {self._config.tts_provider} failed"
            return fallback_result

        return TTSResult(
            audio=b"",
            provider=self._config.tts_provider,
            error=f"TTS failed: primary={self._config.tts_provider} fallback={self._config.tts_fallback} both unavailable",
            latency_ms=round((time.monotonic() - t0) * 1000, 1),
        )

    def _try_synthesize(
        self,
        text: str,
        *,
        voice_id: str,
        output_format: str,
        provider: str,
    ) -> Optional[TTSResult]:
        try:
            if provider == PROVIDER_DEEPGRAM:
                return self._synthesize_deepgram(text, voice_id=voice_id, output_format=output_format)
            elif provider == PROVIDER_MACOS_SAY:
                return self._synthesize_macos_say(text)
            elif provider == PROVIDER_OPENAI:
                return self._synthesize_openai(text, voice_id=voice_id)
        except Exception as exc:
            logger.warning("TTS provider %r error: %s", provider, exc)
        return None

    def _synthesize_deepgram(
        self,
        text: str,
        *,
        voice_id: str,
        output_format: str,
    ) -> Optional[TTSResult]:
        from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
        api_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if not api_key:
            return None
        backend = DeepgramTTSBackend(api_key=api_key)
        if not backend.health():
            return None
        v = voice_id or self._config.tts_model
        tts_result = backend.synthesize(text, voice_id=v, output_format=output_format)
        return TTSResult(
            audio=tts_result.audio,
            format=tts_result.format,
            duration_seconds=tts_result.duration_seconds,
            voice_id=tts_result.voice_id,
            provider=PROVIDER_DEEPGRAM,
            model=v,
            cost_metadata={"provider": "deepgram", "model": v},
        )

    def _synthesize_macos_say(self, text: str) -> Optional[TTSResult]:
        import platform, shutil
        if platform.system() != "Darwin" or not shutil.which("say"):
            return None
        # macOS say doesn't return audio bytes — return sentinel for speak_response
        return TTSResult(
            audio=b"MACOS_SAY",
            format="macos_say",
            provider=PROVIDER_MACOS_SAY,
            model="say",
        )

    def _synthesize_openai(self, text: str, *, voice_id: str) -> Optional[TTSResult]:
        from openjarvis.speech.openai_tts import OpenAITTSBackend
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            return None
        backend = OpenAITTSBackend(api_key=api_key)
        if not backend.health():
            return None
        v = voice_id or "alloy"
        tts_result = backend.synthesize(text, voice_id=v)
        return TTSResult(
            audio=tts_result.audio,
            format=tts_result.format,
            duration_seconds=tts_result.duration_seconds,
            voice_id=tts_result.voice_id,
            provider=PROVIDER_OPENAI,
            model=v,
        )

    # ------------------------------------------------------------------ #
    # Provider info (secret-safe diagnostics)                              #
    # ------------------------------------------------------------------ #

    def diagnostics(self) -> Dict[str, Any]:
        """Return safe diagnostics — no key values, prefixes, or lengths."""
        h = self.health()
        return {
            "voice_provider": self._config.voice_provider,
            "stt_provider": self._config.stt_provider,
            "tts_provider": self._config.tts_provider,
            "stt_available": h.stt_available,
            "tts_available": h.tts_available,
            "stt_blocker": h.stt_blocker,
            "tts_blocker": h.tts_blocker,
            "key_configured": h.key_configured,
            "stt_fallback": self._config.stt_fallback,
            "tts_fallback": self._config.tts_fallback,
            "language": self._config.language,
        }


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def get_default_provider() -> VoiceProvider:
    """Return a VoiceProvider using env-var config. Deepgram is default."""
    return VoiceProvider(VoiceProviderConfig.from_env())


def get_stt_provider() -> VoiceProvider:
    """Return a VoiceProvider configured for STT from env."""
    return get_default_provider()


def get_tts_provider() -> VoiceProvider:
    """Return a VoiceProvider configured for TTS from env."""
    return get_default_provider()


__all__ = [
    "VoiceProvider",
    "VoiceProviderConfig",
    "STTResult",
    "TTSResult",
    "VoiceMetrics",
    "ProviderHealth",
    "PROVIDER_DEEPGRAM",
    "PROVIDER_FASTER_WHISPER",
    "PROVIDER_OPENAI",
    "PROVIDER_MACOS_SAY",
    "PROVIDER_NOT_CONFIGURED",
    "get_default_provider",
    "get_stt_provider",
    "get_tts_provider",
]
