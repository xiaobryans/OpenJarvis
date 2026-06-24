---
name: blocker-triage
description: Identify, categorize, and report Plan 2 blockers. Stops on the first blocker that prevents the current sprint from proceeding. Does not work around blockers — surfaces them clearly for Bryan.
---

# Blocker Triage

Identify, categorize, and report **Plan 2 blockers**. Stop on first hard blocker.

## Trigger
Use when a sprint encounters an obstacle, or to check the current blocker list
before starting a new sprint.

## Blocker Categories

### Hard Blockers (HOLD — cannot proceed without resolution)
- Missing credential / secret not present in env
- Auth logic broken or weakened
- Plan 1 checkpoint regressed
- Merge conflict in protected area
- Tauri rebuild required but deferred
- Feature requires deployment action not yet done (Fargate, vault, etc.)

### Soft Blockers (HOLD — document and report; may parallel-work around)
- Notion not configured (connector missing)
- Telegram env var mismatch
- Approval notification loop not wired
- Fargate worker not deployed

### Informational (continue with caveat)
- Unrelated dirty files present (do not stage)
- Matrix docs out of sync
- MCP connectors not configured

## Steps
1. Check for hard blockers in current sprint scope.
2. If hard blocker found → **HOLD immediately**; do not continue the sprint.
3. Classify all other blockers as soft or informational.
4. Update the blocker list against `CLAUDE.md` known blockers.
5. Report with resolution path for each blocker.

## Stop Conditions
- First hard blocker → **HOLD sprint, report full detail**.

## Output
```
BLOCKER TRIAGE: [CLEAR / HOLD]
Hard blockers: [none / list with resolution path]
Soft blockers: [none / list]
Informational: [none / list]
Sprint may proceed: [YES / NO — blocked by: ...]
```
