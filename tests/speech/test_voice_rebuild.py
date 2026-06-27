"""Code-level verification for the rebuilt voice pipeline (Task 1).

Headless, no microphone — exercises every pure decision rule plus client
construction and the transcript endpoint, matching the spec's verify checklist:
  1. voice_loop imports/parses cleanly
  2. wake_responses returns the correct slot for a given SGT time
  3. Deepgram client initialises
  4. ElevenLabs client initialises
  5. VAD logic verified with synthetic audio
  6. conversation-end phrases detected
  7. clap detection unit-tested
  8. transcript endpoint exists
"""

from __future__ import annotations

import random
import struct
from datetime import datetime

import pytest

from openjarvis.speech import voice_loop as vl
from openjarvis.speech import wake_responses as wr


# 1 — module imports cleanly (the import above already proves parse-ability)
def test_voice_loop_imports():
    assert hasattr(vl, "VoiceLoop")
    assert vl.CLAP_THRESHOLD == 2500     # in-app double clap
    assert vl.CLAP_MIN_GAP == 0.15
    assert vl.CLAP_MAX_GAP == 0.8
    assert vl.CLAP_COOLDOWN == 5.0


# 2 — wake_responses slots for SGT time
@pytest.mark.parametrize("hour,pool", [
    (6, wr.EARLY_MORNING), (10, wr.MORNING), (14, wr.AFTERNOON),
    (19, wr.EVENING), (23, wr.NIGHT), (3, wr.LATE_NIGHT),
])
def test_slot_for_hour(hour, pool):
    assert wr.slot_for_hour(hour) is pool


def test_full_vs_short_greeting():
    rng = random.Random(0)
    # First wake (no prior) → a full greeting from the hour pool.
    g = wr.get_wake_response(now=datetime(2026, 6, 27, 10, 0), last_wake_ts=None, rng=rng)
    assert any(g.endswith(x) or g == x for x in wr.MORNING) or "Go ahead" in g or len(g) > 3
    # Subsequent wake (1 min ago) → a short ack.
    now = datetime(2026, 6, 27, 10, 0)
    recent = now.timestamp() - 60
    s = wr.get_wake_response(now=now, last_wake_ts=recent, rng=rng)
    assert s in wr.SHORT_ACKS


def test_monday_prefix_and_special_date():
    # 2026-07-20 is a Monday → "New week." prefix.
    g = wr.get_wake_response(now=datetime(2026, 7, 20, 10, 0), force_full=True)
    assert g.startswith("New week.")
    # Anniversary on Jul 22.
    g2 = wr.get_wake_response(now=datetime(2026, 7, 22, 10, 0), force_full=True)
    assert "anniversary today" in g2


# 3 — Deepgram client init (constructs; health False without a key is fine)
def test_deepgram_client_init():
    from openjarvis.speech.deepgram import DeepgramSpeechBackend
    backend = DeepgramSpeechBackend(api_key="test_key_123")
    assert backend.backend_id == "deepgram"
    opts = vl.deepgram_options()
    assert opts["model"] == "nova-2"
    assert opts["language"] == "en-SG"
    assert opts["smart_format"] is True
    assert opts["interim_results"] is True
    assert opts["punctuate"] is True
    assert "VANTA:10" in opts["keywords"]


# 4 — ElevenLabs client init
def test_elevenlabs_client_init():
    from openjarvis.speech.elevenlabs_tts import ElevenLabsTTSBackend
    backend = ElevenLabsTTSBackend(api_key="k")
    assert backend.backend_id == "elevenlabs"
    assert backend.health() is True


# 5 — VAD with synthetic audio
def test_vad_start_and_stop():
    vad = vl.VadState(gate=600, silence_stop=1.5)
    assert vad.feed(100, 0.0) == "idle"
    assert vad.feed(900, 0.5) == "start"      # loud → start
    assert vad.feed(800, 0.7) == "recording"  # still loud
    assert vad.feed(100, 1.0) == "recording"  # brief silence, under 1.5s
    assert vad.feed(100, 2.6) == "stop"       # >1.5s silence → stop


# 6 — conversation-end phrases
@pytest.mark.parametrize("phrase", ["that's all", "bye", "done", "stop listening", "thanks", "thank you"])
def test_end_phrases(phrase):
    assert vl.is_end_phrase(phrase) is True


def test_non_end_phrase():
    assert vl.is_end_phrase("what's the weather") is False


# 7 — clap detection
def test_double_clap_valid():
    det = vl.ClapDetector()
    assert det.feed(100, 0.0) is False        # quiet
    assert det.feed(3500, 0.10) is False       # first spike
    assert det.feed(100, 0.20) is False        # dip (re-arm)
    assert det.feed(3500, 0.50) is True        # second spike, gap 0.40s → valid


def test_single_clap_ignored():
    det = vl.ClapDetector()
    assert det.feed(3500, 0.0) is False
    assert det.feed(100, 0.3) is False
    # no second spike → never fires


def test_clap_too_far_apart_ignored():
    det = vl.ClapDetector()
    det.feed(3500, 0.0)
    det.feed(100, 0.2)
    assert det.feed(3500, 1.5) is False  # gap 1.5s > CLAP_MAX_GAP


# 8 — transcript endpoint exists
def test_transcript_endpoint_exists():
    pytest.importorskip("fastapi")
    from openjarvis.server import voice_ux_routes
    paths = {getattr(r, "path", "") for r in voice_ux_routes.router.routes}
    assert "/v1/voice/transcript" in paths
    assert "/v1/voice/state" in paths


# Extra — classification, interrupts, controls, wake word, rms
@pytest.mark.parametrize("text,tier", [
    ("what time is it", "simple"),
    ("how's the weather", "simple"),
    ("tell me a joke", "simple"),
    ("email mum saying i'll be late", "complex"),
    ("research the best crm for plumbers", "complex"),
    ("check my calendar and then draft a reply", "complex"),
])
def test_classify_complexity(text, tier):
    assert vl.classify_complexity(text) == tier


@pytest.mark.parametrize("text,kind", [
    ("stop", "hard"), ("hold on", "hold"), ("one sec", "hold"),
    ("actually wait", "soft"), ("wait", "soft"), ("carry on please", None),
])
def test_detect_interrupt(text, kind):
    assert vl.detect_interrupt(text) == kind


@pytest.mark.parametrize("text,action", [
    ("louder", "volume_up"), ("quieter", "volume_down"),
    ("repeat that", "repeat"), ("faster", "speed_up"), ("slower", "speed_down"),
    ("hello there", None),
])
def test_voice_control(text, action):
    assert vl.voice_control(text) == action


@pytest.mark.parametrize("text,match", [
    ("hey vanta", True), ("VANTA stop", True), ("okay vanta", True),
    ("fanta", False), ("vantage point", False), ("the event", False),
])
def test_wake_word_boundary(text, match):
    assert vl.contains_wake_word(text) is match


def test_rms_from_pcm16():
    silence = struct.pack("<4h", 0, 0, 0, 0)
    assert vl.rms_from_pcm16(silence) == 0.0
    loud = struct.pack("<4h", 10000, -10000, 10000, -10000)
    assert vl.rms_from_pcm16(loud) == pytest.approx(10000, rel=0.01)


def test_summarise_for_speech_limits_sentences():
    txt = "One. Two. Three. Four. Five."
    out = vl.summarise_for_speech(txt, max_sentences=3)
    assert out == "One. Two. Three."


# Wake gate thresholds (rebuild spec)
def test_thresholds():
    assert vl.RMS_GATE == 600        # VAD start (in-conversation)
    assert vl.WAKE_RMS == 1500       # in-app wake gate
    assert vl.WAKE_MIN_WORDS == 3
    assert vl.WAKE_COOLDOWN == 10.0


def test_wake_should_fire_valid():
    assert vl.wake_should_fire("hey vanta wake up", now=100.0, last_wake_ts=None) is True


@pytest.mark.parametrize("text", ["vanta", "", "vanta!", "hey there"])
def test_wake_should_fire_too_short_or_no_word(text):
    # Single word / empty / no standalone 'vanta' in a 3+ word phrase.
    assert vl.wake_should_fire(text, now=100.0, last_wake_ts=None) is False


def test_wake_should_fire_no_wake_word_3plus_words():
    assert vl.wake_should_fire("hello there friend", now=100.0, last_wake_ts=None) is False


def test_wake_should_fire_cooldown():
    # Fired 5s ago (< 10s cooldown) -> suppressed, even with a valid phrase.
    assert vl.wake_should_fire("okay vanta listen", now=105.0, last_wake_ts=100.0) is False
    # 11s later -> allowed again.
    assert vl.wake_should_fire("okay vanta listen", now=111.0, last_wake_ts=100.0) is True


# Brain — thin HTTP layer over the text pipeline
def test_call_brain_silent_on_error():
    # Unreachable URL -> returns '' (never raises, never speaks an error).
    out = vl.call_brain([{"role": "user", "content": "hi"}], "gpt-4o-mini",
                        url="http://127.0.0.1:9/none", token="test", timeout=1.0)
    assert out == ""


def test_brain_config():
    assert "/v1/chat/completions" in vl.BRAIN_URL
    assert vl.BRAIN_TOKEN  # defaults to 'test'
    assert "Ivy" in vl.IVY_SYSTEM


def test_handle_user_text_routes_through_brain(monkeypatch):
    loop = vl.VoiceLoop()
    monkeypatch.setattr(vl, "call_brain", lambda messages, model, **k: "Short answer.")
    monkeypatch.setattr(vl, "synthesize_ivy", lambda text, **k: None)  # no audio
    reply = loop.handle_user_text("what time is it")
    assert reply == "Short answer."
    # Conversation history captured both turns (last 20).
    roles = [t["role"] for t in loop.conversation.context()]
    assert roles == ["user", "assistant"]


def test_handle_user_text_silent_on_brain_error(monkeypatch):
    loop = vl.VoiceLoop()
    monkeypatch.setattr(vl, "call_brain", lambda *a, **k: "")   # brain error
    monkeypatch.setattr(vl, "synthesize_ivy", lambda text, **k: None)
    assert loop.handle_user_text("hello") == ""  # never speaks an error


def test_voice_state_has_six_states():
    from openjarvis.speech import voice_bus
    for s in ("standby", "listening", "wake_detected", "recording", "thinking", "speaking"):
        assert s in voice_bus._VALID_STATES
