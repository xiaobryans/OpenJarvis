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
| Delegation queue route | `src/openjarvis/server/delegation_routes.py` | **COMPLETE (B7 — fcf623d0)** | `tests/server/test_delegation_routes.py` (19) |
| Delegation queue UI | `frontend/src/pages/DelegationPage.tsx` | **COMPLETE (B7 — fcf623d0)** | — |
| System/connector status route | `src/openjarvis/server/system_status_routes.py` | **COMPLETE (B7 — fcf623d0)** | `tests/server/test_system_status_routes.py` (19) |

---

## Pillar 3 — Native iOS / Productization

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| PWA manifest | `src/openjarvis/server/static/manifest.webmanifest` | EXISTING (Plan 2) | — |
| PWA icons | `src/openjarvis/server/static/pwa-*.png` | EXISTING (Plan 2) | — |
| Mobile parity routes | `src/openjarvis/server/plan2_routes.py` | EXISTING (Plan 2) | — |
| Mobile proof page | `src/openjarvis/server/mobile_proof_page.py` | EXISTING (Plan 2) | — |
| Productization gate matrix | `src/openjarvis/server/productization_routes.py` | **COMPLETE (iOS truth fix sprint)** | `tests/server/test_productization_routes.py` |
| Desktop Tauri scaffold | `frontend/src-tauri/` | PRESENT — macOS/Windows/Linux only (`com.openjarvis.desktop`) | — |
| Native iOS scaffold | — | NOT_STARTED — iOS target not initialized; run `tauri ios init` | — |
| App Store submission | — | NOT_SUBMITTED — honest; external gate | — |

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
| Wired into Jarvis PA response | `src/openjarvis/server/frontdoor_routes.py` | **WIRED (B6 — bc5b8ea6)** | `tests/server/test_frontdoor_expert_roles.py` (11) |

---

## Pillar 6 — Unified UI/UX

| Component | File(s) | Status | Tests |
|-----------|---------|--------|-------|
| Frontend build | `src/openjarvis/server/static/` | EXISTING (Plan 2) | — |
| Rules manager UI | `frontend/src/pages/RulesManagerPage.tsx` | **COMPLETE (B5 — bc5b8ea6)** | — |
| Expert roles status UI | `frontend/src/pages/ExpertRolesPage.tsx` | **COMPLETE (B5 — bc5b8ea6)** | — |
| Capability/status panel | `frontend/src/pages/JarvisCapabilitiesPage.tsx` | **COMPLETE (B5 — bc5b8ea6; system status section added at fcf623d0)** | — |
| Delegation UI | `frontend/src/pages/DelegationPage.tsx` | **COMPLETE (B7 — fcf623d0)** | — |

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
| /v1/productization/status | GET | productization_routes | **Plan 4-6 B3 (bc5b8ea6)** |
| /v1/productization/ios | GET | productization_routes | **Plan 4-6 B3 (bc5b8ea6)** |
| /v1/productization/mobile | GET | productization_routes | **Plan 4-6 B3 (bc5b8ea6)** |
| /v1/frontdoor/submit | POST | frontdoor_routes (RoleSelector wired) | **Plan 4-6 B6 (bc5b8ea6)** |
| /v1/delegation/queue | GET | delegation_routes | **Plan 4-6 B7 (fcf623d0)** |
| /v1/delegation/queue/summary | GET | delegation_routes | **Plan 4-6 B7 (fcf623d0)** |
| /v1/system/status | GET | system_status_routes | **Plan 4-6 B7 (fcf623d0)** |

---

## Blocker Status

| ID | Blocker | Status | Closed At |
|----|---------|--------|-----------|
| B3 | Native iOS — Apple Dev Account (external gate) | CLOSED — productization gate matrix honest; Apple Dev Account is external, not a code blocker | bc5b8ea6 |
| B4 | Voice/TTS — Plan 3 | PARKED intentionally — not a Plan 4-6 blocker | — |
| B5 | UI surfaces for Plan 4-6 features | CLOSED — RulesManagerPage, ExpertRolesPage, JarvisCapabilitiesPage built | bc5b8ea6 |
| B6 | Expert role wiring into Jarvis PA response | CLOSED — RoleSelector wired into /v1/frontdoor/submit | bc5b8ea6 |
| B7 | Life-Business OS delegation queue UI | CLOSED — DelegationPage + delegation_routes + system_status_routes | fcf623d0 |

**No open Plan 4-6 code blockers.** Apple Developer Account enrollment is an external gate, not a code blocker.
