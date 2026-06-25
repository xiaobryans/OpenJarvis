"""Skills Expansion Routes — catalog summary, permissions matrix, dry-run intake.

Routes:
  GET  /v1/skills/catalog/summary   — summary counts from SkillRegistry
  GET  /v1/skills/permissions       — per-skill permission/risk matrix
  POST /v1/skills/intake/dry-run    — validate manifest without installing
  GET  /v1/skills/intake/queue      — intake review queue (always empty; no pipeline)

Design rules:
  - fake_data: False in all responses
  - automation_honesty: True where applicable
  - No secret reading, no credential access, no live external calls
  - Skills are never auto-installed; approval always required
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for skills_expansion_routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["skills-expansion"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_SAFETY_LEVELS = ("low", "medium", "high", "critical")


def _load_skill_catalog():
    """Initialize catalogs and return (SkillRegistry, error_note).

    Returns (SkillRegistry class, "") on success or (None, error_note) on failure.
    """
    try:
        from openjarvis.skills.catalog import initialize_catalog as init_skill_catalog
        from openjarvis.skills.jarvis_registry import SkillRegistry

        init_skill_catalog()
        return SkillRegistry, ""
    except Exception as exc:
        logger.debug("Skill catalog load failed: %s", exc)
        return None, f"Skill catalog unavailable: {exc}"


def _approval_tier(safety_level: str) -> str:
    """Map a safety_level string to an approval tier label."""
    if safety_level == "critical":
        return "blocked"
    if safety_level == "high":
        return "tier4_approval"
    if safety_level == "medium":
        return "tier3_approval"
    return "auto"


# ---------------------------------------------------------------------------
# GET /v1/skills/catalog/summary
# ---------------------------------------------------------------------------


@router.get("/v1/skills/catalog/summary")
async def get_catalog_summary() -> Dict[str, Any]:
    """Return a summary of the skill catalog counts by status.

    Reads live from SkillRegistry. Reports zeros if registry unavailable.
    """
    registry, error_note = _load_skill_catalog()

    if registry is None:
        return {
            "total": 0,
            "available": 0,
            "blocked": 0,
            "disabled": 0,
            "not_configured": 0,
            "planned": 0,
            "has_intake_queue": False,
            "intake_queue_size": 0,
            "marketplace_live": False,
            "fake_data": False,
            "automation_honesty": True,
            "note": (
                "Skill catalog from local SkillRegistry. "
                "Third-party marketplace integration requires external gate review. "
                f"Error: {error_note}"
            ),
        }

    skills = registry.list_all()
    skill_dicts = [s.to_dict() for s in skills]

    counts: Dict[str, int] = {}
    for s in skill_dicts:
        st = s.get("status", "unknown")
        counts[st] = counts.get(st, 0) + 1

    return {
        "total": len(skill_dicts),
        "available": counts.get("available", 0),
        "blocked": counts.get("blocked", 0),
        "disabled": counts.get("disabled", 0),
        "not_configured": counts.get("not_configured", 0),
        "planned": counts.get("planned", 0),
        "has_intake_queue": False,
        "intake_queue_size": 0,
        "marketplace_live": False,
        "fake_data": False,
        "automation_honesty": True,
        "note": (
            "Skill catalog from local SkillRegistry. "
            "Third-party marketplace integration requires external gate review."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/skills/permissions
# ---------------------------------------------------------------------------


@router.get("/v1/skills/permissions")
async def get_skill_permissions() -> Dict[str, Any]:
    """Return a permission/risk matrix for all registered skills.

    Computes approval_required, network_access, data_access, and
    approval_tier for each skill based on live registry data.
    """
    registry, error_note = _load_skill_catalog()

    if registry is None:
        return {
            "skills": [],
            "count": 0,
            "permission_gates_active": True,
            "fake_data": False,
            "note": error_note,
        }

    skills = registry.list_all()
    rows: List[Dict[str, Any]] = []

    for skill in skills:
        d = skill.to_dict()
        skill_id: str = d.get("skill_id", "")
        # SkillSpec uses risk_level; tolerate a safety_level alias if present
        safety_level: str = d.get("risk_level", d.get("safety_level", "low"))
        tags: List[str] = d.get("tags", [])

        rows.append({
            "skill_id": skill_id,
            "name": d.get("display_name", skill_id),
            "safety_level": safety_level,
            "requires_approval": safety_level in ("high", "critical"),
            "network_access": "connector" in skill_id or "network" in tags,
            "data_access": "memory" in skill_id or "data" in tags,
            "approval_tier": _approval_tier(safety_level),
        })

    return {
        "skills": rows,
        "count": len(rows),
        "permission_gates_active": True,
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# POST /v1/skills/intake/dry-run
# ---------------------------------------------------------------------------


class DryRunManifestRequest(BaseModel):
    manifest: Dict[str, Any] = Field(..., description="Skill manifest to dry-run validate")


@router.post("/v1/skills/intake/dry-run")
async def dry_run_intake(body: DryRunManifestRequest) -> Dict[str, Any]:
    """Validate a skill manifest without installing it.

    Checks required fields and safety_level. Never installs or activates.
    Activation always requires explicit reviewer approval.
    """
    manifest = body.manifest
    errors: List[str] = []
    warnings: List[str] = []

    name: str = manifest.get("name", "")
    description: str = manifest.get("description", "")
    safety_level: str = manifest.get("safety_level", "")
    actions = manifest.get("actions", [])

    if not name:
        errors.append("manifest.name is required and must be non-empty")
    if not description:
        errors.append("manifest.description is required and must be non-empty")
    if not safety_level:
        errors.append(
            f"manifest.safety_level is required; must be one of {_VALID_SAFETY_LEVELS}"
        )
    elif safety_level not in _VALID_SAFETY_LEVELS:
        errors.append(
            f"manifest.safety_level '{safety_level}' is not valid; "
            f"must be one of {_VALID_SAFETY_LEVELS}"
        )

    if not isinstance(actions, list):
        errors.append("manifest.actions must be a list")
    elif len(actions) == 0:
        warnings.append("manifest.actions is empty; skill will have no callable actions")

    if safety_level in ("high", "critical"):
        warnings.append(
            f"safety_level '{safety_level}' requires Tier 4 approval before activation"
        )

    valid = len(errors) == 0

    return {
        "dry_run": True,
        "valid": valid,
        "errors": errors,
        "warnings": warnings,
        "safety_level": safety_level or "unknown",
        "approval_required": safety_level in ("high", "critical"),
        "would_install": False,
        "approval_gate": "tier3_approval_required",
        "fake_data": False,
    }


# ---------------------------------------------------------------------------
# GET /v1/skills/intake/queue
# ---------------------------------------------------------------------------


@router.get("/v1/skills/intake/queue")
async def get_intake_queue() -> Dict[str, Any]:
    """Return the intake review queue.

    Currently always empty — no automated third-party skill intake pipeline.
    Manual review is required for all third-party skill submissions.
    """
    return {
        "queue": [],
        "count": 0,
        "intake_automated": False,
        "review_required": True,
        "fake_data": False,
        "note": (
            "Manual intake review required. "
            "No automated third-party skill intake pipeline active."
        ),
    }


__all__ = ["router"]
