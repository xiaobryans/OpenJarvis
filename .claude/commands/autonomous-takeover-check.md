# /autonomous-takeover-check

**Validate that the full Claude Code autonomous execution infrastructure is
installed, configured, and discoverable.** Run this before the first autonomous
Plan 2C sprint to confirm Claude is ready for takeover.

## What this checks

### 1. CLAUDE.md
- [ ] `DEFAULT_AUTONOMOUS_EXECUTION_MODE` section present
- [ ] `Full Automation Accountability` section present
- [ ] Locked roadmap state documented
- [ ] Hard rules documented
- [ ] Standing permission scope documented
- [ ] Hard-stop boundaries documented

### 2. Agents (`.claude/agents/`)
- [ ] `default-automation-router` — router entry point
- [ ] `plan2-coordinator` — file ownership, routing
- [ ] `backend-implementer` — backend changes
- [ ] `frontend-mobile-implementer` — frontend changes
- [ ] `connector-specialist` — connector wiring
- [ ] `memory-sync-specialist` — memory system
- [ ] `cloud-infra-planner` — infra planning
- [ ] `security-reviewer` — can HOLD
- [ ] `validation-reporter` — exact outputs
- [ ] `docs-matrix-maintainer` — docs/matrix
- [ ] `merge-coordinator` — integration gate
- [ ] `automation-auditor` — ledger review

### 3. Skills (`.claude/skills/`)
- [ ] `openjarvis-validation`
- [ ] `secret-safety-review`
- [ ] `plan2-sprint`
- [ ] `plan2-report`
- [ ] `checkpoint-regression`
- [ ] `changed-file-review`
- [ ] `safe-merge-review`
- [ ] `parallel-worktree`
- [ ] `tauri-deferred-plan2`
- [ ] `blocker-triage`
- [ ] `full-automation-ledger`
- [ ] `jarvis-plan-executor`

### 4. Commands (`.claude/commands/`)
- [ ] `/auto-execute`
- [ ] `/jarvis-plan`
- [ ] `/parallel-auto`
- [ ] `/plan2-next`, `/plan2-sprint`, `/validate-openjarvis`
- [ ] `/secret-scan`, `/checkpoint-regression`, `/plan2-report`
- [ ] `/safe-merge-review`, `/parallel-plan2`, `/stop-on-blocker`
- [ ] `/status-roadmap`, `/automation-ledger`, `/full-auto-setup`

### 5. Hooks (`.claude/hooks/` + `.claude/settings.json`)
- [ ] `settings.json` exists and has PreToolUse/PostToolUse hooks
- [ ] `warn-tauri-build.sh` present (blocks `build-local.sh --install`)
- [ ] `warn-env-access.sh` present (passive)
- [ ] `remind-diff-check.sh` present (passive)
- [ ] `remind-action-ledger.sh` present (passive)

### 6. Action Ledger
- [ ] `full-automation-ledger` skill present
- [ ] `/automation-ledger` command present
- [ ] `automation-auditor` agent present

### 7. Standing Permission
- [ ] `DEFAULT_AUTONOMOUS_EXECUTION_MODE` in `CLAUDE.md` grants standing permission
- [ ] Hard-stop boundaries are documented
- [ ] `default-automation-router` will classify out-of-scope requests correctly

### 8. Blockers
List current Plan 2 blockers from `CLAUDE.md`.
Flag any blocker that would prevent the next sprint from starting.

## Output
```
AUTONOMOUS TAKEOVER CHECK: [READY / NOT READY]

CLAUDE.md:        [✓ / ✗ — missing: ...]
Agents:           [✓ X/12 present / ✗ missing: ...]
Skills:           [✓ X/12 present / ✗ missing: ...]
Commands:         [✓ X/15 present / ✗ missing: ...]
Hooks:            [✓ active / ✗ missing/inactive]
Action ledger:    [✓ ready / ✗ missing]
Standing perm:    [✓ documented / ✗ missing]

Current blockers: [list]
Next task:        [task or "all blocked — see blockers"]

Verdict: READY for autonomous Plan 2C execution
      OR NOT READY — missing: [list]
```
