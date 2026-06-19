# Jarvis Company Org — Unified OS Architecture Specification

**Status:** HOLD — Sprint 3 Consolidated Final: MacBook-off token still invalid  
**No-Gap Status:** HOLD — full no-gap certification not yet complete  
**Voice Status:** SEPARATE_SPRINT_REQUIRED — text fallback required and documented  
**Universal Mobile Project-Building:** REQUIRED_FOR_NO_GAP_JARVIS — remote execution runtime needed  
**MacBook-off Continuity:** BLOCKED_WAITING_FOR_BRYAN_NOW — requires GITHUB_TOKEN in .env  
**PWA:** FREE_AND_PRACTICAL_NOW — /mobile route + /manifest.webmanifest live  
**Native iOS/Android:** REQUIRES_BRYAN_SETUP — Tauri 2 supported; setup steps documented  
**Partial Accept Policy:** NOT ACCEPTED — all gaps are explicitly disclosed below  

---

## 1. Architecture Overview

```
Bryan (owner)
    │
    └── Jarvis HQ / Front Door (universal entry — any request)
            │
            └── COS — Chief of Staff (routing, prioritization, hard-gate enforcement)
                    │
                    └── GM — General Manager (execution coordination, stall detection)
                            │
                            ├── Coding Manager     → [repo-inspector, test-runner]
                            ├── Research Manager   → [web-searcher, knowledge-retriever, ...]
                            ├── Memory Manager     → [memory-sync, obsidian-exporter]
                            ├── Connector Manager  → [slack-sender, telegram-sender, ...]
                            └── Ops/Safety Manager → [safety-auditor, ...]
                                    │
                                    └── Verifier (independent audit gate — never team member)
```

Escalation protocol: **Worker → Manager → GM → COS → Bryan**

---

## 2. Role Definitions

### 2.1 Jarvis (top-level front door)

| Field | Value |
|---|---|
| Role ID | `jarvis` |
| Tier | JARVIS |
| Persona | `jarvis-hq` (real Slack bot) |
| Description | Universal private AI OS — single entry point for all requests |
| Parallelizable | No (serial by design) |
| Stall policy | Escalate to Bryan after 300s |

**Key invariant:** Jarvis is NOT OMNIX-only. Personal tasks, research, automation, business — all route through the same front door.

### 2.2 COS — Chief of Staff

| Field | Value |
|---|---|
| Role ID | `cos` |
| Tier | COS |
| Persona | `jarvis-cos` (real Slack bot) |
| Description | Routing, prioritization, hard-gate enforcement |
| Parallelizable | No (serial coordinator) |
| Stall policy | Escalate to Bryan after 600s |

### 2.3 GM — General Manager

| Field | Value |
|---|---|
| Role ID | `gm` |
| Tier | GM |
| Persona | `jarvis-gm` (real Slack bot) |
| Description | Execution coordination, parallel manager oversight, stall detection |
| Parallelizable | No (GM is serial; manages parallel work below it) |
| Stall policy | Report to COS after 600s |

### 2.4 Managers (domain-specific)

| Role ID | Title | Slack Persona | Channel | Parallelizable |
|---|---|---|---|---|
| `manager-coding` | Coding Manager | `jarvis-coding-mgr` | `#jarvis-coding` | Yes (no file conflicts) |
| `manager-research` | Research Manager | `jarvis-research-mgr` | `#jarvis-tasks` | Yes |
| `manager-memory` | Memory Manager | `jarvis-memory-mgr` | `#jarvis-memory` | Yes (reads), No (writes) |
| `manager-connector` | Connector Manager | `jarvis-connector-mgr` | `#jarvis-connectors` | No (serial sends) |
| `manager-ops-safety` | Ops/Safety Manager | `jarvis-ops-safety-mgr` | `#jarvis-ops` | No |

### 2.5 Verifier (independent audit gate)

| Field | Value |
|---|---|
| Role ID | `verifier` |
| Tier | VERIFIER |
| Persona | `jarvis-verifier` (Slack bot — `slack_bot_configured=False` in this sprint) |
| Description | Independent validation gate — never part of the team being verified |
| Self-verify | PERMANENTLY BLOCKED |
| Stall policy | Report to COS only — never reassign to the team being verified |

**Verifier gate behavior:**
1. Unsupported row → REJECTED + fix list
2. Contradictory status → REJECTED + fix list
3. Stale artifact → REJECTED + fix list
4. Missing evidence → REJECTED + fix list
5. Valid evidence with trace → ACCEPTED

### 2.6 Workers (virtual — assembled dynamically)

| Role ID | Title | Manager | Parallelizable |
|---|---|---|---|
| `worker-repo-inspector` | repo-inspector | Coding | Yes (read-only) |
| `worker-test-runner` | test-runner | Coding | Yes (no shared state) |
| `worker-obsidian-exporter` | obsidian-exporter | Memory | Yes (different docs) |
| `worker-memory-sync` | memory-sync | Memory | No (write conflicts) |

**Worker count policy:** NOT fixed. Teams are assembled dynamically by task need. Fake/headcount-only workers are FORBIDDEN.

---

## 3. Skill/Tool Coverage Matrix

| Role | Required Tools | Required Skills | Coverage Status |
|---|---|---|---|
| Jarvis | jarvis_registry, shell_exec, file_read/write, git_tool, web_search, knowledge_search, memory_manage, think, llm_tool | intent_classification, risk_assessment, routing, governance, cost_governance, telemetry | VERIFIED_PRESENT |
| COS | jarvis_registry, llm_tool, knowledge_search, memory_manage, think, approval_store | task_prioritization, manager_selection, team_assembly, governance, escalation | VERIFIED_PRESENT |
| GM | jarvis_registry, llm_tool, knowledge_search, think | parallel_execution_coordination, stall_detection, result_aggregation | VERIFIED_PRESENT |
| Coding Manager | shell_exec, git_tool, file_read/write/search, apply_patch | code_review, test_execution, linting, refactoring | VERIFIED_PRESENT |
| Research Manager | web_search, knowledge_search, knowledge_sql, retrieval, llm_tool | source_verification, evidence_synthesis, fact_checking | VERIFIED_PRESENT |
| Memory Manager | memory_manage, storage_tools, knowledge_tools | memory_continuity, conflict_detection, cloud_sync | VERIFIED_PRESENT |
| Connector Manager | channel_tools, approval_store, http_request | send_gating, approval_enforcement | VERIFIED_PRESENT |
| Ops/Safety Manager | approval_store, jarvis_registry, think | governance_enforcement, hard_gate_check, safety_audit | VERIFIED_PRESENT |
| Verifier | jarvis_registry, file_read, knowledge_search, think | evidence_tracing, contradiction_detection, stale_artifact_detection, fix_list_generation | IMPLEMENTED_THIS_SPRINT |
| worker-repo-inspector | file_read, file_search, git_tool | diff_analysis, change_detection | VERIFIED_PRESENT |
| worker-test-runner | shell_exec | test_execution | VERIFIED_PRESENT |
| worker-obsidian-exporter | file_write, knowledge_tools | obsidian_export | VERIFIED_PRESENT |
| worker-memory-sync | memory_manage, storage_tools | cloud_sync | BLOCKED_LOCAL_TOOLCHAIN (credentials not configured) |

---

## 4. Parallel Execution Policy

Tasks parallelized when:
- No shared file write conflicts
- No dependency order requirement
- `parallelizable=True` on the WorkerTask

Tasks sequenced when:
- Explicit `dependencies` list on WorkerTask
- `parallelizable=False` (e.g., memory-sync, serial sends)
- Safety constraint requires ordering (e.g., inspect before test)

See `src/openjarvis/agents/worker_pool.py` → `WorkerPool.build_execution_plan()`.

---

## 5. Stall Detection and Reassignment

| Role | Timeout | Action | Reassignable |
|---|---|---|---|
| Jarvis | 300s | Escalate to Bryan | No |
| COS | 600s | Escalate to Bryan | No |
| GM | 600s | Report to COS | No |
| Managers | 300s | Report to GM, reassign if safe | Yes |
| Workers | 300s | Report to manager, reassign | Yes |
| Verifier | 300s | Report to COS only | No (anti-capture) |

See `src/openjarvis/agents/worker_pool.py` → `WorkerPool.check_stalls()`.

---

## 6. Artifact Output Policy

Every completed worker task must produce a structured artifact (file path or structured dict) where appropriate. Artifacts are tracked by `WorkerPool.get_artifacts()`.

Output artifact types:
- `test_results_file` — pytest output
- `lint_report_file` — lint output
- `diff_review_file` — git diff with analysis
- `research_report_file` — research findings
- `sync_status_report` — memory sync state
- `obsidian_export_file` — Obsidian vault export

---

## 7. Self-Improvement / Durable Bug Prevention

Policy: **"Catch flaw once → fix once → add durable prevention."**

Mechanics (see `src/openjarvis/agents/self_improvement.py`):
1. `SelfImprovementRegistry.record_flaw()` — records flaw, auto-creates `PreventionItem`
2. `PreventionItem` includes `concrete_action` and optional `validation_command`
3. `CachedPlan` stores reusable plans with `gates_required` — reuse NEVER removes gates
4. Routing decisions stored in `routing_memory` for faster future selection

**Invariant:** Reusing a cached plan does NOT bypass required validation gates.

---

## 8. Slack Persona Architecture

**Architecture:** Single-bot + message prefixes + channels (NOT 100+ real Slack apps)

Real Slack bots (bounded set):
- `jarvis-hq` → `#jarvis-ops`
- `jarvis-cos` → `#jarvis-ops`
- `jarvis-gm` → `#jarvis-ops`
- `jarvis-coding-mgr` → `#jarvis-coding`
- `jarvis-research-mgr` → `#jarvis-tasks`
- `jarvis-memory-mgr` → `#jarvis-memory`
- `jarvis-connector-mgr` → `#jarvis-connectors`
- `jarvis-ops-safety-mgr` → `#jarvis-ops`
- `jarvis-notifications` → `#jarvis-alerts`

Virtual workers post via manager bots with `[Worker: worker-name]` prefix.  
All external sends require Bryan authorization — NOT automated in this sprint.

---

## 9. Mobile / Cross-Device Continuity

### 9.1 Foundation (IMPLEMENTED_THIS_SPRINT)

Module: `src/openjarvis/mobile/continuity.py`

**Session model:** `Session` in `src/openjarvis/sessions/session.py` (existing)  
**Device model:** `DeviceModel` — registered trusted devices  
**Continuity snapshot:** `ContinuitySnapshot` — full state capture  
**Resume token:** opaque UUID token → snapshot lookup  
**Sync status:** `SyncStatus` enum (synced/pending/conflict/offline/degraded/unknown)  
**Conflict policy:** SURFACE_CONFLICT — conflicts are always surfaced, never hidden  
**Offline policy:** DEGRADE_GRACEFULLY  
**Security policy:** TRUSTED_DEVICE_REQUIRED  

### 9.2 Required Continuity State

All 12 required state fields are implemented in `ContinuitySnapshot`:
1. ✅ User/device identity
2. ✅ Active conversation/thread
3. ✅ Active task/workflow
4. ✅ Manager/worker assignment
5. ✅ Pending approvals
6. ✅ Artifacts/files (artifact_pointers)
7. ✅ Project context
8. ✅ Memory references
9. ✅ Tool/connector state (safe subset, no secrets)
10. ✅ Sync status
11. ✅ Conflict state
12. ✅ Last known device/session state

### 9.3 Mobile Client/API Contract

Defined via `ContinuityStore.get_mobile_api_contract()`.

Endpoints:
- `POST /continuity/snapshot` — save snapshot from current device
- `GET /continuity/resume/{resume_token}` — retrieve for cross-device resume
- `GET /continuity/latest` — get latest user snapshot
- `POST /devices/register` — register trusted device

### 9.4 Missing Mobile Work (REQUIRED_FOR_NO_GAP_JARVIS)

| Item | Status |
|---|---|
| React Native / iOS / Android native app | REQUIRED_AND_MISSING |
| Real mobile push notifications | REQUIRED_AND_MISSING |
| Device pairing UX | REQUIRED_AND_MISSING |
| Mobile-specific approval UI | REQUIRED_AND_MISSING |
| Real backend API endpoints (FastAPI routes) | REQUIRED_AND_MISSING |

**Classification:** Mobile backend/session contract is IMPLEMENTED. Mobile UI is REQUIRED_FOR_NO_GAP_JARVIS.

---

## 10. Runtime Wiring — What Is Wired and Tested

| Module | Status | Integration Point |
|---|---|---|
| `company_org.py` | WIRED_AND_TESTED | `/v1/company-org/status`, `/v1/company-org/roster` |
| `agents/company_org_runtime.py` | WIRED_AND_TESTED | `POST /v1/company-org/task` — full Jarvis→COS→GM→Manager→Workers→Verifier pipeline |
| `agents/verifier.py` | WIRED_AND_TESTED | Called from runtime; result attached to task response |
| `agents/worker_pool.py` | WIRED_AND_TESTED | Called from runtime; stall detection active |
| `agents/self_improvement.py` | WIRED_AND_TESTED | Stall events trigger `record_flaw()` + prevention item |
| `mobile/continuity.py` | WIRED_AND_TESTED | `POST/GET /v1/continuity/*` real API routes |
| Verifier Slack persona | CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN | Single-bot: `jarvis-hq` posts `[Verifier]` prefix via `roster.format_slack_message()` |
| worker-memory-sync credentials | CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN | Local SQLite store is authoritative for founder-local ops; cloud sync is REQUIRED_FOR_NO_GAP_JARVIS |
| Mobile web UI | WIRED_AND_TESTED | FastAPI serves React SPA at `/`; accessible from mobile browser on LAN |
| Native iOS/Android app | REQUIRED_FOR_NO_GAP_JARVIS | No native app exists; web path is the current mobile path |

### What is fully wired and tested (HOLD Correction added)

- ✅ Company org spec (`src/openjarvis/company_org.py`) with all 6 role tiers
- ✅ Company org runtime (`src/openjarvis/agents/company_org_runtime.py`) — real callable Jarvis→COS→GM→Manager→Worker→Verifier pipeline
- ✅ FastAPI router (`src/openjarvis/server/company_org_routes.py`) — wired into `app.py`
- ✅ Verifier gate operationalized and called from runtime route
- ✅ Worker pool with stall detection wired into runtime
- ✅ Self-improvement: stall events trigger prevention items
- ✅ Mobile continuity API routes — real FastAPI endpoints for snapshot CRUD, resume, sync-status, conflict
- ✅ **MacBook-off continuity backend** (`src/openjarvis/mobile/continuity_backend.py`) — GitHub Gist (free, no new account), setup documented
- ✅ **COS Skill** (`src/openjarvis/agents/cos_skill.py`) — real callable COS: prioritization, routing, escalation, handoff, status
- ✅ **Code Sentinel** (`src/openjarvis/agents/code_sentinel.py`) — changed-file review, stale artifact detection, secret scan, unsupported claim rejection
- ✅ **Drift Guard** (`src/openjarvis/agents/drift_guard.py`) — fake readiness, hidden blocker, forbidden claim, tone drift detection
- ✅ **Role-scoped cache** (`src/openjarvis/jarvis_os/role_cache.py`) — 7 layers, all roles, security enforcement, explicit cache miss
- ✅ **Cost/token ledger** (`src/openjarvis/jarvis_os/cost_ledger.py`) — role/task/cache/retry tracking, expensive task alerts
- ✅ **Runtime self-knowledge manifest** (`src/openjarvis/jarvis_os/manifest.py`) — callable manifest: all capabilities, blockers, voice/no-gap status
- ✅ **PWA manifest + mobile page** (`/manifest.webmanifest`, `/mobile`) — free, no accounts, add to home screen
- ✅ **One-system integration** — company runtime response includes: routing trace, COS decision, cache trace, cost trace, capability status, sentinel findings, drift findings, blocker list
- ✅ **Continuity snapshot** extended with: `cache_state_ref`, `cost_task_ref`, `capability_status_ref`, `blocker_list`
- ✅ Tests: 31 unit tests + 22 API integration tests + **20 FINAL HOLD CORRECTION tests** (`test_final_hold_correction.py`)

### Unified Jarvis OS — What Is One System Now

```
Bryan Request
    │
    ├── COS Skill (routing, priority, escalation, handoff)
    │       ├── Manager Selection (keyword match → manager-coding/research/memory/connector/ops)
    │       ├── Blocker Escalation → Jarvis
    │       └── No-Hidden-Gap Enforcement
    │
    ├── Company Org Runtime (Jarvis→COS→GM→Manager→Workers→Verifier)
    │       ├── Role-Scoped Cache (7 layers, security-enforced)
    │       ├── Cost Ledger (role/task/cache/retry/model tracking)
    │       ├── Code Sentinel (stale artifact, secret scan, claim rejection)
    │       ├── Drift Guard (fake readiness, forbidden claims)
    │       └── Capability Manifest (real-time status of all capabilities)
    │
    ├── Mobile Continuity
    │       ├── /mobile — mobile-optimized text-first page (PWA-installable)
    │       ├── /manifest.webmanifest — PWA manifest
    │       ├── Local file store (MacBook-on only)
    │       └── GitHub Gist backend (MacBook-off — needs GITHUB_TOKEN)
    │
    └── FastAPI Routes — all exposed, all real
```

### MacBook-Off Continuity — Exact Status

| Path | Status | Evidence |
|---|---|---|
| LAN mobile web (MacBook on) | WIRED_AND_TESTED | FastAPI + /mobile route |
| MacBook-off (GITHUB_TOKEN valid ghp_... 40+ chars) | AVAILABLE | GitHub Gist backend wired |
| MacBook-off (GITHUB_TOKEN present but invalid) | BLOCKED_INVALID_TOKEN_FORMAT | Token too short/unknown prefix — HTTP 401 |
| MacBook-off (no GITHUB_TOKEN) | BLOCKED_WAITING_FOR_BRYAN_NOW | Setup: PAT with gist+workflow+repo scopes → .env |

**Current status:** BLOCKED — token present but too short (unknown prefix, fails GitHub API 401)

**Bryan setup required (Classic PAT — free, 5 steps):**
1. github.com → Settings → Developer settings → Personal access tokens (Classic)
2. Create token with scopes: **gist** (snapshot sync) + **workflow** (trigger builds/tests) + **repo** (diffs, logs)
3. Token must start with `ghp_` and be 40+ characters
4. Add to `.env`: `GITHUB_TOKEN=ghp_yourtoken`
5. Restart Jarvis server

Snapshots will be saved as private gists — not public, no new account needed.

---

## Universal Mobile Project-Building Runtime

**LOCKED REQUIREMENT:** Mobile means full MacBook-equivalent Jarvis capability from phone.
OMNIX is only one example project. Jarvis must support any project/new project/workflow.

**What mobile must eventually do:**
- Start any new project from phone through Jarvis
- Continue any existing project from phone with 100% context continuity
- Trigger coding tasks, code review, tests, builds, packaging checks
- View diffs, logs, artifacts
- Approve/reject gated actions (deploy, merge, delete)
- Monitor managers/workers/verifier/sentinel
- Reassign or escalate stuck workers
- Work when MacBook is completely off

**Why PWA/snapshot-only is NOT enough:**
- Cloud memory/snapshot sync = state preservation only, no execution
- LAN-only MacBook server access = breaks when MacBook is off
- PWA/native app alone = UI without backend when MacBook is off
- Real requirement: always-available remote/cloud execution runtime

**Current mobile project-building capability audit:**

| Capability | MacBook-On | MacBook-Off | Status |
|---|---|---|---|
| Start new project | PARTIALLY_WIRED | REQUIRED | Remote runtime needed |
| Continue existing project | WIRED_AND_TESTED | BLOCKED_CREDENTIALS | Valid token + runtime needed |
| Trigger coding task | WIRED_AND_TESTED | REQUIRED | Remote runtime needed |
| Trigger code review | PARTIALLY_WIRED | REQUIRED | GitHub API + runtime needed |
| Trigger tests | PARTIALLY_WIRED | REQUIRED | Workers simulated only |
| Trigger builds | REQUIRED | REQUIRED | Not implemented |
| Trigger packaging/release | REQUIRED | REQUIRED | Not implemented |
| View diffs/logs/artifacts | PARTIALLY_WIRED | REQUIRED | Artifact pointers only |
| Approve/reject gated actions | PARTIALLY_WIRED | REQUIRED | No dedicated mobile approval UI |
| Monitor agents/stalls/blockers | WIRED_AND_TESTED | BLOCKED_CREDENTIALS | Needs valid token |
| Reassign/escalate workers | WIRED_AND_TESTED | REQUIRED | Remote runtime needed |
| Full MacBook-off parity | N/A | REQUIRED_FOR_NO_GAP_JARVIS | Runtime + valid token needed |
| Remote/cloud execution runtime | N/A | REQUIRED_FOR_NO_GAP_JARVIS | GitHub Actions — designed |

### Remote/Cloud Execution Runtime — Recommended Path

**Cheapest free path: GitHub Actions (workflow_dispatch)**

| Option | Classification | Cost | macOS-off Capable |
|---|---|---|---|
| **GitHub Actions** | REQUIRES_BRYAN_SETUP | **FREE** (2000 min/month) | Yes |
| GitHub API direct ops | FREE_AND_PRACTICAL_NOW | Free | Yes (no execution) |
| GitHub Codespaces | REQUIRES_BRYAN_SETUP | 60h/month free | Yes |
| Tailscale + always-on machine | REQUIRES_BRYAN_SETUP | Free | Only if machine on |
| Fly.io | LOW_COST_AND_JUSTIFIED | $0–$5/month | Yes |
| Self-hosted GitHub runner | REQUIRES_BRYAN_SETUP | Free | Only if machine on |

**Bryan setup for GitHub Actions (recommended):**
1. Replace `.env GITHUB_TOKEN` with Classic PAT having `gist + workflow + repo` scopes
2. Create `.github/workflows/jarvis-remote.yml` (template at `src/openjarvis/remote/github_actions_backend.py`)
3. Commit workflow file to repo and push
4. Mobile → POST `/v1/remote/trigger-workflow?task_type=test`
5. Poll `GET /v1/remote/workflow-status` for result

**What GitHub Actions gives Jarvis (free):**
- Run pytest → results in artifacts
- Run npm/cargo build → build output
- Run linting → findings report
- Generate diffs between branches
- Store artifacts (7-day retention)
- Post status back to Jarvis via commit status API

**Deploys remain hard-gated:** Bryan authorization required in workflow — no auto-deploy.

### MacBook-Off Continuity — Exact Status

### Mobile / PWA — Exact Status

| Path | Status | Cost | Accounts |
|---|---|---|---|
| Mobile web browser (LAN) | WIRED_AND_TESTED | Free | None |
| PWA install (/mobile) | FREE_AND_PRACTICAL_NOW | Free | None |
| Tauri 2 iOS | REQUIRES_BRYAN_SETUP | Free for personal device, $99/yr for distribution | Apple ID |
| Tauri 2 Android | REQUIRES_BRYAN_SETUP | Free for local testing | Google account |
| Expo/React Native | REQUIRES_BRYAN_SETUP — separate codebase | Free tier | Expo account |

**Tauri 2 iOS local device (free, no App Store):**
```bash
npm run tauri ios init
# Connect iPhone, trust Mac
npm run tauri ios dev
# No Apple Developer Program needed for personal device testing
```

### Role-Scoped Cache Model

| Layer | Scope | Security | Cache Miss |
|---|---|---|---|
| `global_jarvis` | Jarvis-wide policy/architecture | Internal | Explicit CacheMiss |
| `role` | Per-role: COS/GM/managers | Internal | Explicit CacheMiss |
| `worker` | Per-worker task context | Internal | Explicit CacheMiss |
| `project` | Per-project context | Internal | Explicit CacheMiss |
| `validation` | Gate results / verifier output | Internal | Explicit CacheMiss |
| `failure_prevention` | Bug patterns, prevention items | Internal | Explicit CacheMiss |
| `continuity` | Mobile session/device state | Private | Explicit CacheMiss |

Workers cannot read Private-level entries of other roles. Cache miss is never guessed.

### Cost Dashboard / Token Ledger

- Tracks per role: Jarvis/COS/GM/manager/worker/verifier
- Tracks per task: token estimate, model, cache hit, retry count, rework tokens
- All costs without real provider metadata marked `[ESTIMATE]`
- Expensive task threshold: >$0.10/run — requires approval
- Exposed via `GET /v1/jarvis/cost-dashboard`

### Runtime Self-Knowledge Manifest

- Callable at runtime: `GET /v1/jarvis/manifest`
- Reports: current git HEAD/branch, active roles, available/blocked/missing items
- Reports voice status, mobile continuity status, no-gap status
- All items either `AVAILABLE` (with evidence file) or explicitly classified as blocked/missing

### COS Skill

Callable in pipeline — not just documented. `COSSkill.route()` returns `RoutingDecision`:
- Manager selected by keyword match against capability index
- Priority: CRITICAL/HIGH/NORMAL/LOW/DEFERRED
- Execution mode: parallel/sequential/single
- Verifier assignment: triggered on release/ship/deploy/accept keywords
- Blocker escalation: `cos.escalate_blocker()` → surfaced to Jarvis
- No-hidden-gap: `cos.enforce_no_hidden_gap()` compares claimed vs actual blockers

### Code Sentinel

Callable in pipeline and standalone. `CodeSentinel.run_gate()`:
1. Changed-file review (targeted access — no broad scan)
2. Stale artifact detection (7-day TTL)
3. Secret scan (regex patterns — OpenAI, GitHub PAT, AWS, password, api_key)
4. Unsafe action detection (force push, DROP TABLE, rm -rf, --no-verify)
5. Unsupported claim rejection (FULL_NO_GAP_JARVIS_COMPLETE, NO_GAP_JARVIS_CERTIFIED, etc.)
6. Validation command requirement (claims without commands → HIGH severity finding)
7. Durable prevention items created for CRITICAL/HIGH findings

### Personality / Policy Drift Guard

`DriftGuard.run_full_guard()` checks:
1. Fake readiness: "looks good", "should be fine", "mostly done"
2. Hidden blockers: "optional", "deferred", "skipped for brevity"
3. Forbidden claims: FULL_NO_GAP_JARVIS_COMPLETE, etc. → CRITICAL severity
4. Tone drift: "amazing", "fantastic", "we're all set" → MEDIUM severity
5. Validation skip: claimed vs actual commands run
6. Cross-device inconsistency: MacBook status vs mobile status mismatch

---

## 11. What Remains Required (Sprint 3 Consolidated Final)

| Gap | Classification | Evidence |
|---|---|---|
| MacBook-off continuity — valid token | BLOCKED_INVALID_TOKEN_FORMAT | Token present but too short/unknown prefix; HTTP 401 |
| Universal mobile project-building runtime | REQUIRED_FOR_NO_GAP_JARVIS | GitHub Actions backend designed; token + workflow setup needed |
| Remote execution runtime (GitHub Actions) | REQUIRES_BRYAN_SETUP | Template available; Bryan must create workflow + valid token |
| Real test/build execution (not simulated) | REQUIRED_FOR_NO_GAP_JARVIS | Worker-test-runner is simulated; needs real shell execution |
| Native iOS/Android (distribution) | REQUIRES_BRYAN_SETUP | Local device testing free; $99/yr for App Store distribution |
| Voice daily-driver | SEPARATE_SPRINT_REQUIRED | Text fallback required and documented |
| Full no-gap certification suite (30 tasks) | HOLD | Not run in this sprint |
| Production deploy | BLOCKED — Bryan authorization required | Hard gate |
| External Slack/Telegram sends | BLOCKED — safety policy | No sends in this sprint |

**GITHUB_TOKEN exact requirement:**
- Must start with `ghp_` (Classic PAT) and be 40+ characters
- Required scopes: `gist` (snapshot sync) + `workflow` (trigger Actions) + `repo` (diffs, logs)
- Current status: BLOCKED_INVALID_TOKEN_FORMAT — present but too short, unknown prefix

**OMNIX is NOT the center:**
- Jarvis must support any project/new project through the universal mobile runtime
- All capability matrix entries use generic project references, not OMNIX-specific paths

### Voice / Text Fallback Contract

**Text fallback is REQUIRED for all voice-first mobile UI:**
- Mic failure → text input (always available)
- No mic permission → text input
- Background noise → text input
- Voice is separate sprint — not activated here

---

## 12. Governance

- Hard gates require explicit Bryan approval — no exceptions
- Real outbound sends (Slack/Telegram) are hard-gated
- Destructive git/filesystem ops are hard-gated
- Secrets never appear in snapshots, logs, or responses
- `ACCEPT` requires concrete verified evidence — never assumed
- Partial/subpar completion is NOT accepted
- Voice remains separate sprint
- Full no-gap: `HOLD`
- Code Sentinel, Drift Guard, and Verifier are all callable in pipeline

---

*Generated: Sprint 3 Consolidated Final Retest — MacBook-Off Continuity + Universal Mobile Project-Building + Remote Execution Runtime Design + Hot-Reload + Security*
