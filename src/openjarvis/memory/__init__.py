"""Jarvis Memory OS — project-scoped persistent memory foundation.

Plan 4 Sprint 1: raw/archive layer, distilled layer, retrieval, context
injection, Memory OS status, and governance controls.

Plan 4 Sprint 2: automatic distillation, TF-IDF ranking, honest semantic
search blocker, approval workflow, immutable audit trail, bulk forget,
expiry enforcement, and cloud sync status.

Plan 4 Sprint 2B: semantic/vector search (OpenAI embeddings, when key present),
S3 cloud sync (OMNIX workbench bucket), cloud audit replication, AI-assisted
distillation (OpenRouter gpt-4o-mini, with rule-based fallback).
"""

from openjarvis.memory.store import JarvisMemory, MemoryEntry, MEMORY_KINDS, MEMORY_STATUSES
from openjarvis.memory.distilled import DistilledMemory, DistilledEntry, DISTILLED_KINDS
from openjarvis.memory.retrieval import (
    MemoryRetriever,
    RetrievalResult,
    SemanticSearchStatus,
    TfIdfRanker,
)
from openjarvis.memory.context import MemoryContextBuilder, InjectedContext
from openjarvis.memory.status import MemoryOSStatus, get_memory_os_status
from openjarvis.memory.governance import (
    MemoryGovernance,
    GovernanceResult,
    GovernanceAuditLog,
    AuditRecord,
    ApprovalRequired,
    BulkForgetResult,
    ExpiryEnforcementResult,
    HIGH_CONFIDENCE_THRESHOLD,
    PROTECTED_KINDS,
)
from openjarvis.memory.distillation import (
    AutoDistillEngine,
    AIDistillEngine,
    AIDistillationResult,
    DistillationResult,
    DISTILLABLE_KINDS,
)
from openjarvis.memory.cloud_memory import (
    CloudMemoryGateway,
    CloudMemoryStatus,
    check_cloud_memory_status,
)
from openjarvis.memory.cloud_sync import (
    JarvisMemoryS3Sync,
    CloudSyncResult,
    CloudSyncStatus,
)

__all__ = [
    # store
    "JarvisMemory",
    "MemoryEntry",
    "MEMORY_KINDS",
    "MEMORY_STATUSES",
    # distilled
    "DistilledMemory",
    "DistilledEntry",
    "DISTILLED_KINDS",
    # retrieval + ranking (Sprint 2B: semantic active when OPENAI_API_KEY set)
    "MemoryRetriever",
    "RetrievalResult",
    "SemanticSearchStatus",
    "TfIdfRanker",
    # context
    "MemoryContextBuilder",
    "InjectedContext",
    # status
    "MemoryOSStatus",
    "get_memory_os_status",
    # governance (Sprint 1 + Sprint 2)
    "MemoryGovernance",
    "GovernanceResult",
    "GovernanceAuditLog",
    "AuditRecord",
    "ApprovalRequired",
    "BulkForgetResult",
    "ExpiryEnforcementResult",
    "HIGH_CONFIDENCE_THRESHOLD",
    "PROTECTED_KINDS",
    # distillation (Sprint 2 rule-based + Sprint 2B AI-assisted)
    "AutoDistillEngine",
    "AIDistillEngine",
    "AIDistillationResult",
    "DistillationResult",
    "DISTILLABLE_KINDS",
    # cloud memory status
    "CloudMemoryGateway",
    "CloudMemoryStatus",
    "check_cloud_memory_status",
    # cloud sync (Sprint 2B: OMNIX S3 push/pull/merge)
    "JarvisMemoryS3Sync",
    "CloudSyncResult",
    "CloudSyncStatus",
]
