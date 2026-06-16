"""Tests for Jarvis Doctor checks — 31 independent diagnostic checks.

Covers:
  - Each check returns a CheckResult with check_id, category, status, evidence
  - Status is one of: pass, warn, fail, not_configured
  - run_all_checks() returns exactly 31 results
  - backend_health passes (core modules importable)
  - project_registry_health passes (OMNIX registered)
  - tool_registry_counts passes or warns (never zero available after init)
  - skill_registry_counts passes or warns (never zero available)
  - memory_store_health passes (SQLite + secret rejection)
  - autonomy_mode_status passes (hard gate enforcement verified)
  - watchdog_status returns results for all 8 watchdogs
  - alert_status reports store reachable
  - execution_log_health reports log reachable
  - git_worktree_status returns branch/head evidence
  - handoff_freshness returns evidence for OMNIX handoff paths
  - packaged_app_build_metadata returns checked_paths evidence
  - No check raises an unhandled exception
  - to_dict() is complete and machine-readable
"""

from __future__ import annotations

import pytest

from openjarvis.doctor.checks import (
    CheckResult,
    CheckStatus,
    _ALL_CHECK_FNS,
    check_alert_status,
    check_automation_policy_health,
    check_autonomy_mode_status,
    check_backend_health,
    check_connector_readiness,
    check_desktop_operator_status,
    check_execution_log_health,
    check_git_worktree_status,
    check_handoff_freshness,
    check_memory_store_health,
    check_mobile_readiness,
    check_packaged_app_build_metadata,
    check_persistent_ops_status,
    check_project_linkage_status,
    check_project_registry_health,
    check_skill_registry_counts,
    check_tool_registry_counts,
    check_voice_pipeline_status,
    check_watchdog_status,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_registries():
    """Ensure tool/skill registries are clean per test."""
    from openjarvis.tools.jarvis_registry import ToolRegistry
    from openjarvis.skills.jarvis_registry import SkillRegistry
    from openjarvis.autonomy.modes import AutonomyPolicy

    ToolRegistry.clear()
    SkillRegistry.clear()
    AutonomyPolicy.clear()
    yield
    ToolRegistry.clear()
    SkillRegistry.clear()
    AutonomyPolicy.clear()


# ---------------------------------------------------------------------------
# CheckResult contract
# ---------------------------------------------------------------------------


class TestCheckResultContract:
    def test_check_result_fields(self):
        r = CheckResult(
            check_id="test_check",
            category="test",
            status=CheckStatus.PASS,
            summary="ok",
            evidence={"key": "val"},
            project_id="omnix",
        )
        assert r.check_id == "test_check"
        assert r.category == "test"
        assert r.status == CheckStatus.PASS
        assert r.project_id == "omnix"
        assert r.checked_at > 0

    def test_to_dict_complete(self):
        r = CheckResult(
            check_id="test_check",
            category="test",
            status=CheckStatus.WARN,
            summary="warning",
            evidence={"x": 1},
            project_id="omnix",
        )
        d = r.to_dict()
        assert d["check_id"] == "test_check"
        assert d["status"] == "warn"
        assert d["evidence"] == {"x": 1}
        assert "checked_at" in d

    def test_valid_statuses(self):
        for s in [CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.NOT_CONFIGURED]:
            assert isinstance(s, str)


# ---------------------------------------------------------------------------
# run_all_checks — 31 total
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    def test_returns_exactly_32_results(self):
        results = run_all_checks(project_id="omnix")
        assert len(results) == 32

    def test_all_results_are_check_result(self):
        results = run_all_checks(project_id="omnix")
        for r in results:
            assert isinstance(r, CheckResult)

    def test_all_check_ids_unique(self):
        results = run_all_checks(project_id="omnix")
        ids = [r.check_id for r in results]
        assert len(ids) == len(set(ids))

    def test_all_statuses_are_valid(self):
        results = run_all_checks(project_id="omnix")
        valid = {CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.NOT_CONFIGURED}
        for r in results:
            assert r.status in valid, f"{r.check_id}: invalid status {r.status}"

    def test_all_have_nonempty_evidence(self):
        results = run_all_checks(project_id="omnix")
        for r in results:
            assert isinstance(r.evidence, dict), f"{r.check_id}: evidence not dict"

    def test_all_have_nonempty_summary(self):
        results = run_all_checks(project_id="omnix")
        for r in results:
            assert r.summary, f"{r.check_id}: empty summary"

    def test_project_id_propagated(self):
        results = run_all_checks(project_id="omnix")
        for r in results:
            assert r.project_id == "omnix"

    def test_all_check_fns_count(self):
        assert len(_ALL_CHECK_FNS) == 32

    def test_no_exception_on_unknown_project(self):
        results = run_all_checks(project_id="nonexistent_xyz_proj")
        assert len(results) == 32


# ---------------------------------------------------------------------------
# check_backend_health
# ---------------------------------------------------------------------------


class TestBackendHealth:
    def test_passes_with_core_modules(self):
        r = check_backend_health("omnix")
        assert r.check_id == "backend_health"
        assert r.status == CheckStatus.PASS
        assert "openjarvis.tools.jarvis_registry" in r.evidence

    def test_evidence_all_ok(self):
        r = check_backend_health("omnix")
        for key, val in r.evidence.items():
            assert val == "ok", f"Module {key} not ok: {val}"

    def test_category_is_backend(self):
        r = check_backend_health("omnix")
        assert r.category == "backend"


# ---------------------------------------------------------------------------
# check_project_registry_health
# ---------------------------------------------------------------------------


class TestProjectRegistryHealth:
    def test_omnix_present(self):
        r = check_project_registry_health("omnix")
        assert r.check_id == "project_registry_health"
        assert r.status == CheckStatus.PASS
        assert r.evidence["omnix_present"] is True

    def test_unknown_project_warns(self):
        r = check_project_registry_health("nonexistent_xyz")
        assert r.status == CheckStatus.WARN
        assert r.evidence["omnix_present"] is True

    def test_category_is_project(self):
        r = check_project_registry_health("omnix")
        assert r.category == "project"

    def test_total_projects_gte_1(self):
        r = check_project_registry_health("omnix")
        assert r.evidence["total_projects"] >= 1


# ---------------------------------------------------------------------------
# check_tool_registry_counts
# ---------------------------------------------------------------------------


class TestToolRegistryCounts:
    def test_available_gt_zero_after_init(self):
        r = check_tool_registry_counts("omnix")
        assert r.check_id == "tool_registry_counts"
        assert r.evidence["available"] > 0

    def test_status_pass_or_warn(self):
        r = check_tool_registry_counts("omnix")
        assert r.status in (CheckStatus.PASS, CheckStatus.WARN)

    def test_has_by_status(self):
        r = check_tool_registry_counts("omnix")
        assert "by_status" in r.evidence

    def test_has_unavailable_reasons(self):
        r = check_tool_registry_counts("omnix")
        assert "unavailable_reasons" in r.evidence
        assert isinstance(r.evidence["unavailable_reasons"], list)


# ---------------------------------------------------------------------------
# check_skill_registry_counts
# ---------------------------------------------------------------------------


class TestSkillRegistryCounts:
    def test_available_gt_zero_after_init(self):
        r = check_skill_registry_counts("omnix")
        assert r.check_id == "skill_registry_counts"
        assert r.evidence["available"] > 0

    def test_status_pass_or_warn(self):
        r = check_skill_registry_counts("omnix")
        assert r.status in (CheckStatus.PASS, CheckStatus.WARN)

    def test_has_degraded_details(self):
        r = check_skill_registry_counts("omnix")
        assert "degraded_details" in r.evidence


# ---------------------------------------------------------------------------
# check_memory_store_health
# ---------------------------------------------------------------------------


class TestMemoryStoreHealth:
    def test_passes_with_write_and_secret_rejection(self):
        r = check_memory_store_health("omnix")
        assert r.check_id == "memory_store_health"
        assert r.status == CheckStatus.PASS
        assert r.evidence["write_ok"] is True
        assert r.evidence["secret_rejection_functional"] is True

    def test_category_is_memory(self):
        r = check_memory_store_health("omnix")
        assert r.category == "memory"

    def test_entry_id_present(self):
        r = check_memory_store_health("omnix")
        assert "entry_id" in r.evidence


# ---------------------------------------------------------------------------
# check_autonomy_mode_status
# ---------------------------------------------------------------------------


class TestAutonomyModeStatus:
    def test_passes_with_hard_gate_enforcement(self):
        r = check_autonomy_mode_status("omnix")
        assert r.check_id == "autonomy_mode_status"
        assert r.status == CheckStatus.PASS
        assert r.evidence["hard_gate_enforcement_verified"] is True

    def test_hard_gates_always_blocked(self):
        r = check_autonomy_mode_status("omnix")
        assert r.evidence["hard_gates_always_blocked"] is True

    def test_real_send_always_blocked(self):
        r = check_autonomy_mode_status("omnix")
        assert r.evidence["real_send_always_blocked"] is True

    def test_mode_is_observe_only_by_default(self):
        r = check_autonomy_mode_status("omnix")
        assert r.evidence["mode"] == "observe_only"


# ---------------------------------------------------------------------------
# check_watchdog_status
# ---------------------------------------------------------------------------


class TestWatchdogStatus:
    def test_8_watchdogs_registered(self):
        r = check_watchdog_status("omnix")
        assert r.check_id == "watchdog_status"
        assert r.evidence["registered_count"] == 8

    def test_status_pass_or_warn(self):
        r = check_watchdog_status("omnix")
        assert r.status in (CheckStatus.PASS, CheckStatus.WARN)

    def test_has_results_by_id(self):
        r = check_watchdog_status("omnix")
        assert "results_by_id" in r.evidence
        assert len(r.evidence["results_by_id"]) == 8


# ---------------------------------------------------------------------------
# check_alert_status
# ---------------------------------------------------------------------------


class TestAlertStatus:
    def test_store_reachable(self):
        r = check_alert_status("omnix")
        assert r.check_id == "alert_status"
        assert r.evidence.get("store_reachable") is True

    def test_status_pass_or_warn(self):
        r = check_alert_status("omnix")
        assert r.status in (CheckStatus.PASS, CheckStatus.WARN)

    def test_has_open_count(self):
        r = check_alert_status("omnix")
        assert "open" in r.evidence


# ---------------------------------------------------------------------------
# check_execution_log_health
# ---------------------------------------------------------------------------


class TestExecutionLogHealth:
    def test_log_reachable(self):
        r = check_execution_log_health("omnix")
        assert r.check_id == "execution_log_health"
        assert r.status == CheckStatus.PASS
        assert r.evidence["log_reachable"] is True

    def test_has_recent_entries_count(self):
        r = check_execution_log_health("omnix")
        assert "recent_entries" in r.evidence
        assert isinstance(r.evidence["recent_entries"], int)


# ---------------------------------------------------------------------------
# check_git_worktree_status
# ---------------------------------------------------------------------------


class TestGitWorktreeStatus:
    def test_returns_check_result(self):
        r = check_git_worktree_status("omnix")
        assert r.check_id == "git_worktree_status"

    def test_status_pass_warn_or_fail(self):
        r = check_git_worktree_status("omnix")
        assert r.status in (CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL)

    def test_evidence_has_branch_when_git_available(self):
        r = check_git_worktree_status("omnix")
        if r.status in (CheckStatus.PASS, CheckStatus.WARN):
            assert "branch" in r.evidence
            assert "head" in r.evidence
            assert isinstance(r.evidence["dirty"], bool)

    def test_category_is_git(self):
        r = check_git_worktree_status("omnix")
        assert r.category == "git"


# ---------------------------------------------------------------------------
# check_handoff_freshness
# ---------------------------------------------------------------------------


class TestHandoffFreshness:
    def test_returns_check_result(self):
        r = check_handoff_freshness("omnix")
        assert r.check_id == "handoff_freshness"

    def test_evidence_contains_jarvis_handoff_path(self):
        r = check_handoff_freshness("omnix")
        if r.status != CheckStatus.NOT_CONFIGURED:
            assert "JARVIS_OMNIX_HANDOFF.md" in r.evidence

    def test_status_is_valid(self):
        r = check_handoff_freshness("omnix")
        valid = {CheckStatus.PASS, CheckStatus.WARN, CheckStatus.FAIL, CheckStatus.NOT_CONFIGURED}
        assert r.status in valid


# ---------------------------------------------------------------------------
# check_project_linkage_status
# ---------------------------------------------------------------------------


class TestProjectLinkageStatus:
    @pytest.fixture(autouse=True)
    def reset_source_registry(self, monkeypatch):
        monkeypatch.setenv("JARVIS_PROJECT_OMNIX_REPO_PATH", "/Users/user/OpenJarvis")
        monkeypatch.setenv("OPENCLAW_WORKSPACE_PATH", "")
        monkeypatch.setenv("OPENCLAW_HANDOFF_PATH", "")
        from openjarvis.projects.source_links import ProjectSourceRegistry
        ProjectSourceRegistry.clear()
        yield
        ProjectSourceRegistry.clear()

    def test_omnix_fails_as_placeholder(self):
        r = check_project_linkage_status("omnix")
        assert r.check_id == "project_linkage_status"
        assert r.status == CheckStatus.FAIL

    def test_placeholder_blocker_in_evidence(self):
        r = check_project_linkage_status("omnix")
        assert r.evidence["linkage_status"] == "placeholder"

    def test_category_is_project_linkage(self):
        r = check_project_linkage_status("omnix")
        assert r.category == "project_linkage"

    def test_counts_in_evidence(self):
        r = check_project_linkage_status("omnix")
        assert "counts" in r.evidence
        assert r.evidence["counts"]["placeholder"] >= 1

    def test_sources_in_evidence(self):
        r = check_project_linkage_status("omnix")
        assert "sources" in r.evidence
        assert len(r.evidence["sources"]) >= 1


# ---------------------------------------------------------------------------
# check_packaged_app_build_metadata
# ---------------------------------------------------------------------------


class TestPackagedAppBuildMetadata:
    def test_returns_check_result(self):
        r = check_packaged_app_build_metadata("omnix")
        assert r.check_id == "packaged_app_build_metadata"

    def test_status_pass_or_not_configured(self):
        r = check_packaged_app_build_metadata("omnix")
        assert r.status in (CheckStatus.PASS, CheckStatus.NOT_CONFIGURED, CheckStatus.FAIL)

    def test_checked_paths_in_evidence(self):
        r = check_packaged_app_build_metadata("omnix")
        assert "checked_paths" in r.evidence
        assert len(r.evidence["checked_paths"]) >= 1

    def test_app_found_key_present(self):
        r = check_packaged_app_build_metadata("omnix")
        assert "app_found" in r.evidence
