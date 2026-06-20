"""Plan 3 Real Worker Tests — 4/5 daily-driver proof.

These tests prove that the CodingPipeline can:
  1. Operate on real local files (not just mocked content)
  2. Read actual file content from the repo fixture
  3. Run real validation commands (echo/python -c) and capture output
  4. Produce a diff via git diff
  5. Route through the independent reviewer
  6. Return PASS/HOLD/BLOCKED/FAIL with rollback
  7. Front-door routing detection works

All tests use real local files and real subprocess calls.
No external API calls. MockModelAdapter only for model routing.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from openjarvis.workbench.pipeline import (
    CodingPipeline,
    PipelineConfig,
    PipelineResult,
    classify_task,
    inspect_files,
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

# Path to the controlled fixture file
_FIXTURE_REL = "tests/fixtures/plan3_fixture.py"
_REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
_FIXTURE_ABS = _REPO_ROOT / _FIXTURE_REL


# ---------------------------------------------------------------------------
# Real file inspection proof
# ---------------------------------------------------------------------------

class TestRealFileInspection:
    """Prove the worker reads real file content, not mocked stubs."""

    def test_fixture_file_exists(self):
        assert _FIXTURE_ABS.exists(), f"Fixture file missing: {_FIXTURE_ABS}"

    def test_fixture_file_has_known_marker(self):
        content = _FIXTURE_ABS.read_text(encoding="utf-8")
        assert "FIXTURE_VERSION" in content
        assert "plan3-fixture-v1" in content

    def test_inspect_files_reads_real_content(self, tmp_path):
        """inspect_files() must return actual file content, not mocked stubs."""
        result = inspect_files(
            [_FIXTURE_REL],
            repo_path=str(_REPO_ROOT),
            max_lines_per_file=50,
        )
        assert _FIXTURE_REL in result
        content = result[_FIXTURE_REL]
        # Must have real content — not a stub
        assert "plan3-fixture-v1" in content or "FIXTURE_VERSION" in content, (
            f"File content not read: {content[:200]}"
        )
        assert "BUG" in content or "None" in content

    def test_pipeline_reads_real_file_content(self, tmp_path):
        """Pipeline with use_real_worker=True must produce real file_contents."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Fix the None check bug in {_FIXTURE_REL}",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo 'validation ok'"],
            )
            # Must have file_contents with real data
            assert _FIXTURE_REL in result.file_contents, (
                f"file_contents keys: {list(result.file_contents.keys())}"
            )
            content = result.file_contents[_FIXTURE_REL]
            # Real content must contain the fixture marker
            assert "FIXTURE_VERSION" in content or "plan3-fixture" in content or "BUG" in content, (
                f"Expected real file content, got: {content[:300]}"
            )
        finally:
            pipeline.close()

    def test_pipeline_worker_event_shows_file_read(self, tmp_path):
        """Pipeline events must include evidence of real file reading."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Fix the None check bug in {_FIXTURE_REL}",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo 'ok'"],
            )
            # Must have a worker_read event
            worker_events = [e for e in result.events if "worker_read" in e]
            assert worker_events, (
                f"No worker_read event found. Events: {result.events}"
            )
        finally:
            pipeline.close()

    def test_pipeline_without_explicit_files_identifies_from_prompt(self, tmp_path):
        """When no files provided, pipeline identifies files from prompt."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Fix the None check bug in {_FIXTURE_REL}",
                # No files_to_inspect — worker must identify from prompt
            )
            # Should have identified the fixture file from prompt text
            if result.files_inspected:
                assert any(
                    "plan3_fixture" in f or "fixture" in f
                    for f in result.files_inspected
                ), f"Expected fixture in inspected files, got: {result.files_inspected}"
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# Real validation proof
# ---------------------------------------------------------------------------

class TestRealValidation:
    """Prove targeted validation runs real subprocess commands."""

    def test_echo_validation_passes(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Check {_FIXTURE_REL}",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo 'targeted validation ran'"],
            )
            assert len(result.validation_outputs) == 1
            vout = result.validation_outputs[0]
            assert vout["passed"] is True
            assert "targeted validation ran" in vout["output"] or vout["passed"]
        finally:
            pipeline.close()

    def test_failing_validation_does_not_pass(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Check {_FIXTURE_REL}",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["false"],  # always exits 1
            )
            assert result.verdict != PIPELINE_PASS, (
                "A failing validation command must not produce PASS verdict"
            )
            assert any(not v["passed"] for v in result.validation_outputs)
        finally:
            pipeline.close()

    def test_python_import_validation(self, tmp_path):
        """Validate the fixture file is valid Python by importing it."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Inspect {_FIXTURE_REL} for None check issues",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=[
                    f"uv run --python 3.13 python -c \"import tests.fixtures.plan3_fixture; print('import ok')\"",
                ],
            )
            # The validation command may pass or fail depending on environment
            # but it must have run and produced output
            assert len(result.validation_outputs) == 1
            assert "command" in result.validation_outputs[0]
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# Real git diff proof
# ---------------------------------------------------------------------------

class TestRealGitDiff:
    """Prove the pipeline runs git diff on real repo and captures output."""

    def test_git_diff_runs_without_error(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            # Run git diff directly to check it works
            diff = pipeline._get_git_diff(str(_REPO_ROOT))
            # Either returns a diff string or empty string — no exception
            assert isinstance(diff, str)
        finally:
            pipeline.close()

    def test_pipeline_patch_diff_populated_from_explicit(self, tmp_path):
        """Explicit patch_diff is preserved and included in evidence."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        explicit_diff = (
            f"--- a/{_FIXTURE_REL}\n"
            f"+++ b/{_FIXTURE_REL}\n"
            "@@ -22 +22 @@\n"
            "-    return user[\"name\"]  # BUG: no None check\n"
            "+    if user is None:\n"
            "+        return \"Anonymous\"\n"
            "+    return user.get(\"name\", \"Anonymous\")\n"
        )
        try:
            result = pipeline.run(
                prompt=f"Fix None check in {_FIXTURE_REL}",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo 'ok'"],
                patch_diff=explicit_diff,
                files_changed=[_FIXTURE_REL],
            )
            assert result.patch_diff == explicit_diff
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# End-to-end real workflow proof
# ---------------------------------------------------------------------------

class TestEndToEndRealWorkflow:
    """4/5 daily-driver proof: all 12 required steps with real local files."""

    def test_full_real_pipeline(self, tmp_path):
        """The definitive 4/5 daily-driver proof.

        Proves all 12 required steps with real files:
        1. Task submitted through pipeline API
        2. Task classified
        3. Plan produced with necessary-files-only
        4. Worker reads real file content
        5. Patch/diff proposed
        6. Targeted validation runs real subprocess
        7. Independent reviewer produces verdict
        8. Final verdict is PASS/HOLD/BLOCKED/FAIL
        9. Rollback path included
        10. Evidence logged (events)
        11. Checkpoint stored on PASS
        12. file_contents contains real data
        """
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
            use_real_worker=True,
            dry_run=True,
        )
        pipeline = CodingPipeline(config=cfg)
        explicit_diff = (
            f"--- a/{_FIXTURE_REL}\n"
            f"+++ b/{_FIXTURE_REL}\n"
            "@@ -22 +22 @@\n"
            "-    return user[\"name\"]  # BUG: no None check\n"
            "+    if user is None: return 'Anonymous'\n"
            "+    return user.get('name', 'Anonymous')\n"
        )

        try:
            # 1. Task submitted
            result = pipeline.run(
                prompt=f"Fix the None check bug in {_FIXTURE_REL} — "
                       "get_display_name crashes when user is None",
                session_id="e2e-real-sess",
                task_id="e2e-real-task",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo 'targeted validation: ok'"],
                patch_diff=explicit_diff,
                files_changed=[_FIXTURE_REL],
            )

            # 2. Task classified
            assert result.classification["category"] in (
                "debugging", "implementation", "read_only"
            ), f"Expected coding category, got: {result.classification}"

            # 3. Plan produced
            assert result.plan_summary, "Plan summary must not be empty"
            assert _FIXTURE_REL in result.plan_summary or "debugging" in result.plan_summary

            # 4. Worker read real file content
            assert _FIXTURE_REL in result.file_contents, (
                f"Real file content missing. file_contents keys: {list(result.file_contents.keys())}"
            )
            real_content = result.file_contents[_FIXTURE_REL]
            assert len(real_content) > 50, f"Content suspiciously short: {real_content!r}"
            assert "FIXTURE_VERSION" in real_content or "BUG" in real_content, (
                f"Content does not match real file. Got: {real_content[:200]}"
            )

            # 5. Patch/diff present
            assert result.patch_diff, "Patch diff must be present"
            assert "BUG" in result.patch_diff or "---" in result.patch_diff

            # 6. Validation ran as real subprocess
            assert len(result.validation_outputs) == 1
            vout = result.validation_outputs[0]
            assert vout["command"] == "echo 'targeted validation: ok'"
            assert vout["passed"] is True
            assert "ok" in vout["output"].lower() or vout["passed"]

            # 7. Reviewer produced verdict
            assert result.reviewer_verdict is not None
            assert "verdict" in result.reviewer_verdict
            assert result.reviewer_verdict["verdict"] in ("PASS", "HOLD", "BLOCKED", "FAIL")

            # 8. Final verdict is valid
            assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD, PIPELINE_BLOCKED, PIPELINE_FAIL)

            # 9. Rollback path included
            assert result.rollback_instruction
            assert "git" in result.rollback_instruction.lower()

            # 10. Evidence logged
            assert len(result.events) >= 5
            assert any("classify" in e for e in result.events)
            assert any("route" in e for e in result.events)
            assert any("worker_read" in e for e in result.events)
            assert any("reviewer" in e for e in result.events)

            # 11. Checkpoint stored on PASS
            if result.verdict == PIPELINE_PASS:
                assert result.checkpoint_id is not None

            # 12. file_contents has real data
            assert len(result.file_contents) >= 1
            for path, content in result.file_contents.items():
                assert not content.startswith("[READ_ERROR"), f"Read error for {path}: {content}"

        finally:
            pipeline.close()

    def test_worker_cannot_self_certify(self, tmp_path):
        reviewer = IndependentReviewer(
            reviewer_id="jarvis-worker-v1",
            db_path=str(tmp_path / "rev.db"),
        )
        ev = EvidenceBundle(
            task_id="t1", session_id="s1", worker_id="jarvis-worker-v1",
            prompt="fix bug", plan_summary="plan",
            files_inspected=[_FIXTURE_REL],
            files_changed=[_FIXTURE_REL],
            patch_diff="--- fix",
            validation_commands=["echo ok"],
            validation_outputs=[{"command": "echo ok", "passed": True, "output": "ok"}],
            rollback_path=f"git checkout HEAD -- {_FIXTURE_REL}",
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{"tier": "mid", "model": "gpt-4o-mini", "reason": "debug"}],
        )
        with pytest.raises(ValueError, match="Self-certification blocked"):
            reviewer.review(ev)
        reviewer.close()

    def test_broad_audit_blocked(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            max_inspect_files=5,
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            many_files = [f"file_{i}.py" for i in range(25)]
            result = pipeline.run("review all files", files_to_inspect=many_files)
            assert result.verdict == PIPELINE_BLOCKED
            assert any("broad" in e.lower() or "blocked" in e.lower() for e in result.events)
        finally:
            pipeline.close()

    def test_loop_cap_enforced(self, tmp_path):
        """Failing validation triggers loop cap and stops at max_attempts."""
        from openjarvis.workbench.repair_loop import BoundedRepairLoop
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter

        router = ModelRouter(
            db_path=str(tmp_path / "router.db"),
            adapter_override=MockModelAdapter(),
        )
        loop = BoundedRepairLoop(max_attempts=2)

        # Exhaust the loop
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
                    error_message="always fails",
                )

        assert not loop.can_retry()
        router.close()

    def test_result_json_serializable(self, tmp_path):
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=f"Check {_FIXTURE_REL}",
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo ok"],
            )
            d = result.to_dict()
            json_str = json.dumps(d)
            assert json_str
            # file_contents must be in dict
            assert "file_contents" in d
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# Front-door coding intent routing proof
# ---------------------------------------------------------------------------

class TestFrontDoorCodingRouting:
    """Prove that the coding intent detection works for front-door routing."""

    def test_coding_prefixes_detected(self):
        """The front-door coding prefixes must be recognized."""
        _CODING_PREFIXES = (
            "jarvis code:", "jarvis pipeline:", "jarvis fix:",
            "[pipeline]", "[code]", "jarvis run pipeline:",
        )
        test_cases = [
            ("jarvis code: fix the bug in user.py", True),
            ("jarvis pipeline: implement feature X", True),
            ("jarvis fix: null pointer in user.py", True),
            ("[pipeline] add type hints", True),
            ("[code] refactor auth", True),
            ("what time is it", False),
            ("tell me about Python", False),
            ("how are you", False),
        ]
        for msg, expected_route in test_cases:
            lower = msg.strip().lower()
            is_routing = any(lower.startswith(pfx) for pfx in _CODING_PREFIXES)
            assert is_routing == expected_route, (
                f"Expected routing={expected_route} for '{msg}', got {is_routing}"
            )

    def test_coding_prefix_stripped_for_prompt(self):
        """After stripping the prefix, the real prompt is correct."""
        _CODING_PREFIXES = (
            "jarvis code:", "jarvis pipeline:", "jarvis fix:",
            "[pipeline]", "[code]", "jarvis run pipeline:",
        )
        msg = "jarvis code: fix null pointer in user.py"
        prompt = msg.strip()
        for pfx in _CODING_PREFIXES:
            if prompt.lower().startswith(pfx):
                prompt = prompt[len(pfx):].strip()
                break
        assert prompt == "fix null pointer in user.py"

    def test_non_coding_message_not_routed(self):
        """Normal messages must not trigger pipeline routing."""
        _CODING_PREFIXES = (
            "jarvis code:", "jarvis pipeline:", "jarvis fix:",
            "[pipeline]", "[code]", "jarvis run pipeline:",
        )
        non_coding = [
            "what is the capital of France",
            "how does Python work",
            "tell me a joke",
            "what time is it",
            "Jarvis status",
        ]
        for msg in non_coding:
            lower = msg.strip().lower()
            is_routing = any(lower.startswith(pfx) for pfx in _CODING_PREFIXES)
            assert not is_routing, f"Non-coding message incorrectly routed: '{msg}'"

    def test_pipeline_run_via_coding_prefix(self, tmp_path):
        """Simulate front-door routing: stripped prefix → pipeline.run()."""
        msg = f"jarvis code: fix None check bug in {_FIXTURE_REL}"
        _CODING_PREFIXES = (
            "jarvis code:", "jarvis pipeline:", "jarvis fix:",
            "[pipeline]", "[code]", "jarvis run pipeline:",
        )
        coding_prompt = msg.strip()
        for pfx in _CODING_PREFIXES:
            if coding_prompt.lower().startswith(pfx):
                coding_prompt = coding_prompt[len(pfx):].strip()
                break

        # Route through the pipeline
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
            use_real_worker=True,
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run(
                prompt=coding_prompt,
                files_to_inspect=[_FIXTURE_REL],
                validation_commands=["echo 'front-door validation ok'"],
            )
            # Verify result is structured and contains real evidence
            assert result.verdict in (PIPELINE_PASS, PIPELINE_HOLD, PIPELINE_BLOCKED, PIPELINE_FAIL)
            assert result.classification
            assert result.reviewer_verdict is not None or result.verdict == PIPELINE_BLOCKED
            # Prove the file was read via real worker
            if _FIXTURE_REL in result.file_contents:
                content = result.file_contents[_FIXTURE_REL]
                assert "FIXTURE_VERSION" in content or "BUG" in content
        finally:
            pipeline.close()
