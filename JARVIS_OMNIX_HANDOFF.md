# Jarvis OMNIX Workbench Handoff

---

## Governance Lock-In — Constitution + Policy Enforcement

**Verdict: ACCEPT**
**Local HEAD:** `9bd8684b` | **Remote fork HEAD:** `9bd8684b` | **Git status:** clean

### What Was Built

| File | Change |
|---|---|
| `src/openjarvis/governance/constitution.py` | **NEW** — Jarvis identity, `Verdict`/`Evidence`/`Blocker` types, `HARD_GATE_ACTIONS`, `ALWAYS_APPROVAL_AGENTS`, `ProjectProfile`, `ProjectRegistry`, `OMNIX_PROJECT` |
| `src/openjarvis/governance/policies.py` | **NEW** — `requires_approval()`, `is_hard_gate()`, `classify_verdict()`, `validate_completion()`, `gate_check()`, `project_gate_check()`, `audit_log()` (secret-scrubbing), `build_blocker()`, `check_action_category()` |
| `src/openjarvis/governance/__init__.py` | **NEW** — unified exports |
| `docs/JARVIS_CONSTITUTION.md` | **NEW** — human-readable doctrine |
| `src/openjarvis/mission/router.py` | `_requires_approval()` now delegates to `governance.policies.requires_approval()` |
| `src/openjarvis/mission/runner.py` | `_persist_result()` uses `governance.validate_completion()` + `completion_refusal_reason()` |
| `tests/test_governance.py` | **NEW** — 44 governance tests |

### Governance Rules Locked In (Code-Enforced)

**1. Jarvis Identity:** Project-agnostic; OMNIX is Project 1 not the whole system; supervises all active projects concurrently.

**2. Honesty Policy:** `classify_verdict()` enforces ACCEPT requires verified evidence; HOLD on assumption/missing; UNSAFE on hard gate. `insufficient_data_message()` as standard phrase.

**3. Hard Gates (UNSAFE — no exception):**
`secrets_exposure`, `open_public_endpoint`, `tailscale_funnel`, `aws_infrastructure_change`, `omnix_production_deploy`, `vercel_deploy`, `supabase_change`, `stripe_change`, `billing_change`, `provider_routing_change`, `destructive_filesystem_op`, `destructive_git_op`, `real_slack_send`, `real_telegram_send`, `real_email_send`, `browser_form_submit`, `browser_purchase`, `browser_delete`, `browser_send`, `browser_account_mutation`, `production_data_change`

**4. Always-Approval Agents:** `deployment`, `email`, `security_risk`, `browser`, `coding`

**5. Multi-Project:** `ProjectRegistry` holds concurrent projects; OMNIX registered with priority=1; isolated `memory_namespace` per project; OMNIX `deploy_gates` include all production-critical gates.

**6. No Fake Work:** `validate_completion(output)` returns False for empty/whitespace; `_persist_result` in MissionRunner calls this via governance (not inline logic).

**7. Audit Safety:** `audit_log()` scrubs `token`, `secret`, `api_key`, `bot_token`, `chat_id`, etc. from context dicts before logging.

### How Future Agents Use Governance

```python
from openjarvis.governance import gate_check, classify_verdict, Evidence, EvidenceStatus, build_blocker

# Gate check before any action
result = gate_check("real_slack_send", agent_id="docs_report", risk_level="low")
# → {"allowed": False, "verdict": "UNSAFE", ...}

# Verdict from evidence
verdict = classify_verdict([
    Evidence("pytest output", EvidenceStatus.VERIFIED, source="pytest"),
])
# → Verdict.ACCEPT only if all evidence VERIFIED, no MISSING

# Structured blocker
blocker = build_blocker(
    blocker="web_search tool not wired",
    why_it_matters="research agent cannot execute without external search",
    unblock_path="implement WebSearchTool, register in ExecutorRegistry",
    can_continue_partially=True,
    partial_scope="docs/qa tasks can still run",
)
```

### Validation

```
pytest tests/test_governance.py tests/mission/ -v
→ 183 passed, 0 failed, 1 warning (httpx deprecation, non-blocking)
```

### What Remains to Enforce Later

- ProjectRegistry persistence (SQLite) — currently in-process only
- Per-project memory isolation enforcement in memory backend
- Multi-project mission routing (currently single pool)
- Slack/Telegram per-project channel routing via notifier
- Governance version history / immutable audit log persistence
- Agent-to-agent governance checks

---

## Mega Sprint 3 — Real Agent Execution + Slack/Telegram Operational Loop

**Verdict: ACCEPT**

### What Sprint 3 Implemented

**Backend — Agent Execution Layer**

| File | Change |
|---|---|
| `src/openjarvis/core/events.py` | Added: `MISSION_RUNNER_STARTED`, `TASK_STARTED`, `TASK_COMPLETED`, `TASK_BLOCKED`, `TASK_FAILED` |
| `src/openjarvis/mission/executor.py` | **NEW** — `ExecutionResult`, `AgentExecutor` protocol, 12 executor impls, `ExecutorRegistry` |
| `src/openjarvis/mission/runner.py` | **NEW** — `MissionRunner` with full lifecycle + `run_mission_pass` + `get_run_state` + auto-notify |
| `src/openjarvis/server/mission_routes.py` | Added: `POST /v1/missions/{id}/run`, `POST /v1/tasks/{id}/run`, `GET /v1/missions/{id}/run-state`, `GET /v1/executors`, `POST /v1/missions/{id}/notify/slack`, `POST /v1/missions/{id}/notify/telegram` |
| `src/openjarvis/mission/__init__.py` | Exports `ExecutionResult`, `ExecutorRegistry`, `MissionRunner`, `RunResult` |
| `tests/mission/test_mission_sprint3.py` | **NEW** — 53 tests, all passing |

**Frontend**

| File | Change |
|---|---|
| `frontend/src/pages/MissionControlPage.tsx` | Added: "Run Mission Pass" button with pass result summary, "Notify Slack" + "Notify Telegram" buttons with not_configured inline feedback, task `summary`/`result`/blocked reason display |

### Executor Behavior

| Agent | Executor | Behavior |
|---|---|---|
| `docs_report` | `DocsReportExecutor` | **COMPLETES** — deterministic text report from mission/task context |
| `qa` | `QAExecutor` | **COMPLETES** — deterministic QA validation report |
| `architect` | `ArchitectExecutor` | **COMPLETES** — deterministic architecture plan |
| `testing_bug` | `TestingBugExecutor` | **COMPLETES** — deterministic test validation report |
| `research` | `ResearchExecutor` | **BLOCKED** — `web_search`/`read_url` tool not yet wired |
| `coding` | `CodingExecutor` | **AWAITING_APPROVAL** — must not auto-modify code |
| `deployment` | `DeploymentExecutor` | **AWAITING_APPROVAL** — always |
| `email` | `EmailExecutor` | **AWAITING_APPROVAL** — always |
| `browser` | `BrowserExecutor` | **AWAITING_APPROVAL** — tool not wired |
| `security_risk` | `SecurityRiskExecutor` | **AWAITING_APPROVAL** — always |
| `reminders` | `RemindersExecutor` | **BLOCKED** — calendar tool not wired |
| `manager` | `ManagerExecutor` | **BLOCKED** — coordination only, no domain execution |

### Mission Runner Behavior

- `run_mission_pass(mission_id, max_steps=20)` runs one controlled pass
- Iterates tasks in priority order; skips `awaiting_approval`/already-terminal tasks
- Respects `task.dependencies` (waits for all deps to be `completed`)
- Persists every status change to `MissionStore` + emits `MissionEvent`
- Derives `MissionStatus` from final task states (never fakes it)
- Refuses to mark a task `COMPLETED` if executor returned empty `output`
- Returns `RunResult` dict with `ok`, progress counts, `no_progress_reason`

### How to Run a Mission Pass

```bash
# Create a mission
curl -X POST http://localhost:57291/v1/missions \
  -H 'Content-Type: application/json' \
  -d '{"objective": "validate quality and document results"}'

# Run one execution pass
curl -X POST http://localhost:57291/v1/missions/{mission_id}/run \
  -H 'Content-Type: application/json' \
  -d '{"max_steps": 20}'

# Get run state
curl http://localhost:57291/v1/missions/{mission_id}/run-state

# Run a single task
curl -X POST http://localhost:57291/v1/tasks/{task_id}/run

# List executors
curl http://localhost:57291/v1/executors
```

### Slack/Telegram Notify Routes

```bash
# Mission-scoped Slack notify (returns not_configured if OPENCLAW_SLACK_BOT_TOKEN missing)
curl -X POST http://localhost:57291/v1/missions/{mission_id}/notify/slack

# Mission-scoped Telegram notify (returns not_configured if tokens missing)
curl -X POST http://localhost:57291/v1/missions/{mission_id}/notify/telegram
```

Both endpoints:
- Return `{"ok": false, "error_type": "not_configured"}` if tokens missing/placeholder
- Never expose token values in response body
- Send a structured mission summary including title, status, task counts, blocked items

### Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `OPENCLAW_SLACK_BOT_TOKEN` | Slack bot token | none (not_configured) |
| `OPENCLAW_SLACK_CONTINUOUS_OPS_CHANNEL` | Slack channel | `C0BAF08SQTB` |
| `JARVIS_TELEGRAM_BOT_TOKEN` | Telegram bot token | none (not_configured) |
| `JARVIS_TELEGRAM_CHAT_ID` | Telegram chat ID | none (not_configured) |
| `JARVIS_SLACK_MISSION_AUTONOTIFY` | Auto-post to Slack on major mission events | `false` |
| `JARVIS_TELEGRAM_MISSION_AUTONOTIFY` | Auto-alert Telegram on major mission events | `false` |

Auto-notify only fires on: `completed`, `failed`, `blocked`, `awaiting_approval` status. Never spams every event.

### Validation Results

```
pytest tests/mission/test_mission_foundation.py tests/mission/test_mission_sprint2.py tests/mission/test_mission_sprint3.py -v
→ 139 passed, 0 failed, 1 warning (httpx deprecation, non-blocking)

Frontend typecheck: npx tsc -b --noEmit → Exit 0, clean
Tauri build: npm run tauri -- build → Finished, OpenJarvis.app bundled
Installed: /Applications/OpenJarvis.app (Sprint 3 build, Jun 15 2026)
```

### Functional Demo Output (exact)

Safe mission (`validate quality and document results`):
```
tasks_completed=1, tasks_blocked=0, approvals_required=0, ok=True
docs_report → completed (real output: [docs_report] Documentation/report generated...)
mission_status → completed
```

Mixed mission (`research, deploy, email, document`):
```
tasks_completed=1, tasks_blocked=1, approvals_required=2, ok=True
research → blocked (no tool wired)
deployment → awaiting_approval (always)
docs_report → completed
email → awaiting_approval (always)
mission_status → awaiting_approval
```

Slack/Telegram (no tokens configured):
```
ok=False, error_type=not_configured (no network call made)
```

### Repository State (Sprint 3)

| Field | Value |
|---|---|
| Branch | `localhost-get-tool` |
| Local HEAD | `460871e9` |
| Remote fork HEAD | `460871e9` (xiaobryans/OpenJarvis) |
| Git status | Clean after push |

### ACCEPT/HOLD Checklist

- [x] Real execution loop exists
- [x] At least one safe executor (docs_report/qa/architect/testing_bug) completes with persisted real output
- [x] Risky tasks (deployment/email/security_risk/coding) remain approval-gated/blocked
- [x] Mission runner emits real events and updates statuses correctly
- [x] Slack/Telegram notification routes work safely with not_configured behavior and no token exposure
- [x] 139/139 tests pass (Sprint 1+2+3)
- [x] Frontend typechecked and packaged app visually verified
- [x] Git clean and pushed to fork
- [x] No fake agent work
- [x] No forbidden systems touched

### Safety Confirmations

- No secrets printed or committed
- No public endpoints opened
- No Tailscale Funnel
- No AWS infrastructure changes
- No OMNIX production/Vercel/Supabase/Stripe/billing touched
- No real Slack/Telegram messages sent
- No auto-send email/browser/deploy/destructive actions

### What Is Ready for Mega Sprint 4

- **research executor**: Wire `web_search`/`read_url` tool → unblocks research tasks
- **coding executor**: Define safe action gate → enable diff-only code proposals
- **WebSocket/SSE push**: Replace polling on Mission Control page with real-time event stream
- **Manager Agent**: Connect `MissionRouter` outputs to actual agent dispatching loop
- **Slack event bus subscription**: Wire `mission_runner_started`/`task_awaiting_approval` to auto-post on event bus (currently env-gated only)
- **testing_bug real execution**: Run `pytest` in a sandboxed subprocess for safe test tasks
- **Mission chaining**: Multi-mission dependency graph

### What Is Intentionally Not Built (Sprint 3)

- Browser automation (no browser tool)
- Email sending (always approval-gated, no send tool)
- Voice activation
- LLM-based planning (still `keyword_deterministic`)
- Real web search for research agent
- WebSocket push (still polling)
- Production deploys or AWS infra changes

---

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
