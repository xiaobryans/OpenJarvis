"""REST endpoints for Jarvis Skill Registry.

Routes:
  GET /v1/skills              — list all skills (with computed status from tool availability)
  GET /v1/skills/{skill_id}   — get single skill spec

Skill status is computed live from ToolRegistry — no cached/fake state.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
except ImportError:
    raise ImportError("fastapi is required for skills routes")

from openjarvis.skills.catalog import initialize_catalog as init_skill_catalog
from openjarvis.skills.jarvis_registry import SkillRegistry
from openjarvis.tools.catalog import initialize_catalog as init_tool_catalog

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_catalogs() -> None:
    init_tool_catalog()
    init_skill_catalog()


@router.get("/v1/skills")
async def list_skills(agent_id: str = "") -> Dict[str, Any]:
    """List all skills with computed availability status.

    Pass ?agent_id=<id> to filter to skills compatible with that agent.
    Status is computed live from ToolRegistry — blocked tools propagate.
    """
    _ensure_catalogs()
    if agent_id:
        skills = SkillRegistry.list_for_agent(agent_id)
    else:
        skills = SkillRegistry.list_all()
    stats = SkillRegistry.stats()
    return {
        "skills": [s.to_dict() for s in skills],
        "count": len(skills),
        "stats": stats,
    }


@router.get("/v1/skills/{skill_id}")
async def get_skill(skill_id: str) -> Dict[str, Any]:
    _ensure_catalogs()
    skill = SkillRegistry.get(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return {"skill": skill.to_dict()}


__all__ = ["router"]
