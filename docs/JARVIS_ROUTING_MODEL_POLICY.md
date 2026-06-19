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
