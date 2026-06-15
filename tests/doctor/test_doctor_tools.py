"""Tests for Jarvis Doctor tool catalog — 5 doctor/readiness tools.

Covers:
  - All 5 tools registered and available after initialize_doctor_catalog()
  - initialize_doctor_catalog() is idempotent (safe to call twice)
  - tool_ids: doctor.run, doctor.project, doctor.report,
              readiness.evaluate, readiness.evidence_summary
  - Each executor returns a dict with project_id
  - doctor.run returns exactly 12 checks
  - readiness.evaluate returns verdict in {ready, warn, hold, unsafe}
  - readiness.evidence_summary returns counts with tools/skills/watchdogs
  - No tool claims available without an executor
  - ToolRegistry.get_executor() returns non-None for all 5 tools
  - Gateway blocks unsafe actions (governance regression check)
"""

from __future__ import annotations

import pytest

from openjarvis.tools.jarvis_registry import ToolRegistry
from openjarvis.tools.doctor_catalog import initialize_doctor_catalog


_DOCTOR_TOOL_IDS = [
    "doctor.run",
    "doctor.project",
    "doctor.report",
    "readiness.evaluate",
    "readiness.evidence_summary",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_registries():
    ToolRegistry.clear()
    from openjarvis.skills.jarvis_registry import SkillRegistry
    from openjarvis.autonomy.modes import AutonomyPolicy

    SkillRegistry.clear()
    AutonomyPolicy.clear()
    yield
    ToolRegistry.clear()
    SkillRegistry.clear()
    AutonomyPolicy.clear()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestDoctorToolRegistration:
    def test_all_5_tools_registered(self):
        initialize_doctor_catalog()
        for tool_id in _DOCTOR_TOOL_IDS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None, f"Tool '{tool_id}' not registered"

    def test_all_5_tools_available(self):
        initialize_doctor_catalog()
        for tool_id in _DOCTOR_TOOL_IDS:
            spec = ToolRegistry.get(tool_id)
            assert spec is not None
            assert spec.is_available(), (
                f"Tool '{tool_id}' not available: "
                f"status={spec.implementation_status} "
                f"configured={spec.configured} enabled={spec.enabled}"
            )

    def test_idempotent_double_init(self):
        initialize_doctor_catalog()
        initialize_doctor_catalog()
        specs = [ToolRegistry.get(tid) for tid in _DOCTOR_TOOL_IDS]
        assert all(s is not None for s in specs)

    def test_all_have_executors(self):
        initialize_doctor_catalog()
        for tool_id in _DOCTOR_TOOL_IDS:
            executor = ToolRegistry.get_executor(tool_id)
            assert executor is not None, f"No executor for '{tool_id}'"

    def test_no_available_tool_without_executor(self):
        from openjarvis.tools.catalog import initialize_catalog
        initialize_catalog()
        available = ToolRegistry.list_available()
        for tool in available:
            exec_fn = ToolRegistry.get_executor(tool.tool_id)
            assert exec_fn is not None, (
                f"Tool '{tool.tool_id}' claims available but has no executor"
            )

    def test_category_is_doctor_or_readiness(self):
        initialize_doctor_catalog()
        for tool_id in _DOCTOR_TOOL_IDS:
            spec = ToolRegistry.get(tool_id)
            assert spec.category in ("doctor", "readiness"), (
                f"Tool '{tool_id}' has unexpected category: {spec.category}"
            )

    def test_risk_level_is_low(self):
        initialize_doctor_catalog()
        for tool_id in _DOCTOR_TOOL_IDS:
            spec = ToolRegistry.get(tool_id)
            assert spec.risk_level == "low"

    def test_approval_not_required(self):
        initialize_doctor_catalog()
        for tool_id in _DOCTOR_TOOL_IDS:
            spec = ToolRegistry.get(tool_id)
            assert spec.approval_required is False


# ---------------------------------------------------------------------------
# Executor behaviour
# ---------------------------------------------------------------------------


class TestDoctorRunExecutor:
    def test_returns_12_checks(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.run")
        result = executor({"project_id": "omnix"}, {})
        assert result["total_checks"] == 12
        assert len(result["checks"]) == 12

    def test_project_id_in_result(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.run")
        result = executor({"project_id": "omnix"}, {})
        assert result["project_id"] == "omnix"

    def test_by_status_keys_are_valid(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.run")
        result = executor({}, {})
        valid = {"pass", "warn", "fail", "not_configured"}
        for k in result["by_status"]:
            assert k in valid


class TestDoctorProjectExecutor:
    def test_returns_4_checks(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.project")
        result = executor({"project_id": "omnix"}, {})
        assert result["total_checks"] == 4

    def test_project_id_propagated(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.project")
        result = executor({"project_id": "omnix"}, {})
        assert result["project_id"] == "omnix"


class TestDoctorReportExecutor:
    def test_has_by_category(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.report")
        result = executor({"project_id": "omnix"}, {})
        assert "by_category" in result
        assert isinstance(result["by_category"], dict)

    def test_12_checks_total(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("doctor.report")
        result = executor({"project_id": "omnix"}, {})
        assert result["total_checks"] == 12


class TestReadinessEvaluateExecutor:
    def test_verdict_is_valid(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evaluate")
        result = executor({"project_id": "omnix"}, {})
        valid = {"ready", "warn", "hold", "unsafe"}
        assert result["verdict"] in valid

    def test_has_8_categories(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evaluate")
        result = executor({"project_id": "omnix"}, {})
        assert len(result["categories"]) == 8

    def test_cost_control_compliant(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evaluate")
        result = executor({"project_id": "omnix"}, {})
        assert result["cost_control_compliant"] is True

    def test_accepted_checkpoints_present(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evaluate")
        result = executor({"project_id": "omnix"}, {})
        assert len(result["accepted_checkpoints"]) >= 7

    def test_no_fake_inflation(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evaluate")
        result = executor({"project_id": "omnix"}, {})
        assert result["fake_capability_check"]["inflation_detected"] is False


class TestReadinessEvidenceSummaryExecutor:
    def test_returns_counts(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evidence_summary")
        result = executor({"project_id": "omnix"}, {})
        assert "counts" in result

    def test_tools_available_gt_zero(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evidence_summary")
        result = executor({"project_id": "omnix"}, {})
        assert result["counts"]["tools"]["available"] > 0

    def test_watchdogs_registered_8(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evidence_summary")
        result = executor({"project_id": "omnix"}, {})
        assert result["counts"]["watchdogs"]["registered"] == 8

    def test_unsafe_actions_blocked_present(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evidence_summary")
        result = executor({"project_id": "omnix"}, {})
        assert "real_slack_send" in result["unsafe_actions_blocked"]
        assert "omnix_production_deploy" in result["unsafe_actions_blocked"]

    def test_remaining_limitations_present(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evidence_summary")
        result = executor({"project_id": "omnix"}, {})
        assert len(result["remaining_limitations"]) >= 1

    def test_post_v1_roadmap_present(self):
        initialize_doctor_catalog()
        executor = ToolRegistry.get_executor("readiness.evidence_summary")
        result = executor({"project_id": "omnix"}, {})
        assert len(result["post_v1_roadmap"]) >= 1


# ---------------------------------------------------------------------------
# Governance regression: unsafe action still blocked via gateway
# ---------------------------------------------------------------------------


class TestGovernanceGatewayBlock:
    def test_real_slack_send_blocked_by_gateway(self):
        from openjarvis.tools.gateway import ToolExecutionGateway
        from openjarvis.tools.catalog import initialize_catalog

        initialize_catalog()
        gw = ToolExecutionGateway()
        result = gw.execute(
            "slack.notify_mission",
            inputs={"message": "test"},
            project_id="omnix",
        )
        assert result.ok is False
        assert result.outcome in ("not_configured", "hard_gate", "blocked", "failed")

    def test_doctor_run_executes_cleanly_via_gateway(self):
        from openjarvis.tools.gateway import ToolExecutionGateway
        from openjarvis.tools.catalog import initialize_catalog

        initialize_catalog()
        gw = ToolExecutionGateway()
        result = gw.execute("doctor.run", inputs={"project_id": "omnix"})
        assert result.ok is True
        assert result.outcome == "success"
        assert result.output["total_checks"] == 12
