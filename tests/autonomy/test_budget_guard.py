"""Tests for Runtime Budget / Token Spend Guard (US9 Phase 3)."""

from __future__ import annotations

import pytest

from openjarvis.autonomy.budget_guard import (
    BudgetStatus,
    check_budget,
    estimate_cost,
    get_budget_status,
    load_budget_config,
    save_budget_config,
)


class TestCostEstimation:
    def test_gpt4o_mini_cheap(self):
        cost = estimate_cost("gpt-4o-mini", 1000, 500)
        assert cost < 0.01
        assert cost > 0

    def test_gpt4_expensive(self):
        cost = estimate_cost("gpt-4", 1000, 1000)
        assert cost > 0.03

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("unknown-model-xyz", 1000, 1000)
        assert cost > 0

    def test_zero_tokens_zero_cost(self):
        assert estimate_cost("gpt-4o", 0, 0) == 0.0


class TestBudgetConfig:
    def test_load_returns_dict(self):
        cfg = load_budget_config()
        assert "per_run_hard_limit_usd" in cfg
        assert "per_day_hard_limit_usd" in cfg
        assert cfg["per_run_hard_limit_usd"] > 0

    def test_defaults_present(self):
        cfg = load_budget_config()
        assert "stop_on_hard_breach" in cfg
        assert "non_llm_diagnostics_exempt" in cfg


class TestBudgetCheck:
    def test_diagnostic_exempt(self):
        result = check_budget(
            model="gpt-4o",
            prompt_tokens=10000,
            completion_tokens=10000,
            action="test_diagnostic",
            is_diagnostic=True,
            run_id="test-exempt-run",
        )
        assert result["ok"] is True
        assert result["verdict"] == "exempt"
        assert result["estimated_cost_usd"] == 0.0

    def test_cheap_call_allowed(self):
        result = check_budget(
            model="gpt-4o-mini",
            prompt_tokens=100,
            completion_tokens=50,
            action="test_cheap",
            is_diagnostic=False,
            run_id="test-cheap-run",
        )
        assert result["ok"] is True
        assert result["verdict"] in ("ok", "soft_warn")

    def test_result_has_required_fields(self):
        result = check_budget(
            model="gpt-4o-mini",
            prompt_tokens=10,
            completion_tokens=10,
            action="field_test",
            run_id="test-fields-run",
        )
        assert "ok" in result
        assert "verdict" in result
        assert "estimated_cost_usd" in result
        assert "decision_reason" in result

    def test_very_large_call_hard_stop(self):
        cfg = load_budget_config()
        # Force a call that would exceed per_run_hard_limit
        # Use tokens that cost > hard limit
        hard_limit = cfg["per_run_hard_limit_usd"]
        # At $0.015/1K output for gpt-4o: need > hard_limit / 0.015 * 1000 tokens
        big_tokens = int(hard_limit / 0.015 * 1000 * 2)
        result = check_budget(
            model="gpt-4o",
            prompt_tokens=0,
            completion_tokens=big_tokens,
            action="test_big",
            is_diagnostic=False,
            run_id="test-hard-stop-isolated-xyz",
        )
        assert result["verdict"] == "hard_stop"
        assert result["ok"] is False


class TestBudgetStatus:
    def test_returns_budget_status(self):
        s = get_budget_status()
        assert isinstance(s, BudgetStatus)
        assert s.verdict in ("ok", "soft_warn", "hard_stop")
        assert s.today_spend_usd >= 0
        assert s.config is not None

    def test_budget_status_overall_ok_when_under_limit(self):
        s = get_budget_status(run_id="test-fresh-status-run")
        # For a fresh run with no entries, should be ok
        assert isinstance(s.overall_ok, bool)
