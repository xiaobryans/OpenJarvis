# /stop-on-blocker

Check for **current sprint blockers** and stop if any hard blocker is found.

## What this does
Runs the `blocker-triage` skill:
1. Checks current sprint scope against known hard blockers.
2. Identifies missing credentials, broken auth, Fargate deployment gaps,
   unresolved env mismatches.
3. Reports CLEAR (sprint may proceed) or HOLD (must resolve first).

## When to use
- Before starting any Plan 2 sprint.
- When a sprint hits an unexpected obstacle.
- When uncertain whether to continue or stop.

## Rules
- HOLD on first hard blocker — does not continue.
- Does not work around blockers (no fake credential stubs, no placeholder fixes).
- Reports exact resolution path for each blocker.

## Output
CLEAR (proceed) or HOLD with:
- Hard blockers and resolution path
- Soft blockers (can parallel-work around)
- Informational items
