# /crash-resume

Verify crash-resume safety and show the `RESUME_FROM_HERE` prompt.

## Usage
```
/crash-resume
```

## When to use
- At the start of a new session after a suspected crash or context compaction.
- When Bryan wants to verify it's safe to auto-resume without manual review.

## What this does
Runs the `openjarvis-handoff-continuity` skill check:
1. Reads `docs/automation/POST_PLAN2_AUTOMATION_RESUME_PROMPT.md` and `POST_PLAN2_AUTOMATION_SESSION_STATE.md`.
2. Verifies actual git state matches handoff state (branch, HEAD, dirty files).
3. Checks `safe_to_continue_automatically` flag.
4. If SAFE: prints the `RESUME_FROM_HERE` section and recommends auto-continue.
5. If NOT SAFE: prints the blockers and requires manual Bryan review.

## Manual fallback
If no automation is available:
1. Open new Claude Code chat.
2. Paste contents of `docs/automation/POST_PLAN2_AUTOMATION_RESUME_PROMPT.md`.
3. Run `/handoff-resume-check` to verify state.
4. Resume from the `RESUME_FROM_HERE` marker.

## Output
```
CRASH-RESUME CHECK
Branch: [name] — MATCH | MISMATCH
HEAD: [sha] — MATCH | MISMATCH
Dirty files: PRE-EXISTING | UNEXPECTED
safe_to_continue_automatically: YES | NO
RECOMMENDATION: AUTO_RESUME_SAFE | MANUAL_REVIEW_REQUIRED

RESUME_FROM_HERE:
[current phase and next step from resume prompt]
```
