"""Voice supervisor — starts the voice loop when the server is ready.

Polls ``/health`` every 0.5s; on the first 200 it starts the voice loop in a
background daemon thread and restarts it if it crashes. ``VANTA_VOICE=off``
skips it. Never raises into server startup.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_MAX_RESTART_BACKOFF_S = 30.0
_HEALTH_POLL_INTERVAL_S = 0.5
_HEALTH_POLL_TIMEOUT_S = 120.0

_thread: Optional[threading.Thread] = None
_stop = threading.Event()

StatusLog = Callable[[str], None]
_TRUE = {"1", "true", "yes", "on"}


def voice_disabled() -> bool:
    """True if voice is opted out via env (``VANTA_VOICE=off`` or legacy flags)."""
    if (os.environ.get("VANTA_VOICE") or "").strip().lower() == "off":
        return True
    val = (os.environ.get("VANTA_NO_VOICE") or os.environ.get("OPENJARVIS_NO_VOICE") or "").strip().lower()
    return val in _TRUE


def is_running() -> bool:
    return _thread is not None and _thread.is_alive()


def _health_url() -> str:
    port = (os.environ.get("JARVIS_PORT") or os.environ.get("OPENJARVIS_PORT") or "8000").strip()
    return f"http://127.0.0.1:{port}/health"


def _wait_for_health() -> bool:
    """Poll /health every 0.5s until 200 (or stop/timeout)."""
    url = _health_url()
    deadline = time.time() + _HEALTH_POLL_TIMEOUT_S
    while not _stop.is_set() and time.time() < deadline:
        try:
            import httpx
            if httpx.get(url, timeout=2.0).status_code == 200:
                return True
        except Exception:
            pass
        if _stop.wait(_HEALTH_POLL_INTERVAL_S):
            return False
    return False


def _supervise(status_log: StatusLog) -> None:
    status_log("voice supervisor: polling /health (0.5s)…")
    if not _wait_for_health():
        status_log("voice supervisor: server not healthy in time — voice not started")
        return
    backoff = 1.0
    while not _stop.is_set():
        try:
            from openjarvis.speech.voice_loop import VoiceLoop
        except Exception as exc:
            status_log(f"voice loop unavailable (missing deps): {exc}")
            return
        try:
            status_log('voice loop active — say "Hey VANTA"')
            VoiceLoop().run()
            if _stop.is_set():
                return
            status_log("voice loop exited; restarting")
            backoff = 1.0
        except Exception as exc:
            if _stop.is_set():
                return
            status_log(f"voice loop crashed ({exc!r}); restarting in {backoff:.0f}s")
        if _stop.wait(backoff):
            return
        backoff = min(_MAX_RESTART_BACKOFF_S, backoff * 2.0)


def start_voice_supervisor(status_log: Optional[StatusLog] = None) -> bool:
    """Start the voice loop in a background daemon thread. Never raises."""
    global _thread
    log: StatusLog = status_log or (lambda m: logger.info("voice: %s", m))
    try:
        if voice_disabled():
            log("voice disabled via VANTA_VOICE=off — not starting")
            return False
        if is_running():
            return False
        _stop.clear()
        _thread = threading.Thread(target=_supervise, args=(log,), name="vanta-voice", daemon=True)
        _thread.start()
        return True
    except Exception as exc:
        log(f"could not start voice supervisor: {exc!r}")
        return False


def stop_voice_supervisor(timeout: float = 2.0) -> None:
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=timeout)
