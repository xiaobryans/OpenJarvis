# Bryan Manual Actions Required

**Updated:** 2026-06-22
**Branch:** `localhost-get-tool`

---

## 1. Gmail OAuth (PRIORITY — blocks Gmail + Calendar)

```bash
cd /Users/user/OpenJarvis
python3 -m openjarvis.connectors.gmail oauth-setup
```
- A browser window opens to Google consent page.
- Click **Allow**.
- Token is saved automatically to `~/.openjarvis/connectors/`.
- Validate: `python3 -m openjarvis.connectors.gmail status`

**Note:** This single OAuth flow authorizes Gmail AND Calendar (same Google provider, same token file).

---

## 2. Calendar OAuth (after Gmail)

Calendar shares the Google token. After Gmail OAuth completes, check:
```bash
python3 -m openjarvis.connectors.gcalendar status
```

If Calendar still shows not connected:
```bash
python3 -m openjarvis.connectors.gcalendar oauth-setup
```

---

## 3. Physical Mobile Screenshot

1. Ensure backend is running:
   ```bash
   cd /Users/user/OpenJarvis
   python3 -m openjarvis.cli serve --host 0.0.0.0 --port 8000
   ```
2. Connect iPhone to same Wi-Fi as MacBook.
3. Open Safari → `http://192.168.1.16:8000/mobile`
4. Screenshot confirms mobile proof. Share or save as evidence.

---

## 4. Apple Signing / Developer Certificate

**Cannot be code-fixed.** External steps:
1. Enroll in Apple Developer Program ($99/year): https://developer.apple.com/programs/
2. Generate "Developer ID Application" certificate in Xcode Preferences → Accounts → Manage Certificates.
3. Certificate installs in keychain automatically after enrollment.
4. Update `frontend/src-tauri/tauri.conf.json` `signingIdentity` to match.
5. Re-run `npm run build:tauri:release`.

---

## 5. Slack DM History Sync

**Platform constraint.** Only `xoxb` bot token available. For DM history sync:
1. Create/update Slack app with User Token OAuth flow.
2. Add scopes: `im:history`, `users:read`, `channels:history`.
3. Complete user OAuth to get `xoxp` token.
4. Add `SLACK_USER_TOKEN=xoxp-...` to `.env`.

---

## 6. Voice Wake Word (Optional — parked)

Wake word engine is not configured. Does NOT block text/mobile cutover.

To enable (optional):
```bash
pip install openwakeword
# or obtain pvporcupine API key at https://picovoice.ai/
```

---

## 7. Rust Memory Bridge (Optional — parked)

Native memory backend requires Rust build:
```bash
uv run maturin develop -m rust/crates/openjarvis-python/Cargo.toml
# Requires rustc >= 1.88
```

---

## Summary Priority Order

1. ✅ Backend running: `python3 -m openjarvis.cli serve --host 0.0.0.0 --port 8000`
2. 🔴 **Gmail OAuth** (enables Gmail + Calendar)
3. 🔴 **Mobile screenshot** (physical proof)
4. 🟡 Apple signing (external enrollment)
5. 🟡 Slack DM xoxp (Slack platform)
6. ⚪ Voice wake word (optional/parked)
7. ⚪ Rust memory bridge (optional/parked)
