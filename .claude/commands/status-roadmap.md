# /status-roadmap

Show the **current OpenJarvis roadmap status**, locked checkpoints, and blockers.

## What this does
Reads `CLAUDE.md` and `docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md` to produce:
1. Locked checkpoint states (accepted plans).
2. Active plan and scope summary.
3. Current Plan 2 blockers.
4. Next unblocked task (if any).
5. Parked items (Plan 3 voice/TTS, Tauri rebuild).

## Rules
- Read-only — does not modify anything.
- Does not start any plan or sprint.
- Does not claim acceptance of any checkpoint.
- Reports current state exactly as documented.

## Output
```
ROADMAP STATUS — [date]

LOCKED:
  ✓ PLAN_1_DUAL_PLATFORM_JARVIS_NEURAL_COMMAND_CENTER_ACCEPTED
  ✓ PLAN_2A_MOBILE_MACBOOK_OFF_FOUNDATION_ACCEPTED_PENDING_FINAL_TAURI_REBUILD
  ✓ PLAN_2B_CONNECTOR_TASK_PARITY_FOUNDATION_ACCEPTED_PENDING_FINAL_TAURI_REBUILD
  ✓ CLAUDE_CODE_BASELINE_SETUP_ACCEPTED

ACTIVE: Plan 2 — Full Mobile MacBook-Off Parity Runtime

BLOCKERS: [list]

PARKED: Plan 3 voice/TTS | Tauri rebuild

NEXT TASK: [task or "all remaining tasks blocked — see BLOCKERS"]
```
