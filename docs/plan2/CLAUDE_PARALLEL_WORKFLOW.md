# OpenJarvis — Claude Code Parallel Worktree Workflow

**Plan 2 Only. Requires Bryan's approval before starting parallel work.**
In `DEFAULT_AUTONOMOUS_EXECUTION_MODE`, parallelization is evaluated and
executed automatically when file ownership can be fully separated.

## Overview

One coordinator session manages the sprint plan.
Independent sprints run in separate git worktrees on separate branches.
No worker touches a file owned by another worker.
All worktrees merge through merge-coordinator.
Every session maintains an action ledger.

## Roles

| Role | Agent | Responsibility |
|------|-------|---------------|
| **Router** | `default-automation-router` | Classifies request, decides parallel vs sequential |
| **Coordinator** | `plan2-coordinator` | File ownership map, routing, blocker detection |
| **Worker A..N** | specialist agents | Implements only files in declared ownership scope |
| **Merge Coordinator** | `merge-coordinator` | Final integration gate — PASS or HOLD |
| **Auditor** | `automation-auditor` | Reviews ledger, flags unlogged/unjustified actions |

## Automatic Parallelization (DEFAULT_AUTONOMOUS_EXECUTION_MODE)

`/parallel-auto` and `/jarvis-plan` evaluate parallelization automatically.
Bryan does **not** need to approve the decision — Claude reports it in the ledger.

**Safe to parallelize — Claude proceeds automatically when ALL true:**
1. ≥2 independent sub-tasks exist
2. Their file sets have zero overlap
3. Neither sub-task touches protected areas simultaneously
4. Each sub-task can be validated independently

**Not safe — Claude falls back to sequential without prompting when ANY true:**
- File sets overlap
- Either task touches a protected area simultaneously
- Only 1 meaningful sub-task exists
- Parallel overhead exceeds benefit (trivially small tasks)

Claude reports its decision (parallel or sequential) and the reason in the action ledger.

## Worktree Safety Rules

Protected areas — STOP if parallel work would overlap these:
- Auth middleware and token validation logic
- Unified memory search (SQLite + JarvisMemory)
- Cloud-first routing logic
- Connector token handling
- Approval gate logic
- Shared route files used by multiple features
- `CLAUDE.md` (never edit in parallel)

## Action Ledger Requirement

Every worker session must log in the action ledger:
- Every file created or modified
- Every command run
- Every staging / commit / push action (MEDIUM risk — pre-approved in scope)
- Every validation result
- Worktree creation and cleanup

High-risk actions (auth, connectors, memory/routing, approval gates, deletion)
require justification written **before** the action.

## Protocol

### Step 1 — Router Decision
`default-automation-router` produces the parallelization decision and file
ownership map automatically. Bryan is NOT asked unless ownership overlap is
unavoidable.

### Step 2 — Ownership Declaration
```
File ownership map:
  Worktree A (branch: plan2c-feature-x):
    - src/backend/routes/connector_github.py
    - src/backend/schemas/github.py

  Worktree B (branch: plan2c-feature-y):
    - src/backend/routes/connector_telegram.py
    - src/backend/schemas/telegram.py

  (zero file overlap)
```
Logged in action ledger (LOW risk).
**HOLD if overlap detected** — do not create worktrees.

### Step 3 — Create Worktrees
After ownership map is clean (no prompt needed if safe):
```bash
git worktree add ../openjarvis-wt-a plan2c-feature-x
git worktree add ../openjarvis-wt-b plan2c-feature-y
```
Logged in action ledger (LOW risk, Bryan-approved via standing permission).

### Step 4 — Implement (each worker in its worktree)
- Worker touches **only** declared files.
- Undeclared file needed → **stop, report to coordinator**, do not edit.
- No Tauri rebuild in any worktree.
- No live cloud/OAuth actions.
- Every file edit logged in action ledger.

### Step 5 — Validate (per worktree, independently)
Each worker runs before signaling ready-to-merge:
```bash
git status --short
git diff --check
# secret scan (presence-only)
npx tsc --noEmit             # if TS/frontend changed
npx vite build --mode development  # if frontend changed
# relevant backend tests     # if backend changed
```
Failures in one worktree do NOT block the other — they are independent.
Log all validation results in the action ledger.

### Step 6 — Merge Review (merge-coordinator)
For each worktree branch:
1. `safe-merge-review` skill
2. File ownership respected? → HOLD if not
3. Protected area conflicts? → HOLD if yes
4. Secret scan on all changed files
5. Checkpoint regression assessment
6. `automation-auditor` reviews worker's ledger for gaps
7. Report **PASS or HOLD** per worktree — **never auto-merge**

### Step 7 — Bryan Approves Merge
Merge-coordinator presents PASS/HOLD per branch.
Bryan approves merges individually.
Worker logs the approved merge in the ledger (MEDIUM risk — Bryan approved).

### Step 8 — Cleanup
```bash
git worktree remove ../openjarvis-wt-a
git worktree remove ../openjarvis-wt-b
```
Logged in action ledger (LOW risk).

## How Claude Explains and Justifies Actions

### Routine scoped actions (LOW/MEDIUM risk inside scope) — log after, no prior ask
```
| Step | Action | Reason | Risk | Files | Command | Validation | Result | Bryan Approval? |
| 3    | Create worktree A | Parallel sprint, safe ownership | low | n/a | git worktree add | ownership verified | ✓ | No (standing perm) |
| 7    | Stage worktree-A files | Commit sprint scope | medium | [list] | git add [paths] | secret scan PASS | ✓ | No (standing perm) |
```

### High-risk actions — justify BEFORE performing
```
[HIGH-RISK ACTION — Step N]
Action: Modifying auth middleware
Reason: [specific sprint requirement]
Risk: HIGH
Files: [list]
Alternative: [considered alternatives]
Proceeding because: [Bryan explicit approval]
```

## Commit / Push Rules (autonomous parallel mode)

1. Stage only files in the worktree's declared scope — explicit paths only.
2. `git diff --cached --name-only` — verify against ownership declaration.
3. Secret scan on staged files.
4. `git diff --check`.
5. Commit with message referencing the feature.
6. Push only to the worktree's declared branch.
7. Log all steps in the action ledger.

No prompt to Bryan unless validation fails or protected-area conflict is detected.

## What CANNOT run in any worktree
- `bash scripts/build-local.sh --install` (blocked by hook)
- Live OAuth flows
- Fargate deployment commands
- Any destructive operation without Bryan's approval
- `git add .` or `git add -A` (always use explicit paths)

## Examples

| Bryan says | Claude does |
|------------|-------------|
| "Parallelize if safe." | Router evaluates ownership → creates worktrees if safe → sequential if not |
| "Implement GitHub and Telegram connectors." | Router checks overlap → parallel if no shared files → sequential if overlap |
| "Fix the backend and update mobile UI." | Router checks → parallel if files fully separate → logs decision |
