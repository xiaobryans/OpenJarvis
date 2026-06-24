---
name: openjarvis-plan4-6-mega-sprint-planning
description: Plan and decompose Plan 4–6 mega-sprint goals into safe, sequenced sub-sprints with file ownership maps and acceptance checklists. Does NOT implement Plan 4–6 features. Produces a planning document for Bryan's review. Use only when Bryan explicitly asks to plan Plan 4–6.
---

# OpenJarvis Plan 4–6 Mega-Sprint Planning

Plans the **Plan 4–6 mega-sprint** at a structural level — no implementation.

## When to use
- When Bryan explicitly asks to plan or prepare Plan 4–6.
- When `/plan4-6-mega-sprint` is invoked.
- **NOT** during any Plan 2 or post-Plan-2 automation sprint.

## Pre-condition
Verify Plan 2 is accepted (`PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_ACCEPTED` in `CLAUDE.md`).
Verify Plan 3 is NOT being opened (parked).

## Steps

1. Invoke `plan4-6-mega-sprint-architect` agent.
2. For each Plan 4–6 goal: decompose into sub-sprints with file ownership, dependencies, acceptance criteria, blockers.
3. Identify parallel vs sequential sub-sprint sequencing.
4. Produce risk register.
5. Identify pre-conditions (external: Apple developer account, iOS device, App Store, etc.).
6. Write output to `docs/automation/PLAN4_6_READINESS_CHECKLIST.md`.

## Output
Structured planning document in `docs/automation/PLAN4_6_READINESS_CHECKLIST.md`.
Does NOT commit or push — planning only.
Does NOT mark any plan as accepted.
