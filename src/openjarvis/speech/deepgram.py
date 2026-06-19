"""Deepgram speech-to-text backend (cloud) — deepgram-sdk v6."""

from __future__ import annotations

import os
from typing import List, Optional

from openjarvis.core.registry import SpeechRegistry
from openjarvis.speech._stubs import SpeechBackend, TranscriptionResult

try:
    from deepgram import DeepgramClient
    _DEEPGRAM_AVAILABLE = True
except ImportError:
    DeepgramClient = None  # type: ignore[assignment, misc]
    _DEEPGRAM_AVAILABLE = False


@SpeechRegistry.register("deepgram")
class DeepgramSpeechBackend(SpeechBackend):
    """Cloud speech-to-text using Deepgram API (deepgram-sdk v6)."""

    backend_id = "deepgram"

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self._client = None
        if self._api_key and _DEEPGRAM_AVAILABLE:
            self._client = DeepgramClient(api_key=self._api_key)

    def transcribe(
        self,
        audio: bytes,
        *,
        format: str = "wav",
        language: Optional[str] = None,
    ) -> TranscriptionResult:
        """Transcribe audio using Deepgram's prerecorded API (v6)."""
        if self._client is None:
            raise RuntimeError(
                "Deepgram client not initialized — "
                "install deepgram-sdk and set DEEPGRAM_API_KEY"
            )

        kwargs: dict = {
            "request": audio,
            "model": "nova-2",
            "smart_format": True,
        }
        if language:
            kwargs["language"] = language
        else:
            kwargs["detect_language"] = True

        response = self._client.listen.v1.media.transcribe_file(**kwargs)

        # Extract transcript from v6 response
        text = ""
        confidence: Optional[float] = None
        detected_lang: Optional[str] = None
        duration = 0.0

        try:
            channels = response.results.channels
            if channels and channels[0].alternatives:
                alt = channels[0].alternatives[0]
                text = alt.transcript or ""
                confidence = getattr(alt, "confidence", None)
            if channels:
                detected_lang = getattr(channels[0], "detected_language", None)
        except (AttributeError, IndexError):
            pass

        try:
            duration = float(response.metadata.duration or 0.0)
        except (AttributeError, TypeError):
            pass

        return TranscriptionResult(
            text=text,
            language=detected_lang,
            confidence=confidence,
            duration_seconds=duration,
            segments=[],
        )

    def health(self) -> bool:
        return self._client is not None and bool(self._api_key)

    def supported_formats(self) -> List[str]:
        return ["wav", "mp3", "ogg", "flac", "webm", "m4a"]
