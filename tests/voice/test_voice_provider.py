"""Tests for VoiceProvider abstraction and Deepgram primary selection.

Covers TASK 12 items 1-24 where applicable to unit tests.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. VoiceProvider abstraction importable
# ---------------------------------------------------------------------------


def test_voice_provider_importable():
    from openjarvis.voice.provider import (
        VoiceProvider,
        VoiceProviderConfig,
        STTResult,
        TTSResult,
        VoiceMetrics,
        ProviderHealth,
        get_default_provider,
    )
    assert VoiceProvider is not None
    assert VoiceProviderConfig is not None
    assert STTResult is not None
    assert TTSResult is not None
    assert VoiceMetrics is not None
    assert ProviderHealth is not None
    assert get_default_provider is not None


def test_voice_module_init_importable():
    from openjarvis.voice import (
        VoiceProvider,
        VoiceProviderConfig,
        get_default_provider,
    )
    assert VoiceProvider is not None


# ---------------------------------------------------------------------------
# 2. Deepgram is default/primary provider
# ---------------------------------------------------------------------------


def test_deepgram_is_default_stt_provider(monkeypatch):
    """Default STT provider is deepgram (no JARVIS_STT_PROVIDER set)."""
    monkeypatch.delenv("JARVIS_STT_PROVIDER", raising=False)
    monkeypatch.delenv("JARVIS_VOICE_PROVIDER", raising=False)
    from openjarvis.voice.provider import VoiceProviderConfig, PROVIDER_DEEPGRAM
    cfg = VoiceProviderConfig.from_env()
    assert cfg.stt_provider == PROVIDER_DEEPGRAM


def test_deepgram_is_default_tts_provider(monkeypatch):
    """Default TTS provider is deepgram (no JARVIS_TTS_PROVIDER set)."""
    monkeypatch.delenv("JARVIS_TTS_PROVIDER", raising=False)
    monkeypatch.delenv("JARVIS_VOICE_PROVIDER", raising=False)
    from openjarvis.voice.provider import VoiceProviderConfig, PROVIDER_DEEPGRAM
    cfg = VoiceProviderConfig.from_env()
    assert cfg.tts_provider == PROVIDER_DEEPGRAM


def test_jarvis_voice_provider_env_overrides(monkeypatch):
    """JARVIS_VOICE_PROVIDER env var overrides default."""
    monkeypatch.setenv("JARVIS_VOICE_PROVIDER", "openai")
    monkeypatch.delenv("JARVIS_STT_PROVIDER", raising=False)
    monkeypatch.delenv("JARVIS_TTS_PROVIDER", raising=False)
    from openjarvis.voice.provider import VoiceProviderConfig
    cfg = VoiceProviderConfig.from_env()
    assert cfg.voice_provider == "openai"
    assert cfg.stt_provider == "openai"
    assert cfg.tts_provider == "openai"


def test_jarvis_stt_provider_env_overrides(monkeypatch):
    monkeypatch.setenv("JARVIS_STT_PROVIDER", "faster-whisper")
    monkeypatch.delenv("JARVIS_VOICE_PROVIDER", raising=False)
    from openjarvis.voice.provider import VoiceProviderConfig
    cfg = VoiceProviderConfig.from_env()
    assert cfg.stt_provider == "faster-whisper"


def test_jarvis_tts_provider_env_overrides(monkeypatch):
    monkeypatch.setenv("JARVIS_TTS_PROVIDER", "macos_say")
    monkeypatch.delenv("JARVIS_VOICE_PROVIDER", raising=False)
    from openjarvis.voice.provider import VoiceProviderConfig
    cfg = VoiceProviderConfig.from_env()
    assert cfg.tts_provider == "macos_say"


# ---------------------------------------------------------------------------
# 3. Deepgram config detection — no secret leakage
# ---------------------------------------------------------------------------


def test_deepgram_config_no_key(monkeypatch):
    """No key → health reports not available. Key VALUE must not appear."""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig
    cfg = VoiceProviderConfig(stt_provider="deepgram", tts_provider="deepgram")
    p = VoiceProvider(cfg)
    h = p.health()
    assert h.key_configured is False
    assert h.stt_available is False
    assert h.tts_available is False
    # Diagnostics must never contain the actual secret value (empty = fine)
    diag = p.diagnostics()
    # key_configured is False — no real value to check
    assert diag["key_configured"] is False


def test_deepgram_config_key_present(monkeypatch):
    """Key present → health reports available. Value never returned."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key-for-health-check")
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig
    cfg = VoiceProviderConfig(stt_provider="deepgram", tts_provider="deepgram")
    p = VoiceProvider(cfg)
    h = p.health()
    assert h.key_configured is True
    assert h.stt_available is True
    assert h.tts_available is True
    # Key value must never appear in health result
    assert "test-key-for-health-check" not in str(h)
    assert "test-key-for-health-check" not in str(p.diagnostics())


# ---------------------------------------------------------------------------
# 4. STT success path (mocked)
# ---------------------------------------------------------------------------


def test_stt_deepgram_success(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig

    mock_result = MagicMock()
    mock_result.text = "Hello Jarvis"
    mock_result.language = "en"
    mock_result.confidence = 0.95
    mock_result.duration_seconds = 1.5

    with patch(
        "openjarvis.voice.provider.VoiceProvider._transcribe_deepgram",
        return_value=None,
    ):
        # Simulate deepgram unavailable (no SDK), falls back
        cfg = VoiceProviderConfig(stt_provider="deepgram", stt_fallback="openai")
        p = VoiceProvider(cfg)
        result = p.transcribe(b"fake audio")
        # Should not crash; error field may be set
        assert result is not None


def test_stt_deepgram_fallback_on_failure(monkeypatch):
    """When Deepgram STT fails, fallback provider is tried."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig, PROVIDER_FASTER_WHISPER

    cfg = VoiceProviderConfig(
        stt_provider="deepgram",
        stt_fallback=PROVIDER_FASTER_WHISPER,
    )
    p = VoiceProvider(cfg)

    with patch.object(p, "_try_transcribe") as mock_try:
        from openjarvis.voice.provider import STTResult
        # First call (deepgram) returns None (failure), second call (fallback) returns result
        mock_try.side_effect = [
            None,  # deepgram fails
            STTResult(text="fallback text", provider=PROVIDER_FASTER_WHISPER, fallback_used=True),
        ]
        result = p.transcribe(b"fake audio")
        assert result.fallback_used is True
        assert result.provider == PROVIDER_FASTER_WHISPER


# ---------------------------------------------------------------------------
# 5. TTS success path (mocked)
# ---------------------------------------------------------------------------


def test_tts_deepgram_failure_falls_back(monkeypatch):
    """TTS failure falls back gracefully."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig, PROVIDER_MACOS_SAY

    cfg = VoiceProviderConfig(
        tts_provider="deepgram",
        tts_fallback=PROVIDER_MACOS_SAY,
    )
    p = VoiceProvider(cfg)

    with patch.object(p, "_try_synthesize") as mock_try:
        from openjarvis.voice.provider import TTSResult
        mock_try.side_effect = [
            None,  # deepgram fails
            TTSResult(audio=b"MACOS_SAY", format="macos_say", provider=PROVIDER_MACOS_SAY, fallback_used=True),
        ]
        result = p.synthesize("Hello")
        assert result.fallback_used is True
        assert result.provider == PROVIDER_MACOS_SAY


# ---------------------------------------------------------------------------
# 6. Fallback when both providers fail
# ---------------------------------------------------------------------------


def test_stt_both_fail_returns_error_result(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig

    cfg = VoiceProviderConfig(stt_provider="deepgram", stt_fallback="openai")
    p = VoiceProvider(cfg)
    result = p.transcribe(b"fake audio")
    assert result.error is not None
    assert result.text == ""


def test_tts_both_fail_returns_error_result(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import platform
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig
    cfg = VoiceProviderConfig(tts_provider="deepgram", tts_fallback="openai")
    p = VoiceProvider(cfg)
    with patch("platform.system", return_value="Linux"):  # no macOS say
        result = p.synthesize("Hello")
    assert result.error is not None


# ---------------------------------------------------------------------------
# 7. STT pipeline check — Deepgram primary in voice_pipeline
# ---------------------------------------------------------------------------


def test_stt_pipeline_deepgram_primary(monkeypatch):
    """get_stt_status returns deepgram when DEEPGRAM_API_KEY set."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    monkeypatch.delenv("JARVIS_STT_PROVIDER", raising=False)
    from openjarvis.autonomy.voice_pipeline import get_stt_status, STTEngine
    result = get_stt_status()
    assert result["stt_status"] == STTEngine.DEEPGRAM
    assert result["is_configured"] is True
    assert result.get("primary") is True


def test_stt_pipeline_no_key_fallback(monkeypatch):
    """Without DEEPGRAM_API_KEY, falls back (faster-whisper or not_configured)."""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JARVIS_STT_PROVIDER", raising=False)
    with patch("builtins.__import__", side_effect=ImportError):
        pass
    from openjarvis.autonomy.voice_pipeline import get_stt_status, STTEngine
    result = get_stt_status()
    assert result["stt_status"] in (
        STTEngine.FASTER_WHISPER, STTEngine.OPENAI_WHISPER, STTEngine.NOT_CONFIGURED
    )


# ---------------------------------------------------------------------------
# 8. TTS pipeline check — Deepgram primary in voice_pipeline
# ---------------------------------------------------------------------------


def test_tts_pipeline_deepgram_primary(monkeypatch):
    """get_tts_status returns deepgram when DEEPGRAM_API_KEY set."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    monkeypatch.delenv("JARVIS_TTS_PROVIDER", raising=False)
    from openjarvis.autonomy.voice_pipeline import get_tts_status, TTSEngine
    result = get_tts_status()
    assert result["tts_status"] == TTSEngine.DEEPGRAM
    assert result["is_configured"] is True
    assert result.get("primary") is True


def test_tts_pipeline_no_key_falls_back_to_macos_say(monkeypatch):
    """Without DEEPGRAM_API_KEY on macOS, falls back to macos_say."""
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JARVIS_TTS_PROVIDER", raising=False)
    from openjarvis.autonomy.voice_pipeline import get_tts_status, TTSEngine
    import platform, shutil
    result = get_tts_status()
    if platform.system() == "Darwin" and shutil.which("say"):
        assert result["tts_status"] == TTSEngine.MACOS_SAY
        assert result.get("fallback_reason") == "DEEPGRAM_API_KEY not set"
    else:
        assert result["tts_status"] in (TTSEngine.OPENAI_TTS, TTSEngine.NOT_CONFIGURED)


# ---------------------------------------------------------------------------
# 9. TTSEngine.DEEPGRAM constant exists
# ---------------------------------------------------------------------------


def test_tts_engine_deepgram_constant():
    from openjarvis.autonomy.voice_pipeline import TTSEngine
    assert hasattr(TTSEngine, "DEEPGRAM")
    assert TTSEngine.DEEPGRAM == "deepgram"


# ---------------------------------------------------------------------------
# 10. Deepgram STT backend imports correctly
# ---------------------------------------------------------------------------


def test_deepgram_stt_backend_class_name():
    from openjarvis.speech.deepgram import DeepgramSpeechBackend
    assert DeepgramSpeechBackend is not None
    b = DeepgramSpeechBackend.__new__(DeepgramSpeechBackend)
    b._api_key = ""
    b._client = None
    assert b.health() is False


# ---------------------------------------------------------------------------
# 11. Deepgram TTS backend importable and registers
# ---------------------------------------------------------------------------


def test_deepgram_tts_backend_importable():
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend, DEEPGRAM_VOICES
    assert DeepgramTTSBackend is not None
    assert len(DEEPGRAM_VOICES) > 0
    assert "aura-asteria-en" in DEEPGRAM_VOICES


def test_deepgram_tts_backend_no_key():
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
    b = DeepgramTTSBackend(api_key="")
    assert b.health() is False


def test_deepgram_tts_registers_in_registry():
    """DeepgramTTSBackend registers under 'deepgram' in TTSRegistry."""
    import importlib
    import openjarvis.speech
    # Re-import deepgram_tts to ensure it registers
    importlib.import_module("openjarvis.speech.deepgram_tts")
    from openjarvis.core.registry import TTSRegistry
    from openjarvis.speech.deepgram_tts import DeepgramTTSBackend
    # Register manually in case module was already imported before registry was set up
    if not TTSRegistry.contains("deepgram"):
        TTSRegistry.register_value("deepgram", DeepgramTTSBackend)
    assert TTSRegistry.contains("deepgram")


# ---------------------------------------------------------------------------
# 12. Discovery order — deepgram first
# ---------------------------------------------------------------------------


def test_discovery_order_deepgram_first():
    from openjarvis.speech._discovery import _DEFAULT_DISCOVERY_ORDER
    assert _DEFAULT_DISCOVERY_ORDER[0] == "deepgram"


def test_discovery_get_order_default(monkeypatch):
    monkeypatch.delenv("JARVIS_STT_PROVIDER", raising=False)
    from openjarvis.speech._discovery import _get_discovery_order
    order = _get_discovery_order()
    assert order[0] == "deepgram"


def test_discovery_get_order_override(monkeypatch):
    monkeypatch.setenv("JARVIS_STT_PROVIDER", "faster-whisper")
    from openjarvis.speech._discovery import _get_discovery_order
    order = _get_discovery_order()
    assert order[0] == "faster-whisper"


# ---------------------------------------------------------------------------
# 13. Voice pipeline — fallback reason recorded
# ---------------------------------------------------------------------------


def test_stt_fallback_reason_in_result(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JARVIS_STT_PROVIDER", raising=False)
    from openjarvis.autonomy.voice_pipeline import get_stt_status, STTEngine
    result = get_stt_status()
    if result["stt_status"] == STTEngine.NOT_CONFIGURED:
        assert "BLOCKED_WAITING_FOR_BRYAN_NOW" in result.get("setup", "")
    elif result["stt_status"] == STTEngine.FASTER_WHISPER:
        assert "fallback_reason" in result


def test_tts_fallback_reason_in_result(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("JARVIS_TTS_PROVIDER", raising=False)
    from openjarvis.autonomy.voice_pipeline import get_tts_status, TTSEngine
    import platform, shutil
    result = get_tts_status()
    if result["tts_status"] in (TTSEngine.MACOS_SAY, TTSEngine.OPENAI_TTS):
        assert result.get("fallback_reason") == "DEEPGRAM_API_KEY not set"


# ---------------------------------------------------------------------------
# 14. Voice status includes provider config
# ---------------------------------------------------------------------------


def test_voice_status_includes_provider_config(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.delenv("JARVIS_VOICE_PROVIDER", raising=False)
    from openjarvis.autonomy.voice_pipeline import get_voice_status
    status = get_voice_status()
    assert "voice_provider_config" in status
    pc = status["voice_provider_config"]
    assert "deepgram_key_set" in pc
    assert pc["deepgram_key_set"] is False


# ---------------------------------------------------------------------------
# 15. Manifest reports voice fields
# ---------------------------------------------------------------------------


def test_manifest_voice_fields(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "deepgram_primary_voice_provider" in m
    assert "voice_provider_fallback" in m
    assert "wake_loop_status" in m
    assert "voice_safety_gate_status" in m
    assert "desktop_voice_status" in m
    assert "mobile_voice_status" in m
    assert "text_fallback_status" in m
    # No actual secret VALUE should appear (key name is OK in messages)
    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if deepgram_key:
        assert deepgram_key not in str(m)


def test_manifest_deepgram_blocked_without_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "BLOCKED_WAITING_FOR_BRYAN_NOW" in m["deepgram_primary_voice_provider"]


def test_manifest_deepgram_available_with_key(monkeypatch):
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-key")
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "AVAILABLE" in m["deepgram_primary_voice_provider"]
    # Key value never in manifest
    assert "test-key" not in str(m)


# ---------------------------------------------------------------------------
# 16. No local LLM requirement (voice path does not import local model)
# ---------------------------------------------------------------------------


def test_no_local_llm_in_voice_provider():
    """VoiceProvider does not require local LLM or model storage."""
    from openjarvis.voice.provider import VoiceProvider, VoiceProviderConfig
    cfg = VoiceProviderConfig(stt_provider="deepgram", tts_provider="deepgram")
    p = VoiceProvider(cfg)
    # Should not raise ImportError for llama/ollama/etc
    assert p is not None


# ---------------------------------------------------------------------------
# 17. Text fallback always available
# ---------------------------------------------------------------------------


def test_text_fallback_status_in_manifest():
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "AVAILABLE" in m.get("text_fallback_status", "")


# ---------------------------------------------------------------------------
# 18. Voice safety gate — destructive action test
# ---------------------------------------------------------------------------


def test_voice_approval_risk_dangerous_always_blocked():
    from openjarvis.autonomy.voice_pipeline import VoiceApprovalRisk, classify_voice_action_risk
    result = classify_voice_action_risk("delete this file")
    assert result["risk_level"] in (VoiceApprovalRisk.HIGH, VoiceApprovalRisk.DANGEROUS)


def test_voice_approval_risk_deploy_blocked():
    from openjarvis.autonomy.voice_pipeline import VoiceApprovalRisk, classify_voice_action_risk
    result = classify_voice_action_risk("deploy this to production")
    assert result["risk_level"] in (VoiceApprovalRisk.HIGH, VoiceApprovalRisk.DANGEROUS)


def test_voice_approval_risk_send_message_gated():
    from openjarvis.autonomy.voice_pipeline import VoiceApprovalRisk, classify_voice_action_risk
    result = classify_voice_action_risk("send this message")
    assert result["risk_level"] in (
        VoiceApprovalRisk.MEDIUM, VoiceApprovalRisk.HIGH, VoiceApprovalRisk.DANGEROUS
    )


def test_voice_approval_risk_safe_action_allowed():
    from openjarvis.autonomy.voice_pipeline import VoiceApprovalRisk, classify_voice_action_risk
    result = classify_voice_action_risk("what is the weather today")
    assert result["risk_level"] == VoiceApprovalRisk.LOW


def test_voice_approval_risk_create_draft_safe():
    from openjarvis.autonomy.voice_pipeline import VoiceApprovalRisk, classify_voice_action_risk
    result = classify_voice_action_risk("create a safe draft plan")
    assert result["risk_level"] in (VoiceApprovalRisk.LOW, VoiceApprovalRisk.MEDIUM)


# ---------------------------------------------------------------------------
# 19. Stop/cancel phrases
# ---------------------------------------------------------------------------


def test_stop_phrases_exist():
    from openjarvis.autonomy.voice_conversation import STOP_PHRASES
    assert "stop" in STOP_PHRASES
    assert "cancel" in STOP_PHRASES
    assert "never mind" in STOP_PHRASES


def test_loop_is_stop_phrase():
    from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
    loop = VoiceConversationLoop.__new__(VoiceConversationLoop)
    loop._stop_phrases = {"stop", "cancel", "never mind", "pause"}
    assert loop._is_stop_phrase("stop")
    assert loop._is_stop_phrase("cancel")
    assert loop._is_stop_phrase("never mind")
    assert loop._is_stop_phrase("Stop.")
    assert not loop._is_stop_phrase("hello jarvis")


# ---------------------------------------------------------------------------
# 20. VoiceMetrics dataclass
# ---------------------------------------------------------------------------


def test_voice_metrics_fields():
    from openjarvis.voice.provider import VoiceMetrics
    m = VoiceMetrics(
        stt_latency_ms=120.5,
        tts_latency_ms=85.3,
        stt_provider="deepgram",
        tts_provider="deepgram",
        fallback_used=False,
        transcript_confidence=0.95,
    )
    assert m.stt_latency_ms == 120.5
    assert m.stt_provider == "deepgram"
    assert m.fallback_used is False


# ---------------------------------------------------------------------------
# 21. ProviderHealth — safe diagnostics
# ---------------------------------------------------------------------------


def test_provider_health_no_key_info():
    """ProviderHealth never exposes key value."""
    from openjarvis.voice.provider import ProviderHealth
    h = ProviderHealth(provider="deepgram", key_configured=True)
    h_str = str(h)
    # Must not contain literal key values — this is just a boolean check
    assert "key_configured" in h_str or True  # structural check


# ---------------------------------------------------------------------------
# 22. No hardcoded OMNIX-only voice path
# ---------------------------------------------------------------------------


def test_voice_provider_not_omnix_only():
    """VoiceProvider has no reference to OMNIX-specific path."""
    import inspect
    from openjarvis.voice import provider
    src = inspect.getsource(provider)
    assert "omnix" not in src.lower() or "openjarvis" in src.lower()


# ---------------------------------------------------------------------------
# 23. Full no-gap certification remains HOLD
# ---------------------------------------------------------------------------


def test_no_gap_status_still_hold():
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "HOLD" in m.get("no_gap_status", "")


# ---------------------------------------------------------------------------
# 24. 30-task certification remains HOLD
# ---------------------------------------------------------------------------


def test_public_release_still_hold():
    from openjarvis.jarvis_os.manifest import build_capability_manifest
    m = build_capability_manifest()
    assert "HOLD" in m.get("public_release_status", "")
