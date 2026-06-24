---
name: plan2-report
description: Generate the required OpenJarvis sprint final report. Use at the end of any Plan 2 sprint or validation run to produce the mandatory 13-point report format.
---

# Plan 2 Report

Generate the **required OpenJarvis sprint final report** (13-point format).

## Trigger
Use at the end of any Plan 2 sprint, validation run, or before any merge request.

## Required Report Format
Produce all 13 points in order — no skipping, no abbreviating:

1. **Verdict** — `PASS` / `HOLD` / `PATCHED_PENDING_REVIEW`
2. **Branch** — current branch name
3. **Previous HEAD** — git SHA before sprint
4. **New HEAD** — git SHA after sprint (or "no new commit — pending review")
5. **Changed files** — exact list from `git diff --name-only HEAD~1..HEAD`
   (or `git diff --cached --name-only` if not yet committed)
6. **Files inspected and why** — each file + reason it was reviewed
7. **Root cause** — what problem was solved (or "N/A — new feature")
8. **Exact fix** — what code changed and how
9. **Validation command outputs** — exact stdout/stderr of every command run
10. **Secret scan result** — PASS or HOLD with line numbers (no values)
11. **Proof accepted checkpoints were not regressed** — explicit per-checkpoint
    confirmation for all Plan 1 and prior Plan 2 checkpoints
12. **Statement that Tauri rebuild is deferred until full Plan 2 completion**
13. **Remaining blockers** — full current blocker list from `CLAUDE.md`

## Rules
- **No fake PASS / no fake ACCEPTED.**
- **Do not skip items** — if data is unavailable, say so explicitly.
- **Do not print secret values** in any output field.

## Output
The complete 13-point report, formatted with headers for each point.
