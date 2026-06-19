"""NUS REST API routes — Learning Foundation (1A) + Recommendation Workflow (1B) + Safe Autopilot (1C) + NUS 1F.

NUS 1A Routes:
  GET /v1/nus/learning/status           — NUS 1A status + safety gates
  GET /v1/nus/learning/scorecards       — Generate and return an AgentScorecard
  GET /v1/nus/learning/failure-patterns — Detected failure patterns
  GET /v1/nus/learning/snapshot         — Full learning snapshot

NUS 1B Routes:
  GET  /v1/nus/recommendations/status         — NUS 1B recommendation workflow status
  GET  /v1/nus/recommendations/list           — List all recommendations
  POST /v1/nus/recommendations/create-dry-run — Create a dry-run recommendation
  POST /v1/nus/recommendations/approve-dry-run — Approve a recommendation dry-run
  POST /v1/nus/recommendations/reject-dry-run  — Reject a recommendation
  GET  /v1/nus/telemetry/status               — Telemetry normalizer status
  POST /v1/nus/telemetry/ingest-dry-run       — Ingest events (dry-run, read-only)
  GET  /v1/nus/autonomy-policy/status         — Autonomy policy scaffold status

NUS 1C Routes:
  GET  /v1/nus/recommendations/queue/status        — Persistent queue status
  GET  /v1/nus/recommendations/queue/list          — List queue items by status
  POST /v1/nus/recommendations/queue/enqueue-dry-run — Enqueue a recommendation (dry-run)
  POST /v1/nus/autopilot/safe/run-dry-run          — Run safe autopilot dry-run
  GET  /v1/nus/autopilot/status                    — Safe autopilot status
  GET  /v1/nus/failure-learning/status             — Cross-session failure learning status
  POST /v1/nus/telemetry/operator/ingest-dry-run   — Ingest operator/agent telemetry (dry-run)
  GET  /v1/nus/routing/recommendations/status      — Learned routing recommendations status
  POST /v1/nus/routing/recommendations/dry-run     — Generate routing recommendation (dry-run)

NUS 1F Routes:
  GET  /v1/nus/high-autonomy/status                      — NUS 1F framework status
  POST /v1/nus/high-autonomy/session/dry-run-create      — Create session (dry-run)
  POST /v1/nus/high-autonomy/session/evaluate-dry-run    — Evaluate action in session (dry-run)
  POST /v1/nus/high-autonomy/session/revoke-dry-run      — Revoke session (dry-run)
  GET  /v1/nus/high-autonomy/policy/status               — 95% automation policy status
  GET  /v1/nus/production-gate/status                    — Production gate status
  POST /v1/nus/production-gate/evaluate-dry-run          — Evaluate production gate (dry-run)
  POST /v1/nus/decision-records/dry-run                  — Create decision record (dry-run)

Safety constraints (all routes):
  - Read-only or dry-run only.
  - No writes, deploys, external sends, or secret access.
  - No self-modification, no auto-commit, no auto-push, no auto-merge.
  - No source-code mutation by autopilot.
  - Production execution blocked — dry-run only in NUS 1F.
  - US13 voice remains HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except ImportError:
    raise ImportError("fastapi and pydantic are required for NUS routes")

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# GET /v1/nus/learning/status
# ---------------------------------------------------------------------------


@router.get("/v1/nus/learning/status")
async def nus_learning_status() -> Dict[str, Any]:
    """Return NUS 1A learning foundation status and safety gate summary."""
    try:
        from openjarvis.nus.learning_foundation import (
            NUS1A_VERSION,
            get_learning_foundation,
        )
        foundation = get_learning_foundation()
        return {
            "status": "ok",
            "nus1a_version": NUS1A_VERSION,
            "record_count": foundation.record_count,
            "safety_gates_active": True,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "no_self_modification": True,
            "no_auto_commit": True,
            "no_deploy": True,
            "no_external_sends": True,
            "nus1b_status": "not_started",
            "nus1c_status": "not_started",
        }
    except Exception as exc:
        logger.exception("NUS 1A status error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /v1/nus/learning/scorecards
# ---------------------------------------------------------------------------


@router.get("/v1/nus/learning/scorecards")
async def nus_learning_scorecards(ingest: bool = True) -> Dict[str, Any]:
    """Generate and return an AgentScorecard from recent workbench events."""
    try:
        from openjarvis.nus.learning_foundation import get_learning_foundation
        foundation = get_learning_foundation()
        if ingest:
            ingested = foundation.ingest_from_workbench_events(limit=200)
        else:
            ingested = 0
        scorecard = foundation.get_scorecard()
        return {
            "status": "ok",
            "ingested_events": ingested,
            "scorecard": scorecard.to_dict(),
        }
    except Exception as exc:
        logger.exception("NUS 1A scorecards error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /v1/nus/learning/failure-patterns
# ---------------------------------------------------------------------------


@router.get("/v1/nus/learning/failure-patterns")
async def nus_learning_failure_patterns(ingest: bool = True) -> Dict[str, Any]:
    """Return detected failure patterns from ingested outcome records."""
    try:
        from openjarvis.nus.learning_foundation import get_learning_foundation
        foundation = get_learning_foundation()
        if ingest:
            foundation.ingest_from_workbench_events(limit=200)
        patterns = foundation.get_failure_patterns()
        return {
            "status": "ok",
            "pattern_count": len(patterns),
            "patterns": [p.to_dict() for p in patterns],
        }
    except Exception as exc:
        logger.exception("NUS 1A failure-patterns error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# GET /v1/nus/learning/snapshot
# ---------------------------------------------------------------------------


@router.get("/v1/nus/learning/snapshot")
async def nus_learning_snapshot(ingest: bool = True) -> Dict[str, Any]:
    """Return a full LearningSnapshot aggregating all available sources."""
    try:
        from openjarvis.nus.learning_foundation import get_learning_foundation
        foundation = get_learning_foundation()
        if ingest:
            foundation.ingest_from_workbench_events(limit=200)
        snapshot = foundation.get_snapshot()
        return {
            "status": "ok",
            "snapshot": snapshot.to_dict(),
        }
    except Exception as exc:
        logger.exception("NUS 1A snapshot error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1B — Recommendation routes
# ---------------------------------------------------------------------------


# In-process registry (reset per process; persisted records survive via store)
_rec_registry: Any = None


def _get_registry() -> Any:
    global _rec_registry
    if _rec_registry is None:
        from openjarvis.nus.recommendation_registry import RecommendationRegistry
        _rec_registry = RecommendationRegistry()
    return _rec_registry


@router.get("/v1/nus/recommendations/status")
async def nus_recommendations_status() -> Dict[str, Any]:
    """Return NUS 1B recommendation workflow status."""
    try:
        from openjarvis.nus.recommendation_registry import NUS1B_REC_VERSION
        from openjarvis.nus.learning_store import NUS1B_STORE_VERSION
        from openjarvis.nus.autonomy_policy import NUS1B_POLICY_VERSION
        registry = _get_registry()
        return {
            "status": "ok",
            "nus1b_rec_version": NUS1B_REC_VERSION,
            "nus1b_store_version": NUS1B_STORE_VERSION,
            "nus1b_policy_version": NUS1B_POLICY_VERSION,
            "recommendation_counts": registry.count_by_status(),
            "safety_gates_active": True,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "no_self_modification": True,
            "no_auto_commit": True,
            "no_deploy": True,
        }
    except Exception as exc:
        logger.exception("NUS 1B recommendations status error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/recommendations/list")
async def nus_recommendations_list() -> Dict[str, Any]:
    """List all in-process recommendations."""
    try:
        registry = _get_registry()
        recs = registry.list_all()
        return {
            "status": "ok",
            "count": len(recs),
            "recommendations": [r.to_dict() for r in recs],
        }
    except Exception as exc:
        logger.exception("NUS 1B recommendations list error")
        raise HTTPException(status_code=500, detail=str(exc))


class CreateDryRunRequest(BaseModel):
    source: str = "api"
    category: str = ""
    title: str
    summary: str
    rationale: str = ""
    affected_area: str = ""
    risk_level: str = "low"
    required_action_type: str = "local_analysis"
    expected_benefit: str = ""


@router.post("/v1/nus/recommendations/create-dry-run")
async def nus_recommendations_create_dry_run(req: CreateDryRunRequest) -> Dict[str, Any]:
    """Create a recommendation (dry-run — no real execution)."""
    try:
        registry = _get_registry()
        rec = registry.create(
            source=req.source,
            category=req.category,
            title=req.title,
            summary=req.summary,
            rationale=req.rationale,
            affected_area=req.affected_area,
            risk_level=req.risk_level,
            required_action_type=req.required_action_type,
            expected_benefit=req.expected_benefit,
        )
        return {"status": "ok", "recommendation": rec.to_dict()}
    except Exception as exc:
        logger.exception("NUS 1B create-dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


class ApproveRejectRequest(BaseModel):
    rec_id: str
    reason: str = ""
    actor: str = "founder"


@router.post("/v1/nus/recommendations/approve-dry-run")
async def nus_recommendations_approve_dry_run(req: ApproveRejectRequest) -> Dict[str, Any]:
    """Approve a recommendation and execute dry-run if safe."""
    try:
        registry = _get_registry()
        approve_result = registry.approve(req.rec_id, approved_by=req.actor)
        if not approve_result.get("ok"):
            return {"status": "error", **approve_result}
        dry_run = registry.execute_dry_run(req.rec_id)
        return {"status": "ok", "approve": approve_result, "dry_run": dry_run}
    except Exception as exc:
        logger.exception("NUS 1B approve-dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/v1/nus/recommendations/reject-dry-run")
async def nus_recommendations_reject_dry_run(req: ApproveRejectRequest) -> Dict[str, Any]:
    """Reject a recommendation."""
    try:
        registry = _get_registry()
        result = registry.reject(req.rec_id, reason=req.reason, rejected_by=req.actor)
        return {"status": "ok" if result.get("ok") else "error", **result}
    except Exception as exc:
        logger.exception("NUS 1B reject-dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1B — Telemetry routes
# ---------------------------------------------------------------------------

_telemetry_normalizer: Any = None


def _get_normalizer() -> Any:
    global _telemetry_normalizer
    if _telemetry_normalizer is None:
        from openjarvis.nus.telemetry import TelemetryNormalizer
        _telemetry_normalizer = TelemetryNormalizer()
    return _telemetry_normalizer


@router.get("/v1/nus/telemetry/status")
async def nus_telemetry_status() -> Dict[str, Any]:
    """Return telemetry normalizer status."""
    try:
        normalizer = _get_normalizer()
        return {"status": "ok", **normalizer.get_status()}
    except Exception as exc:
        logger.exception("NUS 1B telemetry status error")
        raise HTTPException(status_code=500, detail=str(exc))


class TelemetryIngestRequest(BaseModel):
    events: list = []


@router.post("/v1/nus/telemetry/ingest-dry-run")
async def nus_telemetry_ingest_dry_run(req: TelemetryIngestRequest) -> Dict[str, Any]:
    """Ingest events into the telemetry normalizer (dry-run — no external actions)."""
    try:
        normalizer = _get_normalizer()
        count = normalizer.ingest_batch(req.events)
        return {
            "status": "ok",
            "ingested": count,
            "dry_run": True,
            "total_records": normalizer.record_count,
        }
    except Exception as exc:
        logger.exception("NUS 1B telemetry ingest error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1B — Autonomy policy route
# ---------------------------------------------------------------------------


@router.get("/v1/nus/autonomy-policy/status")
async def nus_autonomy_policy_status() -> Dict[str, Any]:
    """Return autonomy policy scaffold status."""
    try:
        from openjarvis.nus.autonomy_policy import get_policy_status
        return {"status": "ok", **get_policy_status()}
    except Exception as exc:
        logger.exception("NUS 1B autonomy policy status error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1C — Persistent recommendation queue routes
# ---------------------------------------------------------------------------

_nus1c_queue = None


def _get_queue():
    global _nus1c_queue
    if _nus1c_queue is None:
        from openjarvis.nus.recommendation_queue import RecommendationQueue
        _nus1c_queue = RecommendationQueue()
    return _nus1c_queue


@router.get("/v1/nus/recommendations/queue/status")
async def nus_queue_status() -> Dict[str, Any]:
    """Return persistent recommendation queue status."""
    try:
        q = _get_queue()
        return {"status": "ok", **q.summarize()}
    except Exception as exc:
        logger.exception("NUS 1C queue status error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/recommendations/queue/list")
async def nus_queue_list(filter_status: str = "pending") -> Dict[str, Any]:
    """List queue items. filter_status: pending|all|approved|rejected|blocked|dry_run."""
    try:
        q = _get_queue()
        if filter_status == "pending":
            items = q.list_pending()
        elif filter_status == "approved":
            items = q.list_approved()
        elif filter_status == "rejected":
            items = q.list_rejected()
        elif filter_status == "blocked":
            items = q.list_blocked()
        elif filter_status == "dry_run":
            items = q.list_dry_run()
        else:
            items = q.list_all()
        return {
            "status": "ok",
            "filter_status": filter_status,
            "count": len(items),
            "items": [i.to_dict() for i in items[:50]],
        }
    except Exception as exc:
        logger.exception("NUS 1C queue list error")
        raise HTTPException(status_code=500, detail=str(exc))


class QueueEnqueueRequest(BaseModel):
    source: str = "api"
    category: str = ""
    title: str = ""
    summary: str = ""
    rationale: str = ""
    required_action_type: str = "local_analysis"
    risk_level: str = "low"
    dedup_key: str = ""


@router.post("/v1/nus/recommendations/queue/enqueue-dry-run")
async def nus_queue_enqueue_dry_run(req: QueueEnqueueRequest) -> Dict[str, Any]:
    """Enqueue a recommendation (dry-run — safe local only, no external actions)."""
    try:
        q = _get_queue()
        item = q.enqueue(
            source=req.source,
            category=req.category,
            title=req.title,
            summary=req.summary,
            rationale=req.rationale,
            required_action_type=req.required_action_type,
            risk_level=req.risk_level,
            dedup_key=req.dedup_key,
        )
        return {
            "status": "ok",
            "dry_run": True,
            "queue_id": item.queue_id,
            "item_status": item.status,
            "safety_note": (
                "Enqueue is dry-run only. No external actions, no code mutation, "
                "no deploy, no auto-commit."
            ),
        }
    except Exception as exc:
        logger.exception("NUS 1C queue enqueue error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1C — Safe autopilot routes
# ---------------------------------------------------------------------------

_nus1c_autopilot = None


def _get_autopilot():
    global _nus1c_autopilot
    if _nus1c_autopilot is None:
        from openjarvis.nus.safe_autopilot import SafeAutopilot
        _nus1c_autopilot = SafeAutopilot(kill_switch=False)
    return _nus1c_autopilot


@router.get("/v1/nus/autopilot/status")
async def nus_autopilot_status() -> Dict[str, Any]:
    """Return safe autopilot status."""
    try:
        ap = _get_autopilot()
        return {"status": "ok", **ap.get_status()}
    except Exception as exc:
        logger.exception("NUS 1C autopilot status error")
        raise HTTPException(status_code=500, detail=str(exc))


class AutopilotDryRunRequest(BaseModel):
    action_type: str = "local_analysis"
    context: Dict[str, Any] = {}


@router.post("/v1/nus/autopilot/safe/run-dry-run")
async def nus_autopilot_safe_run_dry_run(req: AutopilotDryRunRequest) -> Dict[str, Any]:
    """Run a safe autopilot dry-run for a given action type.

    Only safe local actions are auto-allowed. Dangerous actions are blocked.
    No source-code mutation, no commit, no deploy, no external send.
    """
    try:
        ap = _get_autopilot()
        decision = ap.evaluate(req.action_type, req.context)
        return {
            "status": "ok",
            "dry_run": True,
            **decision.to_dict(),
        }
    except Exception as exc:
        logger.exception("NUS 1C autopilot run-dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1C — Failure learning routes
# ---------------------------------------------------------------------------


@router.get("/v1/nus/failure-learning/status")
async def nus_failure_learning_status() -> Dict[str, Any]:
    """Return cross-session failure learning status."""
    try:
        from openjarvis.nus.failure_learning import FailureLearner
        learner = FailureLearner()
        learner.analyze()
        return {"status": "ok", **learner.get_summary()}
    except Exception as exc:
        logger.exception("NUS 1C failure learning status error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1C — Operator telemetry ingest route
# ---------------------------------------------------------------------------


class OperatorTelemetryRequest(BaseModel):
    records: list = []


@router.post("/v1/nus/telemetry/operator/ingest-dry-run")
async def nus_operator_telemetry_ingest_dry_run(req: OperatorTelemetryRequest) -> Dict[str, Any]:
    """Ingest operator/agent telemetry records (dry-run — no external actions)."""
    try:
        normalizer = _get_normalizer()
        count = normalizer.ingest_operator_batch(req.records)
        return {
            "status": "ok",
            "dry_run": True,
            "ingested": count,
            "total_records": normalizer.record_count,
            "routing_observations": len(normalizer.to_routing_observations()),
        }
    except Exception as exc:
        logger.exception("NUS 1C operator telemetry ingest error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1C — Learned routing recommendation routes
# ---------------------------------------------------------------------------


@router.get("/v1/nus/routing/recommendations/status")
async def nus_routing_status() -> Dict[str, Any]:
    """Return learned routing recommendation status."""
    try:
        from openjarvis.nus.learned_routing import get_learned_router
        router_inst = get_learned_router()
        return {"status": "ok", **router_inst.get_status()}
    except Exception as exc:
        logger.exception("NUS 1C routing status error")
        raise HTTPException(status_code=500, detail=str(exc))


class RoutingDryRunRequest(BaseModel):
    task_category: str = "unknown"
    risk_level: str = "low"
    complexity_level: str = "moderate"
    validation_failures: int = 0
    context_size_tokens: int = 0


@router.post("/v1/nus/routing/recommendations/dry-run")
async def nus_routing_dry_run(req: RoutingDryRunRequest) -> Dict[str, Any]:
    """Generate a learned routing recommendation (dry-run — recommendation only, no model switch)."""
    try:
        from openjarvis.nus.learned_routing import get_learned_router
        router_inst = get_learned_router()
        rec = router_inst.recommend_for_task(
            task_category=req.task_category,
            risk_level=req.risk_level,
            complexity_level=req.complexity_level,
            context_size_tokens=req.context_size_tokens if req.context_size_tokens > 0 else None,
            validation_failures=req.validation_failures,
        )
        return {
            "status": "ok",
            "dry_run": True,
            **rec.to_dict(),
        }
    except Exception as exc:
        logger.exception("NUS 1C routing dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1D — Eval gate routes
# ---------------------------------------------------------------------------


class EvalRunRequest(BaseModel):
    action_type: str = "local_analysis"
    risk_level: str = "low"
    validation_plan: str = ""
    rollback_plan: str = ""
    capability_id: str = ""
    capability_ready: bool = True
    safety_gate_result: str = "pass"


@router.get("/v1/nus/eval/status")
async def nus_eval_status() -> Dict[str, Any]:
    """Return eval gate framework status."""
    try:
        from openjarvis.nus.eval_gate import get_eval_gate_status
        return {"status": "ok", **get_eval_gate_status()}
    except Exception as exc:
        logger.exception("NUS 1D eval status error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/v1/nus/eval/run-dry-run")
async def nus_eval_run_dry_run(req: EvalRunRequest) -> Dict[str, Any]:
    """Run eval gates against a candidate (dry-run — no execution)."""
    try:
        from openjarvis.nus.eval_gate import EvalCandidate, run_eval_gate
        candidate = EvalCandidate(
            action_type=req.action_type,
            risk_level=req.risk_level,
            validation_plan=req.validation_plan,
            rollback_plan=req.rollback_plan,
            capability_id=req.capability_id,
            capability_ready=req.capability_ready,
            safety_gate_result=req.safety_gate_result,
        )
        report = run_eval_gate(candidate)
        return {"status": "ok", "dry_run": True, **report.to_dict()}
    except Exception as exc:
        logger.exception("NUS 1D eval run-dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/rollback/status")
async def nus_rollback_status() -> Dict[str, Any]:
    """Return rollback enforcer status."""
    try:
        from openjarvis.nus.rollback import RollbackEnforcer
        enforcer = RollbackEnforcer()
        return {"status": "ok", **enforcer.get_status()}
    except Exception as exc:
        logger.exception("NUS 1D rollback status error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/approvals/status")
async def nus_approvals_status() -> Dict[str, Any]:
    """Return approval workflow status."""
    try:
        from openjarvis.nus.approval_workflow import ApprovalWorkflow
        wf = ApprovalWorkflow()
        return {"status": "ok", **wf.get_status()}
    except Exception as exc:
        logger.exception("NUS 1D approvals status error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1E — Low-risk execution routes
# ---------------------------------------------------------------------------


@router.get("/v1/nus/execution/low-risk/status")
async def nus_low_risk_status() -> Dict[str, Any]:
    """Return low-risk execution manager status."""
    try:
        from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
        mgr = LowRiskExecutionManager()
        return {"status": "ok", **mgr.get_status()}
    except Exception as exc:
        logger.exception("NUS 1E low-risk status error")
        raise HTTPException(status_code=500, detail=str(exc))


class LowRiskDryRunRequest(BaseModel):
    action_type: str = "local_analysis"
    risk_level: str = "low"
    file_targets: list = []
    tool_requirements: list = []
    agent_metadata: Dict[str, Any] = {}
    task_category: str = "unknown"


@router.post("/v1/nus/execution/low-risk/dry-run")
async def nus_low_risk_dry_run(req: LowRiskDryRunRequest) -> Dict[str, Any]:
    """Classify and dry-run a low-risk execution candidate."""
    try:
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        clf = ExecutionClassifier()
        result = clf.classify(
            action_type=req.action_type,
            risk_level=req.risk_level,
            file_targets=req.file_targets,
            tool_requirements=req.tool_requirements,
            agent_metadata=req.agent_metadata,
            task_category=req.task_category,
        )
        return {"status": "ok", "dry_run": True, **result.to_dict()}
    except Exception as exc:
        logger.exception("NUS 1E low-risk dry-run error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/governance/future-proof/status")
async def nus_governance_future_proof_status() -> Dict[str, Any]:
    """Return future-proof governance status."""
    try:
        from openjarvis.nus.execution_classifier import ExecutionClassifier
        clf = ExecutionClassifier()
        return {
            "status": "ok",
            "future_proof_governance": True,
            "agent_name_agnostic": True,
            "metadata_contract_driven": True,
            "classifier_status": clf.get_status(),
            "docs": [
                "docs/JARVIS_FUTURE_PROOF_ARCHITECTURE_PRINCIPLES.md",
                "docs/JARVIS_AGENT_REGISTRY_AND_CONTRACTS.md",
                "docs/JARVIS_ROUTING_MODEL_POLICY.md",
                "docs/JARVIS_95_PERCENT_AUTONOMY_TARGET.md",
                "docs/JARVIS_TOKEN_COST_GOVERNANCE.md",
                "docs/POST_NUS_COMPANY_AGENT_ORCHESTRATOR_PLAN.md",
            ],
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }
    except Exception as exc:
        logger.exception("NUS governance future-proof status error")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# NUS 1F — Controlled High-Autonomy Session Framework routes
# ---------------------------------------------------------------------------


@router.get("/v1/nus/high-autonomy/status")
async def nus_high_autonomy_status() -> Dict[str, Any]:
    """Return NUS 1F controlled high-autonomy framework status."""
    try:
        from openjarvis.nus.high_autonomy_session import get_session_manager, NUS1F_SESSION_VERSION
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        from openjarvis.nus.production_gate import get_production_gate
        from openjarvis.nus.decision_record import get_decision_record_status

        mgr = get_session_manager()
        policy = get_action_policy()
        gate = get_production_gate()
        dr_status = get_decision_record_status()

        return {
            "status": "ok",
            "nus1f_session_version": NUS1F_SESSION_VERSION,
            "session_manager": mgr.get_status(),
            "action_policy": policy.get_status(),
            "production_gate": gate.get_status(),
            "decision_record_schema": dr_status,
            "production_autonomy_enabled": False,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
            "no_real_deploy": True,
            "no_auto_push": True,
            "no_auto_merge": True,
        }
    except Exception as exc:
        logger.exception("NUS 1F high-autonomy status error")
        raise HTTPException(status_code=500, detail=str(exc))


class HighAutonomySessionDryRunRequest(BaseModel):
    owner: str = "founder"
    requested_profile: str = "safe_autopilot"
    ttl_seconds: float = 3600.0
    allowed_domains: list = []
    allowed_action_types: list = []
    blocked_action_types: list = []
    allowed_repos_or_paths: list = []
    cost_budget: float = 0.0
    token_budget: int = 0
    time_budget: float = 0.0
    risk_ceiling: str = "low"
    tool_policy: Dict[str, Any] = {}
    validation_policy: Dict[str, Any] = {}
    rollback_policy: Dict[str, Any] = {}
    reason: str = ""


@router.post("/v1/nus/high-autonomy/session/dry-run-create")
async def nus_session_dry_run_create(req: HighAutonomySessionDryRunRequest) -> Dict[str, Any]:
    """Dry-run create a high-autonomy session. No real execution."""
    try:
        from openjarvis.nus.high_autonomy_session import (
            get_session_manager, SessionCreateRequest,
        )
        mgr = get_session_manager()
        create_req = SessionCreateRequest(
            owner=req.owner,
            requested_profile=req.requested_profile,
            ttl_seconds=req.ttl_seconds,
            allowed_domains=req.allowed_domains,
            allowed_action_types=req.allowed_action_types,
            blocked_action_types=req.blocked_action_types,
            allowed_repos_or_paths=req.allowed_repos_or_paths,
            cost_budget=req.cost_budget,
            token_budget=req.token_budget,
            time_budget=req.time_budget,
            risk_ceiling=req.risk_ceiling,
            tool_policy=req.tool_policy,
            validation_policy=req.validation_policy,
            rollback_policy=req.rollback_policy,
            reason=req.reason,
        )
        result = mgr.create_session(create_req)
        return {"status": "ok", "dry_run": True, **result.to_dict()}
    except Exception as exc:
        logger.exception("NUS 1F session dry-run create error")
        raise HTTPException(status_code=500, detail=str(exc))


class SessionActionEvalRequest(BaseModel):
    session_id: str
    action_type: str = "local_read"


@router.post("/v1/nus/high-autonomy/session/evaluate-dry-run")
async def nus_session_evaluate_dry_run(req: SessionActionEvalRequest) -> Dict[str, Any]:
    """Evaluate whether an action is allowed in a session. Dry-run only."""
    try:
        from openjarvis.nus.high_autonomy_session import get_session_manager
        mgr = get_session_manager()
        result = mgr.evaluate_action(req.session_id, req.action_type)
        return {"status": "ok", "dry_run": True, **result}
    except Exception as exc:
        logger.exception("NUS 1F session evaluate error")
        raise HTTPException(status_code=500, detail=str(exc))


class SessionRevokeRequest(BaseModel):
    session_id: str
    reason: str = ""


@router.post("/v1/nus/high-autonomy/session/revoke-dry-run")
async def nus_session_revoke_dry_run(req: SessionRevokeRequest) -> Dict[str, Any]:
    """Revoke a high-autonomy session. Dry-run only."""
    try:
        from openjarvis.nus.high_autonomy_session import get_session_manager
        mgr = get_session_manager()
        result = mgr.revoke_session(req.session_id, req.reason)
        return {"status": "ok", "dry_run": True, **result.to_dict()}
    except Exception as exc:
        logger.exception("NUS 1F session revoke error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/high-autonomy/policy/status")
async def nus_high_autonomy_policy_status() -> Dict[str, Any]:
    """Return 95% automation action policy status."""
    try:
        from openjarvis.nus.autonomy_action_policy import get_action_policy
        policy = get_action_policy()
        return {"status": "ok", **policy.get_status()}
    except Exception as exc:
        logger.exception("NUS 1F policy status error")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/v1/nus/production-gate/status")
async def nus_production_gate_status() -> Dict[str, Any]:
    """Return production gate status. Production execution blocked in NUS 1F."""
    try:
        from openjarvis.nus.production_gate import get_production_gate
        gate = get_production_gate()
        return {"status": "ok", **gate.get_status()}
    except Exception as exc:
        logger.exception("NUS 1F production gate status error")
        raise HTTPException(status_code=500, detail=str(exc))


class ProductionGateDryRunRequest(BaseModel):
    owner: str = "founder"
    action_type: str = "staging_deploy"
    environment: str = "staging"
    rollback_plan: Dict[str, Any] = {}
    validation_plan: Dict[str, Any] = {}
    audit_log_id: str = ""
    risk_review: Dict[str, Any] = {}
    cost_budget: float = 0.0
    secret_leakage_checked: bool = False
    kill_switch_available: bool = False
    owner_authorization: str = ""
    staging_preconditions: Dict[str, Any] = {}
    reason: str = ""


@router.post("/v1/nus/production-gate/evaluate-dry-run")
async def nus_production_gate_evaluate_dry_run(req: ProductionGateDryRunRequest) -> Dict[str, Any]:
    """Evaluate production gate dry-run. No real execution. Always blocked or dry-run in NUS 1F."""
    try:
        from openjarvis.nus.production_gate import get_production_gate, create_production_gate_request
        gate = get_production_gate()
        gate_req = create_production_gate_request(
            owner=req.owner,
            action_type=req.action_type,
            environment=req.environment,
            rollback_plan=req.rollback_plan,
            validation_plan=req.validation_plan,
            audit_log_id=req.audit_log_id,
            risk_review=req.risk_review,
            cost_budget=req.cost_budget,
            secret_leakage_checked=req.secret_leakage_checked,
            kill_switch_available=req.kill_switch_available,
            owner_authorization=req.owner_authorization,
            staging_preconditions=req.staging_preconditions,
            reason=req.reason,
        )
        result = gate.evaluate(gate_req)
        return {"status": "ok", "dry_run": True, **result.to_dict()}
    except Exception as exc:
        logger.exception("NUS 1F production gate evaluate error")
        raise HTTPException(status_code=500, detail=str(exc))


class DecisionRecordDryRunRequest(BaseModel):
    action_type: str = "local_read"
    decision: str = "allowed"
    reason: str = "test"
    evidence: Dict[str, Any] = {}
    session_id: str = ""
    hierarchy_level: str = "jarvis_pa"
    risk_level: str = "low"


@router.post("/v1/nus/decision-records/dry-run")
async def nus_decision_record_dry_run(req: DecisionRecordDryRunRequest) -> Dict[str, Any]:
    """Create a structured decision record (dry-run). No raw chain-of-thought stored."""
    try:
        from openjarvis.nus.decision_record import build_action_decision_record
        dr = build_action_decision_record(
            action_type=req.action_type,
            decision=req.decision,
            reason=req.reason,
            evidence=req.evidence,
            session_id=req.session_id,
            hierarchy_level=req.hierarchy_level,
            risk_level=req.risk_level,
        )
        return {"status": "ok", "dry_run": True, "decision_record": dr}
    except Exception as exc:
        logger.exception("NUS 1F decision record error")
        raise HTTPException(status_code=500, detail=str(exc))
