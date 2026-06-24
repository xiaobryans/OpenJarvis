---
name: checkpoint-regression
description: Verify that all accepted Plan 1 and Plan 2 checkpoints have not regressed after a sprint. Use after any implementation sprint before generating the final report.
---

# Checkpoint Regression Check

Verify all **accepted checkpoints** have not regressed.

## Trigger
Use after any implementation sprint, before committing or reporting PASS.

## Checkpoints to verify (all required)

### Plan 1 Checkpoints
- [ ] **Jarvis PA identity** — responses identify as Jarvis, not generic Claude.
- [ ] **Normal chat speed** — cloud-first routing active, no degradation.
- [ ] **Cloud-first routing** — chat routes to cloud backend, not local fallback.
- [ ] **Unified memory search** — search returns results from SQLite + JarvisMemory.
- [ ] **Same-session continuity** — context preserved within a session.
- [ ] **Cmd+K history viewer** — opens read-only, does NOT dispatch actions.
- [ ] **Cmd+Shift+K command palette** — opens command palette (not history).

### Plan 2 Checkpoints (as completed)
- [ ] **Plan 2A** — mobile/MacBook-off parity status endpoint returns valid matrix.
- [ ] **Plan 2B** — connector/task parity matrix returned; no sensitive field leakage.
- [ ] **Claude Code baseline** — CLAUDE.md, agents, skills, commands present.

## Steps
1. For each checkpoint, identify the relevant code path or test.
2. Run the minimum smoke test that exercises the checkpoint.
3. Report PASS / REGRESSED per checkpoint with exact evidence.

## Stop Conditions
- Any checkpoint marked REGRESSED → **HOLD the sprint immediately**.

## Output
```
CHECKPOINT REGRESSION RESULT: [ALL PASS / HOLD]
Per-checkpoint results:
  - Jarvis PA identity: [PASS / REGRESSED / UNTESTABLE — reason]
  - [... all checkpoints ...]
Overall: [ALL PASS → proceed] | [HOLD → list regressed checkpoints]
```
