"""Plan 8 — Trusted Delegation / Sensitive Authority Expansion.

The `authority` module implements the full Plan 8 safety architecture:

  A. Permission tiers (tiers.py)         — AuthorityTier 0-5 model
  B. Risk classifier (risk_classifier.py) — RiskProfile per action type
  C. Approval engine (approval_engine.py) — ApprovalEngine with all modes
  D. Action preview (action_preview.py)   — ActionPreview + DryRunEngine
  E. Audit store (audit_store.py)         — Durable SQLite audit log
  F. Rollback model (rollback.py)         — RollbackRecord + RollbackStore
  G. Spend guard (spend_guard.py)         — SpendGuard budget enforcement
  H. Secret policy (secret_policy.py)     — SecretPolicyChecker
  I. Emergency stop (emergency.py)        — EmergencyStopStore + revocation

All Plan 8 gates check emergency stop before executing Tier 2+ actions.
No secret values are stored in any Plan 8 record.
"""

from openjarvis.authority.action_preview import ActionPreview, DryRunEngine, build_preview
from openjarvis.authority.approval_engine import (
    ApprovalEngine,
    ApprovalMode,
    ApprovalRecord,
    ApprovalStatus,
)
from openjarvis.authority.audit_store import AuditEntry, AuditStore
from openjarvis.authority.emergency import (
    EmergencyStopStore,
    clear_emergency_stop,
    emergency_gate_check,
    get_emergency_status,
    is_emergency_stop_active,
    set_emergency_stop,
)
from openjarvis.authority.risk_classifier import (
    ActionTypeCategory,
    RiskProfile,
    classify_action,
    classify_risk_matrix,
)
from openjarvis.authority.rollback import (
    RollbackMethod,
    RollbackRecord,
    RollbackStore,
    rollback_for_action_type,
)
from openjarvis.authority.secret_policy import (
    SECRET_POLICY_MANIFEST,
    SecretPolicyChecker,
    SecretScanResult,
    redact_secrets,
    secret_scan_string,
)
from openjarvis.authority.spend_guard import (
    SpendGuard,
    SpendImpact,
    classify_spend_impact,
    estimate_action_cost,
)
from openjarvis.authority.tiers import (
    AuthorityTier,
    TierDefinition,
    get_tier_definition,
    is_tier_allowed,
    tier_for_action,
    tier_matrix,
)

PLAN_8_VERSION = "plan8-trusted-delegation-v1"

__all__ = [
    "PLAN_8_VERSION",
    # A. Tiers
    "AuthorityTier",
    "TierDefinition",
    "get_tier_definition",
    "is_tier_allowed",
    "tier_for_action",
    "tier_matrix",
    # B. Risk classifier
    "ActionTypeCategory",
    "RiskProfile",
    "classify_action",
    "classify_risk_matrix",
    # C. Approval engine
    "ApprovalEngine",
    "ApprovalMode",
    "ApprovalRecord",
    "ApprovalStatus",
    # D. Action preview
    "ActionPreview",
    "DryRunEngine",
    "build_preview",
    # E. Audit store
    "AuditEntry",
    "AuditStore",
    # F. Rollback
    "RollbackMethod",
    "RollbackRecord",
    "RollbackStore",
    "rollback_for_action_type",
    # G. Spend guard
    "SpendGuard",
    "SpendImpact",
    "classify_spend_impact",
    "estimate_action_cost",
    # H. Secret policy
    "SECRET_POLICY_MANIFEST",
    "SecretPolicyChecker",
    "SecretScanResult",
    "redact_secrets",
    "secret_scan_string",
    # I. Emergency
    "EmergencyStopStore",
    "clear_emergency_stop",
    "emergency_gate_check",
    "get_emergency_status",
    "is_emergency_stop_active",
    "set_emergency_stop",
]
