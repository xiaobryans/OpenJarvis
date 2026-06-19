"""NUS — Next-generation Upgrade System package.

NUS 1A: Learning Foundation (local, read-only, no self-modification).
NUS 1B: Recommendation Workflow, Persistence, Telemetry, Autonomy Policy Scaffold.
NUS 1C: Persistent Queue, Safe Autopilot, Failure Learning, Learned Routing.
NUS 1D: Eval Gates, Rollback Enforcement, Approval Workflow, Power Autopilot Boundary.
NUS 1E: Low-Risk Execution Classifier, Auto-Commit Foundation, Production-Safe Gate.
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
from openjarvis.nus.recommendation_queue import QueueItem, RecommendationQueue
from openjarvis.nus.safe_autopilot import AutopilotDecision, SafeAutopilot, get_safe_autopilot
from openjarvis.nus.failure_learning import CrossSessionPattern, FailureLearner
from openjarvis.nus.learned_routing import LearnedRouter, RoutingRecommendation, get_learned_router
from openjarvis.nus.eval_gate import EvalCandidate, EvalGateReport, EvalGateResult, EvalGateRunner, run_eval_gate
from openjarvis.nus.rollback import RollbackEnforcer, RollbackPlan
from openjarvis.nus.approval_workflow import ApprovalDecision, ApprovalWorkflow
from openjarvis.nus.power_autopilot import PowerAutopilot, PowerAutopilotDecision
from openjarvis.nus.execution_classifier import ClassificationResult, ExecutionClassifier
from openjarvis.nus.low_risk_execution import AutoCommitCandidate, LowRiskExecutionManager

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
    # NUS 1C
    "QueueItem",
    "RecommendationQueue",
    "AutopilotDecision",
    "SafeAutopilot",
    "get_safe_autopilot",
    "CrossSessionPattern",
    "FailureLearner",
    "LearnedRouter",
    "RoutingRecommendation",
    "get_learned_router",
    # NUS 1D
    "EvalCandidate",
    "EvalGateReport",
    "EvalGateResult",
    "EvalGateRunner",
    "run_eval_gate",
    "RollbackEnforcer",
    "RollbackPlan",
    "ApprovalDecision",
    "ApprovalWorkflow",
    "PowerAutopilot",
    "PowerAutopilotDecision",
    # NUS 1E
    "ClassificationResult",
    "ExecutionClassifier",
    "AutoCommitCandidate",
    "LowRiskExecutionManager",
]
