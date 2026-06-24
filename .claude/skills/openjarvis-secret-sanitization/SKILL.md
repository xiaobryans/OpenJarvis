---
name: openjarvis-secret-sanitization
description: Deep secret audit of changed files, sprint docs, commit messages, and generated outputs — token prefixes, high-entropy strings, AWS credentials, private key markers, OAuth blobs. Presence-only reporting. Broader than secret-safety-review (also scans docs and commit history). Use after any sprint touching connectors, OAuth, or AWS config.
---

# OpenJarvis Secret Sanitization

Performs a **deep secret audit** beyond the standard changed-file scan.

## When to use
- After any sprint touching connector files, OAuth tokens, AWS config, or credentials.
- Before acceptance review for any plan that involves secrets migration.
- Periodically on the full repo if Bryan requests a broad audit.

## Scope (broader than secret-safety-review)
- All changed files (`git diff HEAD~1..HEAD --name-only`)
- All sprint docs (`docs/plan2/`, `docs/automation/`)
- Commit messages from this sprint (`git log [base]..HEAD --format=%s`)
- `PLAN2_AUTONOMOUS_SESSION_STATE.md` and `PLAN2_RESUME_PROMPT.md`
- Any script files added in this sprint

## Steps

1. **Invoke `secret-sanitization-auditor` agent** on the full scope.
2. Report file:line for any hit (never print the value).
3. Classify: CONFIRMED_SECRET | HIGH_ENTROPY_SUSPECT | FALSE_POSITIVE.
4. If CONFIRMED_SECRET or HIGH_ENTROPY_SUSPECT: HOLD immediately.

## Safe commands
```bash
git diff HEAD~1..HEAD --name-only
git log [base]..HEAD --format='%s'
grep -rn --include='*.md' --include='*.json' --include='*.py' --include='*.sh' \
  -E 'ya29\.|sk-|xoxb-|xoxp-|ghp_|github_pat_|AIza|AKIA|ASIA|-----BEGIN' \
  [path] 2>/dev/null | head -50
```

## Forbidden commands
- Never grep for values and print them — grep for patterns and report file:line only.
- Never run `cat` on `.env`, OAuth token JSON, or private key files.

## Output
```
DEEP SECRET SANITIZATION
[structured output from secret-sanitization-auditor agent]
VERDICT: CLEAN | HOLD
```
