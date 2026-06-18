# Wave 1–4 Platform Roadmap

**Status as of: Wave 1 Final Closeout Sprint**
**Commit tag: `Close Wave 1 platform readiness`**

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

## Wave 3 — Creation & Media: NOT STARTED

- Epic G: Content & Media Studio — NOT_IMPLEMENTED
- No code exists. Platform registry marks as `NOT_IMPLEMENTED`.

## Wave 4 — Jarvis Expansion: NOT STARTED

- Epic H: Autonomous Expansion — NOT_IMPLEMENTED
- No code exists. Platform registry marks as `NOT_IMPLEMENTED`.

## NUS 1 — Autonomous Upgrade: NOT STARTED / LOCKED

- NUS 1 is locked for a future sprint. Not implemented in Wave 2.
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
