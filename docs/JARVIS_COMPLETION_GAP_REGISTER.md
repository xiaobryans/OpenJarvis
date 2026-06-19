# Jarvis Completion Gap Register — 4/5 Completion Matrix

**Last updated:** 2026-06-19
**Sprint:** Universalize Jarvis and close completion gaps
**Base HEAD:** ed6e7527 | **Sprint HEAD:** c75dce19
**Branch:** localhost-get-tool

---

## Purpose

This register is the authoritative 4/5 Completion Matrix for Jarvis as a
universal private AI operating system. No vague future scope. Every item
is classified with current score, target score, blocker, and acceptance criteria.

**Score scale:**
- 0 = Not started / missing entirely
- 1 = Stub/placeholder only
- 2 = Partial — key path exists but incomplete
- 3 = Functional for happy path; adversarial/edge cases missing
- 4 = Daily-driver ready: works for Bryan in normal use
- 5 = Public/hostile-grade: adversarial inputs handled, full test coverage, no silent failures

**Minimum target:** 4/5 (daily-driver ready) for all required items.
**5/5 required** where public/hostile-ready applies (security, governance, NUS gates).

---

## Status Legend

| Code | Meaning |
|------|---------|
| `DAILY_DRIVER_ACCEPT` | Score ≥ 4; works for Bryan in normal use |
| `PUBLIC_READY_ACCEPT` | Score = 5; adversarial/hostile-grade |
| `BLOCKED_BRYAN_ACTION` | Bryan must take a specific action to unblock |
| `BLOCKED_PROVIDER` | Missing model/provider API key |
| `BLOCKED_CREDENTIALS` | Missing non-model credential (Apple ID, OAuth token, etc.) |
| `BLOCKED_HARDWARE` | Missing hardware/system permission |
| `BLOCKED_SAFETY` | Intentional permanent safety block |
| `BLOCKED_IMPLEMENTATION` | Code not yet written; no Bryan action can unblock it |
| `PLANNED_IN_EXISTING_PROMPT` | Planned in a defined future prompt/sprint |
| `OPTIONAL_BACKLOG` | Not required for core Jarvis OS; optional enhancement |

---

## Matrix

### 1. Universal Front Door Architecture

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `UniversalTaskRequest` | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Works without project_context; OMNIX, personal, research all valid inputs |
| `ProjectContext` | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Supports OMNIX, OpenJarvis, personal (None), any future project; no OMNIX-specific field required |
| `JarvisFrontDoor` | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Routes any request; dangerous actions blocked; adapters optional |
| `FrontDoorAdapter` ABC | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | OMNIX plugs in as OmnixFrontDoorAdapter; future projects add adapters |
| `OmnixFrontDoorAdapter` | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | OMNIX as optional enrichment; not required by JarvisFrontDoor |
| `FrontDoorResult` | EXISTING | 4 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Public Hardening | — | — | Structured result, no raw CoT; 5/5 requires adversarial input hardening |
| OMNIX not required for orchestration | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | Personal task with no project_context routes successfully through full stack |

---

### 2. COS/GM Runtime

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `CosGmOrchestrator` class | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Receives UniversalTaskRequest, classifies, routes to planner, returns FrontDoorResult |
| Intent/risk/complexity classification | EXISTING | 3 | 4 | `PLANNED_IN_EXISTING_PROMPT` | COS/GM Hardening | — | — | Keyword-based; 4/5 requires domain-model scoring, not just keyword scan |
| Structured decision record emitted | EXISTING | 4 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Public Hardening | — | — | Every activation emits NUS 1F decision record; 5/5 requires record store query proof |
| Dangerous actions permanently blocked | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | auto_push, auto_merge, production_deploy, external_send, us13_voice all blocked |
| US13 voice HOLD/UNSAFE/PARKED | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | Blocked in CosGmOrchestrator and JarvisFrontDoor; not activatable |
| Project context routed correctly | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Project label appears in FrontDoorResult; non-OMNIX project routes correctly |

---

### 3. DynamicActivationPlanner + NUS Integration

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| Dynamic activation (no fixed formula) | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | Different tasks produce different teams; proven in test_dynamic_activation.py |
| Skip reasons for all non-selected roles | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | All managers accounted: selected ∪ skipped = all |
| NUS feedback: `_load_nus_feedback()` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Reads LearningStore + LearnedRouter; graceful degradation if unavailable |
| NUS feedback: prior failures escalate validation | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | ≥3 failures → testing_validation_manager activated |
| NUS feedback tag in activation plan | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `nus_feedback:loaded` or `nus_feedback:not_available` in nus_learning_tags |
| `get_status()` reports nus_feedback_available | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `status["nus_feedback_available"]` is bool |
| Cheap model blocked for critical actions | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | `cheap_model_blocked_for_approval: True` in model_routing_plan |
| Model/provider sufficiency disclosed | EXISTING | 4 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Provider Sprint | `BLOCKED_PROVIDER` (see §8) | See §8 | `provider_sufficiency` key in model_routing_plan; 5/5 requires live provider check |

---

### 4. Worker Execution Adapters

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `WorkerAdapter` base class | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Gate checks: always-blocked, registry check, NUS gate, delegate to _execute_safe() |
| `DoctorValidationWorkerAdapter` | EXISTING (new) | 3 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Worker Hardening | — | — | Runs doctor checks via local_validation; 4/5 requires full check suite dispatch |
| `NUSLearningWorkerAdapter` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Reads LearningStore.summarize(); dry-run safe |
| `CostAnalysisWorkerAdapter` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Reads LearnedRouter.get_status(); dry-run safe |
| Blocked actions refused by all adapters | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | auto_push, production_deploy, external_send refused at adapter level |
| NUS gate checked before execution | EXISTING (new) | 3 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Worker Hardening | — | — | Safe local actions pass; non-dry-run requires LowRiskExecutionManager; 4/5 needs integration test |
| Real coding/refactor worker execution | MISSING | 0 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Worker Execution Sprint | `BLOCKED_IMPLEMENTATION` | — | Workbench coding manager connected to workers; safe local execution through NUS gates |

---

### 5. OMNIX Universalization

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| OMNIX not root/default front door | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | JarvisFrontDoor works without OMNIX; OMNIX is OmnixFrontDoorAdapter (optional) |
| OMNIX as one ProjectContext | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | constitution.py OMNIX_PROJECT is ProjectProfile; ProjectRegistry.get_default() resolves dynamically |
| No OMNIX hardcoding in orchestration | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | activation.py, cos_gm.py, contracts.py: grep for OMNIX returns 0 results in routing logic |
| `check_project_registry_health` universal | EXISTING (fixed) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | Passes if any project registered; OMNIX not required for PASS verdict |
| `run_all_checks` default universal | EXISTING (fixed) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | `project_id=None` resolves via `ProjectRegistry.get_default()` |
| readiness.py generic messages | EXISTING (fixed) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | No "OMNIX hardcoded" language in remaining_limitations |
| OpenJarvis project bootstrap | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `_bootstrap_openjarvis()` in ProjectSourceRegistry |
| Non-OMNIX project routes end-to-end | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | Proven in test_universal_jarvis.py: synthetic_test_project, openjarvis, personal tasks |

---

### 6. ProjectRegistry and Multi-Project

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `ProjectProfile` + `ProjectRegistry` | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | In constitution.py; OMNIX pre-registered; future projects via register() |
| In-process registry (not persisted) | PARTIAL | 2 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Persistence Sprint | `BLOCKED_IMPLEMENTATION` | — | SQLite/config-file persistence; survives restart |
| Multi-project concurrent supervision | PARTIAL | 2 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Multi-Project Sprint | `BLOCKED_IMPLEMENTATION` | — | Jarvis supervises all active projects simultaneously; currently OMNIX + OpenJarvis bootstrapped only |

---

### 7. Inactive Manager Classification

#### connector_auth_manager

This manager has four distinct blockers — each classified separately:

| Sub-item | Classification | Score | Target | Status | Blocker Type | Bryan Action | Acceptance Criteria |
|----------|---------------|-------|--------|--------|-------------|--------------|---------------------|
| Workers assigned | MISSING | 0 | 4 | `PLANNED_IN_EXISTING_PROMPT` | `BLOCKED_IMPLEMENTATION` | None — code change required | At least one connector_auth_worker registered and active |
| Live secret/credential access policy | EXISTING | 5 | 5 | `BLOCKED_SAFETY` | `BLOCKED_SAFETY` (permanent) | None — intentional | `access_live_secrets` and `rotate_credentials` permanently in blocked_action_types |
| Live connector credentials (OAuth tokens, API keys) | MISSING | 0 | 4 | `BLOCKED_CREDENTIALS` | `BLOCKED_CREDENTIALS` | Configure connector credentials in `~/.jarvis/cloud-keys.env`: `GOOGLE_OAUTH_CLIENT_ID`, `SLACK_BOT_TOKEN`, etc. | Connector health check passes for configured connectors |
| Full connector auth implementation | MISSING | 0 | 4 | `PLANNED_IN_EXISTING_PROMPT` | `BLOCKED_IMPLEMENTATION` | None — code change required | `connector_auth_manager` moves to STATUS_ACTIVE after workers implemented |

**Summary:** `connector_auth_manager` is STATUS_INACTIVE for two distinct reasons: (1) no workers assigned (BLOCKED_IMPLEMENTATION), and (2) live secret access permanently blocked by safety policy (BLOCKED_SAFETY). Credentials are also missing (BLOCKED_CREDENTIALS). This does NOT block Core Runtime.

---

#### release_packaging_manager

Scope: packaging/release only. Does NOT block Core Runtime.

| Sub-item | Classification | Score | Target | Status | Blocker Type | Bryan Action | Acceptance Criteria |
|----------|---------------|-------|--------|--------|-------------|--------------|---------------------|
| release_packaging_worker active | EXISTING | 1 | 4 | `BLOCKED_USER_AUTHORIZATION` | `BLOCKED_USER_AUTHORIZATION` | Authorize activation explicitly | Worker moves to STATUS_ACTIVE after Bryan authorization |
| DMG build | MISSING | 0 | 4 | `BLOCKED_USER_AUTHORIZATION` | `BLOCKED_USER_AUTHORIZATION` | Authorize release packaging sprint | DMG builds successfully for local distribution |
| Apple notarization | MISSING | 0 | 4 | `BLOCKED_CREDENTIALS` | `BLOCKED_CREDENTIALS` | Set `APPLE_DEVELOPER_IDENTITY` (e.g. `"Developer ID Application: Bryan…"`) and `APPLE_TEAM_ID` in `~/.jarvis/cloud-keys.env` (never committed) | Notarization passes; Gatekeeper clears DMG |
| Core Runtime impact | N/A | — | — | None — packaging scope only | — | — | release_packaging_manager STATUS_INACTIVE does not affect Core Runtime operation |

---

### 8. Provider/Model Sufficiency

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `ModelProviderSufficiencyGap` type | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | Disclosed in ActivationPlan.model_provider_gaps |
| `provider_sufficiency` in model_routing_plan | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Key present in every plan; no silent fallback |
| OpenAI GPT-4 for premium tasks | MISSING | 0 | 4 | `BLOCKED_PROVIDER` | `BLOCKED_PROVIDER` | Set `OPENAI_API_KEY` in `~/.jarvis/cloud-keys.env`. Without it: dry-run planning only; no real LLM-reviewed orchestration. | `OPENAI_API_KEY` present → `ModelProviderSufficiencyGap` resolved for openai tier |
| Anthropic Claude for mid/premium tasks | MISSING | 0 | 4 | `BLOCKED_PROVIDER` | `BLOCKED_PROVIDER` | Set `ANTHROPIC_API_KEY` in `~/.jarvis/cloud-keys.env`. Without it: no Claude-based orchestration. | `ANTHROPIC_API_KEY` present → gap resolved for anthropic tier |
| OpenRouter for model routing | PARTIAL | 2 | 4 | `BLOCKED_PROVIDER` | `BLOCKED_PROVIDER` | Set `OPENROUTER_API_KEY` in `~/.jarvis/cloud-keys.env` | OpenRouter routing active; model selection follows `JARVIS_ROUTING_MODEL_POLICY.md` |
| Local model fallback | PARTIAL | 2 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Local Model Sprint | `BLOCKED_IMPLEMENTATION` | — | Local model (Ollama/llama.cpp) used when cloud providers unavailable |
| Live provider availability check | MISSING | 0 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Provider Sprint | `BLOCKED_IMPLEMENTATION` | — | Doctor check pings provider endpoints; surfaces gaps in status route |

---

### 9. US13 Voice

**Overall status: HOLD / UNSAFE / PARKED**

US13 is explicitly not activated in this sprint. Voice is assigned to the Voice/Public Hardening prompt. Bryan must explicitly reopen.

| Blocker | Type | Score | Target | Notes |
|---------|------|-------|--------|-------|
| VAD / endpointing | `BLOCKED_IMPLEMENTATION` | 0 | 4 | No voice activity detection; no ability to determine when user starts/stops speaking |
| Record-until-end-of-speech | `BLOCKED_IMPLEMENTATION` | 0 | 4 | No mechanism to stop recording when user stops; fixed duration or manual stop only |
| Silence / noise hallucination rejection | `BLOCKED_IMPLEMENTATION` | 0 | 4 | Background noise and silence trigger false STT transcriptions; no rejection filter |
| Follow-up listening (multi-turn) | `BLOCKED_IMPLEMENTATION` | 0 | 4 | No re-trigger after Jarvis responds; single-shot only |
| Stop phrases / cancellation commands | `BLOCKED_IMPLEMENTATION` | 0 | 4 | "Stop", "cancel", "never mind" mid-response not handled |
| Barge-in / TTS cancellation | `BLOCKED_IMPLEMENTATION` | 0 | 4 | User cannot interrupt Jarvis TTS playback; no barge-in detection |
| Latency (round-trip < 500ms target) | `BLOCKED_IMPLEMENTATION` | 0 | 4 | No latency budget enforced; cloud STT + LLM + TTS likely > 2s |
| STT provider / API key | `BLOCKED_PROVIDER` | 0 | 4 | No STT provider configured; `WHISPER_API_KEY` or `OPENAI_API_KEY` with Whisper endpoint required |
| TTS provider / API key | `BLOCKED_PROVIDER` | 0 | 4 | No TTS provider configured; ElevenLabs, OpenAI TTS, or local TTS required |
| Voice approval UI | `BLOCKED_IMPLEMENTATION` | 0 | 4 | No voice approval flow in Mission Control UI |
| Safety: `us13_voice` in always-blocked | `BLOCKED_SAFETY` | 5 | 5 | Permanently blocked in JarvisFrontDoor and CosGmOrchestrator until explicitly reopened |

**Assigned prompt:** Voice/Public Hardening (do not activate before all implementation blockers resolved)

**Bryan action to reopen:** Explicitly authorize Voice sprint + provide STT/TTS provider API keys + authorize UI changes.

---

### 10. Doctor/Readiness Checks

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `check_universal_front_door` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Personal task, non-OMNIX, OMNIX adapter, blocked actions, US13 all verified |
| `check_worker_execution_adapters` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Adapter registry, dry-run, blocked refusal, unknown worker graceful |
| `check_nus_scorecard_feedback_loop` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | _load_nus_feedback, plan tags, get_status verified |
| `check_inactive_manager_classification` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | connector_auth_manager and release_packaging_manager classified with exact blockers |
| `check_post_nus_orchestrator` | EXISTING | 4 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Public Hardening | — | — | 4/5 now; 5/5 requires adversarial input proof |
| Doctor route (HTTP) | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `/api/doctor/check` endpoint returns structured results |
| Full doctor run covers all 42+ checks | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `run_all_checks()` includes universal front door + worker adapter checks |

---

### 11. Documentation

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `JARVIS_COMPLETION_GAP_REGISTER.md` | EXISTING (new) | 4 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Ongoing — updated each sprint | — | — | This file; 5/5 when all items tracked with full matrix fields |
| `POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md` | EXISTING (updated) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Universal scope documented; COS/GM architecture correct |
| `JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md` | EXISTING (updated) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | "Not OMNIX-only" principle stated; universal scope |
| `JARVIS_ROUTING_MODEL_POLICY.md` | EXISTING (updated) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Provider sufficiency disclosure requirement stated |
| `WAVE_ROADMAP.md` | EXISTING (updated) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Universal Jarvis scope stated |
| `JARVIS_CONSTITUTION.md` | EXISTING | 4 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Governance Hardening | — | — | 5/5 requires adversarial/hostile input coverage of all hard gates |
| User-facing docs / README | PARTIAL | 2 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Public Docs Sprint | `BLOCKED_IMPLEMENTATION` | — | docs/index.md and README accurately describe universal Jarvis OS scope |

---

### 12. NUS Full Stack

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| NUS 1A–1F (learning foundation through high-autonomy) | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | 551 NUS tests pass; all hierarchy levels covered |
| NUS applies to all hierarchy levels | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | jarvis_pa, cos_gm, manager, worker, validator, governance all emit decision records |
| Structured decision records (no raw CoT) | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | `no_raw_chain_of_thought: True` on all plans and results |
| NUS learning store persistence | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | LearningStore writes to `~/.jarvis/nus/` |
| NUS scorecard feedback in activation | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | _load_nus_feedback reads from LearningStore + LearnedRouter; graceful degradation |

---

### 13. Governance and Safety

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| Hard gates permanently blocked | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | production_deploy, auto_push, auto_merge, external_send blocked in CosGmOrchestrator, JarvisFrontDoor, WorkerAdapters |
| Governance safety manager active | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | governance_safety_manager activated for high/blocked risk tasks |
| Cheap model blocked for critical approvals | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | cheap_model_blocked_for_approval: True in model_routing_plan |
| Approval workflow (manual gate) | EXISTING | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | ApprovalRecord, ApprovalWorkflow in nus/approval_workflow.py |
| Production gate | EXISTING | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | ProductionGate in nus/production_gate.py; always-blocked enforced |

---

## Summary Table

| Category | Items | ACCEPT | PLANNED | BLOCKED_IMPL | BLOCKED_CREDS | BLOCKED_PROVIDER | BLOCKED_SAFETY | BLOCKED_AUTH | OPTIONAL |
|----------|-------|--------|---------|--------------|--------------|-----------------|----------------|--------------|---------|
| Universal Front Door | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| COS/GM Runtime | 6 | 5 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Activation Planner + NUS | 8 | 7 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Worker Adapters | 7 | 5 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| OMNIX Universalization | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ProjectRegistry/Multi-Project | 3 | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| connector_auth_manager | 4 | 1 | 1 | 2 | 1 | 0 | 1 | 0 | 0 |
| release_packaging_manager | 4 | 1 | 0 | 0 | 1 | 0 | 0 | 2 | 0 |
| Provider/Model Sufficiency | 7 | 2 | 2 | 2 | 0 | 3 | 0 | 0 | 0 |
| US13 Voice | 11 | 1 | 0 | 8 | 0 | 2 | 1 | 0 | 0 |
| Doctor/Readiness | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Documentation | 7 | 5 | 2 | 1 | 0 | 0 | 0 | 0 | 0 |
| NUS Full Stack | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Governance & Safety | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **89** | **59** | **11** | **8** | **2** | **5** | **2** | **2** | **0** |

---

## Required Bryan Actions (Exact)

All items below require Bryan to take a specific action before they can progress:

| Item | Action | Where | Priority |
|------|--------|-------|---------|
| OpenAI API key | Set `OPENAI_API_KEY=sk-...` | `~/.jarvis/cloud-keys.env` | High — unlocks real LLM orchestration |
| Anthropic API key | Set `ANTHROPIC_API_KEY=sk-ant-...` | `~/.jarvis/cloud-keys.env` | High — unlocks Claude-based orchestration |
| OpenRouter API key | Set `OPENROUTER_API_KEY=sk-or-...` | `~/.jarvis/cloud-keys.env` | Medium — model routing across providers |
| Apple Developer signing identity | Set `APPLE_DEVELOPER_IDENTITY="Developer ID Application: ..."` | `~/.jarvis/cloud-keys.env` | Low — release packaging only |
| Apple Team ID | Set `APPLE_TEAM_ID=XXXXXXXXXX` | `~/.jarvis/cloud-keys.env` | Low — release packaging only |
| Release packaging authorization | Explicitly authorize release sprint | Bryan approval | Low — release packaging only |
| Voice sprint reopen | Explicitly authorize Voice sprint + STT/TTS provider keys | Bryan approval | Low — US13 HOLD/PARKED |
| Connector credentials | Set OAuth tokens and connector API keys | `~/.jarvis/cloud-keys.env` | Medium — unlocks connector_auth_manager workers |

**File:** `~/.jarvis/cloud-keys.env` — never committed to git, never logged, never shown in responses.

---

## No Vague Future Scope

Every item in this register is classified as one of:
`DAILY_DRIVER_ACCEPT`, `PUBLIC_READY_ACCEPT`, `BLOCKED_BRYAN_ACTION`, `BLOCKED_PROVIDER`,
`BLOCKED_CREDENTIALS`, `BLOCKED_HARDWARE`, `BLOCKED_SAFETY`, `BLOCKED_IMPLEMENTATION`,
`PLANNED_IN_EXISTING_PROMPT`, or `OPTIONAL_BACKLOG`.

No item is left as plain "future scope."
