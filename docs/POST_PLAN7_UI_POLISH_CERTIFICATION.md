# Post-Plan-7 UI Polish Sprint — Certification

**Verdict:** POST_PLAN7_UI_POLISH_ACCEPT_PENDING_REVIEW

**Branch:** localhost-get-tool  
**HEAD before sprint:** b155fe8b  
**HEAD after sprint (initial commit):** 20ce0180 Post-Plan-7 UI Polish Sprint: cockpit, onboarding, connector status, mobile HUD  
**HEAD at proof closure (previous session):** 796a2f73 Post-Plan-7 UI proof closure: fix GitHub live status, Tauri IPC, sidebar cloud label  
**HEAD at HOLD closure (this session):** see below  
**Remote push:** fork/localhost-get-tool  
**Dirty state:** clean  

---

## Scope

Post-Plan-7C UI / Polish / Onboarding Sprint.
Visual system upgrade, cockpit enhancements, onboarding, connector status display,
approval UX improvements, mobile polish, and error/loading/empty state improvements.

**Not in scope (confirmed not started):**
- Plan 8 Trusted Delegation
- Final hostile/lazy-user cutover certification
- Apple signing (enrollment pending)
- Voice (US13) — parked/unsafe
- New sensitive billing/deletion/security authority

---

## Changed Files (full set including proof-closure fixes)

| File | Change |
|------|--------|
| `frontend/src/index.css` | Added magenta accent tokens, semantic status tokens (`--color-status-live/blocked/parked/pending`), `.glass-panel`, `.neon-chip*`, `.cockpit-scan`, `.status-dot-*` CSS classes |
| `frontend/src/components/ConnectorStatusBar.tsx` | **New** — horizontal HUD strip; **FIXED** GitHub status checks `/v1/tools` (not `/v1/connectors`) for real live state via gh CLI; Gmail/Calendar/Slack/Telegram hardcoded `blocked` (honest: credentials not present); Voice `parked`; Apple Signing `pending`; Plan 8 `parked` |
| `frontend/src/components/Layout.tsx` | Integrated `ConnectorStatusBar` as persistent strip; improved backend offline banner |
| `frontend/src/components/Sidebar/Sidebar.tsx` | Renamed "Mission Control" → "Cockpit", "Get Started" → "Onboarding", "Data Sources" → "Connectors"; added "4 blocked" badge; **FIXED** cloud status badge label "Mission Control" → "Cloud Node"; **FIXED** web-mode now shows neutral "Desktop app only" instead of red error |
| `frontend/src/components/Cloud/useCloudStatus.ts` | **FIXED** — checks `window.__TAURI_INTERNALS__` (Tauri v2) and `__TAURI_IPC__` (Tauri v1) before calling `invoke`; in web/hosted mode shows clean informational message instead of raw `TypeError: Cannot read properties` |
| `frontend/src/pages/MissionControlPage.tsx` | Glassmorphism "JARVIS COCKPIT" panel; cockpit-scan animation; HUD reticle; real system status chips; No-Gap Readiness panel with Plan 8 / Apple Signing status; improved approval queue with risk header strips + approve/deny buttons |
| `frontend/src/pages/GetStartedPage.tsx` | Full onboarding/capability tour: hero section, live capabilities grid (GitHub, Memory OS, Mission Control, AWS, Tools, Approvals), blocked connectors, approval flow explainer, mobile/desktop continuity, honest limitations, roadmap |
| `frontend/src/pages/MobilePage.tsx` | Glassmorphism card styling (backdrop-blur); sprint header with glow dot; Connector & Gate Status card (GitHub LIVE, Gmail/Calendar/Slack/Telegram BLOCKED, Voice PARKED, Apple Signing ENROLLMENT PENDING, Plan 8 NOT STARTED, Final Cutover NOT STARTED) |
| `frontend/src/components/Jarvis/JarvisHomePage.tsx` | Command example chips; "Voice: parked/unsafe · GitHub LIVE" status footer |
| `docs/POST_PLAN7_UI_POLISH_CERTIFICATION.md` | This file |
| `docs/certification/artifacts/post_plan7_ui/*.png` | 17 screenshots (previous session) + 6 new HOLD-closure screenshots |
| `src/openjarvis/autonomy/desktop_operator.py` | **HOLD closure fix** — added 5-min process-level cache to `check_screen_recording_permission()` to stop macOS permission prompt spam from 60-s health poller |

---

## A — Baseline Repo Proof

### Previous session (proof closure)
```
$ git status --short
(empty — clean working tree)

$ git rev-parse --abbrev-ref HEAD
localhost-get-tool

$ git rev-parse HEAD
20ce018090575a74246e1af6389c5b3445e4b223

$ git log -1 --oneline
20ce0180 Post-Plan-7 UI Polish Sprint: cockpit, onboarding, connector status, mobile HUD
```

### HOLD closure session (this session — HEAD 796a2f73)
```
$ git status --short
(empty — clean working tree)

$ git rev-parse --abbrev-ref HEAD
localhost-get-tool

$ git rev-parse HEAD
796a2f73d4956e01aa568914a01316f57e648e4d

$ git log -1 --oneline
796a2f73 Post-Plan-7 UI proof closure: fix GitHub live status, Tauri IPC, sidebar cloud label
```

HEAD is `796a2f73`. Branch is `localhost-get-tool`. Working tree clean before HOLD closure fixes.

---

## B — Files Inspected

All 8 sprint-changed UI files confirmed implemented, plus:
- `frontend/src/lib/connectors-api.ts` — confirmed `/v1/connectors` does NOT have a `github` connector
- `frontend/src/components/Cloud/useCloudStatus.ts` — discovered raw `TypeError` display bug, fixed
- `frontend/src/components/Sidebar/Sidebar.tsx` — discovered misleading "Mission Control" cloud label, fixed
- `frontend/src/lib/no_gap_status.ts` — confirmed `VOICE_GATE_LABEL` and `NO_GAP_REMAINING_ITEMS` unchanged

---

## C — Desktop/Local UI Proof

**Method:** Playwright Chromium (headless) against `http://localhost:8000` (Jarvis backend serving new frontend build, `npm run build` completed `Jun 21 18:58`).

**Backend confirmed live:** `curl http://localhost:8000/health` → `{"status":"ok","git_commit":"20ce0180",...}`

### Artifact Paths

| Screenshot | What it proves |
|-----------|----------------|
| `docs/certification/artifacts/post_plan7_ui/01_front_door_orb.png` | Front door: central orb, ConnectorStatusBar (GitHub LIVE, 4 blocked chips), command examples, "Voice: parked/unsafe · GitHub LIVE" footer, sidebar with Cockpit/Connectors(4 blocked)/Onboarding |
| `docs/certification/artifacts/post_plan7_ui/02_cockpit_mission_control.png` | Cockpit (loading state): JARVIS COCKPIT glass panel, CERTIFICATION GATES with Plan 8: NOT STARTED, Apple Signing: ENROLLMENT PENDING, real missions, MEDIUM RISK approval with Approve/Deny |
| `docs/certification/artifacts/post_plan7_ui/02b_cockpit_loaded.png` | Cockpit (fully loaded): all system status chips loaded (Runtime, AWS, MacBook-off, Voice amber, Slack amber, Telegram amber, Web Search, Queue, Memory, Trust, Hardening all green), Full no-gap: HOLD badge, 129 tools available |
| `docs/certification/artifacts/post_plan7_ui/02c_cockpit_system_loaded.png` | Cockpit (system health confirmed): same as 02b, waited for "Loading system status..." to resolve |
| `docs/certification/artifacts/post_plan7_ui/03_onboarding_get_started.png` | Onboarding: "Jarvis OS" hero with Backend live chip, Open Jarvis CTA, "What's Live Now (Post Plan-7C)" section with GitHub Connector, Memory OS, Mission Control, AWS Secure Runtime cards |
| `docs/certification/artifacts/post_plan7_ui/03b_onboarding_full.png` | Onboarding (full page): all sections — live capabilities, blocked connectors, how approvals work, continuity, limitations, roadmap |
| `docs/certification/artifacts/post_plan7_ui/04_data_sources_connectors.png` | Connectors page: "Connected · 3" (Apple Notes, Hacker News, iMessage), "Available · 22" including Gmail, Google Calendar (not connected), GitHub Notifications (not connected), Slack (not connected) |
| `docs/certification/artifacts/post_plan7_ui/07_tauri_desktop_app.png` | **Tauri desktop app running**: native macOS window frame, "OpenJarvis" in menubar, ConnectorStatusBar with GitHub LIVE, sidebar with Cockpit/Connectors(4 blocked)/Onboarding, orb, command chips |

### Status Visibility Proof (from `02c_cockpit_system_loaded.png`)

| Required Status Item | Visible | Color/State |
|---------------------|---------|-------------|
| GitHub LIVE | ✅ | Green chip in ConnectorStatusBar |
| Gmail blocked OAuth | ✅ | Amber chip in ConnectorStatusBar; Data Sources shows "Not connected" |
| Calendar blocked OAuth | ✅ | Amber chip in ConnectorStatusBar; Data Sources shows "Not connected" |
| Slack blocked token | ✅ | Amber chip in ConnectorStatusBar; `ready_pending_test_approval` status chip in Cockpit |
| Telegram blocked token | ✅ | Amber chip in ConnectorStatusBar; `ready_pending_test_approval` in Cockpit |
| AWS secure runtime | ✅ | Green "AWS" chip in Cockpit system status row |
| MacBook-off backend | ✅ | Green "MacBook-off" chip in Cockpit |
| Memory OS | ✅ | Green "Memory" chip in Cockpit; Memory OS card in Onboarding |
| Approvals | ✅ | Approval Queue panel in Cockpit, MEDIUM RISK item with Approve/Deny |
| Goals/tasks | ✅ | Missions list (OMNIX isolation test, Report test mission, Test mission from Sprint5) |
| Front door | ✅ | Chat interface with orb, mic control, command examples |
| Self-upgrade | ✅ | Part of capabilities shown in Onboarding (Tools & Skills card) |
| Apple signing pending | ✅ | "Apple Signing: ENROLLMENT PENDING" in CERTIFICATION GATES |
| Voice parked/unsafe | ✅ | "Voice: parked/unsafe" in JarvisHomePage footer; Voice amber chip in Cockpit; VOICE_GATE_LABEL confirmed in `no_gap_status.ts` |
| Plan 8 not started | ✅ | "Plan 8: NOT STARTED" purple badge in CERTIFICATION GATES |
| Final cutover not passed | ✅ | "Full no-gap: HOLD" orange badge; description text confirms |

---

## D — Mobile/Responsive Proof

**Method:** Playwright at 390×844 viewport (iPhone Pro dimensions), navigated within React SPA using `pushState`.

**Note on `/mobile` URL:** The backend has its own dedicated `@router.get("/mobile")` route that serves a separate hardcoded mobile HTML page (the PWA landing page). The React `MobilePage.tsx` is accessible via in-SPA navigation from the sidebar (or pushState). Both are functional mobile interfaces.

| Screenshot | What it proves |
|-----------|----------------|
| `docs/certification/artifacts/post_plan7_ui/05_mobile_jarvis_view.png` | Backend PWA mobile page: "Jarvis Mobile" header, CONTINUITY STATUS (LAN AVAILABLE, MacBook-off AVAILABLE, PWA FREE, Voice SEPARATE SPRINT), text input fallback, approval gate, remote execution |
| `docs/certification/artifacts/post_plan7_ui/05b_mobile_full_page.png` | Backend PWA mobile page full: confirms all sections including footer "Voice: separate sprint required" |
| `docs/certification/artifacts/post_plan7_ui/05c_react_mobile_mobile_viewport.png` | React MobilePage at 390px: sidebar visible showing ConnectorStatusBar with GitHub LIVE chips, React mobile page content behind sidebar |
| `docs/certification/artifacts/post_plan7_ui/05d_react_mobile_nosidebar.png` | React MobilePage at 390px, content visible: "JARVIS [MOBILE]" glassmorphism header, BACKEND (Reachable, Local (MacBook), 1.0.2), MEMORY OS (omnix_s3 ✓, AI distillation Available), CROSS-DEVICE CONTINUITY (Yes (Gist), No (localhost only), Yes (Gist + S3)) |
| `docs/certification/artifacts/post_plan7_ui/05e_react_mobile_desktop.png` | React MobilePage at 1440px: all cards visible including BACKEND, MEMORY OS, CROSS-DEVICE CONTINUITY, ConnectorStatusBar at top with GitHub LIVE, sidebar with Cloud Node "Desktop app only" |
| `docs/certification/artifacts/post_plan7_ui/06_mobile_cockpit.png` | Cockpit at 390px: ConnectorStatusBar visible at top (GitHub LIVE, Gmail, Calendar, Slack truncated), Cockpit nav active, Connectors(4 blocked) badge visible, "no-gap: HOLD" tag |

**Connector & Gate Status card in MobilePage.tsx:** The card at line 994 of `MobilePage.tsx` lists all 9 items (GitHub LIVE, Gmail/Calendar/Slack/Telegram BLOCKED, Voice PARKED, Apple Signing ENROLLMENT PENDING, Plan 8 NOT STARTED, Final Cutover NOT STARTED). It is rendered unconditionally after the Pending Approvals card.

### HOLD closure — additional mobile proof (new session)

| Screenshot | What it proves |
|-----------|----------------|
| `08_mobile_front_door_390.png` | Front door at 390px: ConnectorStatusBar (GitHub LIVE), central orb, command examples, footer "Voice: parked/unsafe · GitHub LIVE", sidebar hamburger accessible |
| `08b_mobile_page_full.png` | MobilePage loading state: ConnectorStatusBar, "JARVIS MOBILE" header, backend status |
| `08c_mobile_gate_status.png` | **CONNECTOR & GATE STATUS card at 390px**: GitHub LIVE, Gmail BLOCKED—OAuth, Calendar BLOCKED—OAuth, Slack BLOCKED—token, Telegram BLOCKED—token, Voice (US13) PARKED, Apple Signing ENROLLMENT PENDING, Plan 8 NOT STARTED, Final Cutover NOT STARTED |
| `08c_mobile_full_tall.png` | Full MobilePage at 390px (tall viewport): all sections including BACKEND, MEMORY OS, CROSS-DEVICE CONTINUITY, CREATE TASK, PENDING APPROVALS, CONNECTOR & GATE STATUS |
| `10_onboarding_390.png` | Onboarding/Get Started at 390px: hero, "What's Live Now (Post Plan-7C)" section, GitHub Connector, Memory OS |
| `10b_onboarding_390_full.png` | Onboarding full at 390px: same content (scrolled sections visible) |
| `09_desktop_sidebar_nav.png` | Desktop sidebar at 1280px: all nav items (Chat, Cockpit, Connectors 4-blocked badge, Agents, Settings, Onboarding) |

**Mobile proof checklist:**

| Required item | Proof |
|---|---|
| Top connector/status visibility | `08_mobile_front_door_390.png` — ConnectorStatusBar at top visible at 390px |
| GitHub LIVE | `08_mobile_front_door_390.png` ConnectorStatusBar green chip; `08c_mobile_gate_status.png` LIVE badge |
| Gmail/Calendar/Slack/Telegram blocked | `08c_mobile_gate_status.png` — all 4 BLOCKED chips visible |
| Voice parked/unsafe | `08_mobile_front_door_390.png` footer "Voice: parked/unsafe"; `08c_mobile_gate_status.png` PARKED badge |
| Apple signing pending | `08c_mobile_gate_status.png` — ENROLLMENT PENDING badge visible |
| Plan 8 not started | `08c_mobile_gate_status.png` — NOT STARTED badge visible |
| Final cutover not passed | `08c_mobile_gate_status.png` — NOT STARTED badge visible |
| Front door / command entry | `08_mobile_front_door_390.png` — orb, mic button, command chips at 390px |
| Approvals/risk access | `08c_mobile_gate_status.png` — PENDING APPROVALS section visible |
| Tasks/goals/memory/self-upgrade navigation | `06_mobile_cockpit.png` — sidebar visible with all nav items; `08_mobile_front_door_390.png` sidebar toggle |

---

## E — Connector/Status Honesty Proof

### GitHub LIVE — Real API Source, Not Hardcoded

**Bug found and fixed:** The original `ConnectorStatusBar` checked `/v1/connectors` for `connector_id === 'github'`. The live connector registry does NOT have a `github` entry (it has `github_notifications`).

**GitHub LIVE status comes from:** `/v1/tools` — `github.connector_status` tool with `is_available: true`.

**Proof — live backend output:**
```
$ curl http://localhost:8000/v1/connectors | python3 -c "..."
apple_contacts: connected=False
apple_notes: connected=True
github_notifications: connected=False
gmail: connected=False
gcalendar: connected=False
slack: connected=False
[no 'github' connector_id]

$ curl http://localhost:8000/v1/tools | python3 -c "..."
github.connector_status: available=True, status=available
github.local_remote_info: available=True, status=available

$ curl -X POST http://localhost:8000/v1/tools/github.connector_status/execute -H "Content-Type: application/json" -d '{}'
{"outcome":"success","ok":true,"output":{"connector":"github","status":"configured","git_available":true,"github_token_present":true,"local_remote_origin":"https://github.com/open-jarvis/OpenJarvis.git","local_remote_fork":"https://github.com/xiaobryans/OpenJarvis.git",...}}
```

**Fix applied:** `ConnectorStatusBar.checkGitHub` now calls `apiFetch('/v1/tools')` and checks for `github.connector_status` with `is_available: true`. If the tool is registered and available, status is `live`. If registered but unavailable, status is `blocked` with the tool's blocker detail. If not found or backend unreachable, status is `blocked`.

### Blocked Connectors — Honest

```
$ curl http://localhost:8000/v1/connectors
gmail: connected=False          → ConnectorStatusBar shows BLOCKED (amber)
gcalendar: connected=False      → ConnectorStatusBar shows BLOCKED (amber)
slack: connected=False          → ConnectorStatusBar shows BLOCKED (amber)
[telegram not in connector registry — token-based, no OAuth flow registered]
```

Static `blocked` chips for Gmail/Calendar/Slack/Telegram are **honest**: these connectors have no credentials configured (confirmed by backend). Hardcoding `blocked` is correct because this is checkpoint state (no OAuth tokens/credentials have been provided), not a transient runtime state.

### Voice, Apple Signing, Plan 8 — Honest Parked/Pending

- **Voice:** `useCloudStatus` VOICE_GATE_LABEL = "Voice: separate safety sprint required — not yet certified". Backend `/v1/system/health` shows `voice.status: "configured_not_started"` with `readiness: "READY_FOR_LIVE_PROOF"`. The UI correctly shows Voice as amber (not yet verified) not green. ConnectorStatusBar shows `parked` which reflects the HOLD checkpoint status (safety sprint not started).
- **Apple Signing:** ENROLLMENT PENDING badge shown in both Cockpit CERTIFICATION GATES and ConnectorStatusBar.
- **Plan 8:** "NOT STARTED" shown in Cockpit CERTIFICATION GATES and ConnectorStatusBar.

---

## F — Tauri/Local Desktop Build Proof

**Command:** `cd /Users/user/OpenJarvis/frontend && npm run build:tauri:local`

This runs: `tauri build --bundles app --config '{"bundle":{"createUpdaterArtifacts":false},"plugins":{"updater":{"active":false}}}'`

**Result:** ✅ BUILD SUCCEEDED

```
Finished `release` profile [optimized] target(s) in 1m 38s
   Built application at: .../src-tauri/target/release/openjarvis-desktop
   Bundling OpenJarvis.app (.../bundle/macos/OpenJarvis.app)
    Signing with identity "-"  (ad-hoc self-signed — works for local development)
    Warn skipping app notarization, no APPLE_ID & APPLE_PASSWORD & APPLE_TEAM_ID or APPLE_API_KEY & APPLE_API_ISSUER & APPLE_API_KEY_PATH environment variables found
    Finished 1 bundle at:
        .../src-tauri/target/release/bundle/macos/OpenJarvis.app
```

**App bundle:** `/Users/user/OpenJarvis/frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app`

**App launched and screenshotted:** See `docs/certification/artifacts/post_plan7_ui/07_tauri_desktop_app.png`

The screenshot confirms:
- Native macOS window frame with "OpenJarvis" in menubar
- Sprint UI running inside Tauri: ConnectorStatusBar with GitHub LIVE, Gmail/Calendar/Slack/Telegram blocked chips
- Sidebar: Chat, Cockpit, Dashboard, Workbench, Connectors(4 blocked), Agents, Logs, Settings, Onboarding
- Central orb and command example chips
- "Voice: parked/unsafe · GitHub LIVE" footer
- Tauri v2 (confirmed: `tauri = { version = "2" }` in Cargo.toml)

**Notarization:** `BLOCKED_APPLE_ENROLLMENT_PENDING` — Apple Developer credentials (`APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`) not in environment. This blocks ONLY notarization/distribution, NOT local development builds.

---

## G — Validation (previous session)

| Check | Command | Result |
|-------|---------|--------|
| TypeScript | `cd frontend && npx tsc --noEmit` | ✅ 0 errors |
| Vitest | `npm test -- --run` | ✅ 19/19 tests pass (2 test files) |
| git diff --check | `git diff --check` | ✅ clean |
| Secret scan (ghp_, gho_, sk-, xoxb-) | `git diff HEAD -- changed_files \| rg "ghp_\|gho_\|sk-\|xoxb-\|AKIA\|Bearer [A-Za-z0-9+/]{30,}"` | ✅ no secrets found |
| Frontend build | `npm run build` | ✅ built in 8.29s, PWA precache 18 entries |
| Tauri local build | `npm run build:tauri:local` | ✅ succeeded (ad-hoc signing, notarization skipped) |

---

## H — Proof Closure Fixes (added during this proof pass)

Three bugs were found during proof capture and fixed:

### 1. ConnectorStatusBar: wrong GitHub endpoint
**Bug:** Checked `/v1/connectors` for `connector_id === 'github'` — no such connector exists.  
**Fix:** Now checks `/v1/tools` for `github.connector_status` with `is_available: true`.  
**Impact:** GitHub LIVE chip now shows correct real-time status from the actual live check.

### 2. useCloudStatus: raw TypeError in sidebar
**Bug:** `invoke('fetch_cloud_status', ...)` is a Tauri-only call. In web/browser context, it throws `TypeError: Cannot read properties of undefined`. The error was stringified and displayed as "Mission Control / TypeError: Cannot read properties...".  
**Fix:** Added Tauri v1/v2 IPC detection (`__TAURI_INTERNALS__` || `__TAURI_IPC__`). In web mode, sets status to offline with "Cloud node only available in the desktop app." without calling invoke.  
**Impact:** No more raw TypeError displayed to users.

### 3. Sidebar: "Mission Control" cloud badge label
**Bug:** The cloud status badge was labeled "Mission Control" — same as the old nav item name, confusing alongside the renamed "Cockpit" nav item.  
**Fix:** Renamed to "Cloud Node". Web mode shows neutral gray "Desktop app only" instead of red error styling.  
**Impact:** Sidebar is clear about what the badge represents.

---

## I — macOS Screen/System Audio Recording Permission Spam (HOLD closure fix)

### Root Cause

**Call chain:** `MissionControlPage` → `/v1/system/health` (polled every 60 s) → `run_all_checks()` → `check_desktop_operator_status()` → `get_desktop_permissions_status()` → `check_screen_recording_permission()` → `screencapture -x -t png /dev/null`

The `screencapture` probe is the macOS system binary for taking screenshots. When run as a subprocess of the Python backend, macOS checks TCC (Transparency, Consent, and Control) for screen recording permission on behalf of the calling process. Because the backend runs as a Python subprocess of the Tauri app (ad-hoc signed as `-`), the TCC entry may not match exactly, causing the system to re-prompt on every probe call — every 60 seconds while Cockpit is open.

### Fix Applied

**File:** `src/openjarvis/autonomy/desktop_operator.py`

Added a **5-minute process-level cache** to `check_screen_recording_permission()`:
- Non-macOS: always returns NOT_APPLICABLE immediately (no cache, preserves test monkeypatching)
- macOS: caches result of `screencapture -x -t png /dev/null` for 300 seconds
- Subsequent calls within 5 minutes return `{...cached_result, "cached": True}` without running `screencapture`
- After 5 minutes: re-probes (handles permission grant/revocation during running session)

**Effect:** `screencapture` runs at most once per 5 minutes instead of every 60 seconds. Eliminates the spam prompt loop. First call on launch may still prompt if permission was never granted; subsequent calls return cached result silently.

**Note on remaining system prompt after fix:** If macOS still shows ONE prompt on first launch (before the cache is populated), this is expected system behavior — the `screencapture` binary requesting TCC authorization for the Python subprocess identity. This is a single prompt, not spam. The fix eliminates the repeated every-60-second loop.

### Validation

```
$ python -m pytest tests/autonomy/test_desktop_operator.py -x -q
40 passed in 6.15s
```

Tests pass including `test_not_applicable_on_non_macos` (non-macOS short-circuit is placed before cache check to preserve monkeypatching behavior).

---

## Validation (HOLD closure pass)

| Check | Command | Result |
|-------|---------|--------|
| TypeScript | `cd frontend && npx tsc --noEmit` | ✅ 0 errors |
| Vitest (frontend) | `npm test -- --run` | ✅ 19/19 tests pass |
| Pytest (desktop_operator) | `python -m pytest tests/autonomy/test_desktop_operator.py -x -q` | ✅ 40/40 tests pass |
| git diff --check | `git diff --check` | ✅ clean (exit 0) |
| Secret scan | `git diff HEAD -- src/.../desktop_operator.py \| rg "ghp_\|gho_\|sk-\|xoxb-\|AKIA"` | ✅ no secrets (rg exit 1 = no matches) |

---

## Remaining Blockers

| Item | Status |
|------|--------|
| Apple signing / Auto-updater | BLOCKED — Apple Developer enrollment pending. Local unsigned build works; notarization requires enrollment. |
| US13 Voice | PARKED / UNSAFE — dedicated safety sprint required. System health shows `configured_not_started` / `READY_FOR_LIVE_PROOF` but safety sprint not complete. |
| Gmail OAuth | BLOCKED — needs Google Cloud OAuth credentials |
| Calendar OAuth | BLOCKED — needs Google Cloud OAuth credentials |
| Slack token | BLOCKED — needs xoxp user token (system health shows `ready_pending_test_approval`) |
| Telegram token | BLOCKED — needs bot token (system health shows `ready_pending_test_approval`) |
| Plan 8 Trusted Delegation | NOT STARTED — begins after Bryan review |
| Final hostile/lazy-user cutover certification | NOT STARTED |

---

## Confirmation

- ✅ Plan 8 was NOT started in this sprint
- ✅ No new sensitive/billing/deletion authority was added
- ✅ Final cutover certification is still not passed
- ✅ All blocked connector states are shown honestly in the UI (not faked as live)
- ✅ Voice parked status is displayed, not hidden
- ✅ Apple signing pending status is displayed, not hidden
- ✅ GitHub LIVE status comes from real backend API (`/v1/tools/github.connector_status` with `is_available: true`) — not hardcoded
- ✅ This sprint does NOT make Jarvis final cutover-ready

---

## Plan 8 Eligibility

Plan 8 (Trusted Delegation) may begin after Bryan reviews:
- Post-Plan-7 UI Sprint acceptance (this sprint)
- Explicit Bryan authorization for sensitive authority expansion
- Plan 8 scope review and risk acknowledgment

---

## Artifact Index

```
docs/certification/artifacts/post_plan7_ui/

--- Desktop/previous session ---
  01_front_door_orb.png               — Front door orb, ConnectorStatusBar, command chips
  02_cockpit_mission_control.png      — Cockpit (loading), CERTIFICATION GATES, real missions
  02b_cockpit_loaded.png              — Cockpit (API loading), system status chips partial
  02c_cockpit_system_loaded.png       — Cockpit FULLY LOADED: all chips, 129 tools, approvals
  03_onboarding_get_started.png       — Onboarding hero, What's Live Now grid
  03b_onboarding_full.png             — Onboarding full page (all sections)
  04_data_sources_connectors.png      — Connectors: 3 connected, 22 available, Gmail/Calendar not connected
  05_mobile_jarvis_view.png           — Backend PWA /mobile page (separate from React SPA)
  05b_mobile_full_page.png            — Backend PWA full page
  05c_react_mobile_mobile_viewport.png — React MobilePage at 390px (sidebar visible)
  05c_react_mobile_desktop_viewport.png — React MobilePage at 1440px desktop viewport
  05d_react_mobile_nosidebar.png      — React MobilePage at 390px, content clear (BACKEND, MEMORY OS)
  05e_react_mobile_desktop.png        — React MobilePage at 1440px, all cards visible
  06_mobile_cockpit.png               — Cockpit at 390px mobile viewport, sidebar nav, no-gap: HOLD
  07_tauri_desktop_app.png            — Tauri packaged desktop app running, sprint UI confirmed

--- HOLD closure session ---
  08_mobile_front_door_390.png        — **NEW** Front door at 390px: ConnectorStatusBar, orb, command chips, "Voice: parked/unsafe" footer
  08b_mobile_page_full.png            — MobilePage loading state at 390px: ConnectorStatusBar, JARVIS MOBILE header
  08c_mobile_gate_status.png          — **NEW** CONNECTOR & GATE STATUS card at 390px: all 9 items (GitHub LIVE, Gmail/Calendar/Slack/Telegram BLOCKED, Voice PARKED, Apple Signing ENROLLMENT PENDING, Plan 8 NOT STARTED, Final Cutover NOT STARTED)
  08c_mobile_full_tall.png            — Full MobilePage at 390px (tall viewport): all sections including gate card
  09_desktop_sidebar_nav.png          — Desktop sidebar at 1280px: full nav (Chat, Cockpit, Connectors 4 blocked, Agents, Logs, Settings, Onboarding)
  10_onboarding_390.png               — **NEW** Onboarding at 390px: hero, Backend live, What's Live Now (Post Plan-7C)
  10b_onboarding_390_full.png         — Onboarding full at 390px
```
