# /post-plan2-automation-status

Show full **post-Plan-2 automation expansion status** — inventory, sprint state, blockers.

## Usage
```
/post-plan2-automation-status
```

## What this does
1. Reads `docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md` — sprint phase, HEAD, blockers.
2. Reads `docs/automation/POST_PLAN2_AUTOMATION_MATRIX.md` — gap audit status.
3. Counts: agents, skills, commands, hooks (current vs pre-sprint).
4. Reports current sprint phase completion status.
5. Reports any remaining blockers.
6. Reports quality score if available.

## Output
```
POST-PLAN-2 AUTOMATION STATUS
Branch: localhost-get-tool
HEAD: [sha]
Sprint: POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION

Agents: [existing] + [new] = [total]
Skills: [existing] + [new] = [total]
Commands: [existing] + [new] = [total]
Hooks: [existing] + [new] = [total]

Phase completion:
  Phase 0 — Baseline: [status]
  Phase 1 — Gap audit: [status]
  ...

Blockers: [none | list]
Quality score: [N]/5 | NOT_YET_SCORED
Sprint verdict: [verdict or PENDING]
```
