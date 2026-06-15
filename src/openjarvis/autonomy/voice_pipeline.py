"""Jarvis Voice Pipeline — wake-word detection, STT/TTS status, voice approval layer.

Target behavior (honest implementation):
  Wake word: "Jarvis" or "Hey Jarvis"
  Engine priority: openwakeword (free) > pvporcupine (needs access key) > not_configured
  STT: faster-whisper (local) > openai whisper > deepgram > not_configured
  TTS: macOS say (built-in, always available on macOS) > openai TTS > not_configured

Voice approval layer:
  - low-risk actions: no approval challenge
  - medium-risk: voice approve/reject accepted
  - high-risk: voice + confirmation phrase required
  - dangerous/prod/billing/secrets/destructive: always_blocked (no voice override)

Honest status contract:
  - wake_word_status: openwakeword/pvporcupine/not_configured
  - is_listening: ONLY True if engine is actually running
  - stt_status: faster_whisper/openai_whisper/deepgram/not_configured
  - tts_status: macos_say/openai_tts/not_configured
  - microphone_permission: see desktop_operator.py
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Engine / status constants
# ---------------------------------------------------------------------------


class WakeWordEngine:
    OPENWAKEWORD = "openwakeword"
    PVPORCUPINE = "pvporcupine"
    NOT_CONFIGURED = "not_configured"


class STTEngine:
    FASTER_WHISPER = "faster_whisper"
    OPENAI_WHISPER = "openai_whisper"
    DEEPGRAM = "deepgram"
    NOT_CONFIGURED = "not_configured"


class TTSEngine:
    MACOS_SAY = "macos_say"
    OPENAI_TTS = "openai_tts"
    NOT_CONFIGURED = "not_configured"


class VoiceApprovalRisk:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    DANGEROUS = "dangerous"


# ---------------------------------------------------------------------------
# Wake-word engine checks
# ---------------------------------------------------------------------------


def _check_openwakeword() -> Dict[str, Any]:
    try:
        import openwakeword  # noqa: F401
        return {
            "available": True,
            "engine": WakeWordEngine.OPENWAKEWORD,
            "blocker": (
                "openwakeword importable but model not loaded — "
                "requires audio input device and microphone permission"
            ),
        }
    except ImportError:
        return {
            "available": False,
            "engine": WakeWordEngine.NOT_CONFIGURED,
            "blocker": "openwakeword not installed — run: pip install openwakeword",
        }


def _check_pvporcupine() -> Dict[str, Any]:
    try:
        import pvporcupine  # noqa: F401
        access_key = os.environ.get("JARVIS_WAKEWORD_ACCESS_KEY", "")
        if not access_key:
            return {
                "available": False,
                "engine": WakeWordEngine.NOT_CONFIGURED,
                "blocker": (
                    "pvporcupine installed but JARVIS_WAKEWORD_ACCESS_KEY not set — "
                    "get free key at picovoice.ai"
                ),
            }
        return {
            "available": True,
            "engine": WakeWordEngine.PVPORCUPINE,
            "blocker": (
                "pvporcupine configured but model not started — "
                "call VoicePipeline.start() with microphone permission"
            ),
        }
    except ImportError:
        return {
            "available": False,
            "engine": WakeWordEngine.NOT_CONFIGURED,
            "blocker": (
                "pvporcupine not installed — "
                "run: pip install pvporcupine (also needs JARVIS_WAKEWORD_ACCESS_KEY)"
            ),
        }


def get_wake_word_status() -> Dict[str, Any]:
    """Check wake-word engine availability. Never claims is_listening=True unless actually running."""
    oww = _check_openwakeword()
    if oww["available"]:
        return {
            "wake_word_status": WakeWordEngine.OPENWAKEWORD,
            "engine": WakeWordEngine.OPENWAKEWORD,
            "phrases": ["jarvis", "hey jarvis"],
            "is_listening": False,
            "blocker": oww.get("blocker", ""),
            "install_command": None,
        }
    pvp = _check_pvporcupine()
    if pvp["available"]:
        return {
            "wake_word_status": WakeWordEngine.PVPORCUPINE,
            "engine": WakeWordEngine.PVPORCUPINE,
            "phrases": ["jarvis", "hey jarvis"],
            "is_listening": False,
            "blocker": pvp.get("blocker", ""),
            "install_command": None,
        }
    return {
        "wake_word_status": WakeWordEngine.NOT_CONFIGURED,
        "engine": WakeWordEngine.NOT_CONFIGURED,
        "phrases": ["jarvis", "hey jarvis"],
        "is_listening": False,
        "blockers": [oww.get("blocker", ""), pvp.get("blocker", "")],
        "install_commands": [
            "pip install openwakeword  # free, no API key required",
            "pip install pvporcupine   # also needs JARVIS_WAKEWORD_ACCESS_KEY from picovoice.ai",
        ],
    }


# ---------------------------------------------------------------------------
# STT status
# ---------------------------------------------------------------------------


def get_stt_status() -> Dict[str, Any]:
    """Check speech-to-text engine availability."""
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        return {
            "stt_status": STTEngine.FASTER_WHISPER,
            "engine": STTEngine.FASTER_WHISPER,
            "is_configured": True,
            "requires_api_key": False,
            "blocker": None,
        }
    except ImportError:
        pass

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        return {
            "stt_status": STTEngine.OPENAI_WHISPER,
            "engine": STTEngine.OPENAI_WHISPER,
            "is_configured": True,
            "requires_api_key": True,
            "key_env_var": "OPENAI_API_KEY",
            "blocker": None,
        }

    deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
    if deepgram_key:
        return {
            "stt_status": STTEngine.DEEPGRAM,
            "engine": STTEngine.DEEPGRAM,
            "is_configured": True,
            "requires_api_key": True,
            "key_env_var": "DEEPGRAM_API_KEY",
            "blocker": None,
        }

    return {
        "stt_status": STTEngine.NOT_CONFIGURED,
        "engine": STTEngine.NOT_CONFIGURED,
        "is_configured": False,
        "blockers": [
            "faster-whisper not installed (run: pip install faster-whisper)",
            "OPENAI_API_KEY not set",
            "DEEPGRAM_API_KEY not set",
        ],
        "install_options": [
            "pip install faster-whisper  # local, free, no API key",
            "Set OPENAI_API_KEY for OpenAI Whisper cloud STT",
            "Set DEEPGRAM_API_KEY for Deepgram cloud STT",
        ],
    }


# ---------------------------------------------------------------------------
# TTS status
# ---------------------------------------------------------------------------


def get_tts_status() -> Dict[str, Any]:
    """Check text-to-speech engine availability."""
    is_macos = platform.system() == "Darwin"
    say_path = shutil.which("say")
    if is_macos and say_path:
        return {
            "tts_status": TTSEngine.MACOS_SAY,
            "engine": TTSEngine.MACOS_SAY,
            "is_configured": True,
            "requires_api_key": False,
            "say_path": say_path,
            "note": "macOS built-in TTS ('say' command) available",
        }

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        return {
            "tts_status": TTSEngine.OPENAI_TTS,
            "engine": TTSEngine.OPENAI_TTS,
            "is_configured": True,
            "requires_api_key": True,
            "key_env_var": "OPENAI_API_KEY",
        }

    return {
        "tts_status": TTSEngine.NOT_CONFIGURED,
        "engine": TTSEngine.NOT_CONFIGURED,
        "is_configured": False,
        "blockers": [
            f"macOS 'say' command not found (platform={platform.system()})",
            "OPENAI_API_KEY not set",
        ],
    }


# ---------------------------------------------------------------------------
# TTS test (actually runs 'say' on macOS if available)
# ---------------------------------------------------------------------------


def tts_test(text: str = "Jarvis is ready.") -> Dict[str, Any]:
    """Test TTS. On macOS runs 'say' command. Elsewhere returns draft."""
    tts = get_tts_status()
    if tts["tts_status"] == TTSEngine.MACOS_SAY:
        try:
            result = subprocess.run(
                ["say", text],
                capture_output=True,
                timeout=10,
            )
            return {
                "ok": result.returncode == 0,
                "engine": TTSEngine.MACOS_SAY,
                "text_spoken": text,
                "returncode": result.returncode,
            }
        except Exception as exc:
            return {"ok": False, "engine": TTSEngine.MACOS_SAY, "error": str(exc)}
    return {
        "ok": False,
        "engine": tts["tts_status"],
        "blocker": tts.get("blockers") or tts.get("blocker"),
        "text_would_speak": text,
    }


# ---------------------------------------------------------------------------
# STT test (config check only — does not record)
# ---------------------------------------------------------------------------


def stt_test() -> Dict[str, Any]:
    """Check STT readiness. Does not record audio."""
    stt = get_stt_status()
    wake = get_wake_word_status()
    return {
        "stt_engine": stt["stt_status"],
        "stt_configured": stt.get("is_configured", False),
        "stt_blocker": stt.get("blockers") or stt.get("blocker"),
        "wake_word_engine": wake["wake_word_status"],
        "wake_word_listening": wake.get("is_listening", False),
        "wake_word_blocker": wake.get("blockers") or wake.get("blocker"),
        "note": "Does not record audio — config check only.",
    }


# ---------------------------------------------------------------------------
# Full voice status
# ---------------------------------------------------------------------------


def get_voice_status() -> Dict[str, Any]:
    """Complete voice pipeline status."""
    wake = get_wake_word_status()
    stt = get_stt_status()
    tts = get_tts_status()

    wake_ok = wake["wake_word_status"] != WakeWordEngine.NOT_CONFIGURED
    stt_ok = stt.get("is_configured", False)
    tts_ok = tts.get("is_configured", False)
    fully_configured = wake_ok and stt_ok and tts_ok

    if fully_configured:
        status = "configured_not_started"
        summary = (
            "Voice pipeline configured. Not started — "
            "requires macOS Microphone permission and explicit VoicePipeline.start() call."
        )
    elif stt_ok and tts_ok:
        status = "partial_no_wake_word"
        summary = (
            "STT and TTS configured. Wake-word engine not installed — "
            "install openwakeword (pip install openwakeword) for always-on detection."
        )
    elif tts_ok:
        status = "tts_only"
        summary = "Only TTS configured. STT and wake-word not configured."
    else:
        status = "not_configured"
        summary = "Voice pipeline not configured. See blockers for setup steps."

    return {
        "voice_status": status,
        "summary": summary,
        "fully_configured": fully_configured,
        "wake_word": wake,
        "stt": stt,
        "tts": tts,
        "push_to_talk_available": stt_ok,
        "wake_word_available": wake_ok and stt_ok,
    }


# ---------------------------------------------------------------------------
# Voice approval layer
# ---------------------------------------------------------------------------


@dataclass
class ApprovalChallenge:
    challenge_id: str
    token: str
    action_class: str
    description: str
    risk_level: str
    confirmation_phrase_required: bool
    expires_at: float
    status: str = "pending"

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "token": self.token,
            "action_class": self.action_class,
            "description": self.description,
            "risk_level": self.risk_level,
            "confirmation_phrase_required": self.confirmation_phrase_required,
            "expires_at": self.expires_at,
            "status": self.status,
            "is_expired": self.is_expired(),
        }


_ACTIVE_CHALLENGES: Dict[str, ApprovalChallenge] = {}
_APPROVAL_AUDIT_LOG: List[Dict[str, Any]] = []
_CHALLENGE_TTL = 120  # 2 minutes

# Hard-blocked — voice approval cannot override these
_VOICE_HARD_BLOCKED: frozenset = frozenset({
    "production_deploy",
    "aws_infrastructure_change",
    "billing_change",
    "stripe_change",
    "vercel_deploy",
    "supabase_change",
    "secrets_mutation",
    "env_mutation",
    "browser_form_submit",
    "browser_purchase",
    "open_public_endpoint",
    "tailscale_funnel",
    "persistent_daemon_install",
})

_RISK_FOR_ACTION: Dict[str, str] = {
    "read_only_check": VoiceApprovalRisk.LOW,
    "watchdog_run": VoiceApprovalRisk.LOW,
    "draft_report": VoiceApprovalRisk.LOW,
    "draft_slack_message": VoiceApprovalRisk.MEDIUM,
    "draft_telegram_message": VoiceApprovalRisk.MEDIUM,
    "branch_commit": VoiceApprovalRisk.MEDIUM,
    "git_push_to_fork": VoiceApprovalRisk.HIGH,
    "real_slack_send_private": VoiceApprovalRisk.HIGH,
    "real_telegram_send_private": VoiceApprovalRisk.HIGH,
}


def classify_voice_risk(action_class: str) -> str:
    if action_class in _VOICE_HARD_BLOCKED:
        return VoiceApprovalRisk.DANGEROUS
    return _RISK_FOR_ACTION.get(action_class, VoiceApprovalRisk.MEDIUM)


def issue_approval_challenge(
    action_class: str,
    description: str,
) -> ApprovalChallenge:
    """Issue a voice approval challenge for a pending action."""
    if action_class in _VOICE_HARD_BLOCKED:
        raise ValueError(
            f"Action '{action_class}' is voice-hard-blocked. "
            "This action requires manual (non-voice) approval."
        )
    risk = classify_voice_risk(action_class)
    requires_phrase = risk == VoiceApprovalRisk.HIGH
    challenge_id = str(uuid.uuid4())
    token = hashlib.sha256(
        f"{challenge_id}:{action_class}:{time.time()}".encode()
    ).hexdigest()[:8].upper()
    challenge = ApprovalChallenge(
        challenge_id=challenge_id,
        token=token,
        action_class=action_class,
        description=description,
        risk_level=risk,
        confirmation_phrase_required=requires_phrase,
        expires_at=time.time() + _CHALLENGE_TTL,
    )
    _ACTIVE_CHALLENGES[challenge_id] = challenge
    return challenge


def confirm_voice_approval(
    challenge_id: str,
    spoken_response: str = "",
    confirmation_phrase: str = "",
) -> Dict[str, Any]:
    """Confirm a voice approval challenge by parsing the spoken response."""
    challenge = _ACTIVE_CHALLENGES.get(challenge_id)
    if challenge is None:
        return {"ok": False, "error": "Challenge not found", "challenge_id": challenge_id}
    if challenge.is_expired():
        challenge.status = "expired"
        return {
            "ok": False,
            "error": "Challenge expired — issue a new one",
            "challenge_id": challenge_id,
        }
    if challenge.status != "pending":
        return {
            "ok": False,
            "error": f"Challenge already {challenge.status}",
            "challenge_id": challenge_id,
        }

    spoken_lower = spoken_response.lower().strip()
    approve_words = {"approve", "yes", "confirm", "ok", "affirmative", "do it", "proceed"}
    reject_words = {"reject", "no", "deny", "cancel", "stop", "abort", "negative"}

    if any(w in spoken_lower for w in reject_words):
        challenge.status = "rejected"
        _APPROVAL_AUDIT_LOG.append({
            "event": "voice_approval_rejected",
            "challenge_id": challenge_id,
            "action_class": challenge.action_class,
            "at": time.time(),
        })
        return {"ok": False, "status": "rejected", "challenge_id": challenge_id}

    if any(w in spoken_lower for w in approve_words):
        if challenge.confirmation_phrase_required and not confirmation_phrase:
            return {
                "ok": False,
                "error": (
                    "Confirmation phrase required for high-risk voice approval. "
                    "Provide confirmation_phrase."
                ),
                "challenge_id": challenge_id,
                "risk_level": challenge.risk_level,
            }
        challenge.status = "approved"
        _APPROVAL_AUDIT_LOG.append({
            "event": "voice_approval_confirmed",
            "challenge_id": challenge_id,
            "action_class": challenge.action_class,
            "risk_level": challenge.risk_level,
            "at": time.time(),
        })
        return {
            "ok": True,
            "status": "approved",
            "challenge_id": challenge_id,
            "token": challenge.token,
            "action_class": challenge.action_class,
        }

    return {
        "ok": False,
        "status": "pending",
        "challenge_id": challenge_id,
        "hint": "Speak 'approve' or 'reject' to respond",
    }


def parse_voice_approval(text: str) -> Dict[str, Any]:
    """Parse a text/voice string for approval intent."""
    lower = text.lower().strip()
    approve_words = {"approve", "yes", "confirm", "ok", "proceed", "do it", "affirmative"}
    reject_words = {"reject", "no", "deny", "cancel", "stop", "abort", "negative"}
    hold_words = {"hold", "wait", "pause", "later", "not now"}

    if any(w in lower for w in reject_words):
        return {"intent": "reject", "confidence": 0.9, "raw": text}
    if any(w in lower for w in hold_words):
        return {"intent": "hold", "confidence": 0.8, "raw": text}
    if any(w in lower for w in approve_words):
        return {"intent": "approve", "confidence": 0.9, "raw": text}
    return {
        "intent": "unknown",
        "confidence": 0.0,
        "raw": text,
        "hint": "Speak approve/reject/hold",
    }


def preview_command(text: str) -> Dict[str, Any]:
    """Preview what a voice command would do before executing."""
    vs = get_voice_status()
    return {
        "preview_text": text,
        "interpreted_as": text,
        "voice_pipeline_status": vs["voice_status"],
        "would_route_through_governance": True,
        "preview_only": True,
        "note": "No action taken. This is a preview only.",
    }


def get_approval_audit_log() -> List[Dict[str, Any]]:
    return list(_APPROVAL_AUDIT_LOG)


def clear_for_tests() -> None:
    _ACTIVE_CHALLENGES.clear()
    _APPROVAL_AUDIT_LOG.clear()


__all__ = [
    "WakeWordEngine",
    "STTEngine",
    "TTSEngine",
    "VoiceApprovalRisk",
    "ApprovalChallenge",
    "get_voice_status",
    "get_wake_word_status",
    "get_stt_status",
    "get_tts_status",
    "tts_test",
    "stt_test",
    "classify_voice_risk",
    "issue_approval_challenge",
    "confirm_voice_approval",
    "parse_voice_approval",
    "preview_command",
    "get_approval_audit_log",
    "clear_for_tests",
]
