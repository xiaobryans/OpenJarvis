# /plan-acceptance-review

Run the **full OpenJarvis plan acceptance review** before presenting to Bryan.

## Usage
```
/plan-acceptance-review
/plan-acceptance-review [plan name]
```

## What this does
Runs the `openjarvis-final-acceptance-review` skill:
1. No-skip blocker closure audit (all declared blockers must have evidence).
2. Endpoint security audit (all public endpoints clean).
3. Secret scan (changed files, docs, commit messages).
4. Test pass rate check (80%+ required).
5. Tauri status check (rebuilt+SHA-match or deferred-with-reason).
6. Plan 1 checkpoint regression check.
7. Handoff continuity check (session state, progress ledger, resume prompt current).
8. Quality score (must be 4/5 or higher).
9. Final report in 13-point format.

## Output
- Verdict: `READY_FOR_REVIEW` or `HOLD`
- Quality score: N/5
- Per-dimension checklist
- Any gaps requiring fix before review

## Hard stops
- Any blocker without explicit closure evidence → HOLD
- Secret scan hit → HOLD
- Quality score below 4/5 → HOLD
- Handoff files stale → update and warn (does not block)

## Rules
- Does NOT mark anything accepted — only Bryan can do that.
- Does NOT skip any checklist item because the rest are clean.
