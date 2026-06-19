"""NUS REST API routes — Learning Foundation (1A) + Recommendation Workflow (1B).

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

Safety constraints (all routes):
  - Read-only or dry-run only.
  - No writes, deploys, external sends, or secret access.
  - No self-modification.
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
