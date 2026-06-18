# Wave 4 — Autonomous Expansion (Epic H)

**Status:** COMPLETE — local/founder V1  
**Epic:** H — Autonomous Expansion (Supervised)  
**Module:** `src/openjarvis/wave/autonomous_expansion.py`  
**Tests:** `tests/wave/test_wave4.py`  
**Capability ID:** `wave4_autonomous_expansion`

---

## What Wave 4 Completed

Wave 4 adds a supervised expansion scaffolding system. It is **proposal-only** — no autonomous
execution, no code self-modification, no auto-commit, no deploy.

### Core Features

| Feature | Status |
|---|---|
| Expansion opportunity detection | READY |
| Capability gap analysis | READY |
| Safe expansion proposal creation | READY |
| Dependency/risk classification | READY |
| Acceptance criteria generation | READY |
| Validation-plan generation | READY |
| Rollback-plan generation | READY |
| Approval-gated expansion queue | READY |
| Wave 1 skill/automation/knowledge/research proposals | READY |
| Wave 2 cost/routing/performance classification | READY |
| Wave 3 content spec/handoff/readiness report drafting | READY |
| Event logging (5 event types) | READY |
| API routes `/v1/wave4/expansion/*` | READY |
| Doctor/readiness check | READY |

### Wave 1 Integration

- `propose_wave1_skill()` — create a proposal to add a new Wave 1 skill
- `propose_wave1_automation()` — create a proposal to add a new automation trigger
- `propose_wave1_knowledge_source()` — create a proposal to add a new knowledge source
- `propose_wave1_research_provider()` — create a proposal to add a new research provider
- `detect_expansion_opportunities()` — scans Wave 1 registries for gaps

All proposals are classified `needs_approval` — no auto-registration.

### Wave 2 Integration

- Cost/routing/performance impact classified using Wave 2 optimization patterns
- High-cost patterns (large model, concurrent, bulk) trigger `needs_approval` classification
- Gap analysis reads Wave 2 professional skill pack counts

### Wave 3 Integration

- Content spec drafted in Wave 3 template format (dry-run, no external publish without approval)
- Handoff pack drafted with acceptance criteria and review instructions
- Readiness report drafted with safety status (NUS 1 not started, US13 parked)

---

## What Is Local/Founder Ready

- Creating and inspecting expansion proposals via API or direct Python calls
- Viewing expansion opportunities and capability gaps
- Generating validation and rollback plans
- Querying the expansion queue

---

## What Requires Approval

Any proposal with these types is classified `needs_approval`:

- `register_capability`
- `add_provider`
- `add_integration`
- `wave1_skill_register`
- `wave1_automation_register`
- `wave1_knowledge_source_register`
- `wave1_research_provider_register`
- Any description containing external API, cloud, remote, or webhook references

**No approval bypass is implemented. Proposals queue and wait for explicit owner review.**

---

## What Is Explicitly Blocked

These proposal types and description patterns are always `blocked`:

| Blocked Type | Reason |
|---|---|
| `file_write` | No autonomous file writes |
| `code_edit` | No code self-modification |
| `self_modification` | Hardcoded blocked |
| `auto_commit` | No auto-commit |
| `auto_push` | No auto-push |
| `production_deploy` | No deploy |
| `secret_access` | No secret access |
| `external_send` | No Slack/email/Telegram |
| `browser_automation` | No uncontrolled browser automation |
| Description contains `auto-commit` | Pattern blocked |
| Description contains `auto-push` | Pattern blocked |
| Description contains `deploy to production` | Pattern blocked |
| Description contains `api_key`, `secret_key`, `private_key` | Credential pattern blocked |
| Description contains `bypass approval` | Approval bypass blocked |

---

## What Remains for NUS 1

NUS 1 (full self-improvement autonomy) is **NOT STARTED** and **LOCKED for a future sprint**.

NUS 1 would add:
- Autonomous capability self-upgrade
- Self-directed code improvement proposals with auto-execution
- Unrestricted self-modification workflows

**Wave 4 explicitly does not implement any of these.**

---

## US13 Voice Status

**US13 voice remains HOLD / UNSAFE / PARKED.**

- No wake word detection in this sprint.
- No hands-free voice automation.
- Voice runtime is disabled/excluded from release readiness.

---

## Event Types Added

```python
EVENT_EXPANSION_OPPORTUNITY_DETECTED   = "expansion_opportunity_detected"
EVENT_EXPANSION_PROPOSAL_CREATED       = "expansion_proposal_created"
EVENT_EXPANSION_PROPOSAL_BLOCKED       = "expansion_proposal_blocked"
EVENT_EXPANSION_APPROVAL_REQUIRED      = "expansion_approval_required"
EVENT_EXPANSION_VALIDATION_PLAN_GENERATED = "expansion_validation_plan_generated"
```

---

## API Routes

| Route | Method | Description |
|---|---|---|
| `/v1/wave4/expansion/status` | GET | Module status, flags, queue summary |
| `/v1/wave4/expansion/opportunities` | GET | Detect Wave 1–3 expansion opportunities |
| `/v1/wave4/expansion/gaps` | GET | Capability gap analysis |
| `/v1/wave4/expansion/queue` | GET | Current expansion proposal queue |
| `/v1/wave4/expansion/propose` | POST | Create a safe local expansion proposal |
| `/v1/wave4/expansion/validate` | POST | Generate validation plan for a proposal |

---

## Safety Summary

| Safety Property | Status |
|---|---|
| Reuses US17 adversarial safety | YES |
| No approval bypass | YES |
| No autonomous self-modification | YES |
| No auto-commit or auto-push | YES |
| No deploy/release automation | YES |
| No external sends | YES |
| No secret access | YES |
| No uncontrolled browser automation | YES |
| Blocked events logged | YES |
| NUS 1 not started | YES |
| US13 voice parked | YES |

---

## Retest Commands

```bash
cd /Users/user/OpenJarvis

# Wave 4 tests only
uv run python -m pytest tests/wave/test_wave4.py -v --tb=short

# Full wave + core regression
uv run python -m pytest tests/wave tests/workbench/test_us15_foundation.py tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q --tb=short

# Git status (must be clean before commit)
git status --short
git diff --check
```

---

## Capability Status

```
capability_id: wave4_autonomous_expansion
status: ready
summary: Wave 4 Epic H: Supervised expansion scaffolding.
         Proposal-only. No auto-execute, no code self-modification,
         no auto-commit, no deploy.
         NUS 1 not started. US13 voice HOLD/UNSAFE/PARKED.
```

Statuses for specific action types:
- `ready` — supervised local proposal workflows (read-only, proposal-only)
- `needs_approval` — proposal execution or high-risk expansion types
- `blocked` — deploy/self-modification/secret/external-send bypass attempts
