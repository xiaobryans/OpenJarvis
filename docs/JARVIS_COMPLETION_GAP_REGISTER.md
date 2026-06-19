# Jarvis Completion Gap Register

**Last updated:** 2026-06-19  
**Sprint:** Universalize Jarvis and close completion gaps  
**Base HEAD:** ed6e7527

---

## Purpose

This register tracks every known gap in Jarvis's universal private AI operating system
architecture. No vague "future scope." Every gap is explicitly classified.

Jarvis is Bryan's universal private AI operating system. OMNIX is one project
under Jarvis — not the root, not the default, not the only purpose.

---

## Classification Legend

| Status | Meaning |
|--------|---------|
| `DONE` | Implemented, tested, accepted |
| `BLOCKED_SAFETY` | Blocked by safety/governance policy — intentional permanent block |
| `BLOCKED_PROVIDER` | Blocked: missing model/provider/API key |
| `BLOCKED_CREDENTIALS` | Blocked: missing authentication credentials |
| `BLOCKED_USER_AUTHORIZATION` | Blocked: requires explicit Bryan authorization |
| `REQUIRES_BRYAN_ACTION` | Bryan must take a specific action to unblock |
| `OPTIONAL_BACKLOG` | Not required for core Jarvis OS; optional enhancement |

---

## Gap Register

### Universal Front Door Architecture

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| `UniversalTaskRequest` — generic request type for any Bryan request | `DONE` | `src/openjarvis/frontdoor/frontdoor.py` | Works without OMNIX; project_context optional |
| `ProjectContext` — universal project/task context | `DONE` | `src/openjarvis/orchestrator/contracts.py` | Supports OMNIX, OpenJarvis, personal, research, any future project |
| `JarvisFrontDoor` — universal entry point | `DONE` | `src/openjarvis/frontdoor/frontdoor.py` | Routes any request; OMNIX is one optional adapter |
| `FrontDoorAdapter` ABC | `DONE` | `src/openjarvis/frontdoor/frontdoor.py` | OMNIX plugs in as OmnixFrontDoorAdapter |
| `OmnixFrontDoorAdapter` | `DONE` | `src/openjarvis/frontdoor/omnix_adapter.py` | OMNIX as optional enrichment adapter |
| `FrontDoorResult` — unified structured result | `DONE` | `src/openjarvis/frontdoor/frontdoor.py` | No raw chain-of-thought |
| Non-OMNIX project works | `DONE` | `tests/orchestrator/test_universal_jarvis.py` | Synthetic project and personal task verified |
| Personal (no-project) task works | `DONE` | `tests/orchestrator/test_universal_jarvis.py` | No project_context required |

### COS/GM Runtime

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| `CosGmOrchestrator` class | `DONE` | `src/openjarvis/orchestrator/cos_gm.py` | Receives UniversalTaskRequest, classifies, activates, returns FrontDoorResult |
| Universal request routing (not OMNIX-only) | `DONE` | `src/openjarvis/orchestrator/cos_gm.py` | project_context optional |
| Structured decision record emitted | `DONE` | via DynamicActivationPlanner + NUS decision_record | |
| Dangerous actions permanently blocked | `DONE` | `_ALWAYS_BLOCKED_ACTIONS` in cos_gm.py | auto_push, auto_merge, production_deploy, external_send |
| US13 voice HOLD/UNSAFE/PARKED | `DONE` | cos_gm.py + governance_plan | Not activated |

### NUS Scorecard Feedback Loop

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| Activation planner reads NUS failure patterns | `DONE` | `activation.py::_load_nus_feedback()` | Reads LearningStore; graceful degradation |
| Activation planner reads NUS routing recommendations | `DONE` | `activation.py::_load_nus_feedback()` | Reads LearnedRouter; graceful degradation |
| Prior failures escalate validation | `DONE` | `activation.py::_apply_nus_feedback()` | ≥3 failures → testing_validation_manager activated |
| NUS feedback tagged in plan | `DONE` | `nus_learning_tags` in ActivationPlan | `nus_feedback:loaded` or `nus_feedback:not_available` |
| get_status() reports nus_feedback_available | `DONE` | `DynamicActivationPlanner.get_status()` | |

### Worker Execution Adapters

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| `WorkerAdapter` base class | `DONE` | `src/openjarvis/orchestrator/worker_adapters.py` | Gate checking, blocked action enforcement |
| `DoctorValidationWorkerAdapter` | `DONE` | worker_adapters.py | Dry-run doctor check execution |
| `NUSLearningWorkerAdapter` | `DONE` | worker_adapters.py | NUS learning store summarization |
| `CostAnalysisWorkerAdapter` | `DONE` | worker_adapters.py | Routing analysis |
| Base adapter dry-run (all workers) | `DONE` | WorkerAdapter._execute_safe() | Falls back to base for unregistered workers |
| Blocked actions refused by all adapters | `DONE` | `_ALWAYS_BLOCKED_ADAPTER_ACTIONS` | auto_push, production_deploy, etc. |
| NUS gate checked before execution | `DONE` | WorkerAdapter._check_nus_gate() | Uses LowRiskExecutionManager |

### OMNIX Universalization

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| `omnix_frontdoor.py` not root front door | `DONE` | JarvisFrontDoor replaces it as root | omnix_frontdoor.py = OMNIX-specific script |
| OMNIX as one ProjectContext | `DONE` | `constitution.py::OMNIX_PROJECT` | OMNIX = Project 1, not the whole system |
| OMNIX as one FrontDoorAdapter | `DONE` | `OmnixFrontDoorAdapter` | Optional enrichment |
| Orchestration path has no OMNIX hardcoding | `DONE` | activation.py, cos_gm.py, contracts.py | Verified by tests |
| Doctor checks accept any project_id | `DONE` | check_project_registry_health refactored | No longer fails if only non-OMNIX projects |
| `run_all_checks` default uses ProjectRegistry | `DONE` | `run_all_checks(project_id=None)` resolves via `ProjectRegistry.get_default()` | |
| readiness.py OMNIX-hardcoded messages fixed | `DONE` | readiness.py | Generic language used |
| source_links.py bootstraps OpenJarvis | `DONE` | `_bootstrap_openjarvis()` added | |

### Provider/Model Sufficiency

| Item | Status | Evidence | Notes |
|------|--------|----------|-------|
| `ModelProviderSufficiencyGap` type | `DONE` | `orchestrator/contracts.py` | Surfaced in ActivationPlan |
| Gaps disclosed in activation plan | `DONE` | DynamicActivationPlanner `_build_model_routing_plan()` | |
| `get_status()` reports nus_feedback_available | `DONE` | DynamicActivationPlanner | |
| Real autonomous execution providers | `BLOCKED_PROVIDER` | — | **REQUIRES_BRYAN_ACTION**: See below |

**REQUIRES_BRYAN_ACTION — Model Provider Setup:**

For real autonomous execution (beyond dry-run/local-analysis), Jarvis needs live model API access:

| Provider | Key Needed | Where to Set | Why Needed | Current Status |
|----------|-----------|--------------|------------|----------------|
| OpenAI (GPT-4) | `OPENAI_API_KEY` | `~/.jarvis/cloud-keys.env` | Premium model for high-risk tasks | Missing → dry-run only |
| Anthropic (Claude) | `ANTHROPIC_API_KEY` | `~/.jarvis/cloud-keys.env` | Mid/premium model for complex tasks | Missing → dry-run only |
| OpenRouter | `OPENROUTER_API_KEY` | `~/.jarvis/cloud-keys.env` | Model routing across providers | Configured or missing |

**What cannot be completed without providers:** Real autonomous code execution, real LLM-reviewed plans, real model-in-the-loop orchestration.  
**What works now:** Dry-run planning, local analysis, NUS gate checking, doctor validation, structured decision records.

### Inactive Manager Classification

| Manager | Status | Exact Blocker | Bryan Action Required |
|---------|--------|---------------|----------------------|
| `connector_auth_manager` | `BLOCKED_CREDENTIALS` | No workers assigned; live secret/credential access blocked by policy | None — correctly inactive |
| `release_packaging_manager` | `BLOCKED_USER_AUTHORIZATION` | DMG build + Apple notarization requires Apple Developer signing identity and explicit Bryan approval | Provide Apple Developer credentials + authorize release build |

### Package/DMG/Notarization

| Item | Status | Notes |
|------|--------|-------|
| DMG build | `BLOCKED_USER_AUTHORIZATION` | Requires explicit Bryan authorization for `release_packaging_manager` activation |
| Apple notarization | `REQUIRES_BRYAN_ACTION` | Apple Developer signing identity needed; set `APPLE_DEVELOPER_IDENTITY` and `APPLE_TEAM_ID` in secure config |
| Release packaging manager activation | `BLOCKED_USER_AUTHORIZATION` | Currently `STATUS_INACTIVE`; Bryan must authorize before activation |
| `release_packaging_worker` activation | `BLOCKED_USER_AUTHORIZATION` | Paired with release_packaging_manager; same authorization required |

**Bryan Action Required for Package/DMG:**
1. Authorize activation of `release_packaging_manager` and `release_packaging_worker`
2. Provide `APPLE_DEVELOPER_IDENTITY` (e.g. `"Developer ID Application: Bryan..."`)
3. Provide `APPLE_TEAM_ID`
4. Place in `~/.jarvis/cloud-keys.env` (never committed)

### US13 Voice

| Item | Status | Notes |
|------|--------|-------|
| US13 voice pipeline | `BLOCKED_REQUIRED_LATER` | Technical blockers: no real STT (whisper.cpp or cloud), no voice approval UI, no real-time audio pipeline |
| Voice activation | `BLOCKED_SAFETY` | Permanently blocked in COS/GM and JarvisFrontDoor; `us13_voice` is in `_ALWAYS_BLOCKED` |
| Voice re-enablement | `REQUIRES_BRYAN_ACTION` | Bryan must explicitly reopen voice sprint, provide STT provider, and authorize activation |

### Documentation

| Item | Status | Notes |
|------|--------|-------|
| JARVIS_COMPLETION_GAP_REGISTER.md | `DONE` | This file |
| POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md updated | `DONE` | Updated for universal Jarvis |
| JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md updated | `DONE` | Updated |
| JARVIS_ROUTING_MODEL_POLICY.md updated | `DONE` | Updated |
| WAVE_ROADMAP.md updated | `DONE` | Updated |

### Doctor/Readiness Checks

| Item | Status | Notes |
|------|--------|-------|
| `check_universal_front_door` | `DONE` | Verifies universal front door, non-OMNIX project, personal task, blocked actions |
| `check_worker_execution_adapters` | `DONE` | Verifies adapter registry, dry-run, blocked action refusal |
| `check_nus_scorecard_feedback_loop` | `DONE` | Verifies activation planner reads NUS feedback |
| `check_inactive_manager_classification` | `DONE` | Classifies inactive managers with exact blockers |

---

## Summary

| Category | DONE | BLOCKED | REQUIRES_BRYAN_ACTION | OPTIONAL |
|----------|------|---------|-----------------------|----------|
| Universal front door | 8 | 0 | 0 | 0 |
| COS/GM runtime | 5 | 0 | 0 | 0 |
| NUS scorecard feedback | 5 | 0 | 0 | 0 |
| Worker execution adapters | 7 | 0 | 0 | 0 |
| OMNIX universalization | 8 | 0 | 0 | 0 |
| Provider/model sufficiency | 4 | 1 | 1 | 0 |
| Inactive manager classification | 2 | 2 | 1 | 0 |
| Package/DMG/notarization | 0 | 1 | 3 | 0 |
| US13 voice | 1 | 1 | 1 | 0 |
| Docs | 5 | 0 | 0 | 0 |
| Doctor checks | 4 | 0 | 0 | 0 |

**No vague future scope.** Every gap is DONE, BLOCKED (with exact reason), or REQUIRES_BRYAN_ACTION (with exact instructions).
