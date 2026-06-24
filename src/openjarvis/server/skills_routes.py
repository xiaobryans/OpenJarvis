"""REST endpoints for Jarvis Skill Registry.

Routes:
  GET  /v1/skills                     — list all skills (status from ToolRegistry)
  GET  /v1/skills/{skill_id}          — get single skill spec
  POST /v1/skills/{skill_id}/enable   — enable a skill
  POST /v1/skills/{skill_id}/disable  — disable a skill
  POST /v1/skills/intake/validate     — validate a third-party skill manifest

Skill status is computed live from ToolRegistry — no cached/fake state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Set

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for skills routes")

from openjarvis.skills.catalog import initialize_catalog as init_skill_catalog
from openjarvis.skills.jarvis_registry import SkillRegistry
from openjarvis.tools.catalog import initialize_catalog as init_tool_catalog

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory override set — tracks skills explicitly disabled via API
_disabled_skills: Set[str] = set()


def _ensure_catalogs() -> None:
    init_tool_catalog()
    init_skill_catalog()


def _apply_disable_overlay(skill_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Mark skill as disabled if it's in the disable override set."""
    if skill_dict.get("skill_id") in _disabled_skills:
        skill_dict = {**skill_dict, "status": "disabled", "disabled_via_api": True}
    return skill_dict


@router.get("/v1/skills")
async def list_skills(
    agent_id: str = "",
    project_id: str = "",
    status: str = "",
) -> Dict[str, Any]:
    """List all skills with computed availability status.

    Filters:
      ?agent_id=<id>       — skills compatible with that agent
      ?project_id=<id>     — skills scoped to a project ([] = all projects)
      ?status=<status>     — available | degraded | blocked | not_configured | planned | disabled

    Status is computed live from ToolRegistry — blocked tools propagate.
    """
    _ensure_catalogs()
    if agent_id:
        skills = SkillRegistry.list_for_agent(agent_id)
    else:
        skills = SkillRegistry.list_all()
    if project_id:
        skills = [
            s for s in skills
            if not s.project_scopes or project_id in s.project_scopes
        ]
    skill_dicts = [_apply_disable_overlay(s.to_dict()) for s in skills]
    if status:
        skill_dicts = [s for s in skill_dicts if s.get("status") == status]
    base_stats = SkillRegistry.stats()
    stats = {**base_stats, "disabled": len(_disabled_skills)}
    return {
        "skills": skill_dicts,
        "count": len(skill_dicts),
        "stats": stats,
    }


@router.get("/v1/skills/{skill_id}")
async def get_skill(skill_id: str) -> Dict[str, Any]:
    _ensure_catalogs()
    skill = SkillRegistry.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"skill": _apply_disable_overlay(skill.to_dict())}


@router.post("/v1/skills/{skill_id}/enable")
async def enable_skill(skill_id: str) -> Dict[str, Any]:
    """Remove a skill from the API-disabled set."""
    _ensure_catalogs()
    skill = SkillRegistry.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    _disabled_skills.discard(skill_id)
    return {
        "skill_id": skill_id,
        "status": "enabled",
        "note": "Skill re-enabled. Underlying tool availability may still block it.",
    }


@router.post("/v1/skills/{skill_id}/disable")
async def disable_skill(skill_id: str) -> Dict[str, Any]:
    """Add a skill to the API-disabled set (survives until server restart)."""
    _ensure_catalogs()
    skill = SkillRegistry.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    _disabled_skills.add(skill_id)
    return {
        "skill_id": skill_id,
        "status": "disabled",
        "note": "Skill disabled. Re-enable with POST /v1/skills/{skill_id}/enable.",
    }


class IntakeValidateRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Raw skill manifest content to validate")
    source_url: str = Field("", description="Provenance URL (not fetched)")
    license_spdx: str = Field("UNKNOWN", description="SPDX license identifier")


@router.post("/v1/skills/intake/validate")
async def validate_intake(req: IntakeValidateRequest) -> Dict[str, Any]:
    """Validate a third-party skill manifest for safety.

    Checks for: prompt injection, secret exposure, shell commands,
    network calls, destructive commands, outbound sends.

    Returns a preflight report. Does NOT activate or install the skill.
    Activation always requires explicit reviewer approval.
    """
    from openjarvis.skills.intake import IntakePreflight
    preflight = IntakePreflight()
    result = preflight.check(
        content=req.content,
        source_url=req.source_url,
        license_spdx=req.license_spdx,
    )
    return {
        "preflight": result.to_dict(),
        "verdict": "PASS" if result.passed else "HOLD",
        "activation_status": "requires_reviewer_approval",
        "note": "Passing preflight does not auto-activate. Activation requires explicit approval.",
    }


__all__ = ["router"]
