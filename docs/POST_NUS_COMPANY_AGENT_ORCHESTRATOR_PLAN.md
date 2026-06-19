# Post-NUS Company-Grade Agent Orchestrator Plan

**Status:** IMPLEMENTED — Sprint `post_nus_hierarchical_orchestrator` + universalized in `Universalize Jarvis` sprint
**Previous status:** LOCKED (NUS 1A–1F gate) → ACCEPTED NUS 1F → NOW IMPLEMENTED → NOW UNIVERSALIZED
**Implementation module:** `src/openjarvis/orchestrator/`

---

## Jarvis is Bryan's Universal Private AI Operating System

Jarvis is NOT an OMNIX-only assistant. OMNIX is one current project managed by Jarvis.
Jarvis supports:
- OMNIX (Project 1)
- OpenJarvis (self-improvement)
- Personal tasks
- Research tasks
- Automation workflows
- Business ideas
- Any future project Bryan creates

No request requires OMNIX context. All routing is universal.

---

## Universal Front Door Architecture

```
Bryan (any request — no project required)
    │
    └── JarvisFrontDoor (universal entry — src/openjarvis/frontdoor/)
            │ optional: FrontDoorAdapter (OMNIX, OpenJarvis, etc.)
            └── CosGmOrchestrator (src/openjarvis/orchestrator/cos_gm.py)
                    │ UniversalTaskRequest → TaskRoutingRequest + ProjectContext
                    └── DynamicActivationPlanner
                            │
                            ├── Domain Managers (activated by metadata, not fixed formula)
                            └── Specialist Workers → WorkerAdapters
```

---

## Vision

After NUS 1F activates controlled high-autonomy sessions, Jarvis evolves
from a single-agent personal assistant to a manager/orchestrator that
decomposes tasks and routes them to specialist workers.

This document records the plan and current implementation status.

---

## Architecture

```
Bryan (owner)
    │
    └── Jarvis Open Chat (single front door — always)
            │
            └── Manager / Orchestrator
                    │
                    ├── Specialist Agent 1 (e.g. docs_writer)
                    ├── Specialist Agent 2 (e.g. test_runner)
                    ├── Specialist Agent 3 (e.g. nus_analyzer)
                    └── ... (up to 30 specialist workers)
```

**Jarvis Open Chat remains Bryan's single personal assistant front door.
This never changes.**

---

## Orchestrator Responsibilities

- Receive task from Bryan via Jarvis Open Chat.
- Decompose task into sub-tasks.
- Route sub-tasks to appropriate specialist agents based on metadata/contracts.
- Aggregate results and report back to Bryan.
- Apply NUS governance to all sub-task routing decisions.
- Emit telemetry for all orchestration events.

---

## Agent Registration Requirements

Every specialist agent must provide:

| Field | Required |
|-------|----------|
| `agent_name` | Unique, descriptive name |
| `responsibility` | Single clear statement |
| `input_contract` | Expected input format |
| `output_contract` | Expected output format |
| `model_pool` | Approved models/tiers |
| `risk_policy` | `low_risk_only` / `medium_with_approval` / `high_gated` |
| `tool_permissions` | Explicit list of allowed tools |
| `validation_requirements` | How output is validated |
| `escalation_path` | What happens on failure |
| `tests` | Coverage requirement |
| `event_logging` | Must emit to `WorkbenchEventLog` |
| `nus_hooks` | Must emit telemetry to `TelemetryNormalizer` |

---

## Implementation Rules (When Activated)

1. **Audit repo first** — do not duplicate accepted Wave/NUS systems.
2. **Reuse** existing NUS telemetry, scorecards, routing, policy, validation, event logging.
3. **No overwrite** of accepted NUS 1A–1E modules.
4. **Metadata/contract-driven** routing — no hardcoded agent name logic.
5. **Eval gates required** for all orchestration-initiated mutations.
6. **Rollback plans required** for all mutations.
7. **Approval workflow** for medium/high risk sub-tasks.

---

## What Is NOT Included

- No NUS 1F production autonomy (requires separate gate).
- No real-world agent registration in this sprint.
- No Slack/email/social sends.
- No payment/billing agents.
- No unrestricted web browsing agents.

---

## Estimated Scale

- Manager/Orchestrator: 1
- Specialist workers: up to 30 (justified, with full contract)
- Categories: analysis, writing, testing, NUS operations, routing,
  telemetry, validation, monitoring

---

## Activation Gate

Post-NUS orchestrator requires:
1. NUS 1F ACCEPT
2. Explicit Bryan approval for each new agent class
3. Full contract registration
4. Tests + doctor checks for each agent
5. NUS integration validation for each agent

---

## See Also

- `docs/JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md`
- `docs/JARVIS_AGENT_REGISTRY_AND_CONTRACTS.md`
- `docs/JARVIS_95_PERCENT_AUTONOMY_TARGET.md`
- `docs/JARVIS_CONSTITUTION.md`

---

## NUS 1F Readiness Update

NUS 1F provides the infrastructure that the post-NUS company-grade orchestrator will build on:

### Session boundaries
`HighAutonomySession` objects define explicit scope, TTL, budget, risk ceiling, and kill switch. The company-grade orchestrator will assign sessions to manager/worker pools within these boundaries.

### Structured decision records
`StructuredDecisionRecord` schema covers all hierarchy levels (jarvis_pa, cos_gm, manager, worker, validator, governance). The orchestrator will emit decision records at each level for NUS learning aggregation.

### Action policy
`AutonomyActionPolicy` 6-tier classification will govern which worker actions are auto-allowed vs. approval-required. The orchestrator inherits this policy without code changes.

### Dynamic activation policy
The policy principles are documented and tested in NUS 1F. The orchestrator must:
- Never use fixed worker-count formulas
- Activate based on evidence
- Prefer minimum sufficient team
- Every activation needs rationale

### Implementation Status (Post-NUS Sprint)

The hierarchical orchestrator foundation is now implemented at:
- `src/openjarvis/orchestrator/contracts.py` — ManagerContract, WorkerContract, TaskRoutingRequest, ActivationPlan
- `src/openjarvis/orchestrator/manager_registry.py` — 17 domain managers
- `src/openjarvis/orchestrator/worker_registry.py` — 30 specialist workers
- `src/openjarvis/orchestrator/activation.py` — Dynamic activation planner (no fixed formulas)
- `src/openjarvis/server/orchestrator_routes.py` — Dry-run/read-only API routes
- `tests/orchestrator/` — Focused orchestrator tests

**Scope: dry-run/read-only framework.** Real production execution remains blocked.
**Production autonomy requires future explicit Bryan approval via a new policy gate.**

See `docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md` for NUS 1F details.

### Duplicate Prevention
- `update-existing-not-duplicate` rule applied:
  - NUS 1F `decision_record.py` reused (not duplicated) — hierarchy levels already covered
  - `model_router.py` ModelTier reused — no duplicate routing system created
  - `capabilities_registry.py` extended — orchestrator capabilities added, not separate file
  - `event_log.py` extended — orchestrator events added, not separate file
  - `doctor/checks.py` extended — orchestrator check added, not separate doctor
  - `docs/` updated in-place — no duplicate plan/registry docs created

### Dynamic Activation Policy
- No fixed formulas ("simple = 1 manager + 1 worker" is forbidden)
- Registered workers are NOT active workers (activation is always planner-driven)
- Every activation has rationale; every skip has rationale
- NUS applies to all hierarchy levels: jarvis_pa, cos_gm, manager, worker, validator, governance

### Model/Provider Sufficiency
- Current sprint (dry-run/read-only): existing OpenRouter tiers (local/cheap/mid/premium) sufficient
- Real autonomous execution (future): requires verified provider keys + production model access
- Gap disclosed in ActivationPlan.model_provider_gaps and routing_plan.provider_sufficiency
- Cheap models cannot approve critical/high-risk actions (enforced in model routing plan)
