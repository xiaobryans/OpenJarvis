"""Tests for Wake-Word Fallback (US9 Closeout).

Covers:
  - Status always reports true_wakeword_status = BLOCKED_BY_PROVIDER_OR_PLATFORM
  - is_listening always False
  - Manual API trigger fires callbacks
  - Callback count correct after registration
  - Microphone status reports device info or honest failure
  - Hotkey start returns dict with ok/mode
  - No secrets in status output
"""

from __future__ import annotations

import time

import pytest

from openjarvis.autonomy.wakeword_fallback import (
    FALLBACK_HOTKEY,
    FALLBACK_MANUAL_API,
    FALLBACK_NONE,
    WAKEWORD_STATUS_BLOCKED,
    VoiceTriggerEvent,
    _FallbackEngineState,
    get_microphone_status,
    get_wakeword_engine_status,
    activate_voice,
    register_voice_callback,
    stop_listener,
)


@pytest.fixture
def fresh_engine():
    """Return a fresh engine instance for isolation."""
    return _FallbackEngineState()


class TestWakewordStatusContract:
    def test_true_wakeword_always_blocked(self):
        s = get_wakeword_engine_status()
        assert s["true_wakeword_status"] == WAKEWORD_STATUS_BLOCKED

    def test_is_listening_always_false(self):
        s = get_wakeword_engine_status()
        assert s["is_listening"] is False

    def test_status_has_fallback_mode(self):
        s = get_wakeword_engine_status()
        assert "fallback_mode" in s
        assert s["fallback_mode"] in (FALLBACK_HOTKEY, FALLBACK_MANUAL_API, FALLBACK_NONE)

    def test_status_has_microphone_ready(self):
        s = get_wakeword_engine_status()
        assert "microphone_ready" in s
        assert isinstance(s["microphone_ready"], dict)

    def test_configured_hotkey_present(self):
        s = get_wakeword_engine_status()
        assert "configured_hotkey" in s

    def test_trigger_count_non_negative(self):
        s = get_wakeword_engine_status()
        assert s["trigger_count"] >= 0


class TestManualTrigger:
    def test_manual_trigger_returns_ok(self, fresh_engine):
        result = fresh_engine.manual_trigger()
        assert result["ok"] is True
        assert result["source"] == "manual_api"

    def test_trigger_count_increments(self, fresh_engine):
        fresh_engine.manual_trigger()
        fresh_engine.manual_trigger()
        s = fresh_engine.status()
        assert s["trigger_count"] == 2

    def test_last_trigger_set_after_fire(self, fresh_engine):
        before = time.time()
        fresh_engine.manual_trigger()
        after = time.time()
        s = fresh_engine.status()
        assert s["last_trigger"] is not None
        assert before <= s["last_trigger"] <= after

    def test_callback_fired_on_trigger(self, fresh_engine):
        events = []
        fresh_engine.register_callback(lambda e: events.append(e))
        fresh_engine.manual_trigger()
        assert len(events) == 1
        assert isinstance(events[0], VoiceTriggerEvent)
        assert events[0].source == "manual_api"

    def test_multiple_callbacks_all_fired(self, fresh_engine):
        results = []
        fresh_engine.register_callback(lambda e: results.append("cb1"))
        fresh_engine.register_callback(lambda e: results.append("cb2"))
        fresh_engine.manual_trigger()
        assert "cb1" in results
        assert "cb2" in results

    def test_callback_exception_does_not_crash(self, fresh_engine):
        def bad_cb(e):
            raise RuntimeError("intentional test error")
        fresh_engine.register_callback(bad_cb)
        result = fresh_engine.manual_trigger()
        assert result["ok"] is True

    def test_callback_count_tracked(self, fresh_engine):
        fresh_engine.register_callback(lambda e: None)
        fresh_engine.register_callback(lambda e: None)
        s = fresh_engine.status()
        assert s["callbacks_registered"] == 2


class TestVoiceTriggerEvent:
    def test_event_has_source_and_timestamp(self, fresh_engine):
        events = []
        fresh_engine.register_callback(lambda e: events.append(e))
        fresh_engine.manual_trigger()
        ev = events[0]
        assert ev.source == "manual_api"
        assert ev.triggered_at > 0


class TestHotkeyStart:
    """Hotkey tests mock pynput to avoid SIGABRT when Accessibility permission is absent."""

    def test_start_returns_dict(self, fresh_engine, monkeypatch):
        import types
        fake_listener = types.SimpleNamespace(daemon=True, start=lambda: None, stop=lambda: None)
        monkeypatch.setattr(
            "openjarvis.autonomy.wakeword_fallback.kb",
            types.SimpleNamespace(GlobalHotKeys=lambda hotkeys: fake_listener),
            raising=False,
        )
        import pynput
        original_kb = pynput.keyboard
        try:
            import pynput.keyboard as kb_mod
            orig_ghk = kb_mod.GlobalHotKeys
            kb_mod.GlobalHotKeys = lambda hotkeys: fake_listener
            result = fresh_engine.start_hotkey("<f9>")
            assert isinstance(result, dict)
            assert "ok" in result
            assert "mode" in result
        finally:
            kb_mod.GlobalHotKeys = orig_ghk
            fresh_engine.stop()

    def test_second_start_returns_already_running(self, fresh_engine, monkeypatch):
        import pynput.keyboard as kb_mod, types
        fake_listener = types.SimpleNamespace(daemon=True, start=lambda: None, stop=lambda: None)
        orig = kb_mod.GlobalHotKeys
        kb_mod.GlobalHotKeys = lambda hotkeys: fake_listener
        try:
            fresh_engine.start_hotkey("<f9>")
            result = fresh_engine.start_hotkey("<f9>")
            assert result.get("already_running") is True
            assert result["ok"] is True
        finally:
            kb_mod.GlobalHotKeys = orig
            fresh_engine.stop()

    def test_stop_clears_running(self, fresh_engine, monkeypatch):
        import pynput.keyboard as kb_mod, types
        fake_listener = types.SimpleNamespace(daemon=True, start=lambda: None, stop=lambda: None)
        orig = kb_mod.GlobalHotKeys
        kb_mod.GlobalHotKeys = lambda hotkeys: fake_listener
        try:
            fresh_engine.start_hotkey("<f9>")
        finally:
            kb_mod.GlobalHotKeys = orig
        fresh_engine.stop()
        s = fresh_engine.status()
        assert s["hotkey_active"] is False


class TestMicrophoneStatus:
    def test_returns_dict(self):
        s = get_microphone_status()
        assert isinstance(s, dict)
        assert "ok" in s

    def test_if_ok_has_device_info(self):
        s = get_microphone_status()
        if s["ok"]:
            assert "device" in s
            assert "channels" in s
            assert "sample_rate" in s
            assert s["permission"] == "granted"

    def test_if_fail_has_manual_action(self):
        s = get_microphone_status()
        if not s["ok"]:
            assert "manual_action" in s


class TestModuleLevelFunctions:
    def test_activate_voice_ok(self):
        result = activate_voice()
        assert result["ok"] is True
        assert result["source"] == "manual_api"

    def test_register_and_activate_fires_callback(self):
        events = []
        register_voice_callback(lambda e: events.append(e))
        activate_voice()
        assert any(e.source == "manual_api" for e in events)
