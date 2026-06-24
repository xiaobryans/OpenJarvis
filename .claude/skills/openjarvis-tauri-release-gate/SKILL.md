---
name: openjarvis-tauri-release-gate
description: Gate a Tauri release before promotion — SHA256 match across bundle/home/applications, version string consistency, signing status, Plan 1 regression check. Only runs when Bryan explicitly authorizes a Tauri rebuild. Produces PASS | HOLD. Use before any Tauri app is promoted to /Applications/ or distributed.
---

# OpenJarvis Tauri Release Gate

Gates a Tauri release artifact before promotion or distribution.

## When to use
**ONLY when Bryan explicitly says "rebuild Tauri" or "run tauri-release-gate" in the current sprint prompt.**
If no explicit authorization: immediately output HOLD and stop.

## Pre-condition check
Before any step: verify Bryan explicitly authorized a Tauri rebuild in the current sprint scope.
If NOT authorized: output `HOLD — Tauri rebuild not authorized in current sprint` and stop.

## Steps (if authorized)

1. **SHA256 check** — compute SHA of build artifact, `~/Applications/OpenJarvis.app`, `/Applications/OpenJarvis.app`.
   ```bash
   find src-tauri/target/release/bundle -name "*.dmg" -exec shasum -a 256 {} \;
   shasum -a 256 ~/Applications/OpenJarvis.app/Contents/MacOS/OpenJarvis
   shasum -a 256 /Applications/OpenJarvis.app/Contents/MacOS/OpenJarvis
   ```
2. **Version check** — confirm `tauri.conf.json` version matches `Cargo.toml` and binary.
3. **Signing check** — `codesign -dv /Applications/OpenJarvis.app 2>&1 | grep Authority`.
4. **Distribution files** — confirm `.dmg` and `_update.json` exist.
5. **Plan 1 regression** — invoke `checkpoint-regression` skill.
6. **Invoke `tauri-release-gate-reviewer` agent** — produce gated verdict.

## Forbidden commands
- `bash scripts/build-local.sh --install` — BLOCKED by hook unless Bryan authorized
- Copying `.app` to `/Applications/` without Bryan's explicit authorization

## Output
```
TAURI RELEASE GATE
[structured output from tauri-release-gate-reviewer agent]
```
