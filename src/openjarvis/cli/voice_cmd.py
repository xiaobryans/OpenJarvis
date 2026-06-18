"""``jarvis voice`` — Voice pipeline management and testing commands.

Subcommands:
  jarvis voice status       Print voice pipeline readiness (all input paths, no secrets).
  jarvis voice start        Start the wake-word listener (blocks; Ctrl+C to stop).
  jarvis voice test-tts     Run a quick TTS test using the configured engine.
  jarvis voice test-stt     Check STT configuration (does not record audio).

Governance:
  - No secrets printed or committed.
  - No live outbound sends.
  - No microphone access without explicit 'voice start'.
  - 'voice start' requires explicit user invocation.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict

import click


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_field(label: str, value: str, ok: bool | None = None) -> str:
    """Return a single status line. ok=None = neutral."""
    if ok is True:
        mark = "\033[32m✓\033[0m"
    elif ok is False:
        mark = "\033[33m!\033[0m"
    else:
        mark = " "
    return f"  {mark}  {label:<32} {value}"


def _voice_status_dict() -> Dict[str, Any]:
    """Return full voice status dict. All values are strings/bools — no secrets."""
    from openjarvis.autonomy.voice_pipeline import get_voice_status
    return get_voice_status()


def _redact_status(vs: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of the status dict with no secret fields."""
    safe_keys = {
        "voice_readiness", "voice_status", "readiness_reason", "summary",
        "manual_chatbox_status", "hotkey_status", "hotkey_binding", "hotkey_note",
        "inapp_push_to_talk", "mic_button_status",
        "true_wakeword_status", "true_wakeword_worker_available", "true_wakeword_worker_running",
        "stt_status", "tts_status", "microphone_status",
        "approval_pin_status", "push_to_talk_available", "wake_word_available",
        "fully_configured",
    }
    return {k: v for k, v in vs.items() if k in safe_keys}


# ---------------------------------------------------------------------------
# Command group
# ---------------------------------------------------------------------------


@click.group(help="Voice pipeline management: status, start, TTS test, STT test.")
def voice() -> None:
    pass


# ---------------------------------------------------------------------------
# jarvis voice status
# ---------------------------------------------------------------------------


@voice.command("status")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
def voice_status(as_json: bool) -> None:
    """Print voice pipeline readiness for all three input paths.

    Shows: manual chat, push-to-talk hotkey, wake-word backend, STT,
    TTS, microphone. No secrets in output.
    """
    try:
        vs = _voice_status_dict()
    except Exception as exc:
        click.echo(f"ERROR: could not retrieve voice status: {exc}", err=True)
        sys.exit(1)

    safe = _redact_status(vs)

    if as_json:
        click.echo(json.dumps(safe, indent=2))
        return

    readiness = safe.get("voice_readiness", "HOLD")
    color = (
        "\033[32m" if readiness in ("READY", "RUNTIME_STARTED")
        else "\033[33m" if readiness in ("PARTIAL", "READY_FOR_LIVE_PROOF")
        else "\033[31m"
    )
    reset = "\033[0m"

    click.echo()
    click.echo(f"  Voice pipeline readiness: {color}{readiness}{reset}")
    click.echo()
    click.echo("  ── Input paths ──────────────────────────────────────────────")

    # Manual chat
    click.echo(_fmt_field("Manual chat", "always available", ok=True))

    # In-app push-to-talk (mic button in InputArea)
    click.echo(_fmt_field(
        "In-app push-to-talk",
        "mic button in chat input  [available_in_ui — enable in Settings > Input & Voice]",
        ok=None,
    ))

    # CLI voice hotkey (pynput, only in CLI mode — Cmd+Shift+Space opens overlay in Tauri app)
    hotkey_binding = safe.get("hotkey_binding", "cmd+shift+space")
    hotkey_status = safe.get("hotkey_status", "available")
    hotkey_note = safe.get("hotkey_note", "")
    click.echo(_fmt_field(
        "CLI voice hotkey (daemon mode)",
        f"{hotkey_binding}  [{hotkey_status}]{' — ' + hotkey_note if hotkey_note else ''}",
        ok=hotkey_status in ("active", "available"),
    ))
    click.echo(_fmt_field(
        "  Note",
        "Cmd+Shift+Space in packaged Tauri app opens chat overlay (not voice)",
        ok=None,
    ))

    # Wake-word
    wake_status = safe.get("true_wakeword_status", "not_configured")
    wake_worker = safe.get("true_wakeword_worker_available", False)
    if wake_worker:
        click.echo(_fmt_field(
            "Wake-word (hey jarvis)",
            "worker available — not started (run: jarvis voice start)",
            ok=None,
        ))
    else:
        click.echo(_fmt_field(
            "Wake-word (hey jarvis)",
            f"not available [{wake_status}]",
            ok=False,
        ))

    click.echo()
    click.echo("  ── Voice subsystems ─────────────────────────────────────────")

    # STT
    stt = safe.get("stt_status", "not_configured")
    click.echo(_fmt_field("STT engine", stt, ok=(stt != "not_configured")))

    # TTS
    tts = safe.get("tts_status", "not_configured")
    click.echo(_fmt_field("TTS engine", tts, ok=(tts != "not_configured")))

    # Microphone
    mic = safe.get("microphone_status", "unknown")
    click.echo(_fmt_field("Microphone", mic, ok=(mic == "granted")))

    click.echo()
    click.echo("  ── Setup instructions ───────────────────────────────────────")
    if not wake_worker:
        click.echo("  Wake-word: set up isolated worker venv:")
        click.echo("    uv venv .wake_worker_venv --python 3.12")
        click.echo("    uv pip install --python .wake_worker_venv/bin/python openwakeword sounddevice")
    if stt == "not_configured":
        click.echo("  STT:  pip install faster-whisper   # local, free, no API key")
        click.echo("        OR set OPENAI_API_KEY / DEEPGRAM_API_KEY")
    if tts == "not_configured":
        click.echo("  TTS:  macOS 'say' command not found — check platform")
    click.echo()

    click.echo("  ── Server / port ────────────────────────────────────────────")
    click.echo("  If 'jarvis serve' fails with 'address already in use':")
    click.echo("    jarvis status          # check running daemon")
    click.echo("    jarvis stop            # stop it cleanly")
    click.echo("    lsof -ti:8000 | xargs kill -9   # force-kill if stuck")
    click.echo()

    if readiness == "HOLD":
        click.echo("  Voice runtime is HOLD. Run 'jarvis voice start' when worker is ready.")
        sys.exit(1)
    elif readiness == "READY_FOR_LIVE_PROOF":
        click.echo("  Voice pipeline configured. Run 'jarvis voice start' to prove live wake-word.")
    elif readiness == "RUNTIME_STARTED":
        click.echo("  Voice runtime is running.")


# ---------------------------------------------------------------------------
# jarvis voice start
# ---------------------------------------------------------------------------


@voice.command("start")
@click.option(
    "--auto-restart",
    is_flag=True,
    default=False,
    help="Automatically restart worker on crash (up to 5 times).",
)
@click.option(
    "--debug",
    "debug_mode",
    is_flag=True,
    default=False,
    help="Show worker output, model load, and raw per-frame scores (verbose).",
)
@click.option(
    "--threshold",
    type=float,
    default=None,
    help="Override wake-word detection threshold (default 0.3, range 0.1–1.0).",
)
def voice_start(auto_restart: bool, debug_mode: bool, threshold: float | None) -> None:
    """Start the wake-word listener.

    Requires .wake_worker_venv with openwakeword + sounddevice installed.
    Blocks until Ctrl+C. Prints trigger events to stdout.
    No secrets printed. Microphone is accessed by the worker subprocess.

    Run with --debug to see worker output, model keys, audio frame counts,
    and per-frame scores (useful when detection does not fire).
    """
    try:
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        from openjarvis.autonomy.voice_pipeline import get_voice_status
    except ImportError as exc:
        click.echo(f"ERROR: voice pipeline module not available: {exc}", err=True)
        sys.exit(1)

    bridge = WakeWordBridge()

    if not bridge.is_available():
        click.echo("ERROR: wake-word worker venv not found.", err=True)
        click.echo("", err=True)
        click.echo("Setup steps:", err=True)
        click.echo("  uv venv .wake_worker_venv --python 3.12", err=True)
        click.echo("  uv pip install --python .wake_worker_venv/bin/python openwakeword sounddevice", err=True)
        click.echo("", err=True)
        click.echo("Then retry: jarvis voice start", err=True)
        sys.exit(1)

    import os as _os
    import time

    # Set env overrides before starting bridge
    if threshold is not None:
        _os.environ["JARVIS_WAKEWORD_THRESHOLD"] = str(threshold)
    if debug_mode:
        _os.environ["JARVIS_WAKEWORD_DEBUG"] = "1"
        click.echo("  [debug] Socket path:   /tmp/jarvis_wakeword.sock")
        click.echo(f"  [debug] Threshold:     {threshold or 0.3}")

    # Check STT/TTS status (advisory only — voice start proceeds anyway)
    try:
        vs = get_voice_status()
        stt = vs.get("stt_status", "not_configured")
        tts = vs.get("tts_status", "not_configured")
        mic = vs.get("microphone_status", "unknown")
        if mic != "granted":
            click.echo(f"WARNING: microphone_status={mic!r}. You may need to grant mic permission in System Settings > Privacy & Security.", err=True)
        if stt == "not_configured":
            click.echo("WARNING: STT not configured — wake-word will detect but STT transcription will fail.", err=True)
            click.echo("  Fix: pip install faster-whisper  OR  set OPENAI_API_KEY", err=True)
        if tts == "not_configured":
            click.echo("WARNING: TTS not configured — responses will not be spoken.", err=True)
    except Exception:
        pass

    # Register callback to print trigger events
    def _on_trigger(event: Any) -> None:
        ts = time.strftime("%H:%M:%S")
        model = getattr(event, "model", None) or getattr(event, "model_name", None) or "unknown"
        score = getattr(event, "score", "?")
        score_str = f"{score:.3f}" if isinstance(score, float) else str(score)
        click.echo(f"  [{ts}] Wake word detected! model={model!r} score={score_str}")
        click.echo("  → Wake-word fired. STT transcription will activate if connected.")

    bridge.register_callback(_on_trigger)

    click.echo()
    click.echo("Starting wake-word listener...")
    result = bridge.start(auto_restart=auto_restart, debug=debug_mode)

    if not result.get("ok"):
        err_msg = result.get("error", "unknown error")
        click.echo(f"ERROR: {err_msg}", err=True)
        click.echo()
        click.echo("Diagnostics:", err=True)
        click.echo("  Socket path:  /tmp/jarvis_wakeword.sock", err=True)
        click.echo("  Worker venv:  .wake_worker_venv", err=True)
        click.echo("  Re-run with:  jarvis voice start --debug", err=True)
        click.echo("  Mic access:   System Settings > Privacy & Security > Microphone", err=True)
        sys.exit(1)

    pid = result.get("worker_pid", "?")
    socket_path = result.get("socket", "/tmp/jarvis_wakeword.sock")
    t_thresh = threshold or 0.3
    click.echo(f"  Wake-word listener running (worker pid={pid})")
    click.echo(f"  Socket: {socket_path}")
    click.echo(f"  Threshold: {t_thresh}")
    click.echo("  Phrases: 'hey jarvis'")
    if debug_mode:
        click.echo("  [debug] Worker output shown above prefixed with [worker]")
    else:
        click.echo("  Tip: run with --debug to see per-frame scores and worker output")
    click.echo("  Press Ctrl+C to stop.")
    click.echo()

    _ready_shown = [False]

    try:
        while True:
            time.sleep(0.5)
            s = bridge.status()
            if not _ready_shown[0] and s.get("worker_ready"):
                _ready_shown[0] = True
                mdl = s.get("true_wakeword_model", "unknown")
                thr = s.get("worker_threshold", t_thresh)
                click.echo(f"  Worker ready: model={mdl!r} threshold={thr} — say 'hey jarvis'")
            if not s.get("worker_running") and not auto_restart:
                click.echo("Worker stopped unexpectedly.", err=True)
                click.echo(f"  Last error: {s.get('error', 'none')}", err=True)
                click.echo("  Re-run with: jarvis voice start --debug", err=True)
                break
    except KeyboardInterrupt:
        click.echo("\nStopping wake-word listener...")
    finally:
        bridge.stop()
        s = bridge.status()
        click.echo(f"Voice listener stopped. Total detections: {s.get('trigger_count', 0)}")


# ---------------------------------------------------------------------------
# jarvis voice test-tts
# ---------------------------------------------------------------------------


@voice.command("test-tts")
@click.option(
    "--text",
    default="Jarvis is ready.",
    show_default=True,
    help="Text to speak.",
)
def voice_test_tts(text: str) -> None:
    """Run a TTS test using the configured engine.

    On macOS uses the built-in 'say' command. On other platforms requires
    OPENAI_API_KEY. Does not print secrets.
    """
    try:
        from openjarvis.autonomy.voice_pipeline import tts_test, get_tts_status
    except ImportError as exc:
        click.echo(f"ERROR: voice pipeline not available: {exc}", err=True)
        sys.exit(1)

    tts = get_tts_status()
    engine = tts.get("tts_status", "not_configured")
    click.echo(f"TTS engine: {engine}")

    if engine == "not_configured":
        blockers = tts.get("blockers") or tts.get("blocker") or []
        click.echo("TTS not configured.", err=True)
        if isinstance(blockers, list):
            for b in blockers:
                click.echo(f"  {b}", err=True)
        else:
            click.echo(f"  {blockers}", err=True)
        sys.exit(1)

    result = tts_test(text)
    if result.get("ok"):
        click.echo(f"TTS OK: engine={result['engine']!r}, text spoken.")
    else:
        blocker = result.get("blocker") or result.get("error") or "unknown"
        click.echo(f"TTS FAIL: {blocker}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# jarvis voice test-stt
# ---------------------------------------------------------------------------


@voice.command("test-stt")
def voice_test_stt() -> None:
    """Check STT configuration — does not record audio.

    Reports which STT engine is configured (faster-whisper, openai_whisper,
    deepgram, or not_configured). Does not print API keys.
    """
    try:
        from openjarvis.autonomy.voice_pipeline import stt_test, get_stt_status
    except ImportError as exc:
        click.echo(f"ERROR: voice pipeline not available: {exc}", err=True)
        sys.exit(1)

    stt = get_stt_status()
    engine = stt.get("stt_status", "not_configured")
    is_configured = stt.get("is_configured", False)
    requires_key = stt.get("requires_api_key", False)

    click.echo(f"STT engine:      {engine}")
    click.echo(f"Configured:      {is_configured}")
    if requires_key:
        key_var = stt.get("key_env_var", "unknown")
        click.echo(f"API key source:  {key_var} (set, not printed)")

    if not is_configured:
        blockers = stt.get("blockers") or stt.get("blocker") or []
        click.echo("STT not configured. Setup options:", err=True)
        if isinstance(blockers, list):
            for b in blockers:
                click.echo(f"  {b}", err=True)
        else:
            click.echo(f"  {blockers}", err=True)

        install_options = stt.get("install_options", [])
        if install_options:
            click.echo("Install options:", err=True)
            for opt in install_options:
                click.echo(f"  {opt}", err=True)
        sys.exit(1)

    result = stt_test()
    click.echo(f"Note: {result.get('note', 'config check only')}")
    click.echo("STT config check passed.")


__all__ = ["voice"]
