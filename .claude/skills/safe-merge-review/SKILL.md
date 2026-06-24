---
name: safe-merge-review
description: Review a merge candidate (branch or PR) for safety before integration. Checks file ownership, protected area conflicts, secret exposure, and Plan 1 regression risk. Returns PASS or HOLD.
---

# Safe Merge Review

Review a **merge candidate** for safety before integration into the main branch.

## Trigger
Use before any merge of a Plan 2 sprint branch into `localhost-get-tool` or main.
Use by merge-coordinator agent before final integration.

## Steps
1. List all changed files on the source branch:
   `git diff --name-only <base>..<branch>`

2. Check for **protected area conflicts**:
   - Auth middleware / token validation
   - Memory search / JarvisMemory
   - Cloud-first routing logic
   - Connector token handling
   - Approval gate logic
   - Shared route files
   → HOLD if any conflict in these areas.

3. Check for **file ownership violations**:
   - Were any files modified outside declared ownership scope?
   → HOLD if yes.

4. `git diff --check` on the merge candidate.

5. **Secret scan** on all changed files (secret-safety-review skill).

6. **Checkpoint regression assessment** — do any changed files touch Plan 1
   checkpoint paths? If yes, run checkpoint-regression skill.

7. Check for **merge conflicts** in protected files:
   `git merge --no-commit --no-ff <branch>` (dry run, abort after)

## Stop Conditions
- Conflict in protected area → **HOLD**.
- File ownership violation → **HOLD**.
- Secret value found → **HOLD**.
- Merge conflict in auth/memory/routing → **HOLD**.

## Output
```
SAFE MERGE REVIEW: [PASS / HOLD]
Branch: [branch name]
Changed files: [list]
Protected area conflicts: [none / list]
File ownership violations: [none / list]
Secret scan: [PASS / HOLD]
Merge conflict check: [CLEAN / CONFLICTS in: ...]
Verdict: PASS (safe to merge) | HOLD (see above)
```
