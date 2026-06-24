# Plan 4–6 Mega Sprint — Resume Prompt

**RESUME_FROM_HERE**

---

## Context

You are resuming the `PLAN_4_6_MEGA_SPRINT_TEXT_FIRST_JARVIS_OS` sprint for OpenJarvis.

**Branch:** `localhost-get-tool`
**Remote:** `fork/xiaobryans/OpenJarvis`
**Expected HEAD after commit:** see `PLAN4_6_SESSION_STATE.md`

## Locked Accepted State (do NOT reopen)
- Plan 1: ACCEPTED
- Plan 2: ACCEPTED
- Post-Plan-2 Automation: ACCEPTED
- Plan 3 Voice/TTS: PARKED (do not start)

## What Was Already Done in This Session

### New code:
- `src/openjarvis/rules/` — Rules engine (types, registry, engine, __init__)
- `src/openjarvis/orchestrator/expert_roles.py` — ExpertRoleRegistry + 10 builtin roles + RoleSelector
- `src/openjarvis/server/rules_routes.py` — /v1/rules/* REST API (CRUD + evaluate)
- `src/openjarvis/server/expert_roles_routes.py` — /v1/expert-roles/* REST API
- `src/openjarvis/server/self_knowledge_routes.py` — /v1/jarvis/capabilities, /v1/jarvis/status, /v1/jarvis/roadmap
- `src/openjarvis/server/skills_routes.py` — extended with enable/disable, intake/validate
- `src/openjarvis/server/app.py` — registered 3 new routers
- `tests/rules/` — 44 tests (all pass)
- `tests/server/test_rules_routes.py` — 22 tests (all pass)
- `tests/server/test_self_knowledge_routes.py` — 9 tests (all pass)
- `docs/plan4_6/` — all 5 handoff docs

### Tests:
- 75 new tests all pass
- 5 pre-existing failures confirmed unchanged

## What Remains (in priority order)

1. **Commit** — stage and commit the sprint work
2. **UI/UX surfaces** — add frontend routes/pages for rules manager, expert roles status, Jarvis capability panel
3. **Life-Business OS delegation queue UI** — frontend for delegation/approval queue
4. **Mobile/iOS PWA polish** — update manifest, onboarding, mobile viewport
5. **Expert role orchestration wiring** — wire RoleSelector into the Jarvis PA response path
6. **Resolve B3** — confirm Apple Developer Account enrollment before any native iOS work

## Hard-Stop Rules
1. Never print secret values
2. Never read .env / OAuth / credential files for contents
3. Never stage unrelated dirty files (JARVIS_OMNIX_HANDOFF.md, tests/workbench/test_us14a_fixture.py, evidence/, scripts/plan1_*)
4. Do NOT start Plan 3 voice/TTS
5. Do NOT mark accepted — only Bryan can

## Files to Stage (explicit only)
```
src/openjarvis/rules/__init__.py
src/openjarvis/rules/types.py
src/openjarvis/rules/registry.py
src/openjarvis/rules/engine.py
src/openjarvis/orchestrator/expert_roles.py
src/openjarvis/server/rules_routes.py
src/openjarvis/server/expert_roles_routes.py
src/openjarvis/server/self_knowledge_routes.py
src/openjarvis/server/skills_routes.py
src/openjarvis/server/app.py
tests/rules/__init__.py
tests/rules/test_rules_engine.py
tests/rules/test_expert_roles.py
tests/server/test_rules_routes.py
tests/server/test_self_knowledge_routes.py
docs/plan4_6/PLAN4_6_SESSION_STATE.md
docs/plan4_6/PLAN4_6_PROGRESS_LEDGER.md
docs/plan4_6/PLAN4_6_RESUME_PROMPT.md
docs/plan4_6/PLAN4_6_SOURCE_OF_TRUTH_MATRIX.md
docs/plan4_6/plan4_6_matrix.json
```
