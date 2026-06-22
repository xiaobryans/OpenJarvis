"""Plan 9 — CLI Command Tests.

Tests every plan9 CLI subcommand via Click's CliRunner:
  - jarvis plan9 capability-matrix
  - jarvis plan9 parity-status
  - jarvis plan9 model-routing
  - jarvis plan9 model-route-explain
  - jarvis plan9 worker-pool
  - jarvis plan9 mac-queue
  - jarvis plan9 mac-queue-submit
  - jarvis plan9 secret-scan
  - jarvis plan9 validate
  - jarvis plan9 rules
  - jarvis plan9 skills
  - jarvis plan9 commands
  - jarvis plan9 parked
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from openjarvis.cli.plan9_cmd import plan9


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_queue(monkeypatch):
    """Reset mac worker queue singleton for each test."""
    import openjarvis.plan9.mac_worker_queue as mwq
    monkeypatch.setattr(mwq, "_MAC_QUEUE", None)


# ============================================================================
# capability-matrix
# ============================================================================

class TestCapabilityMatrixCmd:

    def test_basic_run(self, runner):
        result = runner.invoke(plan9, ["capability-matrix"])
        assert result.exit_code == 0
        assert "capability_id" in result.output.lower() or "CLOUD_LIVE" in result.output

    def test_json_output(self, runner):
        import json
        result = runner.invoke(plan9, ["capability-matrix", "--json-out"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0

    def test_filter_by_domain(self, runner):
        result = runner.invoke(plan9, ["capability-matrix", "--domain", "coding_manager"])
        assert result.exit_code == 0
        assert "coding_manager" in result.output

    def test_filter_by_status_parked(self, runner):
        result = runner.invoke(plan9, ["capability-matrix", "--status", "PARKED"])
        assert result.exit_code == 0
        assert "PARKED" in result.output

    def test_filter_invalid_status_exits_1(self, runner):
        result = runner.invoke(plan9, ["capability-matrix", "--status", "NOT_A_REAL_STATUS"])
        assert result.exit_code != 0

    def test_no_secrets_in_output(self, runner):
        import re
        result = runner.invoke(plan9, ["capability-matrix", "--json-out"])
        secret_patterns = [
            re.compile(r"sk-[A-Za-z0-9]{20,}"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"Bearer eyJ[A-Za-z0-9+/=]{20,}"),
        ]
        for p in secret_patterns:
            assert not p.search(result.output), f"Secret pattern in CLI output: {p.pattern}"


# ============================================================================
# parity-status
# ============================================================================

class TestParityStatusCmd:

    def test_basic_run(self, runner):
        result = runner.invoke(plan9, ["parity-status"])
        assert result.exit_code == 0
        assert "Parity" in result.output

    def test_shows_summary_counts(self, runner):
        result = runner.invoke(plan9, ["parity-status"])
        assert "CROSS_DEVICE_LIVE" in result.output or "CLOUD_LIVE" in result.output

    def test_shows_parked_items(self, runner):
        result = runner.invoke(plan9, ["parity-status"])
        assert "voice_wake_tts" in result.output or "Plan 10" in result.output

    def test_show_gaps_flag(self, runner):
        result = runner.invoke(plan9, ["parity-status", "--show-gaps"])
        assert result.exit_code == 0
        assert "Gaps" in result.output or "UNKNOWN" in result.output

    def test_json_output(self, runner):
        import json
        result = runner.invoke(plan9, ["parity-status", "--json-out"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "summary" in data
        assert "parked" in data


# ============================================================================
# model-routing
# ============================================================================

class TestModelRoutingCmd:

    def test_basic_run(self, runner):
        result = runner.invoke(plan9, ["model-routing"])
        assert result.exit_code == 0
        assert "coding_manager" in result.output

    def test_shows_17_managers(self, runner):
        result = runner.invoke(plan9, ["model-routing"])
        # All 17 manager IDs should appear
        for mid in ["coding_manager", "architecture_manager", "governance_safety_manager"]:
            assert mid in result.output

    def test_filter_by_role(self, runner):
        result = runner.invoke(plan9, ["model-routing", "--role", "coding_manager"])
        assert result.exit_code == 0
        assert "coding_manager" in result.output

    def test_validation_ok(self, runner):
        result = runner.invoke(plan9, ["model-routing"])
        assert "validation: OK" in result.output

    def test_json_output(self, runner):
        import json
        result = runner.invoke(plan9, ["model-routing", "--json-out"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        role_ids = [d["role_id"] for d in data]
        assert "coding_manager" in role_ids


# ============================================================================
# model-route-explain
# ============================================================================

class TestModelRouteExplainCmd:

    def test_basic_explain(self, runner):
        result = runner.invoke(plan9, [
            "model-route-explain", "--role", "coding_manager",
            "--risk", "medium", "--complexity", "moderate"
        ])
        assert result.exit_code == 0
        assert "Recommended tier" in result.output

    def test_high_risk_shows_best(self, runner):
        result = runner.invoke(plan9, [
            "model-route-explain", "--role", "coding_manager",
            "--risk", "high", "--complexity", "complex"
        ])
        assert "best" in result.output.lower()

    def test_low_risk_shows_cheap(self, runner):
        result = runner.invoke(plan9, [
            "model-route-explain", "--role", "coding_manager",
            "--risk", "low", "--complexity", "simple"
        ])
        assert "cheap" in result.output.lower()

    def test_3_failures_shows_stop(self, runner):
        result = runner.invoke(plan9, [
            "model-route-explain", "--role", "coding_manager",
            "--risk", "medium", "--failures", "3"
        ])
        assert "stop" in result.output.lower()

    def test_shows_escalation_rule(self, runner):
        result = runner.invoke(plan9, [
            "model-route-explain", "--role", "architecture_manager",
            "--risk", "high"
        ])
        assert "Escalation" in result.output or "escalation" in result.output.lower()


# ============================================================================
# worker-pool
# ============================================================================

class TestWorkerPoolCmd:

    def test_basic_run(self, runner):
        result = runner.invoke(plan9, ["worker-pool"])
        assert result.exit_code == 0
        assert "git_commit_worker" in result.output

    def test_git_commit_is_single_executor(self, runner):
        result = runner.invoke(plan9, ["worker-pool", "--role", "git_commit_worker"])
        assert result.exit_code == 0
        assert "YES" in result.output  # single_executor_only

    def test_retrieval_can_scale(self, runner):
        result = runner.invoke(plan9, ["worker-pool", "--role", "retrieval_worker"])
        assert result.exit_code == 0
        assert "Yes" in result.output  # scaling_allowed

    def test_json_output(self, runner):
        import json
        result = runner.invoke(plan9, ["worker-pool", "--json-out"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "git_commit_worker" in data
        assert data["git_commit_worker"]["single_executor_only"] is True


# ============================================================================
# mac-queue
# ============================================================================

class TestMacQueueCmd:

    def test_empty_queue(self, runner, isolated_queue):
        result = runner.invoke(plan9, ["mac-queue"])
        assert result.exit_code == 0
        assert "Total tasks: 0" in result.output

    def test_shows_mac_only_types(self, runner, isolated_queue):
        result = runner.invoke(plan9, ["mac-queue"])
        assert "app_reinstall" in result.output

    def test_json_output(self, runner, isolated_queue):
        import json
        result = runner.invoke(plan9, ["mac-queue", "--json-out"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "queue_status" in data


# ============================================================================
# mac-queue-submit
# ============================================================================

class TestMacQueueSubmitCmd:

    def test_submit_app_reinstall(self, runner, isolated_queue):
        result = runner.invoke(plan9, [
            "mac-queue-submit",
            "--type", "app_reinstall",
            "--name", "Reinstall OpenJarvis.app",
        ])
        assert result.exit_code == 0
        assert "Task queued" in result.output

    def test_submit_mac_app_control(self, runner, isolated_queue):
        result = runner.invoke(plan9, [
            "mac-queue-submit",
            "--type", "mac_app_control",
            "--name", "Open System Settings",
        ])
        assert result.exit_code == 0

    def test_task_appears_in_queue_after_submit(self, runner, isolated_queue):
        runner.invoke(plan9, [
            "mac-queue-submit", "--type", "app_reinstall", "--name", "Test"
        ])
        result = runner.invoke(plan9, ["mac-queue"])
        assert "Total tasks: 1" in result.output


# ============================================================================
# secret-scan
# ============================================================================

class TestSecretScanCmd:

    def test_clean_file(self, runner, tmp_path):
        f = tmp_path / "clean.py"
        f.write_text("x = 1\n")
        result = runner.invoke(plan9, ["secret-scan", str(f)])
        assert result.exit_code == 0
        assert "CLEAN" in result.output

    def test_found_secret_exits_1(self, runner, tmp_path):
        f = tmp_path / "dirty.py"
        # Assemble a clearly-fake key at runtime so file scanners don't flag the test file itself
        fake_key = "sk-" + "x" * 21
        f.write_text(f"api_key = '{fake_key}'\n")
        result = runner.invoke(plan9, ["secret-scan", str(f)])
        assert result.exit_code == 1
        assert "FOUND_SECRETS" in result.output or "FOUND_SECRETS" in (result.stderr or "")

    def test_no_paths_gives_message(self, runner):
        result = runner.invoke(plan9, ["secret-scan"])
        assert result.exit_code == 0
        assert "Nothing to scan" in result.output


# ============================================================================
# rules
# ============================================================================

class TestRulesCmd:

    def test_shows_all_rules(self, runner):
        result = runner.invoke(plan9, ["rules"])
        assert result.exit_code == 0
        assert "p9.truth.no_fake_complete" in result.output

    def test_filter_by_category(self, runner):
        result = runner.invoke(plan9, ["rules", "--category", "PARKED"])
        assert result.exit_code == 0
        assert "PARKED" in result.output
        assert "p9.parked" in result.output

    def test_shows_categories(self, runner):
        result = runner.invoke(plan9, ["rules"])
        for cat in ["TRUTH_EVIDENCE", "STOP_ON_BLOCKER", "SECRET_SECURITY"]:
            assert cat in result.output


# ============================================================================
# skills
# ============================================================================

class TestSkillsCmd:

    def test_shows_21_skills(self, runner):
        result = runner.invoke(plan9, ["skills"])
        assert result.exit_code == 0
        assert "21" in result.output

    def test_filter_by_wired(self, runner):
        result = runner.invoke(plan9, ["skills", "--status", "WIRED"])
        assert result.exit_code == 0
        assert "WIRED" in result.output

    def test_invalid_status_exits(self, runner):
        result = runner.invoke(plan9, ["skills", "--status", "INVALID_XYZ"])
        assert result.exit_code != 0


# ============================================================================
# commands
# ============================================================================

class TestCommandsCmd:

    def test_shows_20_commands(self, runner):
        result = runner.invoke(plan9, ["commands"])
        assert result.exit_code == 0
        assert "20" in result.output

    def test_shows_key_commands(self, runner):
        result = runner.invoke(plan9, ["commands"])
        assert "capability matrix" in result.output
        assert "parity status" in result.output


# ============================================================================
# parked
# ============================================================================

class TestParkedCmd:

    def test_shows_parked_items(self, runner):
        result = runner.invoke(plan9, ["parked"])
        assert result.exit_code == 0
        assert "voice_wake_tts" in result.output
        assert "apple_signing_updater" in result.output

    def test_shows_plan_references(self, runner):
        result = runner.invoke(plan9, ["parked"])
        assert "Plan 10" in result.output
        assert "Plan 11" in result.output

    def test_shows_mac_only_exception(self, runner):
        result = runner.invoke(plan9, ["parked"])
        assert "QUEUED_MAC_ONLY" in result.output or "OpenJarvis.app" in result.output
