"""Deterministic single-turn voice engine — manual-command-first.

Design principles
-----------------
* A turn starts ONLY on an explicit POST /v1/voice/turn/start.
  Background noise, ambient voices, and wake-word events CANNOT start turns.
* No wake-word dependency for command execution.
* One turn at a time.  Double-starts are rejected with a clear error.
* Every pipeline stage has a hard timeout that surfaces a visible error.
* cancel_turn() is always effective — at recording, STT, route, or TTS.
* end_recording_now() submits captured audio immediately (End & send escape).

Turn pipeline
-------------
  start_turn() called
  → RECORDING          (adaptive VAD; abort_event for End & send)
  → audio validation   (size, duration, sample_rate; fail fast with exact reason)
  → TRANSCRIBING       (existing STT path; 30 s timeout)
  → transcript gate    (existing energy/hallucination/confidence gates)
  → THINKING           (existing engine + safety gates; 60 s timeout)
  → SPEAKING           (existing TTS path; 30 s timeout)
  → IDLE               (turn_complete emitted)

Safety preserved
----------------
* query_jarvis_text() calls setup_security() unconditionally.
* Dangerous commands still require approval.
* No secrets in SSE events or logs.

Reuse (no new STT/TTS/engine systems)
--------------------------------------
* record_command_audio_vad    — voice_conversation.py
* transcribe_command_result   — voice_conversation.py
* evaluate_voice_transcript   — voice_conversation.py
* query_jarvis_text           — voice_conversation.py
* speak_response              — voice_conversation.py
"""

from __future__ import annotations

import concurrent.futures
import io
import logging
import queue
import threading
import time
import wave
from enum import Enum
from typing import Any, Callable, Dict, Generator, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage timeouts (seconds)
# ---------------------------------------------------------------------------

_RECORD_MAX_S: float = 120.0   # emergency cap — same as existing default
_STT_TIMEOUT_S: float = 30.0
_ROUTE_TIMEOUT_S: float = 60.0
_TTS_TIMEOUT_S: float = 30.0

# Audio validation minimums
_MIN_AUDIO_BYTES: int = 500      # WAV header + minimal audio
_MIN_AUDIO_DURATION_S: float = 0.1


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------


class TurnPhase(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    WAITING_FOR_SILENCE = "waiting_for_silence"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"
    CANCELLED = "cancelled"


# Phases from which a new turn may be started
_STARTABLE_PHASES = {TurnPhase.IDLE, TurnPhase.ERROR, TurnPhase.CANCELLED}


# ---------------------------------------------------------------------------
# Deepgram streaming partial transcript helper
# ---------------------------------------------------------------------------


class _DGStreamPartial:
    """Minimal display-only Deepgram streaming client for live partials.

    Runs TWO daemon threads (sender + receiver).  Any failure degrades
    gracefully to no-partials — does NOT affect the canonical VAD + batch
    STT pipeline.  Uses websockets.sync (available via deepgram-sdk dep).
    """

    _DG_WSS = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2&interim_results=true&encoding=linear16"
        "&sample_rate={sample_rate}&channels=1&utterance_end_ms=800"
    )

    def __init__(
        self,
        api_key: str,
        sample_rate: int,
        on_partial: "Callable[[str], None]",
    ) -> None:
        self._api_key = api_key
        self._sample_rate = sample_rate
        self._on_partial = on_partial
        self._audio_q: "queue.Queue[Optional[bytes]]" = queue.Queue(maxsize=500)
        self._stop = threading.Event()
        self._ws = None
        self._ok = False

    def start(self) -> bool:
        try:
            import websockets.sync.client as _ws_sync  # type: ignore[import]
            url = self._DG_WSS.format(sample_rate=self._sample_rate)
            self._ws = _ws_sync.connect(
                url,
                additional_headers={"Authorization": f"Token {self._api_key}"},
                open_timeout=5,
            )
            self._ok = True
        except Exception as exc:
            logger.debug("DGStreamPartial: WebSocket connect failed: %s", exc)
            return False

        threading.Thread(
            target=self._run_sender, daemon=True, name="dg-partial-sender"
        ).start()
        threading.Thread(
            target=self._run_receiver, daemon=True, name="dg-partial-receiver"
        ).start()
        return True

    def send_chunk(self, pcm_bytes: bytes) -> None:
        if not self._ok or self._stop.is_set():
            return
        try:
            self._audio_q.put_nowait(pcm_bytes)
        except queue.Full:
            pass  # drop — display-only, non-blocking

    def stop(self) -> None:
        self._stop.set()
        try:
            self._audio_q.put_nowait(None)
        except Exception:
            pass
        if self._ws:
            try:
                import json as _json
                self._ws.send(_json.dumps({"type": "CloseStream"}))
            except Exception:
                pass
            try:
                self._ws.close()
            except Exception:
                pass

    def _run_sender(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    chunk = self._audio_q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                try:
                    self._ws.send(chunk)
                except Exception:
                    break
        except Exception as exc:
            logger.debug("DGStreamPartial sender: %s", exc)

    def _run_receiver(self) -> None:
        import json as _json
        try:
            while not self._stop.is_set():
                try:
                    msg = self._ws.recv(timeout=2.0)
                except TimeoutError:
                    continue
                except Exception:
                    break
                try:
                    data = _json.loads(msg)
                    alts = (
                        data.get("channel", {}).get("alternatives", [])
                    )
                    if alts:
                        text = alts[0].get("transcript", "").strip()
                        if text:
                            self._on_partial(text)
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("DGStreamPartial receiver: %s", exc)


# ---------------------------------------------------------------------------
# VoiceTurnEngine
# ---------------------------------------------------------------------------


class VoiceTurnEngine:
    """Single-turn voice engine — manual-command-first.

    One global instance per server process.  Thread-safe.
    All stages run in a daemon thread so the HTTP request returns immediately.
    """

    def __init__(
        self,
        silence_stop_ms: Optional[float] = None,
        silence_rms_threshold: Optional[float] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._phase = TurnPhase.IDLE
        self._turn_counter = 0
        self._active_turn_id: Optional[int] = None

        # Tunable defaults — read from env via existing helpers.
        # Default 900ms: finalizes naturally after ~0.9s of quiet after speech.
        # Override via JARVIS_VOICE_SILENCE_STOP_MS env var (e.g. 1500 for
        # noisier environments or 600 for snappier response).
        self._silence_stop_ms: float = silence_stop_ms or _env_float(
            "JARVIS_VOICE_SILENCE_STOP_MS", 900.0
        )
        self._silence_rms_threshold: float = silence_rms_threshold or _env_float(
            "JARVIS_VOICE_SILENCE_RMS", 300.0
        )

        # Signals
        self._cancel_event = threading.Event()
        self._recording_abort = threading.Event()

        # TTS playback handle — allows cancel_turn() to kill the afplay subprocess
        # while it is still speaking.  Imported lazily to avoid circular import.
        from openjarvis.autonomy.voice_conversation import _TTSPlayback
        self._tts_playback = _TTSPlayback()

        # SSE subscriber queues — one per connected client
        self._subscribers: List[queue.Queue] = []
        self._subs_lock = threading.Lock()

        # Last turn artifacts (non-secret; cleared on start_turn)
        self._last_vad: Optional[Dict] = None
        self._last_transcript: str = ""
        self._last_response: str = ""
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_turn(
        self,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Start one recording turn immediately.

        Rejected with error_code='turn_in_progress' if already running.
        Returns immediately; execution continues in a daemon thread.
        """
        with self._lock:
            if self._phase not in _STARTABLE_PHASES:
                return {
                    "ok": False,
                    "error": (
                        f"Turn already in progress (phase={self._phase.value}). "
                        "Cancel first or wait for the turn to complete."
                    ),
                    "error_code": "turn_in_progress",
                    "current_phase": self._phase.value,
                }
            self._turn_counter += 1
            turn_id = self._turn_counter
            self._active_turn_id = turn_id
            self._cancel_event.clear()
            self._recording_abort.clear()
            self._last_transcript = ""
            self._last_response = ""
            self._last_error = None
            self._phase = TurnPhase.RECORDING

        self._emit({"type": "state", "state": TurnPhase.RECORDING.value, "turn_id": turn_id})
        logger.info("VoiceTurnEngine: turn %d started (lang=%s)", turn_id, language)

        threading.Thread(
            target=self._run_turn,
            args=(turn_id, language),
            daemon=True,
            name=f"voice-turn-{turn_id}",
        ).start()

        return {"ok": True, "turn_id": turn_id}

    def cancel_turn(self) -> Dict[str, Any]:
        """Cancel the current turn at whatever stage it's in."""
        with self._lock:
            phase = self._phase
            turn_id = self._active_turn_id

        if phase in _STARTABLE_PHASES:
            return {"ok": True, "was_idle": True, "phase": phase.value}

        self._cancel_event.set()
        self._recording_abort.set()
        # Kill any active TTS subprocess (afplay/say) so speaking stops immediately.
        self._tts_playback.cancel()
        logger.info("VoiceTurnEngine: cancel requested (turn=%s phase=%s)", turn_id, phase.value)
        return {"ok": True, "cancelled_turn": turn_id, "phase": phase.value}

    def end_recording_now(self) -> Dict[str, Any]:
        """Force-end active VAD recording and proceed to STT immediately."""
        with self._lock:
            phase = self._phase

        if phase not in (TurnPhase.RECORDING, TurnPhase.WAITING_FOR_SILENCE):
            return {
                "ok": False,
                "error": "No active recording to end.",
                "error_code": "not_recording",
                "current_phase": phase.value,
            }
        self._recording_abort.set()
        return {"ok": True}

    def status(self) -> Dict[str, Any]:
        """Current engine state — safe to poll."""
        with self._lock:
            return {
                "phase": self._phase.value,
                "turn_id": self._active_turn_id,
                "last_transcript": self._last_transcript,
                "last_response": self._last_response,
                "last_error": self._last_error,
                "last_vad": self._last_vad,
            }

    def subscribe(self) -> "queue.Queue[Dict]":
        """Return a new subscriber queue. Caller is responsible for draining it.

        Unsubscribe by calling unsubscribe(q) or let the SSE handler do it.
        """
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._subs_lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: "queue.Queue") -> None:
        with self._subs_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def events_stream(self, subscriber_q: "queue.Queue") -> Generator[Dict, None, None]:
        """Yield events from a subscriber queue; emit keepalive on idle."""
        try:
            while True:
                try:
                    yield subscriber_q.get(timeout=15)
                except queue.Empty:
                    yield {"type": "keepalive", "ts": time.time()}
        finally:
            self.unsubscribe(subscriber_q)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _emit(self, event: Dict) -> None:
        event.setdefault("ts", time.time())
        with self._subs_lock:
            dead: List["queue.Queue"] = []
            for q in self._subscribers:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.remove(q)

    def _set_phase(self, phase: TurnPhase, **extra) -> None:
        with self._lock:
            self._phase = phase
        self._emit({"type": "state", "state": phase.value, **extra})
        logger.info("VoiceTurnEngine: → %s %s", phase.value, extra if extra else "")

    def _is_turn_live(self, turn_id: int) -> bool:
        with self._lock:
            return self._active_turn_id == turn_id

    def _finalize(self, turn_id: int) -> None:
        with self._lock:
            if self._active_turn_id == turn_id:
                self._active_turn_id = None
                if self._phase not in (TurnPhase.IDLE, TurnPhase.ERROR, TurnPhase.CANCELLED):
                    self._phase = TurnPhase.IDLE
        self._emit({"type": "turn_done", "turn_id": turn_id, "final_phase": self._phase.value})
        logger.info(
            "VoiceTurnEngine: turn %d finalised (phase=%s)", turn_id, self._phase.value
        )

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    def _run_turn(self, turn_id: int, language: str) -> None:
        """Full turn pipeline — runs in a daemon thread."""
        if not self._is_turn_live(turn_id):
            return
        try:
            # Stage 1: Record
            audio, ok = self._stage_record(turn_id)
            if audio is None:
                return  # _stage_record already set phase + finalised

            # Stage 2: Validate audio
            if not self._is_turn_live(turn_id):
                self._set_phase(TurnPhase.CANCELLED)
                self._finalize(turn_id)
                return

            validation = _validate_audio(audio)
            if not validation["ok"]:
                reason = f"audio_invalid: {validation['reason']}"
                logger.warning("Turn %d audio validation failed: %s", turn_id, validation)
                self._last_error = reason
                self._emit({"type": "error", "reason": reason, "detail": validation})
                self._set_phase(TurnPhase.ERROR, reason=reason)
                self._finalize(turn_id)
                return

            # Stage 3: STT
            if not self._is_turn_live(turn_id):
                self._set_phase(TurnPhase.CANCELLED)
                self._finalize(turn_id)
                return
            text = self._stage_stt(turn_id, audio, language)
            if text is None:
                return

            # Stage 4: Route / model
            if not self._is_turn_live(turn_id):
                self._set_phase(TurnPhase.CANCELLED)
                self._finalize(turn_id)
                return
            response = self._stage_route(turn_id, text)
            if response is None:
                return

            # Stage 5: TTS
            self._stage_tts(turn_id, response)

        except Exception as exc:
            logger.exception("VoiceTurnEngine: unexpected error in turn %d", turn_id)
            if self._is_turn_live(turn_id):
                self._last_error = f"unexpected_error: {type(exc).__name__}: {exc}"
                self._emit({"type": "error", "reason": self._last_error})
                self._set_phase(TurnPhase.ERROR, reason=self._last_error)
                self._finalize(turn_id)

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _stage_record(self, turn_id: int):
        """Record with adaptive VAD. Returns (audio_bytes, ok) or (None, False)."""
        from openjarvis.autonomy.voice_conversation import (
            _DEFAULT_MIN_RECORD_SECONDS,
            record_command_audio_vad,
        )

        calib_data: Dict = {}
        last_chunk_diag: Dict = {}   # latest on_vad_chunk data for final vad event

        def _on_state(s: str) -> None:
            if not self._is_turn_live(turn_id):
                return
            if s in ("waiting_for_silence", "recording"):
                with self._lock:
                    self._phase = TurnPhase(s)
            self._emit({"type": "state", "state": s})

        def _on_calibrated(noise_floor: float, eff_thresh: float) -> None:
            calib_data["noise_floor_rms"] = round(noise_floor, 1)
            calib_data["effective_threshold"] = round(eff_thresh, 1)

        def _on_vad_chunk(chunk: Dict) -> None:
            """Emit live VAD diagnostics as SSE vad_progress events.

            Throttled: only emitted when silence is accumulating (silence_consecutive >= 1)
            or on every 5th chunk during speech, to avoid flooding the SSE stream.
            Always updates last_chunk_diag for the final vad SSE event.
            """
            last_chunk_diag.update(chunk)
            if not self._is_turn_live(turn_id):
                return
            sc = chunk.get("silence_consecutive", 0)
            loud_streak = chunk.get("loud_streak", 0)
            # Only emit when silence is actively accumulating or every 5th speech chunk
            if sc > 0 or (loud_streak % 5 == 0):
                self._emit({
                    "type": "vad_progress",
                    "rms": chunk.get("rms"),
                    "threshold": chunk.get("threshold"),
                    "foreground_threshold": chunk.get("foreground_threshold"),
                    "noise_floor": chunk.get("noise_floor"),
                    "ambient_ema": chunk.get("ambient_ema"),
                    "speech_ema": chunk.get("speech_ema"),
                    "silence_elapsed_ms": chunk.get("silence_elapsed_ms"),
                    "relative_silence_ms": chunk.get("relative_silence_ms"),
                    "silence_consecutive": sc,
                    "silence_chunks_needed": chunk.get("silence_chunks_needed"),
                    "speech_detected": chunk.get("speech_detected"),
                    "background_noise_detected": chunk.get("background_noise_detected"),
                })

        # Deepgram streaming partial transcripts (display-only).
        # Runs in daemon threads; degrades gracefully on any failure.
        _dg_partial: Optional[_DGStreamPartial] = None
        import os as _os
        _dg_key = _os.environ.get("DEEPGRAM_API_KEY", "")
        if _dg_key:
            _last_partial: Dict[str, str] = {}

            def _on_partial(text: str) -> None:
                if not self._is_turn_live(turn_id):
                    return
                if text != _last_partial.get("text"):
                    _last_partial["text"] = text
                    self._emit({"type": "partial_transcript", "text": text})
                    logger.debug("DG partial: %r", text)

            _dg_partial = _DGStreamPartial(
                api_key=_dg_key,
                sample_rate=16000,
                on_partial=_on_partial,
            )
            if not _dg_partial.start():
                _dg_partial = None  # failed to connect — no partials this turn
        else:
            logger.debug("DGStreamPartial skipped: DEEPGRAM_API_KEY not set")

        def _on_audio_chunk(pcm_bytes: bytes) -> None:
            if _dg_partial is not None:
                _dg_partial.send_chunk(pcm_bytes)

        rec_start = time.monotonic()
        try:
            audio, stop_reason = record_command_audio_vad(
                min_seconds=_DEFAULT_MIN_RECORD_SECONDS,
                silence_stop_ms=self._silence_stop_ms,
                max_seconds=_RECORD_MAX_S,
                sample_rate=16000,
                silence_rms_threshold=self._silence_rms_threshold,
                on_state=_on_state,
                abort_event=self._recording_abort,
                on_calibrated=_on_calibrated,
                on_vad_chunk=_on_vad_chunk,
                on_audio_chunk=_on_audio_chunk,
            )
        except Exception as exc:
            logger.error("Recording exception in turn %d: %s", turn_id, exc)
            if self._is_turn_live(turn_id):
                self._last_error = f"recording_failed: {exc}"
                self._emit({"type": "error", "reason": self._last_error})
                self._set_phase(TurnPhase.ERROR, reason=self._last_error)
                self._finalize(turn_id)
            return None, False

        # Stop streaming partial transcripts (recording is done)
        if _dg_partial is not None:
            _dg_partial.stop()

        vad_diag = {
            "stop_reason": stop_reason,
            "endpoint_mode": last_chunk_diag.get("endpoint_mode", "absolute"),
            "duration_s": round(time.monotonic() - rec_start, 2),
            "silence_stop_ms": self._silence_stop_ms,
            "background_noise_detected": last_chunk_diag.get("background_noise_detected", False),
            "speech_detected": last_chunk_diag.get("speech_detected", False),
            "speech_ema": last_chunk_diag.get("speech_ema"),
            "ambient_ema": last_chunk_diag.get("ambient_ema"),
            **calib_data,
        }
        self._last_vad = vad_diag
        self._emit({"type": "vad", **vad_diag})

        # Check if cancelled during recording
        if self._cancel_event.is_set() or not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None, False

        return audio, True

    def _stage_stt(self, turn_id: int, audio: bytes, language: str) -> Optional[str]:
        """Run STT with timeout. Returns transcript text or None on error/cancel."""
        self._set_phase(TurnPhase.TRANSCRIBING)

        from openjarvis.autonomy.voice_conversation import (
            evaluate_voice_transcript,
            transcribe_command_result,
        )

        def _do_stt():
            return transcribe_command_result(audio, language=language)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_do_stt)
                try:
                    stt_result = fut.result(timeout=_STT_TIMEOUT_S)
                except concurrent.futures.TimeoutError:
                    raise TimeoutError(
                        f"STT timed out after {_STT_TIMEOUT_S}s — check network/API"
                    )
        except TimeoutError as exc:
            self._last_error = str(exc)
            self._emit({"type": "error", "reason": self._last_error})
            self._set_phase(TurnPhase.ERROR, reason=self._last_error)
            self._finalize(turn_id)
            return None
        except Exception as exc:
            self._last_error = f"stt_error: {type(exc).__name__}: {exc}"
            self._emit({"type": "error", "reason": self._last_error})
            self._set_phase(TurnPhase.ERROR, reason=self._last_error)
            self._finalize(turn_id)
            return None

        if self._cancel_event.is_set() or not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None

        text = (
            stt_result.text.strip()
            if hasattr(stt_result, "text")
            else str(stt_result).strip()
        )

        # Existing transcript gate: energy, hallucination fragments, confidence
        decision = evaluate_voice_transcript(
            text, stt_result, wav_bytes=audio, is_stop_phrase=False
        )
        if not decision.accepted:
            reason = f"transcript_rejected:{decision.reason}"
            logger.info(
                "Turn %d transcript rejected (%s): %r", turn_id, decision.reason, text
            )
            self._last_error = reason
            self._emit({"type": "transcript_rejected", "reason": decision.reason, "text": text})
            self._set_phase(TurnPhase.ERROR, reason=reason)
            self._finalize(turn_id)
            return None

        text = decision.text
        self._last_transcript = text
        self._emit({"type": "transcript", "text": text})
        logger.info("Turn %d transcript accepted: %r", turn_id, text)
        return text

    def _stage_route(self, turn_id: int, text: str) -> Optional[str]:
        """Route through Jarvis engine with safety gates and timeout.

        Runtime/status queries (voice provider, Deepgram, fallback, etc.) are
        intercepted BEFORE the LLM and answered directly from real runtime state.
        """
        self._set_phase(TurnPhase.THINKING)

        from openjarvis.autonomy.voice_conversation import (
            handle_voice_runtime_query,
            query_jarvis_text,
        )

        # Intercept voice/provider/status queries before the LLM so the user
        # gets accurate runtime state instead of a generic model-generated answer.
        runtime_answer = handle_voice_runtime_query(text)
        if runtime_answer is not None:
            logger.info(
                "Turn %d: runtime query intercepted — skipping LLM: %r", turn_id, text[:60]
            )
            self._emit({"type": "route", "intercepted": True, "reason": "voice_runtime_query"})
            return runtime_answer

        cancel = self._cancel_event
        route_info: Dict = {}

        def _on_route(r: Dict) -> None:
            route_info.update(r)
            self._emit({"type": "route", **r})

        def _do_route():
            return query_jarvis_text(text, on_route=_on_route)

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_do_route)
                deadline = time.monotonic() + _ROUTE_TIMEOUT_S
                while True:
                    try:
                        response = fut.result(timeout=1.0)
                        break
                    except concurrent.futures.TimeoutError:
                        if cancel.is_set():
                            fut.cancel()
                            self._set_phase(TurnPhase.CANCELLED)
                            self._finalize(turn_id)
                            return None
                        if time.monotonic() >= deadline:
                            raise TimeoutError(
                                f"Jarvis route timed out after {_ROUTE_TIMEOUT_S}s"
                            )
        except TimeoutError as exc:
            self._last_error = str(exc)
            self._emit({"type": "error", "reason": self._last_error})
            self._set_phase(TurnPhase.ERROR, reason=self._last_error)
            self._finalize(turn_id)
            return None
        except Exception as exc:
            self._last_error = f"route_error: {type(exc).__name__}: {exc}"
            self._emit({"type": "error", "reason": self._last_error})
            self._set_phase(TurnPhase.ERROR, reason=self._last_error)
            self._finalize(turn_id)
            return None

        if cancel.is_set() or not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None

        self._last_response = response
        self._emit({"type": "response", "text": response})
        logger.info(
            "Turn %d response (%d chars): %r…", turn_id, len(response), response[:60]
        )
        return response

    def _stage_tts(self, turn_id: int, text: str) -> None:
        """Speak response with timeout (non-fatal on timeout — text was displayed)."""
        self._set_phase(TurnPhase.SPEAKING)

        from openjarvis.autonomy.voice_conversation import speak_response

        cancel = self._cancel_event

        def _do_tts():
            return speak_response(
                text,
                playback=self._tts_playback,
                cancel_check=lambda: cancel.is_set(),
            )

        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_do_tts)
                try:
                    fut.result(timeout=_TTS_TIMEOUT_S)
                except concurrent.futures.TimeoutError:
                    logger.warning(
                        "Turn %d TTS timed out after %ss — text response still shown",
                        turn_id,
                        _TTS_TIMEOUT_S,
                    )
        except Exception as exc:
            logger.warning("Turn %d TTS error (non-fatal): %s", turn_id, exc)

        # Always complete turn normally — even on TTS failure, the text was shown
        if self._is_turn_live(turn_id) and not cancel.is_set():
            self._set_phase(TurnPhase.IDLE, reason="turn_complete")
        elif cancel.is_set():
            self._set_phase(TurnPhase.CANCELLED)

        self._finalize(turn_id)


# ---------------------------------------------------------------------------
# Audio validation
# ---------------------------------------------------------------------------


def _validate_audio(wav_bytes: bytes) -> Dict:
    """Validate WAV audio before sending to STT. No network calls."""
    if not wav_bytes:
        return {"ok": False, "reason": "empty_audio", "bytes": 0}

    n = len(wav_bytes)
    if n < _MIN_AUDIO_BYTES:
        return {"ok": False, "reason": "audio_too_short", "bytes": n}

    try:
        with wave.open(io.BytesIO(wav_bytes)) as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            channels = wf.getnchannels()
    except Exception as exc:
        return {"ok": False, "reason": f"wav_parse_error:{exc}", "bytes": n}

    if rate < 1:
        return {"ok": False, "reason": "invalid_sample_rate", "sample_rate": rate}

    duration_s = frames / rate
    if duration_s < _MIN_AUDIO_DURATION_S:
        return {
            "ok": False,
            "reason": "duration_too_short",
            "duration_s": round(duration_s, 3),
            "minimum_s": _MIN_AUDIO_DURATION_S,
        }

    return {
        "ok": True,
        "bytes": n,
        "duration_s": round(duration_s, 2),
        "sample_rate": rate,
        "channels": channels,
    }


# ---------------------------------------------------------------------------
# Env var helper (reuse pattern from voice_conversation.py)
# ---------------------------------------------------------------------------


def _env_float(key: str, default: float) -> float:
    import os
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_engine: Optional[VoiceTurnEngine] = None
_engine_lock = threading.Lock()


def get_engine() -> VoiceTurnEngine:
    """Return the process-level VoiceTurnEngine singleton."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = VoiceTurnEngine()
    return _engine


__all__ = [
    "TurnPhase",
    "VoiceTurnEngine",
    "get_engine",
    "_validate_audio",
]
