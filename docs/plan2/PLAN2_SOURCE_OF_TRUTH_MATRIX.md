# Plan 2 — Full Mobile MacBook-Off Parity Runtime
## Source-of-Truth Matrix

**Acceptance target:** `MOBILE_MACBOOK_PARITY_TARGET_LOCKED`
**Sprint:** Plan 2A + 2B + 2C + 2D + 2E + 2F + 2G + 2H + 2I Foundation + Live Proof + B1 Google OAuth Cloud
**Sprint verdict:** `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_READY_FOR_ACCEPTANCE_REVIEW`
**Previous verdict:** `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD` (all B1–B8 now closed)
**Based on:** Plan 1 accepted commit `6cc99316`
**Plan 1 verdict locked:** `PLAN_1_DUAL_PLATFORM_JARVIS_NEURAL_COMMAND_CENTER_ACCEPTED`
**Generated:** 2026-06-24
**Last updated:** 2026-06-25 (final acceptance review sprint — all blockers live-proven, Tauri rebuild validated)
**Fargate:** task def rev 20, image `jarvis-full-9a1cbdc1`, RUNNING + HEALTHY
**Tauri build:** v1.0.2 artifact built and validated (build-local.sh --allow-applications-update, 117s)
**Machine-readable artifact:** `docs/plan2/plan2_matrix.json`
**Runtime status endpoint:** `GET /v1/mobile-parity/status`
**Plan 2C detail endpoint:** `GET /v1/mobile-parity/files`

---

## Plain Requirement

Whatever Jarvis can do on MacBook/desktop should eventually be operable from phone/mobile while the MacBook is off, subject only to real platform, security, connector, permission, cost, and approval limits.

---

## Status Legend

| Status | Meaning |
|--------|---------|
| `READY` | Fully working on this surface right now |
| `LOCAL_ONLY` | Works only when connected to local MacBook backend |
| `CLOUD_REQUIRED` | Needs cloud/Fargate backend + auth; API exists but must be pointed at cloud URL |
| `MACBOOK_OFF_PENDING` | Architecture exists but data/worker not cloud-synced yet |
| `AUTH_REQUIRED` | Needs Bearer token or OAuth — not configured for this surface |
| `NOT_CONFIGURED` | Feature exists in codebase but no keys/setup for this surface |
| `SETUP_REQUIRED` | Needs manual setup step before this surface can use it |
| `UNAVAILABLE` | Not implemented or blocked by hard gate |
| `PARKED` | Explicitly deferred to a later plan |
| `DEGRADED` | Partially working — some capability degraded |
| `ERROR` | Real runtime failure (not a placeholder) |

---

## 2A — Coding / Workbench Parity

**Implementation files:**
- `src/openjarvis/server/workbench_routes.py`
- `src/openjarvis/plan9/capability_matrix.py`
- `src/openjarvis/server/plan9_routes.py`

**Key routes:** `POST /v1/workbench/plan`, `POST /v1/workbench/execute`, `POST /v1/workbench/approve`, `GET /v1/workbench/capabilities`, `POST /v1/workbench/terminal/exec`, `GET /v1/coding/workspace`, `POST /v1/coding/files/read`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `CLOUD_REQUIRED` |
| MacBook-off | `CLOUD_REQUIRED` |
| Auth | Bearer token required |

**Data/storage:** SQLite session store; `OMNIX_WORKBENCH_ARTIFACT_BUCKET` (S3, configured)
**Connector dependency:** GitHub (`CROSS_DEVICE_LIVE`); repo clone required for file edit
**Known blockers:**
- No mobile-native IDE shell — coding tasks route through chat/frontdoor
- `coding_file_edit` is `CLOUD_LIVE` (not cross-device) — requires cloud execution context
- Terminal exec requires `approval_token`; no push-notification channel for mobile approval yet
- Fargate backend must be running for MacBook-off execution

**Required next patch:** Mobile task submission form for workbench plans; approval notification routing
**Proof for acceptance:** `POST /v1/workbench/plan` from iPhone Safari returns 200 with `session_id`; status poll returns result

---

## 2B — Connector / Task Parity

**Implementation files:**
- `src/openjarvis/server/connectors_router.py`
- `src/openjarvis/server/frontdoor_routes.py`
- `src/openjarvis/connectors/{gcalendar,gmail,github,gdrive,slack_connector}.py`

**Key routes:** `GET /v1/connectors/status`, `POST /v1/frontdoor/submit`, `GET /v1/connectors/list`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `CLOUD_REQUIRED` |
| MacBook-off | `CLOUD_REQUIRED` |
| Auth | Bearer token + connector OAuth tokens |

**Data/storage:** Google OAuth refresh token migrated to AWS Secrets Manager (B1 LIVE_PROVEN). Slack/Telegram/GitHub tokens in task def. Notion API key in task def.
**Connector dependency:** Gmail, Calendar, Drive: `LIVE_PROVEN` (Fargate rev 20). Slack, Telegram: `LIVE_PROVEN` (notifications delivered). Notion: `LIVE_PROVEN` (bot user authenticated). GitHub: `CROSS_DEVICE_LIVE`.
**Known blockers (resolved):**
- B1 CLOSED — Google OAuth refresh token in Secrets Manager; `google_auth.py` cloud path active; Gmail/Calendar/Drive LIVE_PROVEN from Fargate
- B4 CLOSED — NOTION_API_KEY in Secrets Manager + task def; Notion API LIVE_PROVEN
- B5C CLOSED — Slack DELIVERED: True; Telegram DELIVERED: True (JARVIS_TELEGRAM_CHAT_ID injected rev 19)

**Required next patch:** Secure connector token export to cloud vault; mobile OAuth callback handler
**Proof for acceptance:** `GET /v1/connectors/status` from iPhone shows authenticated connectors; task routes to connector

---

## 2C — File / Workspace / Data Parity

**Sprint verdict:** `PLAN_2C_FILE_WORKSPACE_DATA_PARITY_CLOSED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/server/plan9_routes.py`
- `src/openjarvis/plan9/workspace_root.py`
- `src/openjarvis/server/plan2_routes.py`
- `src/openjarvis/server/auth_middleware.py`
- `src/openjarvis/omnix_storage.py`
- `src/openjarvis/omnix_workbench.py`

**Key routes:**
- `GET /v1/files/cloud-index` — git-tracked file index, cloud-container safe (public)
- `GET /v1/files/workspace/status` ← **NEW (Plan 2C closure)** — workspace sync status (auth-gated)
- `GET /v1/mobile-parity/files` — Plan 2C parity status detail (public, sanitized)
- `GET /v1/files/index` — local filesystem index (allowlisted, metadata only)
- `POST /v1/coding/files/read` — read file content (allowlisted, git-tracked paths, auth-gated)
- `POST /v1/coding/search` — repo code search (auth-gated)

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `MACBOOK_OFF_PENDING` |
| MacBook-off | `MACBOOK_OFF_PENDING` |
| Auth | Bearer token required (`/v1/mobile-parity/files` is public) |

**Data/storage:** Local filesystem + `OMNIX_WORKBENCH_MEMORY_BUCKET` (S3, configured). Full workspace not synced.
**Connector dependency:** `OMNIX_WORKBENCH_ARTIFACT_BUCKET` (S3); `OMNIX_WORKBENCH_STORAGE_PROVIDER` configured
**Known blockers:**
- Full workspace sync to S3 not implemented — git-tracked files accessible via repo operations only
- Mac-only unsynced files remain `QUEUED_MAC_ONLY` per Plan 9 acceptance (permanent exception)

**Plan 2C closure (this sprint):**
- `workspace_sync_summary()` added to `workspace_root.py` — honest git-tracked/modified/untracked counts; no paths/contents
- `_s3_artifact_store_probe()` added to `plan2_routes.py` — presence-only S3 status; never exposes values; returns READY/PARTIAL/BLOCKED/NOT_CONFIGURED
- `GET /v1/files/workspace/status` added (auth-gated) — full workspace sync accounting including S3 probe; blocks 401 without Bearer token
- `_status_2c_files()` updated — uses `_s3_artifact_store_probe()` and `workspace_sync_summary()`; reports `s3_artifact_store_status`
- `GET /v1/mobile-parity/files` updated — sanitized public response; `sprint_verdict: PLAN_2C_FILE_WORKSPACE_DATA_PARITY_CLOSED_PENDING_REVIEW`
- `tests/plan9/test_plan2c_file_parity.py` — 27 smoke tests: path traversal, secret non-exposure, fake-READY prevention, S3 honest status

**Plan 2 Fargate readiness sprint (B8 code-side gating):**
- `workspace_sync_status.py` added to `memory/` — 5-layer workspace sync tracking; `sync_executed` and `cloud_worker_access` always `LAYER_REQUIRES_DEPLOYMENT` (no live S3 calls)
- `_workspace_sync_probe()` added to `plan2_routes.py` — calls `get_workspace_sync_status().to_dict()`
- `_status_2c_files()` updated — adds `workspace_sync_status` (full object) and `workspace_sync_layers` (5-layer breakdown) to files parity dict; B8 blocker references `sync_executed == requires_deployment`
- `GET /v1/mobile-parity/cloud-worker` includes `workspace_sync_status` summary (public endpoint)
- 52 new tests in `test_plan2_fargate_readiness.py` cover `TestWorkspaceSyncLayerDistinction` (7 tests: all 5 layers present, sync_executed always requires_deployment)

**Known remaining (not Plan 2C blockers):**
- Full bidirectional workspace sync to S3 is a Fargate deployment concern, not a code blocker — architecture is present
- Mac-only untracked files remain QUEUED_MAC_ONLY permanently

**Required next patch (Plan 2D):** Memory/context/routing parity
**Proof for closure:** `GET /v1/mobile-parity/files` returns `cloud_file_index_available: true` and `s3_artifact_store_status` reflects runtime; 27 tests pass

---

## 2D — Memory / Context / Routing Parity

**Sprint verdict:** `PLAN_2D_MEMORY_CONTEXT_ROUTING_PARITY_PATCHED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/server/memory_routes.py`
- `src/openjarvis/memory/{store,cloud_sync,cloud_memory,status}.py`
- `src/openjarvis/mobile/continuity.py`

**Key routes:** `GET /v1/memory/status`, `POST /v1/memory`, `GET /v1/memory/retrieve`, `GET /v1/continuity/snapshot`, `GET /v1/continuity/resume`, `GET /v1/mobile/continuity/status`, `GET /v1/mobile-parity/memory (public, sanitized)`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `CLOUD_REQUIRED` |
| MacBook-off | `CLOUD_REQUIRED` |
| Auth | Bearer token required; `/v1/continuity/macbook-off-status` is public |

**Data/storage:** Primary SQLite (local). Cloud sync: `OMNIX_WORKBENCH_MEMORY_BUCKET` (S3). Semantic: Pinecone (`PINECONE_API_KEY` present).
**Connector dependency:** `PINECONE_API_KEY` present; `OMNIX_WORKBENCH_MEMORY_BUCKET` present
**Known blockers:**
- SQLite primary store is local — cloud sync to S3 requires explicit sync trigger
- Full bidirectional sync not verified post-Plan 9
- Context injection from cloud memory to cloud-executed tasks not verified

**Required next patch:** Verify cloud memory sync end-to-end; snapshot sync trigger on commit
**Proof for acceptance:** Memory written on iPhone appears in `GET /v1/memory/retrieve` on desktop within 60s

---

## 2E — Life-Business OS Operation Parity

**Sprint verdict:** `PLAN_2E_LIFE_OS_PARITY_PATCHED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/server/{life_os_routes,workstream_routes,goals_routes,mission_routes}.py`

**Key routes:** `GET/POST /v1/life-os/tasks`, `GET/POST /v1/workstreams`, `GET/POST /v1/goals`, `GET /v1/mobile-parity/life-os (public, sanitized)`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `CLOUD_REQUIRED` |
| MacBook-off | `CLOUD_REQUIRED` |
| Auth | Bearer token required |

**Data/storage:** SQLite local; no cloud sync implemented for life-os data yet
**Connector dependency:** None required for basic task management
**Known blockers:**
- Life-OS data (tasks, workstreams, goals) stored in local SQLite — not synced to cloud
- No push notification for task updates on mobile
- Mission control real-time updates not streamed to mobile

**Required next patch:** Cloud sync for life-os data store; mobile-optimized task management UI
**Proof for acceptance:** Task created on iPhone visible on desktop; task created on desktop visible on iPhone

---

## 2F — Voice / Tap-to-Speak Foundation

**Sprint verdict:** `PLAN_2F_VOICE_FOUNDATION_PATCHED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/server/voice_routes.py`
- `src/openjarvis/speech/`, `src/openjarvis/voice/`

**Key routes:** `POST /v1/voice/transcribe`, `POST /v1/voice/speak`, `GET /v1/mobile-parity/voice (public — Plan 3 PARKED)`

| Surface | Status |
|---------|--------|
| Desktop | `LOCAL_ONLY` |
| Mobile web | `NOT_CONFIGURED` |
| MacBook-off | `MACBOOK_OFF_PENDING` |
| Auth | Bearer token required |

**Data/storage:** `DEEPGRAM_API_KEY` present; `JARVIS_STT_PROVIDER` configured; `JARVIS_TTS_PROVIDER` configured
**Known blockers:**
- Full wake word and TTS is `PARKED` (Plan 3) — **do NOT reopen**
- Foundation tap-to-speak (browser MediaRecorder → `/v1/voice/transcribe`) not wired in mobile UI
- Audio permissions require HTTPS on mobile browsers
- TTS playback requires Web Audio API on mobile — not yet wired

**Required next patch (foundation only):** Wire browser MediaRecorder → `POST /v1/voice/transcribe` in mobile UI
**Proof for acceptance:** Tap-to-speak button captures audio, sends to backend, populates chat input (no wake word, no TTS)

---

## 2G — Notifications / Approval Parity

**Sprint verdict:** `PLAN_2G_APPROVAL_NOTIFICATION_PARITY_PATCHED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/server/{approval_routes,notify_routes}.py`
- `src/openjarvis/tools/approval_store.py`
- `src/openjarvis/authority/approval_engine.py`
- `src/openjarvis/authority/notification_queue.py` ← **NEW (Plan 2G B5B closure)**

**Key routes:** `GET /v1/approvals/pending`, `POST /v1/approvals/{id}/approve`, `POST /v1/approvals/{id}/deny`, `GET /v1/notify/status`, `POST /v1/notify/send`, `GET /v1/mobile-parity/approvals (public, sanitized)`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `CLOUD_REQUIRED` |
| MacBook-off | `CLOUD_REQUIRED` |
| Auth | Bearer token required for approval actions; `/v1/mobile-parity/approvals` is public |

**Data/storage:** SQLite approval store (local); SQLite internal notification event queue (local). External channel keys present — but delivery auto-trigger not deployed.

**B5 three-layer breakdown:**

| Layer | Status | Notes |
|-------|--------|-------|
| B5A — Approval gate / queue | `READY` | `ApprovalEngine` creates PENDING records for tier 2+; auth-gated routes; `ApprovalStore` persists; NUS1D TTL/scope enforced |
| B5B — Internal notification enqueue | `READY` (Plan 2G closure sprint) | PENDING approval creation enqueues an internal event in `notification_queue.db`; safe metadata only; no external side effects |
| B5C — External delivery | `NOT_CONFIGURED` | Slack/Telegram/push delivery requires live provider tokens + Fargate deployment; auto-trigger not wired |

**Known blockers:**
- B5A: Approval store is local SQLite — not synced to cloud for MacBook-off case
- B5A: Mobile approval polling interval not yet implemented in UI
- B5B: **CLOSED (Plan 2G closure sprint)** — internal notification enqueue now wired on PENDING approval creation
- B5C: External delivery (Slack/Telegram/push) not deployed — requires live provider tokens and Fargate worker

**Plan 2G B5B closure (Plan 2G sprint):**
- `notification_queue.py` added to `authority/` — SQLite-backed internal event queue; safe metadata only; no external side effects
- `approval_engine.py` hooked — `request_approval()` enqueues internal notification event when `status == PENDING` (tier 2+); soft hook (failure logged, never blocks approval)
- `_status_2g_approvals()` updated — three-layer B5A/B5B/B5C breakdown in status dict
- `/v1/mobile-parity/approvals` updated — exposes `approval_gate_status`, `internal_notification_queue_status`, `external_notification_delivery_status`; sanitized blockers; no env var names
- `tests/plan9/test_plan2g_approval_notification.py` — 35 tests: B5A gate, B5B enqueue, B5C blocked, public endpoint safety, auth-gated routes, overall HOLD verdict

**Plan 2 Fargate readiness sprint (B5C code-side gating):**
- `notification_dispatcher.py` added to `authority/` — injectable `NotificationProviderAdapter` ABC; `NotificationDispatcher` consumer skeleton; no live sends without configured provider tokens; approval gates never modified
- `get_external_delivery_status()` — returns `NOT_CONFIGURED` or `CONFIGURED_NOT_DEPLOYED` based on token presence; never returns `READY` without live verification
- `_notification_queue_probe()` updated in `plan2_routes.py` — calls `get_external_delivery_status()` for B5C status; fallback if import fails
- 52 new tests in `test_plan2_fargate_readiness.py` cover `TestNotificationDispatcherNoLiveDelivery` and `TestExternalDeliveryHonestStatus`; `TestApprovalGateNotBypassed` verifies no bypasses

**Required next patch (B5C):** Deploy Fargate worker with Telegram/Slack provider token; wire `NotificationQueue.list_pending()` → external delivery; mobile approval polling every 30s
**Proof for acceptance:** New pending approval triggers Telegram notification; Bryan approves from iPhone via `POST /v1/approvals/{id}/approve`

---

## 2H — Long-Running Cloud Execution Parity

**Sprint verdict:** `PLAN_2H_LONG_RUNNING_PARITY_PATCHED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/plan9/mac_worker_queue.py`
- `src/openjarvis/server/{plan9_routes,orchestrator_routes}.py`
- `src/openjarvis/server/fargate_readiness.py` ← **NEW (Plan 2 Fargate readiness sprint)**

**Key routes:** `GET /v1/mac-worker/queue`, `POST /v1/mac-worker/queue`, `GET /v1/mac-worker/status`, `POST /v1/orchestration/dag/run`, `POST /v1/orchestration/batch/run`, `GET /v1/mobile-parity/long-running (public)`, `GET /v1/mobile-parity/cloud-worker (public, B6 status)`, `GET /v1/mobile-parity/cloud-worker/detail (auth-gated, layer detail)`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `CLOUD_REQUIRED` |
| MacBook-off | `MACBOOK_OFF_PENDING` |
| Auth | Bearer token required |

**Data/storage:** Mac worker queue: local SQLite. Fargate: `OMNIX_WORKBENCH_AWS_PROFILE` + `OMNIX_WORKBENCH_AWS_REGION` configured.
**Connector dependency:** AWS ECS Fargate (configured per Plan 4)

**B6 Fargate worker readiness layers (this sprint):**

| Layer | Status | Notes |
|-------|--------|-------|
| code_present | `ok` | `deploy/aws/cloud_runtime.py` exists |
| configured | depends on env | All 5 required env vars must be set |
| deployed | `REQUIRES_EXTERNAL_ACTION` | ECS service not started |
| reachable | `REQUIRES_EXTERNAL_ACTION` | Health check not verified |
| executing | `REQUIRES_EXTERNAL_ACTION` | No worker process running |

**Known blockers:**
- Mac worker queue processes tasks only when MacBook is online and process is running
- Cloud execution daemon not deployed to Fargate (B6: CONFIGURED_NOT_DEPLOYED)
- No long-running job status webhook/push for mobile polling
- DAG/batch orchestration routes are cloud-safe but require Fargate worker for execution

**Plan 2 Fargate readiness sprint (this sprint):**
- `fargate_readiness.py` added — multi-layer B6 readiness abstraction; no live calls; no secret values
- `get_cloud_worker_parity_status()` — new public `/v1/mobile-parity/cloud-worker` endpoint
- `get_cloud_worker_detail()` — new auth-gated `/v1/mobile-parity/cloud-worker/detail` endpoint
- `tests/plan9/test_plan2_fargate_readiness.py` — 52 tests covering all 9 required scenarios
- `docs/plan2/FARGATE_WORKER_DEPLOYMENT_CONTRACT.md` — deployment contract (non-secret)

**Required next patch:** Deploy Fargate worker (requires live AWS credentials — separate authorized sprint)
**Proof for acceptance:** Long-running task submitted from iPhone completes while MacBook is off; result visible on iPhone

---

## 2I — Deployment / Release / Signing Workflow Parity

**Sprint verdict:** `PLAN_2I_DEPLOY_PARITY_PATCHED_PENDING_REVIEW`

**Implementation files:**
- `src/openjarvis/server/{plan9_routes,self_upgrade_routes}.py`
- `scripts/build-local.sh`
- `rust/`, `desktop/`

**Key routes:** `POST /v1/deploy/plan`, `POST /v1/self-upgrade/request`, `GET /v1/self-upgrade/status`, `GET /v1/mobile-parity/deploy (public)`

| Surface | Status |
|---------|--------|
| Desktop | `READY` |
| Mobile web | `MACBOOK_OFF_PENDING` |
| MacBook-off | `MACBOOK_OFF_PENDING` |
| Auth | `APPROVAL_REQUIRED` for all deploy/signing actions |

**Data/storage:** `APPLE_SIGNING_IDENTITY`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD` present (local keychain)
**Connector dependency:** `GITHUB_TOKEN` present; AWS profile configured for ECS deploy
**Known blockers:**
- Tauri app build and signing require MacBook with Xcode/codesign — cannot run on Fargate (`QUEUED_MAC_ONLY`)
- Apple signing certificate in local keychain — not accessible from cloud
- ECS/Vercel deploy (non-signing) could be triggered from mobile with approval gate — not yet wired
- Self-upgrade route exists but triggers local script — not safe from mobile without cloud CI

**Required next patch:** Wire cloud ECS deploy to be triggerable from mobile with approval gate; Tauri signing stays `QUEUED_MAC_ONLY`
**Proof for acceptance:** ECS backend redeployment triggered from iPhone returns 200 after approval; Tauri signing correctly rejected from mobile

---

## Global Auth State

| Item | Status |
|------|--------|
| Mechanism | Bearer API key (`OPENJARVIS_API_KEY`) |
| Desktop storage | `~/.openjarvis/config.toml` |
| Mobile storage | `localStorage` (`jarvis_mobile_api_key`) |
| Cloud auth | Same Bearer token against AWS ECS Fargate |
| Multi-user | Not implemented (single-user only) |
| Public endpoints | `/health`, `/health/mobile-proof`, `/v1/continuity/macbook-off-status`, `/v1/mobile-parity/status` |

---

## Cloud Backend State

| Item | Status |
|------|--------|
| Provider | AWS ECS Fargate |
| URL | `https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com` |
| Plan 4 certification | `PLAN_4_AWS_PRIVATE_RUNTIME_SECURITY_ACCEPT_PENDING_REVIEW` |
| TLS cert | Amazon RSA 2048, expires Aug 2026 |
| Fargate worker deployed | No — API only, no worker process |

---

## MacBook-Off Summary

| Subsection | MacBook-Off Status |
|-----------|-------------------|
| 2A Coding/Workbench | `CLOUD_REQUIRED` |
| 2B Connector/Task | `CLOUD_REQUIRED` |
| 2C File/Workspace | `MACBOOK_OFF_PENDING` |
| 2D Memory/Context | `CLOUD_REQUIRED` |
| 2E Life-Business OS | `CLOUD_REQUIRED` |
| 2F Voice (foundation) | `MACBOOK_OFF_PENDING` |
| 2G Notifications/Approval | `CLOUD_REQUIRED` |
| 2H Long-Running Execution | `MACBOOK_OFF_PENDING` |
| 2I Deployment/Signing | `MACBOOK_OFF_PENDING` |

**Global blocker:** Primary data stores (memory, approvals, life-os, connector tokens) are local SQLite — cloud sync required for MacBook-off parity across all subsections.

---

## Plan 2A Foundation Sprint — What Was Patched

1. **`GET /v1/mobile-parity/status`** — new read-only endpoint, public (no auth required), returns honest runtime state for each Plan 2 subsection using Plan 2 status vocabulary.
2. **`docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md`** — this document.
3. **`docs/plan2/plan2_matrix.json`** — machine-readable matrix artifact.
4. **Frontend Plan 2 parity panel** — added to `MobilePage.tsx` as `Plan2ParityPanel` component, calls `/v1/mobile-parity/status`, displays honest per-subsection status.
5. **`auth_middleware.py`** — `/v1/mobile-parity/status` added to public paths.

---

## What Was NOT Done (Plan 2A Is Foundation Only)

- Did not implement cloud sync for SQLite stores
- Did not deploy Fargate worker process
- Did not implement tap-to-speak (2F)
- Did not implement Telegram/Slack approval notification triggers
- Did not wire ECS deploy from mobile
- Did not complete any subsection to `READY` on mobile/MacBook-off
- Did not claim Plan 2 is complete or accepted
- Did not start Plan 3 voice/wake/TTS
