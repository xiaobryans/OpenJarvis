"""Jarvis Memory OS — project-scoped persistent memory foundation.

Plan 4 Sprint 1: raw/archive layer, distilled layer, retrieval, context
injection, Memory OS status, and governance controls.

Plan 4 Sprint 2: automatic distillation, TF-IDF ranking, honest semantic
search blocker, approval workflow, immutable audit trail, bulk forget,
expiry enforcement, and cloud sync status.
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
from openjarvis.memory.distillation import AutoDistillEngine, DistillationResult, DISTILLABLE_KINDS
from openjarvis.memory.cloud_memory import (
    CloudMemoryGateway,
    CloudMemoryStatus,
    check_cloud_memory_status,
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
    # retrieval + ranking
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
    # distillation
    "AutoDistillEngine",
    "DistillationResult",
    "DISTILLABLE_KINDS",
    # cloud
    "CloudMemoryGateway",
    "CloudMemoryStatus",
    "check_cloud_memory_status",
]
