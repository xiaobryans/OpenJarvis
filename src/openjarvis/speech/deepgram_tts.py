"""Deepgram text-to-speech backend (cloud) — deepgram-sdk v6.

Uses the Deepgram Aura TTS API via deepgram-sdk v6.
Deepgram is the primary/default TTS provider for Jarvis Voice Safety Sprint.

Fallback: macOS 'say' command or OpenAI TTS if Deepgram is unavailable.

Install: uv sync --extra speech-deepgram
"""

from __future__ import annotations

import os
from typing import List, Optional

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

try:
    from deepgram import DeepgramClient
    _DEEPGRAM_AVAILABLE = True
except ImportError:
    DeepgramClient = None  # type: ignore[assignment, misc]
    _DEEPGRAM_AVAILABLE = False

# Deepgram Aura voice model IDs (v6 supported models)
DEEPGRAM_VOICES: List[str] = [
    "aura-asteria-en",   # default — clear US female
    "aura-luna-en",
    "aura-stella-en",
    "aura-athena-en",
    "aura-hera-en",
    "aura-orion-en",
    "aura-arcas-en",
    "aura-perseus-en",
    "aura-angus-en",
    "aura-orpheus-en",
    "aura-helios-en",
    "aura-zeus-en",
    # Aura-2 voices (v6)
    "aura-2-asteria-en",
    "aura-2-zeus-en",
]

_DEFAULT_VOICE = "aura-asteria-en"
_DEFAULT_FORMAT = "mp3"

# Encoding map for Deepgram v6 API
_FORMAT_TO_ENCODING = {
    "mp3": "mp3",
    "wav": "linear16",
    "ogg": "opus",
    "flac": "flac",
    "aac": "aac",
    "opus": "opus",
}


@TTSRegistry.register("deepgram")
class DeepgramTTSBackend(TTSBackend):
    """Cloud text-to-speech using Deepgram Aura API (deepgram-sdk v6)."""

    backend_id = "deepgram"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = None
        if self._api_key and _DEEPGRAM_AVAILABLE:
            self._client = DeepgramClient(api_key=self._api_key)

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = _DEFAULT_FORMAT,
    ) -> TTSResult:
        """Synthesize text using Deepgram Aura TTS (v6 API)."""
        if self._client is None:
            raise RuntimeError(
                "Deepgram TTS client not initialized — "
                "install deepgram-sdk and set DEEPGRAM_API_KEY"
            )

        voice = voice_id or _DEFAULT_VOICE
        if voice not in DEEPGRAM_VOICES:
            voice = _DEFAULT_VOICE

        encoding = _FORMAT_TO_ENCODING.get(output_format, "mp3")

        # v6 API: client.speak.v1.audio.generate() returns Iterator[bytes]
        audio_chunks: List[bytes] = []
        for chunk in self._client.speak.v1.audio.generate(
            text=text,
            model=voice,
            encoding=encoding,
        ):
            if chunk:
                audio_chunks.append(chunk)

        audio_bytes = b"".join(audio_chunks)

        return TTSResult(
            audio=audio_bytes,
            format=output_format,
            voice_id=voice,
            metadata={"provider": "deepgram", "model": voice},
        )

    def available_voices(self) -> List[str]:
        return list(DEEPGRAM_VOICES)

    def health(self) -> bool:
        return self._client is not None and bool(self._api_key)

    def supported_formats(self) -> List[str]:
        return ["mp3", "wav", "ogg", "flac", "aac", "opus"]
