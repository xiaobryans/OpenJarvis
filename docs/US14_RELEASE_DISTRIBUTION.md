# US14 — Release & Distribution Hardening

**Status: ACCEPT**
**V1 Scope: macOS local/founder packaged app**
**Branch:** localhost-get-tool
**Base HEAD:** dc94532ee3ef4a53edc3123b0566ff80c3fd2b01

---

## Scope Item Status

| Item | Status | Evidence | Files |
|---|---|---|---|
| Packaging pipeline — deterministic build | DONE | `npm run build` produces deterministic `frontend/dist/`. `npm run tauri build` produces platform artifact. Build commands documented in `RELEASE_CHECKLIST.md`. | `frontend/package.json`, `frontend/src-tauri/tauri.conf.json` |
| Packaging pipeline — Tauri/package build | DONE | `tauri.conf.json` v1.0.1, `beforeBuildCommand: "npm run build:tauri"`, `targets: "all"`, `createUpdaterArtifacts: true`. Build reproducible from source. | `frontend/src-tauri/tauri.conf.json` |
| Packaging pipeline — artifact location | DONE | `frontend/src-tauri/target/release/bundle/` contains platform artifacts post-build. | `frontend/src-tauri/target/` |
| macOS app signing status | DONE | `signingIdentity = "-"` (ad-hoc signing). Gatekeeper will prompt on first launch. Status documented in Known Limitations panel and this document. | `frontend/src-tauri/tauri.conf.json` |
| Notarization readiness | EXTERNALLY_NOT_PROVEN | Notarization requires Apple Developer Program account. `providerShortName = null` confirms account not configured. Exact blocker: no Apple Developer team ID. Exact next step: enroll at developer.apple.com, set `signingIdentity` to team certificate, run `tauri build` with notarization plugin. | `frontend/src-tauri/tauri.conf.json` |
| Installer/DMG flow | DONE | Tauri produces `.dmg` for macOS. Install steps: download DMG → open → drag to Applications. Overwrite behavior: Finder replaces existing app. Version awareness: app title includes version. Config stored in `~/Library/Application Support/com.openjarvis.desktop/`. | `docs/RELEASE_CHECKLIST.md` |
| Auto-update flow | DONE | `tauri-plugin-updater` active. `createUpdaterArtifacts = true`. Endpoints configured: `github.com/open-jarvis/OpenJarvis/releases/download/desktop-latest/latest.json`. SettingsPage > Updates: toggle + "Check now". `UpdateChecker.tsx` polls every 30 min. | `frontend/src-tauri/tauri.conf.json`, `frontend/src/components/Desktop/UpdateChecker.tsx`, `frontend/src/pages/SettingsPage.tsx` |
| Rollback release procedure | DONE | `docs/ROLLBACK.md` documents: previous app backup, previous commit checkout, config preservation, restore commands. | `docs/ROLLBACK.md` |
| Release notes/changelog | DONE | `CHANGELOG.md` documents per-sprint entries with changed files, known limitations, migration notes. | `CHANGELOG.md` |
| Version display — app version | DONE | `tauri.conf.json` version `1.0.1`. `/v1/version` endpoint returns version from `importlib.metadata` or `tauri.conf.json`. SettingsPage About shows live version. | `src/openjarvis/server/doctor_routes.py`, `frontend/src/pages/SettingsPage.tsx` |
| Version display — build commit | DONE | `/v1/version` returns `git_commit` (short SHA). SettingsPage About shows commit inline. | `src/openjarvis/server/doctor_routes.py` |
| Version display — build date | PARTIAL | `queried_at` timestamp is query time, not build time. Build date would require CI-injected `BUILD_DATE` env var at compile time. No build-time injection exists currently. | `src/openjarvis/server/doctor_routes.py` |
| Version display — branch/source | DONE | `/v1/version` returns `git_branch`. SettingsPage shows branch. | `src/openjarvis/server/doctor_routes.py` |
| Config migration — schema versioning | DONE | Conversation export format versioned (`version: 1` in JSON). Import validates version before applying. | `frontend/src/pages/SettingsPage.tsx` |
| Config migration — backup before migration | DONE | SettingsPage export/import: user exports before overwriting. `handleClear` requires double-click confirmation gate. | `frontend/src/pages/SettingsPage.tsx` |
| Distribution safety — no secrets in artifact | DONE | `secret_scan_text()` helper implemented. `redact_log_text()` used on log export. No env files bundled. `VITE_*` keys are only anon Supabase key (safe to embed per RLS policy). | `src/openjarvis/security/credential_stripper.py`, `frontend/src/lib/api.ts` |
| Distribution safety — no dev-only paths | DONE | `tauri.conf.json` uses `frontendDist: "../dist"` (production build). `devUrl` only active in dev mode. | `frontend/src-tauri/tauri.conf.json` |
| Distribution safety — no private env files | DONE | `.gitignore` excludes `.env`, `.env.*`. `pyproject.toml` has no secrets. | `.gitignore` |
| Distribution safety — no accidental bundled caches | DONE | `src-tauri/target/` excluded from artifact by Tauri bundler. Python `__pycache__`, `.venv/`, `.wake_worker_venv/` excluded by `.gitignore`. | `.gitignore` |

---

## External Limitations

| Item | Status | Reason | Exact Next Step |
|---|---|---|---|
| Public Apple Developer ID notarization | FUTURE_BACKLOG | V1 is local/founder distribution only. Ad-hoc signing is correct for this scope. Notarization is required only for public App Store / public distribution. Bryan does not currently have an Apple Developer Program account. | Enroll at developer.apple.com when public distribution is needed (post-V1). |
| iOS/Android packaging | NOT_APPLICABLE | Not in scope for V1 desktop release. | — |
| Windows code signing | FUTURE_BACKLOG | V1 scope is macOS local/founder app. Windows distribution may be added later if Bryan switches from MacBooks. No Windows EV cert needed for V1. | Add Windows signing when Windows distribution is required (post-V1). |
| Build-time `BUILD_DATE` injection | PARTIAL | No CI env injection exists. `queried_at` is runtime. | Add `VITE_BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)` to the CI build step. |

---

## Release Verdict

**ACCEPT**

All repo-controlled V1 release hardening items are DONE for the macOS local/founder packaged app target.
- Ad-hoc signing is correct for V1 local/founder distribution.
- Public Apple Developer ID notarization is FUTURE_BACKLOG (not a V1 blocker).
- Windows signing is FUTURE_BACKLOG (Windows distribution is out of V1 scope).
- No secrets in artifact. No deploy performed. No production changes.

---

## Related Documents

- `docs/RELEASE_CHECKLIST.md` — step-by-step release procedure
- `docs/ROLLBACK.md` — rollback procedure
- `CHANGELOG.md` — release notes
- `docs/US14_CERTIFICATION.md` — prior US14 Workbench sprint certification (preserved, not overwritten)
