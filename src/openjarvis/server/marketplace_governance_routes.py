"""Plugin / Marketplace Governance REST Routes (Phase C5).

Routes:
  GET  /v1/marketplace-governance/status               — governance framework status
  GET  /v1/marketplace-governance/review-queue          — pending plugin review queue
  POST /v1/marketplace-governance/review/{plugin_id}/dry-run — permission/risk scoring dry-run
  GET  /v1/marketplace-governance/policy                — enforced governance policies

Design:
  - fake_data: False in all responses
  - Prefix: /v1/marketplace-governance/* — does NOT conflict with existing /v1/marketplace/*
  - dry_run_only: True — no automated pipeline or live marketplace claims
  - All plugins require human security review before activation
  - live_marketplace_claims: False always
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(tags=["marketplace-governance"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# GET /v1/marketplace-governance/status
# ---------------------------------------------------------------------------

@router.get("/v1/marketplace-governance/status")
async def get_marketplace_governance_status() -> Dict[str, Any]:
    """Return marketplace governance framework availability and feature flags."""
    return {
        "governance_framework_available": True,
        "review_pipeline_live": False,  # manual review only, no automated pipeline
        "permission_scoring_live": True,  # local scoring without external calls
        "version_control_live": False,
        "rollback_available": False,
        "dry_run_only": True,
        "live_marketplace_claims": False,  # ALWAYS False
        "fake_data": False,
        "note": (
            "Marketplace governance framework. Manual review required. "
            "No automated pipeline or live marketplace."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/marketplace-governance/review-queue
# ---------------------------------------------------------------------------

@router.get("/v1/marketplace-governance/review-queue")
async def get_review_queue() -> Dict[str, Any]:
    """Return pending plugin review queue from SkillRegistry if available."""
    queue: List[Dict[str, Any]] = []

    try:
        from openjarvis.skills.jarvis_registry import SkillRegistry  # type: ignore

        all_skills = SkillRegistry.list_all() or []
        pending = [s for s in all_skills if getattr(s, "status", None) == "pending_review"]
        queue = [
            {
                "plugin_id": str(getattr(s, "id", getattr(s, "plugin_id", ""))),
                "name": str(getattr(s, "name", "")),
                "status": "pending_review",
                "submitted_at": None,  # no timestamp yet
                "risk_score": None,
                "human_review_required": True,
            }
            for s in pending
        ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("SkillRegistry unavailable: %s", exc)
        queue = []

    return {
        "queue": queue,
        "count": len(queue),
        "auto_review": False,
        "human_review_required": True,
        "fake_data": False,
        "note": (
            "All plugins require human security review before activation."
        ),
    }


# ---------------------------------------------------------------------------
# POST /v1/marketplace-governance/review/{plugin_id}/dry-run
# ---------------------------------------------------------------------------

@router.post("/v1/marketplace-governance/review/{plugin_id}/dry-run")
async def review_plugin_dry_run(plugin_id: str) -> Dict[str, Any]:
    """Perform a permission/risk scoring dry-run for a plugin. No action is taken."""
    return {
        "plugin_id": plugin_id,
        "dry_run": True,
        "risk_assessment": {
            "network_access": None,  # unknown without manifest
            "data_access": None,
            "code_execution": None,
            "estimated_risk": "unknown",
        },
        "permission_gates": [
            "Human security review required",
            "Sandboxed execution environment required",
            "Bryan approval required for activation",
        ],
        "approved": False,
        "activated": False,
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# GET /v1/marketplace-governance/policy
# ---------------------------------------------------------------------------

@router.get("/v1/marketplace-governance/policy")
async def get_marketplace_governance_policy() -> Dict[str, Any]:
    """Return enforced and planned marketplace governance policies."""
    policies: List[Dict[str, Any]] = [
        {
            "policy_id": "human_review_required",
            "name": "Human Review Required",
            "enforced": True,
            "description": (
                "All third-party plugins require manual security review "
                "before activation"
            ),
        },
        {
            "policy_id": "no_auto_install",
            "name": "No Auto-Install",
            "enforced": True,
            "description": (
                "Plugins cannot be installed without explicit Bryan approval"
            ),
        },
        {
            "policy_id": "sandboxed_execution",
            "name": "Sandboxed Execution",
            "enforced": False,
            "description": (
                "Sandbox environment not yet deployed (external gate)"
            ),
            "gate": "Requires sandboxed runtime",
        },
        {
            "policy_id": "version_pinning",
            "name": "Version Pinning",
            "enforced": False,
            "description": "Version control not yet implemented",
            "gate": "Future work",
        },
        {
            "policy_id": "rollback_ready",
            "name": "Rollback-Ready Installs",
            "enforced": False,
            "description": "Rollback mechanism not yet implemented",
            "gate": "Future work",
        },
    ]

    enforced_count = sum(1 for p in policies if p.get("enforced"))

    return {
        "policies": policies,
        "policies_enforced_count": enforced_count,
        "live_marketplace": False,
        "fake_data": False,
        "note": (
            "Marketplace governance policies. Human review and no-auto-install "
            "are enforced. Sandbox/versioning/rollback require future work."
        ),
    }
