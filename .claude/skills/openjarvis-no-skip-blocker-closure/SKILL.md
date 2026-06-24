---
name: openjarvis-no-skip-blocker-closure
description: Verify all declared sprint blockers have explicit closure evidence — test output, live proof, or code change. No quiet skips allowed. Produces CLEAN | HOLD verdict. Use before any acceptance review and after any sprint that closes blockers.
---

# OpenJarvis No-Skip Blocker Closure

Verifies **no blocker was quietly skipped** in a sprint.

## When to use
- Before presenting a plan for acceptance review.
- After any sprint that claims to close blockers.
- When `/no-skip-audit` is invoked.

## Steps

1. Read `CLAUDE.md` active plan blockers section.
2. Read session state blocker registry.
3. Read sprint progress ledger for closure actions.
4. Invoke `no-skip-blocker-auditor` agent — compare declared blockers against closure evidence.
5. Verify each closure has: specific test name OR specific live proof output OR specific code commit.
6. Flag PARTIAL closures that were labeled CLOSED.
7. Flag PARKED blockers that have no PARKED label.

## Safe commands
```bash
grep -n 'CLOSED\|LIVE_PROVEN\|PARTIAL\|PARKED\|HOLD' docs/plan2/PLAN2_AUTONOMOUS_SESSION_STATE.md | head -30
git log --oneline -10
```

## Stop conditions
- Any blocker without evidence → HOLD immediately.
- Any blocker missing from the closure table → HOLD.
- Any PARTIAL labeled as CLOSED → HOLD.

## Output
```
NO-SKIP BLOCKER CLOSURE AUDIT
[structured output from no-skip-blocker-auditor agent]
VERDICT: CLEAN | HOLD
```
