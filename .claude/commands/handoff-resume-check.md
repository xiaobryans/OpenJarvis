# /handoff-resume-check

Verify crash-safe handoff state matches actual repo — safe to auto-resume?

## Usage
```
/handoff-resume-check
```

## What this does
1. Reads `docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md`.
2. Reads actual `git branch --show-current` and `git rev-parse HEAD`.
3. Reads `git status --short`.
4. Compares handoff state to actual repo state.
5. Checks `safe_to_continue_automatically` flag.
6. Prints `RESUME_FROM_HERE` section from the resume prompt.
7. Reports any discrepancies between handoff and actual state.

## When to use
- At the start of a new session to verify safe-to-continue before auto-proceeding.
- After any suspected crash or context compaction.
- When Bryan wants to verify the handoff before resuming.

## Output
```
HANDOFF RESUME CHECK
Branch: expected=[X] actual=[Y] — MATCH | MISMATCH
HEAD: expected=[X] actual=[Y] — MATCH | MISMATCH
Dirty files: PRE-EXISTING ONLY | UNEXPECTED DIRTY STATE
safe_to_continue_automatically: YES | NO
RESUME_FROM_HERE: [current phase / next step]
RECOMMENDATION: AUTO_RESUME_SAFE | MANUAL_REVIEW_REQUIRED
```
