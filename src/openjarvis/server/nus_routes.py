"""NUS 1A REST API routes — Learning Foundation (read-only).

Routes:
  GET /v1/nus/learning/status           — NUS 1A status + safety gates
  GET /v1/nus/learning/scorecards       — Generate and return an AgentScorecard
  GET /v1/nus/learning/failure-patterns — Detected failure patterns
  GET /v1/nus/learning/snapshot         — Full learning snapshot

Safety constraints (all routes):
  - Read-only / dry-run only.
  - No writes, deploys, external sends, or secret access.
  - No self-modification.
  - US13 voice remains HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
except ImportError:
    raise ImportError("fastapi is required for NUS routes")

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
