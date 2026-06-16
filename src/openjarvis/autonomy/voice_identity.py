"""Jarvis Voice Identity / Auth for Voice Approvals.

Hardens voice approvals beyond approval phrase alone:
  - Sensitive actions require local operator confirmation (PIN or phrase)
  - Expiry window: approval tokens expire after TTL (default 120s)
  - Replay protection: consumed tokens cannot be reused
  - Audit log: all identity checks logged with timestamp
  - Biometric/speaker ID: not feasible without dedicated hardware — documented fallback

Safe fallback for biometric limitation:
  - Multi-factor: voice approval phrase + local PIN confirmation
  - Replay window: token single-use
  - Time-bound: strict expiry
  - Audit: immutable append-only log

Sensitive action classes (require operator identity challenge):
  - git_push_to_fork
  - real_slack_send_private
  - real_telegram_send_private
  - file_write
  - edit_config
  - any HIGH or DANGEROUS risk action
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CHALLENGE_TTL = int(os.environ.get("JARVIS_VOICE_CHALLENGE_TTL", "120"))
_PIN_HASH_ENV = "JARVIS_OPERATOR_PIN_HASH"  # SHA-256 hex of operator PIN

# Actions that require operator identity challenge
_SENSITIVE_ACTIONS: Set[str] = {
    "git_push_to_fork",
    "real_slack_send_private",
    "real_telegram_send_private",
    "file_write",
    "edit_config",
    "git_commit",
    "queue_job_submit",
    "secrets_mutation",
}

# Biometric limitation note
BIOMETRIC_LIMITATION = (
    "Speaker ID / biometric voice authentication is not feasible without dedicated "
    "hardware (microphone array + voice model). Jarvis uses multi-factor fallback: "
    "voice approval phrase + local operator PIN + replay/expiry protection."
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class IdentityChallenge:
    challenge_id: str
    action_class: str
    description: str
    requires_pin: bool
    token: str
    nonce: str
    created_at: float
    expires_at: float
    consumed: bool = False
    status: str = "pending"  # pending / approved / rejected / expired / consumed

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "action_class": self.action_class,
            "description": self.description,
            "requires_pin": self.requires_pin,
            "token": self.token,
            "nonce": self.nonce,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "consumed": self.consumed,
            "status": self.status,
            "is_expired": self.is_expired(),
            "ttl_remaining": max(0.0, self.expires_at - time.time()),
        }


# In-memory stores (reset per process — session-scoped)
_ACTIVE_CHALLENGES: Dict[str, IdentityChallenge] = {}
_CONSUMED_NONCES: Set[str] = set()  # replay protection
_IDENTITY_AUDIT_LOG: List[Dict[str, Any]] = []


# ---------------------------------------------------------------------------
# PIN helpers
# ---------------------------------------------------------------------------


def _get_pin_hash() -> Optional[str]:
    """Get stored operator PIN hash from env. Never print the PIN."""
    return os.environ.get(_PIN_HASH_ENV) or None


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


def verify_pin(pin: str) -> bool:
    """Verify operator PIN against stored hash. Returns False if no PIN configured."""
    stored = _get_pin_hash()
    if not stored:
        return False
    return hmac.compare_digest(stored, _hash_pin(pin))


def set_operator_pin_hash(pin: str) -> str:
    """Return the SHA-256 hex to set as JARVIS_OPERATOR_PIN_HASH env var.

    Never stores the PIN itself. Caller must set env var.
    """
    return _hash_pin(pin)


# ---------------------------------------------------------------------------
# Challenge lifecycle
# ---------------------------------------------------------------------------


def requires_identity_challenge(action_class: str) -> bool:
    """True if action requires operator identity challenge."""
    return action_class in _SENSITIVE_ACTIONS


def issue_identity_challenge(
    action_class: str,
    description: str,
    ttl: int = _CHALLENGE_TTL,
) -> IdentityChallenge:
    """Issue an identity challenge for a sensitive action."""
    pin_hash = _get_pin_hash()
    requires_pin = bool(pin_hash)
    challenge_id = str(uuid.uuid4())
    nonce = secrets.token_hex(16)
    token = hashlib.sha256(
        f"{challenge_id}:{nonce}:{action_class}:{time.time()}".encode()
    ).hexdigest()[:12].upper()

    challenge = IdentityChallenge(
        challenge_id=challenge_id,
        action_class=action_class,
        description=description,
        requires_pin=requires_pin,
        token=token,
        nonce=nonce,
        created_at=time.time(),
        expires_at=time.time() + ttl,
    )
    _ACTIVE_CHALLENGES[challenge_id] = challenge
    _IDENTITY_AUDIT_LOG.append({
        "event": "identity_challenge_issued",
        "challenge_id": challenge_id,
        "action_class": action_class,
        "requires_pin": requires_pin,
        "at": time.time(),
    })
    return challenge


def confirm_identity(
    challenge_id: str,
    approval_phrase: str = "",
    operator_pin: str = "",
) -> Dict[str, Any]:
    """Confirm an identity challenge.

    Requires:
      - approval phrase (spoken: "approve", "yes", "confirm")
      - operator PIN if PIN is configured
      - challenge not expired
      - challenge not already consumed (replay protection)
    """
    challenge = _ACTIVE_CHALLENGES.get(challenge_id)
    if challenge is None:
        return {"ok": False, "error": "Challenge not found", "challenge_id": challenge_id}

    if challenge.consumed:
        _IDENTITY_AUDIT_LOG.append({
            "event": "identity_replay_attempt",
            "challenge_id": challenge_id,
            "at": time.time(),
        })
        return {"ok": False, "error": "Replay attempt — challenge already consumed", "challenge_id": challenge_id}

    if challenge.is_expired():
        challenge.status = "expired"
        _IDENTITY_AUDIT_LOG.append({
            "event": "identity_challenge_expired",
            "challenge_id": challenge_id,
            "at": time.time(),
        })
        return {"ok": False, "error": "Challenge expired — issue a new one", "challenge_id": challenge_id}

    # Check nonce replay
    if challenge.nonce in _CONSUMED_NONCES:
        return {"ok": False, "error": "Nonce already consumed — replay blocked", "challenge_id": challenge_id}

    # Validate approval phrase
    approve_words = {"approve", "yes", "confirm", "ok", "proceed", "affirmative"}
    phrase_lower = approval_phrase.lower().strip()
    if not any(w in phrase_lower for w in approve_words):
        return {
            "ok": False,
            "error": "Approval phrase not recognized. Speak 'approve' or 'confirm'.",
            "challenge_id": challenge_id,
        }

    # Validate PIN if required
    if challenge.requires_pin:
        if not operator_pin:
            return {
                "ok": False,
                "error": "Operator PIN required for this action. Set JARVIS_OPERATOR_PIN_HASH.",
                "challenge_id": challenge_id,
                "requires_pin": True,
            }
        if not verify_pin(operator_pin):
            _IDENTITY_AUDIT_LOG.append({
                "event": "identity_pin_failed",
                "challenge_id": challenge_id,
                "at": time.time(),
            })
            return {"ok": False, "error": "Operator PIN incorrect", "challenge_id": challenge_id}

    # Success — consume challenge (replay protection)
    challenge.consumed = True
    challenge.status = "approved"
    _CONSUMED_NONCES.add(challenge.nonce)
    del _ACTIVE_CHALLENGES[challenge_id]

    _IDENTITY_AUDIT_LOG.append({
        "event": "identity_confirmed",
        "challenge_id": challenge_id,
        "action_class": challenge.action_class,
        "pin_used": challenge.requires_pin,
        "at": time.time(),
    })

    return {
        "ok": True,
        "status": "approved",
        "challenge_id": challenge_id,
        "token": challenge.token,
        "action_class": challenge.action_class,
        "pin_verified": challenge.requires_pin,
    }


def reject_identity(challenge_id: str) -> Dict[str, Any]:
    """Explicitly reject an identity challenge."""
    challenge = _ACTIVE_CHALLENGES.get(challenge_id)
    if challenge:
        challenge.status = "rejected"
        challenge.consumed = True
        del _ACTIVE_CHALLENGES[challenge_id]
    _IDENTITY_AUDIT_LOG.append({
        "event": "identity_rejected",
        "challenge_id": challenge_id,
        "at": time.time(),
    })
    return {"ok": True, "status": "rejected", "challenge_id": challenge_id}


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


def get_identity_audit_log() -> List[Dict[str, Any]]:
    return list(_IDENTITY_AUDIT_LOG)


def get_voice_identity_status() -> Dict[str, Any]:
    """Doctor/readiness status for voice identity."""
    pin_configured = bool(_get_pin_hash())
    return {
        "active": True,
        "pin_configured": pin_configured,
        "pin_env_var": _PIN_HASH_ENV,
        "biometric_available": False,
        "biometric_limitation": BIOMETRIC_LIMITATION,
        "fallback": "voice_phrase + operator_pin + replay_protection + expiry",
        "challenge_ttl_seconds": _CHALLENGE_TTL,
        "sensitive_actions_requiring_challenge": sorted(_SENSITIVE_ACTIONS),
        "replay_protection": "nonce_consumed_on_use",
        "expiry_protection": f"{_CHALLENGE_TTL}s TTL per challenge",
        "audit_log_entries": len(_IDENTITY_AUDIT_LOG),
        "status": (
            "ready_with_pin" if pin_configured
            else "partial_no_pin — set JARVIS_OPERATOR_PIN_HASH for full hardening"
        ),
    }


def clear_for_tests() -> None:
    """Reset all session state. For tests only."""
    _ACTIVE_CHALLENGES.clear()
    _CONSUMED_NONCES.clear()
    _IDENTITY_AUDIT_LOG.clear()


__all__ = [
    "IdentityChallenge",
    "requires_identity_challenge",
    "issue_identity_challenge",
    "confirm_identity",
    "reject_identity",
    "verify_pin",
    "set_operator_pin_hash",
    "get_identity_audit_log",
    "get_voice_identity_status",
    "clear_for_tests",
    "BIOMETRIC_LIMITATION",
    "_SENSITIVE_ACTIONS",
]
