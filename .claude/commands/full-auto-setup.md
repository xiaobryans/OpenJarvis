# /full-auto-setup

Run the **full Claude Code automation foundation setup** sprint with action ledger.

## Usage
```
/full-auto-setup        — run or resume the full automation setup sprint
/full-auto-setup status — show current setup completion status
```

## What this does
1. Checks `docs/plan2/CLAUDE_AUTOMATION_SETUP.md` for current setup state.
2. Identifies any missing agents, skills, commands, hooks, or docs.
3. Creates missing items (setup files only — no feature code).
4. Runs changed-file validation (git status, diff --check, secret scan).
5. Maintains the action ledger for every step taken.
6. Stages only setup files using explicit paths (never `git add .`).
7. Reports full status for Bryan's approval before commit.

## Rules
- **Does NOT start Plan 2C.**
- **Does NOT rebuild Tauri.**
- **Does NOT run live cloud/OAuth/deployment actions.**
- **Does NOT stage unrelated dirty files.**
- **Does NOT mark anything ACCEPTED.**
- Uses explicit `git add <path>` only — never `git add .`
- Maintains full action ledger (`full-automation-ledger` skill).
- High-risk actions (staging, commit, push) require Bryan's approval or
  pre-granted sprint permission.

## Bypass Permission Mode
When bypass permission is active:
- All project hard rules from `CLAUDE.md` still apply.
- Claude may act autonomously within declared sprint scope.
- Action ledger is mandatory.
- Staging/commit/push are medium-risk and must be justified in the ledger.

## Output
- Setup completion checklist
- Action ledger
- Staged files list (for Bryan's review before commit)
- Verdict: READY_TO_COMMIT or HOLD
