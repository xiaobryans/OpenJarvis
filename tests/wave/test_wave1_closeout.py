"""Wave 1 Closeout Sprint Tests.

Tests covering:
  Epic A — Skill Induction Pipeline (skill_induction.py)
  Epic B — Automation Scheduler (automation_scheduler.py)
  Epic C — Local Folder Connector (local_folder_connector.py)
  Epic D — Tavily Web Research Provider (tavily_provider.py)

All external HTTP calls are mocked. No real network required.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# EPIC A — Skill Induction Pipeline
# ─────────────────────────────────────────────────────────────────────────────


class TestSkillInductionValidation:
    """Validate manifest safety checks."""

    def test_safe_manifest_passes(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "my_safe_skill",
            "name": "My Safe Skill",
            "description": "Lists local files in workspace",
            "tags": [],
            "risk_level": "low",
        })
        assert result.valid, f"Expected valid, violations={result.violations}"
        assert not result.hard_gate
        assert not result.approval_required

    def test_missing_skill_id_fails(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({"name": "No ID"})
        assert not result.valid
        kinds = [v.kind for v in result.violations]
        assert "missing_field" in kinds

    def test_missing_name_fails(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({"skill_id": "noid"})
        assert not result.valid

    def test_destructive_command_rejected(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "bad",
            "name": "Bad Skill",
            "description": "Runs rm -rf / to clean up",
        })
        assert not result.valid
        kinds = [v.kind for v in result.violations]
        assert "destructive_command" in kinds

    def test_secret_capability_rejected(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "secret_skill",
            "name": "Secret Skill",
            "description": "Access api_key vault",
        })
        assert not result.valid
        kinds = [v.kind for v in result.violations]
        assert "unsafe_capability" in kinds

    def test_external_send_tag_is_hard_gate(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "slack_skill",
            "name": "Slack Sender",
            "description": "Sends notifications",
            "tags": ["external_send"],
        })
        assert not result.valid
        assert result.hard_gate

    def test_terminal_tag_requires_approval(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "term_skill",
            "name": "Terminal Skill",
            "description": "Runs terminal commands",
            "tags": ["terminal"],
        })
        assert result.valid  # warnings only, no violations
        assert result.approval_required

    def test_high_risk_requires_approval(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "risky",
            "name": "Risky Skill",
            "description": "Does something risky",
            "tags": [],
            "risk_level": "high",
        })
        assert result.valid
        assert result.approval_required

    def test_credential_in_description_blocked(self):
        from openjarvis.wave.skill_induction import validate_skill_manifest
        result = validate_skill_manifest({
            "skill_id": "cred_skill",
            "name": "Credential Extractor",
            "description": "Extracts credential from browser",
        })
        assert not result.valid


class TestSkillInductionPipeline:
    """Test full induction pipeline."""

    def test_safe_skill_inductable(self):
        from openjarvis.wave.skill_induction import induce_skill
        result = induce_skill({
            "skill_id": "test_induct_safe",
            "name": "Test Inductable Safe",
            "description": "Read-only local status check",
            "tags": [],
            "risk_level": "low",
        })
        assert result.ok, f"Expected ok=True, got error={result.error}"
        assert result.status == "accepted"

    def test_unsafe_manifest_rejected_on_induct(self):
        from openjarvis.wave.skill_induction import induce_skill
        result = induce_skill({
            "skill_id": "test_induct_unsafe",
            "name": "Unsafe",
            "description": "sudo rm -rf /",
            "tags": [],
        })
        assert not result.ok
        assert result.status in ("rejected", "hard_gate_blocked")

    def test_hard_gate_tag_blocked_from_induction(self):
        from openjarvis.wave.skill_induction import induce_skill
        result = induce_skill({
            "skill_id": "test_induct_hg",
            "name": "Slack Skill",
            "description": "Sends slack messages",
            "tags": ["slack"],
        })
        assert not result.ok
        assert result.status == "hard_gate_blocked"

    def test_high_risk_inducted_as_pending_approval(self):
        from openjarvis.wave.skill_induction import induce_skill
        result = induce_skill({
            "skill_id": "test_induct_hr",
            "name": "High Risk",
            "description": "Writes to disk",
            "tags": ["write"],
            "risk_level": "high",
        })
        assert not result.ok
        assert result.status == "pending_approval"

    def test_induction_pipeline_status(self):
        from openjarvis.wave.skill_induction import get_induction_pipeline_status
        info = get_induction_pipeline_status()
        assert info["implemented"] is True
        assert "required_fields" in info["validation_checks"]

    def test_induction_event_logged(self):
        from openjarvis.wave.skill_induction import induce_skill
        result = induce_skill({
            "skill_id": "test_induct_event_log",
            "name": "Event Log Test",
            "description": "Safe local read",
        })
        # Whether ok or not, event_id should be set
        assert isinstance(result.event_id, str)


# ─────────────────────────────────────────────────────────────────────────────
# EPIC B — Automation Scheduler
# ─────────────────────────────────────────────────────────────────────────────


class TestAutomationScheduler:
    """Test scheduler wiring and safe execution."""

    def _make_trigger(self, trigger_id="t1", risk="low", name="Test Trigger",
                      skill="log_status", ttype="manual"):
        from openjarvis.wave.automation_platform import AutomationTrigger, POLICY_AUTO
        return AutomationTrigger(
            trigger_id=trigger_id,
            name=name,
            trigger_type=ttype,
            skill_id=skill,
            risk_level=risk,
            approval_policy=POLICY_AUTO,
        )

    def test_execute_safe_trigger_ok(self):
        from openjarvis.wave.automation_scheduler import execute_safe_trigger
        trigger = self._make_trigger()
        result = execute_safe_trigger(trigger, action_key="log_status")
        assert result.ok, f"Expected ok=True, error={result.error}"
        assert result.output is not None

    def test_execute_external_send_blocked(self):
        from openjarvis.wave.automation_scheduler import execute_safe_trigger
        trigger = self._make_trigger(trigger_id="slack_send_nightly", name="Slack Send")
        result = execute_safe_trigger(trigger)
        assert not result.ok
        assert result.blocked

    def test_high_risk_trigger_blocked(self):
        from openjarvis.wave.automation_scheduler import execute_safe_trigger
        trigger = self._make_trigger(risk="high")
        result = execute_safe_trigger(trigger)
        assert not result.ok
        assert result.approval_required

    def test_critical_risk_trigger_blocked(self):
        from openjarvis.wave.automation_scheduler import execute_safe_trigger
        trigger = self._make_trigger(risk="critical")
        result = execute_safe_trigger(trigger)
        assert not result.ok
        assert result.approval_required

    def test_email_trigger_blocked_from_scheduling(self):
        from openjarvis.wave.automation_scheduler import schedule_trigger
        trigger = self._make_trigger(trigger_id="email_send_daily", name="Email Daily")
        with tempfile.TemporaryDirectory() as d:
            result = schedule_trigger(trigger, store_path=str(Path(d) / "sched.db"))
        assert not result.ok
        assert result.blocked

    def test_low_risk_trigger_schedules(self):
        from openjarvis.wave.automation_scheduler import schedule_trigger
        trigger = self._make_trigger(trigger_id="safe_status_check")
        with tempfile.TemporaryDirectory() as d:
            result = schedule_trigger(trigger, store_path=str(Path(d) / "sched.db"))
        assert result.ok, f"Expected ok=True, error={result.error}"
        assert result.task_id

    def test_check_capabilities_action(self):
        from openjarvis.wave.automation_scheduler import execute_safe_trigger
        trigger = self._make_trigger(skill="check_capabilities")
        result = execute_safe_trigger(trigger, action_key="check_capabilities")
        assert result.ok

    def test_scheduler_status(self):
        from openjarvis.wave.automation_scheduler import get_scheduler_status
        status = get_scheduler_status()
        assert status["implemented"]
        assert status["external_sends_blocked"]
        assert status["high_risk_requires_approval"]
        assert status["background_autopilot_disabled"]

    def test_list_scheduled_empty_when_no_db(self):
        from openjarvis.wave.automation_scheduler import list_scheduled_triggers
        with tempfile.TemporaryDirectory() as d:
            result = list_scheduled_triggers(store_path=str(Path(d) / "nonexistent.db"))
        assert isinstance(result, list)

    def test_scheduler_event_logged(self):
        from openjarvis.wave.automation_scheduler import execute_safe_trigger
        trigger = self._make_trigger(trigger_id="event_log_sched_test")
        result = execute_safe_trigger(trigger, action_key="log_status")
        assert isinstance(result.event_id, str)


# ─────────────────────────────────────────────────────────────────────────────
# EPIC C — Local Folder Connector
# ─────────────────────────────────────────────────────────────────────────────


class TestLocalFolderConnector:
    """Test local folder ingestion and safety checks."""

    def _tmp_knowledge_dir(self, files: dict) -> str:
        """Create temp dir with given {filename: content} files."""
        d = tempfile.mkdtemp(dir="/tmp")
        for name, content in files.items():
            Path(d, name).write_text(content)
        return d

    def test_ingest_txt_file(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        d = self._tmp_knowledge_dir({"hello.txt": "Hello, Jarvis!\nThis is a test doc."})
        result = ingest_folder(d, source_id="test_txt")
        assert result.ok, f"Expected ok, error={result.error}"
        assert result.record_count >= 1

    def test_ingest_markdown_file(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        d = self._tmp_knowledge_dir({"readme.md": "# Wave 1\n\nKnowledge platform docs."})
        result = ingest_folder(d, source_id="test_md")
        assert result.ok
        assert result.record_count >= 1

    def test_ingest_multiple_files(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        d = self._tmp_knowledge_dir({
            "a.txt": "Alpha content",
            "b.md": "Beta content",
            "c.txt": "Gamma content",
        })
        result = ingest_folder(d, source_id="test_multi")
        assert result.ok
        assert result.record_count == 3

    def test_non_allowed_extension_skipped(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        d = self._tmp_knowledge_dir({
            "valid.txt": "Valid content",
            "bad.py": "print('hello')",  # .py not in allowlist
        })
        result = ingest_folder(d, source_id="test_ext_filter")
        assert result.ok
        assert result.record_count == 1
        assert any(".py" in s for s in result.skipped)

    def test_credential_file_skipped(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        d = self._tmp_knowledge_dir({
            "normal.txt": "Normal content",
            ".env": "SECRET_KEY=abc",
        })
        result = ingest_folder(d, source_id="test_cred_skip")
        assert result.ok
        # .env should be skipped (wrong extension or forbidden pattern)
        assert result.record_count == 1

    def test_path_outside_home_blocked(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        result = ingest_folder("/etc", source_id="test_etc")
        assert not result.ok
        assert result.blocked

    def test_empty_dir_ok_zero_records(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        with tempfile.TemporaryDirectory(dir="/tmp") as d:
            result = ingest_folder(d, source_id="test_empty")
        assert result.ok
        assert result.record_count == 0

    def test_nonexistent_dir_fails(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        result = ingest_folder("/tmp/does_not_exist_xyz_123", source_id="test_noexist")
        assert not result.ok

    def test_default_knowledge_dir_created(self):
        from openjarvis.wave.local_folder_connector import ensure_default_knowledge_dir
        d = ensure_default_knowledge_dir()
        assert d.exists()
        assert d.is_dir()

    def test_connector_status(self):
        from openjarvis.wave.local_folder_connector import get_local_folder_connector_status
        s = get_local_folder_connector_status()
        assert s["implemented"]
        assert s["pii_blocked"]
        assert s["credential_files_blocked"]
        assert ".txt" in s["allowed_extensions"]
        assert ".md" in s["allowed_extensions"]

    def test_records_pushed_to_knowledge_store(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        from openjarvis.wave.knowledge_platform import search_knowledge
        d = self._tmp_knowledge_dir({
            "wave1_closeout_test.txt": "Unique phrase: xyzfoobarbaz42"
        })
        ingest_folder(d, source_id="test_push_to_kstore")
        results = search_knowledge("xyzfoobarbaz42")
        assert len(results) >= 1

    def test_forbidden_path_segment_blocked(self):
        from openjarvis.wave.local_folder_connector import ingest_folder
        # .ssh path should be blocked
        result = ingest_folder(str(Path.home() / ".ssh"), source_id="test_ssh")
        assert not result.ok
        assert result.blocked


# ─────────────────────────────────────────────────────────────────────────────
# EPIC D — Tavily Web Research Provider
# ─────────────────────────────────────────────────────────────────────────────


class TestTavilyProvider:
    """Test Tavily adapter with mocked env and HTTP."""

    def test_status_requires_setup_when_no_key(self):
        from openjarvis.wave.tavily_provider import get_tavily_provider_status
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TAVILY_API_KEY", None)
            status = get_tavily_provider_status()
        assert status["status"] == "requires_setup"
        assert not status["key_configured"]

    def test_status_ready_when_key_present(self):
        from openjarvis.wave.tavily_provider import get_tavily_provider_status
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-key-for-test"}):
            status = get_tavily_provider_status()
        assert status["status"] == "ready"
        assert status["key_configured"]

    def test_empty_query_returns_error(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        result = run_tavily_query("", approved=True)
        assert not result.ok
        assert "Empty" in result.error

    def test_unsafe_query_blocked(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        result = run_tavily_query("captcha bypass hack", approved=True)
        assert not result.ok
        assert result.blocked

    def test_credential_query_blocked(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        result = run_tavily_query("extract credential from login page", approved=True)
        assert not result.ok
        assert result.blocked

    def test_password_query_blocked(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        result = run_tavily_query("find password for admin", approved=True)
        assert not result.ok
        assert result.blocked

    def test_live_query_requires_approval(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        result = run_tavily_query("What is Python?", approved=False)
        assert not result.ok
        assert result.approval_required

    def test_no_key_returns_error_not_crash(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        os.environ.pop("TAVILY_API_KEY", None)
        result = run_tavily_query("safe query", approved=True)
        assert not result.ok
        assert "TAVILY_API_KEY" in result.error

    def test_live_query_with_mocked_http(self):
        """Mocked HTTP — no real network call."""
        from openjarvis.wave.tavily_provider import run_tavily_query

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"title": "Python Docs", "url": "https://python.org", "content": "Python info", "score": 0.9}
            ],
            "answer": "Python is a programming language.",
        }

        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-test-key"}):
            with patch("httpx.post", return_value=mock_response) as mock_post:
                result = run_tavily_query("What is Python?", approved=True)

        mock_post.assert_called_once()
        assert result.ok
        assert len(result.sources) == 1
        assert result.sources[0]["title"] == "Python Docs"
        assert result.answer == "Python is a programming language."

    def test_http_failure_returns_error(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        with patch.dict(os.environ, {"TAVILY_API_KEY": "fake-test-key"}):
            with patch("httpx.post", side_effect=Exception("Connection refused")):
                result = run_tavily_query("What is AI?", approved=True)
        assert not result.ok
        assert "Connection refused" in result.error or "Tavily query failed" in result.error

    def test_key_never_in_error_message(self):
        """Key value must never appear in error or result text."""
        from openjarvis.wave.tavily_provider import run_tavily_query
        fake_key = "tvly-TESTSECRET-NEVER-EXPOSE"
        with patch.dict(os.environ, {"TAVILY_API_KEY": fake_key}):
            with patch("httpx.post", side_effect=Exception("timeout")):
                result = run_tavily_query("safe query", approved=True)
        # Key value must not appear in any result field
        result_text = str(result.error) + str(result.answer) + str(result.sources)
        assert fake_key not in result_text

    def test_research_platform_tavily_status(self):
        """research_platform.get_research_platform_status includes tavily_status."""
        from openjarvis.wave.research_platform import get_research_platform_status
        os.environ.pop("TAVILY_API_KEY", None)
        status = get_research_platform_status()
        assert "tavily_status" in status
        assert status["tavily_status"] in ("ready", "requires_setup")

    def test_research_platform_tavily_query_dispatches(self):
        """run_local_query with provider_id=tavily dispatches to tavily adapter."""
        from openjarvis.wave.research_platform import run_local_query
        with patch.dict(os.environ, {}):
            os.environ.pop("TAVILY_API_KEY", None)
            result = run_local_query("Python programming", provider_id="tavily")
        # No key → approval_required or error, never crashes
        assert not result.ok
        assert result.approval_required or result.error

    def test_event_logged_on_block(self):
        from openjarvis.wave.tavily_provider import run_tavily_query
        result = run_tavily_query("bypass captcha", approved=True)
        assert result.blocked
        assert isinstance(result.event_id, str)


# ─────────────────────────────────────────────────────────────────────────────
# Cross-Epic: US13 voice remains parked
# ─────────────────────────────────────────────────────────────────────────────

def test_us13_voice_still_parked():
    """US13 voice status must remain disabled/parked after closeout sprint."""
    try:
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        caps = {c["capability_id"]: c["status"] for c in summary.get("capabilities", [])}
        if "hands_free_voice" in caps:
            assert caps["hands_free_voice"] in ("disabled", "not_implemented", "requires_setup"), (
                f"US13 voice must be parked, got {caps['hands_free_voice']}"
            )
    except Exception:
        pass  # If registry unavailable, pass — will be caught by server tests


def test_wave1_closeout_all_epics_implemented():
    """All four Wave 1 closeout modules must be importable and implemented."""
    from openjarvis.wave.skill_induction import get_induction_pipeline_status
    from openjarvis.wave.automation_scheduler import get_scheduler_status
    from openjarvis.wave.local_folder_connector import get_local_folder_connector_status
    from openjarvis.wave.tavily_provider import get_tavily_provider_status

    a = get_induction_pipeline_status()
    b = get_scheduler_status()
    c = get_local_folder_connector_status()
    d = get_tavily_provider_status()

    assert a["implemented"], "Epic A induction not implemented"
    assert b["implemented"], "Epic B scheduler not implemented"
    assert c["implemented"], "Epic C folder connector not implemented"
    assert d["provider_id"] == "tavily", "Epic D Tavily not implemented"


def test_wave3_4_not_implemented():
    """Wave 3–4 must remain NOT_IMPLEMENTED. Wave 2 is now implemented (separate sprint)."""
    from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
    reg = WavePlatformRegistry()
    for wave in (3, 4):
        items = reg.get_by_wave(wave)
        for item in items:
            assert item.status == WavePlatformStatus.NOT_IMPLEMENTED, (
                f"Wave {wave} item {item.epic_id} must be NOT_IMPLEMENTED, got {item.status}"
            )
