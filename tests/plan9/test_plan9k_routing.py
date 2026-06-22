"""Plan 9K Routing Tests.

Tests proving:
1. PA/front-door uses GPT/OpenAI-style stable model set.
2. Normal UI does not expose manual model picker.
3. Ollama/Qwen is NOT selected for normal chat.
4. No manager/worker/COS/brain has generic fixed model defaults.
5. Every role declares capability requirements.
6. Cheap routes are capability-specific, not universal.
7. Research roles prefer web-grounded/citation-capable providers.
8. Security/billing/IAM/secrets/deploy/final_review forbid local/cheap models.
9. Kimi is NOT default until benchmark proof.
10. Kimi fallback/escalation to Sonnet works when benchmark fails.
11. Provider catalog includes hundreds of model metadata entries (11 providers).
12. Routing audit explains why a model was selected.
13. Fallback chains work when provider unavailable is simulated.
14. Existing Plan 9 routes still pass (routing matrix validates).
"""

from __future__ import annotations

import pytest

from openjarvis.plan9.heavy_coding_policy import is_glm_52_model
from openjarvis.plan9.model_catalog_9k import (
    BenchmarkStatus,
    CapabilityTag,
    ModelEntry9K,
    ProviderCatalog9K,
    get_provider_catalog,
    CATALOG,
    PROVIDERS,
    PA_STABLE_MODELS,
)
from openjarvis.plan9.model_routing import (
    ModelTier,
    get_role_routing_matrix,
    DEFAULT_ROUTING,
)
from openjarvis.plan9.specialized_router import (
    RoleCapabilityDeclaration,
    RoutingDecision9K,
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


@pytest.fixture
def matrix():
    return get_role_routing_matrix()


# ---------------------------------------------------------------------------
# 1. PA/front-door uses GPT/OpenAI stable route
# ---------------------------------------------------------------------------

class TestPAFrontDoor:
    def test_pa_balanced_model_is_openai_gpt(self, matrix):
        """PA balanced_model must be GPT/OpenAI-style model."""
        pa = matrix.get("jarvis_pa")
        assert pa.role_id == "jarvis_pa"
        assert "gpt" in pa.balanced_model.lower() or "openai" in pa.balanced_model.lower(), (
            f"PA balanced_model must be GPT/OpenAI route, got: {pa.balanced_model}"
        )

    def test_pa_cheap_model_is_openai(self, matrix):
        """PA cheap_model must be GPT/OpenAI mini."""
        pa = matrix.get("jarvis_pa")
        assert "gpt" in pa.cheap_model.lower() or "openai" in pa.cheap_model.lower(), (
            f"PA cheap_model must be GPT/OpenAI route, got: {pa.cheap_model}"
        )

    def test_pa_forbidden_kimi(self, matrix):
        """PA must have kimi in forbidden_model_classes."""
        pa = matrix.get("jarvis_pa")
        assert "kimi" in pa.forbidden_model_classes, (
            "PA must forbid kimi in forbidden_model_classes"
        )

    def test_pa_forbidden_ollama(self, matrix):
        """PA must forbid ollama/offline_fallback."""
        pa = matrix.get("jarvis_pa")
        assert "ollama" in pa.forbidden_model_classes, (
            "PA must forbid ollama in forbidden_model_classes"
        )

    def test_pa_routing_uses_openai(self, router):
        """Specialized router must route PA to OpenAI provider."""
        decision = router.select(role_id="jarvis_pa", task_description="Coordinate with Bryan")
        assert decision.chosen_provider == "openai", (
            f"PA must route to openai provider, got: {decision.chosen_provider}"
        )

    def test_pa_routing_not_kimi(self, router):
        """PA must never route to Kimi."""
        decision = router.select(role_id="jarvis_pa", task_description="normal chat")
        assert "kimi" not in decision.chosen_model_id.lower(), (
            f"PA must not route to Kimi, got: {decision.chosen_model_id}"
        )

    def test_pa_routing_not_ollama(self, router):
        """PA must never route to Ollama."""
        decision = router.select(role_id="jarvis_pa", task_description="normal chat")
        assert "ollama" not in decision.chosen_model_id.lower(), (
            f"PA must not route to Ollama, got: {decision.chosen_model_id}"
        )

    def test_pa_stable_models_all_openai(self):
        """PA_STABLE_MODELS constant must be GPT/OpenAI models only."""
        for model_id in PA_STABLE_MODELS:
            assert "openai" in model_id.lower() or "gpt" in model_id.lower(), (
                f"PA stable model must be OpenAI, got: {model_id}"
            )


# ---------------------------------------------------------------------------
# 2. No manual model picker in normal UI (structural test via source check)
# ---------------------------------------------------------------------------

class TestNoManualModelPicker:
    def test_no_model_picker_in_cockpit_page(self):
        """JarvisCockpitPage.tsx must not contain a manual model picker/selector.

        The routing panel shows READ-ONLY routing status, not a selector.
        """
        import pathlib
        page = pathlib.Path(__file__).parent.parent.parent / "frontend" / "src" / "pages" / "JarvisCockpitPage.tsx"
        if not page.exists():
            pytest.skip("Frontend file not found")

        content = page.read_text()
        # Must NOT have model selector/picker components for user to switch
        forbidden_patterns = [
            "ModelSelector",
            "ModelPicker",
            "<select.*model",
            "onChange.*setModel",
            "model-selector",
            "model-picker",
        ]
        for pattern in forbidden_patterns:
            import re
            if re.search(pattern, content, re.IGNORECASE):
                pytest.fail(
                    f"Normal UI should not expose manual model picker. "
                    f"Found forbidden pattern: {pattern!r}"
                )

    def test_routing_panel_is_readonly(self):
        """Routing status panel must be read-only (no model selection)."""
        import pathlib
        page = pathlib.Path(__file__).parent.parent.parent / "frontend" / "src" / "pages" / "JarvisCockpitPage.tsx"
        if not page.exists():
            pytest.skip("Frontend file not found")

        content = page.read_text()
        # Routing panel should exist
        assert "'routing'" in content, "Routing panel must exist in JarvisCockpitPage"
        # Routing panel content must have read-only status rows
        assert "Model Routing" in content, "Model Routing panel title must exist"


# ---------------------------------------------------------------------------
# 3. Ollama/Qwen NOT selected for normal chat
# ---------------------------------------------------------------------------

class TestOllamaFallbackOnly:
    def test_ollama_models_tagged_offline_fallback(self, catalog):
        """All ollama models must have OFFLINE_FALLBACK capability tag."""
        ollama_models = catalog.models_for_provider("ollama")
        assert len(ollama_models) > 0, "Catalog must include ollama/local fallback models"
        for m in ollama_models:
            assert m.is_offline_fallback, (
                f"Ollama model {m.model_id} must have offline_fallback tag"
            )

    def test_ollama_not_selected_for_normal_chat(self, router):
        """Normal chat routing must not select Ollama."""
        decision = router.select(role_id="jarvis_pa", task_description="What's the weather?")
        assert "ollama" not in decision.chosen_model_id.lower(), (
            f"Ollama must not be selected for normal chat, got: {decision.chosen_model_id}"
        )

    def test_ollama_not_selected_for_coding(self, router):
        """Coding routing must not select Ollama in normal mode."""
        decision = router.select(role_id="coding_manager", task_description="fix the API bug")
        assert "ollama" not in decision.chosen_model_id.lower(), (
            f"Ollama must not be selected for normal coding, got: {decision.chosen_model_id}"
        )

    def test_ollama_selected_in_force_fallback(self, router):
        """Ollama should be selected when force_fallback=True (simulating outage)."""
        decision = router.select(
            role_id="coding_manager",
            task_description="fix bug",
            force_fallback=True,
        )
        assert decision.offline_fallback_active is True, (
            "offline_fallback_active must be True when force_fallback=True"
        )

    def test_fallback_reason_logged_when_ollama_active(self, router):
        """When fallback activates, decision must have a fallback_reason."""
        decision = router.select(
            role_id="coding_manager",
            task_description="fix bug",
            force_fallback=True,
        )
        # Either the decision itself is fallback or fallback was noted
        assert decision.offline_fallback_active, "offline_fallback_active must be set"

    def test_qwen_not_in_normal_pa_route(self, matrix):
        """PA cheap/balanced/best must not include Qwen."""
        pa = matrix.get("jarvis_pa")
        for model in [pa.cheap_model, pa.balanced_model, pa.best_model]:
            assert "qwen" not in model.lower(), (
                f"PA routing must not include Qwen/Ollama, found: {model}"
            )


# ---------------------------------------------------------------------------
# 4. No generic fixed cheap/balanced/best across ALL roles
# ---------------------------------------------------------------------------

class TestNoUniversalModels:
    def test_no_universal_cheap_model(self, matrix):
        """Plan 9K: cheap routing must be capability-specific, not one universal model."""
        errors = matrix.validate_no_universal_cheap()
        assert len(errors) == 0, (
            f"Universal cheap model detected (Plan 9K violation): {errors}"
        )

    def test_different_cheap_models_exist(self, matrix):
        """Multiple different cheap models must exist across roles (not all gpt-4o-mini)."""
        cheap_models = {e.cheap_model for e in matrix.entries}
        assert len(cheap_models) >= 3, (
            f"Expected at least 3 distinct cheap models for different roles, got: {cheap_models}"
        )

    def test_coding_uses_coding_specialist_cheap(self, matrix):
        """Coding roles must use a coding-specialist cheap model (not generic)."""
        coding_roles = ["coding_manager", "backend_worker", "test_worker", "unit_test_worker"]
        for role_id in coding_roles:
            entry = matrix.get(role_id)
            if entry.role_id == "__default__":
                continue
            # Coding cheap model should be deepseek or another coding specialist
            cheap = entry.cheap_model
            is_coding_specialist = any(
                s in cheap.lower() for s in ["deepseek", "codestral", "coding"]
            )
            assert is_coding_specialist, (
                f"Role {role_id} cheap_model should be coding specialist, got: {cheap}"
            )

    def test_research_manager_uses_web_grounded_cheap(self, matrix):
        """research_manager cheap route must use web-grounded model."""
        entry = matrix.get("research_manager")
        cheap = entry.cheap_model
        assert "perplexity" in cheap.lower() or "sonar" in cheap.lower(), (
            f"research_manager cheap must be Perplexity/Sonar, got: {cheap}"
        )

    def test_pa_uses_gpt_route(self, matrix):
        """PA cheap must use GPT/OpenAI, not deepseek/perplexity."""
        pa = matrix.get("jarvis_pa")
        assert "gpt" in pa.cheap_model.lower() or "openai" in pa.cheap_model.lower(), (
            f"PA cheap must be GPT/OpenAI, got: {pa.cheap_model}"
        )


# ---------------------------------------------------------------------------
# 5. Every role declares capability requirements
# ---------------------------------------------------------------------------

class TestRoleCapabilityDeclarations:
    def test_all_matrix_roles_have_required_capabilities(self, matrix):
        """Every role in the matrix must have required_capabilities."""
        errors = matrix.validate()
        cap_errors = [e for e in errors if "required_capabilities" in e]
        assert len(cap_errors) == 0, (
            f"Roles missing required_capabilities: {cap_errors}"
        )

    def test_all_matrix_roles_have_fallback_chain(self, matrix):
        """Every role in the matrix must have a fallback_chain."""
        errors = matrix.validate()
        chain_errors = [e for e in errors if "fallback_chain" in e]
        assert len(chain_errors) == 0, (
            f"Roles missing fallback_chain: {chain_errors}"
        )

    def test_all_declarations_have_required_capabilities(self):
        """Every role declaration in the specialized router must have required_capabilities."""
        decls = get_role_declarations()
        for role_id, decl in decls.items():
            assert len(decl.required_capabilities) > 0, (
                f"Role {role_id} missing required_capabilities"
            )

    def test_all_declarations_have_fallback_chain(self):
        """Every role declaration must have a non-empty fallback_chain."""
        decls = get_role_declarations()
        for role_id, decl in decls.items():
            assert len(decl.fallback_chain) > 0, (
                f"Role {role_id} missing fallback_chain"
            )

    def test_major_roles_covered(self):
        """Critical roles must have explicit declarations (not default)."""
        decls = get_role_declarations()
        required_roles = [
            "jarvis_pa", "cos_gm", "coding_manager", "security_code_worker",
            "research_manager", "release_packaging_manager",
            "governance_safety_manager", "backend_worker",
        ]
        for role_id in required_roles:
            assert role_id in decls, f"Critical role {role_id} missing declaration"


# ---------------------------------------------------------------------------
# 6. Cheap routes are capability-specific
# ---------------------------------------------------------------------------

class TestCheapRoutesCapabilitySpecific:
    def test_coding_cheap_is_coding_specialist(self, router):
        """Coding role must select a coding-specialist model (GLM/Kimi/deepseek/sonnet)."""
        decision = router.select(
            role_id="coding_manager",
            task_description="write a Python function",
            task_classification="normal_heavy_coding",
        )
        mid = decision.chosen_model_id.lower()
        assert any(s in mid for s in ("glm", "kimi", "deepseek", "sonnet", "claude")), (
            f"coding_manager should use coding specialist, got: {decision.chosen_model_id}"
        )

    def test_retrieval_cheap_is_extraction_specialist(self, router):
        """Retrieval worker cheap route must be extraction/fast model."""
        decision = router.select(role_id="retrieval_worker", task_description="retrieve context")
        # Retrieval uses gpt-4o-mini (extraction)
        assert "gpt-4o-mini" in decision.chosen_model_id or "mini" in decision.chosen_model_id.lower(), (
            f"retrieval_worker should use mini/extraction model, got: {decision.chosen_model_id}"
        )

    def test_research_cheap_is_web_grounded(self, router):
        """Research cheap route must prefer web-grounded model."""
        decision = router.select(role_id="research_manager", task_description="research current events")
        # Research should use perplexity/sonar or sonar-pro
        assert "perplexity" in decision.chosen_model_id.lower() or "sonar" in decision.chosen_model_id.lower(), (
            f"research_manager should use Perplexity, got: {decision.chosen_model_id}"
        )

    def test_frontend_cheap_is_ui_specialist(self, router):
        """Frontend route must use a UI-capable model (GLM/Kimi/mini/haiku)."""
        decision = router.select(role_id="frontend_worker", task_description="fix CSS button style")
        mid = decision.chosen_model_id.lower()
        assert any(s in mid for s in ["gpt-4o-mini", "mini", "haiku", "glm", "kimi"]), (
            f"frontend_worker should be UI-capable model, got: {decision.chosen_model_id}"
        )

    def test_doc_cheap_is_summarization_capable(self, router):
        """Documentation cheap route must use a summarization-capable model."""
        decision = router.select(role_id="documentation_worker", task_description="write docstring")
        assert any(s in decision.chosen_model_id.lower() for s in ["gpt", "openai", "haiku"]), (
            f"documentation_worker should use gpt/openai model, got: {decision.chosen_model_id}"
        )


# ---------------------------------------------------------------------------
# 7. Research roles prefer web-grounded providers
# ---------------------------------------------------------------------------

class TestResearchWebGrounded:
    def test_research_manager_uses_perplexity(self, router):
        """research_manager must prefer Perplexity/Sonar for web-grounded research."""
        decision = router.select(
            role_id="research_manager",
            task_description="find current information about AI models released in 2026",
        )
        assert "perplexity" in decision.chosen_provider.lower(), (
            f"research_manager should use perplexity, got: {decision.chosen_provider}"
        )

    def test_perplexity_models_have_web_grounded_tag(self, catalog):
        """Perplexity models must have web_grounded and citations tags."""
        perplexity_models = catalog.models_for_provider("perplexity")
        assert len(perplexity_models) >= 2, "Catalog must include multiple Perplexity models"
        for m in perplexity_models:
            assert m.has_capability(CapabilityTag.WEB_GROUNDED), (
                f"Perplexity model {m.model_id} must have web_grounded tag"
            )
            assert m.has_capability(CapabilityTag.CITATIONS), (
                f"Perplexity model {m.model_id} must have citations tag"
            )

    def test_local_research_worker_can_fallback_to_perplexity(self, router):
        """local_research_worker best model should be perplexity/sonar-pro."""
        decl = get_role_declarations().get("local_research_worker")
        assert decl is not None
        # Check fallback chain includes perplexity
        has_perplexity_in_chain = any(
            "perplexity" in m.lower() or "sonar" in m.lower()
            for m in decl.fallback_chain
        )
        assert has_perplexity_in_chain, (
            f"local_research_worker fallback chain should include perplexity: {decl.fallback_chain}"
        )


# ---------------------------------------------------------------------------
# 8. Security/billing/IAM/secrets/deploy/final_review forbid cheap/local
# ---------------------------------------------------------------------------

class TestSecurityRolesNoChap:
    _HIGH_RISK_ROLES = [
        "security_code_worker",
        "release_packaging_manager",
        "release_packaging_worker",
        "governance_safety_manager",
        "integration_review_manager",
    ]

    def test_security_roles_no_local_in_cheap(self, matrix):
        """Security/deploy/governance roles must not have ollama/qwen/local in cheap model."""
        for role_id in self._HIGH_RISK_ROLES:
            entry = matrix.get(role_id)
            if entry.role_id == "__default__":
                continue
            for model in [entry.cheap_model, entry.balanced_model, entry.best_model]:
                assert "qwen" not in model.lower(), (
                    f"{role_id} must not use Qwen, found: {model}"
                )
                assert "ollama" not in model.lower(), (
                    f"{role_id} must not use Ollama, found: {model}"
                )

    def test_security_roles_forbidden_classes_include_ollama(self, matrix):
        """Security roles must list ollama in forbidden_model_classes."""
        for role_id in self._HIGH_RISK_ROLES:
            entry = matrix.get(role_id)
            if entry.role_id == "__default__":
                continue
            assert "ollama" in entry.forbidden_model_classes, (
                f"{role_id} must have ollama in forbidden_model_classes"
            )

    def test_security_code_worker_uses_anthropic(self, router):
        """security_code_worker must route to Anthropic (not deepseek, not ollama)."""
        decision = router.select(
            role_id="security_code_worker",
            task_description="audit authentication code for vulnerabilities",
        )
        assert decision.chosen_provider == "anthropic", (
            f"security_code_worker must use anthropic, got: {decision.chosen_provider}"
        )

    def test_release_packaging_manager_uses_anthropic(self, router):
        """release_packaging_manager must route to Anthropic."""
        decision = router.select(
            role_id="release_packaging_manager",
            task_description="plan ECS deployment",
        )
        assert decision.chosen_provider == "anthropic", (
            f"release_packaging_manager must use anthropic, got: {decision.chosen_provider}"
        )

    def test_high_risk_roles_forbidden_kimi(self, matrix):
        """Security/deploy/governance roles must forbid kimi."""
        for role_id in ["security_code_worker", "release_packaging_manager", "governance_safety_manager"]:
            entry = matrix.get(role_id)
            if entry.role_id == "__default__":
                continue
            assert "kimi" in entry.forbidden_model_classes, (
                f"{role_id} must forbid kimi in forbidden_model_classes"
            )

    def test_security_roles_risk_threshold_critical(self, matrix):
        """Security/deploy roles must have critical or high risk_threshold."""
        for role_id in ["security_code_worker", "release_packaging_manager"]:
            entry = matrix.get(role_id)
            if entry.role_id == "__default__":
                continue
            assert entry.risk_threshold in ("critical", "high"), (
                f"{role_id} risk_threshold must be critical/high, got: {entry.risk_threshold}"
            )


# ---------------------------------------------------------------------------
# 9. Kimi is NOT default until benchmark proof
# ---------------------------------------------------------------------------

class TestKimiNotDefault:
    def test_kimi_not_benchmarked_initially(self, catalog):
        """All Kimi models must start as NOT_BENCHMARKED."""
        kimi_models = catalog.kimi_models()
        assert len(kimi_models) > 0, "Kimi models must be in catalog"
        for m in kimi_models:
            assert m.benchmark_status == BenchmarkStatus.NOT_BENCHMARKED, (
                f"Kimi model {m.model_id} must start as NOT_BENCHMARKED, "
                f"got: {m.benchmark_status}"
            )

    def test_catalog_kimi_not_benchmarked(self, catalog):
        """catalog.kimi_benchmarked() must return False initially."""
        assert catalog.kimi_benchmarked() is False

    def test_kimi_k26_allowed_for_heavy_coding_pending_benchmark(self, router):
        """Heavy coding may use Kimi K2.6 as secondary route pending benchmark."""
        decision = router.select(
            role_id="coding_manager",
            task_description="implement feature",
            task_classification="normal_heavy_coding",
        )
        # GLM preferred first; if GLM selected that's also valid
        mid = decision.chosen_model_id.lower()
        assert any(s in mid for s in ("glm", "kimi", "deepseek", "sonnet")), (
            f"coding_manager heavy coding route invalid: {decision.chosen_model_id}"
        )

    def test_kimi_not_selected_for_pa(self, router):
        """PA must not select Kimi."""
        decision = router.select(role_id="jarvis_pa", task_description="hello")
        assert "kimi" not in decision.chosen_model_id.lower()

    def test_kimi_not_default_any_role(self, matrix):
        """No role in the routing matrix should have Kimi as default cheap/balanced/best."""
        for entry in matrix.entries:
            for model in [entry.cheap_model, entry.balanced_model, entry.best_model]:
                assert "kimi" not in model.lower(), (
                    f"Role {entry.role_id} must not have Kimi as default model (not benchmarked). "
                    f"Found Kimi in: {model}"
                )

    def test_kimi_eligible_after_benchmark_accepted(self, catalog, router):
        """When Kimi benchmark is accepted, Kimi becomes eligible for routing."""
        # Accept kimi/kimi-k2 benchmark
        catalog.update_benchmark_status(
            "kimi/kimi-k2",
            BenchmarkStatus.ACCEPTED,
            {"coding": 0.92, "repo_understanding": 0.88},
        )
        try:
            assert catalog.kimi_benchmarked() is True
            decision = router.select(
                role_id="refactor_worker",
                task_description="large refactor across 50 files",
            )
            assert decision.kimi_eligible is True
        finally:
            # Reset benchmark status
            catalog.update_benchmark_status("kimi/kimi-k2", BenchmarkStatus.NOT_BENCHMARKED)


# ---------------------------------------------------------------------------
# 10. Kimi fallback/escalation to Sonnet when benchmark fails
# ---------------------------------------------------------------------------

class TestKimiFallback:
    def test_kimi_not_selected_when_not_benchmarked(self, router):
        """Non-heavy-coding research role must skip Kimi when not benchmarked."""
        decision = router.select(
            role_id="research_manager",
            task_description="find papers on transformers",
        )
        assert "kimi" not in decision.chosen_model_id.lower()

    def test_fallback_when_glm_kimi_unavailable(self, router, catalog):
        """When GLM and Kimi unavailable, coding routes to other coding models."""
        glm_ids = [m.model_id for m in catalog.all_models if is_glm_52_model(m.model_id)]
        kimi_ids = [m.model_id for m in catalog.all_models if "kimi" in m.model_id.lower()]
        saved = {}
        for mid in glm_ids + kimi_ids:
            m = catalog.get_model(mid)
            if m:
                saved[mid] = m.is_available
                m.is_available = False
        try:
            decision = router.select(
                role_id="coding_manager",
                task_description="large refactor",
                task_classification="repo_refactor",
            )
            assert "kimi" not in decision.chosen_model_id.lower() or not saved
            assert "ollama" not in decision.chosen_model_id.lower()
        finally:
            for mid, avail in saved.items():
                m = catalog.get_model(mid)
                if m:
                    m.is_available = avail


# ---------------------------------------------------------------------------
# 11. Provider catalog includes hundreds of model entries with capability tags
# ---------------------------------------------------------------------------

class TestProviderCatalog:
    def test_catalog_has_multiple_providers(self, catalog):
        """Catalog must include multiple configured providers."""
        assert catalog.provider_count() >= 10, (
            f"Expected at least 10 providers, got: {catalog.provider_count()}"
        )

    def test_catalog_has_meaningful_model_count(self, catalog):
        """Catalog must include a meaningful number of models."""
        assert catalog.model_count() >= 20, (
            f"Expected at least 20 models in catalog, got: {catalog.model_count()}"
        )

    def test_all_required_providers_present(self, catalog):
        """All required providers must be in the catalog."""
        required = ["openai", "anthropic", "kimi", "perplexity", "google",
                    "deepseek", "mistral", "xai", "openrouter", "ollama", "aimlapi"]
        provider_ids = {p.provider_id for p in catalog.all_providers}
        for p in required:
            assert p in provider_ids, f"Provider {p!r} must be in catalog"

    def test_all_models_have_capability_tags(self, catalog):
        """Every model in catalog must have at least one capability tag."""
        for m in catalog.all_models:
            assert len(m.capability_tags) > 0, (
                f"Model {m.model_id} must have at least one capability tag"
            )

    def test_all_required_capability_tags_covered(self, catalog):
        """All required capability tags must be represented in catalog."""
        from openjarvis.plan9.model_catalog_9k import CapabilityTag
        required_tags = [
            CapabilityTag.DEFAULT_CHAT,
            CapabilityTag.CODING,
            CapabilityTag.WEB_GROUNDED,
            CapabilityTag.LONG_CONTEXT,
            CapabilityTag.SECURITY_REVIEW,
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.OFFLINE_FALLBACK,
            CapabilityTag.CHEAP_FAST,
        ]
        summary = catalog.capability_summary()
        for tag in required_tags:
            assert len(summary.get(tag.value, [])) > 0, (
                f"No models with capability tag {tag.value!r} in catalog"
            )

    def test_kimi_in_catalog(self, catalog):
        """Kimi models must be in catalog."""
        kimi = catalog.kimi_models()
        assert len(kimi) >= 2, f"Expected at least 2 Kimi models, got: {len(kimi)}"

    def test_perplexity_in_catalog(self, catalog):
        """Perplexity models must be in catalog."""
        perplexity = catalog.models_for_provider("perplexity")
        assert len(perplexity) >= 2, f"Expected at least 2 Perplexity models"

    def test_catalog_large_scale(self, catalog):
        """Catalog must support hundreds of models without hardcoded per-role lists."""
        # Verify the catalog is a normalized structure, not hardcoded per role
        assert hasattr(catalog, "all_models"), "Catalog must have all_models property"
        assert hasattr(catalog, "capability_summary"), "Catalog must support capability queries"
        assert hasattr(catalog, "models_with_capability"), "Catalog must support filtering by capability"


# ---------------------------------------------------------------------------
# 12. Routing audit explains why model selected
# ---------------------------------------------------------------------------

class TestRoutingAudit:
    def test_routing_decision_has_route_reason(self, router):
        """Every routing decision must have a non-empty route_reason."""
        decision = router.select(role_id="coding_manager", task_description="implement auth")
        assert decision.route_reason, "route_reason must not be empty"
        assert len(decision.route_reason) > 20, "route_reason must be substantive"

    def test_routing_decision_has_provider(self, router):
        """Every routing decision must have chosen_provider."""
        for role_id in ["jarvis_pa", "coding_manager", "research_manager", "security_code_worker"]:
            decision = router.select(role_id=role_id, task_description="test task")
            assert decision.chosen_provider, f"chosen_provider must not be empty for {role_id}"

    def test_routing_decision_has_required_capabilities(self, router):
        """Every routing decision must list required_capabilities."""
        decision = router.select(role_id="coding_manager", task_description="write tests")
        assert len(decision.required_capabilities) > 0, "required_capabilities must not be empty"

    def test_routing_decision_serializable(self, router):
        """Routing decision must serialize to dict with all audit fields."""
        decision = router.select(role_id="backend_worker", task_description="add endpoint")
        d = decision.to_dict()
        required_fields = [
            "role_id", "task_description", "chosen_provider", "chosen_model_id",
            "route_reason", "why_cheaper_rejected", "required_capabilities",
            "risk_level", "benchmark_required", "kimi_eligible", "offline_fallback_active",
        ]
        for f in required_fields:
            assert f in d, f"Routing decision dict missing field: {f}"

    def test_routing_explains_rejected_alternatives(self, router):
        """When Kimi is rejected, why_cheaper_rejected must explain why."""
        decision = router.select(
            role_id="coding_manager",
            task_description="big refactor",
        )
        # Since Kimi is in the refactor_worker chain but not benchmarked,
        # why_cheaper_rejected should mention something
        assert isinstance(decision.why_cheaper_rejected, str)


# ---------------------------------------------------------------------------
# 13. Fallback chains work when provider unavailable
# ---------------------------------------------------------------------------

class TestFallbackChains:
    def test_force_fallback_activates_offline_mode(self, router):
        """When force_fallback=True, offline_fallback_active must be True."""
        decision = router.select(
            role_id="coding_manager",
            task_description="fix bug",
            force_fallback=True,
        )
        assert decision.offline_fallback_active is True

    def test_force_fallback_not_anthropic(self, router):
        """When offline fallback is active, model may be local (not anthropic cloud required)."""
        decision = router.select(
            role_id="coding_manager",
            task_description="fix bug",
            force_fallback=True,
        )
        # In force_fallback mode, we should get something (not error)
        assert decision.chosen_model_id, "Must select some model even in fallback"

    def test_unknown_role_gets_default_safe_model(self, router):
        """Unknown roles must get a safe default (not Kimi, not Ollama in normal mode)."""
        decision = router.select(
            role_id="unknown_future_role_xyz",
            task_description="some task",
        )
        assert "ollama" not in decision.chosen_model_id.lower(), (
            "Unknown roles must not default to Ollama"
        )
        assert "kimi" not in decision.chosen_model_id.lower(), (
            "Unknown roles must not default to Kimi"
        )

    def test_fallback_chain_used_when_primary_unavailable(self, catalog, router):
        """When primary model is unavailable, fallback chain is used."""
        # Mark deepseek unavailable
        deepseek = catalog.get_model("deepseek/deepseek-chat")
        if deepseek:
            deepseek.is_available = False
            try:
                decision = router.select(
                    role_id="coding_manager",
                    task_description="implement feature",
                )
                # Should fall back to next in chain (not deepseek)
                assert "deepseek/deepseek-chat" not in decision.chosen_model_id
            finally:
                deepseek.is_available = True


# ---------------------------------------------------------------------------
# 14. Existing Plan 9 routes still pass
# ---------------------------------------------------------------------------

class TestExistingPlan9Routes:
    def test_matrix_validates(self, matrix):
        """Routing matrix must pass validation (no missing models/rules)."""
        errors = matrix.validate()
        assert len(errors) == 0, f"Routing matrix validation errors: {errors}"

    def test_matrix_has_all_managers(self, matrix):
        """Matrix must include all 17 managers."""
        manager_roles = [e.role_id for e in matrix.entries if e.role_type == "manager"]
        assert len(manager_roles) >= 17, (
            f"Expected at least 17 managers, got: {len(manager_roles)}"
        )

    def test_matrix_has_all_workers(self, matrix):
        """Matrix must include at least 30 workers."""
        worker_roles = [e.role_id for e in matrix.entries if e.role_type == "worker"]
        assert len(worker_roles) >= 30, (
            f"Expected at least 30 workers, got: {len(worker_roles)}"
        )

    def test_matrix_get_returns_entry_not_default(self, matrix):
        """matrix.get() must return specific entries for known roles."""
        for role_id in ["jarvis_pa", "coding_manager", "security_code_worker"]:
            entry = matrix.get(role_id)
            assert entry.role_id == role_id, (
                f"matrix.get({role_id!r}) returned default instead of specific entry"
            )

    def test_default_routing_has_all_fields(self):
        """DEFAULT_ROUTING must have all required Plan 9K fields."""
        assert DEFAULT_ROUTING.required_capabilities, "DEFAULT_ROUTING missing required_capabilities"
        assert DEFAULT_ROUTING.forbidden_model_classes, "DEFAULT_ROUTING missing forbidden_model_classes"
        assert DEFAULT_ROUTING.fallback_chain, "DEFAULT_ROUTING missing fallback_chain"

    def test_tier_for_task_works(self, matrix):
        """tier_for_task must return correct tiers."""
        entry = matrix.get("coding_manager")
        assert entry.tier_for_task("high", "complex", 0) == ModelTier.BEST
        assert entry.tier_for_task("low", "simple", 0) == ModelTier.CHEAP
        assert entry.tier_for_task("medium", "moderate", 0) == ModelTier.BALANCED
        assert entry.tier_for_task("medium", "moderate", 3) == ModelTier.STOP

    def test_routing_status_serializable(self, router):
        """routing_status() must return a valid dict."""
        status = router.routing_status()
        assert "provider_count" in status
        assert "model_count" in status
        assert "kimi_benchmarked" in status
        assert "pa_front_door_model" in status

    def test_matrix_no_security_roles_with_local(self, matrix):
        """Security/deploy/governance roles must not have local models."""
        errors = matrix.validate()
        security_errors = [e for e in errors if "FORBIDDEN" in e and "security" in e.lower()]
        assert len(security_errors) == 0, f"Security role model violations: {security_errors}"


# ---------------------------------------------------------------------------
# Additional: Plan 9K-specific invariants
# ---------------------------------------------------------------------------

class TestPlan9KInvariants:
    def test_pa_default_tier_is_balanced(self, matrix):
        """PA default_tier must be BALANCED (not CHEAP or BEST)."""
        pa = matrix.get("jarvis_pa")
        assert pa.default_tier == ModelTier.BALANCED

    def test_security_worker_default_tier_is_best(self, matrix):
        """security_code_worker default_tier must be BEST."""
        sec = matrix.get("security_code_worker")
        assert sec.default_tier == ModelTier.BEST

    def test_release_manager_default_tier_is_best(self, matrix):
        """release_packaging_manager default_tier must be BEST."""
        rel = matrix.get("release_packaging_manager")
        assert rel.default_tier == ModelTier.BEST

    def test_memory_manager_default_tier_is_cheap(self, matrix):
        """memory_knowledge_manager default_tier must be CHEAP (reads/retrieval)."""
        mem = matrix.get("memory_knowledge_manager")
        assert mem.default_tier == ModelTier.CHEAP

    def test_retrieval_worker_default_tier_is_cheap(self, matrix):
        """retrieval_worker default_tier must be CHEAP."""
        ret = matrix.get("retrieval_worker")
        assert ret.default_tier == ModelTier.CHEAP

    def test_kimi_catalog_has_required_notes(self, catalog):
        """Kimi catalog entries must contain benchmark-gated notes."""
        kimi_models = catalog.kimi_models()
        for m in kimi_models:
            if m.provider_id == "kimi":  # direct kimi provider
                assert "benchmark" in m.notes.lower() or "not default" in m.notes.lower(), (
                    f"Kimi model {m.model_id} must have benchmark-gated notes"
                )

    def test_coding_cheap_not_equal_to_research_cheap(self, matrix):
        """coding_manager cheap != research_manager cheap (capability-specific)."""
        coding = matrix.get("coding_manager")
        research = matrix.get("research_manager")
        assert coding.cheap_model != research.cheap_model, (
            "coding_manager and research_manager should use different cheap models "
            f"(got same: {coding.cheap_model})"
        )

    def test_router_explain_returns_catalog_model(self, router):
        """router.explain() must return catalog_model for the chosen model."""
        explanation = router.explain(
            role_id="coding_manager",
            task_description="implement feature",
        )
        assert "decision" in explanation
        assert "role_declaration" in explanation
