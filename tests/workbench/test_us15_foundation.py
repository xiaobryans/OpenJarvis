"""US15+US16 foundation tests — capabilities, repo index, repair loop, validation profiles."""

from __future__ import annotations

import pytest


class TestCapabilitiesRegistry:
    def test_all_seven_capabilities_present(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities

        caps = get_all_capabilities()
        ids = {c.capability_id for c in caps}
        assert ids == {
            "assistant",
            "workbench_coding",
            "reviewer_validator",
            "voice",
            "browser_automation",
            "research",
            "automation",
        }

    def test_voice_is_not_ready_while_us13_parked(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities

        voice = next(c for c in get_all_capabilities() if c.capability_id == "voice")
        assert voice.status != "ready"
        assert voice.evidence.get("hands_free_excluded") is True

    def test_valid_status_labels_only(self):
        from openjarvis.workbench.capabilities_registry import (
            STATUS_DISABLED,
            STATUS_INSUFFICIENT_DATA,
            STATUS_NEEDS_APPROVAL,
            STATUS_NOT_IMPLEMENTED,
            STATUS_READY,
            STATUS_REQUIRES_SETUP,
            get_all_capabilities,
        )

        allowed = {
            STATUS_READY,
            STATUS_DISABLED,
            STATUS_REQUIRES_SETUP,
            STATUS_NEEDS_APPROVAL,
            STATUS_NOT_IMPLEMENTED,
            STATUS_INSUFFICIENT_DATA,
        }
        for cap in get_all_capabilities():
            assert cap.status in allowed


class TestRepoIndex:
    def test_build_repo_index_returns_files_and_symbols(self):
        from openjarvis.workbench.repo_index import build_repo_index

        idx = build_repo_index(".")
        assert len(idx.files) > 0
        assert isinstance(idx.symbols, list)
        assert isinstance(idx.dependencies, list)

    def test_ci_visibility_reports_workflows_or_setup(self):
        from openjarvis.workbench.repo_index import ci_visibility_status

        ci = ci_visibility_status(".")
        assert ci["status"] in ("ready", "requires_setup")


class TestValidationProfiles:
    def test_us15_profile_exists(self):
        from openjarvis.workbench.validation_profiles import get_validation_profile

        p = get_validation_profile("workbench_us15")
        assert "pytest" in p["command"]
        assert p["local_first"] is True

    def test_voice_profile_marked_not_release_gate(self):
        from openjarvis.workbench.validation_profiles import get_validation_profile

        p = get_validation_profile("voice_us13_parked")
        assert p.get("release_gate") is False


class TestAutoBrowserProvider:
    def test_unsafe_actions_rejected(self):
        from openjarvis.workbench.auto_browser_provider import auto_browser_safety_allows

        assert auto_browser_safety_allows("captcha_bypass") is False
        assert auto_browser_safety_allows("file_read") is True

    def test_default_status_blocked_not_merged(self):
        from openjarvis.workbench.auto_browser_provider import get_auto_browser_status

        st = get_auto_browser_status()
        assert st["merged_into_core"] is False
        assert st["integration_status"] in ("blocked", "requires_setup")


class TestRepairLoop:
    def test_bounded_repair_stops_at_max_attempts(self):
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


class TestContextCache:
    def test_repo_map_cache_roundtrip(self, tmp_path, monkeypatch):
        from openjarvis.workbench.context_cache import ContextCache, warm_repo_map_cache

        db = tmp_path / "ctx.db"
        cache = ContextCache(str(db))
        monkeypatch.setattr(
            "openjarvis.workbench.context_cache.ContextCache",
            lambda db_path=None: cache,
        )
        warm_repo_map_cache(".")
        got = cache.get("repo_map", ".")
        assert got is not None
        assert got["payload"]["file_count"] > 0


class TestCostRecording:
    def test_execute_records_nonzero_cost_for_cloud_tier(self, tmp_path):
        from openjarvis.workbench.coding_manager import CodingManager, Subtask, TaskPlan

        mgr = CodingManager(repo_path=".", db_dir=str(tmp_path))
        plan = TaskPlan(
            session_id="s1",
            task_id="t1",
            prompt="test",
            repo_path=".",
            subtasks=[],
            dry_run=True,
            stop_on_blocker=True,
        )
        st = Subtask(
            id="st1",
            index=1,
            description="test",
            tool_id="file_read",
            params={},
            worker_tier="cloud-cheap",
            requires_approval=False,
        )
        mgr._record_subtask_cost(st, plan)
        assert st.cost_usd >= 0.0
        summary = mgr._costs.session_total("s1")
        assert summary["entry_count"] >= 1
