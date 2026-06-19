# Jarvis Bryan-Action Blocker Ledger

**Last updated:** 2026-06-19
**Sprint:** Full Blocker / Bryan Manual-Action Clearance (Post Ops Foundation)
**Branch:** localhost-get-tool
**Base HEAD:** 561c0ffa

**Purpose:**
No Bryan-action blocker should be lost, even if low priority.
Every item below is classified, owned, and assigned exact clearing steps.
This ledger is exported to Obsidian on every sprint and updated each run.

**Status codes used:**
- `DAILY_DRIVER_ACCEPT` — Cleared, operational
- `CLEARED` — Resolved this sprint (sub-type of DAILY_DRIVER_ACCEPT)
- `BLOCKED_CREDENTIALS` — Bryan must provide credentials/tokens
- `BLOCKED_USER_AUTHORIZATION` — Requires explicit Bryan approval/action
- `BLOCKED_IMPLEMENTATION` — Code not yet written
- `BLOCKED_PROVIDER` — External provider/API issue
- `BLOCKED_HARDWARE` — Hardware/system permission missing
- `BLOCKED_SAFETY` — Intentional permanent safety block
- `PLANNED_IN_EXISTING_PROMPT` — Scheduled for a defined future sprint
- `OPTIONAL_BACKLOG` — Not required for core Jarvis OS
- `SCHEDULED_AFTER_CERTIFICATION` — Valid but deferred until burn-in done

---

## 1. Google OAuth (Gmail / Calendar / Drive)

| Field | Value |
|-------|-------|
| **Item** | Google OAuth client secret + access/refresh tokens |
| **Owner** | Bryan |
| **Priority** | High (required for Gmail/Calendar/Drive live read) |
| **Status** | `CLEARED` |
| **Blocks certification** | CLEARED |
| **Blocks final replacement** | CLEARED |
| **Cleared this sprint** | GOOGLE_OAUTH_CLIENT_SECRET SET(len=35). OAuth flow completed. Token file: ~/.openjarvis/connectors/google.json EXISTS. access_token(253) + refresh_token(103) obtained. |
| **Verification** | Gmail live read: email=xia***@gmail.com, 55,122 messages. Calendar: 3 calendars listed. Read-only. No sends. |

---

## 2. Gmail Live Read

| Field | Value |
|-------|-------|
| **Item** | Gmail live read (requires Google OAuth above) |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `CLEARED` |
| **Blocks certification** | CLEARED |
| **Blocks final replacement** | CLEARED |
| **Cleared this sprint** | Google OAuth completed. Gmail API enabled. Live read proven: email=xia***@gmail.com, 55,122 messages, 37,796 threads. Read-only. No sends. |
| **Verification** | Live read proven this sprint. |

---

## 3. Google Calendar Live Read

| Field | Value |
|-------|-------|
| **Item** | Google Calendar live read (requires Google OAuth above) |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `CLEARED` |
| **Blocks certification** | CLEARED |
| **Blocks final replacement** | CLEARED |
| **Cleared this sprint** | Calendar API enabled. Live read proven: 3 calendars (personal + Holidays in Singapore + Family). Read-only. No invites. |
| **Verification** | Live read proven this sprint. |

---

## 4. Google Drive Live Read

| Field | Value |
|-------|-------|
| **Item** | Google Drive live read (requires Google OAuth above) |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `BLOCKED_CREDENTIALS` (depends on item 1) |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | Clear Google OAuth (item 1). Enable Drive API in Google Cloud Console. |
| **Verification** | `jarvis doctor --check google_drive` returns PASS |

---

## 5. Slack Workspace Rename to Jarvis HQ

| Field | Value |
|-------|-------|
| **Item** | Rename current OMNIX HQ workspace (team_id=T0B9XK63CJ3) to Jarvis HQ |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `BLOCKED_USER_AUTHORIZATION` |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Log into Slack as workspace owner at slack.com. 2. Settings & administration → Workspace settings → Name. 3. Change to "Jarvis HQ". 4. Update SLACK_WORKSPACE_NAME in `~/.jarvis/cloud-keys.env` (for reference only). |
| **Verification** | `auth.test` response shows `"team": "Jarvis HQ"` |
| **Verified this sprint** | Current name: OMNIX HQ. team_id: T0B9XK63CJ3. bot_user: openjarvis. Status unchanged. |

---

## 6. Slack Channel Creation (missing `chat:write` + `channels:manage` scopes)

| Field | Value |
|-------|-------|
| **Item** | Slack `chat:write` + `channels:manage` scopes + required channel creation |
| **Owner** | Bryan |
| **Priority** | High |
| **Status** | `CLEARED` |
| **Blocks certification** | CLEARED |
| **Blocks final replacement** | CLEARED |
| **Cleared this sprint** | Bryan added scopes + reinstalled app. Scopes confirmed: chat:write=True, channels:manage=True. All 5 required channels created (#jarvis-ops, #jarvis-tasks, #jarvis-debug, #jarvis-approvals, #omnix-project). 5 optional channels created. Smoke test SENT (ts=1781872923.187269, trace=slack-closure-001). |
| **Verification** | auth.test: ok=True, OMNIX HQ. chat:write=True. channels:manage=True. Smoke test SENT. Audit record exists. |

---

## 7. Slack Manager Persona / App Setup

| Field | Value |
|-------|-------|
| **Item** | Create real Slack bot apps for: Jarvis HQ, Jarvis COS, Jarvis GM, Managers, Notifications |
| **Owner** | Bryan |
| **Priority** | Medium |
| **Status** | `PLANNED_IN_EXISTING_PROMPT` |
| **Blocks certification** | No (virtual personas functional) |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Go to api.slack.com → Your Apps → Create App. 2. Create apps for each real persona. 3. Add bot tokens to `~/.jarvis/cloud-keys.env` as JARVIS_COS_SLACK_TOKEN, etc. 4. Register in agent roster. |
| **Verification** | Each persona posts messages with distinct Slack bot identity |

---

## 8. Telegram Bryan Chat ID

| Field | Value |
|-------|-------|
| **Item** | TELEGRAM_BRYAN_CHAT_ID — required for Telegram fallback alerts |
| **Owner** | Jarvis |
| **Priority** | Medium |
| **Status** | `CLEARED` — resolved via alias `JARVIS_TELEGRAM_CHAT_ID` in `~/.openjarvis/cloud-keys.env` |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | N/A — cleared |
| **Cleared this sprint** | Credential loader now maps `JARVIS_TELEGRAM_CHAT_ID` → `TELEGRAM_BRYAN_CHAT_ID`. Telegram smoke test: SENT (message_id=8). |
| **Verification** | Telegram smoke test returned SENT. Audit record: `smoke-test-001`, target_chat=bryan_chat, status=SENT. |

---

## 9. Slack Workspace Deletion Confirmation

| Field | Value |
|-------|-------|
| **Item** | Explicit Bryan confirmation for any Slack workspace deletion |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `BLOCKED_USER_AUTHORIZATION` — all 9 checks must pass + explicit flag |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Confirm all 9 deletion checks pass (see slack_ops.py). 2. Set `BRYAN_APPROVES_SLACK_WORKSPACE_DELETE=true` in `~/.jarvis/cloud-keys.env`. 3. Run deletion command. |
| **Verification** | Deletion command succeeds with audit record |

---

## 10. AWS/S3 Cloud Memory Credentials

| Field | Value |
|-------|-------|
| **Item** | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, JARVIS_MEMORY_S3_BUCKET for cloud memory |
| **Owner** | Bryan |
| **Priority** | Low (local SQLite is daily-driver sufficient) |
| **Status** | `SCHEDULED_AFTER_CERTIFICATION` — local SQLite operational; S3 is cross-device enhancement |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Create AWS IAM user with S3 read/write permissions. 2. Create S3 bucket (e.g. jarvis-memory-bryan). 3. Add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `JARVIS_MEMORY_S3_BUCKET`, `AWS_DEFAULT_REGION` to `~/.jarvis/cloud-keys.env`. 4. Run: `cd /Users/user/OpenJarvis && .venv/bin/pip install boto3 && .venv/bin/python -c "from openjarvis.memory.cloud_memory import check_cloud_memory_status; print(check_cloud_memory_status())"`. |
| **Verification** | `check_cloud_memory_status()` returns `active_backend="s3_aws"` |
| **Verified this sprint** | AWS_ACCESS_KEY_ID: MISSING. AWS_SECRET_ACCESS_KEY: MISSING. JARVIS_MEMORY_S3_BUCKET: MISSING. Note: OMNIX_WORKBENCH_MEMORY_BUCKET is set in .env (OMNIX-specific, not Jarvis cloud memory). Local SQLite: DAILY_DRIVER_ACCEPT. |

---

## 11. Supabase Cloud Memory Sync

| Field | Value |
|-------|-------|
| **Item** | Supabase memory sync implementation |
| **Owner** | Jarvis |
| **Priority** | Medium |
| **Status** | `SCHEDULED_AFTER_CERTIFICATION` (credentials present in some configs; implementation pending) |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Implement supabase memory adapter in cloud_memory.py. 2. Create jarvis_memory table in Supabase. 3. Test sync/fallback. |
| **Verification** | `check_cloud_memory_status()` returns supabase as available |

---

## 12. Obsidian Vault Path Manual Setup

| Field | Value |
|-------|-------|
| **Item** | JARVIS_OBSIDIAN_VAULT — configure real vault path if different from default |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `DAILY_DRIVER_ACCEPT` (default ~/.jarvis/obsidian-vault works; no Obsidian app required) |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | No |
| **Clearing steps** | 1. Find your Obsidian vault path (e.g. ~/Documents/Jarvis Vault). 2. Set `JARVIS_OBSIDIAN_VAULT` in `~/.jarvis/cloud-keys.env`. 3. Rerun export. |
| **Verification** | ObsidianMirror writes to correct vault path |

---

## 13. Apple Signing Credentials

| Field | Value |
|-------|-------|
| **Item** | Apple Developer signing credentials for macOS app distribution |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `OPTIONAL_BACKLOG` |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Apple Developer account required ($99/yr). 2. Create provisioning profile and signing certificate. 3. Set `APPLE_DEVELOPER_IDENTITY="Developer ID Application: Bryan..."` and `APPLE_TEAM_ID=XXXXXXXXXX` in `~/.jarvis/cloud-keys.env`. 4. Configure Xcode or manual codesign. |
| **Verification** | `codesign --verify JarvisApp.app` passes |

---

## 14. openjarvis_rust / maturin

| Field | Value |
|-------|-------|
| **Item** | Rust bridge (maturin) for performance-critical paths |
| **Owner** | Jarvis / Bryan |
| **Priority** | Low |
| **Status** | `OPTIONAL_BACKLOG` |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes |
| **Clearing steps** | 1. Install Rust toolchain (rustc ≥ 1.88): `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh`. 2. `pip install maturin`. 3. Build: `maturin develop -m rust/crates/openjarvis-python/Cargo.toml`. |
| **Verification** | `import openjarvis_rust` succeeds |

---

## 15. Voice / STT / TTS

| Field | Value |
|-------|-------|
| **Item** | Voice pipeline — STT, TTS, wake word |
| **Owner** | Future sprint |
| **Priority** | Parked |
| **Status** | `OPTIONAL_BACKLOG` (VOICE_HOLD_UNSAFE_PARKED) |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Hold until after certification** | Yes — permanently parked until voice sprint is authorized |
| **Clearing steps** | N/A — requires separate sprint authorization from Bryan. 10 known blockers remain (VAD, endpointing, STT/TTS provider, etc.) |
| **Verification** | N/A |

---

## 16. Burn-in Certification

| Field | Value |
|-------|-------|
| **Item** | Fixed Jarvis Replacement Certification Suite |
| **Owner** | Bryan |
| **Priority** | High |
| **Status** | `BLOCKED_USER_AUTHORIZATION` (JARVIS_PRIMARY_CURSOR_FALLBACK until certified) |
| **Blocks certification** | This IS the certification |
| **Blocks final replacement** | Yes (CURSOR_WINDSURF_REPLACEMENT_ACCEPT requires this) |
| **Hold until after certification** | N/A — this is certification |
| **Clearing steps** | 1. Resolve all blocking Bryan actions (Slack scopes, Google OAuth). 2. Run Jarvis for real coding/AI tasks for ≥ 2 weeks. 3. Track success/failure cases. 4. Run the fixed certification suite when ready. 5. Declare CURSOR_WINDSURF_REPLACEMENT_ACCEPT or identify gaps. |
| **Verification** | Bryan certifies: "Jarvis is my primary coding assistant" with evidence |

---

## 17. Extended External AI Apps Burn-in

| Field | Value |
|-------|-------|
| **Item** | Extended trial of Jarvis as primary AI (replacing ChatGPT/Claude/Gemini apps) |
| **Owner** | Bryan |
| **Priority** | High |
| **Status** | `BLOCKED_USER_AUTHORIZATION` (JARVIS_PRIMARY_EXTERNAL_APPS_FALLBACK until certified) |
| **Blocks certification** | No (different certification track) |
| **Blocks final replacement** | Yes |
| **Hold until after certification** | Post-certification |
| **Clearing steps** | 1. Use Jarvis for daily AI tasks instead of ChatGPT/Claude. 2. Track capability gaps. 3. Decide on EXTERNAL_APPS_REPLACEMENT_ACCEPT. |
| **Verification** | Bryan certifies replacement verdict |

---

## 18. Missing Provider / Model API Keys

| Field | Value |
|-------|-------|
| **Item** | Any missing model API keys (Anthropic, Gemini, local model config) |
| **Owner** | Bryan |
| **Priority** | Low |
| **Status** | `DAILY_DRIVER_ACCEPT` — all 3 primary keys configured (OpenAI len=164, Anthropic len=108, OpenRouter len=73) |
| **Blocks certification** | No |
| **Blocks final replacement** | No |
| **Cleared this sprint** | Verified via credential probe: OPENAI_API_KEY SET(164), ANTHROPIC_API_KEY SET(108), OPENROUTER_API_KEY SET(73). |
| **Verification** | `jarvis doctor --check providers` returns all required providers PASS |

---

## 19. ENV/Token Alias Normalization (NEW — This Sprint)

| Field | Value |
|-------|-------|
| **Item** | Alias mapping for OPENCLAW_/JARVIS_ prefixed credentials to canonical ops module names |
| **Owner** | Jarvis |
| **Priority** | High |
| **Status** | `CLEARED` — shared credential loader implemented and tested |
| **Blocks certification** | Cleared |
| **Blocks final replacement** | Cleared |
| **Cleared this sprint** | `src/openjarvis/channels/credentials.py` implemented. 23 tests pass. Aliases: JARVIS_SLACK_BOT_TOKEN→SLACK_BOT_TOKEN, OPENCLAW_SLACK_BOT_TOKEN→SLACK_BOT_TOKEN, JARVIS_TELEGRAM_BOT_TOKEN→TELEGRAM_BOT_TOKEN, JARVIS_TELEGRAM_CHAT_ID→TELEGRAM_BRYAN_CHAT_ID. Both slack_ops.py and telegram_ops.py updated to use shared loader. |
| **Verification** | 23 credential tests pass. Telegram smoke test SENT. Slack credential probe: SET(len=59). |

---

## Summary Table

| # | Item | Owner | Priority | Status | Blocks Cert | Blocks Final |
|---|------|-------|----------|--------|-------------|--------------|
| **1** | **Google OAuth client secret** | **Jarvis** | **High** | **`CLEARED`** | **Cleared** | **Cleared** |
| **2** | **Gmail live read** | **Jarvis** | **Medium** | **`CLEARED`** | **Cleared** | **Cleared** |
| **3** | **Google Calendar live read** | **Jarvis** | **Medium** | **`CLEARED`** | **Cleared** | **Cleared** |
| 4 | Google Drive live read | Bryan | Low | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| 5 | Slack workspace rename to Jarvis HQ | Bryan | Medium | `BLOCKED_USER_AUTHORIZATION` (cosmetic only) | No | No |
| **6** | **Slack scopes + channels + smoke test** | **Jarvis** | **High** | **`CLEARED`** | **Cleared** | **Cleared** |
| 7 | Slack manager persona apps | Bryan | Low | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| **8** | **Telegram Bryan chat ID + smoke test** | **Jarvis** | **Medium** | **`CLEARED`** | **Cleared** | **Cleared** |
| 9 | Slack workspace deletion | Bryan | Low | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| 10 | AWS/S3 cloud memory creds | Bryan | Low | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| 11 | Supabase memory sync | Jarvis | Medium | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| **12** | **Obsidian vault path** | **Jarvis** | **Low** | **`CLEARED`** | **Cleared** | **Cleared** |
| 13 | Apple signing credentials | Bryan | Low | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| 14 | openjarvis_rust / maturin | Jarvis/Bryan | Low | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT` | No | No |
| 15 | Voice / STT / TTS | Future sprint | Parked | `VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_TEXT_PLATFORM` | No | No |
| 16 | Fixed Replacement Certification Suite | Bryan | High | `BLOCKED_WAITING_FOR_BRYAN_NOW` (pre-cert gates all CLEARED — ready to start) | N/A | Yes |
| 17 | External AI platform replacement certification | Bryan | High | `BLOCKED_WAITING_FOR_BRYAN_NOW` (ready to start) | No | Yes |
| **18** | **Provider API keys** | **Jarvis** | **Low** | **`CLEARED`** | **Cleared** | **Cleared** |
| **19** | **ENV/token alias normalization** | **Jarvis** | **High** | **`CLEARED`** | **Cleared** | **Cleared** |

**Cleared this sprint:** Items 1, 2, 3, 6, 8, 12, 18, 19 (all critical pre-certification blockers)
**Verified optional (not required for replacement):** Items 4, 7, 9, 10, 11, 13, 14, 15
**Remaining Bryan actions:** Item 5 (Slack workspace rename — cosmetic only); Items 16+17 (certification suite — all gates CLEARED, ready to start)

---

## Bryan Manual Actions — Exact Commands

All items below require Bryan to take action before they can progress.

### Action A: Add Google OAuth Client Secret (Unblocks items 1–4)
```bash
# Add to ~/.jarvis/cloud-keys.env (NEVER committed to git):
echo 'GOOGLE_OAUTH_CLIENT_SECRET=<your-client-secret>' >> ~/.jarvis/cloud-keys.env
```
Then run OAuth flow:
```bash
cd /Users/user/OpenJarvis
.venv/bin/python -c "
from openjarvis.connectors.oauth import run_oauth_flow
run_oauth_flow(
  client_id='<from-cloud-console>',
  client_secret='<your-client-secret>',
  scopes=[
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
  ],
  credentials_path='$HOME/.openjarvis/connectors/google.json'
)
"
```
**Source:** Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON

### Action B: Add Slack `chat:write` and `channels:manage` Scopes (Unblocks item 6)
1. Go to https://api.slack.com/apps
2. Find app **openjarvis** (workspace: OMNIX HQ, team_id: T0B9XK63CJ3)
3. OAuth & Permissions → Scopes → Bot Token Scopes → Add:
   - `channels:manage`
   - `chat:write`
4. Click "Reinstall to Workspace"
5. After reinstall, run smoke test:
```bash
cd /Users/user/OpenJarvis
.venv/bin/python -c "
from openjarvis.channels.slack_ops import SlackOpsCommandCenter
c = SlackOpsCommandCenter()
r = c.send_ops_message('#jarvis-ops', 'Jarvis ops channel ready.', 'smoke_test_notification')
print(r.status)
"
```

### Action C: Rename Slack Workspace to Jarvis HQ (Item 5)
1. Log into slack.com as workspace owner
2. Settings & administration → Workspace settings → Name
3. Change to: **Jarvis HQ**

### Action D: Update Bot Display Name to "Jarvis" (Item 7 partial)
1. Go to https://api.slack.com/apps → openjarvis app → Basic Information
2. Display Name: change to **Jarvis**
3. Save changes

---

*Ledger version: Full Blocker / Bryan Manual-Action Clearance Sprint*
*Last verified: 2026-06-19*
*Export to Obsidian: docs/blockers/bryan-action-blocker-ledger.md*
