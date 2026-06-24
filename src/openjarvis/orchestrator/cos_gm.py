"""COS/GM Orchestrator — Chief of Staff / General Manager layer.

Sits between the Jarvis front door and the domain managers/workers.
Receives a UniversalTaskRequest, classifies intent/risk/complexity,
calls the DynamicActivationPlanner, dispatches selected workers through
worker execution adapters, collects structured results, and returns
a FrontDoorResult with full execution evidence.

Design rules (non-negotiable):
  - Receives universal Jarvis front-door request; never OMNIX-specific input.
  - project_context is optional — personal tasks and non-project tasks work.
  - No fixed worker-count formulas.
  - Structured decision record always emitted; no raw chain-of-thought.
  - NUS applies: all hierarchy levels emit decision records.
  - Dangerous actions remain permanently blocked.
  - US13 voice remains HOLD/UNSAFE/PARKED — not activated here.
  - Emits runtime trace events for every stage of the pipeline.
  - Workers are dispatched after planning for dry-run execution (safe local only).
  - Real (non-dry-run) execution requires Bryan authorization per action.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from openjarvis.orchestrator.contracts import (
    ProjectContext,
    TaskRoutingRequest,
    RISK_LOW,
    RISK_HIGH,
    RISK_BLOCKED,
    COMPLEXITY_SIMPLE,
    COMPLEXITY_COMPLEX,
)
from openjarvis.orchestrator.activation import get_activation_planner
from openjarvis.orchestrator.runtime_trace import (
    start_trace,
    get_trace_store,
    EVENT_COS_GM,
    EVENT_MANAGER_ACTIVATION,
    EVENT_WORKER_EXECUTION,
    EVENT_REVIEWER_VERIFICATION,
    EVENT_VALIDATION,
    EVENT_NUS_FEEDBACK,
    EVENT_BLOCKER,
    EVENT_FINAL_RESPONSE,
)

logger = logging.getLogger(__name__)

# Permanently blocked actions — COS/GM enforces these before delegating
_ALWAYS_BLOCKED_ACTIONS = frozenset({
    "auto_push",
    "auto_merge",
    "production_deploy",
    "external_send",
    "secret_access",
    "bypass_governance",
    "bypass_safety_gate",
    "us13_voice_activation",
})

_RISK_KEYWORDS = {
    "deploy": RISK_HIGH,
    "production": RISK_HIGH,
    "delete": RISK_HIGH,
    "drop": RISK_HIGH,
    "override": RISK_HIGH,
    "bypass": RISK_BLOCKED,
    "secret": RISK_HIGH,
    "credential": RISK_HIGH,
}

_COMPLEXITY_KEYWORDS_COMPLEX = frozenset({
    "architecture", "migration", "refactor", "multi-file", "cross-system",
    "schema", "upgrade bundle", "integration",
})
_COMPLEXITY_KEYWORDS_MODERATE = frozenset({
    "feature", "fix", "update", "test", "review", "analyze",
})


class CosGmOrchestrator:
    """Chief of Staff / General Manager orchestration layer.

    Receives any UniversalTaskRequest and produces a FrontDoorResult by:
      1. Classifying intent/risk/complexity
      2. Checking always-blocked actions
      3. Calling DynamicActivationPlanner
      4. Creating structured decision record
      5. Attaching governance and validation plan
      6. Returning unified FrontDoorResult
    """

    def handle(self, request: "UniversalTaskRequest") -> "FrontDoorResult":  # type: ignore[name-defined]
        """Route any request through COS/GM, activate managers, dispatch workers.

        Pipeline:
          1. Emit COS/GM entry trace event
          2. Check always-blocked actions
          3. Classify intent/risk/complexity
          4. Build TaskRoutingRequest
          5. Call DynamicActivationPlanner → ActivationPlan
          6. Emit manager activation trace events
          7. Dispatch selected workers through WorkerAdapter (dry-run by default)
          8. Collect WorkerAdapterResults
          9. Emit NUS feedback trace event
          10. Emit final response trace event
          11. Return FrontDoorResult with full execution evidence
        """
        from openjarvis.frontdoor.frontdoor import FrontDoorResult, UniversalTaskRequest

        start = time.time()
        trace_id = request.metadata.get("trace_id")

        # Start or attach trace
        try:
            if trace_id:
                trace = get_trace_store().get(trace_id)
            else:
                trace = None
            if trace is None:
                trace = start_trace(request.request_id, trace_id=trace_id)
                trace_id = trace.trace_id
            trace.add_event(
                EVENT_COS_GM,
                component="cos_gm",
                summary=f"COS/GM received request intent='{request.intent}'",
                payload={
                    "request_id": request.request_id,
                    "intent": request.intent,
                    "risk_level": request.risk_level,
                    "complexity_level": request.complexity_level,
                    "project": (
                        request.project_context.project_id
                        if request.project_context else None
                    ),
                },
            )
        except Exception as _te:
            logger.debug("Trace event failed (non-fatal): %s", _te)

        # 1. Check always-blocked actions
        requested = request.metadata.get("requested_actions", [])
        blocked = [a for a in requested if a in _ALWAYS_BLOCKED_ACTIONS]
        if blocked:
            try:
                trace.add_event(
                    EVENT_BLOCKER,
                    component="cos_gm",
                    summary=f"COS/GM blocked: {blocked}",
                    payload={"blocked_actions": blocked},
                )
                trace.add_event(
                    EVENT_FINAL_RESPONSE,
                    component="cos_gm",
                    summary="Response: blocked",
                    payload={"status": "blocked"},
                )
            except Exception:
                pass
            return FrontDoorResult.create(
                request_id=request.request_id,
                status="blocked",
                summary=(
                    f"COS/GM blocked request: {blocked} are permanently blocked. "
                    "No production deploy, auto-push, auto-merge, external send, "
                    "secret access, governance bypass, or voice activation."
                ),
                blocked_actions=blocked,
                project_context=request.project_context,
                nus_learning_tags=["cos_gm:blocked_action"],
                elapsed_ms=(time.time() - start) * 1000,
                metadata={"trace_id": trace_id},
            )

        # 2. Classify intent/risk/complexity from request
        effective_risk, effective_complexity = self._classify(request)

        # 3. Build TaskRoutingRequest
        routing_req = TaskRoutingRequest.create(
            user_request_summary=request.user_input,
            intent=request.intent,
            risk_level=effective_risk,
            complexity_level=effective_complexity,
            domains_required=request.domains_required,
            required_skills=request.required_skills,
            required_tools=request.required_tools,
            validation_required=request.validation_required,
            context_budget=request.context_budget,
            cost_budget=request.cost_budget,
            latency_requirement=request.latency_requirement,
            autonomy_profile=request.autonomy_profile,
            session_id=request.session_id,
            project_context=request.project_context,
            metadata=request.metadata,
        )

        # 4. Activate managers/workers via DynamicActivationPlanner
        planner = get_activation_planner()
        plan = planner.plan(routing_req)

        # 5. Emit manager activation events
        try:
            for mgr_id in plan.selected_managers:
                trace.add_event(
                    EVENT_MANAGER_ACTIVATION,
                    component="cos_gm",
                    summary=f"Manager activated: {mgr_id}",
                    payload={"manager_id": mgr_id, "plan_id": plan.plan_id},
                )
        except Exception:
            pass

        # 6. Dispatch workers through adapters (dry-run by default)
        worker_results: list = []
        worker_result_dicts: list = []
        workers_dispatched = 0
        workers_succeeded = 0

        for worker_id in plan.selected_workers:
            try:
                from openjarvis.orchestrator.worker_adapters import execute_worker
                # Determine safe action type for this worker
                action_type = self._safe_action_for_worker(worker_id, request)
                w_result = execute_worker(
                    worker_id=worker_id,
                    action_type=action_type,
                    inputs={
                        "request_id": request.request_id,
                        "intent": request.intent,
                        "user_input": request.user_input,
                        "project_id": (
                            request.project_context.project_id
                            if request.project_context else None
                        ),
                    },
                    dry_run=True,
                    session_id=request.session_id,
                )
                workers_dispatched += 1
                if w_result.status in ("ok", "dry_run_ok"):
                    workers_succeeded += 1
                worker_results.append(w_result)
                worker_result_dicts.append(w_result.to_dict())
                try:
                    trace.add_event(
                        EVENT_WORKER_EXECUTION,
                        component=f"worker:{worker_id}",
                        summary=f"Worker {worker_id} → {w_result.status}",
                        payload={
                            "worker_id": worker_id,
                            "action_type": action_type,
                            "status": w_result.status,
                            "nus_gate_passed": w_result.nus_gate_passed,
                        },
                    )
                except Exception:
                    pass
            except Exception as exc:
                logger.warning("Worker %s dispatch failed: %s", worker_id, exc)
                try:
                    trace.add_event(
                        EVENT_WORKER_EXECUTION,
                        component=f"worker:{worker_id}",
                        summary=f"Worker {worker_id} dispatch error: {exc}",
                        payload={"worker_id": worker_id, "error": str(exc)},
                    )
                except Exception:
                    pass

        # 7. Reviewer/Tester/Verifier integration (independent layer, before returning to PA)
        #    Runs when validation_required=True and at least one worker was dispatched.
        #    Self-verify is blocked by VerifierGate. Reviewer is independent of the team.
        verification_outcome: str = "not_required"
        verification_summary: str = "verification_not_required"
        verification_fix_list: list = []
        if request.validation_required and workers_dispatched > 0:
            try:
                from openjarvis.agents.verifier import (
                    VerifierGate,
                    EvidenceItem,
                    VerificationOutcome,
                )
                import time as _time
                gate = VerifierGate(verifier_id="cos_gm_reviewer", stale_threshold_seconds=3600)
                evidence_items = [
                    EvidenceItem(
                        claim_id=f"worker:{wr.worker_id}",
                        claim_text=f"Worker {wr.worker_id} status={wr.status}",
                        source_type="worker_execution",
                        source_ref=f"worker_id:{wr.worker_id}",
                        last_updated_at=_time.time(),
                        is_supported=wr.status in ("ok", "dry_run_ok"),
                    )
                    for wr in worker_results
                ]
                v_report = gate.verify(
                    team_id=f"cos_gm_workers:{request.request_id}",
                    evidence_items=evidence_items,
                )
                verification_outcome = v_report.outcome.value
                if v_report.outcome == VerificationOutcome.ACCEPTED:
                    verification_summary = (
                        f"Reviewer: ACCEPTED — {len(v_report.accepted_claims)} claim(s) verified. "
                        f"Trace: {v_report.acceptance_trace}"
                    )
                else:
                    verification_summary = (
                        f"Reviewer: {v_report.outcome.value} — "
                        f"{len(v_report.rejected_claims)} claim(s) rejected."
                    )
                    verification_fix_list = v_report.fix_list
                try:
                    trace.add_event(
                        EVENT_REVIEWER_VERIFICATION,
                        component="reviewer_layer",
                        summary=verification_summary,
                        payload={
                            "outcome": verification_outcome,
                            "accepted_claims": v_report.accepted_claims,
                            "rejected_claims": v_report.rejected_claims,
                            "fix_list": verification_fix_list,
                            "independent": True,
                            "self_verify_blocked": True,
                        },
                    )
                except Exception:
                    pass
            except Exception as _ve:
                verification_outcome = "reviewer_error"
                verification_summary = f"Reviewer gate error (non-fatal): {_ve}"
                logger.warning("VerifierGate integration failed (non-fatal): %s", _ve)
                try:
                    trace.add_event(
                        EVENT_REVIEWER_VERIFICATION,
                        component="reviewer_layer",
                        summary=verification_summary,
                        payload={"outcome": "reviewer_error", "error": str(_ve)},
                    )
                except Exception:
                    pass

        # 8. Validation event (if validation_required)
        validation_summary = "validation_not_required"
        if request.validation_required and workers_dispatched > 0:
            validation_summary = (
                f"{workers_succeeded}/{workers_dispatched} workers succeeded (dry-run); "
                f"reviewer={verification_outcome}"
            )
            try:
                trace.add_event(
                    EVENT_VALIDATION,
                    component="cos_gm",
                    summary=validation_summary,
                    payload={
                        "workers_dispatched": workers_dispatched,
                        "workers_succeeded": workers_succeeded,
                        "verification_outcome": verification_outcome,
                    },
                )
            except Exception:
                pass

        # 10. NUS feedback trace event
        nus_available = any("nus_feedback:loaded" in t for t in plan.nus_learning_tags)
        try:
            trace.add_event(
                EVENT_NUS_FEEDBACK,
                component="activation_planner",
                summary=f"NUS feedback: {'loaded' if nus_available else 'not_available'}",
                payload={"nus_feedback_available": nus_available},
            )
        except Exception:
            pass

        # 11. Build result
        project_label = (
            request.project_context.display_name
            if request.project_context
            else "no_project_context"
        )
        model_gap_dicts = [g.to_dict() for g in plan.model_provider_gaps]
        nus_tags = list(plan.nus_learning_tags) + [
            "cos_gm:routed",
            f"project:{request.project_context.project_id if request.project_context and request.project_context.project_id else 'none'}",
        ]
        if workers_dispatched > 0:
            nus_tags.append(f"cos_gm:workers_dispatched:{workers_dispatched}")
            status = "executed"
        else:
            status = "planned"

        if verification_fix_list:
            nus_tags.append(f"reviewer:rejected:{len(verification_fix_list)}_fixes_required")
        else:
            nus_tags.append(f"reviewer:{verification_outcome}")

        summary = (
            f"COS/GM activated {len(plan.selected_managers)} manager(s), "
            f"dispatched {workers_dispatched} worker(s) "
            f"({workers_succeeded} succeeded, dry-run), "
            f"reviewer={verification_outcome} "
            f"for request '{request.intent}' "
            f"[project={project_label}, risk={effective_risk}, complexity={effective_complexity}]. "
            f"decision_record={plan.structured_decision_record_id}."
        )

        result_metadata = {
            "trace_id": trace_id,
            "workers_dispatched": workers_dispatched,
            "workers_succeeded": workers_succeeded,
            "worker_results": worker_result_dicts,
            "validation_summary": validation_summary,
            "verification_outcome": verification_outcome,
            "verification_summary": verification_summary,
            "verification_fix_list": verification_fix_list,
            "reviewer_independent": True,
            "reviewer_self_verify_blocked": True,
        }

        try:
            trace.add_event(
                EVENT_FINAL_RESPONSE,
                component="cos_gm",
                summary=f"Response: status={status}",
                payload={"status": status, "elapsed_ms": (time.time() - start) * 1000},
            )
        except Exception:
            pass

        return FrontDoorResult.create(
            request_id=request.request_id,
            status=status,
            summary=summary,
            activation_plan_id=plan.plan_id,
            selected_managers=plan.selected_managers,
            selected_workers=plan.selected_workers,
            structured_decision_record_id=plan.structured_decision_record_id,
            project_context=request.project_context,
            model_provider_gaps=model_gap_dicts,
            blocked_actions=list(_ALWAYS_BLOCKED_ACTIONS),
            nus_learning_tags=nus_tags,
            elapsed_ms=(time.time() - start) * 1000,
            metadata=result_metadata,
        )

    def _safe_action_for_worker(
        self,
        worker_id: str,
        request: "UniversalTaskRequest",  # type: ignore[name-defined]
    ) -> str:
        """Determine the safe dry-run action type for a given worker.

        Maps worker IDs to appropriate safe local action types.
        Default: routing_dry_run (always safe).
        """
        _WORKER_SAFE_ACTIONS: Dict[str, str] = {
            "unit_test_worker": "local_validation",
            "doctor_check_worker": "doctor_run",
            "nus_learning_worker": "nus_dry_run",
            "cost_analysis_worker": "routing_dry_run",
            "coding_safe_worker": "local_analysis",
            "file_inspection_worker": "local_read",
            "local_research_worker": "local_analysis",
            "risk_classification_worker": "risk_assessment",
            "policy_gate_worker": "policy_check",
        }
        return _WORKER_SAFE_ACTIONS.get(worker_id, "routing_dry_run")

    def _classify(
        self, request: "UniversalTaskRequest"  # type: ignore[name-defined]
    ) -> tuple[str, str]:
        """Classify risk and complexity from request metadata.

        Does not override explicit values from the request — only elevates if
        keywords indicate higher risk/complexity than declared.
        """
        risk = request.risk_level
        complexity = request.complexity_level

        text = (request.user_input + " " + request.intent).lower()

        # Elevate risk if keywords found
        for keyword, keyword_risk in _RISK_KEYWORDS.items():
            if keyword in text:
                if keyword_risk == RISK_BLOCKED:
                    risk = RISK_BLOCKED
                    break
                elif keyword_risk == RISK_HIGH and risk == RISK_LOW:
                    risk = RISK_HIGH

        # Elevate complexity
        if any(kw in text for kw in _COMPLEXITY_KEYWORDS_COMPLEX):
            if complexity == COMPLEXITY_SIMPLE:
                complexity = COMPLEXITY_COMPLEX
        elif any(kw in text for kw in _COMPLEXITY_KEYWORDS_MODERATE):
            if complexity == COMPLEXITY_SIMPLE:
                from openjarvis.orchestrator.contracts import COMPLEXITY_MODERATE
                complexity = COMPLEXITY_MODERATE

        return risk, complexity

    def get_status(self) -> Dict[str, Any]:
        """Return COS/GM status summary."""
        planner = get_activation_planner()
        return {
            "cos_gm_orchestrator": "active",
            "always_blocked_actions": sorted(_ALWAYS_BLOCKED_ACTIONS),
            "activation_planner": planner.get_status() if hasattr(planner, "get_status") else "available",
            "us13_voice": "HOLD/UNSAFE/PARKED",
            "no_raw_chain_of_thought": True,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_orchestrator: Optional[CosGmOrchestrator] = None


def get_cos_gm_orchestrator() -> CosGmOrchestrator:
    """Return the module-level CosGmOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CosGmOrchestrator()
    return _orchestrator
