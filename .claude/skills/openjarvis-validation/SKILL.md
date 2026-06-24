---
name: openjarvis-validation
description: Validate an OpenJarvis sprint with changed-file-only review and strict reporting. Use when validating a sprint, checking changed files before commit, or producing a sprint validation report for OpenJarvis.
---

# OpenJarvis Validation

Validate an OpenJarvis sprint with **changed-file-only review** and **strict reporting**.

## Rules
- Validate **changed files only** unless scope requires broader checks.
- **Do not rebuild Tauri during Plan 2.**
- **Do not print secrets** (presence-only key reporting).

## Run
- `git status --short`
- `git diff --check`
- changed-file secret scan
- `npx tsc --noEmit` — when TS / frontend changed
- `npx vite build --mode development` — when frontend changed
- relevant backend smoke / unit tests — when backend changed

## Report
- Report **exact outputs** of every command.
- If **anything fails**, the verdict is **HOLD**.

Follow the required final report format in `CLAUDE.md`:
verdict, branch, previous HEAD, new HEAD, changed files, files inspected and why,
root cause, exact fix, validation command outputs, secret scan result, proof
accepted checkpoints were not regressed, Tauri-rebuild-deferred statement, and
remaining blockers.
