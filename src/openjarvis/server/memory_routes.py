"""REST endpoints for Jarvis Memory Store.

Routes:
  GET  /v1/memory/namespaces  — list all namespaces with entry counts
  POST /v1/memory             — write a memory entry
  GET  /v1/memory/search      — search memory (query, namespace, project_id)
  GET  /v1/memory/status      — Memory OS full status (Sprint 2B surface)
  POST /v1/memory/sync        — push local→S3 / pull S3→local for cross-device parity

Governance:
  - No secrets accepted (ValueError → 400)
  - Project memories isolated by project_id
  - OMNIX is project_id='omnix', not hardcoded as the only project
  - Sync pull does INSERT OR REPLACE (no deletions via sync — deletions must go
    through MemoryGovernance) so it is safe to call from cloud ECS or mobile.
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
            "backend": "jarvis_s3",
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


@router.post("/v1/memory/sync")
async def sync_memory(
    mode: str = "pull",
    namespace: Optional[str] = None,
) -> Dict[str, Any]:
    """Sync memory with S3 for cross-device parity.

    mode values:
      "pull"  — pull S3 entries into local SQLite (use on ECS/iPhone cloud)
      "push"  — push local SQLite entries to S3  (use on MacBook after writes)
      "both"  — push first, then pull (full bidirectional merge)

    namespace: optional — restrict push to a single namespace (pull is always full).

    This is the mechanism for Plan 9 cross-device memory parity:
      MacBook: POST /v1/memory  (write)  → POST /v1/memory/sync?mode=push
      iPhone:  POST /v1/memory/sync?mode=pull → GET /v1/memory/search (finds it)
    """
    if mode not in ("pull", "push", "both"):
        raise HTTPException(status_code=400, detail="mode must be 'pull', 'push', or 'both'")

    from openjarvis.memory.cloud_sync import JarvisMemoryS3Sync

    mem = _get_memory()
    sync = JarvisMemoryS3Sync()
    result: Dict[str, Any] = {"mode": mode}

    # ------------------------------------------------------------------ push
    if mode in ("push", "both"):
        try:
            raw_entries = mem.list_all_raw()
            if namespace:
                raw_entries = [e for e in raw_entries if e.namespace == namespace]
            push_result = sync.push_raw([e.to_dict() for e in raw_entries])
            result["push"] = push_result.to_dict()
        except Exception as exc:
            result["push"] = {"ok": False, "error": str(exc)}

    # ------------------------------------------------------------------ pull
    if mode in ("pull", "both"):
        try:
            ok, s3_entries, err = sync.pull_raw()
            if not ok:
                result["pull"] = {
                    "ok": False,
                    "error": err or "S3 pull failed",
                    "hint": "Ensure OMNIX_WORKBENCH_MEMORY_BUCKET and AWS credentials are set",
                }
            else:
                imported = 0
                skipped = 0
                errors: List[str] = []
                for raw in s3_entries:
                    try:
                        mem.store(
                            namespace=raw.get("namespace") or "default",
                            content=raw.get("content") or "",
                            source=raw.get("source") or "s3_sync",
                            project_id=raw.get("project_id") or "",
                            mission_id=raw.get("mission_id"),
                            agent_id=raw.get("agent_id"),
                            tags=raw.get("tags") or [],
                            confidence=float(raw.get("confidence", 1.0)),
                            kind=raw.get("kind") or "event",
                            status=raw.get("status") or "active",
                            expires_at=raw.get("expires_at"),
                            entry_id=raw.get("entry_id"),
                        )
                        imported += 1
                    except ValueError:
                        # secret scrubber rejected content — skip silently
                        skipped += 1
                    except Exception as exc:
                        errors.append(str(exc)[:120])
                result["pull"] = {
                    "ok": True,
                    "total_from_s3": len(s3_entries),
                    "imported": imported,
                    "skipped_secret": skipped,
                    "errors": errors[:5],
                }
        except Exception as exc:
            result["pull"] = {"ok": False, "error": str(exc)}

    result["total_entries_after"] = mem.count()
    return result


@router.get("/v1/memory/rust-status")
async def memory_rust_status() -> Dict[str, Any]:
    """Return openjarvis_rust extension availability and actionable fix hint."""
    try:
        from openjarvis._rust_bridge import RUST_AVAILABLE
        if RUST_AVAILABLE:
            return {
                "rust_available": True,
                "status": "IMPORT_OK",
                "detail": "openjarvis_rust extension is installed and importable.",
            }
        else:
            return {
                "rust_available": False,
                "status": "MISSING",
                "detail": (
                    "openjarvis_rust not importable. Memory API routes (store/search/sync) "
                    "work without it via pure-Python SQLite path. "
                    "Rust extension adds BM25/semantic retrieval for tool calls. "
                    "Fix: ensure Dockerfile builds rust/crates/openjarvis-python with maturin."
                ),
            }
    except Exception as exc:
        return {"rust_available": False, "status": "ERROR", "detail": str(exc)}


__all__ = ["router"]
