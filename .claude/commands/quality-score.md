# /quality-score

Produce a **consistent N/5 quality score** for the current sprint.

## Usage
```
/quality-score
/quality-score [sprint name]
```

## What this does
Runs the `openjarvis-quality-score` skill:
1. Invokes `quality-score-reviewer` agent.
2. Scores 5 dimensions (1 point each):
   - Blocker closure: all declared blockers closed with evidence.
   - Test pass rate: 80%+ in-scope tests passing.
   - Secret safety: secret scan CLEAN.
   - Handoff completeness: session state and resume prompt current.
   - No fake PASS: every verdict backed by proof.
3. Returns N/5 with per-dimension rationale.
4. HOLD if score is 3/5 or below.

## Output
```
QUALITY SCORE: [N]/5
Dim 1 — Blocker closure: [1|0]
Dim 2 — Test pass rate: [1|0] ([N]/[total])
Dim 3 — Secret safety: [1|0]
Dim 4 — Handoff completeness: [1|0]
Dim 5 — No fake PASS: [1|0]
VERDICT: READY_FOR_REVIEW | HOLD
```

## Minimum bar
- 4/5 required for READY_FOR_REVIEW.
- 5/5 expected for ACCEPTED (Bryan's call).
- 3/5 or below → HOLD. Do not commit or push.
