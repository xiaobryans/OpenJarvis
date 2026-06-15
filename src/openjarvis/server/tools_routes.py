"""REST endpoints for Jarvis Tool Registry + Tool Execution Gateway.

Routes:
  GET  /v1/tools                   — list all tools (with status)
  GET  /v1/tools/{tool_id}         — get single tool spec
  POST /v1/tools/{tool_id}/execute — execute a tool through gateway
  GET  /v1/tools/executions/recent — recent execution log entries

All tool execution goes through ToolExecutionGateway.
Planned/degraded tools are visible but never counted as available.
No secrets are included in any response.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for tools routes")

from openjarvis.tools.catalog import initialize_catalog
from openjarvis.tools.gateway import get_gateway
from openjarvis.tools.jarvis_registry import ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_catalog() -> None:
    initialize_catalog()


class ToolExecuteRequest(BaseModel):
    inputs: Dict[str, Any] = Field(default_factory=dict)
    project_id: str = ""
    mission_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: str = ""


@router.get("/v1/tools")
async def list_tools(available_only: bool = False) -> Dict[str, Any]:
    """List all registered tools with their status.

    Pass ?available_only=true to filter to only available tools.
    Never inflates counts — planned/degraded appear separately.
    """
    _ensure_catalog()
    if available_only:
        tools = ToolRegistry.list_available()
    else:
        tools = ToolRegistry.list_all()
    stats = ToolRegistry.stats()
    return {
        "tools": [t.to_dict() for t in tools],
        "count": len(tools),
        "stats": stats,
    }


@router.get("/v1/tools/executions/recent")
async def list_recent_executions(limit: int = 50) -> Dict[str, Any]:
    """Return recent tool execution log entries."""
    _ensure_catalog()
    gateway = get_gateway()
    entries = gateway.get_log().list_recent(limit=max(1, min(limit, 200)))
    return {
        "executions": [e.to_dict() for e in entries],
        "count": len(entries),
    }


@router.get("/v1/tools/{tool_id}")
async def get_tool(tool_id: str) -> Dict[str, Any]:
    _ensure_catalog()
    spec = ToolRegistry.get(tool_id)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_id}' not found")
    return {"tool": spec.to_dict()}


@router.post("/v1/tools/{tool_id}/execute")
async def execute_tool(tool_id: str, req: ToolExecuteRequest) -> Dict[str, Any]:
    """Execute a tool through the ToolExecutionGateway.

    Returns structured result including outcome, ok, output, error.
    Hard-gated and not_configured tools return structured blocked results.
    Never raises on governance failure — returns blocked result instead.
    """
    _ensure_catalog()
    gateway = get_gateway()
    result = gateway.execute(
        tool_id=tool_id,
        inputs=req.inputs,
        project_id=req.project_id,
        mission_id=req.mission_id,
        task_id=req.task_id,
        agent_id=req.agent_id,
    )
    return result.to_dict()


__all__ = ["router"]
