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

    def test_explicit_task_type_planning_only_overrides_complex_us14a1_prompt(self, mgr):
        prompt = """US14A.1 IMPLEMENTATION PLAN — PA CHAT FRONT DOOR + NOTIFICATIONS + APPROVAL/AUTOPILOT

Task Type: planning_only

Goal:
Produce a changed-file-only implementation plan for US14A.1: PA Chat Front Door + Notifications + Approval/Autopilot before original US14.

Required changed-file-only discovery:
- Do not modify files.
- Do not create files.
- Do not commit.
- Do not push.
"""
        plan = mgr.plan(prompt, dry_run=False)
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

    def test_classify_explicit_task_type_planning_only_overrides_complex_keywords(self):
        from openjarvis.workbench.coding_manager import classify_prompt

        prompt = """US14A.1 IMPLEMENTATION PLAN — PA CHAT FRONT DOOR + NOTIFICATIONS + APPROVAL/AUTOPILOT

Task Type: planning_only

Goal:
Produce a changed-file-only implementation plan for US14A.1: PA Chat Front Door + Notifications + Approval/Autopilot before original US14.
"""
        assert classify_prompt(prompt) == "planning_only"

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


# ---------------------------------------------------------------------------
# US14A.1 Plan Synthesis: planning_only Report must be a real planning artifact
# ---------------------------------------------------------------------------

_US14A1_PLAN_PROMPT = (
    "US14A.1 IMPLEMENTATION PLAN ONLY — PA Chat-to-Workbench + Unified Notifications"
    " + Guarded Autopilot\n\nTask:\nCreate a scoped implementation plan for US14A.1."
    "\n\nDo not edit files yet.\nDo not create files yet.\nDo not run write commands."
    "\nDo not commit.\nDo not push.\nDo not send Slack or Telegram messages."
    "\nDo not run production/deploy commands.\nDo not expose secrets."
    "\n\nReturn a scoped implementation plan only."
)


@pytest.fixture()
def us14a1_executed_plan(mgr):
    """Plan + execute the exact US14A.1 prompt; return the executed plan."""
    plan = mgr.plan(_US14A1_PLAN_PROMPT, dry_run=True)
    return mgr.execute(plan)


class TestPlanSynthesisReport:
    """Prove the planning_only report produces a real planning artifact."""

    def test_planning_report_has_implementation_phases(self, us14a1_executed_plan):
        """Plan Only report must contain implementation phases."""
        report = us14a1_executed_plan.final_report or ""
        assert "Implementation Phases" in report, (
            "Planning report must contain '## Implementation Phases'"
        )
        assert "Phase 1" in report, (
            "Planning report must contain at least 'Phase 1'"
        )

    def test_planning_report_has_risks(self, us14a1_executed_plan):
        """Plan Only report must contain a Risks section."""
        report = us14a1_executed_plan.final_report or ""
        assert "## Risks" in report, "Planning report must contain '## Risks'"
        assert "Insufficient data to verify" in report or "Risk:" in report, (
            "Risks section must contain at least one risk entry"
        )

    def test_planning_report_has_validation_commands(self, us14a1_executed_plan):
        """Plan Only report must contain validation commands."""
        report = us14a1_executed_plan.final_report or ""
        assert "Validation Commands" in report, (
            "Planning report must contain '## Validation Commands'"
        )
        assert "pytest" in report, (
            "Validation commands must reference pytest"
        )

    def test_planning_report_has_approval_gates(self, us14a1_executed_plan):
        """Plan Only report must contain approval gates."""
        report = us14a1_executed_plan.final_report or ""
        assert "Approval Gates" in report, (
            "Planning report must contain '## Approval Gates'"
        )
        assert "Gate" in report, (
            "Approval gates section must list at least one gate"
        )

    def test_planning_report_has_acceptance_tests(self, us14a1_executed_plan):
        """Plan Only report must contain acceptance tests."""
        report = us14a1_executed_plan.final_report or ""
        assert "Acceptance Tests" in report, (
            "Planning report must contain '## Acceptance Tests'"
        )

    def test_planning_report_has_recommended_next_files(self, us14a1_executed_plan):
        """Plan Only report must contain recommended next files to inspect."""
        report = us14a1_executed_plan.final_report or ""
        assert "Recommended Next Files" in report, (
            "Planning report must contain '## Recommended Next Files to Inspect'"
        )
        assert "src/openjarvis" in report or "frontend/src" in report, (
            "Recommended next files must include OpenJarvis source paths"
        )

    def test_planning_report_has_model_routing_plan(self, us14a1_executed_plan):
        """Plan Only report must contain a model routing / provider verification plan."""
        report = us14a1_executed_plan.final_report or ""
        assert "Model Routing" in report, (
            "Planning report must contain '## Model Routing / Provider Verification Plan'"
        )
        assert "MockModelAdapter" in report or "paid calls" in report, (
            "Model routing plan must reference MockModelAdapter or paid call safety"
        )

    def test_planning_report_has_slack_telegram_gating(self, us14a1_executed_plan):
        """Plan Only report must contain a Slack/Telegram notification gating plan."""
        report = us14a1_executed_plan.final_report or ""
        assert "Slack" in report and "Telegram" in report, (
            "Planning report must reference both Slack and Telegram"
        )
        assert "Gating Plan" in report or "gating" in report.lower(), (
            "Planning report must contain the notification gating section"
        )

    def test_planning_report_no_accept_verdict(self, us14a1_executed_plan):
        """Plan Only report must NOT say bare ACCEPT; must use PLAN_READY_FOR_REVIEW or HOLD_FOR_MORE_DISCOVERY."""
        report = us14a1_executed_plan.final_report or ""
        valid_verdicts = ("PLAN_READY_FOR_REVIEW", "HOLD_FOR_MORE_DISCOVERY")
        assert any(v in report for v in valid_verdicts), (
            f"Planning report must contain one of {valid_verdicts}, got report starting with: "
            f"{report[:200]!r}"
        )
        assert "Final Verdict" not in report, (
            "Planning report must not contain generic 'Final Verdict' from the execution summary"
        )

    def test_planning_report_not_generic_execution_summary(self, mgr):
        """Tiny marker task must still produce the generic execution report, not a planning artifact."""
        plan = mgr.plan("Add a self-test fixture marker for E2E proof", dry_run=True)
        assert plan.task_type == "tiny_marker", (
            f"Expected tiny_marker, got {plan.task_type}"
        )
        plan = mgr.execute(plan)
        report = plan.final_report or ""
        assert "Implementation Phases" not in report, (
            "Tiny marker execution report must NOT contain planning artifact sections"
        )

    def test_planning_report_has_known_unknowns(self, us14a1_executed_plan):
        """Plan Only report must contain Known Unknowns section with Insufficient data entries."""
        report = us14a1_executed_plan.final_report or ""
        assert "Known Unknowns" in report, (
            "Planning report must contain '## Known Unknowns'"
        )
        assert "Insufficient data to verify" in report, (
            "Known unknowns must use the standard 'Insufficient data to verify' prefix"
        )

    def test_planning_report_has_likely_files_by_subsystem(self, us14a1_executed_plan):
        """Plan Only report must group likely files by subsystem."""
        report = us14a1_executed_plan.final_report or ""
        assert "Likely Files by Subsystem" in report, (
            "Planning report must contain '## Likely Files by Subsystem'"
        )
        subsystems_expected = [
            "Workbench", "Notification", "Slack", "Telegram",
        ]
        found = [s for s in subsystems_expected if s in report]
        assert len(found) >= 2, (
            f"Planning report must group files into at least 2 subsystems from "
            f"{subsystems_expected}, found: {found}"
        )


# ---------------------------------------------------------------------------
# US14A.1 Discovery Planner: explicit file lists must be extracted and read
# ---------------------------------------------------------------------------

_US14A1_PHASE1_PROMPT = (
    "US14A.1 PHASE 1 DISCOVERY \u2014 READ-ONLY ARCHITECTURE REVIEW\n\n"
    "Read these files only if they exist:\n\n"
    "- `src/openjarvis/tools/approval_store.py`\n"
    "- `src/openjarvis/channels/slack.py`\n"
    "- `src/openjarvis/channels/telegram.py`\n"
    "- `frontend/src/components/ApprovalBell.tsx`\n"
    "- `src/openjarvis/autonomy/automation_policy.py`\n"
    "- `src/openjarvis/governance/constitution.py`\n"
    "- `src/openjarvis/workbench/model_router.py`\n"
    "- `src/openjarvis/workbench/cost_ledger.py`\n"
    "- `src/openjarvis/intelligence/model_catalog.py`\n"
    "- `src/openjarvis/server/routes.py`\n"
    "- `src/openjarvis/workbench/coding_manager.py`\n"
    "- `src/openjarvis/mission/notifier.py`\n"
    "- `src/openjarvis/server/approval_routes.py`\n"
    "- `frontend/src/pages/WorkbenchPage.tsx`\n"
    "- `tests/workbench/test_us14a.py`\n"
    "- `tests/workbench/test_us14a_planner.py`\n\n"
    "Do not edit files.\n"
    "Do not create files.\n"
    "Do not delete files.\n"
    "Do not commit.\n"
    "Do not push.\n"
    "Do not send Slack or Telegram messages.\n"
    "Return a read-only architecture discovery report."
)

_PHASE1_LISTED_FILES = [
    "src/openjarvis/tools/approval_store.py",
    "src/openjarvis/channels/slack.py",
    "src/openjarvis/channels/telegram.py",
    "frontend/src/components/ApprovalBell.tsx",
    "src/openjarvis/autonomy/automation_policy.py",
    "src/openjarvis/governance/constitution.py",
    "src/openjarvis/workbench/model_router.py",
    "src/openjarvis/workbench/cost_ledger.py",
    "src/openjarvis/intelligence/model_catalog.py",
    "src/openjarvis/server/routes.py",
    "src/openjarvis/workbench/coding_manager.py",
    "src/openjarvis/mission/notifier.py",
    "src/openjarvis/server/approval_routes.py",
    "frontend/src/pages/WorkbenchPage.tsx",
    "tests/workbench/test_us14a.py",
    "tests/workbench/test_us14a_planner.py",
]


class TestExplicitFileDiscovery:
    """Prove that explicit file paths in prompts are extracted, read, and reported."""

    def test_extract_explicit_files_backtick(self):
        """Backtick-quoted paths must be extracted from a prompt."""
        from openjarvis.workbench.coding_manager import _extract_explicit_files

        prompt = (
            "Read these files:\n"
            "- `src/openjarvis/channels/slack.py`\n"
            "- `frontend/src/pages/WorkbenchPage.tsx`\n"
            "Do not edit."
        )
        result = _extract_explicit_files(prompt)
        assert "src/openjarvis/channels/slack.py" in result, (
            f"Must extract backtick path 'src/openjarvis/channels/slack.py', got: {result}"
        )
        assert "frontend/src/pages/WorkbenchPage.tsx" in result, (
            f"Must extract backtick path 'frontend/src/pages/WorkbenchPage.tsx', got: {result}"
        )

    def test_extract_explicit_files_bullet(self):
        """Plain bullet-listed repo-relative paths must be extracted."""
        from openjarvis.workbench.coding_manager import _extract_explicit_files

        prompt = (
            "Read these files:\n"
            "- src/openjarvis/workbench/coding_manager.py\n"
            "- src/openjarvis/workbench/model_router.py\n"
            "Return only a report."
        )
        result = _extract_explicit_files(prompt)
        assert "src/openjarvis/workbench/coding_manager.py" in result, (
            f"Must extract plain bullet path 'coding_manager.py', got: {result}"
        )
        assert "src/openjarvis/workbench/model_router.py" in result, (
            f"Must extract plain bullet path 'model_router.py', got: {result}"
        )

    def test_explicit_files_become_file_read_subtasks(self, tmp_path):
        """Existing explicit files must become file_read subtasks in the plan."""
        from openjarvis.workbench.coding_manager import CodingManager
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        existing = [
            "src/openjarvis/channels/slack.py",
            "src/openjarvis/workbench/model_router.py",
        ]
        for fpath in existing:
            full = tmp_path / fpath
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("# stub")

        router = ModelRouter(db_path=str(tmp_path / "r.db"), adapter_override=MockModelAdapter())
        mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)

        plan = mgr.plan(
            "Read these files:\n"
            "- `src/openjarvis/channels/slack.py`\n"
            "- `src/openjarvis/workbench/model_router.py`\n"
            "Do not edit files.",
            dry_run=True,
        )
        file_read_paths = {
            st.params.get("path", "").replace(str(tmp_path) + "/", "")
            for st in plan.subtasks if st.tool_id == "file_read"
        }
        for fpath in existing:
            assert fpath in file_read_paths, (
                f"Explicit file {fpath!r} must become a file_read subtask, "
                f"got file_read paths: {sorted(file_read_paths)}"
            )

    def test_missing_explicit_files_in_report(self, mgr):
        """Files requested but not on disk must appear in the report as 'file not found'."""
        plan = mgr.plan(_US14A1_PHASE1_PROMPT, dry_run=True)
        plan = mgr.execute(plan)
        report = plan.final_report or ""
        assert "Missing Files" in report, (
            "Report must contain '## Missing Files (Requested But Not Found on Disk)'"
        )
        assert "file not found" in report, (
            "Missing files must be labelled 'file not found' in the report"
        )
        assert any(f in report for f in _PHASE1_LISTED_FILES), (
            "Report must mention at least one of the explicitly listed files"
        )

    def test_paths_outside_repo_are_rejected(self):
        """Absolute paths, tilde paths, and traversal paths must be rejected."""
        from openjarvis.workbench.coding_manager import _is_safe_repo_relative

        assert not _is_safe_repo_relative("/etc/passwd"), "absolute path must be rejected"
        assert not _is_safe_repo_relative("~/config.py"), "tilde path must be rejected"
        assert not _is_safe_repo_relative("../secrets.env"), "traversal must be rejected"
        assert not _is_safe_repo_relative("../../etc/hosts"), "double traversal must be rejected"
        assert not _is_safe_repo_relative(""), "empty string must be rejected"
        assert not _is_safe_repo_relative("HOLD_FOR_MORE_DISCOVERY"), (
            "identifier without extension+slash must be rejected"
        )
        # These must pass
        assert _is_safe_repo_relative("src/openjarvis/channels/slack.py")
        assert _is_safe_repo_relative("frontend/src/pages/WorkbenchPage.tsx")
        assert _is_safe_repo_relative("tests/workbench/test_us14a.py")

    def test_us14a1_phase1_reads_all_existing_files(self, tmp_path):
        """US14A.1 Phase 1 prompt must create file_read subtasks for all existing listed files."""
        from openjarvis.workbench.coding_manager import CodingManager
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        existing = [
            "src/openjarvis/channels/slack.py",
            "src/openjarvis/channels/telegram.py",
            "src/openjarvis/workbench/model_router.py",
            "src/openjarvis/workbench/cost_ledger.py",
            "src/openjarvis/server/routes.py",
        ]
        for fpath in existing:
            full = tmp_path / fpath
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("# stub")

        router = ModelRouter(db_path=str(tmp_path / "r.db"), adapter_override=MockModelAdapter())
        mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)

        plan = mgr.plan(_US14A1_PHASE1_PROMPT, dry_run=True)
        file_read_paths = {
            st.params.get("path", "").replace(str(tmp_path) + "/", "")
            for st in plan.subtasks if st.tool_id == "file_read"
        }
        for fpath in existing:
            assert fpath in file_read_paths, (
                f"Phase 1 prompt must read existing file {fpath!r}, "
                f"got file_read paths: {sorted(file_read_paths)}"
            )

    def test_explicit_file_prompt_no_file_search(self, mgr):
        """Phase 1 explicit-file-list prompt must not add a file_search subtask."""
        plan = mgr.plan(_US14A1_PHASE1_PROMPT, dry_run=True)
        tool_ids = [st.tool_id for st in plan.subtasks]
        assert "file_search" not in tool_ids, (
            f"Phase 1 discovery prompt must not add file_search, got subtasks: {tool_ids}"
        )

    def test_explicit_file_prompt_no_writes(self, mgr):
        """Phase 1 explicit-file-list prompt must not add write/commit/push subtasks."""
        plan = mgr.plan(_US14A1_PHASE1_PROMPT, dry_run=True)
        forbidden = {"file_write", "file_delete", "git_commit", "git_push"}
        present = {st.tool_id for st in plan.subtasks} & forbidden
        assert not present, (
            f"Phase 1 prompt must not add write/commit/push subtasks, found: {present}"
        )

    def test_report_lists_files_inspected(self, tmp_path):
        """Report must list files actually read under 'Files Read in This Session'."""
        from openjarvis.workbench.coding_manager import CodingManager
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        fpath = "src/openjarvis/workbench/coding_manager.py"
        full = tmp_path / fpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text("# stub")

        router = ModelRouter(db_path=str(tmp_path / "r.db"), adapter_override=MockModelAdapter())
        mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)

        plan = mgr.plan(
            f"Read these files:\n- `{fpath}`\nDo not edit files.", dry_run=True
        )
        plan = mgr.execute(plan)
        report = plan.final_report or ""
        assert "Files Read in This Session" in report, (
            "Report must contain '## Files Read in This Session'"
        )
        assert fpath in report, (
            f"Report must list the file that was read: {fpath!r}"
        )

    def test_report_lists_missing_files(self, mgr):
        """Report must list files requested but not found under 'Missing Files'."""
        plan = mgr.plan(_US14A1_PHASE1_PROMPT, dry_run=True)
        plan = mgr.execute(plan)
        report = plan.final_report or ""
        assert "Missing Files" in report, (
            "Report must contain '## Missing Files (Requested But Not Found on Disk)'"
        )
        assert "Insufficient data to verify" in report, (
            "Missing files must use the 'Insufficient data to verify' prefix"
        )

    def test_report_hold_when_not_all_read(self, mgr):
        """Report must return HOLD_FOR_MORE_DISCOVERY when requested files are missing."""
        plan = mgr.plan(_US14A1_PHASE1_PROMPT, dry_run=True)
        plan = mgr.execute(plan)
        report = plan.final_report or ""
        assert "HOLD_FOR_MORE_DISCOVERY" in report, (
            f"Report must return HOLD_FOR_MORE_DISCOVERY when listed files are missing; "
            f"got report start: {report[:300]!r}"
        )
        # The **Status** banner must say HOLD, not PLAN_READY (gates may reference it as a noun)
        assert "**Status**: `PLAN_READY_FOR_REVIEW`" not in report, (
            "Report Status banner must not say PLAN_READY_FOR_REVIEW when discovery is incomplete"
        )

    def test_report_plan_ready_when_all_read(self, tmp_path):
        """Report must return PLAN_READY_FOR_REVIEW when all requested existing files are read."""
        from openjarvis.workbench.coding_manager import CodingManager
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        listed = [
            "src/openjarvis/channels/slack.py",
            "src/openjarvis/workbench/model_router.py",
        ]
        for fpath in listed:
            full = tmp_path / fpath
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("# stub")

        router = ModelRouter(db_path=str(tmp_path / "r.db"), adapter_override=MockModelAdapter())
        mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)

        prompt = (
            "Read these files:\n"
            "- `src/openjarvis/channels/slack.py`\n"
            "- `src/openjarvis/workbench/model_router.py`\n"
            "Do not edit files."
        )
        plan = mgr.plan(prompt, dry_run=True, stop_on_blocker=False)
        plan = mgr.execute(plan)
        report = plan.final_report or ""
        assert "READY_FOR_IMPLEMENTATION_APPROVAL" in report, (
            f"Report must return READY_FOR_IMPLEMENTATION_APPROVAL when all requested "
            f"existing files were read; got: {report[:300]!r}"
        )


# ---------------------------------------------------------------------------
# US14A.1 Architecture Synthesis Remediation tests
# ---------------------------------------------------------------------------

_ADDENDUM_PROMPT = (
    "US14A.1 IMPLEMENTATION READINESS ADDENDUM \u2014 SOURCE-DERIVED ARCHITECTURE PLAN\n\n"
    "Read these files only if they exist:\n\n"
    "- `src/openjarvis/tools/approval_store.py`\n"
    "- `src/openjarvis/channels/slack.py`\n"
    "- `src/openjarvis/channels/telegram.py`\n"
    "- `frontend/src/components/ApprovalBell.tsx`\n"
    "- `src/openjarvis/autonomy/automation_policy.py`\n"
    "- `src/openjarvis/governance/constitution.py`\n"
    "- `src/openjarvis/workbench/model_router.py`\n"
    "- `src/openjarvis/workbench/cost_ledger.py`\n"
    "- `src/openjarvis/intelligence/model_catalog.py`\n"
    "- `src/openjarvis/server/routes.py`\n"
    "- `src/openjarvis/server/workbench_routes.py`\n"
    "- `src/openjarvis/server/channel_bridge.py`\n"
    "- `src/openjarvis/server/notify_routes.py`\n"
    "- `src/openjarvis/workbench/coding_manager.py`\n"
    "- `src/openjarvis/mission/notifier.py`\n"
    "- `src/openjarvis/server/approval_routes.py`\n"
    "- `frontend/src/pages/WorkbenchPage.tsx`\n"
    "- `tests/workbench/test_us14a.py`\n"
    "- `tests/workbench/test_us14a_planner.py`\n\n"
    "Do not edit files.\n"
    "Do not create files.\n"
    "Do not delete files.\n"
    "Do not commit.\n"
    "Do not push.\n"
    "Do not send Slack or Telegram messages.\n"
    "Return an implementation-readiness architecture plan with final recommendation "
    "exactly one of: READY_FOR_IMPLEMENTATION_APPROVAL, HOLD_FOR_MORE_DISCOVERY, or UNSAFE."
)

_VALID_VERDICTS = {
    "READY_FOR_IMPLEMENTATION_APPROVAL",
    "HOLD_FOR_MORE_DISCOVERY",
    "UNSAFE",
}


def _make_mgr_with_files(tmp_path, file_paths, content="# stub"):
    """Create a CodingManager whose repo_path is tmp_path with specified files pre-created."""
    from openjarvis.workbench.coding_manager import CodingManager
    from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

    for fpath in file_paths:
        full = tmp_path / fpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    router = ModelRouter(db_path=str(tmp_path / "r.db"), adapter_override=MockModelAdapter())
    return CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path), model_router=router)


def _execute_addendum(mgr, prompt=None):
    """Plan + execute the addendum prompt and return the final report.

    Uses stop_on_blocker=False so that git_status/git_diff failures in
    non-git tmp_path repos don't halt execution before file_read subtasks run.
    """
    p = prompt or _ADDENDUM_PROMPT
    plan = mgr.plan(p, dry_run=True, stop_on_blocker=False)
    plan = mgr.execute(plan)
    return plan, plan.final_report or ""


class TestArchitectureSynthesis:
    """Prove source-derived report sections and correct verdict terminology."""

    def test_verdict_not_plan_ready_for_review(self, mgr):
        """PLAN_READY_FOR_REVIEW must not appear in implementation-readiness reports."""
        _, report = _execute_addendum(mgr)
        assert "PLAN_READY_FOR_REVIEW" not in report, (
            "Report must NOT use PLAN_READY_FOR_REVIEW for implementation-readiness prompts"
        )

    def test_verdict_is_valid_three_option(self, mgr):
        """Final recommendation must be exactly one of the three valid verdicts."""
        _, report = _execute_addendum(mgr)
        assert any(v in report for v in _VALID_VERDICTS), (
            f"Report must use one of {_VALID_VERDICTS}, got report start: {report[:300]!r}"
        )

    def test_verdict_in_status_banner(self, mgr):
        """**Status** line must use one of the three valid verdicts."""
        _, report = _execute_addendum(mgr)
        status_line = next(
            (l for l in report.splitlines() if l.startswith("**Status**")), ""
        )
        assert any(v in status_line for v in _VALID_VERDICTS), (
            f"Status banner must contain a valid verdict, got: {status_line!r}"
        )

    def test_no_contradiction_for_inspected_files(self, tmp_path):
        """Report must not say a file was not inspected when it was actually read."""
        files = [
            "src/openjarvis/workbench/model_router.py",
            "src/openjarvis/channels/slack.py",
            "src/openjarvis/channels/telegram.py",
            "src/openjarvis/mission/notifier.py",
        ]
        mgr = _make_mgr_with_files(tmp_path, files)
        prompt = (
            "Read these files:\n"
            + "".join(f"- `{f}`\n" for f in files)
            + "Do not edit files."
        )
        plan, report = _execute_addendum(mgr, prompt)
        reads_done = {
            st.params.get("path", "").replace(str(tmp_path) + "/", "")
            for st in plan.subtasks if st.tool_id == "file_read" and st.status == "done"
        }
        for fpath in reads_done:
            fname = fpath.split("/")[-1]
            assert f"{fname} not inspected" not in report, (
                f"Report must NOT say '{fname} not inspected' after reading it; "
                f"reads_done={reads_done}"
            )

    def test_report_has_architecture_map_section(self, tmp_path):
        """Report must include a 'Current Architecture Map' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/workbench/coding_manager.py"])
        prompt = (
            "Read these files:\n"
            "- `src/openjarvis/workbench/coding_manager.py`\n"
            "Do not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Current Architecture Map" in report, (
            "Report must contain '## Current Architecture Map' section"
        )

    def test_report_has_files_likely_to_change(self, tmp_path):
        """Report must include 'Files Likely to Change' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/server/routes.py"])
        prompt = (
            "Read these files:\n"
            "- `src/openjarvis/server/routes.py`\n"
            "Do not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Files Likely to Change" in report, (
            "Report must contain '## Files Likely to Change' section"
        )

    def test_report_has_new_files_likely_needed(self, mgr):
        """Report must include 'New Files Likely Needed' section."""
        _, report = _execute_addendum(mgr)
        assert "New Files Likely Needed" in report, (
            "Report must contain '## New Files Likely Needed' section"
        )

    def test_report_has_backend_api_plan(self, tmp_path):
        """Report must include 'Backend / API Implementation Plan' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/server/routes.py"])
        prompt = (
            "Read these files:\n- `src/openjarvis/server/routes.py`\nDo not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Backend" in report and "Implementation Plan" in report, (
            "Report must contain a backend/API implementation plan section"
        )

    def test_report_has_frontend_plan(self, tmp_path):
        """Report must include 'Frontend Implementation Plan' section."""
        mgr = _make_mgr_with_files(tmp_path, ["frontend/src/pages/WorkbenchPage.tsx"])
        prompt = (
            "Read these files:\n"
            "- `frontend/src/pages/WorkbenchPage.tsx`\n"
            "Do not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Frontend" in report and "Implementation Plan" in report, (
            "Report must contain a frontend implementation plan section"
        )

    def test_report_has_notification_event_plan(self, tmp_path):
        """Report must include 'Notification / Event Implementation Plan' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/mission/notifier.py"])
        prompt = (
            "Read these files:\n- `src/openjarvis/mission/notifier.py`\nDo not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Notification" in report and "Event" in report, (
            "Report must contain a Notification/Event Implementation Plan section"
        )

    def test_report_has_slack_telegram_gating_plan(self, tmp_path):
        """Report must include 'Slack / Telegram Notification Gating Plan' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/channels/slack.py"])
        prompt = (
            "Read these files:\n- `src/openjarvis/channels/slack.py`\nDo not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Slack" in report and "Telegram" in report and "Gating" in report, (
            "Report must contain a Slack/Telegram Gating Plan section"
        )

    def test_report_has_model_routing_plan(self, tmp_path):
        """Report must include 'Model Routing / Provider Verification Plan' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/workbench/model_router.py"])
        prompt = (
            "Read these files:\n"
            "- `src/openjarvis/workbench/model_router.py`\n"
            "Do not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Model Routing" in report, (
            "Report must contain '## Model Routing / Provider Verification Plan'"
        )

    def test_report_has_approval_autopilot_plan(self, tmp_path):
        """Report must include 'Approval / Autopilot Policy Plan' section."""
        mgr = _make_mgr_with_files(tmp_path, ["src/openjarvis/tools/approval_store.py"])
        prompt = (
            "Read these files:\n"
            "- `src/openjarvis/tools/approval_store.py`\n"
            "Do not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Approval" in report and "Autopilot" in report and "Policy" in report, (
            "Report must contain '## Approval / Autopilot Policy Plan'"
        )

    def test_report_has_tests_section(self, tmp_path):
        """Report must include a 'Tests to Add / Update' section."""
        mgr = _make_mgr_with_files(tmp_path, ["tests/workbench/test_us14a.py"])
        prompt = (
            "Read these files:\n- `tests/workbench/test_us14a.py`\nDo not edit files."
        )
        _, report = _execute_addendum(mgr, prompt)
        assert "Tests to Add" in report or "Tests to add" in report, (
            "Report must contain '## Tests to Add / Update'"
        )

    def test_report_has_validation_commands(self, mgr):
        """Report must include 'Validation Commands' section."""
        _, report = _execute_addendum(mgr)
        assert "Validation Commands" in report, (
            "Report must contain '## Validation Commands'"
        )

    def test_hold_when_no_files_read(self, mgr):
        """Report must return HOLD_FOR_MORE_DISCOVERY when no explicit files could be read."""
        _, report = _execute_addendum(mgr)
        assert "**Status**: `HOLD_FOR_MORE_DISCOVERY`" in report, (
            "When no files exist in tmp_path, all are missing → HOLD_FOR_MORE_DISCOVERY"
        )

    def test_ready_for_approval_when_all_read(self, tmp_path):
        """Report must return READY_FOR_IMPLEMENTATION_APPROVAL when all requested files are read."""
        listed = [
            "src/openjarvis/channels/slack.py",
            "src/openjarvis/server/routes.py",
            "src/openjarvis/workbench/model_router.py",
            "tests/workbench/test_us14a.py",
        ]
        mgr = _make_mgr_with_files(tmp_path, listed)
        prompt = (
            "Read these files:\n"
            + "".join(f"- `{f}`\n" for f in listed)
            + "Do not edit files."
        )
        plan, report = _execute_addendum(mgr, prompt)
        assert "**Status**: `READY_FOR_IMPLEMENTATION_APPROVAL`" in report, (
            f"Must return READY_FOR_IMPLEMENTATION_APPROVAL when all files read; "
            f"got: {report[:400]!r}"
        )

    def test_no_plan_ready_for_review_anywhere_in_addendum(self, mgr):
        """PLAN_READY_FOR_REVIEW must not appear anywhere in an addendum-style prompt report."""
        _, report = _execute_addendum(mgr)
        assert "PLAN_READY_FOR_REVIEW" not in report, (
            "PLAN_READY_FOR_REVIEW is a retired verdict; must not appear in any report"
        )


# ---------------------------------------------------------------------------
# US14A.1 execution safety: no false ACCEPT when implementation did not occur
# ---------------------------------------------------------------------------

def _make_execution_safety_plan(tmp_path, *, task_type="bug_fix", validation_output="1 passed"):
    from openjarvis.workbench.coding_manager import CodingManager, Subtask, TaskPlan

    mgr = CodingManager(repo_path=str(tmp_path), db_dir=str(tmp_path / ".openjarvis-test"))
    plan = TaskPlan(
        session_id="safety001",
        task_id="task001",
        prompt="Fix Workbench execution safety by editing files",
        repo_path=str(tmp_path),
        subtasks=[
            Subtask(
                id="s1",
                index=0,
                description="Run validation / tests",
                tool_id="shell_exec",
                params={},
                worker_tier="cloud-cheap",
                requires_approval=False,
                status="done",
                output=validation_output,
            )
        ],
        dry_run=False,
        stop_on_blocker=True,
        status="done",
        task_type=task_type,
        validation_output=validation_output,
    )
    return mgr, plan


def test_us14a1_bug_fix_no_write_no_diff_returns_hold(tmp_path):
    mgr, plan = _make_execution_safety_plan(tmp_path, task_type="bug_fix")
    report = mgr._generate_report(plan)
    assert "## Implementation Evidence" in report
    assert "implementation did not run; no files were edited" in report
    assert "## Final Verdict\n\nHOLD" in report


def test_us14a1_complex_implementation_no_write_no_diff_returns_hold(tmp_path):
    mgr, plan = _make_execution_safety_plan(tmp_path, task_type="complex_implementation")
    report = mgr._generate_report(plan)
    assert "implementation did not run; no files were edited" in report
    assert "## Final Verdict\n\nHOLD" in report


def test_us14a1_validation_no_pytest_found_returns_hold(tmp_path):
    mgr, plan = _make_execution_safety_plan(
        tmp_path,
        task_type="bug_fix",
        validation_output="No pytest found",
    )
    report = mgr._generate_report(plan)
    assert "validation unavailable: no pytest found" in report
    assert "validation status: **blocked: no pytest found**" in report
    assert "## Final Verdict\n\nHOLD" in report


def test_us14a1_validation_no_module_named_pytest_returns_hold(tmp_path):
    mgr, plan = _make_execution_safety_plan(
        tmp_path,
        task_type="bug_fix",
        validation_output="/usr/bin/python3: No module named pytest",
    )
    report = mgr._generate_report(plan)
    assert "validation unavailable: no module named pytest" in report
    assert "## Final Verdict\n\nHOLD" in report


def test_us14a1_validation_bad_file_descriptor_returns_hold(tmp_path):
    mgr, plan = _make_execution_safety_plan(
        tmp_path,
        task_type="bug_fix",
        validation_output="Fatal Python error: init_sys_streams\nOSError: [Errno 9] Bad file descriptor",
    )
    report = mgr._generate_report(plan)
    assert "validation unavailable: fatal python error" in report
    assert "## Final Verdict\n\nHOLD" in report


def test_us14a1_report_includes_implementation_evidence_section(tmp_path):
    mgr, plan = _make_execution_safety_plan(tmp_path, task_type="bug_fix")
    report = mgr._generate_report(plan)
    assert "## Implementation Evidence" in report
    assert "file_write subtasks:" in report
    assert "git diff has changes:" in report
    assert "validation status:" in report

# ---------------------------------------------------------------------------
# US14A.1 explicit file-block implementation capability
# ---------------------------------------------------------------------------

def test_us14a1_extract_explicit_file_blocks():
    from openjarvis.workbench.coding_manager import _extract_explicit_file_blocks

    prompt = """Fix this file.

<<<OPENJARVIS_FILE:tests/workbench/generated_example.py
VALUE = 42

def test_value():
    assert VALUE == 42
OPENJARVIS_FILE
"""
    blocks = _extract_explicit_file_blocks(prompt)

    assert blocks == [
        {
            "path": "tests/workbench/generated_example.py",
            "content": "VALUE = 42\n\ndef test_value():\n    assert VALUE == 42",
        }
    ]


def test_us14a1_explicit_file_block_adds_file_write_for_bug_fix(mgr):
    prompt = """Fix generated module by applying the explicit file block.

<<<OPENJARVIS_FILE:tests/workbench/generated_bug_fix.py
VALUE = "bug-fix"

def test_value():
    assert VALUE == "bug-fix"
OPENJARVIS_FILE
"""
    plan = mgr.plan(prompt, dry_run=False)

    assert plan.task_type == "bug_fix"
    writes = [s for s in plan.subtasks if s.tool_id == "file_write"]
    assert len(writes) == 1
    assert writes[0].params["path"].endswith("tests/workbench/generated_bug_fix.py")
    assert 'VALUE = "bug-fix"' in writes[0].params["content"]


def test_us14a1_explicit_file_block_adds_file_write_for_complex_implementation(mgr):
    prompt = """Implement generated module by applying the explicit file block.

<<<OPENJARVIS_FILE:tests/workbench/generated_complex_impl.py
VALUE = "complex"

def test_value():
    assert VALUE == "complex"
OPENJARVIS_FILE
"""
    plan = mgr.plan(prompt, dry_run=False)

    assert plan.task_type == "complex_implementation"
    writes = [s for s in plan.subtasks if s.tool_id == "file_write"]
    assert len(writes) == 1
    assert writes[0].params["path"].endswith("tests/workbench/generated_complex_impl.py")
    assert 'VALUE = "complex"' in writes[0].params["content"]


def test_us14a1_plan_only_ignores_explicit_file_blocks(mgr):
    prompt = """Plan only. Do not edit files.

<<<OPENJARVIS_FILE:tests/workbench/should_not_write.py
VALUE = "nope"
OPENJARVIS_FILE
"""
    plan = mgr.plan(prompt, dry_run=False)

    assert plan.task_type == "planning_only"
    assert "file_write" not in [s.tool_id for s in plan.subtasks]


def test_us14a1_rejects_unsafe_explicit_file_block_path(mgr):
    prompt = """Fix generated module.

<<<OPENJARVIS_FILE:../outside.py
VALUE = "unsafe"
OPENJARVIS_FILE
"""
    plan = mgr.plan(prompt, dry_run=False)

    assert "file_write" not in [s.tool_id for s in plan.subtasks]


def test_us14a1_git_changed_files_includes_untracked_files(tmp_path):
    import subprocess

    from openjarvis.workbench.coding_manager import CodingManager

    subprocess.run(
        ["git", "init"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    probe = tmp_path / "probe.txt"
    probe.write_text("untracked probe\n")

    changed = CodingManager._git_changed_files(str(tmp_path))

    assert "probe.txt" in changed
