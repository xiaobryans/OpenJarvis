# OpenJarvis — Claude Code Parallel Worktree Workflow

**Plan 2 Only. Requires Bryan's approval before starting parallel work.**

## Overview

One coordinator session manages the sprint plan.
Independent sprints run in separate git worktrees on separate branches.
No worker touches a file owned by another worker.
All worktrees merge through merge-coordinator.
Every session maintains an action ledger.

## Roles

| Role | Agent | Responsibility |
|------|-------|---------------|
| **Coordinator** | `plan2-coordinator` | File ownership map, routing, blocker detection |
| **Worker A..N** | specialist agents | Implements only files in declared ownership scope |
| **Merge Coordinator** | `merge-coordinator` | Final integration gate — PASS or HOLD |
| **Auditor** | `automation-auditor` | Reviews ledger, flags unlogged/unjustified actions |

## Action Ledger Requirement

Every worker session must maintain an action ledger using the
`full-automation-ledger` skill. The ledger must cover:
- Every file created or modified
- Every command run
- Every staging / commit / push action (MEDIUM risk — must be justified)
- Every validation result
- Whether Bryan approval was required

High-risk actions (auth, connectors, memory/routing, approval gates, file deletion)
must have justification written **before** the action is taken.

## Protocol

### Step 1 — Ownership Declaration (BEFORE creating worktrees)
The coordinator must produce an explicit file ownership map:

```
Worktree A (branch: plan2c-feature-x):
  - src/backend/routes/connector_github.py
  - src/backend/schemas/github.py

Worktree B (branch: plan2c-feature-y):
  - src/backend/routes/connector_telegram.py
  - src/backend/schemas/telegram.py

(zero file overlap between worktrees)
```

**Stop if overlap is detected.** Do not create worktrees until overlap is resolved.

### Step 2 — Create Worktrees
After Bryan approves the ownership map:
```bash
git worktree add ../openjarvis-wt-a plan2c-feature-x
git worktree add ../openjarvis-wt-b plan2c-feature-y
```
Log this action in the ledger (LOW risk, no files modified, Bryan already approved).

### Step 3 — Implement (each worker in its worktree)
- Worker touches **only** its declared files.
- If undeclared file needed → **stop, report to coordinator**, do not edit.
- No Tauri rebuild in any worktree.
- No live cloud/OAuth actions.
- Log every file edit in the action ledger.

### Step 4 — Validate (per worktree, independently)
Each worker runs before signaling ready-to-merge:
```
git status --short
git diff --check
changed-file secret scan (presence-only)
npx tsc --noEmit             (if TS/frontend changed)
npx vite build --mode development  (if frontend changed)
relevant backend smoke/unit tests  (if backend changed)
```
One worktree failing does NOT block the other from merging — they are independent.
Log validation results in the action ledger.

### Step 5 — Merge Review (merge-coordinator)
For each worktree branch:
1. Run `safe-merge-review` skill.
2. Check file ownership was respected.
3. Check no protected area conflicts.
4. Secret scan on all changed files.
5. Checkpoint regression assessment.
6. Report **PASS or HOLD** per worktree — never auto-merge.
7. `automation-auditor` reviews each worker's ledger for gaps.

### Step 6 — Bryan Approves Merge
Merge-coordinator presents PASS/HOLD per branch to Bryan.
Bryan approves merges individually.
Worker logs the approved merge in the ledger (MEDIUM risk — Bryan approved).

### Step 7 — Cleanup
```bash
git worktree remove ../openjarvis-wt-a
git worktree remove ../openjarvis-wt-b
```
Log cleanup in the ledger (LOW risk).

## How Claude Explains and Justifies Actions

### Standard actions (LOW risk) — log after
```
| Step | Action | Reason | Risk | Files | Command | Validation | Result | Bryan Approval? |
| 3    | Created connector route | Sprint scope item | low | connector_github.py | Write | tsc pass | ✓ | No |
```

### Medium-risk actions (staging/commit/push) — justify in ledger
```
[MEDIUM-RISK ACTION — Step N]
Action: git add src/backend/routes/connector_github.py
Reason: Staging sprint scope file for commit
Risk: MEDIUM
Justification: File is within declared ownership scope; secret scan passed;
               Bryan pre-approved this sprint's staging/commit/push.
Proceeding.
```

### High-risk actions — justify BEFORE performing
```
[HIGH-RISK ACTION — Step N]
Action: Modifying auth middleware
Reason: [specific sprint requirement]
Risk: HIGH
Files affected: [list]
Alternative considered: [what else was considered]
Proceeding because: [Bryan explicit approval / sprint scope]
```

## Commit / Push Rules (parallel mode)

1. Stage only files in the worktree's declared scope — explicit paths only.
2. Verify: `git diff --cached --name-only` matches ownership declaration.
3. Secret scan on staged files.
4. `git diff --check`.
5. Commit with message referencing the feature branch.
6. Push only to the worktree's declared branch.
7. Log each step in the action ledger.

## Hard Stops — Parallel Work MUST Halt

Stop if parallel work would overlap these protected files or systems:
- Auth middleware and token validation logic
- Unified memory search (SQLite + JarvisMemory)
- Cloud-first routing logic
- Connector token handling
- Approval gate logic
- Shared route files used by multiple features
- `CLAUDE.md` (cannot be edited in parallel)

## What CANNOT run in any worktree
- `bash scripts/build-local.sh --install` (Tauri rebuild — blocked by hook)
- Live OAuth flows
- Fargate deployment commands
- Any destructive operation without Bryan's approval
- `git add .` or `git add -A` (always use explicit paths)
