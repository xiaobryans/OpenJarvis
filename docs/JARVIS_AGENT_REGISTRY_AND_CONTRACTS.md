# Jarvis Agent Registry and Contracts

**Status:** Active — NUS 1D/1E sprint  
**Machine-readable:** `openjarvis.governance.constitution.AGENT_REGISTRY`

---

## Purpose

Defines the contract every agent, sub-agent, or worker must satisfy to
participate in the Jarvis NUS ecosystem. Registration is via standard
metadata fields — not hardcoded integration per agent name.

---

## Agent Contract (Required Fields)

```python
{
    "agent_name": str,          # Descriptive, unique name (e.g. "docs_writer_worker")
    "agent_type": str,          # Role category (e.g. "analysis", "execution", "monitoring")
    "agent_version": str,       # Semantic version (e.g. "1.0.0")
    "capabilities": List[str],  # List of action_types this agent performs
    "contract_version": str,    # Contract version ("v1", "v2", ...)
    "risk_policy": str,         # "low_risk_only" | "medium_with_approval" | "high_gated"
    "tool_permissions": List[str], # Tools the agent is allowed to use
    "validation_requirements": str, # How to validate agent output
    "escalation_path": str,     # What to do when agent fails
    "event_log_enabled": bool,  # Must emit events to WorkbenchEventLog
    "nus_hooks_enabled": bool,  # Must emit telemetry to TelemetryNormalizer
}
```

All fields are required. Missing fields default to most restrictive interpretation.

---

## NUS Integration Points (All Agents Must Hook In)

| NUS System | Integration Method | Effect |
|-----------|-------------------|--------|
| Telemetry | `TelemetryNormalizer.ingest_operator_record()` | Feeds learning signals |
| Learning foundation | `LearningFoundation` scorecards | Tracks performance over time |
| Failure learning | `FailureLearner.analyze()` | Detects recurring agent failures |
| Routing recommendations | `LearnedRouter.recommend_for_task()` | Suggests model/tier changes |
| Autonomy policy | `SafeAutopilot.evaluate()` / `PowerAutopilot.evaluate()` | Action gating |
| Eval gates | `EvalGateRunner.run()` | Validates readiness |
| Event logging | `WorkbenchEventLog.push()` | Audit trail |

---

## Action Type Registry (Extensible)

Agents declare their action types in `capabilities`. Routing, autonomy,
and eval gates use these types — not agent names — to determine policy.

To register a new action type:
1. Add to the taxonomy in `execution_classifier.py`.
2. Assign it to a tier (safe_local, safe_docs, medium, high, blocked).
3. Update `JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md`.
4. Add tests that verify the new type is correctly classified.

---

## Current Registered Agents (NUS 1D/1E Sprint)

| Agent | Type | Capabilities | Risk Policy | Status |
|-------|------|-------------|-------------|--------|
| `jarvis_core` | core_assistant | All safe local actions | low_risk_safe_autopilot | active |
| `safe_autopilot` | autonomy | safe local dry-runs | safe_autopilot profile | active |
| `power_autopilot` | autonomy | safe local + medium dry-run | controlled_not_broadly_activated | bounded |

Future agents are registered by adding metadata to this table and
satisfying the contract above — no code changes required for routing/policy.

---

## Safety Contract (Mandatory for All Agents)

Every agent must agree to:
- Never bypass eval gates by claiming elevated identity.
- Never access secrets, credentials, or API keys.
- Never trigger auto-push, auto-merge, or production deploy.
- Never modify safety/governance policies.
- Emit all telemetry through `TelemetryNormalizer`.
- Respect kill-switch state.
- US13 voice remains HOLD/UNSAFE/PARKED.

Violations result in action blocked at the autonomy policy layer.

---

## See Also

- `docs/JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md`
- `docs/POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md`
- `src/openjarvis/nus/execution_classifier.py`
- `src/openjarvis/nus/eval_gate.py`

---

## NUS 1F Update — Session-Level Contracts

NUS 1F extends agent/worker contracts to include session scope boundaries:

### Session contract fields (new in NUS 1F)
When an agent/worker operates inside a `HighAutonomySession`, its contract is extended with:
- `allowed_action_types` — scope whitelist (empty = no restriction beyond permanently blocked)
- `blocked_action_types` — explicit scope blacklist
- `allowed_repos_or_paths` — filesystem scope
- `risk_ceiling` — max risk tier this agent/worker may operate at
- `cost_budget`, `token_budget`, `time_budget` — resource ceilings
- `audit_log_id` — mandatory audit log reference
- `rollback_policy` — rollback contract

### Metadata-driven classification
The `AutonomyActionPolicy` classifies actions by `action_type` and `agent_metadata` — never by hardcoded agent names. Future agents/workers pass their capability metadata and are evaluated transparently.

### Structured decision records
All agent decisions must emit `StructuredDecisionRecord` objects with:
- `hierarchy_level` indicating the emitting level
- `agent_metadata` with capability/contract fields
- `no_raw_chain_of_thought: True` always

See `docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md` for full session framework specification.

---

## Post-NUS Hierarchical Orchestrator Contracts (Sprint: post_nus_hierarchical_orchestrator)

The company-grade orchestrator adds two concrete contract types:

### ManagerContract (`src/openjarvis/orchestrator/contracts.py`)

| Field | Type | Required |
|-------|------|----------|
| `manager_id` | str | Yes — unique |
| `name` | str | Yes |
| `department` | str | Yes |
| `responsibility` | str | Yes — single clear statement |
| `input_contract` | dict | Yes |
| `output_contract` | dict | Yes — `no_raw_chain_of_thought: True` |
| `skill_domains` | list[str] | Yes |
| `worker_pool` | list[str] | Yes — registered worker IDs |
| `allowed_action_types` | list[str] | Yes |
| `blocked_action_types` | list[str] | Yes — always includes production_deploy/auto_push/auto_merge |
| `model_pool` | list[str] | Yes |
| `risk_ceiling` | str | Yes — low/medium/high/blocked |
| `tool_policy` | dict | Yes |
| `validation_policy` | dict | Yes |
| `escalation_policy` | dict | Yes |
| `telemetry_policy` | dict | Yes |
| `nus_learning_hooks` | dict | Yes |
| `status` | str | Yes — active/inactive/degraded/blocked |

### WorkerContract (`src/openjarvis/orchestrator/contracts.py`)

Same as ManagerContract with additions:
| `worker_id` | str | Yes — unique |
| `manager_id` | str | Yes — must reference valid manager |
| `skills` | list[str] | Yes |
| `allowed_tools` | list[str] | Yes |
| `blocked_tools` | list[str] | Yes — always includes production_deploy_tool |
| `validation_requirements` | dict | Yes |
| `escalation_path` | dict | Yes |

### Duplicate Prevention
- `ManagerRegistry.register()` raises `ValueError` on duplicate `manager_id`
- `WorkerRegistry.register()` raises `ValueError` on duplicate `worker_id`
- `WorkerRegistry.validate_manager_references()` validates all manager references
- Future managers/workers: add a new `ManagerContract`/`WorkerContract` via `register()` — no activation logic changes

### Registered ≠ Active
Registered workers are NOT active workers. The `DynamicActivationPlanner` activates
only workers justified by the `TaskRoutingRequest`. Activation always has rationale.
