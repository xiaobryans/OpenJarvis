# NUS 1A — Learning Foundation

**Sprint:** NUS 1A  
**Status:** READY (local, founder V1)  
**Module:** `src/openjarvis/nus/learning_foundation.py`  
**Version:** 1.0.0  
**Accepted at commit:** (see final HEAD in sprint report)

---

## What NUS 1A Does

NUS 1A gives Jarvis the foundation to **learn from outcomes** without letting it modify itself.

It collects and exposes structured learning signals from:

- Task outcomes (success, failure, blocked, approval-required, partial)
- Validation results (pass/fail per session/task)
- Blocked actions (safety gates, unsafe action classification)
- Approval-required actions (gated writes, deploys, external providers)
- Repeated failure patterns (validation loops, approval gate hits, unsafe blocks, config gaps)
- Capability readiness (capability registry status aggregation)
- Model routing decisions (model_used metadata from outcome records)
- Cost/performance metadata (estimated_cost_usd per task, averages, totals)
- Wave 1–4 events (aggregated from workbench event log)
- Workbench/coding outcomes (subtask done/failed, diff reviews, terminal approvals)

### Core classes

| Class | Purpose |
|---|---|
| `TaskOutcomeRecord` | Structured record of one task execution outcome |
| `FailurePatternRecord` | A detected repeated failure pattern |
| `LearningSignal` | A typed signal extracted from outcomes |
| `AgentScorecard` | Aggregated scorecard from outcome records |
| `LearningSnapshot` | Full learning state snapshot (no external services) |
| `LearningFoundation` | Main interface — ingest, analyze, snapshot |

### Signal types

| Signal | Meaning |
|---|---|
| `positive_signal` | Successful outcomes observed |
| `negative_signal` | Failure outcomes observed |
| `risk_signal` | Blocked / unsafe action outcomes |
| `cost_signal` | Cost/token metadata available |
| `validation_signal` | Validation pass/fail outcomes |
| `capability_signal` | Capability/model routing observations |
| `approval_signal` | Approval-required outcomes |

### Failure pattern categories

| Category | Trigger |
|---|---|
| `repeated_validation_failure` | 2+ validation_failed events |
| `repeated_approval_gate` | 3+ approval_required events |
| `repeated_blocked_unsafe` | 2+ blocked safety events |
| `repeated_missing_setup` | 2+ provider_unavailable events |
| `repeated_capability_not_ready` | 3+ capability_denied events |
| `repeated_routing_cost_inefficiency` | 3+ optimization_blocked/budget_exceeded |

### API routes (read-only)

| Route | Description |
|---|---|
| `GET /v1/nus/learning/status` | NUS 1A status + safety gate summary |
| `GET /v1/nus/learning/scorecards` | Generate AgentScorecard from recent events |
| `GET /v1/nus/learning/failure-patterns` | Detected failure patterns |
| `GET /v1/nus/learning/snapshot` | Full LearningSnapshot |

All routes are **read-only** and **local-only**. No external sends.

### Capability

- `nus1a_learning_foundation` — status `ready` in capability registry
- Doctor check: `check_nus1a_learning_foundation` — verifies module importable, safety gates active, blocked gate functional

### Event types added

- `learning_snapshot_created`
- `agent_scorecard_generated`
- `failure_pattern_detected`
- `learning_recommendation_created`
- `learning_action_blocked`
- `learning_approval_required`
- `task_outcome_ingested`
- `task_outcomes_ingested_batch`
- `learning_foundation_initialized`

---

## What NUS 1A Does NOT Do

NUS 1A is **observation and reporting only**. The following are permanently blocked:

- No code self-modification
- No file writes (beyond approved safe internal event log paths)
- No auto-commit, auto-push, auto-merge
- No production deploy
- No external sends (Slack, email, HTTP outbound)
- No secret access
- No browser automation
- No account setup
- No autonomous execution of recommendations
- No weakening of safety/governance gates
- US13 voice remains **HOLD / UNSAFE / PARKED** — unaffected by NUS 1A

Any `make_recommendation()` call with a blocked action class returns `{"status": "blocked"}`.  
Any recommendation implying writes, deploys, external providers, or self-modification returns `{"status": "needs_approval"}` or `{"status": "blocked"}`.

---

## How It Learns From Outcomes

1. **Ingest**: `LearningFoundation.ingest_from_workbench_events()` pulls recent `WorkbenchEventLog` records and converts them to `TaskOutcomeRecord` objects.
2. **Classify**: `classify_signals()` groups records into typed `LearningSignal` objects.
3. **Detect patterns**: `detect_failure_patterns()` identifies recurring failure categories above thresholds.
4. **Score**: `generate_scorecard()` produces an `AgentScorecard` with risk level, confidence, and recommended review action.
5. **Snapshot**: `get_snapshot()` aggregates scorecard + patterns + signals + Wave 1–4 status + capabilities + doctor summary into a `LearningSnapshot`.

The loop is: **observe → classify → detect → score → snapshot → recommend (no execute)**.

---

## Wave 1–4 Integration

NUS 1A reads (does not write to) these systems:

| Wave | Integration |
|---|---|
| Wave 1 | `get_automation_platform_status()` — automation platform status |
| Wave 2 | `get_optimization_platform_status()` — optimization + skill pack status |
| Wave 3 | `get_content_studio_status()` — content/media studio status |
| Wave 4 | `get_expansion_status()` — autonomous expansion proposal status |
| Workbench | `WorkbenchEventLog.list_recent()` — event log aggregation |
| Capabilities | `get_all_capabilities()` — capability registry status |
| Doctor | `check_backend_health()`, `check_strict_operating_rules_present()` |

All integrations are **best-effort** — if a wave module is unavailable, the snapshot records `{"status": "unavailable", "error": "..."}` and continues.

---

## Safety Gates

| Gate | Implementation |
|---|---|
| Blocked action classes | `make_recommendation()` checks against `_BLOCKED_ACTIONS` frozenset |
| Needs-approval classes | `make_recommendation()` checks against `_APPROVAL_ACTIONS` frozenset |
| Doctor check | `check_nus1a_learning_foundation` verifies blocked gate is functional |
| US13 parked | All snapshots and routes report `us13_voice_status = "HOLD/UNSAFE/PARKED"` |
| No file writes | Module does not call `open(..., 'w')` or write to arbitrary paths |
| Event log | All events go through `WorkbenchEventLog.push()` — local SQLite only, no external sends |

---

## What Remains for NUS 1B / 1C

NUS 1A is **observation + reporting only**. The following are deferred:

| Feature | Sprint |
|---|---|
| Automated recommendation execution (with approval gates) | NUS 1B |
| Learning from operator/agent telemetry | NUS 1B |
| Cross-session learning persistence | NUS 1B |
| Structured recommendation queue with approval workflow | NUS 1B |
| A/B routing based on learned signals | NUS 1C |
| Full self-improvement autonomy (supervised) | NUS 1C+ |
| Production deployment of learning insights | Requires explicit owner gate |

---

## US13 Voice Status

US13 voice is **HOLD / UNSAFE / PARKED**.  
NUS 1A does not change this status.  
All snapshots, routes, and the doctor check report `us13_voice_status = "HOLD/UNSAFE/PARKED"`.  
See `docs/US15_US16_FOUNDATION.md § US13 parked voice backlog`.

---

## Retest Commands

```bash
cd /Users/user/OpenJarvis

# NUS 1A focused
uv run python -m pytest tests/nus -q --tb=short

# NUS + core regression
uv run python -m pytest tests/nus tests/wave tests/workbench/test_us15_foundation.py tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q --tb=short

# Doctor check only
uv run python -c "from openjarvis.doctor.checks import check_nus1a_learning_foundation; r = check_nus1a_learning_foundation(); print(r.status, r.summary)"

# Capability check
uv run python -c "from openjarvis.workbench.capabilities_registry import get_all_capabilities; caps = get_all_capabilities(); nus = next(c for c in caps if c.capability_id == 'nus1a_learning_foundation'); print(nus.status, nus.summary[:80])"
```
