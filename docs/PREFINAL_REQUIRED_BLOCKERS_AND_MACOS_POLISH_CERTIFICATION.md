# Pre-Final Required Blockers and macOS Polish Certification

**Date:** 2026-06-22
**Branch:** `localhost-get-tool`
**Status:** `PREFINAL_BLOCKERS_DOCUMENTED — AWAITING_MANUAL_CLOSURE`

---

## Code-Closed This Sprint

| Item | Classification |
|------|---------------|
| Registry duplicate registration crash | `CLOSED` — idempotent `__qualname__` check |
| Gmail `__main__` CLI entrypoint | `CLOSED` — `oauth-setup` + `status` commands |
| Calendar `__main__` CLI entrypoint | `CLOSED` — `oauth-setup` + `status` commands |
| Env var credential discovery | `CLOSED` — fallback chain covers `Google_CLIENT_ID` |
| macOS permission prompt spam | `MACOS_PERMISSION_PROMPT_POLISH_CLOSED` |
| Unified cockpit UI | `CLOSED` — implemented, tsc clean |

---

## Remaining Pre-Final Blockers

### REQUIRED for text/mobile final cutover

| Blocker | Action | Owner |
|---------|--------|-------|
| Gmail OAuth token | Run `python3 -m openjarvis.connectors.gmail oauth-setup`, authorize | Bryan |
| Calendar OAuth token | Check after Gmail; run `gcalendar oauth-setup` if needed | Bryan |
| Physical mobile screenshot | Open `http://192.168.1.16:8000/mobile` from iPhone | Bryan |

### Platform-blocked (cannot be code-fixed)

| Blocker | Classification | Detail |
|---------|---------------|--------|
| Apple signing cert | `BLOCKED_BY_MISSING_APPLE_DEVELOPER_CERT` | Enrollment + cert required |
| Slack DM history | `BLOCKED_BY_SLACK_TOKEN_SCOPE_CONSTRAINT` | `xoxp` required |

### Parked (do NOT block text/mobile cutover)

| Item | Classification |
|------|---------------|
| Voice wake word | `PARKED_WAKE_WORD_NOT_CONFIGURED` |
| Rust memory bridge | `PARKED_BUILD_STEP_PENDING` |

---

## macOS Permission Prompt Classification

| Check | Classification | Evidence |
|-------|---------------|----------|
| Screen recording TCC prompt | `MACOS_PERMISSION_PROMPT_POLISH_CLOSED` | 5-min cache, no polling loop |
| System audio / microphone TCC | `MACOS_PERMISSION_PROMPT_POLISH_CLOSED` | Lazy check only |
| Accessibility | `LIMITED_ACCEPT_FIRST_PROMPT_ONLY` | Checked once per process start via ctypes |

---

## Final Readiness

- Text input: ✅ Ready (backend runs, chat endpoint functional)
- Mobile access: ✅ Server confirmed, URL confirmed, physical proof pending Bryan
- Voice: ⛔ Parked
- Desktop operator: ⚠️ Permissions not granted; lazy check, no spam
- Connectors: Gmail/Calendar pending; Slack/Telegram/GitHub live
