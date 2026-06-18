# OpenJarvis Release Checklist

Use this checklist before tagging and publishing a new release.

---

## Pre-Release Gates

### 1. Branch & Commit

- [ ] On the release branch (e.g. `localhost-get-tool` or `main`)
- [ ] `git status --short` is clean (no uncommitted changes)
- [ ] `git diff --check` passes (no trailing whitespace)
- [ ] `git rev-parse HEAD` matches expected base

### 2. Python Validation

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

```sh
cd frontend
npm run tauri build
```

- [ ] Build exits 0
- [ ] Artifact at: `frontend/src-tauri/target/release/bundle/`
  - macOS: `macos/OpenJarvis.app`, `dmg/OpenJarvis_*.dmg`
- [ ] App launches from the `.app` bundle
- [ ] SetupScreen appears and completes on first launch
- [ ] Version visible in Settings > About

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

### macOS Notarization (EXTERNALLY_NOT_PROVEN — blocked by Apple Developer account)

- [ ] Apple Developer Program enrollment complete
- [ ] `signingIdentity` updated to team certificate name
- [ ] `tauri-plugin-notarize` configured with `APPLE_ID`, `APPLE_PASSWORD`, `APPLE_TEAM_ID`
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

## Rollback

If anything goes wrong post-release, follow `docs/ROLLBACK.md`.
