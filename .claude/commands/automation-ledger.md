# /automation-ledger

Show or audit the **Claude Code action ledger** for the current sprint.

## Usage
```
/automation-ledger          — show ledger for current sprint
/automation-ledger audit    — run automation-auditor agent on current sprint
/automation-ledger reset    — start a fresh ledger (new sprint)
```

## What this does
Invokes the `full-automation-ledger` skill:
1. Presents the current sprint action ledger (all steps logged so far).
2. Identifies any unlogged actions (gaps in the ledger).
3. Flags any high-risk actions without justification.
4. Reports overall: PASS (all logged) or HOLD (unlogged/unjustified actions).

With `audit`: runs `automation-auditor` agent for independent review.

## Rules
- **No fabricated entries** — every entry must reflect a real action.
- Bypass permission mode does not remove ledger requirements.
- High-risk actions (auth, connectors, staging/commit/push, hook activation)
  must have explicit justification written before the action was taken.
- Do not print secret values in any ledger entry.

## Output
Full action ledger table with verdict: PASS or HOLD.
