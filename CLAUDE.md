# OpenJarvis — Claude Code Project Rules

## Repository / Git
- **Branch:** `localhost-get-tool`
- **Remote:** `fork` / `xiaobryans/OpenJarvis`

## Plan Status
- **Plan 1 accepted:** `PLAN_1_DUAL_PLATFORM_JARVIS_NEURAL_COMMAND_CENTER_ACCEPTED`
- **Plan 2A accepted** — pending final Tauri rebuild
- **Plan 2B accepted** — pending final Tauri rebuild
- **Active plan:** `Plan 2 — Full Mobile MacBook-Off Parity Runtime`

## Hard Rules (do not violate)
- Do **not** start Plan 3 (voice / wake / TTS) unless Bryan explicitly asks.
- Do **not** rebuild/reinstall Tauri until full Plan 2 completion unless Bryan explicitly asks.
- Do **not** run `bash scripts/build-local.sh --install`.
- **No fake PASS.**
- **No fake ACCEPTED.**
- **No secret values printed.**
- **Presence-only key reporting** (report that a key exists, never its value).
- **Changed-file-only review by default.**
- **Stop on blocker** — do not proceed past a blocker; report it.
- Do **not** weaken auth.
- Do **not** stage unrelated dirty files.
- For contradictions / ambiguous cleanup, **ask Bryan first** before editing or removing anything.

## Accepted Plan 1 Behavior — must NOT regress
- Jarvis PA identity
- Normal chat speed
- Cloud-first routing
- Unified memory search
- Same-session continuity
- Cmd+K history viewer only (read-only)
- Cmd+Shift+K command palette

## Current Plan 2 Blockers
- Google OAuth tokens are local JSON and need vault/cloud migration.
- GitHub / Slack / Telegram env tokens need Fargate deployment.
- Telegram env mismatch: `TELEGRAM_BOT_TOKEN` vs `JARVIS_TELEGRAM_BOT_TOKEN`.
- Notion is not configured.
- Approval notification loop is not wired.
- Fargate worker / cloud execution path is not deployed.
- Voice / wake / TTS remains parked for Plan 3.

## Required Final Report Format
Every sprint/validation report must include, in order:
1. **Verdict**
2. **Branch**
3. **Previous HEAD**
4. **New HEAD**
5. **Changed files**
6. **Files inspected and why**
7. **Root cause**
8. **Exact fix**
9. **Validation command outputs**
10. **Secret scan result**
11. **Proof accepted checkpoints were not regressed**
12. **Statement that Tauri rebuild is deferred until full Plan 2 completion**
13. **Remaining blockers**
