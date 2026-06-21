# MOBILE_ACCESS_HANDOFF.md

**Branch:** `localhost-get-tool`
**Updated:** 2026-06-22 (NO-GAP sprint)
**Purpose:** Complete handoff guide for mobile access to Jarvis.

## Confirmed Live State (2026-06-22)

| Item | Status |
|------|--------|
| MacBook LAN IP | `192.168.1.16` |
| Backend health | `{"status":"ok","version":"1.0.2","git_commit":"e80a2a0f"}` |
| `/mobile` route | 200 OK, 11KB HTML, mobile viewport, Jarvis branding |
| `/app` route | 200 OK |
| API key | Generated, stored in `~/.openjarvis/config.toml` |
| PWA manifest | `manifest.webmanifest` present in static build |

**Start command for LAN access:**
```bash
cd /Users/user/OpenJarvis
python3 -m openjarvis.cli serve --host 0.0.0.0 --port 8000
```

**iPhone URL:** `http://192.168.1.16:8000/mobile`

---

## Overview

Jarvis has two mobile access surfaces:

| Surface | URL | Notes |
|---------|-----|-------|
| **Backend PWA page** | `http://<host>:8000/mobile` | FastAPI-served, mobile-optimized HTML |
| **React MobilePage** | `http://<host>:5173` (dev) or `http://<host>:8000/app` (prod) → `/mobile` route | Full React SPA with mobile-responsive layout |
| **Authority Cockpit (mobile)** | Same React SPA → `/mobile` route → MobileAuthorityCockpit section | Plan 8B — emergency stop, tier view, approvals, audit |

---

## Access Method

### Option A — Local (MacBook on, LAN)

**MacBook must be on.** Backend runs locally at port 8000.

1. Start Jarvis:
   ```bash
   cd /Users/user/OpenJarvis
   python3 -m openjarvis.cli serve
   ```
2. Find MacBook LAN IP:
   ```bash
   ipconfig getifaddr en0
   ```
3. On mobile browser, open:
   - PWA landing: `http://<LAN-IP>:8000/mobile`
   - React full SPA: `http://<LAN-IP>:5173` (Vite dev server)

### Option B — AWS (MacBook off, remote)

**MacBook does not need to be on.** AWS ECS Fargate backend serves Jarvis remotely.

1. Ensure `JARVIS_AWS_BASE_URL` is configured (in `.env` or `cloud-keys.env`).
2. On mobile browser, open: `https://<AWS-domain>/mobile` (or configured domain).
3. React SPA frontend must be deployed to Vercel/CloudFront separately.

**Current AWS status:** Configured per Plan 4 certification (`PLAN_4_AWS_PRIVATE_RUNTIME_SECURITY_ACCEPT_PENDING_REVIEW`). MacBook-off capability is `FULLY_REAL`.

---

## iPhone Steps

1. Connect iPhone to same Wi-Fi as MacBook (for LAN access).
2. Open Safari (or any browser).
3. Navigate to `http://<LAN-IP>:8000/mobile`.
4. Verify PWA mobile page loads:
   - "Jarvis Mobile" header
   - CONTINUITY STATUS section (LAN, MacBook-off, PWA)
   - Text input fallback
   - Approval gate display
5. For React SPA access, navigate to `http://<LAN-IP>:5173`.
6. Verify MobilePage loads:
   - JARVIS [MOBILE] header
   - Backend status card
   - Memory OS card
   - Cross-device continuity card
   - MobileAuthorityCockpit section (Plan 8B authority controls)
7. Add to Home Screen (optional PWA install):
   - Safari → Share → "Add to Home Screen" → "Jarvis Mobile"

---

## Android Steps

Same as iPhone. Use Chrome instead of Safari.  
For PWA install: Chrome menu → "Add to Home Screen".

---

## Login / Auth / Token / Pairing Flow

**Current state:** No separate mobile login required.  
- The app uses `JARVIS_OPERATOR_PIN_HASH` (set in `cloud-keys.env`) for approval gating.
- The backend API does not currently require a separate mobile auth token.
- The `JARVIS_MOBILE_API_KEY` (if configured) is passed via the React frontend's `localStorage` (set during onboarding or via the GetStarted page).

**Mobile-specific config check:**  
In the React app, navigate to `/get-started` or `/settings` to configure the mobile backend URL if the default auto-detection doesn't find the backend.

---

## Features Available on Mobile

| Feature | Available on Mobile? | Notes |
|---------|----------------------|-------|
| Backend status | Yes | Backend PWA + React MobilePage |
| Memory OS status | Yes | React MobilePage |
| Cross-device continuity | Yes | React MobilePage |
| Connector/gate status | Yes | ConnectorStatusBar + Gate Status card |
| Pending approvals | Yes | React MobilePage + MobileAuthorityCockpit |
| Create task | Yes | React MobilePage |
| Authority cockpit | Yes | MobileAuthorityCockpit (Plan 8B) |
| Emergency stop | Yes | MobileAuthorityCockpit — activate/clear buttons |
| Permission tier view | Yes | MobileAuthorityCockpit — compact tier cards |
| Risk classifier | Yes | MobileAuthorityCockpit — quick action preview |
| Recent audit trail | Yes | MobileAuthorityCockpit |
| Spend/secret guardrails | Yes | MobileAuthorityCockpit |
| GitHub connector | Yes (read-only status) | Live in ConnectorStatusBar |
| Slack notifications | Partial (status only) | Full sync requires `xoxp-` token |
| Gmail / Calendar | Blocked (OAuth required) | Status shows BLOCKED—OAuth |
| Telegram | Yes (bot live) | OpenJarvisPersonalBot configured |
| Voice / STT | No | US13 PARKED / UNSAFE |
| Chat/LLM | Yes (via API calls) | Requires backend to be running |
| Mission control | Yes (via React SPA) | Full mission control accessible |
| Workbench | Yes (via React SPA) | Coding manager, file tools |

---

## Known Limitations

1. **Slack DM sync blocked** — requires `xoxp-` user token (see `BRYAN_MANUAL_ACTIONS_REQUIRED.md` Item 1).
2. **Gmail/Calendar blocked** — OAuth consent flow required (see Items 2 & 3).
3. **Voice not available** — US13 is `PARKED / UNSAFE`. Text input fallback available.
4. **No native mobile app** — mobile access is PWA/browser-only. No TestFlight, no App Store, no native iOS/Android app.
5. **LAN-only limitation** — without AWS deployment, MacBook must be on same network.
6. **Authority routes: fresh server restart** — if the Jarvis server has been running since before Plan 8B was deployed, a restart is required: `python3 -m openjarvis.cli serve` (kill and restart).
7. **macOS Screen/System Audio permission prompt** — on first launch, macOS may prompt for screen recording / system audio access. Accept once; prompt recurs at most every 5 minutes per sprint cache.

---

## Reconnect / Recovery Steps

If mobile cannot reach backend:
1. Verify MacBook is on and Jarvis server is running (`ps aux | grep jarvis`).
2. Verify same Wi-Fi network.
3. Check LAN IP hasn't changed: `ipconfig getifaddr en0`.
4. Restart server: `cd /Users/user/OpenJarvis && python3 -m openjarvis.cli serve`.
5. Hard-refresh mobile browser (Safari: hold-refresh icon; Chrome: settings → refresh).

If React SPA shows blank screen:
1. Check Vite dev server is running: `cd /Users/user/OpenJarvis/frontend && npm run dev`.
2. Or build and serve: `npm run build && npx serve dist -l 5173`.

---

## Emergency Stop / Revoke from Mobile

From the MobileAuthorityCockpit section (accessible at `/mobile` React route):

1. Scroll to "Authority Cockpit" section.
2. Tap "Activate Emergency Stop" button.
3. Confirm in the modal prompt.
4. The emergency stop activates across all Jarvis sessions immediately.
5. To clear: tap "Clear Emergency Stop" (requires operator PIN if configured).

Alternative — direct API call from mobile browser devtools or curl:
```bash
curl -X POST http://<LAN-IP>:8000/v1/authority/emergency-stop/activate \
  -H "Content-Type: application/json" \
  -d '{"reason": "manual mobile trigger"}'
```

---

## How Bryan Verifies Mobile Is Working

**Automated (backend):**
```bash
cd /Users/user/OpenJarvis
python3 -c "
import httpx, json
r = httpx.get('http://localhost:8000/mobile', timeout=5)
print('PWA page status:', r.status_code)
r2 = httpx.get('http://localhost:8000/v1/authority/status', timeout=5)
print('Authority route:', r2.status_code, r2.json().get('status', 'unknown'))
"
```

**Physical proof (Bryan manual):**
1. Load `http://<LAN-IP>:8000/mobile` on phone — confirm page loads.
2. Load React SPA on phone — confirm MobileAuthorityCockpit section visible.
3. Tap emergency stop — confirm button responds.
4. Screenshot saved to `docs/certification/artifacts/mobile_phone_proof/`.
5. Report to next certification session.

---

## Mobile Backend Configuration

The React frontend reads backend URL from:
1. `localStorage.openjarvis_api_base` (set via `/get-started` onboarding)
2. `VITE_API_BASE_URL` env var at build time
3. Default: same origin as frontend (assumes frontend served from same host as backend)

For mobile access from a different device, Bryan must set the backend URL in the frontend:
- Open React SPA on laptop → `/get-started` → "Backend URL" → enter `http://<LAN-IP>:8000`
- This config is saved in `localStorage` and used for subsequent requests from that browser.

---

*Last updated: 2026-06-21 | Sprint: Pre-Final Blocker Closure*
