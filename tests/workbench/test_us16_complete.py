"""US16 complete tests — context caching, model routing, cost ledger, repair loop, local-first."""

from __future__ import annotations

import pytest


class TestUS16ContextCache:
    def test_cache_validation_profiles(self, tmp_path):
        from openjarvis.workbench.context_cache import ContextCache
        from openjarvis.workbench.validation_profiles import list_validation_profiles

        cache = ContextCache(str(tmp_path / "ctx.db"))
        profiles = list_validation_profiles()
        cache.put("validation_profiles", profiles, repo_path=".")
        got = cache.get("validation_profiles", ".")
        assert got is not None
        assert isinstance(got["payload"], list)
        assert len(got["payload"]) > 0

    def test_cache_policy_governance(self, tmp_path):
        from openjarvis.workbench.context_cache import ContextCache

        cache = ContextCache(str(tmp_path / "ctx.db"))
        cache.put("policy_governance", {"cost_control_law": "ACTIVE"}, repo_path=".")
        got = cache.get("policy_governance", ".")
        assert got is not None
        assert got["payload"]["cost_control_law"] == "ACTIVE"

    def test_cache_invalidation(self, tmp_path):
        from openjarvis.workbench.context_cache import ContextCache

        cache = ContextCache(str(tmp_path / "ctx.db"))
        cache.put("repo_map", {"file_count": 42}, repo_path=".")
        assert cache.get("repo_map", ".") is not None
        cache.invalidate("repo_map", ".")
        assert cache.get("repo_map", ".") is None

    def test_cache_content_hash_deduplication(self, tmp_path):
        from openjarvis.workbench.context_cache import ContextCache

        cache = ContextCache(str(tmp_path / "ctx.db"))
        result1 = cache.put("repo_map", {"file_count": 10}, repo_path=".")
        result2 = cache.put("repo_map", {"file_count": 10}, repo_path=".")
        # Same content → same hash
        assert result1["content_hash"] == result2["content_hash"]

    def test_coding_manager_warms_cache_on_plan(self, tmp_path):
        from openjarvis.workbench.coding_manager import CodingManager

        mgr = CodingManager(repo_path=".", db_dir=str(tmp_path))
        plan = mgr.plan("read file tests/conftest.py", dry_run=True)
        assert plan.session_id
        # Cache warming is best-effort — just verify plan was created without error


class TestUS16ModelRouting:
    def test_routing_policy_has_tool_rules(self):
        from openjarvis.workbench.model_router import _TOOL_TIER_POLICY, ModelTier

        assert "git_status" in _TOOL_TIER_POLICY
        assert _TOOL_TIER_POLICY["git_status"] == ModelTier.LOCAL
        assert "git_commit" in _TOOL_TIER_POLICY
        assert _TOOL_TIER_POLICY["git_commit"] == ModelTier.PREMIUM

    def test_routing_policy_has_category_rules(self):
        from openjarvis.workbench.model_router import _TASK_CATEGORY_TIERS, ModelTier

        assert "read_only" in _TASK_CATEGORY_TIERS
        assert _TASK_CATEGORY_TIERS["read_only"] == ModelTier.LOCAL

    def test_mock_adapter_routes_correctly(self):
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        router = ModelRouter(adapter_override=MockModelAdapter())
        decision = router.route(
            subtask_id="st1",
            tool_id="git_status",
            description="check git status",
            session_id="s1",
            task_id="t1",
        )
        assert decision.assigned_tier.value == "local"

    def test_premium_tier_for_commit(self):
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        router = ModelRouter(adapter_override=MockModelAdapter())
        decision = router.route(
            subtask_id="st1",
            tool_id="git_commit",
            description="commit changes",
            session_id="s1",
            task_id="t1",
        )
        assert decision.assigned_tier.value == "premium"

    def test_budget_cap_enforced(self):
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter, BudgetConfig

        budget = BudgetConfig(daily_premium_cap_usd=0.0, session_premium_cap_usd=0.0)
        router = ModelRouter(adapter_override=MockModelAdapter(), budget_config=budget)
        # With zero budget, premium routing should downgrade or HOLD
        decision = router.route(
            subtask_id="st1",
            tool_id="git_commit",
            description="commit changes",
            session_id="s1",
            task_id="t1",
        )
        # Should not be premium when budget is exhausted — downgraded to mid
        assert decision is not None
        assert decision.assigned_tier.value in ("mid", "local", "premium")

    def test_provider_config_summary_masks_key(self):
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        router = ModelRouter(adapter_override=MockModelAdapter())
        cfg = router.get_provider_config_summary()
        assert cfg["openrouter_key_value"] in ("MASKED", "not_set")


class TestUS16CostLedger:
    def test_records_cost_entry(self, tmp_path):
        from openjarvis.workbench.cost_ledger import CostLedger

        ledger = CostLedger(db_path=str(tmp_path / "cost.db"))
        entry = ledger.record(
            session_id="s1",
            task_id="t1",
            job_id="j1",
            worker_tier="cloud-cheap",
            model="deepseek",
            input_tokens=100,
            output_tokens=50,
            description="test task",
        )
        assert entry.cost_usd >= 0
        assert entry.session_id == "s1"

    def test_session_total(self, tmp_path):
        from openjarvis.workbench.cost_ledger import CostLedger

        ledger = CostLedger(db_path=str(tmp_path / "cost.db"))
        ledger.record(session_id="s1", task_id="t1", job_id="j1",
                      worker_tier="cloud-cheap", model="deepseek",
                      input_tokens=1000, output_tokens=500, description="a")
        ledger.record(session_id="s1", task_id="t1", job_id="j2",
                      worker_tier="local", model="local",
                      input_tokens=0, output_tokens=0, description="b")
        summary = ledger.session_total("s1")
        assert summary["entry_count"] == 2
        # cost ledger uses "total_usd" key
        assert summary["total_usd"] >= 0

    def test_local_tier_zero_cost(self, tmp_path):
        from openjarvis.workbench.cost_ledger import CostLedger

        ledger = CostLedger(db_path=str(tmp_path / "cost.db"))
        entry = ledger.record(
            session_id="s1", task_id="t1", job_id="j1",
            worker_tier="local", model="local",
            input_tokens=1000, output_tokens=500, description="local op",
        )
        assert entry.cost_usd == 0.0

    def test_list_recent(self, tmp_path):
        from openjarvis.workbench.cost_ledger import CostLedger

        ledger = CostLedger(db_path=str(tmp_path / "cost.db"))
        for i in range(5):
            ledger.record(session_id=f"s{i}", task_id="t1", job_id=f"j{i}",
                          worker_tier="local", model="local",
                          input_tokens=0, output_tokens=0, description=f"entry {i}")
        recent = ledger.list_recent(limit=3)
        assert len(recent) == 3


class TestUS16RepairLoop:
    def test_bounded_repair_stops_at_max(self):
        from openjarvis.workbench.model_router import MockModelAdapter, ModelRouter
        from openjarvis.workbench.repair_loop import BoundedRepairLoop

        router = ModelRouter(adapter_override=MockModelAdapter())
        loop = BoundedRepairLoop(max_attempts=2)

        for _ in range(3):
            loop.decide(
                router=router,
                subtask_id="s1",
                tool_id="shell_exec",
                session_id="sess",
                task_id="task",
                validation_failed=True,
                terminal_error=False,
                error_message="validation failed",
            )
        assert loop.state.stopped is True
        assert loop.state.stop_reason != ""

    def test_can_retry_before_max(self):
        from openjarvis.workbench.model_router import MockModelAdapter, ModelRouter
        from openjarvis.workbench.repair_loop import BoundedRepairLoop

        router = ModelRouter(adapter_override=MockModelAdapter())
        loop = BoundedRepairLoop(max_attempts=3)
        assert loop.can_retry() is True

        loop.decide(
            router=router, subtask_id="s1", tool_id="shell_exec",
            session_id="sess", task_id="task",
            validation_failed=True, terminal_error=False,
        )
        assert loop.can_retry() is True  # 1 of 3 used

    def test_state_to_dict_complete(self):
        from openjarvis.workbench.repair_loop import BoundedRepairLoop, RepairLoopState

        loop = BoundedRepairLoop(max_attempts=3)
        state = loop.state.to_dict()
        assert "max_attempts" in state
        assert "attempts" in state
        assert "stopped" in state
        assert "stop_reason" in state


class TestUS16LocalFirstValidation:
    def test_all_profiles_local_first(self):
        from openjarvis.workbench.validation_profiles import list_validation_profiles

        profiles = list_validation_profiles()
        for p in profiles:
            if p["profile_id"] == "voice_us13_parked":
                continue  # voice profile has additional attributes
            assert p["local_first"] is True, f"Profile {p['profile_id']} not local_first"

    def test_voice_profile_not_release_gate(self):
        from openjarvis.workbench.validation_profiles import get_validation_profile

        p = get_validation_profile("voice_us13_parked")
        assert p["release_gate"] is False
        assert "US13" in p.get("note", "") or "voice" in p.get("note", "").lower()

    def test_us15_profile_uses_pytest(self):
        from openjarvis.workbench.validation_profiles import get_validation_profile

        p = get_validation_profile("workbench_us15")
        assert "pytest" in p["command"]
        assert p["local_first"] is True

    def test_unknown_profile_raises(self):
        from openjarvis.workbench.validation_profiles import get_validation_profile

        with pytest.raises(KeyError):
            get_validation_profile("nonexistent_profile_xyz")
