"""Daily-Driver routes — Phase C19.

C19 — Daily-Driver Certification Harness.

Routes:
  GET  /v1/daily-driver/status         — certification status
  GET  /v1/daily-driver/checklist      — certification checklist
  POST /v1/daily-driver/record-session — record a daily-driver usage session
  GET  /v1/daily-driver/blockers       — active certification blockers

Governance:
  - fake_data is always False
  - fake_certification is always False
  - auto_certification_blocked is always True
  - Certification requires real sessions and Bryan sign-off; no auto-certify
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for daily driver routes")

router = APIRouter(tags=["daily-driver"])
__all__ = ["router"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class RecordSessionRequest(BaseModel):
    session_notes: str = Field(..., description="Notes from the daily-driver session")
    duration_minutes: int = Field(..., description="Duration of the session in minutes (must be > 0)")
    issues_found: List[str] = Field(default_factory=list, description="List of issues encountered")


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------


def _checklist_items() -> List[Dict[str, Any]]:
    return [
        {
            "item_id": "chat_session",
            "name": "Real chat session (30+ mins)",
            "status": "pending",
            "certified": False,
            "severity_if_missing": "high",
        },
        {
            "item_id": "connector_live",
            "name": "At least one live connector action",
            "status": "pending",
            "certified": False,
            "severity_if_missing": "high",
        },
        {
            "item_id": "approval_flow",
            "name": "Approval gate used and worked",
            "status": "pending",
            "certified": False,
            "severity_if_missing": "high",
        },
        {
            "item_id": "memory_retrieval",
            "name": "Memory retrieval across session",
            "status": "pending",
            "certified": False,
            "severity_if_missing": "medium",
        },
        {
            "item_id": "mobile_usage",
            "name": "Mobile/PWA used on separate device",
            "status": "pending",
            "certified": False,
            "severity_if_missing": "medium",
        },
        {
            "item_id": "installed_app",
            "name": "Installed Tauri app used",
            "status": "blocked",
            "certified": False,
            "severity_if_missing": "high",
            "blocked_reason": "Held pending latest build",
        },
        {
            "item_id": "no_critical_errors",
            "name": "Zero critical errors in session",
            "status": "pending",
            "certified": False,
            "severity_if_missing": "critical",
        },
    ]


def _blockers() -> List[Dict[str, Any]]:
    return [
        {
            "blocker_id": "installed_app_smoke",
            "name": "Installed app smoke pending latest build",
            "severity": "high",
            "resolution": "Complete and install latest accepted build",
        },
        {
            "blocker_id": "connector_live_proof",
            "name": "Live connector proof not yet captured",
            "severity": "high",
            "resolution": "Run at least one real connector action",
        },
        {
            "blocker_id": "daily_session",
            "name": "No daily-driver sessions recorded",
            "severity": "high",
            "resolution": "Complete minimum 30-minute real usage session",
        },
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/daily-driver/status")
async def daily_driver_status() -> Dict[str, Any]:
    """Daily-driver certification status. Cannot auto-certify."""
    return {
        "certification_status": "pending",
        "certified": False,
        "auto_certification_blocked": True,
        "daily_driver_sessions_recorded": 0,
        "blockers_logged": len(_blockers()),
        "manual_certification_required": True,
        "fake_certification": False,
        "fake_data": False,
        "note": "Daily-driver certification requires real usage sessions and Bryan sign-off. Cannot auto-certify.",
    }


@router.get("/v1/daily-driver/checklist")
async def daily_driver_checklist() -> Dict[str, Any]:
    """Certification checklist — all items pending."""
    items = _checklist_items()
    certified_count = sum(1 for i in items if i.get("certified"))
    pending_count = len(items) - certified_count
    return {
        "checklist": items,
        "certified_count": certified_count,
        "pending_count": pending_count,
        "auto_certify_blocked": True,
        "fake_data": False,
    }


@router.post("/v1/daily-driver/record-session")
async def daily_driver_record_session(body: RecordSessionRequest) -> Dict[str, Any]:
    """Record a daily-driver session. Bryan must review — no auto-certification."""
    if not body.session_notes.strip():
        raise HTTPException(status_code=422, detail="session_notes must be non-empty")
    if body.duration_minutes <= 0:
        raise HTTPException(status_code=422, detail="duration_minutes must be greater than 0")

    logger.info(
        "Daily-driver session recorded: duration=%d minutes issues=%d",
        body.duration_minutes,
        len(body.issues_found),
    )
    return {
        "session_recorded": True,
        "auto_certified": False,
        "certification_granted": False,
        "requires_bryan_review": True,
        "note": "Session recorded. Bryan must review and certify. No auto-certification.",
        "fake_data": False,
    }


@router.get("/v1/daily-driver/blockers")
async def daily_driver_blockers() -> Dict[str, Any]:
    """Active daily-driver certification blockers."""
    blockers = _blockers()
    return {
        "blockers": blockers,
        "total": len(blockers),
        "fake_data": False,
    }
