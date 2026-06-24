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
- `default-automation-router` — classifies any Bryan request and routes automatically

## Skills
See `.claude/skills/` — openjarvis-validation, secret-safety-review, plan2-sprint,
plan2-report, checkpoint-regression, changed-file-review, safe-merge-review,
parallel-worktree, tauri-deferred-plan2, blocker-triage, full-automation-ledger,
jarvis-plan-executor.

## Slash Commands
See `.claude/commands/` — /plan2-next, /plan2-sprint, /validate-openjarvis,
/secret-scan, /checkpoint-regression, /plan2-report, /safe-merge-review,
/parallel-plan2, /stop-on-blocker, /status-roadmap, /automation-ledger,
/full-auto-setup, /auto-execute, /jarvis-plan, /parallel-auto,
/autonomous-takeover-check.

## Hooks
See `.claude/hooks/README.md`. Hooks are **active** via `.claude/settings.json`:
`warn-env-access` (passive), `warn-tauri-build` (blocking, exit 2),
`remind-diff-check` (passive), `remind-action-ledger` (passive).

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

## DEFAULT_AUTONOMOUS_EXECUTION_MODE

Any Bryan plan, sprint, bug, report, or implementation prompt defaults to
**autonomous execution** unless Bryan explicitly says one of:
`review-only`, `no-edits`, `planning-only`, or `ask-first`.

**Default autonomous behaviour:**
- Claude classifies the request automatically using `default-automation-router`.
- Claude chooses relevant agents, skills, and commands automatically.
- Claude decides sequential vs safe parallel work automatically.
- Claude uses worktrees/branches for parallel work when file ownership can be
  fully separated and no protected areas overlap.
- Claude assigns file ownership before any parallel work begins.
- Claude validates changed files after every implementation step.
- Claude runs secret/security checks before every staged commit.
- Claude updates docs/matrix files when the sprint scope requires it.
- Claude may stage explicit files, commit, and push when the prompt grants
  implementation authority or the task is inside an already-approved sprint scope.
- Claude reports all actions and justifications in the action ledger.
- Claude does **not** pause for routine approval on normal repo work inside scope.

**Standing permission (Bryan-granted):**
Bryan grants standing permission for autonomous repo work inside approved
OpenJarvis sprint scope. This covers: file edits, staging (explicit paths),
commits, pushes to `fork/localhost-get-tool`, agent/skill/command invocation,
safe parallel worktree setup, validation, and secret scanning.

**Claude must still stop and ask Bryan when:**
1. Action is outside the current sprint/plan scope.
2. Action may read, expose, or print secret/credential values.
3. Action is destructive (deletes or quarantines files).
4. Action triggers live cloud/OAuth/deployment/spend/external side effects.
5. Action requires Tauri rebuild/reinstall before full Plan 2 completion.
6. Action contradicts a locked roadmap state or accepted checkpoint.
7. Action changes auth/approval gates in a way that weakens safety.
8. Action requires touching unrelated dirty files.
9. Safe parallelization is impossible due to overlapping file ownership.

**Model routing defaults:**
- Sonnet — setup, implementation, validation, docs, reporting, connectors
- Opus — architecture decisions, auth/security tradeoffs, memory/routing design,
  cloud/deployment design, final merge review, contradiction resolution

## MCP
MCP connectors deferred. See `docs/plan2/CLAUDE_AUTOMATION_SETUP.md`.
