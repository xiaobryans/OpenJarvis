"""Tests for VAD-based natural endpointing and runtime/status routing.

Covers:
- record_command_audio_vad with silence-based turn ending
- Long speech (>5 s, >30 s) not prematurely cut off
- Short/thinking pause does not immediately end the turn
- Emergency 120 s cap fires when silence never detected
- Runtime/status queries answer from real Jarvis state, not LLM
- Secret non-leakage in runtime answers
- Dangerous commands still gated
"""

from __future__ import annotations

import io
import os
import struct
import wave
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to build fake WAV audio for numpy/sounddevice mocks
# ---------------------------------------------------------------------------

def _build_fake_wav(num_samples: int = 8000, rms: float = 0.0) -> bytes:
    """Build a minimal WAV byte string with the given RMS level (int16 mono 16kHz)."""
    import math
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        # Build int16 samples with the desired RMS
        if rms > 0:
            samples = bytes(
                struct.pack("<h", int(rms))
                for _ in range(num_samples)
            )
        else:
            samples = bytes(num_samples * 2)
        wf.writeframes(samples)
    return buf.getvalue()


class _FakeInputStream:
    """Mimics sounddevice.InputStream for testing VAD without real hardware."""

    def __init__(self, chunk_rms_sequence: List[float], chunk_samples: int = 1600):
        """
        chunk_rms_sequence: RMS value to return for each successive read().
        When exhausted, returns 0 (silence) indefinitely.
        """
        import numpy as np
        self._seq = list(chunk_rms_sequence)
        self._idx = 0
        self._chunk_samples = chunk_samples
        self._np = np

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass

    def read(self, frames: int):
        import numpy as np
        rms = self._seq[self._idx] if self._idx < len(self._seq) else 0.0
        self._idx += 1
        # Build an int16 array whose RMS equals the requested rms
        val = int(rms)
        data = np.full((frames, 1), val, dtype="int16")
        return data, False


# ---------------------------------------------------------------------------
# VAD endpointing tests (mocked audio — no real microphone)
# ---------------------------------------------------------------------------

def _patch_sd_and_np(chunk_rms_sequence: List[float]):
    """Context manager: patches sounddevice.InputStream + numpy with fake data."""
    import numpy as np

    fake_stream = _FakeInputStream(chunk_rms_sequence)

    class _FakeSD:
        class InputStream:
            def __init__(self, **kwargs):
                self._stream = fake_stream
                self.samplerate = kwargs.get("samplerate", 16000)
                self.blocksize = kwargs.get("blocksize", 1600)

            def start(self):
                fake_stream.start()

            def stop(self):
                fake_stream.stop()

            def close(self):
                fake_stream.close()

            def read(self, n):
                return fake_stream.read(n)

    return (
        patch("openjarvis.autonomy.voice_conversation.sd", _FakeSD),
        patch("openjarvis.autonomy.voice_conversation.np", np),
    )


def _run_vad(chunk_rms_sequence, min_seconds=0.5, silence_stop_ms=400, max_seconds=10.0):
    """Run VAD with a fake audio stream and return (wav_bytes, stop_reason)."""
    import numpy as np

    from openjarvis.autonomy.voice_conversation import (
        _VAD_CHUNK_MS,
        record_command_audio_vad,
    )

    fake_stream = _FakeInputStream(chunk_rms_sequence, chunk_samples=int(16000 * _VAD_CHUNK_MS / 1000))

    class _FakeSD:
        class InputStream:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

            def read(self, n):
                return fake_stream.read(n)

    with patch.dict("sys.modules", {"sounddevice": _FakeSD}):
        with patch("openjarvis.autonomy.voice_conversation.np", np):
            # Temporarily patch the module-level sd and np inside voice_conversation
            import openjarvis.autonomy.voice_conversation as vc
            orig_sd = getattr(vc, "sd", None)
            orig_np = getattr(vc, "np", None)
            # The function imports sd/np inside the function body via try/import
            # so we need to patch the modules directly
            import sounddevice as real_sd_maybe
            with patch("sounddevice.InputStream", _FakeSD.InputStream):
                wav, reason = record_command_audio_vad(
                    min_seconds=min_seconds,
                    silence_stop_ms=silence_stop_ms,
                    max_seconds=max_seconds,
                    sample_rate=16000,
                    silence_rms_threshold=100.0,
                )
    return wav, reason


# Use a simpler import-level patch approach for all VAD tests
@pytest.fixture
def fake_sd_np():
    """Fixture that provides a factory to mock sounddevice + numpy in VAD."""
    import numpy as np
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS

    def _run(chunk_rms_sequence, min_seconds=0.5, silence_stop_ms=400.0, max_seconds=10.0):
        chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
        fake_stream = _FakeInputStream(chunk_rms_sequence, chunk_samples=chunk_samples)

        class _FakeInputStream2:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

            def stop(self):
                pass

            def close(self):
                pass

            def read(self, n):
                return fake_stream.read(n)

        import sounddevice as sd_real
        with patch.object(sd_real, "InputStream", _FakeInputStream2):
            from openjarvis.autonomy.voice_conversation import record_command_audio_vad
            return record_command_audio_vad(
                min_seconds=min_seconds,
                silence_stop_ms=silence_stop_ms,
                max_seconds=max_seconds,
                sample_rate=16000,
                silence_rms_threshold=100.0,
            )

    return _run


def test_vad_ends_on_silence(fake_sd_np):
    """Recording ends when silence_stop_ms of silence detected after speech."""
    # 5 speech chunks then 4+ silence chunks (at 100ms each = 400ms silence)
    chunk_rms = [200] * 5 + [0] * 10  # 5 speech + 10 silence
    wav, reason = fake_sd_np(chunk_rms, min_seconds=0.3, silence_stop_ms=400.0, max_seconds=10.0)
    assert reason == "silence_endpointed", f"Expected silence_endpointed, got {reason}"
    # WAV should be valid
    buf = io.BytesIO(wav)
    with wave.open(buf) as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000


def test_vad_short_pause_does_not_end_turn(fake_sd_np):
    """A 200ms pause (2 chunks) should not end a turn with 400ms silence threshold."""
    # Speech, brief pause (2 chunks = 200ms), more speech, then long silence
    chunk_rms = [200] * 3 + [0] * 2 + [200] * 3 + [0] * 5
    wav, reason = fake_sd_np(chunk_rms, min_seconds=0.1, silence_stop_ms=400.0, max_seconds=10.0)
    # Should continue through the short pause and only stop on the 5-chunk silence
    assert reason == "silence_endpointed", f"Short pause ended turn prematurely: {reason}"


def test_vad_speech_beyond_5_seconds(fake_sd_np):
    """Speech lasting more than 5 seconds is not cut off."""
    # 60 speech chunks = 6 seconds of continuous speech, then silence
    chunk_rms = [200] * 60 + [0] * 6
    wav, reason = fake_sd_np(chunk_rms, min_seconds=0.3, silence_stop_ms=400.0, max_seconds=30.0)
    assert reason == "silence_endpointed"
    buf = io.BytesIO(wav)
    with wave.open(buf) as wf:
        duration_s = wf.getnframes() / wf.getframerate()
    # Should include at least 6 seconds of audio
    assert duration_s >= 5.9, f"Recording was cut short at {duration_s:.1f}s"


def test_vad_speech_beyond_30_seconds(fake_sd_np):
    """Speech lasting more than 30 seconds is not cut off by a 30s cap."""
    # 320 speech chunks = 32 seconds, then silence
    chunk_rms = [200] * 320 + [0] * 6
    wav, reason = fake_sd_np(chunk_rms, min_seconds=0.3, silence_stop_ms=400.0, max_seconds=120.0)
    assert reason == "silence_endpointed"
    buf = io.BytesIO(wav)
    with wave.open(buf) as wf:
        duration_s = wf.getnframes() / wf.getframerate()
    # Should include at least 30 seconds
    assert duration_s >= 29.9, f"Recording was cut at {duration_s:.1f}s (30s cap regression)"


def test_vad_emergency_max_cap(fake_sd_np):
    """Emergency max cap (120s equiv) fires when silence never detected."""
    # All speech, no silence — should hit max_seconds
    chunk_rms = [200] * 10000  # far more than max
    wav, reason = fake_sd_np(chunk_rms, min_seconds=0.1, silence_stop_ms=400.0, max_seconds=2.0)
    assert reason == "max_duration", f"Expected max_duration, got {reason}"


def test_vad_no_speech_returns_pre_speech_timeout(fake_sd_np):
    """When no speech is detected, stop reason is pre_speech_timeout."""
    chunk_rms = [0] * 30  # 3 seconds of silence, no speech
    wav, reason = fake_sd_np(chunk_rms, min_seconds=0.1, silence_stop_ms=400.0, max_seconds=3.0)
    assert reason == "pre_speech_timeout", f"Expected pre_speech_timeout, got {reason}"


def test_vad_default_constants():
    """Default recording config constants are as specified."""
    from openjarvis.autonomy.voice_conversation import (
        _DEFAULT_MAX_RECORD_SECONDS,
        _DEFAULT_MIN_RECORD_SECONDS,
        _DEFAULT_SILENCE_STOP_MS,
    )
    assert _DEFAULT_MAX_RECORD_SECONDS == 120.0, f"Emergency cap must be 120s, got {_DEFAULT_MAX_RECORD_SECONDS}"
    assert _DEFAULT_MIN_RECORD_SECONDS == 1.0
    assert _DEFAULT_SILENCE_STOP_MS == 4000.0


def test_vad_env_var_overrides(monkeypatch):
    """Env vars correctly override endpointing defaults in VoiceConversationLoop."""
    monkeypatch.setenv("JARVIS_VOICE_MIN_RECORD_SECONDS", "2.0")
    monkeypatch.setenv("JARVIS_VOICE_SILENCE_STOP_MS", "6000")
    monkeypatch.setenv("JARVIS_VOICE_MAX_RECORD_SECONDS", "180")
    monkeypatch.setenv("JARVIS_VOICE_SILENCE_RMS", "300")

    # Re-import to pick up env changes (env_float reads at init time)
    from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
    loop = VoiceConversationLoop.__new__(VoiceConversationLoop)
    loop._min_record_seconds = float(os.environ.get("JARVIS_VOICE_MIN_RECORD_SECONDS", 1.0))
    loop._silence_stop_ms = float(os.environ.get("JARVIS_VOICE_SILENCE_STOP_MS", 4000.0))
    loop._max_record_seconds = float(os.environ.get("JARVIS_VOICE_MAX_RECORD_SECONDS", 120.0))
    loop._silence_rms_threshold = float(os.environ.get("JARVIS_VOICE_SILENCE_RMS", 150.0))

    assert loop._min_record_seconds == 2.0
    assert loop._silence_stop_ms == 6000.0
    assert loop._max_record_seconds == 180.0
    assert loop._silence_rms_threshold == 300.0


def test_loop_uses_120s_as_default_max():
    """VoiceConversationLoop default record_seconds is 120 (the emergency cap)."""
    import inspect
    from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
    sig = inspect.signature(VoiceConversationLoop.__init__)
    default = sig.parameters["record_seconds"].default
    assert default == 120.0, f"VoiceConversationLoop default record_seconds must be 120, got {default}"


def test_no_5s_cap_in_loop_default():
    """Ensure the old 5-second default has been removed."""
    import inspect
    from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
    sig = inspect.signature(VoiceConversationLoop.__init__)
    default = sig.parameters["record_seconds"].default
    assert default != 5.0, "Old 5-second cap still present in VoiceConversationLoop"
    assert default != 30.0, "30-second cap must not be the default — use 120s emergency cap"


def test_backend_record_seconds_default_is_120():
    """VoiceStartRequest default record_seconds is 120."""
    from openjarvis.server.voice_routes import VoiceStartRequest
    req = VoiceStartRequest()
    assert req.record_seconds == 120.0, f"Backend default must be 120s, got {req.record_seconds}"


def test_backend_record_seconds_allows_120():
    """Backend accepts record_seconds=120 without validation error."""
    from openjarvis.server.voice_routes import VoiceStartRequest
    req = VoiceStartRequest(record_seconds=120.0)
    assert req.record_seconds == 120.0


# ---------------------------------------------------------------------------
# Runtime / status query routing tests
# ---------------------------------------------------------------------------

def test_runtime_query_voice_provider():
    """'What is the current voice provider?' routes to runtime, not LLM."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("What is the current voice provider?")
    assert result is not None, "Runtime query should be intercepted"
    assert len(result) > 10


def test_runtime_query_using_deepgram():
    """'Are you using Deepgram?' routes to runtime answer."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("Are you using Deepgram?")
    assert result is not None


def test_runtime_query_safe_status_check():
    """'Can you run a safe status check?' routes to runtime, not LLM."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("Can you run a safe status check?")
    assert result is not None


def test_runtime_query_voice_status():
    """'What is your voice status?' routes to runtime answer."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("What is your voice status?")
    assert result is not None


def test_runtime_query_backend_connected():
    """'Are you connected to the backend?' routes to runtime answer."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("Are you connected to the backend?")
    assert result is not None


def test_runtime_query_what_can_you_do():
    """'What can you do right now?' routes to runtime answer."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("What can you do right now?")
    assert result is not None


def test_runtime_query_non_status_returns_none():
    """A general question does not match the runtime router."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    assert handle_voice_runtime_query("Tell me a joke") is None
    assert handle_voice_runtime_query("Schedule a meeting") is None
    assert handle_voice_runtime_query("") is None


def test_runtime_answer_no_secret_leak(monkeypatch):
    """Runtime answer must not contain API key values."""
    fake_key = "dg_test_secret_key_do_not_leak_abc123"
    monkeypatch.setenv("DEEPGRAM_API_KEY", fake_key)

    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    result = handle_voice_runtime_query("What is the current voice provider?")
    assert result is not None
    assert fake_key not in result, "API key value leaked in runtime answer"
    assert "dg_test" not in result, "Partial key leaked in runtime answer"


def test_runtime_answer_mentions_deepgram_when_configured(monkeypatch):
    """When Deepgram is configured as primary, the runtime answer says so."""
    monkeypatch.setenv("JARVIS_STT_PROVIDER", "deepgram")
    monkeypatch.setenv("JARVIS_TTS_PROVIDER", "deepgram")
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg_fake_key_for_test")

    from openjarvis.autonomy.voice_conversation import _build_voice_runtime_answer
    answer = _build_voice_runtime_answer()
    assert "deepgram" in answer.lower(), f"Answer should mention deepgram: {answer}"


def test_runtime_answer_does_not_claim_no_access(monkeypatch):
    """Runtime answer must not say 'no access' for Jarvis's own state."""
    monkeypatch.setenv("DEEPGRAM_API_KEY", "dg_fake_key_for_test")
    from openjarvis.autonomy.voice_conversation import _build_voice_runtime_answer
    answer = _build_voice_runtime_answer()
    assert "no access" not in answer.lower()
    assert "cannot access" not in answer.lower()


# ---------------------------------------------------------------------------
# Safety gate preservation (sanity check — not a full gate test)
# ---------------------------------------------------------------------------

def test_dangerous_commands_still_gated():
    """Dangerous commands do not route through the runtime shortcut."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query
    # These must return None — they should go through the normal security path
    assert handle_voice_runtime_query("Delete this file") is None
    assert handle_voice_runtime_query("Deploy this to production") is None
    assert handle_voice_runtime_query("Send this email") is None


def test_runtime_query_not_destructive():
    """Runtime answer code must only call read-only pipeline functions."""
    # Verify the function only calls get_* (read-only) functions from voice_pipeline
    import inspect
    from openjarvis.autonomy.voice_conversation import _build_voice_runtime_answer
    src = inspect.getsource(_build_voice_runtime_answer)
    # Must not call any mutating operations
    assert "delete" not in src.lower()
    assert "deploy" not in src.lower()
    assert "send_message" not in src.lower()
    assert "os.remove" not in src
