# /secret-scan

Run **changed-file secret scan** on staged or recently changed files.

## What this does
Runs the `secret-safety-review` skill on:
- Staged files: `git diff --cached --name-only`
- Or changed files: `git diff --name-only HEAD~1..HEAD`

## Rules
- **Never prints secret values.** Presence-only: file name + line number only.
- Reports ALL hits — keyword hits and high-entropy value hits separately.
- HOLD if any high-entropy secret value is found.
- HOLD if any `.env` file content is staged.

## Output
```
SECRET SCAN RESULT: [PASS / HOLD]
Files scanned: [list]
Keyword hits: [file:line — type] (no values)
High-entropy value hits: [file:line — type] (no values)
```
