# Wave 1–4 Platform Roadmap

**Status as of: `Universalize Jarvis and close completion gaps` sprint**
**Commit tag: `Close Wave 1 platform readiness` → `Universalize Jarvis and close completion gaps`**

---

## Jarvis Universal Scope

Jarvis is Bryan's universal private AI operating system. OMNIX is one project.
All Waves apply to the universal Jarvis OS, not just OMNIX. Future projects
(OpenJarvis self-improvement, personal tasks, research, automation, business ideas)
are all first-class citizens.

Universal architecture (implemented):
- `JarvisFrontDoor` — any request, any project, or no project
- `ProjectContext` — optional; OMNIX, OpenJarvis, personal, future
- `CosGmOrchestrator` — routes universal requests
- `WorkerAdapters` — real execution adapters (dry-run/local)
- NUS scorecard feedback loop — activation planner reads failure data
- `JARVIS_COMPLETION_GAP_REGISTER.md` — no vague future scope

---

## Wave 1 — Foundation (LOCAL/FOUNDER V1 — COMPLETE)

### Status: READY (local/founder V1)

All four epics are implemented at local/founder V1 level.
External connectors and live web require env configuration or explicit approval.

---

### Epic A — Skill Platform

| Item | Status |
|---|---|
| Skill manifest model (`WaveSkillManifest`) | DONE |
| Skill registry (`WaveSkillRegistry`) | DONE |
| Local skill execution (`run_skill`) | DONE |
| **Skill induction/validation pipeline** (`skill_induction.py`) | **DONE** |
| Unsafe manifest rejection (destructive, secrets, external sends, deploy, bypass, scraping) | DONE |
| Hard-gate tag detection (external_send, slack, email, production_deploy) | DONE |
| Approval-required tag detection (terminal, shell, browser, write, git_push) | DONE |
| Safe local skill registration from manifest | DONE |
| Event logging: inducted / blocked | DONE |
| High-risk skills (risk_level=high/critical) require approval | DONE |
| Tests | DONE (`test_wave1_closeout.py::TestSkillInductionValidation`, `TestSkillInductionPipeline`) |

**Proof:** `induce_skill({safe_manifest})` → status=accepted; unsafe manifest → status=rejected/hard_gate_blocked.

---

### Epic B — Automation Platform

| Item | Status |
|---|---|
| AutomationTrigger model | DONE |
| AutomationRegistry | DONE |
| Dry-run execution (`dry_run_trigger`) | DONE |
| **Scheduler wiring to TaskScheduler** (`automation_scheduler.py`) | **DONE** |
| Register trigger | DONE |
| Enable/schedule low-risk trigger | DONE |
| Execute safe local action immediately | DONE |
| Prevent high/critical risk without approval | DONE |
| Block external sends (Slack/email/Telegram) | DONE |
| Background autopilot disabled | DONE — no uncontrolled thread started |
| Event logging: dry-run, executed, blocked | DONE |
| Tests | DONE (`test_wave1_closeout.py::TestAutomationScheduler`) |

**Proof:** `execute_safe_trigger(low_risk_trigger)` → ok=True; `execute_safe_trigger(high_risk)` → approval_required=True; `execute_safe_trigger(slack_trigger)` → blocked=True.

---

### Epic C — Knowledge Platform

| Item | Status |
|---|---|
| KnowledgeSource model | DONE |
| KnowledgeSourceRegistry | DONE |
| Local text/markdown ingestion (`ingest_local_source`) | DONE |
| Keyword search (`search_knowledge`) | DONE |
| **Local folder connector** (`local_folder_connector.py`) | **DONE** |
| Path allowlist (home dir + /tmp only) | DONE |
| Credential/secret file blocking (.env, .key, .pem, .ssh, etc.) | DONE |
| Forbidden path segment blocking (/.ssh/, /.aws/, /.kube/) | DONE |
| Max file size 500 KB, max 50 files per ingest | DONE |
| Records pushed into knowledge_platform store | DONE |
| PII sources without approval: rejected | DONE |
| Apple Notes / Dropbox connectors | REQUIRES_USER_ACTION (auth unavailable) |
| Event logging: ingested, blocked | DONE |
| Tests | DONE (`test_wave1_closeout.py::TestLocalFolderConnector`) |

**Proof:** `ingest_folder("/tmp/jarvis_docs", source_id="test")` reads .txt/.md files; `/etc` path → blocked=True; `.ssh` path → blocked=True.

**External connectors (REQUIRES_USER_ACTION):**
- Apple Notes: requires macOS entitlement + user authorization
- Dropbox: requires OAuth2 flow with user account
- These report `status=requires_setup` — no fake DONE claimed.

---

### Epic D — Research Platform

| Item | Status |
|---|---|
| ResearchProvider model | DONE |
| ResearchProviderRegistry | DONE |
| Local knowledge query (`run_local_query`) | DONE |
| Platform info fallback | DONE |
| **Tavily web search adapter** (`tavily_provider.py`) | **DONE** |
| Env-gated readiness (`TAVILY_API_KEY`) | DONE |
| Status: `ready` if key present, `requires_setup` if absent | DONE |
| Approval gate for all live queries | DONE |
| Unsafe query blocking (captcha, credential, password, bypass, scraping) | DONE |
| Key value NEVER logged/printed/stored/committed | DONE |
| Mock-based tests (no real network in CI) | DONE |
| Deep research loop | NOT_IMPLEMENTED (future slice) |
| Tests | DONE (`test_wave1_closeout.py::TestTavilyProvider`) |

**Key handling proof:**
- `TAVILY_API_KEY` read only via `os.environ.get("TAVILY_API_KEY")`.
- Value never appears in logs, responses, test output, or committed files.
- Stored in `.env.local` (gitignored) — never committed.

**Live provider status:**
- Key configured via `TAVILY_API_KEY` env var.
- All live queries require `approved=True` — approval gate enforced.
- Unsafe queries (captcha/credential/bypass) blocked regardless of approval.

---

## Retest Commands

```bash
cd /Users/user/OpenJarvis

# Full Wave 1 + US15-18 regression suite
uv run python -m pytest tests/wave tests/workbench/test_us15_foundation.py \
  tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py \
  tests/workbench/test_us18_readiness.py -q --tb=short

# Closeout only
uv run python -m pytest tests/wave/test_wave1_closeout.py -v --tb=short

# Doctor check
curl http://localhost:8000/v1/workbench/doctor | python3 -m json.tool | grep '"check"\|"status"'

# Wave status
curl http://localhost:8000/v1/wave/status | python3 -m json.tool
```

---

## External Setup Required

| Feature | Env Var | Status |
|---|---|---|
| Tavily web search | `TAVILY_API_KEY` | REQUIRES_USER_ACTION (key→ready; no key→requires_setup) |
| Serper web search | `SERPER_API_KEY` | REQUIRES_USER_ACTION |
| Apple Notes | macOS entitlement | REQUIRES_USER_ACTION |
| Dropbox | OAuth2 token | REQUIRES_USER_ACTION |

**Never set API key values in code, tests, rules, or committed files. Use env vars only.**

---

## US13 Voice — HOLD / UNSAFE / PARKED

US13 hands-free voice runtime remains **HOLD / UNSAFE / PARKED**.
No voice runtime code was touched or implemented in Wave 1 or the closeout sprint.
Voice remains disabled/parked for a future sprint pending explicit approval.

---

## Wave 2 — Professional Intelligence (LOCAL/FOUNDER V1 — COMPLETE)

**Commit tag: `Complete Wave 2 professional intelligence`**

### Epic E — Optimization Platform

| Item | Status |
|---|---|
| Workflow scorecard generation | DONE |
| Cost analysis (total cost, thresholds, recommendations) | DONE |
| Model routing analysis (Opus overuse detection) | DONE |
| Validation profile analysis (failing profiles) | DONE |
| Repeated failure detection (event log analysis) | DONE |
| Readiness/risk analysis (capability status) | DONE |
| Approval-gating for deploy/file_write/git/self_upgrade recommendations | DONE |
| No autonomous self-modification / auto-commit / auto-deploy | DONE |
| `/v1/wave2/optimization/status` route | DONE |
| `/v1/wave2/optimization/scorecard` route | DONE |
| `/v1/wave2/optimization/recommendations` route | DONE |
| Doctor check 37 | DONE |
| Tests | DONE (`test_wave2.py::TestOptimizationPlatformStatus`, `TestScorecardGeneration`, `TestRecommendationGeneration`, `TestCostAnalysis`, `TestNoAutonomousSelfModification`) |

**Proof:** `generate_scorecard()` returns `WorkflowScorecard` with all 5 analysis dimensions. Recommendations with `action=deploy/file_write/git_commit/self_upgrade` have `approval_required=True`. No file writes occur during scorecard generation.

### Epic F — Professional Skill Packs

| Item | Status |
|---|---|
| Skill pack registry | DONE |
| Coding Workflow Pack | DONE |
| Research Workflow Pack | DONE |
| Project Operations Pack | DONE |
| Package/Release Readiness Pack | DONE |
| Safety/Review Pack | DONE |
| Deploy/Release Pack (hard-gated, disabled) | DONE |
| Pack validation (required fields, risk level, tags) | DONE |
| Hard-gate enforcement (production_deploy, slack_send) | DONE |
| Approval-required enforcement (browser, terminal, high-risk) | DONE |
| Safe local pack execution | DONE |
| Wave 1 skill platform integration | DONE |
| `/v1/wave2/skill-packs/status` route | DONE |
| `/v1/wave2/skill-packs` list route | DONE |
| `/v1/wave2/skill-packs/run` run route | DONE |
| `/v1/wave2/skill-packs/validate` validate route | DONE |
| Doctor check 38 | DONE |
| Tests | DONE (`test_wave2.py::TestSkillPackRegistry`, `TestSkillPackValidation`, `TestSkillPackExecution`, `TestSkillPackEnabling`, `TestWave2Integration`) |

**Proof:** `run_skill_pack("coding_workflow")` → ok=True. `run_skill_pack("deploy_release")` → blocked=True. `enable_skill_pack("deploy_release")` → blocked=True.

### Wave 2 Capabilities

| Capability ID | Status |
|---|---|
| `wave2_optimization_platform` | ready |
| `wave2_professional_skill_packs` | ready |

### Wave 2 Retest Commands

```bash
cd /Users/user/OpenJarvis

# Wave 2 tests only
uv run python -m pytest tests/wave/test_wave2.py -v --tb=short

# Full suite
uv run python -m pytest tests/wave tests/workbench/test_us15_foundation.py \
  tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py \
  tests/workbench/test_us18_readiness.py -q --tb=short
```

## Wave 3 — Creation & Media (LOCAL/FOUNDER V1 — COMPLETE)

**Commit tag: `Complete Wave 3 content media studio`**

### Epic G — Content & Media Studio

| Item | Status |
|---|---|
| 7 built-in content templates | DONE |
| Product Spec template | DONE |
| Technical Handoff template | DONE |
| Bug Report template | DONE |
| Release Readiness Report template | DONE |
| Coding Agent Prompt Pack template | DONE |
| Research Brief template | DONE |
| Content Plan template | DONE |
| `run_content_workflow()` — dry-run by default | DONE |
| File write approval gate | DONE |
| Content safety policy (credentials, impersonation, spam) | DONE |
| External media providers status check | DONE |
| Social/email/messaging providers hard-blocked | DONE |
| Image/video providers (DALL-E, Stability, etc.) require env key + approval | DONE |
| Wave 1 knowledge store integration | DONE |
| Wave 2 skill pack integration | DONE |
| Release notes convenience workflow | DONE |
| Research brief convenience workflow | DONE |
| Coding agent prompt convenience workflow | DONE |
| Event logging (5 Wave 3 event types) | DONE |
| `/v1/wave3/content/status` route | DONE |
| `/v1/wave3/content/templates` route | DONE |
| `/v1/wave3/content/run` route | DONE |
| `/v1/wave3/content/media-provider/check` route | DONE |
| Doctor check 39 | DONE |
| Tests | DONE (`test_wave3.py` — 63 tests) |

**Proofs:**
- `run_content_workflow("bug_report", dry_run=True)` → ok=True, artifact.dry_run=True
- `run_content_workflow("product_spec", dry_run=False, file_write_approved=False)` → approval_required=True
- `check_content_safety("api_key: mysecret")` → block reason returned
- `check_media_provider("slack_post")` → status=hard_blocked
- `run_media_provider_workflow("dalle", prompt, approved=False)` → approval_required=True

### What Requires Approval
- File writes (`dry_run=False` requires `file_write_approved=True`)
- Live media generation (requires env key + `approved=True`)

### What Requires External Setup (REQUIRES_USER_ACTION)
| Provider | Env Var |
|---|---|
| DALL-E | `OPENAI_API_KEY` |
| Stability | `STABILITY_API_KEY` |
| Midjourney | `MIDJOURNEY_API_KEY` |
| Runway | `RUNWAY_API_KEY` |

### What Is Not Implemented (Future)
- Actual live image/video generation execution (stub — provider adapter done)
- Social media account management
- Publishing pipeline

### Wave 3 Capability
| Capability ID | Status |
|---|---|
| `wave3_content_media_studio` | ready |

### Retest Commands
```bash
cd /Users/user/OpenJarvis
uv run python -m pytest tests/wave/test_wave3.py -v --tb=short
```

## Wave 4 — Jarvis Expansion: COMPLETE (local/founder V1)

- Epic H: Autonomous Expansion — `READY` (supervised proposal workflows only)
- Module: `src/openjarvis/wave/autonomous_expansion.py`
- Tests: `tests/wave/test_wave4.py`
- Full doc: `docs/WAVE4_EXPANSION.md`

### What Wave 4 completed

- Expansion opportunity detection (Wave 1–3 registry scan)
- Capability gap analysis (Wave 1–3)
- Safe expansion proposal creation (approval-gated)
- Dependency/risk classification (adversarial safety reused from US17)
- Acceptance criteria generation
- Validation-plan generation
- Rollback-plan generation
- Approval-gated expansion queue
- Wave 1 integration: propose new skills, automation triggers, knowledge sources, research providers
- Wave 2 integration: cost/routing/performance classification via Wave 2 patterns
- Wave 3 integration: content spec drafting, handoff pack drafting, readiness report drafting
- Event logging: opportunity_detected, proposal_created, proposal_blocked, approval_required, validation_plan_generated
- API routes: `/v1/wave4/expansion/status`, `/opportunities`, `/gaps`, `/queue`, `/propose`, `/validate`
- Doctor/readiness: Wave 4 check added to workbench doctor
- Capability: `wave4_autonomous_expansion` in capabilities registry

### What requires approval before execution

- Any proposal of type: register_capability, add_provider, add_integration, wave1_skill_register,
  wave1_automation_register, wave1_knowledge_source_register, wave1_research_provider_register

### What is explicitly blocked / not allowed

- No code self-modification
- No auto-commit or auto-push
- No deploy or release automation
- No external sends (Slack/email/Telegram)
- No secret access
- No browser automation
- No NUS 1 self-improvement autonomy
- No US13 voice (HOLD/UNSAFE/PARKED)

### Retest commands

```bash
cd /Users/user/OpenJarvis
uv run python -m pytest tests/wave/test_wave4.py -v --tb=short
uv run python -m pytest tests/wave tests/workbench/test_us15_foundation.py tests/workbench/test_us16_complete.py tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q --tb=short
```

## NUS 1 — Autonomous Upgrade

### NUS 1A — Learning Foundation: READY (local founder V1)

- Module: `src/openjarvis/nus/learning_foundation.py`
- Collects structured learning signals from task outcomes, validation, blocked actions,
  Wave 1–4 events, and Workbench/coding outcomes.
- Provides: `AgentScorecard`, `FailurePatternRecord`, `LearningSignal`, `LearningSnapshot`.
- Routes: `/v1/nus/learning/status`, `/v1/nus/learning/scorecards`,
  `/v1/nus/learning/failure-patterns`, `/v1/nus/learning/snapshot`.
- Capability: `nus1a_learning_foundation` → `ready`.
- Doctor check: `check_nus1a_learning_foundation`.
- No self-modification. No auto-commit. No deploy. No external sends. Safety gates active.
- US13 voice remains HOLD/UNSAFE/PARKED.
- Full docs: `docs/NUS1A_LEARNING_FOUNDATION.md`.

### NUS 1B — Recommendation Workflow: READY (local founder V1)

- Modules: `src/openjarvis/nus/learning_store.py`, `src/openjarvis/nus/recommendation_registry.py`,
  `src/openjarvis/nus/telemetry.py`, `src/openjarvis/nus/autonomy_policy.py`
- Cross-session learning persistence (JSONL, safe paths, secret redaction).
- Recommendation registry and lifecycle (draft → ready/needs_approval/blocked → executed_dry_run).
- Approval workflow scaffold (14 approval policy categories).
- Telemetry ingestion/normalization from all sources.
- Autonomy policy scaffold (5 profiles defined; only `manual` activated).
- Routes: `/v1/nus/recommendations/*`, `/v1/nus/telemetry/*`, `/v1/nus/autonomy-policy/status`.
- Capability: `nus1b_recommendation_workflow` → `ready`.
- Doctor check: `check_nus1b_recommendation_workflow`.
- No self-modification. No auto-commit. No deploy. No external sends. Safety gates active.
- US13 voice remains HOLD/UNSAFE/PARKED.
- Full docs: `docs/NUS1B_RECOMMENDATION_WORKFLOW.md`.

### NUS 1C — Safe Autopilot Foundation: READY (local founder V1)

- Modules: `src/openjarvis/nus/recommendation_queue.py`, `src/openjarvis/nus/safe_autopilot.py`,
  `src/openjarvis/nus/failure_learning.py`, `src/openjarvis/nus/learned_routing.py`
- Extends: `src/openjarvis/nus/telemetry.py` (operator ingestion), `src/openjarvis/nus/autonomy_policy.py`
  (safe_autopilot activated)
- Routes: `/v1/nus/recommendations/queue/*`, `/v1/nus/autopilot/*`, `/v1/nus/failure-learning/*`,
  `/v1/nus/telemetry/operator/*`, `/v1/nus/routing/*`
- Capability: `nus1c_safe_autopilot_learning` → `ready`
- Doctor check: `check_nus1c_safe_autopilot`
- Tests: `tests/nus/test_nus1c_safe_autopilot.py`
- Scope: persistent recommendation queue, safe_autopilot active for local analysis/dry-run only,
  cross-session failure pattern learning, operator telemetry normalization, learned routing
  recommendations (advisory only). All dangerous actions blocked. Medium-risk gated.
- US13 voice: HOLD/UNSAFE/PARKED.
- Full docs: `docs/NUS1C_SAFE_AUTOPILOT.md`.

### NUS 1D — Eval Gates, Rollback, Approval Workflow: READY

Implemented in consolidated NUS 1D/1E sprint.

- **Modules:** `eval_gate.py`, `rollback.py`, `approval_workflow.py`, `power_autopilot.py`
- **Eval gate framework:** fail-closed on missing evidence; validates validation plan, rollback plan, risk classification, capability readiness, safety gate result, blocked action check.
- **Rollback enforcement:** structured `RollbackPlan`, required for file_write/code_edit/commit-like actions. No destructive rollback execution without explicit approval.
- **Approval workflow:** `ApprovalDecision` with TTL, scope constraints, explicit denial, audit log. Cannot override blocked categories (secrets/self_modification/deploy/push/merge).
- **Power autopilot boundary:** `controlled_not_broadly_activated`. Safe local dry-runs allowed with kill-switch off + eval gate pass. Medium-risk requires gate+rollback+approval. Permanently blocked: deploy/push/merge/secret/self_modification/browser/sends.
- **Capability:** `nus1d_eval_rollback_gates` — `ready`
- **Routes:** `/v1/nus/eval/status`, `/v1/nus/eval/run-dry-run`, `/v1/nus/rollback/status`, `/v1/nus/approvals/status`
- **Doctor check:** `check_nus1d_eval_rollback`
- **Tests:** `tests/nus/test_nus1d_eval_rollback.py`
- **US13 voice:** HOLD/UNSAFE/PARKED

### NUS 1E — Low-Risk Execution Foundation: READY

Implemented in consolidated NUS 1D/1E sprint.

- **Modules:** `execution_classifier.py`, `low_risk_execution.py`
- **Execution classifier:** metadata/contract-driven (not fixed agent names). Classifies actions into safe_local_dry_run, safe_docs_metadata, medium_file_write, high_external, blocked_dangerous tiers.
- **Auto-commit foundation:** dry-run scaffold. Requires clean git, diff classification, validation pass, rollback plan, audit log, kill-switch disabled, no secret files, no deploy artifacts. No auto-push, no auto-merge, no production deploy.
- **Production gate:** permanently blocked in NUS 1E. Requires NUS 1F explicit gate.
- **Future-proof:** synthetic future agents classified correctly without hardcoded name logic.
- **Capability:** `nus1e_low_risk_execution_foundation` — `ready`
- **Routes:** `/v1/nus/execution/low-risk/status`, `/v1/nus/execution/low-risk/dry-run`, `/v1/nus/governance/future-proof/status`
- **Doctor check:** `check_nus1e_low_risk_execution`
- **Tests:** `tests/nus/test_nus1e_low_risk_execution.py`, `tests/nus/test_future_proof_governance.py`
- **Docs added:** `JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md`, `JARVIS_AGENT_REGISTRY_AND_CONTRACTS.md`, `JARVIS_ROUTING_MODEL_POLICY.md`, `JARVIS_95_PERCENT_AUTONOMY_TARGET.md`, `JARVIS_TOKEN_COST_GOVERNANCE.md`, `POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md`
- **US13 voice:** HOLD/UNSAFE/PARKED

### NUS 1F — Controlled Production Autonomy: NOT STARTED / LOCKED

- Requires explicit Bryan approval.
- Handles controlled high-autonomy sessions, production-safe execution gates, and founder_override session activation.
- Post-NUS company-grade orchestrator plan is LOCKED until NUS 1F is complete.
- Post-NUS company-grade orchestrator: LOCKED — do not implement until explicitly authorized.
- No `autonomous_upgrade` module exists.

---

## Wave 1 Doctor Checks

The `/v1/workbench/doctor` endpoint includes checks 28–36 covering:
- Check 28: Skill Platform local execution
- Check 29: Automation Platform dry-run
- Check 30: Knowledge Platform ingestion
- Check 31: Research Platform status
- Check 32: Wave 2–4 not claimed ready
- Check 33: **Skill induction pipeline** (NEW)
- Check 34: **Automation scheduler wiring** (NEW)
- Check 35: **Local folder connector** (NEW)
- Check 36: **Tavily research provider** (NEW)

---

## Accepted Checkpoints (intentionally not reverified)

- US12–US18: Previously validated. No regression evidence.
- Wave 1 foundation scaffold: `405b4be8 Add Wave 1 platform foundation`
- Wave 1 core integration: `7691cff2 Complete Wave 1 platform integration`
- Only Wave 1 closeout files were inspected and changed.
