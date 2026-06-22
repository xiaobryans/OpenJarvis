"""Plan 9K — GLM-5.2 / Kimi K2.6 temporary heavy-coding routing policy tests."""

from __future__ import annotations

import pytest

from openjarvis.plan9.heavy_coding_policy import (
    RoutingPolicyLabel,
    get_target_model_availability,
    is_glm_52_model,
    is_heavy_coding_context_for_decl,
    is_kimi_k26_model,
    provider_key_status,
    reorder_heavy_coding_candidates,
)
from openjarvis.plan9.inheritance_policy import RoleInheritanceValidator
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
    RiskThreshold,
    RoleCapabilityDeclaration,
    SpecializedRouter,
    get_role_declarations,
)


@pytest.fixture
def catalog():
    return get_provider_catalog()


@pytest.fixture
def router(catalog):
    return SpecializedRouter(catalog=catalog)


class TestHeavyCodingPreference:
    def test_heavy_coding_selects_glm_52_when_available(self, router):
        decision = router.select(
            role_id="coding_manager",
            task_description="implement backend API",
            task_classification="normal_heavy_coding",
        )
        assert is_glm_52_model(decision.chosen_model_id), (
            f"Expected GLM-5.2 for heavy coding, got {decision.chosen_model_id}"
        )
        assert decision.heavy_coding_preference_applied is True
        assert any(
            RoutingPolicyLabel.GLM_5_2_CURRENT_PREFERRED_HEAVY_CODING_ROUTE_PENDING_BENCHMARK.value
            in lbl for lbl in decision.policy_labels
        )

    def test_heavy_coding_falls_back_to_kimi_k26_when_glm_unavailable(self, catalog, router):
        glm_ids = [m.model_id for m in catalog.all_models if is_glm_52_model(m.model_id)]
        saved = {mid: catalog.get_model(mid).is_available for mid in glm_ids if catalog.get_model(mid)}
        try:
            for mid in glm_ids:
                m = catalog.get_model(mid)
                if m:
                    m.is_available = False
            decision = router.select(
                role_id="backend_worker",
                task_classification="backend_implementation",
            )
            assert is_kimi_k26_model(decision.chosen_model_id) or "kimi" in decision.chosen_model_id.lower(), (
                f"Expected Kimi K2.6 fallback, got {decision.chosen_model_id}"
            )
        finally:
            for mid, avail in saved.items():
                m = catalog.get_model(mid)
                if m:
                    m.is_available = avail

    def test_heavy_coding_falls_back_to_coding_catalog_when_glm_and_kimi_unavailable(
        self, catalog, router
    ):
        glm_ids = [m.model_id for m in catalog.all_models if is_glm_52_model(m.model_id)]
        kimi_ids = [m.model_id for m in catalog.all_models if is_kimi_k26_model(m.model_id)]
        saved = {}
        for mid in glm_ids + kimi_ids:
            m = catalog.get_model(mid)
            if m:
                saved[mid] = m.is_available
                m.is_available = False
        try:
            decision = router.select(
                role_id="coding_manager",
                task_classification="test_fix",
            )
            assert "ollama" not in decision.chosen_model_id.lower()
            assert any(
                s in decision.chosen_model_id.lower()
                for s in ("deepseek", "sonnet", "gpt", "claude")
            ), f"Expected coding catalog fallback, got {decision.chosen_model_id}"
        finally:
            for mid, avail in saved.items():
                m = catalog.get_model(mid)
                if m:
                    m.is_available = avail

    def test_sonnet_for_high_risk_security_role_not_glm_kimi(self, router):
        decision = router.select(
            role_id="security_code_worker",
            task_description="review IAM policy changes",
            task_classification="security_review",
        )
        assert "glm" not in decision.chosen_model_id.lower()
        assert "kimi" not in decision.chosen_model_id.lower()
        assert "sonnet" in decision.chosen_model_id.lower() or "claude" in decision.chosen_model_id.lower() or "opus" in decision.chosen_model_id.lower()

    def test_pa_uses_openai_not_glm_kimi(self, router):
        decision = router.select(role_id="jarvis_pa", task_description="hello")
        assert decision.chosen_provider == "openai"
        assert "glm" not in decision.chosen_model_id.lower()
        assert "kimi" not in decision.chosen_model_id.lower()

    def test_ollama_not_selected_without_fallback(self, router):
        decision = router.select(
            role_id="coding_manager",
            task_classification="normal_implementation",
        )
        assert "ollama" not in decision.chosen_model_id.lower()
        assert decision.offline_fallback_active is False

    def test_ollama_only_with_force_fallback(self, router):
        decision = router.select(
            role_id="coding_manager",
            force_fallback=True,
            override_reason="offline debug",
        )
        assert decision.offline_fallback_active is True
        assert any(
            RoutingPolicyLabel.OLLAMA_LOCAL_FALLBACK_ONLY.value in lbl
            for lbl in decision.policy_labels
        )


class TestDynamicNotFixed:
    def test_reorder_injects_catalog_glm_without_role_edit(self, catalog):
        candidates = ["deepseek/deepseek-chat"]
        reordered, labels = reorder_heavy_coding_candidates(candidates, catalog, inject_from_catalog=True)
        glm_positions = [i for i, m in enumerate(reordered) if is_glm_52_model(m)]
        assert glm_positions, "GLM-5.2 must appear from catalog without role-file edit"
        assert glm_positions[0] == 0, "GLM-5.2 must be first preference"
        assert labels

    def test_new_discovered_coding_model_eligible_without_role_edit(self, catalog, router):
        from openjarvis.plan9.specialized_router import RoleCapabilityDeclaration, RiskThreshold, LatencyClass
        new_model = ModelEntry9K(
            model_id="futureai/new-coding-model",
            display_name="Future Coding",
            provider_id="futureai",
            context_window=128_000,
            input_cost_per_mtok=1.0,
            output_cost_per_mtok=4.0,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset([CapabilityTag.CODING, CapabilityTag.BACKEND_API]),
            allowed_risk_level=AllowedRiskLevel.MEDIUM,
            model_status=ModelStatus.STATIC_METADATA,
        )
        catalog.add_discovered_model(new_model)
        decl = RoleCapabilityDeclaration(
            role_id="brand_new_coding_worker_xyz",
            role_type="worker",
            required_capabilities=[CapabilityTag.CODING],
            preferred_capabilities=[CapabilityTag.BACKEND_API],
            forbidden_provider_classes=["ollama"],
            fallback_chain=[],
            escalation_model="anthropic/claude-sonnet-4-20250514",
            cost_ceiling="high",
            latency_preference=LatencyClass.MEDIUM,
            risk_threshold=RiskThreshold.MEDIUM,
            benchmark_required_for=["kimi/kimi-k2"],
            audit_required=True,
        )
        try:
            candidates, _ = router._build_candidate_list(
                decl, False, False, "normal_heavy_coding"
            )
            assert "futureai/new-coding-model" in candidates
        finally:
            catalog._models = [m for m in catalog._models if m.model_id != "futureai/new-coding-model"]
            catalog._by_id.pop("futureai/new-coding-model", None)


class TestFutureProofInheritance:
    def test_fake_new_coding_worker_inherits_heavy_coding_preference(self, router):
        decision = router.select(
            role_id="fake_future_coding_worker",
            task_classification="normal_implementation",
        )
        assert decision.heavy_coding_preference_applied or is_glm_52_model(decision.chosen_model_id)

    def test_fake_non_coding_worker_no_heavy_coding_preference(self, router):
        decl = router._get_declaration("fake_future_research_worker")
        heavy = is_heavy_coding_context_for_decl(
            "fake_future_research_worker",
            "research",
            [CapabilityTag.RESEARCH, CapabilityTag.WEB_GROUNDED],
            [CapabilityTag.CITATIONS],
            RiskThreshold.MEDIUM,
        )
        assert heavy is False

    def test_fake_security_worker_fails_without_capabilities(self):
        validator = RoleInheritanceValidator()
        result = validator.validate_new_role(
            role_id="fake_security_worker",
            role_type="worker",
            required_capabilities=None,
        )
        assert result["valid"] is False

    def test_fake_security_worker_no_glm_kimi(self, router):
        decision = router.select(
            role_id="deploy_review_manager",
            task_classification="deploy_review",
        )
        assert "glm" not in decision.chosen_model_id.lower()
        assert "kimi" not in decision.chosen_model_id.lower()


class TestPolicyLabelsAndAudit:
    def test_audit_records_glm_kimi_policy_labels(self, router):
        decision = router.select(
            role_id="coding_manager",
            task_classification="repo_refactor",
        )
        assert decision.policy_labels
        assert decision.route_reason
        assert "heavy_coding" in decision.route_reason or decision.heavy_coding_preference_applied

    def test_kimi_not_benchmarked_label_present(self, router):
        decision = router.select(
            role_id="coding_manager",
            task_classification="normal_heavy_coding",
        )
        if "kimi" in decision.chosen_model_id.lower():
            assert RoutingPolicyLabel.KIMI_NOT_BENCHMARKED.value in decision.policy_labels


class TestProviderAvailability:
    def test_provider_key_status_no_secret_values(self):
        status = provider_key_status("openrouter")
        assert "configured" in status
        assert "env_var" in status
        assert "sk-" not in str(status)

    def test_target_model_availability_structure(self, catalog):
        report = get_target_model_availability(catalog)
        assert "glm_5_2" in report
        assert "kimi_k2_6" in report
        assert "provider_keys" in report
        for provider in ("openrouter", "aimlapi", "zai"):
            assert provider in report["glm_5_2"]
        for provider in ("openrouter", "aimlapi", "kimi"):
            assert provider in report["kimi_k2_6"]


class TestUINoManualPicker:
    def test_cockpit_no_model_picker(self):
        from pathlib import Path
        src = Path(__file__).resolve().parents[2] / "frontend/src/pages/JarvisCockpitPage.tsx"
        content = src.read_text()
        assert "model picker" not in content.lower() or "no manual model picker" in content.lower()
        assert "ModelPicker" not in content
        assert "selectModel" not in content
