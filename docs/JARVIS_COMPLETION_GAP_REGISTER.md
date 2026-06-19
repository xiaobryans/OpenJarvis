# Jarvis Completion Gap Register — 4/5 Completion Matrix

**Last updated:** 2026-06-19
**Sprint:** Private Daily-Driver Hardening Mega Sprint (Prompt 2)
**Base HEAD:** c98d88d1 | **Sprint HEAD:** (uncommitted — Prompt 2)
**Branch:** localhost-get-tool

---

## Purpose

This register is the authoritative 4/5 Completion Matrix for Jarvis as a
universal private AI operating system. No vague future scope. Every item
is classified with current score, target score, blocker, and acceptance criteria.

**Score scale (0–5 only):**
- 0 = Not started / missing entirely
- 1 = Stub/placeholder only
- 2 = Partial — key path exists but incomplete
- 3 = Functional for happy path; adversarial/edge cases missing
- 4 = Daily-driver ready (`DAILY_DRIVER_ACCEPT` minimum)
- 5 = Public/hostile-grade (`PUBLIC_READY_ACCEPT`)

**Minimum target:** current_score ≥ **4/5** (`DAILY_DRIVER_ACCEPT`) for all required items.
**5/5 required** where public/hostile-ready applies (security, governance, NUS gates).

Matrix columns use **Score** = current_score (0–5) and **Target** = target_score (0–5).
Scorecard uses explicit **current_score/target_score** notation (e.g. 3/5 → 4/5).

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
| Real worker dispatch after planning | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | COS/GM calls execute_worker() for each selected worker; status="executed" when workers run |
| Runtime trace events emitted | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | COS_GM, MANAGER_ACTIVATION, WORKER_EXECUTION, VALIDATION, NUS_FEEDBACK, FINAL_RESPONSE events all emitted |
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
| `DoctorValidationWorkerAdapter` | EXISTING (upgraded) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Full check suite dispatch via run_all_checks(); proven in tests; 44 checks dispatched |
| `NUSLearningWorkerAdapter` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Reads LearningStore.summarize(); dry-run safe |
| `CostAnalysisWorkerAdapter` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Reads LearnedRouter.get_status(); dry-run safe |
| `FileInspectionWorkerAdapter` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Reads targeted files (read-only), returns line-range snippets and metadata |
| `CodingSafeWorkerAdapter` | EXISTING (new) | 3 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Provider Sprint | `BLOCKED_PROVIDER` (patch_propose, repair_loop) | Set OPENAI_API_KEY or ANTHROPIC_API_KEY | Coding proof path: classify, inspect, test_run, diff_report, rollback_plan all 4/5. patch_propose/repair_loop require LLM → BLOCKED_PROVIDER → 3/5 → 4/5 when key configured |
| Blocked actions refused by all adapters | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | auto_push, production_deploy, external_send, us13_voice refused at adapter level; proven in adversarial injection tests |
| NUS gate checked before execution | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Safe local actions pass; non-dry-run gates via LowRiskExecutionManager; proven in orchestrator tests |
| Coding proof path: classify + inspect + test + diff + rollback | EXISTING (new) | 3 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Provider Sprint | `BLOCKED_PROVIDER` (LLM code generation) | See §8 provider actions | Sub-paths available: classify (4/5), inspect (4/5), test_run (4/5), diff_report (4/5), rollback_plan (4/5). Full path (patch_propose + repair_loop) needs LLM |

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
| Full doctor run covers all 44+ checks | EXISTING (updated) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `run_all_checks()` includes universal front door + worker adapter checks (44 checks confirmed) |

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

### 14. Execution Capability Registry (NEW — Prompt 1)

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `ExecutionCapabilityRegistry` class | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Classifies all actions by risk/approval/rollback/provider/status; singleton available |
| All hard-gate actions classified blocked | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | auto_push, auto_merge, production_deploy, external_send, secret_access, us13_voice all BLOCKED_SAFETY in registry |
| Safe local actions classified available | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | local_analysis, doctor_run, nus_dry_run, routing_dry_run, local_validation all STATUS_AVAILABLE |
| Coding proof path actions registered | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | coding_task_classify, coding_file_inspect, coding_test_run, coding_diff_report, coding_rollback: AVAILABLE; coding_patch_propose, coding_repair_loop: DEGRADED/BLOCKED_PROVIDER |
| Provider-gated actions disclose blockers | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | OPENAI, ANTHROPIC, OPENROUTER keys: BLOCKED_PROVIDER with exact env var and fallback_behavior |
| Unknown action returns blocked (not silent) | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | `get_or_blocked()` returns BLOCKED_IMPLEMENTATION for any unregistered action |
| Provider status check | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `check_provider_status()` checks env and cloud-keys.env for each key |
| Proven in tests | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | 25+ tests in test_capability_registry.py pass |

---

### 15. Runtime Trace / Observability (NEW — Prompt 1)

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `RuntimeTraceStore` / `OrchestratorTrace` | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | In-memory trace store; up to 200 traces retained; singleton |
| Task trace ID assigned at front-door | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | trace_id set at JarvisFrontDoor entry; propagated through COS/GM; present in FrontDoorResult.metadata |
| FRONT_DOOR event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted at front-door entry with request_id, intent, project_id |
| ROUTING event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted when request routed to COS/GM with adapter info |
| COS_GM event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted at COS/GM entry with risk/complexity classification |
| MANAGER_ACTIVATION event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted for each activated manager |
| WORKER_EXECUTION event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted for each dispatched worker with status and nus_gate_passed |
| VALIDATION event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted when validation_required=True with worker success ratio |
| NUS_FEEDBACK event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted after activation plan with nus_feedback_available flag |
| BLOCKER event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted when blocked action detected at front-door or COS/GM |
| FINAL_RESPONSE event | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | Emitted at end with final status and elapsed_ms |
| Replay log | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | `replay_log(trace_id)` returns structured pipeline steps with elapsed_from_start |
| No raw CoT in trace events | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | `no_raw_chain_of_thought=True` on every RuntimeTraceEvent |
| Trace persistence to disk | MISSING | 0 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Persistence Sprint | `BLOCKED_IMPLEMENTATION` | — | Traces persisted to ~/.jarvis/traces/; survives restart |
| Proven in tests | EXISTING (new) | 4 | 4 | `DAILY_DRIVER_ACCEPT` | — | — | — | 30+ tests in test_runtime_trace.py pass |

---

### 16. Adversarial / Injection Test Suite (NEW — Prompt 1)

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| Blocked actions blocked via requested_actions injection | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | auto_push/merge/deploy/send/voice/secret all blocked when in requested_actions; proven in test_adversarial_injection.py |
| Prompt injection in user_input text | EXISTING (new) | 3 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Hardening Sprint | — | — | Jailbreak phrasing routes safely; 5/5 requires LLM-based injection detection |
| Worker adapter refuses blocked action_types | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | All adapters refuse auto_push, external_send, production_deploy, us13_voice, secret_access, browser_purchase at execute() level |
| Malicious metadata injection | EXISTING (new) | 3 | 5 | `PLANNED_IN_EXISTING_PROMPT` | Hardening Sprint | — | — | Top-level requested_actions checked; nested injection and fake key injection tested; 5/5 requires full metadata sanitization |
| Capability registry unknown action blocked | EXISTING (new) | 5 | 5 | `PUBLIC_READY_ACCEPT` | — | — | — | get_or_blocked() returns BLOCKED for any unknown action; no silent capability grant |

---

### 17. Previously Missing Register Items — Classification Map

The sprint prompt listed 11 items to check. Status:

| Item | Coverage | Register Section |
|------|----------|-----------------|
| execution capability registry | **ADDED** §14 | capability_registry.py |
| router trace object | **ADDED** §15 (runtime_trace.py) | DAILY_DRIVER_ACCEPT |
| memory quality test matrix | `PLANNED_IN_EXISTING_PROMPT` — core memory baseline not required for this sprint runtime | See §12 NUS / memory persistence |
| voice state-machine acceptance matrix | `BLOCKED_SAFETY` — US13 HOLD/PARKED; not to be opened | See §9 US13 Voice |
| connector dry-run simulator | **ADDED** in capability_registry.py as `connector_dry_run` action (STATUS_AVAILABLE) | §14 |
| adversarial code/task injection test suite | **ADDED** §16 | test_adversarial_injection.py |
| orchestrator replay log | **ADDED** §15 (`replay_log()` method on RuntimeTraceStore) | DAILY_DRIVER_ACCEPT |
| manager/worker capability coverage matrix | **ADDED** §14 (ExecutionCapabilityRegistry classifies all worker action types) | DAILY_DRIVER_ACCEPT |
| human correction ingestion schema | `PLANNED_IN_EXISTING_PROMPT` — advanced NUS work; not required for core runtime path | Future NUS Sprint |
| stale memory conflict detector | `PLANNED_IN_EXISTING_PROMPT` — memory persistence sprint; not required for core runtime path | Future Persistence Sprint |
| provider/key/blocker dashboard | **PARTIALLY ADDED** — capability_registry.check_provider_status() + get_status_summary() provide structured provider/blocker data; HTTP dashboard route is `PLANNED_IN_EXISTING_PROMPT` | §14 + Future UI Sprint |

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

## Prompt 2 — Private Daily-Driver Hardening Items (NEW)

### 18. Provider Readiness and Blocker Dashboard

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `get_provider_readiness()` | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Returns structured report; no key values; 3 providers checked; doctor-visible |
| LLM-in-loop orchestration (OpenAI) | NEW | 2 | 4 | `BLOCKED_PROVIDER` | Prompt 2 | `OPENAI_API_KEY` missing | Set `OPENAI_API_KEY` in `~/.jarvis/cloud-keys.env` | Real LLM call succeeds; validated output |
| LLM-in-loop orchestration (Anthropic) | NEW | 2 | 4 | `BLOCKED_PROVIDER` | Prompt 2 | `ANTHROPIC_API_KEY` missing | Set `ANTHROPIC_API_KEY` in `~/.jarvis/cloud-keys.env` | Real LLM call succeeds |
| LLM-in-loop orchestration (OpenRouter) | NEW | 2 | 4 | `BLOCKED_PROVIDER` | Prompt 2 | `OPENROUTER_API_KEY` missing | Set `OPENROUTER_API_KEY` in `~/.jarvis/cloud-keys.env` | Multi-model routing works |
| `coding_patch_propose` (real LLM) | NEW | 1 | 4 | `BLOCKED_PROVIDER` | Prompt 2 | Any LLM key missing | Set any LLM key | Produces real patch; validated by tests |
| `check_provider_readiness` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | PASS when key present; WARN when missing; never FAIL without error |

---

### 19. Trace Persistence

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| Disk trace writes (`~/.jarvis/traces/`) | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Traces written as JSONL; readable after restart |
| `load_trace_from_disk(trace_id)` | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Cross-restart trace retrieval works |
| Bounded retention (_MAX_TRACE_FILES=500) | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Old files pruned when over limit |
| Graceful disk-unavailable degradation | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Disk failure → in-memory only; no crash |
| `check_trace_persistence` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Probe write + status visible in doctor |
| Front-door auto-persist on completion | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Every completed request has trace on disk |

---

### 20. ProjectRegistry Persistence

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `persist_registry()` to JSON | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Registry survives restart; all projects reloaded |
| `load_registry()` from JSON | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | OMNIX and OpenJarvis always present after load |
| OpenJarvis project auto-registration | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | `openjarvis` project registered alongside OMNIX |
| Atomic write (tmp + rename) | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | No corrupt file on crash mid-write |
| Personal/no-project tasks unaffected | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Works without any persisted project |
| `check_project_registry_persistence` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | PASS when OMNIX+OpenJarvis present |

---

### 21. Runtime Recovery

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `RuntimeStatusRecord` with no raw CoT | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Snapshot recorded; `no_raw_chain_of_thought=True` |
| `FailedTaskRecord` (no raw CoT) | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Failed tasks recorded with blocker type + safe resume |
| Disk persistence (`runtime_recovery.json`) | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Survives restart; unresolved failures visible |
| No automatic dangerous resume | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | `safe_resume_guidance` only; no auto-re-run |
| `check_runtime_recovery` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Unresolved failure count visible in doctor |

---

### 22. Connector Dry-Run Framework

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| Gmail dry-run capability | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | `plan_connector_action("gmail", ...)` returns plan; no live call |
| Calendar dry-run capability | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Same as Gmail |
| Slack dry-run (safety-blocked sends) | NEW | 4 | 5 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | `BLOCKED_SAFETY` (live sends) | Per-message authorization | Dry-run plan produced; live sends permanently blocked without auth |
| Telegram dry-run (safety-blocked sends) | NEW | 4 | 5 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | `BLOCKED_SAFETY` (live sends) | Per-message authorization | Same as Slack |
| GitHub dry-run capability | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | PR/issue plans producible without live call |
| Drive dry-run capability | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | File listing plans producible |
| `check_connector_dryrun_framework` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | 6 connectors registered; PASS in doctor |

---

### 23. Connector Auth Manager Classification

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| BLOCKED_IMPLEMENTATION (no workers) | CLASSIFIED | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | `BLOCKED_IMPLEMENTATION` | Code change required | Explicitly classified; not combined with other blockers |
| BLOCKED_CREDENTIALS (no tokens) | CLASSIFIED | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | `BLOCKED_CREDENTIALS` | Set tokens in `cloud-keys.env` | Explicitly classified |
| BLOCKED_SAFETY (live secret access) | CLASSIFIED | 4 | 5 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | `BLOCKED_SAFETY` (permanent) | None — intentional | Classified as permanent; no bypass |
| BLOCKED_USER_AUTHORIZATION (per-connector) | CLASSIFIED | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | `BLOCKED_USER_AUTHORIZATION` | `jarvis connect <connector>` | Classified; unblockable after impl+creds |

---

### 24. Memory Quality Matrix

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `MemoryQualityMatrix.assess()` | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Stale/no-provenance/low-confidence entries flagged; quality score computed |
| `StaleConflictDetector` | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Stale entries + prefix-based conflicts detected |
| `insufficient_evidence()` response | NEW | 4 | 5 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Structured response; never auto-fills missing data |
| Semantic deduplication | NEW | 1 | 4 | `BLOCKED_PROVIDER` | Prompt 3 | Embedding model required | Set LLM key | Prefix-only for now; semantic requires embedding |
| `check_memory_quality_matrix` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Entry count, stale count, conflict count visible |

---

### 25. Human Correction Ingestion

| Item | Classification | Score | Target | Status | Assigned Prompt | Blocker | Bryan Action | Acceptance Criteria |
|------|---------------|-------|--------|--------|-----------------|---------|--------------|---------------------|
| `CorrectionRecord` schema | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | 6 categories; provenance required; no raw CoT |
| JSONL append-only disk persistence | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Corrections survive restart |
| NUS hook (best-effort) | NEW | 3 | 4 | `PLANNED_IN_EXISTING_PROMPT` | Prompt 3 | NUS `LearningStore` API TBD | — | Hook writes to NUS; confirmed with integration test |
| `check_human_correction_store` doctor | NEW | 4 | 4 | `DAILY_DRIVER_ACCEPT` | Prompt 2 | — | — | Count and pending visible in doctor |

---

### 26. Cursor/Windsurf Replacement Evidence

| Item | Evidence Status | Score | Blocker | Notes |
|------|----------------|-------|---------|-------|
| Jarvis-only bug fix | NO EVIDENCE | 1 | `BLOCKED_PROVIDER` | Requires real LLM key for code generation |
| Jarvis-only medium feature | NO EVIDENCE | 1 | `BLOCKED_PROVIDER` | Same |
| Failed-test repair | PARTIAL | 2 | `BLOCKED_PROVIDER` | `CodingSafeWorkerAdapter._run_tests()` can detect failures; LLM fix blocked |
| Multi-file change | NO EVIDENCE | 1 | `BLOCKED_PROVIDER` | `FileInspectionWorkerAdapter` + planning only |
| Rollback proof | PARTIAL | 2 | — | `_rollback_plan()` produces `git restore` plan; requires Bryan auth |
| Validation proof | PARTIAL | 4 | — | Full test suites run via worker; doctor validation proven; status=`DAILY_DRIVER_ACCEPT` for validation path |
| Model/provider sufficiency proof | PARTIAL | 4 | — | `ExecutionCapabilityRegistry` + `provider_readiness` prove exact blockers; status=`DAILY_DRIVER_ACCEPT` for sufficiency reporting |
| **Overall verdict** | **HOLD** | 1/5 | `BLOCKED_PROVIDER` | Set any LLM key to start collecting real evidence; target=4/5 |

---

### 27. Memory Storage Backend (Rust Extension)

Pre-existing test failure — classified in blocker ledger (not a Prompt 2 regression).

| Item | Classification | current_score | target_score | Status | Assigned Prompt | Blocker | Bryan Action | Blocks Prompt 2 memory 4/5? | Acceptance Criteria |
|------|---------------|---------------|--------------|--------|-----------------|---------|--------------|----------------------------|---------------------|
| `openjarvis_rust` native extension | EXISTING (not built) | 1 | 4 | `BLOCKED_IMPLEMENTATION` | Memory/Storage Sprint | Native extension not compiled into `.venv`; `ModuleNotFoundError: No module named 'openjarvis_rust'` | Optional — only if advanced storage backend needed: `uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml` (requires rustc ≥ 1.88) | **No** — does not block Prompt 2 `JarvisMemory` quality matrix (uses `memory/store.py` SQLite path; doctor check passes) | Extension import succeeds; `RUST_AVAILABLE=True` |
| `tests/memory/test_storage_suite.py` | EXISTING | 1 | 4 | `BLOCKED_IMPLEMENTATION` | Memory/Storage Sprint | 11 tests fail when `openjarvis_rust` missing; affects `tools/storage/sqlite.py` and hybrid backend only | Same as above — build step, not a product credential | **No** for Prompt 2 daily-driver memory quality path; **Yes** for advanced storage backend 4/5 | Full storage suite passes after extension built |
| Rust toolchain (rustc ≥ 1.88) | ENV | 0 | 4 | `BLOCKED_HARDWARE` | Memory/Storage Sprint | Maturin build requires rustc ≥ 1.88 if extension not pre-built | Install/update Rust toolchain if build attempted | Only if attempting maturin build | `rustc --version` ≥ 1.88; maturin develop succeeds |

**Summary:** Prompt 2 memory readiness (`MemoryQualityMatrix`, `StaleConflictDetector`, `JarvisMemory` at `~/.jarvis/memory.db`) is **not blocked** by this failure. The failing suite covers an optional/advanced native storage backend. Classification: `BLOCKED_IMPLEMENTATION` (extension not built). Bryan action: **not required** for Prompt 2 daily-driver memory path; optional build step if advanced storage is needed.

---

## Status Count Table

Counts below use the **Status** column only. No plain "ACCEPT" — split into `DAILY_DRIVER_ACCEPT` (current_score ≥ 4/5) and `PUBLIC_READY_ACCEPT` (current_score = 5/5).

| Category | Items | DAILY_DRIVER_ACCEPT | PUBLIC_READY_ACCEPT | PLANNED_IN_EXISTING_PROMPT | BLOCKED_PROVIDER | BLOCKED_IMPLEMENTATION | BLOCKED_CREDENTIALS | BLOCKED_SAFETY | BLOCKED_USER_AUTHORIZATION | BLOCKED_HARDWARE | OPTIONAL_BACKLOG |
|----------|-------|---------------------|---------------------|----------------------------|------------------|------------------------|---------------------|----------------|----------------------------|------------------|------------------|
| Universal Front Door | 7 | 5 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| COS/GM Runtime | 8 | 4 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Activation Planner + NUS | 8 | 4 | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Worker Adapters | 9 | 6 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| OMNIX Universalization | 8 | 2 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ProjectRegistry/Multi-Project | 3 | 0 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| connector_auth_manager | 4 | 0 | 0 | 2 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| release_packaging_manager | 3 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 2 | 0 | 0 |
| Provider/Model Sufficiency | 7 | 1 | 1 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| US13 Voice | 11 | 0 | 0 | 0 | 2 | 8 | 0 | 1 | 0 | 0 | 0 |
| Doctor/Readiness | 7 | 6 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Documentation | 7 | 4 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| NUS Full Stack | 5 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Governance & Safety | 5 | 1 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Execution Capability Registry | 8 | 6 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Runtime Trace / Observability | 15 | 13 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Adversarial / Injection Suite | 5 | 0 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Provider Readiness Dashboard (P2) | 6 | 2 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 |
| Trace Persistence (P2) | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ProjectRegistry Persistence (P2) | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Runtime Recovery (P2) | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Connector Dry-Run Framework (P2) | 7 | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Connector Auth Manager Classification (P2) | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Memory Quality Matrix (P2) | 5 | 4 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| Human Correction Ingestion (P2) | 4 | 3 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Cursor/Windsurf Replacement Evidence (P2) | 5 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| Memory Storage Backend (Rust) (P2 ledger) | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 1 | 0 |
| **TOTAL** | **171** | **91** | **28** | **20** | **15** | **10** | **2** | **2** | **2** | **1** | **0** |

---

## Private Daily-Driver Scorecard (Prompt 2)

**Score scale:** 0–5 only. Daily-driver minimum = **4/5**. Public/hostile-ready = **5/5**.

*A category reaches DAILY_DRIVER_ACCEPT only if current_score ≥ 4/5 and integrated, tested, and observable per register criteria.*

| Category | current_score | target_score | Status | Blocker | Next Action |
|----------|---------------|--------------|--------|---------|-------------|
| AI assistant replacement | 3/5 | 4/5 | `BLOCKED_PROVIDER` | No LLM keys — natural language understanding limited | Set OPENAI_API_KEY or ANTHROPIC_API_KEY |
| Coding agent | 2/5 | 4/5 | `BLOCKED_PROVIDER` | `coding_patch_propose` + `coding_repair_loop` blocked without LLM key | Set any LLM key |
| Project/task routing | 4/5 | 4/5 | `DAILY_DRIVER_ACCEPT` | — | Front door → COS/GM → worker dispatch proven; universal not OMNIX-only |
| Memory/context continuity | 3/5 | 4/5 | `PLANNED_IN_EXISTING_PROMPT` | Quality matrix + stale detection added; NUS hook partial; no cross-session semantic recall | Prompt 3: semantic embeddings |
| Tool/connector execution | 3/5 | 4/5 | `BLOCKED_CREDENTIALS` | Connectors registered + dry-run planning ready; live execution blocked until credentials + auth | Configure connector credentials |
| Model/provider routing | 3/5 | 4/5 | `BLOCKED_PROVIDER` | Registry + readiness dashboard built; no real model routing until any LLM key set | Set any LLM key |
| Cost/provider fallback | 3/5 | 4/5 | `BLOCKED_PROVIDER` | Fallback logic designed; cannot execute without provider key | Set any LLM key |
| Safety/approvals | 5/5 | 5/5 | `PUBLIC_READY_ACCEPT` | Hard gates enforced; adversarial tests pass; no raw CoT; BLOCKED_SAFETY correct | None — fully hardened |
| Observability/debugging | 4/5 | 4/5 | `DAILY_DRIVER_ACCEPT` | Trace persistence + doctor checks + replay by trace_id all working | Add metric aggregation in Prompt 3 |
| Reliability/recovery | 4/5 | 4/5 | `DAILY_DRIVER_ACCEPT` | RuntimeRecoveryStore + ProjectRegistry persistence + restart recovery | Prompt 3: auto-heal integration |
| Cursor/Windsurf replacement | 1/5 | 4/5 | `BLOCKED_PROVIDER` | Evidence collection HOLD — all real coding evidence blocked by missing LLM key | Set any LLM key, then collect evidence |
| Single AI platform replacement | 1/5 | 4/5 | `BLOCKED_PROVIDER` | Not claimable without real LLM + connector execution + proven coding agent | Set LLM key; authorize connectors; collect evidence |

**Scorecard summary:** 3 of 12 categories at `DAILY_DRIVER_ACCEPT` (current_score ≥ 4/5); 1 at `PUBLIC_READY_ACCEPT` (5/5); 8 below daily-driver minimum (4/5).

**Verdict: NOT DAILY_DRIVER_ACCEPT** — overall private daily-driver platform not at 4/5 minimum.
Primary blocker: `BLOCKED_PROVIDER` for all LLM-dependent capabilities.
Bryan action: Set any LLM key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`) in `~/.jarvis/cloud-keys.env`.

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
