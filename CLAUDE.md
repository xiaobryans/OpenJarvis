# OpenJarvis — Claude Code Project Rules

## Repository / Git
- **Branch:** `localhost-get-tool`
- **Remote:** `fork` / `xiaobryans/OpenJarvis`

## Locked Roadmap State
- `PLAN_1_DUAL_PLATFORM_JARVIS_NEURAL_COMMAND_CENTER_ACCEPTED`
- `PLAN_2A_MOBILE_MACBOOK_OFF_FOUNDATION_ACCEPTED_PENDING_FINAL_TAURI_REBUILD`
- `PLAN_2B_CONNECTOR_TASK_PARITY_FOUNDATION_ACCEPTED_PENDING_FINAL_TAURI_REBUILD`
- `CLAUDE_CODE_BASELINE_SETUP_ACCEPTED`

## Active Plan
**Plan 2 — Full Mobile MacBook-Off Parity Runtime**

Scope:
- Mobile/MacBook-off parity status endpoints and matrix
- Connector and task parity (GitHub, Slack, Telegram, Notion, Google OAuth)
- Approval notification loop
- Fargate worker / cloud execution path
- Safe public parity routes (no sensitive field leakage)

## Hard Rules (do not violate)
- Do **not** start Plan 3 (voice / wake / TTS) unless Bryan explicitly asks.
- Do **not** rebuild/reinstall Tauri until full Plan 2 completion unless Bryan explicitly asks.
- Do **not** run `bash scripts/build-local.sh --install`.
- **No fake PASS.**
- **No fake ACCEPTED.**
- **No secret values printed.**
- **Presence-only key reporting** (report that a key is present/absent, never its value).
- **Changed-file-only review by default.**
- **Stop on blocker** — do not proceed past a blocker; surface it immediately.
- Do **not** weaken auth.
- Do **not** stage unrelated dirty files.
- **Contradiction rule:** for ambiguous, stale, duplicate, or contradictory systems — report evidence and options to Bryan first; do not auto-edit or auto-remove.
- No agent may claim acceptance on Bryan's behalf.

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

## Required Final Sprint Report Format
Every sprint / validation report must include, in order:
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

## Agents
See `.claude/agents/` for full agent definitions. Key agents:
- `plan2-coordinator` — sprint ownership, file conflict prevention
- `backend-implementer` — API/route/handler changes
- `frontend-mobile-implementer` — UI/mobile/TypeScript changes
- `connector-specialist` — connector integrations
- `memory-sync-specialist` — memory/search system
- `cloud-infra-planner` — Fargate/vault planning (no live deploys)
- `security-reviewer` — auth/secret/endpoint safety (can HOLD)
- `validation-reporter` — exact command outputs, sprint reports
- `docs-matrix-maintainer` — matrix/doc maintenance only
- `merge-coordinator` — final integration gate
- `automation-auditor` — action ledger review, accountability enforcement

## Skills
See `.claude/skills/` — openjarvis-validation, secret-safety-review, plan2-sprint,
plan2-report, checkpoint-regression, changed-file-review, safe-merge-review,
parallel-worktree, tauri-deferred-plan2, blocker-triage.

## Slash Commands
See `.claude/commands/` — /plan2-next, /plan2-sprint, /validate-openjarvis,
/secret-scan, /checkpoint-regression, /plan2-report, /safe-merge-review,
/parallel-plan2, /stop-on-blocker, /status-roadmap,
/automation-ledger, /full-auto-setup.

## Hooks
See `.claude/hooks/README.md` — hook scripts prepared but not yet activated.
Activation requires wiring into `.claude/settings.json`.

## Full Automation Accountability

When bypass permission mode is enabled, **all project hard rules still apply**.
Autonomy is granted within the declared sprint scope only. The following rules
govern autonomous / full-automation sprints:

- Claude may act autonomously within the approved sprint scope.
- Claude must maintain an **action ledger** for every meaningful action taken.
  See `full-automation-ledger` skill and `/automation-ledger` command.
- Claude must justify **high-risk actions** before or while performing them.
  High-risk: auth changes, connector/token/OAuth changes, memory/routing changes,
  approval-gate changes, deployment/cloud actions, file deletion, large refactors,
  staging/commit/push, hook activation, any command that could expose secrets.
- Claude must **never hide** changed files, commands, validation failures, or blockers.
- Claude must **not claim acceptance** — only Bryan (or ChatGPT reviewer) can accept.
- Claude must use **explicit staging paths** — never `git add .` or `git add -A`.
- Claude must **preserve unrelated dirty files** — never stage them.
- Bypass permission does not authorize actions outside sprint scope.
- Bypass permission does not remove the ledger requirement.

## MCP
MCP connectors deferred. See `docs/plan2/CLAUDE_AUTOMATION_SETUP.md`.
