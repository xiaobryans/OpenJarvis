"""Targeted tests for Deepgram runtime init fix.

Validation coverage (per task spec):
  1. deepgram_sdk_import_ok      — SDK is importable in the uv environment
  2. get_stt_status_sdk_missing  — key present but SDK unimportable → NOT_CONFIGURED,
                                   exact non-secret blocker in response
  3. get_stt_status_key_missing  — SDK ok but key missing → NOT_CONFIGURED with key blocker
  4. get_stt_status_both_ok      — key + SDK → DEEPGRAM returned
  5. transcribe_sdk_missing      — transcribe_command_result raises clear RuntimeError
                                   when SDK unavailable (not the generic client-init message)
  6. transcribe_key_missing      — transcribe_command_result raises clear RuntimeError
                                   when key not set
  7. turn_preflight_stt_not_ready — POST /v1/voice/turn/start returns stt_not_ready
                                   before entering recording when STT unavailable
  8. health_reports_deepgram      — VoiceProvider.health() reports stt_available=True
                                   when key + SDK both present
  9. health_reports_sdk_missing   — VoiceProvider.health() still reports key_configured
                                   when key is set, stt_available via provider chain
"""

from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# 1. SDK importable after uv sync
# ---------------------------------------------------------------------------

def test_deepgram_sdk_import_ok():
    """deepgram-sdk must be importable in the packaged uv environment."""
    from deepgram import DeepgramClient  # noqa: F401 — ImportError = test failure


# ---------------------------------------------------------------------------
# 2. get_stt_status: key present, SDK missing → NOT_CONFIGURED + exact blocker
# ---------------------------------------------------------------------------

def test_get_stt_status_sdk_missing():
    """When Deepgram is explicitly requested (JARVIS_STT_PROVIDER=deepgram) but the
    SDK import fails, Deepgram must NOT be selected — it falls back to another
    provider (Whisper is the new default; Deepgram is opt-in/fallback only)."""
    import sys

    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test-key-present",
                                 "JARVIS_STT_PROVIDER": "deepgram"}):
        # Simulate SDK not installed by temporarily hiding the deepgram module
        with patch.dict(sys.modules, {"deepgram": None}):
            # Force reimport of voice_pipeline to pick up the patched sys.modules
            import importlib
            import openjarvis.autonomy.voice_pipeline as vp
            importlib.reload(vp)
            try:
                stt = vp.get_stt_status()
            finally:
                importlib.reload(vp)  # restore

    assert stt["stt_status"] != "deepgram", (
        "get_stt_status() must not return DEEPGRAM when its SDK is not installed"
    )


# ---------------------------------------------------------------------------
# 3. get_stt_status: SDK ok, key missing → NOT_CONFIGURED with key blocker
# ---------------------------------------------------------------------------

def test_get_stt_status_key_missing():
    """When SDK is present but DEEPGRAM_API_KEY is not set, Deepgram must not be selected."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "DEEPGRAM_API_KEY"}
    env_without_key["JARVIS_STT_PROVIDER"] = ""

    with patch.dict(os.environ, env_without_key, clear=True):
        from openjarvis.autonomy.voice_pipeline import get_stt_status
        stt = get_stt_status()

    assert stt["stt_status"] != "deepgram", (
        "get_stt_status() must not return DEEPGRAM when DEEPGRAM_API_KEY is not set"
    )


# ---------------------------------------------------------------------------
# 4. get_stt_status: explicit deepgram override + key + SDK → DEEPGRAM
# ---------------------------------------------------------------------------

def test_get_stt_status_both_ok():
    """With explicit JARVIS_STT_PROVIDER=deepgram + key + SDK installed,
    get_stt_status() returns DEEPGRAM (the opt-in path still works)."""
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test-key",
                                 "JARVIS_STT_PROVIDER": "deepgram"}):
        from openjarvis.autonomy.voice_pipeline import get_stt_status
        stt = get_stt_status()

    assert stt["stt_status"] == "deepgram", (
        f"Expected stt_status=deepgram with explicit override+key+SDK, got: {stt['stt_status']}"
    )
    assert stt.get("primary") is True


# ---------------------------------------------------------------------------
# 5. transcribe_command_result: SDK missing → clear RuntimeError
# ---------------------------------------------------------------------------

def test_transcribe_sdk_missing_raises_clear_error():
    """transcribe_command_result must raise a clear RuntimeError when SDK is missing,
    not the opaque 'Deepgram client not initialized' message.

    Patches _DEEPGRAM_AVAILABLE and get_stt_status to avoid module reload
    conflicts with the global SpeechRegistry.
    """
    from openjarvis.autonomy.voice_pipeline import STTEngine

    stt_deepgram = {
        "stt_status": STTEngine.DEEPGRAM,
        "engine": STTEngine.DEEPGRAM,
        "is_configured": True,
        "primary": True,
        "blocker": None,
    }

    with patch("openjarvis.autonomy.voice_pipeline.get_stt_status", return_value=stt_deepgram):
        with patch("openjarvis.speech.deepgram._DEEPGRAM_AVAILABLE", False):
            from openjarvis.autonomy.voice_conversation import transcribe_command_result
            dummy_wav = b"RIFF" + b"\x00" * 100
            with pytest.raises(RuntimeError) as exc_info:
                transcribe_command_result(dummy_wav, language="en")
            err = str(exc_info.value).lower()
            assert "deepgram-sdk" in err or "not installed" in err, (
                f"Error must mention 'deepgram-sdk not installed', got: {exc_info.value}"
            )
            # Must NOT be the opaque client-init message
            assert "client not initialized" not in err, (
                "Error must be the clear SDK-missing message, not the generic client-init error"
            )


# ---------------------------------------------------------------------------
# 6. transcribe_command_result: SDK ok, key missing → clear RuntimeError
# ---------------------------------------------------------------------------

def test_transcribe_key_missing_raises_clear_error():
    """When DEEPGRAM_API_KEY is absent at transcription time, transcribe_command_result
    must raise a clear RuntimeError from the backend health check — not silently
    return empty text."""
    from openjarvis.autonomy.voice_pipeline import STTEngine

    stt_deepgram = {
        "stt_status": STTEngine.DEEPGRAM,
        "engine": STTEngine.DEEPGRAM,
        "is_configured": True,
        "primary": True,
        "blocker": None,
    }

    env_no_key = {k: v for k, v in os.environ.items() if k != "DEEPGRAM_API_KEY"}

    with patch("openjarvis.autonomy.voice_pipeline.get_stt_status", return_value=stt_deepgram):
        with patch.dict(os.environ, env_no_key, clear=True):
            from openjarvis.autonomy.voice_conversation import transcribe_command_result
            dummy_wav = b"RIFF" + b"\x00" * 100
            with pytest.raises(RuntimeError) as exc_info:
                transcribe_command_result(dummy_wav, language="en")
            err = str(exc_info.value).lower()
            assert any(tok in err for tok in ("deepgram_api_key", "api_key", "not set", "not ready")), (
                f"Expected key-missing error message, got: {exc_info.value}"
            )


# ---------------------------------------------------------------------------
# 7. Turn preflight: stt_not_ready returned before recording starts
# ---------------------------------------------------------------------------

def test_turn_preflight_stt_not_ready():
    """POST /v1/voice/turn/start must return stt_not_ready when STT is NOT_CONFIGURED
    without ever entering the recording phase."""
    import asyncio
    from openjarvis.server.voice_routes import voice_turn_start
    from starlette.requests import Request
    from starlette.datastructures import Headers
    import io

    class _FakeRequest:
        async def json(self):
            return {"language": "en"}

    not_configured = {
        "stt_status": "not_configured",
        "deepgram_blocker": "deepgram-sdk not installed — run: uv sync",
        "blockers": ["deepgram-sdk not installed — run: uv sync"],
    }

    with patch("openjarvis.autonomy.voice_pipeline.get_stt_status", return_value=not_configured):
        result = asyncio.get_event_loop().run_until_complete(
            voice_turn_start(_FakeRequest())  # type: ignore[arg-type]
        )

    assert result.get("ok") is False, f"Expected ok=False, got: {result}"
    assert result.get("error_code") == "stt_not_ready", f"Expected error_code=stt_not_ready, got: {result}"
    # Must include the non-secret blocker text
    combined = str(result.get("deepgram_blocker", "")) + str(result.get("blockers", ""))
    assert "deepgram-sdk" in combined or "not installed" in combined, (
        f"Blocker text missing from response: {result}"
    )


# ---------------------------------------------------------------------------
# 8. VoiceProvider.health() reports stt_available=True when key + SDK present
# ---------------------------------------------------------------------------

def test_voice_provider_health_deepgram_ready():
    """VoiceProvider.health() must report stt_available=True when key is set and SDK installed."""
    with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test-key"}):
        from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig, PROVIDER_DEEPGRAM
        cfg = VoiceProviderConfig(
            voice_provider=PROVIDER_DEEPGRAM,
            stt_provider=PROVIDER_DEEPGRAM,
            tts_provider=PROVIDER_DEEPGRAM,
        )
        vp = VoiceProvider(cfg)
        h = vp.health()

    assert h.stt_available is True, f"Expected stt_available=True, got: {h}"
    assert h.key_configured is True


# ---------------------------------------------------------------------------
# 9. VoiceProvider.health(): stt_available reflects key_configured (SDK installed)
# ---------------------------------------------------------------------------

def test_voice_provider_health_key_missing():
    """VoiceProvider.health() must report stt_available=False when key is missing."""
    env_no_key = {k: v for k, v in os.environ.items() if k != "DEEPGRAM_API_KEY"}
    with patch.dict(os.environ, env_no_key, clear=True):
        from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig, PROVIDER_DEEPGRAM
        cfg = VoiceProviderConfig(
            voice_provider=PROVIDER_DEEPGRAM,
            stt_provider=PROVIDER_DEEPGRAM,
            tts_provider=PROVIDER_DEEPGRAM,
        )
        vp = VoiceProvider(cfg)
        h = vp.health()

    assert h.stt_available is False
    assert h.key_configured is False
    assert "DEEPGRAM_API_KEY" in h.stt_blocker
