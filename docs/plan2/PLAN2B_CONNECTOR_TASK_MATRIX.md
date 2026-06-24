# Plan 2B — Connector / Task Parity Foundation
## Source-of-Truth Matrix

**Parent plan:** Plan 2 — Full Mobile MacBook-Off Parity Runtime  
**Sprint:** Plan 2B Foundation  
**Sprint verdict target:** `PLAN_2B_CONNECTOR_TASK_PARITY_FOUNDATION_PATCHED_PENDING_REVIEW`  
**Based on:** Plan 2A corrective commit `d82943b1`  
**Machine-readable artifact:** `docs/plan2/plan2b_matrix.json`  
**Public runtime endpoint:** `GET /v1/mobile-parity/connectors`  
**Authenticated detail endpoint:** `GET /v1/mobile-parity/connectors/detail`

---

## Token Storage Architecture

| Connector | Token Storage | Location | Cloud-Safe | Vault-Backed |
|-----------|--------------|----------|------------|-------------|
| Gmail | OAuth 2.0 JSON file | `~/.openjarvis/connectors/gmail.json` | No | No |
| Google Calendar | OAuth 2.0 JSON file | `~/.openjarvis/connectors/gcalendar.json` | No | No |
| Google Drive | OAuth 2.0 JSON file | `~/.openjarvis/connectors/gdrive.json` | No | No |
| GitHub | Env var (`GITHUB_TOKEN`) | Process environment | Yes (if on Fargate) | No |
| Slack | Env var + optional file | Process env / `~/.openjarvis/connectors/slack.json` | Yes (if on Fargate) | No |
| Notion | Integration token file | `~/.openjarvis/connectors/notion.json` | No | No |
| Telegram | Env var (`TELEGRAM_BOT_TOKEN`) | Process environment | Yes (if on Fargate) | No |

**Critical finding:** Google OAuth tokens (Gmail, Calendar, Drive) are stored as local JSON files. Fargate cannot access local filesystem paths. These connectors are `LOCAL_ONLY` / `MACBOOK_OFF_PENDING` until a cloud vault migration is implemented.

---

## Per-Connector Parity Matrix

### Gmail

| Field | Value |
|-------|-------|
| Provider | Google |
| Token type | OAuth 2.0 (local JSON) |
| Desktop status | `READY` |
| Mobile status | `LOCAL_ONLY` |
| MacBook-off status | `MACBOOK_OFF_PENDING` |
| Locally connected | Yes |
| Approval required | For email_archive (read-only otherwise) |
| Outbound send | No (read-only) |
| **Exact blocker** | Google OAuth token in `~/.openjarvis/connectors/gmail.json` — inaccessible from Fargate |
| **Next step** | Migrate Google OAuth token to AWS Secrets Manager; load from vault on Fargate startup |
| **Proof for acceptance** | GET Gmail data from iPhone while MacBook is off |

### Google Calendar

| Field | Value |
|-------|-------|
| Provider | Google |
| Token type | OAuth 2.0 (local JSON, shared with Gmail) |
| Desktop status | `READY` |
| Mobile status | `LOCAL_ONLY` |
| MacBook-off status | `MACBOOK_OFF_PENDING` |
| Locally connected | Yes |
| **Exact blocker** | Same as Gmail — shared Google OAuth token in local file |
| **Next step** | Same vault migration as Gmail (single Google OAuth flow covers all Google connectors) |

### Google Drive

| Field | Value |
|-------|-------|
| Provider | Google |
| Token type | OAuth 2.0 (local JSON, shared with Gmail) |
| Desktop status | `READY` |
| Mobile status | `LOCAL_ONLY` |
| MacBook-off status | `MACBOOK_OFF_PENDING` |
| Locally connected | Yes |
| **Exact blocker** | Same as Gmail — shared Google OAuth token in local file |
| **Next step** | Same vault migration as Gmail |

### GitHub

| Field | Value |
|-------|-------|
| Provider | GitHub |
| Token type | Personal access token (env var `GITHUB_TOKEN`) |
| Desktop status | `READY` |
| Mobile status | `CLOUD_REQUIRED` |
| MacBook-off status | `CLOUD_REQUIRED` |
| Locally connected | Yes |
| Approval required | For git_push, PR creation, merge |
| Cloud-safe | Yes — env var, deployable to Fargate |
| **Exact blocker** | `GITHUB_TOKEN` not deployed to Fargate task definition |
| **Next step** | Add `GITHUB_TOKEN` to Fargate task env or AWS Secrets Manager |
| **Proof for acceptance** | GET GitHub repo data from iPhone while MacBook is off |

### Slack

| Field | Value |
|-------|-------|
| Provider | Slack |
| Token type | Bot token (env vars) + user token (local file) |
| Desktop status | `READY` |
| Mobile status | `CLOUD_REQUIRED` |
| MacBook-off status | `CLOUD_REQUIRED` |
| Locally connected | Yes |
| Outbound send | Yes — approval-gated always |
| Approval required | For all message sends |
| Cloud-safe | Yes (env vars deployable to Fargate) |
| **Exact blocker** | Slack bot token env vars not deployed to Fargate; outbound send not wired through approval gate for mobile trigger |
| **Next step** | Deploy Slack bot token to Fargate; wire send through approval gate with mobile confirmation flow |
| **Proof for acceptance** | Mobile-triggered Slack message via approval gate; Slack message sent after Bryan approves |

### Notion

| Field | Value |
|-------|-------|
| Provider | Notion |
| Token type | Internal integration token (local file) |
| Desktop status | `NOT_CONFIGURED` |
| Mobile status | `NOT_CONFIGURED` |
| MacBook-off status | `NOT_CONFIGURED` |
| Locally connected | No (`notion.json` absent) |
| **Exact blocker** | No Notion integration token created — manual setup required at notion.so/my-integrations |
| **Next step** | Create Notion integration, paste token via `/v1/connectors/notion/connect` |

### Telegram

| Field | Value |
|-------|-------|
| Provider | Telegram |
| Token type | Bot token (env var `TELEGRAM_BOT_TOKEN`) |
| Desktop status | `DEGRADED` |
| Mobile status | `CLOUD_REQUIRED` |
| MacBook-off status | `CLOUD_REQUIRED` |
| Locally connected | Yes (token present) |
| Outbound send | Yes — approval-gated always |
| Approval required | For all message sends |
| Cloud-safe | Yes (env var deployable to Fargate) |
| **Exact blocker** | `TELEGRAM_BOT_TOKEN` present but connector diagnostics use `JARVIS_TELEGRAM_BOT_TOKEN` — var name mismatch. No auto-trigger on approval events. |
| **Next step** | Resolve var name mismatch; wire auto-trigger on new pending approval queued; deploy to Fargate |
| **Proof for acceptance** | New approval queued → Telegram notification sent → Bryan approves/denies from iPhone |

### Workbench / Coding Task Queue

| Field | Value |
|-------|-------|
| Provider | Internal |
| Token type | Bearer API key |
| Desktop status | `READY` |
| Mobile status | `CLOUD_REQUIRED` |
| MacBook-off status | `MACBOOK_OFF_PENDING` |
| Approval required | For execute_with_side_effects, git_push, terminal_exec |
| **Exact blocker** | Mac worker queue runs only when MacBook is online; no Fargate worker process; no push notification for completion |
| **Next step** | Deploy Fargate worker; wire completion notifications |

---

## Task Action Classification

| Class | Description | Mobile-Safe | MacBook-Off Safe |
|-------|-------------|-------------|-----------------|
| `READONLY` | Safe read ops, no approval needed | Yes | Yes |
| `APPROVAL_REQUIRED` | Any outbound send, write, state change | Yes | Yes |
| `DESTRUCTIVE_GATED` | Hard-gated ops (hard gate, Bryan explicit) | No | No |
| `MAC_REQUIRED` | MacBook + local toolchain (Tauri, keychain) | No | No |
| `CLOUD_SAFE` | Runs on Fargate, no local deps | Yes | Yes |
| `CONNECTOR_GATED` | Requires connector OAuth in execution context | Yes (local) | No (vault needed) |

All action-capable routes remain approval-gated through Jarvis PA. No unsafe remote execution added.

---

## Plan 2B Foundation Sprint — What Was Patched

1. **`GET /v1/mobile-parity/connectors`** — public (no auth), coarse per-connector mobile/MacBook-off status. No token presence, no env var names, no paths.
2. **`GET /v1/mobile-parity/connectors/detail`** — auth-gated, presence-only diagnostics per connector. No secret values.
3. **`docs/plan2/PLAN2B_CONNECTOR_TASK_MATRIX.md`** — this document.
4. **`docs/plan2/plan2b_matrix.json`** — machine-readable matrix artifact.

---

## MacBook-Off Summary

| Connector | MacBook-Off Status |
|-----------|-------------------|
| Gmail | `MACBOOK_OFF_PENDING` |
| Google Calendar | `MACBOOK_OFF_PENDING` |
| Google Drive | `MACBOOK_OFF_PENDING` |
| GitHub | `CLOUD_REQUIRED` |
| Slack | `CLOUD_REQUIRED` |
| Notion | `NOT_CONFIGURED` |
| Telegram | `CLOUD_REQUIRED` |
| Workbench Queue | `MACBOOK_OFF_PENDING` |

**Global blocker:** Google OAuth tokens (Gmail, Calendar, Drive) stored in local JSON files — Fargate cannot access them. No cloud vault integration implemented. Zero connectors are `READY` on MacBook-off.

---

## What Was NOT Done (Plan 2B Is Foundation Only)

- Did not implement cloud vault migration for Google OAuth tokens
- Did not deploy connector tokens to Fargate task definition
- Did not wire Slack/Telegram outbound send through mobile approval flow
- Did not implement auto-trigger for approval notifications
- Did not configure Notion integration
- Did not claim any connector is READY on MacBook-off
- Did not start Plan 2C
- Did not start Plan 3 voice/wake/TTS
