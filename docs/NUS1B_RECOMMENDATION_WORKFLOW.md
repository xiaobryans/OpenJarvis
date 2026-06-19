# NUS 1B — Recommendation Workflow

**Sprint:** NUS 1B  
**Status:** READY (local, founder V1)  
**Modules:**
- `src/openjarvis/nus/learning_store.py`
- `src/openjarvis/nus/recommendation_registry.py`
- `src/openjarvis/nus/telemetry.py`
- `src/openjarvis/nus/autonomy_policy.py`

**Builds on:** NUS 1A (`src/openjarvis/nus/learning_foundation.py`)

---

## What NUS 1B Does

NUS 1B moves Jarvis from "learning and scoring" to **persistent learning + actionable recommendations + approval workflow scaffolding**, while still not executing risky changes automatically.

### 1. Cross-Session Learning Persistence (`learning_store.py`)

`LearningStore` provides safe JSONL persistence for:
- Task outcome records
- Learning signals
- Failure pattern records
- Learning snapshots
- Recommendation records

**Safe paths only:** Writes are restricted to `~/.openjarvis/nus/` or temp dirs (for tests). The following paths are rejected: `.env`, `.env.local`, `.ssh`, `.aws`, `.git`, `credentials`, `api_key`, `secret`, `password`, `token`, and other secret-pattern paths.

**Secret redaction:** All values are passed through `redact_suspicious()` before persistence. Keys matching secret patterns (api_key, secret, token, password, etc.) are replaced with `[REDACTED]`. Values matching known secret formats (sk-, Bearer, AKIA, long base64) are also redacted.

### 2. Recommendation Registry (`recommendation_registry.py`)

`RecommendationRegistry` manages the full lifecycle of structured recommendations:

| Status | Description |
|---|---|
| `draft` | Just created, not yet validated |
| `ready` | Safe local action — auto-allowed |
| `needs_approval` | Medium-risk — requires explicit owner approval |
| `approved` | Approved by owner |
| `rejected` | Rejected by owner |
| `blocked` | Dangerous action — permanently blocked |
| `executed_dry_run` | Dry-run executed (safe local only) |
| `superseded` | Replaced by a newer recommendation |

**Classification at creation:** Every recommendation is classified by `required_action_type`:

| Action type | Result |
|---|---|
| `local_read`, `local_analysis`, `local_validation` | `ready` |
| `file_write`, `external_provider_setup`, `browser_automation`, `external_send` | `needs_approval` |
| `self_modification`, `code_edit`, `secret_access`, `auto_commit`, `auto_push`, `deploy`, `safety_policy_change` | `blocked` |

**Dry-run:** Safe (`auto_allowed_*`) recommendations can be dry-run immediately. `needs_approval` recommendations require explicit `approve()` first. Blocked recommendations can never be dry-run.

**Factory methods:**
- `RecommendationRegistry.from_scorecard(scorecard_dict)` — create from NUS 1A scorecard
- `RecommendationRegistry.from_failure_patterns(patterns)` — create from NUS 1A failure patterns

### 3. Telemetry Ingestion/Normalization (`telemetry.py`)

`TelemetryNormalizer` ingests diverse event sources and produces `NormalizedTelemetryRecord` objects:

| Source | Method |
|---|---|
| Workbench events | `ingest_workbench_event(event)` |
| Validation outputs | `ingest_validation_output(output)` |
| Capability status summaries | `ingest_capability_summary(summary)` |
| Model routing/cost metadata | `ingest_routing_cost_metadata(metadata)` |
| Wave 1–4 summaries | `ingest_wave_summary(wave, summary)` |
| NUS 1A learning records | `ingest_nus1a_record(learning_record)` |
| Blocked/approval actions | `ingest_blocked_action(action, reason)` |
| Batch events | `ingest_batch(events)` |

**Event → signal mapping:**

| Category | Signal type |
|---|---|
| blocked | `risk_signal` |
| approval | `approval_signal` |
| validation | `validation_signal` |
| cost | `cost_signal` |
| routing | `capability_signal` |
| task failure | `negative_signal` |
| task success, wave, learning | `positive_signal` |

**Redaction:** All ingested data passes through `redact_suspicious()`.

**Recommendation generation:** `to_recommendations()` converts high-signal normalized records into recommendation hints (multiple blocked events → blocked pattern recommendation; multiple failures → failure remediation recommendation).

### 4. Autonomy Policy Scaffold (`autonomy_policy.py`)

Defines the structure for future automation profiles. Only `manual` is fully activated in NUS 1B.

| Profile | Status in NUS 1B | Description |
|---|---|---|
| `manual` | **active** | Default. All actions require human approval. |
| `safe_autopilot` | defined, not activated | Local read/analysis/validation auto-allowed. Everything else gated. |
| `power_autopilot` | defined, not activated (kill-switch on) | Local ops + audited file writes. Sends/browser/deploy/secrets gated. |
| `founder_override_session` | defined, not activated (kill-switch on) | Expanded local permissions. Auto-commit/push/deploy/secrets blocked. |
| `production_restricted` | defined, not activated | Read-only. All mutations blocked. |

**Always-blocked (all profiles):** `self_modification`, `code_edit`, `secret_access`, `auto_push`, `deploy`, `safety_policy_change`

**Always-needs-approval (all profiles):** `external_send`, `browser_automation`, `external_provider_setup`

**Kill-switch:** `autonomy_kill_switch=True` blocks all auto actions regardless of profile. `power_autopilot` and `founder_override_session` have kill-switch on by default in NUS 1B.

### 5. API Routes

| Route | Method | Description |
|---|---|---|
| `/v1/nus/recommendations/status` | GET | NUS 1B status + safety gates |
| `/v1/nus/recommendations/list` | GET | List all in-process recommendations |
| `/v1/nus/recommendations/create-dry-run` | POST | Create a recommendation (dry-run) |
| `/v1/nus/recommendations/approve-dry-run` | POST | Approve + execute dry-run |
| `/v1/nus/recommendations/reject-dry-run` | POST | Reject a recommendation |
| `/v1/nus/telemetry/status` | GET | Telemetry normalizer status |
| `/v1/nus/telemetry/ingest-dry-run` | POST | Ingest events (dry-run, no external actions) |
| `/v1/nus/autonomy-policy/status` | GET | Autonomy policy scaffold status |

All routes are read-only or dry-run. No external sends. No secret access.

### 6. Capability

- `nus1b_recommendation_workflow` → `ready`
- Doctor check: `check_nus1b_recommendation_workflow`

### 7. Event Types Added

- `recommendation_created`
- `recommendation_approved`
- `recommendation_rejected`
- `recommendation_blocked`
- `recommendation_dry_run_executed`
- `learning_record_persisted`
- `telemetry_ingested`
- `autonomy_policy_evaluated`
- `autonomy_action_blocked`

---

## What NUS 1B Does NOT Do

- No code self-modification
- No file writes except safe JSONL store at `~/.openjarvis/nus/`
- No auto-commit, auto-push, auto-merge
- No production deploy
- No external sends (Slack, email, HTTP outbound)
- No secret access
- No browser automation
- No account setup
- No autonomous execution of recommendations — dry-run only, no real execution
- No weakening of safety or governance gates
- US13 voice remains **HOLD / UNSAFE / PARKED** — unaffected by NUS 1B
- NUS 1C+ (safe_autopilot activation, A/B routing) remains NOT STARTED

---

## Persistence Behavior

**Format:** JSONL (one JSON record per line)  
**Location:** `~/.openjarvis/nus/` (default), or any safe temp/home path  
**Files:**
- `task_outcomes.jsonl`
- `learning_signals.jsonl`
- `failure_patterns.jsonl`
- `learning_snapshots.jsonl`
- `recommendations.jsonl`

**Safety:** Path validated via `_is_safe_path()`. Blocked patterns: `.env`, `.ssh`, `.aws`, `.git`, `credentials`, `secret`, `api_key`, `token`, `password`, `private_key`, etc.

**Redaction:** All values pass through `redact_suspicious()` before write. Tests must use temp dirs.

---

## Recommendation Lifecycle

```
create() → classified → draft/ready/needs_approval/blocked
              ↓
    [if blocked] → blocked (final)
    [if needs_approval] → approve() → approved → execute_dry_run()
    [if ready] → execute_dry_run() immediately
              ↓
    executed_dry_run (no real execution — simulation only)
              or
    reject() → rejected
              or
    supersede() → superseded
```

---

## Approval Workflow Scaffold

This is the beginning of future 95% automation. In NUS 1B:

- Safe local read/analysis/validation → `ready` → auto dry-run allowed
- Medium-risk (file writes, provider setup, browser, external sends) → `needs_approval` → requires `approve()` before dry-run
- Dangerous (self-modification, code edit, secret access, auto-commit, auto-push, deploy, safety policy change) → `blocked` → no path to execution

**Future NUS 1C+:** safe_autopilot profile activation will allow `local_read`, `local_analysis`, `local_validation` to be auto-executed without prompt. This is the gateway to eventual 95% automation.

---

## Why 95% Automation Is Not Enabled Yet

The goal is eventually:
- 95% automated (safe local ops, analysis, validation, routine recommendations)
- 5% strict policy-controlled (external sends, file writes, deploy, secrets, browser)

NUS 1B only defines the structure. Full activation requires:
1. Validated approval workflow (NUS 1C)
2. Persistent cross-session learning (NUS 1B foundation done, NUS 1C to extend)
3. Operator/agent telemetry integration (NUS 1C)
4. A/B routing based on learned signals (NUS 1C)
5. Explicit owner activation of safe_autopilot profile

---

## How This Supports Eventual 95% Automation

| Piece | Sprint |
|---|---|
| Learning from outcomes | NUS 1A (done) |
| Persistent learning records | NUS 1B (done) |
| Recommendation lifecycle | NUS 1B (done) |
| Approval workflow scaffold | NUS 1B (done) |
| Telemetry normalization | NUS 1B (done) |
| Autonomy policy structure | NUS 1B (done) |
| safe_autopilot activation | NUS 1C |
| A/B routing | NUS 1C |
| Operator telemetry integration | NUS 1C |
| Recommendation queue with approval UI | NUS 1C/1D |
| power_autopilot activation | NUS 1D/1E |
| Production-safe recommendation execution | NUS 1E/1F |

---

## What Remains for NUS 1C/1D/1E/1F

| Feature | Sprint |
|---|---|
| Activate safe_autopilot profile | NUS 1C |
| Persistent recommendation queue across sessions | NUS 1C |
| Operator/agent telemetry integration | NUS 1C |
| A/B model routing based on learned signals | NUS 1C |
| Founder approval UI for recommendations | NUS 1C/1D |
| Activate power_autopilot with explicit approval | NUS 1D |
| Cross-session failure pattern learning | NUS 1C/1D |
| Activate founder_override_session | NUS 1D |
| Production-safe execution path | NUS 1E |
| Deployment recommendation execution | NUS 1F (explicit gate required) |

---

## Safety Gates

| Gate | Implementation |
|---|---|
| Blocked action types | `resolve_approval_policy()` → `STATUS_BLOCKED` |
| Approval-required types | `resolve_approval_policy()` → `STATUS_NEEDS_APPROVAL` |
| Always-blocked set | `_ALWAYS_BLOCKED` frozenset in autonomy_policy |
| Path safety | `_assert_safe_path()` in learning_store |
| Secret redaction | `redact_suspicious()` in learning_store + telemetry |
| Kill-switch | `autonomy_kill_switch` field in AutonomyPolicy |
| Doctor check | `check_nus1b_recommendation_workflow` verifies all gates |
| US13 parked | All routes/checks/snapshots report `us13_voice_status=HOLD/UNSAFE/PARKED` |

---

## US13 Voice Status

US13 voice is **HOLD / UNSAFE / PARKED**.  
NUS 1B does not change this status.  
All routes, doctor checks, autonomy policy status, and capability summaries report `us13_voice_status = "HOLD/UNSAFE/PARKED"`.

---

## Retest Commands

```bash
cd /Users/user/OpenJarvis

# NUS 1B focused
uv run python -m pytest tests/nus/test_nus1b_recommendation_workflow.py -q --tb=short

# Full NUS regression
uv run python -m pytest tests/nus -q --tb=short

# NUS + wave + workbench core regression
uv run python -m pytest tests/nus tests/wave tests/workbench/test_us15_foundation.py tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q --tb=short

# Doctor check
uv run python -c "from openjarvis.doctor.checks import check_nus1b_recommendation_workflow; r = check_nus1b_recommendation_workflow(); print(r.status, r.summary[:120])"

# Capability check
uv run python -c "from openjarvis.workbench.capabilities_registry import get_all_capabilities; caps = get_all_capabilities(); cap = next(c for c in caps if c.capability_id == 'nus1b_recommendation_workflow'); print(cap.status, cap.summary[:80])"
```
