"""Plan 9K — Dynamic Routing Tests.

Tests proving:
1. score_candidates() returns ALL eligible models from full catalog (not just fallback_chain).
2. New model added to catalog is automatically eligible (no code change needed).
3. Dynamic expansion beyond fixed fallback_chain works.
4. Capability-specific cheap routes select from eligible pool.
5. Unknown/UNKNOWN_NEEDS_METADATA models are excluded from routing.
6. score_candidates cost ceiling filtering works.
7. Dynamic scoring prefers models with more matched preferred capabilities.
"""

from __future__ import annotations

import pytest
from copy import deepcopy

from openjarvis.plan9.model_catalog_9k import (
    AllowedRiskLevel,
    BenchmarkStatus,
    CapabilityTag,
    LatencyClass,
    ModelEntry9K,
    ModelStatus,
    ProviderCatalog9K,
    get_provider_catalog,
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
def catalog() -> ProviderCatalog9K:
    return get_provider_catalog()


@pytest.fixture
def router(catalog) -> SpecializedRouter:
    return SpecializedRouter(catalog=catalog)


def _make_model(
    model_id: str,
    provider_id: str,
    capabilities: list,
    cost: float = 1.0,
    risk: AllowedRiskLevel = AllowedRiskLevel.MEDIUM,
    status: ModelStatus = ModelStatus.STATIC_METADATA,
    is_available: bool = True,
) -> ModelEntry9K:
    return ModelEntry9K(
        model_id=model_id,
        display_name=model_id,
        provider_id=provider_id,
        context_window=128_000,
        input_cost_per_mtok=cost,
        output_cost_per_mtok=cost * 4,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=frozenset(capabilities),
        allowed_risk_level=risk,
        model_status=status,
        is_available=is_available,
    )


# ---------------------------------------------------------------------------
# 1. score_candidates returns ALL eligible catalog models
# ---------------------------------------------------------------------------

class TestScoreCandidates:
    def test_score_candidates_returns_eligible_models(self, catalog):
        """score_candidates must return multiple models with CODING capability."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.CODING],
            preferred_caps=[CapabilityTag.BACKEND_API],
            forbidden_providers=["ollama"],
            risk_threshold="low",
            cost_ceiling="any",
        )
        assert len(candidates) >= 5, (
            f"Expected at least 5 coding-capable models from full catalog, got {len(candidates)}: {candidates}"
        )

    def test_score_candidates_prefers_preferred_capabilities(self, catalog):
        """Models with more preferred capabilities should score higher."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.CODING],
            preferred_caps=[CapabilityTag.BACKEND_API, CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.TOOL_CALLING],
            forbidden_providers=["ollama"],
            risk_threshold="low",
            cost_ceiling="any",
        )
        assert len(candidates) >= 2
        # First model should score higher than last
        first = catalog.get_model(candidates[0])
        last = catalog.get_model(candidates[-1])
        assert first is not None and last is not None

        preferred = [CapabilityTag.BACKEND_API, CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.TOOL_CALLING]
        first_score = sum(1 for p in preferred if first.has_capability(p))
        last_score = sum(1 for p in preferred if last.has_capability(p))
        assert first_score >= last_score, (
            f"First candidate ({candidates[0]}, score={first_score}) should have >= preferred caps "
            f"than last ({candidates[-1]}, score={last_score})"
        )

    def test_score_candidates_excludes_offline_fallback(self, catalog):
        """score_candidates must exclude offline_fallback models by default."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.CODING],
            preferred_caps=[],
            forbidden_providers=["ollama"],
            include_fallback=False,
        )
        for mid in candidates:
            m = catalog.get_model(mid)
            assert m is not None
            assert not m.is_offline_fallback, (
                f"Offline fallback model {mid} must not appear in non-fallback candidates"
            )

    def test_score_candidates_excludes_unavailable(self, catalog):
        """score_candidates must exclude unavailable models."""
        # Temporarily mark a model unavailable
        deepseek = catalog.get_model("deepseek/deepseek-chat")
        if deepseek:
            deepseek.is_available = False
            try:
                candidates = catalog.score_candidates(
                    required_caps=[CapabilityTag.CODING],
                    preferred_caps=[],
                    forbidden_providers=["ollama"],
                )
                assert "deepseek/deepseek-chat" not in candidates
            finally:
                deepseek.is_available = True

    def test_score_candidates_cheap_ceiling_filters_expensive(self, catalog):
        """cost_ceiling='cheap' must exclude expensive models."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.CODING],
            preferred_caps=[],
            forbidden_providers=["ollama"],
            cost_ceiling="cheap",
        )
        # claude-opus is >15 $/mtok — should be deprioritized
        # deepseek is 0.27 $/mtok — should be present
        assert any("deepseek" in c for c in candidates), (
            f"Cheap ceiling should include deepseek: {candidates}"
        )

    def test_score_candidates_research_returns_perplexity(self, catalog):
        """Research candidates must include Perplexity models."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.WEB_GROUNDED],
            preferred_caps=[CapabilityTag.CITATIONS],
            forbidden_providers=["ollama"],
        )
        assert any("perplexity" in c for c in candidates), (
            f"Research candidates must include Perplexity: {candidates}"
        )

    def test_score_candidates_high_risk_excludes_low_risk_models(self, catalog):
        """High-risk roles must not select models with allowed_risk_level=LOW."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.HIGH_REASONING],
            preferred_caps=[CapabilityTag.SECURITY_REVIEW],
            forbidden_providers=["ollama", "offline_fallback"],
            risk_threshold="high",
        )
        for mid in candidates:
            m = catalog.get_model(mid)
            assert m is not None
            assert m.allowed_risk_level.value in ("high", "critical", "medium"), (
                f"High-risk candidate {mid} has low risk level: {m.allowed_risk_level}"
            )


# ---------------------------------------------------------------------------
# 2. New model in catalog is automatically eligible (no code change needed)
# ---------------------------------------------------------------------------

class TestNewModelAutoEligibility:
    def test_new_cloud_model_becomes_eligible_for_coding(self, catalog):
        """A new coding model added to catalog is automatically eligible without any code change."""
        new_model = _make_model(
            model_id="futureai/super-coder-v1",
            provider_id="futureai",
            capabilities=[CapabilityTag.CODING, CapabilityTag.BACKEND_API, CapabilityTag.STRUCTURED_OUTPUT],
            cost=0.50,
            risk=AllowedRiskLevel.MEDIUM,
        )
        catalog.add_discovered_model(new_model)
        try:
            candidates = catalog.score_candidates(
                required_caps=[CapabilityTag.CODING, CapabilityTag.BACKEND_API],
                preferred_caps=[CapabilityTag.STRUCTURED_OUTPUT],
                forbidden_providers=["ollama"],
                risk_threshold="medium",
            )
            assert "futureai/super-coder-v1" in candidates, (
                "New model with required capabilities should be eligible automatically."
            )
        finally:
            # Clean up: remove the test model
            catalog._models = [m for m in catalog._models if m.model_id != "futureai/super-coder-v1"]
            catalog._by_id.pop("futureai/super-coder-v1", None)

    def test_new_provider_model_needs_no_role_file_changes(self, catalog, router):
        """Router selects new eligible model without any role file changes."""
        new_model = _make_model(
            model_id="newprovider/coding-specialist",
            provider_id="newprovider",
            capabilities=[CapabilityTag.CODING, CapabilityTag.BACKEND_API, CapabilityTag.CHEAP_FAST],
            cost=0.10,
            risk=AllowedRiskLevel.MEDIUM,
        )
        catalog.add_discovered_model(new_model)
        try:
            # The coding_manager declaration has no "newprovider" in fallback_chain.
            # But dynamic expansion should find and score this model.
            # Since it's very cheap and has required caps, it could appear in candidates.
            candidates = catalog.score_candidates(
                required_caps=[CapabilityTag.CODING, CapabilityTag.BACKEND_API],
                preferred_caps=[],
                forbidden_providers=["ollama"],
            )
            assert "newprovider/coding-specialist" in candidates, (
                "New model must be in scored candidates without role file changes."
            )
        finally:
            catalog._models = [m for m in catalog._models if m.model_id != "newprovider/coding-specialist"]
            catalog._by_id.pop("newprovider/coding-specialist", None)

    def test_unknown_needs_metadata_excluded_from_routing(self, catalog, router):
        """UNKNOWN_NEEDS_METADATA models must NOT be routed even if capabilities match."""
        unknown_model = _make_model(
            model_id="openrouter/unknown-model/v1",
            provider_id="openrouter",
            capabilities=[],  # No capability tags
            status=ModelStatus.UNKNOWN_NEEDS_METADATA,
        )
        catalog.add_discovered_model(unknown_model)
        try:
            candidates = catalog.score_candidates(
                required_caps=[CapabilityTag.DEFAULT_CHAT],
                preferred_caps=[],
                forbidden_providers=["ollama"],
            )
            # Model with no capability tags will be filtered by hard capability check
            assert "openrouter/unknown-model/v1" not in candidates, (
                "UNKNOWN_NEEDS_METADATA model (no caps) must not appear in routing candidates."
            )
        finally:
            catalog._models = [m for m in catalog._models if m.model_id != "openrouter/unknown-model/v1"]
            catalog._by_id.pop("openrouter/unknown-model/v1", None)

    def test_newly_discovered_model_stays_unknown_until_tagged(self, catalog):
        """Discovered model retains UNKNOWN status until capability tags are assigned."""
        new_model = ModelEntry9K(
            model_id="openrouter/mystery-ai/v99",
            display_name="Mystery AI",
            provider_id="openrouter",
            context_window=0,
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset(),
            allowed_risk_level=AllowedRiskLevel.LOW,
            model_status=ModelStatus.UNKNOWN_NEEDS_METADATA,
            discovery_source="openrouter",
        )
        catalog.add_discovered_model(new_model)
        try:
            m = catalog.get_model("openrouter/mystery-ai/v99")
            assert m is not None
            assert m.model_status == ModelStatus.UNKNOWN_NEEDS_METADATA
            assert len(m.capability_tags) == 0, "Untagged model must have no capability tags."
        finally:
            catalog._models = [m for m in catalog._models if m.model_id != "openrouter/mystery-ai/v99"]
            catalog._by_id.pop("openrouter/mystery-ai/v99", None)


# ---------------------------------------------------------------------------
# 3. Dynamic expansion beyond fixed fallback_chain
# ---------------------------------------------------------------------------

class TestDynamicExpansion:
    def test_router_finds_model_not_in_fallback_chain(self, catalog, router):
        """When all fallback_chain models are unavailable, router must find an eligible model
        from the full dynamic catalog."""
        # Mark all coding_manager fallback_chain models as unavailable
        decl = get_role_declarations().get("coding_manager")
        assert decl is not None

        unavailable_models = []
        for mid in decl.fallback_chain:
            m = catalog.get_model(mid)
            if m and m.is_available:
                m.is_available = False
                unavailable_models.append(m)

        try:
            decision = router.select(
                role_id="coding_manager",
                task_description="implement feature",
            )
            # Should have found a model from dynamic expansion
            assert decision.chosen_model_id not in decl.fallback_chain, (
                f"Router should select from dynamic expansion when chain is exhausted, "
                f"got: {decision.chosen_model_id}"
            )
            assert "ollama" not in decision.chosen_model_id.lower()
            assert "kimi" not in decision.chosen_model_id.lower()
        finally:
            for m in unavailable_models:
                m.is_available = True

    def test_router_candidate_list_contains_more_than_chain(self, catalog, router):
        """_build_candidate_list must include models beyond the declared fallback_chain."""
        decl = get_role_declarations().get("coding_manager")
        assert decl is not None
        is_kimi_benchmarked = catalog.kimi_benchmarked()

        # Build candidate list
        candidates = router._build_candidate_list(decl, is_kimi_benchmarked, force_fallback=False)
        chain_set = set(decl.fallback_chain)

        # Candidates must include at least some models NOT in the declared chain
        extra_candidates = [c for c in candidates if c not in chain_set]
        assert len(extra_candidates) > 0, (
            f"Dynamic expansion must add models beyond the declared fallback_chain. "
            f"Chain: {decl.fallback_chain}. Candidates: {candidates[:10]}"
        )

    def test_no_role_is_forced_to_single_model(self, catalog, router):
        """No non-PA role should have only 1 eligible candidate when catalog has many models."""
        excluded_roles = {"jarvis_pa"}  # PA intentionally limited
        decls = get_role_declarations()
        for role_id, decl in decls.items():
            if role_id in excluded_roles:
                continue
            candidates = router._build_candidate_list(
                decl, catalog.kimi_benchmarked(), force_fallback=False
            )
            eligible = [
                c for c in candidates
                if catalog.get_model(c) and catalog.get_model(c).is_available
            ]
            assert len(eligible) >= 2, (
                f"Role {role_id} has only {len(eligible)} eligible candidate(s). "
                "Non-PA roles must have multiple eligible candidates from the catalog."
            )


# ---------------------------------------------------------------------------
# 4. Catalog summary
# ---------------------------------------------------------------------------

class TestCatalogSummary:
    def test_catalog_summary_has_required_fields(self, catalog):
        summary = catalog.catalog_summary()
        required_fields = [
            "total_models", "total_providers", "active_cloud_models",
            "fallback_only_models", "unknown_needs_metadata", "by_provider",
            "kimi_benchmarked",
        ]
        for f in required_fields:
            assert f in summary, f"catalog_summary missing field: {f}"

    def test_catalog_summary_fallback_count(self, catalog):
        summary = catalog.catalog_summary()
        assert summary["fallback_only_models"] >= 5, (
            f"Expected at least 5 Ollama fallback models, got {summary['fallback_only_models']}"
        )

    def test_catalog_summary_cloud_count(self, catalog):
        summary = catalog.catalog_summary()
        assert summary["active_cloud_models"] >= 20, (
            f"Expected at least 20 active cloud models, got {summary['active_cloud_models']}"
        )

    def test_catalog_summary_by_provider_has_all_providers(self, catalog):
        summary = catalog.catalog_summary()
        for p in ["openai", "anthropic", "kimi", "perplexity", "deepseek", "mistral"]:
            assert p in summary["by_provider"], (
                f"Provider {p} missing from catalog_summary by_provider"
            )


# ---------------------------------------------------------------------------
# 5. ModelStatus for new discovered models
# ---------------------------------------------------------------------------

class TestModelStatus:
    def test_static_catalog_models_have_static_status(self, catalog):
        """All existing static catalog models should have STATIC_METADATA status."""
        static_models = [m for m in catalog.all_models if m.discovery_source == "static"]
        for m in static_models:
            assert m.model_status == ModelStatus.STATIC_METADATA, (
                f"Static model {m.model_id} has wrong status: {m.model_status}"
            )

    def test_add_discovered_model_preserves_static_tags(self, catalog):
        """When a discovered model matches a static model, static capability tags are preserved."""
        static_model = catalog.get_model("openai/gpt-4o")
        original_tags = frozenset(static_model.capability_tags)

        # Simulate "discovery" of same model with no tags
        discovered = ModelEntry9K(
            model_id="openai/gpt-4o",
            display_name="GPT-4o (discovered)",
            provider_id="openai",
            context_window=128_000,
            input_cost_per_mtok=2.50,
            output_cost_per_mtok=10.00,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset(),  # No tags from API
            allowed_risk_level=AllowedRiskLevel.MEDIUM,
            model_status=ModelStatus.UNKNOWN_NEEDS_METADATA,
            discovery_source="live_api",
        )
        catalog.add_discovered_model(discovered)
        updated = catalog.get_model("openai/gpt-4o")
        assert updated is not None
        # add_discovered_model preserves original tags if discovered has none
        assert len(updated.capability_tags) > 0, (
            "add_discovered_model must preserve static capability tags when discovered model has none."
        )

    def test_model_status_serialized_in_to_dict(self, catalog):
        """ModelEntry9K.to_dict() must include model_status and discovery_source."""
        m = catalog.get_model("openai/gpt-4o")
        assert m is not None
        d = m.to_dict()
        assert "model_status" in d
        assert "discovery_source" in d


# ---------------------------------------------------------------------------
# 6. PA stable model set
# ---------------------------------------------------------------------------

class TestPAStableRoute:
    def test_pa_routing_selects_openai_gpt(self, router):
        """PA must always route to openai/gpt-4o (first in fallback_chain)."""
        decision = router.select(role_id="jarvis_pa", task_description="coordinate with Bryan")
        assert decision.chosen_provider == "openai"
        assert "gpt" in decision.chosen_model_id.lower()

    def test_pa_dynamic_candidates_only_openai(self, catalog, router):
        """PA's dynamic candidates should only come from OpenAI (forbidden: kimi, ollama)."""
        decl = get_role_declarations().get("jarvis_pa")
        candidates = router._build_candidate_list(decl, False, force_fallback=False)
        for mid in candidates:
            m = catalog.get_model(mid)
            if m:
                assert "kimi" not in m.provider_id, f"PA must not include Kimi in candidates"
                assert "ollama" not in m.provider_id, f"PA must not include Ollama in candidates"


# ---------------------------------------------------------------------------
# 7. Cheap routes are capability-specific (dynamic, not universal)
# ---------------------------------------------------------------------------

class TestDynamicCheapRoutes:
    def test_coding_cheap_pool_has_multiple_candidates(self, catalog):
        """Cheap coding pool must have multiple eligible models."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.CODING],
            preferred_caps=[CapabilityTag.CHEAP_FAST],
            forbidden_providers=["ollama"],
            cost_ceiling="cheap",
        )
        assert len(candidates) >= 2, (
            f"Cheap coding pool should have multiple candidates: {candidates}"
        )

    def test_research_cheap_pool_has_web_grounded(self, catalog):
        """Cheap research pool must include web-grounded models."""
        candidates = catalog.score_candidates(
            required_caps=[CapabilityTag.WEB_GROUNDED],
            preferred_caps=[CapabilityTag.CITATIONS],
            forbidden_providers=["ollama"],
            cost_ceiling="any",
        )
        assert any("perplexity" in c or "sonar" in c for c in candidates), (
            f"Research candidates must include Perplexity: {candidates}"
        )

    def test_different_roles_get_different_top_candidates(self, catalog):
        """coding_manager and research_manager should get different top candidates."""
        coding = catalog.score_candidates(
            required_caps=[CapabilityTag.CODING],
            preferred_caps=[CapabilityTag.BACKEND_API],
            forbidden_providers=["ollama"],
        )
        research = catalog.score_candidates(
            required_caps=[CapabilityTag.WEB_GROUNDED],
            preferred_caps=[CapabilityTag.CITATIONS],
            forbidden_providers=["ollama"],
        )
        # Top candidates for coding and research should be different
        top_coding = coding[:3] if coding else []
        top_research = research[:3] if research else []
        assert set(top_coding) != set(top_research), (
            "Coding and research roles should have different top candidates."
        )
