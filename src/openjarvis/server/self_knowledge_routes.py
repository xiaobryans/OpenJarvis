"""Self-Knowledge Routes — Jarvis capability awareness and status endpoints.

Routes:
  GET /v1/jarvis/capabilities  — what can Jarvis do right now?
  GET /v1/jarvis/status        — current Jarvis system status
  GET /v1/jarvis/roadmap       — current roadmap and plan state

Design rules:
  - No secret values.
  - Honest partial/blocked state reporting — no fake AVAILABLE.
  - Plan 3 voice/TTS explicitly reported as PARKED.
  - Returns human-readable descriptions for "what can you do?" queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi required for self-knowledge routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jarvis-self-knowledge"])


# ---------------------------------------------------------------------------
# Static capability manifest
# ---------------------------------------------------------------------------

_CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "chat",
        "name": "Text-first intelligent chat",
        "status": "available",
        "description": "Answer questions, plan tasks, write code, research topics, and assist with decisions in a unified text conversation.",
        "plan": "Plan 1",
    },
    {
        "id": "memory",
        "name": "Unified memory search",
        "status": "available",
        "description": "Remember context from prior sessions; search and retrieve from memory namespaces.",
        "plan": "Plan 1",
    },
    {
        "id": "cloud_routing",
        "name": "Cloud-first routing",
        "status": "available",
        "description": "Routes requests to Fargate workers for long-running or compute-intensive tasks.",
        "plan": "Plan 1",
    },
    {
        "id": "connectors",
        "name": "Connector integrations",
        "status": "partial",
        "description": "GitHub, Slack, Telegram, Notion, Google OAuth connectors. Cloud env tokens needed for full Fargate deployment.",
        "plan": "Plan 2",
        "blocker": "Fargate env vars not yet deployed for all connectors",
    },
    {
        "id": "mobile_parity",
        "name": "Mobile/MacBook-off parity",
        "status": "available",
        "description": "Core parity endpoints available for mobile access. PWA manifest present.",
        "plan": "Plan 2",
    },
    {
        "id": "approval_gates",
        "name": "Approval and delegation gates",
        "status": "available",
        "description": "Six-tier authority model. Actions require explicit approval at Tier 3+. Emergency stop supported.",
        "plan": "Plan 2 / Plan 8",
    },
    {
        "id": "skills",
        "name": "Skill registry",
        "status": "available",
        "description": "Skill discovery, cataloging, enable/disable, and third-party skill intake with vetting.",
        "plan": "Plan 1 / Plan 4",
    },
    {
        "id": "rules",
        "name": "Rules engine",
        "status": "available",
        "description": "User-defined and system rules governing Jarvis behavior. CRUD, conflict detection, scope-aware evaluation.",
        "plan": "Plan 4",
    },
    {
        "id": "life_os",
        "name": "Life-Business OS",
        "status": "available",
        "description": "Personal tasks, goals, reminders, daily summaries, approval workflow.",
        "plan": "Plan 4-5",
    },
    {
        "id": "expert_roles",
        "name": "Expert role orchestration",
        "status": "available",
        "description": "Internal expert roles (coding, product, research, security, etc.) selected behind the scenes. Single Jarvis PA voice.",
        "plan": "Plan 6",
    },
    {
        "id": "doctor",
        "name": "Self-diagnostic doctor",
        "status": "available",
        "description": "19 health checks across all system categories. Readiness report with PASS/WARN/FAIL per category.",
        "plan": "Plan 1",
    },
    {
        "id": "automation_policy",
        "name": "Automation ladder",
        "status": "available",
        "description": "7-level automation policy with hard gates. 14 action classes always blocked. Standing approval.",
        "plan": "Post-Plan-2",
    },
    {
        "id": "voice_tts",
        "name": "Voice / Wake / TTS",
        "status": "parked",
        "description": "Voice, wake-word, and TTS capabilities are PARKED until Jarvis is text-first stable. Not implemented.",
        "plan": "Plan 3 — PARKED",
        "blocker": "Plan 3 explicitly parked by Bryan. Text-first priority.",
    },
    {
        "id": "ios_native",
        "name": "Native iOS / Productization",
        "status": "partial",
        "description": (
            "PWA fully implemented (Plan 2). Tauri desktop scaffold present at frontend/src-tauri/ "
            "(macOS/Windows/Linux only). Native iOS target not yet initialized — requires "
            "'tauri ios init' and Apple Developer Account enrollment (external gate). "
            "See GET /v1/productization/status for full breakdown."
        ),
        "plan": "Plan 4-5",
        "external_gate": "Apple Developer Account enrollment",
    },
    {
        "id": "expert_role_wiring",
        "name": "Expert role routing in Jarvis PA",
        "status": "available",
        "description": "RoleSelector is wired into the frontdoor submit path. Expert roles are selected internally behind one Jarvis PA voice.",
        "plan": "Plan 4-6",
    },
    {
        "id": "delegation_queue",
        "name": "Life-Business OS delegation queue",
        "status": "available",
        "description": (
            "Unified delegation/approval queue aggregating life-os tasks, agent actions, "
            "and mission tasks pending approval. Approve/reject through existing gated routes. "
            "See GET /v1/delegation/queue."
        ),
        "plan": "Plan 4-5",
    },
    {
        "id": "system_status",
        "name": "Unified system / connector status",
        "status": "available",
        "description": (
            "Presence-only status for all connectors (Gmail, Calendar, Drive, Slack, Telegram, "
            "Notion, GitHub, S3) and system components (Fargate, mobile/PWA/iOS, skills/rules, "
            "expert roles). See GET /v1/system/status."
        ),
        "plan": "Plan 4-6",
    },
]

_ROADMAP: List[Dict[str, Any]] = [
    {"plan": "Plan 1", "name": "Dual-Platform Jarvis Neural Command Center", "status": "ACCEPTED"},
    {"plan": "Plan 2", "name": "Full Mobile MacBook-Off Parity Runtime", "status": "ACCEPTED"},
    {"plan": "Post-Plan-2", "name": "Claude Code Automation Expansion", "status": "ACCEPTED"},
    {"plan": "Plan 3", "name": "Voice / Wake / TTS", "status": "PARKED — text-first priority"},
    {"plan": "Plan 4-6", "name": "Text-First Jarvis OS Mega-Sprint", "status": "IN_PROGRESS"},
    {"plan": "Plan 4-6 B3/B5/B6", "name": "iOS/Productization + UI Surfaces + RoleSelector Wiring", "status": "ACCEPTED"},
    {"plan": "Plan 4-6 B7", "name": "Delegation Queue UI + Connector Status Polish", "status": "ACCEPTED"},
    {"plan": "Plan 4", "name": "Skills / Rules / Third-Party Skill Intake", "status": "COMPLETE"},
    {"plan": "Plan 5", "name": "Life-Business OS + Trusted Delegation + iOS", "status": "IN_PROGRESS"},
    {"plan": "Plan 6", "name": "Chat Intelligence + Expert Roles + UI/UX Polish", "status": "IN_PROGRESS"},
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/jarvis/capabilities")
async def get_capabilities(status: str = "") -> Dict[str, Any]:
    """Return what Jarvis can do right now.

    Honest partial/blocked/parked reporting — no fake AVAILABLE claims.
    """
    caps = _CAPABILITIES
    if status:
        caps = [c for c in caps if c.get("status") == status]
    available = [c for c in _CAPABILITIES if c.get("status") == "available"]
    partial = [c for c in _CAPABILITIES if c.get("status") == "partial"]
    parked = [c for c in _CAPABILITIES if c.get("status") == "parked"]
    not_started = [c for c in _CAPABILITIES if c.get("status") == "not_started"]
    return {
        "capabilities": caps,
        "summary": {
            "total": len(_CAPABILITIES),
            "available": len(available),
            "partial": len(partial),
            "parked": len(parked),
            "not_started": len(not_started),
        },
        "identity": "Jarvis — one unified PA voice",
        "text_first": True,
        "voice_status": "PARKED",
    }


@router.get("/v1/jarvis/status")
async def get_jarvis_status() -> Dict[str, Any]:
    """Current Jarvis system status snapshot."""
    available_count = sum(1 for c in _CAPABILITIES if c.get("status") == "available")
    total_count = len(_CAPABILITIES)
    return {
        "name": "Jarvis",
        "identity": "One unified PA voice — text-first",
        "plan_state": {
            "plan_1": "ACCEPTED",
            "plan_2": "ACCEPTED",
            "post_plan2_automation": "ACCEPTED",
            "plan_3_voice": "PARKED",
            "plan_4_6_mega_sprint": "IN_PROGRESS",
        },
        "capability_summary": {
            "available": available_count,
            "total": total_count,
        },
        "text_first": True,
        "voice_parked": True,
        "mobile_parity": "available",
        "approval_gates": "active",
        "fake_claims": False,
    }


@router.get("/v1/jarvis/roadmap")
async def get_roadmap() -> Dict[str, Any]:
    """Current Jarvis roadmap and plan acceptance state."""
    return {
        "roadmap": _ROADMAP,
        "active_sprint": "PLAN_4_6_MEGA_SPRINT_TEXT_FIRST_JARVIS_OS",
        "next": "Complete Plan 4-6 pillars, then Plan 3 voice when Bryan reopens it.",
        "note": "Only Bryan can mark plans as ACCEPTED.",
    }


__all__ = ["router"]
