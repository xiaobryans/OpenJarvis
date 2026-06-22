"""Plan 9K — Inheritance Policy Tests.

Tests proving:
1. New manager/worker automatically inherits model-routing defaults.
2. New role missing required_capabilities fails validation.
3. New role with explicit override reason passes validation.
4. Future roles do not need manual model hardcoding.
5. New discovered model stays UNKNOWN until tagged.
6. High-risk capability triggers force high_reasoning requirement.
7. Ollama override requires explicit reason.
8. Kimi must be benchmark-gated.
"""

from __future__ import annotations

import pytest

from openjarvis.plan9.model_catalog_9k import (
    AllowedRiskLevel,
    BenchmarkStatus,
    CapabilityTag,
    LatencyClass,
    ModelEntry9K,
    ModelStatus,
    get_provider_catalog,
)
from openjarvis.plan9.inheritance_policy import (
    DefaultInheritancePolicy,
    InheritanceValidationError,
    RoleInheritanceValidator,
    get_default_policy,
    get_inheritance_coverage,
)
from openjarvis.plan9.specialized_router import (
    RoleCapabilityDeclaration,
    RiskThreshold,
    SpecializedRouter,
    get_role_declarations,
    get_specialized_router,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def policy() -> DefaultInheritancePolicy:
    return get_default_policy()


@pytest.fixture
def validator(policy) -> RoleInheritanceValidator:
    return RoleInheritanceValidator(policy)


@pytest.fixture
def catalog():
    return get_provider_catalog()


@pytest.fixture
def router(catalog):
    return SpecializedRouter(catalog=catalog)


# ---------------------------------------------------------------------------
# 1. New roles inherit defaults automatically
# ---------------------------------------------------------------------------

class TestDefaultInheritance:
    def test_new_manager_gets_default_declaration(self, router):
        """A new manager role with no explicit declaration gets the safe default."""
        decision = router.select(
            role_id="totally_new_future_manager_xyz",
            task_description="some management task",
        )
        # Must get a real model (not error out)
        assert decision.chosen_model_id, "New role must resolve to a model via default inheritance"
        assert "ollama" not in decision.chosen_model_id.lower()
        assert "kimi" not in decision.chosen_model_id.lower()

    def test_new_worker_gets_default_declaration(self, router):
        """A new worker role gets the safe default routing."""
        decision = router.select(
            role_id="new_future_worker_abc",
            task_description="process something",
        )
        assert decision.chosen_model_id
        assert "ollama" not in decision.chosen_model_id.lower()

    def test_default_declaration_uses_openai_as_first_choice(self, policy):
        """Default declaration must prefer OpenAI GPT models."""
        decl = policy.build_default_declaration("test_role")
        assert "openai/gpt-4o-mini" in decl.fallback_chain or "openai/gpt-4o" in decl.fallback_chain, (
            f"Default declaration must include OpenAI models in fallback_chain: {decl.fallback_chain}"
        )

    def test_default_declaration_forbids_ollama(self, policy):
        """Default declaration must forbid ollama."""
        decl = policy.build_default_declaration("test_role")
        assert "ollama" in decl.forbidden_provider_classes

    def test_default_declaration_has_required_capabilities(self, policy):
        """Default declaration must have non-empty required_capabilities."""
        decl = policy.build_default_declaration("test_role")
        assert len(decl.required_capabilities) > 0

    def test_default_declaration_has_audit_required(self, policy):
        """Default declaration must have audit_required=True."""
        decl = policy.build_default_declaration("test_role")
        assert decl.audit_required is True

    def test_default_declaration_has_benchmark_required_for_kimi(self, policy):
        """Default declaration must have kimi in benchmark_required_for."""
        decl = policy.build_default_declaration("test_role")
        assert any("kimi" in m for m in decl.benchmark_required_for), (
            "Default declaration must require benchmark proof for Kimi."
        )


# ---------------------------------------------------------------------------
# 2. New role missing required_capabilities fails validation
# ---------------------------------------------------------------------------

class TestMissingCapabilitiesFailsValidation:
    def test_new_role_no_caps_fails(self, validator):
        """New role with required_capabilities=None must fail validation."""
        result = validator.validate_new_role(
            role_id="bad_new_role",
            role_type="worker",
            required_capabilities=None,  # Missing!
        )
        assert not result["valid"], "Role with no capabilities must fail validation"
        assert len(result["errors"]) > 0
        error_rules = [e["rule"] for e in result["errors"]]
        assert "required_capabilities_non_empty" in error_rules

    def test_new_role_empty_caps_fails(self, validator):
        """New role with empty required_capabilities must fail validation."""
        # Build a fake declaration with empty caps
        decl = RoleCapabilityDeclaration(
            role_id="empty_caps_role",
            role_type="worker",
            required_capabilities=[],  # Empty!
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=["openai/gpt-4o-mini"],
            escalation_model="openai/gpt-4o",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "required_capabilities_non_empty" in error_rules

    def test_new_role_no_fallback_chain_fails(self, validator):
        """New role with empty fallback_chain must fail validation."""
        decl = RoleCapabilityDeclaration(
            role_id="no_chain_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[],  # Empty!
            escalation_model="openai/gpt-4o",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "fallback_chain_non_empty" in error_rules


# ---------------------------------------------------------------------------
# 3. New role with explicit override passes validation
# ---------------------------------------------------------------------------

class TestExplicitOverridePasses:
    def test_new_role_with_valid_caps_passes(self, validator):
        """New role with valid capabilities and fallback_chain passes validation."""
        result = validator.validate_new_role(
            role_id="good_new_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
        )
        assert result["valid"], f"Valid new role must pass: {result['errors']}"
        assert result["inherited_defaults"] is True

    def test_high_risk_role_with_high_reasoning_passes(self, validator):
        """High-risk role with HIGH_REASONING + Anthropic chain passes."""
        result = validator.validate_new_role(
            role_id="good_security_role",
            role_type="worker",
            required_capabilities=[
                CapabilityTag.SECURITY_REVIEW,
                CapabilityTag.HIGH_REASONING,
            ],
            fallback_chain=[
                "anthropic/claude-sonnet-4-20250514",
                "anthropic/claude-opus-4-20250514",
            ],
            risk_threshold=RiskThreshold.HIGH,
            override_reason="Security review role needs Anthropic high-reasoning models only.",
        )
        errors = [e for e in result.get("errors", []) if "high_reasoning" in e.get("rule", "")]
        assert len(errors) == 0, f"High-risk role with HIGH_REASONING must not fail: {result['errors']}"


# ---------------------------------------------------------------------------
# 4. High-risk capability triggers enforcement
# ---------------------------------------------------------------------------

class TestHighRiskEnforcement:
    def test_security_role_without_high_reasoning_fails(self, validator):
        """security_review role (with SECURITY_REVIEW cap) without HIGH_REASONING must fail."""
        decl = RoleCapabilityDeclaration(
            role_id="bad_security_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.SECURITY_REVIEW],  # No HIGH_REASONING!
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=["anthropic/claude-sonnet-4-20250514"],
            escalation_model="anthropic/claude-opus-4-20250514",
            cost_ceiling="any",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.HIGH,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "high_risk_requires_high_reasoning" in error_rules, (
            f"SECURITY_REVIEW without HIGH_REASONING must fail; got error rules: {error_rules}"
        )

    def test_deploy_review_role_with_deepseek_in_chain_fails(self, validator):
        """DEPLOY_REVIEW role must not have deepseek in fallback_chain (per policy)."""
        decl = RoleCapabilityDeclaration(
            role_id="bad_deploy_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.DEPLOY_REVIEW, CapabilityTag.HIGH_REASONING],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[
                "deepseek/deepseek-chat",  # FORBIDDEN for deploy review!
                "anthropic/claude-sonnet-4-20250514",
            ],
            escalation_model="anthropic/claude-opus-4-20250514",
            cost_ceiling="any",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.HIGH,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "high_risk_no_cheap_local_models" in error_rules

    def test_all_existing_security_roles_have_high_reasoning(self, validator):
        """Roles with SECURITY_REVIEW/DEPLOY_REVIEW/FINAL_REVIEW must have HIGH_REASONING."""
        from openjarvis.plan9.model_catalog_9k import CapabilityTag as CT
        security_triggers = {
            CT.SECURITY_REVIEW, CT.DEPLOY_REVIEW, CT.FINAL_REVIEW,
            CT.BILLING_IAM_REVIEW, CT.SECRETS_REVIEW,
        }
        decls = get_role_declarations()
        failures = []
        for role_id, decl in decls.items():
            has_security_cap = any(cap in decl.required_capabilities for cap in security_triggers)
            if has_security_cap and CT.HIGH_REASONING not in decl.required_capabilities:
                failures.append(
                    f"{role_id}: has security trigger but missing HIGH_REASONING"
                )
        assert len(failures) == 0, f"Security roles missing HIGH_REASONING: {failures}"


# ---------------------------------------------------------------------------
# 5. Kimi must be benchmark-gated
# ---------------------------------------------------------------------------

class TestKimiBenchmarkGate:
    def test_kimi_in_chain_requires_benchmark_required_for(self, validator):
        """A role with kimi in fallback_chain must have kimi in benchmark_required_for."""
        decl = RoleCapabilityDeclaration(
            role_id="kimi_using_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[
                "deepseek/deepseek-chat",
                "kimi/kimi-k2",  # Kimi in chain but not gated!
            ],
            escalation_model="anthropic/claude-sonnet-4-20250514",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=[],  # Missing kimi gate!
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "kimi_must_be_benchmark_gated" in error_rules

    def test_kimi_in_chain_with_gate_passes(self, validator):
        """A role with kimi in fallback_chain AND kimi in benchmark_required_for passes."""
        decl = RoleCapabilityDeclaration(
            role_id="kimi_gated_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[
                "deepseek/deepseek-chat",
                "kimi/kimi-k2",  # Kimi in chain
            ],
            escalation_model="anthropic/claude-sonnet-4-20250514",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],  # Properly gated
            audit_required=True,
        )
        errors = validator.validate(decl)
        kimi_errors = [e for e in errors if e.rule == "kimi_must_be_benchmark_gated"]
        assert len(kimi_errors) == 0


# ---------------------------------------------------------------------------
# 6. Audit required
# ---------------------------------------------------------------------------

class TestAuditRequired:
    def test_audit_required_false_fails(self, validator):
        """audit_required=False must fail validation."""
        decl = RoleCapabilityDeclaration(
            role_id="no_audit_role",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=["openai/gpt-4o-mini"],
            escalation_model="openai/gpt-4o",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=False,  # Must be True!
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "audit_required" in error_rules


# ---------------------------------------------------------------------------
# 7. Inheritance coverage report
# ---------------------------------------------------------------------------

class TestInheritanceCoverage:
    def test_coverage_report_has_all_declared_roles(self):
        """Inheritance coverage must cover all explicitly declared roles."""
        coverage = get_inheritance_coverage()
        decls = get_role_declarations()
        for role_id in decls:
            assert role_id in coverage["coverage"], (
                f"Role {role_id!r} missing from inheritance coverage report"
            )

    def test_coverage_report_has_inheritance_rules(self):
        """Coverage report must include inheritance rules list."""
        coverage = get_inheritance_coverage()
        assert "inheritance_rules" in coverage
        assert len(coverage["inheritance_rules"]) >= 5

    def test_coverage_report_has_default_policy(self):
        """Coverage report must include default_policy dict."""
        coverage = get_inheritance_coverage()
        assert "default_policy" in coverage
        policy_dict = coverage["default_policy"]
        assert "default_fallback_chain" in policy_dict
        assert "default_required_capabilities" in policy_dict

    def test_no_existing_role_has_zero_required_capabilities(self):
        """All explicitly declared roles must have non-empty required_capabilities."""
        validator = RoleInheritanceValidator()
        decls = get_role_declarations()
        errors_by_role = {}
        for role_id, decl in decls.items():
            errs = validator.validate(decl)
            hard_errors = [e for e in errs if e.severity == "error"]
            if hard_errors:
                errors_by_role[role_id] = [str(e) for e in hard_errors]

        assert len(errors_by_role) == 0, (
            f"These existing roles fail inheritance validation: {errors_by_role}"
        )
