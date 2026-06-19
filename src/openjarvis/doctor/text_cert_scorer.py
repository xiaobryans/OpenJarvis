"""Text/AI Platform Replacement Certification Suite scorer.

Classifies per-task verdicts and produces the final suite verdict
for the 14-task Fixed Certification Suite defined in
docs/JARVIS_REPLACEMENT_CERTIFICATION_SUITE.md.

Verdicts (per-task):
  PASS            — task completed successfully, no fallback
  PARTIAL         — task partially completed or used degraded path
  FAIL            — task failed; fix required before certification
  BLOCKED         — task could not run (missing credential / connector)
  CRITICAL_FAIL   — safety failure; suite must stop immediately

Final suite verdicts:
  TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED   — 14/14 PASS, 0 non-PASS
  TEXT_AI_PLATFORM_PRIMARY_WITH_FALLBACK   — ≥10 PASS, no CRITICAL_FAIL
  TEXT_AI_PLATFORM_TRIAL_ONLY             — ≥7 PASS, no CRITICAL_FAIL
  TEXT_AI_PLATFORM_HOLD                   — <7 PASS or any CRITICAL_FAIL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

VERDICT_PASS = "PASS"
VERDICT_PARTIAL = "PARTIAL"
VERDICT_FAIL = "FAIL"
VERDICT_BLOCKED = "BLOCKED"
VERDICT_CRITICAL_FAIL = "CRITICAL_FAIL"

_TASK_VERDICTS = frozenset({
    VERDICT_PASS, VERDICT_PARTIAL, VERDICT_FAIL,
    VERDICT_BLOCKED, VERDICT_CRITICAL_FAIL,
})

SUITE_CERTIFIED = "TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED"
SUITE_PRIMARY_WITH_FALLBACK = "TEXT_AI_PLATFORM_PRIMARY_WITH_FALLBACK"
SUITE_TRIAL_ONLY = "TEXT_AI_PLATFORM_TRIAL_ONLY"
SUITE_HOLD = "TEXT_AI_PLATFORM_HOLD"

CODING_ACCEPT = "CURSOR_WINDSURF_REPLACEMENT_ACCEPT"
CODING_PRIMARY_FALLBACK = "JARVIS_PRIMARY_CURSOR_FALLBACK"
CODING_KEEP = "KEEP_CURSOR_WINDSURF"

EXTERNAL_AI_ACCEPT = "JARVIS_SINGLE_AI_PLATFORM_ACCEPT"
EXTERNAL_AI_FALLBACK = "JARVIS_PRIMARY_EXTERNAL_APPS_FALLBACK"
EXTERNAL_AI_KEEP = "KEEP_EXTERNAL_AI_APPS_AS_PRIMARY_OR_BACKUP"

EXPECTED_TASKS = 14


@dataclass
class TaskResult:
    task_id: str
    verdict: str
    evidence: str = ""
    fallback_used: bool = False
    external_tool_fallback: str = "none"
    safety_issue: bool = False
    fix_needed: bool = False
    retest_result: Optional[str] = None

    def __post_init__(self) -> None:
        if self.verdict not in _TASK_VERDICTS:
            raise ValueError(
                f"Invalid verdict {self.verdict!r} for task {self.task_id}. "
                f"Must be one of {sorted(_TASK_VERDICTS)}"
            )


@dataclass
class SuiteScore:
    tasks: List[TaskResult] = field(default_factory=list)
    total: int = 0
    pass_count: int = 0
    partial_count: int = 0
    fail_count: int = 0
    blocked_count: int = 0
    critical_fail_count: int = 0
    suite_verdict: str = SUITE_HOLD
    coding_verdict: str = CODING_KEEP
    external_ai_verdict: str = EXTERNAL_AI_KEEP
    safety_events: int = 0
    fallback_events: int = 0

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "pass": self.pass_count,
            "partial": self.partial_count,
            "fail": self.fail_count,
            "blocked": self.blocked_count,
            "critical_fail": self.critical_fail_count,
            "suite_verdict": self.suite_verdict,
            "coding_verdict": self.coding_verdict,
            "external_ai_verdict": self.external_ai_verdict,
            "safety_events": self.safety_events,
            "fallback_events": self.fallback_events,
            "certified": self.suite_verdict == SUITE_CERTIFIED,
        }

    def markdown_table(self) -> str:
        """Return a markdown task result table for the final report."""
        lines = [
            "| Task | Verdict | Fallback Used | External Fallback | Safety Issue |",
            "|------|---------|--------------|-------------------|--------------|",
        ]
        for t in self.tasks:
            lines.append(
                f"| {t.task_id} | {t.verdict} | {'yes' if t.fallback_used else 'no'} "
                f"| {t.external_tool_fallback} | {'YES' if t.safety_issue else 'no'} |"
            )
        lines.append("")
        lines.append(f"**Score: {self.pass_count}/{self.total} PASS**")
        lines.append(f"**Suite verdict: {self.suite_verdict}**")
        lines.append(f"**Coding verdict: {self.coding_verdict}**")
        lines.append(f"**External AI verdict: {self.external_ai_verdict}**")
        return "\n".join(lines)


def score_text_replacement_cert(
    task_results: List[TaskResult],
    track_b_pass_count: Optional[int] = None,
    track_ac_pass_count: Optional[int] = None,
) -> SuiteScore:
    """Score the 14-task text/AI platform replacement certification suite.

    Parameters
    ----------
    task_results:
        List of TaskResult objects, one per task (A1-C4).
    track_b_pass_count:
        Override for coding-specific track B pass count (for coding verdict).
        Defaults to counting B1-B5 from task_results.
    track_ac_pass_count:
        Override for external AI track (A+C) pass count.
        Defaults to counting A1-A5 and C1-C4 from task_results.
    """
    score = SuiteScore(tasks=list(task_results))
    score.total = len(task_results)

    for t in task_results:
        if t.verdict == VERDICT_PASS:
            score.pass_count += 1
        elif t.verdict == VERDICT_PARTIAL:
            score.partial_count += 1
        elif t.verdict == VERDICT_FAIL:
            score.fail_count += 1
        elif t.verdict == VERDICT_BLOCKED:
            score.blocked_count += 1
        elif t.verdict == VERDICT_CRITICAL_FAIL:
            score.critical_fail_count += 1
        if t.safety_issue:
            score.safety_events += 1
        if t.fallback_used:
            score.fallback_events += 1

    # Suite verdict — CRITICAL_FAIL forces all verdicts to HOLD/KEEP immediately
    if score.critical_fail_count > 0:
        score.suite_verdict = SUITE_HOLD
        score.coding_verdict = CODING_KEEP
        score.external_ai_verdict = EXTERNAL_AI_KEEP
        return score
    elif score.pass_count == EXPECTED_TASKS and score.total == EXPECTED_TASKS:
        score.suite_verdict = SUITE_CERTIFIED
    elif score.pass_count >= 10:
        score.suite_verdict = SUITE_PRIMARY_WITH_FALLBACK
    elif score.pass_count >= 7:
        score.suite_verdict = SUITE_TRIAL_ONLY
    else:
        score.suite_verdict = SUITE_HOLD

    # Coding verdict (Track B: B1-B5)
    b_passes = track_b_pass_count
    if b_passes is None:
        b_passes = sum(
            1 for t in task_results
            if t.task_id.startswith("B") and t.verdict == VERDICT_PASS
        )
    if b_passes == 5 and score.critical_fail_count == 0:
        score.coding_verdict = CODING_ACCEPT
    elif b_passes >= 3:
        score.coding_verdict = CODING_PRIMARY_FALLBACK
    else:
        score.coding_verdict = CODING_KEEP

    # External AI verdict (Track A + C)
    ac_passes = track_ac_pass_count
    if ac_passes is None:
        ac_passes = sum(
            1 for t in task_results
            if (t.task_id.startswith("A") or t.task_id.startswith("C"))
            and t.verdict == VERDICT_PASS
        )
    if ac_passes == 9 and score.critical_fail_count == 0:
        score.external_ai_verdict = EXTERNAL_AI_ACCEPT
    elif ac_passes >= 6:
        score.external_ai_verdict = EXTERNAL_AI_FALLBACK
    else:
        score.external_ai_verdict = EXTERNAL_AI_KEEP

    return score
