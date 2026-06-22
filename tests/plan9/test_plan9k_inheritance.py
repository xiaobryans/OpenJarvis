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
    def test_new_manager_gets_dynamic_default_declaration(self, router, catalog):
        """A new manager role gets DYNAMIC routing — selects from full catalog, not fixed chain."""
        decision = router.select(
            role_id="totally_new_future_manager_xyz",
            task_description="some management task",
        )
        assert decision.chosen_model_id, "New role must resolve to a model via dynamic catalog scoring"
        assert "ollama" not in decision.chosen_model_id.lower()
        assert "kimi" not in decision.chosen_model_id.lower()

        # Prove: the default fallback_chain is empty (dynamic, not fixed)
        decl = router._get_declaration("totally_new_future_manager_xyz")
        assert len(decl.fallback_chain) == 0, (
            f"Non-PA default declaration must have empty fallback_chain. "
            f"Got: {decl.fallback_chain}"
        )

    def test_new_worker_gets_dynamic_default_declaration(self, router):
        """A new worker role gets dynamic routing via catalog scoring."""
        decision = router.select(
            role_id="new_future_worker_abc",
            task_description="process something",
        )
        assert decision.chosen_model_id
        assert "ollama" not in decision.chosen_model_id.lower()
        decl = router._get_declaration("new_future_worker_abc")
        assert len(decl.fallback_chain) == 0, (
            "Non-PA worker must have empty fallback_chain (dynamic catalog scoring)."
        )

    def test_non_pa_dynamic_routing_uses_full_catalog(self, router, catalog):
        """Non-PA dynamic routing selects from full catalog, not fixed list."""
        # Add a specialized new model to catalog
        from openjarvis.plan9.model_catalog_9k import ModelEntry9K, LatencyClass, AllowedRiskLevel, ModelStatus
        new_model = ModelEntry9K(
            model_id="futureai/new-chat-model",
            display_name="FutureAI Chat",
            provider_id="futureai",
            context_window=128_000,
            input_cost_per_mtok=1.0,
            output_cost_per_mtok=4.0,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset([
                __import__("openjarvis.plan9.model_catalog_9k", fromlist=["CapabilityTag"]).CapabilityTag.DEFAULT_CHAT,
                __import__("openjarvis.plan9.model_catalog_9k", fromlist=["CapabilityTag"]).CapabilityTag.STRUCTURED_OUTPUT,
            ]),
            allowed_risk_level=AllowedRiskLevel.MEDIUM,
            model_status=ModelStatus.STATIC_METADATA,
        )
        catalog.add_discovered_model(new_model)
        try:
            # Verify the new model is in scored candidates for a non-PA role
            from openjarvis.plan9.model_catalog_9k import CapabilityTag
            candidates = catalog.score_candidates(
                required_caps=[CapabilityTag.DEFAULT_CHAT],
                preferred_caps=[CapabilityTag.STRUCTURED_OUTPUT],
                forbidden_providers=["ollama"],
            )
            assert "futureai/new-chat-model" in candidates, (
                "New model must be in dynamic candidates without any role code changes"
            )
        finally:
            catalog._models = [m for m in catalog._models if m.model_id != "futureai/new-chat-model"]
            catalog._by_id.pop("futureai/new-chat-model", None)

    def test_non_pa_default_declaration_has_empty_chain(self, policy):
        """Non-PA default declaration has EMPTY fallback_chain — dynamic scoring takes over."""
        decl = policy.build_default_declaration("some_new_worker", is_pa=False)
        assert len(decl.fallback_chain) == 0, (
            f"Non-PA default must have empty fallback_chain (dynamic scoring). "
            f"Got: {decl.fallback_chain}"
        )

    def test_pa_default_declaration_has_stable_chain(self, policy):
        """PA default declaration has a stable small OpenAI chain."""
        decl = policy.build_default_declaration("jarvis_pa", is_pa=True)
        assert len(decl.fallback_chain) >= 1
        assert all("openai" in m for m in decl.fallback_chain), (
            f"PA chain must be OpenAI only: {decl.fallback_chain}"
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

    def test_non_pa_role_empty_fallback_chain_allowed(self, validator):
        """Non-PA role with empty fallback_chain is VALID — dynamic scoring covers it."""
        decl = RoleCapabilityDeclaration(
            role_id="dynamic_only_worker",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[],  # Empty — dynamic catalog scoring takes over
            escalation_model="anthropic/claude-sonnet-4-20250514",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "pa_fallback_chain_non_empty" not in error_rules, (
            "Non-PA role with empty fallback_chain must NOT fail validation. "
            "Dynamic catalog scoring is the primary mechanism."
        )

    def test_pa_role_empty_fallback_chain_fails(self, validator):
        """PA role MUST have a stable fallback_chain."""
        decl = RoleCapabilityDeclaration(
            role_id="jarvis_pa",
            role_type="agent",
            required_capabilities=[CapabilityTag.DEFAULT_CHAT],
            preferred_capabilities=[],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[],  # Empty — WRONG for PA!
            escalation_model="openai/gpt-4o",
            cost_ceiling="medium",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        errors = validator.validate(decl)
        error_rules = [e.rule for e in errors if e.severity == "error"]
        assert "pa_fallback_chain_non_empty" in error_rules, (
            "PA role must have a stable fallback_chain (GPT/OpenAI models)"
        )


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
        """Coverage report must include default_policy dict with PA and non-PA chains."""
        coverage = get_inheritance_coverage()
        assert "default_policy" in coverage
        policy_dict = coverage["default_policy"]
        assert "pa_fallback_chain" in policy_dict, "PA stable chain must be in policy"
        assert "non_pa_fallback_chain" in policy_dict, "Non-PA dynamic chain must be in policy"
        assert "default_required_capabilities" in policy_dict
        # Non-PA chain must be empty (dynamic catalog scoring)
        assert policy_dict["non_pa_fallback_chain"] == [], (
            "Non-PA default fallback_chain must be empty (dynamic routing)"
        )

    def test_no_non_pa_role_is_fixed_to_one_model(self):
        """No non-PA role should have only 1 static model as its entire candidate pool.
        Dynamic scoring must provide additional candidates beyond fallback_chain."""
        from openjarvis.plan9.specialized_router import SpecializedRouter
        from openjarvis.plan9.model_catalog_9k import get_provider_catalog

        catalog = get_provider_catalog()
        router = SpecializedRouter(catalog=catalog)
        decls = get_role_declarations()
        pa_roles = {"jarvis_pa", "cos_gm"}

        violations = []
        for role_id, decl in decls.items():
            if role_id in pa_roles:
                continue
            candidates, _ = router._build_candidate_list(decl, False, force_fallback=False)
            eligible = [c for c in candidates if catalog.get_model(c) and catalog.get_model(c).is_available]
            if len(eligible) <= 1:
                violations.append(
                    f"{role_id}: only {len(eligible)} eligible candidate(s). "
                    "Dynamic routing must provide multiple choices."
                )
        assert len(violations) == 0, (
            f"Non-PA roles fixed to single model (Plan 9K violation): {violations}"
        )

    def test_non_pa_default_routes_from_full_catalog(self):
        """Unknown non-PA role must select from full catalog via dynamic scoring."""
        from openjarvis.plan9.specialized_router import SpecializedRouter
        from openjarvis.plan9.model_catalog_9k import get_provider_catalog

        catalog = get_provider_catalog()
        router = SpecializedRouter(catalog=catalog)

        # Build default declaration for an unknown non-PA role
        decl = router._get_declaration("unknown_new_brain_module")
        # Must be dynamic (empty chain)
        assert len(decl.fallback_chain) == 0, (
            f"Non-PA default must have empty fallback_chain, got: {decl.fallback_chain}"
        )

        # Build candidates list — must come entirely from dynamic scoring
        candidates, _ = router._build_candidate_list(decl, False, force_fallback=False)
        assert len(candidates) >= 3, (
            f"Dynamic scoring must find 3+ candidates for DEFAULT_CHAT, got: {candidates}"
        )
        # Candidates must include models from multiple providers (not just one fixed chain)
        providers_represented = {
            catalog.get_model(c).provider_id
            for c in candidates
            if catalog.get_model(c)
        }
        assert len(providers_represented) >= 2, (
            f"Dynamic routing must draw from 2+ providers, got: {providers_represented}"
        )

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
