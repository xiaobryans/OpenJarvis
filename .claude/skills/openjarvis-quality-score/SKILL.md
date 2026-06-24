---
name: openjarvis-quality-score
description: Produce a consistent quality score (N/5) for an OpenJarvis sprint across 5 dimensions — blocker closure, test pass rate, secret safety, handoff completeness, no-fake-PASS compliance. Minimum 4/5 to be READY_FOR_REVIEW. Use at the end of any sprint before the final report.
---

# OpenJarvis Quality Score

Produces a **consistent N/5 quality score** for any OpenJarvis sprint.

## When to use
- At the end of any sprint before generating the final report.
- When `/quality-score` is invoked.
- As a component of `openjarvis-final-acceptance-review`.

## Steps

1. Invoke `quality-score-reviewer` agent.
2. Supply: blocker registry, test results, secret scan result, handoff file state.
3. Receive: N/5 score with per-dimension rationale.
4. If score is 3/5 or below: report HOLD. Do not continue to commit/push.
5. If score is 4/5 or 5/5: proceed to final report.

## Scoring dimensions
1. Blocker closure — all declared blockers closed with evidence.
2. Test pass rate — 80%+ in-scope tests passing.
3. Secret safety — secret scan CLEAN.
4. Handoff completeness — session state/resume prompt current.
5. No fake PASS — every verdict backed by proof.

## Output
```
QUALITY SCORE: [N]/5
[per-dimension breakdown]
VERDICT: READY_FOR_REVIEW (4–5/5) | HOLD (0–3/5)
```
