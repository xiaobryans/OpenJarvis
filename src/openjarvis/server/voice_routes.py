"""Voice conversation session REST + SSE API.

Routes:
  POST /v1/voice/session/start   — start the voice conversation loop
  POST /v1/voice/session/stop    — stop the loop
  GET  /v1/voice/session/status  — current loop state + bridge info
  GET  /v1/voice/session/events  — SSE stream of state/transcript/latency events

Platform support (honest declaration):
  macOS (founder platform): SUPPORTED
    - Wake-word: .wake_worker_venv / openwakeword
    - TTS: macOS built-in 'say' command
  Windows / Linux: NOT_PROVEN
    - Wake-word and TTS paths not verified on these platforms.
    - status endpoint reports platform_support accordingly.

User-facing start path:
  The Tauri packaged app calls POST /v1/voice/session/start via the
  VoiceOverlay component.  This is the normal daily-use path — no
  terminal command is required by the end user.

Reuse:
  Uses existing VoiceConversationLoop (which reuses WakeWordBridge,
  get_engine, setup_security, STT backends, TTS path).
  Does NOT duplicate planners, memory, approval systems, or chat loops.
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import queue
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for voice routes")

router = APIRouter()

# ---------------------------------------------------------------------------
# Global session singleton (one active voice session per server process)
# ---------------------------------------------------------------------------

_session_lock = threading.Lock()
_global_session: Optional[Any] = None  # VoiceConversationLoop


def _get_session() -> Optional[Any]:
    return _global_session


def _platform_support() -> Dict[str, str]:
    sys = platform.system()
    if sys == "Darwin":
        return {"status": "SUPPORTED", "platform": "macOS"}
    return {
        "status": "NOT_PROVEN",
        "platform": sys,
        "note": (
            "Wake-word and TTS paths are only proven on macOS. "
            "Windows/Linux require equivalent openwakeword + TTS setup."
        ),
    }


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class VoiceStartRequest(BaseModel):
    record_seconds: float = Field(default=5.0, ge=1.0, le=30.0)
    language: str = Field(default="en", max_length=10)
    session_timeout: float = Field(default=30.0, ge=5.0, le=300.0)
    threshold: Optional[float] = Field(default=None, ge=0.05, le=1.0)
    auto_restart: bool = False
    debug: bool = False
    user_name: str = Field(default="Bryan", max_length=64)


# ---------------------------------------------------------------------------
# POST /v1/voice/session/start
# ---------------------------------------------------------------------------


@router.post("/v1/voice/session/start")
async def start_voice_session(req: VoiceStartRequest) -> Dict[str, Any]:
    """Start the voice conversation loop from the packaged app.

    Requires .wake_worker_venv and a configured STT backend.
    Returns immediately; the loop runs in a background thread.
    """
    global _global_session

    plat = _platform_support()
    if plat["status"] == "NOT_PROVEN":
        return {
            "ok": False,
            "error": f"Voice conversation is NOT_PROVEN on {plat['platform']}. "
                     "Only macOS is currently supported.",
            "platform_support": plat,
        }

    try:
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
    except ImportError as exc:
        return {"ok": False, "error": f"voice_conversation module not available: {exc}"}

    import os as _os

    with _session_lock:
        if _global_session is not None:
            # Return existing session if already running
            st = _global_session.status()
            if st.get("bridge", {}).get("worker_running"):
                return {
                    "ok": True,
                    "already_running": True,
                    "loop_state": st["loop_state"],
                }
            # Previous session stopped — clean up
            try:
                _global_session.stop()
            except Exception:
                pass
            _global_session = None

        # Pre-flight: wake-word worker venv
        _check_bridge = WakeWordBridge()
        if not _check_bridge.is_available():
            return {
                "ok": False,
                "error": (
                    "Wake-word worker venv not found. "
                    "Run: uv venv .wake_worker_venv --python 3.12 && "
                    "uv pip install --python .wake_worker_venv/bin/python openwakeword sounddevice"
                ),
            }

        # Advisory: STT must be configured
        try:
            from openjarvis.autonomy.voice_pipeline import get_voice_status
            vs = get_voice_status()
            if vs.get("stt_status") == "not_configured":
                return {
                    "ok": False,
                    "error": "STT not configured. Install faster-whisper or set OPENAI_API_KEY.",
                }
        except Exception:
            pass

        if req.threshold is not None:
            _os.environ["JARVIS_WAKEWORD_THRESHOLD"] = str(req.threshold)
        if req.debug:
            _os.environ["JARVIS_WAKEWORD_DEBUG"] = "1"

        loop = VoiceConversationLoop(
            record_seconds=req.record_seconds,
            language=req.language,
            auto_restart=req.auto_restart,
            debug=req.debug,
            session_timeout=req.session_timeout,
            user_name=req.user_name,
        )

        result = loop.start(debug=req.debug)
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error", "Failed to start worker")}

        _global_session = loop

    return {
        "ok": True,
        "worker_pid": result.get("worker_pid"),
        "socket": result.get("socket"),
        "loop_state": loop.status()["loop_state"],
        "platform_support": plat,
    }


# ---------------------------------------------------------------------------
# POST /v1/voice/session/stop
# ---------------------------------------------------------------------------


@router.post("/v1/voice/session/stop")
async def stop_voice_session() -> Dict[str, Any]:
    """Stop the active voice session."""
    global _global_session
    with _session_lock:
        sess = _global_session
        _global_session = None

    if sess is None:
        return {"ok": True, "was_running": False}

    try:
        sess.stop()
    except Exception as exc:
        logger.warning("Error stopping voice session: %s", exc)

    return {"ok": True, "was_running": True}


# ---------------------------------------------------------------------------
# GET /v1/voice/session/status
# ---------------------------------------------------------------------------


@router.get("/v1/voice/session/status")
async def get_voice_session_status() -> Dict[str, Any]:
    """Return current voice session state."""
    sess = _get_session()
    plat = _platform_support()

    if sess is None:
        return {
            "active": False,
            "loop_state": "idle",
            "platform_support": plat,
        }

    st = sess.status()
    return {
        "active": True,
        "loop_state": st["loop_state"],
        "turns_completed": st["turns_completed"],
        "record_seconds": st["record_seconds"],
        "language": st["language"],
        "session_timeout": st["session_timeout"],
        "worker_running": st.get("bridge", {}).get("worker_running", False),
        "worker_ready": st.get("bridge", {}).get("worker_ready", False),
        "platform_support": plat,
    }


# ---------------------------------------------------------------------------
# GET /v1/voice/session/events  (SSE)
# ---------------------------------------------------------------------------


@router.get("/v1/voice/session/events")
async def stream_voice_events() -> StreamingResponse:
    """SSE stream of voice state, transcript, response, and latency events.

    Clients connect here to receive real-time updates:
      {"type": "state", "state": "wake_listening", "ts": ...}
      {"type": "state", "state": "wake_detected", "model": ..., "score": ...}
      {"type": "interim_transcript", "text": "Recording... (5s)"}
      {"type": "transcript", "text": "What is the capital of France?"}
      {"type": "response", "text": "The capital of France is Paris."}
      {"type": "latency", "stage": "stt_duration_ms", "value_ms": 1234.5}
      {"type": "error", "message": "..."}
      {"type": "stopped"}

    Replays recent history on connect so the client has context.
    Sends keepalive comments every 15 seconds.
    """
    async def _generate():
        sess = _get_session()
        if sess is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No active voice session'})}\n\n"
            return

        # Replay recent history
        for event in sess.get_events_history():
            yield f"data: {json.dumps(event)}\n\n"

        # Subscribe to live events
        eq = sess.subscribe_events()
        try:
            while True:
                try:
                    # Poll with timeout so we can send keepalives
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: eq.get(timeout=15.0)
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                    # Disconnect on stop sentinel
                    if event.get("type") == "stopped":
                        break
                except queue.Empty:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if sess is not None:
                sess.unsubscribe_events(eq)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
