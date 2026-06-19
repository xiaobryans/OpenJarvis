# Jarvis Routing Model Policy

**Status:** Active — NUS 1D/1E sprint  
**Enforced by:** `LearnedRouter`, `EvalGateRunner`, `ExecutionClassifier`

---

## Purpose

Defines how Jarvis recommends (not enforces) model/tier selection for tasks.
Routing decisions are advisory — the user (Bryan) retains control.
Routing is based on metadata and learned signals, never on hardcoded agent names.

---

## Model Tiers

| Tier | When | Examples |
|------|------|---------|
| `cheap_fast` | docs-only, low risk, no reasoning required | changelog update, readme edit |
| `balanced` | moderate complexity, 1–5 files, single feature | single route fix, validation |
| `strong` | architecture, security, governance, 6+ files | schema migration, cross-system refactor |
| `stop` | repeated failures, blocker condition, avoid spinning | 3+ failed attempts same approach |

---

## Routing Decision Inputs (Metadata-Driven)

Routing recommendations consume:
- `task_category`: `docs_only`, `code_simple`, `architecture`, `security`, `governance`, `deploy_risk`
- `risk_level`: `low`, `medium`, `high`, `critical`
- `complexity_level`: `simple`, `moderate`, `complex`
- `context_size_tokens`: estimated context window usage
- `validation_failures`: count of recent failures for this task
- `scorecard`: accumulated performance data from `LearningFoundation`
- `telemetry`: normalized records from `TelemetryNormalizer`
- `failure_patterns`: from `FailureLearner`

**Not consumed:** agent name, session ID, hardcoded model name.

---

## Routing Rules (Advisory — No Enforcement)

| Condition | Recommendation |
|-----------|---------------|
| `task_category=docs_only`, `risk=low` | `cheap_fast` |
| `task_category=code_simple`, `complexity=simple` | `cheap_fast` or `balanced` |
| `task_category=architecture` | `strong` |
| `task_category=security` or `governance` | `strong` |
| `task_category=deploy_risk` | `strong` |
| `validation_failures >= 2` | escalate tier |
| `validation_failures >= 4` | `stop` — break approach |
| `context_size_tokens > 80000` | prefer `cheap_fast` for summaries |
| `risk=critical` | `strong` |

---

## Enforcement Policy

Routing is **advisory only**. The system:
- Recommends a tier via `LearnedRouter.recommend_for_task()`
- Never automatically switches provider/model
- Never changes user's selected model in Cursor
- Records recommendation as a `RoutingRecommendation` object

The user reviews routing recommendations and applies them manually.

---

## Future Direction

NUS 1F (not started) may implement controlled auto-routing within approved
provider pools for specific safe task categories. That requires:
- Explicit Bryan approval
- Scoped provider list
- Eval gate + rollback + audit log

---

## See Also

- `src/openjarvis/nus/learned_routing.py`
- `docs/JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md`
- `docs/JARVIS_95_PERCENT_AUTONOMY_TARGET.md`
- Rule `10-api-token-and-model.mdc` — user always picks model in Cursor

---

## NUS 1F Update — Session-Aware Provider Pool Routing

NUS 1F adds provider/model tier constraints to the routing policy:

### Model tier constraints for action approval
Cheap models cannot approve critical or strict-policy actions:

| Action tier | Minimum model tier |
|---|---|
| `auto_allowed` | Any (including cheap) |
| `auto_allowed_with_audit` | Any |
| `dry_run_only` | standard_model |
| `needs_approval` | standard_model |
| `strict_policy_controlled` | premium_model |
| `blocked` | No model — permanently blocked |

### Session-bounded routing
All model routing within a `HighAutonomySession` must respect:
- `risk_ceiling` field — no model may route actions exceeding session risk ceiling
- No new external provider keys
- No secrets in routing metadata
- Validation failure escalates — repeated failure stops and reports blocker

### Future-proof routing
Routing recommendations use metadata/contract fields, not hardcoded agent names. Future workers/managers pass capability metadata; the router evaluates transparently.

See `docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md` for session framework and `src/openjarvis/nus/autonomy_action_policy.py` for model tier implementation.

---

## Post-NUS Orchestrator Routing (Sprint: post_nus_hierarchical_orchestrator)

The `DynamicActivationPlanner` integrates with the existing ModelRouter tiers:

### Orchestrator routing rules

| Task Profile | Tier |
|---|---|
| simple + low risk | cheap |
| fast latency required | cheap |
| moderate complexity | mid (default) |
| high/blocked risk | premium |
| critical action approval | premium (cheap blocked) |

### Critical action rule
**Cheap models cannot approve critical or high-risk actions.**
Enforced via `critical_approval_check.cheap_model_blocked_for_approval = True` in every ActivationPlan.

### Provider sufficiency disclosure
- Sprint scope (dry-run/read-only): existing OpenRouter tiers sufficient
- Future real autonomous execution: requires verified provider keys + production model access
- Gap disclosed in `ActivationPlan.model_provider_gaps` and `model_routing_plan.provider_sufficiency`
- If provider unavailable: fallback tier disclosed + quality/safety tradeoff documented

### Per-worker routing
Each selected worker receives a routing recommendation based on:
- worker's `model_pool` capabilities
- task `risk_level`
- global tier recommendation

### No hardcoded names
Routing decisions consume `task_metadata` (risk, complexity, intent) — never hardcoded agent or worker names.
