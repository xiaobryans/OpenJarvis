# /checkpoint-regression

Verify all **accepted Plan 1 and Plan 2 checkpoints** have not regressed.

## What this does
Runs the `checkpoint-regression` skill:
1. Checks all Plan 1 checkpoints (Jarvis identity, chat speed, routing,
   memory search, session continuity, Cmd+K, Cmd+Shift+K).
2. Checks Plan 2 checkpoints (parity endpoint, connector matrix, baseline setup).
3. Runs minimum smoke tests for each checkpoint.
4. Reports PASS or REGRESSED per checkpoint.

## Rules
- HOLD on first regressed checkpoint — do not continue the sprint.
- Report exact evidence per checkpoint (not just "looks fine").
- Does not fake PASS for untested checkpoints — reports UNTESTABLE with reason.

## Output
Per-checkpoint PASS / REGRESSED / UNTESTABLE with evidence.
Overall: ALL PASS or HOLD.
