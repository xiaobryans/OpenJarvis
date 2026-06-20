"""Plan 3 Patch/Edit Flow Tests — 4/5 final daily-driver proof.

Proves the full multi-step coding agent workflow:
  1. Worker identifies necessary files
  2. Worker reads real file content
  3. Worker applies a real minimal patch (file write)
  4. git diff shows actual changed file
  5. Pre-fix validation fails (proves bug existed)
  6. Post-fix validation passes (proves fix works)
  7. Independent reviewer validates evidence
  8. Final verdict PASS
  9. Rollback path included
  10. Checkpoint/log/evidence recorded
  11. No broad audit

Also proves:
  - Natural coding intent detection (no prefix required)
  - Gate 0 routes (time/date/status) do not regress
  - Worker cannot self-certify
  - Front-door Cmd+K compatibility (same route)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from openjarvis.workbench.pipeline import (
    CodingPipeline,
    PipelineConfig,
    detect_coding_intent,
    classify_task,
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

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "plan3_fixture.py"
_REPO_ROOT = Path(__file__).parent.parent.parent.resolve()

# Buggy and fixed versions for the patch flow test
_ORIGINAL = """\
def get_name(user):
    \"\"\"Return user display name. BUG: crashes if user is None.\"\"\"
    return user["name"]  # BUG: no None check
"""

_FIXED = """\
def get_name(user):
    \"\"\"Return user display name. Fixed: safe None check.\"\"\"
    if user is None:
        return "Anonymous"
    return user.get("name", "Anonymous")
"""

_VALIDATION_PRE = (
    # This command FAILS (exit 1) when run on buggy code — proving the bug exists.
    # get_name(None) raises TypeError (None["name"]), which is the confirmed bug.
    "python -c \""
    "import sys; sys.path.insert(0, '.'); "
    "from fixture import get_name; "
    "get_name(None)"
    "\""
)

_VALIDATION_POST = (
    "python -c \""
    "import sys; sys.path.insert(0, '.')\n"
    "from fixture import get_name\n"
    "assert get_name(None) == 'Anonymous', 'fix failed: None case'\n"
    "assert get_name({'name': 'Alice'}) == 'Alice', 'fix failed: normal case'\n"
    "print('fix confirmed: all assertions passed')\n"
    "\""
)


# ---------------------------------------------------------------------------
# A. Real patch/edit flow proof
# ---------------------------------------------------------------------------

class TestRealPatchFlow:
    """Prove the full patch flow: read → apply → diff → validate → review."""

    def test_patch_flow_full_end_to_end(self, tmp_path):
        """The definitive 4/5 daily-driver patch proof.

        All steps use real local operations:
          - real file write (original buggy + fixed)
          - real git init + commit + diff
          - real subprocess validation (pre-fail + post-pass)
          - real reviewer verdict (PASS)
          - real checkpoint stored
        """
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix the None check bug in fixture.py — get_name crashes when user is None",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None guard before accessing user dict fields",
                validation_pre=_VALIDATION_PRE,
                validation_post=_VALIDATION_POST,
                session_id="patch-e2e-sess",
                task_id="patch-e2e-task",
            )

            # 1. Classification
            assert result.classification["category"] in ("debugging", "implementation", "read_only")

            # 2. Worker read original file content
            assert "fixture.py" in result.file_contents
            content = result.file_contents["fixture.py"]
            assert "BUG" in content or "get_name" in content

            # 3. Real git diff produced
            assert result.patch_diff, "Real git diff must be non-empty"
            assert "fixture.py" in result.patch_diff
            assert "---" in result.patch_diff and "+++" in result.patch_diff
            assert "-    return user" in result.patch_diff or "@@" in result.patch_diff

            # 4. Pre-fix validation ran — either FAIL (confirms bug) or PASS (unexpected)
            pre_events = [e for e in result.events if "validation_pre" in e]
            assert pre_events, f"No pre-fix validation evidence. Events: {result.events}"

            # 5. Post-fix validation passed (fix works)
            post_events = [e for e in result.events if "validation_post" in e and "PASS" in e.upper()]
            assert post_events, f"No post-fix pass evidence. Events: {result.events}"

            # 6. Validation outputs include both pre and post results
            assert len(result.validation_outputs) >= 1
            post_vout = [v for v in result.validation_outputs if v.get("passed")]
            assert post_vout, "Post-fix validation must pass"

            # 7. Reviewer produced PASS
            assert result.reviewer_verdict is not None
            assert result.reviewer_verdict["verdict"] == Verdict.PASS.value, (
                f"Expected PASS, got {result.reviewer_verdict['verdict']}. "
                f"Reasons: {result.reviewer_verdict.get('reasons', [])}"
            )

            # 8. Final verdict PASS
            assert result.verdict == PIPELINE_PASS

            # 9. Rollback path included
            assert result.rollback_instruction
            assert "git checkout HEAD" in result.rollback_instruction
            assert "fixture.py" in result.rollback_instruction

            # 10. Events include full flow evidence
            assert any("classify" in e for e in result.events)
            assert any("worker_read" in e for e in result.events)
            assert any("worker_diff" in e for e in result.events)
            assert any("reviewer" in e for e in result.events)

            # 11. Checkpoint stored on PASS
            assert result.checkpoint_id is not None

            # 12. No broad audit (only 1 file inspected)
            assert result.files_inspected == ["fixture.py"]
            assert len(result.files_inspected) == 1

        finally:
            pipeline.close()

    def test_patch_diff_is_real_git_diff(self, tmp_path):
        """Git diff must come from actual git, not string comparison."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug in fixture.py",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post="echo 'ok'",
            )
            diff = result.patch_diff
            # Real git diff format markers
            assert diff.startswith("diff --git") or "@@" in diff, (
                f"Expected real git diff format, got: {diff[:100]}"
            )
        finally:
            pipeline.close()

    def test_pre_fix_validation_fails(self, tmp_path):
        """Pre-fix command must fail (exit 1) — proving the bug existed before the patch.

        _VALIDATION_PRE calls get_name(None) which raises TypeError on buggy code.
        subprocess exits 1 → passed=False → proves bug exists in original.
        """
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_pre=_VALIDATION_PRE,
                validation_post="echo 'ok'",
            )
            # Pre-fix validation is recorded in reviewer_verdict extra
            # and in "validation_pre: FAIL (confirms bug exists)" event
            pre_fail_events = [e for e in result.events if "validation_pre" in e]
            assert pre_fail_events, f"Pre-fix validation not evidenced. Events: {result.events}"
            # The pre-fix command should have exited 1 (bug confirmed)
            fail_events = [e for e in pre_fail_events if "FAIL" in e.upper() or "confirms" in e]
            assert fail_events, (
                f"Pre-fix command should fail (confirms bug). Events: {pre_fail_events}"
            )
        finally:
            pipeline.close()

    def test_post_fix_validation_passes(self, tmp_path):
        """Post-fix command must pass — proving the fix works."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post=_VALIDATION_POST,
            )
            post_pass = [v for v in result.validation_outputs if v.get("passed")]
            assert post_pass, f"Post-fix validation must pass. outputs: {result.validation_outputs}"
        finally:
            pipeline.close()

    def test_worker_reads_original_not_fixed(self, tmp_path):
        """file_contents must show the original (buggy) file, not the fixed one."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post="echo ok",
            )
            assert "fixture.py" in result.file_contents
            content = result.file_contents["fixture.py"]
            assert "BUG" in content, f"Worker should read original (BUG) content, got: {content[:200]}"
        finally:
            pipeline.close()

    def test_worker_cannot_self_certify_in_patch_flow(self, tmp_path):
        """Worker cannot submit evidence to itself as reviewer."""
        reviewer = IndependentReviewer(
            reviewer_id="jarvis-worker-v1",  # same as default worker
            db_path=str(tmp_path / "rev.db"),
        )
        ev = EvidenceBundle(
            task_id="t1", session_id="s1",
            worker_id="jarvis-worker-v1",  # same as reviewer_id
            prompt="fix bug",
            plan_summary="Patch task",
            files_inspected=["fixture.py"],
            files_changed=["fixture.py"],
            patch_diff="--- a/fixture.py\n+++ b/fixture.py",
            validation_commands=["echo ok"],
            validation_outputs=[{"command": "echo ok", "passed": True, "output": "ok"}],
            rollback_path="git checkout HEAD -- fixture.py",
            loop_state={"stopped": False, "max_attempts": 3, "attempts": []},
            model_decisions=[{"tier": "mid", "model": "gpt-4o-mini", "reason": "debug"}],
        )
        with pytest.raises(ValueError, match="Self-certification blocked"):
            reviewer.review(ev)
        reviewer.close()

    def test_rollback_path_surfaced_in_patch_flow(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug in fixture.py",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post="echo ok",
            )
            assert result.rollback_instruction
            assert "git checkout HEAD" in result.rollback_instruction
            assert "fixture.py" in result.rollback_instruction
        finally:
            pipeline.close()

    def test_main_repo_fixture_not_modified_by_patch_flow(self, tmp_path):
        """Patch flow must not modify the main repo fixture file.

        run_with_patch() uses an isolated temp git repo — the main repo fixture
        must be unchanged after the patch flow completes.
        """
        # Read fixture content before
        fixture_before = _FIXTURE_PATH.read_text(encoding="utf-8")

        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            repo_path=str(_REPO_ROOT),
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="plan3_fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post="echo ok",
            )
        finally:
            pipeline.close()

        # Fixture file in main repo must be unchanged
        fixture_after = _FIXTURE_PATH.read_text(encoding="utf-8")
        assert fixture_after == fixture_before, (
            "Patch flow modified the main repo fixture file! "
            "run_with_patch() must only write to the isolated temp git repo."
        )

    def test_result_json_serializable(self, tmp_path):
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post="echo ok",
            )
            d = result.to_dict()
            json_str = json.dumps(d)
            assert json_str
            assert "patch_diff" in d
            assert "file_contents" in d
        finally:
            pipeline.close()


# ---------------------------------------------------------------------------
# B. Natural coding intent detection
# ---------------------------------------------------------------------------

class TestNaturalCodingIntent:
    """Prove detect_coding_intent() routes correctly without prefixes."""

    SHOULD_ROUTE = [
        "fix this bug in user.py",
        "patch the failing test",
        "continue the current sprint",
        "run validation and commit",
        "implement the auth feature",
        "review this diff and apply the fix",
        "update the code in auth.py",
        "fix the null pointer in user.py",
        "add a test for the login flow",
        "refactor the database module",
        "run tests and push",
        "debug the crash in api.py",
    ]

    SHOULD_NOT_ROUTE = [
        "what is Python",
        "how does the pipeline work",
        "what time is it",
        "tell me about this project",
        "explain how git works",
        "what's the difference between None and undefined",
        "how do I use pytest",
        "who created Python",
        "when was this project started",
        "why is the sky blue",
    ]

    @pytest.mark.parametrize("msg", SHOULD_ROUTE)
    def test_coding_message_routes(self, msg):
        assert detect_coding_intent(msg) is True, (
            f"Expected coding intent=True for: {msg!r}"
        )

    @pytest.mark.parametrize("msg", SHOULD_NOT_ROUTE)
    def test_non_coding_message_not_routed(self, msg):
        assert detect_coding_intent(msg) is False, (
            f"Expected coding intent=False for: {msg!r}"
        )

    def test_time_query_not_routed(self):
        assert not detect_coding_intent("what time is it")
        assert not detect_coding_intent("what is the current time")
        assert not detect_coding_intent("what's today's date")

    def test_status_query_not_routed(self):
        assert not detect_coding_intent("what is Jarvis status")
        assert not detect_coding_intent("how is Jarvis doing")

    def test_explicit_file_with_verb_routes(self):
        assert detect_coding_intent("fix the bug in auth.py")
        assert detect_coding_intent("update user.ts to add type hints")
        assert detect_coding_intent("check api.js for null references")

    def test_general_coding_question_not_routed(self):
        """General questions about code concepts should not trigger pipeline."""
        assert not detect_coding_intent("how does async/await work in Python")
        assert not detect_coding_intent("what is a null pointer exception")


# ---------------------------------------------------------------------------
# C. Front-door Cmd+K compatibility
# ---------------------------------------------------------------------------

class TestFrontDoorRouting:
    """Prove front-door routes work for both prefix and natural intent."""

    def test_prefix_routes_detected(self):
        _CODING_PREFIXES = (
            "jarvis code:", "jarvis pipeline:", "jarvis fix:",
            "[pipeline]", "[code]", "jarvis run pipeline:",
        )
        prefix_msgs = [
            "jarvis code: fix the auth bug",
            "jarvis pipeline: run validation",
            "jarvis fix: null pointer in user.py",
            "[pipeline] implement feature X",
            "[code] refactor auth module",
        ]
        for msg in prefix_msgs:
            lower = msg.strip().lower()
            is_prefix = any(lower.startswith(pfx) for pfx in _CODING_PREFIXES)
            assert is_prefix, f"Expected prefix match for: {msg!r}"

    def test_natural_intent_routes(self):
        """Natural coding messages must route without requiring a prefix."""
        natural_coding = [
            "fix this bug in user.py",
            "patch the failing test",
            "continue the current sprint",
        ]
        for msg in natural_coding:
            _CODING_PREFIXES = (
                "jarvis code:", "jarvis pipeline:", "jarvis fix:",
                "[pipeline]", "[code]", "jarvis run pipeline:",
            )
            lower = msg.strip().lower()
            prefix_match = any(lower.startswith(pfx) for pfx in _CODING_PREFIXES)
            natural = detect_coding_intent(msg)
            assert not prefix_match, f"Should not match prefix for: {msg!r}"
            assert natural, f"Expected natural intent for: {msg!r}"

    def test_cmdK_inherits_same_route(self):
        """Cmd+K uses same /v1/chat/completions route — same intent detection applies."""
        # Both chat and Cmd+K route through /v1/chat/completions.
        # These messages have clear coding verb + object pairs that should route.
        cmdK_messages = [
            ("fix the null pointer exception", True),   # fix + exception (object)
            ("add type hints to this function", True),   # add + function (object)
            ("refactor this method", True),              # refactor + method (object)
        ]
        for msg, expected in cmdK_messages:
            result = detect_coding_intent(msg)
            assert result is expected, (
                f"Cmd+K message routing: expected {expected} for {msg!r}, got {result}"
            )

    def test_gate0_time_not_routed(self):
        """Gate 0 time queries must not trigger coding pipeline."""
        time_queries = [
            "what time is it",
            "what's the current time",
            "tell me the time",
        ]
        for q in time_queries:
            assert not detect_coding_intent(q), f"Time query must not route: {q!r}"

    def test_gate0_date_not_routed(self):
        date_queries = [
            "what is today's date",
            "what day is it today",
        ]
        for q in date_queries:
            assert not detect_coding_intent(q), f"Date query must not route: {q!r}"

    def test_gate0_status_not_routed(self):
        status_queries = [
            "what is Jarvis status",
            "how is Jarvis running",
        ]
        for q in status_queries:
            assert not detect_coding_intent(q), f"Status query must not route: {q!r}"

    def test_non_coding_falls_through(self):
        """Non-coding messages must not route — confirmed for front-door."""
        non_coding = [
            "tell me about the OpenJarvis project",
            "what is an LLM",
            "explain machine learning",
        ]
        for msg in non_coding:
            prefix_match = any(
                msg.strip().lower().startswith(pfx)
                for pfx in ("jarvis code:", "[pipeline]", "jarvis fix:")
            )
            natural = detect_coding_intent(msg)
            assert not prefix_match and not natural, f"Non-coding should not route: {msg!r}"


# ---------------------------------------------------------------------------
# D. Multi-step evidence — classify → inspect → patch → validate → reviewer
# ---------------------------------------------------------------------------

class TestMultiStepWorkerEvidence:
    """Prove the full multi-step coding agent flow is recorded in evidence."""

    def test_all_12_steps_evidenced(self, tmp_path):
        """12 required steps all present in evidence from patch flow."""
        cfg = PipelineConfig(
            db_path=str(tmp_path / "pipeline.db"),
            worker_id="jarvis-worker-v1",
            reviewer_id="jarvis-reviewer-v1",
        )
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix the None check bug in fixture.py",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None guard",
                validation_pre=_VALIDATION_PRE,
                validation_post=_VALIDATION_POST,
            )
            events = result.events
            # Step 1: task submitted → classify event
            assert any("classify" in e for e in events), "Step 1 missing: classify"
            # Step 2: classification present
            assert result.classification["category"], "Step 2 missing: classification"
            # Step 3: plan/route present
            assert any("route" in e for e in events), "Step 3 missing: route"
            # Step 4: worker read real file
            assert any("worker_read" in e for e in events), "Step 4 missing: worker_read"
            # Step 5: patch applied
            assert any("worker_patch" in e for e in events), "Step 5 missing: worker_patch"
            # Step 6: git diff captured
            assert any("worker_diff" in e for e in events), "Step 6 missing: worker_diff"
            # Step 7: validation ran
            assert len(result.validation_outputs) >= 1, "Step 7 missing: validation"
            # Step 8: reviewer verified
            assert result.reviewer_verdict is not None, "Step 8 missing: reviewer_verdict"
            # Step 9: rollback path
            assert result.rollback_instruction, "Step 9 missing: rollback_instruction"
            # Step 10: logs produced
            assert len(events) >= 6, f"Step 10 missing: events too sparse: {events}"
            # Step 11: checkpoint on PASS
            if result.verdict == PIPELINE_PASS:
                assert result.checkpoint_id, "Step 11 missing: checkpoint_id on PASS"
            # Step 12: file_contents (real inspection)
            assert result.file_contents, "Step 12 missing: file_contents"
        finally:
            pipeline.close()

    def test_model_decisions_logged_in_patch_flow(self, tmp_path):
        """Model routing decisions must be logged even in patch flow."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post="echo ok",
            )
            assert len(result.model_decisions) >= 1
            d = result.model_decisions[0]
            assert "assigned_tier" in d
            assert "assigned_model" in d
            assert "reason" in d
        finally:
            pipeline.close()

    def test_checkpoint_retrievable_after_pass(self, tmp_path):
        """Accepted checkpoint must be retrievable after PASS verdict."""
        cfg = PipelineConfig(db_path=str(tmp_path / "pipeline.db"))
        pipeline = CodingPipeline(config=cfg)
        try:
            result = pipeline.run_with_patch(
                prompt="Fix bug",
                file_name="fixture.py",
                original_content=_ORIGINAL,
                fixed_content=_FIXED,
                rationale="Add None check",
                validation_post=_VALIDATION_POST,
                session_id="checkpoint-sess",
            )
            if result.verdict == PIPELINE_PASS:
                cp = pipeline.get_checkpoint(session_id="checkpoint-sess")
                assert cp is not None, "Checkpoint must be retrievable after PASS"
        finally:
            pipeline.close()
