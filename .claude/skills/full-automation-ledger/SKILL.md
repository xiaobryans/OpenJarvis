---
name: full-automation-ledger
description: Maintain and present the Claude Code action ledger for an OpenJarvis sprint. Use during any autonomous or bypass-permission sprint to document every meaningful action with justification, risk level, and result.
---

# Full Automation Action Ledger

Maintain and present the **Claude Code action ledger** for an OpenJarvis sprint.

## When to use
- Any sprint where bypass permission mode is enabled.
- Any autonomous sprint where Claude acts without per-action confirmation.
- At the end of any sprint as part of the final report.
- When `automation-auditor` agent requests a ledger review.

## Ledger Entry Format

For every meaningful action taken during a sprint, produce a row:

```
| Step | Action | Reason | Risk | Files | Command | Validation | Result | Bryan Approval? |
```

### Risk Levels
- **low** — read-only, doc changes, creating new files with no side effects
- **medium** — staging, committing, pushing, modifying existing files
- **high** — auth changes, token/connector changes, memory/routing changes,
  approval-gate changes, deployment/cloud, file deletion, hook activation,
  large refactors, anything that could expose secrets

### Bryan Approval Required = YES when
- Committing or pushing (unless explicitly granted for this sprint)
- Activating hooks
- Running cloud/deployment actions
- Any high-risk action not covered by sprint approval
- Any action outside declared sprint scope

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
- A partial ledger covering only some actions is HOLD — log all actions or flag gaps.

## Output
Present the complete ledger at the end of the sprint report, appended to the
13-point required format from `CLAUDE.md`.

Format:
```
## Action Ledger

| Step | Action | Reason | Risk | Files | Command | Validation | Result | Bryan Approval? |
|------|--------|--------|------|-------|---------|------------|--------|----------------|
| 1    | ...    | ...    | low  | ...   | ...     | ...        | ✓      | No             |
```
