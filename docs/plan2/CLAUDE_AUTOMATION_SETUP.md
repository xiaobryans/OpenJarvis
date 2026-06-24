# OpenJarvis — Claude Code Automation Setup Status

**Last updated:** 2026-06-24
**Branch:** `localhost-get-tool`
**Baseline committed at:** `8491d99c`
**Full automation committed at:** `4c9f15d9`
**Router extension:** pending review

---

## Files Created / Updated

| File | Status |
|------|--------|
| `CLAUDE.md` | Updated — full rules, locked state, accountability, DEFAULT_AUTONOMOUS_EXECUTION_MODE |
| `.gitignore` | Updated — un-ignored agents/skills/commands/hooks, settings.json tracked |
| `.claude/settings.json` | Created — repo-scoped hook activation |

---

## Agents (`.claude/agents/`)

| Agent | Responsibility |
|-------|---------------|
| `default-automation-router` | Classifies any Bryan request, routes automatically |
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
| `jarvis-plan-executor` | Full autonomous sprint lifecycle (the primary execution skill) |
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
| `/auto-execute` | Autonomous execution entry point — routes + executes any prompt |
| `/jarvis-plan` | Execute Bryan's roadmap/sprint prompt using default automation |
| `/parallel-auto` | Evaluate safe parallelization and execute; fallback to sequential |
| `/autonomous-takeover-check` | Validate all automation infrastructure is ready |
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

| Script | Type | Exit | Purpose |
|--------|------|------|---------|
| `warn-env-access.sh` | PreToolUse (Read/Edit/Write) | 0 — passive | Warns when secret-looking files accessed |
| `warn-tauri-build.sh` | PreToolUse (Bash) | 2 — **blocks** | Hard-blocks `build-local.sh --install` |
| `remind-diff-check.sh` | PostToolUse (Bash) | 0 — passive | Reminds to run `git diff --check` |
| `remind-action-ledger.sh` | PostToolUse (Bash) | 0 — passive | Reminds to log in sprint action ledger |

---

## Default Autonomous Execution Mode

`DEFAULT_AUTONOMOUS_EXECUTION_MODE` is active. Any Bryan plan, sprint, bug,
report, or implementation prompt defaults to **autonomous execution**.

### Activation keywords (Bryan overrides — disables autonomous mode for that prompt)
- `review-only`
- `no-edits`
- `planning-only`
- `ask-first`

### Standing Permission Scope (Bryan-granted)
Autonomous execution is authorized for:
- File edits within declared sprint scope
- Staging (explicit paths only — no `git add .`)
- Committing within sprint scope
- Pushing to `fork/localhost-get-tool`
- Agent/skill/command invocation
- Safe parallel worktree setup (when file ownership fully separable)
- Validation (all forms)
- Secret scanning (presence-only)
- Doc/matrix updates triggered by sprint scope

### No Routine Approval Loop
Claude does NOT pause to ask Bryan for approval on:
- Normal file edits within scope
- Running validation commands
- Staging, committing, pushing within scope
- Agent and skill delegation
- Worktree creation for approved parallel work
- Secret scan (presence-only)

Claude reports actions and justifications in the action ledger instead.

### Automatic Router Behaviour
Every prompt passes through `default-automation-router` which:
1. Classifies the task type
2. Assigns risk class (low/medium/high)
3. Recommends model (Sonnet/Opus)
4. Selects agents, skills, commands
5. Decides sequential vs parallel work
6. Declares file ownership map
7. Plans validation steps
8. Sets commit/push policy

### Automatic Parallelization Rules
Parallel worktrees are created automatically when:
- ≥2 independent sub-tasks exist
- Zero file overlap between tasks
- No task touches protected areas simultaneously
- Each task can validate independently

Fallback to sequential without prompting when any of the above is false.

### When Claude Must Still Ask Bryan
1. Task classified as `out-of-scope`
2. Secret/credential exposure risk
3. Destructive file operations (deletion)
4. Live cloud/OAuth/deployment/spend side effects
5. Tauri rebuild required before full Plan 2 completion
6. Contradicts locked roadmap state or accepted checkpoint
7. Auth/approval-gate weakening
8. Touching unrelated dirty files
9. Unavoidable file ownership overlap in protected areas

### Examples

| Bryan says | Claude does |
|------------|-------------|
| "Plan 2C. Proceed." | Router classifies → ownership map → implement → validate → commit → report |
| "Fix this blocker and validate." | Blocker-triage → fix → validate → report |
| "Run takeover validation." | Checkpoint-regression + security-review → report |
| "Parallelize if safe." | Evaluate ownership → worktrees if safe → sequential if not |
| "Review only." | Router: review-only → reads files → reports → no edits |

---

## Coordinator / Worker / Reviewer Flow (Autonomous)

```
Bryan prompt
  └── default-automation-router (classify, plan, ownership)
        └── jarvis-plan-executor (full lifecycle)
              ├── Sequential: plan2-coordinator → implementer(s)
              └── Parallel: plan2-coordinator → worktree-A + worktree-B
                              └── merge-coordinator (PASS/HOLD)
                                    └── Bryan approves merge
```

Action accountability at every step:
- `full-automation-ledger` records every action
- `automation-auditor` reviews ledger for gaps on request
- `security-reviewer` can HOLD any step independently

---

## MCP Status

**MCP connectors: DEFERRED**

Recommended future MCP activation order:
1. Local filesystem/repo only
2. GitHub read-only
3. Browser/dev server
4. Cloud/provider read-only
5. Write-enabled — only after approval gates proven

---

## Remaining Setup

- [x] Hooks activated via `.claude/settings.json`
- [x] Default autonomous execution mode configured
- [x] Router agent and executor skill in place
- [ ] Wire approval notification loop (Plan 2 blocker)
- [ ] Deploy Fargate worker (Plan 2 blocker)
- [ ] Migrate Google OAuth tokens to vault (Plan 2 blocker)
- [ ] Resolve Telegram env mismatch (Plan 2 blocker)
- [ ] Configure Notion connector (Plan 2 blocker)
- [ ] Activate MCP connectors (deferred)

---

## Is Claude Ready for Autonomous Plan 2C Execution?

**YES — autonomous execution infrastructure is complete.**

✓ `DEFAULT_AUTONOMOUS_EXECUTION_MODE` in `CLAUDE.md`
✓ `default-automation-router` agent — automatic task classification
✓ `jarvis-plan-executor` skill — full sprint lifecycle
✓ 12 agents, 12 skills, 16 commands
✓ 4 hooks active
✓ Action ledger and auditor in place
✓ Parallel worktree flow documented and automated
✓ Standing permission documented with explicit hard-stop boundaries
✓ `/autonomous-takeover-check` command for pre-sprint verification

**Run `/autonomous-takeover-check` to verify all components before first Plan 2C sprint.**
**Run `/stop-on-blocker` to triage current blockers.**
**Bryan must explicitly approve start of Plan 2C sprint.**
