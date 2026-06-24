---
name: parallel-worktree
description: Set up and coordinate parallel git worktrees for independent Plan 2 sprints. Ensures file ownership is declared, no files are shared between workers, and work is validated per worktree before merge.
---

# Parallel Worktree Workflow

Set up and coordinate **parallel git worktrees** for independent Plan 2 sprints.

## Trigger
Use when Bryan approves parallel sprint work across independent features.
See also: `docs/plan2/CLAUDE_PARALLEL_WORKFLOW.md` for the full protocol.

## Pre-conditions
- Coordinator must declare file ownership BEFORE any worktree is created.
- No two worktrees may share any file in the same edit.
- Parallel work must not touch: auth, memory, routing, connector tokens,
  approval gates, or shared route files simultaneously.

## Steps
1. **Declare file ownership map** (coordinator):
   ```
   Worktree A (branch: plan2c-feature-x): [file list]
   Worktree B (branch: plan2c-feature-y): [file list]
   (zero overlap)
   ```
   → Stop if overlap detected.

2. **Create worktrees**:
   ```bash
   git worktree add ../openjarvis-worktree-a plan2c-feature-x
   git worktree add ../openjarvis-worktree-b plan2c-feature-y
   ```

3. **Implement independently** — each worker stays in its worktree,
   touches only its declared files.

4. **Validate per worktree** (before merge):
   - `git status --short`
   - `git diff --check`
   - secret scan on changed files
   - `npx tsc --noEmit` (if TS files changed)
   - relevant tests

5. **Merge review** — run `safe-merge-review` skill per worktree.
   merge-coordinator approves or HOLDs.

6. **Cleanup**:
   ```bash
   git worktree remove ../openjarvis-worktree-a
   git worktree remove ../openjarvis-worktree-b
   ```

## Stop Conditions
- File ownership overlap detected → **STOP before creating worktrees**.
- Conflict in protected area during merge review → **HOLD**.
- Any validation failure per worktree → **HOLD that worktree**.

## Output
- Ownership map (declared before start)
- Per-worktree validation results
- Merge review results (PASS / HOLD per worktree)
