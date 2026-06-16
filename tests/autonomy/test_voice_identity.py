"""Tests for Voice Identity / Auth for Voice Approvals (US9 Phase 7)."""

from __future__ import annotations

import time

import pytest

from openjarvis.autonomy.voice_identity import (
    IdentityChallenge,
    clear_for_tests,
    confirm_identity,
    get_identity_audit_log,
    get_voice_identity_status,
    issue_identity_challenge,
    reject_identity,
    requires_identity_challenge,
    set_operator_pin_hash,
    _SENSITIVE_ACTIONS,
)


@pytest.fixture(autouse=True)
def reset_state():
    clear_for_tests()
    yield
    clear_for_tests()


class TestSensitiveActions:
    def test_git_push_requires_challenge(self):
        assert requires_identity_challenge("git_push_to_fork") is True

    def test_slack_send_requires_challenge(self):
        assert requires_identity_challenge("real_slack_send_private") is True

    def test_read_only_does_not_require_challenge(self):
        assert requires_identity_challenge("read_only_check") is False

    def test_sensitive_actions_set_not_empty(self):
        assert len(_SENSITIVE_ACTIONS) > 3


class TestChallengeLifecycle:
    def test_issue_challenge_returns_challenge(self):
        ch = issue_identity_challenge("git_push_to_fork", "Push to fork")
        assert isinstance(ch, IdentityChallenge)
        assert ch.action_class == "git_push_to_fork"
        assert ch.status == "pending"
        assert not ch.consumed
        assert ch.expires_at > time.time()

    def test_challenge_has_nonce_and_token(self):
        ch = issue_identity_challenge("file_write", "Write config")
        assert len(ch.nonce) > 8
        assert len(ch.token) > 4

    def test_confirm_without_pin_when_none_configured(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        ch = issue_identity_challenge("file_write", "Write a file")
        result = confirm_identity(ch.challenge_id, approval_phrase="approve")
        assert result["ok"] is True
        assert result["status"] == "approved"

    def test_confirm_wrong_phrase_rejected(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        ch = issue_identity_challenge("file_write", "Write file")
        result = confirm_identity(ch.challenge_id, approval_phrase="maybe later")
        assert result["ok"] is False

    def test_confirm_requires_pin_when_configured(self, monkeypatch):
        pin_hash = set_operator_pin_hash("testpin123")
        monkeypatch.setenv("JARVIS_OPERATOR_PIN_HASH", pin_hash)
        ch = issue_identity_challenge("file_write", "Write")
        result = confirm_identity(ch.challenge_id, approval_phrase="approve", operator_pin="")
        assert result["ok"] is False
        assert "PIN" in result["error"]

    def test_confirm_correct_pin_approved(self, monkeypatch):
        pin_hash = set_operator_pin_hash("correctpin")
        monkeypatch.setenv("JARVIS_OPERATOR_PIN_HASH", pin_hash)
        ch = issue_identity_challenge("file_write", "Write")
        result = confirm_identity(
            ch.challenge_id,
            approval_phrase="confirm",
            operator_pin="correctpin",
        )
        assert result["ok"] is True

    def test_confirm_wrong_pin_fails(self, monkeypatch):
        pin_hash = set_operator_pin_hash("rightpin")
        monkeypatch.setenv("JARVIS_OPERATOR_PIN_HASH", pin_hash)
        ch = issue_identity_challenge("file_write", "Write")
        result = confirm_identity(
            ch.challenge_id,
            approval_phrase="approve",
            operator_pin="wrongpin",
        )
        assert result["ok"] is False


class TestReplayProtection:
    def test_challenge_consumed_after_approval(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        ch = issue_identity_challenge("file_write", "Write")
        confirm_identity(ch.challenge_id, approval_phrase="approve")
        # Second attempt should fail (consumed)
        result = confirm_identity(ch.challenge_id, approval_phrase="approve")
        assert result["ok"] is False
        assert "replay" in result["error"].lower() or "not found" in result["error"].lower()

    def test_expired_challenge_rejected(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        ch = issue_identity_challenge("file_write", "Write", ttl=0)
        time.sleep(0.1)
        result = confirm_identity(ch.challenge_id, approval_phrase="approve")
        assert result["ok"] is False
        assert "expired" in result["error"].lower()


class TestRejection:
    def test_reject_challenge(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        ch = issue_identity_challenge("file_write", "Write")
        result = reject_identity(ch.challenge_id)
        assert result["status"] == "rejected"


class TestAuditLog:
    def test_audit_log_records_approval(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        ch = issue_identity_challenge("file_write", "Write")
        confirm_identity(ch.challenge_id, approval_phrase="yes")
        log = get_identity_audit_log()
        events = [e["event"] for e in log]
        assert "identity_confirmed" in events

    def test_audit_log_records_rejection(self):
        ch = issue_identity_challenge("file_write", "Write")
        reject_identity(ch.challenge_id)
        log = get_identity_audit_log()
        events = [e["event"] for e in log]
        assert "identity_rejected" in events


class TestVoiceIdentityStatus:
    def test_status_active(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        s = get_voice_identity_status()
        assert s["active"] is True
        assert s["biometric_available"] is False
        assert "fallback" in s
        assert s["replay_protection"]
        assert s["expiry_protection"]

    def test_pin_not_configured_reflected(self, monkeypatch):
        monkeypatch.delenv("JARVIS_OPERATOR_PIN_HASH", raising=False)
        s = get_voice_identity_status()
        assert s["pin_configured"] is False
        assert "partial" in s["status"]
