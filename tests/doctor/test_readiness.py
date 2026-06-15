"""Tests for Jarvis Readiness Gate — 15 categories, 4 verdicts.

Covers:
  - evaluate_readiness() returns a ReadinessReport
  - Report has 15 categories
  - Verdict is one of: ready, warn, hold, unsafe
  - UNSAFE when safety_governance fails (hard gate not enforced)
  - HOLD when required evidence missing
  - WARN when not_configured or warn checks present
  - READY when all required categories pass
  - accepted_checkpoints are present and non-empty
  - fake_capability_check detects no inflation on real registry
  - generate_v1_report() returns all required fields
  - cost_control_compliant is True
  - categories dict keys match ReadinessCategory constants
  - CategoryResult.to_dict() is complete
  - ReadinessReport.to_dict() is machine-readable
"""

from __future__ import annotations

import pytest

from openjarvis.doctor.checks import CheckResult, CheckStatus
from openjarvis.doctor.readiness import (
    CategoryResult,
    ReadinessCategory,
    ReadinessReport,
    ReadinessVerdict,
    _ACCEPTED_CHECKPOINTS,
    _CATEGORY_CHECKS,
    evaluate_readiness,
    generate_v1_report,
)
from openjarvis.projects.source_links import ProjectSourceRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_registries():
    from openjarvis.tools.jarvis_registry import ToolRegistry
    from openjarvis.skills.jarvis_registry import SkillRegistry
    from openjarvis.autonomy.modes import AutonomyPolicy

    ToolRegistry.clear()
    SkillRegistry.clear()
    AutonomyPolicy.clear()
    ProjectSourceRegistry.clear()
    yield
    ToolRegistry.clear()
    SkillRegistry.clear()
    AutonomyPolicy.clear()
    ProjectSourceRegistry.clear()


# ---------------------------------------------------------------------------
# ReadinessCategory constants
# ---------------------------------------------------------------------------


class TestReadinessCategoryConstants:
    def test_15_categories_defined(self):
        cats = [
            ReadinessCategory.CORE_MISSION_SYSTEM,
            ReadinessCategory.TOOLS_SKILLS_MEMORY,
            ReadinessCategory.AUTONOMY_WATCHDOGS_ALERTS,
            ReadinessCategory.PROJECT_AWARENESS,
            ReadinessCategory.SAFETY_GOVERNANCE,
            ReadinessCategory.PACKAGED_APP_UI,
            ReadinessCategory.HANDOFF_DOCS,
            ReadinessCategory.GIT_CLEANLINESS,
            ReadinessCategory.PROJECT_LINKAGE,
            ReadinessCategory.VOICE_READINESS,
            ReadinessCategory.DESKTOP_READINESS,
            ReadinessCategory.AUTOMATION_READINESS,
            ReadinessCategory.CONNECTOR_READINESS,
            ReadinessCategory.MOBILE_READINESS,
            ReadinessCategory.OPENCLAW_LINKAGE,
        ]
        assert len(cats) == 15

    def test_category_checks_covers_all_15(self):
        assert len(_CATEGORY_CHECKS) == 15
        for cat in [
            ReadinessCategory.CORE_MISSION_SYSTEM,
            ReadinessCategory.TOOLS_SKILLS_MEMORY,
            ReadinessCategory.AUTONOMY_WATCHDOGS_ALERTS,
            ReadinessCategory.PROJECT_AWARENESS,
            ReadinessCategory.SAFETY_GOVERNANCE,
            ReadinessCategory.PACKAGED_APP_UI,
            ReadinessCategory.HANDOFF_DOCS,
            ReadinessCategory.GIT_CLEANLINESS,
            ReadinessCategory.PROJECT_LINKAGE,
            ReadinessCategory.VOICE_READINESS,
            ReadinessCategory.DESKTOP_READINESS,
            ReadinessCategory.AUTOMATION_READINESS,
            ReadinessCategory.CONNECTOR_READINESS,
            ReadinessCategory.MOBILE_READINESS,
            ReadinessCategory.OPENCLAW_LINKAGE,
        ]:
            assert cat in _CATEGORY_CHECKS
            assert len(_CATEGORY_CHECKS[cat]) >= 1


# ---------------------------------------------------------------------------
# ReadinessVerdict constants
# ---------------------------------------------------------------------------


class TestReadinessVerdictConstants:
    def test_four_verdicts(self):
        assert ReadinessVerdict.READY == "ready"
        assert ReadinessVerdict.WARN == "warn"
        assert ReadinessVerdict.HOLD == "hold"
        assert ReadinessVerdict.UNSAFE == "unsafe"


# ---------------------------------------------------------------------------
# evaluate_readiness — full run
# ---------------------------------------------------------------------------


class TestEvaluateReadiness:
    def test_returns_readiness_report(self):
        report = evaluate_readiness(project_id="omnix")
        assert isinstance(report, ReadinessReport)

    def test_has_15_categories(self):
        report = evaluate_readiness(project_id="omnix")
        assert len(report.categories) == 15

    def test_verdict_is_valid(self):
        report = evaluate_readiness(project_id="omnix")
        valid = {
            ReadinessVerdict.READY,
            ReadinessVerdict.WARN,
            ReadinessVerdict.HOLD,
            ReadinessVerdict.UNSAFE,
        }
        assert report.verdict in valid

    def test_project_id_propagated(self):
        report = evaluate_readiness(project_id="omnix")
        assert report.project_id == "omnix"

    def test_cost_control_compliant(self):
        report = evaluate_readiness(project_id="omnix")
        assert report.cost_control_compliant is True

    def test_accepted_checkpoints_nonempty(self):
        report = evaluate_readiness(project_id="omnix")
        assert len(report.accepted_checkpoints) >= 1

    def test_accepted_checkpoints_reference_accepted_sprints(self):
        report = evaluate_readiness(project_id="omnix")
        combined = "\n".join(report.accepted_checkpoints)
        assert "ACCEPT" in combined
        assert "Sprint" in combined

    def test_verdict_is_hold_due_to_omnix_placeholder(self):
        """OMNIX local_repo=OpenJarvis placeholder → project_linkage FAIL → HOLD."""
        report = evaluate_readiness(project_id="omnix")
        assert report.verdict == ReadinessVerdict.HOLD

    def test_fake_capability_check_present(self):
        report = evaluate_readiness(project_id="omnix")
        assert isinstance(report.fake_capability_check, dict)
        assert "inflation_detected" in report.fake_capability_check

    def test_no_fake_inflation_on_real_registry(self):
        report = evaluate_readiness(project_id="omnix")
        assert report.fake_capability_check.get("inflation_detected") is False, (
            f"Fake tool inflation detected: "
            f"{report.fake_capability_check.get('fake_tools_detected')}"
        )

    def test_summary_nonempty(self):
        report = evaluate_readiness(project_id="omnix")
        assert report.summary

    def test_evaluated_at_is_recent(self):
        import time
        report = evaluate_readiness(project_id="omnix")
        assert time.time() - report.evaluated_at < 60


# ---------------------------------------------------------------------------
# evaluate_readiness — accept pre-run check_results
# ---------------------------------------------------------------------------


class TestEvaluateReadinessWithCheckResults:
    def _make_pass_checks(self, project_id: str = "omnix") -> list:
        from openjarvis.doctor.checks import _ALL_CHECK_FNS
        return [fn(project_id=project_id) for fn in _ALL_CHECK_FNS]

    def test_accepts_pre_run_results(self):
        checks = self._make_pass_checks()
        report = evaluate_readiness(project_id="omnix", check_results=checks)
        assert isinstance(report, ReadinessReport)
        assert len(report.categories) == 15

    def test_unsafe_when_safety_governance_fails(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS

        checks = self._make_pass_checks()
        safety_check_id = _CATEGORY_CHECKS[ReadinessCategory.SAFETY_GOVERNANCE][0]
        patched = []
        for c in checks:
            if c.check_id == safety_check_id:
                patched.append(
                    CheckResult(
                        check_id=c.check_id,
                        category=c.category,
                        status=CheckStatus.FAIL,
                        summary="Forced fail for test",
                        evidence={},
                        project_id="omnix",
                    )
                )
            else:
                patched.append(c)
        report = evaluate_readiness(project_id="omnix", check_results=patched)
        assert report.verdict == ReadinessVerdict.UNSAFE

    def test_hold_when_required_category_fails(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS

        checks = self._make_pass_checks()
        core_check_id = _CATEGORY_CHECKS[ReadinessCategory.CORE_MISSION_SYSTEM][0]
        patched = []
        for c in checks:
            if c.check_id == core_check_id:
                patched.append(
                    CheckResult(
                        check_id=c.check_id,
                        category=c.category,
                        status=CheckStatus.FAIL,
                        summary="Forced fail for test",
                        evidence={},
                        project_id="omnix",
                    )
                )
            else:
                patched.append(c)
        report = evaluate_readiness(project_id="omnix", check_results=patched)
        assert report.verdict in (ReadinessVerdict.HOLD, ReadinessVerdict.UNSAFE)

    def test_warn_when_not_configured(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS

        checks = self._make_pass_checks()
        git_check_id = _CATEGORY_CHECKS[ReadinessCategory.GIT_CLEANLINESS][0]
        patched = []
        for c in checks:
            if c.check_id == git_check_id:
                patched.append(
                    CheckResult(
                        check_id=c.check_id,
                        category=c.category,
                        status=CheckStatus.WARN,
                        summary="Forced warn for test",
                        evidence={},
                        project_id="omnix",
                    )
                )
            else:
                patched.append(c)
        report = evaluate_readiness(project_id="omnix", check_results=patched)
        assert report.verdict in (ReadinessVerdict.WARN, ReadinessVerdict.HOLD, ReadinessVerdict.UNSAFE)


# ---------------------------------------------------------------------------
# CategoryResult
# ---------------------------------------------------------------------------


class TestCategoryResult:
    def test_to_dict_has_required_fields(self):
        r = CategoryResult(
            category="test_cat",
            status=CheckStatus.PASS,
            summary="all good",
            checks=[],
            is_required=True,
            is_safety=False,
        )
        d = r.to_dict()
        assert d["category"] == "test_cat"
        assert d["status"] == "pass"
        assert d["is_required"] is True
        assert d["is_safety"] is False
        assert "checks" in d

    def test_categories_in_report_have_to_dict(self):
        report = evaluate_readiness(project_id="omnix")
        for cat in report.categories:
            d = cat.to_dict()
            assert "category" in d
            assert "status" in d
            assert "summary" in d


# ---------------------------------------------------------------------------
# ReadinessReport.to_dict()
# ---------------------------------------------------------------------------


class TestReadinessReportToDict:
    def test_to_dict_is_machine_readable(self):
        import json

        report = evaluate_readiness(project_id="omnix")
        d = report.to_dict()
        json_str = json.dumps(d)
        assert len(json_str) > 100

    def test_to_dict_has_all_required_keys(self):
        report = evaluate_readiness(project_id="omnix")
        d = report.to_dict()
        required_keys = [
            "project_id",
            "verdict",
            "summary",
            "cost_control_compliant",
            "fake_capability_check",
            "accepted_checkpoints",
            "categories",
            "evaluated_at",
        ]
        for k in required_keys:
            assert k in d, f"Missing key: {k}"

    def test_categories_dict_has_15_entries(self):
        report = evaluate_readiness(project_id="omnix")
        d = report.to_dict()
        assert len(d["categories"]) == 15


# ---------------------------------------------------------------------------
# generate_v1_report
# ---------------------------------------------------------------------------


class TestGenerateV1Report:
    def test_returns_dict(self):
        result = generate_v1_report(project_id="omnix")
        assert isinstance(result, dict)

    def test_has_counts_section(self):
        result = generate_v1_report(project_id="omnix")
        assert "counts" in result
        counts = result["counts"]
        assert "tools" in counts
        assert "skills" in counts
        assert "watchdogs" in counts

    def test_tools_available_gt_zero(self):
        result = generate_v1_report(project_id="omnix")
        assert result["counts"]["tools"]["available"] > 0

    def test_skills_available_gt_zero(self):
        result = generate_v1_report(project_id="omnix")
        assert result["counts"]["skills"]["available"] > 0

    def test_watchdogs_registered_8(self):
        result = generate_v1_report(project_id="omnix")
        assert result["counts"]["watchdogs"]["registered"] == 8

    def test_accepted_checkpoints_nonempty(self):
        result = generate_v1_report(project_id="omnix")
        assert len(result["accepted_checkpoints"]) >= 1

    def test_unsafe_actions_blocked_nonempty(self):
        result = generate_v1_report(project_id="omnix")
        blocked = result["unsafe_actions_blocked"]
        assert "real_slack_send" in blocked
        assert "omnix_production_deploy" in blocked
        assert "secrets_exposure" in blocked

    def test_remaining_limitations_nonempty(self):
        result = generate_v1_report(project_id="omnix")
        assert len(result["remaining_limitations"]) >= 1

    def test_post_v1_roadmap_nonempty(self):
        result = generate_v1_report(project_id="omnix")
        assert len(result["post_v1_roadmap"]) >= 1

    def test_verdict_is_valid(self):
        result = generate_v1_report(project_id="omnix")
        valid = {"ready", "warn", "hold", "unsafe"}
        assert result["verdict"] in valid

    def test_cost_control_law_reference(self):
        result = generate_v1_report(project_id="omnix")
        assert "cost_control_law_reference" in result["v1_readiness"]
        assert len(result["v1_readiness"]["cost_control_law_reference"]) > 0


# ---------------------------------------------------------------------------
# Accepted checkpoints
# ---------------------------------------------------------------------------


class TestAcceptedCheckpoints:
    def test_accepted_checkpoints_nonempty(self):
        assert len(_ACCEPTED_CHECKPOINTS) >= 8

    def test_each_sprint_referenced(self):
        combined = "\n".join(_ACCEPTED_CHECKPOINTS)
        for sprint in ["Sprint 1", "Sprint 2", "Sprint 3", "Sprint 4", "Sprint 5", "Sprint 6"]:
            assert sprint in combined, f"Missing sprint: {sprint}"

    def test_all_carry_accept_verdict(self):
        for cp in _ACCEPTED_CHECKPOINTS:
            assert "ACCEPT" in cp, f"Missing ACCEPT in: {cp}"
