# OpenJarvis — Claude Code Automation Setup Status

**Last updated:** 2026-06-24
**Branch:** `localhost-get-tool`
**Baseline committed at:** `8491d99c`
**Full automation commit:** pending review

---

## Files Created / Updated

| File | Status |
|------|--------|
| `CLAUDE.md` | Updated — full rules, locked state, accountability section |
| `.gitignore` | Updated — un-ignored agents/skills/commands/hooks, settings.json tracked |
| `.claude/settings.json` | Created — repo-scoped hook activation |

---

## Agents (`.claude/agents/`)

| Agent | Responsibility |
|-------|---------------|
| `plan2-coordinator` | Sprint ownership, file conflict prevention, routing |
| `backend-implementer` | API/route/handler implementation |
| `frontend-mobile-implementer` | React/TypeScript/mobile UI |
| `connector-specialist` | GitHub/Slack/Telegram/Notion/OAuth wiring |
| `memory-sync-specialist` | Unified memory search, SQLite, JarvisMemory |
| `cloud-infra-planner` | Fargate/vault planning (no live deploys) |
| `security-reviewer` | Auth/secret/endpoint safety — can HOLD |
| `validation-reporter` | Exact command outputs, sprint reports |
| `docs-matrix-maintainer` | Matrix/doc maintenance only (no feature code) |
| `merge-coordinator` | Final integration gate |
| `automation-auditor` | Action ledger review, accountability enforcement |

---

## Skills (`.claude/skills/`)

| Skill | Purpose |
|-------|---------|
| `openjarvis-validation` | Changed-file validation + sprint report |
| `secret-safety-review` | Secret scan — presence-only, PASS/HOLD |
| `plan2-sprint` | Full sprint execution end-to-end |
| `plan2-report` | 13-point required sprint report |
| `checkpoint-regression` | Plan 1 + Plan 2 checkpoint verification |
| `changed-file-review` | Changed-file-only correctness/safety review |
| `safe-merge-review` | Merge candidate safety check |
| `parallel-worktree` | Parallel git worktree setup and coordination |
| `tauri-deferred-plan2` | Enforce Tauri rebuild deferral |
| `blocker-triage` | Blocker identification — HOLD on hard blockers |
| `full-automation-ledger` | Action ledger maintenance and presentation |

---

## Commands (`.claude/commands/`)

| Command | Purpose |
|---------|---------|
| `/plan2-next` | Show next unblocked Plan 2 task |
| `/plan2-sprint` | Execute a Plan 2 sprint |
| `/validate-openjarvis` | Run changed-file validation |
| `/secret-scan` | Run secret scan on staged/changed files |
| `/checkpoint-regression` | Verify Plan 1/2 checkpoints not regressed |
| `/plan2-report` | Generate 13-point sprint report |
| `/safe-merge-review` | Run merge safety review |
| `/parallel-plan2` | Set up parallel worktree workflow |
| `/stop-on-blocker` | Triage blockers, stop if hard blocker found |
| `/status-roadmap` | Show current roadmap status and locked checkpoints |
| `/automation-ledger` | Show/audit sprint action ledger |
| `/full-auto-setup` | Run full automation setup sprint with action ledger |

---

## Hooks (`.claude/hooks/`)

**Status: ACTIVATED in `.claude/settings.json`**

| Script | Type | Exit | Status | Purpose |
|--------|------|------|--------|---------|
| `warn-env-access.sh` | PreToolUse (Read/Edit/Write) | 0 — warn only | **Active** | Warns when secret-looking files accessed |
| `warn-tauri-build.sh` | PreToolUse (Bash) | 2 — **blocks** | **Active** | Blocks `build-local.sh --install` |
| `remind-diff-check.sh` | PostToolUse (Bash) | 0 — warn only | **Active** | Reminds to run `git diff --check` |
| `remind-action-ledger.sh` | PostToolUse (Bash) | 0 — warn only | **Active** | Reminds to log in sprint action ledger |

Hook config lives at `.claude/settings.json` (repo-scoped, tracked by git).
`settings.local.json` remains gitignored (per-developer overrides only).

---

## Full Automation Mode

When **bypass permission mode** is enabled, Claude may act autonomously within the
declared sprint scope. The following rules apply regardless of permission mode:

1. All project hard rules from `CLAUDE.md` remain in force.
2. Claude must maintain an **action ledger** for every meaningful action.
3. **High-risk actions** (auth, connectors, staging/commit/push, hook activation,
   file deletion, large refactors) require explicit justification before execution.
4. Claude must never hide changed files, failed validations, or blockers.
5. Claude must use explicit `git add <path>` — never `git add .` or `git add -A`.
6. Claude must not claim acceptance — only Bryan (or ChatGPT reviewer) can accept.
7. Unrelated dirty files must not be staged.

### Coordinator / Worker / Reviewer Flow

```
Bryan (approves sprint scope)
  └── plan2-coordinator (declares file ownership, routes tasks)
        ├── backend-implementer (owns backend files)
        ├── frontend-mobile-implementer (owns frontend files)
        ├── connector-specialist (owns connector files)
        └── memory-sync-specialist (owns memory files)
              └── merge-coordinator (integration gate, PASS/HOLD)
                    └── Bryan (approves merge)
```

Accountability layer:
- `automation-auditor` reviews ledger after any autonomous sprint.
- `security-reviewer` reviews auth/secret changes — can HOLD independently.
- `validation-reporter` produces exact outputs, no summarizing.

### Commit / Push Rules (full automation mode)
1. Stage only files in declared sprint scope using explicit paths.
2. Verify staged files with `git diff --cached --name-only` before commit.
3. Run secret scan on staged files before commit.
4. Run `git diff --check` before commit.
5. Commit with a clear message describing scope.
6. Push only to the declared remote/branch.
7. Log staging, commit, and push in the action ledger (all MEDIUM risk).

---

## MCP Status

**MCP connectors: DEFERRED**

Recommended future MCP activation order (when ready):
1. Local filesystem/repo only — read-only access to project files
2. GitHub read-only — PR, issue, and diff context
3. Browser/dev server — frontend validation
4. Cloud/provider read-only — monitoring only
5. Write-enabled tools — only after approval gates are proven in production

Do not add write-enabled MCP connectors until:
- Fargate approval gate is deployed and tested
- Cloud execution path is proven safe
- Bryan approves each connector explicitly

---

## Remaining Setup

- [x] Review and activate hooks — done via `.claude/settings.json`
- [ ] Wire approval notification loop (Plan 2 blocker)
- [ ] Deploy Fargate worker (Plan 2 blocker)
- [ ] Migrate Google OAuth tokens to vault (Plan 2 blocker)
- [ ] Resolve Telegram env mismatch (Plan 2 blocker)
- [ ] Configure Notion connector (Plan 2 blocker)
- [ ] Activate MCP connectors (deferred per MCP policy above)

---

## Is Claude Ready for Plan 2C Takeover Validation?

**YES — with the following conditions:**

✓ `CLAUDE.md` with full rules, locked state, and accountability section  
✓ 11 agents defined with narrow responsibilities  
✓ 11 skills defined with exact steps and stop conditions  
✓ 12 commands defined  
✓ 4 hook scripts active via `settings.json`  
✓ Parallel worktree workflow documented  
✓ Action ledger and automation-auditor in place  
✓ Contradiction rule enforced  
✓ No fake PASS / no fake ACCEPTED rules in all agents/skills  

**Conditions before first Plan 2C sprint:**
- Bryan must explicitly approve start of Plan 2C
- Tauri rebuild remains deferred
- Run `/stop-on-blocker` to triage current blockers
- Run `/status-roadmap` to confirm locked state
