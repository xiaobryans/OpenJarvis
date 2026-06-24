# /jarvis-plan [plan name or description]

**Execute a Bryan roadmap/sprint prompt using default autonomous execution.**
Specifically designed for plan-level work: "Plan 2C. Proceed.", sprint tasks,
blocker fixes, and parity implementation.

## Usage
```
/jarvis-plan Plan 2C. Proceed.
/jarvis-plan Fix this blocker and validate.
/jarvis-plan Run takeover validation.
/jarvis-plan Parallelize if safe.
/jarvis-plan Implement connector parity for Telegram env mismatch fix.
```

## Behaviour
Equivalent to `/auto-execute` with plan context enrichment:
1. Reads `CLAUDE.md` for current locked state and active plan.
2. Reads `docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md` for completion status.
3. Reads known blockers.
4. Routes through `default-automation-router`.
5. Executes via `jarvis-plan-executor`.

## Example Interpretations

| Bryan says | Router classifies as | Action |
|------------|---------------------|--------|
| "Plan 2C. Proceed." | implementation / parallel-sprint | Coordinate, assign ownership, implement |
| "Fix this blocker and validate." | bugfix + validation | Fix, validate, report |
| "Run takeover validation." | validation | Checkpoint regression, security review, report |
| "Parallelize if safe." | parallel-sprint | Check file ownership, create worktrees if safe |

## Rules
- Does NOT start Plan 2C unless it is the current approved sprint.
- Does NOT rebuild Tauri.
- Does NOT run live cloud/deployment actions.
- Stops at all hard-rule boundaries defined in `CLAUDE.md`.
