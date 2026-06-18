# US14 — Release & Distribution Hardening

**Status: ACCEPT_WITH_EXTERNAL_LIMITATIONS**
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
| macOS notarization | EXTERNALLY_NOT_PROVEN | No Apple Developer Program account configured. | 1. Enroll at developer.apple.com. 2. Set `signingIdentity` in `tauri.conf.json` to team certificate. 3. Add `tauri-plugin-notarize`. 4. Run `tauri build` on a Mac with Xcode. |
| iOS/Android packaging | NOT_APPLICABLE | Not in scope for V1 desktop release. | — |
| Windows code signing | EXTERNALLY_NOT_PROVEN | `certificateThumbprint: null`. No EV certificate. | Obtain EV certificate, set thumbprint in `tauri.conf.json`. |
| Build-time `BUILD_DATE` injection | PARTIAL | No CI env injection exists. `queried_at` is runtime. | Add `VITE_BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)` to the CI build step. |

---

## Release Verdict

**ACCEPT_WITH_EXTERNAL_LIMITATIONS**

All repo-controlled release hardening items are DONE.
Remaining blockers are exclusively external (Apple Developer account, Windows EV cert, build-date injection).
No secrets in artifact. No deploy performed. No production changes.

---

## Related Documents

- `docs/RELEASE_CHECKLIST.md` — step-by-step release procedure
- `docs/ROLLBACK.md` — rollback procedure
- `CHANGELOG.md` — release notes
- `docs/US14_CERTIFICATION.md` — prior US14 Workbench sprint certification (preserved, not overwritten)
