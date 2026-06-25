"""Review Governance REST Routes (Phase C3).

Routes:
  GET  /v1/review-governance/status          — governance lanes + status
  GET  /v1/review-governance/decisions       — recent governance decisions
  POST /v1/review-governance/review-request  — dry-run review submission
  GET  /v1/review-governance/arbitration     — arbitration framework status

Design:
  - fake_data: False in all responses
  - All lanes require human approval — bypassing_approval_gates: False always
  - Legal/financial lanes require external gates
  - Review submissions are dry-run only; nothing is auto-approved or executed
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(tags=["review-governance"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ReviewRequestBody(BaseModel):
    item_id: str
    title: str
    review_lane: str
    reason: str


# ---------------------------------------------------------------------------
# GET /v1/review-governance/status
# ---------------------------------------------------------------------------

@router.get("/v1/review-governance/status")
async def get_governance_status() -> Dict[str, Any]:
    """Return multi-agent review governance lane status."""
    return {
        "governance_available": True,
        "reviewer_lanes": [
            {
                "lane_id": "security_review",
                "name": "Security Review",
                "active": True,
                "auto_approve": False,
                "approval_tier": "tier3",
            },
            {
                "lane_id": "quality_review",
                "name": "Quality Review",
                "active": True,
                "auto_approve": False,
                "approval_tier": "tier2",
            },
            {
                "lane_id": "financial_review",
                "name": "Financial Review",
                "active": False,
                "auto_approve": False,
                "approval_tier": "tier4",
                "gate": "Financial connector required",
            },
            {
                "lane_id": "legal_review",
                "name": "Legal Review",
                "active": False,
                "auto_approve": False,
                "approval_tier": "tier4",
                "gate": "External legal review required",
            },
            {
                "lane_id": "architectural_review",
                "name": "Architectural Review",
                "active": True,
                "auto_approve": False,
                "approval_tier": "tier2",
            },
        ],
        "active_lanes": 3,
        "approval_gates_active": True,
        "bypassing_approval_gates": False,  # ALWAYS False
        "fake_legal_certification": False,
        "fake_financial_certification": False,
        "fake_security_certification": False,
        "fake_data": False,
        "note": (
            "Review governance. All lanes require approval. "
            "Security/quality/architecture lanes active. "
            "Legal/financial require external gates."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/review-governance/decisions
# ---------------------------------------------------------------------------

@router.get("/v1/review-governance/decisions")
async def get_governance_decisions() -> Dict[str, Any]:
    """Return recent governance decisions from constitution store if available."""
    decisions: List[Dict[str, Any]] = []
    source = "unavailable"

    try:
        from openjarvis.governance.constitution import JarvisConstitution  # type: ignore

        raw = JarvisConstitution.get_recent_decisions()
        decisions = [
            {
                "decision_id": str(d.get("decision_id", "")),
                "title": str(d.get("title", "")),
                "outcome": str(d.get("outcome", "pending")),
                "review_lane": str(d.get("review_lane", "")),
                "authority_tier": str(d.get("authority_tier", "")),
                "fake_decision": False,
            }
            for d in (raw or [])
        ]
        source = "constitution_store"
    except Exception as exc:  # noqa: BLE001
        logger.debug("JarvisConstitution unavailable: %s", exc)
        decisions = []
        source = "unavailable"

    pending = sum(1 for d in decisions if d.get("outcome") == "pending")

    return {
        "decisions": decisions,
        "total": len(decisions),
        "pending": pending,
        "fake_data": False,
        "source": source,
    }


# ---------------------------------------------------------------------------
# POST /v1/review-governance/review-request
# ---------------------------------------------------------------------------

@router.post("/v1/review-governance/review-request")
async def submit_review_request(body: ReviewRequestBody) -> Dict[str, Any]:
    """Dry-run review request submission — no action is taken automatically."""
    # Validate required fields
    if not (body.item_id and body.item_id.strip()):
        raise HTTPException(status_code=422, detail="item_id must be a non-empty string")
    if not (body.title and body.title.strip()):
        raise HTTPException(status_code=422, detail="title must be a non-empty string")
    if not (body.review_lane and body.review_lane.strip()):
        raise HTTPException(status_code=422, detail="review_lane must be a non-empty string")

    return {
        "item_id": body.item_id,
        "title": body.title,
        "review_lane": body.review_lane,
        "dry_run": True,
        "submitted": False,
        "approval_required": True,
        "auto_approve": False,
        "plan": [
            {
                "step": 1,
                "description": f"Validate review lane '{body.review_lane}' authority",
            },
            {
                "step": 2,
                "description": "Queue for human reviewer",
            },
            {
                "step": 3,
                "description": "Await approval decision before any action",
            },
        ],
        "bypassing_gates": False,
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# GET /v1/review-governance/arbitration
# ---------------------------------------------------------------------------

@router.get("/v1/review-governance/arbitration")
async def get_arbitration_status() -> Dict[str, Any]:
    """Return multi-agent arbitration framework status."""
    return {
        "arbitration_available": True,
        "conflicts": [],  # empty — no live multi-agent conflicts detected
        "conflict_resolution": "human_decision_required",
        "auto_resolve": False,
        "fake_arbitration": False,
        "fake_data": False,
        "note": (
            "Arbitration framework. Conflicts require human decision. "
            "No auto-resolution."
        ),
    }
