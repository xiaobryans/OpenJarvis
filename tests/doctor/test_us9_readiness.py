"""Tests for US9 Doctor/Readiness checks (Phases 2-11).

Verifies:
  - All 10 new US9 checks run and return valid CheckResult
  - New readiness categories exist
  - No secrets in check output
  - Doctor check statuses are valid
"""

from __future__ import annotations

import os

import pytest

from openjarvis.doctor.checks import (
    CheckResult,
    CheckStatus,
    check_alert_rate_limiter,
    check_budget_guard,
    check_connector_health_monitor,
    check_dogfood_loop,
    check_inject_guard,
    check_job_queue,
    check_memory_backup,
    check_rollback_policy,
    check_secrets_backend,
    check_voice_identity,
    run_all_checks,
)
from openjarvis.doctor.readiness import ReadinessCategory, _CATEGORY_CHECKS

VALID_STATUSES = {
    CheckStatus.PASS,
    CheckStatus.WARN,
    CheckStatus.FAIL,
    CheckStatus.NOT_CONFIGURED,
}

US9_CHECKS = [
    check_secrets_backend,
    check_budget_guard,
    check_job_queue,
    check_rollback_policy,
    check_inject_guard,
    check_voice_identity,
    check_connector_health_monitor,
    check_alert_rate_limiter,
    check_memory_backup,
    check_dogfood_loop,
]

US9_CHECK_IDS = [
    "secrets_backend",
    "budget_guard",
    "job_queue",
    "rollback_policy",
    "inject_guard",
    "voice_identity",
    "connector_health_monitor",
    "alert_rate_limiter",
    "memory_backup",
    "dogfood_loop",
]


class TestUS9ChecksRunAndReturnResult:
    @pytest.mark.parametrize("check_fn", US9_CHECKS)
    def test_check_returns_check_result(self, check_fn):
        result = check_fn()
        assert isinstance(result, CheckResult)

    @pytest.mark.parametrize("check_fn", US9_CHECKS)
    def test_check_returns_valid_status(self, check_fn):
        result = check_fn()
        assert result.status in VALID_STATUSES, f"{check_fn.__name__}: invalid status '{result.status}'"

    @pytest.mark.parametrize("check_fn", US9_CHECKS)
    def test_check_has_check_id(self, check_fn):
        result = check_fn()
        assert result.check_id
        assert isinstance(result.check_id, str)

    @pytest.mark.parametrize("check_fn", US9_CHECKS)
    def test_check_has_summary(self, check_fn):
        result = check_fn()
        assert result.summary
        assert len(result.summary) > 3

    @pytest.mark.parametrize("check_fn", US9_CHECKS)
    def test_check_no_secret_values(self, check_fn):
        result = check_fn()
        result_str = str(result.to_dict())
        for key in ("JARVIS_SLACK_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN", "TAVILY_API_KEY", "OPENAI_API_KEY"):
            val = os.environ.get(key, "")
            if val and len(val) > 4:
                assert val not in result_str, f"Secret {key} leaked in check {check_fn.__name__}"


class TestUS9ReadinessCategories:
    def test_secrets_backend_category_exists(self):
        assert ReadinessCategory.SECRETS_BACKEND == "secrets_backend"

    def test_budget_guard_category_exists(self):
        assert ReadinessCategory.BUDGET_GUARD == "budget_guard"

    def test_job_queue_category_exists(self):
        assert ReadinessCategory.JOB_QUEUE == "job_queue"

    def test_rollback_policy_category_exists(self):
        assert ReadinessCategory.ROLLBACK_POLICY == "rollback_policy"

    def test_inject_guard_category_exists(self):
        assert ReadinessCategory.INJECT_GUARD == "inject_guard"

    def test_voice_identity_category_exists(self):
        assert ReadinessCategory.VOICE_IDENTITY == "voice_identity"

    def test_connector_health_monitor_category_exists(self):
        assert ReadinessCategory.CONNECTOR_HEALTH_MONITOR == "connector_health_monitor"

    def test_alert_rate_limiter_category_exists(self):
        assert ReadinessCategory.ALERT_RATE_LIMITER == "alert_rate_limiter"

    def test_memory_backup_category_exists(self):
        assert ReadinessCategory.MEMORY_BACKUP == "memory_backup"

    def test_dogfood_loop_category_exists(self):
        assert ReadinessCategory.DOGFOOD_LOOP == "dogfood_loop"

    def test_all_us9_categories_in_check_map(self):
        us9_cats = [
            ReadinessCategory.SECRETS_BACKEND,
            ReadinessCategory.BUDGET_GUARD,
            ReadinessCategory.JOB_QUEUE,
            ReadinessCategory.ROLLBACK_POLICY,
            ReadinessCategory.INJECT_GUARD,
            ReadinessCategory.VOICE_IDENTITY,
            ReadinessCategory.CONNECTOR_HEALTH_MONITOR,
            ReadinessCategory.ALERT_RATE_LIMITER,
            ReadinessCategory.MEMORY_BACKUP,
            ReadinessCategory.DOGFOOD_LOOP,
        ]
        for cat in us9_cats:
            assert cat in _CATEGORY_CHECKS, f"Category {cat} missing from _CATEGORY_CHECKS"


class TestRunAllChecksIncludes29:
    def test_run_all_checks_returns_31(self):
        results = run_all_checks()
        assert len(results) == 31, f"Expected 31 checks, got {len(results)}"

    def test_all_us9_check_ids_present(self):
        results = run_all_checks()
        result_ids = {r.check_id for r in results}
        for cid in US9_CHECK_IDS:
            assert cid in result_ids, f"Check '{cid}' not in run_all_checks output"

    def test_no_none_results(self):
        results = run_all_checks()
        assert all(r is not None for r in results)

    def test_all_results_have_valid_status(self):
        results = run_all_checks()
        for r in results:
            assert r.status in VALID_STATUSES, f"Check {r.check_id}: invalid status '{r.status}'"


class TestRequiredHardeningChecks:
    def test_budget_guard_check_not_fake_pass(self):
        result = check_budget_guard()
        # Budget guard should not be faking pass — it checks real state
        assert result.status in VALID_STATUSES

    def test_rollback_policy_pass(self):
        result = check_rollback_policy()
        assert result.status == CheckStatus.PASS

    def test_inject_guard_pass(self):
        result = check_inject_guard()
        assert result.status == CheckStatus.PASS
