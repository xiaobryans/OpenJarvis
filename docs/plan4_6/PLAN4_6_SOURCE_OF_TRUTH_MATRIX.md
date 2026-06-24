# Plan 4–6 Source of Truth Matrix

**Sprint:** `PLAN_4_6_MEGA_SPRINT_TEXT_FIRST_JARVIS_OS`
**Date:** 2026-06-25

---

## Pillar 1 — Skills / Rules / Third-Party Skill Intake

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| Skill registry | `src/openjarvis/skills/jarvis_registry.py` | EXISTING — VERIFIED | `tests/skills/test_skill_registry.py` |
| Skill manager | `src/openjarvis/skills/manager.py` | EXISTING — VERIFIED | `tests/skills/test_manager.py` |
| Skill intake (third-party) | `src/openjarvis/skills/intake.py` | EXISTING — API endpoint added | `tests/skills/test_plan1_intake.py` |
| Skills API — list/get | `src/openjarvis/server/skills_routes.py` | EXISTING | — |
| Skills API — enable/disable | `src/openjarvis/server/skills_routes.py` | **NEW (Sprint 4-6)** | — |
| Skills API — intake validate | `src/openjarvis/server/skills_routes.py` | **NEW (Sprint 4-6)** | — |
| **Rules engine** | `src/openjarvis/rules/` | **NEW (Sprint 4-6)** | `tests/rules/test_rules_engine.py` (44) |
| Rules API | `src/openjarvis/server/rules_routes.py` | **NEW (Sprint 4-6)** | `tests/server/test_rules_routes.py` (22) |

---

## Pillar 2 — Life-Business OS + Trusted Delegation

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| Personal OS (tasks/reminders) | `src/openjarvis/jarvis_os/personal_os.py` | EXISTING — VERIFIED | `tests/server/test_plan7_phase_c_life_os.py` |
| Life OS routes | `src/openjarvis/server/life_os_routes.py` | EXISTING | — |
| Goals routes | `src/openjarvis/server/goals_routes.py` | EXISTING | — |
| Authority tiers (6-tier model) | `src/openjarvis/authority/tiers.py` | EXISTING (Plan 8) | `tests/test_plan8_authority.py` |
| Approval engine | `src/openjarvis/authority/approval_engine.py` | EXISTING (Plan 8) | `tests/server/test_approval_routes.py` |
| Authority routes (full) | `src/openjarvis/server/authority_routes.py` | EXISTING (Plan 8) | — |
| Delegation queue UI | — | NOT_BUILT — OPEN (B6) | — |

---

## Pillar 3 — Native iOS / Productization

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| PWA manifest | `src/openjarvis/server/static/manifest.webmanifest` | EXISTING (Plan 2) | — |
| PWA icons | `src/openjarvis/server/static/pwa-*.png` | EXISTING (Plan 2) | — |
| Mobile parity routes | `src/openjarvis/server/plan2_routes.py` | EXISTING (Plan 2) | — |
| Mobile proof page | `src/openjarvis/server/mobile_proof_page.py` | EXISTING (Plan 2) | — |
| Native iOS app | — | NOT_STARTED — B3 (Apple Dev Account) | — |

---

## Pillar 4 — Chat Intelligence + Self-Knowledge

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| Intelligence/trust | `src/openjarvis/intelligence/` | EXISTING | — |
| **Self-knowledge routes** | `src/openjarvis/server/self_knowledge_routes.py` | **NEW (Sprint 4-6)** | `tests/server/test_self_knowledge_routes.py` (9) |
| Capability status endpoint | `/v1/jarvis/capabilities` | **NEW (Sprint 4-6)** | — |
| Jarvis status endpoint | `/v1/jarvis/status` | **NEW (Sprint 4-6)** | — |
| Roadmap endpoint | `/v1/jarvis/roadmap` | **NEW (Sprint 4-6)** | — |

---

## Pillar 5 — Expert Role Orchestration

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| Capability registry | `src/openjarvis/orchestrator/capability_registry.py` | EXISTING | `tests/orchestrator/test_capability_registry.py` |
| Worker registry | `src/openjarvis/orchestrator/worker_registry.py` | EXISTING | — |
| **Expert role registry** | `src/openjarvis/orchestrator/expert_roles.py` | **NEW (Sprint 4-6)** | `tests/rules/test_expert_roles.py` |
| **Expert roles routes** | `src/openjarvis/server/expert_roles_routes.py` | **NEW (Sprint 4-6)** | — |
| RoleSelector | `src/openjarvis/orchestrator/expert_roles.py` | **NEW (Sprint 4-6)** | — |
| Wired into Jarvis PA response | — | NOT_WIRED — next sprint | — |

---

## Pillar 6 — Unified UI/UX

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| Frontend build | `src/openjarvis/server/static/` | EXISTING (Plan 2) | — |
| Rules manager UI | — | NOT_BUILT — next sprint | — |
| Expert roles status UI | — | NOT_BUILT — next sprint | — |
| Capability/status panel | — | NOT_BUILT — next sprint | — |
| Life-OS dashboard | — | PARTIAL — API exists, UI partial | — |

---

## API Route Matrix

| Route | Method | Module | Sprint |
|-------|--------|--------|--------|
| /v1/skills | GET | skills_routes | Plan 1 |
| /v1/skills/{id} | GET | skills_routes | Plan 1 |
| /v1/skills/{id}/enable | POST | skills_routes | **Plan 4-6** |
| /v1/skills/{id}/disable | POST | skills_routes | **Plan 4-6** |
| /v1/skills/intake/validate | POST | skills_routes | **Plan 4-6** |
| /v1/rules | GET, POST | rules_routes | **Plan 4-6** |
| /v1/rules/stats | GET | rules_routes | **Plan 4-6** |
| /v1/rules/evaluate | POST | rules_routes | **Plan 4-6** |
| /v1/rules/{id} | GET, PATCH, DELETE | rules_routes | **Plan 4-6** |
| /v1/rules/{id}/activate | POST | rules_routes | **Plan 4-6** |
| /v1/rules/{id}/deactivate | POST | rules_routes | **Plan 4-6** |
| /v1/expert-roles | GET | expert_roles_routes | **Plan 4-6** |
| /v1/expert-roles/stats | GET | expert_roles_routes | **Plan 4-6** |
| /v1/expert-roles/select | POST | expert_roles_routes | **Plan 4-6** |
| /v1/expert-roles/{id} | GET | expert_roles_routes | **Plan 4-6** |
| /v1/expert-roles/{id}/activate | POST | expert_roles_routes | **Plan 4-6** |
| /v1/expert-roles/{id}/deactivate | POST | expert_roles_routes | **Plan 4-6** |
| /v1/jarvis/capabilities | GET | self_knowledge_routes | **Plan 4-6** |
| /v1/jarvis/status | GET | self_knowledge_routes | **Plan 4-6** |
| /v1/jarvis/roadmap | GET | self_knowledge_routes | **Plan 4-6** |
| /v1/life-os/tasks | GET, POST | life_os_routes | Plan 2 |
| /v1/life-os/approvals/pending | GET | life_os_routes | Plan 2 |
| /v1/authority/status | GET | authority_routes | Plan 8 |
| /v1/authority/approvals/pending | GET | authority_routes | Plan 8 |
| /v1/authority/tiers | GET | authority_routes | Plan 8 |

---

## Open Blockers

| ID | Blocker | Severity | Next Action |
|----|---------|----------|-------------|
| B3 | Native iOS — Apple Dev Account required | HIGH | Bryan must confirm enrollment |
| B5 | UI surfaces for Plan 4-6 features | MEDIUM | Next sprint |
| B6 | Expert role wiring into Jarvis PA response | MEDIUM | Next sprint |
