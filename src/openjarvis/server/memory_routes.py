"""REST endpoints for Jarvis Memory Store.

Routes:
  GET  /v1/memory/namespaces  — list all namespaces with entry counts
  POST /v1/memory             — write a memory entry
  GET  /v1/memory/search      — search memory (query, namespace, project_id)

Governance:
  - No secrets accepted (ValueError → 400)
  - Project memories isolated by project_id
  - OMNIX is project_id='omnix', not hardcoded as the only project
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for memory routes")

from openjarvis.memory.store import JarvisMemory

logger = logging.getLogger(__name__)

router = APIRouter()

_mem: Optional[JarvisMemory] = None


def _get_memory() -> JarvisMemory:
    global _mem
    if _mem is None:
        _mem = JarvisMemory()
    return _mem


class MemoryWriteRequest(BaseModel):
    namespace: str
    content: str
    source: str = ""
    project_id: str = ""
    mission_id: Optional[str] = None
    agent_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    confidence: float = 1.0


@router.get("/v1/memory/namespaces")
async def list_namespaces() -> Dict[str, Any]:
    """List all memory namespaces with their entry counts."""
    mem = _get_memory()
    namespaces = mem.list_namespaces()
    return {"namespaces": namespaces, "count": len(namespaces)}


@router.post("/v1/memory")
async def write_memory(req: MemoryWriteRequest) -> Dict[str, Any]:
    """Write a memory entry.

    Returns 400 if content contains a raw secret/token.
    """
    if not req.namespace.strip():
        raise HTTPException(status_code=400, detail="namespace must not be empty")
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="content must not be empty")
    mem = _get_memory()
    try:
        entry = mem.write(
            namespace=req.namespace,
            content=req.content,
            source=req.source,
            tags=req.tags,
            project_id=req.project_id,
            mission_id=req.mission_id,
            agent_id=req.agent_id,
            confidence=req.confidence,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "entry": entry.to_dict()}


@router.get("/v1/memory/search")
async def search_memory(
    query: str,
    namespace: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Search memory by keyword. Optionally filter by namespace and/or project_id."""
    if not query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    mem = _get_memory()
    results = mem.search(
        query=query,
        namespace=namespace,
        project_id=project_id,
        limit=max(1, min(limit, 200)),
    )
    return {"results": [r.to_dict() for r in results], "count": len(results)}


__all__ = ["router"]
