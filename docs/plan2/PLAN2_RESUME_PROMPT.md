# Plan 2 — Resume Prompt

Use this file to resume Plan 2 work after a session break.

## RESUME_FROM_HERE

**Branch:** `localhost-get-tool`
**Remote:** `fork/xiaobryans/OpenJarvis`
**Last completed sprint:** Plan 2 Fargate Current-Code Redeploy + Runtime Proof Sprint
**HEAD:** `90471fce` (Plan 2 B6 live proof: fargate_readiness SSL fix)
**Commit pending:** Yes — stage and commit docs update (PLAN2_AUTONOMOUS_SESSION_STATE.md, PLAN2_PROGRESS_LEDGER.md, PLAN2_RESUME_PROMPT.md)
**Verdict:** `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD`

## What was just done

Plan 2 Fargate Current-Code Redeploy + Runtime Proof Sprint:

- **Docker build** — `Dockerfile.full` rebuilt; all 3 build validations passed; image `jarvis-full-90471fce` pushed to ECR.
- **ECS task def rev 17** — 11 secrets total; SLACK_BOT_TOKEN + TELEGRAM_BOT_TOKEN + GOOGLE_CLIENT_SECRET + GOOGLE_OAUTH_CLIENT_ID added as Secrets Manager references.
- **ECS service** — force-new-deployment to rev 17; PRIMARY rolloutState=COMPLETED; ALB target `10.0.0.207` healthy.
- **B6 CLOSED:** Fargate now running `git_commit=90471fce` with `engine=cloud`. All Plan 2 routes active.
- **B2 partial:** SLACK_BOT_TOKEN + TELEGRAM_BOT_TOKEN now injected in Fargate task def. Dispatcher wiring still needed.
- **Smoke tests:** All public endpoints HTTP 200; life-os shows `b7_local_store_type=sqlite`; approval gate READY.
- **plan9 tests:** 440/440 passing (pre-existing failure unchanged).

## Immediate next step (commit/push)

Files to stage (explicit paths only — do NOT use `git add .`):

```
docs/plan2/PLAN2_AUTONOMOUS_SESSION_STATE.md
docs/plan2/PLAN2_PROGRESS_LEDGER.md
docs/plan2/PLAN2_RESUME_PROMPT.md
```

Do NOT stage: `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py`, `evidence/`, `scripts/plan1_cockpit_proof.py`, `scripts/plan9_copy_cloud_api_key.sh`, `scripts/plan9_verify_cloud_api_key.py`

Commit message: `Plan 2 Fargate redeploy: rev 17 live, git_commit=90471fce, engine=cloud, B6 closed`
Push to: `fork localhost-get-tool`

## Remaining blockers (all require external action or code changes)

| ID | Blocker | Status | Requires |
|----|---------|--------|----------|
| B1 | Google OAuth tokens → vault/cloud migration | Code-side abstraction done | Live OAuth credentials + vault setup |
| B2 | Dispatcher not wired; GITHUB_TOKEN local only | SLACK/TELEGRAM injected in task def | Dispatcher code wiring + GITHUB_TOKEN Fargate injection |
| B4 | Notion not configured | Code-side check done | Actual Notion API token |
| B5C | External notification delivery | CONFIGURED_NOT_DEPLOYED | Dispatcher wiring to send Slack/Telegram |
| B6 | ~~Fargate worker / cloud execution~~ | **CLOSED** — `90471fce`, engine=cloud | N/A |
| B7 (cloud) | Life-OS SQLite not synced to cloud | LAYER_REQUIRES_DEPLOYMENT | CloudSync class + Fargate runtime |
| B8 | Full workspace sync to S3 | LAYER_REQUIRES_DEPLOYMENT | CloudSync + Fargate runtime |

## Next external actions needed to unblock Plan 2 acceptance

1. **Wire B2 connector dispatcher** — implement NotificationDispatcher to actually send Slack/Telegram; tokens are now present in Fargate.
2. **Configure Notion API token** → unblocks B4
3. **Implement CloudSync class** → unblocks B7 (cloud) + B8
4. **Wire Life-OS cloud sync** → unblocks B7 (cloud)
5. **Migrate Google OAuth tokens to cloud vault** → unblocks B1

## Files changed in last sprint (docs only — cloud-side work)

- `docs/plan2/PLAN2_AUTONOMOUS_SESSION_STATE.md`
- `docs/plan2/PLAN2_PROGRESS_LEDGER.md`
- `docs/plan2/PLAN2_RESUME_PROMPT.md`

## Hard rules reminder

- No Tauri rebuild
- No `git add .`
- No secret values printed
- No fake ACCEPTED/READY
- No Plan 3 voice/wake/TTS
- Changed-file-only staging
- HOLD verdict until all in-scope blockers are closed
- Only Bryan/ChatGPT reviewer can accept

---
*Generated: Plan 2 Fargate Current-Code Redeploy + Runtime Proof Sprint, 2026-06-24*
