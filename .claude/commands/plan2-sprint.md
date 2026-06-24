# /plan2-sprint [task]

Execute a **single Plan 2 sprint** with full validation and reporting.

## Usage
```
/plan2-sprint fix Telegram env mismatch
/plan2-sprint wire approval notification loop
```

## What this does
Runs the `plan2-sprint` skill end-to-end:
1. Checks pre-conditions (no Plan 2C, no Tauri rebuild, locked state confirmed).
2. Declares file ownership.
3. Routes to appropriate implementer agent.
4. Runs full validation (tsc, vite build, tests — changed files only).
5. Runs secret-safety-review.
6. Runs checkpoint-regression check.
7. Produces full 13-point sprint report.

## Rules
- Does NOT start Plan 2C unless Bryan explicitly approved.
- Does NOT run Tauri rebuild.
- HOLD on any blocker — does not continue past it.
- Does not stage or commit — presents changes for Bryan's approval.
