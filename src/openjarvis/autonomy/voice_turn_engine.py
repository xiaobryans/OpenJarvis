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

Turn pipeline (single turn)
----------------------------
  start_turn() called
  → RECORDING          (adaptive VAD; abort_event for End & send)
  → audio validation   (size, duration, sample_rate; fail fast with exact reason)
  → TRANSCRIBING       (existing STT path; 30 s timeout)
  → transcript gate    (existing energy/hallucination/confidence gates)
  → THINKING           (existing engine + safety gates; 60 s timeout)
  → SPEAKING           (existing TTS path; 30 s timeout)
  → FOLLOW_UP_LISTENING (brief wait for next utterance — no tap required)
     ↳ speech detected  → RECORDING → TRANSCRIBING → THINKING → SPEAKING → FOLLOW_UP_LISTENING
     ↳ stop phrase      → IDLE (conversation_ended)
     ↳ timeout          → IDLE (conversation_timeout)
     ↳ cancel           → CANCELLED → IDLE

Safety preserved
----------------
* query_jarvis_text() calls setup_security() unconditionally.
* Dangerous commands still require approval.
* No secrets in SSE events or logs.
* Follow-up mode does NOT skip approval gates for tool/action requests.
* Conversation does NOT record indefinitely — FOLLOW_UP_TIMEOUT_S cap applies.

Reuse (no new STT/TTS/engine systems)
--------------------------------------
* record_command_audio_vad    — voice_conversation.py
* transcribe_command_result   — voice_conversation.py
* evaluate_voice_transcript   — voice_conversation.py
* query_jarvis_text           — voice_conversation.py
* speak_response              — voice_conversation.py

Mic pickup / gain normalization
--------------------------------
* After recording, audio is gain-normalized before STT if RMS is below
  _TARGET_SPEECH_RMS.  This improves STT accuracy when Bryan is speaking
  at normal volume from normal laptop distance.
* Original RMS, scale factor, and "mic_too_quiet" diagnostic are emitted
  via the vad SSE event so the UI can surface a hint.
* Maximum scale factor is capped at _GAIN_NORM_MAX_SCALE to avoid
  amplifying ambient noise (fans, HVAC) instead of speech.

Wake word
---------
* Wake word: HOLD — no provider is configured or proven on this system.
* Diagnostics (wake_enabled, wake_available, etc.) are exposed via status()
  so the UI can show accurate "wake word — coming soon" state.
* Tap-to-speak (the current path) is unaffected.
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
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stage timeouts (seconds)
# ---------------------------------------------------------------------------

_RECORD_MAX_S: float = 120.0   # emergency cap — same as existing default
_STT_TIMEOUT_S: float = 30.0
# When Deepgram streaming drives endpointing (noise-robust UtteranceEnd), the
# energy-VAD silence window is raised to this backstop so the VAD only fires if
# Deepgram stalls — avoids premature energy-VAD cutoff in noisy rooms.
_DG_VAD_BACKSTOP_MS: float = 4000.0
_ROUTE_TIMEOUT_S: float = 60.0
_TTS_TIMEOUT_S: float = 30.0

# Audio validation minimums
_MIN_AUDIO_BYTES: int = 500      # WAV header + minimal audio
_MIN_AUDIO_DURATION_S: float = 0.1

# ---------------------------------------------------------------------------
# Follow-up listening (hands-free conversation mode)
# ---------------------------------------------------------------------------

# How long to wait for a follow-up utterance after Jarvis finishes speaking.
# After this window with no speech detected, conversation returns to idle.
# Override via JARVIS_VOICE_FOLLOWUP_TIMEOUT_S env var.
_FOLLOWUP_TIMEOUT_S: float = 10.0

# Minimum recording before silence endpointing during follow-up.
# Shorter than main turn so the user doesn't need to wait as long.
_FOLLOWUP_MIN_RECORD_S: float = 0.5

# ---------------------------------------------------------------------------
# Mic gain normalization
# ---------------------------------------------------------------------------

# Target RMS for normalized audio before STT.
# Normal conversational speech at laptop distance ≈ 600–3000 RMS (int16).
# If recording RMS is below this, we scale up to improve STT accuracy.
# Override via JARVIS_VOICE_TARGET_SPEECH_RMS env var.
_TARGET_SPEECH_RMS: float = 1000.0

# Maximum gain multiplier — cap prevents amplifying pure noise when the
# mic captures only ambient noise with no real speech.
_GAIN_NORM_MAX_SCALE: float = 6.0

# "Mic too quiet" hint threshold: if we had to apply > this multiplier,
# the original signal was very faint. UI shows a diagnostic hint.
_GAIN_TOO_QUIET_SCALE: float = 4.0

# ---------------------------------------------------------------------------
# Stop phrases — end the conversation and return to idle
# ---------------------------------------------------------------------------

_STOP_PHRASES: frozenset = frozenset({
    "stop",
    "stop listening",
    "cancel",
    "never mind",
    "nevermind",
    "that's all",
    "thats all",
    "pause",
    "go back to sleep",
    "go to sleep",
    "goodbye",
    "goodbye jarvis",
    "sleep",
    "exit",
    "quit",
})


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
    FOLLOW_UP_LISTENING = "follow_up_listening"
    ERROR = "error"
    CANCELLED = "cancelled"


# Phases from which a new turn may be started
_STARTABLE_PHASES = {TurnPhase.IDLE, TurnPhase.ERROR, TurnPhase.CANCELLED}


# ---------------------------------------------------------------------------
# Deepgram streaming partial transcript helper
# ---------------------------------------------------------------------------


class _DGStreamPartial:
    """Deepgram streaming client for live partial transcripts + endpointing.

    Two roles, both display/control only — the canonical batch STT path
    remains the source of truth for the final transcript:
      1. on_partial(text)   — interim/partial transcripts for live caption
      2. on_endpoint(reason) — fired on Deepgram UtteranceEnd / speech_final,
         used to end recording naturally (noise-robust, word-gap based)

    Runs two daemon threads (sender + receiver).  Any failure degrades
    gracefully — the energy-VAD endpoint + batch STT still complete the turn.
    Uses websockets.sync (installed transitively via deepgram-sdk).

    NOTE: Deepgram requires utterance_end_ms >= 1000. Values below 1000 are
    rejected with HTTP 400 (this was the original "no live transcript" bug).
    """

    # interim_results=true → partial transcripts (live "You: ..." caption).
    # endpointing=N → speech_final after ~N ms of (neural-VAD) trailing
    #   silence. This is the PRIMARY natural endpoint: fast, in Bryan's
    #   700-1200ms target, and noise-robust (Deepgram's neural VAD ignores
    #   non-speech room noise, unlike energy VAD).
    # utterance_end_ms=1000 → UtteranceEnd backup (word-gap based; MUST be
    #   >= 1000 or Deepgram rejects the connection with HTTP 400 — this was
    #   the original "no live transcript" bug, where 800 disabled everything).
    _DG_WSS = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2&interim_results=true&encoding=linear16"
        "&sample_rate={sample_rate}&channels=1"
        "&utterance_end_ms=1000&endpointing={endpointing_ms}"
    )

    def __init__(
        self,
        api_key: str,
        sample_rate: int,
        on_partial: "Callable[[str], None]",
        on_endpoint: "Optional[Callable[[str], None]]" = None,
        endpointing_ms: int = 700,
    ) -> None:
        self._api_key = api_key
        self._sample_rate = sample_rate
        self._on_partial = on_partial
        self._on_endpoint = on_endpoint
        self._endpointing_ms = max(int(endpointing_ms), 100)
        self._audio_q: "queue.Queue[Optional[bytes]]" = queue.Queue(maxsize=500)
        self._stop = threading.Event()
        self._ws = None
        self._ok = False
        # Diagnostics (sprint-required, non-secret)
        self.connected: bool = False
        self.chunks_sent: int = 0
        self.events_received: int = 0
        self.last_error: Optional[str] = None
        self._endpoint_fired: bool = False

    def start(self) -> bool:
        try:
            import websockets.sync.client as _ws_sync  # type: ignore[import]
            url = self._DG_WSS.format(
                sample_rate=self._sample_rate,
                endpointing_ms=self._endpointing_ms,
            )
            self._ws = _ws_sync.connect(
                url,
                additional_headers={"Authorization": f"Token {self._api_key}"},
                open_timeout=5,
            )
            self._ok = True
            self.connected = True
        except Exception as exc:
            self.last_error = f"connect: {type(exc).__name__}: {exc}"
            logger.warning("DGStreamPartial: WebSocket connect failed: %s", self.last_error)
            return False

        threading.Thread(
            target=self._run_sender, daemon=True, name="dg-partial-sender"
        ).start()
        threading.Thread(
            target=self._run_receiver, daemon=True, name="dg-partial-receiver"
        ).start()
        logger.info("DGStreamPartial: connected — live partials + endpointing active")
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
                    self.chunks_sent += 1
                except Exception as exc:
                    self.last_error = f"send: {type(exc).__name__}: {exc}"
                    break
        except Exception as exc:
            self.last_error = f"sender: {type(exc).__name__}: {exc}"
            logger.debug("DGStreamPartial sender: %s", exc)

    def _fire_endpoint(self, reason: str) -> None:
        if self._endpoint_fired:
            return
        self._endpoint_fired = True
        if self._on_endpoint is not None:
            try:
                self._on_endpoint(reason)
            except Exception:
                pass

    def _run_receiver(self) -> None:
        import json as _json
        try:
            while not self._stop.is_set():
                try:
                    msg = self._ws.recv(timeout=2.0)
                except TimeoutError:
                    continue
                except Exception as exc:
                    # ConnectionClosedOK is expected on normal stop
                    if "ConnectionClosed" not in type(exc).__name__:
                        self.last_error = f"recv: {type(exc).__name__}: {exc}"
                    break
                self.events_received += 1
                try:
                    data = _json.loads(msg)
                    msg_type = data.get("type", "")

                    # UtteranceEnd → word-gap backup endpoint (~1000ms).
                    if msg_type == "UtteranceEnd":
                        self._fire_endpoint("deepgram_utterance_end")
                        continue

                    alts = data.get("channel", {}).get("alternatives", [])
                    if alts:
                        text = alts[0].get("transcript", "").strip()
                        if text:
                            self._on_partial(text)
                        # speech_final → PRIMARY natural endpoint (~endpointing
                        # ms of neural-VAD trailing silence after real speech).
                        # Noise-robust; fires only after recognized words.
                        if data.get("speech_final") and text:
                            self._fire_endpoint("deepgram_speech_final")
                except Exception:
                    pass
        except Exception as exc:
            self.last_error = f"receiver: {type(exc).__name__}: {exc}"
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
        followup_enabled: bool = True,
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

        # Follow-up listening config
        self._followup_timeout_s: float = _env_float(
            "JARVIS_VOICE_FOLLOWUP_TIMEOUT_S", _FOLLOWUP_TIMEOUT_S
        )
        self._followup_enabled: bool = followup_enabled

        # Conversation-level tracking (resets on each start_turn)
        self._conversation_turns: int = 0   # number of turns in current conversation
        self._in_conversation: bool = False  # True while follow-up loop is running

        # Gain normalization
        self._target_speech_rms: float = _env_float(
            "JARVIS_VOICE_TARGET_SPEECH_RMS", _TARGET_SPEECH_RMS
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

        # Deepgram partial-streaming diagnostics + endpoint tracking
        self._dg_endpoint_reason: Optional[str] = None
        self._partial_sse_count: int = 0
        self._partial_diag: Dict[str, Any] = {}
        self._last_partial_diag: Dict[str, Any] = {}

        # Mic gain diagnostics (per-turn)
        self._last_gain_diag: Dict[str, Any] = {}

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
            self._conversation_turns = 0
            self._in_conversation = False
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
        """Cancel the current turn at whatever stage it's in.

        Works during FOLLOW_UP_LISTENING — cancels the follow-up recording and
        exits the conversation loop, returning to IDLE.
        """
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
                "partial_diag": self._last_partial_diag,
                # Follow-up / conversation mode
                "follow_up_enabled": self._followup_enabled,
                "follow_up_timeout_s": self._followup_timeout_s,
                "in_conversation": self._in_conversation,
                "conversation_turns": self._conversation_turns,
                # Mic gain diagnostics
                "mic_gain_diag": self._last_gain_diag,
                # Wake word diagnostics (HOLD — no provider configured)
                "wake_enabled": False,
                "wake_available": False,
                "wake_provider": None,
                "wake_worker_running": False,
                "wake_last_error": "not_implemented: no wake-word provider configured in this build",
                "wake_last_detected_at": None,
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
        """Full turn pipeline — runs in a daemon thread.

        After TTS completes, enters the follow-up listening loop so Bryan can
        respond naturally without tapping the mic again.  The loop exits when:
          - Bryan says a stop phrase ("stop", "cancel", "that's all", etc.)
          - No speech is detected within _followup_timeout_s seconds
          - cancel_turn() is called

        When follow-up is disabled (followup_enabled=False), the turn
        finalizes immediately after TTS completes.
        """
        if not self._is_turn_live(turn_id):
            return
        try:
            # ── First turn in the conversation ──────────────────────────
            first_ok = self._run_single_turn(turn_id, language)
            if first_ok is None:
                return  # error / cancel — pipeline already finalized

            # ── Follow-up conversation loop (or finalize if disabled) ────
            if self._followup_enabled and not self._cancel_event.is_set():
                self._follow_up_loop(turn_id, language)
            else:
                # Follow-up disabled — finalize immediately after TTS
                if self._is_turn_live(turn_id) and not self._cancel_event.is_set():
                    self._set_phase(TurnPhase.IDLE, reason="turn_complete")
                elif self._cancel_event.is_set():
                    self._set_phase(TurnPhase.CANCELLED)
                self._finalize(turn_id)

        except Exception as exc:
            logger.exception("VoiceTurnEngine: unexpected error in turn %d", turn_id)
            if self._is_turn_live(turn_id):
                self._last_error = f"unexpected_error: {type(exc).__name__}: {exc}"
                self._emit({"type": "error", "reason": self._last_error})
                self._set_phase(TurnPhase.ERROR, reason=self._last_error)
                self._finalize(turn_id)

    def _run_single_turn(self, turn_id: int, language: str) -> Optional[bool]:
        """Execute one RECORDING→TRANSCRIBING→THINKING→SPEAKING cycle.

        Returns True when TTS completes successfully (caller may follow-up).
        Returns None when cancelled / error (turn already finalized).
        Does NOT finalize on success — caller decides what comes next.
        """
        # Stage 1: Record
        audio, ok = self._stage_record(turn_id)
        if audio is None:
            return None  # _stage_record already set phase + finalised

        # Stage 2: Validate audio
        if not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None

        validation = _validate_audio(audio)
        if not validation["ok"]:
            reason = f"audio_invalid: {validation['reason']}"
            logger.warning("Turn %d audio validation failed: %s", turn_id, validation)
            self._last_error = reason
            self._emit({"type": "error", "reason": reason, "detail": validation})
            self._set_phase(TurnPhase.ERROR, reason=reason)
            self._finalize(turn_id)
            return None

        # Stage 3: STT
        if not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None
        text = self._stage_stt(turn_id, audio, language)
        if text is None:
            return None

        # Stage 4: Route / model
        if not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None
        response = self._stage_route(turn_id, text)
        if response is None:
            return None

        # Stage 5: TTS
        tts_ok = self._stage_tts_nonfinalize(turn_id, response)
        if not tts_ok:
            return None  # cancelled — already finalized in _stage_tts_nonfinalize

        with self._lock:
            self._conversation_turns += 1

        return True

    def _follow_up_loop(self, turn_id: int, language: str) -> None:
        """Hands-free follow-up listening after TTS completes.

        Waits up to _followup_timeout_s for the user to speak.  If speech
        is detected, processes another full RECORDING→STT→THINKING→TTS cycle.
        Exits on stop phrase, timeout, or cancel.  Always finalizes the turn.
        """
        with self._lock:
            self._in_conversation = True

        try:
            while self._is_turn_live(turn_id) and not self._cancel_event.is_set():
                # Enter follow-up listening state
                self._set_phase(
                    TurnPhase.FOLLOW_UP_LISTENING,
                    timeout_s=self._followup_timeout_s,
                    conversation_turns=self._conversation_turns,
                )
                self._emit({
                    "type": "follow_up_listening",
                    "timeout_s": self._followup_timeout_s,
                    "conversation_turns": self._conversation_turns,
                })
                logger.info(
                    "VoiceTurnEngine: follow-up listening (turn=%d, timeout=%.1fs)",
                    turn_id, self._followup_timeout_s,
                )

                # Record follow-up audio.  max_seconds = followup_timeout_s so
                # we return quickly if the user stays silent.
                self._recording_abort.clear()
                audio, stop_reason = self._record_followup(turn_id)
                if audio is None:
                    # Cancelled during recording
                    break

                if stop_reason == "pre_speech_timeout":
                    # No speech — conversation timed out naturally
                    logger.info(
                        "VoiceTurnEngine: follow-up timed out (turn=%d)", turn_id
                    )
                    self._emit({
                        "type": "conversation_ended",
                        "reason": "timeout",
                        "conversation_turns": self._conversation_turns,
                    })
                    break

                # Validate + STT on the follow-up audio
                validation = _validate_audio(audio)
                if not validation["ok"]:
                    logger.debug("Follow-up audio validation failed: %s", validation)
                    self._emit({
                        "type": "conversation_ended",
                        "reason": "audio_invalid",
                        "conversation_turns": self._conversation_turns,
                    })
                    break

                if not self._is_turn_live(turn_id) or self._cancel_event.is_set():
                    break

                # Gain-normalize and transcribe the follow-up
                audio, _gain_diag = _normalize_audio_gain(
                    audio, self._target_speech_rms
                )
                self._last_gain_diag = _gain_diag

                self._set_phase(TurnPhase.TRANSCRIBING)
                from openjarvis.autonomy.voice_conversation import (
                    evaluate_voice_transcript,
                    transcribe_command_result,
                )
                try:
                    stt_result = transcribe_command_result(audio, language=language)
                    text = (
                        stt_result.text.strip()
                        if hasattr(stt_result, "text")
                        else str(stt_result).strip()
                    )
                except Exception as exc:
                    logger.warning("Follow-up STT failed: %s", exc)
                    self._emit({
                        "type": "conversation_ended",
                        "reason": f"stt_error: {exc}",
                        "conversation_turns": self._conversation_turns,
                    })
                    break

                # Stop-phrase check (before transcript gate so stop always works)
                normalized = text.lower().strip().rstrip(".,!?")
                if normalized in _STOP_PHRASES:
                    logger.info(
                        "Follow-up stop phrase detected: %r (turn=%d)", text, turn_id
                    )
                    self._last_transcript = text
                    self._emit({"type": "transcript", "text": text})
                    self._emit({
                        "type": "conversation_ended",
                        "reason": "stop_phrase",
                        "stop_phrase": text,
                        "conversation_turns": self._conversation_turns,
                    })
                    break

                # Transcript gate
                is_stop = normalized in _STOP_PHRASES
                decision = evaluate_voice_transcript(
                    text, stt_result, wav_bytes=audio, is_stop_phrase=is_stop
                )
                if not decision.accepted:
                    logger.info(
                        "Follow-up transcript rejected (%s) — staying in follow-up",
                        decision.reason,
                    )
                    # Re-enter follow-up loop (don't break conversation for bad clip)
                    continue

                text = decision.text
                self._last_transcript = text
                self._emit({"type": "transcript", "text": text})
                logger.info("Follow-up transcript: %r (turn=%d)", text, turn_id)

                # Route + TTS for the follow-up utterance
                if not self._is_turn_live(turn_id) or self._cancel_event.is_set():
                    break
                response = self._stage_route(turn_id, text)
                if response is None:
                    return  # cancelled/error — already finalized

                tts_ok = self._stage_tts_nonfinalize(turn_id, response)
                if not tts_ok:
                    return  # cancelled — already finalized

                with self._lock:
                    self._conversation_turns += 1

                # Loop: go back to FOLLOW_UP_LISTENING

        finally:
            with self._lock:
                self._in_conversation = False

        # Return to idle cleanly
        if self._is_turn_live(turn_id) and not self._cancel_event.is_set():
            self._set_phase(TurnPhase.IDLE, reason="conversation_complete")
        elif self._cancel_event.is_set():
            self._set_phase(TurnPhase.CANCELLED)
        self._finalize(turn_id)

    # ------------------------------------------------------------------
    # Stage implementations
    # ------------------------------------------------------------------

    def _record_followup(self, turn_id: int) -> Tuple[Optional[bytes], str]:
        """Record a follow-up utterance with a short timeout.

        Returns (wav_bytes, stop_reason).  Returns (None, "cancelled") on cancel.
        stop_reason "pre_speech_timeout" means no speech in the window.
        """
        from openjarvis.autonomy.voice_conversation import record_command_audio_vad

        if not self._is_turn_live(turn_id) or self._cancel_event.is_set():
            return None, "cancelled"

        try:
            audio, stop_reason = record_command_audio_vad(
                min_seconds=_FOLLOWUP_MIN_RECORD_S,
                silence_stop_ms=self._silence_stop_ms,
                max_seconds=self._followup_timeout_s,
                sample_rate=16000,
                silence_rms_threshold=self._silence_rms_threshold,
                abort_event=self._recording_abort,
            )
        except Exception as exc:
            logger.warning("Follow-up recording failed: %s", exc)
            return None, "recording_error"

        if self._cancel_event.is_set() or not self._is_turn_live(turn_id):
            return None, "cancelled"

        return audio, stop_reason

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

        # Deepgram streaming: live partial transcripts + noise-robust endpoint.
        # Runs in daemon threads; degrades gracefully on any failure (the
        # energy-VAD endpoint + batch STT still complete the turn).
        _dg_partial: Optional[_DGStreamPartial] = None
        import os as _os
        _dg_key = _os.environ.get("DEEPGRAM_API_KEY", "")
        # Reset per-turn diagnostics + endpoint tracking.
        self._dg_endpoint_reason = None
        self._partial_sse_count = 0
        self._partial_diag = {
            "deepgram_partial_enabled": True,
            "deepgram_partial_key_present": bool(_dg_key),
            "deepgram_partial_connected": False,
            "deepgram_partial_audio_chunks_sent": 0,
            "deepgram_partial_events_received": 0,
            "deepgram_partial_last_error": None,
            "partial_transcript_sse_count": 0,
        }
        if _dg_key:
            _last_partial: Dict[str, str] = {}

            def _on_partial(text: str) -> None:
                if not self._is_turn_live(turn_id):
                    return
                if text != _last_partial.get("text"):
                    _last_partial["text"] = text
                    self._partial_sse_count += 1
                    self._emit({"type": "partial_transcript", "text": text})
                    logger.debug("DG partial: %r", text)

            def _on_endpoint(reason: str) -> None:
                # Deepgram detected end-of-utterance (word-gap / trailing
                # silence). This is far more noise-robust than energy VAD.
                if not self._is_turn_live(turn_id):
                    return
                if self._dg_endpoint_reason is None:
                    self._dg_endpoint_reason = reason
                    logger.info("Deepgram endpoint: %s — finalizing turn", reason)
                    self._recording_abort.set()

            _dg_partial = _DGStreamPartial(
                api_key=_dg_key,
                sample_rate=16000,
                on_partial=_on_partial,
                on_endpoint=_on_endpoint,
                endpointing_ms=int(_env_float("JARVIS_VOICE_DG_ENDPOINTING_MS", 700.0)),
            )
            if not _dg_partial.start():
                self._partial_diag["deepgram_partial_last_error"] = _dg_partial.last_error
                _dg_partial = None  # failed to connect — no partials this turn
            else:
                self._partial_diag["deepgram_partial_connected"] = True
        else:
            self._partial_diag["deepgram_partial_enabled"] = False
            logger.debug("DGStreamPartial skipped: DEEPGRAM_API_KEY not set")

        def _on_audio_chunk(pcm_bytes: bytes) -> None:
            if _dg_partial is not None:
                _dg_partial.send_chunk(pcm_bytes)

        # When Deepgram drives endpointing, the energy VAD becomes a backstop
        # (kept high so it only fires if Deepgram stalls). When Deepgram is
        # unavailable, the energy VAD is primary at its normal short window.
        _effective_silence_stop_ms = (
            max(self._silence_stop_ms, _DG_VAD_BACKSTOP_MS)
            if _dg_partial is not None
            else self._silence_stop_ms
        )

        rec_start = time.monotonic()
        try:
            audio, stop_reason = record_command_audio_vad(
                min_seconds=_DEFAULT_MIN_RECORD_SECONDS,
                silence_stop_ms=_effective_silence_stop_ms,
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
            if _dg_partial is not None:
                _dg_partial.stop()
            if self._is_turn_live(turn_id):
                self._last_error = f"recording_failed: {exc}"
                self._emit({"type": "error", "reason": self._last_error})
                self._set_phase(TurnPhase.ERROR, reason=self._last_error)
                self._finalize(turn_id)
            return None, False

        # Stop streaming partial transcripts (recording is done) + capture diag
        if _dg_partial is not None:
            self._partial_diag["deepgram_partial_audio_chunks_sent"] = _dg_partial.chunks_sent
            self._partial_diag["deepgram_partial_events_received"] = _dg_partial.events_received
            self._partial_diag["deepgram_partial_last_error"] = _dg_partial.last_error
            _dg_partial.stop()
        self._partial_diag["partial_transcript_sse_count"] = self._partial_sse_count

        # Resolve the true endpoint reason: Deepgram endpoint wins over the
        # generic "manually_ended" the VAD reports when its abort_event fires.
        _endpoint_reason = stop_reason
        if stop_reason == "manually_ended" and self._dg_endpoint_reason:
            _endpoint_reason = self._dg_endpoint_reason

        vad_diag = {
            "stop_reason": stop_reason,
            "endpoint_reason": _endpoint_reason,
            "endpoint_mode": last_chunk_diag.get("endpoint_mode", "absolute"),
            "duration_s": round(time.monotonic() - rec_start, 2),
            "silence_stop_ms": _effective_silence_stop_ms,
            "vad_silence_ms": last_chunk_diag.get("silence_elapsed_ms"),
            "vad_noise_floor": last_chunk_diag.get("noise_floor"),
            "vad_speech_detected": last_chunk_diag.get("speech_detected", False),
            "deepgram_endpoint": self._dg_endpoint_reason is not None,
            "background_noise_detected": last_chunk_diag.get("background_noise_detected", False),
            "speech_detected": last_chunk_diag.get("speech_detected", False),
            "speech_ema": last_chunk_diag.get("speech_ema"),
            "ambient_ema": last_chunk_diag.get("ambient_ema"),
            **calib_data,
        }
        self._last_partial_diag = dict(self._partial_diag)
        self._last_vad = vad_diag
        self._emit({"type": "vad", **vad_diag})

        # Check if cancelled during recording
        if self._cancel_event.is_set() or not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return None, False

        return audio, True

    def _stage_stt(self, turn_id: int, audio: bytes, language: str) -> Optional[str]:
        """Run STT with timeout. Returns transcript text or None on error/cancel.

        Applies gain normalization before STT to improve accuracy when the mic
        captures audio at low volume (normal speaking at normal laptop distance).
        The original RMS and scale factor are stored in self._last_gain_diag and
        emitted as part of the vad SSE event diagnostics.
        """
        self._set_phase(TurnPhase.TRANSCRIBING)

        # Gain-normalize the audio before STT.  The VAD already completed so
        # this does not affect endpointing — it only improves STT input quality.
        audio, gain_diag = _normalize_audio_gain(audio, self._target_speech_rms)
        self._last_gain_diag = gain_diag
        if gain_diag.get("too_quiet"):
            logger.warning(
                "Mic too quiet: original_rms=%.0f scale=%.2fx — "
                "try speaking louder or closer to the mic",
                gain_diag.get("original_rms", 0),
                gain_diag.get("scale", 1.0),
            )
            self._emit({
                "type": "mic_diag",
                "too_quiet": True,
                "original_rms": gain_diag.get("original_rms"),
                "scale": gain_diag.get("scale"),
                "hint": "Mic too quiet — try speaking louder or closer to the MacBook",
            })

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

    def _stage_tts_nonfinalize(self, turn_id: int, text: str) -> bool:
        """Speak response with timeout. Does NOT finalize the turn.

        Returns True when TTS completes normally (caller continues conversation).
        Returns False when cancelled (turn already finalized by this method).
        Non-fatal on TTS timeout — text was already displayed to user.
        """
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

        if cancel.is_set() or not self._is_turn_live(turn_id):
            self._set_phase(TurnPhase.CANCELLED)
            self._finalize(turn_id)
            return False

        return True


# ---------------------------------------------------------------------------
# Audio gain normalization
# ---------------------------------------------------------------------------


def _normalize_audio_gain(
    wav_bytes: bytes,
    target_rms: float = _TARGET_SPEECH_RMS,
    max_scale: float = _GAIN_NORM_MAX_SCALE,
) -> Tuple[bytes, Dict[str, Any]]:
    """Normalize WAV audio to target_rms if the recording is quieter.

    Applies uniform gain so Deepgram/Whisper STT receives audio at a consistent
    level regardless of mic distance or soft speaking volume.

    Clipping protection: scales are capped so no sample exceeds ±30000 (int16
    range ±32767), leaving ~3 dB headroom.  max_scale caps the multiplier so
    pure-noise clips aren't amplified into speech-like energy.

    Returns (normalized_wav_bytes, diag_dict).
    diag_dict keys:
      original_rms   — RMS before normalization
      target_rms     — target RMS value used
      scale          — scale factor applied (1.0 = no change)
      too_quiet      — True when scale > _GAIN_TOO_QUIET_SCALE (mic is very faint)
      clipped        — True when clipping protection reduced the scale
    """
    diag: Dict[str, Any] = {
        "original_rms": 0.0,
        "target_rms": target_rms,
        "scale": 1.0,
        "too_quiet": False,
        "clipped": False,
    }

    if not wav_bytes:
        return wav_bytes, diag

    try:
        import numpy as np
    except ImportError:
        # numpy not available — skip normalization, return original
        return wav_bytes, diag

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frame_rate = wf.getframerate()
            raw_frames = wf.readframes(wf.getnframes())
    except Exception:
        return wav_bytes, diag

    if not raw_frames or sample_width != 2:
        # Only normalize int16 (2-byte) PCM — skip other formats
        return wav_bytes, diag

    samples = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float64)
    if samples.size == 0:
        return wav_bytes, diag

    rms = float(np.sqrt(np.mean(samples ** 2)))
    diag["original_rms"] = round(rms, 1)

    if rms < 1.0:
        # Near-silent — no normalization (would just amplify noise)
        return wav_bytes, diag

    if rms >= target_rms:
        # Already loud enough — no normalization needed
        return wav_bytes, diag

    # Compute desired scale
    ideal_scale = target_rms / rms
    peak = float(np.max(np.abs(samples)))

    # Clipping protection: don't let any sample exceed ±30000
    max_safe_scale = 30000.0 / peak if peak > 0 else max_scale
    scale = min(ideal_scale, max_scale, max_safe_scale)
    clipped = scale < ideal_scale

    diag["scale"] = round(scale, 3)
    diag["too_quiet"] = scale > _GAIN_TOO_QUIET_SCALE
    diag["clipped"] = clipped

    scaled = np.clip(samples * scale, -32767, 32767).astype(np.int16)
    new_raw = scaled.tobytes()

    buf = io.BytesIO()
    try:
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(n_channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(frame_rate)
            wf.writeframes(new_raw)
    except Exception:
        return wav_bytes, diag

    logger.debug(
        "Gain norm: rms=%.0f → scale=%.2fx target=%.0f clipped=%s too_quiet=%s",
        rms, scale, target_rms, clipped, diag["too_quiet"],
    )
    return buf.getvalue(), diag


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
    "_normalize_audio_gain",
    "_STOP_PHRASES",
]
