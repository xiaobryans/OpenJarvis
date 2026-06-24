# /secret-scan-deep

Run a **deep secret scan** — broader than `/secret-scan`, covers docs and commit messages too.

## Usage
```
/secret-scan-deep
/secret-scan-deep [path]
```

## What this does
Runs the `openjarvis-secret-sanitization` skill:
1. Scans all changed files (git diff HEAD~1..HEAD).
2. Scans all sprint docs (`docs/plan2/`, `docs/automation/`).
3. Scans commit messages from this sprint.
4. Scans any script files added this sprint.
5. Pattern checks: token prefixes (ya29., sk-, xoxb-, ghp_, AIza, AKIA), high-entropy strings, private key markers, OAuth blobs.
6. Reports file:line for each hit — NEVER prints the value.
7. Classifies: CONFIRMED_SECRET | HIGH_ENTROPY_SUSPECT | FALSE_POSITIVE.

## Difference from `/secret-scan`
- `/secret-scan` covers only staged/changed code files.
- `/secret-scan-deep` also covers docs, commit messages, and script files.

## Output
```
DEEP SECRET SANITIZATION
Files scanned: [N]
Token prefix hits: [N] — CLEAN | HOLD
High-entropy suspects: [N] — CLEAN | NEEDS_REVIEW
VERDICT: CLEAN | HOLD
```
