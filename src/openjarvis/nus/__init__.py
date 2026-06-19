"""NUS — Next-generation Upgrade System package.

NUS 1A: Learning Foundation (local, read-only, no self-modification).
NUS 1B: Recommendation Workflow, Persistence, Telemetry, Autonomy Policy Scaffold.
"""
from openjarvis.nus.learning_foundation import (
    AgentScorecard,
    CapabilitySignal,
    FailurePatternRecord,
    LearningFoundation,
    LearningSignal,
    LearningSnapshot,
    TaskOutcomeRecord,
    get_learning_foundation,
)
from openjarvis.nus.learning_store import LearningStore, PersistedRecord, redact_suspicious
from openjarvis.nus.recommendation_registry import (
    Recommendation,
    RecommendationRegistry,
    resolve_approval_policy,
)
from openjarvis.nus.telemetry import NormalizedTelemetryRecord, TelemetryNormalizer
from openjarvis.nus.autonomy_policy import (
    AutonomyPolicy,
    get_default_policy,
    get_policy_catalog,
    get_policy_status,
)

__all__ = [
    # NUS 1A
    "AgentScorecard",
    "CapabilitySignal",
    "FailurePatternRecord",
    "LearningFoundation",
    "LearningSignal",
    "LearningSnapshot",
    "TaskOutcomeRecord",
    "get_learning_foundation",
    # NUS 1B
    "LearningStore",
    "PersistedRecord",
    "redact_suspicious",
    "Recommendation",
    "RecommendationRegistry",
    "resolve_approval_policy",
    "NormalizedTelemetryRecord",
    "TelemetryNormalizer",
    "AutonomyPolicy",
    "get_default_policy",
    "get_policy_catalog",
    "get_policy_status",
]
