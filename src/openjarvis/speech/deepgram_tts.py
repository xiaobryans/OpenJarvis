"""Deepgram text-to-speech backend (cloud).

Uses the Deepgram Aura TTS API to synthesize speech.
Deepgram is the primary/default TTS provider for Jarvis Voice Safety Sprint.

Fallback: macOS 'say' command or OpenAI TTS if Deepgram is unavailable.
"""

from __future__ import annotations

import io
import os
from typing import List, Optional

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

try:
    from deepgram import DeepgramClient, SpeakOptions
except ImportError:
    DeepgramClient = None  # type: ignore[assignment, misc]
    SpeakOptions = None  # type: ignore[assignment, misc]

# Deepgram Aura voice model IDs (subset — full list at deepgram.com/docs)
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
]

_DEFAULT_VOICE = "aura-asteria-en"
_DEFAULT_FORMAT = "mp3"


@TTSRegistry.register("deepgram")
class DeepgramTTSBackend(TTSBackend):
    """Cloud text-to-speech using Deepgram Aura API."""

    backend_id = "deepgram"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = None
        if self._api_key and DeepgramClient is not None:
            self._client = DeepgramClient(self._api_key)

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = _DEFAULT_FORMAT,
    ) -> TTSResult:
        """Synthesize text using Deepgram Aura TTS."""
        if self._client is None:
            raise RuntimeError(
                "Deepgram TTS client not initialized (missing DEEPGRAM_API_KEY?)"
            )

        voice = voice_id or _DEFAULT_VOICE
        if voice not in DEEPGRAM_VOICES:
            voice = _DEFAULT_VOICE

        # Deepgram SDK: speak.rest returns audio bytes
        speak_kwargs = {"text": text}
        if SpeakOptions is not None:
            options = SpeakOptions(model=voice, encoding=output_format)
        else:
            options = {"model": voice, "encoding": output_format}

        response = self._client.speak.rest.v("1").save_to_buffer(
            speak_kwargs, options
        )

        # response is a buffer-like or bytes object from deepgram SDK
        if hasattr(response, "stream_memory"):
            audio_bytes = response.stream_memory.getvalue()
        elif hasattr(response, "stream"):
            audio_bytes = response.stream.read()
        elif isinstance(response, (bytes, bytearray)):
            audio_bytes = bytes(response)
        else:
            # Fallback: try to read as file-like
            buf = io.BytesIO()
            for chunk in response.iter_content(chunk_size=4096):  # type: ignore[union-attr]
                buf.write(chunk)
            audio_bytes = buf.getvalue()

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
