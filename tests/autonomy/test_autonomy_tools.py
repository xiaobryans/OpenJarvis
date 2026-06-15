"""Tests for autonomy tool catalog (registered in ToolRegistry).

Covers:
  - All 14 autonomy/watchdog/alert/mobile/voice tools are registered
  - All 14 are status=available
  - initialize_autonomy_catalog() is idempotent
  - autonomy.get_status executor returns project status
  - autonomy.set_mode executor sets mode correctly
  - autonomy.set_mode rejects invalid mode strings
  - watchdog.run_project_pack executor returns 8 results
  - watchdog.run_once executor runs a named watchdog
  - watchdog.list_ids executor returns 8 IDs
  - alert.create executor creates an alert
  - alert.list executor lists alerts
  - alert.acknowledge executor acks an alert
  - alert.resolve executor resolves an alert
  - alert.draft_slack_update send_status=not_sent, approval_required=True
  - alert.draft_telegram_update send_status=not_sent, approval_required=True
  - alert.daily_digest returns digest_text
  - mobile.status returns compact payload
  - voice.parse_intent returns intent + voice_status=not_implemented
  - unsafe actions (real_slack_send) are blocked by gateway
"""

from __future__ import annotations

import pytest

from openjarvis.autonomy.modes import AutonomyPolicy
from openjarvis.tools.catalog import initialize_catalog
from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus


EXPECTED_AUTONOMY_TOOLS = [
    "autonomy.get_status",
    "autonomy.set_mode",
    "watchdog.run_project_pack",
    "watchdog.run_once",
    "watchdog.list_ids",
    "alert.create",
    "alert.list",
    "alert.acknowledge",
    "alert.resolve",
    "alert.draft_slack_update",
    "alert.draft_telegram_update",
    "alert.daily_digest",
    "mobile.status",
    "voice.parse_intent",
]


@pytest.fixture(autouse=True)
def setup_catalog():
    ToolRegistry.clear()
    initialize_catalog()
    yield
    ToolRegistry.clear()


@pytest.fixture(autouse=True)
def reset_autonomy():
    AutonomyPolicy.clear()
    yield
    AutonomyPolicy.clear()


class TestAutonomyCatalogRegistration:
    def test_all_14_tools_registered(self):
        for tool_id in EXPECTED_AUTONOMY_TOOLS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None, f"Tool not registered: {tool_id}"

    def test_all_14_are_available(self):
        for tool_id in EXPECTED_AUTONOMY_TOOLS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None
            assert spec.implementation_status == ToolStatus.AVAILABLE, (
                f"{tool_id} should be available, got {spec.implementation_status}"
            )
            assert spec.is_available(), f"{tool_id}.is_available() returned False"

    def test_initialize_is_idempotent(self):
        from openjarvis.tools.autonomy_catalog import initialize_autonomy_catalog
        before = len(ToolRegistry.list_all())
        initialize_autonomy_catalog()
        after = len(ToolRegistry.list_all())
        assert before == after

    def test_tool_categories(self):
        categories = {
            "autonomy.get_status": "autonomy",
            "autonomy.set_mode": "autonomy",
            "watchdog.run_project_pack": "watchdog",
            "watchdog.run_once": "watchdog",
            "watchdog.list_ids": "watchdog",
            "alert.create": "alert",
            "alert.list": "alert",
            "alert.acknowledge": "alert",
            "alert.resolve": "alert",
            "alert.draft_slack_update": "alert",
            "alert.draft_telegram_update": "alert",
            "alert.daily_digest": "alert",
            "mobile.status": "mobile",
            "voice.parse_intent": "voice",
        }
        for tool_id, expected_cat in categories.items():
            spec = ToolRegistry.get(tool_id)
            assert spec.category == expected_cat, (
                f"{tool_id}: expected category={expected_cat}, got {spec.category}"
            )

    def test_total_tool_count_is_63(self):
        """US5: 49 tools. US6 adds 14. Total must be 63."""
        total = len(ToolRegistry.list_all())
        assert total == 63, f"Expected 63 total tools, got {total}"

    def test_available_count_is_60(self):
        """US5: 46 available. US6 adds 14 available. Total available must be 60."""
        available = len(ToolRegistry.list_available())
        assert available == 60, f"Expected 60 available tools, got {available}"


class TestAutonomyExecutors:
    def _exec(self, tool_id, inputs=None, ctx=None):
        executor = ToolRegistry.get_executor(tool_id)
        assert executor is not None, f"No executor for {tool_id}"
        return executor(inputs or {}, ctx or {})

    def test_autonomy_get_status(self):
        result = self._exec("autonomy.get_status", {"project_id": "omnix"})
        assert result["project_id"] == "omnix"
        assert "mode" in result
        assert result["mode"] == "observe_only"
        assert result["hard_gates_always_blocked"] is True

    def test_autonomy_set_mode_valid(self):
        result = self._exec("autonomy.set_mode", {
            "project_id": "omnix",
            "mode": "propose_only",
            "set_by": "test",
            "reason": "testing"
        })
        assert result["ok"] is True
        assert result["mode"] == "propose_only"
        assert result["hard_gates_always_blocked"] is True
        assert result["real_send_always_blocked"] is True

    def test_autonomy_set_mode_invalid_raises(self):
        executor = ToolRegistry.get_executor("autonomy.set_mode")
        with pytest.raises(ValueError, match="Invalid mode"):
            executor({"mode": "totally_fake_mode"}, {})

    def test_autonomy_set_mode_does_not_allow_unsafe(self):
        """Even after setting safe_execute_approved, hard gates stay blocked."""
        from openjarvis.autonomy.modes import AutonomyMode
        self._exec("autonomy.set_mode", {
            "project_id": "omnix",
            "mode": "safe_execute_approved",
        })
        assert AutonomyPolicy.can_auto_execute("omnix", "real_slack_send") is False
        assert AutonomyPolicy.can_auto_execute("omnix", "omnix_production_deploy") is False

    def test_watchdog_list_ids(self):
        result = self._exec("watchdog.list_ids")
        assert result["count"] == 8
        assert len(result["watchdog_ids"]) == 8

    def test_watchdog_run_project_pack(self):
        result = self._exec("watchdog.run_project_pack", {"project_id": "omnix"})
        assert result["project_id"] == "omnix"
        assert result["watchdogs_run"] == 8
        assert "summary" in result
        assert "results" in result
        assert len(result["results"]) == 8

    def test_watchdog_run_once_named(self):
        result = self._exec("watchdog.run_once", {
            "watchdog_id": "backend_health_watchdog",
            "project_id": "omnix",
        })
        assert result["id"] == "backend_health_watchdog"
        assert "evidence" in result

    def test_watchdog_run_once_missing_id_raises(self):
        executor = ToolRegistry.get_executor("watchdog.run_once")
        with pytest.raises(ValueError, match="watchdog_id is required"):
            executor({}, {})

    def test_alert_create(self):
        result = self._exec("alert.create", {
            "project_id": "omnix",
            "title": "Test Alert",
            "evidence": "Tool failure detected",
            "severity": "warning",
        })
        assert result["ok"] is True
        assert result["alert"]["title"] == "Test Alert"
        assert result["alert"]["status"] == "open"

    def test_alert_create_missing_title_raises(self):
        executor = ToolRegistry.get_executor("alert.create")
        with pytest.raises(ValueError, match="title is required"):
            executor({"evidence": "ev"}, {})

    def test_alert_create_missing_evidence_raises(self):
        executor = ToolRegistry.get_executor("alert.create")
        with pytest.raises(ValueError, match="evidence is required"):
            executor({"title": "t"}, {})

    def test_alert_list(self):
        self._exec("alert.create", {
            "project_id": "omnix", "title": "T", "evidence": "E"
        })
        result = self._exec("alert.list", {"project_id": "omnix"})
        assert result["count"] >= 1
        assert result["project_id"] == "omnix"

    def test_alert_acknowledge(self):
        created = self._exec("alert.create", {
            "project_id": "omnix", "title": "T", "evidence": "E"
        })
        alert_id = created["alert"]["alert_id"]
        result = self._exec("alert.acknowledge", {"alert_id": alert_id})
        assert result["ok"] is True
        assert result["alert"]["status"] == "acknowledged"

    def test_alert_resolve(self):
        created = self._exec("alert.create", {
            "project_id": "omnix", "title": "T", "evidence": "E"
        })
        alert_id = created["alert"]["alert_id"]
        result = self._exec("alert.resolve", {"alert_id": alert_id})
        assert result["ok"] is True
        assert result["alert"]["status"] == "resolved"

    def test_alert_draft_slack_never_sends(self):
        result = self._exec("alert.draft_slack_update", {"project_id": "omnix"})
        assert result["send_status"] == "not_sent"
        assert result["approval_required"] is True
        assert "draft_text" in result

    def test_alert_draft_telegram_never_sends(self):
        result = self._exec("alert.draft_telegram_update", {"project_id": "omnix"})
        assert result["send_status"] == "not_sent"
        assert result["approval_required"] is True
        assert "draft_text" in result

    def test_alert_daily_digest(self):
        self._exec("alert.create", {
            "project_id": "omnix", "title": "T", "evidence": "E", "severity": "error"
        })
        result = self._exec("alert.daily_digest", {"project_id": "omnix"})
        assert "digest_text" in result
        assert "open_count" in result
        assert "acknowledged_count" in result
        assert result["project_id"] == "omnix"

    def test_mobile_status(self):
        result = self._exec("mobile.status", {"project_id": "omnix"})
        assert result["project_id"] == "omnix"
        assert "autonomy_mode" in result
        assert "tools" in result
        assert "alerts" in result
        assert "watchdogs" in result
        assert result["watchdogs"]["registered"] == 8
        assert result["mobile_payload_version"] == "1.0"

    def test_voice_parse_intent_known(self):
        result = self._exec("voice.parse_intent", {"text": "show alerts"})
        assert result["intent"] == "show_alerts"
        assert result["confidence"] > 0
        assert result["voice_status"] == "not_implemented"
        assert "blocker" in result
        assert "STT" in result["blocker"] or "speech" in result["blocker"].lower()

    def test_voice_parse_intent_unknown(self):
        result = self._exec("voice.parse_intent", {"text": "xyz_unknown_gibberish_abc"})
        assert result["intent"] == "unknown"
        assert result["voice_status"] == "not_implemented"

    def test_voice_parse_intent_missing_text_raises(self):
        executor = ToolRegistry.get_executor("voice.parse_intent")
        with pytest.raises(ValueError, match="text is required"):
            executor({}, {})


class TestGatewayGovernanceBlocks:
    """Prove gateway blocks unsafe auto-actions regardless of tool catalog."""

    def test_real_slack_send_blocked_by_governance(self):
        from openjarvis.tools.gateway import get_gateway
        gateway = get_gateway()
        result = gateway.execute(
            "slack.notify_mission",
            inputs={},
            project_id="omnix",
        )
        assert result.ok is False
        assert result.outcome in ("not_configured", "blocked", "hard_gate")

    def test_autonomy_tools_not_governance_blocked(self):
        """autonomy/watchdog/alert tools must pass governance (low risk, no hard gate)."""
        from openjarvis.tools.gateway import get_gateway
        gateway = get_gateway()
        result = gateway.execute(
            "autonomy.get_status",
            inputs={"project_id": "omnix"},
            project_id="omnix",
        )
        assert result.ok is True
        assert result.outcome == "success"
