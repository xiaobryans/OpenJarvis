"""Supervised always-on voice loop for VANTA.

Runs :class:`~openjarvis.speech.voice_loop.VoiceLoop` in a background daemon
thread so ``vanta serve`` is always listening for the wake word ("Hey VANTA")
without the API server ever being blocked or taken down by a voice failure.

Design guarantees (see Task C of the VANTA sprint):
  - **Non-blocking**: the supervisor runs in a daemon thread; the server starts
    and serves requests regardless of voice state.
  - **Auto-restart**: if the loop crashes (mic glitch, transient device error)
    it is restarted with exponential backoff (capped), so a momentary fault
    does not permanently silence voice.
  - **Mic-permission tolerant**: if the mic can't be opened (permission not
    granted, device busy) the failure is logged as a warning and retried — the
    server keeps running normally.
  - **Opt-out**: set ``VANTA_NO_VOICE=1`` (or ``OPENJARVIS_NO_VOICE=1``), or pass
    ``vanta serve --no-voice``, to skip starting the loop entirely.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Cap the restart backoff so a permanently-unavailable mic doesn't busy-loop,
# while a transient fault still recovers quickly.
_MAX_RESTART_BACKOFF_S = 30.0

_thread: Optional[threading.Thread] = None
_stop = threading.Event()

StatusLog = Callable[[str], None]

_TRUE = {"1", "true", "yes", "on"}


def voice_disabled() -> bool:
    """True if the always-on voice loop is opted out via env var."""
    val = (
        os.environ.get("VANTA_NO_VOICE")
        or os.environ.get("OPENJARVIS_NO_VOICE")
        or ""
    ).strip().lower()
    return val in _TRUE


def is_running() -> bool:
    """True if the supervisor thread is alive."""
    return _thread is not None and _thread.is_alive()


def _supervise(status_log: StatusLog) -> None:
    """Run the voice loop forever, restarting on crash with backoff."""
    backoff = 1.0
    while not _stop.is_set():
        try:
            from openjarvis.speech.voice_loop import VoiceLoop
        except Exception as exc:  # missing optional speech deps — give up cleanly
            status_log(f"voice loop unavailable (missing deps): {exc}")
            return
        try:
            status_log('voice loop active — say "Hey VANTA"')
            VoiceLoop().run()  # blocks until it returns or raises
            if _stop.is_set():
                return
            # run() returned on its own (uncommon) — treat as a restart.
            status_log("voice loop exited; restarting")
            backoff = 1.0
        except Exception as exc:  # mic permission/device error — keep server up
            if _stop.is_set():
                return
            status_log(
                f"voice loop error ({exc!r}); retrying in {backoff:.0f}s "
                "(server unaffected)"
            )
        # Wait before the next attempt, but wake immediately on stop.
        if _stop.wait(backoff):
            return
        backoff = min(_MAX_RESTART_BACKOFF_S, backoff * 2.0)


def start_voice_supervisor(status_log: Optional[StatusLog] = None) -> bool:
    """Start the always-on voice loop in a background daemon thread.

    Returns ``True`` if a supervisor thread was started, ``False`` if voice is
    disabled or already running. **Never raises** — a voice failure must never
    prevent the API server from starting.
    """
    global _thread
    log: StatusLog = status_log or (lambda m: logger.info("voice: %s", m))
    try:
        if voice_disabled():
            log("voice loop disabled via VANTA_NO_VOICE — not starting")
            return False
        if is_running():
            return False
        _stop.clear()
        _thread = threading.Thread(
            target=_supervise, args=(log,), name="vanta-voice", daemon=True
        )
        _thread.start()
        return True
    except Exception as exc:  # belt-and-suspenders: never break serve startup
        log(f"could not start voice supervisor: {exc!r}")
        return False


def stop_voice_supervisor(timeout: float = 2.0) -> None:
    """Signal the supervisor to stop and (best-effort) join the thread."""
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=timeout)
