"""Plan 8 — Risk Classifier.

Classifies a requested action by destructive potential, external side effects,
money/spend impact, credential/security impact, privacy/sensitive-data impact,
production/deploy impact, reversibility, and user confirmation requirement.

Returns a RiskProfile that maps directly to an AuthorityTier recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Risk dimension enums
# ---------------------------------------------------------------------------


class DestructivePotential(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExternalSideEffect(str, Enum):
    NONE = "none"
    POSSIBLE = "possible"
    DEFINITE = "definite"


class MoneyImpact(str, Enum):
    NONE = "none"
    LOW = "low"
    HIGH = "high"
    CRITICAL = "critical"


class CredentialImpact(str, Enum):
    NONE = "none"
    READ_ONLY = "read_only"
    WRITE = "write"
    CRITICAL = "critical"


class PrivacyImpact(str, Enum):
    NONE = "none"
    LIMITED = "limited"
    HIGH = "high"
    CRITICAL = "critical"


class ProductionImpact(str, Enum):
    NONE = "none"
    STAGING = "staging"
    PRODUCTION = "production"


class Reversibility(str, Enum):
    FULLY = "fully"
    PARTIALLY = "partially"
    MANUAL_ONLY = "manual_only"
    IRREVERSIBLE = "irreversible"


# ---------------------------------------------------------------------------
# Action type categories (machine-readable)
# ---------------------------------------------------------------------------


class ActionTypeCategory(str, Enum):
    READ_ONLY = "read_only"
    DRAFT_SIMULATION = "draft_simulation"
    REVERSIBLE_WRITE = "reversible_write"
    DESTRUCTIVE_WRITE_DELETE = "destructive_write_delete"
    EXTERNAL_COMMUNICATION_SEND = "external_communication_send"
    PRODUCTION_DEPLOY = "production_deploy"
    BILLING_PAYMENT_SUBSCRIPTION = "billing_payment_subscription"
    CREDENTIAL_SECURITY_ACCOUNT = "credential_security_account"
    SENSITIVE_PRIVATE_DATA = "sensitive_private_data"


# ---------------------------------------------------------------------------
# RiskProfile
# ---------------------------------------------------------------------------


@dataclass
class RiskProfile:
    """Complete risk assessment for a proposed action."""

    action_type: str
    action_category: ActionTypeCategory

    destructive_potential: DestructivePotential
    external_side_effect: ExternalSideEffect
    money_impact: MoneyImpact
    credential_impact: CredentialImpact
    privacy_impact: PrivacyImpact
    production_impact: ProductionImpact
    reversibility: Reversibility

    user_confirmation_required: bool

    # Derived fields
    risk_score: int = field(init=False)           # 0-100
    recommended_tier: int = field(init=False)     # 0-5
    risk_label: str = field(init=False)           # low | medium | high | critical
    blocking_reason: str = ""
    irreversible_warning: str = ""

    def __post_init__(self) -> None:
        self.risk_score = self._compute_score()
        self.recommended_tier = self._compute_tier()
        self.risk_label = self._compute_label()
        if self.reversibility == Reversibility.IRREVERSIBLE:
            self.irreversible_warning = (
                f"Action '{self.action_type}' is IRREVERSIBLE. "
                "Cannot be undone after execution. Explicit human approval required."
            )

    def _compute_score(self) -> int:
        """Compute a 0-100 risk score from dimension weights."""
        score = 0
        # Destructive potential (0-30)
        dp_scores = {
            DestructivePotential.NONE: 0,
            DestructivePotential.LOW: 5,
            DestructivePotential.MEDIUM: 15,
            DestructivePotential.HIGH: 25,
            DestructivePotential.CRITICAL: 30,
        }
        score += dp_scores[self.destructive_potential]

        # External side effect (0-20)
        ese_scores = {
            ExternalSideEffect.NONE: 0,
            ExternalSideEffect.POSSIBLE: 10,
            ExternalSideEffect.DEFINITE: 20,
        }
        score += ese_scores[self.external_side_effect]

        # Money impact (0-20)
        mi_scores = {
            MoneyImpact.NONE: 0,
            MoneyImpact.LOW: 5,
            MoneyImpact.HIGH: 15,
            MoneyImpact.CRITICAL: 20,
        }
        score += mi_scores[self.money_impact]

        # Credential impact (0-15)
        ci_scores = {
            CredentialImpact.NONE: 0,
            CredentialImpact.READ_ONLY: 3,
            CredentialImpact.WRITE: 10,
            CredentialImpact.CRITICAL: 15,
        }
        score += ci_scores[self.credential_impact]

        # Privacy impact (0-10)
        pi_scores = {
            PrivacyImpact.NONE: 0,
            PrivacyImpact.LIMITED: 3,
            PrivacyImpact.HIGH: 7,
            PrivacyImpact.CRITICAL: 10,
        }
        score += pi_scores[self.privacy_impact]

        # Reversibility penalty (0-5)
        rev_scores = {
            Reversibility.FULLY: 0,
            Reversibility.PARTIALLY: 1,
            Reversibility.MANUAL_ONLY: 3,
            Reversibility.IRREVERSIBLE: 5,
        }
        score += rev_scores[self.reversibility]

        return min(score, 100)

    def _compute_tier(self) -> int:
        """Map risk score + category to recommended AuthorityTier."""
        # Hard overrides for category
        if self.action_category == ActionTypeCategory.BILLING_PAYMENT_SUBSCRIPTION:
            return 5
        if self.action_category == ActionTypeCategory.CREDENTIAL_SECURITY_ACCOUNT:
            if self.credential_impact in (CredentialImpact.WRITE, CredentialImpact.CRITICAL):
                return 5
            return 4
        if self.action_category == ActionTypeCategory.PRODUCTION_DEPLOY:
            if self.production_impact == ProductionImpact.PRODUCTION:
                return 5
            return 4
        if self.action_category == ActionTypeCategory.DESTRUCTIVE_WRITE_DELETE:
            if self.reversibility == Reversibility.IRREVERSIBLE:
                return 5
            return 4
        if self.action_category == ActionTypeCategory.EXTERNAL_COMMUNICATION_SEND:
            return 4
        if self.action_category == ActionTypeCategory.SENSITIVE_PRIVATE_DATA:
            if self.privacy_impact == PrivacyImpact.CRITICAL:
                return 4
            return 3

        # Score-based fallback
        if self.risk_score >= 70:
            return 4
        if self.risk_score >= 40:
            return 3
        if self.risk_score >= 15:
            return 2
        if self.action_category == ActionTypeCategory.DRAFT_SIMULATION:
            return 1
        if self.action_category == ActionTypeCategory.READ_ONLY:
            return 0
        return 2

    def _compute_label(self) -> str:
        if self.risk_score >= 70:
            return "critical"
        if self.risk_score >= 40:
            return "high"
        if self.risk_score >= 15:
            return "medium"
        return "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "action_category": self.action_category.value,
            "destructive_potential": self.destructive_potential.value,
            "external_side_effect": self.external_side_effect.value,
            "money_impact": self.money_impact.value,
            "credential_impact": self.credential_impact.value,
            "privacy_impact": self.privacy_impact.value,
            "production_impact": self.production_impact.value,
            "reversibility": self.reversibility.value,
            "user_confirmation_required": self.user_confirmation_required,
            "risk_score": self.risk_score,
            "recommended_tier": self.recommended_tier,
            "risk_label": self.risk_label,
            "blocking_reason": self.blocking_reason,
            "irreversible_warning": self.irreversible_warning,
        }


# ---------------------------------------------------------------------------
# Action type registry — known action types mapped to risk dimensions
# ---------------------------------------------------------------------------


_ACTION_RISK_MAP: Dict[str, Dict[str, Any]] = {
    # Tier 0 — read-only
    "read": dict(
        action_category=ActionTypeCategory.READ_ONLY,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    "explain": dict(
        action_category=ActionTypeCategory.READ_ONLY,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    "plan": dict(
        action_category=ActionTypeCategory.READ_ONLY,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    "search": dict(
        action_category=ActionTypeCategory.READ_ONLY,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    # Tier 1 — draft/simulation
    "draft": dict(
        action_category=ActionTypeCategory.DRAFT_SIMULATION,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    "simulate": dict(
        action_category=ActionTypeCategory.DRAFT_SIMULATION,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    "dry_run": dict(
        action_category=ActionTypeCategory.DRAFT_SIMULATION,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=False,
    ),
    # Tier 3 — reversible write
    "file_write": dict(
        action_category=ActionTypeCategory.REVERSIBLE_WRITE,
        destructive_potential=DestructivePotential.LOW,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=True,
    ),
    "file_edit": dict(
        action_category=ActionTypeCategory.REVERSIBLE_WRITE,
        destructive_potential=DestructivePotential.LOW,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=True,
    ),
    "git_commit": dict(
        action_category=ActionTypeCategory.REVERSIBLE_WRITE,
        destructive_potential=DestructivePotential.LOW,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=True,
    ),
    # Tier 4 — external send
    "external_send": dict(
        action_category=ActionTypeCategory.EXTERNAL_COMMUNICATION_SEND,
        destructive_potential=DestructivePotential.MEDIUM,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.LIMITED,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    "slack_send": dict(
        action_category=ActionTypeCategory.EXTERNAL_COMMUNICATION_SEND,
        destructive_potential=DestructivePotential.LOW,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.READ_ONLY,
        privacy_impact=PrivacyImpact.LIMITED,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    "email_send": dict(
        action_category=ActionTypeCategory.EXTERNAL_COMMUNICATION_SEND,
        destructive_potential=DestructivePotential.MEDIUM,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.READ_ONLY,
        privacy_impact=PrivacyImpact.HIGH,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.IRREVERSIBLE,
        user_confirmation_required=True,
    ),
    # Tier 4 — deploy (staging)
    "staging_deploy": dict(
        action_category=ActionTypeCategory.PRODUCTION_DEPLOY,
        destructive_potential=DestructivePotential.MEDIUM,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.LOW,
        credential_impact=CredentialImpact.READ_ONLY,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.STAGING,
        reversibility=Reversibility.PARTIALLY,
        user_confirmation_required=True,
    ),
    # Tier 5 — production deploy
    "production_deploy": dict(
        action_category=ActionTypeCategory.PRODUCTION_DEPLOY,
        destructive_potential=DestructivePotential.HIGH,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.HIGH,
        credential_impact=CredentialImpact.READ_ONLY,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    "vercel_deploy": dict(
        action_category=ActionTypeCategory.PRODUCTION_DEPLOY,
        destructive_potential=DestructivePotential.HIGH,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.LOW,
        credential_impact=CredentialImpact.READ_ONLY,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.PARTIALLY,
        user_confirmation_required=True,
    ),
    # Tier 5 — billing
    "billing_change": dict(
        action_category=ActionTypeCategory.BILLING_PAYMENT_SUBSCRIPTION,
        destructive_potential=DestructivePotential.CRITICAL,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.CRITICAL,
        credential_impact=CredentialImpact.WRITE,
        privacy_impact=PrivacyImpact.HIGH,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    "stripe_change": dict(
        action_category=ActionTypeCategory.BILLING_PAYMENT_SUBSCRIPTION,
        destructive_potential=DestructivePotential.CRITICAL,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.CRITICAL,
        credential_impact=CredentialImpact.WRITE,
        privacy_impact=PrivacyImpact.HIGH,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    # Tier 5 — credential/security/account
    "credential_write": dict(
        action_category=ActionTypeCategory.CREDENTIAL_SECURITY_ACCOUNT,
        destructive_potential=DestructivePotential.CRITICAL,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.HIGH,
        credential_impact=CredentialImpact.CRITICAL,
        privacy_impact=PrivacyImpact.CRITICAL,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    "account_mutation": dict(
        action_category=ActionTypeCategory.CREDENTIAL_SECURITY_ACCOUNT,
        destructive_potential=DestructivePotential.HIGH,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.HIGH,
        credential_impact=CredentialImpact.WRITE,
        privacy_impact=PrivacyImpact.CRITICAL,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    "aws_infra_change": dict(
        action_category=ActionTypeCategory.CREDENTIAL_SECURITY_ACCOUNT,
        destructive_potential=DestructivePotential.CRITICAL,
        external_side_effect=ExternalSideEffect.DEFINITE,
        money_impact=MoneyImpact.CRITICAL,
        credential_impact=CredentialImpact.CRITICAL,
        privacy_impact=PrivacyImpact.CRITICAL,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.MANUAL_ONLY,
        user_confirmation_required=True,
    ),
    # Tier 4 — destructive delete (reversible)
    "file_delete": dict(
        action_category=ActionTypeCategory.DESTRUCTIVE_WRITE_DELETE,
        destructive_potential=DestructivePotential.HIGH,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.NONE,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.PARTIALLY,
        user_confirmation_required=True,
    ),
    # Tier 5 — irreversible delete
    "destructive_irreversible_delete": dict(
        action_category=ActionTypeCategory.DESTRUCTIVE_WRITE_DELETE,
        destructive_potential=DestructivePotential.CRITICAL,
        external_side_effect=ExternalSideEffect.POSSIBLE,
        money_impact=MoneyImpact.HIGH,
        credential_impact=CredentialImpact.NONE,
        privacy_impact=PrivacyImpact.HIGH,
        production_impact=ProductionImpact.PRODUCTION,
        reversibility=Reversibility.IRREVERSIBLE,
        user_confirmation_required=True,
    ),
    # Tier 3 — sensitive private data
    "private_data_read": dict(
        action_category=ActionTypeCategory.SENSITIVE_PRIVATE_DATA,
        destructive_potential=DestructivePotential.NONE,
        external_side_effect=ExternalSideEffect.NONE,
        money_impact=MoneyImpact.NONE,
        credential_impact=CredentialImpact.READ_ONLY,
        privacy_impact=PrivacyImpact.HIGH,
        production_impact=ProductionImpact.NONE,
        reversibility=Reversibility.FULLY,
        user_confirmation_required=True,
    ),
}


# ---------------------------------------------------------------------------
# Classifier function
# ---------------------------------------------------------------------------


def classify_action(action_type: str) -> RiskProfile:
    """Classify a named action type and return its RiskProfile.

    For unknown action types, returns a conservative high-risk profile
    to ensure safety-first defaults.
    """
    action = action_type.lower()
    if action in _ACTION_RISK_MAP:
        dims = _ACTION_RISK_MAP[action]
    else:
        # Unknown action → conservative medium-high risk default
        dims = dict(
            action_category=ActionTypeCategory.REVERSIBLE_WRITE,
            destructive_potential=DestructivePotential.MEDIUM,
            external_side_effect=ExternalSideEffect.POSSIBLE,
            money_impact=MoneyImpact.LOW,
            credential_impact=CredentialImpact.NONE,
            privacy_impact=PrivacyImpact.LIMITED,
            production_impact=ProductionImpact.NONE,
            reversibility=Reversibility.PARTIALLY,
            user_confirmation_required=True,
        )

    return RiskProfile(action_type=action, **dims)


def classify_risk_matrix() -> List[Dict[str, Any]]:
    """Return the full risk classification matrix for all known action types."""
    return [
        classify_action(action).to_dict()
        for action in sorted(_ACTION_RISK_MAP.keys())
    ]


__all__ = [
    "ActionTypeCategory",
    "CredentialImpact",
    "DestructivePotential",
    "ExternalSideEffect",
    "MoneyImpact",
    "PrivacyImpact",
    "ProductionImpact",
    "Reversibility",
    "RiskProfile",
    "_ACTION_RISK_MAP",
    "classify_action",
    "classify_risk_matrix",
]
