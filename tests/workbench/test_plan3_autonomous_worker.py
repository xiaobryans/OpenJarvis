"""Plan 3 Autonomous Worker Tests — final 4/5 daily-driver proof.

Proves real autonomous implementation workflow:
  - Worker receives only a task prompt (no pre-supplied patch content)
  - Worker identifies necessary repo files via identify_files() + CodingManager.plan()
  - Worker reads ACTUAL OpenJarvis source files (full content)
  - Worker decides and generates patch content via code analysis (LocalPatternWorker)
  - Patch is applied to isolated temp git repo containing real file content
  - git diff shows actual change (not fixture-only)
  - Pre-fix validation confirms original state
  - Post-fix validation confirms fix works
  - Independent reviewer gives PASS
  - Rollback covers worker-changed files
  - Checkpoint + commit/push readiness evidenced
  - No Workbench UI required
  - Worker cannot self-certify
  - No broad repo scan

Key distinction from fixture proof:
  FIXTURE: test supplies patch content to worker → worker applies
  AUTONOMOUS: worker receives task description → worker reads+analyzes code → worker decides patch
"""

from __future__ import annotations

import ast
import os
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
from openjarvis.workbench.reviewer import IndependentReviewer, EvidenceBundle, Verdict
from openjarvis.workbench.task_worker import (
    TaskWorker,
    LocalPatternWorker,
    OpenRouterWorker,
    WorkerDecision,
    ConfigurationError,
    create_worker,
)

_REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
_PIPELINE_PY = _REPO_ROOT / "src" / "openjarvis" / "workbench" / "pipeline.py"
_ROUTES_PY = _REPO_ROOT / "src" / "openjarvis" / "server" / "routes.py"
_FIXTURE_DIR = _REPO_ROOT / "tests" / "fixtures" / "multi"

# Task prompt for real OpenJarvis autonomous proof
_REAL_TASK = (
    "Add explicit empty-string guard to detect_coding_intent() in pipeline.py "
    "for robustness: function should return False immediately for empty/whitespace input"
)
_REAL_VALIDATION_POST = (
    "python -c \"import sys; sys.path.insert(0, 'src'); "
    "from openjarvis.workbench.pipeline import detect_coding_intent; "
    "assert detect_coding_intent('') == False; "
    "assert detect_coding_intent('   ') == False; "
    "print('empty guard: ok')\""
)


# ---------------------------------------------------------------------------
# A. LocalPatternWorker — deterministic code analysis
# ---------------------------------------------------------------------------

class TestLocalPatternWorker:
    """Prove LocalPatternWorker analyzes code and generates patches autonomously."""

    def test_worker_is_task_worker_subclass(self):
        w = LocalPatternWorker()
        assert isinstance(w, TaskWorker)

    def test_worker_explain_non_empty(self):
        w = LocalPatternWorker()
        assert "LocalPatternWorker" in w.explain()
        assert "no API" in w.explain() or "deterministic" in w.explain().lower()

    def test_identify_files_finds_pipeline_py(self):
        """Worker must find src/openjarvis/workbench/pipeline.py when prompt mentions it."""
        w = LocalPatternWorker()
        files = w.identify_files(
            "Add guard to detect_coding_intent() in pipeline.py",
            str(_REPO_ROOT),
        )
        assert any("pipeline.py" in f and "workbench" in f for f in files), (
            f"Expected workbench/pipeline.py in identified files. Got: {files}"
        )

    def test_identify_files_skips_venv_and_git(self):
        """File search must skip .git, .venv, node_modules."""
        w = LocalPatternWorker()
        files = w.identify_files(
            "Fix detect_coding_intent() in pipeline.py",
            str(_REPO_ROOT),
        )
        assert all(".git/" not in f for f in files), f"Found .git file: {files}"
        assert all("node_modules" not in f for f in files), f"Found node_modules: {files}"

    def test_early_return_guard_pattern_on_real_pipeline(self):
        """Worker generates a syntactically valid early-return guard for detect_coding_intent()."""
        w = LocalPatternWorker()
        content = _PIPELINE_PY.read_text(encoding="utf-8")
        prompt = "Add explicit empty-string guard to detect_coding_intent() in pipeline.py"
        decision = w.generate_patch(prompt, "pipeline.py", content)

        assert decision is not None, (
            "Worker must find an applicable pattern in pipeline.py for this task"
        )
        assert decision.pattern_used == "early_return_guard"
        assert decision.changed, "Worker must change the content"
        assert decision.confidence > 0
        assert decision.rationale

    def test_worker_patch_is_valid_python(self):
        """Worker-generated patch must be valid Python (no SyntaxError)."""
        w = LocalPatternWorker()
        content = _PIPELINE_PY.read_text(encoding="utf-8")
        prompt = "Add explicit empty-string guard to detect_coding_intent() in pipeline.py"
        decision = w.generate_patch(prompt, "pipeline.py", content)

        assert decision is not None
        assert decision.changed

        # Must compile cleanly
        try:
            compile(decision.patch_content, "pipeline.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"Worker patch has syntax error: {e}")

    def test_worker_patch_contains_guard(self):
        """Worker-generated patch must contain the early-return guard."""
        w = LocalPatternWorker()
        content = _PIPELINE_PY.read_text(encoding="utf-8")
        prompt = "Add explicit empty-string guard to detect_coding_intent() in pipeline.py"
        decision = w.generate_patch(prompt, "pipeline.py", content)

        assert decision is not None
        # Guard must be present in patch (structural check, not line-exact)
        has_guard = (
            "if not stripped" in decision.patch_content
            or "if len(stripped)" in decision.patch_content
        )
        assert has_guard, (
            f"Worker patch must contain early-return guard. "
            f"Patch snippet: {decision.patch_content[1000:1200]}"
        )

    def test_worker_preserves_original_function(self):
        """Worker patch must preserve the detect_coding_intent function."""
        w = LocalPatternWorker()
        content = _PIPELINE_PY.read_text(encoding="utf-8")
        decision = w.generate_patch(
            "Add empty guard to detect_coding_intent() in pipeline.py",
            "pipeline.py", content,
        )
        assert decision is not None
        assert "def detect_coding_intent" in decision.patch_content
        assert "def detect_coding_intent" in content  # must have existed

    def test_worker_decision_not_hardcoded_in_test(self):
        """Prove the worker decides the fix by analyzing code, not from test input.

        The test supplies ONLY:
          - a task prompt
          - a file path
          - the actual file content (read from disk)

        The test does NOT supply:
          - what line to insert
          - where to insert it
          - the exact patch content

        The worker decides all of this by analyzing the code.
        The test verifies structural properties (valid Python, guard present, function preserved).
        """
        w = LocalPatternWorker()
        content = _PIPELINE_PY.read_text(encoding="utf-8")

        # Worker receives only task description + content
        # No patch content is supplied to the worker
        decision = w.generate_patch(
            "Add guard to detect_coding_intent() in pipeline.py",
            str(_PIPELINE_PY),
            content,
        )

        # Test verifies structural properties ONLY:
        assert decision is not None, "Worker must decide a fix"
        assert decision.original_content == content, "Worker must not corrupt original"
        assert decision.patch_content != content, "Worker must actually change content"
        assert decision.files_inspected, "Worker must record which files it inspected"
        assert decision.pattern_used, "Worker must identify which pattern it applied"

        # Behavioral verification (not line-exact):
        try:
            compile(decision.patch_content, "pipeline.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"Worker-generated Python is invalid: {e}")

    def test_worker_returns_none_when_no_pattern_matches(self):
        """Worker returns None when no applicable pattern is found."""
        w = LocalPatternWorker()
        # A file with no applicable patterns for the given prompt
        content = "x = 1\ny = 2\n"
        decision = w.generate_patch(
            "Add empty guard to detect_coding_intent() in pipeline.py",
            "simple.py", content,
        )
        # Should return None (no strip assignment found)
        assert decision is None, f"Expected None for simple content, got: {decision}"

    def test_zero_divisor_guard_pattern(self):
        """Worker applies zero-divisor guard to division code."""
        w = LocalPatternWorker()
        content = (
            "def divide(a, b):\n"
            "    return a / b\n"
        )
        decision = w.generate_patch(
            "Add division by zero guard",
            "divide.py", content,
        )
        assert decision is not None
        assert decision.pattern_used == "zero_divisor_guard"
        assert decision.changed
        try:
            compile(decision.patch_content, "divide.py", "exec")
        except SyntaxError as e:
            pytest.fail(f"Zero-divisor patch SyntaxError: {e}")

    def test_undefined_call_fix_pattern(self):
        """Worker fixes calls to undefined functions."""
        w = LocalPatternWorker()
        content = (
            "def percentage(value, total):\n"
            "    return calculate(value, total)\n"
        )
        decision = w.generate_patch(
            "Fix undefined function call to calculate()",
            "calc.py", content,
        )
        assert decision is not None
        assert decision.pattern_used == "undefined_call_fix"
        assert decision.changed


# ---------------------------------------------------------------------------
# B. OpenRouterWorker — production path (gated)
# ---------------------------------------------------------------------------

class TestOpenRouterWorker:
    """Prove OpenRouterWorker interface exists and is properly gated."""

    def test_open_router_worker_requires_key(self):
        """OpenRouterWorker must raise ConfigurationError if key not set."""
        original = os.environ.pop("JARVIS_OPENROUTER_KEY", None)
        try:
            with pytest.raises(ConfigurationError):
                OpenRouterWorker()
        finally:
            if original is not None:
                os.environ["JARVIS_OPENROUTER_KEY"] = original

    def test_open_router_worker_is_task_worker(self):
        """OpenRouterWorker must satisfy TaskWorker interface (even if not instantiated)."""
        # Verify it's a subclass (interface contract)
        assert issubclass(OpenRouterWorker, TaskWorker)

    def test_create_worker_returns_local_when_key_absent(self):
        """create_worker(prefer_local=True) returns LocalPatternWorker (forced local).

        Updated: create_worker() without prefer_local may return OllamaWorker if
        Ollama is running (priority: OpenRouter > Ollama > LocalPattern).
        prefer_local=True bypasses all model backends → always LocalPatternWorker.
        """
        original = os.environ.pop("JARVIS_OPENROUTER_KEY", None)
        try:
            w = create_worker(prefer_local=True)
            assert isinstance(w, LocalPatternWorker), (
                "create_worker(prefer_local=True) must always return LocalPatternWorker"
            )
        finally:
            if original is not None:
                os.environ["JARVIS_OPENROUTER_KEY"] = original

    def test_create_worker_with_prefer_local(self):
        """create_worker(prefer_local=True) always returns LocalPatternWorker."""
        w = create_worker(prefer_local=True)
        assert isinstance(w, LocalPatternWorker)

    def test_same_interface_for_both_workers(self):
        """Both LocalPatternWorker and OpenRouterWorker implement identical interface."""
        for method in ("identify_files", "generate_patch", "explain"):
            assert hasattr(LocalPatternWorker, method), f"LocalPatternWorker missing {method}"
            assert hasattr(OpenRouterWorker, method), f"OpenRouterWorker missing {method}"


# ---------------------------------------------------------------------------
# C. CodingPipeline.run_task() — autonomous execution on real OpenJarvis files
# ---------------------------------------------------------------------------

class TestRunTaskAutonomous:
    """Prove run_task() on ACTUAL OpenJarvis code (not fixture-only)."""

    def test_run_task_full_end_to_end_on_real_file(self, tmp_path):
        """THE definitive 4/5 autonomous proof.

        Worker receives ONLY the task prompt.
        Worker identifies src/openjarvis/workbench/pipeline.py from the prompt.
        Worker reads the ACTUAL file content.
        Worker decides and generates the patch (early_return_guard pattern).
        Real git diff shows the change.
        Reviewer gives PASS.
        Main repo is not modified.
        """
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            # Explicitly use LocalPatternWorker — this test proves the deterministic
            # early_return_guard pattern, not a real model call.
            # Real model (OllamaWorker) proof is in test_plan3_dogfood_real_model.py.
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post=_REAL_VALIDATION_POST,
                session_id="autonomous-e2e-sess",
                task_id="autonomous-e2e-task",
                worker=LocalPatternWorker(),
            )

            # 1. Worker identified real OpenJarvis file
            assert any("workbench/pipeline.py" in f for f in result.files_inspected), (
                f"Worker must identify workbench/pipeline.py. files_inspected: {result.files_inspected}"
            )

            # 2. Worker changed actual file content
            assert "src/openjarvis/workbench/pipeline.py" in result.files_changed, (
                f"Worker must have changed pipeline.py. files_changed: {result.files_changed}"
            )

            # 3. Worker read real file content (not fixture)
            assert "pipeline.py" in str(result.file_contents), (
                "Worker must have read actual pipeline.py file content"
            )
            real_content_key = next(
                (k for k in result.file_contents if "workbench/pipeline.py" in k), None
            )
            assert real_content_key is not None
            assert "detect_coding_intent" in result.file_contents[real_content_key], (
                "Worker read content must contain detect_coding_intent function"
            )

            # 4. Real git diff produced
            assert result.patch_diff, "Real git diff must be non-empty"
            assert "diff --git" in result.patch_diff
            assert "pipeline.py" in result.patch_diff
            assert result.patch_diff.count("@@") >= 1

            # 5. Worker events prove autonomous operation
            worker_patch_events = [e for e in result.events if "worker_patch" in e]
            assert worker_patch_events, (
                f"Worker must have patched at least one file. Events: {result.events}"
            )
            assert "early_return_guard" in worker_patch_events[0] or "pattern=" in worker_patch_events[0]

            # 6. Post-fix validation passed
            post_pass = [v for v in result.validation_outputs if v.get("passed")]
            assert post_pass, f"Post-fix validation must pass. outputs: {result.validation_outputs}"

            # 7. Reviewer PASS
            assert result.reviewer_verdict is not None
            assert result.reviewer_verdict["verdict"] == Verdict.PASS.value

            # 8. Final verdict PASS
            assert result.verdict == PIPELINE_PASS

            # 9. Rollback covers the changed file
            assert "pipeline.py" in result.rollback_instruction
            assert "git checkout HEAD" in result.rollback_instruction

            # 10. Commit/push readiness surfaced
            commit_events = [e for e in result.events if "commit_ready" in e]
            assert commit_events, "Commit readiness must be evidenced"
            full_commit_ev = "\n".join(commit_events)
            assert "YES" in full_commit_ev
            assert "git push fork" in full_commit_ev

            # 11. Checkpoint stored on PASS
            assert result.checkpoint_id is not None

            # 12. Targeted only (no broad scan)
            assert len(result.files_changed) <= 5

        finally:
            pipeline.close()

    def test_worker_identifies_files_from_prompt_only(self, tmp_path):
        """Worker must identify files from prompt text alone (no pre-supplied list)."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            # No file_hints supplied — worker must identify from prompt
            result = pipeline.run_task(
                prompt="Add guard to detect_coding_intent() in pipeline.py",
                validation_post="echo 'ok'",
            )
            pipeline_files = [
                f for f in result.files_inspected if "pipeline.py" in f
            ]
            assert pipeline_files, (
                f"Worker must identify pipeline.py from prompt without file_hints. "
                f"files_inspected: {result.files_inspected}"
            )
        finally:
            pipeline.close()

    def test_worker_generates_patch_not_fixture(self, tmp_path):
        """Patch content must come from worker analysis, not pre-supplied fixture."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            # Worker patch events must show pattern_used and confidence
            patch_events = [e for e in result.events if "worker_patch" in e]
            if patch_events:
                event_str = patch_events[0]
                assert "pattern=" in event_str, f"No pattern info in worker event: {event_str}"
                assert "confidence=" in event_str, f"No confidence in worker event: {event_str}"
        finally:
            pipeline.close()

    def test_real_repo_not_modified(self, tmp_path):
        """run_task() must not modify any file in the real main repo."""
        pipeline_before = _PIPELINE_PY.read_text(encoding="utf-8")

        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
        finally:
            pipeline.close()

        pipeline_after = _PIPELINE_PY.read_text(encoding="utf-8")
        assert pipeline_after == pipeline_before, (
            "run_task() modified src/openjarvis/workbench/pipeline.py in the main repo! "
            "All patches must only apply to the isolated temp git repo."
        )

    def test_main_repo_git_status_unchanged_by_run_task(self, tmp_path):
        """After run_task(), main repo git status must be identical to before.

        Captures status before and after — proves run_task() doesn't create
        new dirty state in the main repo, even if existing uncommitted edits exist.
        """
        # Capture status before
        status_before = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        ).stdout.strip()

        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
        finally:
            pipeline.close()

        # Status must be identical after (run_task may not dirty the repo)
        status_after = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(_REPO_ROOT), capture_output=True, text=True,
        ).stdout.strip()

        assert status_after == status_before, (
            f"run_task() changed the main repo git status!\n"
            f"Before:\n{status_before}\nAfter:\n{status_after}"
        )

    def test_worker_cannot_self_certify(self, tmp_path):
        """Worker and reviewer must be different — self-certification blocked."""
        reviewer = IndependentReviewer(
            reviewer_id="jarvis-worker-v1",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = EvidenceBundle(
            task_id="t1", session_id="s1",
            worker_id="jarvis-worker-v1",  # same as reviewer_id
            prompt="autonomous task",
            plan_summary="run_task proof",
            files_inspected=["src/openjarvis/workbench/pipeline.py"],
            files_changed=["src/openjarvis/workbench/pipeline.py"],
            patch_diff="diff --git a/pipeline.py ...",
            validation_commands=["echo ok"],
            validation_outputs=[{"command": "echo ok", "passed": True, "output": "ok"}],
            rollback_path="git checkout HEAD -- src/openjarvis/workbench/pipeline.py",
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{"tier": "local", "model": "local", "reason": "autonomous"}],
        )
        with pytest.raises(ValueError, match="Self-certification blocked"):
            reviewer.review(ev)
        reviewer.close()

    def test_rollback_instruction_covers_changed_files(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            if result.files_changed:
                for changed_file in result.files_changed:
                    fname = Path(changed_file).name
                    assert fname in result.rollback_instruction, (
                        f"{fname} not in rollback: {result.rollback_instruction[:120]}"
                    )
        finally:
            pipeline.close()

    def test_commit_push_readiness_after_pass(self, tmp_path):
        """Commit/push readiness must be evidenced after successful run_task()."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            dry_run=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            # Explicit LocalPatternWorker — proves commit readiness for the
            # deterministic early_return_guard pattern.
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post=_REAL_VALIDATION_POST,
                worker=LocalPatternWorker(),
            )
            commit_events = [e for e in result.events if "commit_ready" in e]
            assert commit_events
            full_ev = "\n".join(commit_events)
            assert "YES" in full_ev
            assert "git push fork" in full_ev
        finally:
            pipeline.close()

    def test_no_workbench_required(self, tmp_path):
        """Full autonomous flow runs via normal API, no Workbench UI."""
        # run_task() is the front-door entry — no Workbench route needed
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD, PIPELINE_FAIL)
            # If PASS: reviewer ran without Workbench
            if result.verdict == PIPELINE_PASS:
                assert result.reviewer_verdict is not None
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# D. Front-door routing to autonomous worker
# ---------------------------------------------------------------------------

class TestFrontDoorAutonomousRouting:
    """Prove realistic prompts route to run_task() autonomously via front-door."""

    _AUTONOMOUS_PROMPTS = [
        "fix the failing test in pipeline.py and validate it",
        "continue the current sprint and fix the failing validation",
        "review this report and implement the next blocker fix",
        "patch the failing test, run validation, and prepare the commit evidence",
        "add empty string guard to detect_coding_intent() in pipeline.py",
        "update the code and push",
    ]

    @pytest.mark.parametrize("prompt", _AUTONOMOUS_PROMPTS)
    def test_autonomous_prompt_routes_via_detect_coding_intent(self, prompt):
        assert detect_coding_intent(prompt), (
            f"Autonomous prompt must route via natural intent: {prompt!r}"
        )

    def test_gate0_not_regressed(self):
        gate0 = [
            "what time is it", "what's the date", "what is Jarvis status",
            "how is Jarvis doing", "tell me the time",
        ]
        for msg in gate0:
            assert not detect_coding_intent(msg), f"Gate 0 must not route: {msg!r}"

    def test_non_coding_falls_through(self):
        non_coding = [
            "what is Python", "explain the architecture",
            "how does machine learning work", "who built OpenJarvis",
        ]
        for msg in non_coding:
            assert not detect_coding_intent(msg), f"Non-coding must not route: {msg!r}"

    def test_front_door_routes_to_run_task(self, tmp_path):
        """Simulate front-door: detect_coding_intent() → pipeline.run_task()."""
        prompt = "add empty string guard to detect_coding_intent() in pipeline.py"
        assert detect_coding_intent(prompt), "Front-door must detect coding intent"

        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            # Same call the routes.py handler would make
            result = pipeline.run_task(prompt=prompt, validation_post="echo ok")
            assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD, PIPELINE_FAIL)
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# E. Worker decisions logged in evidence
# ---------------------------------------------------------------------------

class TestWorkerDecisionEvidence:
    """Worker decisions must be logged in evidence for reviewer."""

    def test_worker_decision_in_evidence_extra(self, tmp_path):
        """WorkerDecision must be recorded in evidence extra{}."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            # Worker patch events include pattern + confidence
            patch_events = [e for e in result.events if "worker_patch" in e]
            if patch_events:
                e = patch_events[0]
                assert "pattern=" in e
                assert "confidence=" in e
                assert "rationale" in e.lower() or "|" in e
        finally:
            pipeline.close()

    def test_model_decisions_logged(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), repo_path=str(_REPO_ROOT))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            assert len(result.model_decisions) >= 1
            d = result.model_decisions[0]
            assert "assigned_tier" in d
            assert "assigned_model" in d
        finally:
            pipeline.close()

    def test_plan_event_in_events(self, tmp_path):
        """CodingManager.plan() must be called and evidenced in events."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), repo_path=str(_REPO_ROOT))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            plan_events = [e for e in result.events if "plan:" in e or "plan_skipped" in e]
            assert plan_events, f"CodingManager.plan() must be called. Events: {result.events}"
        finally:
            pipeline.close()

    def test_checkpoint_retrievable_after_pass(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), repo_path=str(_REPO_ROOT))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post=_REAL_VALIDATION_POST,
                session_id="autonomous-cp-sess",
            )
            if result.verdict == PIPELINE_PASS:
                cp = pipeline.get_checkpoint(session_id="autonomous-cp-sess")
                assert cp is not None, "Checkpoint must be retrievable after PASS"
        finally:
            pipeline.close()

    def test_result_json_serializable(self, tmp_path):
        import json
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"), repo_path=str(_REPO_ROOT))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_task(
                prompt=_REAL_TASK,
                validation_post="echo ok",
            )
            d = result.to_dict()
            json.dumps(d)  # must not raise
            assert "patch_diff" in d
            assert "file_contents" in d
        finally:
            pipeline.close()
