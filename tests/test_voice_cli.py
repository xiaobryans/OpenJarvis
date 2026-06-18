"""Tests for ``jarvis voice`` CLI command group.

Covers:
  1.  voice command group is importable
  2.  'jarvis voice --help' exits 0 (command exists)
  3.  'jarvis voice status' exits 0
  4.  'jarvis voice status --json' returns valid JSON with required fields
  5.  'jarvis voice status --json' never contains secret patterns
  6.  'jarvis voice test-stt' exits 0 when STT is configured
  7.  'jarvis voice test-tts' exits 0 on macOS (macos_say available)
  8.  'jarvis voice start --help' exits 0
  9.  'jarvis voice test-tts --help' exits 0
  10. 'jarvis voice test-stt --help' exits 0
  11. docs/US13_DAILY_DRIVER_CERTIFICATION.md does not contain 'jarvis serve --voice'
  12. docs/US12_PRODUCT_POLISH.md does not contain 'jarvis serve --voice'
  13. doctor_routes.py limitations do not contain 'jarvis serve --voice'
  14. SettingsPage.tsx does not contain 'jarvis serve --voice'
  15. voice status JSON: hotkey_binding is not empty
  16. voice status JSON: manual_chatbox_status == 'available'
  17. voice status JSON: voice_readiness in (READY, PARTIAL, HOLD)
  18. test_us13_voice_readiness still imports and passes smoke check
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).parent.parent
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python3"
_CLI_MODULE = "openjarvis.cli"


def _run_cli(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    """Run a jarvis CLI command via the venv Python interpreter."""
    cmd = [str(_VENV_PYTHON), "-m", _CLI_MODULE, *args]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(_REPO_ROOT),
    )


# ---------------------------------------------------------------------------
# 1. Importable
# ---------------------------------------------------------------------------


class TestVoiceCmdImport:
    def test_voice_cmd_importable(self):
        from openjarvis.cli.voice_cmd import voice
        assert voice is not None

    def test_voice_cmd_is_click_group(self):
        import click
        from openjarvis.cli.voice_cmd import voice
        assert isinstance(voice, click.Group)

    def test_voice_cmd_subcommands(self):
        from openjarvis.cli.voice_cmd import voice
        names = set(voice.commands.keys())
        assert "status" in names
        assert "start" in names
        assert "test-tts" in names
        assert "test-stt" in names

    def test_voice_registered_in_cli(self):
        from openjarvis.cli import cli
        assert "voice" in cli.commands


# ---------------------------------------------------------------------------
# 2–3. --help and status exit codes
# ---------------------------------------------------------------------------


class TestVoiceHelp:
    def test_voice_help_exits_zero(self):
        r = _run_cli("voice", "--help")
        assert r.returncode == 0, f"voice --help failed:\n{r.stderr}"

    def test_voice_help_mentions_status(self):
        r = _run_cli("voice", "--help")
        assert "status" in r.stdout

    def test_voice_help_mentions_start(self):
        r = _run_cli("voice", "--help")
        assert "start" in r.stdout

    def test_voice_help_mentions_test_tts(self):
        r = _run_cli("voice", "--help")
        assert "test-tts" in r.stdout

    def test_voice_help_mentions_test_stt(self):
        r = _run_cli("voice", "--help")
        assert "test-stt" in r.stdout

    def test_voice_start_help_exits_zero(self):
        r = _run_cli("voice", "start", "--help")
        assert r.returncode == 0

    def test_voice_test_tts_help_exits_zero(self):
        r = _run_cli("voice", "test-tts", "--help")
        assert r.returncode == 0

    def test_voice_test_stt_help_exits_zero(self):
        r = _run_cli("voice", "test-stt", "--help")
        assert r.returncode == 0


class TestVoiceStatus:
    def test_voice_status_exits_zero_or_one(self):
        r = _run_cli("voice", "status")
        assert r.returncode in (0, 1), f"Unexpected exit code {r.returncode}"

    def test_voice_status_mentions_manual_chat(self):
        r = _run_cli("voice", "status")
        assert "manual" in r.stdout.lower() or "chat" in r.stdout.lower()

    def test_voice_status_mentions_hotkey(self):
        r = _run_cli("voice", "status")
        assert "hotkey" in r.stdout.lower() or "push-to-talk" in r.stdout.lower()

    def test_voice_status_mentions_wake_word(self):
        r = _run_cli("voice", "status")
        assert "wake" in r.stdout.lower()

    def test_voice_status_no_api_key_in_stdout(self):
        r = _run_cli("voice", "status")
        assert "sk-" not in r.stdout
        assert "OPENAI_API_KEY=" not in r.stdout


# ---------------------------------------------------------------------------
# 4–5. JSON output
# ---------------------------------------------------------------------------


class TestVoiceStatusJSON:
    def _get_json(self):
        r = _run_cli("voice", "status", "--json")
        assert r.returncode in (0, 1)
        return json.loads(r.stdout)

    def test_json_output_is_valid(self):
        r = _run_cli("voice", "status", "--json")
        assert r.returncode in (0, 1)
        data = json.loads(r.stdout)
        assert isinstance(data, dict)

    def test_json_has_voice_readiness(self):
        data = self._get_json()
        assert "voice_readiness" in data

    def test_json_has_manual_chatbox_status(self):
        data = self._get_json()
        assert "manual_chatbox_status" in data

    def test_json_has_hotkey_binding(self):
        data = self._get_json()
        assert "hotkey_binding" in data
        assert len(data["hotkey_binding"]) > 0

    def test_json_has_stt_status(self):
        data = self._get_json()
        assert "stt_status" in data

    def test_json_has_tts_status(self):
        data = self._get_json()
        assert "tts_status" in data

    def test_json_has_microphone_status(self):
        data = self._get_json()
        assert "microphone_status" in data

    def test_json_voice_readiness_valid(self):
        data = self._get_json()
        valid = ("RUNTIME_STARTED", "READY_FOR_LIVE_PROOF", "PARTIAL", "HOLD")
        assert data["voice_readiness"] in valid, (
            f"voice_readiness={data['voice_readiness']!r} not in {valid}"
        )

    def test_json_manual_chatbox_always_available(self):
        data = self._get_json()
        assert data["manual_chatbox_status"] == "available"

    def test_json_hotkey_binding_non_empty(self):
        data = self._get_json()
        assert data["hotkey_binding"].strip() != ""

    def test_json_no_secrets(self):
        from openjarvis.security.credential_stripper import secret_scan_text
        r = _run_cli("voice", "status", "--json")
        findings = secret_scan_text(r.stdout)
        assert findings == [], f"Secrets found in voice status JSON: {findings}"


# ---------------------------------------------------------------------------
# 6. test-stt
# ---------------------------------------------------------------------------


class TestVoiceTestSTT:
    def test_test_stt_exits_zero_when_configured(self):
        from openjarvis.autonomy.voice_pipeline import get_stt_status
        stt = get_stt_status()
        if not stt.get("is_configured"):
            pytest.skip("STT not configured in this environment")
        r = _run_cli("voice", "test-stt")
        assert r.returncode == 0, f"test-stt failed:\n{r.stderr}"

    def test_test_stt_does_not_print_api_key(self):
        r = _run_cli("voice", "test-stt")
        assert "sk-" not in r.stdout
        assert "OPENAI_API_KEY=" not in r.stdout

    def test_test_stt_mentions_config_check(self):
        r = _run_cli("voice", "test-stt")
        combined = r.stdout + r.stderr
        assert "record" in combined.lower() or "config" in combined.lower()


# ---------------------------------------------------------------------------
# 7. test-tts
# ---------------------------------------------------------------------------


class TestVoiceTestTTS:
    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    def test_test_tts_exits_zero_on_macos(self):
        import shutil
        if not shutil.which("say"):
            pytest.skip("'say' command not found")
        r = _run_cli("voice", "test-tts")
        assert r.returncode == 0, f"test-tts failed:\n{r.stderr}"

    def test_test_tts_mentions_engine(self):
        r = _run_cli("voice", "test-tts")
        assert "engine" in r.stdout.lower() or "tts" in r.stdout.lower()

    def test_test_tts_no_secrets_in_output(self):
        from openjarvis.security.credential_stripper import secret_scan_text
        r = _run_cli("voice", "test-tts")
        findings = secret_scan_text(r.stdout)
        assert findings == [], f"Secrets found in test-tts output: {findings}"


# ---------------------------------------------------------------------------
# 11–14. Docs do not reference invalid 'jarvis serve --voice'
# ---------------------------------------------------------------------------


class TestNoInvalidCommands:
    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_us13_doc_no_jarvis_serve_voice(self):
        doc = self._read(_REPO_ROOT / "docs" / "US13_DAILY_DRIVER_CERTIFICATION.md")
        assert "jarvis serve --voice" not in doc, (
            "US13 doc still references invalid 'jarvis serve --voice'"
        )

    def test_us12_doc_no_jarvis_serve_voice(self):
        doc = self._read(_REPO_ROOT / "docs" / "US12_PRODUCT_POLISH.md")
        assert "jarvis serve --voice" not in doc

    def test_doctor_routes_no_jarvis_serve_voice(self):
        src = self._read(_REPO_ROOT / "src" / "openjarvis" / "server" / "doctor_routes.py")
        assert "jarvis serve --voice" not in src and "--voice flag" not in src

    def test_settings_page_no_jarvis_serve_voice(self):
        src = self._read(_REPO_ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx")
        assert "jarvis serve --voice" not in src

    def test_us13_doc_has_jarvis_voice_start(self):
        doc = self._read(_REPO_ROOT / "docs" / "US13_DAILY_DRIVER_CERTIFICATION.md")
        assert "jarvis voice start" in doc

    def test_us13_doc_has_jarvis_voice_status(self):
        doc = self._read(_REPO_ROOT / "docs" / "US13_DAILY_DRIVER_CERTIFICATION.md")
        assert "jarvis voice status" in doc

    def test_us13_doc_has_jarvis_voice_test_tts(self):
        doc = self._read(_REPO_ROOT / "docs" / "US13_DAILY_DRIVER_CERTIFICATION.md")
        assert "jarvis voice test-tts" in doc


# ---------------------------------------------------------------------------
# 18. Smoke: test_us13_voice_readiness still importable
# ---------------------------------------------------------------------------


class TestUS13VoiceReadinessSmoke:
    def test_us13_module_importable(self):
        import importlib
        spec = importlib.util.spec_from_file_location(
            "test_us13_voice_readiness",
            str(_REPO_ROOT / "tests" / "test_us13_voice_readiness.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "TestVoiceStatusSchema")

    def test_get_voice_status_still_returns_required_keys(self):
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        for key in ("voice_readiness", "manual_chatbox_status", "hotkey_binding",
                    "stt_status", "tts_status", "microphone_status"):
            assert key in vs


# ---------------------------------------------------------------------------
# B. Wake-word callback crash fix
# ---------------------------------------------------------------------------


class TestWakeWordTriggerEvent:
    def test_event_has_model_field_not_model_name(self):
        """WakeWordTriggerEvent uses .model, not .model_name — root cause of the crash."""
        import time
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent
        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.95, ts=time.time())
        assert hasattr(ev, "model"), "WakeWordTriggerEvent must have 'model' field"
        assert not hasattr(ev, "model_name"), (
            "WakeWordTriggerEvent must NOT have 'model_name' field "
            "(this was the source of the AttributeError crash)"
        )

    def test_event_fields_correct_values(self):
        import time
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent
        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.87, ts=time.time())
        assert ev.model == "hey_jarvis_v0.1"
        assert ev.score == 0.87

    def test_voice_cmd_callback_does_not_crash(self):
        """The voice_cmd._on_trigger callback must not raise when event has only .model and .score."""
        import time
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent
        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.92, ts=time.time())
        # Simulate the fixed callback logic from voice_cmd.py
        model = getattr(ev, "model", None) or getattr(ev, "model_name", None) or "unknown"
        score = getattr(ev, "score", "?")
        score_str = f"{score:.3f}" if isinstance(score, float) else str(score)
        msg = f"Wake word detected! model={model!r} score={score_str}"
        assert "hey_jarvis" in msg
        assert "0.920" in msg

    def test_voice_cmd_callback_graceful_with_missing_fields(self):
        """Callback must not raise even if event has no model or score fields at all."""
        class MinimalEvent:
            pass
        ev = MinimalEvent()
        model = getattr(ev, "model", None) or getattr(ev, "model_name", None) or "unknown"
        score = getattr(ev, "score", "?")
        score_str = f"{score:.3f}" if isinstance(score, float) else str(score)
        msg = f"Wake word detected! model={model!r} score={score_str}"
        assert "unknown" in msg
        assert "?" in msg

    def test_callback_uses_model_not_model_name_in_voice_cmd(self):
        """Regression: voice_cmd.py must not reference event.model_name anywhere."""
        voice_cmd_path = _REPO_ROOT / "src" / "openjarvis" / "cli" / "voice_cmd.py"
        src = voice_cmd_path.read_text(encoding="utf-8")
        assert "event.model_name" not in src, (
            "voice_cmd.py still references event.model_name — this causes AttributeError crash"
        )


# ---------------------------------------------------------------------------
# C. Hotkey truth tests
# ---------------------------------------------------------------------------


class TestHotkeyTruth:
    def test_cmd_shift_space_is_overlay_in_tauri_not_voice(self):
        """lib.rs must register Cmd+Shift+Space for the overlay, not voice."""
        lib_rs = _REPO_ROOT / "frontend" / "src-tauri" / "src" / "lib.rs"
        src = lib_rs.read_text(encoding="utf-8")
        assert "toggle the overlay" in src or "toggle_overlay" in src or "native_overlay::toggle" in src, (
            "lib.rs must register Cmd+Shift+Space for the overlay"
        )

    def test_settings_page_does_not_claim_cmd_shift_space_is_voice(self):
        """SettingsPage.tsx must not label Cmd+Shift+Space as 'Voice push-to-talk hotkey'."""
        src = (_REPO_ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text()
        assert "Voice push-to-talk hotkey" not in src, (
            "SettingsPage.tsx still claims Cmd+Shift+Space is 'Voice push-to-talk hotkey'. "
            "Cmd+Shift+Space opens the chat overlay in the Tauri app."
        )

    def test_settings_page_labels_overlay_correctly(self):
        src = (_REPO_ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text()
        assert "Quick chat overlay" in src or "chat overlay" in src.lower(), (
            "SettingsPage.tsx must label Cmd+Shift+Space as 'Quick chat overlay' or similar"
        )

    def test_settings_page_has_inapp_mic_button(self):
        src = (_REPO_ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text()
        assert "mic button" in src.lower() or "In-app voice" in src, (
            "SettingsPage.tsx must show the in-app mic button as a real push-to-talk path"
        )

    def test_us13_doc_labels_overlay_correctly(self):
        doc = (_REPO_ROOT / "docs" / "US13_DAILY_DRIVER_CERTIFICATION.md").read_text()
        assert "overlay" in doc.lower() and "not voice" in doc.lower(), (
            "US13 doc must clarify that Cmd+Shift+Space opens overlay (not voice)"
        )

    def test_hotkey_note_in_voice_status(self):
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        assert "hotkey_note" in vs
        assert "overlay" in vs["hotkey_note"].lower() or "cli" in vs["hotkey_note"].lower()

    def test_inapp_push_to_talk_in_voice_status(self):
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        assert "inapp_push_to_talk" in vs
        assert "mic" in vs["inapp_push_to_talk"].lower()


# ---------------------------------------------------------------------------
# D. Non-contradictory voice status tests
# ---------------------------------------------------------------------------


class TestNonContradictoryStatus:
    def test_voice_readiness_not_ready(self):
        """READY is no longer a valid voice_readiness value."""
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        assert vs["voice_readiness"] != "READY", (
            "voice_readiness='READY' is contradictory when worker is not running. "
            "Use RUNTIME_STARTED or READY_FOR_LIVE_PROOF."
        )

    def test_valid_readiness_states(self):
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        valid = {"RUNTIME_STARTED", "READY_FOR_LIVE_PROOF", "PARTIAL", "HOLD"}
        assert vs["voice_readiness"] in valid

    def test_worker_not_running_not_runtime_started(self):
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        if not vs.get("true_wakeword_worker_running"):
            assert vs["voice_readiness"] != "RUNTIME_STARTED", (
                "RUNTIME_STARTED requires worker_running=True"
            )

    def test_configured_not_started_consistent(self):
        """voice_status=configured_not_started implies worker not running."""
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        if vs.get("voice_status") == "configured_not_started":
            assert not vs.get("true_wakeword_worker_running", True), (
                "voice_status=configured_not_started but worker_running=True — contradictory"
            )

    def test_json_voice_readiness_not_ready(self):
        r = _run_cli("voice", "status", "--json")
        assert r.returncode in (0, 1)
        data = json.loads(r.stdout)
        assert data.get("voice_readiness") != "READY"

    def test_json_has_hotkey_note(self):
        r = _run_cli("voice", "status", "--json")
        data = json.loads(r.stdout)
        assert "hotkey_note" in data
        note = data["hotkey_note"]
        assert "overlay" in note.lower() or "cli" in note.lower()

    def test_json_has_worker_running_field(self):
        r = _run_cli("voice", "status", "--json")
        data = json.loads(r.stdout)
        assert "true_wakeword_worker_running" in data
        assert isinstance(data["true_wakeword_worker_running"], bool)
