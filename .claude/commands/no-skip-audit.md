# /no-skip-audit

Audit that **no blocker was quietly skipped** in the current sprint.

## Usage
```
/no-skip-audit
/no-skip-audit [plan name]
```

## What this does
Runs the `openjarvis-no-skip-blocker-closure` skill:
1. Reads declared blockers from `CLAUDE.md` and session state.
2. Reads sprint progress ledger for closure actions.
3. Invokes `no-skip-blocker-auditor` agent.
4. Verifies each blocker has: test name, live proof output, or code commit.
5. Flags any PARTIAL labeled as CLOSED.
6. Flags any PARKED blocker without a PARKED label.
7. Produces CLEAN | HOLD verdict.

## Output
```
NO-SKIP BLOCKER AUDIT
Declared blockers: [N]
Per blocker:
  [ID]: CLOSED | LIVE_PROVEN | PARTIAL | PARKED | HOLD
    Evidence: [specific proof]
OVERALL: CLEAN | HOLD
REQUIRED ACTION (if HOLD): [blocker ID and required evidence]
```

## Hard stops
- Any blocker without explicit evidence → HOLD.
- Any blocker missing from the closure table → HOLD.
- Never mark anything closed — only audit.
