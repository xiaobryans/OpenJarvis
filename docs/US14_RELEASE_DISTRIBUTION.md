# US14 — Release & Distribution Hardening

**Status: ACCEPT (founder-local scope)**
**V1 Scope: macOS local/founder packaged app — NOT public distribution**
**Branch:** localhost-get-tool
**Base HEAD:** dc94532ee3ef4a53edc3123b0566ff80c3fd2b01

---

## Sprint 2 Update — Packaging / Release Readiness (Full No-Gap Sprint 2 of 4)

**Sprint 2 HEAD:** 3ba03e02 (Sprint 1 UI polish base) + Sprint 2 changes
**Sprint 2 scope:** Packaging / release readiness for no-gap progression

### Full No-Gap Status

| Sprint | Status |
|---|---|
| Sprint 1: UI polish | ACCEPTED — committed at 3ba03e02 |
| Sprint 2: Packaging / release | IN PROGRESS — this sprint |
| Sprint 3: Voice safety sprint | PENDING — separate required sprint |
| Sprint 4: 30-task no-gap suite | PENDING |
| **Full no-gap verdict** | **HOLD — all four sprints required** |

### Sprint 2 Changes

| Item | Status | Evidence |
|---|---|---|
| Version alignment (pyproject.toml ↔ package.json ↔ tauri.conf.json ↔ Cargo.toml) | DONE | All aligned to 1.0.2 via `bump-desktop-version.sh` |
| Founder-local validation script | DONE | `scripts/release-local.sh` — precheck, version gate, artifact version check, build, health check |
| Artifact version gate | DONE | Script fails with `STALE_OR_MISSING_PACKAGE_ARTIFACT` if bundle version ≠ expected version |
| `installed_stale` reporting | DONE | `/Applications/OpenJarvis.app` reported as `installed_stale` if version ≠ expected — not as pass |
| `RELEASE_CHECKLIST.md` gaps | DONE | Added: no-gap status gate, artifact version gate step, backend runtime, auto-update caveat, voice gate, company org item |
| Stale closure labels replaced | DONE | All vague backlog labels replaced with explicit statuses: `REQUIRED_FOR_PUBLIC_RELEASE`, `REQUIRED_FOR_NO_GAP_JARVIS` |
| Auto-update endpoint status | REQUIRED_FOR_PUBLIC_RELEASE | Endpoint in tauri.conf.json unverified — no public release published |
| Voice safety gate | REQUIRED_FOR_NO_GAP_JARVIS | Checklist and script both gate voice as separate sprint — not claimed here |
| Company org / manager-worker roster | REQUIRED_FOR_NO_GAP_JARVIS | Tracked in checklist and script — not started |
| OMNIX framing | CONFIRMED | All release docs use Jarvis framing; OMNIX appears only as project context |
| Safe founder-local build wrapper | DONE | `./scripts/build-local.sh` — wraps `build:tauri:local`, records /Applications binary SHA256 + plist SHA256 + version + mtime pre/post; any change without `--allow-applications-update` exits non-zero |
| Raw `build:tauri:local` unguarded | NOT ACCEPTED AS VALIDATION PATH | Raw command has no /Applications guard; must not be used as accepted validation path |
| Public/updater build command | REQUIRED_FOR_PUBLIC_RELEASE | `npm run build:tauri:release` exits 1 without `TAURI_SIGNING_PRIVATE_KEY` |
| /Applications mutation root cause | DOCUMENTED | macOS syspolicyd/LaunchServices rescans /Applications when new binary with same bundle ID is codesigned, touching mtime and/or content |
| /Applications content mutation guard | DONE | binary SHA256 or plist SHA256 or version change → `UNAUTHORIZED_APPLICATIONS_MODIFICATION` (exit 1) |
| /Applications mtime-only touch guard | DONE | mtime change with no content change → `UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH` (exit 1); mtime changes are not silently accepted |
| /Applications treated as read-only | DONE | Any change — content or mtime — requires explicit `--allow-applications-update`; stale reported as `installed_stale`, never pass |
| Fresh v1.0.2 artifact | CONFIRMED | `./scripts/build-local.sh` exits 0; v1.0.2 artifact produced; /Applications binary SHA, plist SHA, version, and mtime all unchanged |

### Auto-Update Endpoint Status

| Item | Status | Detail |
|---|---|---|
| Updater plugin active | CONFIGURED | `tauri-plugin-updater`, `createUpdaterArtifacts: true` |
| Endpoint URL | CONFIGURED | `github.com/open-jarvis/OpenJarvis/releases/download/desktop-latest/latest.json` |
| Public release published | UNVERIFIED | No public GitHub release exists — updater will fail silently |
| Signed update artifact | NOT AVAILABLE | Requires Apple Developer ID + public release. Status: REQUIRED_FOR_PUBLIC_RELEASE |
| Action for Bryan | — | Publish a signed release tag when public distribution is needed (post no-gap) |

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
| Public Apple Developer ID notarization | REQUIRED_FOR_PUBLIC_RELEASE | Ad-hoc signing is correct for founder-local scope. Notarization is required only for public App Store / public download distribution. Bryan does not currently have an Apple Developer Program account. | Enroll at developer.apple.com when public distribution is needed. |
| iOS/Android packaging | NOT_APPLICABLE | Not in scope for V1 desktop release. | — |
| Windows code signing | REQUIRED_FOR_PUBLIC_RELEASE | V1 scope is macOS local/founder app. Windows distribution not currently planned. No Windows EV cert needed for founder-local. | Add Windows signing when Windows public distribution is required. |
| Build-time `BUILD_DATE` injection | PARTIAL | No CI env injection exists. `queried_at` is runtime. | Add `VITE_BUILD_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)` to the CI build step. |
| Auto-update endpoint | REQUIRED_FOR_PUBLIC_RELEASE | Endpoint configured in `tauri.conf.json` but no public GitHub release exists. Updater will fail silently until a signed public release is published. | Publish signed release tag when public distribution is ready. |
| Voice safety certification | REQUIRED_FOR_NO_GAP_JARVIS | Voice safety sprint (Sprint 3) is a separate required sprint. Not covered by packaging sprint. | Complete Sprint 3 voice safety sprint independently. |
| Company org / manager-worker roster | REQUIRED_FOR_NO_GAP_JARVIS | Manager-worker agent roster must be completed before full no-gap certification. Not started. | Implement company org sprint after voice safety sprint. |

---

## Release Verdict

**ACCEPT (founder-local scope only)**

All repo-controlled V1 release hardening items are DONE for the macOS local/founder packaged app target.
- Ad-hoc signing is correct for V1 local/founder distribution.
- Public Apple Developer ID notarization: `REQUIRED_FOR_PUBLIC_RELEASE` (not a founder-local blocker).
- Windows signing: `REQUIRED_FOR_PUBLIC_RELEASE` (Windows distribution is out of V1 scope).
- Auto-update endpoint: `REQUIRED_FOR_PUBLIC_RELEASE` (configured but unverified — no public release exists).
- Voice safety sprint: `REQUIRED_FOR_NO_GAP_JARVIS` (separate Sprint 3 — not covered here).
- Company org / manager-worker roster: `REQUIRED_FOR_NO_GAP_JARVIS` (not started — separate item).
- Full no-gap verdict: HOLD until all required sprints and items pass.
- No secrets in artifact. No deploy performed. No production changes.

---

## Related Documents

- `docs/RELEASE_CHECKLIST.md` — step-by-step release procedure
- `docs/ROLLBACK.md` — rollback procedure
- `CHANGELOG.md` — release notes
- `docs/US14_CERTIFICATION.md` — prior US14 Workbench sprint certification (preserved, not overwritten)
