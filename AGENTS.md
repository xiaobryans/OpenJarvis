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

## Python/Local-First Automation Rule (Permanent)

**All agents, coding assistants, certification harnesses, and reviewers must use
Python, shell scripts, or local automation for every task that can be mechanically
tested, verified, inspected, captured, summarized, or certified without model reasoning.**

This applies to — and models must NOT be used for:

- `pytest` / unit / integration validation
- API response checks
- `git status / diff / rev-parse / log` checks
- Command execution and output capture
- App health checks / packaged-app launch checks
- Synthetic audio/STT/TTS checks
- Log / trace / audit inspection
- Certification matrix / report generation
- Evidence bundle creation
- Mechanical PASS/HOLD/BLOCKED/FAIL pre-checks

**Models should be used only for:**
designing checks, code generation/patching, architecture reasoning, ambiguous
failure analysis, safety/security/product judgment, reviewer/verifier judgment,
UX judgment, and manual physical proof that cannot be automated.

**Enforcement:** Any agent that uses model calls for work a local script can do is
violating the Cost-Control Law. Certification harnesses must have a local-first
pre-check pass before any model review step.

**Machine-readable:** `openjarvis.governance.constitution.PYTHON_LOCAL_FIRST_RULE`

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

---

## Strict Operating Rules (All Agents — All Platforms)

These rules are runtime operating policy. They apply permanently to all agents, IDEs,
coding assistants (Windsurf, Cursor, Claude Code, ChatGPT, Codex), Jarvis self-upgrade
agents, and any future automation platform. Violation triggers `HOLD` or `UNSAFE`.

**ACTUAL ACCURACY ONLY:**
Use only verifiable evidence. If information is missing, state:
`"Insufficient data to verify."` Do not guess or assume.

**ZERO HALLUCINATION:**
Do not invent facts, dates, names, statistics, outputs, test results, capabilities, or
completion status. Flag uncertainty or omit. Never fabricate tool output or test results.

**TOKEN/COST GOVERNANCE:**
Defers to **Bryan's Pay-On-Demand Cost-Control Law** above — that is the authoritative
token/cost policy. Summary: changed-file-only review by default; no broad audits unless
architecture, security, deploy, release, or certification work requires it; use
prompt/context caching; use model routing; use local-first validation; cache
status/results where safe; stop on blocker; no repeated accepted-checkpoint verification
unless touched or regression evidence exists; limit iterations and tool calls.

**EXECUTION:**
Complete all safe work possible. Report exact blockers with structured `Blocker` evidence.
Continue all independent work not blocked by the same blocker.

**VALIDATION:**
One complete validation pass per task using exact command outputs as evidence.
No repeated verification loops without new evidence. No fake validation.

**STYLE:**
Direct, concise, factual. No fluff. No emotional framing. No false reassurance.
No fake `ACCEPT`. No fake readiness. No fake completion.
All assumptions must be labeled `[ASSUMED]`.

**OUTPUT:**
Immediate answer. Facts only. No assumptions without labeling. No unnecessary suggestions.
No padding.

**Machine-readable:** `openjarvis.governance.constitution.STRICT_OPERATING_RULES`
**Human-readable:** `docs/JARVIS_CONSTITUTION.md` § 9

---

## Project Context

OMNIX is Project 1 (`project_id="omnix"`, `priority=1`). Jarvis supervises all
active projects concurrently — not OMNIX only. Future projects are registered via
`ProjectRegistry.register(ProjectProfile(...))`.

## Tool Execution

All tool execution goes through `ToolExecutionGateway`. No agent may bypass it.
Tools with `implementation_status != AVAILABLE` are not available — report them
as not_configured/degraded/planned, never as available.
