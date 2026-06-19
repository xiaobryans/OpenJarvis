# NUS 1C — Safe Autopilot Foundation, Persistent Queue, Telemetry Integration, and Learned Routing Scaffold

**Sprint:** NUS 1C  
**Accepted base:** NUS 1B at `ba059ddd`  
**Scope:** Persistent recommendation queue + safe autopilot for low-risk local actions + cross-session failure learning + operator/agent telemetry integration + learned routing recommendation scaffold.

---

## What NUS 1C Does

NUS 1C moves Jarvis from "recommendations and policy scaffold" to an active safe autopilot layer. It:

1. **Activates `safe_autopilot` profile** for safe local analysis and dry-run operations only.
2. **Adds a persistent recommendation queue** that survives across sessions.
3. **Adds cross-session failure pattern learning** from persisted records.
4. **Adds operator/agent telemetry ingestion** to normalize external records into learning signals.
5. **Adds a learned model-routing recommendation scaffold** that advises (never enforces) model tier selection.
6. **Adds 9 new REST routes** under `/v1/nus/*` (all read-only or dry-run only).
7. **Adds capability `nus1c_safe_autopilot_learning`** (status: `ready`).
8. **Adds a doctor check** `check_nus1c_safe_autopilot` proving all safety properties.

---

## What NUS 1C Does NOT Do

- Does **not** implement full autonomous self-improvement.
- Does **not** implement unrestricted self-patching or source-code editing.
- Does **not** implement auto-merge, auto-commit, or auto-push.
- Does **not** implement production autonomy.
- Does **not** implement power_autopilot or founder_override_session profiles (defined but not activated).
- Does **not** touch US13 voice (remains HOLD/UNSAFE/PARKED).
- Does **not** implement the post-NUS company-grade orchestrator.
- Does **not** weaken any safety or governance gates.

---

## Persistent Recommendation Queue

**Module:** `src/openjarvis/nus/recommendation_queue.py`

A JSONL-backed queue that persists across sessions. Safe paths only. Secrets redacted before storage.

### Queue Item Statuses

Aligned with NUS 1B `RecommendationRegistry`:

| Status | Meaning |
|--------|---------|
| `draft` | Created but not yet classified |
| `ready` | Safe local action — ready for dry-run |
| `needs_approval` | Medium-risk — requires human approval |
| `approved` | Approved by owner |
| `rejected` | Explicitly rejected |
| `blocked` | Dangerous action — hard-blocked |
| `executed_dry_run` | Dry-run completed |
| `superseded` | Replaced by newer recommendation |

### Operations

- `enqueue()` — Add a recommendation. Deduplicates by `dedup_key`. Auto-classifies status.
- `list_pending()` — List draft/ready/needs_approval items.
- `list_by_status()` — Filter by any status.
- `update_status()` — Transition item status.
- `supersede()` — Mark item as superseded by a successor.
- `summarize()` — Queue state summary (counts, no payloads).

### Storage

- JSONL file in `~/.openjarvis/nus/recommendation_queue.jsonl`
- Unsafe/secret paths rejected at construction.
- Suspicious values redacted via `redact_suspicious()` before write.
- Tests must use temp dirs (`tmp_path`).

---

## Safe Autopilot Scope

**Module:** `src/openjarvis/nus/safe_autopilot.py`  
**Profile:** `safe_autopilot` (activated in NUS 1C)

### Safe auto-allowed actions (NUS 1C activates these)

```
local_read
local_analysis
local_validation
validation_planning
recommendation_deduplication
scorecard_generation
telemetry_normalization
failure_pattern_summarization
dry_run_recommendation_execution
safe_local_status_snapshot
```

### Medium-risk actions → `needs_approval`

```
file_write
external_provider_setup
browser_automation
external_send
connector_setup
account_auth_change
```

### Dangerous actions → always `blocked`

```
self_modification
code_edit
auto_commit
auto_push
auto_merge
deploy
secret_access
safety_policy_change
destructive_delete
production_action
payment_action
financial_action
```

### Kill-Switch Behavior

If `kill_switch=True` on a `SafeAutopilot` instance:

- **All** action types return `decision="kill_switch_disabled"`.
- No auto-allows are granted regardless of action category.
- Tests prove kill-switch overrides all safe local auto-allows.

---

## Cross-Session Failure Pattern Learning

**Module:** `src/openjarvis/nus/failure_learning.py`

`FailureLearner` loads persisted `LearningStore` records and detects patterns across sessions.

### Detected pattern categories

| Category | Threshold | Severity |
|----------|-----------|----------|
| `recurring_validation_failure` | 2 | medium |
| `recurring_test_suite_failure` | 2 | medium |
| `recurring_approval_gate` | 3 | low |
| `recurring_blocked_unsafe` | 2 | high |
| `recurring_missing_setup` | 2 | medium |
| `recurring_routing_cost_inefficiency` | 3 | medium |
| `recurring_context_overrun` | 2 | medium |
| `recurring_agent_loop` | 2 | high |

### Each pattern includes

- `confidence` score
- `recommended_prevention` guidance
- `affected_area`
- `related_recommendation_ids`
- `escalation_recommended` flag (triggered at 5+ occurrences)
- `escalation_reason`

### What it does NOT do

- Does NOT execute any fixes.
- Does NOT modify source code.
- Does NOT commit, push, deploy, or send.
- Recommendations only.

---

## Telemetry Integration

**Module:** `src/openjarvis/nus/telemetry.py` (extended in NUS 1C)

`TelemetryNormalizer` gains two new NUS 1C methods:

### `ingest_operator_record(record)`

Normalizes an operator/agent telemetry dict. Tolerates missing fields. Redacts secrets.

**Input fields (all optional):**
- `agent_name` / `source`
- `task_id`
- `action_type`
- `result`
- `validation_status`
- `model_used`
- `estimated_cost_usd`
- `risk_level`
- `elapsed_time_seconds`
- `blocked_reason`
- `approval_required_reason`
- `related_files`
- `test_command`

**Output:** `NormalizedTelemetryRecord` mapped to learning signals, failure patterns, recommendations, and routing observations.

### `ingest_operator_batch(records)`

Bulk ingestion. Returns count ingested.

### `to_routing_observations()`

Extract routing-relevant observations (model + cost) from all ingested records.

---

## Learned Model-Routing Recommendations

**Module:** `src/openjarvis/nus/learned_routing.py`

`LearnedRouter` produces routing recommendations. It does NOT enforce model selection.

### Input sources

- `recommend_from_scorecard(scorecard, task_category, complexity_level)` — Uses risk, failure rate, validation failures.
- `recommend_from_telemetry(records, task_category)` — Uses failures, blocks, cost.
- `recommend_from_failure_patterns(patterns, task_category)` — Uses pattern categories and severity.
- `recommend_for_task(task_category, risk_level, complexity_level, context_size_tokens, validation_failures)` — Contextual.

### Model tiers (advisory labels — no real keys)

| Tier | When |
|------|------|
| `cheap_fast` | Low-risk, simple, docs-only |
| `balanced` | Default for moderate risk/complexity |
| `strong` | Architecture, security, governance, deploy-risk, high failure rate |
| `stop` | Repeated failures — stop and investigate, not a model upgrade |

### Enforcement

All recommendations include `enforcement_note`:  
> "This is a recommendation only — no model switch is enforced. No real provider keys required. No external calls made."

---

## Autonomy Profile Status (NUS 1C)

| Profile | NUS 1C Status |
|---------|--------------|
| `manual` | available (conservative default) |
| `safe_autopilot` | **active** (NUS 1C) — safe local analysis/dry-run only |
| `power_autopilot` | defined, not activated |
| `founder_override_session` | defined, not activated |
| `production_restricted` | defined, not activated |

---

## How This Supports Eventual 95% Automation

Bryan's target: 95% automated, 5% strictly policy-controlled, minimal unnecessary approval prompts.

NUS 1C advances this by:
- Proving safe local analysis and dry-runs can be auto-allowed without risk.
- Building the persistent queue infrastructure needed to manage recommendations across sessions.
- Cross-session failure learning reduces repeated mistakes.
- Learned routing reduces token cost by directing routine tasks to cheaper models.

NUS 1C activates only the safe bottom layer. The full path is:

```
NUS 1A: Learning signals (done)
NUS 1B: Recommendation lifecycle, persistence, policy scaffold (done)
NUS 1C: Safe autopilot, persistent queue, failure learning, routing (done)
NUS 1D: Power autopilot — audited file writes (future)
NUS 1E: Founder override session — expanded local permissions (future)
NUS 1F: Production autonomy — gated by explicit approval (future)
```

---

## Why power_autopilot / founder_override / production Paths Are Not Active

- `power_autopilot`: Requires audited file writes. Not safe to enable until file write audit trail is proven.
- `founder_override_session`: Requires explicit per-session activation. Not enabled in NUS 1C.
- `production_restricted`: For production safety audits only. Not in scope for NUS 1C.
- `production_action` / `payment_action` / `financial_action`: Permanently blocked in all NUS 1C profiles.

---

## What Remains for NUS 1D / 1E / 1F

- **NUS 1D:** Power autopilot activation — audited file writes in approved internal paths.
- **NUS 1E:** Founder override session profile — expanded local permissions with kill-switch.
- **NUS 1F:** Production autonomy — strict policy gate, explicit approval required.
- **Post-NUS:** Company-grade agent orchestrator (LOCKED — do not implement until explicitly authorized).

---

## Safety Gates

All NUS 1C safety gates are permanent and tested:

| Gate | Enforcement |
|------|------------|
| No self-modification | `DANGEROUS_ACTIONS` frozenset; `SafeAutopilot.evaluate()` returns `blocked` |
| No auto-commit | Same as above |
| No auto-push | Same as above |
| No auto-merge | Same as above |
| No deploy | Same as above |
| No secret access | Same as above |
| No external sends | Returns `needs_approval` (medium-risk) |
| No uncontrolled browser | Returns `needs_approval` (medium-risk) |
| No source-code mutation | `code_edit` blocked; dry-run results explicitly note no mutation |
| Kill-switch overrides safe autopilot | `SafeAutopilot(kill_switch=True)` returns `kill_switch_disabled` for all actions |
| Path safety | `_assert_safe_path()` rejects `.env`, `.ssh`, `.aws`, credentials paths |
| Secret redaction | `redact_suspicious()` applied before all persistence writes |
| Queue: blocked items cannot be approved | `update_status(id, approved)` returns `ok=False` if status is `blocked` |

---

## Routes

All routes are read-only or dry-run only. No external actions.

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/v1/nus/recommendations/queue/status` | Persistent queue status |
| GET | `/v1/nus/recommendations/queue/list` | List queue items by filter |
| POST | `/v1/nus/recommendations/queue/enqueue-dry-run` | Enqueue recommendation (dry-run) |
| POST | `/v1/nus/autopilot/safe/run-dry-run` | Run safe autopilot dry-run |
| GET | `/v1/nus/autopilot/status` | Safe autopilot status |
| GET | `/v1/nus/failure-learning/status` | Cross-session failure learning |
| POST | `/v1/nus/telemetry/operator/ingest-dry-run` | Ingest operator telemetry |
| GET | `/v1/nus/routing/recommendations/status` | Learned routing status |
| POST | `/v1/nus/routing/recommendations/dry-run` | Generate routing recommendation |

---

## Retest Commands

```bash
cd /Users/user/OpenJarvis

# Focused NUS + core regression
uv run python -m pytest tests/nus tests/wave tests/workbench/test_us15_foundation.py tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q --tb=short

# NUS 1C only
uv run python -m pytest tests/nus/test_nus1c_safe_autopilot.py -v --tb=short
```

---

## NUS Status Summary

| Sprint | Status |
|--------|--------|
| NUS 1A | ready |
| NUS 1B | ready |
| NUS 1C | ready |
| NUS 1D+ | not_started / locked |

---

## US13 Voice Status

**US13 voice: HOLD / UNSAFE / PARKED.**

Voice runtime is excluded from all NUS 1C work. No voice capability is activated, modified, or referenced in NUS 1C implementation. This status must not change without explicit owner approval.
