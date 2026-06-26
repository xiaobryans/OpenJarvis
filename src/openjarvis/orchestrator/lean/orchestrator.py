"""LeanOrchestrator — COS/GM -> managers -> workers, real execution.

Stage 3 (this file): STANDARD tier, sequential.
  1. COS/GM plans the request with a capable cloud model -> picks
     (manager, worker-tool, args) steps + a time estimate.
  2. Workers execute as REAL tool calls (real data).
  3. COS/GM synthesizes a single answer in Jarvis's voice.
  4. Live status is emitted via a callback (immediate ack, per-step updates,
     completion time) for streaming to Bryan.

Later stages extend this: Stage 4 parallel workers (run_complex), Stage 5
tester/quality gate, Stage 6 error recovery, Stage 7 full audit. Built fresh and
lean — does NOT touch the parked legacy cos_gm.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from openjarvis.orchestrator.lean.managers import MANAGERS, managers_catalog

logger = logging.getLogger("openjarvis.lean_orch")

StatusCb = Callable[[str], None]


@dataclass
class WorkerRun:
    manager: str
    tool: str
    args: Dict[str, Any]
    success: bool
    content: str
    elapsed_ms: int
    approved: bool = True        # Quality Manager verdict
    review_reason: str = "ok"
    retried: bool = False


@dataclass
class OrchestratorResult:
    answer: str
    tier: str
    managers_used: List[str] = field(default_factory=list)
    workers: List[WorkerRun] = field(default_factory=list)
    estimate_seconds: int = 0
    elapsed_ms: int = 0
    rationale: str = ""
    error: str = ""
    escalated: bool = False
    notes: List[str] = field(default_factory=list)
    tokens: Dict[str, int] = field(default_factory=dict)
    request_id: str = ""


_PLAN_SYSTEM = (
    "You are COS/GM, the chief-of-staff orchestrator for Jarvis. Given Bryan's "
    "request and the available domain managers (each with worker tools), produce "
    "a concise execution plan: which workers to run, in order, with arguments. "
    "Only use managers/workers from the list. Pick the minimum needed. Respond "
    "with STRICT JSON only, no prose:\n"
    '{"estimate_seconds": <int>, "rationale": "<one sentence>", '
    '"steps": [{"manager": "<id>", "tool": "<worker tool>", "args": {<kwargs>}}]}'
)


class LeanOrchestrator:
    def __init__(
        self,
        model: str = "gpt-4o",
        status_cb: Optional[StatusCb] = None,
        user_profile: str = "",
    ) -> None:
        self.model = model
        self._status = status_cb or (lambda _m: None)
        self.user_profile = user_profile
        self._tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # ------------------------------------------------------------------ LLM
    def _llm(self, system: str, user: str, *, max_tokens: int = 800,
             temperature: float = 0.3) -> str:
        from openjarvis.core.types import Message, Role
        from openjarvis.server.cloud_router import generate_cloud

        msgs = [
            Message(role=Role.SYSTEM, content=system),
            Message(role=Role.USER, content=user),
        ]
        res = generate_cloud(self.model, msgs, temperature=temperature,
                             max_tokens=max_tokens)
        u = res.get("usage", {}) or {}
        for k in self._tokens:
            self._tokens[k] += int(u.get(k, 0) or 0)
        return res.get("content", "") or ""

    # --------------------------------------------------------------- workers
    @staticmethod
    def _run_tool(tool: str, args: Dict[str, Any]) -> tuple[bool, str]:
        import openjarvis.tools  # noqa: F401 ensure registration
        from openjarvis.core.registry import ToolRegistry

        if tool not in ToolRegistry.keys():
            return False, f"(worker '{tool}' not available)"
        try:
            r = ToolRegistry.get(tool)().execute(**(args or {}))
            return bool(getattr(r, "success", False)), getattr(r, "content", "")
        except Exception as exc:
            return False, f"(worker '{tool}' error: {exc})"

    @staticmethod
    def _tool_params_catalog() -> str:
        """List each worker tool with its parameters so the planner fills args."""
        import openjarvis.tools  # noqa: F401
        from openjarvis.core.registry import ToolRegistry

        seen, lines = set(), []
        for m in MANAGERS.values():
            for t in m.workers:
                if t in seen or t not in ToolRegistry.keys():
                    continue
                seen.add(t)
                try:
                    spec = ToolRegistry.get(t)().spec
                    props = (spec.parameters or {}).get("properties", {})
                    req = set((spec.parameters or {}).get("required", []))
                    params = ", ".join(f"{k}{'*' if k in req else ''}" for k in props)
                    lines.append(f"  {t}({params})")
                except Exception:
                    lines.append(f"  {t}()")
        return "\n".join(lines)

    # ------------------------------------------------------------------ plan
    def plan(self, request: str) -> Dict[str, Any]:
        raw = self._llm(
            _PLAN_SYSTEM,
            f"Request: {request}\n\nManagers and their workers:\n"
            f"{managers_catalog()}\n\nWorker tool signatures (fill 'args' from "
            f"the request; * = required):\n{self._tool_params_catalog()}",
            max_tokens=700, temperature=0.1,
        )
        # Strip code fences and parse the first JSON object.
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        try:
            plan = json.loads(cleaned)
        except Exception:
            m = re.search(r"\{.*\}", cleaned, re.DOTALL)
            plan = json.loads(m.group(0)) if m else {"steps": []}
        # Validate steps against real managers/workers.
        valid_steps = []
        for s in plan.get("steps", []):
            mgr = s.get("manager", "")
            tool = s.get("tool", "")
            if mgr in MANAGERS and tool in MANAGERS[mgr].workers:
                valid_steps.append({"manager": mgr, "tool": tool, "args": s.get("args", {}) or {}})
        plan["steps"] = valid_steps
        return plan

    # ------------------------------------------------------------- synthesis
    def _synthesize(self, request: str, runs: List[WorkerRun]) -> str:
        # Only QUALITY-APPROVED worker output is used as fact (Stage 5 gate).
        approved = [r for r in runs if r.approved]
        rejected = [r for r in runs if not r.approved]
        evidence = "\n\n".join(
            f"[{r.manager} / {r.tool}]:\n{r.content}" for r in approved
        ) or "(no approved worker output)"
        if rejected:
            evidence += "\n\nUnavailable (could not complete): " + ", ".join(
                f"{r.tool} ({r.review_reason})" for r in rejected
            )
        persona = (
            "You are VANTA, Bryan's personal AI. Answer directly and naturally "
            "in his voice (you may address him as Bryan/boss/brother — vary it, "
            "never forced). Use ONLY the worker results below as facts; never "
            "invent data. If a worker failed, say so plainly."
        )
        if self.user_profile:
            persona += "\n\nAbout Bryan (background):\n" + self.user_profile[:1500]
        return self._llm(
            persona,
            f"Bryan asked: {request}\n\nWorker results:\n{evidence}\n\n"
            "Give Bryan a single, helpful answer.",
            max_tokens=900, temperature=0.5,
        )

    # ----------------------------------------------- quality gate (testers)
    @staticmethod
    def _review(success: bool, content: str) -> tuple[bool, str]:
        """Quality Manager: approve/reject a worker's output with a reason."""
        if not success:
            return False, f"worker failed: {(content or '')[:80]}"
        c = (content or "").strip()
        if not c:
            return False, "empty output"
        low = c.lower()
        if c.startswith("(") and ("not available" in low or "error" in low):
            return False, "tool error/unavailable"
        if "not configured" in low:
            return False, "service not configured"
        if "needs an extra scope" in low or "missing_scope" in low:
            return False, "missing permission/scope"
        return True, "ok"

    # -------------------------------------------------------- step execution
    def _execute_one(self, step: Dict[str, Any]) -> WorkerRun:
        """Run a worker, then send it through the Quality gate; on rejection,
        redo ONCE and re-review. Only the final verdict is returned."""
        mgr, tool, args = step["manager"], step["tool"], step["args"]
        t0 = time.time()
        ok, content = self._run_tool(tool, args)
        approved, reason = self._review(ok, content)
        retried = False
        if not approved:
            # Rejection → back to the worker to redo (once).
            retried = True
            ok, content = self._run_tool(tool, args)
            approved, reason = self._review(ok, content)
        return WorkerRun(mgr, tool, args, ok, content,
                         int((time.time() - t0) * 1000),
                         approved=approved, review_reason=reason, retried=retried)

    def _execute_sequential(self, steps: List[Dict[str, Any]]) -> List[WorkerRun]:
        runs: List[WorkerRun] = []
        for i, step in enumerate(steps, 1):
            self._status(
                f"[{i}/{len(steps)}] {MANAGERS[step['manager']].name}: "
                f"running {step['tool']}…"
            )
            run = self._execute_one(step)
            if not run.approved:
                self._status(
                    f"   ⚠ Quality gate rejected {run.tool} ({run.review_reason})"
                    + (" — retried" if run.retried else "")
                )
            runs.append(run)
        return runs

    def _execute_parallel(self, steps: List[Dict[str, Any]]) -> List[WorkerRun]:
        """Run independent workers concurrently; report each as it finishes."""
        import concurrent.futures as _cf

        runs: List[WorkerRun] = []
        total = len(steps)
        self._status(f"Dispatching {total} workers in parallel…")
        with _cf.ThreadPoolExecutor(max_workers=min(8, total)) as ex:
            futs = {ex.submit(self._execute_one, s): s for s in steps}
            done = 0
            for fut in _cf.as_completed(futs):
                run = fut.result()
                done += 1
                self._status(
                    f"[{done}/{total}] {MANAGERS[run.manager].name}/{run.tool} "
                    f"{'✓' if run.success else '✗'}"
                )
                runs.append(run)
        return runs

    # --------------------------------------------------- error recovery
    def _direct_answer(self, request: str, note: str = "") -> str:
        """COS/GM alternative approach: answer directly with the cloud model when
        planning/workers can't help. Never returns empty (final fallback)."""
        persona = (
            "You are VANTA, Bryan's personal AI. Answer his request directly and "
            "helpfully in his voice (Bryan/boss/brother, vary naturally). If you "
            "genuinely cannot do something, say exactly what's needed — never a "
            "vague refusal."
        )
        if self.user_profile:
            persona += "\n\nAbout Bryan:\n" + self.user_profile[:1200]
        prompt = request if not note else f"{request}\n\n(Context: {note})"
        try:
            ans = self._llm(persona, prompt, max_tokens=800, temperature=0.5)
            return ans or ("I hit a snag handling that — try rephrasing and I'll "
                           "get right on it, boss.")
        except Exception as exc:
            logger.error("direct answer failed: %s", exc, exc_info=True)
            return (f"I couldn't reach my reasoning model just now ({exc}). "
                    "Everything else is up — try again in a moment, boss.")

    # ------------------------------------------------------------------- run
    def _run(self, request: str, tier: str, parallel: bool) -> OrchestratorResult:
        start = time.time()
        notes: List[str] = []
        self._tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._status("On it, boss — working out the best way to handle this…")

        # Plan failure → escalate to a direct COS/GM answer (never silent).
        try:
            plan = self.plan(request)
        except Exception as exc:
            logger.error("planning failed: %s", exc, exc_info=True)
            self._status("Planner hit a snag — handling it directly…")
            answer = self._direct_answer(request, note="planner unavailable")
            return OrchestratorResult(
                answer=answer, tier=tier, escalated=True,
                error=f"planning failed: {exc}", notes=["planning failed; direct answer"],
                elapsed_ms=int((time.time() - start) * 1000))

        steps = plan.get("steps", [])
        estimate = int(plan.get("estimate_seconds", 0) or 0)
        rationale = str(plan.get("rationale", ""))

        # No actionable steps → COS/GM answers directly (alternative approach).
        if not steps:
            self._status("No tools needed — answering directly…")
            answer = self._direct_answer(request)
            elapsed = int((time.time() - start) * 1000)
            self._status(f"Done — took {elapsed/1000:.1f}s.")
            return OrchestratorResult(
                answer=answer, tier=tier, escalated=True, estimate_seconds=estimate,
                elapsed_ms=elapsed, rationale=rationale or "direct answer",
                notes=["no steps planned; direct answer"])

        est_str = f" This should take about {estimate}s." if estimate else ""
        self._status(f"Plan ready — {rationale}.{est_str}")

        managers_used: List[str] = []
        for s in steps:
            if s["manager"] not in managers_used:
                managers_used.append(s["manager"])

        runs = (self._execute_parallel(steps) if parallel
                else self._execute_sequential(steps))

        # If EVERY worker was rejected, escalate to a direct answer that explains
        # what failed — Bryan never gets an empty/silent response.
        if runs and not any(r.approved for r in runs):
            self._status("Workers couldn't complete — escalating to a direct answer…")
            fails = "; ".join(f"{r.tool}: {r.review_reason}" for r in runs)
            answer = self._direct_answer(
                request, note=f"the tools failed ({fails}); explain to Bryan "
                              "what's needed and help however you can")
            elapsed = int((time.time() - start) * 1000)
            self._status(f"Done (escalated) — took {elapsed/1000:.1f}s.")
            return OrchestratorResult(
                answer=answer, tier=tier, managers_used=managers_used, workers=runs,
                estimate_seconds=estimate, elapsed_ms=elapsed, rationale=rationale,
                escalated=True, notes=[f"all workers rejected: {fails}"])

        self._status("Pulling it together…")
        try:
            answer = self._synthesize(request, runs)
        except Exception as exc:
            # Synthesis failure → compile a plain answer from approved output
            # rather than failing silently.
            logger.error("synthesis failed: %s", exc, exc_info=True)
            approved = [r for r in runs if r.approved]
            answer = ("Here's what I gathered, boss (couldn't do the final "
                      "write-up):\n\n" + "\n\n".join(
                          f"• {r.tool}: {r.content}" for r in approved)) or \
                     f"I gathered the data but synthesis failed ({exc})."
            notes.append(f"synthesis failed: {exc}")

        if not (answer or "").strip():  # absolute never-empty guard
            answer = self._direct_answer(request)
            notes.append("empty synthesis; direct fallback")

        elapsed = int((time.time() - start) * 1000)
        self._status(f"Done — took {elapsed/1000:.1f}s (estimated {estimate}s).")
        return OrchestratorResult(
            answer=answer, tier=tier, managers_used=managers_used, workers=runs,
            estimate_seconds=estimate, elapsed_ms=elapsed, rationale=rationale,
            notes=notes,
        )

    def _finish(self, request: str, res: OrchestratorResult) -> OrchestratorResult:
        """Attach tokens + write the complete audit record (Stage 7)."""
        res.tokens = dict(self._tokens)
        try:
            import uuid as _uuid

            from openjarvis.orchestrator.request_audit import record_request

            rid = f"orch-{_uuid.uuid4().hex[:12]}"
            res.request_id = rid
            outcome = ("error" if res.error else
                       "escalated" if res.escalated else "completed")
            record_request(
                request_id=rid, tier=res.tier, reason=res.rationale or "orchestrated",
                score=0.0, model=self.model, query_preview=request,
                elapsed_ms=res.elapsed_ms, outcome=outcome,
                extra={
                    "managers": res.managers_used,
                    "workers": [
                        {"manager": w.manager, "tool": w.tool, "ok": w.success,
                         "approved": w.approved, "reason": w.review_reason,
                         "retried": w.retried, "ms": w.elapsed_ms}
                        for w in res.workers
                    ],
                    "estimate_s": res.estimate_seconds,
                    "tokens": res.tokens,
                    "escalated": res.escalated,
                    "notes": res.notes,
                },
            )
        except Exception:
            logger.debug("orchestration audit write failed", exc_info=True)
        return res

    def run_standard(self, request: str) -> OrchestratorResult:
        """STANDARD tier: plan -> sequential workers -> synthesize."""
        return self._finish(request, self._run(request, "standard", parallel=False))

    def run_complex(self, request: str) -> OrchestratorResult:
        """COMPLEX tier: plan -> PARALLEL workers -> synthesize, with upfront
        estimate and per-worker progress (never leaves Bryan in silence)."""
        return self._finish(request, self._run(request, "complex", parallel=True))


__all__ = ["LeanOrchestrator", "OrchestratorResult", "WorkerRun"]
