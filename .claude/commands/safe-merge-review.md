# /safe-merge-review [branch]

Run **safe merge review** on a branch before integration.

## Usage
```
/safe-merge-review plan2c-feature-x
/safe-merge-review (reviews current branch vs base)
```

## What this does
Runs the `safe-merge-review` skill via merge-coordinator agent:
1. Lists all changed files on the branch.
2. Checks for conflicts in protected areas (auth, memory, routing, connectors,
   approval gates, shared routes).
3. Checks for file ownership violations.
4. Runs `git diff --check`.
5. Runs secret scan on all changed files.
6. Assesses checkpoint regression risk.
7. Dry-run merge conflict check.

## Rules
- HOLD on any protected area conflict.
- HOLD on any file ownership violation.
- HOLD on any secret found.
- HOLD on any merge conflict in auth/memory/routing.
- Does NOT auto-merge — reports PASS/HOLD for Bryan's approval.
