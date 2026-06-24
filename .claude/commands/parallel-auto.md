# /parallel-auto [task description]

**Evaluate safe worktree parallelization and proceed only if file ownership
can be fully separated.** If safe, set up worktrees and execute in parallel.
If not safe, execute sequentially without prompting.

## Usage
```
/parallel-auto implement GitHub and Telegram connectors
/parallel-auto fix backend routes and update mobile UI
/parallel-auto Parallelize if safe.
```

## Decision Logic

Claude evaluates automatically:

### Safe to parallelize when ALL true:
- ≥2 independent sub-tasks exist
- Their file sets have zero overlap
- Neither touches: auth, memory, routing, connector tokens,
  approval gates, or shared route files simultaneously
- Each can be validated independently

### Not safe — executes sequentially when ANY true:
- File sets overlap
- Either task touches a protected area simultaneously
- Only 1 meaningful sub-task exists
- Parallel setup overhead exceeds benefit (small tasks)

## When parallel is safe — automatic flow:
1. Declare file ownership map.
2. Create git worktrees (separate branches).
3. Execute workers in parallel, each within declared file scope.
4. Validate each worktree independently.
5. Run `safe-merge-review` per worktree via `merge-coordinator`.
6. Report PASS/HOLD per worktree for Bryan's merge approval.

## When not safe — automatic fallback:
Sequential execution without prompting. Reports why parallel was skipped.

## Rules
- Never creates worktrees with overlapping file ownership.
- Never touches protected areas in parallel.
- Never uses `git add .` — explicit paths only.
- Tauri rebuild blocked in all worktrees.
