"""Plugin Marketplace REST Routes (B18).

Routes:
  GET  /v1/marketplace/status          — marketplace availability + local registry stats
  GET  /v1/marketplace/plugins         — list all locally registered skills/plugins
  POST /v1/marketplace/plugins/review  — dry-run review action (approve/reject)
  GET  /v1/marketplace/review-queue    — pending manual review queue

Design:
  - fake_data: False, fake_marketplace: False in all responses
  - No live third-party marketplace — local SkillRegistry only
  - Plugin review is dry-run; never auto-installs or executes anything
  - Human security vetting required before any plugin activation
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Literal, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for marketplace routes")

logger = logging.getLogger(__name__)
router = APIRouter(tags=["marketplace"])

__all__ = ["router"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_local_skill_count() -> int:
    """Return count of locally registered skills; 0 on any failure."""
    try:
        from openjarvis.skills.jarvis_registry import SkillRegistry  # type: ignore

        return len(SkillRegistry.list_all())
    except Exception as exc:  # noqa: BLE001
        logger.warning("marketplace: could not read SkillRegistry: %s", exc)
        return 0


def _get_all_plugins() -> List[Dict[str, Any]]:
    """Return all locally registered skills as plugin dicts; empty list on failure."""
    try:
        from openjarvis.skills.jarvis_registry import SkillRegistry  # type: ignore

        skills = SkillRegistry.list_all()
        return [
            {
                "plugin_id": skill.skill_id,
                "name": getattr(skill, "name", skill.skill_id),
                "version": "local",  # No versioning
                "status": getattr(skill, "status", "unknown"),
                "safety_level": getattr(skill, "risk_level", None) or "unknown",
                "source": "local_registry",
                "marketplace_verified": False,
                "auto_installed": False,
            }
            for skill in skills
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning("marketplace: could not list plugins: %s", exc)
        return []


# ---------------------------------------------------------------------------
# GET /v1/marketplace/status
# ---------------------------------------------------------------------------


@router.get("/v1/marketplace/status")
async def marketplace_status() -> Dict[str, Any]:
    """Return marketplace availability and local registry stats."""
    local_skill_count = _get_local_skill_count()
    return {
        "marketplace_live": False,  # No live marketplace
        "local_registry_available": True,  # SkillRegistry exists locally
        "local_skill_count": local_skill_count,
        "review_queue_size": 0,
        "auto_install": False,
        "network_install": False,
        "version_control": False,  # No versioning yet
        "rollback_available": False,
        "external_gate": (
            "Live marketplace integration requires vetted plugin registry "
            "and security review pipeline."
        ),
        "fake_data": False,
        "fake_marketplace": False,
        "note": (
            "Marketplace is local-registry-only. No live third-party marketplace. "
            "Plugin review requires manual security vetting."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/marketplace/plugins
# ---------------------------------------------------------------------------


@router.get("/v1/marketplace/plugins")
async def list_plugins() -> Dict[str, Any]:
    """Return all locally registered skills/plugins from SkillRegistry."""
    plugins = _get_all_plugins()
    return {
        "plugins": plugins,
        "count": len(plugins),
        "marketplace_live": False,
        "fake_marketplace": False,
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# POST /v1/marketplace/plugins/review
# ---------------------------------------------------------------------------


class PluginReviewRequest(BaseModel):
    plugin_id: str = Field(..., description="ID of the plugin to review")
    action: str = Field(..., description="'approve' or 'reject'")
    reason: str = Field("", description="Reason for the review action")


@router.post("/v1/marketplace/plugins/review")
async def review_plugin(body: PluginReviewRequest) -> Dict[str, Any]:
    """Dry-run plugin review — records intent only, does NOT install or execute.

    Validates action is 'approve' or 'reject'; returns 422 otherwise.
    Human security review is always required before any plugin activation.
    """
    action = body.action.strip().lower()
    if action not in {"approve", "reject"}:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_action",
                "message": "action must be 'approve' or 'reject'",
                "received": body.action,
            },
        )

    return {
        "plugin_id": body.plugin_id,
        "action": action,
        "dry_run": True,
        "executed": False,
        "would_install": False,  # Never auto-install
        "approval_required": True,
        "gate": "Human security review required before any plugin activation",
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# GET /v1/marketplace/review-queue
# ---------------------------------------------------------------------------


@router.get("/v1/marketplace/review-queue")
async def review_queue() -> Dict[str, Any]:
    """Return the plugin manual review queue (currently empty — no automated intake)."""
    return {
        "queue": [],  # No automated intake yet
        "count": 0,
        "auto_review": False,
        "human_review_required": True,
        "fake_data": False,
        "note": (
            "No automated plugin review queue. "
            "Manual security vetting required for all third-party plugins."
        ),
    }
