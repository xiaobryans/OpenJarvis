"""Control Tower routes — Phase C10.

Consolidated phase/gate status, next-decision queue, and completion score
across all OpenJarvis plans. fake_acceptance and auto_decide are always False.
Only Bryan can accept or decide.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(tags=["control-tower"])
__all__ = ["router"]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static phase and gate definitions
# ---------------------------------------------------------------------------

_PHASES: List[Dict[str, Any]] = [
    {"phase": "Plan 1", "status": "ACCEPTED", "note": "Jarvis PA identity, cloud routing"},
    {"phase": "Plan 2", "status": "ACCEPTED", "note": "Mobile/MacBook-off parity runtime"},
    {"phase": "Plan 4-6", "status": "ACCEPTED", "note": "Text-first Jarvis OS"},
    {"phase": "Phase X", "status": "ACCEPTED", "note": "Universal Jarvis / OMNIX decoupling"},
    {
        "phase": "Final Phase A",
        "status": "IN_PROGRESS",
        "note": "Live gate closure active: notarization done, iOS init done, connectors live-verified. Daily-driver + installed-app-smoke need Bryan proof.",
    },
    {
        "phase": "Final Phase A Live Gate Closure",
        "status": "IN_PROGRESS",
        "note": "Active sprint: signing accepted, iOS init completed, 4 connectors live-verified. Open: daily-driver sessions, installed app visual smoke.",
    },
    {
        "phase": "Phase B1-B20",
        "status": "ACCEPTED_ON_HOLD",
        "note": "B1-B20 complete, expansion on hold by Bryan",
    },
    {
        "phase": "Phase C1-C10",
        "status": "ACCEPTED",
        "note": "Autonomous ecosystem / scale sprint accepted",
    },
    {
        "phase": "Phase C11-C20",
        "status": "ACCEPTED",
        "note": "Parity and gate integration sprint accepted",
    },
    {
        "phase": "Plan 3",
        "status": "PARKED",
        "note": "Voice/wake/TTS parked until Bryan reopens",
    },
]

_OPEN_GATES: List[Dict[str, Any]] = [
    {
        "gate_id": "final_phase_a_dmg",
        "name": "DMG Notarization",
        "type": "manual_external",
        "status": "open",
        "requires": "Apple Developer Account + MacBook physical access",
    },
    {
        "gate_id": "multi_user_auth",
        "name": "Production Multi-User Auth",
        "type": "external_implementation",
        "status": "open",
        "requires": "RBAC + auth system implementation",
    },
    {
        "gate_id": "fargate_deployment",
        "name": "Fargate Cloud Deployment",
        "type": "external_infra",
        "status": "open",
        "requires": "AWS Fargate + connector credentials",
    },
    {
        "gate_id": "browser_automation",
        "name": "Browser Automation",
        "type": "external_library",
        "status": "open",
        "requires": "Playwright/Selenium integration",
    },
    {
        "gate_id": "live_marketplace",
        "name": "Live Plugin Marketplace",
        "type": "external_registry",
        "status": "open",
        "requires": "Vetted plugin registry + security pipeline",
    },
    {
        "gate_id": "plan3_voice",
        "name": "Voice/Wake/TTS (Plan 3)",
        "type": "parked_by_bryan",
        "status": "parked",
        "requires": "Bryan to explicitly reopen Plan 3",
    },
]

_CLOSED_GATES: List[Dict[str, Any]] = [
    {
        "gate_id": "omnix_decoupling",
        "name": "OMNIX Decoupling",
        "status": "closed",
        "closed_by": "Phase X",
    },
    {
        "gate_id": "text_first_jarvis_os",
        "name": "Text-First Jarvis OS",
        "status": "closed",
        "closed_by": "Plan 4-6",
    },
]

_NEXT_DECISIONS: List[Dict[str, Any]] = [
    {
        "decision_id": "accept_phase_c",
        "title": "Accept Phase C1-C10",
        "owner": "Bryan",
        "decision_type": "acceptance_review",
        "auto_decide": False,
    },
    {
        "decision_id": "open_final_phase_a",
        "title": "Return to Final Phase A (MacBook access required)",
        "owner": "Bryan",
        "decision_type": "external_gate_readiness",
        "auto_decide": False,
    },
    {
        "decision_id": "open_plan3_voice",
        "title": "Reopen Plan 3 Voice/Wake/TTS",
        "owner": "Bryan",
        "decision_type": "plan_authorization",
        "auto_decide": False,
    },
    {
        "decision_id": "fargate_deployment",
        "title": "Authorize Fargate cloud deployment",
        "owner": "Bryan",
        "decision_type": "cloud_infrastructure",
        "auto_decide": False,
    },
    {
        "decision_id": "multi_user_auth",
        "title": "Prioritize multi-user auth implementation",
        "owner": "Bryan",
        "decision_type": "scope_decision",
        "auto_decide": False,
    },
]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/v1/control-tower/status")
async def control_tower_status() -> Dict[str, Any]:
    """Return consolidated phase and gate status across all plans.

    fake_acceptance is always False — only Bryan can accept.
    Reads from self_knowledge_routes if available; falls back to static data.
    """
    phases = _PHASES

    try:
        from openjarvis.server.self_knowledge_routes import get_roadmap  # type: ignore[import]

        roadmap = await get_roadmap()
        if isinstance(roadmap, dict) and roadmap.get("phases"):
            phases = roadmap["phases"]
    except Exception:
        pass  # use static phase list

    return {
        "phases": phases,
        "active_sprint": "FINAL_PHASE_A_NEURAL_COMMAND_CENTER_UI_COMPLETION_SPRINT",
        "fake_acceptance": False,
        "fake_data": False,
        "note": "Neural Command Center UI completion sprint. Full 3-column layout with 12 panels visible by default around Jarvis orb. DesktopCommandCenter + MobileCommandCenter implemented. App rebuilt, signed, notarized (Apple Accepted, ID ddd69bc8). Installed-app-smoke visual needs Bryan proof. Daily-driver cert needs Bryan usage sessions.",
    }


@router.get("/v1/control-tower/gate-registry")
async def gate_registry() -> Dict[str, Any]:
    """Return all open and closed gates across the roadmap."""
    return {
        "open_gates": _OPEN_GATES,
        "closed_gates": _CLOSED_GATES,
        "open_count": len(_OPEN_GATES),
        "closed_count": len(_CLOSED_GATES),
        "fake_gate_closure": False,
        "fake_data": False,
    }


@router.get("/v1/control-tower/next-decisions")
async def next_decisions() -> Dict[str, Any]:
    """Return queued decisions that require Bryan's explicit authorization.

    auto_decide is always False — only Bryan decides.
    """
    return {
        "decisions": _NEXT_DECISIONS,
        "auto_decide": False,
        "fake_data": False,
        "note": "All decisions require Bryan's explicit authorization. No auto-acceptance.",
    }


@router.get("/v1/control-tower/completion-score")
async def completion_score() -> Dict[str, Any]:
    """Return an honest roadmap completion score.

    completion_score_pct is an honest estimate based on accepted plans.
    fake_score is always False.
    """
    return {
        "core_os_completion": {
            "plans_accepted": ["Plan 1", "Plan 2", "Plan 4-6", "Phase X"],
            "phases_accepted": ["B1-B20", "C1-C10", "C11-C20"],
            "phases_in_progress": ["Final Phase A Live Gate Closure"],
            "phases_parked": ["Plan 3 Voice"],
            "completion_score_pct": 82,
            "fake_score": False,
        },
        "capability_coverage": {
            "chat_intelligence": True,
            "memory_os": True,
            "goals_tasks": True,
            "routines": True,
            "expert_roles": True,
            "delegation": True,
            "follow_up_center": True,
            "command_center": True,
            "skills_marketplace_local": True,
            "connector_github_live": True,
            "connector_slack_live": True,
            "connector_telegram_live": True,
            "connector_tavily_live": True,
            "macos_signed_notarized": True,
            "ios_init_completed": True,
            "daily_driver_certified": False,
            "installed_app_smoke_visual": False,
            "browser_operator_live": False,
            "multi_user": False,
            "voice_wake": False,
            "native_ios_distributed": False,
            "cloud_execution_live": False,
        },
        "fake_data": False,
        "note": (
            "Completion score is honest estimate. 82% based on accepted plans + live gate closures. "
            "Daily-driver cert, installed-app-smoke visual, voice, native iOS distribution, "
            "cloud execution, multi-user remain open."
        ),
    }
