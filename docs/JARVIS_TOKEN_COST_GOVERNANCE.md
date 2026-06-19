# Jarvis Token and Cost Governance

**Status:** Active — mandatory for all agents and automations
**Applies to:** All projects — OMNIX, OpenJarvis, personal tasks, research, and future projects
**Enforced by:** AGENTS.md, .cursorrules, doctor checks, governance constitution, CosGmOrchestrator
**Machine-readable:** `openjarvis.governance.constitution.COST_CONTROL_LAW`

**Model/provider sufficiency disclosure is mandatory.** No silent fallback.
Missing provider/key must surface in status/routes/doctor, not silently degrade.

---

## Purpose

Jarvis runs on Bryan's pay-on-demand API account. Every token has a direct
cost. This document is the permanent, authoritative rule set for token
efficiency across all agents, models, IDEs, and automation platforms.

---

## Mandatory Workflow: Direct-Source-First

Every agent must use a **direct-source-first** workflow:

1. `rg` / `grep` to find the exact file and line number.
2. Read only 30–80 lines around the match.
3. Edit only what is needed.
4. Verify minimally (one targeted test, not a full re-run).
5. Stop on blocker — do not loop the same approach more than 3 times.

**Never:**
- Read entire files when grep found the target.
- Run full repo scans or `task` / `explore` subagents for simple fixes.
- Re-verify accepted checkpoints (Wave 1–4, NUS 1A–1C) unless directly touched.
- Re-run unrelated test suites.
- Reread RULES.md / AGENTS.md on every message.

---

## Model Tier Discipline

| Tier | Model | When |
|------|-------|------|
| Small | Composer 2.5 | 1 file, CSS, docs, rule edits |
| Medium | Sonnet 4.6 | 1–5 files, single feature, investigation |
| Large | Opus 4.7 | Justified: 6+ files, architecture, migrations |

Opus is NOT the default. Agent must justify before using Opus.
Agent calculates projected monthly usage and states it in every model advice line.

---

## Accepted Checkpoint Policy

Previously accepted work is not re-verified unless:
- The current task directly touches that area, OR
- Regression evidence exists.

Accepted checkpoints:
- Wave 1–4: ACCEPT
- NUS 1A–1C: ACCEPT
- US12, US14–US18: ACCEPT (US13: HOLD)

Do not rerun Wave 1–4 or NUS 1A–1C tests unless regression evidence exists.

---

## Scope Control Rules

1. **No broad audits** unless architecture, security, deploy, release, or
   certification work explicitly requires it.
2. **No repo tours** — go directly to relevant files via symbol lookup.
3. **No parallel discovery reads** before the first useful edit.
4. **Scoped tasks** — if user names a file or area, only touch that path.
5. **One complete validation pass** per task using exact command outputs.
   No repeated verification loops.

---

## Loop Cap

Max 3 attempts on the **same approach** for any failing item.

After 3 fails:
1. STOP repeating the same approach.
2. Break down the item into smaller sub-steps.
3. Fix it directly.
4. Continue with the rest of the work.

Never skip a failing item — break it down and fix it.

---

## Enforcement

These rules are enforced in:
- `AGENTS.md` (authoritative, all platforms)
- `.cursorrules` (Cursor IDE)
- `docs/JARVIS_TOKEN_COST_GOVERNANCE.md` (this file)
- Doctor checks: agents should verify cost governance constraints in checks

Future agents inherit these rules via AGENTS.md — no per-agent configuration needed.

---

## See Also

- `AGENTS.md` — § "Bryan's Pay-On-Demand Cost-Control Law"
- `docs/JARVIS_CONSTITUTION.md` — § 7 (Cost-Control Law)
- `.cursor/rules/10-api-token-and-model.mdc`
- `.cursor/rules/07-strict-targeted-access.mdc`

---

## NUS 1F Update — Budget-Bounded Session Governance

NUS 1F adds explicit budget enforcement to high-autonomy sessions:

### Session budget fields
Every `HighAutonomySession` carries:
- `cost_budget` — maximum cost spend in this session (float)
- `token_budget` — maximum token count (int)
- `time_budget` — maximum wall clock seconds (float)

These are recorded in the session object and structured decision records. Budget enforcement against live usage tracking is a future sprint task.

### Cost-control compliance
NUS 1F implementation follows Bryan's Pay-On-Demand Cost-Control Law:
- Only files directly relevant to NUS 1F were inspected
- No broad repo audit
- No reread of accepted NUS 1A–1E internals
- Changed-file-only validation
- grep → narrow read → edit → one validation pass

### Token governance in action classification
The `AutonomyActionPolicy` supports cost/token fields in structured decision records:
- `cost_estimate` — estimated cost impact per decision
- `token_estimate` — estimated token count
These feed into NUS learning for future budget optimization.

See `docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md` for session budget fields specification.
