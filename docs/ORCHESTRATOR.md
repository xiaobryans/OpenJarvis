# Orchestrator Stack — Status & Option-A Implementation Guide

**Status:** PARKED (decision: Option B, 2026-06-26). Not on the live chat path.
**Next major sprint:** Option A — wire the full hierarchy into live chat. This
document is the spec to execute that sprint. It is a TODO/implementation guide,
not a "parked indefinitely" notice.

---

## 1. Current reality (verified)

The live chat path (`POST /v1/chat/completions` → `server/routes.py` →
`_handle_stream_agent` → `app.state.agent`, an `OrchestratorAgent`) does **not**
touch any of the modules below. They are real, substantial code that no real
user request currently reaches.

| Module | Lines | Reachable today via | Entanglement |
|---|---|---|---|
| `orchestrator/cos_gm.py` (`CosGmOrchestrator`) | ~530 | `/v1/orchestrator/*` (dry-run), `/v1/frontdoor/submit` (classify-only), `doctor/checks.py`, tests | ~19 importers (plan9, frontdoor, manager_registry, nus, …) |
| `orchestrator/activation.py` | ~838 | cos_gm + orchestrator routes | medium |
| `agents/hybrid/` (conductor, toolorchestra, archon, minions, …) | ~12,261 | imported only by `agents/__init__.py` (registration) + `tools/storage/__init__.py` | low (registration-only) |
| `agents/hybrid/skillorchestra/` | ~3,126 | `evals/scorers/swebench_harness.py` + hybrid internals | used by **evals** (do not remove without fixing evals) |

**Why parked, not removed:** cos_gm has ~19 importers (removal cascades and
would break doctor checks); skillorchestra is load-bearing for the SWE-bench
eval. Removal is high-risk for low benefit. Parking loses nothing and keeps the
~16.7k lines available for Option A.

---

## 2. Target architecture (Bryan's vision)

```
Bryan → Jarvis PA → COS/GM → Domain Managers → Workers → Testers → COS/GM → Jarvis PA → Bryan
```

- **Jarvis PA** — the single user-facing front door (identity, persona, the
  voice Bryan talks to). Owns the conversation and the final reply.
- **COS/GM** (Chief of Staff / General Manager) — `CosGmOrchestrator`. Receives
  the task from Jarvis PA, plans it (`activation.py` domain→manager mapping),
  dispatches to managers, runs the verifier gate, returns a synthesized result.
- **Domain Managers** — own a domain (e.g. coding, comms, research, finance,
  ops). Decompose the task and assign workers. (~17 today — audit in §5.)
- **Workers** — do the actual unit of work. Prefer **many small-scope workers**
  over few large ones.
- **Testers** — verify worker output before it flows back up (the existing
  `VerifierGate` is the seed of this).

### Tiered routing (latency-aware) — the core behavior to implement

| Tier | Budget | Path |
|---|---|---|
| **Instant** | < 3 s | Jarvis PA answers directly. No hierarchy. (e.g. time, simple recall, chit-chat.) |
| **Fast** | < 15 s | Jarvis PA → COS/GM → **one** manager → worker(s) → back. |
| **Standard** | 15 s – 2 min | Full hierarchy, sequential. |
| **Complex** | 2 min+ | Full hierarchy, **parallel workers**, with **live status updates** to Bryan. |

A classifier (cheap, local-first — reuse the `complexity` scorer already in
`routes.py`) picks the tier per turn. Default to the cheapest tier that fits.

### Live status updates (for Standard/Complex)

- Stream what Jarvis is doing in real time over the existing SSE channel — never
  leave Bryan in silence.
- Give an **up-front time estimate** for complex tasks.
- **Update the estimate** as work progresses.
- Report **actual completion time** when done.
- Surface per-stage progress ("manager X dispatched 3 workers", "tester passed
  2/3", …) as SSE `status`/`progress` events the UI can render.

---

## 3. Where the wiring connects (concrete entry points)

1. **`server/routes.py`** — the live chat dispatch. Today: `_handle_stream_agent`
   runs a single `OrchestratorAgent`. Option A: add a tier classifier; for
   Fast/Standard/Complex, route through `JarvisFrontDoor.handle()` /
   `CosGmOrchestrator` instead, streaming status events back. Keep Instant on
   the current direct path. Preserve the safe fallback to the current agent on
   any orchestration error (do not regress chat).
2. **`frontdoor/frontdoor.py`** — `JarvisFrontDoor.handle()` already chains to
   `CosGmOrchestrator`. This is the intended bridge; today it's only called by
   doctor + tests.
3. **`server/frontdoor_routes.py`** — `/v1/frontdoor/submit` is **classify-only**
   today (returns a routing summary, never executes). Option A: make it actually
   invoke the orchestrator, or fold its classification into the chat path.
4. **`orchestrator/worker_adapters.py`** — several adapters return **dry-run
   stubs** (`_execute_safe` returns a planning dict). Option A: replace stubs
   with real execution behind the NUS gate (now correctly fail-closed).
5. **`orchestrator/cos_gm.py`** — real plan→dispatch→verify loop. Trace events
   now log (P3.2). Wire its output into SSE status updates.

---

## 4. Option-A implementation checklist (execute in this order)

- [ ] Tier classifier in the chat path (reuse complexity scorer; map to 4 tiers).
- [ ] Instant tier: keep current direct `OrchestratorAgent` path unchanged.
- [ ] Bridge: route Fast/Standard/Complex through `JarvisFrontDoor` →
      `CosGmOrchestrator`, with fallback-to-direct on error.
- [ ] Replace dry-run worker stubs (`worker_adapters.py`) with real execution.
- [ ] SSE status/progress event protocol + frontend rendering.
- [ ] Time-estimate up-front + live re-estimate + actual completion time.
- [ ] Parallel worker execution for Complex tier.
- [ ] Managers/workers audit (§5) applied.
- [ ] End-to-end verification per tier (latency + correctness + no silent fail).
- [ ] Regression: Instant-tier latency must not exceed today's chat latency.

---

## 5. Managers & Workers audit (do as part of Option A)

### Read-only audit done 2026-06-26 (execution deferred to Option A)

**17 managers currently registered** (`orchestrator/manager_registry.py`):
coding, architecture, testing_validation, code_review, debugging, research,
memory_knowledge, documentation, product_ux, operations_automation,
governance_safety, release_packaging, data, cost_routing, nus_learning,
connector_auth, runtime_ops.

**Finding — the set is dev/build-centric, not universal.** ~9 of 17 are software
-delivery managers (coding, architecture, testing_validation, code_review,
debugging, documentation, release_packaging, runtime_ops, operations_automation).
For a *universal life OS* this over-indexes on coding and **misses Bryan's actual
life domains**.

**Recommended consolidations (overlap):**
- Merge `architecture_manager` + `debugging_manager` + `code_review_manager`
  into `coding_manager` (sub-roles), or keep but note they're one domain.
- Merge `release_packaging_manager` + `runtime_ops_manager` +
  `operations_automation_manager` → one `devops_manager`.

**Recommended additions (missing universal domains):**
- `communications_manager` (email/Slack/Telegram/messaging)
- `finance_manager` (Stripe/revenue/budgets/transactions)
- `calendar_scheduling_manager` (calendar, reminders, important dates)
- `personal_life_manager` (health, relationships, errands — Bryan's life)
- `knowledge_research_manager` already partly covered by research +
  memory_knowledge; keep.

**Workers:** prefer many small-scope workers per manager (e.g. under
communications: `email_reader`, `email_summarizer`, `slack_reader`,
`telegram_sender` — not one "comms worker"). Audit/define during wiring.

**Why deferred, not done tonight:** managers/workers are imported by
doctor/orchestrator-routes/evals on the PARKED stack; restructuring them before
the hierarchy is wired risks breaking those surfaces with no live benefit (the
chat path doesn't use them yet). Execute this audit as the first step of Option A
so each change is validated end-to-end against a live hierarchy.

### Original checklist
Before wiring, audit the full set:
- Read every manager and worker definition (registries:
  `orchestrator/manager_registry.py`, worker registry, `agents/roster.py`).
- **Remove** redundant/overlapping ones — record which and why.
- **Add** missing ones to make the set comprehensive and universal.
- Prefer **many small-scope workers** over few large-scope workers.
- Caution: managers/workers are imported by doctor/orchestrator-routes/evals —
  validate those still pass after any removal (this is why the destructive audit
  belongs to the Option-A sprint, not the parking step).

---

## 6. Parking guarantees

- No behavior change from parking. All four modules remain importable and their
  existing dry-run/doctor/eval surfaces keep working.
- `cos_gm.py` carries a header pointer to this document so anyone reading it
  knows it is parked-pending-Option-A and where the spec lives.
