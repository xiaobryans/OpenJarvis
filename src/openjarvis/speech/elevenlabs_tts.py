"""ElevenLabs TTS backend — natural cloud voice synthesis.

Wired for VANTA voice responses. Reads ELEVENLABS_API_KEY. Returns real MP3
audio bytes for given text via the ElevenLabs HTTP API.
"""

from __future__ import annotations

import os
from typing import List

import httpx

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSBackend, TTSResult

_API_BASE = "https://api.elevenlabs.io/v1"
# A natural default voice ("Rachel"); override via voice_id or
# ELEVENLABS_VOICE_ID. Model: multilingual v2 for quality, or turbo for latency.
_DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"
_DEFAULT_MODEL = "eleven_turbo_v2_5"


@TTSRegistry.register("elevenlabs")
class ElevenLabsTTSBackend(TTSBackend):
    """Cloud TTS via ElevenLabs."""

    backend_id = "elevenlabs"

    def __init__(self, *, api_key: str = "", model: str = "") -> None:
        self._api_key = api_key or os.environ.get("ELEVENLABS_API_KEY", "")
        self._model = model or os.environ.get("ELEVENLABS_MODEL", _DEFAULT_MODEL)

    def synthesize(
        self,
        text: str,
        *,
        voice_id: str = "",
        speed: float = 1.0,
        output_format: str = "mp3",
    ) -> TTSResult:
        if not self._api_key:
            raise RuntimeError("ELEVENLABS_API_KEY not set")
        vid = voice_id or os.environ.get("ELEVENLABS_VOICE_ID", _DEFAULT_VOICE)
        try:
            with httpx.Client(timeout=60) as c:
                r = c.post(
                    f"{_API_BASE}/text-to-speech/{vid}",
                    headers={
                        "xi-api-key": self._api_key,
                        "accept": "audio/mpeg",
                        "content-type": "application/json",
                    },
                    json={
                        "text": text,
                        "model_id": self._model,
                        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                    },
                )
                r.raise_for_status()
                audio = r.content
        except Exception as exc:
            raise RuntimeError(f"ElevenLabs TTS failed: {exc}") from exc
        return TTSResult(
            audio=audio, format="mp3", voice_id=vid,
            metadata={"backend": "elevenlabs", "model": self._model},
        )

    def available_voices(self) -> List[str]:
        """Real voice list from the account (best-effort)."""
        if not self._api_key:
            return [_DEFAULT_VOICE]
        try:
            with httpx.Client(timeout=20) as c:
                r = c.get(f"{_API_BASE}/voices",
                          headers={"xi-api-key": self._api_key})
                r.raise_for_status()
                return [v.get("voice_id", "") for v in r.json().get("voices", [])]
        except Exception:
            return [_DEFAULT_VOICE]

    def health(self) -> bool:
        return bool(self._api_key)


__all__ = ["ElevenLabsTTSBackend"]
