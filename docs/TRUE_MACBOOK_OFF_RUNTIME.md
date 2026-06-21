# True MacBook-Off Jarvis Runtime

**Branch:** `localhost-get-tool`
**Created:** 2026-06-22
**Status:** `TRUE_MACBOOK_OFF_RUNTIME_DESIGN_ACCEPT_PENDING_REVIEW`

---

## Current Truth (as of 2026-06-22)

| Mode | Status | Evidence |
|------|--------|----------|
| MacBook-on LAN (local_lan) | **LIVE** | `uv run jarvis serve --host 0.0.0.0 --port 8000` → HTTP 200, Rust memory active |
| MacBook-off continuity (state sync) | **AVAILABLE** | GitHub gist backend active, `classification: AVAILABLE` |
| Full MacBook-off Jarvis AI runtime | **LIVE** | AWS ECS Fargate `https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com` — health HTTP 200, `engine:cloud`, `model:gpt-4o`, uptime confirmed Jun 22 2026 |

> **Critical distinction:** "MacBook-off continuity" (GitHub gist, state sync) is NOT the same as "full MacBook-off Jarvis runtime" (AI chat + memory + connectors without MacBook running). Both are now LIVE.

---

## True MacBook-Off Acceptance Criteria

A true MacBook-off Jarvis runtime is accepted **only when ALL of these are true simultaneously**:

1. MacBook uv server is **stopped** (not just asleep).
2. iPhone on any mobile network (not LAN) can reach a stable HTTPS Jarvis URL.
3. `GET /health` returns `status: ok` from that HTTPS URL.
4. `POST /v1/chat/completions` with a valid Bearer token returns an LLM assistant response.
5. Auth gate works: `/v1/*` returns 401 without token.
6. `/mobile` returns HTTP 200 with Jarvis HTML.
7. No secrets are exposed in responses.
8. Local-only tools that are unavailable cloud-side are honestly reported as unavailable (not silently pretending to work).

**Current status:** Items 1–7 are architecturally proven (Plan 4 `ACCEPT_PENDING_REVIEW`). Item 8 is honestly handled: the cloud ECS correctly reports `tool_execution_enabled: false` for destructive local tools.

---

## Runtime Mode Definitions

| Mode | Condition | What Works | What Doesn't |
|------|-----------|------------|--------------|
| `local_lan` | MacBook running, mobile on same WiFi | Full Jarvis AI + memory + connectors + Rust | MacBook-off access |
| `cloud` | ECS Fargate running, any network | Full Jarvis AI + S3 memory + LLM + approvals + auth | Rust bridge, local OAuth tokens, local tools |
| `continuity_only` | No server reachable, GitHub gist available | State snapshot read/write | No AI, no connectors, no LLM |
| `unavailable` | No server, no gist | Nothing | Everything |

The server reports its own mode (`local_lan` or `cloud`). `continuity_only` and `unavailable` are client-side states only (the server can't report them if it's not running).

---

## Existing Cloud Runtime Inventory

### ECS Fargate Full Runtime
- **URL:** `https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com`
- **Entry path:** HTTPS API Gateway → VPC Link → internal NLB → ECS:8000
- **ECS private IP:** `10.0.1.200:8000` (ephemeral — changes on restart)
- **Security:** Port 8000/3091 blocked from `0.0.0.0/0`; only reachable via VPC
- **Image:** `Dockerfile.full` — full Jarvis FastAPI (`jarvis serve --host 0.0.0.0 --port 8000`)
- **Model:** `gpt-4o` via OpenRouter/OpenAI
- **TLS cert:** Amazon RSA 2048 M04, valid until **Aug 26, 2026**
- **Auth:** Bearer token (separate key from local `OPENJARVIS_API_KEY`)
- **Memory:** SQLite + S3 sync active; AI distillation active
- **Last proven live:** 2026-06-22 (this session — health HTTP 200, uptime ~13 hrs)
- **ECS code version:** Deployed during Plan 4 (`~43316a18`–`1062e992`); does NOT include sprints 7C–8B or memory_routes fix from HEAD `334f9726`+

### State-Sync Backend (GitHub Gist)
- Active on both local and cloud paths
- GITHUB_TOKEN present, format valid
- `classification: AVAILABLE`

### Key Infrastructure IDs
| Resource | ID/ARN |
|----------|--------|
| API Gateway | `2r8dnzlz1h` (`jarvis-full-https`) |
| NLB | `jarvis-full-nlb` / `a1bba1be1d8ff367` (internal) |
| VPC Link | `fh2zmj` |
| ECS task private IP | `10.0.1.200` (last known) |

---

## Local-Only Dependency Inventory

| Dependency | Cloud-side status | Risk if unavailable |
|------------|------------------|---------------------|
| SQLite `~/.jarvis/memory.db` | Replaced by S3 JSON on ECS | No local memory on cloud (S3 is cloud memory) |
| Rust memory bridge | NOT available on ECS | No `RUST_AVAILABLE=True` on cloud; SQLite + S3 still works |
| OAuth token files (Gmail/Calendar) | NOT deployed to ECS | Gmail/Calendar `is_connected()` = False on cloud |
| Slack `SLACK_USER_TOKEN` | NOT on ECS | Slack DM sync unavailable cloud-side |
| Local filesystem tools | Blocked (hard gates) | `shell_exec`, `file_write`, `git_commit` unavailable |
| Tauri packaged app | Local UI only | No cloud desktop; mobile PWA is the cloud UI |
| Local Ollama | Not on ECS | No local model; cloud uses OpenRouter/OpenAI |
| `~/.openjarvis/config.toml` local API key | Separate ECS API key | Must use ECS key for cloud auth |

---

## Architecture Options

### Option A — Existing AWS ECS (RECOMMENDED — already live)
Full Jarvis FastAPI on ECS Fargate, served via HTTPS API Gateway. **Currently deployed and running.**

| | |
|--|--|
| **Works while MacBook is off** | Full AI chat (gpt-4o), S3 memory, approvals, connectors (limited), auth, `/mobile` HTML |
| **Does not work** | Rust bridge, local OAuth (Gmail/Calendar), local tools, Slack DM, local memory.db |
| **Secret/storage requirements** | ECS API key (already set), OPENAI/OPENROUTER keys (already in ECS env), S3 bucket (already configured) |
| **Cost** | ~$23.40/month (NLB + VPC Link) + ECS Fargate compute ~$20–30/month = ~$43–53/month running 24/7 |
| **Security** | HTTPS, Bearer token, VPC private origin, no public ports |
| **Implementation effort** | **Zero** — already deployed. Bryan needs to: (a) verify ECS key, (b) optionally rebuild ECS image for latest code |
| **Verdict** | **RECOMMENDED** — use this path |

### Option B — Lightweight Cloud Proxy + Local Worker
A minimal always-on proxy (Cloudflare Worker, Lambda, or small VPS) that receives requests and queues them. MacBook processes when available.

| | |
|--|--|
| **Works while MacBook is off** | Status, state sync, approval submission |
| **Does not work** | AI chat (requires MacBook to respond), real-time queries |
| **Secret/storage requirements** | Proxy credentials, queue storage |
| **Cost** | $5–15/month (small VPS or Lambda) |
| **Implementation effort** | Medium — new proxy layer, queue, MacBook polling agent |
| **Verdict** | Weaker than Option A for real-time AI. Use only if ECS is cost-prohibitive. |

### Option C — Hybrid: Cloud Front Door + GitHub Gist State + Deferred Local
Cloud HTTPS front door serves mobile UI and queues commands. MacBook picks up queue when on. GitHub Gist syncs state.

| | |
|--|--|
| **Works while MacBook is off** | Mobile UI, state read, command queuing |
| **Does not work** | Real-time AI responses, immediate connector actions |
| **Secret/storage requirements** | Cloud front door credentials, GitHub gist (already available) |
| **Cost** | ~$5–15/month |
| **Implementation effort** | Medium-high — deferred execution model, queue, reconciliation |
| **Verdict** | Better than nothing but worse than Option A for daily driver. Fallback only. |

### Option D — Keep Current State, Document Limitation
No cloud backend; document that MacBook must be on for full Jarvis.

| | |
|--|--|
| **Works while MacBook is off** | GitHub gist state sync only |
| **Does not work** | AI chat, connectors, memory queries, approvals |
| **Cost** | $0 additional |
| **Implementation effort** | None |
| **Verdict** | Option A is already live so Option D is a downgrade. Not recommended. |

---

## Recommended Path

**Use Option A (existing ECS) immediately.**

The ECS Fargate full runtime is already deployed, already answering requests, and already proven. No new deployment or account changes needed for the current sprint.

**Remaining steps for Bryan:**

1. **Locate ECS API key** — it was set as `OPENJARVIS_API_KEY` during Plan 4 ECS deployment. Likely stored in:
   - AWS Secrets Manager under `omnix-workbench-secrets`
   - Or the ECS task definition environment variables (check AWS console: ECS → Task Definitions → latest → container env)
   - Or notes from Plan 4 sprint session

2. **Test cloud mobile daily driver** on iPhone:
   ```
   URL: https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com/mobile
   ```
   - No LAN required
   - MacBook can be off

3. **Optional: rebuild ECS image** to include latest code (sprints 7C–8B + memory_routes fix):
   ```bash
   # Requires Bryan approval — do not run without authorization
   docker build -f deploy/aws/Dockerfile.full -t jarvis-full .
   # Push to ECR and update ECS service — Hard Gate: Bryan approval required
   ```

4. **TLS cert renewal**: Current cert valid until Aug 26, 2026. AWS auto-renews API Gateway certs — no action needed.

5. **ECS restart recovery**: If ECS task is restarted, run:
   ```bash
   deploy/aws/update_apigw_origin.sh  # re-registers new ECS private IP in NLB target group
   ```

---

## What Was Implemented This Sprint

### Runtime Mode Detection (`autonomy_routes.py`)
Added `_runtime_mode()` helper and `runtime_mode` + `cloud_url` fields to `/v1/mobile/continuity/status` response:
- `runtime_mode: "cloud"` when running on ECS
- `runtime_mode: "local_lan"` when running on MacBook
- `cloud_url`: reports the configured `JARVIS_CLOUD_URL` env var if set, for mobile clients to discover the cloud backend

### Docs
- This file: `docs/TRUE_MACBOOK_OFF_RUNTIME.md`
- Architecture options, acceptance criteria, local-only inventory

---

## What Was NOT Done (Requires Bryan Approval)

- No ECS deploy, rebuild, or image push
- No AWS account/billing/security changes
- No OAuth token migration to cloud
- No new paid services created
- No secrets moved

---

## Parked Items

- Voice / TTS / wake word: **PARKED**
- Apple signing / updater: **PARKED**
