# BRYAN_MANUAL_ACTIONS_REQUIRED.md

**Branch:** `localhost-get-tool`
**Produced:** 2026-06-21 (updated 2026-06-21 Slack correction pass)
**Status:** Pre-Final Blocker Closure sprint
**Purpose:** Exact manual steps Bryan must complete before final 100% cutover certification.

---

## Summary

| # | Item | Blocks Final Cutover? | Blocks This Sprint? |
|---|------|-----------------------|---------------------|
| 1 | Slack bot/channel notifications | **NOT BLOCKED — LIVE_VALIDATED** | No |
| 1b | Slack DM sync (`xoxp-` user token) | Only if Bryan needs DM sync in memory | No |
| 2 | Gmail OAuth — complete consent flow | Yes (Gmail live connector) | No |
| 3 | Calendar OAuth — complete consent flow | Yes (Calendar live connector) | No |
| 4 | Apple Developer — enroll + obtain cert | No (updater/signing only) | No |
| 5 | Telegram CHAT_ID — find and add | No (bot live, sends need chat_id) | No |
| 6 | Physical mobile phone test | Yes (mobile handoff proof) | No |
| 7 | Voice/mic physical test | No (US13 parked) | No |

---

## Item 1 — Slack: Bot/Channel Notifications — LIVE_VALIDATED (No Action Required)

**Status:** `SLACK_BOT_CHANNEL_LIVE_VALIDATED` — no Bryan action required for notifications.

**Evidence (2026-06-21 live revalidation):**
- `auth.test` → `ok: True`, team=Jarvis HQ, user=openclaw_jarvis, `bot_id: B0BA0S0MTFZ`
- Token type: `xoxb-` (bot token) — confirmed present in `.env` and `cloud-keys.env`
- `get_slack_status()` route → `ready_pending_test_approval` (both bot token and `JARVIS_SLACK_TEST_CHANNEL_ID` configured)
- `conversations.list (public_channel)` → 5 channels accessible (e.g., `#all-omnix-hq`, `#social`)
- Slack notification route (`SlackNotifier`) accepts `xoxb-` bot token — works for sends

**No action required from Bryan for notifications.**

---

## Item 1b — Slack DM Sync: `xoxp-` User Token (Optional — Only if DM Sync Required)

**Status:** `SLACK_DM_SYNC_BLOCKED_PLATFORM_CONSTRAINT`

**Why xoxp- is truly required for DM sync:**
This is a hard Slack platform constraint — not a code bug. Bot tokens (`xoxb-`) cannot read human-to-human DMs:
- `conversations.list?types=im` → `missing_scope` (confirmed live)
- `conversations.list?types=mpim` → `missing_scope` (confirmed live)
- Slack API docs: bot tokens with `im:history` can only read bot↔user DMs, not user↔user DMs
- `slack_connector.py` explicitly rejects bot tokens with this message: *"Bot tokens (xoxb-) can't read DMs."*

**Whether this blocks final cutover:** Only if Bryan wants Jarvis to read all his Slack DM history (human-to-human). If Bryan's use case is Slack channel notifications + channel message sync only, the existing bot token is sufficient.

**If Bryan decides DM sync is required:**
1. Go to [https://api.slack.com/apps](https://api.slack.com/apps) — Sign in with the Jarvis HQ workspace account.
2. Create a new Slack app or use existing → "OAuth & Permissions" → "User Token Scopes" — add:
   - `channels:read`, `channels:history`, `groups:read`, `groups:history`
   - `im:read`, `im:history`, `mpim:read`, `mpim:history`, `users:read`
3. Click "Install App to Workspace" → authorize → copy **User OAuth Token** (starts with `xoxp-`).
4. Store it:
   ```bash
   # Do NOT paste token into chat. Store directly in terminal:
   python3 -c "
   from openjarvis.connectors.oauth import save_tokens
   token = input('Paste xoxp- token (not echoed): ')
   save_tokens('~/.openjarvis/connectors/slack.json', {'token': token})
   print('Saved.')
   "
   ```

**What NOT to paste into chat:** The `xoxp-` token value itself. Never paste into Cursor chat, GitHub issues, or any AI chat.

**Safe storage location:** `~/.openjarvis/connectors/slack.json` (auto-saved by OAuth flow above)

**How Jarvis verifies after completion:**
```bash
cd /Users/user/OpenJarvis
python3 -m pytest tests/connectors/ -k "slack" -v
```

---

## Item 2 — Gmail OAuth: Consent Flow Required

**What Bryan must do:**
`GOOGLE_OAUTH_CLIENT_ID` is set in `.env`. `GOOGLE_OAUTH_CLIENT_SECRET` is a placeholder.
Bryan must add the real client secret and complete the OAuth consent flow.

**Where to do it:**
1. Go to [https://console.cloud.google.com/](https://console.cloud.google.com/) → APIs & Services → Credentials.
2. Find the OAuth 2.0 Client ID already configured for OpenJarvis.
3. Download the credentials JSON, or copy the **Client Secret** value.
4. Add to `~/.openjarvis/cloud-keys.env`:
   ```
   GOOGLE_OAUTH_CLIENT_SECRET=<real-value>
   ```
5. Run the local OAuth flow:
   ```bash
   cd /Users/user/OpenJarvis
   python3 -m openjarvis.connectors.gmail oauth-setup
   ```
   (Or equivalent CLI command in the project — check `--help`.)
6. Complete the browser consent screen (Gmail scopes: `gmail.readonly`).
7. The refresh token will be saved automatically to `~/.openjarvis/connectors/gmail_token.json`.

**What NOT to paste into chat:** Client Secret value, refresh token, access token.

**Safe storage location:**
`~/.openjarvis/cloud-keys.env` (client secret) + `~/.openjarvis/connectors/gmail_token.json` (auto-saved by OAuth flow).

**How Jarvis verifies after completion:**
```bash
python3 -m pytest tests/connectors/ -k "gmail" -v
```

---

## Item 3 — Calendar OAuth: Consent Flow Required

**What Bryan must do:**
Same Google Cloud project as Gmail. Calendar OAuth uses the same client ID/secret.
After completing Gmail OAuth (Item 2), run the Calendar-specific consent flow.

**Where to do it:**
1. Ensure `GOOGLE_OAUTH_CLIENT_SECRET` is set (from Item 2).
2. Add `calendar.readonly` scope if not already present.
3. Run:
   ```bash
   cd /Users/user/OpenJarvis
   python3 -m openjarvis.connectors.gcalendar oauth-setup
   ```
4. Complete browser consent for Calendar scopes.
5. Token saved to `~/.openjarvis/connectors/gcalendar_token.json`.

**What NOT to paste into chat:** Any token or secret values.

**Safe storage location:** `~/.openjarvis/connectors/gcalendar_token.json`

**How Jarvis verifies:**
```bash
python3 -m pytest tests/connectors/ -k "gcalendar or calendar" -v
```

---

## Item 4 — Apple Developer: Enrollment + Signing Certificate

**Applies to:** Tauri app code-signing and notarization only. Does NOT affect Jarvis functionality.

**What Bryan must do:**
1. Enroll in Apple Developer Program at [https://developer.apple.com/enroll/](https://developer.apple.com/enroll/) — requires Apple ID + $99/yr fee.
2. Once enrolled, generate a "Developer ID Application" certificate in Xcode → Settings → Accounts → Manage Certificates.
3. The signing identity will appear in keychain as "Developer ID Application: Bryan Aw (XXXXXXXXXX)".
4. For notarization, set App Store Connect API key or Apple ID + app-specific password:
   ```
   APPLE_ID=bryan@example.com
   APPLE_TEAM_ID=XXXXXXXXXX
   APPLE_ID_PASSWORD=xxxx-xxxx-xxxx-xxxx  (app-specific password)
   ```
   Add to `~/.openjarvis/cloud-keys.env`.

**Current state in `frontend/src-tauri/tauri.conf.json`:**
`signingIdentity: "-"` — unsigned build. App runs locally unsigned. Distribution/auto-update requires signing.

**What NOT to paste into chat:** Apple ID password, APPLE_ID_PASSWORD, cert private key.

**Safe storage:** macOS Keychain (cert) + `~/.openjarvis/cloud-keys.env` (API keys).

**Blocks final cutover?** No — Jarvis is usable unsigned on the local machine. Required only for distribution or auto-update.

---

## Item 5 — Telegram: Confirm CHAT_ID

**What Bryan must do:**
`JARVIS_TELEGRAM_BOT_TOKEN` is set and the bot (`OpenJarvisPersonalBot`) is live.
`JARVIS_TELEGRAM_CHAT_ID` is set in `~/.openjarvis/cloud-keys.env`.
Bryan should verify the chat ID is correct by sending a test message:

```bash
cd /Users/user/OpenJarvis
python3 -c "
import os, httpx
from pathlib import Path
# Read cloud-keys.env
for line in (Path.home() / '.openjarvis' / 'cloud-keys.env').read_text().splitlines():
    if '=' in line and not line.startswith('#'):
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())
tok = os.environ.get('JARVIS_TELEGRAM_BOT_TOKEN', '')
chat = os.environ.get('JARVIS_TELEGRAM_CHAT_ID', '')
print('Bot token prefix:', tok[:10] + '...' if tok else 'MISSING')
print('Chat ID set:', bool(chat))
"
```

If chat_id is missing or wrong, find it by:
1. Send any message to `@OpenJarvisPersonalBot` in Telegram.
2. Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser.
3. Copy the `chat.id` value from the response.
4. Update `JARVIS_TELEGRAM_CHAT_ID` in `~/.openjarvis/cloud-keys.env`.

**What NOT to paste into chat:** Token value, chat_id (marginally sensitive).

**Blocks final cutover?** No — Telegram notifications work; chat_id required for outbound sends.

---

## Item 6 — Physical Mobile Phone Test

**What Bryan must do:**
On your iPhone (or any mobile browser):
1. Start Jarvis locally: `cd /Users/user/OpenJarvis && python3 -m openjarvis.cli serve` (or equivalent).
2. Find your MacBook's LAN IP: `ipconfig getifaddr en0`
3. Open in mobile browser: `http://<LAN-IP>:8000/mobile`
4. Verify the Jarvis Mobile page loads (PWA landing page).
5. Open in mobile browser: `http://<LAN-IP>:5173` (Vite dev server) or the built frontend port.
6. Verify React MobilePage loads, Authority Cockpit section visible.
7. Try tapping Emergency Stop button (confirm it triggers the route).
8. Take a screenshot and save to `docs/certification/artifacts/mobile_phone_proof/`.

**Blocks final cutover?** Yes — final 100% cutover requires physical mobile proof.

**If MacBook is off (AWS backend):** The `JARVIS_AWS_BASE_URL` must be configured and AWS ECS task running. Mobile connects to AWS URL directly — MacBook does not need to be on.

---

## Item 7 — Voice/Mic Physical Test

**Current status:** US13 voice is `PARKED / UNSAFE`. Voice is NOT required for the first 100% cutover.

No action required from Bryan unless Bryan explicitly approves re-opening US13 voice in a future sprint.

**Do not unpause voice without explicit approval.** If Bryan decides to activate voice: a separate voice closure sprint is required before including in cutover scope.

---

## Summary of What Blocks Final Cutover

| Blocker | Currently | Bryan action needed? |
|---------|-----------|----------------------|
| Gmail OAuth | `BLOCKED_NEEDS_OAUTH` | Yes (Item 2) |
| Calendar OAuth | `BLOCKED_NEEDS_OAUTH` | Yes (Item 3) |
| Slack `xoxp-` token | `BLOCKED_NEEDS_BRYAN_MANUAL_ACTION` | Yes (Item 1) |
| Physical mobile test | `BLOCKED_NEEDS_PHYSICAL_TEST` | Yes (Item 6) |
| Telegram chat_id | `LIVE_PARTIALLY` (token live, chat_id set) | Verify (Item 5) |
| GitHub | `LIVE_VALIDATED` | None required |
| Apple signing | `BLOCKED_APPLE_ENROLLMENT_PENDING` | Optional (Item 4) |
| Voice | `PARKED / UNSAFE` | None (parked) |

---

*Do not paste any secret values into Cursor chat, GitHub issues, or any AI tool. All credentials must be stored in `~/.openjarvis/cloud-keys.env` or the macOS Keychain only.*
