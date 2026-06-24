---
name: jarvis-plan-executor
description: Turn any Bryan plan/prompt into automatic execution. Invokes the default-automation-router, runs the full sprint lifecycle (classify → implement → validate → security-check → stage → commit → push → report), and produces a final report with action ledger. Use as the primary autonomous execution skill.
---

# Jarvis Plan Executor

Turn a **Bryan plan/prompt into automatic execution** using
`DEFAULT_AUTONOMOUS_EXECUTION_MODE`.

## Trigger
Any Bryan prompt that is not explicitly `review-only`, `planning-only`,
`no-edits`, or `ask-first`. Invoked by `/auto-execute` and `/jarvis-plan`.

## Pre-conditions
Check before starting:
- Confirm current locked plan state from `CLAUDE.md`.
- Confirm no hard-rule violation would occur.
- Confirm `default-automation-router` can classify the request.

## Execution Flow

### Phase 1 — Classify and Route
Invoke `default-automation-router`:
- Produce task type, risk class, model, agents, skills, commands.
- Produce parallelization decision and file ownership map.
- Produce validation plan and commit/push policy.
- If router returns `HOLD` → stop and ask Bryan. Do not proceed.

### Phase 2 — Check Hard Boundaries
Before any file is touched, verify:
- Task is inside current approved sprint scope.
- No secret/credential values will be read or printed.
- No destructive file operations (deletion).
- No live cloud/OAuth/deployment actions.
- No Tauri rebuild.
- No overlap with unrelated dirty files.
→ If any boundary would be crossed → HOLD, report to Bryan.

### Phase 3 — Decide Sequential vs Parallel
Use router's parallelization decision:
- **Parallel** → invoke `parallel-worktree` skill; assign workers to worktrees.
- **Sequential** → single coordinator → single implementer agent.

### Phase 4 — Assign File Ownership
Declare ownership map before first edit. Log it in action ledger.
If ownership map has overlap in protected areas → HOLD.

### Phase 5 — Implement
Route to the appropriate specialist agent(s):
`backend-implementer`, `frontend-mobile-implementer`, `connector-specialist`,
`memory-sync-specialist`, `docs-matrix-maintainer`, or `cloud-infra-planner`.

Workers touch only declared files. If an undeclared file is needed → stop,
report to coordinator, do not edit.

### Phase 6 — Changed-File Validation
After implementation, run (changed files only):
```bash
git status --short
git diff --check
npx tsc --noEmit             # if TS/frontend changed
npx vite build --mode development  # if frontend changed
# relevant backend tests     # if backend changed
```
→ Any failure: HOLD. Do not proceed to staging.

### Phase 7 — Secret / Security Review
Run `secret-safety-review` on all changed files.
→ Any high-entropy value found: HOLD immediately.

### Phase 8 — Checkpoint Regression Check
If changed files touch Plan 1 or Plan 2 checkpoint paths, run
`checkpoint-regression` skill.
→ Any regression: HOLD immediately.

### Phase 9 — Update Docs / Matrix
If the sprint added, removed, or changed a connector, route, endpoint,
or parity status — update `docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md`
and/or `docs/plan2/plan2_matrix.json` via `docs-matrix-maintainer`.

### Phase 10 — Stage Explicit Files
Stage only sprint-scope files using explicit paths (never `git add .`).
Verify staged list: `git diff --cached --name-only`.
Confirm no unrelated dirty files staged.

### Phase 11 — Commit and Push (if allowed)
Only if:
- All validation passed (Phase 6-8)
- Staged list matches sprint scope
- Commit/push policy from router is ALLOWED
```bash
git commit -m "[message describing the sprint task]"
git push fork localhost-get-tool
```
Log both in action ledger (MEDIUM risk, pre-approved).

### Phase 12 — Final Report
Produce the 13-point sprint report from `CLAUDE.md` plus the full action ledger.

## Stop Conditions (hard stops — do not continue)
- Router returns `HOLD` or `out-of-scope`
- Hard-rule boundary violation detected
- Validation failure (tsc, vite, tests)
- Secret/high-entropy value found in changed files
- Checkpoint regression detected
- File ownership overlap in protected areas
- Any action would require reading/printing secrets

## Output
Full 13-point sprint report + action ledger table.
Verdict: `[TASK]_COMMITTED_PENDING_REVIEW` or `[TASK]_HOLD`.
