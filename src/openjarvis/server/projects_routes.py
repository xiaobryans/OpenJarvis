"""REST endpoints for Jarvis ProjectRegistry.

Routes:
  GET /v1/projects              — list all registered projects
  GET /v1/projects/{project_id} — get a single project profile

OMNIX is Project 1 but the registry supports future projects.
No project-specific credentials are exposed in responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
except ImportError:
    raise ImportError("fastapi is required for projects routes")

from openjarvis.governance.constitution import ProjectRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/v1/projects")
async def list_projects() -> Dict[str, Any]:
    """List all registered projects sorted by priority.

    OMNIX appears first (priority=1). Future projects appear after.
    """
    projects = ProjectRegistry.list_projects()
    return {
        "projects": [p.to_dict() for p in projects],
        "count": len(projects),
        "default_project_id": ProjectRegistry.get_default().project_id,
    }


@router.get("/v1/projects/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    project = ProjectRegistry.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return {"project": project.to_dict()}


__all__ = ["router"]
