# /parallel-plan2

Set up and coordinate **parallel git worktrees** for independent Plan 2 sprints.

## What this does
Runs the `parallel-worktree` skill via plan2-coordinator agent:
1. Declares file ownership map (no overlaps allowed).
2. Creates separate git worktrees per independent sprint.
3. Routes each worker to its appropriate specialist agent.
4. Validates each worktree independently before merge review.
5. Routes all merge candidates through merge-coordinator.

## When to use
When Bryan approves parallel sprint work across clearly independent features
with no shared file dependencies.

## Rules
- Do NOT start parallel work without explicit file ownership declaration.
- Do NOT allow overlap in: auth, memory, routing, connector tokens, approval
  gates, or shared route files.
- Each worktree validates independently — one failure does not block others.
- All worktrees route through merge-coordinator before integration.
- Tauri rebuild blocked in all worktrees during Plan 2.

## Output
- Ownership map
- Worktree creation commands (for Bryan's approval before execution)
- Per-worktree validation plan
