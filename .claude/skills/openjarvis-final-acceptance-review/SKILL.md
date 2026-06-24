---
name: openjarvis-final-acceptance-review
description: Run the full OpenJarvis plan acceptance review — blocker closure audit, endpoint security, secret scan, test pass rate, Tauri status, Plan 1 regression, handoff completeness, quality score. Produces READY_FOR_REVIEW or HOLD. Use before presenting any plan to Bryan for acceptance.
---

# OpenJarvis Final Acceptance Review

Run this skill before presenting any plan for Bryan's acceptance review.

## When to use
- Before Bryan reviews a completed plan sprint.
- After all declared blockers are believed to be closed.
- After all tests pass (or pre-existing failures are documented).

## Inputs
- Current branch and HEAD (from `git branch --show-current`, `git rev-parse HEAD`)
- Sprint scope (from `CLAUDE.md` active plan section)
- Blocker registry (from session state or plan docs)
- Test results (from most recent test run)
- Fargate state (from `docs/plan2/PLAN2_AUTONOMOUS_SESSION_STATE.md` or live ECS query)

## Steps

1. **Invoke `no-skip-blocker-auditor` agent** — verify every declared blocker has explicit closure evidence.
2. **Invoke `endpoint-security-smoke-runner` agent** — verify all public endpoints are clean.
3. **Run `secret-safety-review` skill** — scan changed files for secret exposure.
4. **Check test pass rate** — confirm 80%+ passing; document pre-existing failures separately.
5. **Check Tauri status** — if Tauri rebuild was done: invoke `tauri-release-gate-reviewer`. If deferred: confirm deferred with reason.
6. **Run `checkpoint-regression` skill** — verify Plan 1 behaviors not regressed.
7. **Invoke `handoff-continuity-keeper` agent** — verify handoff files are current.
8. **Invoke `quality-score-reviewer` agent** — produce N/5 score.
9. **Produce final report** using `plan2-report` skill format.

## Safe commands
```bash
git branch --show-current
git rev-parse HEAD
git status --short
git diff --check
git log --oneline -10
python3 -m pytest tests/plan9/ -x --tb=short -q 2>&1 | tail -20
grep -r 'ya29\.\|sk-\|xoxb-\|ghp_' [changed files] || echo "CLEAN"
```

## Forbidden commands
- `aws secretsmanager get-secret-value` — prints secrets
- `git add .` or `git add -A` — never use
- Any command that reads OAuth token file contents
- Any command that prints `.env` file values

## Stop conditions
- Any blocker without explicit closure evidence → HOLD
- Secret scan hit → HOLD
- New test failure (sprint-introduced) → HOLD
- Quality score below 4/5 → HOLD
- Handoff files stale → warn and update before proceeding

## Output
Full 13-point sprint report per `CLAUDE.md` required format.
Verdict: `READY_FOR_REVIEW` or `HOLD`.
Do NOT mark ACCEPTED — only Bryan can do that.

## Examples
```
/plan-acceptance-review
```
