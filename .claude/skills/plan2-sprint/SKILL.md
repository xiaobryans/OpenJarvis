---
name: plan2-sprint
description: Execute a single Plan 2 sprint end-to-end — file ownership declaration, implementation, validation, secret scan, checkpoint regression check, and full report. Use when starting a new Plan 2 feature sprint.
---

# Plan 2 Sprint

Execute a **single Plan 2 sprint** end-to-end.

## Trigger
Use when Bryan assigns a specific Plan 2 task for implementation.

## Pre-conditions
- Confirm current locked plan state from `CLAUDE.md`.
- Confirm Plan 2C has NOT been started unless Bryan explicitly approved.
- Confirm Tauri rebuild is NOT scheduled.

## Steps
1. **Declare file ownership** — list every file that will be changed.
   Stop if any file touches a protected area without coordinator sign-off.

2. **Implement** — use the appropriate specialist agent (backend-implementer,
   frontend-mobile-implementer, connector-specialist, memory-sync-specialist).

3. **Validate** (changed files only):
   - `git status --short`
   - `git diff --check`
   - `npx tsc --noEmit` (if TS/frontend files changed)
   - `npx vite build --mode development` (if frontend files changed)
   - relevant backend smoke/unit tests (if backend files changed)

4. **Secret scan** — run `secret-safety-review` on changed files.

5. **Checkpoint regression check** — run `checkpoint-regression` skill.

6. **Report** — produce the full sprint report using `plan2-report` skill.

## Stop Conditions
- Any validation failure → HOLD, report, do not continue.
- Any secret hit → HOLD.
- Any Plan 1 checkpoint regression → HOLD.
- Any blocker discovered → HOLD, surface immediately.
- Tauri rebuild attempted → STOP, report as violation.

## Output
Full sprint report per required format in `CLAUDE.md`.
