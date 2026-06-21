# PREFINAL REQUIRED BLOCKERS AND MACOS POLISH CERTIFICATION

**Branch:** `localhost-get-tool`
**Updated:** 2026-06-22

---

## Blocker Status (Pre-Final Cutover)

| Blocker | Classification | Status |
|---------|----------------|--------|
| Gmail OAuth | Code fix complete; token live | `CLOSED` |
| Calendar OAuth | Code fix complete; token live | `CLOSED` |
| GitHub MacBook-off continuity (gho_ token) | Code fix: gho_ accepted | `CLOSED` |
| GITHUB_TOKEN from cloud-keys.env | Code fix: env loading updated | `CLOSED` |
| Rust memory bridge | Active via `uv run`; packaged unverified | `CLOSED_CLI_ONLY` |
| Slack bot/channel | Live | `CLOSED` |
| Slack xoxp / DM history | Env fallback added; is_connected=True | `CLOSED` |
| Mobile LAN access | Proven; /mobile page loads | `CLOSED` |
| MacBook-off status public endpoint | Auth exemption in place; 200 no-auth | `CLOSED` |
| Unified cockpit UI | Installed app rebuilt Jun 22 | `CLOSED_PENDING_BRYAN_VERIFY` |
| macOS Screen/System Audio permission | 5min cache, lazy checks only | `MACOS_PERMISSION_PROMPT_POLISH_CLOSED` |
| Voice / wake / TTS | PARKED | Not a blocker |
| Apple signing / updater | PARKED | Not a blocker |

---

## macOS Permission Prompt Polish

**Classification:** `MACOS_PERMISSION_PROMPT_POLISH_CLOSED`

Evidence:
- `_SCREEN_RECORDING_CACHE_TTL = 300.0` in `desktop_operator.py`
- No background thread polls for permissions
- Permission checks only triggered by tool invocations (lazy)
- At most one TCC prompt per 5 minutes per permission type
- `tccutil reset` NOT run (not needed, not safe)

---

## Remaining Manual Verifications (Bryan)

1. Open `/Applications/OpenJarvis.app` → confirm new cockpit UI visible
2. Refresh `http://192.168.1.16:8000/mobile` on iPhone → confirm AVAILABLE
3. `curl -i http://127.0.0.1:8000/v1/continuity/macbook-off-status` → 200
4. `curl -i -X POST http://127.0.0.1:8000/v1/continuity/snapshot` → 401

Once all 4 confirm: proceed to final hostile/lazy-user cutover certification.

---

*Updated: 2026-06-22 | Sprint: Pre-Final Blocker Closure*
