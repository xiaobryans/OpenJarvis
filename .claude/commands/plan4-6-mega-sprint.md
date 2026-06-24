# /plan4-6-mega-sprint

Plan the **Plan 4–6 mega-sprint** at a structural level (no implementation).

## Usage
```
/plan4-6-mega-sprint
/plan4-6-mega-sprint [specific plan — e.g. Plan 4, Plan 5, Plan 6]
```

## When to use
**ONLY** when Bryan explicitly asks to plan or prepare Plan 4–6.
Do NOT use during any Plan 2, post-Plan-2, or Plan 3 sprint.

## Pre-conditions checked
- Plan 2 must be accepted.
- Plan 3 (voice/wake/TTS) must remain parked.

## What this does
Runs `openjarvis-plan4-6-mega-sprint-planning` skill:
1. Decomposes Plan 4–6 goals into sequenced sub-sprints.
2. Produces file ownership maps per sub-sprint.
3. Identifies parallel vs sequential sub-sprints.
4. Produces risk register.
5. Identifies external pre-conditions (Apple account, App Store, etc.).
6. Writes output to `docs/automation/PLAN4_6_READINESS_CHECKLIST.md`.

## Output
- Planning document (no code changes).
- Summary of top 3 risks and recommended first sub-sprint.
- Bryan must explicitly approve before any Plan 4–6 implementation begins.

## Hard stops
- Does NOT implement any Plan 4–6 feature.
- Does NOT open Plan 3.
- Does NOT start iOS/App Store work without external pre-conditions verified.
