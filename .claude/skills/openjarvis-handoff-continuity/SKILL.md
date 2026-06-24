---
name: openjarvis-handoff-continuity
description: Save and verify crash-safe handoff state — updates session state, progress ledger, and resume prompt to match actual git HEAD and dirty state. Sets safe_to_continue_automatically flag. Use at the end of every sprint or before any context-compaction risk.
---

# OpenJarvis Handoff Continuity

Saves and verifies the **crash-safe handoff state** for the current sprint.

## When to use
- At the end of every sprint (before commit/push).
- Before context might be compacted (long session, large diffs).
- When Bryan asks to save state or run `/handoff-save`.
- Any time the session state file is stale relative to actual HEAD.

## Steps

1. Run `git branch --show-current` and `git rev-parse HEAD`.
2. Run `git status --short` — capture dirty files.
3. Read `docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md`.
4. Compare: branch matches? HEAD matches? Dirty files match known pre-existing list?
5. Update session state file if stale.
6. Update `RESUME_FROM_HERE` marker to current sprint phase.
7. Set `safe_to_continue_automatically`:
   - YES: no hard blockers, no unresolved failures, HEAD matches expected.
   - NO: hard blocker present, or unexpected dirty state.
8. Verify resume prompt is self-contained (readable by a fresh Claude session).
9. Report what was updated.

## Invoke via `handoff-continuity-keeper` agent for the actual file updates.

## Safe commands
```bash
git branch --show-current
git rev-parse HEAD
git status --short
git log --oneline -3
```

## Forbidden
- Never stage or commit handoff files in this skill call — that is the sprint-close commit step.
- Never set safe_to_continue_automatically=YES if a hard blocker is unresolved.

## Output
```
HANDOFF CONTINUITY CHECK
Branch: [name] — CURRENT | STALE
HEAD: [sha] — CURRENT | STALE (updated)
Dirty files: PRE-EXISTING ONLY | UNEXPECTED
safe_to_continue_automatically: YES | NO
Files updated: [list]
```
