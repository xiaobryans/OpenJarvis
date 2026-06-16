"""Intelligence primitive — the model definition, catalog, and trust layer."""

from __future__ import annotations

from openjarvis.intelligence.model_catalog import (
    BUILTIN_MODELS,
    merge_discovered_models,
    register_builtin_models,
)
from openjarvis.intelligence.trust import (
    ActionAccessType,
    ActionProfile,
    ConnectorTrustStatus,
    EvidenceRecord,
    INSUFFICIENT_DATA_MSG,
    MemoryProvenance,
    MemorySource,
    PostExecutionSelfCheck,
    PreExecutionSelfCheck,
    ReadinessTrustReport,
    TrustStatus,
    build_action_profile,
    build_readiness_trust_report,
    classify_connector_trust,
    classify_memory_provenance,
    insufficient_data,
)

__all__ = [
    "BUILTIN_MODELS",
    "merge_discovered_models",
    "register_builtin_models",
    "ActionAccessType",
    "ActionProfile",
    "ConnectorTrustStatus",
    "EvidenceRecord",
    "INSUFFICIENT_DATA_MSG",
    "MemoryProvenance",
    "MemorySource",
    "PostExecutionSelfCheck",
    "PreExecutionSelfCheck",
    "ReadinessTrustReport",
    "TrustStatus",
    "build_action_profile",
    "build_readiness_trust_report",
    "classify_connector_trust",
    "classify_memory_provenance",
    "insufficient_data",
]
