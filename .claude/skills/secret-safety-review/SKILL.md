---
name: secret-safety-review
description: Reviews staged or changed files for secret exposure, presence-only. Returns PASS or HOLD. Use before any commit or merge in OpenJarvis. Never prints secret values.
---

# Secret Safety Review

Review **staged or changed files** for secret exposure. Returns PASS or HOLD.

## Trigger
Use before any commit, merge, or PR in OpenJarvis.
Use when a file that could contain credentials is changed.

## Rules
- **Never print secret values.** Presence-only reporting only.
- Report file name + line number for any suspicious pattern.
- Do not suppress or ignore hits — report them all.

## Steps
1. Identify files to scan (staged files by default: `git diff --cached --name-only`).
2. Run keyword scan for: `api_key`, `secret`, `token`, `password`, `passwd`,
   `client_secret`, `private_key`, `BEGIN PRIVATE KEY`, `AKIA`, `ghp_`, `xox`,
   `sk-`, `eyJ` (JWT prefix).
3. Run high-entropy value scan for: AWS key format (`AKIA[0-9A-Z]{16}`),
   GitHub PAT (`ghp_`), Slack token (`xox[baprs]-`), long base64 (40+ chars),
   long hex (32+ chars), JWT (two dot-separated base64 segments 10+ chars each).
4. For each hit: report `filename:line_number` — never the matched value.

## Stop Conditions
- If any high-entropy value pattern is found → **HOLD immediately**.
- If any `.env` file content is staged → **HOLD immediately**.

## Report Format
```
SECRET SCAN RESULT: [PASS / HOLD]
Files scanned: [list]
Keyword hits: [filename:line — keyword type] (no values)
High-entropy value hits: [filename:line — pattern type] (no values)
Verdict: PASS (zero high-entropy values) | HOLD (see hits above)
```
