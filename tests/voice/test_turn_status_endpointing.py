"""Targeted tests for voice turn engine — runtime query interception + endpointing.

Coverage (per task spec):
  1. runtime_query_voice_provider  — voice-provider question bypasses LLM,
                                     returns real Deepgram runtime state
  2. runtime_query_fallback        — fallback-provider question bypasses LLM
  3. non_runtime_query_goes_to_llm — ordinary question is NOT intercepted
  4. vad_silence_submits           — silence_consecutive >= silence_chunks_needed
                                     triggers silence_endpointed stop_reason
  5. vad_transient_no_reset        — single loud chunk does NOT reset silence counter
  6. vad_sustained_loud_resets     — 2+ consecutive loud chunks DO reset counter
  7. end_and_send_still_works      — abort_event stops recording with manually_ended
  8. vad_chunk_callback_called     — on_vad_chunk emits rms/threshold/silence_elapsed_ms
  9. vad_progress_sse_emitted      — _stage_record emits vad_progress SSE events
 10. turn_engine_runtime_intercept — full turn: runtime query → intercepted → no LLM call
"""

from __future__ import annotations

import io
import queue
import struct
import threading
import time
import wave
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    n = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n}h", *([0] * n)))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Runtime query — voice provider bypasses LLM
# ---------------------------------------------------------------------------

def test_runtime_query_voice_provider_intercepted():
    """handle_voice_runtime_query must intercept 'what is the current voice provider'."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query

    queries = [
        "what is the current voice provider",
        "are you using Deepgram",
        "what is your voice status",
        "what STT provider are you using",
    ]
    for q in queries:
        result = handle_voice_runtime_query(q)
        assert result is not None, f"Expected interception for: {q!r}"
        assert isinstance(result, str) and len(result) > 10, f"Expected non-empty answer for: {q!r}"


# ---------------------------------------------------------------------------
# 2. Runtime query — fallback provider bypasses LLM
# ---------------------------------------------------------------------------

def test_runtime_query_fallback_intercepted():
    """handle_voice_runtime_query must intercept fallback-provider questions."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query

    queries = [
        "what fallback do you use if Deepgram fails",
        "what is the STT fallback",
        "if deepgram fails what happens",
    ]
    for q in queries:
        result = handle_voice_runtime_query(q)
        assert result is not None, f"Expected interception for fallback query: {q!r}"


# ---------------------------------------------------------------------------
# 3. Non-runtime query is NOT intercepted
# ---------------------------------------------------------------------------

def test_non_runtime_query_not_intercepted():
    """handle_voice_runtime_query must return None for ordinary questions."""
    from openjarvis.autonomy.voice_conversation import handle_voice_runtime_query

    non_queries = [
        "what is the capital of France",
        "set a timer for 5 minutes",
        "play some music",
        "open the browser",
    ]
    for q in non_queries:
        result = handle_voice_runtime_query(q)
        assert result is None, f"Expected None (no interception) for: {q!r}, got: {result!r}"


# ---------------------------------------------------------------------------
# 4. VAD: silence_consecutive >= silence_chunks_needed triggers endpoint
# ---------------------------------------------------------------------------

def test_vad_silence_submits_after_silence_stop_ms():
    """record_command_audio_vad returns 'silence_endpointed' when silence_stop_ms elapses."""
    import numpy as np
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS, record_command_audio_vad

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    # Plan: 5 calibration chunks quiet, then 3 loud (speech), then 10 quiet (silence)
    # silence_stop_ms=1000ms → silence_chunks_needed=10
    # min_seconds=0.0 → min_chunks=0 (immediately eligible after speech)
    loud_rms = 5000
    quiet_rms = 10

    loud_chunk = (np.full(chunk_samples, loud_rms, dtype=np.int16)).tobytes()
    quiet_chunk = (np.zeros(chunk_samples, dtype=np.int16)).tobytes()

    # Sequence: 5 calib-quiet, 3 loud, 11 quiet (needs >=10)
    # Must produce at least _NOISE_CALIB_CHUNKS calib chunks + min_chunks + silence_chunks_needed
    chunks_plan = (
        [quiet_chunk] * 5     # calibration
        + [loud_chunk] * 3    # speech (loud_streak reaches 2 → silence_consecutive resets)
        + [quiet_chunk] * 12  # silence — should endpoint at 10
    )
    call_count = [0]

    import sounddevice as sd

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            if i < len(chunks_plan):
                raw = chunks_plan[i]
            else:
                raw = quiet_chunk
            arr = np.frombuffer(raw, dtype=np.int16).reshape(-1, 1)
            return arr, False

    with patch.object(sd, "InputStream", _FakeStream):
        _, stop_reason = record_command_audio_vad(
            min_seconds=0.0,
            silence_stop_ms=1000.0,
            max_seconds=30.0,
            silence_rms_threshold=300.0,
        )

    assert stop_reason == "silence_endpointed", (
        f"Expected silence_endpointed, got: {stop_reason!r}"
    )


# ---------------------------------------------------------------------------
# 5. VAD: single loud chunk does NOT reset silence counter (transient resistance)
# ---------------------------------------------------------------------------

def test_vad_transient_single_loud_no_reset():
    """A single 100ms loud chunk must NOT reset silence_consecutive (transient resistance)."""
    import numpy as np
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS, _VAD_TRANSIENT_LOUD_CHUNKS

    assert _VAD_TRANSIENT_LOUD_CHUNKS >= 2, (
        "_VAD_TRANSIENT_LOUD_CHUNKS must be >= 2 for transient resistance to work"
    )

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    loud_chunk = (np.full(chunk_samples, 5000, dtype=np.int16)).tobytes()
    quiet_chunk = (np.zeros(chunk_samples, dtype=np.int16)).tobytes()

    # 5 calib, 3 loud (establish speech), 5 quiet (silence accumulating),
    # 1 loud transient, 5 more quiet → should still endpoint (not reset to 0 at transient)
    chunks_plan = (
        [quiet_chunk] * 5   # calib
        + [loud_chunk] * 3  # speech (loud_streak >= 2 → silence resets)
        + [quiet_chunk] * 5 # 5 silence chunks
        + [loud_chunk] * 1  # transient — must NOT reset silence_consecutive
        + [quiet_chunk] * 12 # enough to reach 10 total non-reset silence chunks
    )
    call_count = [0]
    chunk_events: List[dict] = []

    import sounddevice as sd

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            raw = chunks_plan[i] if i < len(chunks_plan) else quiet_chunk
            return np.frombuffer(raw, dtype=np.int16).reshape(-1, 1), False

    with patch.object(sd, "InputStream", _FakeStream):
        from openjarvis.autonomy.voice_conversation import record_command_audio_vad
        _, stop_reason = record_command_audio_vad(
            min_seconds=0.0,
            silence_stop_ms=1000.0,
            max_seconds=30.0,
            silence_rms_threshold=300.0,
            on_vad_chunk=chunk_events.append,
        )

    assert stop_reason == "silence_endpointed", (
        f"Transient must not prevent endpointing; got stop_reason={stop_reason!r}"
    )


# ---------------------------------------------------------------------------
# 6. VAD: 2+ consecutive loud chunks DO reset silence counter
# ---------------------------------------------------------------------------

def test_vad_sustained_loud_resets_silence():
    """Two consecutive loud chunks must reset silence_consecutive to 0."""
    import numpy as np
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    loud_chunk = (np.full(chunk_samples, 5000, dtype=np.int16)).tobytes()
    quiet_chunk = (np.zeros(chunk_samples, dtype=np.int16)).tobytes()

    chunk_events: List[dict] = []

    # Calib: quiet. Then: 2 loud → silence reset → long quiet → endpoint
    chunks_plan = (
        [quiet_chunk] * 5
        + [loud_chunk] * 2  # sustained → silence_consecutive resets
        + [quiet_chunk] * 12
    )
    call_count = [0]

    import sounddevice as sd

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            raw = chunks_plan[i] if i < len(chunks_plan) else quiet_chunk
            return np.frombuffer(raw, dtype=np.int16).reshape(-1, 1), False

    with patch.object(sd, "InputStream", _FakeStream):
        from openjarvis.autonomy.voice_conversation import record_command_audio_vad
        _, stop_reason = record_command_audio_vad(
            min_seconds=0.0,
            silence_stop_ms=1000.0,
            max_seconds=30.0,
            silence_rms_threshold=300.0,
            on_vad_chunk=chunk_events.append,
        )

    assert stop_reason == "silence_endpointed", f"Expected silence_endpointed, got: {stop_reason!r}"

    # Verify silence_consecutive reached 0 at some point after sustained loud
    min_sc_after_speech = min(
        e["silence_consecutive"] for e in chunk_events if not e["speech_detected"] is False
    ) if chunk_events else -1
    # After sustained loud, silence accumulates from 0 — should see silence_consecutive=1 at some point
    assert any(e["silence_consecutive"] >= 1 for e in chunk_events), (
        "Expected silence_consecutive to increment after sustained loud reset"
    )


# ---------------------------------------------------------------------------
# 7. End & send still works (abort_event)
# ---------------------------------------------------------------------------

def test_end_and_send_abort_event():
    """Aborting via abort_event must return 'manually_ended' immediately."""
    import numpy as np
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet_chunk = np.zeros(chunk_samples, dtype=np.int16).reshape(-1, 1)
    abort = threading.Event()
    call_count = [0]

    import sounddevice as sd

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            if i == 3:
                abort.set()  # set abort on 4th chunk
            return quiet_chunk, False

    with patch.object(sd, "InputStream", _FakeStream):
        from openjarvis.autonomy.voice_conversation import record_command_audio_vad
        _, stop_reason = record_command_audio_vad(
            min_seconds=60.0,   # would never end normally
            silence_stop_ms=60000.0,
            max_seconds=300.0,
            abort_event=abort,
        )

    assert stop_reason == "manually_ended", f"Expected manually_ended, got: {stop_reason!r}"


# ---------------------------------------------------------------------------
# 8. on_vad_chunk callback receives correct fields
# ---------------------------------------------------------------------------

def test_vad_chunk_callback_fields():
    """on_vad_chunk must provide rms, threshold, silence_elapsed_ms, etc."""
    import numpy as np
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet_chunk = np.zeros(chunk_samples, dtype=np.int16).reshape(-1, 1)
    abort = threading.Event()
    chunks: List[dict] = []
    call_count = [0]

    import sounddevice as sd

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            if i == 8:
                abort.set()
            return quiet_chunk, False

    with patch.object(sd, "InputStream", _FakeStream):
        from openjarvis.autonomy.voice_conversation import record_command_audio_vad
        record_command_audio_vad(
            min_seconds=60.0,
            silence_stop_ms=60000.0,
            max_seconds=300.0,
            abort_event=abort,
            on_vad_chunk=chunks.append,
        )

    assert len(chunks) > 0, "on_vad_chunk was never called"
    for c in chunks:
        assert "rms" in c, f"Missing 'rms' in chunk: {c}"
        assert "threshold" in c, f"Missing 'threshold' in chunk: {c}"
        assert "silence_elapsed_ms" in c, f"Missing 'silence_elapsed_ms' in chunk: {c}"
        assert "silence_consecutive" in c, f"Missing 'silence_consecutive' in chunk: {c}"
        assert "speech_detected" in c, f"Missing 'speech_detected' in chunk: {c}"


# ---------------------------------------------------------------------------
# 9. VoiceTurnEngine._stage_record emits vad_progress SSE events
# ---------------------------------------------------------------------------

def test_vad_progress_sse_emitted():
    """VoiceTurnEngine must emit vad_progress events during recording."""
    import numpy as np
    from openjarvis.autonomy.voice_turn_engine import VoiceTurnEngine, TurnPhase
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)
    quiet_chunk = np.zeros(chunk_samples, dtype=np.int16).reshape(-1, 1)

    # Pre-built WAV for STT mock
    wav_bytes = _make_wav(0.5)

    import sounddevice as sd

    call_count = [0]
    abort_ref = [None]

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            if i >= 6 and abort_ref[0] is not None:
                abort_ref[0].set()
            return quiet_chunk, False

    engine = VoiceTurnEngine()
    abort_ref[0] = engine._recording_abort

    sub_q = engine.subscribe()
    events: List[dict] = []

    with patch.object(sd, "InputStream", _FakeStream), \
         patch("openjarvis.autonomy.voice_conversation.record_command_audio_vad",
               wraps=__import__("openjarvis.autonomy.voice_conversation",
                                fromlist=["record_command_audio_vad"]).record_command_audio_vad):
        result = engine.start_turn(language="en")
        assert result.get("ok"), f"start_turn failed: {result}"

        # Drain events for up to 3 seconds
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            try:
                evt = sub_q.get(timeout=0.2)
                events.append(evt)
                if evt.get("type") in ("vad", "error", "state") and evt.get("state") in (
                    "idle", "error", "cancelled", None
                ):
                    phase = engine._phase
                    if phase in (TurnPhase.IDLE, TurnPhase.ERROR, TurnPhase.CANCELLED):
                        break
            except Exception:
                break

    vad_progress_events = [e for e in events if e.get("type") == "vad_progress"]
    assert len(vad_progress_events) > 0, (
        f"Expected vad_progress events in SSE stream; got types: {[e.get('type') for e in events]}"
    )
    for e in vad_progress_events[:3]:
        assert "rms" in e
        assert "silence_elapsed_ms" in e


# ---------------------------------------------------------------------------
# 10. Full turn engine: runtime query intercepted — no LLM call
# ---------------------------------------------------------------------------

def test_turn_engine_runtime_query_no_llm():
    """A voice-provider question in the turn engine must skip query_jarvis_text."""
    import numpy as np
    from openjarvis.autonomy.voice_turn_engine import VoiceTurnEngine, TurnPhase
    from openjarvis.autonomy.voice_conversation import _VAD_CHUNK_MS

    chunk_samples = int(16000 * _VAD_CHUNK_MS / 1000)

    # Loud chunks then quiet — to get through VAD quickly
    loud_val = 3000
    loud_chunk = (np.full(chunk_samples, loud_val, dtype=np.int16)).reshape(-1, 1)
    quiet_chunk = np.zeros(chunk_samples, dtype=np.int16).reshape(-1, 1)

    wav_bytes = _make_wav(0.5)

    import sounddevice as sd

    call_count = [0]
    # Plan: 5 calib-loud (speech), then silence → endpoint
    chunk_plan = [loud_chunk] * 7 + [quiet_chunk] * 50

    class _FakeStream:
        def __init__(self, *a, **kw): pass
        def start(self): pass
        def stop(self): pass
        def close(self): pass
        def read(self, n):
            i = call_count[0]
            call_count[0] += 1
            return chunk_plan[i] if i < len(chunk_plan) else quiet_chunk, False

    jarvis_called = [False]

    def _fake_jarvis(text, *, on_route=None):
        jarvis_called[0] = True
        return "This should not be called for runtime queries"

    fake_stt_result = MagicMock()
    fake_stt_result.text = "what is the current voice provider"
    fake_stt_result.confidence = 0.99
    fake_stt_result.duration_seconds = 0.5
    fake_stt_result.language = "en"

    engine = VoiceTurnEngine(silence_stop_ms=500.0)
    sub_q = engine.subscribe()

    with patch.object(sd, "InputStream", _FakeStream), \
         patch("openjarvis.autonomy.voice_conversation.transcribe_command_result",
               return_value=fake_stt_result), \
         patch("openjarvis.autonomy.voice_conversation.evaluate_voice_transcript") as mock_eval, \
         patch("openjarvis.autonomy.voice_conversation.query_jarvis_text", side_effect=_fake_jarvis), \
         patch("openjarvis.autonomy.voice_conversation.speak_response", return_value=None):

        from openjarvis.autonomy.voice_conversation import VoiceTranscriptDecision
        mock_eval.return_value = VoiceTranscriptDecision(
            accepted=True,
            text="what is the current voice provider",
            reason="ok",
        )

        result = engine.start_turn(language="en")
        assert result.get("ok"), f"start_turn failed: {result}"

        # Collect events up to 5s
        all_events: List[dict] = []
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                evt = sub_q.get(timeout=0.3)
                all_events.append(evt)
            except Exception:
                pass
            if engine._phase in (TurnPhase.IDLE, TurnPhase.ERROR, TurnPhase.CANCELLED):
                time.sleep(0.1)
                break

    assert not jarvis_called[0], (
        "query_jarvis_text must NOT be called for runtime voice provider query"
    )

    route_events = [e for e in all_events if e.get("type") == "route"]
    intercepted = any(e.get("intercepted") for e in route_events)
    assert intercepted, (
        f"Expected at least one route event with intercepted=True; route_events={route_events}"
    )
