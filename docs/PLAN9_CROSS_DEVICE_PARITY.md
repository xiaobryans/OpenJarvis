# Plan 9 — Full Cross-Device Jarvis Parity

**Status:** `PLAN_9_LIMITED_ACCEPT_PENDING_REVIEW`
**Created:** 2026-06-22
**Machine-readable:** `src/openjarvis/plan9/`
**Test suite:** `tests/test_plan9_cross_device_parity.py` — 104/104 passing

---

## Definition

Whatever Bryan can do on MacBook/local Jarvis, he must be able to do from mobile/cloud Jarvis.
Whatever Bryan can do from mobile/cloud Jarvis, he must be able to see/control from MacBook/local Jarvis.

Both are surfaces of one Jarvis system.

**Accepted permanent exception:** Rebuilding/reinstalling `/Applications/OpenJarvis.app` may remain MacBook-only after desktop/Tauri/packaged-app changes. This is classified as `QUEUED_MAC_ONLY`, not a parity gap.

---

## Accepted Parked Items (Not Plan 9 Scope)

| Item | Status | Plan |
|------|--------|------|
| Voice / Wake Word / TTS | `PARKED` | Plan 10 |
| Apple Signing / Auto-updater | `PARKED` | Plan 11 |
| `/Applications/OpenJarvis.app` reinstall | `QUEUED_MAC_ONLY` | Accepted permanent exception |
| Cursor rules | Not part of Plan 9 | Future roadmap |

---

## Scope: All Managers / All Teams

Plan 9 applies to every discovered manager, worker, agent, team, and operator domain.

### 17 Discovered Managers

| Manager ID | Domain |
|-----------|--------|
| `coding_manager` | All software coding |
| `architecture_manager` | System design |
| `testing_validation_manager` | Tests and acceptance evidence |
| `code_review_manager` | Code review and diffs |
| `debugging_manager` | Debugging and root cause |
| `research_manager` | Web and local research |
| `memory_knowledge_manager` | Memory, knowledge, context |
| `documentation_manager` | Documentation |
| `product_ux_manager` | Product and UX |
| `operations_automation_manager` | Ops and automation |
| `governance_safety_manager` | Policy, security, approval, audit |
| `release_packaging_manager` | Release, packaging, deploy |
| `data_manager` | Data operations |
| `cost_routing_manager` | Cost and model routing |
| `nus_learning_manager` | NUS learning and recommendations |
| `connector_auth_manager` | Connectors and auth |
| `runtime_ops_manager` | Runtime operations |

### 30 Discovered Workers

Backend Worker, Frontend Worker, Test Worker, Debug Worker, Refactor Worker,
Integration Worker, Security Code Worker, Performance Worker, Dependency Worker,
Git Commit Worker, System Architecture Worker, Contract Design Worker,
Integration Architecture Worker, Scalability Worker, Unit Test Worker,
Integration Test Worker, Regression Test Worker, Doctor Check Worker,
Acceptance Evidence Worker, Secret Safety Worker, Policy Gate Worker,
Risk Classification Worker, Approval Scope Worker, Local Research Worker,
Documentation Worker, Release Packaging Worker, Runtime Ops Worker,
Cost Analysis Worker, Data Worker, NUS Learning Worker.

---

## Capability Status Classifications

| Status | Meaning |
|--------|---------|
| `CLOUD_LIVE` | Available from mobile/cloud without MacBook |
| `LOCAL_LIVE` | Available on MacBook/local only |
| `CROSS_DEVICE_LIVE` | Available on both cloud and MacBook |
| `QUEUED_MAC_ONLY` | Mac-only; queued when offline |
| `APPROVAL_REQUIRED` | Exists but needs Bryan approval |
| `PARKED` | Explicitly parked to future plan |
| `MISSING` | Not yet implemented |
| `UNSAFE` | Would violate hard gates |
| `UNKNOWN_NEEDS_PROOF` | Cannot be verified without runtime evidence |

Full matrix: `src/openjarvis/plan9/capability_matrix.py`

---

## Jarvis PA vs Brain/Model Layer

```
Bryan
→ Jarvis PA (front-door, summarizer, approval gatekeeper)
  → COS/GM (orchestrates all 17 managers)
    → Managers → Workers / specialists → Reviewers / validators
    ← Aggregated results
  ← COS/GM summary
← Jarvis PA final status report
← Bryan
```

**Jarvis PA:**
- Uses only 1–2 stable models (balanced tier)
- Summarizes, coordinates, asks approvals, reports final status
- Does NOT do multi-provider routing itself

**Brain/model layer:**
- COS/GM + all 17 managers + all 30 workers + reviewers
- Routes across GPT/Claude/Perplexity/local models
- Uses role-based cheap/balanced/best routing

---

## Role-Based Model Routing

Every role has three tiers:

| Tier | When | Examples |
|------|------|---------|
| `CHEAP` | Reads, formatting, extraction, retrieval | Log reads, secret scan, doc formatting |
| `BALANCED` | Normal coding, planning, testing, review | Feature coding, test generation, docs |
| `BEST` | Architecture, security, deploy risk | System arch, security changes, deploy planning |

**Core rule:** Use the lowest-cost model that safely completes the task with enough quality.

Escalation: `cheap → balanced` when complexity=moderate/complex.
Escalation: `balanced → best` when risk=high/critical OR complexity=complex OR failures≥2.
Stop: after 3+ failures on same approach.

Full matrix: `src/openjarvis/plan9/model_routing.py`

---

## Retrieval Worker Policy

Every team has a cheap retrieval/reader/context worker policy.

Responsibilities:
- repo/file search
- log reads, docs lookup
- connector status reads
- memory/context retrieval
- test output summarization
- evidence extraction, source packet preparation
- deduplication, "what changed?" summaries

Retrieval always runs before expensive reasoning.
Expensive models receive compact evidence packets — not raw context dumps.

Full policy: `src/openjarvis/plan9/orchestration_policy.py`

---

## Safe Parallel Execution / DAG Policy

| Action | Safe to Parallelize |
|--------|-------------------|
| retrieval, file reads, log reads | ✅ Yes |
| independent analysis, test discovery | ✅ Yes |
| patch proposals (no master write) | ✅ Yes |
| same-file master writes | ❌ No — single Batch Integration Manager |
| git commit / push | ❌ No — single executor + lock |
| deploy execution | ❌ No — single executor + Bryan approval |
| IAM / secrets / billing changes | ❌ No — hard gate |
| destructive operations | ❌ No — hard gate + Bryan approval |
| external sends | ❌ No — Bryan approval required |

---

## Elastic Same-Role Worker Pools

Most teams support elastic pools:
- Retrieval workers: up to 10 parallel
- Backend/frontend/test workers: 3–8 parallel, shard by module/component
- Single executor only: `git_commit_worker`, `release_packaging_worker`, `secret_safety_worker`, `runtime_ops_worker`

---

## Same-File Batch Integration Protocol

When multiple workers all affect the same file:

1. **Workers** analyze/draft one item each **in parallel** → produce `PatchProposal`
2. **Batch Integration Manager** collects all proposals → produces single integrated diff
3. **Integration Review Manager** independently verifies all items present → `PASS/FAIL`

Rules:
- No patch may be dropped silently
- Overlapping hunks fall back to sequential integration
- Max 1 concurrent master write
- Workers != Integrator != Reviewer

---

## AI Organization Structure

Every manager/worker has:
- Clear ownership and scope
- Acceptance criteria and evidence requirements
- Model tier policy (from `model_routing.py`)
- Report format
- Capability matrix entry (parity status)

---

## Jarvis Internal Rules (Plan 9 Additions)

Defined in `src/openjarvis/plan9/rules.py`. Categories:

1. **TRUTH_EVIDENCE** — No fake complete, report format, classify honestly
2. **STOP_ON_BLOCKER** — Stop on missing credentials, failed validation, unclear authority
3. **SECRET_SECURITY** — Never print/commit secrets, scan before commit, Bryan approval for IAM
4. **APPROVAL_GATES** — Deploy, destructive, external sends, commit/push require gates
5. **TOKEN_COST** — Changed-file-only review, retrieval before reasoning, lowest sufficient model
6. **PARKED** — Voice/TTS, Apple signing, app reinstall exception
7. **PARITY** — Cloud equals Mac, no silent gaps

---

## Plan 9 Skills (21 Total)

| Skill | Status |
|-------|--------|
| Capability Inventory | WIRED |
| Model Routing | WIRED |
| Retrieval / Context Packet | PARTIAL |
| Task DAG / Scheduler | DOCUMENTED |
| Elastic Worker Pool | DOCUMENTED |
| Same-File Patch Proposal | DOCUMENTED |
| Batch Integration | DOCUMENTED |
| Integration Review | DOCUMENTED |
| Coding Workspace | DOCUMENTED |
| Test / Build Runner | DOCUMENTED |
| Commit / Push | DOCUMENTED |
| Deploy Operator | DOCUMENTED |
| Memory Parity | PARTIAL |
| Connector Parity | PARTIAL |
| Cloud File Mirror | DOCUMENTED |
| Mac Worker Queue | WIRED |
| Capability-Aware UI/API | DOCUMENTED |
| Authority / Approval / Audit | PARTIAL |
| Rollback | DOCUMENTED |
| Secret Scan | PARTIAL |
| Sprint Report | DOCUMENTED |

Full manifest: `src/openjarvis/plan9/skills_manifest.py`

---

## Plan 9 Commands (20 Total)

| Command | Status |
|---------|--------|
| `jarvis rules status` | DOCUMENTED |
| `jarvis skills list` | PARTIAL (existing `jarvis skill list`) |
| `jarvis skills status` | DOCUMENTED |
| `jarvis commands list` | DOCUMENTED |
| `jarvis capability matrix` | DOCUMENTED |
| `jarvis model-route explain --role --task --risk` | DOCUMENTED |
| `jarvis context-pack prepare --scope` | DOCUMENTED |
| `jarvis dag plan --task` | DOCUMENTED |
| `jarvis worker-pool plan --role --task` | DOCUMENTED |
| `jarvis patch-propose --file --item` | DOCUMENTED |
| `jarvis patch-integrate dry-run --file` | DOCUMENTED |
| `jarvis merge-review dry-run --file` | DOCUMENTED |
| `jarvis validate targeted` | PARTIAL |
| `jarvis secret-scan` | PARTIAL (existing `jarvis scan`) |
| `jarvis approval classify --action` | PARTIAL |
| `jarvis audit show --limit` | DOCUMENTED |
| `jarvis rollback plan` | DOCUMENTED |
| `jarvis report sprint` | DOCUMENTED |
| `jarvis parity status` | DOCUMENTED |
| `jarvis parked status` | DOCUMENTED |

Full manifest: `src/openjarvis/plan9/commands_manifest.py`

---

## Cloud Operator Capabilities

### Sections 12-15

| Capability | Status |
|-----------|--------|
| Cloud Coding Workspace (inspect/search/read/edit/diff) | CROSS_DEVICE_LIVE (planned route) |
| Cloud Test Runner (targeted pytest) | CROSS_DEVICE_LIVE (planned route) |
| Mobile Commit/Push Workflow | APPROVAL_REQUIRED |
| Cloud Deploy Operator (dry-run + approval) | APPROVAL_REQUIRED |

### Section 16: Cloud Memory Parity
- Cloud S3 memory + local store
- Continuity snapshot/resume
- Memory audit trail

### Section 17: Cloud Connector Parity
- Gmail, Calendar, Slack, GitHub: CROSS_DEVICE_LIVE
- Google Drive, Notion: UNKNOWN_NEEDS_PROOF (needs runtime proof)
- New connectors inherit cloud-parity, authority, audit, secret-safety by default

### Section 18: Cloud-Safe File Mirror/Index
- Allowlisted files indexed for cloud access
- No blind whole-Mac exposure
- Local-only unsynced files → Mac worker queue

### Section 19: Mac Worker Queue
- App reinstall, Mac app control, unsynced files, Keychain credentials
- Status visible on both mobile and MacBook
- Queue survives Mac offline periods

---

## Future-Proof Inheritance

Any new manager or worker automatically inherits:
- DEFAULT_ROUTING (cheap/balanced/best)
- Retrieval worker requirement (or explicit justification to skip)
- Audit/telemetry policy
- Capability matrix obligation
- Mobile + MacBook parity requirement
- Bryan approval for sensitive actions

Override requires `override_reason`. Missing policy = validation failure.

Full policy: `src/openjarvis/plan9/future_inheritance.py`

---

## Tests

**Test file:** `tests/test_plan9_cross_device_parity.py`
**Result:** 104/104 PASSING

Coverage:
- Manager/worker inventory (17+30)
- All managers have routing
- All managers have retrieval policy
- Routing matrix validates cleanly
- Parked items enforced (voice, apple signing)
- Capability status types correct
- Model tier escalation logic
- Parallel DAG safe/unsafe classification
- Elastic pool single-executor enforcement
- Batch integration protocol
- Mac worker queue CRUD
- Future inheritance validation
- Secret leak check

---

## Manual Proof Status

| Requirement | Status |
|------------|--------|
| Cloud/mobile can see capability matrix | DOCUMENTED (route /v1/capabilities/status planned) |
| MacBook can see capability matrix | DOCUMENTED (CLI `jarvis capability matrix` planned) |
| All 17 managers in matrix | ✅ PROVEN (test_all_manager_domains_covered passing) |
| Future manager inheritance tested | ✅ PROVEN (TestFutureInheritance all passing) |
| PA vs brain routing visible | ✅ PROVEN (pa_brain_layer.py + tests) |
| Cheap/balanced/best routing tested | ✅ PROVEN (TestModelRouting all passing) |
| Retrieval worker per team tested | ✅ PROVEN (TestManagerInventory passing) |
| Safe parallel DAG tested | ✅ PROVEN (TestParallelDAG all passing) |
| Elastic worker pool tested | ✅ PROVEN (TestElasticWorkerPools all passing) |
| Same-file batch integration tested | ✅ PROVEN (TestBatchIntegration all passing) |
| Batch Integration + Review Managers tested | ✅ PROVEN |
| Cloud coding workspace | DOCUMENTED (route planned; not yet wired in server) |
| Cloud test runner | DOCUMENTED (route planned; not yet wired in server) |
| Mobile commit/push path | DOCUMENTED (approval-gated; not yet wired in server) |
| Cloud deploy operator | DOCUMENTED (hard-gated dry-run; not yet wired in server) |
| Cloud memory parity | PARTIAL (cloud_memory.py exists; parity check needs runtime) |
| Cloud connector parity | PARTIAL (status route exists; full cloud-parity needs proof) |
| Cloud file mirror/index | DOCUMENTED (route planned; not yet wired) |
| Mac worker queue | ✅ PROVEN (TestMacWorkerQueue all passing) |
| Capability-aware UI/API | DOCUMENTED (routes planned; frontend not yet wired) |
| Audit/approval/rollback | PARTIAL (governance gate check exists; full audit trail planned) |
| No secrets in outputs | ✅ PROVEN (test_no_secrets_in_capability_output passing) |

---

## Verdict

**PLAN_9_LIMITED_ACCEPT_PENDING_REVIEW**

### What is accepted (PROVEN with tests):
- All 17 managers inventoried with routing, retrieval policy, and parity status
- All 30 workers inventoried with routing
- Future-proof inheritance policy — new manager/worker inherits defaults automatically
- Role-based cheap/balanced/best model routing matrix (47 roles)
- Retrieval worker per team (all 17 teams covered)
- Safe parallel DAG policy
- Elastic worker pool policy with single-executor rules
- Same-file batch integration protocol (Batch Integration Manager + Integration Review Manager)
- Mac worker queue implementation
- Capability matrix with all Plan 9 status types
- 21 skills manifest
- 20 commands manifest
- Jarvis PA vs Brain layer architecture
- Jarvis internal operating rules (Plan 9 additions to constitution)
- Parked items (voice, apple signing) enforced

### What remains as closure items (DOCUMENTED, not yet wired/proven at runtime):

1. Cloud coding workspace server routes (`/v1/coding/workspace`, `/v1/coding/files/*`)
2. Cloud test runner server routes (`/v1/testing/run`)
3. Mobile commit/push workflow server routes (`/v1/git/commit`)
4. Cloud deploy operator server routes (`/v1/deploy/plan`)
5. Cloud memory parity check (needs Bryan iPhone runtime proof)
6. Cloud connector parity for Google Drive, Notion (needs runtime proof)
7. Cloud-safe file mirror/index routes (`/v1/files/index`)
8. CLI command wiring for 16 DOCUMENTED commands
9. Capability-aware UI/API frontend integration
10. Full audit trail system wiring

### Rollback instructions:
- All changes are in `src/openjarvis/plan9/` (new directory)
- Constitution extension is additive (comment out `PLAN9_*` fields in `constitution.py` to revert)
- `tests/test_plan9_cross_device_parity.py` is the new test file
- No existing files were modified destructively

### Next narrow prompt if HOLD/BLOCKED:
Wire cloud operator routes in `src/openjarvis/server/` for Section 12-15:
- Add `/v1/coding/workspace`, `/v1/coding/files/read`, `/v1/coding/diff/stage`
- Add `/v1/testing/run`, `/v1/testing/lint`
- Add `/v1/git/commit` (single executor, approval-gated)
- Add `/v1/deploy/plan` (dry-run, hard-gated)
- Add `/v1/capabilities/status` (Plan 9 matrix endpoint)
- Add `/v1/parity/status`
- Add `/v1/mac-worker/queue`, `/v1/mac-worker/status`
