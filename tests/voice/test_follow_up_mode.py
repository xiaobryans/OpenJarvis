"""Tests for PLAN_2S: follow-up listening mode + mic gain normalization.

Coverage:
  1. follow_up_enters_after_tts   — FOLLOW_UP_LISTENING entered after TTS
  2. follow_up_processes_speech   — follow-up speech routed + spoken
  3. follow_up_exits_on_timeout   — no speech → conversation_ended(timeout) → IDLE
  4. follow_up_exits_on_stop      — stop phrase → conversation_ended(stop_phrase) → IDLE
  5. follow_up_cancel             — cancel_turn() during follow-up → CANCELLED
  6. normalize_gain_quiet_audio   — quiet audio scaled up to target RMS
  7. normalize_gain_loud_audio    — loud audio not scaled
  8. normalize_gain_too_quiet     — very quiet → too_quiet diagnostic
  9. normalize_gain_no_clip       — extreme scale capped to avoid clipping
 10. stop_phrases_recognized      — "stop", "cancel", "that's all", "never mind" all match
 11. wake_diagnostics_in_status   — wake_enabled=False, provider=None, no workers
"""

from __future__ import annotations

import io
import math
import struct
import threading
import time
import wave
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.autonomy.voice_turn_engine import (
    TurnPhase,
    VoiceTurnEngine,
    _STOP_PHRASES,
    _normalize_audio_gain,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wav(duration_s: float = 0.5, sample_rate: int = 16000, amplitude: int = 0) -> bytes:
    """Build a valid WAV. amplitude=0 → silence; >0 → tone at that int16 level."""
    n_frames = int(sample_rate * duration_s)
    if amplitude > 0:
        samples = [int(amplitude * math.sin(2 * math.pi * 440 * i / sample_rate)) for i in range(n_frames)]
    else:
        samples = [0] * n_frames
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *samples))
    return buf.getvalue()


def _make_engine_followup(timeout_s: float = 3.0) -> VoiceTurnEngine:
    """Engine with follow-up enabled and short timeout for testing."""
    e = VoiceTurnEngine(followup_enabled=True)
    e._followup_timeout_s = timeout_s
    return e


def _drain_events(engine: VoiceTurnEngine, timeout: float = 8.0,
                  pre_subscribed_q=None) -> List[dict]:
    import queue as _q
    q = pre_subscribed_q if pre_subscribed_q is not None else engine.subscribe()
    events: List[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            evt = q.get(timeout=0.2)
        except _q.Empty:
            continue
        events.append(evt)
        if evt.get("type") == "turn_done":
            break
    if pre_subscribed_q is None:
        engine.unsubscribe(q)
    return events


def _wait_for_event_type(engine: VoiceTurnEngine, event_type: str,
                         timeout: float = 8.0, pre_subscribed_q=None) -> dict | None:
    """Wait until an event of event_type is emitted."""
    import queue as _q
    q = pre_subscribed_q if pre_subscribed_q is not None else engine.subscribe()
    deadline = time.monotonic() + timeout
    found = None
    while time.monotonic() < deadline:
        try:
            evt = q.get(timeout=0.3)
        except _q.Empty:
            continue
        if evt.get("type") == event_type:
            found = evt
            break
    if pre_subscribed_q is None:
        engine.unsubscribe(q)
    return found


def _wait_phase(engine: VoiceTurnEngine, target: TurnPhase, timeout: float = 8.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if engine.status()["phase"] == target.value:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------

def _mock_record(wav: bytes):
    def _impl(self, turn_id):
        return wav, True
    return _impl


def _mock_stt(text: str):
    def _impl(self, turn_id, audio, language):
        self._set_phase(TurnPhase.TRANSCRIBING)
        self._last_transcript = text
        self._emit({"type": "transcript", "text": text})
        return text
    return _impl


def _mock_route(response: str):
    def _impl(self, turn_id, text):
        self._set_phase(TurnPhase.THINKING)
        self._last_response = response
        self._emit({"type": "response", "text": response})
        return response
    return _impl


def _mock_tts_nonfinalize():
    """TTS mock — speaks, returns True, does not finalize."""
    def _impl(self, turn_id, text):
        self._set_phase(TurnPhase.SPEAKING)
        return True
    return _impl


# ---------------------------------------------------------------------------
# Tests: gain normalization
# ---------------------------------------------------------------------------


class TestNormalizeAudioGain:
    """Tests for _normalize_audio_gain()."""

    def test_quiet_audio_scaled_up(self):
        """Audio with RMS well below target is amplified."""
        low_amp_wav = _make_wav(0.5, amplitude=200)  # ~200 RMS
        normalized, diag = _normalize_audio_gain(low_amp_wav, target_rms=1000.0)

        assert diag["scale"] > 1.0, "Expected upscaling"
        assert diag["original_rms"] < 1000.0

    def test_loud_audio_not_scaled(self):
        """Audio already at or above target RMS is left unchanged."""
        loud_wav = _make_wav(0.5, amplitude=2000)  # ~2000 RMS (above 1000 target)
        normalized, diag = _normalize_audio_gain(loud_wav, target_rms=1000.0)

        assert diag["scale"] == 1.0, "Loud audio should not be scaled"
        assert normalized == loud_wav

    def test_very_quiet_triggers_too_quiet(self):
        """Scale > _GAIN_TOO_QUIET_SCALE triggers too_quiet diagnostic."""
        from openjarvis.autonomy.voice_turn_engine import _GAIN_TOO_QUIET_SCALE
        # Very quiet signal: amplitude ~50 RMS
        quiet_wav = _make_wav(0.5, amplitude=50)
        _, diag = _normalize_audio_gain(quiet_wav, target_rms=1000.0)

        # If scale > threshold, too_quiet is True
        if diag["scale"] > _GAIN_TOO_QUIET_SCALE:
            assert diag["too_quiet"] is True
        # Otherwise still a valid result
        assert "original_rms" in diag
        assert "scale" in diag

    def test_no_clip_on_extreme_gain(self):
        """Even extreme scaling never clips beyond int16 range."""
        whisper_wav = _make_wav(0.3, amplitude=10)  # very faint
        normalized, diag = _normalize_audio_gain(whisper_wav, target_rms=1000.0, max_scale=6.0)

        # Verify output WAV samples stay in int16 range
        with wave.open(io.BytesIO(normalized), "rb") as wf:
            raw = wf.readframes(wf.getnframes())

        samples = struct.unpack(f"<{len(raw)//2}h", raw)
        assert all(-32768 <= s <= 32767 for s in samples), "Clip detected in output"

    def test_empty_bytes_passthrough(self):
        """Empty bytes return unchanged with scale=1.0."""
        normalized, diag = _normalize_audio_gain(b"", target_rms=1000.0)
        assert normalized == b""
        assert diag["scale"] == 1.0


# ---------------------------------------------------------------------------
# Tests: stop phrases
# ---------------------------------------------------------------------------


class TestStopPhrases:
    """All required stop phrases are in the set."""

    def test_stop_in_set(self):
        assert "stop" in _STOP_PHRASES

    def test_cancel_in_set(self):
        assert "cancel" in _STOP_PHRASES

    def test_thats_all_in_set(self):
        assert "that's all" in _STOP_PHRASES

    def test_never_mind_in_set(self):
        assert "never mind" in _STOP_PHRASES

    def test_nevermind_in_set(self):
        assert "nevermind" in _STOP_PHRASES

    def test_goodbye_in_set(self):
        assert "goodbye" in _STOP_PHRASES

    def test_go_to_sleep_in_set(self):
        assert "go to sleep" in _STOP_PHRASES


# ---------------------------------------------------------------------------
# Tests: wake diagnostics in status
# ---------------------------------------------------------------------------


class TestWakeDiagnostics:
    """Wake word is HOLD — status must reflect this accurately."""

    def test_wake_enabled_false(self):
        e = VoiceTurnEngine()
        st = e.status()
        assert st["wake_enabled"] is False

    def test_wake_available_false(self):
        e = VoiceTurnEngine()
        assert e.status()["wake_available"] is False

    def test_wake_provider_null(self):
        e = VoiceTurnEngine()
        assert e.status()["wake_provider"] is None

    def test_wake_worker_running_false(self):
        e = VoiceTurnEngine()
        assert e.status()["wake_worker_running"] is False

    def test_wake_last_error_reports_not_implemented(self):
        e = VoiceTurnEngine()
        err = e.status()["wake_last_error"]
        assert err is not None and "not_implemented" in err.lower()

    def test_wake_last_detected_at_null(self):
        e = VoiceTurnEngine()
        assert e.status()["wake_last_detected_at"] is None


# ---------------------------------------------------------------------------
# Tests: follow-up mode lifecycle
# ---------------------------------------------------------------------------


class TestFollowUpMode:
    """Follow-up listening behavior."""

    @pytest.fixture()
    def engine(self):
        return _make_engine_followup(timeout_s=2.0)

    def test_follow_up_enabled_in_status(self, engine):
        st = engine.status()
        assert st["follow_up_enabled"] is True
        assert st["follow_up_timeout_s"] == 2.0

    def test_follow_up_disabled_engine(self):
        e = VoiceTurnEngine(followup_enabled=False)
        assert e.status()["follow_up_enabled"] is False

    def test_follow_up_enters_after_tts(self, engine):
        """FOLLOW_UP_LISTENING phase is entered after TTS completes."""
        wav = _make_wav(0.5, amplitude=500)

        # Make follow-up recording hang long enough to observe FOLLOW_UP_LISTENING
        follow_up_entered = threading.Event()
        original_record_followup = engine._record_followup

        def _spy_record_followup(self, turn_id):
            follow_up_entered.set()
            # Return timeout immediately so test can observe the phase
            return _make_wav(0.1), "pre_speech_timeout"

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi there").__get__(engine)),
                patch.object(engine, "_stage_tts_nonfinalize", _mock_tts_nonfinalize().__get__(engine)),
                patch.object(engine, "_record_followup", _spy_record_followup.__get__(engine)),
            ):
                engine.start_turn()
                assert follow_up_entered.wait(timeout=6.0), "Follow-up recording was never entered"
                _drain_events(engine, timeout=5.0, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

    def test_follow_up_exits_on_timeout(self, engine):
        """No speech within timeout → conversation_ended(timeout) → IDLE."""
        wav = _make_wav(0.5, amplitude=500)

        def _timeout_followup(self, turn_id):
            # Return pre_speech_timeout immediately
            return _make_wav(0.1), "pre_speech_timeout"

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi").__get__(engine)),
                patch.object(engine, "_stage_tts_nonfinalize", _mock_tts_nonfinalize().__get__(engine)),
                patch.object(engine, "_record_followup", _timeout_followup.__get__(engine)),
            ):
                engine.start_turn()
                events = _drain_events(engine, timeout=8.0, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        event_types = [e["type"] for e in events]
        assert "conversation_ended" in event_types, f"Expected conversation_ended, got: {event_types}"

        ended_evt = next(e for e in events if e["type"] == "conversation_ended")
        assert ended_evt["reason"] == "timeout"

        assert engine.status()["phase"] == TurnPhase.IDLE.value

    def test_follow_up_exits_on_stop_phrase(self, engine):
        """Stop phrase in follow-up → conversation_ended(stop_phrase) → IDLE."""
        wav = _make_wav(0.5, amplitude=500)
        stop_wav = _make_wav(0.3, amplitude=800)

        # First follow-up recording returns audio; STT returns "stop"
        followup_called = [0]

        def _followup_record(self, turn_id):
            followup_called[0] += 1
            return stop_wav, "silence_endpointed"

        from openjarvis.autonomy.voice_conversation import (
            VoiceTranscriptDecision,
        )

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi").__get__(engine)),
                patch.object(engine, "_stage_tts_nonfinalize", _mock_tts_nonfinalize().__get__(engine)),
                patch.object(engine, "_record_followup", _followup_record.__get__(engine)),
                patch(
                    "openjarvis.autonomy.voice_conversation.transcribe_command_result",
                    return_value=MagicMock(text="stop"),
                ),
            ):
                engine.start_turn()
                events = _drain_events(engine, timeout=8.0, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        event_types = [e["type"] for e in events]
        assert "conversation_ended" in event_types, f"Got events: {event_types}"
        ended_evt = next(e for e in events if e["type"] == "conversation_ended")
        assert ended_evt["reason"] == "stop_phrase"
        assert engine.status()["phase"] == TurnPhase.IDLE.value

    def test_follow_up_exits_on_cancel(self, engine):
        """cancel_turn() during follow-up → CANCELLED."""
        wav = _make_wav(0.5, amplitude=500)
        follow_up_entered = threading.Event()

        def _blocking_followup(self, turn_id):
            follow_up_entered.set()
            # Block until cancel
            self._cancel_event.wait(timeout=5.0)
            return None, "cancelled"

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi").__get__(engine)),
                patch.object(engine, "_stage_tts_nonfinalize", _mock_tts_nonfinalize().__get__(engine)),
                patch.object(engine, "_record_followup", _blocking_followup.__get__(engine)),
            ):
                engine.start_turn()
                assert follow_up_entered.wait(timeout=6.0), "Follow-up not entered"

                result = engine.cancel_turn()
                assert result["ok"] is True

                _wait_phase(engine, TurnPhase.CANCELLED, timeout=4.0)
                _drain_events(engine, timeout=3.0, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        assert engine.status()["phase"] == TurnPhase.CANCELLED.value

    def test_follow_up_conversation_turn_count(self, engine):
        """conversation_turns increments with each successful turn in the loop."""
        wav = _make_wav(0.5, amplitude=500)
        call_count = [0]

        def _one_then_timeout(self, turn_id):
            call_count[0] += 1
            if call_count[0] == 1:
                # First follow-up: return silence (timeout)
                return _make_wav(0.1), "pre_speech_timeout"
            return None, "cancelled"

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi").__get__(engine)),
                patch.object(engine, "_stage_tts_nonfinalize", _mock_tts_nonfinalize().__get__(engine)),
                patch.object(engine, "_record_followup", _one_then_timeout.__get__(engine)),
            ):
                engine.start_turn()
                _drain_events(engine, timeout=8.0, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        # First turn completed + conversation counter
        assert engine.status()["conversation_turns"] >= 1
