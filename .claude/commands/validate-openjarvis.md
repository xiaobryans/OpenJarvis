# /validate-openjarvis

Run **OpenJarvis changed-file validation** and produce a sprint report.

## What this does
Runs the `openjarvis-validation` skill:
1. `git status --short`
2. `git diff --check`
3. Changed-file secret scan (presence-only, no values printed)
4. `npx tsc --noEmit` (if TS/frontend files changed)
5. `npx vite build --mode development` (if frontend files changed)
6. Relevant backend smoke/unit tests (if backend files changed)
7. Reports exact command outputs.

## Rules
- Does NOT run Tauri rebuild.
- Reports exact outputs — no summarizing or paraphrasing.
- HOLD verdict if anything fails.
- Does not stage or commit.
