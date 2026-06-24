# /tauri-release-gate

Run the **Tauri release gate** before promoting a rebuilt app to `/Applications/`.

## Usage
```
/tauri-release-gate
```

## When to use
**ONLY** when Bryan has explicitly authorized a Tauri rebuild in the current sprint prompt.
If no explicit authorization: immediately outputs HOLD and stops.

## What this does
Runs the `openjarvis-tauri-release-gate` skill:
1. Verifies Bryan authorization exists in sprint scope.
2. SHA256 match across bundle/home/applications.
3. Version string consistency check.
4. Signing status check.
5. Distribution files presence.
6. Plan 1 checkpoint regression check.
7. Produces PASS | HOLD verdict.

## Hard stops
- No Bryan authorization in current sprint → HOLD immediately.
- SHA mismatch → HOLD.
- Plan 1 regression → HOLD.

## Rules
- Never runs `bash scripts/build-local.sh --install` without Bryan authorization.
- Never copies `.app` to `/Applications/` without Bryan authorization.
