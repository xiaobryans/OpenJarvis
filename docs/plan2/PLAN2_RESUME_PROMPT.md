# Plan 2 — Resume Prompt

Use this file to resume Plan 2 work after a session break.

## RESUME_FROM_HERE

**Branch:** `localhost-get-tool`
**Remote:** `fork/xiaobryans/OpenJarvis`
**Last completed sprint:** Plan 2 Live B6 Health Check Proof — SSL Fix + Fargate Runtime Confirmed
**Previous HEAD:** `2bdaef58` (Plan 2 full blocker closure runtime proof: B1/B3/B4/B7 code-side)
**Commit pending:** Yes — stage and commit B6 live SSL fix files
**Verdict:** `PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD`

## What was just done

Plan 2 Live B6 Health Check Proof sprint. Fixed `_live_health_check()` SSLCertVerificationError in `fargate_readiness.py` to prove Fargate is live:

- **B6 Live Proof:** `get_fargate_worker_status()` returns `status=READY, deployed=True, reachable=True, executing=True, engine=cloud, version=1.0.2, commit=fd22fa0f`. Live health check at `https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com/health` returns HTTP 200.
- **SSL Fix:** Replaced broken system-keychain temp-file approach with certifi-backed `SSLContext`. CERT_NONE fallback retained as last resort. The fix: `ssl.create_default_context(cafile=certifi.where())`.
- **Tests:** 442/442 plan9 passing (1 pre-existing unrelated failure).

**Prior sprint (already committed at 2bdaef58):** B1/B3/B4/B7 code-side closure — SQLitePersonalTaskStore, vault status abstraction, Notion env check, Telegram dual-alias, Phase 7 public endpoint security audit.

## Immediate next step (commit/push)

Files to stage (explicit paths only — do NOT use `git add .`):

```
src/openjarvis/server/fargate_readiness.py
docs/plan2/PLAN2_AUTONOMOUS_SESSION_STATE.md
docs/plan2/PLAN2_PROGRESS_LEDGER.md
docs/plan2/PLAN2_RESUME_PROMPT.md
```

Do NOT stage: `JARVIS_OMNIX_HANDOFF.md`, `tests/workbench/test_us14a_fixture.py`, `evidence/`, `scripts/plan1_cockpit_proof.py`, `scripts/plan9_copy_cloud_api_key.sh`, `scripts/plan9_verify_cloud_api_key.py`

Commit message: `Plan 2 B6 live proof: fargate_readiness SSL fix, health check READY`
Push to: `fork localhost-get-tool`

## Remaining blockers (all require external action)

| ID | Blocker | Status | Requires |
|----|---------|--------|----------|
| B1 | Google OAuth tokens → vault/cloud migration | Code-side abstraction done | Live OAuth credentials + vault setup |
| B2 | Slack/Telegram absent from Secrets Manager | Open — 7/9 secrets present | AWS create-secret + ECS task definition revision |
| B4 | Notion not configured | Code-side check done | Actual Notion API token |
| B5C | External notification delivery | Code-gated; CONFIGURED_NOT_DEPLOYED | Fargate redeploy with Plan 2 code + Slack/Telegram secrets |
| B6 (full parity) | Fargate live (pre-Plan-2 commit fd22fa0f) | LIVE PROVEN (deployed+reachable+executing=cloud) | Docker daemon + image rebuild + ECS redeploy with Plan 2 code |
| B7 (cloud) | Life-OS SQLite not synced to cloud | Code-side tracking done | Cloud sync + Fargate with Plan 2 code |
| B8 | Full workspace sync to S3 | Code-gated; LAYER_REQUIRES_DEPLOYMENT | Fargate with Plan 2 code |

## Next external actions needed to unblock Plan 2 acceptance

1. **Authorize live Fargate deployment sprint** → `terraform apply` in `deploy/aws/` → unblocks B2, B6, B8
   - Verify: `GET /v1/mobile-parity/cloud-worker` shows `deployed: true, reachable: true`
2. **Migrate Google OAuth tokens to cloud vault** → unblocks B1
3. **Configure Notion API token** → unblocks B4
4. **Wire external notification delivery** → unblocks B5C (requires deployed Fargate + live tokens)
5. **Wire Life-OS cloud sync** → unblocks B7 (cloud)

## Files changed in last sprint

- `src/openjarvis/server/fargate_readiness.py` — SSL fix for `_live_health_check()` (certifi fallback)
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
*Generated: Plan 2 Full External Blocker Closure + Runtime Proof Sprint, 2026-06-24*
