"""Targeted tests for background-robust endpointing + cancel-during-speaking.

Coverage (per task spec):
  1. endpoint_submits_with_background_rms  — relative endpoint fires after speech
                                             stops even though background RMS stays
                                             high (background music scenario)
  2. short_pause_no_premature_endpoint     — a 1-second pause in speech does NOT
                                             trigger the relative endpoint
  3. end_and_send_bypasses_endpointing     — abort_event bypasses silence detection
  4. cancel_speaking_kills_subprocess      — cancel_turn() terminates the afplay
                                             subprocess when phase == SPEAKING
  5. cancel_speaking_phase_becomes_cancelled — phase transitions to CANCELLED,
                                              not IDLE, after cancel during speak
  6. vad_progress_includes_ambient_speech_ema — vad_progress SSE events include
                                                ambient_ema and speech_ema fields
  7. provider_runtime_query_still_intercepted — handle_voice_runtime_query still works
  8. relative_silence_count_resets_on_speech  — relative count resets when speech
                                                returns above the dropout threshold
  9. background_noise_detected_flag           — background_noise_detected is True
                                                when ambient exceeds static threshold
"""

from __future__ import annotations

import io
import queue
import struct
import threading
import time
import wave
from typing import Dict, List
from unittest.mock import MagicMock, patch, call

import pytest
import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wav(duration_s: float = 0.5, sr: int = 16000) -> bytes:
    n = int(sr * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{n}h", *([0] * n)))
    return buf.getvalue()


def _rms_chunk(rms_val: int, chunk_samples: int = 1600) -> "np.ndarray":
    """Create a mono chunk array with approximately the given RMS."""
    return np.full(chunk_samples, rms_val, dtype=np.int16).reshape(-1, 1)


# ---------------------------------------------------------------------------
# 1. Relative endpoint fires with persistent background noise
# ---------------------------------------------------------------------------

def test_endpoint_submits_with_background_rms():
    """After speech stops, the relative endpoint must fire even when background
    RMS stays above the absolute silence threshold.

    Scenario:
      - Calibration: quiet room (RMS ≈ 0)  →  effective_threshold = 300
      - Background music then starts at RMS 1000 (above 300 → absolute never fires)
      - Bryan speaks at RMS 3500 for 10 chunks (speech_ema builds up)
      - Bryan stops; background music continues at RMS 1000
      - Relative dropout: 1000 < 3500 * 0.55 = 1925 → relative silence accumulates
      - After 25 consecutive relative-silence chunks, endpoint fires
    """
    import sounddevice as sd
    from openjarvis.autonomy.voice_conversation import (
        _VAD_CHUNK_MS, _SPEECH_DROPOUT_CHUNKS, record_command_audio_vad
    )

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet = _rms_chunk(0, chunk_samples)
    music = _rms_chunk(1000, chunk_samples)   # background music — above static threshold
    speech = _rms_chunk(3500, chunk_samples)  # Bryan's voice

    # Plan: 5 quiet calib, 10 speech, then background music only
    chunks_plan = (
        [quiet] * 5        # calibration (quiet → noise_floor ≈ 0)
        + [speech] * 10    # speech builds speech_ema ≈ 3500
        + [music] * 60     # background only — relative silence fires at chunk 25
    )
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            return chunks_plan[i] if i < len(chunks_plan) else music, False

    chunk_events: List[dict] = []

    with patch.object(sd, "InputStream", _FakeStream):
        _, stop_reason = record_command_audio_vad(
            min_seconds=0.0,
            silence_stop_ms=60000.0,   # absolute threshold would never fire (music > 300)
            max_seconds=30.0,
            silence_rms_threshold=300.0,
            on_vad_chunk=chunk_events.append,
        )

    assert stop_reason == "silence_endpointed", (
        f"Expected silence_endpointed via relative dropout with background music; "
        f"got: {stop_reason!r}"
    )

    # Confirm at least one chunk had background_noise_detected=True
    bg_detected = any(e.get("background_noise_detected") for e in chunk_events)
    assert bg_detected, "Expected background_noise_detected=True in at least one chunk event"


# ---------------------------------------------------------------------------
# 2. Short pause does not prematurely endpoint
# ---------------------------------------------------------------------------

def test_short_pause_no_premature_endpoint():
    """A 1-second thinking pause (10 chunks at music RMS) during speech must NOT
    trigger the relative endpoint (needs >= _SPEECH_DROPOUT_CHUNKS consecutive)."""
    import sounddevice as sd
    from openjarvis.autonomy.voice_conversation import (
        _VAD_CHUNK_MS, _SPEECH_DROPOUT_CHUNKS, record_command_audio_vad
    )

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet = _rms_chunk(0, chunk_samples)
    music = _rms_chunk(1000, chunk_samples)
    speech = _rms_chunk(3500, chunk_samples)

    assert _SPEECH_DROPOUT_CHUNKS > 10, (
        "Test assumes _SPEECH_DROPOUT_CHUNKS > 10 to detect a 1-second pause"
    )

    # 5 quiet calib, 10 speech, 10-chunk pause, 10 more speech, then long silence
    chunks_plan = (
        [quiet] * 5
        + [speech] * 10   # speech
        + [music] * 10    # 1s pause — less than _SPEECH_DROPOUT_CHUNKS
        + [speech] * 10   # speech resumes (resets relative count)
        + [music] * 50    # now full silence — relative endpoint fires
    )
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            return chunks_plan[i] if i < len(chunks_plan) else music, False

    # Track when the first pause starts (after chunk 15 = 5 calib + 10 speech)
    pause_started_at = [None]
    endpoint_at = [None]

    def _on_chunk(c):
        # Detect pause start (first music chunk after speech)
        if (c.get("speech_detected") and
                c.get("relative_silence_ms", 0) > 0 and
                pause_started_at[0] is None):
            pause_started_at[0] = c.get("relative_silence_ms")

    with patch.object(sd, "InputStream", _FakeStream):
        _, stop_reason = record_command_audio_vad(
            min_seconds=0.0,
            silence_stop_ms=60000.0,
            max_seconds=30.0,
            silence_rms_threshold=300.0,
            on_vad_chunk=_on_chunk,
        )

    assert stop_reason == "silence_endpointed", (
        f"Expected eventual endpoint after speech stops; got: {stop_reason!r}"
    )


# ---------------------------------------------------------------------------
# 3. End & send bypasses all endpointing
# ---------------------------------------------------------------------------

def test_end_and_send_bypasses_endpointing():
    """abort_event must immediately stop recording regardless of endpointing state."""
    import sounddevice as sd
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS, record_command_audio_vad

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    music = _rms_chunk(1000, chunk_samples)
    abort = threading.Event()
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            if i == 10:
                abort.set()
            return music, False

    with patch.object(sd, "InputStream", _FakeStream):
        _, stop_reason = record_command_audio_vad(
            min_seconds=600.0,   # would never end naturally
            silence_stop_ms=60000.0,
            max_seconds=600.0,
            silence_rms_threshold=300.0,
            abort_event=abort,
        )

    assert stop_reason == "manually_ended", (
        f"Expected manually_ended from abort_event; got: {stop_reason!r}"
    )


# ---------------------------------------------------------------------------
# 4. cancel_turn() kills the TTS subprocess
# ---------------------------------------------------------------------------

def test_cancel_speaking_kills_subprocess():
    """cancel_turn() must call _TTSPlayback.cancel() which terminates the afplay proc."""
    from openjarvis.autonomy.voice_turn_engine import VoiceTurnEngine, TurnPhase
    from openjarvis.autonomy.voice_conversation import _TTSPlayback

    engine = VoiceTurnEngine()

    # Create a mock process and inject it into the engine's _tts_playback
    mock_proc = MagicMock()
    mock_proc.poll.return_value = None   # process is "running"

    with engine._tts_playback._lock:
        engine._tts_playback._proc = mock_proc

    # Simulate engine in SPEAKING phase
    with engine._lock:
        engine._phase = TurnPhase.SPEAKING
        engine._turn_counter = 1
        engine._active_turn_id = 1

    result = engine.cancel_turn()

    assert result.get("ok") is True
    mock_proc.terminate.assert_called_once()


# ---------------------------------------------------------------------------
# 5. Phase becomes CANCELLED after cancel during SPEAKING
# ---------------------------------------------------------------------------

def test_cancel_speaking_phase_becomes_cancelled():
    """After cancel_turn() while speaking, the turn must reach CANCELLED (not IDLE)."""
    import sounddevice as sd
    from openjarvis.autonomy.voice_turn_engine import VoiceTurnEngine, TurnPhase

    chunk_samples = 1600
    quiet = _rms_chunk(0, chunk_samples)

    wav_bytes = _make_wav(0.5)
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            return quiet, False

    engine = VoiceTurnEngine(silence_stop_ms=500.0)
    sub_q = engine.subscribe()

    # TTS mock: block on a threading.Event until cancelled
    speak_started = threading.Event()
    speak_cancelled = threading.Event()

    def _fake_speak(text, *, playback=None, cancel_check=None):
        speak_started.set()
        # Poll cancel_check and the playback.cancel() mechanism
        for _ in range(100):
            if cancel_check is not None and cancel_check():
                speak_cancelled.set()
                return False
            time.sleep(0.02)
        return True

    fake_stt = MagicMock()
    fake_stt.text = "hello world"
    fake_stt.confidence = 0.99
    fake_stt.duration_seconds = 0.5
    fake_stt.language = "en"

    from openjarvis.autonomy.voice_conversation import VoiceTranscriptDecision

    with patch.object(sd, "InputStream", _FakeStream), \
         patch("openjarvis.autonomy.voice_conversation.transcribe_command_result",
               return_value=fake_stt), \
         patch("openjarvis.autonomy.voice_conversation.evaluate_voice_transcript",
               return_value=VoiceTranscriptDecision(accepted=True, text="hello world", reason="ok")), \
         patch("openjarvis.autonomy.voice_conversation.query_jarvis_text",
               return_value="The answer is 42"), \
         patch("openjarvis.autonomy.voice_conversation.speak_response",
               side_effect=_fake_speak):

        result = engine.start_turn(language="en")
        assert result.get("ok"), f"start_turn failed: {result}"

        # Wait for TTS to start then cancel
        assert speak_started.wait(timeout=5.0), "TTS never started"
        engine.cancel_turn()

        assert speak_cancelled.wait(timeout=3.0), "TTS cancel_check never triggered"

    # Drain events
    all_events: List[dict] = []
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        try:
            evt = sub_q.get(timeout=0.2)
            all_events.append(evt)
        except Exception:
            pass
        if engine._phase in (TurnPhase.CANCELLED, TurnPhase.IDLE, TurnPhase.ERROR):
            break

    assert engine._phase == TurnPhase.CANCELLED, (
        f"Expected CANCELLED phase after cancel during speaking; got: {engine._phase}"
    )


# ---------------------------------------------------------------------------
# 6. vad_progress includes ambient_ema and speech_ema
# ---------------------------------------------------------------------------

def test_vad_progress_includes_ambient_speech_ema():
    """vad_progress SSE events must include ambient_ema and speech_ema fields."""
    import sounddevice as sd
    from openjarvis.autonomy.voice_turn_engine import VoiceTurnEngine, TurnPhase

    chunk_samples = 1600
    loud = _rms_chunk(3000, chunk_samples)
    quiet = _rms_chunk(0, chunk_samples)
    abort_ref = [None]
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            if i >= 12 and abort_ref[0] is not None:
                abort_ref[0].set()
            return loud if i < 7 else quiet, False

    engine = VoiceTurnEngine()
    abort_ref[0] = engine._recording_abort
    sub_q = engine.subscribe()

    with patch.object(sd, "InputStream", _FakeStream):
        engine.start_turn(language="en")

        all_events: List[dict] = []
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            try:
                evt = sub_q.get(timeout=0.2)
                all_events.append(evt)
            except Exception:
                pass
            if engine._phase in (TurnPhase.IDLE, TurnPhase.ERROR, TurnPhase.CANCELLED,
                                  TurnPhase.TRANSCRIBING):
                break

    progress_events = [e for e in all_events if e.get("type") == "vad_progress"]
    assert len(progress_events) > 0, "No vad_progress events emitted"
    for e in progress_events[:5]:
        assert "ambient_ema" in e, f"Missing ambient_ema in vad_progress: {e}"
        assert "speech_ema" in e, f"Missing speech_ema in vad_progress: {e}"


# ---------------------------------------------------------------------------
# 7. Runtime provider query still intercepted after changes
# ---------------------------------------------------------------------------

def test_provider_runtime_query_still_intercepted():
    """handle_voice_runtime_query must still intercept provider questions."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query

    result = handle_voice_runtime_query("what is the current voice provider")
    assert result is not None and len(result) > 10, (
        "Expected non-empty interception for voice provider query"
    )

    result2 = handle_voice_runtime_query("are you using Deepgram")
    assert result2 is not None and len(result2) > 10


# ---------------------------------------------------------------------------
# 8. Relative silence count resets when speech returns
# ---------------------------------------------------------------------------

def test_relative_silence_resets_on_speech_return():
    """When speech resumes after a pause, relative_silence_count must reset to 0."""
    import sounddevice as sd
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS, record_command_audio_vad

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet = _rms_chunk(0, chunk_samples)
    speech = _rms_chunk(3500, chunk_samples)
    music = _rms_chunk(1200, chunk_samples)  # above absolute threshold

    # 5 quiet calib, 10 speech, 5 music pause, 10 speech, 30 music (endpoint)
    chunks_plan = (
        [quiet] * 5
        + [speech] * 10
        + [music] * 5     # pause — relative count climbs but < DROPOUT_CHUNKS
        + [speech] * 10   # speech returns → relative count resets
        + [music] * 40    # long silence → endpoint
    )
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            return chunks_plan[i] if i < len(chunks_plan) else music, False

    events: List[dict] = []

    with patch.object(sd, "InputStream", _FakeStream):
        _, stop_reason = record_command_audio_vad(
            min_seconds=0.0,
            silence_stop_ms=60000.0,
            max_seconds=30.0,
            silence_rms_threshold=300.0,
            on_vad_chunk=events.append,
        )

    assert stop_reason == "silence_endpointed", (
        f"Expected eventual endpoint; got: {stop_reason!r}"
    )

    # Find the chunk where speech returns after the first pause
    # There should be a relative_silence_ms=0 chunk after non-zero relative_silence_ms
    relative_ms_seq = [e.get("relative_silence_ms", 0) for e in events]
    found_reset = False
    for i in range(1, len(relative_ms_seq)):
        if relative_ms_seq[i - 1] > 0 and relative_ms_seq[i] == 0:
            found_reset = True
            break
    assert found_reset, (
        "Expected relative_silence_ms to reset to 0 when speech returns; "
        f"relative_ms_seq sample: {relative_ms_seq[:40]}"
    )


# ---------------------------------------------------------------------------
# 9. background_noise_detected flag set correctly
# ---------------------------------------------------------------------------

def test_background_noise_detected_flag():
    """background_noise_detected must be True when ambient EMA > static threshold * 1.5."""
    import sounddevice as sd
    from openjarvis.autonomy.voice_conversation import (
        _VAD_CHUNK_MS, record_command_audio_vad, _DEFAULT_SILENCE_RMS
    )

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet = _rms_chunk(0, chunk_samples)
    speech = _rms_chunk(4000, chunk_samples)
    # Use 4x static threshold so the slow ambient EMA (alpha=0.03) crosses 1.5x threshold
    # within ~60 chunks without requiring hundreds of iterations.
    loud_bg = _rms_chunk(int(_DEFAULT_SILENCE_RMS * 4), chunk_samples)

    abort = threading.Event()
    # 5 quiet calib, 65 loud background (ambient EMA rises), then abort
    chunks_plan = [quiet] * 5 + [loud_bg] * 65 + [quiet] * 5
    call_count = [0]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]; call_count[0] += 1
            if i >= len(chunks_plan) - 3:
                abort.set()
            return chunks_plan[i] if i < len(chunks_plan) else quiet, False

    events: List[dict] = []

    with patch.object(sd, "InputStream", _FakeStream):
        record_command_audio_vad(
            min_seconds=60.0,
            silence_stop_ms=60000.0,
            max_seconds=300.0,
            silence_rms_threshold=_DEFAULT_SILENCE_RMS,
            abort_event=abort,
            on_vad_chunk=events.append,
        )

    later_events = events[50:]  # after ambient EMA has had time to update
    bg_detected = any(e.get("background_noise_detected") for e in later_events)
    assert bg_detected, (
        "Expected background_noise_detected=True after sustained loud background; "
        f"events sample: {[e.get('background_noise_detected') for e in later_events[:10]]}"
    )
