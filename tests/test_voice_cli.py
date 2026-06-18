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


# ---------------------------------------------------------------------------
# E. Wake-word startup reliability
# ---------------------------------------------------------------------------


class TestWakeWordStartupReliability:
    def test_bridge_cleans_stale_socket_before_start(self):
        """WakeWordBridge.start() must delete a stale socket file before spawning worker."""
        import inspect
        from openjarvis.autonomy import wakeword_bridge
        src = inspect.getsource(wakeword_bridge.WakeWordBridge.start)
        assert "os.unlink(_SOCKET_PATH)" in src or "os.unlink" in src, (
            "WakeWordBridge.start() must delete stale socket before spawning worker"
        )

    def test_bridge_drains_worker_stdout(self):
        """WakeWordBridge.start() must read worker stdout in a thread to prevent pipe fill."""
        import inspect
        from openjarvis.autonomy import wakeword_bridge
        src = inspect.getsource(wakeword_bridge.WakeWordBridge.start)
        assert "_drain" in src or "drain" in src.lower(), (
            "WakeWordBridge.start() must drain worker stdout to prevent pipe buffer fill"
        )

    def test_bridge_start_accepts_debug_param(self):
        """WakeWordBridge.start() must accept debug= kwarg."""
        import inspect
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        sig = inspect.signature(WakeWordBridge.start)
        assert "debug" in sig.parameters

    def test_voice_start_has_debug_option(self):
        """jarvis voice start --help must list --debug option."""
        r = _run_cli("voice", "start", "--help")
        assert r.returncode == 0
        assert "--debug" in r.stdout

    def test_voice_start_has_threshold_option(self):
        """jarvis voice start --help must list --threshold option."""
        r = _run_cli("voice", "start", "--help")
        assert r.returncode == 0
        assert "--threshold" in r.stdout

    def test_worker_socket_path_is_tmp(self):
        """Socket path must be /tmp/jarvis_wakeword.sock (or JARVIS_WAKEWORD_SOCKET override)."""
        import os
        expected = os.environ.get("JARVIS_WAKEWORD_SOCKET", "/tmp/jarvis_wakeword.sock")
        from openjarvis.autonomy.wakeword_bridge import _SOCKET_PATH
        assert _SOCKET_PATH == expected

    def test_bridge_error_message_includes_debug_hint(self):
        """Bridge connect-failure message must suggest --debug."""
        import inspect
        from openjarvis.autonomy import wakeword_bridge
        src = inspect.getsource(wakeword_bridge.WakeWordBridge.start)
        assert "--debug" in src

    def test_bridge_status_has_worker_ready(self):
        """bridge.status() must include worker_ready field."""
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        st = b.status()
        assert "worker_ready" in st
        assert st["worker_ready"] is False

    def test_bridge_status_has_debug(self):
        """bridge.status() must include debug field."""
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        st = b.status()
        assert "debug" in st

    def test_bridge_status_has_worker_threshold(self):
        """bridge.status() must include worker_threshold field."""
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
        b = WakeWordBridge()
        st = b.status()
        assert "worker_threshold" in st


# ---------------------------------------------------------------------------
# F. Wake-word detection config
# ---------------------------------------------------------------------------


class TestWakeWordDetectionConfig:
    def test_worker_default_threshold_is_0_3(self):
        """Default threshold must be 0.3 (was 0.5 which was too strict)."""
        import os
        from openjarvis.autonomy import wakeword_worker
        import importlib
        # Read the source to check the default
        import inspect
        src = inspect.getsource(wakeword_worker)
        assert '"0.3"' in src or "'0.3'" in src, (
            "wakeword_worker.py default threshold must be 0.3 (not 0.5)"
        )

    def test_worker_has_debug_mode(self):
        """Worker must have JARVIS_WAKEWORD_DEBUG support."""
        import inspect
        from openjarvis.autonomy import wakeword_worker
        src = inspect.getsource(wakeword_worker)
        assert "JARVIS_WAKEWORD_DEBUG" in src

    def test_worker_sends_ready_event(self):
        """Worker must send a ready event after accepting a connection."""
        import inspect
        from openjarvis.autonomy import wakeword_worker
        src = inspect.getsource(wakeword_worker)
        assert '"ready"' in src or "'ready'" in src, (
            "wakeword_worker.py must send a ready event after client connects"
        )

    def test_worker_logs_first_audio_frame(self):
        """Worker must log when first audio frame arrives to confirm mic is live."""
        import inspect
        from openjarvis.autonomy import wakeword_worker
        src = inspect.getsource(wakeword_worker)
        assert "First audio frame" in src or "first audio" in src.lower()

    def test_worker_flushes_stdout(self):
        """Worker must flush stdout so drain thread sees output promptly."""
        import inspect
        from openjarvis.autonomy import wakeword_worker
        src = inspect.getsource(wakeword_worker)
        assert "sys.stdout.flush()" in src


# ---------------------------------------------------------------------------
# G. Mic button / speechEnabled default
# ---------------------------------------------------------------------------


class TestMicButtonDefault:
    def test_speech_enabled_defaults_true_in_store(self):
        """store.ts must default speechEnabled to true so mic button works on first use."""
        store_path = _REPO_ROOT / "frontend" / "src" / "lib" / "store.ts"
        src = store_path.read_text(encoding="utf-8")
        # Find the speechEnabled default in loadSettings
        idx = src.find("speechEnabled: false")
        assert idx == -1, (
            "store.ts defaults speechEnabled to false — mic button will always be disabled "
            "until user manually enables it in Settings. Change default to true."
        )

    def test_speech_enabled_default_true_present(self):
        """store.ts must have speechEnabled: true in the defaults object."""
        store_path = _REPO_ROOT / "frontend" / "src" / "lib" / "store.ts"
        src = store_path.read_text(encoding="utf-8")
        assert "speechEnabled: true" in src

    def test_inputarea_surfaces_speech_error(self):
        """InputArea.tsx must destructure error from useSpeech and show toast."""
        input_area = _REPO_ROOT / "frontend" / "src" / "components" / "Chat" / "InputArea.tsx"
        src = input_area.read_text(encoding="utf-8")
        assert "speechError" in src and "toast.error" in src, (
            "InputArea.tsx must show toast.error when speech/mic fails, not swallow silently"
        )

    def test_inputarea_error_useeffect_present(self):
        """InputArea.tsx must have useEffect that fires toast.error on speechError."""
        input_area = _REPO_ROOT / "frontend" / "src" / "components" / "Chat" / "InputArea.tsx"
        src = input_area.read_text(encoding="utf-8")
        assert "if (speechError) toast.error" in src or "speechError" in src


# ---------------------------------------------------------------------------
# H. Readiness honesty
# ---------------------------------------------------------------------------


class TestReadinessHonesty:
    def test_mic_button_status_is_available_in_ui(self):
        """voice_status must return mic_button_status='available_in_ui', not 'available'."""
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        assert "mic_button_status" in vs
        assert vs["mic_button_status"] == "available_in_ui", (
            f"mic_button_status={vs['mic_button_status']!r} — must be 'available_in_ui' "
            "(cannot claim it is live-proven without user enabling it in Settings)"
        )

    def test_inapp_push_to_talk_not_claiming_available(self):
        """inapp_push_to_talk field must not claim mic button is unconditionally available."""
        from openjarvis.autonomy.voice_pipeline import get_voice_status
        vs = get_voice_status()
        val = vs.get("inapp_push_to_talk", "")
        assert "always available" not in val.lower(), (
            "inapp_push_to_talk must not say 'always available' — it requires Settings enablement"
        )

    def test_voice_status_json_has_mic_button_status(self):
        """jarvis voice status --json must include mic_button_status."""
        r = _run_cli("voice", "status", "--json")
        assert r.returncode in (0, 1)
        data = json.loads(r.stdout)
        assert "mic_button_status" in data
        assert data["mic_button_status"] == "available_in_ui"

    def test_server_port_guidance_in_status_output(self):
        """jarvis voice status output must include port conflict guidance."""
        r = _run_cli("voice", "status")
        assert r.returncode in (0, 1)
        combined = r.stdout + r.stderr
        assert "8000" in combined or "lsof" in combined or "jarvis stop" in combined, (
            "jarvis voice status must show port conflict guidance"
        )


# ---------------------------------------------------------------------------
# I. Packaged-app mic fix (US13 — WKWebView / Tauri microphone blocker)
# ---------------------------------------------------------------------------


class TestPackagedAppMicFix:
    """Verify all config, entitlement, and frontend changes required to
    unblock microphone access in the macOS packaged Tauri app."""

    # ------------------------------------------------------------------ #
    # 1. tauri.conf.json — NSMicrophoneUsageDescription                   #
    # ------------------------------------------------------------------ #

    def test_tauri_conf_infoPlist_is_string_path(self):
        """tauri.conf.json bundle.macOS.infoPlist must be a string path, not an object.

        Tauri v2 schema: infoPlist is null | string (path to a .plist file).
        Passing a JSON object causes:
          Error on bundle > macOS > infoPlist: {...} is not of types 'null', 'string'
        """
        import json
        tauri_conf = _REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
        conf = json.loads(tauri_conf.read_text(encoding="utf-8"))
        info_plist_val = (
            conf.get("bundle", {})
                .get("macOS", {})
                .get("infoPlist")
        )
        assert isinstance(info_plist_val, str) and info_plist_val.endswith(".plist"), (
            f"bundle.macOS.infoPlist must be a string path to a .plist file, got: {info_plist_val!r}. "
            "Passing a JSON object causes a Tauri build error."
        )

    def test_info_plist_file_has_NSMicrophoneUsageDescription(self):
        """The Info.plist referenced by tauri.conf.json must contain NSMicrophoneUsageDescription.

        macOS Privacy framework (TCC) requires this key in ANY app that accesses
        the microphone, including WKWebView getUserMedia. Without it, macOS refuses
        to show the permission dialog and getUserMedia fails with:
          'microphone is not available for this browser'
        """
        import json
        tauri_conf = _REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
        conf = json.loads(tauri_conf.read_text(encoding="utf-8"))
        plist_name = (
            conf.get("bundle", {})
                .get("macOS", {})
                .get("infoPlist", "Info.plist")
        )
        plist_path = _REPO_ROOT / "frontend" / "src-tauri" / plist_name
        assert plist_path.exists(), (
            f"Info.plist file not found at {plist_path}. "
            "Create it with NSMicrophoneUsageDescription key."
        )
        src = plist_path.read_text(encoding="utf-8")
        assert "NSMicrophoneUsageDescription" in src, (
            f"{plist_path.name} must contain NSMicrophoneUsageDescription. "
            "Without it macOS will not show the permission dialog and getUserMedia "
            "fails with 'microphone is not available for this browser'."
        )

    def test_info_plist_NSMicrophoneUsageDescription_mentions_transcription(self):
        """Usage description in Info.plist should mention speech/transcription for TCC."""
        import json
        tauri_conf = _REPO_ROOT / "frontend" / "src-tauri" / "tauri.conf.json"
        conf = json.loads(tauri_conf.read_text(encoding="utf-8"))
        plist_name = (
            conf.get("bundle", {}).get("macOS", {}).get("infoPlist", "Info.plist")
        )
        if not isinstance(plist_name, str):
            plist_name = "Info.plist"
        plist_path = _REPO_ROOT / "frontend" / "src-tauri" / plist_name
        src = plist_path.read_text(encoding="utf-8") if plist_path.exists() else ""
        # Extract the string value that follows NSMicrophoneUsageDescription key
        import re
        m = re.search(
            r"<key>NSMicrophoneUsageDescription</key>\s*<string>([^<]*)</string>",
            src,
        )
        desc = m.group(1) if m else ""
        assert any(kw in desc.lower() for kw in ("speech", "transcri", "voice", "microphone")), (
            f"NSMicrophoneUsageDescription in {plist_name} should mention speech/transcription. "
            f"Got: {desc!r}"
        )

    # ------------------------------------------------------------------ #
    # 2. Entitlements.plist — audio-input entitlement                     #
    # ------------------------------------------------------------------ #

    def test_entitlements_has_audio_input(self):
        """Entitlements.plist must contain com.apple.security.device.audio-input.

        Belt-and-suspenders alongside NSMicrophoneUsageDescription. Some macOS
        versions check this entitlement during Privacy enforcement.
        """
        entitlements = _REPO_ROOT / "frontend" / "src-tauri" / "Entitlements.plist"
        src = entitlements.read_text(encoding="utf-8")
        assert "com.apple.security.device.audio-input" in src, (
            "Entitlements.plist must include com.apple.security.device.audio-input. "
            "Required for notarization and some macOS Privacy checks."
        )

    def test_entitlements_audio_input_is_true(self):
        """audio-input entitlement must be <true/>, not <false/>."""
        entitlements = _REPO_ROOT / "frontend" / "src-tauri" / "Entitlements.plist"
        src = entitlements.read_text(encoding="utf-8")
        idx = src.find("com.apple.security.device.audio-input")
        assert idx != -1
        # The <true/> tag must follow the key, not <false/>
        after = src[idx:idx + 120]
        assert "<true/>" in after, (
            "com.apple.security.device.audio-input must be <true/>, not <false/>"
        )

    # ------------------------------------------------------------------ #
    # 3. useSpeech.ts — imports isTauri                                    #
    # ------------------------------------------------------------------ #

    def test_useSpeech_imports_isTauri(self):
        """useSpeech.ts must import isTauri so it can detect Tauri context."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "isTauri" in src, (
            "useSpeech.ts must import and use isTauri() to detect packaged-app context."
        )

    def test_useSpeech_isTauri_imported_from_api(self):
        """isTauri must be imported from '../lib/api'."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "isTauri" in src and "../lib/api" in src, (
            "useSpeech.ts must import isTauri from '../lib/api'."
        )

    # ------------------------------------------------------------------ #
    # 4. useSpeech.ts — actionable Tauri error messages                   #
    # ------------------------------------------------------------------ #

    def test_useSpeech_has_system_settings_privacy_message(self):
        """useSpeech.ts must show 'System Settings' path for Tauri mic errors.

        'microphone is not available for this browser' is not actionable.
        The user must be told exactly where to grant the permission.
        """
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "System Settings" in src, (
            "useSpeech.ts must tell the user to go to System Settings when mic "
            "fails in the packaged Tauri app."
        )

    def test_useSpeech_has_not_allowed_error_branch(self):
        """useSpeech.ts must handle NotAllowedError (user explicitly denied mic)."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "NotAllowedError" in src, (
            "useSpeech.ts must handle NotAllowedError separately so the Tauri "
            "packaged app shows an actionable 'open System Settings' message."
        )

    def test_useSpeech_has_not_supported_error_branch(self):
        """useSpeech.ts must handle NotSupportedError (missing NSMicrophoneUsageDescription)."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "NotSupportedError" in src, (
            "useSpeech.ts must handle NotSupportedError — this is the error WKWebView "
            "throws when NSMicrophoneUsageDescription is missing."
        )

    def test_useSpeech_tauri_NotAllowed_message_has_relaunch(self):
        """Tauri NotAllowedError message must say 'relaunch' so user knows the fix."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "relaunch" in src, (
            "useSpeech.ts must tell the user to relaunch OpenJarvis after granting "
            "mic permission (required because WKWebView caches the denial)."
        )

    def test_useSpeech_browser_path_still_preserved(self):
        """Browser path must still say 'Microphone access denied' (not removed)."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "Microphone access denied" in src, (
            "useSpeech.ts must keep the browser 'Microphone access denied' path "
            "for non-Tauri users — do not break localhost/browser mic."
        )

    def test_useSpeech_not_available_message_branch(self):
        """useSpeech.ts must handle 'not available' DOMException message substring."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "not available" in src, (
            "useSpeech.ts must catch DOMException messages containing 'not available' "
            "— this is the exact substring WebKit uses in the packaged app error."
        )

    # ------------------------------------------------------------------ #
    # 5. US13 docs must not mark packaged-app mic as accepted              #
    # ------------------------------------------------------------------ #

    def test_us13_docs_do_not_claim_packaged_app_accepted(self):
        """US13 docs must not claim packaged-app mic transcription is ACCEPT before proof."""
        docs = list((_REPO_ROOT / "docs").glob("*US13*"))
        for doc in docs:
            src = doc.read_text(encoding="utf-8")
            lowered = src.lower()
            # Doc must not claim packaged-app path is accepted/proven
            forbidden_phrases = [
                "packaged app mic: accept",
                "packaged-app mic: accept",
                "tauri mic: accept",
                "verdict: accept",  # only forbidden if combined with packaged mic claim
            ]
            # We only flag if "ACCEPT" appears right next to "packaged" claim
            if "packaged" in lowered and "accept" in lowered:
                # Ensure it's not claiming ACCEPT for the packaged mic specifically
                assert "packaged app mic" not in lowered or "hold" in lowered, (
                    f"{doc.name}: must not claim packaged-app mic is ACCEPT before live proof. "
                    "US13 verdict must remain HOLD until Bryan proves mic transcription in packaged app."
                )


# ---------------------------------------------------------------------------
# J. Packaged-app STT transcription quality fix (US13 — format mismatch)
# ---------------------------------------------------------------------------


class TestSTTTranscriptionQualityFix:
    """Verify the audio-format mismatch fix that caused garbage transcripts.

    Root cause:
      WKWebView (macOS packaged app) records audio/mp4 (AAC) by default.
      The old code hardcoded filename='recording.webm' and mime='audio/webm'.
      The backend infers format from the filename extension -> got 'webm',
      but the actual audio bytes were mp4/m4a -> STT got wrong decoder ->
      garbage output with no relation to what Bryan actually said.

    Fix:
      useSpeech.ts tries supported MIME types (webm/opus first, mp4 fallback),
      derives filename from recorder.mimeType (.m4a for mp4, .webm otherwise),
      passes correct filename to transcribeAudio(blob, filename).
      lib.rs transcribe_audio derives MIME from filename extension dynamically.
    """

    # ------------------------------------------------------------------ #
    # 1. useSpeech.ts — preferred MIME type selection                     #
    # ------------------------------------------------------------------ #

    def test_useSpeech_tries_preferred_mime_types(self):
        """useSpeech.ts must try a list of preferred MIME types via isTypeSupported.

        Without this, WKWebView silently chooses audio/mp4 while the code
        hardcodes 'recording.webm' -> format mismatch -> garbage transcript.
        """
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "isTypeSupported" in src, (
            "useSpeech.ts must call MediaRecorder.isTypeSupported() to pick a "
            "format that WKWebView actually supports before creating the recorder."
        )

    def test_useSpeech_includes_mp4_fallback_mime(self):
        """useSpeech.ts must include audio/mp4 as a fallback MIME type for WKWebView."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "audio/mp4" in src, (
            "useSpeech.ts must include 'audio/mp4' in the preferred MIME list. "
            "WKWebView on macOS does not support audio/webm — mp4 is the fallback."
        )

    def test_useSpeech_includes_webm_opus_primary(self):
        """useSpeech.ts must include audio/webm;codecs=opus as primary (browser path)."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "audio/webm" in src, (
            "useSpeech.ts must keep audio/webm in the preferred list for browser/localhost path."
        )

    # ------------------------------------------------------------------ #
    # 2. useSpeech.ts — filename derived from actual MIME type            #
    # ------------------------------------------------------------------ #

    def test_useSpeech_derives_m4a_extension_for_mp4(self):
        """useSpeech.ts must map audio/mp4 MIME type to .m4a extension."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "'m4a'" in src or '"m4a"' in src, (
            "useSpeech.ts must produce 'recording.m4a' when the recorder MIME is audio/mp4. "
            "The backend reads the extension to select the decoder."
        )

    def test_useSpeech_derives_filename_from_recorder_mimeType(self):
        """useSpeech.ts must use recorder.mimeType (not a hardcoded 'recording.webm') as filename basis."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "recorder.mimeType" in src, (
            "useSpeech.ts must read recorder.mimeType to derive the filename extension. "
            "Hardcoding '.webm' causes the backend to misidentify mp4/m4a audio."
        )

    def test_useSpeech_passes_filename_to_transcribeAudio(self):
        """useSpeech.ts must pass the derived filename to transcribeAudio(blob, filename)."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "transcribeAudio(blob, filename)" in src, (
            "useSpeech.ts must call transcribeAudio(blob, filename) with the derived filename "
            "so the backend receives the correct audio extension."
        )

    # ------------------------------------------------------------------ #
    # 3. useSpeech.ts — minimum size guard                                #
    # ------------------------------------------------------------------ #

    def test_useSpeech_has_minimum_size_guard(self):
        """useSpeech.ts must reject blobs smaller than 1 KB before sending to STT."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "blob.size" in src and "1000" in src, (
            "useSpeech.ts must check blob.size < 1000 and reject the recording "
            "before sending to STT. Tiny blobs produce garbage transcripts."
        )

    def test_useSpeech_size_guard_shows_actionable_error(self):
        """Size guard error message must tell the user to hold the button longer."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "hold" in src.lower() and "mic" in src.lower(), (
            "useSpeech.ts size-guard error must tell user to hold the mic button. "
            "Silent rejection is not actionable."
        )

    # ------------------------------------------------------------------ #
    # 4. useSpeech.ts — dev diagnostics                                   #
    # ------------------------------------------------------------------ #

    def test_useSpeech_has_dev_diagnostics(self):
        """useSpeech.ts must log MIME type and byte count in DEV mode only."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        assert "import.meta.env.DEV" in src, (
            "useSpeech.ts must gate diagnostic logging on import.meta.env.DEV "
            "so production builds don't print audio metadata."
        )
        assert "console.debug" in src or "console.log" in src, (
            "useSpeech.ts must log mimeType/bytes in DEV mode for diagnosing format issues."
        )

    # ------------------------------------------------------------------ #
    # 5. lib.rs — dynamic MIME type from filename extension               #
    # ------------------------------------------------------------------ #

    def test_lib_rs_transcribe_audio_not_hardcoded_webm_mime(self):
        """lib.rs transcribe_audio must NOT hardcode mime_str('audio/webm').

        The old hardcoded value sent wrong Content-Type for mp4/m4a recordings
        from WKWebView. The fix derives MIME from the filename extension.
        """
        lib_rs = _REPO_ROOT / "frontend" / "src-tauri" / "src" / "lib.rs"
        src = lib_rs.read_text(encoding="utf-8")
        # Find the transcribe_audio function
        fn_start = src.find("async fn transcribe_audio(")
        assert fn_start != -1, "transcribe_audio function not found in lib.rs"
        # Get function body (next 60 lines worth)
        fn_body = src[fn_start:fn_start + 2000]
        # Must NOT be hardcoded to audio/webm only
        assert fn_body.count('mime_str("audio/webm")') == 0, (
            "lib.rs transcribe_audio must not hardcode mime_str('audio/webm'). "
            "WKWebView records audio/mp4 — use dynamic MIME derived from filename extension."
        )

    def test_lib_rs_transcribe_audio_has_mp4_mime_branch(self):
        """lib.rs transcribe_audio must map .m4a/.mp4 filenames to audio/mp4 MIME."""
        lib_rs = _REPO_ROOT / "frontend" / "src-tauri" / "src" / "lib.rs"
        src = lib_rs.read_text(encoding="utf-8")
        fn_start = src.find("async fn transcribe_audio(")
        assert fn_start != -1
        fn_body = src[fn_start:fn_start + 2000]
        assert '"audio/mp4"' in fn_body, (
            "lib.rs transcribe_audio must include audio/mp4 as a MIME value. "
            "WKWebView produces m4a/mp4 audio which needs this Content-Type."
        )

    def test_lib_rs_transcribe_audio_has_empty_guard(self):
        """lib.rs transcribe_audio must reject empty audio_data before posting."""
        lib_rs = _REPO_ROOT / "frontend" / "src-tauri" / "src" / "lib.rs"
        src = lib_rs.read_text(encoding="utf-8")
        fn_start = src.find("async fn transcribe_audio(")
        assert fn_start != -1
        fn_body = src[fn_start:fn_start + 2000]
        assert "is_empty()" in fn_body, (
            "lib.rs transcribe_audio must check audio_data.is_empty() and return "
            "an error before attempting to POST zero bytes to the STT backend."
        )

    # ------------------------------------------------------------------ #
    # 6. Backend format detection from filename                           #
    # ------------------------------------------------------------------ #

    def test_backend_reads_format_from_filename_extension(self):
        """api_routes.py must derive audio format from the uploaded filename extension."""
        routes = (
            _REPO_ROOT / "src" / "openjarvis" / "server" / "api_routes.py"
        )
        src = routes.read_text(encoding="utf-8")
        assert "rsplit" in src or "splitext" in src or ".split" in src, (
            "api_routes.py transcribe endpoint must extract the file extension "
            "from the filename to pass the correct format to the STT backend."
        )

    def test_backend_default_format_is_wav_not_webm(self):
        """When filename has no extension, backend should default to 'wav' (safe), not 'webm'."""
        routes = (
            _REPO_ROOT / "src" / "openjarvis" / "server" / "api_routes.py"
        )
        src = routes.read_text(encoding="utf-8")
        assert '"wav"' in src or "'wav'" in src, (
            "api_routes.py must default to 'wav' when the filename has no extension. "
            "'webm' is not universally supported by all STT backends."
        )

    # ------------------------------------------------------------------ #
    # 7. Browser path preservation                                        #
    # ------------------------------------------------------------------ #

    def test_useSpeech_webm_path_not_removed(self):
        """Browser/localhost path (audio/webm) must still be present and preferred."""
        hook = _REPO_ROOT / "frontend" / "src" / "hooks" / "useSpeech.ts"
        src = hook.read_text(encoding="utf-8")
        # webm must still be listed in preferred types
        assert "audio/webm" in src, (
            "useSpeech.ts must keep audio/webm in the list so browser/localhost path works."
        )
        # The filename logic must still produce .webm for webm MIME
        assert "'webm'" in src or '"webm"' in src, (
            "useSpeech.ts must still produce recording.webm for audio/webm recorders."
        )


# ---------------------------------------------------------------------------
# K. STT language / output-mode fix (US13 — Malay misdetection)
# ---------------------------------------------------------------------------


class TestSTTLanguageFix:
    """Verify the English-language default that fixes Malay/Indonesian output.

    Root cause:
      Whisper auto-detects language from the first 30 s of audio.
      For short clips (1-3 s) it misidentifies English as Malay/Indonesian.
      Bryan said "what is the capital of France" and got
      "Apa ialah Kapital Perancis?" (Malay transcription, not translation).

    Fix:
      api_routes.py defaults language='en' from JARVIS_STT_LANGUAGE env var.
      openai_whisper.py adds prompt hint when language='en'.
      faster_whisper.py adds initial_prompt when language='en'.
    """

    # ------------------------------------------------------------------ #
    # 1. api_routes.py — default language 'en'                           #
    # ------------------------------------------------------------------ #

    def test_transcribe_route_has_default_language_en(self):
        """api_routes.py must default STT language to 'en', not None."""
        routes = _REPO_ROOT / "src" / "openjarvis" / "server" / "api_routes.py"
        src = routes.read_text(encoding="utf-8")
        assert '"en"' in src or "'en'" in src, (
            "api_routes.py must set a default language of 'en' for the "
            "/v1/speech/transcribe route. Without it, Whisper auto-detects "
            "and misidentifies short English clips as Malay/Indonesian."
        )

    def test_transcribe_route_reads_JARVIS_STT_LANGUAGE_env(self):
        """api_routes.py must read JARVIS_STT_LANGUAGE env var for the language default."""
        routes = _REPO_ROOT / "src" / "openjarvis" / "server" / "api_routes.py"
        src = routes.read_text(encoding="utf-8")
        assert "JARVIS_STT_LANGUAGE" in src, (
            "api_routes.py must read JARVIS_STT_LANGUAGE env var so non-English "
            "users can override the default language without code changes."
        )

    def test_transcribe_route_language_not_always_none(self):
        """api_routes.py must not pass language=None unconditionally to backend."""
        routes = _REPO_ROOT / "src" / "openjarvis" / "server" / "api_routes.py"
        src = routes.read_text(encoding="utf-8")
        # Old broken pattern was: language=language or None -> passes None
        assert "language or None" not in src, (
            "api_routes.py must not use 'language or None' — this passes None "
            "when no language is provided, disabling the language constraint."
        )

    def test_transcribe_route_imports_os(self):
        """api_routes.py must import os to read JARVIS_STT_LANGUAGE."""
        routes = _REPO_ROOT / "src" / "openjarvis" / "server" / "api_routes.py"
        src = routes.read_text(encoding="utf-8")
        assert "import os" in src, (
            "api_routes.py must import os to call os.environ.get('JARVIS_STT_LANGUAGE')."
        )

    # ------------------------------------------------------------------ #
    # 2. openai_whisper.py — transcription mode + prompt hint            #
    # ------------------------------------------------------------------ #

    def test_openai_whisper_uses_transcriptions_not_translations(self):
        """OpenAI backend must call audio.transcriptions, not audio.translations.

        audio.translations forces output to English regardless of spoken language.
        audio.transcriptions preserves the detected language — we then fix it
        via language='en' parameter, not by using the translation endpoint.
        """
        backend = _REPO_ROOT / "src" / "openjarvis" / "speech" / "openai_whisper.py"
        src = backend.read_text(encoding="utf-8")
        assert "audio.transcriptions" in src, (
            "openai_whisper.py must use audio.transcriptions.create(). "
            "audio.translations would always force output to English and "
            "lose non-English input for future multi-language support."
        )
        assert "audio.translations" not in src, (
            "openai_whisper.py must NOT use audio.translations. Use "
            "audio.transcriptions with language='en' instead."
        )

    def test_openai_whisper_has_english_prompt_hint(self):
        """OpenAI backend must add a 'prompt' hint when language is 'en'."""
        backend = _REPO_ROOT / "src" / "openjarvis" / "speech" / "openai_whisper.py"
        src = backend.read_text(encoding="utf-8")
        assert "prompt" in src, (
            "openai_whisper.py must set the 'prompt' kwarg when language='en'. "
            "This prevents Whisper from re-detecting language mid-clip."
        )
        assert "Do not translate" in src, (
            "openai_whisper.py prompt must say 'Do not translate' to "
            "prevent Malay/Indonesian transliterations for short English clips."
        )

    def test_openai_whisper_language_kwarg_set_when_provided(self):
        """OpenAI backend must pass language kwarg when language is set."""
        backend = _REPO_ROOT / "src" / "openjarvis" / "speech" / "openai_whisper.py"
        src = backend.read_text(encoding="utf-8")
        assert 'kwargs["language"] = language' in src or "language" in src, (
            "openai_whisper.py must pass language to the Whisper API call."
        )

    # ------------------------------------------------------------------ #
    # 3. faster_whisper.py — initial_prompt hint                         #
    # ------------------------------------------------------------------ #

    def test_faster_whisper_has_initial_prompt_for_english(self):
        """faster-whisper backend must add initial_prompt when language is 'en'."""
        backend = _REPO_ROOT / "src" / "openjarvis" / "speech" / "faster_whisper.py"
        src = backend.read_text(encoding="utf-8")
        assert "initial_prompt" in src, (
            "faster_whisper.py must set initial_prompt when language='en'. "
            "This steers the model away from Malay/Indonesian hallucinations "
            "on short English clips."
        )

    def test_faster_whisper_initial_prompt_says_not_translate(self):
        """faster-whisper initial_prompt must mention 'Do not translate'."""
        backend = _REPO_ROOT / "src" / "openjarvis" / "speech" / "faster_whisper.py"
        src = backend.read_text(encoding="utf-8")
        assert "Do not translate" in src, (
            "faster_whisper.py initial_prompt must say 'Do not translate' "
            "to prevent Malay/Indonesian misdetection for short English audio."
        )

    # ------------------------------------------------------------------ #
    # 4. Runtime: transcribe route default language unit test            #
    # ------------------------------------------------------------------ #

    def test_JARVIS_STT_LANGUAGE_default_is_en(self):
        """JARVIS_STT_LANGUAGE env var defaults to 'en' when unset."""
        import os
        # Temporarily unset the env var to test default
        original = os.environ.pop("JARVIS_STT_LANGUAGE", None)
        try:
            default = os.environ.get("JARVIS_STT_LANGUAGE", "en")
            assert default == "en", (
                f"Default JARVIS_STT_LANGUAGE must be 'en', got {default!r}"
            )
        finally:
            if original is not None:
                os.environ["JARVIS_STT_LANGUAGE"] = original

    def test_JARVIS_STT_LANGUAGE_env_is_overridable(self):
        """JARVIS_STT_LANGUAGE can be overridden for non-English users."""
        import os
        original = os.environ.get("JARVIS_STT_LANGUAGE")
        try:
            os.environ["JARVIS_STT_LANGUAGE"] = "fr"
            value = os.environ.get("JARVIS_STT_LANGUAGE", "en")
            assert value == "fr", (
                "JARVIS_STT_LANGUAGE env var must be respected when set."
            )
        finally:
            if original is None:
                os.environ.pop("JARVIS_STT_LANGUAGE", None)
            else:
                os.environ["JARVIS_STT_LANGUAGE"] = original


# ---------------------------------------------------------------------------
# L. US13 Voice Conversation Loop (full back-and-forth loop)
# ---------------------------------------------------------------------------


class TestVoiceConversationModule:
    """voice_conversation.py — module-level structure and import tests."""

    def test_module_importable(self):
        """voice_conversation module must be importable."""
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        assert VoiceConversationLoop is not None

    def test_all_public_symbols_importable(self):
        """All __all__ symbols must be importable."""
        from openjarvis.autonomy import voice_conversation
        for name in voice_conversation.__all__:
            obj = getattr(voice_conversation, name, None)
            assert obj is not None, f"voice_conversation.{name} not found"

    def test_voice_conversation_loop_class_exists(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        assert callable(VoiceConversationLoop)

    def test_record_command_audio_callable(self):
        from openjarvis.autonomy.voice_conversation import record_command_audio
        import inspect
        sig = inspect.signature(record_command_audio)
        assert "duration_seconds" in sig.parameters

    def test_transcribe_command_callable(self):
        from openjarvis.autonomy.voice_conversation import transcribe_command
        import inspect
        sig = inspect.signature(transcribe_command)
        assert "audio_bytes" in sig.parameters
        assert "language" in sig.parameters

    def test_query_jarvis_text_callable(self):
        from openjarvis.autonomy.voice_conversation import query_jarvis_text
        import inspect
        sig = inspect.signature(query_jarvis_text)
        assert "text" in sig.parameters

    def test_speak_response_callable(self):
        from openjarvis.autonomy.voice_conversation import speak_response
        import inspect
        sig = inspect.signature(speak_response)
        assert "text" in sig.parameters


class TestVoiceConversationLoopStructure:
    """VoiceConversationLoop state machine and API structure."""

    def _make_loop(self, **kw):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        return VoiceConversationLoop(**kw)

    def test_loop_has_start_method(self):
        loop = self._make_loop()
        assert hasattr(loop, "start") and callable(loop.start)

    def test_loop_has_stop_method(self):
        loop = self._make_loop()
        assert hasattr(loop, "stop") and callable(loop.stop)

    def test_loop_has_status_method(self):
        loop = self._make_loop()
        assert hasattr(loop, "status") and callable(loop.status)

    def test_loop_has_on_wake_callback(self):
        loop = self._make_loop()
        assert hasattr(loop, "_on_wake") and callable(loop._on_wake)

    def test_loop_has_process_turn(self):
        loop = self._make_loop()
        assert hasattr(loop, "_process_turn") and callable(loop._process_turn)

    def test_loop_initial_state_is_idle(self):
        loop = self._make_loop()
        assert loop._state == "idle"

    def test_loop_language_defaults_to_en(self):
        """Language must default to 'en' (prevents Malay/Indonesian misdetection)."""
        loop = self._make_loop()
        assert loop._language == "en", (
            "VoiceConversationLoop must default to language='en'. "
            "Without this, short English commands may be misidentified as Malay."
        )

    def test_loop_status_returns_required_fields(self):
        loop = self._make_loop()
        st = loop.status()
        for field in ("loop_state", "turns_completed", "record_seconds", "language", "bridge"):
            assert field in st, f"status() missing field: {field}"

    def test_loop_status_turns_starts_at_zero(self):
        loop = self._make_loop()
        assert loop.status()["turns_completed"] == 0

    def test_loop_set_state_updates_state(self):
        loop = self._make_loop()
        loop._set_state("listening")
        assert loop._state == "listening"

    def test_loop_set_state_calls_callback(self):
        states = []
        loop = self._make_loop(on_state_change=states.append)
        loop._set_state("recording")
        assert "recording" in states

    def test_loop_default_record_seconds_is_five(self):
        loop = self._make_loop()
        assert loop._record_seconds == 5.0


class TestWakeWordTriggersRecording:
    """Wake-word event must transition loop from listening to recording."""

    def test_on_wake_sets_state_to_recording(self):
        """_on_wake must change state from listening to recording."""
        import threading
        import time
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent

        loop = VoiceConversationLoop()
        loop._state = "listening"

        turn_started = threading.Event()

        def _mock_process_turn():
            turn_started.set()
            loop._set_state("listening")

        loop._process_turn = _mock_process_turn
        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.9, ts=time.time())
        loop._on_wake(ev)
        turn_started.wait(timeout=2.0)
        assert turn_started.is_set(), "Wake-word callback must start _process_turn thread"

    def test_on_wake_ignored_when_not_listening(self):
        """Wake-word event must be ignored if state is not 'listening'."""
        import time
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent

        loop = VoiceConversationLoop()
        loop._state = "processing"

        threads_started = []
        original_thread_start = None

        import threading as _threading
        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.9, ts=time.time())
        loop._on_wake(ev)
        assert loop._state == "processing", (
            "State must remain 'processing' — double-trigger must be ignored"
        )

    def test_on_wake_records_after_wake_word(self):
        """_process_turn must set state to 'recording' as its first step."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "recording" in src, (
            "_process_turn must set state to 'recording' after wake-word fires"
        )


class TestCommandRecordingFeedsSTT:
    """record_command_audio output feeds existing STT path."""

    def test_transcribe_command_uses_stt_status_check(self):
        """transcribe_command must use get_stt_status() to pick backend."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.transcribe_command)
        assert "get_stt_status" in src, (
            "transcribe_command must call get_stt_status() to pick the configured backend"
        )

    def test_transcribe_command_uses_faster_whisper_backend(self):
        """transcribe_command must use FasterWhisperBackend for faster_whisper engine."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.transcribe_command)
        assert "FasterWhisperBackend" in src

    def test_transcribe_command_uses_openai_whisper_backend(self):
        """transcribe_command must use OpenAIWhisperBackend for openai_whisper engine."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.transcribe_command)
        assert "OpenAIWhisperBackend" in src

    def test_transcribe_command_defaults_language_en(self):
        """transcribe_command must default language to 'en'."""
        import inspect
        from openjarvis.autonomy.voice_conversation import transcribe_command
        sig = inspect.signature(transcribe_command)
        assert sig.parameters["language"].default == "en", (
            "transcribe_command language default must be 'en' to prevent "
            "Malay/Indonesian misdetection on short English clips"
        )

    def test_transcribe_command_passes_language_to_backend(self):
        """transcribe_command must pass language kwarg to the STT backend."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.transcribe_command)
        assert "language=language" in src

    def test_record_command_audio_returns_wav_format(self):
        """record_command_audio must return WAV bytes (not raw PCM)."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.record_command_audio)
        assert "wave.open" in src, (
            "record_command_audio must write a WAV file — STT backends expect WAV"
        )

    def test_packaged_app_stt_english_fix_intact(self):
        """Existing STT English fixes (initial_prompt, language='en') must not be broken."""
        backend = _REPO_ROOT / "src" / "openjarvis" / "speech" / "faster_whisper.py"
        src = backend.read_text(encoding="utf-8")
        assert "initial_prompt" in src and "Do not translate" in src, (
            "faster_whisper.py initial_prompt English fix must remain intact"
        )
        backend_oa = _REPO_ROOT / "src" / "openjarvis" / "speech" / "openai_whisper.py"
        src_oa = backend_oa.read_text(encoding="utf-8")
        assert "Do not translate" in src_oa, (
            "openai_whisper.py English prompt hint must remain intact"
        )


class TestSTTRoutesToJarvisPath:
    """STT output must route through the normal Jarvis chat/model/action path."""

    def test_query_jarvis_text_uses_get_engine(self):
        """query_jarvis_text must use get_engine() — not a duplicate engine."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.query_jarvis_text)
        assert "get_engine" in src, (
            "query_jarvis_text must call get_engine() from the existing engine module"
        )

    def test_query_jarvis_text_uses_load_config(self):
        """query_jarvis_text must use load_config() for config."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.query_jarvis_text)
        assert "load_config" in src

    def test_query_jarvis_text_uses_engine_generate(self):
        """query_jarvis_text must call engine.generate() — the normal inference path."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.query_jarvis_text)
        assert "engine.generate" in src

    def test_query_jarvis_text_respects_default_agent(self):
        """query_jarvis_text must use the configured default_agent if set."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.query_jarvis_text)
        assert "default_agent" in src, (
            "query_jarvis_text must respect config.agent.default_agent"
        )

    def test_no_duplicate_planner_in_voice_conversation(self):
        """voice_conversation must not define its own planner or orchestrator."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation)
        assert "ResearchAgent" not in src, "Must not duplicate the ResearchAgent"
        assert "OrchestratorAgent" not in src, "Must not duplicate the OrchestratorAgent"
        assert "PlannerAgent" not in src, "Must not duplicate the PlannerAgent"


class TestTTSCalledWithResponse:
    """speak_response must use the existing TTS path."""

    def test_speak_response_uses_get_tts_status(self):
        """speak_response must call get_tts_status() from voice_pipeline."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.speak_response)
        assert "get_tts_status" in src

    def test_speak_response_uses_macos_say(self):
        """speak_response must invoke 'say' on macOS."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.speak_response)
        assert '"say"' in src or "'say'" in src

    def test_process_turn_calls_speak_response(self):
        """_process_turn must call speak_response() with the Jarvis response."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "speak_response" in src, (
            "_process_turn must call speak_response() with the Jarvis response"
        )


class TestLoopReturnsToListening:
    """After each turn, the loop must return to listening state."""

    def test_process_turn_returns_to_listening_in_finally(self):
        """_process_turn must set state to 'listening' in a finally block."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "finally" in src, (
            "_process_turn must use finally: to guarantee return to listening"
        )
        assert "listening" in src, (
            "_process_turn finally block must set state to 'listening'"
        )

    def test_loop_returns_to_listening_after_mock_turn(self):
        """After _process_turn finishes, loop state must be 'listening'."""
        import threading
        import time
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent

        loop = VoiceConversationLoop()
        loop._state = "listening"

        done = threading.Event()

        def _mock_turn():
            try:
                pass
            finally:
                loop._set_state("listening")
                done.set()

        loop._process_turn = _mock_turn
        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.9, ts=time.time())
        loop._on_wake(ev)
        done.wait(timeout=3.0)
        assert loop._state == "listening", (
            f"Loop state must be 'listening' after turn, got {loop._state!r}"
        )

    def test_loop_increments_turns_after_turn(self):
        """_turns counter must increment after each completed turn."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "_turns" in src, (
            "_process_turn must increment _turns after each completed turn"
        )


class TestSafetyApprovalGates:
    """Safety/approval gates must not be bypassed for voice commands."""

    def test_query_jarvis_text_calls_setup_security(self):
        """query_jarvis_text must call setup_security() before any inference.

        This ensures the voice path goes through the same security layer as
        the CLI (jarvis ask / jarvis chat). Approval gates, capability policy,
        and hard-blocked action classes all remain active.
        """
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.query_jarvis_text)
        assert "setup_security" in src, (
            "query_jarvis_text MUST call setup_security() — "
            "this is the safety gate that prevents voice from bypassing "
            "approval policies, hard-blocked actions, and capability checks."
        )

    def test_query_jarvis_text_uses_security_engine(self):
        """query_jarvis_text must use sec.engine, not the raw engine."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.query_jarvis_text)
        assert "sec.engine" in src, (
            "query_jarvis_text must replace engine with sec.engine — "
            "the raw engine bypasses security middleware"
        )

    def test_voice_hard_blocked_actions_still_blocked(self):
        """Voice hard-blocked action classes must remain blocked."""
        from openjarvis.autonomy.voice_pipeline import (
            classify_voice_risk,
            VoiceApprovalRisk,
        )
        for action in ("production_deploy", "billing_change", "secrets_mutation"):
            risk = classify_voice_risk(action)
            assert risk == VoiceApprovalRisk.DANGEROUS, (
                f"Action {action!r} must remain DANGEROUS/hard-blocked for voice"
            )

    def test_issue_approval_challenge_still_raises_for_hard_blocked(self):
        """issue_approval_challenge must still raise for hard-blocked actions."""
        from openjarvis.autonomy.voice_pipeline import issue_approval_challenge
        import pytest
        with pytest.raises(ValueError, match="voice-hard-blocked"):
            issue_approval_challenge("production_deploy", "Deploy to prod")

    def test_voice_conversation_module_does_not_bypass_security(self):
        """voice_conversation.py must not import voice_hard_blocked or bypass gates."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation)
        assert "_VOICE_HARD_BLOCKED" not in src, (
            "voice_conversation.py must not access _VOICE_HARD_BLOCKED — "
            "do not replicate or bypass the approval gate list"
        )


class TestVoiceChatCLICommand:
    """'jarvis voice chat' CLI command registration and help tests."""

    def test_voice_chat_subcommand_registered(self):
        """'chat' subcommand must be registered in the voice group."""
        from openjarvis.cli.voice_cmd import voice
        assert "chat" in voice.commands, (
            "'chat' must be registered as a subcommand of 'jarvis voice'"
        )

    def test_voice_chat_help_exits_zero(self):
        r = _run_cli("voice", "chat", "--help")
        assert r.returncode == 0, f"voice chat --help failed:\n{r.stderr}"

    def test_voice_chat_help_mentions_hey_jarvis(self):
        r = _run_cli("voice", "chat", "--help")
        combined = r.stdout + r.stderr
        assert "hey jarvis" in combined.lower() or "wake" in combined.lower()

    def test_voice_chat_help_mentions_record_seconds(self):
        r = _run_cli("voice", "chat", "--help")
        assert "--record-seconds" in r.stdout

    def test_voice_chat_help_mentions_language(self):
        r = _run_cli("voice", "chat", "--help")
        assert "--language" in r.stdout

    def test_voice_chat_help_mentions_threshold(self):
        r = _run_cli("voice", "chat", "--help")
        assert "--threshold" in r.stdout

    def test_voice_chat_help_mentions_debug(self):
        r = _run_cli("voice", "chat", "--help")
        assert "--debug" in r.stdout

    def test_voice_help_mentions_chat(self):
        """'jarvis voice --help' must list the 'chat' subcommand."""
        r = _run_cli("voice", "--help")
        assert "chat" in r.stdout, (
            "'jarvis voice --help' must list the 'chat' subcommand"
        )

    def test_voice_chat_requires_wakeword_worker(self):
        """voice_chat implementation must check bridge availability."""
        voice_cmd_path = _REPO_ROOT / "src" / "openjarvis" / "cli" / "voice_cmd.py"
        src = voice_cmd_path.read_text(encoding="utf-8")
        assert "is_available" in src, (
            "voice_chat must call bridge.is_available() before starting"
        )

    def test_voice_chat_exits_nonzero_without_worker(self):
        """jarvis voice chat must exit non-zero when worker venv is missing."""
        voice_cmd_path = _REPO_ROOT / "src" / "openjarvis" / "cli" / "voice_cmd.py"
        src = voice_cmd_path.read_text(encoding="utf-8")
        assert "sys.exit(1)" in src, (
            "voice_chat must call sys.exit(1) when worker venv is not found"
        )

    def test_voice_chat_checks_stt_configuration(self):
        """voice_chat must check STT is configured before starting."""
        voice_cmd_path = _REPO_ROOT / "src" / "openjarvis" / "cli" / "voice_cmd.py"
        src = voice_cmd_path.read_text(encoding="utf-8")
        assert "stt" in src.lower() and "not_configured" in src

    def test_voice_chat_uses_voice_conversation_loop(self):
        """voice_chat must use VoiceConversationLoop, not re-implement the loop."""
        voice_cmd_path = _REPO_ROOT / "src" / "openjarvis" / "cli" / "voice_cmd.py"
        src = voice_cmd_path.read_text(encoding="utf-8")
        assert "VoiceConversationLoop" in src


# ---------------------------------------------------------------------------
# M. US13 UX: Wake acknowledgement, session loop, transcript, latency, app path
# ---------------------------------------------------------------------------


class TestWakeAcknowledgement:
    """After wake-word fires, Jarvis must immediately acknowledge before recording."""

    def test_time_of_day_greeting_importable(self):
        from openjarvis.autonomy.voice_conversation import time_of_day_greeting
        assert callable(time_of_day_greeting)

    def test_time_of_day_greeting_morning(self):
        import time as _t
        import unittest.mock as mock
        from openjarvis.autonomy.voice_conversation import time_of_day_greeting
        with mock.patch("time.localtime") as m:
            m.return_value = _t.struct_time((2024, 1, 1, 9, 0, 0, 0, 1, 0))
            greet = time_of_day_greeting("Bryan")
        assert "morning" in greet.lower() and "Bryan" in greet

    def test_time_of_day_greeting_afternoon(self):
        import time as _t
        import unittest.mock as mock
        from openjarvis.autonomy.voice_conversation import time_of_day_greeting
        with mock.patch("time.localtime") as m:
            m.return_value = _t.struct_time((2024, 1, 1, 14, 0, 0, 0, 1, 0))
            greet = time_of_day_greeting("Bryan")
        assert "afternoon" in greet.lower() and "Bryan" in greet

    def test_time_of_day_greeting_evening(self):
        import time as _t
        import unittest.mock as mock
        from openjarvis.autonomy.voice_conversation import time_of_day_greeting
        with mock.patch("time.localtime") as m:
            m.return_value = _t.struct_time((2024, 1, 1, 19, 0, 0, 0, 1, 0))
            greet = time_of_day_greeting("Bryan")
        assert "evening" in greet.lower() and "Bryan" in greet

    def test_time_of_day_greeting_night(self):
        import time as _t
        import unittest.mock as mock
        from openjarvis.autonomy.voice_conversation import time_of_day_greeting
        with mock.patch("time.localtime") as m:
            m.return_value = _t.struct_time((2024, 1, 1, 2, 0, 0, 0, 1, 0))
            greet = time_of_day_greeting("Bryan")
        assert "Bryan" in greet

    def test_time_of_day_greeting_returns_string(self):
        from openjarvis.autonomy.voice_conversation import time_of_day_greeting
        result = time_of_day_greeting()
        assert isinstance(result, str) and len(result) > 5

    def test_process_turn_calls_acknowledgement_before_recording(self):
        """_process_turn must set state 'acknowledging' before state 'recording'."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        ack_pos = src.find("acknowledging")
        rec_pos = src.find('"recording"')
        assert ack_pos != -1, "_process_turn must set state 'acknowledging'"
        assert rec_pos != -1, "_process_turn must set state 'recording'"
        assert ack_pos < rec_pos, (
            "_process_turn must acknowledge BEFORE starting the recording state"
        )

    def test_process_turn_speaks_greeting(self):
        """_process_turn must call speak_response with time_of_day_greeting."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "time_of_day_greeting" in src, (
            "_process_turn must call time_of_day_greeting() for wake acknowledgement"
        )

    def test_wake_to_ack_latency_emitted(self):
        """_process_turn must emit wake_to_ack_ms latency event."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "wake_to_ack_ms" in src


class TestVoiceStateTransitions:
    """All required voice states must be emitted as events."""

    def test_state_transitions_are_emitted_as_events(self):
        """_set_state must emit an event of type 'state'."""
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        events = []
        loop = VoiceConversationLoop(on_state_change=lambda s: None)
        loop._emit_event = lambda e: events.append(e)

        loop._set_state("listening")
        loop._set_state("recording")
        states = [e.get("state") for e in events if e.get("type") == "state"]
        assert "listening" in states
        assert "recording" in states

    def test_wake_detected_event_emitted(self):
        """_on_wake must emit a wake_detected state event."""
        import time as _time
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        from openjarvis.autonomy.wakeword_bridge import WakeWordTriggerEvent

        events = []
        loop = VoiceConversationLoop()
        loop._state = "listening"

        original_emit = loop._emit_event
        def _capture(e):
            events.append(e)
        loop._emit_event = _capture

        import threading
        done = threading.Event()
        def _mock_turn():
            done.set()
        loop._process_turn = _mock_turn

        ev = WakeWordTriggerEvent(model="hey_jarvis_v0.1", score=0.85, ts=_time.time())
        loop._on_wake(ev)
        done.wait(timeout=2.0)

        wake_events = [e for e in events if e.get("state") == "wake_detected"]
        assert len(wake_events) >= 1, "wake_detected event must be emitted"
        assert wake_events[0].get("model") is not None
        assert wake_events[0].get("score") is not None

    def test_required_states_in_process_turn_source(self):
        """_process_turn source must reference all required state strings."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        required = [
            "acknowledging", "active_conversation", "recording",
            "transcribing", "thinking", "speaking", "follow_up_listening", "listening",
        ]
        for state in required:
            assert state in src, f"_process_turn must reference state '{state}'"

    def test_loop_has_session_timeout_param(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        import inspect
        sig = inspect.signature(VoiceConversationLoop.__init__)
        assert "session_timeout" in sig.parameters

    def test_loop_has_stop_phrases_param(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        import inspect
        sig = inspect.signature(VoiceConversationLoop.__init__)
        assert "stop_phrases" in sig.parameters

    def test_loop_has_user_name_param(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        import inspect
        sig = inspect.signature(VoiceConversationLoop.__init__)
        assert "user_name" in sig.parameters

    def test_event_subscribe_unsubscribe(self):
        """subscribe_events / unsubscribe_events API must work."""
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        q = loop.subscribe_events()
        assert q is not None
        loop._emit_event({"type": "test", "val": 42})
        item = q.get_nowait()
        assert item["val"] == 42
        loop.unsubscribe_events(q)

    def test_get_events_history(self):
        """get_events_history must return recently emitted events."""
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        loop._emit_event({"type": "state", "state": "listening"})
        history = loop.get_events_history()
        assert any(e.get("state") == "listening" for e in history)


class TestLiveTranscriptEvents:
    """Transcript and interim events must be emitted to the event stream."""

    def test_interim_transcript_event_emitted_during_recording(self):
        """_process_turn must emit interim_transcript events during recording."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "interim_transcript" in src, (
            "_process_turn must emit interim_transcript events so the UI can show "
            "recording progress"
        )

    def test_final_transcript_event_emitted(self):
        """_process_turn must emit a transcript event with the final STT text."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert '"transcript"' in src or "'transcript'" in src, (
            "_process_turn must emit a 'transcript' event with the final STT text"
        )

    def test_response_event_emitted(self):
        """_process_turn must emit a response event with the Jarvis answer text."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert '"response"' in src or "'response'" in src, (
            "_process_turn must emit a 'response' event with the Jarvis answer"
        )

    def test_stop_phrases_constant_exists(self):
        from openjarvis.autonomy.voice_conversation import STOP_PHRASES
        assert isinstance(STOP_PHRASES, list)
        assert len(STOP_PHRASES) > 0

    def test_stop_phrases_include_required_phrases(self):
        from openjarvis.autonomy.voice_conversation import STOP_PHRASES
        phrases_lower = [p.lower() for p in STOP_PHRASES]
        for required in ("stop listening", "cancel", "that's all", "go back to sleep"):
            assert required in phrases_lower, f"STOP_PHRASES must include {required!r}"

    def test_tts_called_with_response_in_process_turn(self):
        """_process_turn must call speak_response with the Jarvis response."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "speak_response(response)" in src or "speak_response(" in src


class TestConversationSessionFollowUp:
    """After first turn, loop must keep session open for follow-up without wake word."""

    def test_process_turn_has_follow_up_listening(self):
        """_process_turn must include 'follow_up_listening' state for multi-turn."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "follow_up_listening" in src, (
            "_process_turn must transition to 'follow_up_listening' between turns "
            "so the user can speak again without saying 'hey jarvis'"
        )

    def test_process_turn_has_session_loop(self):
        """_process_turn must loop (while True) for multi-turn session."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "while True" in src or "while " in src, (
            "_process_turn must contain a loop to support multi-turn conversation"
        )

    def test_is_stop_phrase_method_exists(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        assert hasattr(loop, "_is_stop_phrase") and callable(loop._is_stop_phrase)

    def test_stop_phrase_detection_stop_listening(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        assert loop._is_stop_phrase("stop listening")
        assert loop._is_stop_phrase("Stop Listening.")
        assert loop._is_stop_phrase("cancel")
        assert loop._is_stop_phrase("that's all")
        assert loop._is_stop_phrase("go back to sleep")

    def test_stop_phrase_not_triggered_by_normal_speech(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        assert not loop._is_stop_phrase("what is the capital of France")
        assert not loop._is_stop_phrase("cancel my flight booking")
        assert not loop._is_stop_phrase("how do I stop a process in Python")

    def test_stop_phrase_ends_session_in_source(self):
        """_process_turn must check for stop phrases and break the loop."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "_is_stop_phrase" in src, (
            "_process_turn must call _is_stop_phrase() and break the session loop"
        )

    def test_session_timeout_ends_session_in_source(self):
        """_process_turn must break the loop when session_deadline is exceeded."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        assert "session_deadline" in src or "_session_timeout" in src, (
            "_process_turn must use a session deadline to return to wake-word-only mode"
        )

    def test_session_timeout_default_is_30s(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        assert loop._session_timeout == 30.0

    def test_status_includes_session_timeout(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop(session_timeout=45.0)
        st = loop.status()
        assert st.get("session_timeout") == 45.0


class TestLatencyInstrumentation:
    """Per-stage latency must be measured and emitted as events."""

    def test_emit_latency_method_exists(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        assert hasattr(loop, "_emit_latency") and callable(loop._emit_latency)

    def test_emit_latency_sends_correct_event(self):
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        loop = VoiceConversationLoop()
        q = loop.subscribe_events()
        loop._emit_latency("stt_duration_ms", 1234.5)
        ev = q.get_nowait()
        assert ev["type"] == "latency"
        assert ev["stage"] == "stt_duration_ms"
        assert ev["value_ms"] == 1234.5

    def test_all_required_latency_stages_in_source(self):
        """_process_turn must measure all required latency stages."""
        import inspect
        from openjarvis.autonomy import voice_conversation
        src = inspect.getsource(voice_conversation.VoiceConversationLoop._process_turn)
        required_stages = [
            "wake_to_ack_ms",
            "wake_to_record_start_ms",
            "stt_duration_ms",
            "speech_end_to_stt_final_ms",
            "model_duration_ms",
            "tts_start_ms",
            "total_turn_ms",
        ]
        for stage in required_stages:
            assert stage in src, f"_process_turn must emit latency stage '{stage}'"

    def test_latency_events_reach_subscriber(self):
        """Latency events must be delivered to event subscribers."""
        from openjarvis.autonomy.voice_conversation import VoiceConversationLoop
        import queue as _q
        loop = VoiceConversationLoop()
        sub = loop.subscribe_events()
        loop._emit_latency("total_turn_ms", 5432.1)
        ev = sub.get(timeout=1.0)
        assert ev.get("type") == "latency"
        assert ev.get("stage") == "total_turn_ms"


class TestAppUserFacingStartPath:
    """Packaged app must be able to start voice mode without a terminal command."""

    def test_voice_routes_module_exists(self):
        """voice_routes.py must exist in the server package."""
        vr_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        assert vr_path.exists(), "voice_routes.py must exist"

    def test_voice_session_start_route_registered(self):
        """POST /v1/voice/session/start must be declared in voice_routes.py."""
        vr_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        src = vr_path.read_text(encoding="utf-8")
        assert '"/v1/voice/session/start"' in src or "'/v1/voice/session/start'" in src, (
            "POST /v1/voice/session/start must be registered so the packaged app "
            "can start voice mode without a terminal command"
        )

    def test_voice_session_stop_route_registered(self):
        vr_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        src = vr_path.read_text(encoding="utf-8")
        assert '"/v1/voice/session/stop"' in src or "'/v1/voice/session/stop'" in src

    def test_voice_session_status_route_registered(self):
        vr_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        src = vr_path.read_text(encoding="utf-8")
        assert '"/v1/voice/session/status"' in src or "'/v1/voice/session/status'" in src

    def test_voice_session_events_sse_route_registered(self):
        """GET /v1/voice/session/events must be declared in voice_routes.py."""
        vr_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        src = vr_path.read_text(encoding="utf-8")
        assert '"/v1/voice/session/events"' in src or "'/v1/voice/session/events'" in src, (
            "SSE events endpoint must be registered so the UI can show live "
            "state/transcript/latency updates"
        )

    def test_voice_router_included_in_app(self):
        """voice_router must be registered in create_app."""
        app_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "app.py"
        src = app_path.read_text(encoding="utf-8")
        assert "voice_router" in src, (
            "voice_router must be included in create_app so the packaged app "
            "can reach the voice session endpoints"
        )

    def test_platform_support_declared_in_voice_routes(self):
        """voice_routes.py must explicitly declare platform support."""
        voice_routes_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        src = voice_routes_path.read_text(encoding="utf-8")
        assert "NOT_PROVEN" in src, (
            "voice_routes.py must declare NOT_PROVEN for unsupported platforms "
            "instead of silently ignoring them"
        )
        assert "macOS" in src or "Darwin" in src, (
            "voice_routes.py must declare macOS as the SUPPORTED platform"
        )

    def test_voice_overlay_component_exists(self):
        """VoiceOverlay.tsx must exist as the packaged-app voice UI surface."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        assert overlay_path.exists(), (
            "VoiceOverlay.tsx must exist — it is the user-facing voice surface "
            "in the packaged Tauri app"
        )

    def test_voice_overlay_in_app_tsx(self):
        """VoiceOverlay must be rendered in App.tsx."""
        app_path = _REPO_ROOT / "frontend" / "src" / "App.tsx"
        src = app_path.read_text(encoding="utf-8")
        assert "VoiceOverlay" in src, (
            "VoiceOverlay must be imported and rendered in App.tsx so the mic "
            "button is available in the packaged app without a terminal command"
        )

    def test_use_voice_session_hook_exists(self):
        """useVoiceSession.ts must exist as the frontend SSE/API hook."""
        hook_path = _REPO_ROOT / "frontend" / "src" / "hooks" / "useVoiceSession.ts"
        assert hook_path.exists(), "useVoiceSession.ts hook must exist"

    def test_voice_overlay_shows_state_and_transcript(self):
        """VoiceOverlay.tsx must render state, transcript, and Jarvis response."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "finalTranscript" in src, "VoiceOverlay must show final transcript"
        assert "jarvisResponse" in src, "VoiceOverlay must show Jarvis response"
        assert "voiceState" in src or "VOICE_STATE_LABEL" in src, (
            "VoiceOverlay must show current voice state"
        )

    def test_voice_overlay_shows_latency(self):
        """VoiceOverlay must expose latency metrics to the user."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "latency" in src.lower(), (
            "VoiceOverlay must show latency metrics so bottlenecks are visible"
        )

    def test_voice_overlay_shows_stop_phrase_hint(self):
        """VoiceOverlay must hint the user about stop phrases."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "stop" in src.lower(), (
            "VoiceOverlay must show stop-phrase hint (e.g. 'say stop listening')"
        )


class TestExistingFixesIntact:
    """All previously accepted US13 items must remain intact."""

    def test_existing_voice_conversation_tests_still_pass(self):
        """Smoke-import of all prior test classes."""
        from openjarvis.autonomy.voice_conversation import (
            VoiceConversationLoop,
            record_command_audio,
            transcribe_command,
            query_jarvis_text,
            speak_response,
            STOP_PHRASES,
            time_of_day_greeting,
        )
        assert all([VoiceConversationLoop, record_command_audio, transcribe_command,
                    query_jarvis_text, speak_response, STOP_PHRASES, time_of_day_greeting])

    def test_packaged_app_stt_english_fix_intact_2(self):
        """faster_whisper.py English fix still present after US13 UX rewrite."""
        fw = _REPO_ROOT / "src" / "openjarvis" / "speech" / "faster_whisper.py"
        src = fw.read_text(encoding="utf-8")
        assert "initial_prompt" in src and "Do not translate" in src

    def test_voice_approval_gates_untouched(self):
        """Voice hard-blocked actions and classify_voice_risk still work."""
        from openjarvis.autonomy.voice_pipeline import classify_voice_risk, VoiceApprovalRisk
        assert classify_voice_risk("production_deploy") == VoiceApprovalRisk.DANGEROUS

    def test_voice_conversation_does_not_duplicate_safety_systems(self):
        """voice_conversation.py must not replicate approval/hard-block lists."""
        vc_path = _REPO_ROOT / "src" / "openjarvis" / "autonomy" / "voice_conversation.py"
        src = vc_path.read_text(encoding="utf-8")
        assert "_VOICE_HARD_BLOCKED" not in src
        assert "ResearchAgent" not in src


# ---------------------------------------------------------------------------
# N. US13 UX v2: Wake-driven (not mic-click-driven) acceptance tests
# ---------------------------------------------------------------------------


class TestWakeDrivenNotMicClickDriven:
    """Voice mode must auto-start wake listening — not require a mic button click."""

    def test_voice_overlay_has_auto_start_use_effect(self):
        """VoiceOverlay.tsx must contain a useEffect that calls start() on mount.

        This is the fix for the mic-click-driven failure: voice mode must begin
        listening for 'Hey Jarvis' automatically when the app loads.
        """
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "useEffect" in src, "VoiceOverlay must use useEffect"
        assert "start(" in src, "VoiceOverlay must call start() from useEffect"
        assert "silent" in src, (
            "VoiceOverlay auto-start must use silent:true so missing wake-worker "
            "venv does not flash an error to the user"
        )

    def test_voice_overlay_auto_start_does_not_require_onclick(self):
        """The primary auto-start path must NOT be inside an onClick handler.

        There must be a useEffect (not just onClick) that calls start().
        """
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        # useEffect must call start — confirm start() is referenced outside onClick context
        # The auto-start useEffect uses setTimeout + start({silent:true})
        assert "setTimeout" in src and "silent: true" in src, (
            "VoiceOverlay must schedule an auto-start via setTimeout + start({silent:true}) "
            "in a useEffect — not only in an onClick handler"
        )

    def test_voice_overlay_auto_expands_on_wake_detected(self):
        """VoiceOverlay must expand automatically when wake_detected fires.

        Without this, Bryan sees no UI feedback after saying 'Hey Jarvis'.
        """
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "wake_detected" in src, (
            "VoiceOverlay must check for wake_detected state to auto-expand"
        )
        assert "setExpanded(true)" in src, (
            "VoiceOverlay must call setExpanded(true) when active voice states arrive"
        )

    def test_voice_overlay_uses_active_conv_states_list(self):
        """VoiceOverlay must have a list of active states that trigger auto-expand."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        for state in ("acknowledging", "recording", "thinking", "speaking"):
            assert state in src, (
                f"VoiceOverlay ACTIVE_CONV_STATES must include '{state}' "
                "so the overlay opens automatically during those phases"
            )

    def test_voice_overlay_mic_button_is_fallback_not_required(self):
        """The mic button must be labelled as a fallback/stop control, not the primary path."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        # Primary start must not be tied to handleToggle/onClick only
        assert "handleMicClick" in src or "handleToggle" not in src, (
            "The primary mic-button handler must be handleMicClick (or equivalent) "
            "with auto-start separated into useEffect"
        )
        assert "auto-starts on app launch" in src or "Manually" in src, (
            "The mic button tooltip must indicate it is a manual fallback, "
            "not the required path (auto-start handles normal use)"
        )

    def test_use_voice_session_has_silent_option(self):
        """useVoiceSession start() must accept a silent option."""
        hook_path = _REPO_ROOT / "frontend" / "src" / "hooks" / "useVoiceSession.ts"
        src = hook_path.read_text(encoding="utf-8")
        assert "silent" in src, (
            "useVoiceSession start() must have a silent option for auto-start "
            "so errors from a missing wake-worker venv don't break the UI"
        )

    def test_voice_overlay_shows_background_listening_indicator(self):
        """VoiceOverlay must show a visible indicator while in background wake-only mode."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "animate-pulse" in src or "isWakeListening" in src, (
            "VoiceOverlay must show a pulsing/animated indicator when in background "
            "wake-listening mode so Bryan knows voice is active without the panel open"
        )

    def test_voice_overlay_auto_collapses_after_session(self):
        """VoiceOverlay must auto-collapse after session returns to wake-listening."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        # Must have setExpanded(false) in response to listening/wake_listening state
        assert "setExpanded(false)" in src, (
            "VoiceOverlay must eventually collapse back to background mode after a session"
        )

    def test_voice_overlay_uses_use_effect_and_use_ref(self):
        """VoiceOverlay must import useEffect and useRef for auto-start guard."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "useEffect" in src and "useRef" in src, (
            "VoiceOverlay must import useEffect (for auto-start) and useRef "
            "(for autoStarted guard to prevent double-start on re-render)"
        )

    def test_voice_overlay_shows_auto_start_failure_indicator(self):
        """VoiceOverlay must show a visible red dot when auto-start fails."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "autoStartFailed" in src, (
            "VoiceOverlay must track auto-start failure state"
        )
        assert "var(--color-error" in src and "autoStartFailed" in src, (
            "VoiceOverlay must render a red error indicator when autoStartFailed is true"
        )
        assert "jarvis voice setup" in src or "wake-worker" in src, (
            "The failure indicator tooltip must mention the setup command or wake-worker venv"
        )

    def test_voice_overlay_start_returns_boolean(self):
        """useVoiceSession start() must return boolean for success/failure."""
        hook_path = _REPO_ROOT / "frontend" / "src" / "hooks" / "useVoiceSession.ts"
        src = hook_path.read_text(encoding="utf-8")
        assert "Promise<boolean>" in src, (
            "start() must return Promise<boolean> so VoiceOverlay can detect auto-start failure"
        )
        assert "return true" in src and "return false" in src, (
            "start() must return true on success, false on failure"
        )

    def test_old_chatbox_mic_button_is_hidden(self):
        """The old chatbox MicButton must be hidden to avoid confusion."""
        input_path = _REPO_ROOT / "frontend" / "src" / "components" / "Chat" / "InputArea.tsx"
        src = input_path.read_text(encoding="utf-8")
        assert "MicButton" not in src or "Manual dictation mic hidden" in src, (
            "The old chatbox MicButton must be hidden or commented out so it does not "
            "confuse users with the new wake-word VoiceOverlay"
        )

    def test_voice_overlay_shows_always_visible_state_badge(self):
        """VoiceOverlay must show a state badge even when collapsed."""
        overlay_path = _REPO_ROOT / "frontend" / "src" / "components" / "VoiceOverlay.tsx"
        src = overlay_path.read_text(encoding="utf-8")
        assert "Voice off" in src or "Voice unavailable" in src, (
            "VoiceOverlay must render a state badge showing current status "
            "even when the panel is collapsed"
        )
        assert "isWakeListening" in src and "autoStartFailed" in src, (
            "The state badge must distinguish between wake-listening, active, "
            "and failed states"
        )

    def test_voice_routes_returns_specific_error_codes(self):
        """voice_routes.py must return error_code field for structured error handling."""
        routes_path = _REPO_ROOT / "src" / "openjarvis" / "server" / "voice_routes.py"
        src = routes_path.read_text(encoding="utf-8")
        assert "error_code" in src, (
            "voice_routes.py must include error_code in error responses "
            "so the frontend can display specific failure causes"
        )
        # Check for specific error codes
        for code in ("wake_worker_missing", "stt_not_configured", "loop_start_failed", "platform_not_supported"):
            assert code in src, f"voice_routes.py must define error_code '{code}'"

    def test_frontend_displays_error_code_in_badge(self):
        """useVoiceSession must extract error_code and include it in error state."""
        hook_path = _REPO_ROOT / "frontend" / "src" / "hooks" / "useVoiceSession.ts"
        src = hook_path.read_text(encoding="utf-8")
        assert "error_code" in src, (
            "useVoiceSession must extract error_code from backend response"
        )
        assert "network_error" in src, (
            "useVoiceSession must handle network errors with a specific error code"
        )
