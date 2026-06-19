"""Tests for the deterministic VoiceTurnEngine (voice_turn_engine.py).

Validation coverage:
  1. manual_turn_complete         — full turn with mocked STT/engine/TTS
  2. end_and_send                 — End & send submits audio immediately
  3. empty_audio_rejected         — empty audio fails before STT
  4. short_audio_rejected         — sub-minimum audio fails before STT
  5. stt_timeout_surfaces_error   — STT timeout → error phase with message
  6. route_timeout_surfaces_error — route/model timeout → error phase
  7. cancel_during_recording      — cancel sets phase=cancelled
  8. cancel_during_thinking       — cancel during engine routing
  9. no_double_start              — second start_turn rejected while running
 10. wake_cannot_start_turn       — wake-word path cannot trigger start_turn
                                    (engine has no wake integration)
 11. validate_audio_direct        — _validate_audio unit tests
 12. no_infinite_state            — turn must complete and set IDLE
"""

from __future__ import annotations

import io
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
    _validate_audio,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Build a minimal valid WAV with silence."""
    n_frames = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *([0] * n_frames)))
    return buf.getvalue()


def _make_engine(**kwargs) -> VoiceTurnEngine:
    """Engine with short timeouts for testing."""
    e = VoiceTurnEngine(**kwargs)
    return e


def _drain_events(
    engine: VoiceTurnEngine,
    timeout: float = 5.0,
    pre_subscribed_q: "queue.Queue | None" = None,
) -> List[dict]:
    """Collect all events until turn_done (or timeout).

    Pass pre_subscribed_q to use a queue that was subscribed BEFORE start_turn()
    to avoid missing events from fast-running mocked stages.
    """
    import queue as _queue
    q = pre_subscribed_q if pre_subscribed_q is not None else engine.subscribe()
    events: List[dict] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            evt = q.get(timeout=0.2)
        except _queue.Empty:
            continue
        except Exception:
            continue
        events.append(evt)
        if evt.get("type") == "turn_done":
            break
    if pre_subscribed_q is None:
        engine.unsubscribe(q)
    return events


def _wait_phase(engine: VoiceTurnEngine, target: TurnPhase, timeout: float = 8.0) -> bool:
    """Busy-wait until engine phase == target."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if engine.status()["phase"] == target.value:
            return True
        time.sleep(0.05)
    return False


# ---------------------------------------------------------------------------
# Tests: _validate_audio
# ---------------------------------------------------------------------------


class TestValidateAudio:
    def test_empty_bytes(self):
        v = _validate_audio(b"")
        assert not v["ok"]
        assert v["reason"] == "empty_audio"

    def test_too_short_bytes(self):
        v = _validate_audio(b"\x00" * 10)
        assert not v["ok"]
        assert "short" in v["reason"]

    def test_invalid_wav(self):
        v = _validate_audio(b"RIFF" + b"\x00" * 500)
        assert not v["ok"]
        assert "wav_parse_error" in v["reason"]

    def test_valid_wav(self):
        wav = _make_wav(0.5)
        v = _validate_audio(wav)
        assert v["ok"]
        assert v["duration_s"] == pytest.approx(0.5, abs=0.05)
        assert v["sample_rate"] == 16000

    def test_too_short_duration(self):
        # 0.05s < _MIN_AUDIO_DURATION_S (0.1s)
        wav = _make_wav(0.05)
        v = _validate_audio(wav)
        assert not v["ok"]
        assert "duration_too_short" in v["reason"]


# ---------------------------------------------------------------------------
# Tests: VoiceTurnEngine
# ---------------------------------------------------------------------------


@pytest.fixture()
def engine():
    return _make_engine()


# Patch targets
_RECORD_PATH = "openjarvis.autonomy.voice_turn_engine.VoiceTurnEngine._stage_record"
_STT_PATH = "openjarvis.autonomy.voice_turn_engine.VoiceTurnEngine._stage_stt"
_ROUTE_PATH = "openjarvis.autonomy.voice_turn_engine.VoiceTurnEngine._stage_route"
_TTS_PATH = "openjarvis.autonomy.voice_turn_engine.VoiceTurnEngine._stage_tts"


def _mock_record(wav: bytes):
    """Return a mock for _stage_record that yields a valid WAV."""
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


def _mock_tts():
    def _impl(self, turn_id, text):
        self._set_phase(TurnPhase.SPEAKING)
        # Complete normally
        if self._is_turn_live(turn_id) and not self._cancel_event.is_set():
            self._set_phase(TurnPhase.IDLE, reason="turn_complete")
        self._finalize(turn_id)
    return _impl


class TestTurnComplete:
    """Requirement 1: manual turn completes with mocked STT/TTS path."""

    def test_full_turn_reaches_idle(self, engine):
        wav = _make_wav(0.5)

        # Subscribe BEFORE start_turn to capture all events (mocked stages are fast)
        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine, VoiceTurnEngine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello jarvis").__get__(engine, VoiceTurnEngine)),
                patch.object(engine, "_stage_route", _mock_route("Hi there!").__get__(engine, VoiceTurnEngine)),
                patch.object(engine, "_stage_tts", _mock_tts().__get__(engine, VoiceTurnEngine)),
            ):
                result = engine.start_turn()
                assert result["ok"] is True
                events = _drain_events(engine, timeout=6, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        etypes = [e["type"] for e in events]
        assert "transcript" in etypes, f"got event types: {etypes}"
        assert "response" in etypes
        assert "turn_done" in etypes

        status = engine.status()
        assert status["phase"] == TurnPhase.IDLE.value
        assert status["last_transcript"] == "hello jarvis"
        assert status["last_response"] == "Hi there!"

    def test_state_sequence_order(self, engine):
        """State transitions must follow the expected order."""
        wav = _make_wav(0.5)
        states: List[str] = []

        def _recording_stage(self, turn_id):
            return wav, True

        def _stt_stage(self, turn_id, audio, language):
            states.append("transcribing")
            self._set_phase(TurnPhase.TRANSCRIBING)
            self._last_transcript = "test"
            return "test"

        def _route_stage(self, turn_id, text):
            states.append("thinking")
            self._set_phase(TurnPhase.THINKING)
            self._last_response = "ok"
            return "ok"

        def _tts_stage(self, turn_id, text):
            states.append("speaking")
            self._set_phase(TurnPhase.SPEAKING)
            if self._is_turn_live(turn_id) and not self._cancel_event.is_set():
                self._set_phase(TurnPhase.IDLE, reason="turn_complete")
            self._finalize(turn_id)

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _recording_stage.__get__(engine)),
                patch.object(engine, "_stage_stt", _stt_stage.__get__(engine)),
                patch.object(engine, "_stage_route", _route_stage.__get__(engine)),
                patch.object(engine, "_stage_tts", _tts_stage.__get__(engine)),
            ):
                engine.start_turn()
                _drain_events(engine, timeout=5, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        assert states == ["transcribing", "thinking", "speaking"]


class TestEndAndSend:
    """Requirement 2: End & send submits captured audio immediately."""

    def test_end_recording_fires_abort_event(self, engine):
        abort_set = threading.Event()

        def _recording_that_waits(self, turn_id):
            # Simulate long recording; abort_event will be set
            self._recording_abort.wait(timeout=3.0)
            abort_set.set()
            wav = _make_wav(0.3)
            return wav, True

        with (
            patch.object(engine, "_stage_record", _recording_that_waits.__get__(engine)),
            patch.object(engine, "_stage_stt", _mock_stt("test").__get__(engine)),
            patch.object(engine, "_stage_route", _mock_route("ok").__get__(engine)),
            patch.object(engine, "_stage_tts", _mock_tts().__get__(engine)),
        ):
            engine.start_turn()
            _wait_phase(engine, TurnPhase.RECORDING, timeout=1.0)

            result = engine.end_recording_now()
            assert result["ok"] is True
            assert abort_set.wait(timeout=3.0), "abort_event was not set"

    def test_end_recording_rejected_when_idle(self, engine):
        result = engine.end_recording_now()
        assert result["ok"] is False
        assert result["error_code"] == "not_recording"


class TestEmptyAudioRejected:
    """Requirement 3: empty audio fails before STT."""

    def test_empty_bytes_never_reaches_stt(self, engine):
        stt_called = threading.Event()

        def _empty_record(self, turn_id):
            return b"", True  # empty bytes

        def _stt_spy(self, turn_id, audio, language):
            stt_called.set()
            return "should not reach"

        with (
            patch.object(engine, "_stage_record", _empty_record.__get__(engine)),
            patch.object(engine, "_stage_stt", _stt_spy.__get__(engine)),
        ):
            engine.start_turn()
            _wait_phase(engine, TurnPhase.ERROR, timeout=5.0)

        assert not stt_called.is_set(), "STT was called despite empty audio"
        assert engine.status()["phase"] == TurnPhase.ERROR.value
        assert "audio_invalid" in (engine.status()["last_error"] or "")

    def test_short_wav_never_reaches_stt(self, engine):
        stt_called = threading.Event()

        def _short_record(self, turn_id):
            return _make_wav(0.05), True  # too short

        def _stt_spy(self, turn_id, audio, language):
            stt_called.set()
            return "nope"

        with (
            patch.object(engine, "_stage_record", _short_record.__get__(engine)),
            patch.object(engine, "_stage_stt", _stt_spy.__get__(engine)),
        ):
            engine.start_turn()
            _wait_phase(engine, TurnPhase.ERROR, timeout=5.0)

        assert not stt_called.is_set()
        assert engine.status()["phase"] == TurnPhase.ERROR.value


class TestSTTTimeout:
    """Requirement 4: STT timeout surfaces visible error."""

    def test_stt_timeout_sets_error_phase(self, engine):
        import openjarvis.autonomy.voice_turn_engine as mod

        original_timeout = mod._STT_TIMEOUT_S
        mod._STT_TIMEOUT_S = 0.1  # 100ms timeout for test

        wav = _make_wav(0.5)

        def _slow_stt_impl(*_args, **_kwargs):
            time.sleep(2.0)  # longer than timeout
            return MagicMock(text="should not happen")

        def _recording_stage(self, turn_id):
            return wav, True

        try:
            with (
                patch.object(engine, "_stage_record", _recording_stage.__get__(engine)),
                patch(
                    "openjarvis.autonomy.voice_conversation.transcribe_command_result",
                    side_effect=_slow_stt_impl,
                ),
            ):
                engine.start_turn()
                reached_error = _wait_phase(engine, TurnPhase.ERROR, timeout=6.0)
        finally:
            mod._STT_TIMEOUT_S = original_timeout

        assert reached_error, f"Expected ERROR phase, got {engine.status()['phase']}"
        error = engine.status()["last_error"] or ""
        assert "timeout" in error.lower() or "stt" in error.lower()


class TestRouteTimeout:
    """Requirement 5: route/model timeout surfaces visible error."""

    def test_route_timeout_sets_error_phase(self, engine):
        import openjarvis.autonomy.voice_turn_engine as mod

        original_timeout = mod._ROUTE_TIMEOUT_S
        mod._ROUTE_TIMEOUT_S = 0.1

        wav = _make_wav(0.5)

        def _slow_route(*_args, **_kwargs):
            time.sleep(2.0)
            return "should not happen"

        def _recording_stage(self, turn_id):
            return wav, True

        try:
            with (
                patch.object(engine, "_stage_record", _recording_stage.__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("query").__get__(engine)),
                patch(
                    "openjarvis.autonomy.voice_conversation.query_jarvis_text",
                    side_effect=_slow_route,
                ),
            ):
                engine.start_turn()
                reached_error = _wait_phase(engine, TurnPhase.ERROR, timeout=6.0)
        finally:
            mod._ROUTE_TIMEOUT_S = original_timeout

        assert reached_error, f"Expected ERROR phase, got {engine.status()['phase']}"
        error = engine.status()["last_error"] or ""
        assert "timeout" in error.lower() or "route" in error.lower()


class TestCancel:
    """Requirement 6: cancel sets CANCELLED phase."""

    def test_cancel_during_recording(self, engine):
        recording_started = threading.Event()

        def _blocking_record(self, turn_id):
            recording_started.set()
            self._cancel_event.wait(timeout=5.0)
            return _make_wav(0.3), True

        with (
            patch.object(engine, "_stage_record", _blocking_record.__get__(engine)),
            patch.object(engine, "_stage_stt", _mock_stt("x").__get__(engine)),
        ):
            engine.start_turn()
            assert recording_started.wait(timeout=2.0)

            result = engine.cancel_turn()
            assert result["ok"] is True
            _wait_phase(engine, TurnPhase.CANCELLED, timeout=3.0)

        assert engine.status()["phase"] == TurnPhase.CANCELLED.value

    def test_cancel_during_thinking(self, engine):
        thinking_started = threading.Event()

        def _blocking_route(self, turn_id, text):
            self._set_phase(TurnPhase.THINKING)
            thinking_started.set()
            self._cancel_event.wait(timeout=5.0)
            if self._cancel_event.is_set():
                self._set_phase(TurnPhase.CANCELLED)
                self._finalize(turn_id)
                return None
            return "response"

        wav = _make_wav(0.5)

        with (
            patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
            patch.object(engine, "_stage_stt", _mock_stt("query").__get__(engine)),
            patch.object(engine, "_stage_route", _blocking_route.__get__(engine)),
        ):
            engine.start_turn()
            assert thinking_started.wait(timeout=3.0)

            engine.cancel_turn()
            _wait_phase(engine, TurnPhase.CANCELLED, timeout=3.0)

        assert engine.status()["phase"] == TurnPhase.CANCELLED.value


class TestNoDoubleStart:
    """Requirement 7: second start_turn rejected while turn in progress."""

    def test_double_start_rejected(self, engine):
        recording_started = threading.Event()

        def _blocking_record(self, turn_id):
            recording_started.set()
            time.sleep(2.0)
            return _make_wav(0.3), True

        with patch.object(engine, "_stage_record", _blocking_record.__get__(engine)):
            r1 = engine.start_turn()
            assert r1["ok"] is True
            assert recording_started.wait(timeout=2.0)

            r2 = engine.start_turn()
            assert r2["ok"] is False
            assert r2["error_code"] == "turn_in_progress"

            engine.cancel_turn()


class TestWakeCannotStartTurn:
    """Requirement 8: wake-word / background cannot auto-start commands.

    The new engine has no wake-word integration. start_turn() requires an
    explicit call — there is no event loop, no wake listener, no background
    thread that could auto-trigger a turn.
    """

    def test_engine_starts_idle(self):
        e = VoiceTurnEngine()
        assert e.status()["phase"] == TurnPhase.IDLE.value

    def test_no_background_recording_on_init(self):
        """Engine must not start recording automatically on construction."""
        e = VoiceTurnEngine()
        time.sleep(0.2)  # give any hypothetical background threads time to start
        assert e.status()["phase"] == TurnPhase.IDLE.value

    def test_turn_requires_explicit_call(self):
        """Phase must remain IDLE unless start_turn() is called."""
        e = VoiceTurnEngine()
        for _ in range(10):
            time.sleep(0.05)
            assert e.status()["phase"] == TurnPhase.IDLE.value


class TestNoInfiniteState:
    """Requirement 9: turn must complete and return to IDLE/ERROR/CANCELLED."""

    def test_turn_completes_in_time(self, engine):
        wav = _make_wav(0.5)

        q = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi").__get__(engine)),
                patch.object(engine, "_stage_tts", _mock_tts().__get__(engine)),
            ):
                engine.start_turn()
                _drain_events(engine, timeout=8, pre_subscribed_q=q)
        finally:
            engine.unsubscribe(q)

        final = engine.status()["phase"]
        assert final in (TurnPhase.IDLE.value, TurnPhase.ERROR.value, TurnPhase.CANCELLED.value), (
            f"Turn engine stuck in phase={final!r}"
        )
        assert final == TurnPhase.IDLE.value

    def test_after_error_phase_new_turn_can_start(self, engine):
        """Engine must accept a new turn after an error."""
        def _error_record(self, turn_id):
            # Return empty bytes to trigger audio validation error
            return b"", True

        with patch.object(engine, "_stage_record", _error_record.__get__(engine)):
            engine.start_turn()
            _wait_phase(engine, TurnPhase.ERROR, timeout=5.0)

        assert engine.status()["phase"] == TurnPhase.ERROR.value

        # Can start a new turn immediately
        wav = _make_wav(0.5)
        q2 = engine.subscribe()
        try:
            with (
                patch.object(engine, "_stage_record", _mock_record(wav).__get__(engine)),
                patch.object(engine, "_stage_stt", _mock_stt("hello").__get__(engine)),
                patch.object(engine, "_stage_route", _mock_route("hi").__get__(engine)),
                patch.object(engine, "_stage_tts", _mock_tts().__get__(engine)),
            ):
                result = engine.start_turn()
                assert result["ok"] is True
                _drain_events(engine, timeout=6, pre_subscribed_q=q2)
        finally:
            engine.unsubscribe(q2)

        assert engine.status()["phase"] == TurnPhase.IDLE.value
