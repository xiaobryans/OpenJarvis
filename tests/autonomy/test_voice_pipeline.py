"""Tests for VoicePipeline — wake-word, STT, TTS, voice approval (US8 Phase D).

Covers:
  - get_wake_word_status returns valid engine field and phrases
  - is_listening always False unless engine actually started
  - get_stt_status returns valid engine field
  - get_tts_status returns valid engine field
  - get_voice_status aggregates all three
  - tts_test returns ok or blocker dict (never raises)
  - stt_test returns config status (no actual recording)
  - parse_voice_approval classifies approve/reject/hold/unknown
  - issue_approval_challenge creates valid challenge
  - confirm_voice_approval approve/reject paths
  - confirm expired challenge returns error
  - voice hard-blocked actions cannot get a challenge
  - preview_command returns preview_only=True
  - get_approval_audit_log returns list
"""

from __future__ import annotations

import time

import pytest

from openjarvis.autonomy.voice_pipeline import (
    ApprovalChallenge,
    STTEngine,
    TTSEngine,
    VoiceApprovalRisk,
    WakeWordEngine,
    clear_for_tests,
    confirm_voice_approval,
    get_approval_audit_log,
    get_stt_status,
    get_tts_status,
    get_voice_status,
    get_wake_word_status,
    issue_approval_challenge,
    parse_voice_approval,
    preview_command,
    stt_test,
    tts_test,
)


@pytest.fixture(autouse=True)
def clean_voice():
    clear_for_tests()
    yield
    clear_for_tests()


class TestWakeWordStatus:
    def test_returns_wake_word_status_field(self):
        status = get_wake_word_status()
        assert "wake_word_status" in status
        assert status["wake_word_status"] in (
            WakeWordEngine.OPENWAKEWORD,
            WakeWordEngine.PVPORCUPINE,
            WakeWordEngine.NOT_CONFIGURED,
        )

    def test_is_listening_always_false(self):
        status = get_wake_word_status()
        assert status["is_listening"] is False

    def test_phrases_present(self):
        status = get_wake_word_status()
        assert "phrases" in status
        phrases = status["phrases"]
        assert any("jarvis" in p.lower() for p in phrases)

    def test_not_configured_has_install_commands(self):
        status = get_wake_word_status()
        if status["wake_word_status"] == WakeWordEngine.NOT_CONFIGURED:
            assert "install_commands" in status or "blockers" in status


class TestSTTStatus:
    def test_returns_stt_status_field(self):
        status = get_stt_status()
        assert "stt_status" in status
        assert status["stt_status"] in (
            STTEngine.FASTER_WHISPER,
            STTEngine.OPENAI_WHISPER,
            STTEngine.DEEPGRAM,
            STTEngine.NOT_CONFIGURED,
        )

    def test_has_is_configured_field(self):
        status = get_stt_status()
        assert "is_configured" in status

    def test_not_configured_has_blockers(self):
        status = get_stt_status()
        if status["stt_status"] == STTEngine.NOT_CONFIGURED:
            assert "blockers" in status


class TestTTSStatus:
    def test_returns_tts_status_field(self):
        status = get_tts_status()
        assert "tts_status" in status
        assert status["tts_status"] in (
            TTSEngine.MACOS_SAY,
            TTSEngine.OPENAI_TTS,
            TTSEngine.NOT_CONFIGURED,
        )

    def test_has_is_configured_field(self):
        status = get_tts_status()
        assert "is_configured" in status


class TestVoiceStatus:
    def test_returns_voice_status_field(self):
        status = get_voice_status()
        assert "voice_status" in status
        assert status["voice_status"] in (
            "configured_not_started",
            "partial_no_wake_word",
            "tts_only",
            "not_configured",
        )

    def test_has_fully_configured_field(self):
        status = get_voice_status()
        assert "fully_configured" in status
        assert isinstance(status["fully_configured"], bool)

    def test_aggregates_all_three_engines(self):
        status = get_voice_status()
        assert "wake_word" in status
        assert "stt" in status
        assert "tts" in status

    def test_push_to_talk_available_field(self):
        status = get_voice_status()
        assert "push_to_talk_available" in status


class TestTTSTest:
    def test_returns_dict_never_raises(self):
        result = tts_test("Test.")
        assert isinstance(result, dict)

    def test_has_engine_field(self):
        result = tts_test("Test.")
        assert "engine" in result

    def test_ok_field_is_bool(self):
        result = tts_test("Test.")
        assert isinstance(result.get("ok"), bool)


class TestSTTTest:
    def test_returns_dict_never_raises(self):
        result = stt_test()
        assert isinstance(result, dict)

    def test_has_stt_engine_field(self):
        result = stt_test()
        assert "stt_engine" in result

    def test_does_not_record_audio(self):
        result = stt_test()
        assert "note" in result
        assert "not record" in result["note"].lower()


class TestParseVoiceApproval:
    def test_approve_words(self):
        for phrase in ["yes", "approve", "confirm", "ok", "proceed"]:
            r = parse_voice_approval(phrase)
            assert r["intent"] == "approve", f"'{phrase}' should be approve"

    def test_reject_words(self):
        for phrase in ["no", "reject", "cancel", "stop", "abort"]:
            r = parse_voice_approval(phrase)
            assert r["intent"] == "reject", f"'{phrase}' should be reject"

    def test_hold_words(self):
        for phrase in ["hold", "wait", "pause"]:
            r = parse_voice_approval(phrase)
            assert r["intent"] == "hold", f"'{phrase}' should be hold"

    def test_unknown_returns_unknown(self):
        r = parse_voice_approval("blah blah blah")
        assert r["intent"] == "unknown"
        assert r["confidence"] == 0.0

    def test_returns_raw_field(self):
        r = parse_voice_approval("yes please")
        assert "raw" in r


class TestVoiceApprovalChallenge:
    def test_issue_creates_challenge(self):
        result = issue_approval_challenge("draft_slack_message", "test action")
        assert isinstance(result, ApprovalChallenge)
        assert result.challenge_id
        assert result.token
        assert result.status == "pending"
        assert result.expires_at > time.time()

    def test_hard_blocked_action_raises(self):
        with pytest.raises(ValueError, match="voice-hard-blocked"):
            issue_approval_challenge("production_deploy", "test")

    def test_confirm_approve(self):
        challenge = issue_approval_challenge("draft_slack_message", "test")
        result = confirm_voice_approval(challenge.challenge_id, "yes")
        assert result["ok"] is True
        assert result["status"] == "approved"

    def test_confirm_reject(self):
        challenge = issue_approval_challenge("draft_slack_message", "test")
        result = confirm_voice_approval(challenge.challenge_id, "no")
        assert result["ok"] is False
        assert result["status"] == "rejected"

    def test_confirm_unknown_challenge_id(self):
        result = confirm_voice_approval("nonexistent-id", "yes")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_confirm_expired_challenge(self):
        challenge = issue_approval_challenge("draft_slack_message", "test")
        challenge.expires_at = time.time() - 1
        result = confirm_voice_approval(challenge.challenge_id, "yes")
        assert result["ok"] is False
        assert "expired" in result["error"]

    def test_challenge_to_dict(self):
        challenge = issue_approval_challenge("draft_slack_message", "test")
        d = challenge.to_dict()
        required = [
            "challenge_id", "token", "action_class", "risk_level",
            "expires_at", "status", "is_expired",
        ]
        for k in required:
            assert k in d, f"Missing key: {k}"

    def test_audit_log_recorded_on_approve(self):
        challenge = issue_approval_challenge("draft_slack_message", "test")
        confirm_voice_approval(challenge.challenge_id, "approve")
        log = get_approval_audit_log()
        assert len(log) >= 1
        events = [e["event"] for e in log]
        assert "voice_approval_confirmed" in events

    def test_audit_log_recorded_on_reject(self):
        challenge = issue_approval_challenge("draft_slack_message", "test")
        confirm_voice_approval(challenge.challenge_id, "reject")
        log = get_approval_audit_log()
        events = [e["event"] for e in log]
        assert "voice_approval_rejected" in events


class TestVoiceCommandPreview:
    def test_returns_preview_only_true(self):
        result = preview_command("run watchdogs")
        assert result["preview_only"] is True

    def test_returns_voice_pipeline_status(self):
        result = preview_command("status please")
        assert "voice_pipeline_status" in result

    def test_no_action_taken(self):
        result = preview_command("delete everything")
        assert result["preview_only"] is True
        assert "note" in result
