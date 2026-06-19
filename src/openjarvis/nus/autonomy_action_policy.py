"""NUS 1F — 95% Automation Action Policy.

Classifies actions into autonomy tiers for Bryan's long-term target:
  - 95% automated (eventually)
  - 5% strict policy-controlled
  - minimal unnecessary approval prompts

95% automation means policy-controlled delegated autonomy, NOT unsafe access.

Action classification tiers:
  auto_allowed              → routine safe work, auto-allowed under active policy
  auto_allowed_with_audit   → allowed automatically but logged for review
  dry_run_only              → can run but only as dry-run, no real mutation
  needs_approval            → requires explicit approval before execution
  strict_policy_controlled  → high-risk, explicit policy gate required
  blocked                   → permanently blocked, no policy can unblock

Dangerous categories that remain blocked or strict-gated:
  - production deploy
  - payment/financial action
  - destructive delete
  - secret access or mutation
  - auth/security changes
  - safety/governance changes
  - public posting
  - real Slack/email/social send
  - merge to main
  - public release/notarization
  - self-modifying autonomy/safety logic
  - auto-push, auto-merge, auto-deploy

Provider routing constraints:
  - Routes within approved provider pools only (no new external providers)
  - Cheap models cannot approve critical actions
  - Validation failure escalates
  - Repeated validation failure stops and reports blocker
  - Future agents/workers supported via metadata/contract fields

Hard constraints (permanent):
  - No hardcoded agent names.
  - No bypass of approval gates.
  - US13 voice: HOLD/UNSAFE/PARKED.
  - Production actions remain blocked/dry-run only in NUS 1F.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1F_POLICY_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Autonomy tiers
# ---------------------------------------------------------------------------

TIER_AUTO_ALLOWED = "auto_allowed"
TIER_AUTO_ALLOWED_WITH_AUDIT = "auto_allowed_with_audit"
TIER_DRY_RUN_ONLY = "dry_run_only"
TIER_NEEDS_APPROVAL = "needs_approval"
TIER_STRICT_POLICY_CONTROLLED = "strict_policy_controlled"
TIER_BLOCKED = "blocked"

_ALL_TIERS = frozenset({
    TIER_AUTO_ALLOWED,
    TIER_AUTO_ALLOWED_WITH_AUDIT,
    TIER_DRY_RUN_ONLY,
    TIER_NEEDS_APPROVAL,
    TIER_STRICT_POLICY_CONTROLLED,
    TIER_BLOCKED,
})

# ---------------------------------------------------------------------------
# Permanently blocked (no policy can override)
# ---------------------------------------------------------------------------

_PERMANENTLY_BLOCKED: FrozenSet[str] = frozenset({
    "production_deploy",
    "payment_financial_action",
    "destructive_delete",
    "secret_access",
    "secret_mutation",
    "auth_security_change",
    "safety_governance_change",
    "public_posting",
    "real_slack_send",
    "real_email_send",
    "real_social_send",
    "merge_to_main",
    "public_release",
    "notarization",
    "self_modifying_autonomy_logic",
    "auto_push",
    "auto_merge",
    "auto_deploy",
    "external_provider_setup",
    "browser_account_setup",
})

# ---------------------------------------------------------------------------
# Strict policy-controlled (allowed only with explicit policy gate + approval)
# ---------------------------------------------------------------------------

_STRICT_POLICY_CONTROLLED: FrozenSet[str] = frozenset({
    "production_gate_evaluation",  # evaluation only, no real execution
    "staging_deploy_dry_run",
    "provider_pool_routing_change",
    "high_risk_file_write",
    "cross_system_integration_change",
    "governance_policy_update_dry_run",
})

# ---------------------------------------------------------------------------
# Needs approval (medium–high risk)
# ---------------------------------------------------------------------------

_NEEDS_APPROVAL: FrozenSet[str] = frozenset({
    "medium_file_write",
    "source_code_mutation",
    "config_update",
    "external_api_call_dry_run",
    "provider_routing_recommendation",
    "browser_automation_dry_run",
    "task_queue_mutation",
    "recommendation_approval",
    "auto_commit_candidate",
    "high_autonomy_session_activate",
})

# ---------------------------------------------------------------------------
# Dry-run only (safe to run as dry-run without approval; no real mutation)
# ---------------------------------------------------------------------------

_DRY_RUN_ONLY: FrozenSet[str] = frozenset({
    "recommendation_dry_run",
    "eval_gate_dry_run",
    "rollback_plan_dry_run",
    "session_create_dry_run",
    "session_evaluate_dry_run",
    "production_gate_dry_run",
    "routing_recommendation_dry_run",
    "decision_record_dry_run",
    "auto_commit_dry_run",
})

# ---------------------------------------------------------------------------
# Auto-allowed with audit (write with mandatory log)
# ---------------------------------------------------------------------------

_AUTO_ALLOWED_WITH_AUDIT: FrozenSet[str] = frozenset({
    "scorecard_generation",
    "telemetry_normalization",
    "failure_pattern_summarization",
    "recommendation_deduplication",
    "safe_local_status_snapshot",
    "learning_record_persist",
    "test_run_local",
    "docs_metadata_update",
    "internal_status_update",
})

# ---------------------------------------------------------------------------
# Auto-allowed (routine safe — no approval, light audit)
# ---------------------------------------------------------------------------

_AUTO_ALLOWED: FrozenSet[str] = frozenset({
    "local_read",
    "local_analysis",
    "local_validation",
    "validation_planning",
    "dry_run_recommendation_execution",
    "safe_local_read",
    "safe_docs_read",
    "capability_status_check",
    "health_check",
    "doctor_check",
    "event_log_read",
    "queue_status_check",
    "routing_status_check",
    "session_status_check",
    "decision_record_read",
})

# ---------------------------------------------------------------------------
# Model/provider tier constraints
# ---------------------------------------------------------------------------

# Minimum model tier required for approving actions by tier
# cheap_model = small/fast; standard_model = medium; premium_model = large/premium
MODEL_TIER_CONSTRAINTS: Dict[str, str] = {
    TIER_AUTO_ALLOWED: "any",
    TIER_AUTO_ALLOWED_WITH_AUDIT: "any",
    TIER_DRY_RUN_ONLY: "standard_model",
    TIER_NEEDS_APPROVAL: "standard_model",
    TIER_STRICT_POLICY_CONTROLLED: "premium_model",
    TIER_BLOCKED: "blocked",  # no model can approve
}

# ---------------------------------------------------------------------------
# Action classification
# ---------------------------------------------------------------------------

@dataclass
class ActionClassification:
    """Result of classifying an action."""
    action_type: str
    tier: str
    reason: str
    requires_audit: bool
    requires_approval: bool
    is_blocked: bool
    is_dry_run_safe: bool
    min_model_tier: str
    policy_version: str = NUS1F_POLICY_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "tier": self.tier,
            "reason": self.reason,
            "requires_audit": self.requires_audit,
            "requires_approval": self.requires_approval,
            "is_blocked": self.is_blocked,
            "is_dry_run_safe": self.is_dry_run_safe,
            "min_model_tier": self.min_model_tier,
            "policy_version": self.policy_version,
        }


class AutonomyActionPolicy:
    """Classifies actions into autonomy tiers.

    Metadata/contract-driven — no hardcoded agent names.
    Supports future hierarchy levels via agent_metadata.
    """

    def classify(
        self,
        action_type: str,
        risk_level: str = "low",
        agent_metadata: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionClassification:
        """Classify an action into an autonomy tier."""
        agent_metadata = agent_metadata or {}
        context = context or {}

        # Permanently blocked first
        if action_type in _PERMANENTLY_BLOCKED:
            return ActionClassification(
                action_type=action_type,
                tier=TIER_BLOCKED,
                reason="permanently_blocked_category",
                requires_audit=True,
                requires_approval=False,  # blocked — approval cannot unblock
                is_blocked=True,
                is_dry_run_safe=False,
                min_model_tier="blocked",
            )

        # Risk override: high risk always needs at least approval
        if risk_level in ("high", "critical"):
            if action_type not in _STRICT_POLICY_CONTROLLED:
                return ActionClassification(
                    action_type=action_type,
                    tier=TIER_NEEDS_APPROVAL,
                    reason="high_risk_override",
                    requires_audit=True,
                    requires_approval=True,
                    is_blocked=False,
                    is_dry_run_safe=False,
                    min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_NEEDS_APPROVAL],
                )

        if action_type in _STRICT_POLICY_CONTROLLED:
            return ActionClassification(
                action_type=action_type,
                tier=TIER_STRICT_POLICY_CONTROLLED,
                reason="strict_policy_required",
                requires_audit=True,
                requires_approval=True,
                is_blocked=False,
                is_dry_run_safe=True,
                min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_STRICT_POLICY_CONTROLLED],
            )

        if action_type in _NEEDS_APPROVAL:
            return ActionClassification(
                action_type=action_type,
                tier=TIER_NEEDS_APPROVAL,
                reason="medium_risk_needs_approval",
                requires_audit=True,
                requires_approval=True,
                is_blocked=False,
                is_dry_run_safe=False,
                min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_NEEDS_APPROVAL],
            )

        if action_type in _DRY_RUN_ONLY:
            return ActionClassification(
                action_type=action_type,
                tier=TIER_DRY_RUN_ONLY,
                reason="dry_run_only_allowed",
                requires_audit=True,
                requires_approval=False,
                is_blocked=False,
                is_dry_run_safe=True,
                min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_DRY_RUN_ONLY],
            )

        if action_type in _AUTO_ALLOWED_WITH_AUDIT:
            return ActionClassification(
                action_type=action_type,
                tier=TIER_AUTO_ALLOWED_WITH_AUDIT,
                reason="auto_allowed_audit_required",
                requires_audit=True,
                requires_approval=False,
                is_blocked=False,
                is_dry_run_safe=True,
                min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_AUTO_ALLOWED_WITH_AUDIT],
            )

        if action_type in _AUTO_ALLOWED:
            return ActionClassification(
                action_type=action_type,
                tier=TIER_AUTO_ALLOWED,
                reason="safe_local_routine_action",
                requires_audit=False,
                requires_approval=False,
                is_blocked=False,
                is_dry_run_safe=True,
                min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_AUTO_ALLOWED],
            )

        # Unknown actions default to needs_approval (safe default)
        return ActionClassification(
            action_type=action_type,
            tier=TIER_NEEDS_APPROVAL,
            reason="unknown_action_type_default_approval",
            requires_audit=True,
            requires_approval=True,
            is_blocked=False,
            is_dry_run_safe=False,
            min_model_tier=MODEL_TIER_CONSTRAINTS[TIER_NEEDS_APPROVAL],
        )

    def can_model_tier_approve(self, action_type: str, model_tier: str) -> bool:
        """Check if a model tier can approve/execute this action.

        Cheap models cannot approve critical or strict-policy actions.
        """
        classification = self.classify(action_type)
        if classification.is_blocked:
            return False
        required = MODEL_TIER_CONSTRAINTS.get(classification.tier, "premium_model")
        if required == "blocked":
            return False
        if required == "any":
            return True
        tier_rank = {"any": 0, "cheap_model": 1, "standard_model": 2, "premium_model": 3}
        return tier_rank.get(model_tier, 0) >= tier_rank.get(required, 3)

    def get_status(self) -> Dict[str, Any]:
        return {
            "policy_version": NUS1F_POLICY_VERSION,
            "tiers": sorted(_ALL_TIERS),
            "permanently_blocked_count": len(_PERMANENTLY_BLOCKED),
            "strict_policy_controlled_count": len(_STRICT_POLICY_CONTROLLED),
            "needs_approval_count": len(_NEEDS_APPROVAL),
            "dry_run_only_count": len(_DRY_RUN_ONLY),
            "auto_allowed_with_audit_count": len(_AUTO_ALLOWED_WITH_AUDIT),
            "auto_allowed_count": len(_AUTO_ALLOWED),
            "model_tier_constraints": MODEL_TIER_CONSTRAINTS,
            "target_95pct_automation": True,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "production_execution": "blocked_in_nus1f",
            "no_hardcoded_agent_names": True,
            "metadata_contract_driven": True,
        }


# Module-level singleton
_policy: Optional[AutonomyActionPolicy] = None


def get_action_policy() -> AutonomyActionPolicy:
    global _policy
    if _policy is None:
        _policy = AutonomyActionPolicy()
    return _policy
