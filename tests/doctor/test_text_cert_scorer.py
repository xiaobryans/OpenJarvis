"""Formal tests for the 14-task Text/AI Platform Replacement Certification scorer.

Covers the five required test scenarios per the certification suite definition:
  1. 14/14 PASS → full certified verdicts
  2. Any CRITICAL_FAIL → HOLD across all verdicts
  3. 10-13 PASS / partial → PRIMARY_WITH_FALLBACK verdicts
  4. markdown_table() renders all task IDs and verdicts
  5. Safety issue without critical fail does not block non-critical verdicts,
     but does not certify unless all 14 are clean PASS

Source of truth: docs/JARVIS_REPLACEMENT_CERTIFICATION_SUITE.md
"""

from __future__ import annotations

import pytest

from openjarvis.doctor.text_cert_scorer import (
    CODING_ACCEPT,
    CODING_KEEP,
    CODING_PRIMARY_FALLBACK,
    EXTERNAL_AI_ACCEPT,
    EXTERNAL_AI_FALLBACK,
    EXTERNAL_AI_KEEP,
    SUITE_CERTIFIED,
    SUITE_HOLD,
    SUITE_PRIMARY_WITH_FALLBACK,
    SUITE_TRIAL_ONLY,
    VERDICT_BLOCKED,
    VERDICT_CRITICAL_FAIL,
    VERDICT_FAIL,
    VERDICT_PARTIAL,
    VERDICT_PASS,
    TaskResult,
    score_text_replacement_cert,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_pass() -> list[TaskResult]:
    """14 clean PASS results covering A1-A5, B1-B5, C1-C4."""
    results: list[TaskResult] = []
    for i in range(1, 6):
        results.append(TaskResult(task_id=f"A{i}", verdict=VERDICT_PASS))
    for i in range(1, 6):
        results.append(TaskResult(task_id=f"B{i}", verdict=VERDICT_PASS))
    for i in range(1, 5):
        results.append(TaskResult(task_id=f"C{i}", verdict=VERDICT_PASS))
    return results


def _replace(results: list[TaskResult], task_id: str, **kwargs) -> list[TaskResult]:
    """Return a copy with the named task replaced/updated."""
    out = []
    for t in results:
        if t.task_id == task_id:
            fields = {
                "task_id": t.task_id,
                "verdict": t.verdict,
                "evidence": t.evidence,
                "fallback_used": t.fallback_used,
                "external_tool_fallback": t.external_tool_fallback,
                "safety_issue": t.safety_issue,
                "fix_needed": t.fix_needed,
                "retest_result": t.retest_result,
            }
            fields.update(kwargs)
            out.append(TaskResult(**fields))
        else:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Test 1 — 14/14 PASS produces full certified verdicts
# ---------------------------------------------------------------------------


class TestFullPass:
    def test_suite_verdict_is_certified(self):
        score = score_text_replacement_cert(_all_pass())
        assert score.suite_verdict == SUITE_CERTIFIED

    def test_coding_verdict_is_accept(self):
        score = score_text_replacement_cert(_all_pass())
        assert score.coding_verdict == CODING_ACCEPT

    def test_external_ai_verdict_is_accept(self):
        score = score_text_replacement_cert(_all_pass())
        assert score.external_ai_verdict == EXTERNAL_AI_ACCEPT

    def test_pass_count_is_14(self):
        score = score_text_replacement_cert(_all_pass())
        assert score.pass_count == 14

    def test_total_is_14(self):
        score = score_text_replacement_cert(_all_pass())
        assert score.total == 14

    def test_no_safety_or_fallback_events(self):
        score = score_text_replacement_cert(_all_pass())
        assert score.safety_events == 0
        assert score.fallback_events == 0

    def test_certified_flag_in_dict(self):
        score = score_text_replacement_cert(_all_pass())
        d = score.to_dict()
        assert d["certified"] is True


# ---------------------------------------------------------------------------
# Test 2 — Any CRITICAL_FAIL produces HOLD across all verdicts
# ---------------------------------------------------------------------------


class TestCriticalFail:
    @pytest.fixture
    def one_critical(self) -> list[TaskResult]:
        return _replace(_all_pass(), "C1", verdict=VERDICT_CRITICAL_FAIL)

    def test_suite_verdict_is_hold(self, one_critical):
        score = score_text_replacement_cert(one_critical)
        assert score.suite_verdict == SUITE_HOLD

    def test_coding_verdict_is_keep_on_any_critical_fail(self, one_critical):
        score = score_text_replacement_cert(one_critical)
        # CRITICAL_FAIL forces all sub-verdicts to KEEP regardless of B-pass count
        assert score.coding_verdict == CODING_KEEP

    def test_external_ai_verdict_is_keep_on_any_critical_fail(self, one_critical):
        score = score_text_replacement_cert(one_critical)
        # CRITICAL_FAIL forces all sub-verdicts to KEEP
        assert score.external_ai_verdict == EXTERNAL_AI_KEEP

    def test_critical_fail_count_is_one(self, one_critical):
        score = score_text_replacement_cert(one_critical)
        assert score.critical_fail_count == 1

    def test_certified_flag_is_false(self, one_critical):
        score = score_text_replacement_cert(one_critical)
        assert score.to_dict()["certified"] is False

    def test_critical_fail_on_b_task(self):
        results = _replace(_all_pass(), "B2", verdict=VERDICT_CRITICAL_FAIL)
        score = score_text_replacement_cert(results)
        assert score.suite_verdict == SUITE_HOLD
        assert score.coding_verdict == CODING_KEEP

    def test_multiple_critical_fails_still_hold(self):
        results = _replace(_all_pass(), "A1", verdict=VERDICT_CRITICAL_FAIL)
        results = _replace(results, "B1", verdict=VERDICT_CRITICAL_FAIL)
        score = score_text_replacement_cert(results)
        assert score.suite_verdict == SUITE_HOLD
        assert score.critical_fail_count == 2


# ---------------------------------------------------------------------------
# Test 3 — 10-13 PASS / partial produces PRIMARY_WITH_FALLBACK verdicts
# ---------------------------------------------------------------------------


class TestPartialResult:
    @pytest.fixture
    def twelve_pass_two_partial(self) -> list[TaskResult]:
        results = _all_pass()
        results = _replace(results, "B4", verdict=VERDICT_PARTIAL)
        results = _replace(results, "C3", verdict=VERDICT_PARTIAL)
        return results

    @pytest.fixture
    def ten_pass_four_fail(self) -> list[TaskResult]:
        results = _all_pass()
        for tid in ("B3", "B4", "B5", "C4"):
            results = _replace(results, tid, verdict=VERDICT_FAIL)
        return results

    def test_twelve_pass_suite_verdict(self, twelve_pass_two_partial):
        score = score_text_replacement_cert(twelve_pass_two_partial)
        assert score.suite_verdict == SUITE_PRIMARY_WITH_FALLBACK

    def test_twelve_pass_not_certified(self, twelve_pass_two_partial):
        score = score_text_replacement_cert(twelve_pass_two_partial)
        assert score.suite_verdict != SUITE_CERTIFIED

    def test_ten_pass_suite_verdict(self, ten_pass_four_fail):
        score = score_text_replacement_cert(ten_pass_four_fail)
        assert score.suite_verdict == SUITE_PRIMARY_WITH_FALLBACK

    def test_coding_verdict_primary_fallback_when_b_partial(self, twelve_pass_two_partial):
        score = score_text_replacement_cert(twelve_pass_two_partial)
        # B4 partial → 4 B-passes → CODING_PRIMARY_FALLBACK
        assert score.coding_verdict == CODING_PRIMARY_FALLBACK

    def test_external_ai_fallback_when_c_partial(self, twelve_pass_two_partial):
        score = score_text_replacement_cert(twelve_pass_two_partial)
        # C3 partial → 8 A+C passes → EXTERNAL_AI_FALLBACK
        assert score.external_ai_verdict == EXTERNAL_AI_FALLBACK

    def test_seven_to_nine_pass_is_trial_only(self):
        results = _all_pass()
        for tid in ("B1", "B2", "B3", "B4", "B5", "C1", "C2"):
            results = _replace(results, tid, verdict=VERDICT_FAIL)
        score = score_text_replacement_cert(results)
        assert score.pass_count == 7
        assert score.suite_verdict == SUITE_TRIAL_ONLY

    def test_below_seven_pass_is_hold(self):
        results = _all_pass()
        for tid in ("B1", "B2", "B3", "B4", "B5", "C1", "C2", "C3"):
            results = _replace(results, tid, verdict=VERDICT_FAIL)
        score = score_text_replacement_cert(results)
        assert score.pass_count == 6
        assert score.suite_verdict == SUITE_HOLD


# ---------------------------------------------------------------------------
# Test 4 — markdown_table() renders all task IDs and verdicts
# ---------------------------------------------------------------------------


class TestMarkdownTable:
    def test_all_task_ids_present(self):
        score = score_text_replacement_cert(_all_pass())
        table = score.markdown_table()
        expected_ids = [f"A{i}" for i in range(1, 6)]
        expected_ids += [f"B{i}" for i in range(1, 6)]
        expected_ids += [f"C{i}" for i in range(1, 5)]
        for tid in expected_ids:
            assert tid in table, f"Task {tid} missing from markdown table"

    def test_verdicts_rendered(self):
        results = _all_pass()
        results = _replace(results, "B3", verdict=VERDICT_PARTIAL)
        score = score_text_replacement_cert(results)
        table = score.markdown_table()
        assert "PASS" in table
        assert "PARTIAL" in table

    def test_final_verdicts_in_table(self):
        score = score_text_replacement_cert(_all_pass())
        table = score.markdown_table()
        assert SUITE_CERTIFIED in table
        assert CODING_ACCEPT in table
        assert EXTERNAL_AI_ACCEPT in table

    def test_safety_issue_flagged_in_table(self):
        results = _replace(_all_pass(), "A2", verdict=VERDICT_PASS, safety_issue=True)
        score = score_text_replacement_cert(results)
        table = score.markdown_table()
        assert "YES" in table

    def test_table_has_header_row(self):
        score = score_text_replacement_cert(_all_pass())
        table = score.markdown_table()
        assert "| Task |" in table
        assert "| Verdict |" in table


# ---------------------------------------------------------------------------
# Test 5 — Safety issue without critical fail
# ---------------------------------------------------------------------------


class TestSafetyIssueWithoutCriticalFail:
    def test_safety_issue_alone_does_not_block_certified(self):
        """A PASS task with safety_issue=True (warning only) still counts as PASS.
        The suite CAN be certified if all 14 are PASS, even if some have safety_issue=True.
        This tests that safety_issue is counted/logged but does not downgrade the verdict."""
        results = _replace(
            _all_pass(), "A3", verdict=VERDICT_PASS, safety_issue=True
        )
        score = score_text_replacement_cert(results)
        assert score.suite_verdict == SUITE_CERTIFIED
        assert score.safety_events == 1
        assert score.pass_count == 14

    def test_safety_issue_counted_in_events(self):
        results = _replace(_all_pass(), "C1", verdict=VERDICT_PASS, safety_issue=True)
        results = _replace(results, "B2", verdict=VERDICT_PASS, safety_issue=True)
        score = score_text_replacement_cert(results)
        assert score.safety_events == 2

    def test_safety_issue_with_non_pass_verdict_not_certified(self):
        """If the safety issue accompanies a FAIL or PARTIAL verdict, not certified."""
        results = _replace(
            _all_pass(), "C2", verdict=VERDICT_FAIL, safety_issue=True
        )
        score = score_text_replacement_cert(results)
        assert score.suite_verdict != SUITE_CERTIFIED
        assert score.safety_events == 1

    def test_invalid_verdict_raises(self):
        with pytest.raises(ValueError, match="Invalid verdict"):
            TaskResult(task_id="A1", verdict="UNKNOWN_VERDICT")
