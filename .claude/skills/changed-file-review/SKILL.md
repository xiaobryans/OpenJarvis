---
name: changed-file-review
description: Review only the changed files in a sprint for correctness, safety, and rule compliance. Default review mode for OpenJarvis — does NOT do full codebase review unless Bryan asks.
---

# Changed File Review

Review **only the changed files** in a sprint for correctness, safety, and rule compliance.

## Trigger
Default review after any sprint implementation, before final report.
Use with any commit for a focused, fast review.

## Scope
Changed files only — determined by:
- `git diff --cached --name-only` (staged, pre-commit)
- `git diff HEAD~1..HEAD --name-only` (post-commit)

Do NOT expand to full codebase review unless Bryan explicitly requests it.

## Review Checklist (per changed file)
- [ ] No secret values printed or logged
- [ ] No auth logic weakened
- [ ] No public endpoint leaking token presence, env names, account IDs, paths
- [ ] No new unguarded remote execution paths
- [ ] No approval gate regressions
- [ ] TypeScript types consistent (no `any` shortcuts around critical paths)
- [ ] No Tauri rebuild triggered
- [ ] No unrelated files modified

## Steps
1. List changed files.
2. For each file, apply the checklist above.
3. Run `git diff --check` for whitespace/conflict markers.
4. Note any issues found with file + line number (no secret values).

## Stop Conditions
- Auth weakening found → **HOLD**.
- Secret value in changed file → **HOLD**.
- Approval gate regression → **HOLD**.

## Output
```
CHANGED FILE REVIEW: [PASS / HOLD]
Files reviewed: [list]
Issues found: [file:line — issue description] (no secret values)
Verdict: PASS (no issues) | HOLD (see issues above)
```
