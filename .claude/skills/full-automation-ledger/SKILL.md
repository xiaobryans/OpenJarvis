---
name: full-automation-ledger
description: Maintain and present the Claude Code action ledger for an OpenJarvis sprint. Use during any autonomous or bypass-permission sprint to document every meaningful action with justification, risk level, and result.
---

# Full Automation Action Ledger

Maintain and present the **Claude Code action ledger** for an OpenJarvis sprint.

## When to use
- Any sprint where bypass permission mode is enabled.
- Any autonomous sprint (`DEFAULT_AUTONOMOUS_EXECUTION_MODE`).
- At the end of any sprint as part of the final report.
- When `automation-auditor` agent requests a ledger review.

## Approval Model

### Routine scoped actions — proceed without prior approval
Actions inside the approved sprint scope do NOT require per-action Bryan approval.
Proceed, then record the action in the ledger with justification after.

Routine scoped actions include:
- File reads, edits, and writes within declared file ownership scope
- Validation commands (git status, git diff --check, tsc, vite build, tests)
- Secret scans (presence-only, no values printed)
- Staging explicit files within sprint scope
- Committing and pushing when inside approved sprint scope
- Agent/skill/command invocations
- Worktree creation for approved parallel work
- Doc/matrix updates triggered by sprint scope

### High-risk / out-of-scope actions — require prior Bryan approval
Stop and ask Bryan BEFORE performing:
- Auth or approval-gate changes
- Connector/token/OAuth changes (if outside declared scope)
- Memory or routing changes
- Cloud/deployment actions
- File deletion
- Actions outside declared sprint scope
- Anything that could expose, print, or read secret values

## Ledger Entry Format

For every meaningful action, produce a row:

```
| Step | Action | Reason | Risk | Files | Command | Validation | Result | Bryan Approval? |
```

### Risk Levels
- **low** — read-only, doc changes, creating new files, validation, scans
- **medium** — staging, committing, pushing, modifying existing files,
  worktree creation — **pre-approved when inside sprint scope**
- **high** — auth changes, token/connector changes, memory/routing changes,
  approval-gate changes, deployment/cloud, file deletion, hook activation,
  large refactors, anything that could expose secrets

### Bryan Approval Required = YES when
- Action is outside declared sprint scope
- Risk class is `high` AND not covered by sprint approval
- Action may expose secret/credential values
- Action is destructive

### Bryan Approval Required = NO when
- Inside approved sprint scope (standing permission applies)
- Medium-risk staging/commit/push within scope
- Any validation, scan, or doc update within scope

## High-Risk Action Protocol
For any high-risk action, write the justification **before** performing it:

```
[HIGH-RISK ACTION — Step N]
Action: [description]
Justification: [why this is necessary and safe]
Risk: HIGH
Files affected: [list]
Alternative considered: [what else was considered]
Proceeding because: [sprint approval / Bryan explicit approval / specific rule]
```

## Ledger Rules
- **No fabricated entries.** Every entry must reflect an actual action taken.
- **No skipping high-risk justification.** HOLD if it was skipped.
- **Do not print secret values** in any ledger entry.
- Bypass permission mode does not remove ledger requirements.
- Staged/committed files must be explicitly listed in the ledger.
- A partial ledger covering only some actions is HOLD — log all or flag gaps.

## Output
Present the complete ledger at the end of the sprint report, appended to the
13-point required format from `CLAUDE.md`.

Format:
```
## Action Ledger

| Step | Action | Reason | Risk | Files | Command | Validation | Result | Bryan Approval? |
|------|--------|--------|------|-------|---------|------------|--------|----------------|
| 1    | Read current state | Verify before editing | low | CLAUDE.md | Read | n/a | ✓ | No (in scope) |
| 2    | Create router agent | Sprint scope item | low | default-automation-router.md | Write | No secrets | ✓ | No (in scope) |
| 9    | Stage 5 files | Commit sprint scope | medium | [explicit list] | git add [paths] | Staged list verified | ✓ | No (standing perm) |
```
