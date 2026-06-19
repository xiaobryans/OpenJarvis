"""NUS 1F — Production Gate.

Implements the production safety gate structure.

In NUS 1F, production execution is BLOCKED or DRY-RUN ONLY.
Real deploys, real merges, real auto-push do NOT execute.

A ProductionGateRequest captures all required preconditions for future
gate evaluation. A ProductionGateEvaluation records the result.

For NUS 1F:
  - All production gate evaluations return dry_run_only or blocked.
  - No real execution occurs.
  - Real deploys are blocked by PERMANENTLY_BLOCKED_ACTIONS in session policy.

Required preconditions for any future production gate pass:
  1. Explicit gate object with owner authorization
  2. Staging/safe preconditions verified
  3. Rollback plan present
  4. Validation plan present
  5. Audit log reference
  6. Risk review completed
  7. Cost/budget check passed
  8. No secret leakage
  9. Kill switch available and off
  10. Production-grade approval (not cheap model)

Hard constraints:
  - production_execution: blocked_dry_run_only in NUS 1F
  - No real deploys, no auto-push, no auto-merge.
  - US13 voice: HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

NUS1F_PRODUCTION_GATE_VERSION = "1.0.0"

# Gate outcomes
GATE_OUTCOME_DRY_RUN_ONLY = "dry_run_only"
GATE_OUTCOME_BLOCKED = "blocked"
GATE_OUTCOME_PRECONDITIONS_FAILED = "preconditions_failed"
# Note: GATE_OUTCOME_APPROVED is intentionally absent in NUS 1F
# It is reserved for a future sprint with explicit authorization.

_NUS1F_GATE_OUTCOMES = frozenset({
    GATE_OUTCOME_DRY_RUN_ONLY,
    GATE_OUTCOME_BLOCKED,
    GATE_OUTCOME_PRECONDITIONS_FAILED,
})

# Action categories that trigger production gate evaluation
PRODUCTION_GATE_CATEGORIES = frozenset({
    "production_deploy",
    "staging_deploy",
    "merge_to_main",
    "public_release",
    "auto_push",
    "auto_merge",
    "payment_financial_action",
    "production_database_mutation",
    "production_config_change",
    "cdn_cache_purge",
    "production_rollback",
})

# Actions that are ALWAYS blocked by production gate (not even dry-run eval)
PRODUCTION_ALWAYS_BLOCKED = frozenset({
    "production_deploy",
    "auto_push",
    "auto_merge",
    "merge_to_main",
    "payment_financial_action",
    "public_release",
    "notarization",
    "secret_access",
})


@dataclass
class ProductionGateRequest:
    """Captures all preconditions required for a production gate evaluation."""
    gate_id: str
    created_at: float
    owner: str
    action_type: str
    environment: str  # "production", "staging", "local"
    rollback_plan: Dict[str, Any] = field(default_factory=dict)
    validation_plan: Dict[str, Any] = field(default_factory=dict)
    audit_log_id: str = ""
    risk_review: Dict[str, Any] = field(default_factory=dict)
    cost_budget: float = 0.0
    token_budget: int = 0
    secret_leakage_checked: bool = False
    kill_switch_available: bool = False
    owner_authorization: str = ""
    staging_preconditions: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "created_at": self.created_at,
            "owner": self.owner,
            "action_type": self.action_type,
            "environment": self.environment,
            "rollback_plan_present": bool(self.rollback_plan),
            "validation_plan_present": bool(self.validation_plan),
            "audit_log_id": self.audit_log_id,
            "risk_review_present": bool(self.risk_review),
            "cost_budget": self.cost_budget,
            "secret_leakage_checked": self.secret_leakage_checked,
            "kill_switch_available": self.kill_switch_available,
            "owner_authorization": self.owner_authorization,
            "staging_preconditions_present": bool(self.staging_preconditions),
            "reason": self.reason,
        }


@dataclass
class ProductionGateEvaluation:
    """Result of a production gate evaluation."""
    gate_id: str
    action_type: str
    outcome: str
    blocking_reason: str
    preconditions_met: List[str] = field(default_factory=list)
    preconditions_failed: List[str] = field(default_factory=list)
    is_real_execution: bool = False
    is_dry_run: bool = True
    structured_decision_record: Dict[str, Any] = field(default_factory=dict)
    gate_version: str = NUS1F_PRODUCTION_GATE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "action_type": self.action_type,
            "outcome": self.outcome,
            "blocking_reason": self.blocking_reason,
            "preconditions_met": self.preconditions_met,
            "preconditions_failed": self.preconditions_failed,
            "is_real_execution": self.is_real_execution,
            "is_dry_run": self.is_dry_run,
            "structured_decision_record": self.structured_decision_record,
            "gate_version": self.gate_version,
            "nus1f_production_autonomy_enabled": False,
            "no_real_deploy": True,
            "no_auto_push": True,
            "no_auto_merge": True,
        }


class ProductionGate:
    """Evaluates production gate requests.

    In NUS 1F:
      - Always returns dry_run_only or blocked.
      - Real execution is never performed.
      - Records all preconditions and gaps for future gate implementation.
    """

    def evaluate(self, request: ProductionGateRequest) -> ProductionGateEvaluation:
        """Evaluate a production gate request. Always dry-run or blocked in NUS 1F."""
        from openjarvis.nus.decision_record import build_action_decision_record, RISK_HIGH

        gate_id = request.gate_id

        # Always-blocked categories
        if request.action_type in PRODUCTION_ALWAYS_BLOCKED:
            dr = build_action_decision_record(
                action_type=request.action_type,
                decision="blocked",
                reason="production_always_blocked_category",
                evidence=request.to_dict(),
                risk_level=RISK_HIGH,
                policy_reference="nus1f_production_gate",
                nus_learning_tags=["nus1f", "production_gate", "blocked"],
            )
            return ProductionGateEvaluation(
                gate_id=gate_id,
                action_type=request.action_type,
                outcome=GATE_OUTCOME_BLOCKED,
                blocking_reason=f"{request.action_type} is permanently blocked in NUS 1F",
                is_real_execution=False,
                is_dry_run=False,
                structured_decision_record=dr,
            )

        # Check preconditions
        met = []
        failed = []

        if request.rollback_plan:
            met.append("rollback_plan_present")
        else:
            failed.append("rollback_plan_missing")

        if request.validation_plan:
            met.append("validation_plan_present")
        else:
            failed.append("validation_plan_missing")

        if request.audit_log_id:
            met.append("audit_log_id_present")
        else:
            failed.append("audit_log_id_missing")

        if request.risk_review:
            met.append("risk_review_present")
        else:
            failed.append("risk_review_missing")

        if request.secret_leakage_checked:
            met.append("secret_leakage_checked")
        else:
            failed.append("secret_leakage_not_checked")

        if request.kill_switch_available:
            met.append("kill_switch_available")
        else:
            failed.append("kill_switch_not_available")

        if request.owner_authorization:
            met.append("owner_authorization_present")
        else:
            failed.append("owner_authorization_missing")

        if request.environment in ("staging", "local"):
            met.append("non_production_environment")
        else:
            failed.append("production_environment_not_safe_for_nus1f")

        # In NUS 1F: always dry_run_only regardless of preconditions
        outcome = GATE_OUTCOME_DRY_RUN_ONLY if not failed else GATE_OUTCOME_PRECONDITIONS_FAILED

        dr = build_action_decision_record(
            action_type=request.action_type,
            decision="dry_run",
            reason=f"nus1f_production_gate_dry_run_only — {len(failed)} preconditions failed",
            evidence={
                **request.to_dict(),
                "preconditions_met": met,
                "preconditions_failed": failed,
            },
            risk_level=RISK_HIGH,
            policy_reference="nus1f_production_gate",
            nus_learning_tags=["nus1f", "production_gate", "dry_run"],
        )

        return ProductionGateEvaluation(
            gate_id=gate_id,
            action_type=request.action_type,
            outcome=outcome,
            blocking_reason="NUS 1F: production execution blocked — dry-run only sprint",
            preconditions_met=met,
            preconditions_failed=failed,
            is_real_execution=False,
            is_dry_run=True,
            structured_decision_record=dr,
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "gate_version": NUS1F_PRODUCTION_GATE_VERSION,
            "production_autonomy_enabled": False,
            "nus1f_execution_mode": "blocked_dry_run_only",
            "real_deploy_blocked": True,
            "auto_push_blocked": True,
            "auto_merge_blocked": True,
            "always_blocked_categories": sorted(PRODUCTION_ALWAYS_BLOCKED),
            "gate_categories": sorted(PRODUCTION_GATE_CATEGORIES),
            "required_preconditions": [
                "owner_authorization",
                "rollback_plan",
                "validation_plan",
                "audit_log_id",
                "risk_review",
                "secret_leakage_checked",
                "kill_switch_available",
                "non_production_environment_staging_or_local",
            ],
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
        }


def create_production_gate_request(
    owner: str,
    action_type: str,
    environment: str = "staging",
    **kwargs: Any,
) -> ProductionGateRequest:
    """Convenience factory for production gate requests."""
    return ProductionGateRequest(
        gate_id=str(uuid.uuid4()),
        created_at=time.time(),
        owner=owner,
        action_type=action_type,
        environment=environment,
        **kwargs,
    )


# Module-level singleton
_gate: Optional[ProductionGate] = None


def get_production_gate() -> ProductionGate:
    global _gate
    if _gate is None:
        _gate = ProductionGate()
    return _gate
