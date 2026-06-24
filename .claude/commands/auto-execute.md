# /auto-execute [prompt]

**Autonomous execution entry point.** Routes any prompt through the default
automation router and executes the full sprint lifecycle automatically.

## Usage
```
/auto-execute fix the Telegram env mismatch
/auto-execute implement Plan 2C connector parity for GitHub
/auto-execute validate current sprint and generate report
/auto-execute run takeover validation
```

## What this does
1. Invokes `default-automation-router` to classify the request.
2. Invokes `jarvis-plan-executor` to run the full lifecycle:
   classify → route → ownership → implement → validate → secret-check →
   stage → commit → push → report + action ledger.
3. Does NOT pause for routine approval — reports actions and justifications.
4. Stops only at hard-rule boundaries (see `CLAUDE.md`).

## Standing Permission
Bryan grants standing permission for autonomous repo work inside approved
OpenJarvis sprint scope. This command operates under that standing permission.

## Hard Stops (Claude will pause and ask Bryan)
- Request classified as out-of-scope
- Secret/credential exposure risk
- Destructive file operations
- Live cloud/OAuth/deployment actions
- Tauri rebuild required
- Locked roadmap state contradiction
- Auth/approval-gate weakening
- Unavoidable file ownership overlap
