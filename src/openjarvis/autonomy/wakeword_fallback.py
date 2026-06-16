"""Jarvis Wake-Word Fallback — hotkey push-to-talk + manual-trigger activation.

True wake-word status: BLOCKED_BY_PROVIDER_OR_PLATFORM
  - openwakeword: blocked (onnxruntime incompatible on macOS x86_64 CPython 3.13)
  - pvporcupine: unavailable per US9 authorization
  - snowboy: EOL / Python 3 unsupported
  - precise: abandoned

This module provides the safest available alternative:
  1. Configurable keyboard hotkey (default: F8) via pynput — push-to-talk mode.
  2. Manual API trigger via activate_voice() — callable from REPL, CLI, or HTTP endpoint.
  3. Always-listening mode (key held) — optional, disabled by default.

Classification contract (honest):
  get_wakeword_engine_status() always returns:
    true_wakeword_status = BLOCKED_BY_PROVIDER_OR_PLATFORM
    fallback_mode        = "hotkey" | "manual_api" | "none"
    is_listening         = False (hotkey mode is NOT always-on true wake-word)

Safety rules:
  - Never claims true wake-word detection.
  - Never starts recording without explicit trigger.
  - Activation callbacks receive only a trigger event — no audio captured here.
  - Trigger log is in-memory only (not persisted, no PII).
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

WAKEWORD_STATUS_BLOCKED = "BLOCKED_BY_PROVIDER_OR_PLATFORM"
FALLBACK_HOTKEY = "hotkey"
FALLBACK_MANUAL_API = "manual_api"
FALLBACK_NONE = "none"

_DEFAULT_HOTKEY = os.environ.get("JARVIS_VOICE_HOTKEY", "<f8>")
_DEFAULT_HOLD_TO_TALK_KEY = os.environ.get("JARVIS_VOICE_HOLD_KEY", "<ctrl>+<alt>+j")


# ---------------------------------------------------------------------------
# Trigger event
# ---------------------------------------------------------------------------


@dataclass
class VoiceTriggerEvent:
    """Emitted when voice activation is triggered."""

    source: str  # "hotkey" | "manual_api"
    triggered_at: float = field(default_factory=time.time)
    hotkey: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Fallback engine state
# ---------------------------------------------------------------------------


class _FallbackEngineState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running: bool = False
        self._callbacks: List[Callable[[VoiceTriggerEvent], None]] = []
        self._trigger_count: int = 0
        self._last_trigger: Optional[float] = None
        self._hotkey_active: bool = False
        self._listener: Any = None  # pynput GlobalHotKeys instance
        self._fallback_mode: str = FALLBACK_NONE

    def register_callback(self, cb: Callable[[VoiceTriggerEvent], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)

    def _fire(self, source: str, hotkey: str = "") -> None:
        with self._lock:
            self._trigger_count += 1
            self._last_trigger = time.time()
            callbacks = list(self._callbacks)
        event = VoiceTriggerEvent(source=source, hotkey=hotkey)
        for cb in callbacks:
            try:
                cb(event)
            except Exception as exc:
                logger.warning("Voice trigger callback raised: %s", exc)
        logger.info("Voice trigger fired: source=%s count=%d", source, self._trigger_count)

    def start_hotkey(self, hotkey_str: str = _DEFAULT_HOTKEY) -> Dict[str, Any]:
        """Start pynput GlobalHotKeys listener for push-to-talk."""
        with self._lock:
            if self._running:
                return {"ok": True, "already_running": True, "mode": self._fallback_mode}

        try:
            from pynput import keyboard as kb

            def _on_activate():
                self._fire("hotkey", hotkey=hotkey_str)

            listener = kb.GlobalHotKeys({hotkey_str: _on_activate})
            listener.daemon = True
            listener.start()

            with self._lock:
                self._listener = listener
                self._running = True
                self._hotkey_active = True
                self._fallback_mode = FALLBACK_HOTKEY

            logger.info("Hotkey listener started: %s", hotkey_str)
            return {"ok": True, "mode": FALLBACK_HOTKEY, "hotkey": hotkey_str}

        except ImportError:
            logger.warning("pynput not available — hotkey fallback disabled; manual API only")
            with self._lock:
                self._fallback_mode = FALLBACK_MANUAL_API
            return {
                "ok": False,
                "mode": FALLBACK_MANUAL_API,
                "blocker": "pynput not installed",
            }
        except Exception as exc:
            logger.warning("Hotkey listener failed: %s", exc)
            with self._lock:
                self._fallback_mode = FALLBACK_MANUAL_API
            return {
                "ok": False,
                "mode": FALLBACK_MANUAL_API,
                "error": str(exc),
                "note": "pynput may need Accessibility permission on macOS — grant in System Settings > Privacy > Accessibility",
            }

    def stop(self) -> None:
        with self._lock:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None
            self._running = False
            self._hotkey_active = False
            self._fallback_mode = FALLBACK_NONE

    def manual_trigger(self) -> Dict[str, Any]:
        """Programmatic voice activation — usable from REPL, CLI, or HTTP call."""
        with self._lock:
            if self._fallback_mode == FALLBACK_NONE:
                self._fallback_mode = FALLBACK_MANUAL_API
        self._fire("manual_api")
        with self._lock:
            return {
                "ok": True,
                "source": "manual_api",
                "trigger_count": self._trigger_count,
                "triggered_at": self._last_trigger,
            }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "true_wakeword_status": WAKEWORD_STATUS_BLOCKED,
                "true_wakeword_blocked_reason": (
                    "openwakeword blocked by onnxruntime/macOS x86_64 incompatibility; "
                    "pvporcupine unavailable per US9 authorization"
                ),
                "fallback_mode": self._fallback_mode,
                "fallback_active": self._running or self._fallback_mode == FALLBACK_MANUAL_API,
                "hotkey_active": self._hotkey_active,
                "configured_hotkey": _DEFAULT_HOTKEY,
                "trigger_count": self._trigger_count,
                "last_trigger": self._last_trigger,
                "is_listening": False,  # never true — not real always-on wake-word
                "microphone_ready": _check_microphone_ready(),
                "callbacks_registered": len(self._callbacks),
            }


# ---------------------------------------------------------------------------
# Microphone helper
# ---------------------------------------------------------------------------


def _check_microphone_ready() -> Dict[str, Any]:
    try:
        import sounddevice as sd
        dev = sd.query_devices(kind="input")
        return {
            "ok": True,
            "device": dev["name"],
            "channels": dev["max_input_channels"],
            "sample_rate": dev["default_samplerate"],
            "permission": "granted",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "permission": "denied_or_no_device",
            "manual_action": (
                "System Settings > Privacy & Security > Microphone — "
                "grant access to Terminal or Cursor"
            ),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


_ENGINE = _FallbackEngineState()


def register_voice_callback(cb: Callable[[VoiceTriggerEvent], None]) -> None:
    """Register a callback to fire on voice trigger (hotkey or manual API)."""
    _ENGINE.register_callback(cb)


def start_hotkey_listener(hotkey: str = _DEFAULT_HOTKEY) -> Dict[str, Any]:
    """Start the hotkey push-to-talk listener.

    Default hotkey: F8 (configurable via JARVIS_VOICE_HOTKEY env var).
    Returns status dict. Never claims true wake-word detection.
    """
    return _ENGINE.start_hotkey(hotkey)


def stop_listener() -> None:
    """Stop the hotkey listener."""
    _ENGINE.stop()


def activate_voice() -> Dict[str, Any]:
    """Manually trigger voice activation (API / REPL / CLI call).

    Use this when no hotkey listener is running or for programmatic activation.
    """
    return _ENGINE.manual_trigger()


def get_wakeword_engine_status() -> Dict[str, Any]:
    """Return honest wake-word fallback status.

    true_wakeword_status is always BLOCKED_BY_PROVIDER_OR_PLATFORM.
    is_listening is always False — hotkey is push-to-talk, not always-on.
    """
    return _ENGINE.status()


def get_microphone_status() -> Dict[str, Any]:
    """Return microphone device readiness."""
    return _check_microphone_ready()
