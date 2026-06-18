# OpenJarvis Rollback Procedure

This document describes how to safely roll back OpenJarvis to a previous version
after a bad release or a failed update.

**Governance:**
- No destructive actions without explicit operator confirmation.
- No config deletion — always back up before overwriting.
- Rollback is always to a known-good commit, not a forced reset.

---

## 1. Identify the Target

### Find the previous good commit

```sh
git log --oneline -10
```

Or use the base HEAD recorded in the certification doc:

```sh
cat docs/US14_CERTIFICATION.md | grep "Base HEAD"
cat docs/US14_RELEASE_DISTRIBUTION.md | grep "Base HEAD"
```

### Find the previous good tag (if tagged)

```sh
git tag --sort=-creatordate | head -5
```

---

## 2. Back Up Current Config

**Before any rollback, preserve the current user config:**

```sh
# macOS app config
cp -r ~/Library/Application\ Support/com.openjarvis.desktop \
       ~/Library/Application\ Support/com.openjarvis.desktop.backup-$(date +%Y%m%d)

# Local .env (if present)
cp .env .env.rollback-$(date +%Y%m%d) 2>/dev/null || true
```

---

## 3. Roll Back the App (Desktop)

### Option A — Re-install previous DMG

1. Download the previous DMG from:
   `https://github.com/open-jarvis/OpenJarvis/releases`
2. Open the DMG and drag to `/Applications/` (overwrite prompt will appear).
3. Confirm: open `OpenJarvis.app` → Settings → About → verify version.

### Option B — Build from previous commit

```sh
# Check out the previous good commit
git checkout <previous-commit-sha>

# Build frontend
cd frontend && npm run build && cd ..

# Build Tauri app (macOS)
cd frontend && npm run tauri build && cd ..

# Install the resulting .app from:
# frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app
```

---

## 4. Roll Back the Backend (Python / Server)

```sh
# Check out the previous good commit
git checkout <previous-commit-sha>

# Re-sync dependencies
uv sync

# Restart the server
jarvis serve --port 8000
```

---

## 5. Roll Back via Git (Source Only)

If no binary is available and you are running from source:

```sh
# Verify current state
git rev-parse HEAD
git status --short

# Create a rollback branch from the last good state
git checkout -b rollback/$(date +%Y%m%d) <previous-commit-sha>

# Verify the target commit is the expected base
git rev-parse HEAD

# Re-run validation before running
python3 -m py_compile src/openjarvis/server/doctor_routes.py
.venv/bin/python3 -m pytest tests/workbench/ -q --tb=short
```

---

## 6. Config Migration Rollback

If a config schema changed between versions and the rollback breaks settings:

```sh
# Desktop app config location (macOS)
ls ~/Library/Application\ Support/com.openjarvis.desktop/

# Restore from backup
cp -r ~/Library/Application\ Support/com.openjarvis.desktop.backup-<date> \
       ~/Library/Application\ Support/com.openjarvis.desktop
```

For conversation history rollback (browser/web):
1. Open Settings > Data > Import.
2. Select your `.json` export file from before the release.

---

## 7. Queue Recovery After Rollback

If jobs were running during the rollback:

```sh
# Check stalled jobs via API
curl -s http://localhost:8000/v1/doctor | python3 -m json.tool | grep -A5 job_queue
```

Stalled jobs can be cleared by restarting the server — they will be re-queued on next run.
No data is lost; the job queue is append-only.

---

## 8. Verify Rollback Success

```sh
# Check version
curl -s http://localhost:8000/v1/version | python3 -m json.tool

# Check readiness
curl -s http://localhost:8000/v1/readiness | python3 -m json.tool | grep verdict

# Run targeted tests
.venv/bin/python3 -m pytest tests/workbench/ tests/test_us12_polish.py -q --tb=short
```

Expected: `verdict` is `ready` or `warn`, tests pass, version matches the rollback target.

---

## Known Rollback Limitations

| Limitation | Reason | Mitigation |
|---|---|---|
| Conversation history may be lost if cleared between versions | Browser localStorage / app storage | Always export before upgrading: Settings > Data > Export |
| macOS Gatekeeper re-prompt on version change | Ad-hoc signing resets trust on re-install | Right-click > Open, or `xattr -dr com.apple.quarantine` |
| Queue jobs in `running` state may be abandoned | No cross-version job migration | Restart server after rollback; jobs will re-queue |
