"""Tests proving the Workbench planner correctly classifies prompts and generates
scoped plans — US14A planner remediation.

Test coverage:
1. Complex prompt does NOT default to test_us14a_fixture.py
2. Complex prompt creates discovery/planning subtasks before write subtasks
3. "Plan only / do not edit files" prompt creates no file_write/commit/push subtasks
4. Tiny marker prompt may still use fixture workflow
5. Bug fix prompt identifies likely relevant files from prompt keywords
6. Planner output includes risks, validation commands, and approval gates for complex prompts
7. Existing small live-task behavior is not broken
8. Routing/cost ledger still records decisions
"""
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mgr(tmp_path):
    from openjarvis.workbench.coding_manager import CodingManager
    from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

    router = ModelRouter(
        db_path=str(tmp_path / "routing.db"),
        adapter_override=MockModelAdapter(),
    )
    return CodingManager(
        repo_path=str(tmp_path),
        db_dir=str(tmp_path),
        model_router=router,
    )


# ---------------------------------------------------------------------------
# Test 1: Complex prompt does NOT write test_us14a_fixture.py
# ---------------------------------------------------------------------------


class TestComplexPromptNoFixtureFile:
    def test_complex_prompt_not_fixture_marker(self, mgr):
        """Complex implementation prompt must not produce a file_write to the fixture path."""
        plan = mgr.plan(
            "Plan and implement the US14A.1 PA Chat-to-Workbench bridge feature",
            dry_run=True,
        )
        write_paths = [
            st.params.get("path", "")
            for st in plan.subtasks
            if st.tool_id == "file_write"
        ]
        assert not any("test_us14a_fixture" in p for p in write_paths), (
            f"Complex prompt produced file_write to fixture path: {write_paths}"
        )

    def test_complex_prompt_task_type(self, mgr):
        plan = mgr.plan("Implement the notification autopilot bridge feature", dry_run=True)
        assert plan.task_type == "complex_implementation"


# ---------------------------------------------------------------------------
# Test 2: Complex prompt creates discovery subtasks before any write subtasks
# ---------------------------------------------------------------------------


class TestComplexPromptDiscoveryFirst:
    def test_discovery_subtasks_precede_writes(self, mgr):
        """Complex prompt: discovery (git_status, file_search, file_read) must precede writes."""
        plan = mgr.plan("Implement US14A.1 PA Chat-to-Workbench bridge", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        write_indices = [i for i, t in enumerate(tool_ids) if t == "file_write"]
        read_indices = [
            i for i, t in enumerate(tool_ids)
            if t in ("file_read", "file_search", "git_status", "git_diff")
        ]
        if write_indices:
            assert min(read_indices) < min(write_indices), (
                "Discovery subtasks must precede write subtasks"
            )
        else:
            assert len(read_indices) > 0, "Complex prompt must have discovery subtasks"

    def test_complex_prompt_has_no_default_file_write(self, mgr):
        """Complex implementation prompts must NOT generate a file_write by default."""
        plan = mgr.plan("Implement the sprint remediation planner", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_write" not in tool_ids, (
            "Complex prompt must not include file_write without approval"
        )

    def test_complex_prompt_no_commit_or_push(self, mgr):
        """Complex implementation prompts must NOT include git_commit or git_push by default."""
        plan = mgr.plan("Implement the US14B notification autopilot feature", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "git_commit" not in tool_ids
        assert "git_push" not in tool_ids


# ---------------------------------------------------------------------------
# Test 3: "Plan only" prompt creates no file_write, git_commit, or git_push
# ---------------------------------------------------------------------------


class TestPlanOnlyPrompt:
    def test_plan_only_no_writes(self, mgr):
        """'Do not edit files yet' prompt must produce no file_write/commit/push subtasks."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_write" not in tool_ids, "plan_only must not have file_write"
        assert "git_commit" not in tool_ids, "plan_only must not have git_commit"
        assert "git_push" not in tool_ids, "plan_only must not have git_push"

    def test_plan_only_task_type(self, mgr):
        plan = mgr.plan("Plan only — do not write any files", dry_run=True)
        assert plan.task_type == "planning_only"

    def test_planning_only_phrase_variant(self, mgr):
        plan = mgr.plan("plan only: review coding_manager planner logic", dry_run=True)
        assert plan.task_type == "planning_only"
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_write" not in tool_ids
        assert "git_commit" not in tool_ids
        assert "git_push" not in tool_ids


# ---------------------------------------------------------------------------
# Test 4: Tiny marker prompt still uses fixture workflow
# ---------------------------------------------------------------------------


class TestTinyMarkerPrompt:
    def test_tiny_marker_task_type(self, mgr):
        """Tiny marker prompts must be classified as tiny_marker."""
        plan = mgr.plan("Add a US14A self-test fixture and marker", dry_run=True)
        assert plan.task_type == "tiny_marker"

    def test_tiny_marker_still_produces_subtasks(self, mgr):
        """Tiny marker prompt must still produce a real subtask plan."""
        plan = mgr.plan("Add self-test fixture", dry_run=True)
        assert len(plan.subtasks) > 0
        assert plan.subtasks[0].tool_id == "git_status"

    def test_tiny_marker_may_write_fixture(self, mgr):
        """Tiny marker workflow is allowed to produce a file_write to the fixture path."""
        plan = mgr.plan("Add a self-test fixture marker for E2E proof", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert plan.task_type == "tiny_marker"
        assert "git_status" in tool_ids


# ---------------------------------------------------------------------------
# Test 5: Bug fix prompt identifies likely relevant files
# ---------------------------------------------------------------------------


class TestBugFixPrompt:
    def test_bug_fix_identifies_coding_manager(self, mgr):
        """Bug fix prompt mentioning coding_manager must identify that file."""
        plan = mgr.plan(
            "Fix the bug in coding_manager planner where complex prompts default to fixture marker",
            dry_run=True,
        )
        assert plan.task_type == "bug_fix"
        assert any("coding_manager" in f for f in plan.likely_files), (
            f"Expected coding_manager in likely_files, got: {plan.likely_files}"
        )

    def test_bug_fix_identifies_workbench_routes(self, mgr):
        """Bug fix prompt mentioning workbench_routes must identify that file."""
        plan = mgr.plan(
            "Fix the broken endpoint in workbench_routes that returns 500",
            dry_run=True,
        )
        assert plan.task_type == "bug_fix"
        assert any("workbench" in f for f in plan.likely_files)

    def test_bug_fix_has_validation_subtask(self, mgr):
        """Bug fix plans must include a validation subtask."""
        plan = mgr.plan("Fix the regression in model_router tier assignment", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "shell_exec" in tool_ids, "Bug fix plan must include validation step"

    def test_bug_fix_no_default_commit(self, mgr):
        """Bug fix plans must not include git_commit by default."""
        plan = mgr.plan("Fix the crash in cost_ledger when session is empty", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "git_commit" not in tool_ids
        assert "git_push" not in tool_ids


# ---------------------------------------------------------------------------
# Test 6: Complex prompts include risks, validation commands, approval gates
# ---------------------------------------------------------------------------


class TestComplexPlanningMetadata:
    def test_complex_has_risks(self, mgr):
        """Complex implementation plans must include risk assessments."""
        plan = mgr.plan("Implement US14A.1 PA Chat-to-Workbench bridge", dry_run=True)
        assert len(plan.risks) > 0, "Complex plan must have risk assessments"

    def test_complex_has_validation_commands(self, mgr):
        """Complex implementation plans must include validation commands."""
        plan = mgr.plan("Implement the notification autopilot feature", dry_run=True)
        assert len(plan.validation_commands) > 0

    def test_complex_has_approval_gates(self, mgr):
        """Complex implementation plans must include approval gates."""
        plan = mgr.plan("Implement the remediation planner logic", dry_run=True)
        assert len(plan.approval_gates) > 0
        assert any("Gate" in g for g in plan.approval_gates)

    def test_planning_only_risk_mentions_insufficient_data(self, mgr):
        """Planning-only risk assessment must flag insufficient data."""
        plan = mgr.plan("Plan only — describe planner decomposition", dry_run=True)
        assert any("Insufficient data" in r for r in plan.risks)

    def test_complex_risk_mentions_insufficient_data(self, mgr):
        """Complex plan risk assessment must flag insufficient data until discovery."""
        plan = mgr.plan("Implement the US14B feature sprint", dry_run=True)
        assert any("Insufficient data" in r for r in plan.risks)


# ---------------------------------------------------------------------------
# Test 7: Existing small live-task behavior is not broken
# ---------------------------------------------------------------------------


class TestSmallTaskBehaviorUnchanged:
    def test_small_task_git_status_first(self, mgr):
        """All plans must start with git_status."""
        for prompt in ("Add a test fixture", "Review changes", "Inspect repo status"):
            plan = mgr.plan(prompt, dry_run=True)
            assert plan.subtasks[0].tool_id == "git_status", (
                f"First subtask must be git_status for prompt: {prompt!r}"
            )

    def test_tiny_marker_has_commit_push(self, mgr):
        """Tiny marker prompts must still include commit and push in the plan."""
        plan = mgr.plan("Add a test fixture file", dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "git_commit" in tool_ids
        assert "git_push" in tool_ids

    def test_dry_run_skips_commit_push_for_tiny_marker(self, mgr):
        """Dry-run must still skip commit/push even for tiny marker plans."""
        plan = mgr.plan("Add fixture", dry_run=True)
        plan = mgr.execute(plan)
        for st in plan.subtasks:
            if st.tool_id in ("git_commit", "git_push"):
                assert st.status == "skipped_dry_run", (
                    f"Expected skipped_dry_run for {st.tool_id}, got {st.status}"
                )

    def test_plan_returns_task_plan_instance(self, mgr):
        """plan() must return a TaskPlan instance with required fields."""
        from openjarvis.workbench.coding_manager import TaskPlan
        plan = mgr.plan("Add a test fixture", dry_run=True)
        assert isinstance(plan, TaskPlan)
        assert plan.session_id
        assert plan.task_id
        assert len(plan.subtasks) > 0


# ---------------------------------------------------------------------------
# Test 8: Routing/cost ledger still records decisions
# ---------------------------------------------------------------------------


class TestRoutingLedgerIntegrity:
    def test_complex_plan_produces_routing_log(self, mgr):
        """Routing log must be populated for complex plans."""
        plan = mgr.plan("Implement the US14A.1 feature sprint", dry_run=True)
        log = mgr.get_routing_log(plan.session_id)
        assert len(log) > 0, "Routing log must have entries after planning"

    def test_planning_only_produces_routing_log(self, mgr):
        """Routing log must be populated even for plan-only prompts."""
        plan = mgr.plan("Plan only — review the planner logic", dry_run=True)
        log = mgr.get_routing_log(plan.session_id)
        assert len(log) > 0

    def test_bug_fix_produces_routing_log(self, mgr):
        """Routing log must be populated for bug fix plans."""
        plan = mgr.plan("Fix the broken model_router tier assignment", dry_run=True)
        log = mgr.get_routing_log(plan.session_id)
        assert len(log) > 0

    def test_routing_log_has_git_status_local(self, mgr):
        """git_status subtasks must always route to local tier."""
        plan = mgr.plan("Add a test fixture", dry_run=True)
        log = mgr.get_routing_log(plan.session_id)
        tiers = {e["tool_id"]: e["assigned_tier"] for e in log}
        assert tiers.get("git_status") == "local"

    def test_cost_summary_includes_routing(self, mgr):
        """Cost summary must include routing section after any plan."""
        plan = mgr.plan("Implement the notification autopilot", dry_run=True)
        summary = mgr.get_cost_summary(plan.session_id)
        assert "routing" in summary


# ---------------------------------------------------------------------------
# Standalone: classify_prompt unit tests
# ---------------------------------------------------------------------------


class TestClassifyPrompt:
    def test_classify_plan_only(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        assert classify_prompt("plan only — do not edit any files") == "planning_only"
        assert classify_prompt("do not write files yet, planning only") == "planning_only"

    def test_classify_tiny_marker(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        assert classify_prompt("Add a self-test fixture marker") == "tiny_marker"
        assert classify_prompt("Add US14A e2e proof marker") == "tiny_marker"

    def test_classify_bug_fix(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        assert classify_prompt("Fix the broken route in workbench_routes") == "bug_fix"
        assert classify_prompt("Fix regression in cost_ledger") == "bug_fix"

    def test_classify_complex_implementation(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        assert classify_prompt("Implement US14A.1 PA Chat bridge") == "complex_implementation"
        assert classify_prompt("Implement the notification autopilot feature") == "complex_implementation"

    def test_classify_research(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        assert classify_prompt("Research the model_router escalation logic") == "research"
        assert classify_prompt("Investigate the model tier routing behavior") == "research"

    def test_classify_documentation(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        assert classify_prompt("Update the README with workbench usage") == "documentation"

    def test_complex_overrides_marker(self):
        from openjarvis.workbench.coding_manager import classify_prompt
        result = classify_prompt("Implement us14a.1 bridge with self-test marker")
        assert result == "complex_implementation"


# ---------------------------------------------------------------------------
# Tests for US14A.1 likely-files hints (new in follow-up)
# ---------------------------------------------------------------------------


class TestUS14A1LikelyFiles:
    """Prove that US14A.1-relevant prompts return non-empty likely_files."""

    def test_pa_chat_workbench_prompt_non_empty_likely_files(self, mgr):
        """PA Chat-to-Workbench prompt must return non-empty likely_files."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        assert len(plan.likely_files) > 0, (
            "PA Chat-to-Workbench prompt must return non-empty likely_files"
        )

    def test_pa_chat_workbench_includes_routes_or_workbench(self, mgr):
        """PA Chat-to-Workbench prompt must identify chat routes or workbench routes."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        relevant = [f for f in plan.likely_files if "route" in f or "workbench" in f or "chat" in f.lower()]
        assert len(relevant) > 0, (
            f"Expected chat/workbench route files in likely_files, got: {plan.likely_files}"
        )

    def test_exact_us14a1_prompt_not_empty(self, mgr):
        """The exact US14A.1 prompt must not return likely_files: []."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        assert plan.likely_files != [], (
            "Exact US14A.1 prompt returned empty likely_files"
        )

    def test_notifications_prompt_returns_notification_files(self, mgr):
        """Notifications prompt must return relevant notification/Slack/Telegram files."""
        plan = mgr.plan(
            "Add Slack and Telegram notification events for workbench approval queue",
            dry_run=True,
        )
        assert len(plan.likely_files) > 0
        notification_files = [
            f for f in plan.likely_files
            if any(kw in f for kw in ("slack", "telegram", "notify", "notif"))
        ]
        assert len(notification_files) > 0, (
            f"Expected slack/telegram/notify files in likely_files, got: {plan.likely_files}"
        )

    def test_autopilot_approval_prompt_returns_governance_files(self, mgr):
        """Autopilot/approval prompt must return relevant approval/governance files."""
        plan = mgr.plan(
            "Plan guarded autopilot with approval policy for workbench tasks",
            dry_run=True,
        )
        assert len(plan.likely_files) > 0
        governance_files = [
            f for f in plan.likely_files
            if any(kw in f for kw in ("approval", "autopilot", "automati", "governance", "constitution", "polic"))
        ]
        assert len(governance_files) > 0, (
            f"Expected approval/governance files in likely_files, got: {plan.likely_files}"
        )

    def test_model_routing_prompt_returns_router_and_ledger(self, mgr):
        """Model routing prompt must return model_router, cost_ledger, and model_catalog."""
        plan = mgr.plan(
            "Investigate model routing provider cost ledger decisions",
            dry_run=True,
        )
        assert len(plan.likely_files) > 0, f"likely_files must not be empty"
        lf = plan.likely_files
        assert any("model_router" in f for f in lf), (
            f"Expected model_router.py in likely_files, got: {lf}"
        )
        assert any("cost_ledger" in f for f in lf), (
            f"Expected cost_ledger.py in likely_files, got: {lf}"
        )
        assert any("model_catalog" in f for f in lf), (
            f"Expected model_catalog.py in likely_files, got: {lf}"
        )

    def test_complex_impl_prompt_likely_files_non_empty(self, mgr):
        """Complex implementation bridge/notification/autopilot prompt must have non-empty likely_files."""
        plan = mgr.plan(
            "Implement PA Chat-to-Workbench bridge with unified notifications and guarded autopilot."
            " Plan scoped implementation first.",
            dry_run=True,
        )
        assert plan.task_type == "complex_implementation"
        assert len(plan.likely_files) > 0
        assert "file_write" not in [s.tool_id for s in plan.subtasks]
        assert "git_commit" not in [s.tool_id for s in plan.subtasks]
        assert "git_push" not in [s.tool_id for s in plan.subtasks]


# ---------------------------------------------------------------------------
# US14A.1 Preflight: Search scope, timeout handling, dry-run safety
# ---------------------------------------------------------------------------


class TestSearchScopeAndErrorHandling:
    """Prove that complex/planning_only prompts never search the full repo root."""

    def test_planning_only_no_file_search_subtask(self, mgr):
        """planning_only prompts must not create a file_search subtask.

        They use file_read of likely files instead to avoid full-repo scans.
        """
        plan = mgr.plan(
            "plan only: review coding_manager logic and planner decomposition patterns",
            dry_run=True,
        )
        assert plan.task_type == "planning_only"
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_search" not in tool_ids, (
            f"planning_only must not create file_search subtask, got: {tool_ids}"
        )

    def test_complex_no_file_search_subtask(self, mgr):
        """complex_implementation prompts must not create a file_search subtask.

        They use file_read of likely files instead to avoid full-repo scans.
        """
        plan = mgr.plan(
            "Implement PA Chat-to-Workbench bridge with unified notifications and guarded autopilot."
            " Plan scoped implementation first.",
            dry_run=True,
        )
        assert plan.task_type == "complex_implementation"
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_search" not in tool_ids, (
            f"complex_implementation must not create file_search subtask, got: {tool_ids}"
        )

    def test_exact_us14a1_dry_run_prompt_no_file_search(self, mgr):
        """The exact E2E dry-run prompt must not produce a file_search subtask."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        assert plan.task_type == "planning_only"
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_search" not in tool_ids, (
            f"Exact US14A.1 dry-run prompt must not create file_search, got: {tool_ids}"
        )

    def test_bug_fix_uses_bounded_dir(self, tmp_path):
        """bug_fix file_search must use a bounded subdirectory, not the full repo root."""
        from openjarvis.workbench.coding_manager import CodingManager
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        (tmp_path / "src" / "openjarvis" / "server").mkdir(parents=True)
        router = ModelRouter(
            db_path=str(tmp_path / "routing.db"),
            adapter_override=MockModelAdapter(),
        )
        mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)

        plan = mgr.plan("Fix the broken search timeout bug in workbench_routes", dry_run=True)
        search_subtasks = [st for st in plan.subtasks if st.tool_id == "file_search"]
        assert len(search_subtasks) > 0, "bug_fix must create at least one file_search subtask"
        for st in search_subtasks:
            assert st.params["directory"] != str(tmp_path), (
                f"file_search must not use the full repo root {tmp_path!r}, "
                f"got directory={st.params['directory']!r}"
            )
            assert "exclude_dirs" in st.params, (
                "file_search params must include exclude_dirs to skip heavy directories"
            )

    def test_bug_fix_exclude_dirs_present(self, tmp_path):
        """bug_fix file_search params must include exclude_dirs."""
        from openjarvis.workbench.coding_manager import CodingManager, _SEARCH_EXCLUDE_DIRS
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        (tmp_path / "src" / "openjarvis" / "workbench").mkdir(parents=True)
        router = ModelRouter(
            db_path=str(tmp_path / "routing.db"),
            adapter_override=MockModelAdapter(),
        )
        mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)

        plan = mgr.plan("Fix the crash in model_router tier assignment", dry_run=True)
        search_subtasks = [st for st in plan.subtasks if st.tool_id == "file_search"]
        for st in search_subtasks:
            excl = st.params.get("exclude_dirs", [])
            assert "!.venv" in excl, f"exclude_dirs must contain '!.venv', got: {excl}"
            assert "!node_modules" in excl, (
                f"exclude_dirs must contain '!node_modules', got: {excl}"
            )

    def test_search_timeout_returns_structured_metadata(self):
        """FileSearchTool timeout must return structured metadata, not a generic string."""
        import subprocess
        import unittest.mock as mock
        from openjarvis.tools.file_search import FileSearchTool

        tool = FileSearchTool()
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(["rg"], 60),
        ):
            result = tool.execute(pattern="TestPattern", directory="/tmp")

        assert not result.success
        assert "timed out" in result.content.lower(), (
            f"Timeout error must say 'timed out', got: {result.content!r}"
        )
        assert "TestPattern" in result.content, (
            "Timeout error must include the failing pattern"
        )
        assert result.metadata is not None, "Timeout error must include metadata"
        assert result.metadata.get("error") == "timeout"
        assert result.metadata.get("pattern") == "TestPattern"
        assert result.metadata.get("retryable") is True
        assert "retry_hint" in result.metadata
        assert "TypeError" not in result.content, (
            "Timeout error must not be a generic TypeError string"
        )

    def test_search_timeout_metadata_includes_directory(self):
        """FileSearchTool timeout metadata must include the failing directory."""
        import subprocess
        import unittest.mock as mock
        from openjarvis.tools.file_search import FileSearchTool

        tool = FileSearchTool()
        with mock.patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(["rg"], 60),
        ):
            result = tool.execute(pattern="Unified|Notifications", directory="/Users/user/OpenJarvis")

        assert result.metadata.get("directory") == "/Users/user/OpenJarvis"
        assert result.metadata.get("timeout_seconds") == 60

    def test_file_search_default_excludes_heavy_dirs(self):
        """FileSearchTool default exclude globs must cover all heavy/generated directories."""
        from openjarvis.tools.file_search import _DEFAULT_EXCLUDE_GLOBS

        required = [
            "!.venv", "!node_modules", "!.git",
            "!frontend/node_modules", "!frontend/src-tauri/target",
            "!target", "!__pycache__", "!.pytest_cache",
        ]
        for excl in required:
            assert excl in _DEFAULT_EXCLUDE_GLOBS, (
                f"_DEFAULT_EXCLUDE_GLOBS must contain {excl!r}"
            )

    def test_bounded_search_dir_returns_subdir_when_exists(self, tmp_path):
        """_bounded_search_dir must return a bounded subdir when it exists."""
        from openjarvis.workbench.coding_manager import _bounded_search_dir

        (tmp_path / "src" / "openjarvis" / "server").mkdir(parents=True)
        result = _bounded_search_dir(str(tmp_path))
        assert result != str(tmp_path), (
            "_bounded_search_dir must return a subdir when src/openjarvis/server exists"
        )
        assert "openjarvis" in result or "server" in result

    def test_bounded_search_dir_fallback_to_repo(self, tmp_path):
        """_bounded_search_dir must fall back to repo_path when no subdirs exist."""
        from openjarvis.workbench.coding_manager import _bounded_search_dir

        result = _bounded_search_dir(str(tmp_path))
        assert result == str(tmp_path), (
            "_bounded_search_dir must fall back to repo_path when no targeted subdirs exist"
        )


# ---------------------------------------------------------------------------
# US14A.1 Preflight: Dry-Run mode governance consistency
# ---------------------------------------------------------------------------


class TestDryRunGovernanceConsistency:
    """Prove Dry-Run mode is consistent and blocks all write/commit/push operations."""

    def test_plan_dry_run_true_matches_request(self, mgr):
        """plan.dry_run must be True when dry_run=True is passed."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        assert plan.dry_run is True, (
            f"plan.dry_run must be True when dry_run=True was requested, got {plan.dry_run}"
        )

    def test_plan_dry_run_false_matches_request(self, mgr):
        """plan.dry_run must be False when dry_run=False is passed."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=False,
        )
        assert plan.dry_run is False

    def test_dry_run_planning_only_no_write_subtasks(self, mgr):
        """planning_only + dry_run=True must produce zero file_write/commit/push subtasks."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        for st in plan.subtasks:
            assert st.tool_id not in ("file_write", "git_commit", "git_push"), (
                f"planning_only plan must not contain {st.tool_id}"
            )

    def test_dry_run_execute_skips_file_write(self, mgr):
        """dry_run=True execution must mark file_write subtasks as skipped_dry_run."""
        plan = mgr.plan("Add a test fixture file", dry_run=True)
        plan = mgr.execute(plan)
        for st in plan.subtasks:
            if st.tool_id == "file_write":
                assert st.status == "skipped_dry_run", (
                    f"dry_run must skip file_write, got status={st.status}"
                )

    def test_dry_run_execute_skips_git_commit(self, mgr):
        """dry_run=True execution must mark git_commit subtasks as skipped_dry_run."""
        plan = mgr.plan("Add a test fixture file", dry_run=True)
        plan = mgr.execute(plan)
        for st in plan.subtasks:
            if st.tool_id == "git_commit":
                assert st.status == "skipped_dry_run", (
                    f"dry_run must skip git_commit, got status={st.status}"
                )

    def test_dry_run_execute_skips_git_push(self, mgr):
        """dry_run=True execution must mark git_push subtasks as skipped_dry_run."""
        plan = mgr.plan("Add a test fixture file", dry_run=True)
        plan = mgr.execute(plan)
        for st in plan.subtasks:
            if st.tool_id == "git_push":
                assert st.status == "skipped_dry_run", (
                    f"dry_run must skip git_push, got status={st.status}"
                )

    def test_dry_run_planning_only_execute_no_writes(self, mgr):
        """Executing a planning_only dry_run must complete with zero writes."""
        plan = mgr.plan(
            "Plan US14A.1 PA Chat-to-Workbench + notifications. Do not edit files yet.",
            dry_run=True,
        )
        plan = mgr.execute(plan)
        assert plan.status in ("done_dry_run", "done", "failed", "blocked"), (
            f"Unexpected plan status: {plan.status}"
        )
        for st in plan.subtasks:
            assert st.tool_id not in ("file_write", "git_commit", "git_push") or \
                st.status == "skipped_dry_run", (
                f"Dry-run must not execute {st.tool_id}, got status={st.status}"
            )

    def test_tiny_marker_dry_run_unchanged_behavior(self, mgr):
        """Existing tiny marker dry-run behavior must remain intact."""
        plan = mgr.plan("Add a self-test fixture marker for E2E proof", dry_run=True)
        assert plan.task_type == "tiny_marker"
        plan = mgr.execute(plan)
        for st in plan.subtasks:
            if st.tool_id in ("git_commit", "git_push"):
                assert st.status == "skipped_dry_run", (
                    f"Tiny marker dry_run must skip {st.tool_id}, got {st.status}"
                )
