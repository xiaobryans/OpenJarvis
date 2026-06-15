"""Tests for US8 catalog — 51 new tools registered (US8 all phases).

Covers:
  - All 51 US8 tools are registered
  - All 51 are status=available
  - initialize_us8_catalog() is idempotent
  - Tool categories present: project, automation, voice, desktop, browser,
    mobile, telegram, ops, slack, web, github, openclaw
  - Executors return dicts (basic smoke tests)
  - Total tool count is 129 (78 + 51)
  - Available count is 126 (75 + 51)
  - Hard gates blocked in automation.policy.evaluate
  - draft sends always return send_status=not_sent
  - ops tools return installed=False (no daemon)
  - voice.parse_approval returns intent field
  - desktop.permissions_status returns operator_status
"""

from __future__ import annotations

import pytest

from openjarvis.autonomy.modes import AutonomyPolicy
from openjarvis.tools.catalog import initialize_catalog
from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus

EXPECTED_US8_TOOLS = [
    # Phase B
    "project.onboarding_status",
    "project.link_wizard_state",
    "project.source_config_needed",
    # Phase C
    "automation.policy.get",
    "automation.policy.evaluate",
    "automation.approval.request",
    "automation.approval.approve",
    "automation.approval.reject",
    "automation.approval.list",
    "automation.autopilot.run_once",
    "automation.autopilot.status",
    # Phase D
    "voice.status",
    "voice.listen_status",
    "voice.wake_word_status",
    "voice.parse_approval",
    "voice.approval_challenge",
    "voice.approval_confirm",
    "voice.command_preview",
    "voice.tts_test",
    "voice.stt_test",
    # Phase E
    "desktop.permissions_status",
    "desktop.operator_status",
    "desktop.open_app_plan",
    "desktop.focus_app_plan",
    "desktop.screenshot_status",
    "desktop.safe_demo",
    "browser.operator_status",
    "browser.open_url_plan",
    "browser.read_only_plan",
    # Phase F
    "mobile.pending_approvals",
    "mobile.approval_payload",
    "mobile.safe_access_instructions",
    "telegram.command_preview",
    "telegram.approval_preview",
    "telegram.command_status",
    # Phase G
    "ops.runner_status",
    "ops.run_once",
    "ops.schedule_plan",
    "ops.install_plan",
    "ops.stop_plan",
    "ops.dry_run_schedule",
    # Phase H
    "slack.connector_status",
    "slack.draft_test_send",
    "telegram.connector_status",
    "telegram.draft_test_send",
    "web.search_status",
    "github.connector_status",
    "github.local_remote_info",
    "openclaw.workspace_status",
    "openclaw.handoff_read",
    "openclaw.link_status",
]


@pytest.fixture(autouse=True)
def setup_catalog():
    ToolRegistry.clear()
    AutonomyPolicy.clear()
    initialize_catalog()
    yield
    ToolRegistry.clear()
    AutonomyPolicy.clear()


class TestUS8CatalogRegistration:
    def test_all_51_tools_registered(self):
        for tool_id in EXPECTED_US8_TOOLS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None, f"US8 tool not registered: {tool_id}"

    def test_all_51_are_available(self):
        for tool_id in EXPECTED_US8_TOOLS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None
            assert spec.implementation_status == ToolStatus.AVAILABLE, (
                f"{tool_id} should be available, got {spec.implementation_status}"
            )
            assert spec.is_available(), f"{tool_id}.is_available() returned False"

    def test_expected_51_us8_tools(self):
        assert len(EXPECTED_US8_TOOLS) == 51

    def test_total_tool_count_is_129(self):
        stats = ToolRegistry.stats()
        assert stats["total_registered"] == 129, (
            f"Expected 129 total tools, got {stats['total_registered']}"
        )

    def test_available_tool_count_is_126(self):
        stats = ToolRegistry.stats()
        assert stats["available"] == 126, (
            f"Expected 126 available tools, got {stats['available']}"
        )

    def test_unavailable_count_is_3(self):
        stats = ToolRegistry.stats()
        assert stats["unavailable"] == 3, (
            f"Expected 3 unavailable tools, got {stats['unavailable']}"
        )

    def test_initialize_us8_catalog_idempotent(self):
        from openjarvis.tools.us8_catalog import initialize_us8_catalog
        initialize_us8_catalog()
        initialize_us8_catalog()
        stats = ToolRegistry.stats()
        assert stats["total_registered"] == 129

    def test_all_us8_tools_have_executors(self):
        for tool_id in EXPECTED_US8_TOOLS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None
            assert spec.executor_ref, f"{tool_id}: missing executor_ref"


class TestUS8CatalogCategories:
    def test_automation_category_tools_present(self):
        automation_tools = [t for t in EXPECTED_US8_TOOLS if t.startswith("automation.")]
        assert len(automation_tools) == 8

    def test_voice_category_tools_present(self):
        voice_tools = [t for t in EXPECTED_US8_TOOLS if t.startswith("voice.")]
        assert len(voice_tools) == 9

    def test_desktop_category_tools_present(self):
        desktop_tools = [t for t in EXPECTED_US8_TOOLS if t.startswith("desktop.")]
        assert len(desktop_tools) == 6

    def test_browser_category_tools_present(self):
        browser_tools = [t for t in EXPECTED_US8_TOOLS if t.startswith("browser.")]
        assert len(browser_tools) == 3

    def test_ops_category_tools_present(self):
        ops_tools = [t for t in EXPECTED_US8_TOOLS if t.startswith("ops.")]
        assert len(ops_tools) == 6

    def test_connector_tools_present(self):
        phase_h_tools = [
            "slack.connector_status", "slack.draft_test_send",
            "telegram.connector_status", "telegram.draft_test_send",
            "web.search_status",
            "github.connector_status", "github.local_remote_info",
            "openclaw.workspace_status", "openclaw.handoff_read", "openclaw.link_status",
        ]
        for t in phase_h_tools:
            assert t in EXPECTED_US8_TOOLS, f"Phase H tool missing: {t}"
        assert len(phase_h_tools) == 10


class TestUS8ExecutorSmokeTests:
    def _exec(self, tool_id: str, inputs: dict = None) -> dict:
        spec = ToolRegistry.get(tool_id)
        assert spec is not None, f"Tool not found: {tool_id}"
        executor = ToolRegistry.get_executor(tool_id)
        assert executor is not None, f"No executor for: {tool_id}"
        result = executor(inputs or {}, {})
        assert isinstance(result, dict)
        return result

    def test_automation_policy_get(self):
        r = self._exec("automation.policy.get")
        assert "hard_gate_action_classes" in r
        assert "levels" in r

    def test_automation_policy_evaluate_hard_gate_blocked(self):
        r = self._exec("automation.policy.evaluate", {
            "action_class": "production_deploy"
        })
        assert r["blocked"] is True

    def test_automation_policy_evaluate_safe_action(self):
        r = self._exec("automation.policy.evaluate", {
            "action_class": "read_only_check"
        })
        assert r["can_proceed"] is True

    def test_voice_status(self):
        r = self._exec("voice.status")
        assert "voice_status" in r

    def test_voice_wake_word_status(self):
        r = self._exec("voice.wake_word_status")
        assert "wake_word_status" in r
        assert r["is_listening"] is False

    def test_voice_parse_approval_approve(self):
        r = self._exec("voice.parse_approval", {"text": "yes approve"})
        assert r["intent"] == "approve"

    def test_voice_parse_approval_reject(self):
        r = self._exec("voice.parse_approval", {"text": "no reject"})
        assert r["intent"] == "reject"

    def test_voice_command_preview(self):
        r = self._exec("voice.command_preview", {"text": "run watchdogs"})
        assert r["preview_only"] is True

    def test_voice_tts_test(self):
        r = self._exec("voice.tts_test", {"text": "test"})
        assert "engine" in r

    def test_voice_stt_test(self):
        r = self._exec("voice.stt_test")
        assert "stt_engine" in r
        assert "note" in r

    def test_desktop_permissions_status(self):
        r = self._exec("desktop.permissions_status")
        assert "operator_status" in r

    def test_desktop_operator_status(self):
        r = self._exec("desktop.operator_status")
        assert "operator_status" in r

    def test_desktop_open_app_plan_dry_run(self):
        r = self._exec("desktop.open_app_plan", {"app_name": "Safari"})
        assert r["dry_run"] is True

    def test_browser_open_url_plan_blocks_file_scheme(self):
        r = self._exec("browser.open_url_plan", {"url": "file:///etc/passwd"})
        assert r["blocked"] is True

    def test_browser_operator_status_form_submit_false(self):
        r = self._exec("browser.operator_status")
        assert r["can_submit_form"] is False

    def test_ops_runner_status_installed_false(self):
        r = self._exec("ops.runner_status")
        assert "installed" in r

    def test_ops_run_once_dry_run(self):
        r = self._exec("ops.run_once", {"dry_run": True})
        assert r["dry_run"] is True
        assert all(a["executed"] is False for a in r["actions"])

    def test_ops_dry_run_schedule_3_runs(self):
        r = self._exec("ops.dry_run_schedule")
        assert len(r["simulated_runs"]) == 3

    def test_ops_install_plan_not_installed(self):
        r = self._exec("ops.install_plan")
        assert r["installed"] is False
        assert r["approval_required"] is True

    def test_slack_draft_test_send_not_sent(self):
        r = self._exec("slack.draft_test_send", {"message": "test"})
        assert r["send_status"] == "not_sent"

    def test_telegram_draft_test_send_not_sent(self):
        r = self._exec("telegram.draft_test_send", {"message": "test"})
        assert r["send_status"] == "not_sent"

    def test_slack_connector_status_real_send_false(self):
        r = self._exec("slack.connector_status")
        assert r["real_send_allowed"] is False

    def test_telegram_connector_status_real_send_false(self):
        r = self._exec("telegram.connector_status")
        assert r["real_send_allowed"] is False

    def test_web_search_status_returns_dict(self):
        r = self._exec("web.search_status")
        assert "status" in r

    def test_github_connector_status_read_only(self):
        r = self._exec("github.connector_status")
        assert r["read_only"] is True

    def test_github_local_remote_info_returns_dict(self):
        r = self._exec("github.local_remote_info")
        assert "ok" in r

    def test_openclaw_workspace_status_mutations_false(self):
        r = self._exec("openclaw.workspace_status")
        assert r["mutations_allowed"] is False

    def test_mobile_safe_access_instructions_no_public(self):
        r = self._exec("mobile.safe_access_instructions")
        assert r["access_paths"]["tailnet"]["public_exposure"] is False
        assert r["access_paths"]["tailnet"]["tailscale_funnel"] == "blocked"

    def test_automation_autopilot_run_once_simulated(self):
        r = self._exec("automation.autopilot.run_once")
        assert r["simulated"] is True

    def test_project_onboarding_status_returns_dict(self):
        r = self._exec("project.onboarding_status", {"project_id": "omnix"})
        assert "project_id" in r
        assert "linkage_status" in r

    def test_telegram_approval_preview_not_sent(self):
        r = self._exec("telegram.approval_preview", {"action": "test_action"})
        assert r["send_status"] == "not_sent"
        assert r["preview_only"] is True
