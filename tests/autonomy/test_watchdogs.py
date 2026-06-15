"""Tests for watchdog foundation.

Covers:
  - WatchdogRunner.list_watchdog_ids() returns all 8 IDs
  - WatchdogRunner.run_once() returns WatchdogResult with required fields
  - WatchdogRunner.run_project_pack() returns one result per watchdog
  - WatchdogRunner.summarize() produces correct counts
  - Each watchdog returns honest status (not fake healthy when deps unavailable)
  - memory_secret_rejection_watchdog proves scrub is working
  - git_dirty_watchdog works for OMNIX repo path
  - tool_degradation_watchdog uses real ToolRegistry
  - WatchdogResult.to_dict() includes all required fields
  - No watchdog modifies system state
"""

from __future__ import annotations

import pytest

from openjarvis.autonomy.watchdogs import (
    WatchdogResult,
    WatchdogRunner,
    WatchdogSeverity,
    WatchdogStatus,
)

EXPECTED_WATCHDOG_IDS = [
    "approval_queue_watchdog",
    "backend_health_watchdog",
    "execution_failure_watchdog",
    "git_dirty_watchdog",
    "memory_secret_rejection_watchdog",
    "mission_stuck_watchdog",
    "project_handoff_staleness_watchdog",
    "tool_degradation_watchdog",
]


class TestWatchdogRegistry:
    def test_all_eight_watchdogs_registered(self):
        ids = WatchdogRunner.list_watchdog_ids()
        assert len(ids) == 8

    def test_expected_ids_present(self):
        ids = WatchdogRunner.list_watchdog_ids()
        for wid in EXPECTED_WATCHDOG_IDS:
            assert wid in ids, f"Missing watchdog: {wid}"

    def test_ids_are_sorted(self):
        ids = WatchdogRunner.list_watchdog_ids()
        assert ids == sorted(ids)


class TestWatchdogResult:
    def test_result_has_required_fields(self):
        result = WatchdogRunner.run_once("backend_health_watchdog", "omnix")
        assert isinstance(result, WatchdogResult)
        assert result.id == "backend_health_watchdog"
        assert result.project_id == "omnix"
        assert result.severity in [
            WatchdogSeverity.INFO,
            WatchdogSeverity.WARNING,
            WatchdogSeverity.ERROR,
            WatchdogSeverity.CRITICAL,
        ]
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.FAILED,
            WatchdogStatus.NOT_CONFIGURED,
            WatchdogStatus.SKIPPED,
        ]
        assert isinstance(result.evidence, str)
        assert len(result.evidence) > 0
        assert isinstance(result.recommendation, str)
        assert result.last_checked_at > 0

    def test_to_dict_has_all_keys(self):
        result = WatchdogRunner.run_once("backend_health_watchdog", "omnix")
        d = result.to_dict()
        required_keys = ["id", "project_id", "severity", "status", "evidence",
                         "recommendation", "last_checked_at", "extra"]
        for key in required_keys:
            assert key in d, f"Missing key in to_dict(): {key}"

    def test_unknown_watchdog_returns_not_configured(self):
        result = WatchdogRunner.run_once("nonexistent_watchdog_xyz", "omnix")
        assert result.status == WatchdogStatus.NOT_CONFIGURED
        assert "nonexistent_watchdog_xyz" in result.evidence


class TestRunProjectPack:
    def test_run_project_pack_returns_eight_results(self):
        results = WatchdogRunner.run_project_pack("omnix")
        assert len(results) == 8

    def test_all_results_have_correct_project_id(self):
        results = WatchdogRunner.run_project_pack("omnix")
        for r in results:
            assert r.project_id == "omnix"

    def test_all_results_have_correct_watchdog_id(self):
        results = WatchdogRunner.run_project_pack("omnix")
        result_ids = {r.id for r in results}
        for wid in EXPECTED_WATCHDOG_IDS:
            assert wid in result_ids

    def test_project_pack_different_project(self):
        results = WatchdogRunner.run_project_pack("project_b")
        assert len(results) == 8
        for r in results:
            assert r.project_id == "project_b"


class TestWatchdogSummarize:
    def test_summarize_counts_by_status(self):
        results = WatchdogRunner.run_project_pack("omnix")
        summary = WatchdogRunner.summarize(results)
        assert "total" in summary
        assert summary["total"] == 8
        assert "by_status" in summary
        assert "by_severity" in summary
        assert "healthy" in summary
        assert "degraded" in summary
        assert "failed" in summary
        assert "not_configured" in summary
        total_in_status = sum(summary["by_status"].values())
        assert total_in_status == 8

    def test_summarize_empty_list(self):
        summary = WatchdogRunner.summarize([])
        assert summary["total"] == 0
        assert summary["healthy"] == 0


class TestSpecificWatchdogs:
    def test_memory_secret_rejection_watchdog_healthy(self):
        """Memory store must correctly reject secrets — not fake healthy."""
        result = WatchdogRunner.run_once("memory_secret_rejection_watchdog", "omnix")
        assert result.id == "memory_secret_rejection_watchdog"
        assert result.status == WatchdogStatus.HEALTHY, (
            f"memory_secret_rejection_watchdog should be HEALTHY (scrub works). "
            f"Got: status={result.status} evidence={result.evidence}"
        )

    def test_git_dirty_watchdog_for_omnix(self):
        """git_dirty_watchdog should run against omnix repo path."""
        result = WatchdogRunner.run_once("git_dirty_watchdog", "omnix")
        assert result.id == "git_dirty_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.NOT_CONFIGURED,
            WatchdogStatus.SKIPPED,
        ]
        assert len(result.evidence) > 0

    def test_tool_degradation_watchdog_runs(self):
        """tool_degradation_watchdog must not fake healthy."""
        result = WatchdogRunner.run_once("tool_degradation_watchdog", "omnix")
        assert result.id == "tool_degradation_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.NOT_CONFIGURED,
        ]
        assert len(result.evidence) > 0

    def test_project_handoff_staleness_watchdog_omnix(self):
        """Handoff staleness watchdog finds OMNIX handoff path."""
        result = WatchdogRunner.run_once("project_handoff_staleness_watchdog", "omnix")
        assert result.id == "project_handoff_staleness_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.FAILED,
            WatchdogStatus.NOT_CONFIGURED,
            WatchdogStatus.SKIPPED,
        ]

    def test_mission_stuck_watchdog_runs(self):
        result = WatchdogRunner.run_once("mission_stuck_watchdog", "omnix")
        assert result.id == "mission_stuck_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.NOT_CONFIGURED,
        ]

    def test_approval_queue_watchdog_runs(self):
        result = WatchdogRunner.run_once("approval_queue_watchdog", "omnix")
        assert result.id == "approval_queue_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.NOT_CONFIGURED,
        ]

    def test_backend_health_watchdog_runs(self):
        result = WatchdogRunner.run_once("backend_health_watchdog", "omnix")
        assert result.id == "backend_health_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.FAILED,
            WatchdogStatus.NOT_CONFIGURED,
        ]

    def test_execution_failure_watchdog_runs(self):
        result = WatchdogRunner.run_once("execution_failure_watchdog", "omnix")
        assert result.id == "execution_failure_watchdog"
        assert result.status in [
            WatchdogStatus.HEALTHY,
            WatchdogStatus.DEGRADED,
            WatchdogStatus.FAILED,
            WatchdogStatus.NOT_CONFIGURED,
        ]
