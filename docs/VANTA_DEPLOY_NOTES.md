# VANTA deploy notes — Railway (3H), Notion (3I), WhatsApp (3J)

_Investigated this sprint. No deploy was triggered — config diagnosis + the exact
steps Bryan needs to take._

## 3H — Railway deployment

**Current config (structurally sound):**
- `railway.toml` — Dockerfile builder, `healthcheckPath = /health`, 120s timeout, restart on failure.
- `Dockerfile` — `python:3.12-slim`, installs `.[server,scheduler]`, runs `uvicorn openjarvis.server.railway_app:app`.
- `railway_app.py` — exposes `GET /health` → `{ok: true}` (healthcheck will pass once the app boots) and mounts the WhatsApp + briefing routers.
- `server` and `scheduler` extras both exist in `pyproject.toml`.
- `Procfile` (`web: uvicorn ... railway_app:app`) is **ignored** under the Dockerfile builder — harmless but dead; can be deleted to avoid confusion.

**Most likely failure cause (ranked):**
1. **`auto-browser-client>=1.2.1` in the `server` extra.** The Dockerfile installs the full `server` extra, which pulls `auto-browser-client`. The lean webhook does **not** need it, and a heavy/uncommon wheel like this is the most probable cause of `pip install` failing on the slim image (no wheel for the platform, or missing system build deps). **Recommended fix:** add a minimal `webhook` extra and install that instead of `server`:

   ```toml
   # pyproject.toml -> [project.optional-dependencies]
   webhook = ["fastapi>=0.110", "uvicorn>=0.30", "pydantic>=2.0",
              "python-multipart>=0.0.9", "httpx>=0.27"]
   ```
   ```dockerfile
   # Dockerfile
   RUN pip install --no-cache-dir ".[webhook,scheduler]"
   ```
   ⚠️ Confirm the message-processing path still imports (it lazily imports
   `LeanOrchestrator` + `cloud_router` when a message arrives). If those need an
   extra dep at runtime, add it to the `webhook` extra. **This must be confirmed
   with one Railway build** before relying on it — that's why it isn't applied blind here.

2. **Startup crash from a missing env var.** `railway_app` startup loads env and a memory backend (wrapped in try/except), but if any required token is missing the app may boot unhealthy and the healthcheck times out → deploy marked failed. Ensure the Railway service has the env vars the webhook needs (see 3J).

3. **Healthcheck timeout** if cold-start import is slow. `/health` is lightweight, so this is unlikely unless deps are heavy (see #1).

**To confirm the exact cause, paste the Railway *build* and *deploy* logs** — the config itself is valid, so the failure is almost certainly in the `pip install` step (#1).

## 3I — Notion (verified, read-only)

- `NOTION_API_KEY` is present and **valid**: `GET /v1/users/me` → 200, bot **"Jarvis Integration"** in workspace **"Bryan Aw's Space"**.
- `POST /v1/search` → 200 but **0 objects** — the integration is authenticated but **no pages/databases are shared with it yet**.

**Action for Bryan (one-time, in Notion):** open each page/database VANTA should access → **••• menu → Connections → add "Jarvis Integration"** (or share the top-level page so children inherit). After sharing, `/v1/search` will return those objects and read/write will work. No code or auth fix needed.

## 3J — WhatsApp

- Webhook handler exists: `POST /v1/whatsapp/webhook` (`whatsapp_routes.py`), included in `railway_app`. It sends replies via Twilio (`_twilio_send`) and processes messages through `LeanOrchestrator`.
- **Twilio sandbox path (POST-only): ready.** Once Railway is up:
  1. Deploy succeeds → note the public URL `https://<app>.up.railway.app`.
  2. In the **Twilio WhatsApp sandbox**, set the "When a message comes in" webhook to `https://<app>.up.railway.app/v1/whatsapp/webhook` (HTTP POST).
  3. Set Railway env vars: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` (and `OPENAI_API_KEY` for the brain).
  4. Join the sandbox from your phone and message it to test.
- **Meta WhatsApp Cloud API path (if used instead of Twilio): needs a GET verify endpoint.** Meta verifies a webhook with a `GET` `hub.mode`/`hub.challenge`/`hub.verify_token` handshake. The current route is POST-only, so Meta verification would fail. If Bryan is on Meta Cloud API (not Twilio), add a `GET /v1/whatsapp/webhook` that echoes `hub.challenge` when `hub.verify_token` matches `WHATSAPP_VERIFY_TOKEN`. Twilio does not need this.

**Net:** WhatsApp webhook code is correct for the Twilio sandbox and goes live the moment Railway is fixed and the env vars + Twilio webhook URL are set. Only add the GET verify handler if switching to Meta Cloud API.
