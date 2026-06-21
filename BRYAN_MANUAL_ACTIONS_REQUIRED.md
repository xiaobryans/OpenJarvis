# BRYAN MANUAL ACTIONS REQUIRED

**Branch:** `localhost-get-tool`
**Updated:** 2026-06-22 (Pre-Final Blocker Closure Sprint)

These are actions only Bryan can take. Sorted by priority.

---

## REQUIRED BEFORE FINAL CUTOVER CERTIFICATION

### 1. Verify MacBook-off continuity status on iPhone

After server restart:

```bash
# Start server (memory active):
cd /Users/user/OpenJarvis
uv run python -m openjarvis.cli serve --host 0.0.0.0 --port 8000
```

Then on iPhone:
1. Open Safari → `http://192.168.1.16:8000/mobile`
2. Confirm MacBook-off continuity shows **AVAILABLE** (not BLOCKED)
3. If still BLOCKED: check `gh auth status` for `gist` scope

### 2. Verify new OpenJarvis.app cockpit UI

1. Open `/Applications/OpenJarvis.app`
2. Confirm: **central orb + command cards visible** (not old sidebar/voice page)
3. Confirm: **no persistent sidebar** on the root page
4. Confirm: Settings gear icon (⚙️) in top-right opens settings overlay
5. Confirm: `/classic` route accessible for legacy pages

### 3. Confirm GITHUB_TOKEN has gist scope

```bash
gh auth status
# Look for "gist" in the scopes list
# If gist scope missing: gh auth refresh -s gist
```

---

## REQUIRED FOR GMAIL / CALENDAR (already done — verify only)

### 4. Confirm Gmail OAuth token is live

```bash
cd /Users/user/OpenJarvis
python3 -c "
from openjarvis.connectors.gmail import GmailConnector
c = GmailConnector()
print('Gmail is_connected:', c.is_connected())
"
```
Expected: `Gmail is_connected: True`

### 5. Confirm Calendar OAuth token is live

```bash
cd /Users/user/OpenJarvis
python3 -c "
from openjarvis.connectors.gcalendar import GCalendarConnector
c = GCalendarConnector()
print('Calendar is_connected:', c.is_connected())
"
```
Expected: `Calendar is_connected: True`

---

## PARKED — NO ACTION NEEDED NOW

### Voice / TTS / Wake Word
- PARKED until voice sprint
- Text input fallback is live

### Apple Developer Signing / Updater
- PARKED until Apple Developer enrollment completes
- Ad-hoc signed build installed at `/Applications/OpenJarvis.app`
- No notarization = Gatekeeper may prompt on first open; right-click → Open to bypass

---

## MANUAL VALIDATION COMMANDS

```bash
# MacBook-off status (should return 200, not 401):
curl -i http://127.0.0.1:8000/v1/continuity/macbook-off-status

# Write route still auth-gated (should return 401):
curl -i -X POST http://127.0.0.1:8000/v1/continuity/snapshot

# Connectors live:
curl -s http://127.0.0.1:8000/v1/connectors | python3 -m json.tool
```

---

*Next step after manual verification: run final hostile/lazy-user cutover certification.*
