# /handoff-save

Save the current sprint state to crash-safe handoff files.

## Usage
```
/handoff-save
/handoff-save [sprint phase description]
```

## What this does
Runs the `openjarvis-handoff-continuity` skill:
1. Reads actual `git branch --show-current` and `git rev-parse HEAD`.
2. Reads `git status --short`.
3. Compares to `docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md`.
4. Updates session state file to match actual state.
5. Updates `RESUME_FROM_HERE` marker to current phase.
6. Sets `safe_to_continue_automatically` flag (YES only if no hard blockers).
7. Verifies resume prompt is self-contained.
8. Reports what was updated.

## When to use
- At the end of every sprint phase.
- Before context compaction risk (long session, large diffs).
- After any commit/push to update HEAD in handoff.
- When Bryan asks to save state.

## Important
`/handoff-save` does NOT commit or push the handoff files — that happens as part of the sprint-close commit. The purpose is to write the files so they are ready to be staged.

## Output
```
HANDOFF STATE SAVED
Branch: [name]
HEAD: [sha]
Dirty files: [pre-existing list]
safe_to_continue_automatically: YES | NO
Files updated: [list]
```
