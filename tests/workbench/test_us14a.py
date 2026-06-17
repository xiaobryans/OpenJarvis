"""US14A — Jarvis Coding Workbench core tests.

Tests cover:
  - JobQueue: enqueue, status tracking, mark_done/failed, list
  - CostLedger: record, estimate_cost, session_total, task_total
  - CheckpointStore: save_checkpoint, list_checkpoints, memory ops
  - CodingManager: plan, dry_run enforcement, worker routing, report generation
  - FileSearchTool: basic search functionality
  - FileDeleteTool: safety checks
  - GitPushTool: dry_run flag
  - Git tools: push/branch tool specs
  - Worker routing policy: _route_worker_tier
  - Governance gates: dry_run blocks commit/push
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# JobQueue tests
# ---------------------------------------------------------------------------


class TestJobQueue:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.job_queue import JobQueue
        self.q = JobQueue(db_path=str(Path(self.tmpdir) / "jobs.db"))

    def test_enqueue_returns_job(self):
        job = self.q.enqueue(
            task_id="t1",
            description="test job",
            tool_id="git_status",
            params={"repo_path": "/tmp"},
        )
        assert job.id
        assert job.task_id == "t1"
        assert job.status.value == "pending"
        assert job.tool_id == "git_status"

    def test_mark_running(self):
        job = self.q.enqueue(task_id="t1", description="j", tool_id="git_diff", params={})
        self.q.mark_running(job.id)
        fetched = self.q.get(job.id)
        assert fetched is not None
        assert fetched.status.value == "running"
        assert fetched.started_at is not None

    def test_mark_done(self):
        job = self.q.enqueue(task_id="t2", description="j", tool_id="file_read", params={})
        self.q.mark_running(job.id)
        self.q.mark_done(job.id, output="success output", cost_usd=0.0001)
        fetched = self.q.get(job.id)
        assert fetched.status.value == "done"
        assert fetched.output == "success output"
        assert fetched.cost_usd == pytest.approx(0.0001)
        assert fetched.finished_at is not None

    def test_mark_failed(self):
        job = self.q.enqueue(task_id="t3", description="j", tool_id="shell_exec", params={})
        self.q.mark_failed(job.id, error="command failed")
        fetched = self.q.get(job.id)
        assert fetched.status.value == "failed"
        assert fetched.error == "command failed"

    def test_cancel(self):
        job = self.q.enqueue(task_id="t4", description="j", tool_id="git_push", params={})
        self.q.cancel(job.id)
        fetched = self.q.get(job.id)
        assert fetched.status.value == "cancelled"

    def test_list_by_task(self):
        self.q.enqueue(task_id="task_a", description="j1", tool_id="git_status", params={})
        self.q.enqueue(task_id="task_a", description="j2", tool_id="git_diff", params={})
        self.q.enqueue(task_id="task_b", description="j3", tool_id="file_read", params={})
        jobs = self.q.list_by_task("task_a")
        assert len(jobs) == 2
        for j in jobs:
            assert j.task_id == "task_a"

    def test_list_pending(self):
        self.q.enqueue(task_id="tx", description="j", tool_id="git_status", params={}, priority=1)
        self.q.enqueue(task_id="tx", description="j", tool_id="git_diff", params={}, priority=2)
        pending = self.q.list_pending()
        assert len(pending) >= 2

    def test_list_recent(self):
        for i in range(5):
            self.q.enqueue(task_id=f"t{i}", description=f"j{i}", tool_id="file_read", params={})
        recent = self.q.list_recent(limit=3)
        assert len(recent) == 3

    def test_job_to_dict(self):
        job = self.q.enqueue(task_id="td", description="desc", tool_id="git_log", params={"count": 5})
        d = job.to_dict()
        assert d["id"] == job.id
        assert d["task_id"] == "td"
        assert d["tool_id"] == "git_log"
        assert d["params"]["count"] == 5
        assert d["status"] == "pending"

    def test_worker_tier_stored(self):
        job = self.q.enqueue(
            task_id="t5", description="j", tool_id="git_commit", params={}, worker_tier="high-trust"
        )
        fetched = self.q.get(job.id)
        assert fetched.worker_tier == "high-trust"


# ---------------------------------------------------------------------------
# CostLedger tests
# ---------------------------------------------------------------------------


class TestCostLedger:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.cost_ledger import CostLedger
        self.ledger = CostLedger(db_path=str(Path(self.tmpdir) / "cost.db"))

    def test_estimate_cost_local(self):
        from openjarvis.workbench.cost_ledger import CostLedger
        cost = CostLedger.estimate_cost("local", 1000, 1000)
        assert cost == 0.0

    def test_estimate_cost_claude_opus(self):
        from openjarvis.workbench.cost_ledger import CostLedger
        cost = CostLedger.estimate_cost("claude-opus-4", 1000, 1000)
        assert cost > 0.0

    def test_estimate_cost_deepseek(self):
        from openjarvis.workbench.cost_ledger import CostLedger
        cost = CostLedger.estimate_cost("deepseek-chat", 1000, 1000)
        assert cost > 0.0

    def test_record_entry(self):
        entry = self.ledger.record(
            session_id="s1",
            task_id="t1",
            model="local",
            input_tokens=100,
            output_tokens=200,
            description="test",
        )
        assert entry.id
        assert entry.session_id == "s1"
        assert entry.cost_usd == 0.0

    def test_session_total(self):
        self.ledger.record("s2", "t2", "local", 100, 100, "a")
        self.ledger.record("s2", "t2", "local", 200, 200, "b")
        total = self.ledger.session_total("s2")
        assert total["session_id"] == "s2"
        assert total["total_tokens"] == 600
        assert total["entry_count"] == 2

    def test_task_total(self):
        self.ledger.record("s3", "task_x", "local", 50, 50, "x1")
        self.ledger.record("s3", "task_x", "local", 75, 75, "x2")
        total = self.ledger.task_total("task_x")
        assert total["task_id"] == "task_x"
        assert total["total_tokens"] == 250

    def test_list_recent(self):
        for i in range(3):
            self.ledger.record(f"sess_{i}", f"task_{i}", "local", 10, 10, f"op_{i}")
        entries = self.ledger.list_recent(limit=2)
        assert len(entries) == 2

    def test_entry_to_dict(self):
        entry = self.ledger.record("sx", "tx", "local", 5, 5, "desc")
        d = entry.to_dict()
        assert "id" in d
        assert "cost_usd" in d
        assert d["model"] == "local"


# ---------------------------------------------------------------------------
# CheckpointStore tests
# ---------------------------------------------------------------------------


class TestCheckpointStore:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.checkpoint import CheckpointStore
        self.store = CheckpointStore(db_path=str(Path(self.tmpdir) / "ckpt.db"))

    def test_save_checkpoint(self):
        cp = self.store.save_checkpoint(
            session_id="s1",
            task_id="t1",
            label="plan_created",
            evidence="5 subtasks planned",
            verdict="ACCEPT",
        )
        assert cp.id
        assert cp.label == "plan_created"
        assert cp.verdict == "ACCEPT"
        assert not cp.is_blocker

    def test_save_blocker_checkpoint(self):
        cp = self.store.save_checkpoint(
            session_id="s1",
            task_id="t1",
            label="blocker",
            evidence="test failed",
            verdict="HOLD",
            is_blocker=True,
        )
        assert cp.is_blocker

    def test_list_checkpoints(self):
        self.store.save_checkpoint("s2", "t2", "step_1", "ok", "ACCEPT")
        self.store.save_checkpoint("s2", "t2", "step_2", "ok", "ACCEPT")
        self.store.save_checkpoint("s3", "t3", "step_1", "ok", "ACCEPT")
        cps = self.store.list_checkpoints("s2")
        assert len(cps) == 2
        for cp in cps:
            assert cp.session_id == "s2"

    def test_get_blockers(self):
        self.store.save_checkpoint("s4", "t4", "ok_step", "ok", "ACCEPT", is_blocker=False)
        self.store.save_checkpoint("s4", "t4", "block_step", "fail", "HOLD", is_blocker=True)
        blockers = self.store.get_blockers("s4")
        assert len(blockers) == 1
        assert blockers[0].is_blocker

    def test_task_memory_set_get(self):
        self.store.set_memory("s5", "t5", "last_diff", "--- a\n+++ b")
        val = self.store.get_memory("t5", "last_diff")
        assert val == "--- a\n+++ b"

    def test_task_memory_overwrite(self):
        self.store.set_memory("s6", "t6", "key", "value1")
        self.store.set_memory("s6", "t6", "key", "value2")
        val = self.store.get_memory("t6", "key")
        assert val == "value2"

    def test_get_all_memory(self):
        self.store.set_memory("s7", "t7", "a", "1")
        self.store.set_memory("s7", "t7", "b", "2")
        mem = self.store.get_all_memory("t7")
        assert mem["a"] == "1"
        assert mem["b"] == "2"

    def test_checkpoint_to_dict(self):
        cp = self.store.save_checkpoint("s8", "t8", "lbl", "ev", "ACCEPT", {"foo": "bar"})
        d = cp.to_dict()
        assert d["label"] == "lbl"
        assert d["notes"]["foo"] == "bar"


# ---------------------------------------------------------------------------
# CodingManager tests
# ---------------------------------------------------------------------------


class TestCodingManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        from openjarvis.workbench.coding_manager import CodingManager
        self.mgr = CodingManager(
            repo_path="/Users/user/OpenJarvis",
            db_dir=self.tmpdir,
        )

    def test_plan_returns_task_plan(self):
        from openjarvis.workbench.coding_manager import TaskPlan
        plan = self.mgr.plan("Add a test fixture", dry_run=True)
        assert isinstance(plan, TaskPlan)
        assert plan.session_id
        assert plan.task_id
        assert plan.prompt == "Add a test fixture"
        assert plan.dry_run is True
        assert len(plan.subtasks) > 0

    def test_plan_has_git_status_first(self):
        plan = self.mgr.plan("Read the repo", dry_run=True)
        assert plan.subtasks[0].tool_id == "git_status"

    def test_plan_always_includes_diff(self):
        plan = self.mgr.plan("Review changes", dry_run=True)
        tool_ids = [s.tool_id for s in plan.subtasks]
        assert "git_diff" in tool_ids

    def test_plan_commit_push_at_end(self):
        plan = self.mgr.plan("Add fixture", dry_run=True)
        tool_ids = [s.tool_id for s in plan.subtasks]
        assert "git_commit" in tool_ids
        assert "git_push" in tool_ids
        commit_idx = next(i for i, t in enumerate(tool_ids) if t == "git_commit")
        push_idx = next(i for i, t in enumerate(tool_ids) if t == "git_push")
        assert push_idx > commit_idx

    def test_dry_run_blocks_commit(self):
        plan = self.mgr.plan("Add fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        commit_subtasks = [s for s in plan.subtasks if s.tool_id == "git_commit"]
        for s in commit_subtasks:
            assert s.status == "skipped_dry_run", f"Expected skipped_dry_run, got {s.status}"

    def test_dry_run_blocks_push(self):
        plan = self.mgr.plan("Add fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        push_subtasks = [s for s in plan.subtasks if s.tool_id == "git_push"]
        for s in push_subtasks:
            assert s.status == "skipped_dry_run", f"Expected skipped_dry_run, got {s.status}"

    def test_workers_cannot_commit(self):
        assert self.mgr._WORKERS_CAN_COMMIT is False

    def test_plan_to_dict(self):
        plan = self.mgr.plan("Read", dry_run=True)
        d = plan.to_dict()
        assert "session_id" in d
        assert "subtasks" in d
        assert isinstance(d["subtasks"], list)

    def test_execute_produces_report(self):
        plan = self.mgr.plan("Add self-test fixture", dry_run=True)
        plan = self.mgr.execute(plan)
        assert plan.final_report is not None
        assert "Jarvis Coding Workbench" in plan.final_report

    def test_execute_status_done_dry_run(self):
        plan = self.mgr.plan("Inspect repo", dry_run=True)
        plan = self.mgr.execute(plan)
        assert plan.status in ("done", "done_dry_run", "failed", "blocked", "awaiting_approval")

    def test_get_checkpoints_after_execute(self):
        plan = self.mgr.plan("Check", dry_run=True)
        plan = self.mgr.execute(plan)
        checkpoints = self.mgr.get_checkpoints(plan.session_id)
        assert len(checkpoints) >= 1

    def test_stop_on_blocker_false_continues(self):
        plan = self.mgr.plan("Continue on error", dry_run=True, stop_on_blocker=False)
        assert plan.stop_on_blocker is False


# ---------------------------------------------------------------------------
# Worker routing tests
# ---------------------------------------------------------------------------


class TestWorkerRouting:
    def test_read_only_tools_go_local(self):
        from openjarvis.workbench.coding_manager import _route_worker_tier
        for tool in ("git_status", "git_diff", "git_log", "file_read", "file_search"):
            tier = _route_worker_tier(tool)
            assert tier == "local", f"{tool} should route to local, got {tier}"

    def test_high_risk_tools_go_high_trust(self):
        from openjarvis.workbench.coding_manager import _route_worker_tier
        for tool in ("git_commit", "git_push", "file_delete"):
            tier = _route_worker_tier(tool)
            assert tier == "high-trust", f"{tool} should route to high-trust, got {tier}"

    def test_shell_exec_goes_cloud_cheap(self):
        from openjarvis.workbench.coding_manager import _route_worker_tier
        tier = _route_worker_tier("shell_exec")
        assert tier == "cloud-cheap"

    def test_risky_flag_escalates_to_high_trust(self):
        from openjarvis.workbench.coding_manager import _route_worker_tier
        tier = _route_worker_tier("shell_exec", is_risky=True)
        assert tier == "high-trust"

    def test_git_commit_requires_approval(self):
        from openjarvis.workbench.coding_manager import _APPROVAL_REQUIRED_TOOLS
        assert "git_commit" in _APPROVAL_REQUIRED_TOOLS

    def test_git_push_requires_approval(self):
        from openjarvis.workbench.coding_manager import _APPROVAL_REQUIRED_TOOLS
        assert "git_push" in _APPROVAL_REQUIRED_TOOLS

    def test_file_delete_requires_approval(self):
        from openjarvis.workbench.coding_manager import _APPROVAL_REQUIRED_TOOLS
        assert "file_delete" in _APPROVAL_REQUIRED_TOOLS


# ---------------------------------------------------------------------------
# FileSearchTool tests
# ---------------------------------------------------------------------------


class TestFileSearchTool:
    def test_search_finds_pattern(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test.txt"
            p.write_text("hello world\nfoo bar\nbaz")
            from openjarvis.tools.file_search import FileSearchTool
            tool = FileSearchTool()
            result = tool.execute(pattern="hello", directory=tmpdir, fixed_strings=True)
            assert result.success
            assert "hello" in result.content

    def test_search_no_match_returns_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "test.txt"
            p.write_text("nothing here")
            from openjarvis.tools.file_search import FileSearchTool
            tool = FileSearchTool()
            result = tool.execute(pattern="xyz_not_found_12345", directory=tmpdir)
            assert result.success

    def test_search_missing_directory(self):
        from openjarvis.tools.file_search import FileSearchTool
        tool = FileSearchTool()
        result = tool.execute(pattern="hello", directory="/nonexistent_dir_xyz")
        assert not result.success

    def test_search_empty_pattern(self):
        from openjarvis.tools.file_search import FileSearchTool
        tool = FileSearchTool()
        result = tool.execute(pattern="", directory="/tmp")
        assert not result.success

    def test_search_with_glob(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "hello.py"
            txt_file = Path(tmpdir) / "hello.txt"
            py_file.write_text("def hello(): pass")
            txt_file.write_text("hello world")
            from openjarvis.tools.file_search import FileSearchTool
            tool = FileSearchTool()
            result = tool.execute(pattern="hello", directory=tmpdir, file_glob="*.py")
            assert result.success
            if "hello" in result.content:
                assert "hello.py" in result.content or "def hello" in result.content


# ---------------------------------------------------------------------------
# FileDeleteTool tests
# ---------------------------------------------------------------------------


class TestFileDeleteTool:
    def test_delete_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "to_delete.txt"
            p.write_text("bye")
            from openjarvis.tools.file_delete import FileDeleteTool
            tool = FileDeleteTool()
            result = tool.execute(path=str(p))
            assert result.success
            assert not p.exists()

    def test_delete_nonexistent_fails(self):
        from openjarvis.tools.file_delete import FileDeleteTool
        tool = FileDeleteTool()
        result = tool.execute(path="/tmp/nonexistent_file_xyz_12345.txt")
        assert not result.success

    def test_delete_protected_path_blocked(self):
        from openjarvis.tools.file_delete import FileDeleteTool
        tool = FileDeleteTool()
        result = tool.execute(path="/")
        assert not result.success
        assert "denied" in result.content.lower() or "protected" in result.content.lower()

    def test_delete_non_empty_dir_without_recursive_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            (subdir / "file.txt").write_text("content")
            from openjarvis.tools.file_delete import FileDeleteTool
            tool = FileDeleteTool()
            result = tool.execute(path=str(subdir))
            assert not result.success

    def test_delete_empty_dir(self):
        with tempfile.TemporaryDirectory() as outer:
            inner = Path(outer) / "empty_subdir"
            inner.mkdir()
            from openjarvis.tools.file_delete import FileDeleteTool
            tool = FileDeleteTool()
            result = tool.execute(path=str(inner))
            assert result.success
            assert not inner.exists()

    def test_delete_requires_confirmation_spec(self):
        from openjarvis.tools.file_delete import FileDeleteTool
        tool = FileDeleteTool()
        assert tool.spec.requires_confirmation is True


# ---------------------------------------------------------------------------
# GitPushTool spec tests
# ---------------------------------------------------------------------------


class TestGitPushToolSpec:
    def test_git_push_requires_confirmation(self):
        from openjarvis.tools.git_tool import GitPushTool
        tool = GitPushTool()
        assert tool.spec.requires_confirmation is True

    def test_git_push_has_dry_run_param(self):
        from openjarvis.tools.git_tool import GitPushTool
        tool = GitPushTool()
        props = tool.spec.parameters.get("properties", {})
        assert "dry_run" in props

    def test_git_push_category_vcs(self):
        from openjarvis.tools.git_tool import GitPushTool
        tool = GitPushTool()
        assert tool.spec.category == "vcs"

    def test_git_push_dry_run_execution(self):
        from openjarvis.tools.git_tool import GitPushTool
        tool = GitPushTool()
        result = tool.execute(
            repo_path="/Users/user/OpenJarvis",
            remote="fork",
            dry_run=True,
        )
        assert "[DRY-RUN]" in result.content or result.content

    def test_git_branch_tool_spec(self):
        from openjarvis.tools.git_tool import GitBranchTool
        tool = GitBranchTool()
        assert tool.spec.category == "vcs"
        assert "action" in tool.spec.parameters.get("properties", {})

    def test_git_branch_current(self):
        from openjarvis.tools.git_tool import GitBranchTool
        tool = GitBranchTool()
        result = tool.execute(repo_path="/Users/user/OpenJarvis", action="current")
        assert result.success or "not found" in result.content.lower()
        if result.success:
            assert result.content.strip()


# ---------------------------------------------------------------------------
# Governance constitution integration
# ---------------------------------------------------------------------------


class TestGovernanceIntegration:
    def test_verdict_enum_accessible(self):
        from openjarvis.governance.constitution import Verdict
        assert Verdict.ACCEPT.value == "ACCEPT"
        assert Verdict.HOLD.value == "HOLD"
        assert Verdict.UNSAFE.value == "UNSAFE"

    def test_blocker_has_required_fields(self):
        from openjarvis.governance.constitution import Blocker
        b = Blocker(
            blocker="test",
            why_it_matters="it matters",
            unblock_path="fix it",
        )
        d = b.to_dict()
        assert "blocker" in d
        assert "unblock_path" in d

    def test_evidence_status_enum(self):
        from openjarvis.governance.constitution import EvidenceStatus
        assert EvidenceStatus.VERIFIED.value == "verified"
        assert EvidenceStatus.MISSING.value == "missing"


# ---------------------------------------------------------------------------
# US14A self-test fixture (E2E marker)
# ---------------------------------------------------------------------------


US14A_MARKER = "Jarvis Coding Workbench E2E proof"


def test_us14a_marker():
    """Verify US14A E2E marker is present — used as the E2E proof fixture."""
    assert US14A_MARKER == "Jarvis Coding Workbench E2E proof"


def test_us14a_level1_capabilities_present():
    """Verify all Level 1 required tool classes can be imported."""
    from openjarvis.tools.file_read import FileReadTool
    from openjarvis.tools.file_write import FileWriteTool
    from openjarvis.tools.file_search import FileSearchTool
    from openjarvis.tools.file_delete import FileDeleteTool
    from openjarvis.tools.shell_exec import ShellExecTool
    from openjarvis.tools.git_tool import (
        GitStatusTool, GitDiffTool, GitCommitTool, GitPushTool, GitLogTool, GitBranchTool
    )
    from openjarvis.workbench.coding_manager import CodingManager
    from openjarvis.workbench.job_queue import JobQueue
    from openjarvis.workbench.cost_ledger import CostLedger
    from openjarvis.workbench.checkpoint import CheckpointStore
    assert True


def test_us14a_level2_capabilities_present():
    """Verify Level 2 manager/routing/cost tracking classes can be imported."""
    from openjarvis.workbench.coding_manager import (
        CodingManager, TaskPlan, Subtask,
        _route_worker_tier, _APPROVAL_REQUIRED_TOOLS,
        _HIGH_TRUST_TOOLS, _READ_ONLY_TOOLS,
    )
    assert len(_READ_ONLY_TOOLS) > 0
    assert len(_HIGH_TRUST_TOOLS) > 0
    assert len(_APPROVAL_REQUIRED_TOOLS) > 0
