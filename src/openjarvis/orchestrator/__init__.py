"""Post-NUS Company-Grade Hierarchical Agent Orchestrator.

Architecture:
    Bryan → Jarvis PA / Open Chat → COS/GM → Domain Managers → Specialist Workers
         → Validation / Governance / NUS → unified response back through Jarvis

Design rules (non-negotiable):
- Bryan talks only to Jarvis Open Chat. Routing is fully internal.
- Dynamic activation only; no fixed worker-count formulas.
- Every activation must have rationale. Every skip must have rationale.
- Registered workers are NOT active workers.
- NUS applies to all hierarchy levels.
- All layers emit structured decision records; no raw chain-of-thought.
- Model/provider routing is metadata-driven, never hardcoded by agent name.
- Cheap models cannot approve critical actions.
- Production/deploy/send/auto-push/auto-merge remain blocked.
- US13 voice remains HOLD/UNSAFE/PARKED.

Sprint scope (this implementation):
- Dry-run/read-only framework only.
- No real external sends, no production deploys, no autonomous execution.
- Foundation for future production activation with explicit Bryan approval.
"""

from __future__ import annotations

POST_NUS_ORCHESTRATOR_VERSION = "1.0.0"

from openjarvis.orchestrator.contracts import (
    ManagerContract,
    WorkerContract,
    TaskRoutingRequest,
    ActivationPlan,
    ModelProviderSufficiencyGap,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_BLOCKED,
    COMPLEXITY_SIMPLE,
    COMPLEXITY_MODERATE,
    COMPLEXITY_COMPLEX,
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    STATUS_DEGRADED,
    STATUS_BLOCKED,
)
from openjarvis.orchestrator.manager_registry import (
    ManagerRegistry,
    get_manager_registry,
)
from openjarvis.orchestrator.worker_registry import (
    WorkerRegistry,
    get_worker_registry,
)
from openjarvis.orchestrator.activation import (
    DynamicActivationPlanner,
    get_activation_planner,
)

__all__ = [
    "POST_NUS_ORCHESTRATOR_VERSION",
    "ManagerContract",
    "WorkerContract",
    "TaskRoutingRequest",
    "ActivationPlan",
    "ModelProviderSufficiencyGap",
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_HIGH",
    "RISK_BLOCKED",
    "COMPLEXITY_SIMPLE",
    "COMPLEXITY_MODERATE",
    "COMPLEXITY_COMPLEX",
    "STATUS_ACTIVE",
    "STATUS_INACTIVE",
    "STATUS_DEGRADED",
    "STATUS_BLOCKED",
    "ManagerRegistry",
    "get_manager_registry",
    "WorkerRegistry",
    "get_worker_registry",
    "DynamicActivationPlanner",
    "get_activation_planner",
]
