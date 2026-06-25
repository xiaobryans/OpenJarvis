"""REST endpoints for Jarvis Memory Graph (metadata and search proxy only).

Routes:
  GET  /v1/memory-graph/status      — graph availability and capability flags
  GET  /v1/memory-graph/namespaces  — namespace list from JarvisMemory (if available)
  GET  /v1/memory-graph/metadata    — capability/storage metadata (never reads content)
  POST /v1/memory-graph/search      — keyword search proxy to JarvisMemory.search()

Design rules:
  - No entity extraction, relation mapping, or contradiction detection implemented.
  - cloud_sync_live and knowledge_graph_live are never claimed without proof.
  - All responses fall back gracefully if JarvisMemory is unavailable.
  - Actual memory content is never returned except as search results via search().
  - fake_live: False, fake_data: False in all responses.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for memory graph routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["memory-graph"])

__all__ = ["router"]


def _get_memory():
    """Return a JarvisMemory instance, or None if unavailable."""
    try:
        from openjarvis.memory.store import JarvisMemory  # type: ignore

        return JarvisMemory()
    except Exception as exc:
        logger.debug("JarvisMemory unavailable: %s", exc)
        return None


class MemoryGraphSearchRequest(BaseModel):
    query: str
    namespace: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=200)


@router.get("/v1/memory-graph/status")
async def memory_graph_status() -> Dict[str, Any]:
    """Return memory graph availability and capability flags.

    Attempts to contact JarvisMemory for namespace/entry counts.
    Falls back to zeros if unavailable. Never claims cloud sync or
    knowledge graph capabilities without proof.
    """
    try:
        mem = _get_memory()
        graph_available = mem is not None

        namespace_count = 0
        total_entries = 0

        if mem is not None:
            try:
                namespaces = mem.list_namespaces()
                namespace_count = len(namespaces)
                total_entries = sum(ns.get("count", 0) for ns in namespaces)
            except Exception as exc:
                logger.warning("Failed to retrieve namespace info: %s", exc)

        return {
            "graph_available": graph_available,
            "namespace_count": namespace_count,
            "total_entries": total_entries,
            "entity_extraction": False,
            "relation_mapping": False,
            "contradiction_detection": False,
            "cloud_sync_live": False,
            "knowledge_graph_live": False,
            "fake_data": False,
            "note": (
                "Memory graph is metadata-only. "
                "Entity extraction, relation mapping, and contradiction detection "
                "are not yet implemented. "
                "Cloud sync requires Fargate credentials."
            ),
        }
    except Exception as exc:
        logger.exception("memory_graph_status failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve memory graph status")


@router.get("/v1/memory-graph/namespaces")
async def memory_graph_namespaces() -> Dict[str, Any]:
    """Return namespace list from JarvisMemory.

    Falls back to an empty list if JarvisMemory is unavailable.
    Never claims cloud backing or entity extraction.
    """
    try:
        mem = _get_memory()
        namespaces: List[Dict[str, Any]] = []

        if mem is not None:
            try:
                raw = mem.list_namespaces()
                # Aggregate by namespace name (store may return per project_id rows)
                aggregated: Dict[str, int] = {}
                for row in raw:
                    name = row.get("namespace", "")
                    count = row.get("count", 0)
                    aggregated[name] = aggregated.get(name, 0) + count

                namespaces = [
                    {
                        "name": name,
                        "entry_count": count,
                        "searchable": True,
                        "source": "local_sqlite",
                    }
                    for name, count in sorted(aggregated.items())
                ]
            except Exception as exc:
                logger.warning("Failed to list namespaces: %s", exc)

        return {
            "namespaces": namespaces,
            "count": len(namespaces),
            "cloud_backed": False,
            "knowledge_graph_entities": 0,
            "fake_data": False,
            "source": "local_memory_store",
        }
    except Exception as exc:
        logger.exception("memory_graph_namespaces failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve memory namespaces")


@router.get("/v1/memory-graph/metadata")
async def memory_graph_metadata() -> Dict[str, Any]:
    """Return memory capability and storage metadata.

    Never reads actual memory content. Reports only what is implemented.
    Planned capabilities are listed but not claimed as available.
    """
    try:
        mem = _get_memory()
        memory_works = mem is not None

        return {
            "capabilities": {
                "keyword_search": memory_works,
                "semantic_search": False,
                "entity_extraction": False,
                "relation_mapping": False,
                "contradiction_detection": False,
                "time_aware_retrieval": False,
                "confidence_scoring": False,
            },
            "planned_capabilities": [
                "Entity extraction from memory entries",
                "Relation/knowledge graph mapping",
                "Contradiction/conflict detection",
                "Confidence scoring per memory entry",
                "Time-aware memory retrieval",
            ],
            "storage": {
                "local_sqlite": memory_works,
                "cloud_s3": False,
                "vector_db": False,
            },
            "fake_data": False,
            "note": (
                "Memory graph metadata. "
                "Planned capabilities not yet implemented. "
                "Storage is local SQLite only unless Fargate/S3 deployed."
            ),
        }
    except Exception as exc:
        logger.exception("memory_graph_metadata failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve memory graph metadata")


@router.post("/v1/memory-graph/search")
async def memory_graph_search(req: MemoryGraphSearchRequest) -> Dict[str, Any]:
    """Proxy keyword search to JarvisMemory.search().

    Returns an empty result set if JarvisMemory is unavailable.
    Validates that query is a non-empty string. Returns 422 if invalid.
    Never claims semantic search or cloud backing.
    """
    try:
        query = (req.query or "").strip()
        if not query:
            raise HTTPException(
                status_code=422,
                detail="'query' must be a non-empty string.",
            )

        namespace = req.namespace
        limit = req.limit
        results: List[Dict[str, Any]] = []

        mem = _get_memory()
        if mem is not None:
            try:
                entries = mem.search(
                    query,
                    namespace=namespace,
                    limit=limit,
                )
                results = [
                    {
                        "id": getattr(e, "id", None),
                        "namespace": getattr(e, "namespace", None),
                        "content": getattr(e, "content", None),
                        "source": getattr(e, "source", None),
                        "created_at": getattr(e, "created_at", None),
                        "tags": getattr(e, "tags", []),
                    }
                    for e in entries
                ]
            except Exception as exc:
                logger.warning("JarvisMemory.search failed: %s", exc)

        return {
            "query": query,
            "namespace": namespace or "all",
            "results": results,
            "count": len(results),
            "source": "local_memory_search",
            "semantic_search": False,
            "cloud_backed": False,
            "fake_data": False,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("memory_graph_search failed: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to execute memory graph search")
