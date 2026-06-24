# /plan2-next

Show the **next Plan 2 task** based on current sprint state, blockers, and matrix.

## What this does
1. Reads `CLAUDE.md` for current locked plan state and blockers.
2. Reads `docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md` for completion status.
3. Identifies the next unblocked sprint task.
4. Reports current blockers that must be resolved first.
5. Suggests the appropriate skill or agent to use.

## Rules
- Do not start Plan 2C unless Bryan explicitly confirms.
- Do not start Plan 3 (voice/wake/TTS).
- Do not schedule Tauri rebuild.
- If all remaining tasks are blocked → report blockers, do not invent tasks.

## Output
```
CURRENT LOCKED STATE:
  [list of accepted checkpoints]

CURRENT BLOCKERS:
  [list from CLAUDE.md]

NEXT UNBLOCKED TASK:
  [task description]
  Skill: [skill name]
  Agent: [agent name]
  Files affected: [estimated scope]

BLOCKED TASKS (cannot start yet):
  [list with blocking reason]
```
