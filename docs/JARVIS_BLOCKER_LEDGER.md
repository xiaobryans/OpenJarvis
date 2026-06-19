# Jarvis Bryan-Action Blocker Ledger

**Last updated:** 2026-06-19
**Sprint:** Cloud Memory / Obsidian / Cache / Slack-Telegram Ops / Agent Roster
**Branch:** localhost-get-tool
**Base HEAD:** 19bcf3b2

**Purpose:**
No Bryan-action blocker should be lost, even if low priority.
Every item below is classified, owned, and assigned exact clearing steps.
This ledger is exported to Obsidian on every sprint and updated each run.

**Status codes used:**
- `DAILY_DRIVER_ACCEPT` — Cleared, operational
- `BLOCKED_CREDENTIALS` — Bryan must provide credentials/tokens
- `BLOCKED_USER_AUTHORIZATION` — Requires explicit Bryan approval/action
- `BLOCKED_IMPLEMENTATION` — Code not yet written
- `BLOCKED_PROVIDER` — External provider/API issue
- `BLOCKED_HARDWARE` — Hardware/system permission missing
- `PLANNED_IN_EXISTING_PROMPT` — Scheduled for a defined future sprint
- `OPTIONAL_BACKLOG` — Not required for core Jarvis OS

---

## 1. Google OAuth (Gmail / Calendar / Drive)

| Field | Value |
|-------|-------|
| **Item** | Google OAuth client secret + access/refresh tokens |
| **Owner** | Bryan |
| **Priority** | High (required for Gmail/Calendar/Drive live read) |
| **Status** | `BLOCKED_CREDENTIALS` |
| **Blocks current sprint** | No |
| **Blocks final replacement** | Yes (Gmail/Calendar live read) |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Go to Google Cloud Console → APIs & Services → Credentials. 2. Create OAuth 2.0 Client ID (Desktop). 3. Download client_secret.json. 4. Run: `jarvis auth google` or manually run OAuth flow. 5. Set GOOGLE_CLIENT_SECRET_PATH and GOOGLE_TOKEN_PATH in .env. |
| **Verification** | `jarvis doctor --check google_oauth` returns PASS |

---

## 2. Gmail Live Read

| Field | Value |
|-------|-------|
| **Item** | Gmail live read (requires Google OAuth above) |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `BLOCKED_CREDENTIALS` (depends on item 1) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | Yes |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | Clear Google OAuth (item 1) first. Then enable Gmail API in Google Cloud Console. |
| **Verification** | `jarvis doctor --check gmail` returns PASS |

---

## 3. Google Calendar Live Read

| Field | Value |
|-------|-------|
| **Item** | Google Calendar live read (requires Google OAuth above) |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `BLOCKED_CREDENTIALS` (depends on item 1) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | Yes |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | Clear Google OAuth (item 1). Enable Calendar API in Google Cloud Console. |
| **Verification** | `jarvis doctor --check google_calendar` returns PASS |

---

## 4. Google Drive Live Read

| Field | Value |
|-------|-------|
| **Item** | Google Drive live read (requires Google OAuth above) |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `BLOCKED_CREDENTIALS` (depends on item 1) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | Clear Google OAuth (item 1). Enable Drive API in Google Cloud Console. |
| **Verification** | `jarvis doctor --check google_drive` returns PASS |

---

## 5. Slack Workspace Rename to Jarvis HQ

| Field | Value |
|-------|-------|
| **Item** | Rename current OMNIX HQ workspace to Jarvis HQ |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `BLOCKED_USER_AUTHORIZATION` |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Log into Slack as workspace owner. 2. Settings → Workspace Settings → Name. 3. Change to "Jarvis HQ". 4. Update SLACK_WORKSPACE_NAME in .env. |
| **Verification** | Slack workspace name = "Jarvis HQ" |

---

## 6. Slack Channel Creation/Cleanup

| Field | Value |
|-------|-------|
| **Item** | Create required Jarvis channels (#jarvis-ops, #jarvis-tasks, #jarvis-debug, #jarvis-approvals, #omnix-project) |
| **Owner** | Jarvis (bot token) / Bryan (if missing scopes) |
| **Priority** | High |
| **Status** | `BLOCKED_CREDENTIALS` — requires SLACK_BOT_TOKEN with channels:manage scope |
| **Blocks current sprint** | Partial (smoke test can use existing channels) |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | No |
| **Clearing steps** | 1. Verify SLACK_BOT_TOKEN is set. 2. Ensure bot has channels:manage scope (reinstall app if needed). 3. Run: `jarvis slack create-required-channels`. |
| **Verification** | All 5 required channels exist in workspace |

---

## 7. Slack Manager Persona / App Setup

| Field | Value |
|-------|-------|
| **Item** | Create real Slack bot apps for: Jarvis HQ, Jarvis COS, Jarvis GM, Managers, Notifications |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `PLANNED_IN_EXISTING_PROMPT` |
| **Blocks current sprint** | No (virtual personas functional) |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Go to api.slack.com → Your Apps → Create App. 2. Create apps for each real persona. 3. Add bot tokens to .env as JARVIS_COS_SLACK_TOKEN, etc. 4. Register in agent roster. |
| **Verification** | Each persona posts messages with distinct Slack bot identity |

---

## 8. Telegram Bryan Chat ID

| Field | Value |
|-------|-------|
| **Item** | TELEGRAM_BRYAN_CHAT_ID — required for Telegram fallback alerts |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `BLOCKED_USER_AUTHORIZATION` |
| **Blocks current sprint** | Yes (Telegram smoke test remains BLOCKED_USER_AUTHORIZATION without it) |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | No |
| **Clearing steps** | 1. Ensure TELEGRAM_BOT_TOKEN is set. 2. Send any message to the Jarvis bot from Bryan's Telegram. 3. Call: https://api.telegram.org/bot<TOKEN>/getUpdates. 4. Find chat.id in response. 5. Set TELEGRAM_BRYAN_CHAT_ID=<id> in .env. |
| **Verification** | `jarvis telegram smoke-test` returns SENT |

---

## 9. Slack Workspace Deletion Confirmation

| Field | Value |
|-------|-------|
| **Item** | Explicit Bryan confirmation for any Slack workspace deletion |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `BLOCKED_USER_AUTHORIZATION` — all 9 checks must pass + explicit flag |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Confirm all 9 deletion checks pass (see slack_ops.py). 2. Set BRYAN_APPROVES_SLACK_WORKSPACE_DELETE=true in .env. 3. Run deletion command. |
| **Verification** | Deletion command succeeds with audit record |

---

## 10. AWS/S3 Cloud Memory Credentials

| Field | Value |
|-------|-------|
| **Item** | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, JARVIS_MEMORY_S3_BUCKET for cloud memory |
| **Owner** | Bryan |
| **Priority** | High (cloud memory source of truth) |
| **Status** | `BLOCKED_CREDENTIALS` |
| **Blocks current sprint** | No (local SQLite fallback is operational) |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Create AWS IAM user with S3 read/write permissions. 2. Create S3 bucket (e.g. jarvis-memory-bryan). 3. Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, JARVIS_MEMORY_S3_BUCKET, AWS_DEFAULT_REGION in .env. 4. Install: pip install boto3. 5. Run: `jarvis doctor --check cloud_memory`. |
| **Verification** | `check_cloud_memory_status()` returns active_backend="s3_aws" |

---

## 11. Supabase Cloud Memory Sync

| Field | Value |
|-------|-------|
| **Item** | Supabase memory sync implementation |
| **Owner** | Jarvis |
| **Priority** | Medium |
| **Status** | `PLANNED_IN_EXISTING_PROMPT` (credentials present in some configs; implementation pending) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Implement supabase memory adapter in cloud_memory.py. 2. Create jarvis_memory table in Supabase. 3. Test sync/fallback. |
| **Verification** | check_cloud_memory_status() returns supabase as available |

---

## 12. Obsidian Vault Path Manual Setup

| Field | Value |
|-------|-------|
| **Item** | JARVIS_OBSIDIAN_VAULT — configure real vault path if different from default |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `DAILY_DRIVER_ACCEPT` (default ~/.jarvis/obsidian-vault works; no Obsidian app required) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | No |
| **Clearing steps** | 1. Find your Obsidian vault path (e.g. ~/Documents/Jarvis Vault). 2. Set JARVIS_OBSIDIAN_VAULT in .env. 3. Rerun export. |
| **Verification** | ObsidianMirror writes to correct vault path |

---

## 13. Apple Signing Credentials

| Field | Value |
|-------|-------|
| **Item** | Apple Developer signing credentials for macOS app distribution |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `OPTIONAL_BACKLOG` |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Apple Developer account required ($99/yr). 2. Create provisioning profile and signing certificate. 3. Configure Xcode or manual codesign. |
| **Verification** | `codesign --verify JarvisApp.app` passes |

---

## 14. openjarvis_rust / maturin

| Field | Value |
|-------|-------|
| **Item** | Rust bridge (maturin) for performance-critical paths |
| **Owner** | Jarvis / Bryan |
| **Priority** | Low |
| **Status** | `OPTIONAL_BACKLOG` |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Install Rust toolchain. 2. `pip install maturin`. 3. Build: `maturin develop`. |
| **Verification** | `import openjarvis_rust` succeeds |

---

## 15. Voice / STT / TTS

| Field | Value |
|-------|-------|
| **Item** | Voice pipeline — STT, TTS, wake word |
| **Owner** | Future sprint |
| **Priority** | Parked |
| **Status** | `OPTIONAL_BACKLOG` (VOICE_HOLD_UNSAFE_PARKED) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes — permanently parked until voice sprint is authorized |
| **Clearing steps** | N/A — requires separate sprint authorization from Bryan |
| **Verification** | N/A |

---

## 16. Burn-in Certification

| Field | Value |
|-------|-------|
| **Item** | Extended Cursor/Windsurf coding trial and burn-in certification |
| **Owner** | Bryan |
| **Priority** | High |
| **Status** | `BLOCKED_USER_AUTHORIZATION` (JARVIS_PRIMARY_CURSOR_FALLBACK until certified) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | Yes (CURSOR_WINDSURF_REPLACEMENT_ACCEPT requires this) |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Run Jarvis for coding tasks daily for ≥2 weeks. 2. Document success/failure cases. 3. Decide on CURSOR_WINDSURF_REPLACEMENT_ACCEPT. |
| **Verification** | Bryan certifies: "Jarvis is my primary coding assistant" |

---

## 17. Extended External AI Apps Burn-in

| Field | Value |
|-------|-------|
| **Item** | Extended trial of Jarvis as primary AI (replacing ChatGPT/Claude/Gemini apps) |
| **Owner** | Bryan |
| **Priority** | High |
| **Status** | `BLOCKED_USER_AUTHORIZATION` (JARVIS_PRIMARY_EXTERNAL_APPS_FALLBACK until certified) |
| **Blocks current sprint** | No |
| **Blocks final replacement** | Yes |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Use Jarvis for daily AI tasks instead of ChatGPT/Claude. 2. Track capability gaps. 3. Decide on EXTERNAL_APPS_REPLACEMENT_ACCEPT. |
| **Verification** | Bryan certifies replacement verdict |

---

## 18. Missing Provider / Model API Keys

| Field | Value |
|-------|-------|
| **Item** | Any missing model API keys (Anthropic, Gemini, local model config) |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `BLOCKED_CREDENTIALS` (per-provider; varies) |
| **Blocks current sprint** | No (OpenRouter currently covers primary routing) |
| **Blocks final replacement** | No |
| **Hold until after this sprint** | Yes |
| **Clearing steps** | 1. Check `jarvis doctor` for missing provider keys. 2. Add missing keys to .env. |
| **Verification** | `jarvis doctor --check providers` returns all required providers PASS |

---

## Summary Table

| # | Item | Owner | Priority | Status | Blocks Sprint | Blocks Final |
|---|------|-------|----------|--------|---------------|--------------|
| 1 | Google OAuth client secret | Bryan | High | `BLOCKED_CREDENTIALS` | No | Yes |
| 2 | Gmail live read | Bryan | Medium | `BLOCKED_CREDENTIALS` | No | Yes |
| 3 | Google Calendar live read | Bryan | Medium | `BLOCKED_CREDENTIALS` | No | Yes |
| 4 | Google Drive live read | Bryan | Low | `BLOCKED_CREDENTIALS` | No | No |
| 5 | Slack workspace rename | Bryan | Medium | `BLOCKED_USER_AUTHORIZATION` | No | No |
| 6 | Slack channel creation | Jarvis/Bryan | High | `BLOCKED_CREDENTIALS` | Partial | No |
| 7 | Slack manager persona apps | Bryan | Medium | `PLANNED_IN_EXISTING_PROMPT` | No | No |
| 8 | Telegram Bryan chat ID | Bryan | Medium | `BLOCKED_USER_AUTHORIZATION` | Yes | No |
| 9 | Slack workspace deletion | Bryan | Low | `BLOCKED_USER_AUTHORIZATION` | No | No |
| 10 | AWS/S3 cloud memory creds | Bryan | High | `BLOCKED_CREDENTIALS` | No | No |
| 11 | Supabase memory sync | Jarvis | Medium | `PLANNED_IN_EXISTING_PROMPT` | No | No |
| 12 | Obsidian vault path | Bryan | Low | `DAILY_DRIVER_ACCEPT` | No | No |
| 13 | Apple signing credentials | Bryan | Low | `OPTIONAL_BACKLOG` | No | No |
| 14 | openjarvis_rust / maturin | Jarvis/Bryan | Low | `OPTIONAL_BACKLOG` | No | No |
| 15 | Voice / STT / TTS | Future sprint | Parked | `OPTIONAL_BACKLOG` | No | No |
| 16 | Burn-in certification | Bryan | High | `BLOCKED_USER_AUTHORIZATION` | No | Yes |
| 17 | External AI apps burn-in | Bryan | High | `BLOCKED_USER_AUTHORIZATION` | No | Yes |
| 18 | Missing provider API keys | Bryan | Medium | `BLOCKED_CREDENTIALS` | No | No |

---

*Ledger version: Cloud-Memory-Obsidian-Cache-Slack-Telegram-Roster sprint*
*Export to Obsidian: docs/blockers/bryan-action-blocker-ledger.md*
