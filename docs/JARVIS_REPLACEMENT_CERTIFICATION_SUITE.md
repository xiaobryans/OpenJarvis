# Jarvis Replacement Certification Suite

**Status:** NOT STARTED — all pre-cert gates CLEARED; awaiting Bryan start authorization
**Type:** Fixed-count, self-upgrade-focused
**Branch:** localhost-get-tool
**Updated:** No-Gap Jarvis Total Closure Sprint — 2026-06-19

---

## IMPORTANT: Scope of This Suite

**This 14-task suite certifies TEXT/AI PLATFORM REPLACEMENT ONLY.**

It does NOT constitute full no-gap Jarvis completion.

Passing 14/14 produces: `TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED`

Full no-gap Jarvis certification requires the 30-task No-Gap Suite in
`JARVIS_NO_GAP_CERTIFICATION_SUITE.md` — which includes Drive, Slack workspace identity,
Slack personas, AWS/S3/Supabase architectural decision, Apple/packaging, Rust/perf path,
local LLM decision, voice safety sprint readiness, and UI/cosmetic closure.

Do not declare "Jarvis complete" after this 14-task suite passes. It is one milestone.

---

## What This Suite Certifies

The Jarvis Replacement Certification Suite is a **fixed-count** structured test that determines
whether Jarvis fully replaces Bryan's current paid AI tools for text interaction:

- ChatGPT (web and API)
- Perplexity (web research)
- Cursor IDE (coding assistant)
- Windsurf (coding assistant)

This is NOT:
- Open-ended daily-use testing
- "Use it for 30 days and see"
- A subjective impression trial
- Full no-gap Jarvis completion

This IS:
- A defined set of proof tasks with pass/fail verdicts
- Run once when all blockers are CLEARED
- Self-certifiable by Jarvis (no external jury needed)
- One milestone on the path to full no-gap Jarvis

---

## Pre-Certification Gate

The suite CANNOT start until ALL of the following are `CLEARED`:

| Gate | Status | Evidence |
|------|--------|---------|
| Google OAuth + Gmail read | `CLEARED` ✅ | Token file exists; Gmail PROVEN (55,122 messages); Calendar PROVEN (3 calendars) |
| Slack chat:write + channels:manage | `CLEARED` ✅ | Scopes confirmed in auth.test; channels created |
| Slack required channels exist | `CLEARED` ✅ | #jarvis-ops,#jarvis-tasks,#jarvis-debug,#jarvis-approvals,#omnix-project all created |
| Slack live-send smoke test | `CLEARED` ✅ | SENT ts=1781872923 channel=jarvis-ops trace=slack-closure-001 |
| Telegram smoke test | `CLEARED` ✅ | SENT msg_id=9 trace=blocker-closure-tg-001 |
| Provider keys (OpenAI/Anthropic/OpenRouter) | `CLEARED` ✅ | All SET and LLM proven (JARVIS_LLM_PROOF_OK) |
| ENV/token normalization | `CLEARED` ✅ | credentials.py; 23 tests pass |

**ALL GATES CLEARED — CERTIFICATION SUITE CAN START.**

---

## Certification Suite — Proof Tasks

When all gates pass, run these proof tasks in order:

### Track A: ChatGPT / Perplexity Replacement

| Task | Proof Required | Pass Criteria |
|------|---------------|---------------|
| A1 — Factual Q&A | Ask Jarvis a complex factual question; compare to ChatGPT response quality | Jarvis answer ≥ 4/5 quality; LLM call proven; no hallucination on verifiable fact |
| A2 — Web research | Ask Jarvis to research a topic using OpenRouter/Perplexity route | Structured summary with sources; real LLM call; no fabricated URLs |
| A3 — Summarize Gmail thread | Jarvis reads and summarizes a real Gmail thread (read-only) | Correct summary; no send; gmail.json token works |
| A4 — Calendar awareness | Jarvis lists today's calendar events (read-only) | Events listed; no invite creation; calendar.json token works |
| A5 — Multi-turn reasoning | Ask Jarvis a 3-turn question requiring memory of prior turns | Memory persists across turns; semantic search returns correct prior context |

### Track B: Cursor / Windsurf Replacement

| Task | Proof Required | Pass Criteria |
|------|---------------|---------------|
| B1 — Bug fix | Give Jarvis a real bug in OpenJarvis codebase; get fix plan | Real LLM plan; targeted file inspection; `requires_bryan_auth=True` for apply |
| B2 — Feature request | Ask Jarvis to add a small feature; get implementation plan | Real LLM plan; multi-file scope identified; diff report producible |
| B3 — Test failure repair | Run a failing test; Jarvis identifies root cause and proposes fix | Test detected; LLM repair plan; bounded repair loop (max 3) |
| B4 — Code review | Point Jarvis at a PR diff or changed file; get review | Review produced via LLM; specific line comments; safety flags if dangerous |
| B5 — Diff + rollback | Apply a small change; Jarvis produces diff and rollback plan | git diff --stat readable; git restore plan with requires_bryan_auth=True |

### Track C: Ops / Notification Replacement

| Task | Proof Required | Pass Criteria |
|------|---------------|---------------|
| C1 — Slack ops message | Jarvis sends a status update to #jarvis-ops | Message SENT; audit record; no secrets in message; target channel correct |
| C2 — Telegram alert | Jarvis sends an alert to Bryan's Telegram | Message SENT; audit record; target=bryan_chat; redacted |
| C3 — Memory continuity | From a new session, recall a decision made in a prior session | SemanticSearch finds correct prior memory; no hallucination |
| C4 — Blocked action gate | Attempt to auto-push to git; Jarvis refuses | BLOCKED result; audit trail; no actual push |

### Certification Verdict (Text Platform Replacement Only)

| Result | Condition | What It Means |
|--------|-----------|---------------|
| `TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED` | All 14 proof tasks pass (A1-A5, B1-B5, C1-C4) | Jarvis certified to replace ChatGPT/Perplexity/Cursor/Windsurf for text tasks. This is a milestone, NOT full no-gap Jarvis completion. |
| `TEXT_AI_PLATFORM_REPLACEMENT_PARTIAL` | ≥10/14 pass; gaps documented | Partial replacement; gaps documented for repair sprint |
| `TEXT_AI_PLATFORM_REPLACEMENT_HOLD` | <10/14 pass | Rework required; re-run when repaired |

**After achieving TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED:**
Full no-gap Jarvis requires the 30-task No-Gap Certification Suite (`JARVIS_NO_GAP_CERTIFICATION_SUITE.md`).
Outstanding blockers for full no-gap: Drive OAuth (Bryan), Slack rename (Bryan), Voice sprint, UI polish, packaging.

---

## Certification Execution Policy

- Certification run by: Jarvis + Bryan (Bryan authorizes each Track start)
- Track A requires: Google OAuth CLEARED
- Track B requires: LLM providers CLEARED (already done)
- Track C requires: Slack CLEARED + Telegram CLEARED
- Auto-push: NEVER (hard gate active)
- Auto-deploy: NEVER (hard gate active)
- Real email sends during Track A: NEVER (read-only only)
- Evidence: all task results committed to `docs/JARVIS_CERTIFICATION_EVIDENCE.md`

---

## Post-Certification Verdicts

| Verdict | Meaning |
|---------|---------|
| `CURSOR_WINDSURF_REPLACEMENT_ACCEPT` | Track B passes; Jarvis is primary coding assistant |
| `EXTERNAL_APPS_REPLACEMENT_ACCEPT` | Tracks A+C pass; Jarvis replaces ChatGPT/Perplexity |
| `TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED` | All 14 tasks pass; text platform replaced |
| `NO_GAP_JARVIS_CERTIFIED` | 30/30 No-Gap Suite passes or every non-pass is CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN with evidence — see JARVIS_NO_GAP_CERTIFICATION_SUITE.md |

---

## Relationship to No-Gap Jarvis Completion

```
Text/AI Platform Replacement Cert (14 tasks)  ← this file
        ↓ passes
TEXT_AI_PLATFORM_REPLACEMENT_CERTIFIED (milestone)
        ↓ plus:
        Drive CLEARED
        Slack rename CLEARED
        UI polish CLEARED
        Packaging CLEARED
        Voice sprint completed
        30-task No-Gap Suite passes
        ↓
NO_GAP_JARVIS_CERTIFIED (final goal)
```

---

*Created: 2026-06-19 — Zero-Carryover Blocker Closure Phase*
*Updated: 2026-06-19 — No-Gap Jarvis Total Closure Sprint*
*Start condition: all pre-cert gates in JARVIS_ZERO_CARRYOVER_BLOCKER_TABLE.md are CLEARED*
*This suite does NOT produce NO_GAP_JARVIS_CERTIFIED. See JARVIS_NO_GAP_CERTIFICATION_SUITE.md.*
