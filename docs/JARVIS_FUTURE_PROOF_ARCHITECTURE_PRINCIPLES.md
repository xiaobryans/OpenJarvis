# Jarvis Future-Proof Architecture Principles

**Status:** Active — universalized in `Universalize Jarvis` sprint
**Machine-readable:** `openjarvis.governance.constitution.FUTURE_PROOF_ARCHITECTURE`

---

## Jarvis is Bryan's Universal Private AI Operating System

Jarvis is NOT OMNIX-only. OMNIX is Project 1 (one current project). Jarvis must:
- Support OMNIX, OpenJarvis, personal tasks, research, automation, and any future project
- Work without any project context (personal tasks require no project_id)
- Route based on metadata/contracts, never hardcoded project names
- Never require OMNIX in universal orchestration paths

**Private-first does not mean low quality. Target public-grade/adversarial-grade minimum.**

---

## Purpose

Every component added to Jarvis — feature, NUS phase, agent, worker, routing layer,
skill, capability, telemetry path, policy, or workflow — must be designed to remain
valid and extensible as Jarvis grows to support a universal multi-project,
multi-agent orchestration architecture. This document defines the mandatory principles.

---

## Core Principle: Registry/Metadata/Contract-Driven

**All future components must be registry/metadata/contract-driven where appropriate.**

Do not hardcode specific agent names, worker identities, or model names into:
- routing logic
- autonomy policy decisions
- execution classification
- telemetry ingestion
- doctor/readiness checks
- capability registration

Instead, evaluate by:
- **action type** — what the agent is trying to do
- **risk level** — low / medium / high / critical
- **tool requirements** — which tools does the action require?
- **capability metadata** — what does the capability record declare?
- **validation evidence** — has a validation plan been confirmed?
- **agent metadata contract** — what fields does the agent provide?

---

## New Agent Integration Contract

Every new agent, sub-agent, or worker must:

1. **Provide standard agent metadata** via a defined contract:
   ```json
   {
     "agent_name": "descriptive_name",
     "agent_type": "role_category",
     "agent_version": "semver",
     "capabilities": ["list_of_action_types"],
     "contract_version": "v1",
     "risk_policy": "low_risk_only | medium_with_approval | high_gated"
   }
   ```

2. **Emit telemetry** through `TelemetryNormalizer.ingest_operator_record()`.

3. **Be scored** via `LearningFoundation` scorecards using standard signals.

4. **Appear in failure learning** via `FailureLearner.analyze()` without any new hardcoded logic.

5. **Receive routing recommendations** via `LearnedRouter` based on task category and risk — not name.

6. **Respect autonomy policy** via `SafeAutopilot.evaluate()` — evaluated by action type, not agent name.

7. **Satisfy eval gates** via `EvalGateRunner.run()` — gates check action/risk/validation/rollback, not identity.

8. **Log events** to `WorkbenchEventLog`.

---

## Routing and Autonomy: Metadata-Driven

Routing and autonomy decisions must evaluate:
- `action_type` — from the standard action taxonomy
- `risk_level` — validated against `{low, medium, high, critical}`
- `tool_requirements` — does the action require dangerous tools (git_push, browser_control, etc.)?
- `capability_id` + `capability_ready` — from the capability registry
- `validation_plan` — is there evidence of how to validate?
- `rollback_plan` — is there a rollback plan for mutations?
- `safety_gate_result` — has the safety gate confirmed pass?

**Not** by:
- current agent name
- hardcoded Jarvis version strings
- specific model names
- specific session IDs

---

## Extensibility Requirements

When adding a new NUS phase, agent, or capability:

1. Register in `capabilities_registry.py` with truthful status.
2. Add event types to `event_log.py`.
3. Add a doctor check to `doctor/checks.py`.
4. Add tests that use a synthetic future agent to verify the component
   works without hardcoded agent name logic.
5. Update `WAVE_ROADMAP.md` only if scope warrants it.

---

## Action Taxonomy (Current — Extensible)

| Tier | Action Types | Disposition |
|------|-------------|-------------|
| Safe local | `local_read`, `local_analysis`, `validation_planning`, `scorecard_generation`, `telemetry_normalization`, `failure_pattern_summarization`, `dry_run_recommendation_execution` | auto-allowed |
| Safe docs | `docs_write`, `test_metadata_update`, `internal_status_write`, `changelog_update` | auto-allowed |
| Medium risk | `file_write`, `config_change`, `dependency_update`, `connector_setup` | needs_approval |
| High risk | `external_provider_setup`, `browser_automation`, `external_send` | needs_approval |
| Blocked | `self_modification`, `deploy`, `auto_push`, `auto_merge`, `secret_access`, `safety_policy_change`, `production_action` | permanently blocked |

Future agents add new action types by extending this taxonomy, not by bypassing it.

---

## Safety Guarantees (Permanent)

- No action bypasses eval gates by claiming a privileged identity.
- No agent name grants elevated autonomy beyond its declared risk policy.
- Blocked categories remain blocked regardless of agent.
- US13 voice remains HOLD/UNSAFE/PARKED.
- NUS 1F production autonomy is NOT enabled by this document.

---

## See Also

- `docs/JARVIS_AGENT_REGISTRY_AND_CONTRACTS.md`
- `docs/JARVIS_ROUTING_MODEL_POLICY.md`
- `docs/JARVIS_95_PERCENT_AUTONOMY_TARGET.md`
- `docs/JARVIS_TOKEN_COST_GOVERNANCE.md`
- `docs/POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md`
- `src/openjarvis/nus/execution_classifier.py` — reference implementation

---

## NUS 1F Update — Future-Proof Session and Decision Framework

NUS 1F applies the future-proof principles to autonomy sessions and decisions:

### Principle: No hardcoded agent names
All session policies, action classification, and decision records evaluate by metadata/contract fields — not hardcoded agent names. Future agents/workers inherit compatibility automatically.

### Principle: Schema-additive, never removing
Structured decision record schema (`decision_record.py`) is additive-only. Fields are added in future versions; none removed. All callers are forward-compatible.

### Principle: Registry/metadata/contract-driven
- `HighAutonomySession.allowed_action_types` — list-driven, not hardcoded
- `AutonomyActionPolicy` — type-driven classification, not name-driven
- `StructuredDecisionRecord.hierarchy_level` — metadata tag covering all levels

### Principle: NUS applies to all hierarchy levels
Decision records carry `hierarchy_level`: jarvis_pa, cos_gm, manager, worker, validator, governance. NUS learns from every level — not only Jarvis PA.

### Principle: Dynamic activation
No fixed worker-count formulas. Every activation requires evidence-based rationale. Post-NUS orchestrator will build on this scaffolding.

### Principle: Duplicate/overwrite prevention
NUS 1F extended existing modules (`autonomy_policy.py`, `power_autopilot.py`) by adding new files, not replacing accepted working code.

See `docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md` for implementation details.
