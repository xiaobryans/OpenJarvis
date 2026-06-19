"""NUS — Next-generation Upgrade System package.

NUS 1A: Learning Foundation (local, read-only, no self-modification).
NUS 1B: Recommendation Workflow, Persistence, Telemetry, Autonomy Policy Scaffold.
NUS 1C: Persistent Queue, Safe Autopilot, Failure Learning, Learned Routing.
NUS 1D: Eval Gates, Rollback Enforcement, Approval Workflow, Power Autopilot Boundary.
NUS 1E: Low-Risk Execution Classifier, Auto-Commit Foundation, Production-Safe Gate.
NUS 1F: Controlled High-Autonomy Session Framework, 95% Automation Policy,
        Production Gate, Structured Decision Records.
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
from openjarvis.nus.high_autonomy_session import (
    HighAutonomySession,
    HighAutonomySessionManager,
    SessionCreateRequest,
    SessionEvaluation,
    get_session_manager,
    get_kill_switch_state,
    activate_kill_switch,
    deactivate_kill_switch,
    PERMANENTLY_BLOCKED_ACTIONS,
    NUS1F_SESSION_VERSION,
    STATUS_DRAFT,
    STATUS_ACTIVE,
    STATUS_EXPIRED,
    STATUS_REVOKED,
    STATUS_BLOCKED,
    STATUS_COMPLETED,
)
from openjarvis.nus.autonomy_action_policy import (
    AutonomyActionPolicy,
    ActionClassification,
    get_action_policy,
    TIER_AUTO_ALLOWED,
    TIER_AUTO_ALLOWED_WITH_AUDIT,
    TIER_DRY_RUN_ONLY,
    TIER_NEEDS_APPROVAL,
    TIER_STRICT_POLICY_CONTROLLED,
    TIER_BLOCKED,
    NUS1F_POLICY_VERSION,
)
from openjarvis.nus.production_gate import (
    ProductionGate,
    ProductionGateRequest,
    ProductionGateEvaluation,
    create_production_gate_request,
    get_production_gate,
    NUS1F_PRODUCTION_GATE_VERSION,
    GATE_OUTCOME_DRY_RUN_ONLY,
    GATE_OUTCOME_BLOCKED,
)
from openjarvis.nus.decision_record import (
    StructuredDecisionRecord,
    build_session_decision_record,
    build_action_decision_record,
    get_decision_record_status,
    NUS1F_DECISION_RECORD_VERSION,
    DECISION_ALLOWED,
    DECISION_BLOCKED as DECISION_RECORD_BLOCKED,
    LEVEL_JARVIS_PA,
    LEVEL_COS_GM,
    LEVEL_MANAGER,
    LEVEL_WORKER,
    LEVEL_VALIDATOR,
    LEVEL_GOVERNANCE,
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
    # NUS 1F
    "HighAutonomySession",
    "HighAutonomySessionManager",
    "SessionCreateRequest",
    "SessionEvaluation",
    "get_session_manager",
    "get_kill_switch_state",
    "activate_kill_switch",
    "deactivate_kill_switch",
    "PERMANENTLY_BLOCKED_ACTIONS",
    "NUS1F_SESSION_VERSION",
    "STATUS_DRAFT",
    "STATUS_ACTIVE",
    "STATUS_EXPIRED",
    "STATUS_REVOKED",
    "STATUS_BLOCKED",
    "STATUS_COMPLETED",
    "AutonomyActionPolicy",
    "ActionClassification",
    "get_action_policy",
    "TIER_AUTO_ALLOWED",
    "TIER_AUTO_ALLOWED_WITH_AUDIT",
    "TIER_DRY_RUN_ONLY",
    "TIER_NEEDS_APPROVAL",
    "TIER_STRICT_POLICY_CONTROLLED",
    "TIER_BLOCKED",
    "NUS1F_POLICY_VERSION",
    "ProductionGate",
    "ProductionGateRequest",
    "ProductionGateEvaluation",
    "create_production_gate_request",
    "get_production_gate",
    "NUS1F_PRODUCTION_GATE_VERSION",
    "GATE_OUTCOME_DRY_RUN_ONLY",
    "GATE_OUTCOME_BLOCKED",
    "StructuredDecisionRecord",
    "build_session_decision_record",
    "build_action_decision_record",
    "get_decision_record_status",
    "NUS1F_DECISION_RECORD_VERSION",
    "DECISION_ALLOWED",
    "DECISION_RECORD_BLOCKED",
    "LEVEL_JARVIS_PA",
    "LEVEL_COS_GM",
    "LEVEL_MANAGER",
    "LEVEL_WORKER",
    "LEVEL_VALIDATOR",
    "LEVEL_GOVERNANCE",
]
