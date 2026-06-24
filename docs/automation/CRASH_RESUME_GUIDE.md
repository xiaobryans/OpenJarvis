# OpenJarvis Crash-Resume Guide

**Purpose:** Enable safe session recovery if Claude Code stops from context cap, crash, rate limit, or unexpected exit.

## What "safe resume" means

A safe resume is one where:
1. The repo is on the expected branch and HEAD (or the new HEAD from the last commit).
2. No unintended dirty files are staged.
3. The next step is clearly documented in the handoff files.
4. No hard blocker prevents continuation.
5. `safe_to_continue_automatically=YES` in the session state.

---

## Option A — Automatic resume (preferred)

### 1. Open a new Claude Code session in `/Users/user/OpenJarvis`

### 2. Run `/crash-resume`
This command:
- Reads `docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md`
- Compares to actual git state (branch, HEAD, dirty files)
- Checks `safe_to_continue_automatically` flag
- Prints the `RESUME_FROM_HERE` section

### 3. If RECOMMENDATION is AUTO_RESUME_SAFE
Paste the resume prompt from `docs/automation/POST_PLAN2_AUTOMATION_RESUME_PROMPT.md` into the new session and continue.

### 4. If RECOMMENDATION is MANUAL_REVIEW_REQUIRED
Follow Option B below.

---

## Option B — Manual resume

### Step 1: Open a new Claude Code chat in `/Users/user/OpenJarvis`

### Step 2: Paste this opening block
```
I'm resuming an OpenJarvis automation sprint after a session break.

Branch: localhost-get-tool
Remote: fork/xiaobryans/OpenJarvis
Sprint: POST_PLAN_2_CLAUDE_CODE_AUTOMATION_EXPANSION_AND_OPTIMIZATION

Please:
1. Run git branch --show-current
2. Run git rev-parse HEAD
3. Run git status --short
4. Read docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md
5. Read docs/automation/POST_PLAN2_AUTOMATION_RESUME_PROMPT.md
6. Tell me: does actual repo state match the handoff? What is safe_to_continue_automatically?
7. If safe: proceed from RESUME_FROM_HERE in the resume prompt.
8. If not safe: show me the discrepancy and wait for my instruction.
```

### Step 3: Verify before auto-proceeding

Do NOT auto-proceed if:
- Branch is wrong (not `localhost-get-tool`)
- HEAD doesn't match expected or last committed HEAD
- Unexpected dirty files (beyond known pre-existing list)
- Hard blocker in session state
- `safe_to_continue_automatically=NO`

### Step 4: Resume from RESUME_FROM_HERE

The `RESUME_FROM_HERE` marker in the session state file tells Claude exactly which phase/checkpoint to resume from.

---

## Known pre-existing dirty files (safe to ignore)

These files are always dirty/untracked in this repo. Do NOT stage or modify them:
- `JARVIS_OMNIX_HANDOFF.md`
- `tests/workbench/test_us14a_fixture.py`
- `evidence/`
- `scripts/plan1_cockpit_proof.py`
- `scripts/plan9_copy_cloud_api_key.sh`
- `scripts/plan9_verify_cloud_api_key.py`

---

## Safety invariants (never bypass these on resume)

1. **Never use `git add .`** — always explicit file paths.
2. **Never print secret values.**
3. **Never mark anything ACCEPTED** — only Bryan can.
4. **Never start Plan 3** — permanently parked.
5. **Never start Plan 4–6 implementation** — planning only in this sprint.
6. **Never run Tauri rebuild** — deferred until Bryan explicitly authorizes.
7. **Stop on any hard blocker** — do not proceed past blockers.

---

## Supervisor script (local-only, safe)

A minimal supervisor is available at `scripts/auto_resume_check.py` (if created).
It:
- NEVER reads secrets
- NEVER runs destructive cleanup
- NEVER uses `git add .`
- NEVER restarts endlessly (max 1 check per invocation)
- Reads handoff files
- Verifies branch/HEAD/dirty state
- Reports SAFE_TO_CONTINUE or MANUAL_REVIEW_REQUIRED

Run it manually (not as a daemon):
```bash
python3 scripts/auto_resume_check.py
```

It does NOT start Claude Code automatically — that decision is Bryan's.

---

## Handoff file locations

| File | Purpose |
|------|---------|
| `docs/automation/POST_PLAN2_AUTOMATION_SESSION_STATE.md` | Current phase, branch, HEAD, blockers, safe_to_continue flag |
| `docs/automation/POST_PLAN2_AUTOMATION_PROGRESS_LEDGER.md` | Action ledger for current sprint |
| `docs/automation/POST_PLAN2_AUTOMATION_RESUME_PROMPT.md` | Self-contained resume prompt for next session |
| `docs/plan2/PLAN2_AUTONOMOUS_SESSION_STATE.md` | Plan 2 session state (updated after Plan 2 sprints) |
| `docs/plan2/PLAN2_RESUME_PROMPT.md` | Plan 2 resume prompt |

---

*Last updated: Post-Plan-2 automation expansion sprint, 2026-06-25*
