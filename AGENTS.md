# Jarvis Agent Instructions

**Applies to:** all agents, models, IDEs, and automation platforms operating in this repo —
Jarvis, Windsurf, Claude Code, ChatGPT, Claude, Cursor, API-based agents, IDE agents,
terminal agents, browser agents, and any future automation platform.

**This file is authoritative.** No agent may claim these rules apply to only one tool,
one chat, one IDE, one sprint, one model provider, or one execution environment.

---

## Bryan's Pay-On-Demand Cost-Control Law (Permanent)

Jarvis and all coordinated agents must treat **token/cost efficiency as a mandatory
reliability requirement**. Agents must use a **direct-source-first** workflow:

- Inspect **only** the files, routes, logs, tests, and source-of-truth documents
  directly relevant to the current task.
- Do **not** run broad audits, scan unrelated directories, reread accepted evidence,
  reverify accepted checkpoints, rerun broad tests, rebuild, or repackage unless:
  - the current work touched that area, **or**
  - regression evidence exists, **or**
  - the agent gives a **clear justification before doing so**.

**Final reports must include cost-control accountability:**
1. Files inspected and **why each was inspected**
2. Files changed
3. Tests run and **why those tests were necessary**
4. Accepted checkpoints **intentionally not reverified**
5. Any broader inspection or validation performed, **with justification**
6. Any blockers that caused a stop instead of continued looping

**Enforcement rules:**
- Stop on real blockers instead of repeatedly attempting the same blocked path.
- Fake progress, fake tools, fake skills, fake counts, fake validation, and fake
  completion are **forbidden**.
- Planned, degraded, blocked, and not_configured capabilities must always be
  reported **separately** from available capabilities.
- No tool or skill may be counted as `available` unless it has a real executor
  and `implementation_status == AVAILABLE`.

**Machine-readable:** `openjarvis.governance.constitution.COST_CONTROL_LAW`
**Human-readable:** `docs/JARVIS_CONSTITUTION.md` § 7

---

## Governance Constitution

The full governance doctrine is in `src/openjarvis/governance/constitution.py`
and summarized in `docs/JARVIS_CONSTITUTION.md`. Key rules:

- Hard gates require explicit owner approval — no exception.
- Real outbound sends (Slack/Telegram/email) are hard-gated.
- Destructive git/filesystem/data ops are hard-gated.
- Production deploys (AWS/Vercel/Supabase/Stripe/billing) are hard-gated.
- Secrets must never appear in logs, responses, or commits.
- `ACCEPT` verdict requires concrete verified evidence — never assumed.
- `HOLD` when evidence is missing, incomplete, or assumed.
- `UNSAFE` when a hard gate is violated.

## Project Context

OMNIX is Project 1 (`project_id="omnix"`, `priority=1`). Jarvis supervises all
active projects concurrently — not OMNIX only. Future projects are registered via
`ProjectRegistry.register(ProjectProfile(...))`.

## Tool Execution

All tool execution goes through `ToolExecutionGateway`. No agent may bypass it.
Tools with `implementation_status != AVAILABLE` are not available — report them
as not_configured/degraded/planned, never as available.
