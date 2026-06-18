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

## Wave 1 — Foundation

### What IS implemented in this sprint

**Epic A — Skill Platform** (`src/openjarvis/wave/skill_platform.py`)
- `WaveSkillManifest` dataclass: skill_id, name, version, approval_policy, risk_level, induction_approved
- `WaveSkillRegistry`: register / list / get with approval gate enforcement
- Built-in skills: coding_workbench, terminal_executor, diff_reviewer, browser_automation (all accepted), research_web (scaffolded, pending approval)
- Wraps existing `skills/jarvis_registry.py` — does NOT duplicate it
- Approval policy enforced: `hard_gate` → blocked without explicit approval, `requires_approval` → pending_approval state
- Exposed in capabilities registry as `wave1_skill_platform` (status: `requires_setup`)
- Doctor check 28: `wave1_skill_platform`

**Epic B — Automation Platform** (`src/openjarvis/wave/automation_platform.py`)
- `AutomationTrigger` dataclass: trigger_id, name, trigger_type (cron/event/webhook/manual), schedule, approval_policy, risk_level, enabled
- `AutomationRegistry`: register / enable / disable / list / get
- All triggers disabled by default on registration
- High/critical risk or requires_approval policy → enable() returns approval_required
- References existing `scheduler/` — does NOT duplicate it
- Exposed in capabilities registry as `wave1_automation_platform` (status: `requires_setup`)
- Doctor check 29: `wave1_automation_platform`

**Epic C — Knowledge Platform** (`src/openjarvis/wave/knowledge_platform.py`)
- `KnowledgeSource` dataclass: source_id, name, source_type (file/url/database/connector/memory), access_policy, pii_risk
- `KnowledgeSourceRegistry`: register / list / get with PII approval gate
- Built-in scaffolded sources: apple_notes, apple_contacts, dropbox (all require_approval, pii_risk=True)
- Public sources (access_policy=public, pii_risk=False) register without approval
- References existing `connectors/` — does NOT duplicate them
- Exposed in capabilities registry as `wave1_knowledge_platform` (status: `requires_setup`)
- Doctor check 30: `wave1_knowledge_platform`

**Epic D — Research Platform** (`src/openjarvis/wave/research_platform.py`)
- `ResearchProvider` dataclass: provider_id, name, provider_type (web_search/news/academic/internal), approval_policy
- `ResearchProviderRegistry`: register / list / get with web-search approval gate
- Built-in providers: hackernews (auto), news_rss (auto), web_search_generic (requires_setup + approval), deep_research_agent (requires approval)
- No unauthorized scraping: web_search providers require approval
- References existing `connectors/hackernews`, `agents/deep_research` — does NOT duplicate
- Exposed in capabilities registry as `wave1_research_platform` (status: `requires_setup`)
- Doctor check 31: `wave1_research_platform`

**Wave Platform Registry** (`src/openjarvis/wave/platform_registry.py`)
- `WavePlatformRecord`: per-epic status, acceptance criteria, dependencies, risk areas
- `WavePlatformRegistry`: get_all / get_by_wave / get(epic_id)
- `get_wave_platform_summary()`: used by Mission Control / doctor
- Doctor check 27: `wave1_platform_registry`
- Doctor check 32: `wave2_4_not_claimed_ready` — verifies Wave 2–4 are NOT claiming ready

**Capabilities Registry** (`src/openjarvis/workbench/capabilities_registry.py`)
- 4 new capability IDs added: `wave1_skill_platform`, `wave1_automation_platform`, `wave1_knowledge_platform`, `wave1_research_platform`
- All report `requires_setup` — no fake ready claims
- `get_capabilities_summary()` now reports `wave1_scaffolded: true`, `wave2_3_4_not_implemented: true`

**Tests** (`tests/wave/test_wave1_foundation.py`)
- `TestWaveSkillPlatform` (8 tests): registry, builtins, approval gates
- `TestWaveAutomationPlatform` (6 tests): register, disable-by-default, approval gates
- `TestWaveKnowledgePlatform` (5 tests): registry, PII approval gates
- `TestWaveResearchPlatform` (5 tests): registry, web search approval gates
- `TestWavePlatformRegistry` (6 tests): all epics, wave1 scaffolded, wave2-4 not_implemented
- `TestWaveCapabilities` (3 tests): presence, no fake ready, summary flags
- `TestWaveSafetyIntegration` (4 tests): hard gates, destructive disable, web scraping blocked, PII blocked

---

### What is NOT implemented (Wave 1 next slices — requires explicit Bryan approval)

| Item | Status | Required next action |
|---|---|---|
| Skill induction pipeline (LLM-based) | Not implemented | Epic A next slice |
| Skill execution engine | Not implemented | Epic A next slice |
| Automation cron wiring to `scheduler/` | Not implemented | Epic B next slice |
| Automation event bus integration | Not implemented | Epic B next slice |
| Knowledge ingestion pipeline | Not implemented | Epic C next slice |
| Hybrid search (vector + BM25) | Not implemented | Epic C next slice |
| Web search execution (Serper/Tavily API) | REQUIRES_USER_ACTION (API key + approval) | Epic D next slice |
| Deep research loop | Not implemented | Epic D next slice |

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
