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

    # ------------------------------------------------------------------ plan
    def plan(self, request: str) -> Dict[str, Any]:
        raw = self._llm(
            _PLAN_SYSTEM,
            f"Request: {request}\n\nAvailable managers and workers:\n"
            f"{managers_catalog()}",
            max_tokens=600, temperature=0.1,
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
        evidence = "\n\n".join(
            f"[{r.manager} / {r.tool}] {'OK' if r.success else 'FAILED'}:\n{r.content}"
            for r in runs
        ) or "(no worker output)"
        persona = (
            "You are Jarvis, Bryan's personal AI. Answer directly and naturally "
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

    # -------------------------------------------------------- step execution
    def _execute_one(self, step: Dict[str, Any]) -> WorkerRun:
        mgr, tool, args = step["manager"], step["tool"], step["args"]
        t0 = time.time()
        ok, content = self._run_tool(tool, args)
        return WorkerRun(mgr, tool, args, ok, content,
                         int((time.time() - t0) * 1000))

    def _execute_sequential(self, steps: List[Dict[str, Any]]) -> List[WorkerRun]:
        runs: List[WorkerRun] = []
        for i, step in enumerate(steps, 1):
            self._status(
                f"[{i}/{len(steps)}] {MANAGERS[step['manager']].name}: "
                f"running {step['tool']}…"
            )
            runs.append(self._execute_one(step))
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

    # ------------------------------------------------------------------- run
    def _run(self, request: str, tier: str, parallel: bool) -> OrchestratorResult:
        start = time.time()
        self._status("On it, boss — working out the best way to handle this…")
        try:
            plan = self.plan(request)
        except Exception as exc:
            logger.error("planning failed: %s", exc, exc_info=True)
            return OrchestratorResult(answer="", tier=tier,
                                      error=f"planning failed: {exc}",
                                      elapsed_ms=int((time.time() - start) * 1000))

        steps = plan.get("steps", [])
        estimate = int(plan.get("estimate_seconds", 0) or 0)
        rationale = str(plan.get("rationale", ""))
        # Time estimate given UP FRONT (required for COMPLEX).
        est_str = f" This should take about {estimate}s." if estimate else ""
        self._status(f"Plan ready — {rationale}.{est_str}")

        managers_used: List[str] = []
        for s in steps:
            if s["manager"] not in managers_used:
                managers_used.append(s["manager"])

        runs = (self._execute_parallel(steps) if parallel
                else self._execute_sequential(steps))

        self._status("Pulling it together…")
        try:
            answer = self._synthesize(request, runs)
        except Exception as exc:
            logger.error("synthesis failed: %s", exc, exc_info=True)
            return OrchestratorResult(answer="", tier=tier, workers=runs,
                                      managers_used=managers_used,
                                      error=f"synthesis failed: {exc}",
                                      elapsed_ms=int((time.time() - start) * 1000))

        elapsed = int((time.time() - start) * 1000)
        # Actual time reported on completion (required).
        self._status(f"Done — took {elapsed/1000:.1f}s (estimated {estimate}s).")
        return OrchestratorResult(
            answer=answer, tier=tier, managers_used=managers_used, workers=runs,
            estimate_seconds=estimate, elapsed_ms=elapsed, rationale=rationale,
        )

    def run_standard(self, request: str) -> OrchestratorResult:
        """STANDARD tier: plan -> sequential workers -> synthesize."""
        return self._run(request, "standard", parallel=False)

    def run_complex(self, request: str) -> OrchestratorResult:
        """COMPLEX tier: plan -> PARALLEL workers -> synthesize, with upfront
        estimate and per-worker progress (never leaves Bryan in silence)."""
        return self._run(request, "complex", parallel=True)


__all__ = ["LeanOrchestrator", "OrchestratorResult", "WorkerRun"]
