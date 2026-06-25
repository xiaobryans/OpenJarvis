"""REST endpoints for Autonomous Jarvis Organization Kernel — Phase C1.

Routes:
  GET  /v1/autonomous-org/status             — org kernel status + internal team registry
  GET  /v1/autonomous-org/capability-matrix  — capability availability matrix
  GET  /v1/autonomous-org/mission-routing    — role-to-mission-type routing table
  POST /v1/autonomous-org/route-query        — dry-run role recommendation for a query

Governance:
  - One Jarvis PA voice enforced at all times
  - No autonomous external execution without approval
  - No external personalities
  - fake_data: False in all responses
  - route-query is dry-run only — nothing is executed
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for autonomous_org_routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["autonomous-org"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# Internal team registry (static Phase C1 definition)
# ---------------------------------------------------------------------------

_INTERNAL_TEAM = [
    {
        "role_id": "planner",
        "name": "Mission Planner",
        "type": "internal",
        "live": True,
        "approval_gated": True,
    },
    {
        "role_id": "reviewer",
        "name": "Quality Reviewer",
        "type": "internal",
        "live": True,
        "approval_gated": True,
    },
    {
        "role_id": "executor",
        "name": "Task Executor",
        "type": "internal",
        "live": False,
        "approval_gated": True,
        "gate": "Execution requires Tier 3+ approval",
    },
    {
        "role_id": "researcher",
        "name": "Research Agent",
        "type": "internal",
        "live": False,
        "approval_gated": True,
        "gate": "External research requires connector credentials",
    },
    {
        "role_id": "auditor",
        "name": "Audit Agent",
        "type": "internal",
        "live": True,
        "approval_gated": False,
    },
    {
        "role_id": "coordinator",
        "name": "Coordinator",
        "type": "internal",
        "live": True,
        "approval_gated": True,
    },
]

_CAPABILITY_MATRIX = [
    {
        "capability_id": "mission_planning",
        "name": "Mission Planning",
        "available": True,
        "requires_approval": True,
        "live": True,
    },
    {
        "capability_id": "quality_review",
        "name": "Quality Review",
        "available": True,
        "requires_approval": True,
        "live": True,
    },
    {
        "capability_id": "task_execution",
        "name": "Task Execution",
        "available": False,
        "requires_approval": True,
        "live": False,
        "gate": "Tier 3+ approval + connector credentials",
    },
    {
        "capability_id": "research",
        "name": "Research / Web Retrieval",
        "available": False,
        "requires_approval": True,
        "live": False,
        "gate": "Search connector credentials required",
    },
    {
        "capability_id": "audit",
        "name": "Internal Audit",
        "available": True,
        "requires_approval": False,
        "live": True,
    },
    {
        "capability_id": "coordination",
        "name": "Cross-role Coordination",
        "available": True,
        "requires_approval": True,
        "live": True,
    },
    {
        "capability_id": "decision_record",
        "name": "Decision Records",
        "available": True,
        "requires_approval": False,
        "live": True,
    },
    {
        "capability_id": "external_execution",
        "name": "External Autonomous Execution",
        "available": False,
        "requires_approval": True,
        "live": False,
        "gate": "Permanently requires Tier 4 approval + human oversight",
    },
]

_ROUTING_TABLE = [
    {"mission_type": "research", "assigned_role": "researcher", "approval_required": True, "live": False},
    {"mission_type": "planning", "assigned_role": "planner", "approval_required": True, "live": True},
    {"mission_type": "review", "assigned_role": "reviewer", "approval_required": True, "live": True},
    {
        "mission_type": "execution",
        "assigned_role": "executor",
        "approval_required": True,
        "live": False,
        "gate": "Tier 3+",
    },
    {"mission_type": "audit", "assigned_role": "auditor", "approval_required": False, "live": True},
    {"mission_type": "coordination", "assigned_role": "coordinator", "approval_required": True, "live": True},
]


def _count_active_roles() -> int:
    """Count internal team members where live=True."""
    return sum(1 for r in _INTERNAL_TEAM if r.get("live", False))


def _keyword_route(query: str) -> tuple[str, str]:
    """Return (role_id, reasoning) based on simple keyword matching."""
    q = query.lower()
    if "research" in q or "search" in q or "look up" in q or "find" in q:
        return "researcher", "Query contains research/search keywords; routed to Research Agent."
    if "review" in q or "check" in q or "evaluate" in q or "assess" in q:
        return "reviewer", "Query contains review/evaluate keywords; routed to Quality Reviewer."
    if "plan" in q or "goal" in q or "mission" in q or "strateg" in q:
        return "planner", "Query contains planning/mission keywords; routed to Mission Planner."
    if "audit" in q or "log" in q or "record" in q or "history" in q:
        return "auditor", "Query contains audit/log keywords; routed to Audit Agent."
    return "coordinator", "No specific keyword match; defaulting to Coordinator for triage."


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RouteQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The query to route (non-empty)")
    context: str = Field("", description="Optional additional context")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/autonomous-org/status")
async def autonomous_org_status() -> Dict[str, Any]:
    """Return the Autonomous Org Kernel status and internal team registry."""
    try:
        active_roles = _count_active_roles()
        return {
            "org_kernel_available": True,
            "one_jarvis_pa_identity": True,
            "single_pa_voice": "Jarvis",
            "internal_team": _INTERNAL_TEAM,
            "active_roles": active_roles,
            "autonomous_execution_live": False,
            "external_personality": False,
            "omnix_is_jarvis_core": False,
            "fake_ai_company_running": False,
            "fake_data": False,
            "note": (
                "Autonomous Org Kernel. Internal team registry only. "
                "One Jarvis PA voice. No autonomous external execution without approval."
            ),
        }
    except Exception as exc:
        logger.exception("autonomous_org_status error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/v1/autonomous-org/capability-matrix")
async def autonomous_org_capability_matrix() -> Dict[str, Any]:
    """Return the Phase C1 capability availability matrix."""
    try:
        return {
            "capabilities": _CAPABILITY_MATRIX,
            "one_jarvis_pa_identity": True,
            "external_personalities_live": False,
            "fake_data": False,
            "note": "Phase C1 capability matrix. External execution always requires approval.",
        }
    except Exception as exc:
        logger.exception("autonomous_org_capability_matrix error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/v1/autonomous-org/mission-routing")
async def autonomous_org_mission_routing() -> Dict[str, Any]:
    """Return the mission-type to internal role routing table."""
    try:
        return {
            "routing_table": _ROUTING_TABLE,
            "one_pa_voice": True,
            "fake_routing": False,
            "fake_data": False,
        }
    except Exception as exc:
        logger.exception("autonomous_org_mission_routing error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/v1/autonomous-org/route-query")
async def autonomous_org_route_query(body: RouteQueryRequest) -> Dict[str, Any]:
    """Dry-run: recommend which internal role would handle a given query. No execution."""
    try:
        # Truncate query echo — never reflect raw unbounded input
        query_echo = body.query[:200]

        recommended_role, reasoning = _keyword_route(body.query)

        return {
            "query": query_echo,
            "dry_run": True,
            "recommended_role": recommended_role,
            "reasoning": reasoning,
            "approval_required": True,
            "executed": False,
            "one_pa_voice": "Jarvis",
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("autonomous_org_route_query error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")
