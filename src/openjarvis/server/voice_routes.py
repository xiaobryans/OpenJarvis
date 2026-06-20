"""Voice conversation session REST + SSE API.

Routes (legacy session loop — wake-word path):
  POST /v1/voice/session/start   — start the voice conversation loop
  POST /v1/voice/session/stop    — stop the loop
  GET  /v1/voice/session/status  — current loop state + bridge info
  GET  /v1/voice/session/events  — SSE stream of state/transcript/latency events

Routes (new deterministic turn engine — manual-command-first):
  POST /v1/voice/turn/start         — start one manual recording turn
  POST /v1/voice/turn/cancel        — cancel the current turn at any stage
  POST /v1/voice/turn/end_recording — force-submit captured audio (End & send)
  GET  /v1/voice/turn/status        — current turn engine state
  GET  /v1/voice/turn/events        — SSE stream of turn state/transcript/vad events

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
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for voice routes")

router = APIRouter()

# ---------------------------------------------------------------------------
# Path constants for error messages
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent.parent
_WORKER_VENV = _REPO_ROOT / ".wake_worker_venv"

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
    # Emergency max cap — NOT the normal turn-ending condition.
    # Normal turns end via silence detection (JARVIS_VOICE_SILENCE_STOP_MS).
    # Default 120 s; raise or lower via this field or JARVIS_VOICE_MAX_RECORD_SECONDS.
    record_seconds: float = Field(default=120.0, ge=1.0, le=300.0)
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

    try:
        plat = _platform_support()
        if plat["status"] == "NOT_PROVEN":
            return {
                "ok": False,
                "error_code": "platform_not_supported",
                "error": f"Voice conversation is NOT_PROVEN on {plat['platform']}. "
                         "Only macOS is currently supported.",
                "detail": plat,
                "recovery": "Use macOS for voice conversation support.",
            }

        try:
            from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
            from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        except ImportError as exc:
            return {
                "ok": False,
                "error_code": "module_import_failed",
                "error": f"voice_conversation module not available: {exc}",
                "detail": str(exc),
                "recovery": "Ensure all dependencies are installed via uv sync.",
            }

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

            # Advisory: STT must be configured
            try:
                from openjarvis.autonomy.voice_pipeline import get_voice_status
                vs = get_voice_status()
                if vs.get("stt_status") == "not_configured":
                    return {
                        "ok": False,
                        "error_code": "stt_not_configured",
                        "error": "STT not configured. Install faster-whisper or set OPENAI_API_KEY.",
                        "detail": vs,
                        "recovery": "Install faster-whisper (local) or set OPENAI_API_KEY (cloud).",
                    }
            except Exception as exc:
                return {
                    "ok": False,
                    "error_code": "stt_check_failed",
                    "error": f"STT status check failed: {exc}",
                    "detail": str(exc),
                    "recovery": "Check voice_pipeline configuration and dependencies.",
                }

            if req.threshold is not None:
                _os.environ["JARVIS_WAKEWORD_THRESHOLD"] = str(req.threshold)
            if req.debug:
                _os.environ["JARVIS_WAKEWORD_DEBUG"] = "1"

            loop = VoiceConversationLoop(
                record_seconds=req.record_seconds,  # emergency max cap
                language=req.language,
                auto_restart=req.auto_restart,
                debug=req.debug,
                session_timeout=req.session_timeout,
                user_name=req.user_name,
                # VAD endpointing — read from env; req overrides not exposed
                # in the API to keep request payload minimal.
                # Tune via JARVIS_VOICE_MIN_RECORD_SECONDS,
                #           JARVIS_VOICE_SILENCE_STOP_MS,
                #           JARVIS_VOICE_MAX_RECORD_SECONDS,
                #           JARVIS_VOICE_SILENCE_RMS
            )

            result = loop.start(debug=req.debug)
            if not result.get("ok"):
                # This path should be rare — loop.start() now returns ok=True
                # even in hotkey-only mode.  Only a hard internal error reaches here.
                return {
                    "ok": False,
                    "error_code": "loop_start_failed",
                    "error": result.get("error", "Failed to start voice loop"),
                    "detail": result,
                    "recovery": "Check server logs. Hotkey trigger via POST /v1/voice/session/trigger.",
                }

            _global_session = loop

        # Include provider info so the UI can display which STT/TTS is active
        # without a separate round-trip.
        try:
            from openjarvis.autonomy.voice_pipeline import get_stt_status, get_tts_status
            _stt = get_stt_status()
            _tts = get_tts_status()
            provider_info = {
                "stt": _stt.get("stt_status", "unknown"),
                "tts": _tts.get("tts_status", "unknown"),
                "stt_primary": _stt.get("primary", False),
                "tts_primary": _tts.get("primary", False),
            }
        except Exception:
            provider_info = {"stt": "unknown", "tts": "unknown"}

        st = loop.status()
        return {
            "ok": True,
            "worker_pid": result.get("worker_pid"),
            "socket": result.get("socket"),
            "loop_state": st["loop_state"],
            "wake_mode": result.get("wake_mode", "wake_word"),
            "wake_failure_reason": result.get("wake_failure_reason"),
            "platform_support": plat,
            "provider_info": provider_info,
        }

    except Exception as exc:
        logger.exception("Unexpected error in start_voice_session")
        return {
            "ok": False,
            "error_code": "unexpected_error",
            "error": f"Unexpected error: {exc}",
            "detail": str(exc),
            "recovery": "Check server logs for full traceback.",
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
        "wake_mode": st.get("wake_mode", "wake_word"),
        "wake_failure_reason": st.get("wake_failure_reason"),
        "platform_support": plat,
    }


# ---------------------------------------------------------------------------
# POST /v1/voice/session/trigger  (hotkey / manual-mic path)
# ---------------------------------------------------------------------------


@router.post("/v1/voice/session/trigger")
async def trigger_voice_session() -> Dict[str, Any]:
    """Manually start a voice recording turn (hotkey / mic-button path).

    Use when:
    - Wake-word is unavailable (hotkey-only mode).
    - User pressed Cmd+Shift+Space in the UI.
    - Frontend mic button clicked while session is listening but idle.

    Requires an active session (POST /v1/voice/session/start first).
    """
    sess = _get_session()
    if sess is None:
        return {
            "ok": False,
            "error": "No active voice session. Call POST /v1/voice/session/start first.",
            "error_code": "no_session",
        }
    return sess.trigger()


# ---------------------------------------------------------------------------
# POST /v1/voice/session/end_recording  ("End & send" / force-stop recording)
# ---------------------------------------------------------------------------


@router.post("/v1/voice/session/end_recording")
async def end_recording_session() -> Dict[str, Any]:
    """Force-end the current VAD recording and submit captured audio to STT.

    Use when silence detection hasn't fired (noisy room, soft speaker).
    Safe to call at any time — if recording is not active, no-ops cleanly.
    The vad SSE event will show stop_reason='manually_ended'.
    """
    sess = _get_session()
    if sess is None:
        return {
            "ok": False,
            "error": "No active voice session.",
            "error_code": "no_session",
        }
    return sess.end_recording()


# ---------------------------------------------------------------------------
# GET /v1/voice/diagnostics
# ---------------------------------------------------------------------------


@router.get("/v1/voice/diagnostics")
async def get_voice_diagnostics() -> Dict[str, Any]:
    """Return non-secret wake/manual-trigger diagnostics for UI truth-state.

    Fields:
      wake_mode              — 'wake_word' | 'hotkey_only'
      wake_worker_ready      — True only when worker process is connected
      wake_trigger_supported — True when wake_mode == 'wake_word'
      wake_phrase_active     — True when wake_mode == 'wake_word' AND worker ready
      manual_trigger_available — True when a session is active (trigger() works)
      configured_shortcut    — string | null (null = no shortcut registered)
      wake_failure_reason    — non-secret error string | null
    """
    sess = _get_session()
    if sess is None:
        return {
            "active": False,
            "wake_mode": None,
            "wake_worker_ready": False,
            "wake_trigger_supported": False,
            "wake_phrase_active": False,
            "manual_trigger_available": False,
            "configured_shortcut": None,
            "wake_failure_reason": None,
        }

    st = sess.status()
    wake_mode = st.get("wake_mode", "wake_word")
    worker_ready = st.get("bridge", {}).get("worker_ready", False)
    wake_phrase_active = wake_mode == "wake_word" and worker_ready

    return {
        "active": True,
        "wake_mode": wake_mode,
        "wake_worker_ready": worker_ready,
        "wake_trigger_supported": wake_mode == "wake_word",
        "wake_phrase_active": wake_phrase_active,
        "manual_trigger_available": True,
        "configured_shortcut": None,
        "wake_failure_reason": st.get("wake_failure_reason"),
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


# ---------------------------------------------------------------------------
# Deterministic turn engine routes — manual-command-first
# ---------------------------------------------------------------------------


def _get_turn_engine():
    from openjarvis.autonomy.voice_turn_engine import get_engine as _get

    return _get()


@router.post("/v1/voice/turn/start")
async def voice_turn_start(request: Request) -> Dict[str, Any]:
    """Start one manual recording turn immediately.

    Returns error_code='turn_in_progress' if a turn is already running.
    Wake word is NOT used — this is the manual-command-first path.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    language = str(body.get("language", "en"))

    # Preflight: verify the configured STT provider is ready before allowing
    # recording to start. Fail fast with a visible non-secret reason so the UI
    # shows an actionable error instead of a long "Transcribing…" hang.
    try:
        from openjarvis.autonomy.voice_pipeline import get_stt_status
        stt = get_stt_status()
        if stt.get("stt_status") == "not_configured":
            _dg_blocker = stt.get("deepgram_blocker") or ""
            _blockers = stt.get("blockers", [])
            return {
                "ok": False,
                "error_code": "stt_not_ready",
                "error": "STT provider not ready — cannot start recording.",
                "deepgram_blocker": _dg_blocker,
                "blockers": _blockers,
                "recovery": "Run `uv sync` to install deepgram-sdk, or set OPENAI_API_KEY / install faster-whisper.",
            }
        # Deepgram selected but SDK import check
        if stt.get("stt_status") == "deepgram":
            try:
                from openjarvis.speech.deepgram import _DEEPGRAM_AVAILABLE
                if not _DEEPGRAM_AVAILABLE:
                    return {
                        "ok": False,
                        "error_code": "stt_not_ready",
                        "error": "deepgram-sdk not installed — run: uv sync",
                        "recovery": "Run `uv sync` to install deepgram-sdk (now a core dependency).",
                    }
            except ImportError:
                pass
    except Exception as _preflight_exc:
        logger.warning("STT preflight check failed (non-fatal): %s", _preflight_exc)

    engine = _get_turn_engine()
    return engine.start_turn(language=language)


@router.post("/v1/voice/turn/cancel")
async def voice_turn_cancel() -> Dict[str, Any]:
    """Cancel the current turn at whatever stage it's in."""
    engine = _get_turn_engine()
    return engine.cancel_turn()


@router.post("/v1/voice/turn/end_recording")
async def voice_turn_end_recording() -> Dict[str, Any]:
    """Force-submit captured audio immediately (End & send).

    Triggers the abort_event on the active VAD loop so the recording
    stops and proceeds to STT without waiting for silence endpointing.
    Returns error_code='not_recording' if no VAD loop is active.
    """
    engine = _get_turn_engine()
    return engine.end_recording_now()


@router.get("/v1/voice/turn/status")
async def voice_turn_status() -> Dict[str, Any]:
    """Current turn engine state — safe to poll."""
    engine = _get_turn_engine()
    return engine.status()


@router.get("/v1/voice/turn/events")
async def voice_turn_events() -> StreamingResponse:
    """SSE stream: state changes, transcript, vad diagnostics, keepalives."""
    engine = _get_turn_engine()
    sub_q = engine.subscribe()

    async def _generate():
        loop = asyncio.get_event_loop()
        try:
            while True:
                try:
                    event = await loop.run_in_executor(
                        None, lambda: sub_q.get(timeout=15.0)
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            engine.unsubscribe(sub_q)

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
