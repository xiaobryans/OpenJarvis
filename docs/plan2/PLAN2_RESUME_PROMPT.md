# Plan 2 — Resume Prompt

Use this file to resume Plan 2 work after a session break.

## RESUME_FROM_HERE

**Branch:** `localhost-get-tool`
**Remote:** `fork/xiaobryans/OpenJarvis`
**Last completed sprint:** Final Cutover Gate — Tauri Install + B3 Attribution Fix
**HEAD:** `35c69227` + cutover sprint commit (see below)
**Verdict:** `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_READY_FOR_ACCEPTANCE_REVIEW_FINAL_CUTOVER_PASSED`

## Current Fargate State

- Cluster: `omnix-workbench-071179620006-ap-southeast-1-cluster`
- Service: `omnix-workbench-jarvis-full-service`
- Task def: rev 20 (`omnix-workbench-jarvis-full:20`)
- Image: `jarvis-full-9a1cbdc1`
- Task: `c9a9ca53086f43aaa13db66101e8ed80` — RUNNING + HEALTHY
- Secrets: 15 keys in Secrets Manager; all 12 wired in task def
- ECS Exec: ENABLED (ssmmessages IAM perms active)

## What was just done

**B1 Google OAuth vault migration + cloud auth path + live proof:**
- `scripts/migrate_google_tokens_to_vault.py` — migrated GOOGLE_OAUTH_REFRESH_TOKEN to Secrets Manager (len=103, key 15/15)
- `src/openjarvis/connectors/google_auth.py` — cloud path active: reads GOOGLE_OAUTH_REFRESH_TOKEN + GOOGLE_OAUTH_CLIENT_ID + GOOGLE_CLIENT_SECRET from env; skips disk write in cloud mode
- ECS task def rev 20 — GOOGLE_OAUTH_REFRESH_TOKEN injected via valueFrom ARN; image `jarvis-full-9a1cbdc1`
- B1 LIVE_PROVEN: Gmail HTTP 200 (22 labels), Drive HTTP 200 (quota keys), Calendar HTTP 200 (settings/timezone)

**Final acceptance review sprint:**
- Phase 0: Commit chain verified (5b5b3f31→9a1cbdc1→864a48b8); all pushed to fork
- Phase 1: B1–B8 all confirmed closed/live-proven
- Phase 2: Endpoint security audit PASS (10/10 public endpoints clean; 7/7 auth gates enforced, port 8000)
- Phase 3: 493/494 plan9 tests PASS; secret scan CLEAN; high-entropy scan CLEAN
- Phase 4: Tauri rebuild PASS — `bash scripts/build-local.sh --allow-applications-update` in 117s; artifact v1.0.2 SHA256 b00b8b238ad2; release-local.sh validation PASS; Plan 1 behaviors not regressed
- Phase 5: PLAN2_SOURCE_OF_TRUTH_MATRIX.md, plan2_matrix.json, PLAN2_PROGRESS_LEDGER.md, PLAN2_RESUME_PROMPT.md all updated

## Commit/push remaining

Files to stage (explicit paths only — do NOT use `git add .`):

```
docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md
docs/plan2/plan2_matrix.json
docs/plan2/PLAN2_PROGRESS_LEDGER.md
docs/plan2/PLAN2_RESUME_PROMPT.md
```

Do NOT stage: `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py`, `evidence/`, `scripts/plan1_cockpit_proof.py`, `scripts/plan9_copy_cloud_api_key.sh`, `scripts/plan9_verify_cloud_api_key.py`

Commit message: `Plan 2 final acceptance review and release gate`
Push to: `fork localhost-get-tool`

## B1–B8 Final Proof Matrix

| Blocker | Status | Evidence |
|---------|--------|---------|
| B1 Google OAuth | LIVE_PROVEN | Gmail/Drive/Calendar HTTP 200 from Fargate rev 20; GOOGLE_OAUTH_REFRESH_TOKEN in SM (len=103) |
| B2 Secret injection | CONFIRMED_DEPLOYED | 15 secrets in task def rev 20 |
| B3 Telegram alias | CODE_CLOSED | Both TELEGRAM_BOT_TOKEN and JARVIS_TELEGRAM_BOT_TOKEN accepted |
| B4 Notion | LIVE_PROVEN | NOTION_API_KEY in SM + task def; bot user authenticated |
| B5A Approval gate | CLOSED | ApprovalEngine creates PENDING records for tier 2+ |
| B5B Notification enqueue | CLOSED | NotificationQueue wired on PENDING creation |
| B5C Notification delivery | LIVE_PROVEN | Slack DELIVERED: True; Telegram DELIVERED: True (chat ID 869224118) |
| B6 Fargate | CLOSED | Rev 20 RUNNING + HEALTHY |
| B7 Life-OS cloud sync | LIVE_PROVEN | 0 tasks → S3 life_os_tasks/tasks.jsonl in 219ms |
| B8 Workspace sync | LIVE_PROVEN | 127 entries → S3 jarvis_memory/raw_entries.jsonl in 279ms |
| B9 Voice/TTS | PARKED | Plan 3 — permanent; do NOT reopen |

## Tauri Cutover Status

- `~/Applications/OpenJarvis.app`: INSTALLED — v1.0.2, SHA `b00b8b23...` (via release-local.sh --install)
- `/Applications/OpenJarvis.app`: UPDATED — v1.0.2, SHA `b00b8b23...` (via Bryan-authorized cp -r)
- All three (bundle/home/applications) match ✓
- Signing: adhoc (CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN for founder-local)

## What Bryan/ChatGPT reviewer needs to do

1. Review this report.
2. If accepted: mark `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_ACCEPTED`.
3. Only then: begin Plan 3 (voice/wake/TTS) or post-Plan-2 automation expansion.

## Hard rules active

- Tauri cutover DONE: `/Applications/` + `~/Applications/` both updated to Plan 2 rebuild artifact
- No `git add .`
- No secret values printed
- No fake ACCEPTED/READY
- No Plan 3 voice/wake/TTS until explicit Bryan authorization
- Changed-file-only staging
- Only Bryan/ChatGPT reviewer can accept

---
*Generated: Plan 2 Final Acceptance Review + Tauri Release Gate, 2026-06-25*
