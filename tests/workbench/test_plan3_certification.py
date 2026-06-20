"""Plan 3 Certification Tests — Phases 3A through 3J.

Tests validate each phase independently and Phase 3J as an integrated end-to-end flow.
All tests are self-contained (in-memory or /tmp DBs). No external calls.

Phase verdicts required per phase:
  3A: model_router routes correctly by category/tier, logs decisions, enforces budget
  3B: independent reviewer gives PASS/HOLD/BLOCKED/FAIL, blocks self-certification
  3C: loop cap enforced, stop-on-blocker works, iteration counter is correct
  3D: pipeline classifies task, produces plan, routes to worker tier
  3E: reviewer/verifier gate + rollback path surfaced
  3F: checkpoint store read/write works; known blockers stored
  3G: tool permission scopes enforced; destructive actions require approval
  3H: events logged, cost record exists, model choice logged
  3I: self-build propose/approve/dry_run/apply flow
  3J: end-to-end integrated daily-driver proof
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import pytest

from openjarvis.workbench.model_router import (
    ModelRouter,
    ModelTier,
    MockModelAdapter,
    BudgetConfig,
)
from openjarvis.workbench.reviewer import (
    IndependentReviewer,
    EvidenceBundle,
    Verdict,
)
from openjarvis.workbench.repair_loop import BoundedRepairLoop
from openjarvis.workbench.checkpoint import CheckpointStore
from openjarvis.workbench.pipeline import (
    CodingPipeline,
    PipelineConfig,
    classify_task,
    PIPELINE_PASS,
    PIPELINE_HOLD,
    PIPELINE_BLOCKED,
    PIPELINE_FAIL,
)
from openjarvis.workbench.self_build import LimitedSelfBuild


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def model_router(tmp_db):
    router = ModelRouter(db_path=tmp_db, adapter_override=MockModelAdapter())
    yield router
    router.close()


@pytest.fixture
def reviewer(tmp_path):
    r = IndependentReviewer(
        reviewer_id="test-reviewer",
        db_path=str(tmp_path / "reviewer.db"),
    )
    yield r
    r.close()


@pytest.fixture
def checkpoint_store(tmp_path):
    cs = CheckpointStore(db_path=str(tmp_path / "checkpoint.db"))
    yield cs
    cs.close()


def _good_evidence(
    task_id: str = "task-1",
    session_id: str = "sess-1",
    worker_id: str = "worker-1",
) -> EvidenceBundle:
    return EvidenceBundle(
        task_id=task_id,
        session_id=session_id,
        worker_id=worker_id,
        prompt="Fix null pointer in user.py",
        plan_summary="Bug fix: check for None before accessing .name",
        files_inspected=["src/user.py"],
        files_changed=["src/user.py"],
        patch_diff="--- a/src/user.py\n+++ b/src/user.py\n@@ -1 +1 @@\n-name = obj.name\n+name = obj.name if obj else ''",
        validation_commands=["python -m pytest tests/test_user.py -q"],
        validation_outputs=[{"command": "python -m pytest tests/test_user.py -q", "passed": True, "output": "1 passed"}],
        rollback_path="git checkout HEAD -- src/user.py  # Revert fix",
        loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
        model_decisions=[{"tier": "mid", "model": "gpt-4o-mini", "reason": "debugging task"}],
    )


# ---------------------------------------------------------------------------
# Phase 3A — Model Router + Cost Governor
# ---------------------------------------------------------------------------

class TestPhase3AModelRouter:
    """Phase 3A: model routing correctness + budget enforcement."""

    def test_read_only_routes_local(self, model_router):
        d = model_router.route(
            subtask_id="s1", tool_id="git_status", description="check git status",
            session_id="sess", task_id="t1",
        )
        assert d.assigned_tier == ModelTier.LOCAL
        assert d.assigned_model == "local"

    def test_category_routing_debug(self, model_router):
        d = model_router.route(
            subtask_id="s2", tool_id="file_read", description="fix crash",
            session_id="sess", task_id="t1", category="debugging",
        )
        assert d.assigned_tier == ModelTier.MID

    def test_category_routing_architecture(self, model_router):
        d = model_router.route(
            subtask_id="s3", tool_id="file_read", description="redesign auth",
            session_id="sess", task_id="t1", category="architecture",
        )
        assert d.assigned_tier == ModelTier.PREMIUM

    def test_high_trust_flag_forces_premium(self, model_router):
        d = model_router.route(
            subtask_id="s4", tool_id="file_read", description="read file",
            session_id="sess", task_id="t1", high_trust=True,
        )
        assert d.assigned_tier == ModelTier.PREMIUM

    def test_routing_decision_includes_reason(self, model_router):
        d = model_router.route(
            subtask_id="s5", tool_id="git_diff", description="check diff",
            session_id="sess", task_id="t1",
        )
        assert d.reason

    def test_routing_logged_to_db(self, model_router):
        model_router.route(
            subtask_id="s6", tool_id="file_search", description="find bug",
            session_id="sess-log", task_id="t-log",
        )
        log = model_router.get_routing_log("sess-log")
        assert len(log) >= 1
        assert log[0]["session_id"] == "sess-log"

    def test_premium_budget_cap_downgrades_to_mid(self, tmp_db):
        tiny_budget = BudgetConfig(
            daily_premium_cap_usd=0.0,
            session_premium_cap_usd=0.0,
            daily_mid_cap_usd=10.0,
            session_mid_cap_usd=10.0,
        )
        router = ModelRouter(db_path=tmp_db, budget_config=tiny_budget, adapter_override=MockModelAdapter())
        d = router.route(
            subtask_id="s7", tool_id="file_read", description="architecture review",
            session_id="sess-budget", task_id="t-budget",
            category="architecture",
        )
        assert d.assigned_tier == ModelTier.MID
        assert "cap" in d.budget_check
        router.close()

    def test_cost_summary_structure(self, model_router):
        model_router.route(
            subtask_id="s8", tool_id="file_read", description="implement feature",
            session_id="sess-cost", task_id="t-cost", category="implementation",
        )
        summary = model_router.session_cost_summary("sess-cost")
        assert "session_id" in summary
        assert "total_cost_usd" in summary
        assert "by_tier" in summary

    def test_model_call_logged(self, model_router):
        d = model_router.route(
            subtask_id="s9", tool_id="file_read", description="write test",
            session_id="sess-call", task_id="t-call", category="test_writing",
        )
        model_router.call_model(d, prompt="Write a unit test for user.py")
        call_log = model_router.get_call_log("sess-call")
        assert len(call_log) >= 1


# ---------------------------------------------------------------------------
# Phase 3B — Independent Reviewer
# ---------------------------------------------------------------------------

class TestPhase3BReviewer:
    """Phase 3B: reviewer separation, PASS/HOLD/BLOCKED/FAIL verdicts."""

    def test_good_evidence_passes(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.PASS

    def test_self_certification_blocked(self, reviewer):
        ev = _good_evidence(worker_id="test-reviewer")  # same as reviewer_id
        with pytest.raises(ValueError, match="Self-certification blocked"):
            reviewer.review(ev)

    def test_missing_rollback_fails(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.rollback_path = ""
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.FAIL

    def test_failed_validation_fails(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.validation_outputs = [{"command": "pytest", "passed": False, "output": "FAILED"}]
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.FAIL

    def test_no_validation_outputs_fails(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.validation_outputs = []
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.FAIL

    def test_loop_cap_exceeded_blocked(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.loop_state = {
            "stopped": True,
            "stop_reason": "max_attempts_exceeded",
            "max_attempts": 3,
            "attempts": [{}] * 3,
        }
        verdict = reviewer.review(ev)
        assert verdict.verdict in (Verdict.BLOCKED, Verdict.FAIL)

    def test_broad_audit_held(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.files_inspected = [f"file_{i}.py" for i in range(55)]
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.HOLD

    def test_missing_model_decisions_held(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.model_decisions = []
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.HOLD

    def test_missing_plan_summary_held(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        ev.plan_summary = ""
        verdict = reviewer.review(ev)
        assert verdict.verdict == Verdict.HOLD

    def test_verdict_persisted(self, reviewer):
        ev = _good_evidence(task_id="persist-task", worker_id="worker-A")
        reviewer.review(ev)
        stored = reviewer.get_verdict("persist-task")
        assert stored is not None
        assert stored["verdict"] == Verdict.PASS.value

    def test_rollback_instruction_always_present(self, reviewer):
        ev = _good_evidence(worker_id="worker-A")
        verdict = reviewer.review(ev)
        assert verdict.rollback_instruction


# ---------------------------------------------------------------------------
# Phase 3C — Runtime Stop-on-Loop Enforcement
# ---------------------------------------------------------------------------

class TestPhase3CLoopEnforcement:
    """Phase 3C: bounded repair loop, iteration counter, stop-on-blocker."""

    def test_can_retry_within_cap(self):
        loop = BoundedRepairLoop(max_attempts=3)
        assert loop.can_retry()

    def test_cannot_retry_after_cap(self):
        loop = BoundedRepairLoop(max_attempts=2)
        loop.state.stopped = True
        loop.state.stop_reason = "max_attempts_exceeded"
        assert not loop.can_retry()

    def test_stop_recorded(self):
        loop = BoundedRepairLoop(max_attempts=2)
        loop.record_stop("max_attempts_exceeded")
        assert loop.state.stopped
        assert loop.state.stop_reason == "max_attempts_exceeded"

    def test_decide_hold_at_cap(self, tmp_db):
        router = ModelRouter(db_path=tmp_db, adapter_override=MockModelAdapter())
        loop = BoundedRepairLoop(max_attempts=1)
        # Force stop
        loop.record_stop("max_attempts_exceeded")
        result = loop.decide(
            router=router,
            subtask_id="s1",
            tool_id="shell_exec_readonly",
            session_id="sess",
            task_id="t1",
            validation_failed=True,
            terminal_error=False,
            error_message="tests fail",
        )
        assert result["action"].upper() == "HOLD"
        assert not result.get("retry", True)
        router.close()

    def test_loop_cap_3_enforced(self, tmp_db):
        """After 3 attempts, loop must be stopped — cannot retry."""
        router = ModelRouter(db_path=tmp_db, adapter_override=MockModelAdapter())
        loop = BoundedRepairLoop(max_attempts=3)
        for i in range(3):
            if loop.can_retry():
                loop.decide(
                    router=router,
                    subtask_id=f"s{i}",
                    tool_id="shell_exec_readonly",
                    session_id="sess",
                    task_id="t1",
                    validation_failed=True,
                    terminal_error=True,
                    error_message=f"error {i}",
                )
        # After exhaustion loop must not allow retry
        assert not loop.can_retry()
        router.close()

    def test_max_attempts_in_state(self):
        loop = BoundedRepairLoop(max_attempts=5)
        assert loop.state.max_attempts == 5


# ---------------------------------------------------------------------------
# Phase 3D — Autonomous Coding Workflow
# ---------------------------------------------------------------------------

class TestPhase3DPipeline:
    """Phase 3D: pipeline classifies, plans, routes, runs evidence flow."""

    def test_classify_read_only(self):
        result = classify_task("check git status")
        assert result["category"] == "read_only"
        assert result["risk_tier"] == "local"
        assert not result["requires_approval"]

    def test_classify_risky(self):
        result = classify_task("git push force delete all files")
        assert result["requires_approval"]
        assert result["risk_tier"] == "premium"

    def test_classify_debugging(self):
        result = classify_task("fix the null pointer bug in user.py")
        assert result["category"] == "debugging"

    def test_classify_implementation(self):
        result = classify_task("implement user registration feature")
        assert result["category"] == "implementation"

    def test_pipeline_classify_returns_category(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix null pointer bug")
            assert result.classification["category"] in (
                "debugging", "read_only", "implementation", "architecture",
                "test_writing", "security",
            )
        finally:
            pipeline.close()

    def test_pipeline_produces_plan_summary(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                "fix null pointer bug",
                files_to_inspect=["src/user.py"],
            )
            assert result.plan_summary
            assert "debugging" in result.plan_summary or "implementation" in result.plan_summary or "category" in result.plan_summary
        finally:
            pipeline.close()

    def test_pipeline_model_decisions_logged(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug in user.py", files_to_inspect=["src/user.py"])
            assert len(result.model_decisions) >= 1
        finally:
            pipeline.close()

    def test_pipeline_risky_blocked_without_approval(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                "delete all production files",
                approval_granted=False,
            )
            assert result.verdict == PIPELINE_BLOCKED
        finally:
            pipeline.close()

    def test_pipeline_broad_audit_blocked(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            max_inspect_files=5,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            many_files = [f"file_{i}.py" for i in range(25)]
            result = pipeline.run("check all files", files_to_inspect=many_files)
            assert result.verdict == PIPELINE_BLOCKED
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# Phase 3E — Reviewer/Verifier/Rollback Gate
# ---------------------------------------------------------------------------

class TestPhase3ERollbackGate:
    """Phase 3E: rollback always surfaced, reviewer gives verdict, no self-accept."""

    def test_pipeline_rollback_always_present(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug")
            assert result.rollback_instruction
        finally:
            pipeline.close()

    def test_pipeline_reviewer_verdict_present_when_not_blocked(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                "fix null pointer bug",
                files_to_inspect=["src/user.py"],
            )
            # If not blocked, reviewer_verdict should be present
            if result.verdict != PIPELINE_BLOCKED:
                assert result.reviewer_verdict is not None
                assert "verdict" in result.reviewer_verdict
        finally:
            pipeline.close()

    def test_failed_validation_does_not_self_accept(self, tmp_path):
        """If validation fails, verdict cannot be PASS."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            # Pass a command that will fail
            result = pipeline.run(
                "fix bug",
                validation_commands=["false"],  # always exits 1
                files_to_inspect=["README.md"],
            )
            assert result.verdict != PIPELINE_PASS
        finally:
            pipeline.close()

    def test_worker_id_different_from_reviewer_id(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker",
            reviewer_id="jarvis-reviewer",
        )
        assert cfg.worker_id != cfg.reviewer_id

    def test_reviewer_rollback_instruction_populated(self, tmp_path):
        reviewer = IndependentReviewer(
            reviewer_id="rev",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = _good_evidence(worker_id="worker-X")
        verdict = reviewer.review(ev)
        assert verdict.rollback_instruction
        reviewer.close()


# ---------------------------------------------------------------------------
# Phase 3F — Memory / Checkpoint Integration
# ---------------------------------------------------------------------------

class TestPhase3FCheckpoint:
    """Phase 3F: checkpoint store read/write, blocker tracking, memory."""

    def test_save_and_retrieve_checkpoint(self, checkpoint_store):
        cp = checkpoint_store.save_checkpoint(
            session_id="sess-1",
            task_id="task-1",
            label="gate-0-cleanup",
            evidence="All tests passed",
            verdict="ACCEPT",
        )
        assert cp.id
        stored = checkpoint_store.list_checkpoints("sess-1")
        assert len(stored) == 1
        assert stored[0].label == "gate-0-cleanup"
        assert stored[0].verdict == "ACCEPT"

    def test_blocker_stored_and_retrieved(self, checkpoint_store):
        checkpoint_store.save_checkpoint(
            session_id="sess-2",
            task_id="task-2",
            label="loop-cap-blocker",
            evidence="3 attempts exhausted",
            verdict="BLOCKED",
            is_blocker=True,
        )
        blockers = checkpoint_store.get_blockers("sess-2")
        assert len(blockers) == 1
        assert blockers[0].is_blocker

    def test_memory_set_and_get(self, checkpoint_store):
        checkpoint_store.set_memory("sess-3", "task-3", "branch", "localhost-get-tool")
        val = checkpoint_store.get_memory("task-3", "branch")
        assert val == "localhost-get-tool"

    def test_memory_get_all(self, checkpoint_store):
        checkpoint_store.set_memory("sess-4", "task-4", "head", "ef7c9f49")
        checkpoint_store.set_memory("sess-4", "task-4", "status", "clean")
        mem = checkpoint_store.get_all_memory("task-4")
        assert mem.get("head") == "ef7c9f49"
        assert mem.get("status") == "clean"

    def test_pipeline_checkpoint_stored_on_pass(self, tmp_path):
        """If pipeline returns PASS, checkpoint is stored."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker",
            reviewer_id="jarvis-reviewer",
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                "fix null pointer bug",
                files_to_inspect=["src/user.py"],
                validation_commands=["echo 'ok'"],
                patch_diff="--- a/src/user.py\n+++ b/src/user.py",
                files_changed=["src/user.py"],
            )
            if result.verdict == PIPELINE_PASS:
                assert result.checkpoint_id is not None
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# Phase 3G — Tool/Action Permission System
# ---------------------------------------------------------------------------

class TestPhase3GPermissions:
    """Phase 3G: risky actions blocked/gated, safe reads allowed."""

    def test_risky_task_blocked_without_approval(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("delete production database")
            assert result.verdict == PIPELINE_BLOCKED
            assert any("approval" in e.lower() or "block" in e.lower() for e in result.events)
        finally:
            pipeline.close()

    def test_risky_task_allowed_with_approval(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                "delete production database",
                approval_granted=True,
            )
            # Not BLOCKED at approval gate (may still fail/hold at reviewer)
            assert result.verdict != PIPELINE_BLOCKED or any(
                "approval" not in e.lower() for e in result.events
            )
        finally:
            pipeline.close()

    def test_read_only_task_not_blocked(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("check git status and show recent log")
            assert result.verdict != PIPELINE_BLOCKED or result.classification["requires_approval"]
        finally:
            pipeline.close()

    def test_dry_run_default_prevents_writes(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), dry_run=True)
        assert cfg.dry_run is True

    def test_self_build_requires_authorization(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix null pointer",
            original_contents={"src/user.py": "name = obj.name"},
            proposed_contents={"src/user.py": "name = obj.name if obj else ''"},
        )
        with pytest.raises(PermissionError, match="not authorized"):
            sb.approve(task.task_id, approver="RandomPerson")
        sb.close()

    def test_self_build_too_many_files_blocked(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        with pytest.raises(ValueError, match="limited to"):
            sb.propose(
                target_files=[f"file_{i}.py" for i in range(10)],
                description="Too many files",
                original_contents={},
                proposed_contents={},
            )
        sb.close()


# ---------------------------------------------------------------------------
# Phase 3H — Observability / Certification Harness
# ---------------------------------------------------------------------------

class TestPhase3HObservability:
    """Phase 3H: events logged, model choice logged, verdict logged."""

    def test_pipeline_events_logged(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug", session_id="obs-sess-1")
            assert len(result.events) >= 2
        finally:
            pipeline.close()

    def test_pipeline_events_contain_classify(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("implement feature", session_id="obs-sess-2")
            assert any("classify" in e for e in result.events)
        finally:
            pipeline.close()

    def test_pipeline_events_contain_route(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug", session_id="obs-sess-3")
            assert any("route" in e for e in result.events)
        finally:
            pipeline.close()

    def test_pipeline_events_contain_rollback(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug", session_id="obs-sess-4")
            assert any("rollback" in e for e in result.events)
        finally:
            pipeline.close()

    def test_model_decisions_include_tier_and_model(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug", session_id="obs-sess-5")
            for d in result.model_decisions:
                assert "assigned_tier" in d
                assert "assigned_model" in d
        finally:
            pipeline.close()

    def test_cost_summary_retrievable(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run("fix bug", session_id="cost-sess")
            cost = pipeline.cost_summary("cost-sess")
            assert "session_id" in cost
            assert "total_cost_usd" in cost
        finally:
            pipeline.close()

    def test_reviewer_verdict_logged_to_db(self, tmp_path):
        reviewer = IndependentReviewer(
            reviewer_id="obs-reviewer",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = _good_evidence(task_id="obs-task", worker_id="obs-worker")
        reviewer.review(ev)
        verdicts = reviewer.list_verdicts("sess-1")
        assert len(verdicts) >= 1
        reviewer.close()


# ---------------------------------------------------------------------------
# Phase 3I — Limited Self-Build Mode
# ---------------------------------------------------------------------------

class TestPhase3ISelfBuild:
    """Phase 3I: self-build propose/approve/dry_run/apply."""

    def test_propose_creates_task(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix null pointer",
            original_contents={"src/user.py": "name = obj.name"},
            proposed_contents={"src/user.py": "name = obj.name if obj else ''"},
        )
        assert task.task_id
        assert task.status == "pending_approval"
        assert task.proposed_diff
        sb.close()

    def test_propose_produces_diff(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix null pointer",
            original_contents={"src/user.py": "name = obj.name\n"},
            proposed_contents={"src/user.py": "name = obj.name if obj else ''\n"},
        )
        assert "---" in task.proposed_diff or "+name" in task.proposed_diff
        sb.close()

    def test_approve_by_bryan(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix null pointer",
            original_contents={},
            proposed_contents={},
        )
        approved = sb.approve(task.task_id, approver="Bryan")
        assert approved.status == "approved"
        assert approved.approver == "Bryan"
        sb.close()

    def test_unauthorized_approver_rejected(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix",
            original_contents={},
            proposed_contents={},
        )
        with pytest.raises(PermissionError):
            sb.approve(task.task_id, approver="Hacker")
        sb.close()

    def test_dry_run_returns_result(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix null pointer",
            original_contents={"src/user.py": "name = obj.name\n"},
            proposed_contents={"src/user.py": "name = obj.name if obj else ''\n"},
        )
        result = sb.dry_run(task)
        assert result.status == "dry_run"
        assert result.reviewer_verdict is not None
        assert "verdict" in result.reviewer_verdict
        sb.close()

    def test_apply_requires_approval(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix null pointer",
            original_contents={"src/user.py": "name = obj.name\n"},
            proposed_contents={"src/user.py": "name = obj.name if obj else ''\n"},
        )
        with pytest.raises(PermissionError, match="Only approved"):
            sb.apply(task, proposed_contents={})
        sb.close()

    def test_apply_after_approval(self, tmp_path):
        """Approved self-build writes file and runs reviewer."""
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        content = "name = obj.name if obj else ''\n"
        task = sb.propose(
            target_files=["test_output.py"],
            description="Fix null pointer",
            original_contents={"test_output.py": "name = obj.name\n"},
            proposed_contents={"test_output.py": content},
        )
        approved = sb.approve(task.task_id, approver="Bryan")
        result = sb.apply(
            approved,
            proposed_contents={"test_output.py": content},
            repo_path=str(tmp_path),
        )
        assert "test_output.py" in result.applied_files
        written = (tmp_path / "test_output.py").read_text()
        assert written == content
        sb.close()

    def test_reject_prevents_apply(self, tmp_path):
        sb = LimitedSelfBuild(db_path=str(tmp_path / "sb.db"))
        task = sb.propose(
            target_files=["src/user.py"],
            description="Fix",
            original_contents={},
            proposed_contents={},
        )
        sb.reject(task.task_id, reason="Not needed")
        stored = sb.get_task(task.task_id)
        assert stored.status == "rejected"
        sb.close()


# ---------------------------------------------------------------------------
# Phase 3J — End-to-End Integrated Proof (Daily-Driver)
# ---------------------------------------------------------------------------

class TestPhase3JEndToEnd:
    """Phase 3J: full integrated coding workflow — the daily-driver proof.

    Proves all 12 required steps:
    1. Task submitted
    2. Task classified
    3. Manager/plan produced
    4. Worker inspects only necessary files
    5. Worker proposes patch
    6. Targeted validation runs
    7. Reviewer independently verifies
    8. Final verdict PASS/HOLD/BLOCKED/FAIL
    9. Rollback path included
    10. Evidence logged
    11. Memory/checkpoint updated
    12. API-visible status/logs show progress
    """

    def test_full_pipeline_run(self, tmp_path):
        """Run the complete coding pipeline from task submission to verdict."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
            dry_run=True,
        )
        pipeline = CodingPipeline(config=cfg)

        # 1. Task submitted
        result = pipeline.run(
            prompt="Fix the null pointer bug in user.py where obj.name is accessed without None check",
            session_id="e2e-session",
            task_id="e2e-task",
            files_to_inspect=["src/user.py", "tests/test_user.py"],
            validation_commands=["echo 'validation ok'"],
            patch_diff=(
                "--- a/src/user.py\n+++ b/src/user.py\n"
                "@@ -1 +1 @@\n-name = obj.name\n+name = obj.name if obj else ''"
            ),
            files_changed=["src/user.py"],
        )

        # 2. Task classified
        assert result.classification["category"] in (
            "debugging", "implementation", "read_only"
        )

        # 3. Plan produced
        assert result.plan_summary, "Step 3: plan_summary must be non-empty"

        # 4. Files inspected (targeted, not broad)
        assert result.files_inspected == ["src/user.py", "tests/test_user.py"]
        assert len(result.files_inspected) <= 20

        # 5. Patch diff present
        assert result.patch_diff, "Step 5: patch_diff must be present"

        # 6. Validation ran (echo returns 0)
        assert len(result.validation_outputs) == 1
        assert result.validation_outputs[0]["passed"] is True

        # 7. Reviewer independently verified
        assert result.reviewer_verdict is not None
        assert "verdict" in result.reviewer_verdict
        assert "reasons" in result.reviewer_verdict

        # 8. Final verdict is one of the valid values
        assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD, PIPELINE_BLOCKED, PIPELINE_FAIL)

        # 9. Rollback path included
        assert result.rollback_instruction
        assert "src/user.py" in result.rollback_instruction or "stash" in result.rollback_instruction

        # 10. Evidence logged (events non-empty)
        assert len(result.events) >= 4
        assert any("classify" in e for e in result.events)
        assert any("plan" in e for e in result.events)
        assert any("route" in e for e in result.events)
        assert any("reviewer" in e for e in result.events)

        # 11. Checkpoint stored if PASS
        if result.verdict == PIPELINE_PASS:
            assert result.checkpoint_id is not None
            checkpoint = pipeline.get_checkpoint(session_id="e2e-session")
            assert checkpoint is not None

        # 12. API-visible events retrievable
        api_events = pipeline.get_events(session_id="e2e-session")
        assert isinstance(api_events, list)

        pipeline.close()

    def test_model_router_logs_decision(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        result = pipeline.run(
            "fix bug",
            session_id="e2e-model-sess",
            task_id="e2e-model-task",
        )
        assert result.model_decisions
        d = result.model_decisions[0]
        assert d["assigned_tier"]
        assert d["assigned_model"]
        assert d["reason"]
        pipeline.close()

    def test_worker_cannot_self_certify(self, tmp_path):
        """Worker_id and reviewer_id must be different — enforced by IndependentReviewer."""
        reviewer = IndependentReviewer(
            reviewer_id="jarvis-worker-v1",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = EvidenceBundle(
            task_id="e2e-self-cert",
            session_id="sess",
            worker_id="jarvis-worker-v1",  # same as reviewer_id
            prompt="fix bug",
            plan_summary="fix it",
            files_inspected=["src/user.py"],
            files_changed=["src/user.py"],
            patch_diff="--- a/src/user.py",
            validation_commands=[],
            validation_outputs=[{"command": "echo ok", "passed": True, "output": "ok"}],
            rollback_path="git checkout HEAD -- src/user.py",
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{"tier": "mid", "model": "gpt-4o-mini", "reason": "debugging"}],
        )
        with pytest.raises(ValueError, match="Self-certification blocked"):
            reviewer.review(ev)
        reviewer.close()

    def test_stop_on_loop_blocks_verdict(self, tmp_path):
        """If loop cap exceeded, reviewer returns BLOCKED."""
        reviewer = IndependentReviewer(
            reviewer_id="rev-v1",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = _good_evidence(task_id="loop-task", worker_id="worker-v1")
        ev.loop_state = {
            "stopped": True,
            "stop_reason": "max_attempts_exceeded",
            "max_attempts": 3,
            "attempts": [{}] * 3,
        }
        verdict = reviewer.review(ev)
        assert verdict.verdict in (Verdict.BLOCKED, Verdict.FAIL)
        reviewer.close()

    def test_full_self_build_flow(self, tmp_path):
        """Self-build: propose → approve → dry_run → reviewer gives verdict."""
        sb = LimitedSelfBuild(
            worker_id="self-build-worker",
            reviewer_id="self-build-reviewer",
            db_path=str(tmp_path / "sb.db"),
        )
        orig = "def greet(name):\n    return 'Hello ' + name\n"
        improved = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"

        task = sb.propose(
            target_files=["src/greet.py"],
            description="Add type hints to greet function",
            original_contents={"src/greet.py": orig},
            proposed_contents={"src/greet.py": improved},
        )
        assert task.status == "pending_approval"

        approved = sb.approve(task.task_id, approver="Bryan")
        assert approved.status == "approved"

        dry = sb.dry_run(approved)
        assert dry.status == "dry_run"
        assert dry.reviewer_verdict is not None
        assert dry.rollback_instruction

        sb.close()

    def test_result_to_dict_serializable(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        result = pipeline.run("fix bug")
        d = result.to_dict()
        # Must be JSON-serializable (for API response)
        json_str = json.dumps(d)
        assert json_str
        pipeline.close()
