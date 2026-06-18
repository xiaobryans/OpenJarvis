# Jarvis Wave 1–4 Roadmap

**Status as of this sprint:** Wave 1 foundation scaffolded. Wave 2–4 are roadmap items only.

---

## Accepted baseline (US12–US18)

| US | Title | Status |
|---|---|---|
| US12 | Product Polish | ACCEPT |
| US13 | Hands-free Voice | HOLD / UNSAFE / PARKED |
| US14 | Workbench Coding Platform | ACCEPT |
| US15 | Auto Browser + Terminal + Diff Review | ACCEPT |
| US16 | Platform Hardening | ACCEPT |
| US17 | Adversarial Safety & Failure Recovery | ACCEPT |
| US18 | Founder Dogfood + Public Readiness Gate | ACCEPT |

US13 voice remains parked. Do not claim voice accepted.
Voice backlog: real VAD/endpointing, end-of-speech detection, silence rejection,
wake privacy boundary, follow-up sessions, barge-in, streaming STT.

---

## Wave Overview

| Wave | Epics | Status |
|---|---|---|
| Wave 1 — Foundation | A (Skill), B (Automation), C (Knowledge), D (Research) | **Scaffolded** |
| Wave 2 — Professional Intelligence | E (Optimization), F (Skill Packs) | Not implemented |
| Wave 3 — Creation & Media | G (Content & Media Studio) | Not implemented |
| Wave 4 — Jarvis Expansion | H (Autonomous Expansion) | Not implemented |

---

## Wave 1 — Foundation + Local/Founder V1 Execution

### Status: LOCAL/FOUNDER V1 ACCEPTED

All four Wave 1 epics are locally implemented, tested, and event-logged.
Capabilities report `ready` for locally executable features.

---

### What IS implemented (Wave 1 local/founder V1)

**Epic A — Skill Platform** (`src/openjarvis/wave/skill_platform.py`)
- `WaveSkillManifest` dataclass + `WaveSkillRegistry` (register/list/get)
- `run_skill(skill_id, context)` — local execution for safe read-only built-ins:
  - `list_skills` → list all registered wave skills
  - `list_capabilities` → capabilities summary from registry
  - `platform_status` → wave platform summary
  - `coding_workbench`, `diff_reviewer` → capabilities summary
- Approval gates enforced: `browser_automation`, `terminal_executor` require approval; `hard_gate` skills blocked
- Skills without local handlers return `approval_required` (not auto-blocked)
- Event logging: `EVENT_SKILL_EXECUTED` / `EVENT_SKILL_BLOCKED`
- Capability status: `wave1_skill_platform` → **`ready`**
- Doctor check 28: verifies `run_skill("list_skills")` succeeds
- REST: `GET /v1/wave/skills`, `POST /v1/wave/skills/run`
- Induction pipeline: **not yet implemented** (next slice)

**Epic B — Automation Platform** (`src/openjarvis/wave/automation_platform.py`)
- `AutomationTrigger` dataclass + `AutomationRegistry` (register/enable/disable/list/get)
- `dry_run_trigger(trigger_id)` — simulates trigger execution without real side effects:
  - Low-risk `POLICY_AUTO` triggers → returns simulated output
  - High/critical risk → `approval_required`
  - `slack_*`/`email_*` triggers → hard-blocked (external sends never auto-execute)
- All triggers disabled by default on registration
- Event logging: `EVENT_AUTOMATION_DRY_RUN` / `EVENT_AUTOMATION_BLOCKED`
- Capability status: `wave1_automation_platform` → **`ready`**
- Doctor check 29: registers test trigger, verifies dry-run succeeds
- REST: `GET /v1/wave/automations`, `POST /v1/wave/automations/dry-run`
- Live scheduler wiring (cron): **not yet implemented** (next slice)

**Epic C — Knowledge Platform** (`src/openjarvis/wave/knowledge_platform.py`)
- `KnowledgeSource` dataclass + `KnowledgeSourceRegistry`
- `KnowledgeRecord` — normalized knowledge unit (record_id, source_id, title, content, metadata)
- `ingest_local_source(text, source_id)` — ingests plain text, splits into paragraph chunks, stores in-memory
- `ingest_connector_source(source_id)` — checks approval gate; PII/private sources blocked
- `search_knowledge(query)` — keyword search over ingested records
- `get_ingested_records(source_id)` / `get_all_ingested_records()`
- Event logging: `EVENT_KNOWLEDGE_INGESTED` / `EVENT_KNOWLEDGE_BLOCKED`
- Capability status: `wave1_knowledge_platform` → **`ready`**
- Doctor check 30: ingests test content, verifies record count >= 1
- REST: `GET /v1/wave/knowledge/sources`, `POST /v1/wave/knowledge/ingest`
- PII sources (apple_notes, apple_contacts, dropbox): `approval_required` — NOT auto-ingested
- Connector ingestion pipeline, hybrid search: **not yet implemented** (next slice)

**Epic D — Research Platform** (`src/openjarvis/wave/research_platform.py`)
- `ResearchProvider` dataclass + `ResearchProviderRegistry`
- `ResearchSource` + `ResearchResult` — structured query output
- `run_local_query(query, provider_id)`:
  - Searches local ingested knowledge records first
  - Appends platform info as always-available fallback
  - Forbidden terms (captcha, bypass, credential, password, token, secret) → hard-blocked
  - `web_search_generic` provider → `approval_required` (no auto-scraping)
  - Empty query → error
- Event logging: `EVENT_RESEARCH_QUERIED` / `EVENT_RESEARCH_BLOCKED`
- Capability status: `wave1_research_platform` → **`ready`**
- Doctor check 31: queries `"doctor check"`, verifies sources >= 1
- REST: `GET /v1/wave/research/providers`, `POST /v1/wave/research/query`
- Web search (Serper/Tavily), deep research loop: **not yet implemented / requires_setup**

**Wave Platform Registry** (`src/openjarvis/wave/platform_registry.py`)
- `WavePlatformRecord` + `WavePlatformRegistry`
- `get_wave_platform_summary()` for Mission Control / doctor
- Doctor check 27: `wave1_platform_registry`
- Doctor check 32: `wave2_4_not_claimed_ready`

**Capabilities Registry** — Wave 1 statuses updated:
| Capability | Previous | Now |
|---|---|---|
| `wave1_skill_platform` | requires_setup | **ready** |
| `wave1_automation_platform` | requires_setup | **ready** |
| `wave1_knowledge_platform` | requires_setup | **ready** |
| `wave1_research_platform` | requires_setup | **ready** |

**Event types** (`src/openjarvis/workbench/event_log.py`):
`EVENT_SKILL_EXECUTED`, `EVENT_SKILL_BLOCKED`, `EVENT_AUTOMATION_DRY_RUN`,
`EVENT_AUTOMATION_BLOCKED`, `EVENT_KNOWLEDGE_INGESTED`, `EVENT_KNOWLEDGE_BLOCKED`,
`EVENT_RESEARCH_QUERIED`, `EVENT_RESEARCH_BLOCKED`

**REST endpoints**:
- `GET /v1/wave/status` — full platform status
- `GET /v1/wave/skills` — list skills
- `POST /v1/wave/skills/run` — execute skill
- `GET /v1/wave/automations` — list triggers
- `POST /v1/wave/automations/dry-run` — dry-run trigger
- `POST /v1/wave/knowledge/ingest` — ingest text
- `GET /v1/wave/knowledge/sources` — list sources
- `POST /v1/wave/research/query` — local query
- `GET /v1/wave/research/providers` — list providers

**Tests**:
- `tests/wave/test_wave1_foundation.py` — 40 tests (scaffold, registries, approval gates)
- `tests/wave/test_wave1_execution.py` — ~55 tests (execution, events, capabilities)

---

### What is NOT implemented (explicit REQUIRES_USER_ACTION or next slice)

| Item | Status | Next action |
|---|---|---|
| Skill induction pipeline (LLM-based) | Not implemented | Epic A next slice |
| Automation cron wiring (`scheduler/`) | Not implemented | Epic B next slice |
| Automation event bus | Not implemented | Epic B next slice |
| Knowledge connector ingestion (apple_notes, dropbox) | REQUIRES_USER_ACTION (auth + approval) | Epic C next slice |
| Knowledge hybrid search (vector + BM25) | Not implemented | Epic C next slice |
| Web search execution (Serper/Tavily) | REQUIRES_USER_ACTION (API key + approval) | Epic D next slice |
| Deep research loop | Not implemented | Epic D next slice |
| HackerNews live queries | Requires network; scaffolded | Epic D next slice |

---

### How to retest Wave 1

```bash
cd /Users/user/OpenJarvis
uv run python -m pytest tests/wave/ -q --tb=short
```

Expected: all tests pass (foundation + execution).

```bash
uv run python -c "
from openjarvis.wave.skill_platform import run_skill
from openjarvis.wave.knowledge_platform import ingest_local_source, search_knowledge
from openjarvis.wave.research_platform import run_local_query
import json

# Epic A
r = run_skill('list_skills'); print('Epic A:', r.ok, len(r.output), 'skills')

# Epic C
ingest_local_source('Retest content.', 'retest_01')
results = search_knowledge('retest')
print('Epic C:', len(results), 'records found')

# Epic D
qr = run_local_query('wave platform status')
print('Epic D:', qr.ok, len(qr.sources), 'sources')
"
```

---

## Wave 2 — Professional Intelligence (not implemented)

**Dependencies:** Wave 1 Epics A + B fully accepted.

### Epic E — Optimization Platform
- Profile-based model selection optimization
- Cost/latency trade-off analysis per workflow
- Learning from past routing decisions

### Epic F — Professional Skill Packs
- Curated, approved skill bundles (legal, finance, dev, ops)
- Requires approved skill induction pipeline (Epic A)
- Third-party skill vetting process

**Acceptance criteria:** TBD after Wave 1 acceptance.

---

## Wave 3 — Creation & Media (not implemented)

**Dependencies:** Wave 2 Epics E + F fully accepted.

### Epic G — Content & Media Studio
- Document generation, summarization, editing
- Image/diagram generation (approval-gated)
- Media asset management

**Acceptance criteria:** TBD after Wave 2 acceptance.

---

## Wave 4 — Jarvis Expansion (not implemented)

**Dependencies:** All prior waves + explicit owner approval for autonomous capabilities.

### Epic H — Autonomous Expansion
- Self-directed skill discovery
- Autonomous workflow composition
- Requires hard-gate approval for every autonomous action

**Risk areas:** This wave has the highest risk profile. Every action must be hard-gated.
No autonomous expansion without explicit Bryan approval.

**Acceptance criteria:** TBD after Wave 3 acceptance + separate safety review.

---

## Safety rules (all Waves)

All Wave implementations must:
1. Enforce US17 adversarial safety gates (no bypass)
2. Log all blocked/approval-required actions via `WorkbenchEventLog`
3. Report truthful status in capabilities registry and doctor
4. Not claim `ready` without evidence
5. Follow US16 cost/model routing discipline
6. Not touch `~/.openjarvis` except through existing read-only paths
7. Not perform production deploys without explicit approval
8. Not send Slack/email/messages without hard-gate approval

---

## Doctor checks (Wave 1)

| Check # | Name | Expected result |
|---|---|---|
| 27 | `wave1_platform_registry` | pass — WavePlatformRegistry importable, wave1_scaffolded=True |
| 28 | `wave1_skill_platform` | pass — scaffold importable, approval_gate=True |
| 29 | `wave1_automation_platform` | pass — scaffold importable, approval_gate=True |
| 30 | `wave1_knowledge_platform` | pass — scaffold importable, pii_gate=True |
| 31 | `wave1_research_platform` | pass — scaffold importable, approval_gate=True |
| 32 | `wave2_4_not_claimed_ready` | pass — Wave 2–4 all NOT_IMPLEMENTED |

---

## Recommended next Wave 1 slice (after Bryan approves)

1. **Epic A next**: Wire skill execution engine — invoke `WaveSkillManifest.steps` via existing `skills/executor.py`
2. **Epic B next**: Wire automation cron triggers to `scheduler/scheduler.py`
3. **Epic D next**: Integrate web search (Serper/Tavily) with API key + approval gate
4. **Epic C next**: Wire knowledge ingestion for a single connector (hackernews → memory)

Do not start Wave 2 until all 4 Wave 1 epics are fully accepted (not just scaffolded).
