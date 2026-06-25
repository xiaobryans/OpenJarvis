"""Final Smoke routes — Phase C18.

C18 — Core OS Final Smoke Orchestrator.

Routes:
  GET  /v1/final-smoke/checklist      — full smoke checklist (manual proof required)
  GET  /v1/final-smoke/status         — overall smoke status
  POST /v1/final-smoke/capture-proof  — record proof for a checklist item

Governance:
  - fake_data is always False
  - auto_pass_blocked is always True
  - No checklist item can auto-pass — all require manual Bryan proof
  - No auto-acceptance; Bryan must verify every item
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for final smoke routes")

router = APIRouter(tags=["final-smoke"])
__all__ = ["router"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class CaptureProofRequest(BaseModel):
    item_id: str = Field(..., description="Checklist item ID to record proof for")
    proof_type: str = Field(..., description="Type of proof (screenshot, log, live-demo, etc.)")
    evidence_summary: str = Field(..., description="Summary of the evidence captured")


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


def _checklist_items() -> List[Dict[str, Any]]:
    return [
        {
            "item_id": "backend_health",
            "name": "Backend API health",
            "status": "pending",
            "requires_manual_proof": True,
            "auto_passable": False,
        },
        {
            "item_id": "frontend_build",
            "name": "Frontend build clean",
            "status": "pending",
            "requires_manual_proof": True,
            "auto_passable": False,
        },
        {
            "item_id": "connector_smoke",
            "name": "Connector live smoke",
            "status": "pending",
            "requires_manual_proof": True,
            "auto_passable": False,
        },
        {
            "item_id": "desktop_ui",
            "name": "Desktop UI functional",
            "status": "pending",
            "requires_manual_proof": True,
            "auto_passable": False,
        },
        {
            "item_id": "mobile_pwa",
            "name": "Mobile PWA accessible",
            "status": "pending",
            "requires_manual_proof": True,
            "auto_passable": False,
        },
        {
            "item_id": "approval_gates",
            "name": "Approval gates active",
            "status": "pending",
            "requires_manual_proof": True,
            "auto_passable": False,
        },
        {
            "item_id": "installed_app",
            "name": "Installed app smoke (Tauri DMG)",
            "status": "blocked",
            "requires_manual_proof": True,
            "blocked_reason": "Held pending latest accepted build",
        },
        {
            "item_id": "daily_driver",
            "name": "Daily-driver session completed",
            "status": "blocked",
            "requires_manual_proof": True,
            "blocked_reason": "Held pending latest accepted build",
        },
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/final-smoke/checklist")
async def final_smoke_checklist() -> Dict[str, Any]:
    """Return the full smoke checklist. All items require manual proof."""
    items = _checklist_items()
    return {
        "checklist": items,
        "total": len(items),
        "passed": 0,
        "failed": 0,
        "pending_manual_proof": len(items),
        "manual_proof_required": True,
        "auto_pass_blocked": True,
        "fake_data": False,
        "note": "All checklist items require manual proof or live evidence from Bryan.",
    }


@router.get("/v1/final-smoke/status")
async def final_smoke_status() -> Dict[str, Any]:
    """Overall smoke status — never auto-passes."""
    return {
        "smoke_status": "pending",
        "manual_proof_required": True,
        "claimed_passed": False,
        "fake_smoke_result": False,
        "installed_app_smoke": "blocked_pending_notarize_and_bryan_visual_proof",
        "daily_driver": "blocked_pending_daily_driver_usage_sessions",
        "fake_data": False,
    }


@router.post("/v1/final-smoke/capture-proof")
async def final_smoke_capture_proof(body: CaptureProofRequest) -> Dict[str, Any]:
    """Record proof for a checklist item. Bryan must still verify — no auto-acceptance."""
    if not body.item_id.strip():
        raise HTTPException(status_code=422, detail="item_id must be non-empty")
    if not body.evidence_summary.strip():
        raise HTTPException(status_code=422, detail="evidence_summary must be non-empty")

    logger.info("Smoke proof captured for item_id=%s proof_type=%s", body.item_id, body.proof_type)
    return {
        "item_id": body.item_id,
        "proof_recorded": True,
        "auto_passed": False,
        "requires_bryan_verification": True,
        "note": "Proof captured. Bryan must verify and mark passed. No auto-acceptance.",
        "fake_data": False,
    }
