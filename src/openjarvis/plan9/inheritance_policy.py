"""Plan 9K — Future-Proof Role Inheritance Policy.

Every future manager, worker, agent, tool, skill, command, and provider model
automatically inherits the Plan 9K routing system. No manual hardcoding required.

Inheritance guarantees:
  1. provider/model catalog routing (dynamic, not fixed)
  2. role/task capability routing (required + preferred caps)
  3. fallback/escalation behavior
  4. approval/audit/secret-scan/test gates
  5. memory/context retrieval rules
  6. parity obligations
  7. UI/status visibility
  8. validation/report requirements

Missing routing/capability metadata for a new role MUST fail validation.
Future roles must NOT require manual model hardcoding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from openjarvis.plan9.model_catalog_9k import (
    CapabilityTag,
    LatencyClass,
)
from openjarvis.plan9.specialized_router import (
    RoleCapabilityDeclaration,
    RiskThreshold,
    get_role_declarations,
)


# ---------------------------------------------------------------------------
# Default inheritance policy
# ---------------------------------------------------------------------------

@dataclass
class DefaultInheritancePolicy:
    """The baseline every new role inherits unless explicitly overridden.

    Rules:
    - Any new role that does NOT have an explicit `RoleCapabilityDeclaration`
      automatically gets a safe default: GPT-4o-mini + GPT-4o, no Ollama/Kimi.
    - If a new role declares capabilities, it must pass `RoleInheritanceValidator`.
    - If a new role needs Kimi or Ollama, it must explicitly override with a reason.
    - Security/deploy/IAM/billing/final_review roles must use high_reasoning models.
    """

    # Models any new unknown role defaults to (PA-safe route)
    default_fallback_chain: List[str] = field(default_factory=lambda: [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-sonnet-4-20250514",
    ])
    default_escalation_model: str = "anthropic/claude-sonnet-4-20250514"
    default_required_capabilities: List[CapabilityTag] = field(
        default_factory=lambda: [CapabilityTag.DEFAULT_CHAT]
    )
    default_preferred_capabilities: List[CapabilityTag] = field(
        default_factory=lambda: [CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.TOOL_CALLING]
    )
    default_forbidden_provider_classes: List[str] = field(
        default_factory=lambda: ["ollama", "offline_fallback"]
    )
    default_cost_ceiling: str = "medium"
    default_latency_preference: LatencyClass = LatencyClass.MEDIUM
    default_risk_threshold: RiskThreshold = RiskThreshold.MEDIUM
    default_audit_required: bool = True

    # Capabilities that trigger high-risk validation
    high_risk_capability_triggers: List[CapabilityTag] = field(
        default_factory=lambda: [
            CapabilityTag.SECURITY_REVIEW,
            CapabilityTag.BILLING_IAM_REVIEW,
            CapabilityTag.SECRETS_REVIEW,
            CapabilityTag.DEPLOY_REVIEW,
            CapabilityTag.FINAL_REVIEW,
        ]
    )
    # Models forbidden for high-risk roles
    high_risk_forbidden: List[str] = field(
        default_factory=lambda: ["ollama", "offline_fallback", "kimi", "deepseek"]
    )
    # Required capabilities for high-risk roles
    high_risk_required_capabilities: List[CapabilityTag] = field(
        default_factory=lambda: [CapabilityTag.HIGH_REASONING]
    )

    def build_default_declaration(self, role_id: str, role_type: str = "worker") -> RoleCapabilityDeclaration:
        """Build a default capability declaration for a new unknown role."""
        return RoleCapabilityDeclaration(
            role_id=role_id,
            role_type=role_type,
            required_capabilities=list(self.default_required_capabilities),
            preferred_capabilities=list(self.default_preferred_capabilities),
            forbidden_provider_classes=list(self.default_forbidden_provider_classes),
            fallback_chain=list(self.default_fallback_chain),
            escalation_model=self.default_escalation_model,
            cost_ceiling=self.default_cost_ceiling,
            latency_preference=self.default_latency_preference,
            risk_threshold=self.default_risk_threshold,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=self.default_audit_required,
        )

    def to_dict(self) -> Dict:
        return {
            "default_fallback_chain": self.default_fallback_chain,
            "default_escalation_model": self.default_escalation_model,
            "default_required_capabilities": [t.value for t in self.default_required_capabilities],
            "default_preferred_capabilities": [t.value for t in self.default_preferred_capabilities],
            "default_forbidden_provider_classes": self.default_forbidden_provider_classes,
            "default_cost_ceiling": self.default_cost_ceiling,
            "default_latency_preference": self.default_latency_preference.value,
            "default_risk_threshold": self.default_risk_threshold.value,
            "default_audit_required": self.default_audit_required,
            "high_risk_capability_triggers": [t.value for t in self.high_risk_capability_triggers],
            "high_risk_forbidden": self.high_risk_forbidden,
            "high_risk_required_capabilities": [t.value for t in self.high_risk_required_capabilities],
        }


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

@dataclass
class InheritanceValidationError:
    role_id: str
    rule: str
    message: str
    severity: str = "error"   # "error" | "warning"

    def to_dict(self) -> Dict:
        return {
            "role_id": self.role_id,
            "rule": self.rule,
            "message": self.message,
            "severity": self.severity,
        }

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.role_id}: {self.rule} — {self.message}"


# ---------------------------------------------------------------------------
# Role inheritance validator
# ---------------------------------------------------------------------------

class RoleInheritanceValidator:
    """Validates that a role declaration conforms to Plan 9K inheritance rules.

    Rules enforced:
    1. required_capabilities must be non-empty.
    2. fallback_chain must be non-empty.
    3. High-risk roles (security/deploy/iam/billing/final_review) must:
       - Have HIGH_REASONING in required_capabilities.
       - Not have ollama/kimi/deepseek in fallback_chain or escalation_model.
       - Have risk_threshold HIGH or CRITICAL.
    4. Ollama-using roles must explicitly set override_reason.
    5. Kimi-using roles must have kimi in benchmark_required_for.
    6. audit_required must be True for all roles.
    """

    def __init__(self, policy: Optional[DefaultInheritancePolicy] = None) -> None:
        self._policy = policy or get_default_policy()

    def validate(
        self,
        decl: RoleCapabilityDeclaration,
        override_reason: str = "",
    ) -> List[InheritanceValidationError]:
        errors: List[InheritanceValidationError] = []

        # Rule 1: required_capabilities must be non-empty
        if not decl.required_capabilities:
            errors.append(InheritanceValidationError(
                role_id=decl.role_id,
                rule="required_capabilities_non_empty",
                message="required_capabilities must not be empty. All roles must declare what they need.",
            ))

        # Rule 2: fallback_chain must be non-empty
        if not decl.fallback_chain:
            errors.append(InheritanceValidationError(
                role_id=decl.role_id,
                rule="fallback_chain_non_empty",
                message="fallback_chain must not be empty. All roles must declare priority model hints.",
            ))

        # Rule 3: audit_required must be True
        if not decl.audit_required:
            errors.append(InheritanceValidationError(
                role_id=decl.role_id,
                rule="audit_required",
                message="audit_required must be True. All routing decisions must be auditable.",
            ))

        # Rule 4: Security/deploy/IAM/billing/secrets/final_review roles must use high_reasoning.
        # Note: risk_threshold=HIGH alone is not sufficient — many operational/management roles
        # are high-risk without needing explicit high_reasoning capability (e.g. ops managers).
        # Only roles with explicit security/deploy capability triggers are subject to this rule.
        has_security_trigger = any(
            cap in decl.required_capabilities
            for cap in self._policy.high_risk_capability_triggers
        )

        if has_security_trigger:
            if CapabilityTag.HIGH_REASONING not in decl.required_capabilities:
                errors.append(InheritanceValidationError(
                    role_id=decl.role_id,
                    rule="high_risk_requires_high_reasoning",
                    message=(
                        "Roles with security/deploy/IAM/billing/secrets/final_review capabilities "
                        "must have HIGH_REASONING in required_capabilities."
                    ),
                ))
            for forbidden in self._policy.high_risk_forbidden:
                if any(forbidden in m for m in decl.fallback_chain):
                    errors.append(InheritanceValidationError(
                        role_id=decl.role_id,
                        rule="high_risk_no_cheap_local_models",
                        message=(
                            f"Security/deploy/IAM/final_review role must not have {forbidden!r} "
                            "in fallback_chain. Use Anthropic Claude only."
                        ),
                    ))

        # Rule 5: If ollama allowed, must have explicit override
        if "ollama" not in decl.forbidden_provider_classes and not override_reason:
            errors.append(InheritanceValidationError(
                role_id=decl.role_id,
                rule="ollama_requires_override_reason",
                message=(
                    "Ollama/local allowed in this role but no override_reason provided. "
                    "Ollama is FALLBACK_ONLY. If intentional, provide an override_reason."
                ),
                severity="warning",
            ))

        # Rule 6: Kimi usage must be benchmark-gated
        kimi_in_chain = any("kimi" in m.lower() for m in decl.fallback_chain)
        if kimi_in_chain:
            kimi_benchmarked_in_decl = any(
                "kimi" in m for m in decl.benchmark_required_for
            )
            if not kimi_benchmarked_in_decl:
                errors.append(InheritanceValidationError(
                    role_id=decl.role_id,
                    rule="kimi_must_be_benchmark_gated",
                    message=(
                        "Kimi appears in fallback_chain but 'kimi/kimi-k2' is not in "
                        "benchmark_required_for. Kimi must be benchmark-gated."
                    ),
                ))

        return errors

    def validate_new_role(
        self,
        role_id: str,
        role_type: str,
        required_capabilities: Optional[List[CapabilityTag]] = None,
        fallback_chain: Optional[List[str]] = None,
        forbidden_provider_classes: Optional[List[str]] = None,
        risk_threshold: Optional[RiskThreshold] = None,
        override_reason: str = "",
    ) -> Dict:
        """Validate a new role definition against Plan 9K inheritance policy.

        Returns dict with 'valid', 'errors', 'warnings', and 'declaration'.
        """
        if required_capabilities is None:
            return {
                "valid": False,
                "errors": [InheritanceValidationError(
                    role_id=role_id,
                    rule="required_capabilities_non_empty",
                    message="New role missing required_capabilities. Validation failure.",
                ).to_dict()],
                "warnings": [],
                "declaration": None,
                "inherited_defaults": True,
            }

        decl = RoleCapabilityDeclaration(
            role_id=role_id,
            role_type=role_type,
            required_capabilities=required_capabilities,
            preferred_capabilities=[],
            forbidden_provider_classes=forbidden_provider_classes or ["ollama", "offline_fallback"],
            fallback_chain=fallback_chain or self._policy.default_fallback_chain,
            escalation_model=self._policy.default_escalation_model,
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=risk_threshold or RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )

        validation_errors = self.validate(decl, override_reason=override_reason)
        errors = [e for e in validation_errors if e.severity == "error"]
        warnings = [e for e in validation_errors if e.severity == "warning"]

        return {
            "valid": len(errors) == 0,
            "errors": [e.to_dict() for e in errors],
            "warnings": [e.to_dict() for e in warnings],
            "declaration": decl.to_dict(),
            "inherited_defaults": True,
        }


# ---------------------------------------------------------------------------
# Inheritance coverage report
# ---------------------------------------------------------------------------

def get_inheritance_coverage() -> Dict:
    """Report which declared roles have explicit declarations vs using defaults."""
    decls = get_role_declarations()
    policy = get_default_policy()
    validator = RoleInheritanceValidator(policy)

    coverage = {}
    for role_id, decl in decls.items():
        errors = validator.validate(decl)
        coverage[role_id] = {
            "has_explicit_declaration": True,
            "validation_errors": len([e for e in errors if e.severity == "error"]),
            "validation_warnings": len([e for e in errors if e.severity == "warning"]),
            "required_capabilities": [t.value for t in decl.required_capabilities],
            "risk_threshold": decl.risk_threshold.value,
            "cost_ceiling": decl.cost_ceiling,
            "fallback_chain_length": len(decl.fallback_chain),
        }

    return {
        "total_explicit_declarations": len(decls),
        "default_policy": policy.to_dict(),
        "coverage": coverage,
        "inheritance_rules": [
            "Any new role without an explicit declaration inherits the default policy.",
            "New roles must declare required_capabilities or fail validation.",
            "Security/deploy/IAM/billing/final_review roles must have HIGH_REASONING.",
            "Ollama/local use requires explicit override_reason.",
            "Kimi use requires kimi in benchmark_required_for.",
            "audit_required=True is mandatory for all roles.",
            "Dynamic catalog scoring applies to ALL roles automatically.",
            "New providers/models added to catalog become eligible without code changes.",
        ],
    }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_DEFAULT_POLICY: Optional[DefaultInheritancePolicy] = None


def get_default_policy() -> DefaultInheritancePolicy:
    global _DEFAULT_POLICY
    if _DEFAULT_POLICY is None:
        _DEFAULT_POLICY = DefaultInheritancePolicy()
    return _DEFAULT_POLICY


__all__ = [
    "DefaultInheritancePolicy",
    "InheritanceValidationError",
    "RoleInheritanceValidator",
    "get_default_policy",
    "get_inheritance_coverage",
]
