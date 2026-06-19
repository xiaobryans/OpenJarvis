# OpenJarvis Release Checklist

> **Scope: FOUNDER-LOCAL PACKAGED APP**
> This checklist covers local/founder distribution only.
> Public distribution, Apple Developer ID notarization, and auto-update release
> infrastructure are explicitly NOT ready. See Known Limitations below.

> **No-Gap Status: HOLD**
> Full no-gap Jarvis certification requires all required items to pass:
> - ~~Sprint 1: UI polish~~ — accepted and committed
> - **Sprint 2: Packaging / release** — this sprint (in progress)
> - Sprint 3: Voice safety sprint — `REQUIRED_FOR_NO_GAP_JARVIS` — separate sprint, not covered here
> - Sprint 4: 30-task no-gap certification suite — `REQUIRED_FOR_NO_GAP_JARVIS`
> - Company org / manager-worker roster — `REQUIRED_FOR_NO_GAP_JARVIS` — not started
>
> Voice is NOT covered by this checklist. Voice safety sprint is a separate required sprint.
> Company org / manager-worker roster must be completed before final no-gap certification.

> **Auto-Update: UNVERIFIED**
> `tauri.conf.json` contains updater endpoints pointing to GitHub releases.
> No public GitHub release exists. Auto-update will silently fail until a signed
> public release is published. This is an expected limitation for founder-local scope.

Use this checklist before tagging and publishing a new release.

---

## Pre-Release Gates

### 1. Branch & Commit

- [ ] On the release branch (e.g. `localhost-get-tool` or `main`)
- [ ] `git status --short` is clean (no uncommitted changes)
- [ ] `git diff --check` passes (no trailing whitespace)
- [ ] `git rev-parse HEAD` matches expected base

### 2. Version Alignment

Run `scripts/bump-desktop-version.sh` to ensure all three version files agree before tagging:

```sh
# Check current versions
grep '^version' pyproject.toml
node -e "console.log(require('./frontend/package.json').version)"
python3 -c "import json; print(json.load(open('frontend/src-tauri/tauri.conf.json'))['version'])"

# Bump all three if mismatched
./scripts/bump-desktop-version.sh <version>
```

- [ ] `pyproject.toml`, `frontend/package.json`, and `frontend/src-tauri/tauri.conf.json` all match
- [ ] `frontend/src-tauri/Cargo.toml` also matches (bumped by the script)

### 3. Python Validation

```sh
# Compile-check all changed server/workbench modules
python3 -m py_compile \
  src/openjarvis/server/notify_routes.py \
  src/openjarvis/server/workbench_routes.py \
  src/openjarvis/server/doctor_routes.py \
  src/openjarvis/workbench/checkpoint.py \
  src/openjarvis/workbench/coding_manager.py \
  src/openjarvis/workbench/cost_ledger.py \
  src/openjarvis/workbench/job_queue.py \
  src/openjarvis/workbench/model_router.py \
  src/openjarvis/workbench/event_log.py

# Run all targeted tests
.venv/bin/python3 -m pytest tests/workbench/ tests/test_us12_polish.py tests/test_us13_certification.py tests/test_us14_release.py -q --tb=short
```

### 3. Frontend Validation

```sh
cd frontend && npm run build
```

- [ ] Build completes with exit code 0
- [ ] No new type errors
- [ ] Chunk-size warnings are existing (not new regressions)

### 4. Secret Scan

- [ ] No secrets in `frontend/dist/` (no API keys, tokens, or private keys)
- [ ] No `.env` files included in the artifact
- [ ] Run a quick manual grep:
  ```sh
  grep -rE "sk-[a-zA-Z0-9_-]{20,}|AKIA[0-9A-Z]{16}|ghp_[a-zA-Z0-9]{36}" frontend/dist/ || echo "CLEAN"
  ```

### 5. Version Bump (if applicable)

- [ ] `pyproject.toml` version updated (e.g. `1.0.2` → `1.0.3`)
- [ ] `frontend/src-tauri/tauri.conf.json` version matches
- [ ] `CHANGELOG.md` updated with this release's changes

### 6. Doctor/Readiness Check

```sh
# Requires running server
curl -s http://localhost:8000/v1/readiness | python3 -m json.tool | grep verdict
curl -s http://localhost:8000/v1/version | python3 -m json.tool
```

- [ ] `verdict` is `ready` or `warn` (not `hold` or `unsafe`)
- [ ] `git_commit` matches current HEAD
- [ ] `git_branch` is the release branch

---

## Tauri / Desktop Build (macOS)

> Requires: Rust toolchain, Xcode CLT, Node 18+, cargo

### Founder-Local Build — Safe Wrapper (canonical command)

**Always use the safe wrapper for founder-local builds.** It records `/Applications` content
checksums before and after the build and fails with `UNAUTHORIZED_APPLICATIONS_MODIFICATION`
if content changes without explicit authorization.

```sh
./scripts/build-local.sh
```

> `build-local.sh` wraps `npm run build:tauri:local` (`--bundles app`, no DMG, no updater signing).
> Records `/Applications/OpenJarvis.app` binary SHA256 + Info.plist SHA256 pre/post build.
> **Exits 0 only if build succeeds AND /Applications content is unchanged.**
> **Exits 1 with `UNAUTHORIZED_APPLICATIONS_MODIFICATION` if /Applications content changes.**

Root-cause context:
> When `npm run build:tauri:local` compiles a NEW binary and codesigns it, macOS's security
> infrastructure (syspolicyd/LaunchServices) may rescan the installed copy in `/Applications`
> that shares the same bundle ID (`com.openjarvis.desktop`), updating its mtime and/or content.
> The wrapper detects ALL changes — binary SHA256, Info.plist SHA256, version string, and mtime.
> Any change without `--allow-applications-update` exits non-zero:
> - Content change → `UNAUTHORIZED_APPLICATIONS_MODIFICATION`
> - mtime-only change → `UNAUTHORIZED_APPLICATIONS_METADATA_TOUCH`
> No change is silently passed. mtime changes are not accepted without explicit authorization.

To allow `/Applications` content change (explicit authorization required):
```sh
./scripts/build-local.sh --allow-applications-update
```

To build AND install to `~/Applications/` (does not touch `/Applications`):
```sh
./scripts/build-local.sh --install
```

**Do not run `npm run build:tauri:local` directly as the accepted non-mutating validation path.**
Raw `build:tauri:local` has no /Applications guard and is not accepted for sprint validation.

- [ ] `./scripts/build-local.sh` exits 0
- [ ] `/Applications` content unchanged (binary SHA256 + plist SHA256 match pre-state)
- [ ] Artifact at: `frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app`
  - DMG: skipped for founder-local. Use `build:tauri:release` for DMG (public release).
- [ ] **Artifact version gate**: `CFBundleShortVersionString` matches source version
  ```sh
  plutil -extract CFBundleShortVersionString raw \
    frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app/Contents/Info.plist
  # Must equal the version in pyproject.toml / package.json / tauri.conf.json / Cargo.toml
  # If stale → STALE_OR_MISSING_PACKAGE_ARTIFACT — rebuild with ./scripts/build-local.sh
  ```

### /Applications/OpenJarvis.app Policy

> `/Applications/OpenJarvis.app` is **read-only evidence** by default.
>
> **Mutation mechanism** (documented root cause): Running any Tauri build that compiles a new
> binary and codesigns it may trigger macOS's security infrastructure to rescan the installed
> copy in `/Applications`, updating its content. This is NOT authorized by default.
>
> **The safe wrapper** (`scripts/build-local.sh`) detects content mutations via SHA256 checksums
> and fails with `UNAUTHORIZED_APPLICATIONS_MODIFICATION` if /Applications changes without
> the explicit `--allow-applications-update` flag.
>
> Raw `npm run build:tauri:local` has NO such guard and must NOT be used as the accepted
> non-mutating validation path.

- [ ] Use `./scripts/build-local.sh` (not raw `npm run build:tauri:local`) for all sprint validation
- [ ] Without `--allow-applications-update`: binary SHA, plist SHA, version, AND mtime must all be unchanged
- [ ] Any change — content or mtime — without the flag → non-zero exit (no silent pass)
- [ ] If `/Applications` version is stale: reported as `installed_stale` — not as pass
- [ ] `/Applications` update requires explicit Bryan authorization + `--allow-applications-update` flag

### Public / Updater Build (REQUIRED_FOR_PUBLIC_RELEASE)

> **Requires `TAURI_SIGNING_PRIVATE_KEY`**. This build exits 1 without the key.
> Status: `REQUIRED_FOR_PUBLIC_RELEASE` — do NOT use for founder-local packaging.
> Only run when preparing a signed public release with explicit Bryan authorization.

```sh
cd frontend
npm run build:tauri:release   # or: npm run tauri build
```

- [ ] `TAURI_SIGNING_PRIVATE_KEY` env var set (obtain from secure secret store)
- [ ] Build exits 0
- [ ] Updater `.tar.gz` artifact signed
- [ ] Public release tag created and pushed

### Backend Runtime (required before launching packaged app)

> **The packaged app requires the backend server running separately.**
> The app connects to `http://localhost:8000` by default. Without the backend,
> the app shows connection errors — this is expected, not a packaging defect.

```sh
# In a separate terminal — start the backend before opening the app
cd /path/to/OpenJarvis
uv run jarvis serve
# or: .venv/bin/python3 -m uvicorn openjarvis.server.app:app --host 127.0.0.1 --port 8000
```

```sh
# Open the app
open /Applications/OpenJarvis.app
# or: open ~/Applications/OpenJarvis.app
```

### Install / Copy to Applications

```sh
# Drag-and-drop from DMG (standard macOS install):
#   open frontend/src-tauri/target/release/bundle/dmg/OpenJarvis_1.0.2_x64.dmg
#   → drag OpenJarvis.app to /Applications/

# Or copy directly from bundle (founder-local convenience):
cp -r frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app ~/Applications/

# Or use the validation script (also runs build + artifact checks):
./scripts/release-local.sh --install
```

### Launch Verification

- [ ] App launches from the `.app` bundle
- [ ] Backend is running (`uv run jarvis serve`) before opening the app
- [ ] SetupScreen appears and completes on first launch
- [ ] Version visible in Settings > About
- [ ] Health check passes: `curl -s http://localhost:8000/v1/readiness | python3 -m json.tool`

### Auto-Update Caveat

> **Auto-update endpoint is UNVERIFIED for founder-local use.**
> `tauri.conf.json` updater points to `github.com/open-jarvis/OpenJarvis/releases/...`
> No public GitHub release has been published. The updater will fail silently.
> This is expected and correct for founder-local scope. Do not mark auto-update
> ready until a signed, notarized public release is published.

- [ ] Acknowledged: auto-update will not function until a public release is published

### macOS Signing (ad-hoc — current default)

```sh
# Verify the current signing identity in tauri.conf.json
grep signingIdentity frontend/src-tauri/tauri.conf.json
# Expected: "-"
```

- [ ] `signingIdentity = "-"` confirmed (ad-hoc; Gatekeeper will prompt)
- [ ] Document: users must right-click → Open on first launch, OR:
  ```sh
  xattr -dr com.apple.quarantine /Applications/OpenJarvis.app
  ```

### macOS Notarization (REQUIRED_FOR_PUBLIC_RELEASE — not required for founder-local distribution)

> V1 uses ad-hoc signing (`signingIdentity = "-"`). This is correct and sufficient for
> local/founder use. Notarization is only needed for public App Store or public download
> distribution. Bryan does not currently have an Apple Developer Program account.

- [ ] **Only required for public distribution (post-V1):** Enroll at developer.apple.com
- [ ] Set `signingIdentity` to team certificate, add `tauri-plugin-notarize`
- [ ] Re-run `npm run tauri build` with notarization

---

## Distribution Safety Checks

- [ ] No `.env` or `.env.*` files in the release artifact
- [ ] No `__pycache__/` or `.venv/` directories bundled
- [ ] No private keys or tokens in `frontend/dist/`
- [ ] `src-tauri/target/` is not included in git

---

## Git Tag & Push

```sh
# Tag the release
git tag -a v$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2) -m "Release v$(grep '^version' pyproject.toml | head -1 | cut -d'"' -f2)"

# Push tag to fork
git push xiaobryans/OpenJarvis --tags

# Push branch
git push xiaobryans/OpenJarvis localhost-get-tool
```

---

## Post-Release

- [ ] `CHANGELOG.md` moved `[Unreleased]` to versioned section
- [ ] GitHub release draft created (if applicable)
- [ ] Known limitations documented in release notes
- [ ] `docs/US14_RELEASE_DISTRIBUTION.md` updated if scope changed

---

## Founder-Local Validation Script

Run `scripts/release-local.sh` for an automated precheck + build + artifact verify pass:

```sh
# Basic validation (no install, no health check):
./scripts/release-local.sh

# Validate + copy to ~/Applications/:
./scripts/release-local.sh --install

# Validate + health check (requires running backend):
./scripts/release-local.sh --health
```

The script explicitly reports:
- Full no-gap HOLD status and remaining sprints
- Voice safety sprint gate (separate, not covered)
- Ad-hoc signing status
- Auto-update unverified status
- Public distribution NOT ready

## Rollback

If anything goes wrong post-release, follow `docs/ROLLBACK.md`.
