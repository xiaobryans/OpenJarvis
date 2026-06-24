# Apple Signing Personal Baseline Review

**Sprint date:** 2026-06-22  
**Notarization closure date:** 2026-06-24
**Plan 9 baseline:** `PLAN_9_FULL_ACCEPTED` · `JARVIS_REPLACEMENT_ACCEPTED`
**Branch:** `localhost-get-tool` · **Baseline HEAD:** `9bc9778d`
**Scope:** Personal-use macOS installability only (not App Store, not public release)

---

## Final Verdict

**`APPLE_SIGNING_PERSONAL_BASELINE_ACCEPT_PENDING_REVIEW`**

Developer ID codesign + Apple notarization + Gatekeeper acceptance fully proven on physical Mac.

---

## Notarization Proof (2026-06-24)

| Check | Result |
|-------|--------|
| Submission ID | `11ca2087-fdb9-49d8-a3b3-b203a0bbb93f` |
| Keychain profile | `OpenJarvisNotary` |
| Apple notary status | **Accepted** |
| `xcrun stapler staple /Applications/OpenJarvis.app` | **Success** |
| `xcrun stapler validate /Applications/OpenJarvis.app` | **Success** |
| `codesign --verify --deep --strict` | **valid on disk · satisfies Designated Requirement** |
| `TeamIdentifier` | `TQL4A44WDJ` |
| `spctl --assess --type execute --verbose=4` | **accepted · source=Notarized Developer ID** |
| App opened | Yes — no Gatekeeper warning |
| `/health` `status` | `ok` |
| `/health` `backend_source` | `desktop_app` |
| `/health` `version` | `1.0.2` |
| `/health` `git_commit` | `9bc9778d` |
| `/health` `jarvis_build_commit` | `9bc9778d` |

**Plan 9 runtime regression:** None — backend starts from installed signed app, all health fields match accepted baseline.

### Script patch in this commit

`scripts/build-sign-personal.sh` was updated to:
- Accept `APPLE_NOTARY_KEYCHAIN_PROFILE` / `APPLE_KEYCHAIN_PROFILE` as Option A (preferred)
- Accept Command Line Tools `notarytool`/`stapler` without requiring full Xcode
- Prefer `xcrun notarytool submit … --keychain-profile` over Apple ID/password flow
- Preserve all prior Option B (Apple ID) and Option C (API key) credential flows
- Emit `APPLE_NOTARIZATION_CREDENTIALS_HOLD` with setup instructions on missing creds

### Previous hold (now closed)

`APPLE_SIGNING_PERSONAL_BASELINE_HOLD` — was waiting on Developer ID certificate, credentials, and notarization toolchain. All closed.

---

## Platform scope

| Surface | Status |
|---------|--------|
| **macOS app** (`/Applications/OpenJarvis.app`, Tauri bundle) | **In scope** — must be Developer ID signed + notarized for trust-warning-free personal use |
| **iPhone / mobile** | **Browser/PWA only** — Plan 9 proof used Safari at public cloud URL `/health/mobile-proof`. **No native iOS app in repo.** Do not invent native iOS work. |
| **Updater** | **Present in config but disabled for personal baseline** — `build:tauri:local` and `build-sign-personal.sh` set `updater.active=false`, `createUpdaterArtifacts=false`. Updater signing deferred until public release path. |

---

## Phase 0 — Baseline preservation

| Check | Result |
|-------|--------|
| Branch | `localhost-get-tool` |
| HEAD | `fd22fa0f` |
| Working tree | Modified: `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py`, `.gitignore`; untracked: `docs/certification/PLAN_9_FINAL_ACCEPTANCE_REVIEW.md`, `evidence/`, key helper scripts |
| Certification artifact | `docs/certification/PLAN_9_FINAL_ACCEPTANCE_REVIEW.md` contains `PLAN_9_FULL_ACCEPTED` + owner sign-off — **present, uncommitted** |
| Recommended tag | `plan9-full-accepted-fd22fa0f` — **not created** (awaiting Bryan approval to commit cert + tag) |
| Proceed without tag? | Bryan authorized this signing sprint; Plan 9 runtime verified live at `fd22fa0f` on cloud and local app backend |

**Action needed from Bryan:** Confirm commit of `docs/certification/PLAN_9_FINAL_ACCEPTANCE_REVIEW.md` and creation of tag `plan9-full-accepted-fd22fa0f` before first signed release build.

---

## Phase 1 — Signing target audit

### macOS bundle

| Component | Path / note |
|-----------|-------------|
| Installed app | `/Applications/OpenJarvis.app` v1.0.2 |
| Tauri bundle output | `frontend/src-tauri/target/release/bundle/macos/OpenJarvis.app` |
| Bundle ID | `com.openjarvis.desktop` |
| Main binary | `Contents/MacOS/openjarvis-desktop` |
| Embedded backend | App-spawned Python/`uv` Jarvis server on `127.0.0.1:8000` (not separate signed binary) |
| Entitlements | `frontend/src-tauri/Entitlements.plist` (no sandbox; network client/server; JIT; audio input) |
| Current signature | **adhoc** (`Signature=adhoc`, `TeamIdentifier=not set`) |

### iPhone path

Physical iPhone Plan 9 proof = **Safari browser** to cloud API Gateway URL. No Xcode iOS target, no `.xcodeproj` iOS app, no TestFlight artifact.

### Updater

| Item | Status |
|------|--------|
| `tauri-plugin-updater` | Installed in `Cargo.toml` |
| `plugins.updater.active` | `true` in `tauri.conf.json` default |
| Personal build path | **Disabled** in `build-sign-personal.sh` and `npm run build:tauri:local` |
| Updater pubkey / GitHub endpoint | Configured for future public release — **not validated this sprint** |

---

## Phase 2 — Apple account / certificate readiness (presence only)

| Item | Status |
|------|--------|
| Xcode command line tools | **Present** (`/Library/Developer/CommandLineTools`) |
| Full Xcode | **Missing** — `xcodebuild`, `notarytool`, `stapler` require full Xcode.app |
| Apple Developer account | **Insufficient data to verify enrollment on this machine** |
| Codesigning identities in keychain | **0 valid identities found** |
| `APPLE_SIGNING_IDENTITY` / `APPLE_DEVELOPER_IDENTITY` | **absent** (shell + cloud-keys files) |
| `APPLE_TEAM_ID` | **absent** |
| `APPLE_ID` / app-specific password / API key | **absent** |
| Notarization credential path | **Missing** (no creds + no notarytool) |
| Bundle ID in config | **Present** — `com.openjarvis.desktop` |
| Team ID in config | **Missing** — `providerShortName: null` in `tauri.conf.json` |

No private keys, passwords, tokens, or certificate material printed or committed.

---

## Phase 3 — Minimal signing pipeline (implemented)

| File | Change |
|------|--------|
| `scripts/build-sign-personal.sh` | **NEW** — loads `APPLE_*` from local cloud-keys env files; preflight; Tauri build with Developer ID identity; optional notarize+staple; updater off; `--dry-run`, `--install`, `--notarize` |
| `.gitignore` | Protect `*.p12`, `*.mobileprovision`, `AuthKey_*.p8`, `.apple-signing/`, notarization logs |
| `frontend/src-tauri/tauri.conf.json` | **Unchanged** — remains ad-hoc default (`signingIdentity: "-"`) so Plan 9 local builds are unaffected |

Secrets stay in keychain / local env files only.

---

## Phase 4 — Build / sign / notarize validation

| Step | Result |
|------|--------|
| `./scripts/build-sign-personal.sh --dry-run` | **FAIL** — no `APPLE_SIGNING_IDENTITY`; 0 keychain identities |
| Clean signed build | **Not run** — blocked by missing Developer ID certificate |
| Sign / verify | **Not run** |
| Notarize / staple | **Not run** — full Xcode + credentials missing |
| Install signed app | **Not run** |
| Gatekeeper clean open | **Not proven** — installed app remains ad-hoc |
| Plan 9 runtime regression check | **PASS (existing install)** — `GET http://127.0.0.1:8000/health` → `status=ok`, `backend_source=desktop_app`, `git_commit=fd22fa0f` |
| Cloud Plan 9 baseline | **Unchanged** — `PLAN_9_FULL_ACCEPTED` not affected |

---

## Phase 5 — Secret scan

| Scan | Result |
|------|--------|
| New/changed signing files | No secrets, keys, passwords, or cert blobs in repo |
| Script output this sprint | No secret values printed |

---

## Remaining blockers

1. **Apple Developer Program enrollment + Developer ID Application certificate** — import into login keychain (0 valid identities today).
2. **Configure local credentials** (values never in repo):
   - `APPLE_SIGNING_IDENTITY="Developer ID Application: …"`
   - `APPLE_TEAM_ID=…`
   - For notarization: `APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` **or** App Store Connect API key trio
   - Store in `~/.jarvis/cloud-keys.env` (preferred) or `~/.openjarvis/cloud-keys.env`
3. **Install full Xcode.app** and run `sudo xcode-select -s /Applications/Xcode.app/Contents/Developer` for `notarytool` + `stapler`.
4. **Preserve Plan 9 baseline in git** — commit certification doc + tag `plan9-full-accepted-fd22fa0f` (Bryan approval pending).
5. **Hardened-runtime / entitlements review** after first signed build — embedded Python may require entitlement tuning for notarization acceptance.

---

## Bryan manual verification (after blockers cleared)

1. Import Developer ID Application certificate to Keychain Access.
2. Add to `~/.jarvis/cloud-keys.env` (never commit):
   ```
   APPLE_SIGNING_IDENTITY=Developer ID Application: …
   APPLE_TEAM_ID=…
   APPLE_ID=…
   APPLE_APP_SPECIFIC_PASSWORD=…
   ```
3. Install Xcode → `xcode-select -s /Applications/Xcode.app/Contents/Developer`
4. Preflight:
   ```bash
   ./scripts/build-sign-personal.sh --dry-run
   ```
   Expect: signing identity found, keychain match.
5. Build + sign + install:
   ```bash
   ./scripts/build-sign-personal.sh --install --notarize
   ```
6. Open `/Applications/OpenJarvis.app` — confirm **no Gatekeeper “damaged/unidentified developer” block**.
7. Verify runtime:
   ```bash
   curl -s http://127.0.0.1:8000/health | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status'), d.get('git_commit'))"
   ```
   Expect: `ok` and current commit.
8. Spot-check chat, registry (`/v1/plan9/registry`), memory status — same Plan 9 acceptance bar.
9. iPhone: no change required — continue browser cloud proof path.

---

## Accepted state preserved

* `PLAN_9_FULL_ACCEPTED` — unchanged  
* `JARVIS_REPLACEMENT_ACCEPTED` — unchanged  

When personal signed install is proven, promote this sprint to:
**`APPLE_SIGNING_PERSONAL_BASELINE_ACCEPT_PENDING_REVIEW`**

---

## Cost-control accountability

1. **Inspected:** `tauri.conf.json`, `Entitlements.plist`, `build-local.sh`, `package.json`, keychain/Xcode presence, installed app signature, local `/health`, Plan 9 cert doc.
2. **Changed:** `scripts/build-sign-personal.sh`, `.gitignore`, this review doc.
3. **Tests run:** Signing dry-run preflight only; local health curl. No full Tauri rebuild (blocked).
4. **Not reverified:** Full Plan 9 pytest, cloud redeploy, updater path.
5. **Blockers causing stop:** No Developer ID cert, no Apple env creds, no full Xcode.
