# Post-Plan-2 Automation Expansion — Resume Prompt

Use this file to resume the post-Plan-2 automation expansion sprint after a session break.

## RESUME_FROM_HERE

**Branch:** `localhost-get-tool`
**Remote:** `fork/xiaobryans/OpenJarvis`
**Sprint:** `POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION`
**Base HEAD:** `d34d7c82` (Plan 2 final cutover gate)
**Locked plan state:** `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_ACCEPTED`

## Hard Rules (active for this sprint)
- No Tauri rebuild, no Plan 3, no Plan 4–6 implementation
- No `git add .` — explicit file staging only
- No secret values printed
- No fake ACCEPTED/READY
- Do not stage: `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py`, `evidence/`, `scripts/plan1_cockpit_proof.py`, `scripts/plan9_copy_cloud_api_key.sh`, `scripts/plan9_verify_cloud_api_key.py`

## What was done in this sprint

1. **Phase 0:** Repo state verified. Branch, HEAD, remote, dirty files, and automation inventory all confirmed.
2. **Phase 1:** Automation gap audit complete. 14 agent gaps, 11 skill gaps, 14 command gaps, 4 hook gaps identified and documented in `POST_PLAN2_AUTOMATION_MATRIX.md`.
3. **Phase 2:** 14 new agents created in `.claude/agents/`.
4. **Phase 3:** 11 new skills created in `.claude/skills/`.
5. **Phase 4:** 14 new commands created in `.claude/commands/`.
6. **Phase 5:** 4 new hooks created in `.claude/hooks/` + `settings.json` updated.
7. **Phase 6:** Crash-resume guide created at `docs/automation/CRASH_RESUME_GUIDE.md`.
8. **Phase 7:** MCP/plugin expansion plan created at `docs/automation/MCP_PLUGIN_EXPANSION_PLAN.md`.
9. **Phase 8:** Plan 4–6 readiness checklist created at `docs/automation/PLAN4_6_READINESS_CHECKLIST.md`.
10. **Phase 9:** Validation pending (see below).
11. **Phase 10:** Handoff docs updated.
12. **Phase 11:** Commit/push pending.

## Pending (if resuming)

### Phase 9 — Validation
Run:
```bash
git status --short
git diff --check
# Check no unrelated files staged
# Run secret scan on changed files
# Check hook syntax
# Verify agent/skill/command discoverability
```

### Phase 11 — Commit/push
Stage ONLY the sprint-scope files (explicit list in `POST_PLAN2_AUTOMATION_PROGRESS_LEDGER.md`).
Commit: `Post-Plan-2 Claude Code automation expansion`
Push: `fork localhost-get-tool`

## Sprint verdict (target)
`POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION_READY_FOR_REVIEW`

## Do NOT
- Mark as accepted (only Bryan can accept)
- Start Plan 3
- Start Plan 4–6 implementation
- Stage unrelated dirty files
- Read or print secret values
