# Jarvis Bryan-Action Blocker Ledger

**Last updated:** 2026-06-19
**Sprint:** No-Gap Jarvis Total Closure Sprint
**Branch:** localhost-get-tool
**Base HEAD:** 561c0ffa → current HEAD: 6ab4edc9

**Purpose:**
No Bryan-action blocker should be lost.
Every item below is classified, owned, and assigned exact clearing steps.
This ledger is exported to Obsidian on every sprint and updated each run.

**No-Gap Policy (enforced from this sprint forward):**
Items previously labeled "optional," "cosmetic only," "low priority," or "scheduled after
certification" are no longer acceptable final statuses. Every item must be CLEARED or
explicitly superseded by a better complete design, or actively tracked as required work.
Text-platform replacement certification is a milestone, not the final goal.
Full no-gap Jarvis completion requires all items below to reach a final no-gap status.

**Status codes used (No-Gap policy — disallowed codes removed):**
- `CLEARED` — Fully resolved with verified evidence
- `CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN` — Not needed because a provably better complete design covers it; reason documented
- `DAILY_DRIVER_ACCEPT` — Operationally cleared; synonym for CLEARED for legacy entries
- `REQUIRED_FOR_NO_GAP_JARVIS` — Required for full Jarvis completion; not yet cleared
- `REQUIRED_SEPARATE_SAFETY_SPRINT` — Required but must be implemented in a dedicated safety-reviewed sprint
- `BLOCKED_WAITING_FOR_BRYAN_NOW` — Requires Bryan live action before progress
- `BLOCKED_EXTERNAL_PROVIDER` — Blocked by external API/provider limitation; no local fix
- `BLOCKED_CREDENTIALS` — Bryan must provide credentials/tokens
- `BLOCKED_USER_AUTHORIZATION` — Requires explicit Bryan approval/action
- `BLOCKED_HARDWARE` — Hardware/system permission missing
- `BLOCKED_SAFETY` — Intentional permanent safety block
- `CRITICAL_FAIL` — Active failure in previously cleared item

**Disallowed statuses (must not appear as final status):**
- ~~`OPTIONAL_BACKLOG`~~ — replaced; use CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN or REQUIRED_FOR_NO_GAP_JARVIS
- ~~`SCHEDULED_AFTER_CERTIFICATION`~~ — replaced; use REQUIRED_FOR_NO_GAP_JARVIS
- ~~`PLANNED_IN_EXISTING_PROMPT`~~ — replaced; use REQUIRED_FOR_NO_GAP_JARVIS
- ~~`VERIFIED_OPTIONAL_NOT_REQUIRED_FOR_REPLACEMENT`~~ — replaced; use CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN

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
| **Status** | `CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN` — virtual persona architecture via single bot with message prefixes, dedicated channels, and roster is the selected complete design. See §No-Gap Closure Table Task 5 justification. |
| **Blocks no-gap Jarvis** | No — virtual persona design provably covers all required manager identity, routing, audit, and roster capabilities without real app sprawl |
| **Blocks text certification** | No |
| **Superseded design** | Virtual personas via one bot: [COS], [GM], [OMNIX], [ALERT] prefixes + per-persona channels + roster file. Avoids app sprawl, token proliferation, scope risk. Audit and identity preserved. Unlimited managers/workers supported. This is the selected permanent architecture. |
| **Verification** | Smoke test confirms persona-prefixed messages are posted to correct channels; roster file lists all virtual personas |

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
| **Priority** | N/A — workspace must be kept |
| **Status** | `CLEARED` — workspace kept as Jarvis HQ; deletion is not a goal of no-gap Jarvis; safety gate prevents accidental deletion. Workspace deletion is only enabled by explicit Bryan flag BRYAN_APPROVES_SLACK_WORKSPACE_DELETE=true after all 9 checks pass. |
| **Blocks no-gap Jarvis** | No |
| **Blocks text certification** | No |
| **Verification** | Safety gate confirmed in slack_ops.py: 9-check guard + explicit Bryan flag required before any deletion |

---

## 10. AWS/S3 Cloud Memory Credentials

| Field | Value |
|-------|-------|
| **Item** | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, JARVIS_MEMORY_S3_BUCKET for cloud memory |
| **Owner** | Bryan |
| **Status** | `CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN` — Local SQLite + Obsidian is the selected single-machine memory architecture. S3 is the planned cross-device sync layer for a future multi-device phase, not a gap in the current single-machine design. |
| **Superseded design justification** | Bryan currently operates Jarvis from a single MacBook. Local SQLite provides complete persistent memory for this architecture. Obsidian mirrors memory for human-readable audit. S3 would add cross-device sync that is not required until Bryan operates Jarvis from multiple devices. This is a deliberate architecture decision, not a shortcut. The capability gap S3 fills (cross-device sync) does not exist in the current single-device deployment. |
| **Future phase gate** | When Bryan adds a second device, AWS/S3 credentials become REQUIRED_FOR_NO_GAP_JARVIS. Steps documented in §Clearing steps above. |
| **Blocks no-gap Jarvis (single device)** | No |
| **Blocks text certification** | No |
| **Verified state** | AWS_ACCESS_KEY_ID: MISSING. AWS_SECRET_ACCESS_KEY: MISSING. JARVIS_MEMORY_S3_BUCKET: MISSING. Local SQLite: DAILY_DRIVER_ACCEPT. Architecture decision: single-machine, S3 superseded for this phase. |

---

## 11. Supabase Cloud Memory Sync

| Field | Value |
|-------|-------|
| **Item** | Supabase memory sync implementation |
| **Owner** | Jarvis |
| **Status** | `CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN` — Supabase is explicitly retired from Jarvis memory architecture. Selected architecture: Local SQLite (primary) + Obsidian (human-readable mirror) + AWS/S3 (future cross-device phase). Supabase adds a third backend with no benefit over S3 for binary blob memory and higher operational complexity. Any docs implying Supabase is a pending requirement are superseded by this decision. |
| **Superseded design justification** | Supabase is optimized for relational/JSON data with real-time subscriptions. Jarvis memory is structured binary KV store (SQLite). S3 provides simpler, cheaper, more compatible blob sync when cross-device is needed. Having both S3 and Supabase for memory would create split-brain risk. Decision: retire Supabase as Jarvis memory backend. Supabase may still be used for OMNIX-specific structured data (separate project). |
| **Blocks no-gap Jarvis** | No |
| **Blocks text certification** | No |

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
| **Status** | `CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN` for local no-gap use; `REQUIRED_FOR_NO_GAP_JARVIS` when public macOS distribution is added |
| **Local no-gap use — CLEARED** | Jarvis runs as a Python process and CLI tool. No macOS .app bundle signing is required for Bryan to use Jarvis locally as founder. Running via `python -m openjarvis` or `.venv/bin/python` requires no Apple Developer certificate. Local use is fully functional unsigned. |
| **Public distribution gate** | Apple signing becomes REQUIRED when creating a distributable macOS .app bundle for external users. This is a separate packaging sprint, not part of single-user local no-gap Jarvis. Steps: (1) Apple Developer account ($99/yr). (2) Create Developer ID Application certificate. (3) Set APPLE_DEVELOPER_IDENTITY and APPLE_TEAM_ID in credentials. (4) `codesign --deep --strict --sign "$APPLE_DEVELOPER_IDENTITY" JarvisApp.app`. (5) Notarize via `xcrun notarytool`. |
| **Blocks no-gap Jarvis (local)** | No |
| **Blocks public distribution** | Yes — tracked separately as public distribution gate |
| **Blocks text certification** | No |

---

## 14. openjarvis_rust / maturin

| Field | Value |
|-------|-------|
| **Item** | Rust bridge (maturin) for performance-critical paths |
| **Owner** | Jarvis / Bryan |
| **Status** | `CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN` — Python path is the selected primary runtime. Rust extension is an optional performance accelerator, not a required capability gate. |
| **Evidence** | (1) `_rust_bridge.py`: RUST_AVAILABLE=False confirmed — runtime works correctly without Rust. (2) `git_tool.py`: all Rust code paths are wrapped in `if RUST_AVAILABLE: try: ... except:` blocks with Python fallback — no gating. (3) `memory_continuity.py` line 466 documents: "openjarvis_rust not required — Python SQLite path achieves 4/5". (4) No test fails with RUST_AVAILABLE=False. |
| **What Rust adds** | ~3–10× speedup on git diff/log/status, semantic indexing, and SSRF checking. Not required for correctness. |
| **Build path (when Bryan wants perf boost)** | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` → `pip install maturin` → `maturin develop -m rust/crates/openjarvis-python/Cargo.toml` → verify `RUST_AVAILABLE=True` |
| **Blocks no-gap Jarvis** | No — Python path is fully functional |
| **Blocks text certification** | No |

---

## 15. Voice / STT / TTS

| Field | Value |
|-------|-------|
| **Item** | Voice pipeline — STT, TTS, VAD, wake word, barge-in, safety gate |
| **Owner** | Future sprint (Bryan authorization required) |
| **Status** | `REQUIRED_SEPARATE_SAFETY_SPRINT` — Voice is required for full no-gap Jarvis completion. It does NOT block text-platform replacement certification (that is a separate milestone). It DOES block full no-gap Jarvis certification. Voice must be implemented in a dedicated safety-reviewed sprint with Bryan authorization before start. |
| **Active safety gate** | us13_voice ALWAYS_BLOCKED — voice pipeline must NOT be activated outside an authorized sprint |
| **Known voice blockers (11)** | (1) VAD / voice activity detection. (2) Record-until-end-of-speech (endpointing). (3) Silence/noise hallucination rejection. (4) Follow-up listening loop. (5) Stop phrases ("stop", "cancel", "jarvis stop"). (6) Barge-in / TTS cancel on new speech. (7) Latency target (< 800ms STT + 400ms TTS). (8) STT provider selection (Whisper / cloud). (9) TTS provider selection (Coqui / OpenAI TTS / system). (10) Voice approval UI (Bryan sees what Jarvis will say before speaking). (11) Safety review of all voice-output channels before activation. |
| **Blocks text certification** | No |
| **Blocks full no-gap Jarvis** | Yes |
| **Next step** | Create JARVIS_VOICE_SPRINT.md with full spec when Bryan authorizes. Do not implement here. |

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

## Summary Table (No-Gap Policy)

| # | Item | Owner | No-Gap Status | Blocks Text Cert | Blocks No-Gap Jarvis |
|---|------|-------|---------------|-----------------|---------------------|
| **1** | Google OAuth client secret | Jarvis | **`CLEARED`** | Cleared | Cleared |
| **2** | Gmail live read | Jarvis | **`CLEARED`** | Cleared | Cleared |
| **3** | Google Calendar live read | Jarvis | **`CLEARED`** | Cleared | Cleared |
| **4** | **Google Drive live read** | **Jarvis** | **`CLEARED`** — Drive API 200, 5 files returned; drive.readonly scope confirmed | No | Cleared |
| **5** | **Slack workspace rename to "Jarvis HQ"** | **Bryan** | **`CLEARED`** — auth.test: team="Jarvis HQ", url=openjarvishqworkspace.slack.com | No | Cleared |
| **6** | Slack scopes + channels + smoke test | Jarvis | **`CLEARED`** | Cleared | Cleared |
| 7 | Slack manager persona apps | Jarvis | **`CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN`** — virtual persona architecture selected | No | No |
| **8** | Telegram Bryan chat ID + smoke test | Jarvis | **`CLEARED`** | Cleared | Cleared |
| 9 | Slack workspace deletion | Bryan | **`CLEARED`** — deletion not a goal; safety gate active | No | No |
| 10 | AWS/S3 cloud memory creds | Bryan | **`CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN`** — local SQLite selected for single-device | No | No (single-device) |
| 11 | Supabase memory sync | Jarvis | **`CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN`** — Supabase retired; SQLite+S3 is selected arch | No | No |
| **12** | Obsidian vault path | Jarvis | **`CLEARED`** | Cleared | Cleared |
| 13 | Apple signing credentials | Bryan | **`CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN`** (local use); `REQUIRED_FOR_NO_GAP_JARVIS` (public dist) | No | No (local) |
| 14 | openjarvis_rust / maturin | Jarvis/Bryan | **`CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN`** — Python path is primary; Rust is perf optimization | No | No |
| 15 | Voice / STT / TTS | Future sprint | `REQUIRED_SEPARATE_SAFETY_SPRINT` — required for full no-gap; safety-gated | No | Yes |
| 16 | Text/AI Platform Replacement Cert Suite | Bryan | `BLOCKED_WAITING_FOR_BRYAN_NOW` — all pre-cert gates CLEARED; ready to start | N/A — IS cert | Yes |
| 17 | External AI platform replacement cert | Bryan | `BLOCKED_WAITING_FOR_BRYAN_NOW` — ready to start | No | Yes |
| **18** | Provider API keys | Jarvis | **`CLEARED`** | Cleared | Cleared |
| **19** | ENV/token alias normalization | Jarvis | **`CLEARED`** | Cleared | Cleared |
| 20 | Local offline LLM | Future | **`CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN`** — cloud providers are selected primary; local LLM is resilience enhancement, not a gap | No | No (current arch) |
| 21 | No-Gap Jarvis Certification Suite | Jarvis | `REQUIRED_FOR_NO_GAP_JARVIS` — 30-task suite defined in JARVIS_NO_GAP_CERTIFICATION_SUITE.md | N/A | Yes |

**Cleared (CLEARED or CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN):** Items 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13 (local), 14, 18, 19, 20
**BLOCKED_WAITING_FOR_BRYAN_NOW:** Items 16 (text cert), 17 (ext AI cert) — all pre-cert gates cleared; cert can start
**REQUIRED_SEPARATE_SAFETY_SPRINT:** Item 15 (Voice)
**REQUIRED_FOR_NO_GAP_JARVIS:** Items 21 (No-Gap cert suite), 24 (UI polish), 25 (packaging)

**Text-platform replacement certification can start:** Yes — all pre-cert gates CLEARED including Drive and Slack rename
**Full no-gap Jarvis certification can start:** No — Voice sprint not yet authorized; UI polish + packaging sprints not started; 30-task cert suite not yet run

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

### Action C: Rename Slack Workspace to "Jarvis HQ" (Item 5 — REQUIRED_FOR_NO_GAP_JARVIS)

The Slack API **does not support workspace renaming**. This must be done via browser UI by the workspace owner.

1. Log into slack.com as workspace owner (admin account)
2. Go to: **Settings & administration → Workspace settings → Name**
3. Change workspace name to: **Jarvis HQ**
4. Save changes
5. After confirming, tell Jarvis to run:
```bash
cd /Users/user/OpenJarvis && .venv/bin/python -c "
from openjarvis.channels.slack_ops import SlackOpsCommandCenter
c = SlackOpsCommandCenter()
r = c.get_workspace_info()
print('team_name:', r.get('team',{}).get('name','UNKNOWN'))
"
```
Expected: `team_name: Jarvis HQ`

**Status after Bryan completes:** Item 5 moves to `CLEARED`

### Action D: Re-run Google OAuth with Drive Scope (Item 4 — REQUIRED_FOR_NO_GAP_JARVIS)

Current token has `gmail.readonly` and `calendar.readonly` but NOT `drive.readonly`. Drive API returns 403.

**Delete old token first:**
```bash
rm ~/.openjarvis/connectors/google.json
```

**Re-run OAuth with all three scopes:**
```bash
cd /Users/user/OpenJarvis
.venv/bin/python -c "
import os
from openjarvis.connectors.oauth import run_oauth_flow
# Load client credentials from env file
import pathlib
env_text = pathlib.Path.home().joinpath('.jarvis/cloud-keys.env').read_text()
env = dict(line.split('=', 1) for line in env_text.strip().splitlines() if '=' in line and not line.startswith('#'))
client_id = env.get('GOOGLE_OAUTH_CLIENT_ID', os.environ.get('GOOGLE_OAUTH_CLIENT_ID', ''))
client_secret = env.get('GOOGLE_OAUTH_CLIENT_SECRET', os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', ''))
run_oauth_flow(
  client_id=client_id,
  client_secret=client_secret,
  scopes=[
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/drive.readonly',
  ],
  credentials_path=str(pathlib.Path.home() / '.openjarvis/connectors/google.json')
)
"
```
Complete browser consent. Then Jarvis will verify Drive live read.

**Status after Bryan completes:** Item 4 moves to `CLEARED`

---

*Ledger version: No-Gap Jarvis Total Closure Sprint*
*Last verified: 2026-06-19*
*Base HEAD: 6ab4edc9*
*Export to Obsidian: docs/blockers/bryan-action-blocker-ledger.md*
