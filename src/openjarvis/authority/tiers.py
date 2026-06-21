"""Plan 8 — Permission Tier Model.

Defines the formal six-tier authority model (Tier 0-5) for Jarvis trusted delegation.
Each tier specifies allowed/blocked action categories, required approval mode,
required audit fields, rollback requirements, and credential/spend/external-send policy.

This is the machine-readable source of truth for authority escalation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List


# ---------------------------------------------------------------------------
# Tier enumeration
# ---------------------------------------------------------------------------


class AuthorityTier(int, Enum):
    """Six-tier authority model.

    Tiers are integers so callers can do numeric comparisons:
        action_tier > AuthorityTier.TIER_2 -> requires higher approval
    """

    TIER_0 = 0  # Read-only / explain / plan
    TIER_1 = 1  # Draft-only / simulation / no external side effect
    TIER_2 = 2  # Low-risk reversible actions
    TIER_3 = 3  # Medium-risk writes with explicit approval
    TIER_4 = 4  # High-risk sensitive actions requiring step-up approval
    TIER_5 = 5  # Prohibited / never autonomous without direct human action

    def label(self) -> str:
        return _TIER_LABELS[self]

    def description(self) -> str:
        return _TIER_DESCRIPTIONS[self]


_TIER_LABELS: Dict[AuthorityTier, str] = {
    AuthorityTier.TIER_0: "Read-only / Explain / Plan",
    AuthorityTier.TIER_1: "Draft-only / Simulation",
    AuthorityTier.TIER_2: "Low-risk Reversible",
    AuthorityTier.TIER_3: "Medium-risk Write (Explicit Approval)",
    AuthorityTier.TIER_4: "High-risk Sensitive (Step-up Approval)",
    AuthorityTier.TIER_5: "Prohibited / Human-only",
}

_TIER_DESCRIPTIONS: Dict[AuthorityTier, str] = {
    AuthorityTier.TIER_0: (
        "Safe read-only operations: explain, plan, summarize, search, retrieve. "
        "No external side effects. No writes. No credential access. Auto-allowed."
    ),
    AuthorityTier.TIER_1: (
        "Draft and simulation operations: generate drafts, dry-run previews, "
        "simulated actions without external side effects. Auto-allowed."
    ),
    AuthorityTier.TIER_2: (
        "Low-risk reversible local actions: notes, reminders, non-sensitive file reads, "
        "local state changes that can be fully undone. One-time approval."
    ),
    AuthorityTier.TIER_3: (
        "Medium-risk writes: local file edits, git commits, task updates, "
        "non-sensitive data writes. Explicit one-time approval required. "
        "No external sends, deploys, billing, or account changes."
    ),
    AuthorityTier.TIER_4: (
        "High-risk sensitive: external sends, credential-backed ops, "
        "some deploys with approval, private data ops. Step-up approval required. "
        "No billing/subscription/account mutations, no irreversible destructive ops."
    ),
    AuthorityTier.TIER_5: (
        "Prohibited from autonomous execution. Requires direct human action. "
        "Includes: billing/subscription changes, AWS/security infrastructure, "
        "production account mutations, irreversible destructive deletes/overwrites, "
        "credential/secret changes, force-push protected branches."
    ),
}


# ---------------------------------------------------------------------------
# Tier definition dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierDefinition:
    """Full definition of a single authority tier."""

    tier: AuthorityTier
    label: str
    description: str

    # Action categories allowed/blocked
    allowed_action_types: FrozenSet[str]
    blocked_action_types: FrozenSet[str]

    # Approval requirements
    required_approval_mode: str        # auto_allow | one_time | scoped | step_up | prohibited
    step_up_required: bool             # True = requires re-authentication before execution

    # Audit requirements
    required_audit_fields: FrozenSet[str]
    audit_on_execution: bool

    # Rollback
    rollback_required: bool
    rollback_method: str               # none | best_effort | required | impossible_warn

    # Credential access
    credentials_allowed: bool
    credential_scope: str              # none | read_only_scoped | scoped | all (never for tier<4)

    # Spend policy
    spend_bearing_allowed: bool
    max_spend_per_action: float        # 0.0 = no spend allowed; -1 = unlimited (tier 5 N/A)

    # External sends / deploys / account changes
    external_sends_allowed: bool
    production_deploy_allowed: bool
    account_changes_allowed: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier.value,
            "label": self.label,
            "description": self.description,
            "allowed_action_types": sorted(self.allowed_action_types),
            "blocked_action_types": sorted(self.blocked_action_types),
            "required_approval_mode": self.required_approval_mode,
            "step_up_required": self.step_up_required,
            "required_audit_fields": sorted(self.required_audit_fields),
            "audit_on_execution": self.audit_on_execution,
            "rollback_required": self.rollback_required,
            "rollback_method": self.rollback_method,
            "credentials_allowed": self.credentials_allowed,
            "credential_scope": self.credential_scope,
            "spend_bearing_allowed": self.spend_bearing_allowed,
            "max_spend_per_action": self.max_spend_per_action,
            "external_sends_allowed": self.external_sends_allowed,
            "production_deploy_allowed": self.production_deploy_allowed,
            "account_changes_allowed": self.account_changes_allowed,
        }


# ---------------------------------------------------------------------------
# Tier matrix — canonical definitions
# ---------------------------------------------------------------------------

TIER_DEFINITIONS: Dict[AuthorityTier, TierDefinition] = {

    AuthorityTier.TIER_0: TierDefinition(
        tier=AuthorityTier.TIER_0,
        label=_TIER_LABELS[AuthorityTier.TIER_0],
        description=_TIER_DESCRIPTIONS[AuthorityTier.TIER_0],
        allowed_action_types=frozenset({
            "read", "explain", "plan", "summarize", "search", "retrieve",
            "list", "status_check", "health_check", "diff_view", "log_view",
        }),
        blocked_action_types=frozenset({
            "write", "edit", "delete", "send", "deploy", "commit", "push",
            "credential_access", "billing_change", "account_change",
            "external_send", "production_deploy",
        }),
        required_approval_mode="auto_allow",
        step_up_required=False,
        required_audit_fields=frozenset({"action_type", "actor", "ts"}),
        audit_on_execution=False,
        rollback_required=False,
        rollback_method="none",
        credentials_allowed=False,
        credential_scope="none",
        spend_bearing_allowed=False,
        max_spend_per_action=0.0,
        external_sends_allowed=False,
        production_deploy_allowed=False,
        account_changes_allowed=False,
    ),

    AuthorityTier.TIER_1: TierDefinition(
        tier=AuthorityTier.TIER_1,
        label=_TIER_LABELS[AuthorityTier.TIER_1],
        description=_TIER_DESCRIPTIONS[AuthorityTier.TIER_1],
        allowed_action_types=frozenset({
            "read", "explain", "plan", "summarize", "search", "retrieve",
            "draft", "simulate", "dry_run", "preview", "generate_preview",
            "action_preview", "diff_generate",
        }),
        blocked_action_types=frozenset({
            "delete", "send", "deploy", "commit", "push",
            "credential_access", "billing_change", "account_change",
            "external_send", "production_deploy", "file_write",
        }),
        required_approval_mode="auto_allow",
        step_up_required=False,
        required_audit_fields=frozenset({"action_type", "actor", "ts", "target"}),
        audit_on_execution=False,
        rollback_required=False,
        rollback_method="none",
        credentials_allowed=False,
        credential_scope="none",
        spend_bearing_allowed=False,
        max_spend_per_action=0.0,
        external_sends_allowed=False,
        production_deploy_allowed=False,
        account_changes_allowed=False,
    ),

    AuthorityTier.TIER_2: TierDefinition(
        tier=AuthorityTier.TIER_2,
        label=_TIER_LABELS[AuthorityTier.TIER_2],
        description=_TIER_DESCRIPTIONS[AuthorityTier.TIER_2],
        allowed_action_types=frozenset({
            "read", "explain", "plan", "summarize", "search", "retrieve",
            "draft", "simulate", "dry_run", "preview",
            "local_note_write", "local_reminder_set", "local_state_change",
            "file_read", "non_sensitive_file_read",
        }),
        blocked_action_types=frozenset({
            "delete", "send", "deploy", "push",
            "credential_access", "billing_change", "account_change",
            "external_send", "production_deploy",
            "sensitive_file_write", "secret_access",
        }),
        required_approval_mode="one_time",
        step_up_required=False,
        required_audit_fields=frozenset({
            "action_type", "actor", "ts", "target", "approval_id",
        }),
        audit_on_execution=True,
        rollback_required=True,
        rollback_method="best_effort",
        credentials_allowed=False,
        credential_scope="none",
        spend_bearing_allowed=False,
        max_spend_per_action=0.0,
        external_sends_allowed=False,
        production_deploy_allowed=False,
        account_changes_allowed=False,
    ),

    AuthorityTier.TIER_3: TierDefinition(
        tier=AuthorityTier.TIER_3,
        label=_TIER_LABELS[AuthorityTier.TIER_3],
        description=_TIER_DESCRIPTIONS[AuthorityTier.TIER_3],
        allowed_action_types=frozenset({
            "read", "explain", "plan", "draft", "simulate", "dry_run", "preview",
            "file_write", "file_edit", "local_note_write", "local_reminder_set",
            "git_commit", "git_add", "task_update", "local_db_write",
            "non_sensitive_data_write", "config_write",
        }),
        blocked_action_types=frozenset({
            "delete", "external_send", "deploy", "push", "production_deploy",
            "billing_change", "account_change", "credential_write",
            "secret_access", "destructive_delete", "force_push",
        }),
        required_approval_mode="one_time",
        step_up_required=False,
        required_audit_fields=frozenset({
            "action_type", "actor", "ts", "target", "approval_id",
            "diff_summary", "rollback_plan_id",
        }),
        audit_on_execution=True,
        rollback_required=True,
        rollback_method="required",
        credentials_allowed=True,
        credential_scope="read_only_scoped",
        spend_bearing_allowed=False,
        max_spend_per_action=0.0,
        external_sends_allowed=False,
        production_deploy_allowed=False,
        account_changes_allowed=False,
    ),

    AuthorityTier.TIER_4: TierDefinition(
        tier=AuthorityTier.TIER_4,
        label=_TIER_LABELS[AuthorityTier.TIER_4],
        description=_TIER_DESCRIPTIONS[AuthorityTier.TIER_4],
        allowed_action_types=frozenset({
            "read", "explain", "plan", "draft", "simulate", "dry_run", "preview",
            "file_write", "file_edit", "git_commit", "git_push", "git_add",
            "external_send_approved", "email_draft_send", "slack_send_approved",
            "credential_read_scoped", "oauth_backed_read",
            "staging_deploy", "private_data_op_approved",
        }),
        blocked_action_types=frozenset({
            "billing_change", "subscription_change", "payment_change",
            "account_mutation", "credential_write", "security_config_change",
            "aws_infra_change", "production_deploy", "force_push",
            "destructive_irreversible_delete", "protected_branch_push",
        }),
        required_approval_mode="step_up",
        step_up_required=True,
        required_audit_fields=frozenset({
            "action_type", "actor", "ts", "target", "approval_id",
            "diff_summary", "rollback_plan_id", "risk_level",
            "affected_systems", "cost_estimate", "irreversible_warning",
        }),
        audit_on_execution=True,
        rollback_required=True,
        rollback_method="required",
        credentials_allowed=True,
        credential_scope="scoped",
        spend_bearing_allowed=True,
        max_spend_per_action=10.0,
        external_sends_allowed=True,
        production_deploy_allowed=False,
        account_changes_allowed=False,
    ),

    AuthorityTier.TIER_5: TierDefinition(
        tier=AuthorityTier.TIER_5,
        label=_TIER_LABELS[AuthorityTier.TIER_5],
        description=_TIER_DESCRIPTIONS[AuthorityTier.TIER_5],
        allowed_action_types=frozenset(),  # nothing auto-allowed
        blocked_action_types=frozenset({
            "billing_change", "subscription_change", "payment_change",
            "account_mutation", "credential_write", "security_config_change",
            "aws_infra_change", "production_deploy", "force_push",
            "destructive_irreversible_delete", "protected_branch_push",
            "stripe_change", "vercel_deploy", "supabase_change",
            "all_autonomous_actions",
        }),
        required_approval_mode="prohibited",
        step_up_required=True,
        required_audit_fields=frozenset({
            "action_type", "actor", "ts", "target", "approval_id",
            "diff_summary", "rollback_plan_id", "risk_level",
            "affected_systems", "cost_estimate", "irreversible_warning",
            "human_confirmation_id",
        }),
        audit_on_execution=True,
        rollback_required=True,
        rollback_method="impossible_warn",
        credentials_allowed=False,
        credential_scope="none",
        spend_bearing_allowed=False,
        max_spend_per_action=0.0,
        external_sends_allowed=False,
        production_deploy_allowed=False,
        account_changes_allowed=False,
    ),
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def get_tier_definition(tier: AuthorityTier) -> TierDefinition:
    """Return the full TierDefinition for a given tier."""
    return TIER_DEFINITIONS[tier]


def tier_for_action(action_type: str) -> AuthorityTier:
    """Return the minimum required tier for a given action type.

    Scans all tiers (Tier 5 → Tier 0) to find the highest tier that
    lists this action as blocked. The required tier is one above that.
    Returns Tier 0 if the action is not explicitly blocked anywhere.
    """
    action = action_type.lower()
    for t in sorted(TIER_DEFINITIONS.keys(), reverse=True):
        defn = TIER_DEFINITIONS[t]
        if action in {a.lower() for a in defn.blocked_action_types}:
            return t
    # Check if action appears in any tier's allowed_action_types at tier 0-1
    return AuthorityTier.TIER_0


def is_tier_allowed(action_type: str, current_tier: AuthorityTier) -> bool:
    """Return True if current_tier has the action in its allowed set.

    Tier 0/1 auto-allow all read/draft actions.
    Higher tiers extend the allowed set cumulatively.
    """
    action = action_type.lower()
    # Check from current tier down to Tier 0
    for t in range(current_tier.value, -1, -1):
        tier = AuthorityTier(t)
        defn = TIER_DEFINITIONS[tier]
        if action in {a.lower() for a in defn.allowed_action_types}:
            return True
    return False


def tier_matrix() -> List[Dict[str, Any]]:
    """Return the full tier matrix as a list of dicts (for API/docs)."""
    return [
        TIER_DEFINITIONS[t].to_dict()
        for t in sorted(TIER_DEFINITIONS.keys(), key=lambda x: x.value)
    ]


__all__ = [
    "TIER_DEFINITIONS",
    "AuthorityTier",
    "TierDefinition",
    "get_tier_definition",
    "is_tier_allowed",
    "tier_for_action",
    "tier_matrix",
]
