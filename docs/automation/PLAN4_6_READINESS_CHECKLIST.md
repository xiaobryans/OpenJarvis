# Plan 4–6 Readiness Checklist

**Sprint:** POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION
**Status:** PLANNING ONLY — no implementation
**Date:** 2026-06-25

This document prepares the readiness scaffolding for the later Plan 4–6 mega-sprint.
Bryan must explicitly authorize Plan 4–6 before any implementation begins.

---

## Plan 4–6 Scope Summary

| Plan | Theme | Key deliverables |
|------|-------|-----------------|
| Plan 4 | Skills / Rules / Third-Party Skill Intake | Skill registry, rule engine, third-party skill vetting |
| Plan 5 | Life-Business OS + Trusted Delegation + Native iOS App | Life-OS features, delegation framework, iOS native app, App Store |
| Plan 6 | Chat Intelligence + Self-Knowledge + Expert Role Orchestration + UI/UX Polish | Intelligence layer, expert agent orchestration, unified Jarvis UI |

---

## Pre-Conditions Before Plan 4–6 Can Begin

| Pre-condition | Status | Who resolves |
|--------------|--------|-------------|
| Plan 2 accepted | ACCEPTED | Bryan (complete) |
| Plan 3 parked decision confirmed | CONFIRMED (parked) | Bryan |
| Apple Developer Account active | UNKNOWN — Bryan must verify | Bryan |
| iOS device for testing | UNKNOWN — Bryan must specify | Bryan |
| App Store enrollment decision | UNKNOWN — TestFlight vs App Store vs enterprise | Bryan |
| Cloud infrastructure budget approved for Plan 5 | UNKNOWN — cost estimate needed | Bryan |
| Legal review of delegation framework | UNKNOWN — trusted delegation has legal implications | Bryan |
| Third-party skill intake security policy | UNKNOWN — needs vetting framework | Claude + Bryan |

---

## Plan 4 — Skills / Rules / Third-Party Skill Intake

### Sub-sprints

| # | Sprint | File Ownership | Dependencies | Acceptance Criteria |
|---|--------|---------------|-------------|---------------------|
| 4.1 | Skill registry design | `src/openjarvis/skills/`, `docs/skills/` | Plan 2 complete | Skills can be registered, listed, and invoked by name |
| 4.2 | Rule engine foundation | `src/openjarvis/rules/` | 4.1 complete | Rules can be defined and evaluated against context |
| 4.3 | Third-party skill intake vetting | `.claude/skills/intake/` policy docs | 4.1 complete | Vetting checklist exists; unsafe skills are rejected |
| 4.4 | Skill invocation in Jarvis PA flow | `src/openjarvis/jarvis_brain/` | 4.1, 4.2 | Jarvis PA can invoke skills contextually |

### Acceptance Checklist (Plan 4)
- [ ] Skill registry with CRUD operations
- [ ] Rule engine with at least 3 rule types
- [ ] Vetting checklist for third-party skills (safety, secret exposure, prompt injection)
- [ ] Jarvis PA can invoke a skill from chat
- [ ] 80%+ test pass rate
- [ ] Secret scan CLEAN
- [ ] Plan 1 regression PASS
- [ ] Quality score 4/5+

### Risk Register (Plan 4)
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Third-party skill prompt injection | HIGH | Mandatory vetting checklist; sandbox invocation |
| Skill conflicts with existing Jarvis behavior | MEDIUM | Conflict resolution in rule engine |
| Scope creep into Plan 5/6 features | LOW | Strict file ownership boundaries |

---

## Plan 5 — Life-Business OS + Trusted Delegation + Native iOS App

### Sub-sprints

| # | Sprint | File Ownership | Dependencies | Acceptance Criteria |
|---|--------|---------------|-------------|---------------------|
| 5.1 | Life-OS feature expansion | `src/openjarvis/jarvis_os/` | Plan 2 life-os cloud sync proven | Calendar, tasks, reminders integrated with Jarvis PA |
| 5.2 | Trusted delegation framework | `src/openjarvis/delegation/` | 5.1, rule engine (4.2) | Bryan can delegate actions to Jarvis with explicit authority boundaries |
| 5.3 | iOS native app foundation | `ios/`, `src-tauri/` (if Tauri-iOS) | Apple Developer Account | iOS app builds and connects to Fargate backend |
| 5.4 | App Store submission | Build artifacts, signing | 5.3 + Apple enrollment | App passes App Store review guidelines |
| 5.5 | Productization | `docs/product/`, user-facing docs | 5.1–5.4 | Product is installable by non-developer user |

### Acceptance Checklist (Plan 5)
- [ ] Life-OS features working on mobile and desktop
- [ ] Trusted delegation: Bryan can set authority boundaries and confirm delegated actions
- [ ] iOS app connects to Fargate API with auth
- [ ] App Store: TestFlight distribution working OR App Store submission approved
- [ ] Productization: one-click install for non-developer users
- [ ] Approval gate NOT weakened by delegation framework
- [ ] Quality score 4/5+

### Risk Register (Plan 5)
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Apple App Store rejection | HIGH | Test with TestFlight first; no external interpreter rule compliance |
| Delegation framework bypasses approval gates | HIGH | Delegated actions still require approval gates; delegation only expands scope within bounds |
| iOS development environment setup | MEDIUM | Bryan must have Xcode + Apple Developer Account before 5.3 starts |
| iOS Tauri build complexity | HIGH | Evaluate Tauri iOS vs React Native vs SwiftUI native before committing |

---

## Plan 6 — Chat Intelligence + Expert Role Orchestration + UI/UX Polish

### Sub-sprints

| # | Sprint | File Ownership | Dependencies | Acceptance Criteria |
|---|--------|---------------|-------------|---------------------|
| 6.1 | Chat intelligence layer | `src/openjarvis/jarvis_brain/` | Plan 2 memory/routing accepted | Jarvis proactively suggests, not just reacts |
| 6.2 | Self-knowledge system | `src/openjarvis/self_knowledge/` | 6.1 | Jarvis knows its own capabilities, history, and context |
| 6.3 | Expert role orchestration | `.claude/agents/` expansion | 4.1 (skills), 6.1 | Jarvis automatically invokes expert agents for specialized tasks |
| 6.4 | Unified Jarvis UI/UX | `src/`, frontend | 5.3 or desktop-only | UI is polished, consistent, and represents the real Jarvis end-goal |
| 6.5 | Product interface polish | All UI files | 6.4 | Product feels like a real, shippable product |

### Acceptance Checklist (Plan 6)
- [ ] Chat intelligence: Jarvis proactively surfaces relevant context
- [ ] Self-knowledge: Jarvis can answer "what can you do?" accurately
- [ ] Expert orchestration: automatic agent routing works for at least 3 expert domains
- [ ] UI/UX polish: `ui-ux-product-reviewer` passes all components
- [ ] Jarvis PA identity: single unified voice throughout
- [ ] Quality score 5/5 for final release

### Risk Register (Plan 6)
| Risk | Severity | Mitigation |
|------|----------|-----------|
| Chat intelligence adds latency | HIGH | Progressive enhancement; intelligence layer optional fallback |
| Expert orchestration confused by ambiguous prompts | MEDIUM | Clear handoff protocol between agents; Bryan disambiguation request |
| UI/UX polish scope creep | MEDIUM | Strict definition of "done" per component; `ui-ux-product-reviewer` gate |

---

## Acceptance Review Template (per Plan 4–6 sub-sprint)

```
PLAN [N.N] ACCEPTANCE REVIEW

Verdict: READY_FOR_REVIEW | HOLD
Sprint: [name]
Branch: [name]
HEAD: [sha]

Checklist:
  1. Blocker closure: PASS | HOLD — [evidence]
  2. Test pass rate: [N]/[total] — PASS | HOLD
  3. Secret scan: CLEAN | HOLD
  4. Endpoint security: PASS | HOLD
  5. Tauri/iOS build: PASS | HOLD | NOT_APPLICABLE
  6. Plan 1 regression: PASS | HOLD
  7. UI/UX polish (if UI changed): PASS | NEEDS_POLISH
  8. Handoff files: CURRENT | STALE
  9. Quality score: [N]/5 — PASS | HOLD
 10. No fake PASS: CONFIRMED | VIOLATION

Gaps: [list]
Required fixes before acceptance: [list]

Do NOT mark ACCEPTED — only Bryan can do that.
```

---

## Blocker Matrix Template (per Plan 4–6 plan)

| ID | Blocker | Plan | Status | Evidence | Remaining Gap |
|----|---------|------|--------|----------|---------------|
| B[N] | [description] | Plan [N] | OPEN | N/A | [what's needed] |

---

## Expert Orchestration Checklist

Before shipping expert role orchestration (Plan 6.3):
- [ ] Each expert agent has clear purpose, boundaries, trigger conditions, and output format
- [ ] No expert agent can weaken auth or approval gates
- [ ] No expert agent can print secret values
- [ ] No expert agent can mark acceptance
- [ ] Expert routing does not create infinite loops
- [ ] Expert handoff back to Jarvis PA is clean (one unified voice)
- [ ] Expert agents are tested with adversarial inputs (prompt injection, ambiguous goals)

---

## Mobile/iOS Productization Checklist

Before iOS/App Store submission:
- [ ] Apple Developer Account enrolled and active
- [ ] Xcode project builds without errors
- [ ] TestFlight internal distribution working
- [ ] App Store guidelines compliance check (no external interpreter, privacy nutrition label, etc.)
- [ ] iOS app connects to Fargate API with auth (no hardcoded credentials)
- [ ] Data privacy: no user data sent to third parties without consent
- [ ] Offline mode: app gracefully handles no-network state
- [ ] Accessibility: VoiceOver support for key flows

---

*Last updated: Post-Plan-2 automation expansion sprint, 2026-06-25*
*This is a planning document only. No Plan 4–6 features are implemented in this file.*
