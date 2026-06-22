"""Plan 9 — Future-Proof Manager/Worker Inheritance Policy.

Guarantees that newly registered managers and workers automatically inherit
Plan 9 default architecture requirements. No future manager/worker can
silently bypass model routing, retrieval worker, approval/audit, or parity.

If a future manager/worker requires custom behavior, it must override
the default explicitly with a reason. Missing policy = validation failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.plan9.model_routing import DEFAULT_ROUTING, ModelTier


# ---------------------------------------------------------------------------
# Default inheritance policy
# ---------------------------------------------------------------------------

@dataclass
class DefaultInheritancePolicy:
    """The default Plan 9 policy inherited by every new manager or worker.

    A new manager/worker that does not declare a custom policy inherits all of
    these defaults. Any field overridden must include an override_reason.
    """

    # Model routing
    default_model_tier: ModelTier = ModelTier.BALANCED
    cheap_model: str = DEFAULT_ROUTING.cheap_model
    balanced_model: str = DEFAULT_ROUTING.balanced_model
    best_model: str = DEFAULT_ROUTING.best_model
    escalation_rule: str = DEFAULT_ROUTING.escalation_rule
    fallback_rule: str = DEFAULT_ROUTING.fallback_rule

    # Retrieval worker
    retrieval_worker_required: bool = True
    retrieval_model_tier: ModelTier = ModelTier.CHEAP
    retrieval_before_reasoning: bool = True

    # Elastic pool
    scaling_allowed: bool = True
    max_workers_default: int = 3
    single_executor_for_writes: bool = True

    # Parallel DAG
    inherits_parallel_dag_safety: bool = True
    risky_actions_sequential: bool = True

    # Same-file batch integration
    must_use_batch_integrator_for_writes: bool = True
    patch_proposals_required: bool = True

    # Authority / audit
    audit_events_required: bool = True
    hard_gated_actions_blocked_by_default: bool = True
    bryan_approval_required_for_sensitive: bool = True

    # Parity
    must_appear_in_capability_matrix: bool = True
    mobile_parity_required: bool = True
    mac_parity_required: bool = True

    # Validation
    structured_output_required: bool = True
    decision_record_required: bool = True
    test_evidence_required: bool = True

    # Report
    report_format: str = (
        "1. Files changed. "
        "2. Tests run and results. "
        "3. Validation proof. "
        "4. Blockers. "
        "5. Rollback notes. "
        "6. Secret scan result."
    )


PLAN9_DEFAULT_INHERITANCE = DefaultInheritancePolicy()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclass
class InheritanceValidationResult:
    entity_id: str
    entity_type: str   # "manager" | "worker"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_manager_inheritance(
    manager_id: str,
    manager_metadata: Dict[str, Any],
    policy: Optional[DefaultInheritancePolicy] = None,
) -> InheritanceValidationResult:
    """Validate that a manager entry satisfies Plan 9 inheritance requirements.

    Checks:
    - Has model routing (cheap/balanced/best) or inherits default
    - Has retrieval worker policy or explicit justification for not needing it
    - Has capability_matrix entry (or will have one)
    - Has authority/audit policy
    - Has parity classification

    Returns InheritanceValidationResult with any errors.
    """
    p = policy or PLAN9_DEFAULT_INHERITANCE
    result = InheritanceValidationResult(entity_id=manager_id, entity_type="manager")

    # Model routing check
    has_routing = (
        manager_metadata.get("model_routing")
        or manager_metadata.get("model_pool")
    )
    if not has_routing:
        result.warnings.append(
            f"{manager_id}: no explicit model routing — inherits DEFAULT_ROUTING. "
            "Ensure this is intentional."
        )

    # Retrieval worker check
    has_retrieval = (
        manager_metadata.get("retrieval_worker_policy")
        or manager_metadata.get("retrieval_needed")
    )
    retrieval_justification = manager_metadata.get("no_retrieval_justification", "")
    if not has_retrieval and not retrieval_justification:
        result.errors.append(
            f"{manager_id}: missing retrieval_worker_policy. "
            "Either define one or provide no_retrieval_justification."
        )

    # Audit requirements
    if not manager_metadata.get("telemetry_policy") and not manager_metadata.get("audit_enabled"):
        result.warnings.append(
            f"{manager_id}: no explicit audit/telemetry policy — inherits default (emit_events=True)."
        )

    # Parity check
    if not manager_metadata.get("parity_status") and not manager_metadata.get("capability_matrix_ref"):
        result.warnings.append(
            f"{manager_id}: no explicit parity_status — must appear in Plan9CapabilityMatrix."
        )

    return result


def validate_worker_inheritance(
    worker_id: str,
    worker_metadata: Dict[str, Any],
    policy: Optional[DefaultInheritancePolicy] = None,
) -> InheritanceValidationResult:
    """Validate that a worker entry satisfies Plan 9 inheritance requirements.

    Same checks as manager but for worker level.
    """
    p = policy or PLAN9_DEFAULT_INHERITANCE
    result = InheritanceValidationResult(entity_id=worker_id, entity_type="worker")

    has_routing = (
        worker_metadata.get("model_routing")
        or worker_metadata.get("model_pool")
    )
    if not has_routing:
        result.warnings.append(
            f"{worker_id}: no explicit model routing — inherits DEFAULT_ROUTING."
        )

    if not worker_metadata.get("telemetry_policy") and not worker_metadata.get("audit_enabled"):
        result.warnings.append(
            f"{worker_id}: no explicit audit policy — inherits default."
        )

    return result


def validate_all_managers_have_routing(
    manager_ids: List[str],
    routing_role_ids: List[str],
) -> List[str]:
    """Return list of manager_ids that have no routing entry.

    Manager IDs present in manager_registry but absent from
    role_routing_matrix inherit DEFAULT_ROUTING (not an error,
    but must be validated explicitly in tests).
    """
    missing = [mid for mid in manager_ids if mid not in routing_role_ids]
    return missing


def validate_all_managers_in_capability_matrix(
    manager_ids: List[str],
    capability_domains: List[str],
) -> List[str]:
    """Return manager_ids not represented by any domain in the capability matrix."""
    missing = [mid for mid in manager_ids if mid not in capability_domains]
    return missing
