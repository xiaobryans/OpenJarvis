# Post-NUS Company-Grade Agent Orchestrator Plan

**Status:** LOCKED — do not implement in NUS 1D/1E sprint  
**Implementation gate:** Requires NUS 1F completion + explicit Bryan approval

---

## Vision

After NUS 1F activates controlled high-autonomy sessions, Jarvis can evolve
from a single-agent personal assistant to a manager/orchestrator that
decomposes tasks and routes them to up to 30 specialist workers.

This document records the plan. **Nothing here is implemented yet.**

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
