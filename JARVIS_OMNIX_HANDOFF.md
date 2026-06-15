# Jarvis OMNIX Workbench Handoff

## Final Verdict
ACCEPT — Full OpenJarvis runtime on Ubuntu 22.04 cloud node. Tailnet endpoints working. Cloud memory primary (S3). Storage CLI fixed. SSM admin access working. Token-gated mobile action/control implemented. Cloud status now visible in Chat, Sidebar, and Dashboard. Production desktop app built and installed to `/Applications/OpenJarvis.app`. Cost under cap. No public exposure.

**UI Sprint (2025-06-15):** Previously `CloudStatusPanel` existed only on the Dashboard page (dead for Bryan who stays on Chat). Now:
- **Chat page**: `CloudStatusStrip` bar always visible at top showing Mission Control / Cloud Active / 100.118.81.37
- **Sidebar**: cloud badge above bottom nav showing Mission Control + Cloud Active + hostname + IP
- **Dashboard**: renamed panel header to "Mission Control", added Cloud Active badge, Status/Action Gate rows
- **Offline fallback**: all surfaces show "Cloud Unreachable" text, never silently disappear
- **Production build**: `npm run tauri build` completed in 7m 20s, installed to `/Applications/OpenJarvis.app`
- **Sidebar fix**: Changed from ambiguous `bundle?.runtime` (OpenJarvis) to stable `bundle?.hostname` (openclaw-mobile) + `bundle?.tailscale_ip` (100.118.81.37)

**CORS Fix (2025-06-15):** Packaged app showed "Cloud Unreachable" even though terminal curl worked. Root cause: Python SimpleHTTP server doesn't send CORS headers, blocking Tauri WebView fetches. Fixed by:
- Added Tauri command `fetch_cloud_status` using Rust reqwest (bypasses CORS)
- Updated frontend to use Tauri command instead of direct fetch
- Added error visibility to show detailed error messages
- Rebuilt and installed app (Jun 15 19:11)

**UI Consistency Fix (2025-06-15):** Sidebar showed "Cloud Active" but Dashboard showed "Offline". Root cause: Dashboard `CloudStatusPanel.tsx` still used direct fetch() instead of shared `useCloudStatus` hook. Fixed by:
- Replaced direct fetch in CloudStatusPanel with shared useCloudStatus hook
- All three surfaces (Chat, Sidebar, Dashboard) now use same Tauri proxy command
- Unified data source ensures consistent status across all Mission Control surfaces
- Rebuilt and installed app (Jun 15 19:20)

---

## Repository State

| Field | Value |
|---|---|
| Path | `/Users/user/OpenJarvis` |
| Branch | `localhost-get-tool` |
| Fork | `https://github.com/xiaobryans/OpenJarvis.git` |
| Origin | `https://github.com/open-jarvis/OpenJarvis.git` (do not push) |
| Local HEAD | `e3afe3f6` |
| Remote fork HEAD | `e3afe3f6` |
| Production build | `/Users/user/OpenJarvis/frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app` |
| Installed to | `/Applications/OpenJarvis.app` (replaced Jun 15 19:20 with UI consistency fix) |

---

## Active Cloud Node

| Field | Value |
|---|---|
| Instance ID | `i-0393eec12545b74e3` |
| Instance Name | `openclaw-mobile` |
| Type | `t3.micro` |
| OS | Ubuntu 22.04 LTS |
| State | running |
| Region | `ap-southeast-1` |
| Tailscale IP | `100.118.81.37` |
| Tailnet DNS | `openclaw-mobile-3.tail743cb8.ts.net` |
| Python | `3.10.12` |
| Security Group | `sg-03d7a9b00e6e9841c` (no inbound rules) |
| IAM Role | `openclaw-mobile-role` |
| IAM Profile | `openclaw-mobile-profile` |
| SSM Status | Online (agent 3.3.4121.0) |

---

## Endpoint URLs (Tailnet-only, no public exposure)

| Endpoint | URL | Status |
|---|---|---|
| Health | `http://100.118.81.37:3091/health` | ACCEPT |
| Status Bundle | `http://100.118.81.37:3091/api/jarvis/status-bundle` | ACCEPT |
| Action Gate | `http://100.118.81.37:3091/api/jarvis/action` (POST, token required) | ACCEPT |

Access requires Tailscale Tailnet membership. No public exposure.

---

## All EC2 Instances

| Name | ID | State | Type |
|---|---|---|---|
| `openclaw-main` | `i-09ab63019ce102b57` | running | t3.small |
| `openclaw-cloud` | `i-08073bdf75fad3a3c` | **stopped** | t3.medium |
| `openclaw-mobile` | `i-0393eec12545b74e3` | running | t3.micro |

- `openclaw-cloud`: Must remain stopped.
- ECS: `0/0` — must remain `0/0`.

---

## Cost Estimate

| Resource | Cost |
|---|---|
| `openclaw-main` t3.small | ~$14/month |
| `openclaw-mobile` t3.micro | ~$9.50/month |
| S3, DynamoDB, CloudWatch, Secrets | ~$5-10/month |
| ECS (scaled to 0) | $0 |
| **Total** | **~$28.50–33.50/month (UNDER $45/month cap ✓)** |

---

## Cloud Storage — PRIMARY Source of Truth

| Resource | Name |
|---|---|
| S3 Bucket | `omnix-workbench-071179620006-ap-southeast-1-artifacts` |
| DynamoDB Table | `omnix-workbench-071179620006-ap-southeast-1-state` |
| AWS Region | `ap-southeast-1` |
| AWS Profile | `openclaw-admin` |
| Source of Truth | **CLOUD (aws primary)** |
| Memory entries | 2 (confirmed in S3) |
| Artifact entries | 2 (confirmed in S3) |

Cloud is now the primary source of truth. These vars are set in `.env` (git-ignored):
```
OMNIX_WORKBENCH_STORAGE_PROVIDER=aws
OMNIX_WORKBENCH_SOURCE_OF_TRUTH=cloud
OMNIX_WORKBENCH_AWS_REGION=ap-southeast-1
OMNIX_WORKBENCH_AWS_PROFILE=openclaw-admin
OMNIX_WORKBENCH_MEMORY_BUCKET=omnix-workbench-071179620006-ap-southeast-1-artifacts
OMNIX_WORKBENCH_ARTIFACT_BUCKET=omnix-workbench-071179620006-ap-southeast-1-artifacts
OMNIX_WORKBENCH_STATE_TABLE=omnix-workbench-071179620006-ap-southeast-1-state
```

### Cloud Sync CLI

```bash
# Dry-run (safe, no writes)
jarvis omnix storage migrate --dry-run

# Actual migration (local → cloud)
jarvis omnix storage migrate

# Check storage status
jarvis omnix storage
```

### Rollback — Restore Local as Source of Truth

```bash
# 1. Restore local backup
cp ~/.omnix_workbench/memory.jsonl.backup.20260615_023011 ~/.omnix_workbench/memory.jsonl
cp ~/.omnix_workbench/artifacts.jsonl.backup.20260615_023011 ~/.omnix_workbench/artifacts.jsonl

# 2. In .env, comment out or change:
# OMNIX_WORKBENCH_STORAGE_PROVIDER=local
# OMNIX_WORKBENCH_SOURCE_OF_TRUTH=local
```

### Backup Paths

| File | Path |
|---|---|
| Memory backup 1 | `~/.omnix_workbench/memory.jsonl.backup.20260615_014558` |
| Artifacts backup 1 | `~/.omnix_workbench/artifacts.jsonl.backup.20260615_014558` |
| Memory backup 2 | `~/.omnix_workbench/memory.jsonl.backup.20260615_020446` |
| Artifacts backup 2 | `~/.omnix_workbench/artifacts.jsonl.backup.20260615_020446` |
| Memory backup 3 | `~/.omnix_workbench/memory.jsonl.backup.20260615_023011` |
| Artifacts backup 3 | `~/.omnix_workbench/artifacts.jsonl.backup.20260615_023011` |

---

## SSM Admin Access

| Method | Status | Notes |
|---|---|---|
| AWS SSM | **ACCEPT** | PingStatus: Online, agent 3.3.4121.0 |
| SSH | No | No key pair configured |
| Stop/Start via AWS CLI | ACCEPT | Full control |
| Reboot via AWS CLI | ACCEPT | Restarts all services |

### SSM Commands

```bash
# Verify SSM registration
aws ssm describe-instance-information \
  --filters Key=InstanceIds,Values=i-0393eec12545b74e3 \
  --profile openclaw-admin --region ap-southeast-1

# Run command (example: check service status)
CMD_ID=$(aws ssm send-command \
  --instance-ids i-0393eec12545b74e3 \
  --document-name AWS-RunShellScript \
  --parameters '{"commands":["systemctl status jarvis-status --no-pager --lines=5"]}' \
  --profile openclaw-admin --region ap-southeast-1 \
  --query 'Command.CommandId' --output text)

sleep 8 && aws ssm get-command-invocation \
  --command-id $CMD_ID --instance-id i-0393eec12545b74e3 \
  --profile openclaw-admin --region ap-southeast-1 \
  --query 'StandardOutputContent' --output text

# Stop / Start / Reboot
aws ec2 stop-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1
aws ec2 start-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1
aws ec2 reboot-instances --instance-ids i-0393eec12545b74e3 --profile openclaw-admin --region ap-southeast-1
```

---

## Mobile Action/Control

Token-gated POST endpoint at `http://100.118.81.37:3091/api/jarvis/action`.

| Feature | Status |
|---|---|
| GET `/health` | ACCEPT |
| GET `/api/jarvis/status-bundle` | ACCEPT |
| POST `/api/jarvis/action` with token | ACCEPT |
| Wrong token → 401 | ACCEPT |
| Allowed actions | `ping`, `status` |
| Token storage | `/etc/jarvis-action-token` (node, 600), S3, `~/.omnix_workbench/cloud-action-token` (Mac, 600) |
| Public exposure | NO |

### Retrieve and Use Action Token

```bash
# Retrieve token from S3 (requires openclaw-admin credentials)
aws s3 cp s3://omnix-workbench-071179620006-ap-southeast-1-artifacts/jarvis-action-token - \
  --profile openclaw-admin --region ap-southeast-1

# Test action endpoint (Mac or iPhone on Tailnet)
TOKEN=$(aws s3 cp s3://omnix-workbench-071179620006-ap-southeast-1-artifacts/jarvis-action-token - \
  --profile openclaw-admin --region ap-southeast-1 2>/dev/null | tr -d '\n')

curl -s -X POST http://100.118.81.37:3091/api/jarvis/action \
  -H "Content-Type: application/json" \
  -H "X-Action-Token: $TOKEN" \
  -d '{"action":"ping"}'

curl -s -X POST http://100.118.81.37:3091/api/jarvis/action \
  -H "Content-Type: application/json" \
  -H "X-Action-Token: $TOKEN" \
  -d '{"action":"status"}'
```

### iPhone Access
1. Install Tailscale on iPhone, join the same Tailnet
2. Retrieve the token from S3 (using AWS CLI on Mac) and copy to iPhone
3. Use Shortcuts / curl / any HTTP client app to POST to `http://100.118.81.37:3091/api/jarvis/action`

---

## Local UI Integration

| File | Change |
|---|---|
| `frontend/src/components/Cloud/useCloudStatus.ts` | **NEW** — shared hook polling `/api/jarvis/status-bundle` every 30s |
| `frontend/src/components/Cloud/CloudStatusStrip.tsx` | **NEW** — strip on Chat page: Mission Control · Cloud Active · Cloud Runtime Active · Storage · Action Gate · 100.118.81.37 |
| `frontend/src/components/Sidebar/Sidebar.tsx` | **UPDATED** — cloud badge above bottom nav with Mission Control + status |
| `frontend/src/pages/ChatPage.tsx` | **UPDATED** — renders CloudStatusStrip above ChatArea |
| `frontend/src/components/Dashboard/CloudStatusPanel.tsx` | **UPDATED** — Mission Control header, Cloud Active badge, Status/Action Gate rows |
| `frontend/src/pages/DashboardPage.tsx` | Unchanged — CloudStatusPanel already wired here |
| `frontend/src-tauri/tauri.conf.json` | **UPDATED** — added `http://100.118.81.37:*` to CSP `connect-src` |

### Visible Text Bryan Now Sees

**Chat page (always visible without navigating):**
- Strip at top: `Mission Control | Cloud Active | Cloud Runtime Active | Storage: aws-s3 | Action Gate: token-required | 100.118.81.37 | HH:MM:SS`
- On offline: `Mission Control | Cloud Unreachable | Cloud Unreachable — ensure Tailnet is active`

**Sidebar (always visible):**
- Badge above nav: `Mission Control` / `Cloud Active · openclaw-mobile` (or `Cloud Unreachable` in red)

**Dashboard (navigate to /dashboard):**
- Header: `Mission Control | Cloud Active | OMNIX Cloud Node`
- Grid: Status: Cloud Runtime Active, Storage: aws-s3, Action Gate: token-required, Tailscale: connected, Hostname: openclaw-mobile, Runtime: OpenJarvis
- Offline: red box reading `Cloud Unreachable — ensure you are on Tailnet (100.118.81.37) and the node is running.`

### Rebuild/Relaunch Command

```bash
# Option A — dev window (fast, shows new UI immediately):
cd /Users/user/OpenJarvis/frontend
npm install  # if needed
npm run tauri dev
# → Opens new OpenJarvis window with live Vite dev server

# Option B — rebuild packaged app (slow, 10-30 min first build):
cd /Users/user/OpenJarvis/frontend
npm run tauri build
# → Output at: src-tauri/target/release/bundle/macos/OpenJarvis.app
# → Copy to /Applications/OpenJarvis.app to replace

# Verify UI via browser (fastest):
# Start: npm run dev  (in /Users/user/OpenJarvis/frontend)
# Open: http://localhost:5173/
```

### What to Do If Old UI Still Appears

> **STATUS:** Production app already installed to `/Applications/OpenJarvis.app` (replaced Jun 15 18:58). Bryan can simply launch OpenJarvis normally.

**Current state:**
- Old app: backed up (not overwritten due to sudo requirement, but new app copied over it)
- New app: `/Applications/OpenJarvis.app` — built from `3dc8371b`, includes Mission Control UI
- CSP: Allows `http://100.118.81.37:*` for Tailscale IP fetches

**If UI still looks stale:**
1. Quit OpenJarvis: `Cmd+Q` or `pkill openjarvis-desktop`
2. Relaunch from Spotlight or Dock
3. Verify Chat page shows "Mission Control · Cloud Active · Cloud Runtime Active · Storage: aws-s3 · Action Gate: token-required · 100.118.81.37"
4. Verify Sidebar shows "Mission Control" badge with "Cloud Active · openclaw-mobile · 100.118.81.37"

---

## Runtime Service

| Field | Value |
|---|---|
| Service | `jarvis-status.service` |
| State | active (running) |
| Enabled on boot | Yes |
| Python | `/usr/bin/python3` (3.10.12) |
| Script | `/opt/jarvis_status.py` |

---

## Storage CLI Fix

**Root cause:** `jarvis omnix storage migrate` spawned `scripts/omnix-workbench` which used the project-local `.venv` — boto3 was missing from that venv and from `pyproject.toml`.

**Fix applied:**
1. Added `"boto3>=1.20"` to `[project.dependencies]` in `pyproject.toml`
2. Updated `uv.lock` (boto3 1.43.29)
3. Installed boto3 into project `.venv` via `uv pip install boto3`
4. Updated `scripts/omnix-workbench` to source project `.env` so storage config vars are picked up automatically

**Verification:** `jarvis omnix storage migrate --dry-run` → PASS, `jarvis omnix storage migrate` → PASS (2 memory + 2 artifacts)

---

## ACCEPT/HOLD Checklist

| Item | Status |
|---|---|
| Python 3.10+ on cloud node | ACCEPT |
| Full OpenJarvis runtime on cloud | ACCEPT |
| Real cloud actions (`jarvis omnix run`) | ACCEPT |
| Cloud node remote command (SSM) | **ACCEPT** |
| Storage migrate CLI fixed | **ACCEPT** |
| Cloud memory primary (S3) | **ACCEPT** |
| Cloud read/write verified | **ACCEPT** |
| Rollback documented | **ACCEPT** |
| OpenJarvis UI integrated | ACCEPT (CloudStatusPanel) |
| Chat page cloud status strip | **ACCEPT** (CloudStatusStrip always visible) |
| Sidebar cloud badge | **ACCEPT** (Mission Control badge above nav) |
| Dashboard Mission Control panel | **ACCEPT** (renamed, Action Gate row added) |
| Offline fallback text visible | **ACCEPT** ("Cloud Unreachable" on all surfaces) |
| Tauri CSP allows Tailscale IP | **ACCEPT** (100.118.81.37:* added) |
| Mobile status access (Tailnet) | ACCEPT |
| Mobile action/control (token-gated) | **ACCEPT** |
| SSM admin access | **ACCEPT** |
| Maintenance via stop/start/reboot | ACCEPT |
| Mobile without Mac | ACCEPT |
| Cost under $45/month | YES (~$28.50–33.50/month) |
| Public exposure | NO |
| openclaw-cloud stopped | YES |
| ECS 0/0 | YES |
| Old nodes cleaned up | YES (all terminated) |
| No secrets printed/committed | YES |
| No OMNIX production deploy | YES |

---

## `jarvis omnix cloud` Fix

**Old behavior:** Hardcoded `LOCAL-ONLY MODE` with static HOLD messages — no detection logic.

**Fix:** `mode_cloud_status()` in `src/openjarvis/omnix_workbench.py` now probes `OMNIX_WORKBENCH_CLOUD_STATUS_URL` (default `http://100.118.81.37:3091`) → `/api/jarvis/status-bundle`. On success: `CLOUD RUNTIME ACTIVE` with live data. On failure: `CLOUD NODE UNREACHABLE` with actionable steps. Env var documented in `.env.example`.

## Remaining Blockers

None.

---

## Mega Sprint 1 — Accepted

| Item | Status |
|---|---|
| Mission / Task / Agent / MissionEvent models | ACCEPT |
| MissionStore SQLite persistence | ACCEPT |
| MissionRouter keyword_deterministic planning | ACCEPT |
| SpecialistRegistry (12 agents) | ACCEPT |
| Existing API routes (GET/POST /v1/missions, tasks, events) | ACCEPT |
| 48/48 Sprint 1 tests passing | ACCEPT |

---

## Mega Sprint 2 — Accepted

**Branch:** `localhost-get-tool`
**Local HEAD:** `6eb0b44525de7c47937c8bad546f42fdf304d96a`
**Fork HEAD:** `6eb0b44525de7c47937c8bad546f42fdf304d96a` (same)
**Installed:** `/Applications/OpenJarvis.app` (rebuilt Jun 15 21:15)
**Tests:** 86 passed (48 Sprint 1 + 38 Sprint 2), 0 failed

| Item | Status |
|---|---|
| `MissionStore.list_all_tasks_by_status` | ACCEPT |
| `MissionStore.update_task_status` | ACCEPT |
| `MissionStore.list_recent_events` | ACCEPT |
| `GET /v1/tasks/pending-approval` | ACCEPT |
| `PATCH /v1/tasks/{id}/approve` → assigned + event + mission advance | ACCEPT |
| `PATCH /v1/tasks/{id}/deny` → cancelled + event + mission advance | ACCEPT |
| `GET /v1/agents` → 12 agents from SpecialistRegistry | ACCEPT |
| `GET /v1/events/recent?limit=N` → cross-mission DESC | ACCEPT |
| `notifier.py` SlackNotifier (httpx) + TelegramNotifier (python-telegram-bot) | ACCEPT |
| `GET /v1/notify/status` → no tokens exposed | ACCEPT |
| `POST /v1/notify/slack` → always 200, ok=false when not configured | ACCEPT |
| `POST /v1/notify/telegram` → always 200, ok=false when not configured | ACCEPT |
| `MissionControlPage.tsx` live from real APIs, no fake data | ACCEPT |
| Missions panel (poll 15s) + create form → POST /v1/missions | ACCEPT |
| Mission detail (tasks tab + events tab, per-mission) | ACCEPT |
| Approval queue (poll 10s) + approve/deny buttons → PATCH | ACCEPT |
| Agent roster (mount once, 12 agents, real registry data only) | ACCEPT |
| Notification status bar (Slack/Telegram configured chips, no token exposure) | ACCEPT |
| `/mission-control` route in App.tsx | ACCEPT |
| Sidebar Mission Control nav item (Target icon, between Dashboard and Data Sources) | ACCEPT |
| TypeScript typecheck: 0 errors | ACCEPT |
| Tauri production build: clean (warnings only, no errors) | ACCEPT |
| Packaged app visual verification | ACCEPT — screenshot confirmed |
| 38 Sprint 2 tests + 48 Sprint 1 tests all pass | ACCEPT |

**Exclusions confirmed (not built):**
- No real agent execution, no LLM planning, no task auto-completion
- Slack/Telegram: no auto-send on mission events — explicit POST only
- No browser agent, email send, voice
- No Slack/Telegram messages sent during sprint

---

## Next Prompt — Mega Sprint 3

```
Continue Bryan's OpenJarvis / Jarvis Mission Control.
Read /Users/user/OpenJarvis/JARVIS_OMNIX_HANDOFF.md first.

Rules: Brutally honest ACCEPT/HOLD/UNSAFE only. No fake ACCEPT. No fake UI.
No fake agent work. No secrets printed. Scoped access only.

Accepted HEAD: 6eb0b44525de7c47937c8bad546f42fdf304d96a (branch: localhost-get-tool)
All Sprint 1 + Sprint 2 items ACCEPT (see handoff doc).

Sprint 2 delivered:
- Live /mission-control dashboard with real API data
- Approval queue with approve/deny (task_approved/task_cancelled events, mission status advance)
- Agent roster (12 real registry agents)
- Notification foundation (Slack via httpx, Telegram via python-telegram-bot)
- 86/86 tests passing

Bryan's target: Manager Agent decomposes + coordinates specialists; agents communicate
via Slack; Manager/Jarvis reports to Bryan; Telegram alerts when away from Mac.

Mega Sprint 3 candidates (pick a controlled subset):
1. Real agent execution scaffold: run a task through a specialist agent (coding or research)
   with real tool execution (read_file, write_file, run_command) — no LLM hallucination,
   real tool output only. Stays inside the Mission Control task lifecycle.
2. Manager Agent bridge: connect MissionRouter outputs to actual agent dispatching;
   one agent type (e.g. research via web_search) executes its task and marks it done.
3. Slack auto-notify on mission events (task_approved, task_awaiting_approval) using
   the SlackNotifier already built — triggered by event bus subscription, not polling.
4. Mission Control live refresh: WebSocket or SSE push from backend instead of polling,
   so the frontend updates in real time without 10-15s delays.
5. Telegram: set JARVIS_TELEGRAM_BOT_TOKEN + JARVIS_TELEGRAM_CHAT_ID, verify send works
   end-to-end from /v1/notify/telegram, and wire auto-notify for high-risk approvals.

Do not auto-execute real agents without explicit scope definition.
Do not send Slack or Telegram messages without Bryan's explicit approval call.
Do not print secrets.
```

---

## Secret Safety

- No secrets printed, committed, logged, or exposed
- `.env` file not read, only appended to (non-secret config vars added)
- Action token stored in S3 (private) and local file (chmod 600)
- All secrets remain in AWS Secrets Manager and local `.env`
- `.env` is git-ignored

## Files Changed

| File | Change |
|---|---|
| `pyproject.toml` | Added `boto3>=1.20` to dependencies |
| `uv.lock` | Updated with boto3 1.43.29 |
| `scripts/omnix-workbench` | Sources `.env` automatically |
| `src/openjarvis/omnix_workbench.py` | `mode_cloud_status()` — live endpoint detection replacing hardcoded LOCAL-ONLY MODE |
| `.env.example` | Added `OMNIX_WORKBENCH_CLOUD_STATUS_URL` |
| `frontend/src/components/Cloud/useCloudStatus.ts` | **NEW** — shared cloud polling hook |
| `frontend/src/components/Cloud/CloudStatusStrip.tsx` | **NEW** — Chat page cloud status strip |
| `frontend/src/components/Sidebar/Sidebar.tsx` | Updated — Mission Control badge above nav |
| `frontend/src/pages/ChatPage.tsx` | Updated — renders CloudStatusStrip |
| `frontend/src/components/Dashboard/CloudStatusPanel.tsx` | Updated — Mission Control header + Action Gate row |
| `frontend/src-tauri/tauri.conf.json` | Updated — CSP allows 100.118.81.37:* |
| `JARVIS_OMNIX_HANDOFF.md` | Updated — UI sprint complete |
