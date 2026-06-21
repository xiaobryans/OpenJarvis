"""REST endpoints for Jarvis Memory Store.

Routes:
  GET  /v1/memory/namespaces  — list all namespaces with entry counts
  POST /v1/memory             — write a memory entry
  GET  /v1/memory/search      — search memory (query, namespace, project_id)
  GET  /v1/memory/status      — Memory OS full status (Sprint 2B surface)

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


@router.get("/v1/memory/status")
async def memory_status() -> Dict[str, Any]:
    """Return full Memory OS status: semantic search, cloud sync, AI distillation."""
    result: Dict[str, Any] = {}

    # Core Memory OS status
    try:
        from openjarvis.memory.status import get_memory_os_status
        mos = get_memory_os_status()
        result["memory_os"] = {
            "sprint": mos.to_dict().get("sprint"),
            "total_entries": mos.raw_archive_count,
            "total_distilled": mos.distilled_count,
            "completed_items": mos.completed_items,
            "planned_not_complete": mos.planned_not_complete,
        }
    except Exception as exc:
        result["memory_os"] = {"status": "error", "detail": str(exc)}

    # Semantic search status
    try:
        from openjarvis.memory.retrieval import SemanticSearchStatus
        sss = SemanticSearchStatus.to_dict()
        result["semantic_search"] = sss
    except Exception as exc:
        result["semantic_search"] = {"status": "error", "detail": str(exc)}

    # Cloud sync status
    try:
        from openjarvis.memory.cloud_sync import JarvisMemoryS3Sync
        sync_status = JarvisMemoryS3Sync().get_status()
        result["cloud_sync"] = {
            "available": sync_status.available,
            "backend": "omnix_s3",
            "bucket": sync_status.bucket,
            "last_error": sync_status.last_error,
        }
    except Exception as exc:
        result["cloud_sync"] = {"available": False, "status": "error", "detail": str(exc)}

    # AI distillation status
    try:
        from openjarvis.memory.distillation import AIDistillEngine
        dist_status = AIDistillEngine.distillation_status()
        result["ai_distillation"] = dist_status
    except Exception as exc:
        result["ai_distillation"] = {"status": "error", "detail": str(exc)}

    return result


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
