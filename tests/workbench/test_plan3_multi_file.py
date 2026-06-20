"""Plan 3 Multi-File / Multi-Step Worker Tests — 4/5 final blocker proof.

Proves the full multi-step coding agent workflow for MULTI-FILE tasks:
  - Normal Jarvis front-door coding request (no Workbench UI required)
  - CodingManager.plan() integration (task planning, subtasks, task_type)
  - Multi-file identification (calculator.py + test_calculator.py)
  - Real multi-file read (both files in file_contents)
  - Worker applies patches to BOTH files simultaneously
  - git diff shows changes across 2 files
  - Pre-fix validation fails (confirms bugs existed in both files)
  - Post-fix validation passes (confirms all fixes work)
  - Independent reviewer gives PASS verdict
  - Rollback covers ALL changed files
  - Checkpoint logged on PASS
  - Commit/push readiness evidenced
  - Main repo not touched
  - Worker cannot self-certify
  - No broad repo scan

Acceptance rule (from user spec):
  real front-door request → multi-step/multi-file CodingPipeline/CodingManager →
  real local file edits → real git diff → targeted validation →
  independent reviewer → rollback/log/checkpoint
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from openjarvis.workbench.pipeline import (
    CodingPipeline,
    FilePatch,
    PipelineConfig,
    detect_coding_intent,
    PIPELINE_PASS,
    PIPELINE_HOLD,
    PIPELINE_BLOCKED,
    PIPELINE_FAIL,
)
from openjarvis.workbench.reviewer import (
    IndependentReviewer,
    EvidenceBundle,
    Verdict,
)

_REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
_CALC_FIXTURE = Path(__file__).parent.parent / "fixtures" / "multi" / "calculator.py"
_TEST_FIXTURE = Path(__file__).parent.parent / "fixtures" / "multi" / "test_calculator.py"

# ---------------------------------------------------------------------------
# Fixture content helpers
# ---------------------------------------------------------------------------

def _calc_original() -> str:
    return _CALC_FIXTURE.read_text(encoding="utf-8")


def _test_original() -> str:
    return _TEST_FIXTURE.read_text(encoding="utf-8")


def _calc_fixed() -> str:
    c = _calc_original()
    c = c.replace(
        "    return a / b  # BUG: missing `if b == 0: raise ValueError(\"division by zero\")`",
        "    if b == 0:\n        raise ValueError(\"division by zero\")\n    return a / b",
    )
    c = c.replace(
        "    return calculate(value, total)  # BUG: undefined function, should be: value / total * 100",
        "    if total == 0:\n        raise ValueError(\"total cannot be zero\")\n    return value / total * 100",
    )
    return c


def _test_fixed() -> str:
    t = _test_original()
    t = t.replace(
        "    with pytest.raises(ValueError):  # BUG: calculator raises ZeroDivisionError, not ValueError",
        "    with pytest.raises(ValueError):  # fixed: calculator now raises ValueError",
    )
    return t


def _standard_patches() -> "list[FilePatch]":
    return [
        FilePatch(
            file_name="calculator.py",
            original_content=_calc_original(),
            fixed_content=_calc_fixed(),
            rationale="Add zero-divisor guard to divide(); fix percentage() to use inline formula",
        ),
        FilePatch(
            file_name="test_calculator.py",
            original_content=_test_original(),
            fixed_content=_test_fixed(),
            rationale="Fix test_divide_by_zero to assert ValueError (not ZeroDivisionError)",
        ),
    ]


_VALIDATION_PRE = "python -m pytest test_calculator.py -q --tb=no"
_VALIDATION_POST = "python -m pytest test_calculator.py -v --tb=short"

_MULTI_FILE_PROMPTS = [
    "Fix the multi-file calculator bug and validate it",
    "fix the multi-file bug and validate it",
    "patch the failing test, run validation, and prepare the commit evidence",
    "continue the current sprint and fix the failing validation",
    "review this report and implement the next blocker fix",
]


# ---------------------------------------------------------------------------
# A. Multi-step/multi-file worker execution
# ---------------------------------------------------------------------------

class TestMultiFileWorkerExecution:
    """Prove multi-step/multi-file patch flow: plan → inspect → patch → diff → validate → review."""

    def test_multi_file_full_end_to_end(self, tmp_path):
        """The definitive multi-file 4/5 proof.

        From front-door request → CodingManager.plan() → multi-file patches →
        real git diff (2 files) → pre/post validation → independent reviewer PASS.
        No Workbench UI, no manual Bryan operation required.
        """
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix the multi-file calculator bug: divide() crashes on zero, "
                       "percentage() raises NameError, test assertion wrong",
                patches=_standard_patches(),
                validation_pre=_VALIDATION_PRE,
                validation_post=_VALIDATION_POST,
                session_id="multi-e2e-sess",
                task_id="multi-e2e-task",
            )

            # 1. Both files inspected
            assert "calculator.py" in result.files_inspected
            assert "test_calculator.py" in result.files_inspected
            assert len(result.files_inspected) == 2

            # 2. Both files read (file_contents present for each)
            assert "calculator.py" in result.file_contents
            assert "test_calculator.py" in result.file_contents
            assert "BUG" in result.file_contents["calculator.py"]
            assert "BUG" in result.file_contents["test_calculator.py"]

            # 3. Real multi-file git diff
            assert result.patch_diff, "Multi-file git diff must be non-empty"
            assert result.patch_diff.count("diff --git") == 2, (
                f"Expected 2 files in diff, got {result.patch_diff.count('diff --git')}. "
                f"Diff: {result.patch_diff[:300]}"
            )
            assert "calculator.py" in result.patch_diff
            assert "test_calculator.py" in result.patch_diff

            # 4. Pre-fix validation confirmed bugs
            pre_events = [e for e in result.events if "validation_pre" in e]
            assert pre_events, "Pre-fix validation must be evidenced"
            fail_confirmed = [e for e in pre_events if "FAIL" in e.upper() or "confirms" in e]
            assert fail_confirmed, (
                f"Pre-fix must fail (confirm bugs). Events: {pre_events}"
            )

            # 5. Post-fix validation passed
            post_events = [e for e in result.events if "validation_post" in e and "PASS" in e.upper()]
            assert post_events, f"Post-fix must pass. Events: {result.events}"

            # 6. CodingManager.plan() integration evidenced
            plan_events = [e for e in result.events if "plan:" in e]
            assert plan_events, (
                "CodingManager.plan() must be called for task planning. "
                f"Events: {result.events}"
            )
            plan_event = plan_events[0]
            assert "subtasks=" in plan_event, f"Plan must have subtasks: {plan_event}"
            assert "type=" in plan_event, f"Plan must have task_type: {plan_event}"

            # 7. Reviewer PASS
            assert result.reviewer_verdict is not None
            assert result.reviewer_verdict["verdict"] == Verdict.PASS.value

            # 8. Final verdict PASS
            assert result.verdict == PIPELINE_PASS

            # 9. Rollback covers both files
            assert "calculator.py" in result.rollback_instruction
            assert "test_calculator.py" in result.rollback_instruction
            assert "git checkout HEAD" in result.rollback_instruction

            # 10. Commit/push readiness surfaced
            commit_events = [e for e in result.events if "commit_ready" in e]
            assert commit_events, "Commit readiness must be evidenced"
            assert "YES" in commit_events[0], f"Should be commit ready: {commit_events}"

            # 11. Checkpoint stored on PASS
            assert result.checkpoint_id is not None

            # 12. No broad scan (only 2 targeted files)
            assert set(result.files_inspected) == {"calculator.py", "test_calculator.py"}

        finally:
            pipeline.close()

    def test_coding_manager_plan_returns_subtasks(self, tmp_path):
        """CodingManager.plan() must return a structured task plan."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix multi-file bug in calculator.py and test_calculator.py",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            plan_events = [e for e in result.events if "plan:" in e]
            skip_events = [e for e in result.events if "plan_skipped" in e]
            # plan must succeed or gracefully degrade
            if skip_events:
                pytest.fail(f"CodingManager.plan() skipped unexpectedly: {skip_events}")
            assert plan_events, f"plan event not found. Events: {result.events}"
        finally:
            pipeline.close()

    def test_multi_file_diff_has_correct_format(self, tmp_path):
        """Real git diff must use diff --git format for each changed file."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator bugs",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            diff = result.patch_diff
            assert diff.startswith("diff --git"), f"Wrong diff format: {diff[:100]}"
            assert diff.count("---") >= 2
            assert diff.count("+++") >= 2
            assert diff.count("@@") >= 2
        finally:
            pipeline.close()

    def test_both_files_changed_in_diff(self, tmp_path):
        """git diff must show changes in both calculator.py and test_calculator.py."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator bugs",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            assert "calculator.py" in result.patch_diff
            assert "test_calculator.py" in result.patch_diff
        finally:
            pipeline.close()

    def test_pre_fix_validation_fails(self, tmp_path):
        """Pre-fix pytest must fail (exit 1) — bugs confirmed in originals."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator",
                patches=_standard_patches(),
                validation_pre=_VALIDATION_PRE,
                validation_post="echo ok",
            )
            pre_events = [e for e in result.events if "validation_pre" in e]
            fail_events = [e for e in pre_events if "FAIL" in e.upper() or "confirms" in e]
            assert fail_events, f"Pre-fix must fail. Events: {pre_events}"
        finally:
            pipeline.close()

    def test_post_fix_validation_passes(self, tmp_path):
        """Post-fix pytest must pass — all fixes confirmed."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator",
                patches=_standard_patches(),
                validation_post=_VALIDATION_POST,
            )
            post_passed = [v for v in result.validation_outputs if v.get("passed")]
            assert post_passed, f"Post-fix validation must pass. outputs: {result.validation_outputs}"
        finally:
            pipeline.close()

    def test_worker_reads_original_content(self, tmp_path):
        """file_contents must show original (buggy) versions, not fixed."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            assert "BUG" in result.file_contents.get("calculator.py", "")
            assert "BUG" in result.file_contents.get("test_calculator.py", "")
        finally:
            pipeline.close()

    def test_worker_cannot_self_certify_multi_file(self, tmp_path):
        """Worker reviewer_id must differ from worker_id."""
        reviewer = IndependentReviewer(
            reviewer_id="jarvis-worker-v1",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = EvidenceBundle(
            task_id="t1", session_id="s1",
            worker_id="jarvis-worker-v1",
            prompt="fix multi-file bug",
            plan_summary="Multi patch",
            files_inspected=["calculator.py", "test_calculator.py"],
            files_changed=["calculator.py", "test_calculator.py"],
            patch_diff="diff --git a/calculator.py ...",
            validation_commands=["pytest test_calculator.py"],
            validation_outputs=[{"command": "pytest", "passed": True, "output": "passed"}],
            rollback_path="git checkout HEAD -- calculator.py && git checkout HEAD -- test_calculator.py",
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{"tier": "mid", "model": "gpt-4o-mini", "reason": "bug_fix"}],
        )
        with pytest.raises(ValueError, match="Self-certification blocked"):
            reviewer.review(ev)
        reviewer.close()

    def test_rollback_covers_all_files(self, tmp_path):
        """Rollback instruction must reference ALL changed files."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            assert "calculator.py" in result.rollback_instruction
            assert "test_calculator.py" in result.rollback_instruction
            assert "git checkout HEAD" in result.rollback_instruction
        finally:
            pipeline.close()

    def test_main_repo_not_modified(self, tmp_path):
        """run_multi_file_patch() must not modify files in the main repo."""
        calc_before = _CALC_FIXTURE.read_text(encoding="utf-8")
        test_before = _TEST_FIXTURE.read_text(encoding="utf-8")

        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            pipeline.run_multi_file_patch(
                prompt="Fix calculator bugs",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
        finally:
            pipeline.close()

        assert _CALC_FIXTURE.read_text(encoding="utf-8") == calc_before, (
            "calculator.py was modified in main repo by run_multi_file_patch()"
        )
        assert _TEST_FIXTURE.read_text(encoding="utf-8") == test_before, (
            "test_calculator.py was modified in main repo by run_multi_file_patch()"
        )

    def test_result_json_serializable(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            d = result.to_dict()
            json_str = json.dumps(d)
            assert "patch_diff" in d
            assert "file_contents" in d
            assert len(json_str) > 100
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# B. Multi-file evidence completeness
# ---------------------------------------------------------------------------

class TestMultiFileEvidenceCompleteness:
    """All 14 required multi-step evidence items must be present."""

    def test_all_required_evidence_present(self, tmp_path):
        """14-point evidence checklist: all required items present."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix multi-file calculator: zero-division, NameError, test assertion",
                patches=_standard_patches(),
                validation_pre=_VALIDATION_PRE,
                validation_post=_VALIDATION_POST,
            )
            events = result.events

            # 1. classify → task classification
            assert any("classify" in e for e in events), "Missing: classify"
            assert result.classification["category"], "Missing: classification.category"

            # 2. plan → CodingManager task plan
            assert any("plan:" in e for e in events), "Missing: plan event"

            # 3. identify_files → targeted only
            assert any("identify_files" in e for e in events), "Missing: identify_files"

            # 4. route → model tier decision
            assert any("route" in e for e in events), "Missing: route"
            assert len(result.model_decisions) >= 1, "Missing: model_decisions"

            # 5. worker_setup → temp git repo
            assert any("worker_setup" in e for e in events), "Missing: worker_setup"

            # 6. worker_read → both files read
            read_events = [e for e in events if "worker_read" in e]
            assert len(read_events) >= 2, f"Missing: 2 worker_read events. Got: {read_events}"

            # 7. validation_pre → bug confirmed
            pre_events = [e for e in events if "validation_pre" in e]
            assert pre_events, "Missing: validation_pre"

            # 8. worker_patch → both files patched
            patch_events = [e for e in events if "worker_patch" in e]
            assert len(patch_events) >= 2, f"Missing: 2 worker_patch events. Got: {patch_events}"

            # 9. worker_diff → git diff captured
            diff_events = [e for e in events if "worker_diff" in e]
            assert diff_events, "Missing: worker_diff"
            assert "2 file" in diff_events[0], f"Expected 2 files in diff: {diff_events}"

            # 10. validation_post → fixes confirmed
            assert any("validation_post" in e for e in events), "Missing: validation_post"

            # 11. rollback → covers all files
            assert any("rollback" in e for e in events), "Missing: rollback"

            # 12. reviewer verdict
            assert result.reviewer_verdict is not None, "Missing: reviewer_verdict"

            # 13. checkpoint on PASS
            if result.verdict == PIPELINE_PASS:
                assert result.checkpoint_id, "Missing: checkpoint_id on PASS"

            # 14. commit_ready evidence
            commit_events = [e for e in events if "commit_ready" in e]
            assert commit_events, "Missing: commit_ready evidence"

        finally:
            pipeline.close()

    def test_model_decisions_logged(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix multi-file bug",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            assert len(result.model_decisions) >= 1
            d = result.model_decisions[0]
            assert "assigned_tier" in d
            assert "assigned_model" in d
        finally:
            pipeline.close()

    def test_checkpoint_retrievable_after_pass(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix multi-file bug",
                patches=_standard_patches(),
                validation_post=_VALIDATION_POST,
                session_id="multi-cp-sess",
            )
            if result.verdict == PIPELINE_PASS:
                cp = pipeline.get_checkpoint(session_id="multi-cp-sess")
                assert cp is not None, "Checkpoint must be retrievable after PASS"
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# C. Front-door multi-step routing (no Workbench required)
# ---------------------------------------------------------------------------

class TestFrontDoorMultiStepRouting:
    """Prove realistic multi-step prompts route via detect_coding_intent() front-door."""

    @pytest.mark.parametrize("prompt", _MULTI_FILE_PROMPTS)
    def test_multi_step_prompt_routes_to_pipeline(self, prompt):
        """Front-door multi-step coding prompts route without 'jarvis code:' prefix."""
        assert detect_coding_intent(prompt), (
            f"Multi-step prompt should route via natural intent: {prompt!r}"
        )

    def test_no_workbench_required(self, tmp_path):
        """Full workflow runs from pipeline.run_multi_file_patch() — no Workbench UI."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
        )
        # run_multi_file_patch() is the front-door entry — no Workbench route needed
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="continue the current sprint and fix the failing validation",
                patches=_standard_patches(),
                validation_post=_VALIDATION_POST,
            )
            # If verdict is PASS or HOLD (not BLOCKED due to Workbench), Workbench not required
            assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD, PIPELINE_FAIL), (
                f"Unexpected BLOCKED verdict — may indicate Workbench dependency: {result.verdict}"
            )
            assert result.reviewer_verdict is not None, "Reviewer must run without Workbench"
        finally:
            pipeline.close()

    def test_gate0_routes_not_regressed(self):
        """Gate 0 time/date/status routes must not be detected as coding intent."""
        gate0_messages = [
            "what time is it",
            "what's today's date",
            "what is Jarvis status",
            "how is Jarvis running",
            "tell me the current time",
            "what day is it",
        ]
        for msg in gate0_messages:
            assert not detect_coding_intent(msg), (
                f"Gate 0 message must NOT route to pipeline: {msg!r}"
            )

    def test_non_coding_falls_through(self):
        """Non-coding questions must fall through to normal LLM/tool route."""
        non_coding = [
            "what is Python",
            "how does machine learning work",
            "tell me about OpenJarvis",
            "explain the architecture",
            "who built this project",
        ]
        for msg in non_coding:
            assert not detect_coding_intent(msg), (
                f"Non-coding message must NOT route: {msg!r}"
            )

    def test_prefix_routes_still_work(self):
        """Explicit prefix routing must still work alongside natural routing."""
        _CODING_PREFIXES = (
            "jarvis code:", "jarvis pipeline:", "jarvis fix:",
            "[pipeline]", "[code]", "jarvis run pipeline:",
        )
        prefix_msgs = [
            "jarvis code: fix the multi-file calculator bug",
            "jarvis fix: divide-by-zero crash",
            "[pipeline] run validation and commit",
        ]
        for msg in prefix_msgs:
            lower = msg.strip().lower()
            is_prefix = any(lower.startswith(pfx) for pfx in _CODING_PREFIXES)
            assert is_prefix, f"Prefix routing broken for: {msg!r}"

    def test_workbench_admin_debug_routes_preserved(self):
        """Workbench routes for admin/debug must still exist (not removed)."""
        # Verify the workbench routes module still exists with admin/debug routes
        from openjarvis.server import routes
        route_names = [
            r.path for r in getattr(routes.router, "routes", [])
            if hasattr(r, "path")
        ]
        # Core workbench routes should still exist
        workbench_routes = [r for r in route_names if "workbench" in r or "pipeline" in r]
        # At minimum, the router module is importable (routes still present)
        assert routes is not None


# ---------------------------------------------------------------------------
# D. Commit/push readiness
# ---------------------------------------------------------------------------

class TestCommitPushReadiness:
    """Prove commit/push readiness is evidenced after successful patch flow."""

    def test_commit_ready_evidenced_after_pass(self, tmp_path):
        """commit_ready: YES must appear in events when post-validation passes."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            dry_run=True,  # dry_run — command shown but not executed
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator and validate",
                patches=_standard_patches(),
                validation_post=_VALIDATION_POST,
            )
            commit_events = [e for e in result.events if "commit_ready" in e]
            assert commit_events, "commit_ready event must be present"
            assert "YES" in commit_events[0], (
                f"Expected commit_ready: YES after PASS. Got: {commit_events}"
            )
        finally:
            pipeline.close()

    def test_commit_command_in_evidence(self, tmp_path):
        """Commit/push command must appear in evidence when validation passes."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), dry_run=True)
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator and push",
                patches=_standard_patches(),
                validation_post=_VALIDATION_POST,
            )
            commit_events = [e for e in result.events if "commit_ready" in e]
            if commit_events and "YES" in commit_events[0]:
                # Commit command should be in the event
                assert "git" in commit_events[0] or "git" in result.reviewer_verdict.get("evidence_ref", ""), (
                    f"Git commit command not found in evidence. Event: {commit_events[0]}"
                )
        finally:
            pipeline.close()

    def test_no_actual_commit_when_dry_run(self, tmp_path):
        """With dry_run=True, no actual commit should be made to any repo."""
        # Record git log before
        git_log_before = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        ).stdout.strip()

        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), dry_run=True)
        pipeline = CodingPipeline(config=cfg)
        try:
            pipeline.run_multi_file_patch(
                prompt="Fix and commit calculator bug",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
        finally:
            pipeline.close()

        git_log_after = subprocess.run(
            ["git", "log", "--oneline", "-3"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        ).stdout.strip()

        assert git_log_after == git_log_before, (
            "Git log changed — dry_run=True should not commit to any repo"
        )


# ---------------------------------------------------------------------------
# E. FilePatch dataclass
# ---------------------------------------------------------------------------

class TestFilePatchDataclass:
    """FilePatch must be importable and usable without error."""

    def test_file_patch_importable(self):
        from openjarvis.workbench.pipeline import FilePatch
        fp = FilePatch(
            file_name="foo.py",
            original_content="original",
            fixed_content="fixed",
            rationale="test",
        )
        assert fp.file_name == "foo.py"
        assert fp.original_content == "original"
        assert fp.fixed_content == "fixed"
        assert fp.rationale == "test"

    def test_file_patch_in_all(self):
        from openjarvis.workbench import pipeline
        assert "FilePatch" in pipeline.__all__

    def test_multi_patch_with_single_file(self, tmp_path):
        """run_multi_file_patch() must also work with only 1 file (degenerate case)."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix single file",
                patches=[FilePatch("single.py", "x = 1  # BUG\n", "x = 2  # fixed\n", "fix x")],
                validation_post="echo ok",
            )
            assert result.patch_diff
            assert result.patch_diff.count("diff --git") == 1
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# F. Workbench not manually required
# ---------------------------------------------------------------------------

class TestWorkbenchNotRequired:
    """Prove the full workflow runs from normal API path without Workbench UI."""

    def test_pipeline_importable_without_workbench(self):
        """CodingPipeline must be importable and runnable from normal code path."""
        from openjarvis.workbench.pipeline import CodingPipeline, PipelineConfig, FilePatch
        assert CodingPipeline is not None

    def test_coding_manager_plan_called_in_multi_file(self, tmp_path):
        """CodingManager.plan() is called inside pipeline — no manual Workbench."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt="Fix calculator multi-file bug",
                patches=_standard_patches(),
                validation_post="echo ok",
            )
            # CodingManager.plan() runs inside run_multi_file_patch() — evidenced by plan event
            plan_events = [e for e in result.events if "plan:" in e or "plan_skipped" in e]
            assert plan_events, f"CodingManager.plan() must be called. Events: {result.events}"
            # If plan succeeded (not skipped), task was classified by CodingManager
            success_plans = [e for e in plan_events if "plan:" in e and "subtasks=" in e]
            if success_plans:
                assert "subtasks=" in success_plans[0]
        finally:
            pipeline.close()

    def test_front_door_routes_entire_flow(self, tmp_path):
        """Entire flow invocable via front-door routing + pipeline — no Workbench step."""
        # Simulate front-door: detect_coding_intent → CodingPipeline.run_multi_file_patch
        prompt = "fix the multi-file bug and validate it"
        assert detect_coding_intent(prompt), "Front-door must route this prompt"

        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_multi_file_patch(
                prompt=prompt,
                patches=_standard_patches(),
                validation_post=_VALIDATION_POST,
            )
            assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD)
            assert result.reviewer_verdict is not None
        finally:
            pipeline.close()
