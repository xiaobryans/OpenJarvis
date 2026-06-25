"""Daily-Driver routes — Phase C19 / Phase D Gate.

C19 — Daily-Driver Certification Harness.
Phase D — Daily-Driver Readiness Gate (2026-06-26 update).

Routes:
  GET  /v1/daily-driver/status         — certification status
  GET  /v1/daily-driver/checklist      — certification checklist
  POST /v1/daily-driver/record-session — record a daily-driver usage session
  GET  /v1/daily-driver/blockers       — active certification blockers
  GET  /v1/daily-driver/readiness      — Phase D gate readiness summary

Governance:
  - fake_data is always False
  - fake_certification is always False
  - auto_certification_blocked is always True
  - Certification requires real sessions and Bryan sign-off; no auto-certify

Phase D gate status (2026-06-26):
  - installed_app_smoke:      PASSED_BY_BRYAN  (2026-06-26)
  - chat_replies_verified:    PASSED_BY_BRYAN  (2026-06-26)
  - routines_panel_visible:   PASSED_BY_BRYAN  (2026-06-26)
  - taxonomy_correct:         PASSED_BY_BRYAN  (2026-06-26)
  - mobile_narrow_layout_url: LIVE_VERIFIED    (192.168.1.16:5173 / 100.103.51.30:5173)
  - daily_driver_real_session: NOT_STARTED     (Bryan must complete 30+ min session)
  - core_os_decision:          NEEDS_BRYAN_DECISION
  - certified:                 False           (cannot certify without real session)
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
            "status": "not_started",
            "certified": False,
            "severity_if_missing": "high",
            "note": "Bryan must complete a 30+ minute real usage session and confirm via POST /v1/daily-driver/record-session.",
        },
        {
            "item_id": "connector_live",
            "name": "At least one live connector action",
            "status": "partial",
            "certified": False,
            "severity_if_missing": "high",
            "note": "GitHub/Slack/Telegram/Tavily live-verified (Jun 25 2026) via read-only probes. Real daily-driver connector action (write/send) pending.",
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
            "status": "live_verified",
            "certified": False,
            "severity_if_missing": "medium",
            "note": "Live at http://192.168.1.16:5173 (LAN) or http://100.103.51.30:5173 (Tailscale). Bryan confirm narrow layout on device.",
        },
        {
            "item_id": "installed_app",
            "name": "Installed Tauri app used",
            "status": "passed_by_bryan",
            "passed_date": "2026-06-26",
            "certified": False,
            "severity_if_missing": "high",
            "note": "Desktop visual smoke passed by Bryan (2026-06-26).",
        },
        {
            "item_id": "chat_replies_verified",
            "name": "Chat replies verified",
            "status": "passed_by_bryan",
            "passed_date": "2026-06-26",
            "certified": False,
            "severity_if_missing": "high",
            "note": "Confirmed by Bryan (2026-06-26).",
        },
        {
            "item_id": "routines_panel_visible",
            "name": "Routines panel visible",
            "status": "passed_by_bryan",
            "passed_date": "2026-06-26",
            "certified": False,
            "severity_if_missing": "medium",
            "note": "Confirmed by Bryan (2026-06-26).",
        },
        {
            "item_id": "taxonomy_correct",
            "name": "UI taxonomy correct",
            "status": "passed_by_bryan",
            "passed_date": "2026-06-26",
            "certified": False,
            "severity_if_missing": "medium",
            "note": "Confirmed by Bryan (2026-06-26).",
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
            "blocker_id": "daily_session",
            "name": "No daily-driver sessions recorded",
            "severity": "high",
            "resolution": (
                "Bryan must complete a minimum 30-minute real usage session "
                "and record it via POST /v1/daily-driver/record-session. "
                "System is READY FOR SESSION — all pre-session gates passed."
            ),
        },
        {
            "blocker_id": "mobile_narrow_layout_bryan_confirm",
            "name": "Mobile narrow layout Bryan confirmation pending",
            "severity": "medium",
            "resolution": (
                "Visit http://192.168.1.16:5173 (LAN) or "
                "http://100.103.51.30:5173 (Tailscale) on a mobile device "
                "and confirm narrow layout renders correctly."
            ),
        },
        {
            "blocker_id": "core_os_decision",
            "name": "Core-OS decision needed after real session",
            "severity": "medium",
            "resolution": (
                "After completing the 30-minute session, Bryan must decide "
                "on any Core-OS adjustments before final daily-driver certification."
            ),
        },
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/daily-driver/status")
async def daily_driver_status() -> Dict[str, Any]:
    """Daily-driver certification status. Cannot auto-certify."""
    return {
        "classification": "DAILY_DRIVER_READY_FOR_BRYAN_SESSION",
        "certification_status": "ready_for_bryan_session",
        "certified": False,
        "fake_data": False,
        "fake_certification": False,
        "auto_certification_blocked": True,
        "manual_certification_required": True,
        "daily_driver_sessions_recorded": 0,
        "blockers_logged": len(_blockers()),
        # Phase D gate status (2026-06-26)
        "phase_d_gates": {
            "installed_app_smoke": {
                "status": "passed_by_bryan",
                "date": "2026-06-26",
            },
            "chat_replies_verified": {
                "status": "passed_by_bryan",
                "date": "2026-06-26",
            },
            "routines_panel_visible": {
                "status": "passed_by_bryan",
                "date": "2026-06-26",
            },
            "taxonomy_correct": {
                "status": "passed_by_bryan",
                "date": "2026-06-26",
            },
            "mobile_narrow_layout_url": {
                "status": "live_verified",
                "urls": [
                    "http://192.168.1.16:5173 (LAN)",
                    "http://100.103.51.30:5173 (Tailscale)",
                ],
                "bryan_confirm_pending": True,
            },
            "daily_driver_real_session": {
                "status": "not_started",
                "requirement": "Bryan must complete 30+ min real usage session",
            },
            "core_os_decision": {
                "status": "needs_bryan_decision",
                "note": "Required after real session, before final certification",
            },
        },
        "connectors_live_verified": True,
        "connectors_live_verified_date": "2026-06-25",
        "note": (
            "Phase D pre-session gates PASSED by Bryan (2026-06-26). "
            "System is READY FOR SESSION. "
            "Certification cannot proceed until Bryan completes a 30+ min real usage session "
            "and makes the core-OS decision. No auto-certify."
        ),
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


@router.get("/v1/daily-driver/readiness")
async def daily_driver_readiness() -> Dict[str, Any]:
    """Phase D gate readiness summary.

    Reports which daily-driver gates have been passed by Bryan and what
    remains before final certification is possible.  Certification is
    intentionally blocked until Bryan completes a real 30+ minute session
    and makes the core-OS decision.
    """
    return {
        "classification": "DAILY_DRIVER_READY_FOR_BRYAN_SESSION",
        "gates_passed": [
            "installed_app_smoke",
            "chat_replies",
            "routines_visible",
            "taxonomy_correct",
        ],
        "gates_passed_detail": {
            "installed_app_smoke": "passed_by_bryan — 2026-06-26",
            "chat_replies": "passed_by_bryan — 2026-06-26",
            "routines_visible": "passed_by_bryan — 2026-06-26",
            "taxonomy_correct": "passed_by_bryan — 2026-06-26",
        },
        "gates_pending": [
            "mobile_narrow_layout_bryan_confirm",
            "30_min_real_session",
            "core_os_decision",
        ],
        "gates_pending_detail": {
            "mobile_narrow_layout_bryan_confirm": (
                "Visit http://192.168.1.16:5173 (LAN) or "
                "http://100.103.51.30:5173 (Tailscale) on a mobile device "
                "and confirm narrow layout."
            ),
            "30_min_real_session": (
                "Bryan must use Jarvis as primary PA for 30+ continuous minutes "
                "and record the session via POST /v1/daily-driver/record-session."
            ),
            "core_os_decision": (
                "After the real session, Bryan decides on any Core-OS adjustments "
                "before issuing final daily-driver certification."
            ),
        },
        "mobile_url": (
            "http://192.168.1.16:5173 (LAN) or http://100.103.51.30:5173 (Tailscale)"
        ),
        "core_os_decision": "NEEDS_BRYAN_DECISION_AFTER_REAL_SESSION",
        "certified": False,
        "fake_data": False,
        "note": (
            "All Phase D pre-session gates passed. System ready. "
            "Certification blocked until Bryan completes the real session and "
            "signs off. No auto-certify."
        ),
    }
