---
name: tauri-deferred-plan2
description: Enforce and document Tauri rebuild deferral during Plan 2. Intercepts any attempt to run Tauri rebuild commands and produces a HOLD with explanation. Use when a sprint task might involve or suggest a Tauri rebuild.
---

# Tauri Rebuild Deferral (Plan 2)

**Tauri rebuild is deferred until full Plan 2 completion**, unless Bryan explicitly
approves it for the current sprint.

## Trigger
Use when:
- A sprint task mentions Tauri, `src-tauri`, `tauri build`, or `build-local.sh`.
- A validation step might attempt `bash scripts/build-local.sh --install`.
- A dependency change could trigger Tauri recompilation.

## Blocked commands (do NOT run during Plan 2 unless Bryan approves)
- `bash scripts/build-local.sh --install`
- `bash scripts/build-local.sh` (with `--install` flag)
- `cargo tauri build`
- `npm run tauri build`
- `tauri build`

## Allowed (does NOT require rebuild)
- `npx tsc --noEmit` — TypeScript type check only, no build artifact
- `npx vite build --mode development` — frontend bundle only, no Tauri
- Backend Python / FastAPI changes — no Tauri involvement
- `git status`, `git diff`, validation commands

## Action
If a Tauri rebuild is attempted or suggested:
1. **HOLD** immediately.
2. Report: "Tauri rebuild blocked per CLAUDE.md Plan 2 deferral rule."
3. State: "Do you want to request an exception? This requires Bryan's explicit approval."
4. Do NOT proceed with the rebuild.

## Required Statement in Every Sprint Report
> "Tauri rebuild is deferred until full Plan 2 completion, per CLAUDE.md.
>  No Tauri rebuild was run in this sprint."

## Output
```
TAURI DEFERRAL CHECK: [CLEAR / HOLD]
Commands attempted: [none / list of blocked commands]
Action taken: [no rebuild attempted] | [HOLD — blocked command: ...]
```
