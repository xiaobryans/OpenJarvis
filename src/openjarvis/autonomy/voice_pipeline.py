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
    HOTKEY_FALLBACK = "hotkey_fallback"
    NOT_CONFIGURED = "not_configured"
    BLOCKED_BY_PROVIDER_OR_PLATFORM = "BLOCKED_BY_PROVIDER_OR_PLATFORM"


class STTEngine:
    FASTER_WHISPER = "faster_whisper"
    OPENAI_WHISPER = "openai_whisper"
    DEEPGRAM = "deepgram"
    NOT_CONFIGURED = "not_configured"


class TTSEngine:
    DEEPGRAM = "deepgram"
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
    # Both engines unavailable — report fallback mode honestly
    try:
        from openjarvis.autonomy.wakeword_fallback import get_wakeword_engine_status
        fb = get_wakeword_engine_status()
        fallback_mode = fb.get("fallback_mode", "none")
    except Exception:
        fallback_mode = "none"

    return {
        "wake_word_status": WakeWordEngine.BLOCKED_BY_PROVIDER_OR_PLATFORM,
        "engine": WakeWordEngine.HOTKEY_FALLBACK if fallback_mode == "hotkey" else WakeWordEngine.NOT_CONFIGURED,
        "phrases": ["jarvis", "hey jarvis"],
        "is_listening": False,
        "true_wakeword_blocked": True,
        "true_wakeword_blocked_reason": (
            "openwakeword blocked by onnxruntime/macOS x86_64 incompatibility; "
            "pvporcupine unavailable per US9 authorization"
        ),
        "fallback_mode": fallback_mode,
        "fallback_available": fallback_mode in ("hotkey", "manual_api"),
        "blockers": [oww.get("blocker", ""), pvp.get("blocker", "")],
        "install_commands": [
            "pip install openwakeword  # blocked on macOS x86_64/CPython 3.13 by onnxruntime",
        ],
        "manual_action": (
            "Use F8 hotkey (push-to-talk) or call activate_voice() from wakeword_fallback module"
        ),
    }


# ---------------------------------------------------------------------------
# STT status
# ---------------------------------------------------------------------------


def get_stt_status() -> Dict[str, Any]:
    """Check speech-to-text engine availability.

    Priority (Voice Safety Sprint):
      Deepgram is the primary/default STT provider.
      Override with JARVIS_STT_PROVIDER env var.
      Existing providers (faster-whisper, openai) are fallback only.
    """
    try:
        from openjarvis.projects.source_links import _load_openjarvis_env
        _load_openjarvis_env()
    except Exception:
        pass

    stt_override = os.environ.get("JARVIS_STT_PROVIDER", "").strip().lower()

    # Deepgram check — primary/default unless JARVIS_STT_PROVIDER says otherwise
    if stt_override in ("", "deepgram"):
        deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if deepgram_key:
            return {
                "stt_status": STTEngine.DEEPGRAM,
                "engine": STTEngine.DEEPGRAM,
                "is_configured": True,
                "requires_api_key": True,
                "key_env_var": "DEEPGRAM_API_KEY",
                "primary": True,
                "blocker": None,
            }

    # Explicit override to faster-whisper or openai
    if stt_override == "faster-whisper" or stt_override == "faster_whisper":
        try:
            from faster_whisper import WhisperModel  # noqa: F401
            return {
                "stt_status": STTEngine.FASTER_WHISPER,
                "engine": STTEngine.FASTER_WHISPER,
                "is_configured": True,
                "requires_api_key": False,
                "primary": False,
                "blocker": None,
            }
        except ImportError:
            pass

    if stt_override == "openai":
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key:
            return {
                "stt_status": STTEngine.OPENAI_WHISPER,
                "engine": STTEngine.OPENAI_WHISPER,
                "is_configured": True,
                "requires_api_key": True,
                "key_env_var": "OPENAI_API_KEY",
                "primary": False,
                "blocker": None,
            }

    # Fallback chain: faster-whisper → openai (deepgram key missing)
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        return {
            "stt_status": STTEngine.FASTER_WHISPER,
            "engine": STTEngine.FASTER_WHISPER,
            "is_configured": True,
            "requires_api_key": False,
            "primary": False,
            "fallback_reason": "DEEPGRAM_API_KEY not set",
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
            "primary": False,
            "fallback_reason": "DEEPGRAM_API_KEY not set",
            "blocker": None,
        }

    return {
        "stt_status": STTEngine.NOT_CONFIGURED,
        "engine": STTEngine.NOT_CONFIGURED,
        "is_configured": False,
        "blockers": [
            "DEEPGRAM_API_KEY not set — set in .env (primary provider)",
            "faster-whisper not installed — run: pip install faster-whisper (fallback)",
            "OPENAI_API_KEY not set (fallback)",
        ],
        "install_options": [
            "Set DEEPGRAM_API_KEY in .env for Deepgram cloud STT (primary)",
            "pip install faster-whisper  # local fallback, no API key",
            "Set OPENAI_API_KEY for OpenAI Whisper cloud STT (fallback)",
        ],
        "setup": "BLOCKED_WAITING_FOR_BRYAN_NOW — add DEEPGRAM_API_KEY to .env",
    }


# ---------------------------------------------------------------------------
# TTS status
# ---------------------------------------------------------------------------


def get_tts_status() -> Dict[str, Any]:
    """Check text-to-speech engine availability.

    Priority (Voice Safety Sprint):
      Deepgram is the primary/default TTS provider.
      Override with JARVIS_TTS_PROVIDER env var.
      macOS say and OpenAI TTS are fallback.
    """
    try:
        from openjarvis.projects.source_links import _load_openjarvis_env
        _load_openjarvis_env()
    except Exception:
        pass

    tts_override = os.environ.get("JARVIS_TTS_PROVIDER", "").strip().lower()

    # Deepgram TTS — primary/default
    if tts_override in ("", "deepgram"):
        deepgram_key = os.environ.get("DEEPGRAM_API_KEY", "")
        if deepgram_key:
            return {
                "tts_status": TTSEngine.DEEPGRAM,
                "engine": TTSEngine.DEEPGRAM,
                "is_configured": True,
                "requires_api_key": True,
                "key_env_var": "DEEPGRAM_API_KEY",
                "primary": True,
                "note": "Deepgram Aura TTS (primary)",
            }

    # macOS say — always available on macOS as fallback
    is_macos = platform.system() == "Darwin"
    say_path = shutil.which("say")
    if tts_override in ("macos_say", "say") or (tts_override == "" and is_macos and say_path):
        if is_macos and say_path:
            return {
                "tts_status": TTSEngine.MACOS_SAY,
                "engine": TTSEngine.MACOS_SAY,
                "is_configured": True,
                "requires_api_key": False,
                "say_path": say_path,
                "primary": False,
                "fallback_reason": "DEEPGRAM_API_KEY not set",
                "note": "macOS built-in TTS ('say' command) — fallback",
            }

    # OpenAI TTS fallback
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        return {
            "tts_status": TTSEngine.OPENAI_TTS,
            "engine": TTSEngine.OPENAI_TTS,
            "is_configured": True,
            "requires_api_key": True,
            "key_env_var": "OPENAI_API_KEY",
            "primary": False,
            "fallback_reason": "DEEPGRAM_API_KEY not set",
        }

    # macOS say as last resort
    if is_macos and say_path:
        return {
            "tts_status": TTSEngine.MACOS_SAY,
            "engine": TTSEngine.MACOS_SAY,
            "is_configured": True,
            "requires_api_key": False,
            "say_path": say_path,
            "primary": False,
            "fallback_reason": "DEEPGRAM_API_KEY not set",
            "note": "macOS built-in TTS ('say' command) — fallback",
        }

    return {
        "tts_status": TTSEngine.NOT_CONFIGURED,
        "engine": TTSEngine.NOT_CONFIGURED,
        "is_configured": False,
        "blockers": [
            "DEEPGRAM_API_KEY not set — set in .env (primary Deepgram TTS)",
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


def _get_approval_pin_status() -> str:
    """Return 'set' if JARVIS_OPERATOR_PIN_HASH is present, else 'not_set'."""
    import os as _os
    from pathlib import Path as _Path
    h = _os.environ.get("JARVIS_OPERATOR_PIN_HASH", "")
    if not h:
        env_file = _Path.home() / ".openjarvis" / "cloud-keys.env"
        try:
            for line in env_file.read_text().splitlines():
                if line.startswith("JARVIS_OPERATOR_PIN_HASH="):
                    h = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
    return "set" if len(h) == 64 else "not_set"


def _get_fallback_status() -> Dict[str, Any]:
    """Get hotkey + manual chatbox status from wakeword_fallback."""
    try:
        from openjarvis.autonomy.wakeword_fallback import get_wakeword_engine_status
        fb = get_wakeword_engine_status()
        return {
            "hotkey_status": fb.get("hotkey_status", "available"),
            "hotkey_binding": fb.get("hotkey_binding", "cmd+shift+space"),
            "manual_chatbox_status": fb.get("manual_chatbox_status", "available"),
            "microphone_status": fb.get("microphone_status", "unknown"),
            "microphone_device": fb.get("microphone_device", ""),
            "true_wakeword_worker_available": fb.get("true_wakeword_worker_available", False),
        }
    except Exception:
        return {
            "hotkey_status": "available",
            "hotkey_binding": "cmd+shift+space",
            "manual_chatbox_status": "available",
            "microphone_status": "unknown",
            "microphone_device": "",
            "true_wakeword_worker_available": False,
        }


def get_voice_status() -> Dict[str, Any]:
    """Complete voice pipeline status with all required fields.

    Voice readiness (honest runtime states):
      RUNTIME_STARTED   — wake-word worker is running (live proof possible)
      READY_FOR_LIVE_PROOF — all deps configured, worker NOT yet started
                            (run 'jarvis voice start' to prove live activation)
      PARTIAL           — manual chat or in-app mic available but wake-word not configured
      HOLD              — no usable activation path

    IMPORTANT: READY is never returned; the pipeline can only be proven by
    live activation (say 'hey jarvis' while worker is running).
    """
    wake = get_wake_word_status()
    stt = get_stt_status()
    tts = get_tts_status()
    fb = _get_fallback_status()
    pin_status = _get_approval_pin_status()

    wake_status_val = wake["wake_word_status"]
    wake_true = wake_status_val not in (
        WakeWordEngine.NOT_CONFIGURED,
        WakeWordEngine.BLOCKED_BY_PROVIDER_OR_PLATFORM,
    )
    wake_blocked = wake_status_val == WakeWordEngine.BLOCKED_BY_PROVIDER_OR_PLATFORM
    worker_available = fb.get("true_wakeword_worker_available", False)
    # If bridge worker is available, treat as non-blocked even if main-venv is blocked
    effective_wake_true = wake_true or worker_available
    wake_fallback = fb.get("hotkey_status") in ("active", "available")
    stt_ok = stt.get("is_configured", False)
    tts_ok = tts.get("is_configured", False)
    mic_ok = fb.get("microphone_status") == "granted"
    pin_ok = pin_status == "set"
    fully_configured = effective_wake_true and stt_ok and tts_ok

    # Check if wake-word worker is actually running
    worker_running = False
    try:
        from openjarvis.autonomy.wakeword_bridge import get_bridge
        worker_running = get_bridge().status().get("worker_running", False)
    except Exception:
        pass

    # Voice readiness classification — honest runtime states only
    if worker_running and stt_ok and tts_ok and mic_ok:
        voice_readiness = "RUNTIME_STARTED"
        readiness_reason = (
            "Wake-word worker is running. Say 'hey jarvis' to prove live activation. "
            "STT/TTS/mic all operational."
        )
    elif effective_wake_true and stt_ok and tts_ok and mic_ok and pin_ok:
        voice_readiness = "READY_FOR_LIVE_PROOF"
        readiness_reason = (
            "All deps configured (wake-word worker available, STT, TTS, mic, PIN). "
            "Worker NOT started — run 'jarvis voice start' to prove live activation."
        )
    elif (wake_fallback or fb.get("manual_chatbox_status") == "available") and (stt_ok or tts_ok):
        voice_readiness = "PARTIAL"
        active_paths = []
        if wake_fallback:
            active_paths.append(f"hotkey({fb.get('hotkey_binding','cmd+shift+space')})")
        if fb.get("manual_chatbox_status") == "available":
            active_paths.append("manual_chatbox")
        if worker_available:
            active_paths.append("true_wakeword_worker(available)")
        readiness_reason = (
            f"Hotkey/manual chatbox active. True wake-word: "
            f"{'worker_available' if worker_available else 'BLOCKED'}. "
            f"Active paths: {', '.join(active_paths)}"
        )
    else:
        voice_readiness = "HOLD"
        readiness_reason = "No usable activation path — check microphone, STT, and hotkey config"

    if worker_running and fully_configured:
        status = "runtime_started"
        summary = (
            "Wake-word listener is running. Say 'hey jarvis' to activate STT/TTS pipeline. "
            "Run 'jarvis voice start' to start if not running."
        )
    elif fully_configured:
        status = "configured_not_started"
        summary = (
            "Voice pipeline configured. Worker NOT started — "
            "run 'jarvis voice start' to start wake-word listener."
        )
    elif (wake_blocked or worker_available) and stt_ok and tts_ok:
        status = "partial_hotkey_fallback"
        summary = (
            f"STT and TTS configured. True wake-word: "
            f"{'worker_available' if worker_available else 'BLOCKED_BY_PROVIDER_OR_PLATFORM'} — "
            f"hotkey ({fb.get('hotkey_binding', 'cmd+shift+space')}) available."
        )
    elif stt_ok and tts_ok:
        status = "partial_no_wake_word"
        summary = (
            "STT and TTS configured. Wake-word engine not installed — "
            "worker venv not found."
        )
    elif tts_ok:
        status = "tts_only"
        summary = "Only TTS configured. STT and wake-word not configured."
    else:
        status = "not_configured"
        summary = "Voice pipeline not configured. See blockers for setup steps."

    return {
        # Core status
        "voice_status": status,
        "voice_readiness": voice_readiness,
        "readiness_reason": readiness_reason,
        "summary": summary,
        "fully_configured": fully_configured,
        # Required status fields
        "true_wakeword_status": wake_status_val,
        "true_wakeword_worker_available": worker_available,
        "true_wakeword_worker_running": worker_running,
        "hotkey_status": fb.get("hotkey_status", "available"),
        "hotkey_binding": fb.get("hotkey_binding", "cmd+shift+space"),
        "hotkey_note": (
            "CLI daemon mode only. In packaged Tauri app, "
            "Cmd+Shift+Space opens chat overlay (not voice)."
        ),
        "inapp_push_to_talk": "mic button in chat input (enable in Settings > Input & Voice)",
        "mic_button_status": "available_in_ui",
        "manual_chatbox_status": fb.get("manual_chatbox_status", "available"),
        "microphone_status": fb.get("microphone_status", "unknown"),
        "microphone_device": fb.get("microphone_device", ""),
        "stt_status": stt.get("stt_status", STTEngine.NOT_CONFIGURED),
        "tts_status": tts.get("tts_status", TTSEngine.NOT_CONFIGURED),
        "stt_primary": stt.get("primary", False),
        "tts_primary": tts.get("primary", False),
        "stt_fallback_reason": stt.get("fallback_reason", ""),
        "tts_fallback_reason": tts.get("fallback_reason", ""),
        "approval_pin_status": pin_status,
        # Voice provider config (env-based)
        "voice_provider_config": {
            "JARVIS_VOICE_PROVIDER": os.environ.get("JARVIS_VOICE_PROVIDER", "deepgram (default)"),
            "JARVIS_STT_PROVIDER": os.environ.get("JARVIS_STT_PROVIDER", "deepgram (default)"),
            "JARVIS_TTS_PROVIDER": os.environ.get("JARVIS_TTS_PROVIDER", "deepgram (default)"),
            "deepgram_key_set": bool(os.environ.get("DEEPGRAM_API_KEY", "")),
        },
        # Raw sub-statuses
        "wake_word": wake,
        "stt": stt,
        "tts": tts,
        "push_to_talk_available": stt_ok,
        "wake_word_available": (effective_wake_true or wake_fallback) and stt_ok,
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


# Natural language keywords → risk tiers for voice transcript classification
_DANGEROUS_KEYWORDS: frozenset = frozenset({
    "delete", "destroy", "wipe", "remove file", "drop table",
    "deploy", "push to production", "publish", "go live",
    "send message", "send slack", "send telegram", "send email",
    "merge to main", "force push",
    "change billing", "stripe", "vercel deploy", "aws", "supabase",
    "expose", "open port", "tailscale funnel",
})
_HIGH_KEYWORDS: frozenset = frozenset({
    "push", "git push",
    "send", "post to slack", "post to telegram",
})
_MEDIUM_KEYWORDS: frozenset = frozenset({
    "run tests", "run test", "execute tests",
    "commit", "merge branch",
})
_LOW_KEYWORDS: frozenset = frozenset({
    "what", "show", "list", "check", "tell me", "read",
    "status", "help", "how", "explain", "summarize",
    "draft", "create plan", "scaffold", "set up", "start a",
    "weather", "time", "calculate",
})


def classify_voice_action_risk(text: str) -> Dict[str, Any]:
    """Classify a natural language voice transcript into a risk tier.

    This maps free-form speech to action risk levels so voice safety gates
    can be applied before any action is executed.

    Returns a dict with 'risk_level' and 'reason'.
    """
    normalized = text.lower().strip()

    for kw in _DANGEROUS_KEYWORDS:
        if kw in normalized:
            return {
                "risk_level": VoiceApprovalRisk.DANGEROUS,
                "reason": f"Matched dangerous keyword: {kw!r}",
                "action_required": "approval_required — voice cannot auto-approve",
                "original": text,
            }

    for kw in _HIGH_KEYWORDS:
        if kw in normalized:
            return {
                "risk_level": VoiceApprovalRisk.HIGH,
                "reason": f"Matched high-risk keyword: {kw!r}",
                "action_required": "approval_required — voice can request approval",
                "original": text,
            }

    for kw in _MEDIUM_KEYWORDS:
        if kw in normalized:
            return {
                "risk_level": VoiceApprovalRisk.MEDIUM,
                "reason": f"Matched medium-risk keyword: {kw!r}",
                "action_required": "route_to_jarvis_for_classification",
                "original": text,
            }

    for kw in _LOW_KEYWORDS:
        if kw in normalized:
            return {
                "risk_level": VoiceApprovalRisk.LOW,
                "reason": f"Matched low-risk keyword: {kw!r}",
                "action_required": "none — route through normal Jarvis path",
                "original": text,
            }

    # Unknown / ambiguous → medium by default
    return {
        "risk_level": VoiceApprovalRisk.MEDIUM,
        "reason": "No specific risk keyword matched — defaulting to medium",
        "action_required": "route_to_jarvis_for_classification",
        "original": text,
    }


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
    "classify_voice_action_risk",
    "issue_approval_challenge",
    "confirm_voice_approval",
    "parse_voice_approval",
    "preview_command",
    "get_approval_audit_log",
    "clear_for_tests",
]
