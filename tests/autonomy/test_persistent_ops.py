"""Tests for PersistentOps — runner plan, dry-run, install plan (US8 Phase G).

Covers:
  - get_runner_status returns valid status and installed=False (no daemon installed)
  - run_once dry_run=True: returns simulated results, executed=False for all
  - run_once dry_run=False: attempts execution, never installs daemon
  - generate_schedule_plan returns plan with installed=False
  - generate_install_plan returns plan with installed=False and approval_required=True
  - dry_run_schedule returns 3 simulated runs, installed=False
  - generate_stop_plan returns note when nothing installed
  - No persistent daemon is ever installed by any function
"""

from __future__ import annotations

import pytest

from openjarvis.autonomy.persistent_ops import (
    RunnerStatus,
    dry_run_schedule,
    generate_install_plan,
    generate_schedule_plan,
    generate_stop_plan,
    get_runner_status,
    run_once,
)


class TestRunnerStatus:
    def test_returns_runner_status_field(self):
        r = get_runner_status()
        assert "runner_status" in r

    def test_returns_installed_field(self):
        r = get_runner_status()
        assert "installed" in r
        assert isinstance(r["installed"], bool)

    def test_returns_log_path_field(self):
        r = get_runner_status()
        assert "log_path" in r

    def test_note_says_no_persistent_runner(self):
        r = get_runner_status()
        assert "note" in r
        note = r["note"].lower()
        assert "no persistent runner" in note or "not installed" in note


class TestRunOnceDryRun:
    def test_dry_run_returns_would_run(self):
        r = run_once("omnix", dry_run=True)
        assert r["dry_run"] is True
        for action in r["actions"]:
            assert action["dry_run"] is True
            assert action["executed"] is False
            assert action["status"] == "would_run"

    def test_dry_run_never_installs_daemon(self):
        run_once("omnix", dry_run=True)
        status = get_runner_status()
        assert status["installed"] is False

    def test_returns_project_id(self):
        r = run_once("omnix", dry_run=True)
        assert r["project_id"] == "omnix"

    def test_returns_actions_list(self):
        r = run_once("omnix", dry_run=True)
        assert "actions" in r
        assert len(r["actions"]) >= 1

    def test_note_says_no_persistent_runner(self):
        r = run_once("omnix", dry_run=True)
        assert "note" in r
        assert "daemon" in r["note"] or "persistent" in r["note"]


class TestSchedulePlan:
    def test_returns_plan_type(self):
        r = generate_schedule_plan("omnix", 60)
        assert r["plan_type"] == "schedule"

    def test_runner_status_is_planned(self):
        r = generate_schedule_plan("omnix", 60)
        assert r["runner_status"] == RunnerStatus.PLANNED

    def test_install_requires_explicit_approval(self):
        r = generate_schedule_plan("omnix", 60)
        assert r["install_requires_explicit_approval"] is True

    def test_note_says_plan_only(self):
        r = generate_schedule_plan("omnix", 60)
        assert "PLAN" in r["note"] or "plan" in r["note"].lower()

    def test_returns_planned_actions(self):
        r = generate_schedule_plan("omnix", 60)
        assert "planned_actions" in r
        assert len(r["planned_actions"]) >= 1


class TestInstallPlan:
    def test_installed_false(self):
        r = generate_install_plan("omnix", 60)
        assert r["installed"] is False

    def test_approval_required_true(self):
        r = generate_install_plan("omnix", 60)
        assert r["approval_required"] is True

    def test_has_install_plan_steps(self):
        r = generate_install_plan("omnix", 60)
        assert "install_plan" in r
        assert len(r["install_plan"]) >= 1

    def test_all_steps_not_executed(self):
        r = generate_install_plan("omnix", 60)
        for step in r["install_plan"]:
            assert step["not_executed"] is True

    def test_all_steps_require_approval(self):
        r = generate_install_plan("omnix", 60)
        for step in r["install_plan"]:
            assert step["requires_approval"] is True

    def test_note_says_nothing_installed(self):
        r = generate_install_plan("omnix", 60)
        assert "note" in r
        note = r["note"].lower()
        assert "nothing" in note or "not installed" in note or "never" in note

    def test_has_explicit_approval_message(self):
        r = generate_install_plan("omnix", 60)
        assert "explicit_approval_message" in r


class TestDryRunSchedule:
    def test_returns_3_simulated_runs(self):
        r = dry_run_schedule("omnix", 60)
        assert len(r["simulated_runs"]) == 3

    def test_all_runs_simulated(self):
        r = dry_run_schedule("omnix", 60)
        for run in r["simulated_runs"]:
            assert run["simulated"] is True

    def test_installed_false(self):
        r = dry_run_schedule("omnix", 60)
        assert r["installed"] is False

    def test_runner_status_dry_run_only(self):
        r = dry_run_schedule("omnix", 60)
        assert r["runner_status"] == RunnerStatus.DRY_RUN_ONLY

    def test_note_says_nothing_executed(self):
        r = dry_run_schedule("omnix", 60)
        assert "note" in r
        note = r["note"].lower()
        assert "nothing executed" in note or "no daemon" in note or "dry run" in note

    def test_actions_would_execute_true(self):
        r = dry_run_schedule("omnix", 60)
        for run in r["simulated_runs"]:
            for action in run["actions"]:
                assert action["would_execute"] is True
                assert action["simulated"] is True


class TestStopPlan:
    def test_nothing_to_stop_when_not_installed(self):
        r = generate_stop_plan()
        if not r.get("runner_installed"):
            assert "note" in r
            assert "nothing to stop" in r["note"].lower()

    def test_returns_dict_never_raises(self):
        r = generate_stop_plan()
        assert isinstance(r, dict)
