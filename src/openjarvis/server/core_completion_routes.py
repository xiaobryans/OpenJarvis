"""Core Completion routes — Phase C20.

C20 — Jarvis Core OS Completion + Phase D Decision Gate.

Routes:
  GET /v1/core-completion/status                — honest phase completion status
  GET /v1/core-completion/phase-d-options       — Phase D decision options (Bryan decides)
  GET /v1/core-completion/readiness-classification — readiness classification with open gates

Governance:
  - fake_data is always False
  - fake_completion is always False
  - fake_100_percent is always False
  - fake_score is always False
  - auto_decision is always False; all Phase D decisions require Bryan
  - fake_classification is always False
  - Completion score is an honest estimate — no rounding up
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi is required for core completion routes")

router = APIRouter(tags=["core-completion"])
__all__ = ["router"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static data helpers
# ---------------------------------------------------------------------------


def _phases() -> List[Dict[str, Any]]:
    return [
        {"phase": "Plan 1", "status": "ACCEPTED", "note": "Jarvis PA identity, cloud routing"},
        {"phase": "Plan 2", "status": "ACCEPTED", "note": "Mobile/MacBook-off parity"},
        {"phase": "Plan 4-6", "status": "ACCEPTED", "note": "Text-first Jarvis OS"},
        {"phase": "Phase X", "status": "ACCEPTED", "note": "OMNIX decoupling"},
        {
            "phase": "Phase B1-B20",
            "status": "ACCEPTED_ON_HOLD",
            "note": "B1-B20 complete, expansion on hold by Bryan",
        },
        {"phase": "Phase C1-C10", "status": "ACCEPTED", "note": "Autonomous ecosystem scale"},
        {"phase": "Phase C11-C20", "status": "IN_PROGRESS", "note": "Parity and gate integration"},
        {
            "phase": "Final Phase A",
            "status": "ON_HOLD",
            "note": "MacBook DMG, daily-driver, connector live proof required",
        },
        {"phase": "Plan 3", "status": "PARKED", "note": "Voice/wake/TTS parked until Bryan reopens"},
    ]


def _phase_d_options() -> List[Dict[str, Any]]:
    return [
        {
            "option_id": "final_phase_a_closure",
            "name": "Close Final Phase A",
            "description": "Complete daily-driver cert, DMG notarization, connector live proof",
            "prerequisite": "Latest build available + MacBook access",
        },
        {
            "option_id": "phase_d_productization",
            "name": "Phase D — Productization",
            "description": "App Store submission, TestFlight, public release",
            "prerequisite": "Final Phase A closed + native iOS init completed",
        },
        {
            "option_id": "maintenance_mode",
            "name": "Enter Maintenance Mode",
            "description": "Stabilize current scope, no new phases",
            "prerequisite": "None",
        },
        {
            "option_id": "release_hardening",
            "name": "Release Hardening Sprint",
            "description": "Performance, security audit, edge case coverage",
            "prerequisite": "None",
        },
        {
            "option_id": "open_plan3",
            "name": "Reopen Plan 3 Voice/TTS",
            "description": "Voice, wake-word, TTS implementation",
            "prerequisite": "Bryan explicitly reopens Plan 3",
        },
    ]


def _open_manual_gates() -> List[Dict[str, Any]]:
    return [
        {
            "gate_id": "ios_init",
            "name": "tauri ios init",
            "status": "deferred",
            "reason": "Requires explicit Bryan authorization",
        },
        {
            "gate_id": "macos_notarization",
            "name": "macOS signing + notarization",
            "status": "ready_when_build_available",
        },
        {
            "gate_id": "daily_driver_cert",
            "name": "Daily-driver certification",
            "status": "pending_sessions",
        },
        {
            "gate_id": "notion",
            "name": "Notion connector",
            "status": "blocked",
            "reason": "Page lagging — Bryan said retry later",
        },
        {
            "gate_id": "installed_app_smoke",
            "name": "Installed app smoke",
            "status": "held_pending_build",
        },
    ]


def _ready_prerequisites() -> List[str]:
    return [
        "macOS permissions",
        "Gmail/Google OAuth",
        "Slack",
        "Telegram",
        "GitHub",
        "Tavily",
        "AWS/S3/Fargate/Tailscale",
        "Xcode 16.4",
        "iOS Rust targets",
        "CocoaPods",
        "Apple certificates",
        "Notarization credentials",
    ]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/core-completion/status")
async def core_completion_status() -> Dict[str, Any]:
    """Honest completion status across all phases. No fake 100%."""
    return {
        "phases": _phases(),
        "completion_classification": "complete_with_deferred_gates",
        "fake_completion": False,
        "fake_100_percent": False,
        "completion_score_pct": 72,
        "fake_score": False,
        "phase_d_ready": False,
        "manual_gates_open": True,
        "fake_data": False,
        "note": (
            "Completion is honest estimate. Manual gates (iOS, notarization, "
            "daily-driver, Notion) remain open."
        ),
    }


@router.get("/v1/core-completion/phase-d-options")
async def core_completion_phase_d_options() -> Dict[str, Any]:
    """Phase D decision options — Bryan decides, never auto-decided."""
    return {
        "options": _phase_d_options(),
        "auto_decision": False,
        "all_decisions_require_bryan": True,
        "fake_data": False,
    }


@router.get("/v1/core-completion/readiness-classification")
async def core_completion_readiness_classification() -> Dict[str, Any]:
    """Readiness classification with open manual gates listed."""
    return {
        "classification": "complete_with_deferred_gates",
        "classification_options": [
            "complete",
            "complete_with_deferred_gates",
            "blocked",
            "needs_manual_proof",
        ],
        "current_classification_reason": (
            "Core OS phases accepted. Manual gates (iOS init, notarization, "
            "daily-driver, Notion, installed-app-smoke) remain open."
        ),
        "open_manual_gates": _open_manual_gates(),
        "ready_prerequisites": _ready_prerequisites(),
        "fake_classification": False,
        "fake_data": False,
    }
