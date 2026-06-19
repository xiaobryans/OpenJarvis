"""Tests for Deepgram TTS backend (deepgram-sdk v6)."""

from unittest.mock import MagicMock, patch

import pytest

from openjarvis.core.registry import TTSRegistry
from openjarvis.speech.tts import TTSResult


@pytest.fixture(autouse=True)
def _register_deepgram_tts():
    """Ensure DeepgramTTSBackend is registered."""
    import importlib, openjarvis.speech
    importlib.import_module("openjarvis.speech.deepgram_tts")
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
    if not TTSRegistry.contains("deepgram"):
        TTSRegistry.register_value("deepgram", DeepgramTTSBackend)


def test_deepgram_tts_registers():
    assert TTSRegistry.contains("deepgram")


def test_deepgram_tts_health_no_key():
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
    b = DeepgramTTSBackend(api_key="")
    assert b.health() is False


def test_deepgram_tts_health_with_key():
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
    with patch("openjarvis.speech.deepgram_tts.DeepgramClient"):
        b = DeepgramTTSBackend(api_key="test-key")
        assert b.health() is True


def test_deepgram_tts_synthesize():
    """Test TTS synthesis with mocked v6 API (speak.v1.audio.generate returns Iterator[bytes])."""
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend

    mock_client = MagicMock()
    fake_audio = b"fake mp3 audio content"
    # v6 API: client.speak.v1.audio.generate(text=..., model=..., encoding=...) -> Iterator[bytes]
    mock_client.speak.v1.audio.generate.return_value = iter([fake_audio])

    with patch("openjarvis.speech.deepgram_tts.DeepgramClient", return_value=mock_client):
        b = DeepgramTTSBackend(api_key="test-key")
        result = b.synthesize("Hello Jarvis")

    assert isinstance(result, TTSResult)
    assert result.audio == fake_audio
    assert result.voice_id == "aura-asteria-en"
    assert result.format == "mp3"
    assert result.metadata.get("provider") == "deepgram"


def test_deepgram_tts_available_voices():
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend, DEEPGRAM_VOICES
    b = DeepgramTTSBackend(api_key="")
    voices = b.available_voices()
    assert "aura-asteria-en" in voices
    assert len(voices) >= 12


def test_deepgram_tts_supported_formats():
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
    b = DeepgramTTSBackend(api_key="")
    assert "mp3" in b.supported_formats()
    assert "wav" in b.supported_formats()
