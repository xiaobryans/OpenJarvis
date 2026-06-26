# Jarvis — System Status

_Last updated: 2026-06-26 (tonight's build). Branch `localhost-get-tool`._

This is the honest, current state of Jarvis: what works with real data, what's
connected, and what still needs input. No aspirational claims — only verified
facts.

---

## ✅ Working & verified (real data / real execution)

| Capability | State | How it was verified |
|---|---|---|
| Real-time awareness (time/date/day/timezone) | **Working** | `current_time` tool + per-turn system-clock injection; live chat answers correctly |
| Tool execution on live chat | **Working** | streaming chat runs the agent tool loop; tools fire (`tools_used≥1`) |
| Memory: save / recall / cross-session | **Working** | save-back + pure-Python FTS5 store; verified recall after new session |
| USER.md personal profile | **Working** | full 6014-char profile loads on BOTH paths (live chat + backend); "What is my name?" → "Bryan Aw" |
| Weather (Singapore) | **Working** | `current_weather` via wttr.in (no key); live data |
| Google Calendar (today) | **Working** | `calendar_today`; real events (deduped) |
| Gmail (unread/important) | **Working** | `gmail_important`; real unread messages |
| Slack | **Connected** | `slack_recent`; auth OK (team "Jarvis HQ"); see scope note below |
| Morning briefing | **Working (on-demand)** | `morning_briefing` tool + `daily_ops.generate_morning_briefing()`; real composite output verified |
| Overnight monitor | **Working (on-demand)** | `daily_ops.run_overnight_monitor()`; real health + memory round-trip check |
| Scheduling registration | **Configured** | `register_daily_ops()` creates cron tasks (08:00 / 03:00 SGT) on TaskScheduler |

## ⚙️ Connected with real data
- **Gmail, Google Calendar** — OAuth tokens present at `~/.openjarvis/connectors/`; real reads verified.
- **Slack** — bot token valid (`auth.test` OK). Reading channel history needs the bot to be **in** channels and the scopes `channels:read` + `channels:history` (tool reports the exact missing scope if absent).
- **Weather** — wttr.in, no credentials needed.

## ⏳ Pending — needs your input / credentials
- **Stripe** — NOT configured: no API key in any cred file AND no Stripe connector module exists. To enable: add `STRIPE_API_KEY` (restricted, read-only is fine) and a Stripe connector will need building.
- **Notion** — connector exists but NO token. To enable: add `NOTION_API_KEY` (Notion internal integration token) + share the target pages with the integration.
- **Google auto-refresh** — reads work now, but the OAuth status reader flags a missing refresh token; if Gmail/Calendar stop working when the access token expires, re-run the Google OAuth flow (`GOOGLE_OAUTH_CLIENT_SECRET` + `python -m openjarvis.connectors.google_auth`).
- **Scheduled 8am firing** — see "Scheduling" below.

## 🅿️ Parked (intentional, documented)
- **Orchestrator stack** (cos_gm / activation / hybrid / skillorchestra) — real, not on the live chat path. Parked pending the "Option A" sprint. Full spec + wiring guide: [docs/ORCHESTRATOR.md](docs/ORCHESTRATOR.md).
- **Voice pipeline** — real pipeline exists (Deepgram/Whisper STT, Deepgram/Kokoro/OpenAI TTS, wake word), macOS-only, mounted at `/v1/voice/*`. PARKED for Plan 3 (per project hard rules — not activated). To activate: install audio deps (sounddevice/pyaudio/openwakeword), grant mic permission, run end-to-end STT→brain→TTS test.

---

## Scheduling — how the briefing/monitor actually run

Two mechanisms:
1. **In-process** (`register_daily_ops`): when the Jarvis server/daemon is
   running, cron tasks fire the briefing (08:00 SGT) and monitor (03:00 SGT).
   Needs `croniter` installed for precise cron (`uv pip install croniter`);
   without it the scheduler falls back to coarse intervals.
2. **OS-level (recommended, fires even if the server is down)** — add a
   launchd/cron entry calling the CLI:
   ```
   # macOS launchd or crontab — 08:00 SGT briefing, 03:00 SGT monitor
   0 8 * * *  cd /Users/user/OpenJarvis && .venv/bin/python -m openjarvis.jarvis_os.daily_ops briefing
   0 3 * * *  cd /Users/user/OpenJarvis && .venv/bin/python -m openjarvis.jarvis_os.daily_ops monitor
   ```
Times are configurable in `~/.openjarvis/jarvis_schedule.json`.

Output locations:
- Briefings: `~/.openjarvis/briefings/latest.md` (+ timestamped copies)
- Monitor: `~/.openjarvis/monitor/latest.json` + `monitor.log`

---

## How to verify it yourself
```bash
# Briefing + monitor produce real output:
.venv/bin/python -m openjarvis.jarvis_os.daily_ops briefing
.venv/bin/python -m openjarvis.jarvis_os.daily_ops monitor

# Connector tools (real data):
.venv/bin/python -c "import openjarvis.tools; from openjarvis.core.registry import ToolRegistry; \
print(ToolRegistry.get('current_weather')().execute().content)"

# In chat, ask: 'what time is it', 'what's my calendar today', 'any important emails',
# 'what's the weather', 'what is my name', 'give me my morning briefing'.
```
