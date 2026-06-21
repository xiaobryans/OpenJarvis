"""Memory OS Status — honest backend readiness and counts.

Provides a lightweight status object for Mission Control / monitoring.
All operations are read-only.  No model API calls required.

Sprint 1 (foundation): raw/archive, distilled, retrieval, context injection,
governance (forget/edit/export), status, memory injection into executor.

Sprint 2 additions reflected here:
  - automatic_distillation_from_raw: COMPLETE (AutoDistillEngine)
  - semantic_vector_search: BLOCKED (TF-IDF fallback active; see SemanticSearchStatus)
  - cloud_sync: BLOCKED_CREDENTIALS (both S3 and Supabase) — local_only
  - approval_workflow_for_distilled: COMPLETE (force=True gate in MemoryGovernance)
  - full_audit_trail_for_governance: COMPLETE (SQLite immutable triggers)
  - bulk_forget: COMPLETE (bulk_forget with dry_run + safety gates)
  - expiry_enforcement: COMPLETE (enforce_expiry, deterministic, testable)
  - cross_device_sync: BLOCKED_NO_CLOUD_SYNC (pending cloud sync sprint)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jarvis" / "memory.db"


@dataclass
class MemoryOSStatus:
    """Honest status of the Memory OS after Sprint 2.

    Fields
    ------
    backend_available           True if SQLite DB is accessible
    backend_type                Always 'sqlite' for Sprint 1+2
    backend_path                Absolute path to the DB file
    raw_archive_count           Total entries in memory_entries table
    raw_active_count            Entries with status='active'
    distilled_count             Total entries in distilled_entries table
    audit_log_count             Total entries in governance_audit table
    namespaces_count            Distinct namespaces in raw archive
    context_injection_enabled   Whether MemoryContextBuilder can inject context
    last_error                  Last exception message if any, else None
    foundation_complete         Honest sprint-level flag
    completed_items             What was fully implemented in Sprint 1+2
    planned_not_complete        What remains incomplete (honest list)
    """

    backend_available: bool = False
    backend_type: str = "sqlite"
    backend_path: str = ""
    raw_archive_count: int = 0
    raw_active_count: int = 0
    distilled_count: int = 0
    audit_log_count: int = 0
    namespaces_count: int = 0
    context_injection_enabled: bool = True
    last_error: Optional[str] = None
    foundation_complete: bool = True
    completed_items: List[str] = field(default_factory=lambda: [
        "raw_archive_memory_store",
        "distilled_memory_layer",
        "structured_retrieval_with_tfidf_ranking",
        "context_injection_into_agent_prompts",
        "memory_os_status_api",
        "automatic_distillation_from_raw",
        "immutable_audit_trail_for_governance",
        "approval_workflow_for_protected_entries",
        "bulk_forget_with_safety_gates",
        "expiry_enforcement_scheduler",
    ])
    planned_not_complete: List[str] = field(default_factory=lambda: [
        {
            "item": "semantic_vector_search",
            "status": "BLOCKED_NO_EMBEDDING_MODEL",
            "active_fallback": "tfidf_ranking",
            "detail": (
                "Embedding-based semantic search requires OPENAI_API_KEY or "
                "local sentence-transformers. Neither configured. "
                "TF-IDF fallback is active and genuinely useful."
            ),
        },
        {
            "item": "cloud_sync_cross_device",
            "status": "BLOCKED_CREDENTIALS",
            "detail": (
                "Cloud memory sync requires AWS_ACCESS_KEY_ID+secret or "
                "SUPABASE_URL+SUPABASE_SERVICE_ROLE_KEY. "
                "Neither is configured. Local SQLite only."
            ),
        },
        {
            "item": "cloud_audit_replication",
            "status": "BLOCKED_NO_CLOUD_SYNC",
            "detail": "Audit trail is local SQLite only. Cloud replication blocked pending cloud sync sprint.",
        },
        {
            "item": "ai_assisted_distillation",
            "status": "NOT_IMPLEMENTED",
            "detail": "Rule-based local distillation is active. Model-assisted summarization is planned future sprint.",
        },
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend_available": self.backend_available,
            "backend_type": self.backend_type,
            "backend_path": self.backend_path,
            "raw_archive_count": self.raw_archive_count,
            "raw_active_count": self.raw_active_count,
            "distilled_count": self.distilled_count,
            "audit_log_count": self.audit_log_count,
            "namespaces_count": self.namespaces_count,
            "context_injection_enabled": self.context_injection_enabled,
            "last_error": self.last_error,
            "foundation_complete": self.foundation_complete,
            "completed_items": self.completed_items,
            "planned_not_complete": self.planned_not_complete,
            "sprint": "plan4_sprint2_memory_os_completion",
        }


def get_memory_os_status(db_path: Optional[Path] = None) -> MemoryOSStatus:
    """Return honest Memory OS status.

    Safe to call at any time — catches all exceptions and returns a status
    with backend_available=False and last_error set.
    """
    resolved_path = Path(db_path) if db_path else _DEFAULT_DB

    status = MemoryOSStatus(backend_path=str(resolved_path))

    try:
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory(db_path=resolved_path)
        status.raw_archive_count = mem.count()
        status.raw_active_count = mem.count(status="active")
        ns = mem.list_namespaces()
        status.namespaces_count = len(ns)
        status.backend_available = True
    except Exception as exc:
        status.backend_available = False
        status.last_error = str(exc)
        logger.warning("Memory OS status check failed (raw): %s", exc)
        return status

    try:
        from openjarvis.memory.distilled import DistilledMemory

        dist = DistilledMemory(db_path=resolved_path)
        status.distilled_count = dist.count()
    except Exception as exc:
        status.last_error = str(exc)
        logger.warning("Memory OS status check failed (distilled): %s", exc)

    try:
        from openjarvis.memory.governance import GovernanceAuditLog

        audit = GovernanceAuditLog(resolved_path)
        status.audit_log_count = audit.count()
    except Exception as exc:
        logger.warning("Memory OS status check failed (audit): %s", exc)

    return status


__all__ = ["MemoryOSStatus", "get_memory_os_status"]
