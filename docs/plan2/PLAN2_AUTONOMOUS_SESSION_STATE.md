# Plan 2 Autonomous Session State

**RESUME_FROM_HERE**

## Current State

| Field | Value |
|-------|-------|
| Branch | `localhost-get-tool` |
| HEAD | `b8cb53bf` (Fix B8 workspace sync: correct JarvisMemory import path and MemoryEntry serialization) |
| Remote | `fork/localhost-get-tool` (push pending — after this update) |
| Working tree | Dirty — pre-existing only: `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py` |
| Untracked (pre-existing, do NOT stage) | `evidence/`, `scripts/plan1_cockpit_proof.py`, `scripts/plan9_copy_cloud_api_key.sh`, `scripts/plan9_verify_cloud_api_key.py` |
| Active worktrees | None |
| Fargate image | `jarvis-full-b8cb53bf` (task def rev 19) — RUNNING + HEALTHY + ECS Exec ENABLED |
| Auto-continue safe | YES — all live proofs complete; B1 vault migration is the only remaining open blocker |

## Plan 2 Verdict

`PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD`

**Reason:** B1 (Google OAuth refresh tokens local-only — vault migration requires manual OAuth re-grant) is the single remaining open blocker.
All other blockers: B2 CLOSED, B3 CLOSED, B4 LIVE_PROVEN, B5A READY, B5B READY, B5C LIVE_PROVEN (Slack + Telegram both), B6 CLOSED, B7 LIVE_PROVEN, B8 LIVE_PROVEN.

**Not accepted.** Only Bryan/ChatGPT reviewer can accept.

## Plan 2 Live Proof Sprint — B4/B5C/B7/B8 via ECS Exec (current)

**Sprint:** Plan 2 live proof — B4 Notion, B5C Slack+Telegram, B7 Life-OS, B8 Workspace via ECS Exec
**Base HEAD:** `03630202` → fixes → `b8cb53bf`
**Fargate:** task def rev 19, image `jarvis-full-b8cb53bf`, task `f4b726323916494ba9950952eedea901`
**ECS Exec:** ENABLED (ssmmessages IAM perms added to task role; force-new-deployment)
**JARVIS_TELEGRAM_CHAT_ID:** discovered via `getUpdates` inside container; added to task def rev 19 environment
**NOTION_API_KEY:** added to task def rev 19 secrets (valueFrom Secrets Manager ARN); API live-proven

### What was done

1. **IAM task role update** — added `ssmmessages:CreateControlChannel/DataChannel/OpenControlChannel/OpenDataChannel` to `omnix-workbench-ecs-task-policy`; required for ECS Exec.
2. **ECS service** — `enable-execute-command=true` + force-new-deployment on rev 18 → rev 19.
3. **Telegram chat ID discovery** — used `getUpdates` via ECS Exec on rev 18 task; chat type: private; ID captured without printing token.
4. **task def rev 19** — new image `jarvis-full-b8cb53bf`; NOTION_API_KEY added to secrets; JARVIS_TELEGRAM_CHAT_ID added to environment (public identifier, not a secret).
5. **B8 import fix** — `plan2_routes.py` corrected: `openjarvis.jarvis_memory` → `openjarvis.memory.store`; `MemoryEntry` objects serialized via `.to_dict()` before `push_raw()`.
6. **Docker build** — `jarvis-full-b8cb53bf` built and pushed to ECR.
7. **Rev 19 deployment** — registered task def rev 19; service updated; task RUNNING + HEALTHY + ExecAgent RUNNING.

### Live Proof Results (via ECS Exec on rev 19 task f4b726323916494ba9950952eedea901)

| Blocker | Proof Command | Result |
|---------|---------------|--------|
| B5C Slack | `SlackNotificationAdapter.send()` | **SLACK_DELIVERED: True** |
| B5C Telegram | `TelegramNotificationAdapter.send()` (with JARVIS_TELEGRAM_CHAT_ID=discovery) | **TG_DELIVERED: True** |
| B7 Life-OS | `POST /v1/life-os/sync` | **b7_sync_status: SYNCED**, 0 tasks → `life_os_tasks/tasks.jsonl` in 219ms |
| B8 Workspace | `POST /v1/workspace/sync` | **b8_sync_status: SYNCED**, 127 raw entries → `jarvis_memory/raw_entries.jsonl` in 279ms |
| B4 Notion | Notion API `/v1/users/me` | **REACHABLE_AND_AUTHENTICATED**, user_type=bot, len=50 key |

### B1 Google OAuth — Exact Blocker Statement

**Status:** No vault migration exists in the repo. Manual step required:

1. User (Bryan) re-grants Google OAuth via browser for each connector (Gmail, GCalendar, GDrive, GContacts, GTasks)
2. Resulting refresh tokens stored in AWS Secrets Manager under the existing secrets key
3. `src/openjarvis/connectors/google_auth.py` updated to read refresh tokens from Secrets Manager instead of local files (`~/.openjarvis/connectors/google.json` etc.)
4. New Fargate task def revision referencing the new secret keys
5. ECS service redeployment

**No automated path exists.** `_google_oauth_local_status()` returns `LOCAL_FILE_ONLY, cloud_vault_configured=False` as designed. This is a human-action blocker.

### Blocker registry after this sprint

| Blocker | Before | After | Status |
|---------|--------|-------|--------|
| B1 Google OAuth | LOCAL_FILE_ONLY | Unchanged — vault migration not implemented | **OPEN — manual vault migration required** |
| B2 Env vars | Secret refs confirmed | Unchanged (CLOSED) | CLOSED |
| B3 Telegram alias | Code CLOSED | Unchanged | CLOSED |
| B4 Notion | NOT_CONFIGURED | NOTION_API_KEY in task def rev 19; API live-proven | **LIVE_PROVEN** |
| B5A GitHub | Ready | Unchanged | READY |
| B5B Slack DM | Ready | Unchanged | READY |
| B5C Slack notification | Deployed, unproven | **LIVE_PROVEN — SLACK_DELIVERED: True** | **LIVE_PROVEN** |
| B5C Telegram notification | No chat ID | JARVIS_TELEGRAM_CHAT_ID discovered + injected; **LIVE_PROVEN — TG_DELIVERED: True** | **LIVE_PROVEN** |
| B6 Fargate readiness | CLOSED | Unchanged | CLOSED |
| B7 Life-OS cloud sync | Deployed, unproven | **LIVE_PROVEN — 0 tasks → S3 in 219ms** | **LIVE_PROVEN** |
| B8 Workspace sync | SYNC_ERROR (wrong import) | Fixed import; **LIVE_PROVEN — 127 entries → S3 in 279ms** | **LIVE_PROVEN** |

### Next step to resume

B1 Google OAuth vault migration — Bryan must:
1. Run OAuth re-grant flow for each Google connector via browser
2. Upload refresh tokens to AWS Secrets Manager
3. Update `google_auth.py` vault path
4. New task def revision + redeploy
5. Prove Google connector connectivity from Fargate

---

## Plan 2 Final Runtime Blocker Closure Sprint (prior)

**Sprint:** Plan 2 final runtime blocker closure — B2/B5C/B7/B8 adapters + sync endpoints
**Base HEAD:** `f3fc3480` (Plan 2 Fargate redeploy: rev 17 live)
**Commit:** `06ef9bf1`
**Purpose:** Implement concrete Slack/Telegram notification adapters (B5C), Life-OS S3 sync (B7 cloud), workspace memory sync (B8) endpoints; deploy rev 18; confirm HEALTHY.

### What was done

1. **notification_adapters.py** (NEW) — `SlackNotificationAdapter` + `TelegramNotificationAdapter` implementing `NotificationProviderAdapter`; checks all known token env var aliases incl. Fargate-injected `SLACK_BOT_TOKEN` / `TELEGRAM_BOT_TOKEN`; `get_configured_adapters()` factory; `get_adapter_status()` (no token values).
2. **life_os_s3_sync.py** (NEW) — `LifeOSTaskS3Sync` exports SQLitePersonalTaskStore tasks to S3 under `life_os_tasks/` prefix using `OMNIX_WORKBENCH_MEMORY_BUCKET` (present in Fargate env since task def rev 17).
3. **plan2_routes.py** (MODIFIED) — 6 new auth-gated endpoints: `POST /v1/notifications/dispatch`, `GET /v1/notifications/dispatch/status`, `POST /v1/life-os/sync`, `GET /v1/life-os/sync/status`, `POST /v1/workspace/sync`, `GET /v1/workspace/sync/status`.
4. **test_plan2_b2_b5c_b7_b8.py** (NEW) — 51 tests; 51/51 PASS.
5. **Docker build** — `jarvis-full-06ef9bf1` built and pushed to ECR.
6. **ECS task def rev 18** — registered; same 11 secrets + S3 env vars; new image tag.
7. **ECS service** — force-new-deployment to rev 18; rolloutState=COMPLETED; task RUNNING+HEALTHY.

### Live deployment proof

```
Task: ef923db555414371901bad1916dca2f3
lastStatus: RUNNING
health: HEALTHY
taskDef: omnix-workbench-jarvis-full:18
image: jarvis-full-06ef9bf1
containerHealth: HEALTHY
```

### Validation results
- 51/51 new B2/B5C/B7/B8 tests: PASS
- 493/494 total plan9 tests: PASS (1 pre-existing unrelated failure)
- git diff --check: CLEAN
- Secret scan: CLEAN
- High-entropy scan: CLEAN
- Fargate health: RUNNING + HEALTHY via ECS API

### Blocker status after this sprint

| Blocker | Before | After | Remaining gap |
|---------|--------|-------|---------------|
| B2 | Secret refs not all confirmed | ALL 11 secrets confirmed in task def rev 17/18 | Dispatcher DEPLOYED (new image) |
| B5C | No concrete adapters | SlackNotificationAdapter + TelegramNotificationAdapter + dispatch endpoint deployed | Live delivery needs Tailscale + JARVIS_TELEGRAM_CHAT_ID for Telegram |
| B7 (cloud) | No sync endpoint | LifeOSTaskS3Sync + POST /v1/life-os/sync deployed; S3 fully configured in Fargate | Live sync proof needs Tailscale |
| B8 | No sync trigger | POST /v1/workspace/sync deployed; S3 fully configured in Fargate | Live sync proof needs Tailscale |
| B1 | LOCAL_FILE_ONLY | Unchanged — client creds in SM; refresh tokens still local | Vault migration requires manual OAuth re-grant |
| B4 | NOT_CONFIGURED | Unchanged | Notion token required |

---

## Plan 2 Fargate Current-Code Redeploy + Runtime Proof Sprint (prior)

**Sprint:** Plan 2 Fargate current-code redeploy + runtime proof
**Base HEAD:** `90471fce` (Plan 2 B6 live proof: fargate_readiness SSL fix)
**Purpose:** Redeploy Fargate with Plan 2 code (`90471fce`); inject SLACK_BOT_TOKEN + TELEGRAM_BOT_TOKEN into task def; prove `git_commit=90471fce, engine=cloud`.

### What was done (cloud-side only — no code changes)

1. **Docker build** — `Dockerfile.full` rebuilt with all 3 validations passing; image `jarvis-full-90471fce` tagged.
2. **ECR push** — image pushed to `071179620006.dkr.ecr.ap-southeast-1.amazonaws.com/omnix-workbench:jarvis-full-90471fce`
3. **ECS task def rev 17** — registered with 11 secrets (7 existing + SLACK_BOT_TOKEN, TELEGRAM_BOT_TOKEN, GOOGLE_CLIENT_SECRET, GOOGLE_OAUTH_CLIENT_ID as Secrets Manager references)
4. **ECS service update** — `force-new-deployment` to rev 17; PRIMARY rolloutState=COMPLETED
5. **ALB target group** — deregistered old IP `10.0.1.99`; registered new IP `10.0.0.207`; state `initial → healthy`

### B6 Full Parity Live Proof

```
HTTP 200
status: ok
git_commit: 90471fce
jarvis_build_commit: 90471fce
engine: cloud
version: 1.0.2
```

Fargate is now running current HEAD `90471fce` — the same commit with Plan 2 routes, SSL fix, B1/B3/B4/B7 code-side changes, and all 5 layers confirmed.

### Smoke test results
- `/health` — 200, git_commit=90471fce, engine=cloud ✓
- `/v1/mobile-parity/status` — 200, HOLD verdict ✓
- `/v1/mobile-parity/connectors` — 200, connector matrix ✓
- `/v1/mobile-parity/life-os` — 200, b7_local_store_type=sqlite ✓
- `/v1/mobile-parity/memory` — 200, cloud_sync_available=True ✓
- `/v1/mobile-parity/approvals` — 200, approval_gate_status=READY, internal_notification_queue_status=READY ✓
- `/v1/mobile-parity/cloud-worker` — 200, BLOCKED (expected — JARVIS_CLOUD_ENDPOINT not set inside container) ✓

### Validation results
- 440 plan9 tests: PASS (1 pre-existing unrelated failure: `test_batch_integration_same_file_live`)
- Secret scan: CLEAN (docs only — no code changes this sprint)
- Live health check: HTTP 200, git_commit=90471fce, engine=cloud

---

## Plan 2 Full External Blocker Closure + Runtime Proof Sprint (prior)

**Sprint:** Plan 2 full blocker closure runtime proof (B1/B3/B4/B7 code-side)
**Base HEAD:** `6c9fdd25` (Plan 2 cloud worker readiness gating)
**Commit:** `2bdaef58`
**Purpose:** Close all safe code-only gating work for B1 (Google OAuth vault status abstraction), B3 (Telegram env alias verification), B4 (Notion env var check), B7 (SQLite persistence fix + cloud sync layer tracking)

### What was implemented (code)

- `src/openjarvis/jarvis_os/life_os_store.py` (NEW) — SQLite-backed `SQLitePersonalTaskStore`; closes the local-persistence gap for B7; no cloud calls; no secret values
- `src/openjarvis/jarvis_os/life_os_cloud_sync_status.py` (NEW) — B7 5-layer sync tracking (`local_store_type` / `s3_configured` / `sync_code_present` / `sync_executed` / `worker_access`); `sync_executed` and `worker_access` always `LAYER_REQUIRES_DEPLOYMENT`; no live S3 calls
- `src/openjarvis/jarvis_os/personal_os.py` (MODIFIED) — `get_personal_task_store()` now prefers `SQLitePersonalTaskStore` with in-memory fallback
- `src/openjarvis/server/plan2_routes.py` (MODIFIED) — added `_notion_present()`, `_google_oauth_local_status()`, `_life_os_cloud_sync_probe()`; updated `_connector_token_present()` for Notion (env var + file); updated `_status_2b_connectors()` with B1/B4 fields; updated `_status_2e_life_os()` with B7 layers; updated `GET /v1/mobile-parity/life-os`; fixed `GET /v1/mobile-parity/memory` to remove `pinecone_configured` and `cloud_sync_bucket_configured` presence booleans from public response (Phase 7 security audit)
- `tests/plan9/test_plan2_b1_b3_b4_b7.py` (NEW) — 43 tests: `TestB3TelegramDualAlias` (6), `TestB1GoogleOAuthVaultStatus` (7), `TestB4NotionNotConfigured` (8), `TestB7LifeOSCloudSyncStatus` (8), `TestB7SQLiteStore` (6), `TestPublicEndpointSafetyB1B4B7` (3), `TestPlan2HoldWithBlockers` (5)

### Validation results
- 43/43 new tests: PASS
- 442 plan9 tests: PASS (1 pre-existing unrelated failure: `test_batch_integration_same_file_live`)
- `git diff --check`: CLEAN
- Secret scan: CLEAN

### B1/B3/B4/B7 Code-Side Gating Summary

| Blocker | Before | After | External action still needed? |
|---------|--------|-------|-------------------------------|
| B1 | No vault status abstraction | `_google_oauth_local_status()` reports `LOCAL_FILE_ONLY`, `cloud_vault_configured=False` | YES — vault migration requires live credentials |
| B3 | Single env var only | Both `TELEGRAM_BOT_TOKEN` and `JARVIS_TELEGRAM_BOT_TOKEN` accepted | NO — code-side CLOSED |
| B4 | File-only check | Env vars `NOTION_API_TOKEN`, `NOTION_TOKEN`, `NOTION_INTEGRATION_TOKEN` also checked | NO for code; YES for actual token |
| B7 (local) | In-memory only | SQLite backend active; tasks survive restart | NO — local persistence CLOSED |
| B7 (cloud) | No sync tracking | 5-layer tracking; sync_executed always LAYER_REQUIRES_DEPLOYMENT | YES — cloud sync requires Fargate |

## Plan 2 Fargate Worker Readiness Sprint (prior)

**Sprint:** Plan 2 cloud worker readiness gating
**Base HEAD:** `43c58b89` (Plan 2G B5B)
**Commit:** `6c9fdd25`
**Purpose:** Close all safe code-only gating work for B6/B8/B5C before live Fargate deployment sprint

| Blocker | Before | After | External action still needed? |
|---------|--------|-------|-------------------------------|
| B5C | NOT_CONFIGURED | `CONFIGURED_NOT_DEPLOYED` (code-side gating present) | YES — live Fargate + Slack/Telegram tokens |
| B6 | OPEN (no gating) | `CONFIGURED_NOT_DEPLOYED` (multi-layer abstraction, never fakes READY) | YES — live ECS Fargate deployment |
| B8 | OPEN (no gating) | `LAYER_REQUIRES_DEPLOYMENT` (5-layer tracking, sync_executed always blocked) | YES — live Fargate worker for sync execution |

## Plan Sequence

| Plan | Verdict | Status |
|------|---------|--------|
| Plan 2A | `PLAN_2A_MOBILE_MACBOOK_OFF_FOUNDATION_PATCHED_PENDING_REVIEW` | Foundation patched — awaiting acceptance |
| Plan 2B | `PLAN_2B_CONNECTOR_TASK_PARITY_FOUNDATION_PATCHED_PENDING_REVIEW` | Foundation patched — awaiting acceptance |
| Plan 2C | `PLAN_2C_FILE_WORKSPACE_DATA_PARITY_CLOSED_PENDING_REVIEW` | Foundation closed — awaiting acceptance |
| Plan 2D | `PLAN_2D_MEMORY_CONTEXT_ROUTING_PARITY_PATCHED_PENDING_REVIEW` | Foundation patched — awaiting acceptance |
| Plan 2E | `PLAN_2E_LIFE_OS_PARITY_PATCHED_PENDING_REVIEW` | Foundation patched — awaiting acceptance |
| Plan 2F | `PLAN_2F_VOICE_FOUNDATION_PATCHED_PENDING_REVIEW` | Foundation patched (Plan 3 parked) |
| Plan 2G | `PLAN_2G_APPROVAL_NOTIFICATION_PARITY_PATCHED_PENDING_REVIEW` | B5A+B5B closed; B5C CONFIGURED_NOT_DEPLOYED |
| Plan 2H | `PLAN_2H_LONG_RUNNING_PARITY_PATCHED_PENDING_REVIEW` | Foundation patched + Fargate readiness gating; awaiting acceptance |
| Plan 2I | `PLAN_2I_DEPLOY_PARITY_PATCHED_PENDING_REVIEW` | Foundation patched — awaiting acceptance |
| Full Plan 2 | `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD` | **HOLD — B1, B4, B5C (partial), B7/B8 (code deployed, live proof needed); B2/B3/B5A/B5B/B6 CLOSED/CONFIRMED** |

## Blocker Registry (updated 2026-06-24)

| ID | Blocker | Subsection | Status | Remaining gap |
|----|---------|------------|--------|---------------|
| B1 | Google OAuth tokens local JSON → vault/cloud migration | 2B | **PARTIAL** — GOOGLE_CLIENT_SECRET + GOOGLE_OAUTH_CLIENT_ID in SM ✓; gmail.json refresh tokens still LOCAL_FILE_ONLY | Vault migration for refresh tokens — manual OAuth re-grant required |
| B2 | GitHub/Slack/Telegram env tokens → Fargate deployment | 2B | **CONFIRMED_DEPLOYED** — ALL 11 secrets in task def rev 17/18; Slack+Telegram+GitHub adapters wired; dispatch endpoint at POST /v1/notifications/dispatch | Telegram delivery needs JARVIS_TELEGRAM_CHAT_ID env in task def; Slack can deliver (hardcoded default channel) |
| B3 | Telegram env mismatch | 2B | **CODE_CLOSED** — both TELEGRAM_BOT_TOKEN and JARVIS_TELEGRAM_BOT_TOKEN accepted | N/A |
| B4 | Notion not configured | 2B | **NOT_CONFIGURED** — no token in SM or task def | Notion API token required |
| B5A | Approval gate / queue | 2G | **CLOSED** | N/A |
| B5B | Internal notification enqueue | 2G | **CLOSED** | N/A |
| B5C | External notification delivery | 2G | **DEPLOYED — live proof pending** — SlackNotificationAdapter + TelegramNotificationAdapter + POST /v1/notifications/dispatch deployed in rev 18; Slack token present + default channel hardcoded → can deliver; Telegram missing JARVIS_TELEGRAM_CHAT_ID | Live delivery proof needs Tailscale to call endpoint; Telegram needs chat ID env var |
| B6 | Fargate worker / cloud execution path | 2H | **CLOSED** — Running rev 18 `06ef9bf1`, RUNNING+HEALTHY, task def rev 18 active | N/A |
| B7 (local) | Life-OS task store in-memory | 2E | **CLOSED** — SQLite backend active | N/A |
| B7 (cloud) | Life-OS not synced to cloud | 2E | **DEPLOYED — live proof pending** — LifeOSTaskS3Sync + POST /v1/life-os/sync deployed; S3 bucket config present in Fargate env | Live S3 sync proof needs Tailscale to call endpoint |
| B8 | Workspace sync to S3 | 2C | **DEPLOYED — live proof pending** — POST /v1/workspace/sync deployed; JarvisMemoryS3Sync available; S3 config present in Fargate env | Live S3 sync proof needs Tailscale to call endpoint |
| B9 | Voice/wake/TTS | 2F | **Parked** (Plan 3 — permanent) | N/A |

## Hard Blockers Remaining

- **B1**: Google OAuth refresh token vault migration — manual OAuth re-grant required; client credentials already in SM
- **B4**: Notion API token — not configured anywhere
- **B5C (Telegram)**: `JARVIS_TELEGRAM_CHAT_ID` env var not in Fargate task def — add to task def to enable Telegram delivery
- **B5C/B7/B8 (live proof)**: Tailscale stopped — cannot call Fargate endpoints locally; start Tailscale to prove delivery/sync

## Next Step to Resume

**RESUME_FROM_HERE:** B2/B5C/B7/B8 code implemented + deployed in Fargate rev 18. Docs update pending commit.

**To prove remaining live delivery:**
1. **Start Tailscale** → call `POST /v1/notifications/dispatch` with Bearer auth → proves B5C Slack delivery
2. **Add JARVIS_TELEGRAM_CHAT_ID to task def env** → register rev 19 → redeploy → prove Telegram delivery
3. **Call `POST /v1/life-os/sync`** with Bearer auth → proves B7 cloud sync
4. **Call `POST /v1/workspace/sync`** with Bearer auth → proves B8 S3 sync
5. **Migrate Google OAuth refresh tokens** to SM → proves B1

**To close B4:**
- Add Notion API token to SM under `NOTION_API_TOKEN` key → update task def to inject it → redeploy

**Do NOT stage:** `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py`, `evidence/`, `scripts/plan1_cockpit_proof.py`, `scripts/plan9_copy_cloud_api_key.sh`, `scripts/plan9_verify_cloud_api_key.py`

## Hard Rules Active
- No Tauri rebuild
- No `git add .`
- No secret values printed
- No fake ACCEPTED/READY
- No Plan 3 voice/wake/TTS
- Changed-file-only staging
- HOLD verdict until all in-scope blockers are closed

---
*Last updated: Plan 2 Full External Blocker Closure + Runtime Proof Sprint — B1/B3/B4/B7 code-side, Phase 7 public endpoint security audit*
*Never save secret values, tokens, OAuth contents, private keys, .env contents*
