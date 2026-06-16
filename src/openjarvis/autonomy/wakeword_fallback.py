"""Jarvis Wake-Word Fallback — hotkey push-to-talk + manual-trigger activation.

Activation paths:
  1. True wake-word: via WakeWordBridge (isolated .wake_worker_venv, Python 3.12,
     openwakeword + onnxruntime). See wakeword_bridge.py.
  2. Hotkey (push-to-talk): configurable via JARVIS_VOICE_HOTKEY env var.
     Default: cmd+shift+space (human-readable), parsed to pynput format.
     Supports: cmd, ctrl, alt, shift + any key. Example: 'cmd+shift+space'.
  3. Manual API / chatbox: activate_voice() callable from REPL, CLI, or UI.

Hotkey configuration:
  JARVIS_VOICE_HOTKEY='cmd+shift+space'   # default
  JARVIS_VOICE_HOTKEY='ctrl+alt+j'        # override example
  JARVIS_VOICE_HOTKEY='<backtick>'        # backtick only if explicitly set

Classification contract:
  get_wakeword_engine_status() returns:
    true_wakeword_status   = from wakeword_bridge (openwakeword or BLOCKED)
    hotkey_status          = "active" | "available" | "unavailable"
    hotkey_binding         = human-readable binding string
    manual_chatbox_status  = "available" (always)
    is_listening           = False (hotkey is push-to-talk, not always-on)

Safety rules:
  - Never claims true wake-word detection from this module.
  - Never starts recording without explicit trigger.
  - Trigger log in-memory only (not persisted, no PII).
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

_DEFAULT_HOTKEY_HUMAN = "cmd+shift+space"
_DEFAULT_HOTKEY_ENV = os.environ.get("JARVIS_VOICE_HOTKEY", _DEFAULT_HOTKEY_HUMAN)

# Human-readable → pynput key name mapping
_KEY_ALIASES: dict[str, str] = {
    "cmd": "<cmd>",
    "command": "<cmd>",
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "option": "<alt>",
    "shift": "<shift>",
    "space": "<space>",
    "enter": "<enter>",
    "return": "<enter>",
    "esc": "<esc>",
    "escape": "<esc>",
    "tab": "<tab>",
    "backtick": "<96>",  # backtick — supported only as explicit override
    "`": "<96>",
    "f1": "<f1>", "f2": "<f2>", "f3": "<f3>", "f4": "<f4>",
    "f5": "<f5>", "f6": "<f6>", "f7": "<f7>", "f8": "<f8>",
    "f9": "<f9>", "f10": "<f10>", "f11": "<f11>", "f12": "<f12>",
}


def _parse_hotkey(human: str) -> str:
    """Convert human-readable hotkey string to pynput GlobalHotKeys format.

    Examples:
      'cmd+shift+space'  -> '<cmd>+<shift>+<space>'
      'ctrl+alt+j'       -> '<ctrl>+<alt>+j'
      '<f8>'             -> '<f8>'   (pass-through if already pynput-formatted)
    """
    if human.startswith("<"):
        return human  # already in pynput format
    parts = [p.strip().lower() for p in human.split("+")]
    pynput_parts = [_KEY_ALIASES.get(p, p) for p in parts]
    return "+".join(pynput_parts)


_DEFAULT_HOTKEY = _parse_hotkey(_DEFAULT_HOTKEY_ENV)


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
        # Query bridge for true wake-word availability (import guarded)
        try:
            from openjarvis.autonomy.wakeword_bridge import get_worker_status
            bridge_status = get_worker_status()
            true_wakeword_status = bridge_status.get("true_wakeword_status", WAKEWORD_STATUS_BLOCKED)
            worker_available = bridge_status.get("worker_available", False)
        except Exception:
            true_wakeword_status = WAKEWORD_STATUS_BLOCKED
            worker_available = False
            bridge_status = {}

        mic = _check_microphone_ready()
        with self._lock:
            hotkey_pynput = _DEFAULT_HOTKEY
            hotkey_human = _DEFAULT_HOTKEY_ENV
            hotkey_active = self._hotkey_active
            fallback_mode = self._fallback_mode
            trigger_count = self._trigger_count
            last_trigger = self._last_trigger
            cbs = len(self._callbacks)

        return {
            # True wake-word
            "true_wakeword_status": true_wakeword_status,
            "true_wakeword_worker_available": worker_available,
            "true_wakeword_model": bridge_status.get("model", "hey_jarvis_v0.1"),
            "true_wakeword_phrases": bridge_status.get("phrases", ["hey jarvis"]),
            # Hotkey
            "hotkey_status": "active" if hotkey_active else "available",
            "hotkey_binding": hotkey_human,
            "hotkey_binding_pynput": hotkey_pynput,
            # Manual chatbox
            "manual_chatbox_status": "available",
            # Microphone
            "microphone_status": "granted" if mic.get("ok") else "denied_or_no_device",
            "microphone_device": mic.get("device", ""),
            # Legacy / internal
            "fallback_mode": fallback_mode,
            "fallback_active": hotkey_active or fallback_mode == FALLBACK_MANUAL_API,
            "trigger_count": trigger_count,
            "last_trigger": last_trigger,
            "is_listening": False,
            "microphone_ready": mic,
            "callbacks_registered": cbs,
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

    Default hotkey: Cmd+Shift+Space (configurable via JARVIS_VOICE_HOTKEY env var).
    Accepts human-readable format: 'cmd+shift+space', 'ctrl+alt+j', etc.
    Returns status dict. Never claims true wake-word detection.
    """
    parsed = _parse_hotkey(hotkey)
    return _ENGINE.start_hotkey(parsed)


def stop_listener() -> None:
    """Stop the hotkey listener."""
    _ENGINE.stop()


def activate_voice() -> Dict[str, Any]:
    """Manually trigger voice activation (API / REPL / CLI call).

    Use this when no hotkey listener is running or for programmatic activation.
    """
    return _ENGINE.manual_trigger()


def get_wakeword_engine_status() -> Dict[str, Any]:
    """Return full activation-path status:
      - true_wakeword_status: openwakeword_available | BLOCKED_BY_PROVIDER_OR_PLATFORM
      - hotkey_status / hotkey_binding: Cmd+Shift+Space (configurable)
      - manual_chatbox_status: always available
      - microphone_status: granted | denied_or_no_device
      - is_listening: always False (hotkey = push-to-talk, not always-on)
    """
    return _ENGINE.status()


def get_microphone_status() -> Dict[str, Any]:
    """Return microphone device readiness."""
    return _check_microphone_ready()
