"""Plan 9K — API Route Tests.

Tests all new Plan 9K endpoints using FastAPI TestClient.

Endpoints tested:
  GET  /v1/model-catalog/providers
  GET  /v1/model-catalog/models
  GET  /v1/model-catalog/capabilities
  GET  /v1/model-catalog/summary
  GET  /v1/model-routing/status
  POST /v1/model-routing/explain
  POST /v1/model-routing/select
  GET  /v1/model-routing/audit
  GET  /v1/model-routing/inheritance
  POST /v1/model-routing/validate-role
  POST /v1/model-routing/benchmark/plan
  GET  /v1/model-routing/benchmark/results
"""

from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:
    pytest.skip("fastapi not available", allow_module_level=True)

from openjarvis.server.model_catalog_routes import router

# Create a minimal FastAPI app for testing
from fastapi import FastAPI
_app = FastAPI()
_app.include_router(router)

client = TestClient(_app)


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/providers
# ---------------------------------------------------------------------------

class TestProvidersEndpoint:
    def test_providers_returns_200(self):
        resp = client.get("/v1/model-catalog/providers")
        assert resp.status_code == 200

    def test_providers_has_required_fields(self):
        resp = client.get("/v1/model-catalog/providers")
        data = resp.json()
        assert "total" in data
        assert "providers" in data
        assert data["total"] >= 10, f"Expected 10+ providers, got {data['total']}"

    def test_providers_includes_all_required_providers(self):
        resp = client.get("/v1/model-catalog/providers")
        data = resp.json()
        provider_ids = {p["provider_id"] for p in data["providers"]}
        required = {"openai", "anthropic", "kimi", "perplexity", "google",
                    "deepseek", "mistral", "xai", "openrouter", "ollama", "aimlapi"}
        missing = required - provider_ids
        assert not missing, f"Missing providers: {missing}"

    def test_providers_no_secrets_exposed(self):
        resp = client.get("/v1/model-catalog/providers")
        data = resp.json()
        # No actual API key values — only configured status
        for p in data["providers"]:
            for key, val in p.items():
                if "key" in key.lower() and isinstance(val, str):
                    # Must be a boolean/status, not an actual key value
                    assert len(val) < 50 or val in ("", "not_set", "configured"), (
                        f"Possible secret leaked in provider field {key}: {val[:20]}..."
                    )

    def test_providers_has_kimi_benchmark_status(self):
        resp = client.get("/v1/model-catalog/providers")
        data = resp.json()
        assert "kimi_benchmark_status" in data
        assert data["kimi_benchmark_status"] in ("NOT_BENCHMARKED", "BENCHMARK_ACCEPTED")

    def test_providers_has_ollama_policy(self):
        resp = client.get("/v1/model-catalog/providers")
        data = resp.json()
        assert "ollama_policy" in data
        assert "OFFLINE FALLBACK ONLY" in data["ollama_policy"]


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/models
# ---------------------------------------------------------------------------

class TestModelsEndpoint:
    def test_models_returns_200(self):
        resp = client.get("/v1/model-catalog/models")
        assert resp.status_code == 200

    def test_models_has_total_count(self):
        resp = client.get("/v1/model-catalog/models")
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 25, f"Expected 25+ models, got {data['total']}"

    def test_models_filter_by_provider(self):
        resp = client.get("/v1/model-catalog/models?provider_id=anthropic")
        assert resp.status_code == 200
        data = resp.json()
        for m in data["models"]:
            assert m["provider_id"] == "anthropic"

    def test_models_filter_exclude_fallback(self):
        resp = client.get("/v1/model-catalog/models?exclude_fallback=true")
        data = resp.json()
        for m in data["models"]:
            assert "offline_fallback" not in m.get("capability_tags", [])

    def test_models_kimi_only_filter(self):
        resp = client.get("/v1/model-catalog/models?kimi_only=true")
        data = resp.json()
        assert data["total"] >= 2, f"Expected at least 2 Kimi models"
        for m in data["models"]:
            assert m["provider_id"] == "kimi" or "kimi" in m["model_id"].lower()

    def test_models_has_capability_tags(self):
        resp = client.get("/v1/model-catalog/models")
        data = resp.json()
        for m in data["models"]:
            assert "capability_tags" in m
            assert "provider_id" in m
            assert "model_id" in m

    def test_models_has_model_status(self):
        resp = client.get("/v1/model-catalog/models")
        data = resp.json()
        for m in data["models"]:
            assert "model_status" in m, f"Model {m.get('model_id')} missing model_status"


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/capabilities
# ---------------------------------------------------------------------------

class TestCapabilitiesEndpoint:
    def test_capabilities_returns_200(self):
        resp = client.get("/v1/model-catalog/capabilities")
        assert resp.status_code == 200

    def test_capabilities_has_all_required_tags(self):
        resp = client.get("/v1/model-catalog/capabilities")
        data = resp.json()
        tags = set(data["capability_tags"])
        required_tags = {
            "coding", "research", "web_grounded", "long_context",
            "security_review", "high_reasoning", "offline_fallback",
            "cheap_fast", "default_chat", "tool_calling",
        }
        missing = required_tags - tags
        assert not missing, f"Missing capability tags: {missing}"

    def test_capabilities_coding_has_multiple_models(self):
        resp = client.get("/v1/model-catalog/capabilities")
        data = resp.json()
        coding_models = data["capabilities"]["coding"]["models"]
        assert len(coding_models) >= 5, f"coding capability must cover 5+ models"

    def test_capabilities_web_grounded_includes_perplexity(self):
        resp = client.get("/v1/model-catalog/capabilities")
        data = resp.json()
        web_models = data["capabilities"]["web_grounded"]["models"]
        assert any("perplexity" in m for m in web_models), (
            f"web_grounded must include Perplexity: {web_models}"
        )

    def test_capabilities_offline_fallback_only_ollama(self):
        resp = client.get("/v1/model-catalog/capabilities")
        data = resp.json()
        fallback_models = data["capabilities"]["offline_fallback"]["models"]
        for m in fallback_models:
            assert "ollama" in m.lower(), (
                f"offline_fallback must only contain Ollama models, got: {m}"
            )


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/summary
# ---------------------------------------------------------------------------

class TestSummaryEndpoint:
    def test_summary_returns_200(self):
        resp = client.get("/v1/model-catalog/summary")
        assert resp.status_code == 200

    def test_summary_has_required_fields(self):
        resp = client.get("/v1/model-catalog/summary")
        data = resp.json()
        required = [
            "total_models", "total_providers", "active_cloud_models",
            "fallback_only_models", "discovery_status_per_provider",
        ]
        for f in required:
            assert f in data, f"Summary missing field: {f}"

    def test_summary_discovery_status_has_all_providers(self):
        resp = client.get("/v1/model-catalog/summary")
        data = resp.json()
        status = data["discovery_status_per_provider"]
        for p in ["openai", "anthropic", "kimi", "perplexity"]:
            assert p in status, f"Discovery status missing provider: {p}"

    def test_summary_active_cloud_count(self):
        resp = client.get("/v1/model-catalog/summary")
        data = resp.json()
        assert data["active_cloud_models"] >= 20

    def test_summary_has_fallback_only(self):
        resp = client.get("/v1/model-catalog/summary")
        data = resp.json()
        assert data["fallback_only_models"] >= 5


# ---------------------------------------------------------------------------
# GET /v1/model-routing/status
# ---------------------------------------------------------------------------

class TestRoutingStatusEndpoint:
    def test_routing_status_returns_200(self):
        resp = client.get("/v1/model-routing/status")
        assert resp.status_code == 200

    def test_routing_status_has_required_fields(self):
        resp = client.get("/v1/model-routing/status")
        data = resp.json()
        required = [
            "provider_count", "model_count", "kimi_benchmarked",
            "pa_front_door_model", "provider_health", "active_routing_policy",
            "blocked_providers", "role_declaration_count",
        ]
        for f in required:
            assert f in data, f"routing/status missing field: {f}"

    def test_routing_status_pa_model_is_openai(self):
        resp = client.get("/v1/model-routing/status")
        data = resp.json()
        assert "gpt" in data["pa_front_door_model"].lower() or "openai" in data["pa_front_door_model"].lower()

    def test_routing_status_kimi_not_benchmarked(self):
        resp = client.get("/v1/model-routing/status")
        data = resp.json()
        assert data["kimi_benchmarked"] is False

    def test_routing_status_has_provider_health(self):
        resp = client.get("/v1/model-routing/status")
        data = resp.json()
        health = data["provider_health"]
        for p in ["openai", "anthropic", "kimi"]:
            assert p in health

    def test_routing_status_role_declaration_count(self):
        resp = client.get("/v1/model-routing/status")
        data = resp.json()
        assert data["role_declaration_count"] >= 50, (
            f"Expected 50+ role declarations, got {data['role_declaration_count']}"
        )


# ---------------------------------------------------------------------------
# POST /v1/model-routing/explain
# ---------------------------------------------------------------------------

class TestRoutingExplainEndpoint:
    def test_explain_coding_manager(self):
        resp = client.post("/v1/model-routing/explain", json={
            "role": "coding_manager",
            "task": "implement a new API endpoint",
            "task_classification": "normal",
            "force_fallback": False,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "role_declaration" in data
        d = data["decision"]
        assert d["chosen_model_id"]
        assert d["route_reason"]
        assert d["required_capabilities"]

    def test_explain_returns_why_kimi_rejected(self):
        resp = client.post("/v1/model-routing/explain", json={
            "role": "refactor_worker",
            "task": "large refactor",
            "task_classification": "normal",
        })
        data = resp.json()
        d = data["decision"]
        # Kimi should be mentioned as rejected (not benchmarked)
        assert "kimi" in d["why_cheaper_rejected"].lower() or \
               "kimi" in d["route_reason"].lower(), (
            "explain must mention why Kimi was rejected"
        )

    def test_explain_research_routes_to_perplexity(self):
        resp = client.post("/v1/model-routing/explain", json={
            "role": "research_manager",
            "task": "find current AI research papers",
        })
        data = resp.json()
        d = data["decision"]
        assert "perplexity" in d["chosen_provider"], (
            f"research_manager should route to perplexity, got: {d['chosen_provider']}"
        )

    def test_explain_security_routes_to_anthropic(self):
        resp = client.post("/v1/model-routing/explain", json={
            "role": "security_code_worker",
            "task": "audit auth code",
        })
        data = resp.json()
        d = data["decision"]
        assert d["chosen_provider"] == "anthropic"

    def test_explain_force_fallback(self):
        resp = client.post("/v1/model-routing/explain", json={
            "role": "coding_manager",
            "task": "fix bug",
            "force_fallback": True,
        })
        data = resp.json()
        d = data["decision"]
        assert d["offline_fallback_active"] is True


# ---------------------------------------------------------------------------
# POST /v1/model-routing/select
# ---------------------------------------------------------------------------

class TestRoutingSelectEndpoint:
    def test_select_returns_decision(self):
        resp = client.post("/v1/model-routing/select", json={
            "role": "backend_worker",
            "task": "add REST endpoint",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert data["decision"]["chosen_model_id"]

    def test_select_logs_to_audit(self):
        client.post("/v1/model-routing/select", json={
            "role": "coding_manager",
            "task": "audit log test",
        })
        resp = client.get("/v1/model-routing/audit")
        data = resp.json()
        assert data["total"] >= 1


# ---------------------------------------------------------------------------
# GET /v1/model-routing/audit
# ---------------------------------------------------------------------------

class TestRoutingAuditEndpoint:
    def test_audit_returns_200(self):
        resp = client.get("/v1/model-routing/audit")
        assert resp.status_code == 200

    def test_audit_has_entries_structure(self):
        resp = client.get("/v1/model-routing/audit")
        data = resp.json()
        assert "total" in data
        assert "entries" in data

    def test_audit_role_filter(self):
        client.post("/v1/model-routing/select", json={
            "role": "jarvis_pa", "task": "filter test"
        })
        resp = client.get("/v1/model-routing/audit?role_filter=jarvis_pa")
        data = resp.json()
        for entry in data["entries"]:
            assert entry["role_id"] == "jarvis_pa"


# ---------------------------------------------------------------------------
# GET /v1/model-routing/inheritance
# ---------------------------------------------------------------------------

class TestInheritanceEndpoint:
    def test_inheritance_returns_200(self):
        resp = client.get("/v1/model-routing/inheritance")
        assert resp.status_code == 200

    def test_inheritance_has_required_fields(self):
        resp = client.get("/v1/model-routing/inheritance")
        data = resp.json()
        assert "total_explicit_declarations" in data
        assert "default_policy" in data
        assert "coverage" in data
        assert "inheritance_rules" in data

    def test_inheritance_total_declarations(self):
        resp = client.get("/v1/model-routing/inheritance")
        data = resp.json()
        assert data["total_explicit_declarations"] >= 50

    def test_inheritance_default_policy_present(self):
        resp = client.get("/v1/model-routing/inheritance")
        data = resp.json()
        policy = data["default_policy"]
        assert "pa_fallback_chain" in policy, "PA stable chain must be in policy"
        assert "non_pa_fallback_chain" in policy, "Non-PA dynamic chain must be in policy"
        assert "default_forbidden_provider_classes" in policy
        # Non-PA chain must be empty
        assert policy["non_pa_fallback_chain"] == [], (
            "non_pa_fallback_chain must be empty (dynamic catalog scoring)"
        )

    def test_inheritance_rules_non_empty(self):
        resp = client.get("/v1/model-routing/inheritance")
        data = resp.json()
        assert len(data["inheritance_rules"]) >= 5


# ---------------------------------------------------------------------------
# POST /v1/model-routing/validate-role
# ---------------------------------------------------------------------------

class TestValidateRoleEndpoint:
    def test_valid_role_passes(self):
        resp = client.post(
            "/v1/model-routing/validate-role",
            params={
                "role_id": "my_new_manager",
                "role_type": "manager",
                "required_capabilities": ["coding"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    def test_role_missing_caps_fails(self):
        resp = client.post(
            "/v1/model-routing/validate-role",
            params={
                "role_id": "bad_new_role",
                "role_type": "worker",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0


# ---------------------------------------------------------------------------
# POST /v1/model-routing/benchmark/plan
# ---------------------------------------------------------------------------

class TestBenchmarkPlanEndpoint:
    def test_benchmark_plan_kimi_model(self):
        resp = client.post("/v1/model-routing/benchmark/plan", json={
            "model_id": "kimi/kimi-k2",
            "dry_run": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "DRY_RUN_PLAN"
        assert data["dry_run"] is True
        assert data["approval_required"] is True
        assert "benchmark_plan" in data

    def test_benchmark_plan_requires_dry_run(self):
        resp = client.post("/v1/model-routing/benchmark/plan", json={
            "model_id": "kimi/kimi-k2",
        })
        data = resp.json()
        # Regardless of dry_run flag, this is always dry_run
        assert data.get("dry_run", True) is True

    def test_benchmark_plan_kimi_not_benchmarked_status(self):
        resp = client.post("/v1/model-routing/benchmark/plan", json={
            "model_id": "kimi/kimi-k2",
        })
        data = resp.json()
        assert data["current_benchmark_status"] == "not_benchmarked"

    def test_benchmark_plan_missing_model_404(self):
        resp = client.post("/v1/model-routing/benchmark/plan", json={
            "model_id": "nonexistent/model-xyz",
        })
        data = resp.json()
        assert data["status"] == "MODEL_NOT_FOUND"


# ---------------------------------------------------------------------------
# GET /v1/model-routing/benchmark/results
# ---------------------------------------------------------------------------

class TestBenchmarkResultsEndpoint:
    def test_benchmark_results_returns_200(self):
        resp = client.get("/v1/model-routing/benchmark/results")
        assert resp.status_code == 200

    def test_benchmark_results_kimi_not_benchmarked(self):
        resp = client.get("/v1/model-routing/benchmark/results")
        data = resp.json()
        assert data["kimi_benchmarked"] is False
        assert data["kimi_eligible_for_routing"] is False
        for m_id, status in data.get("kimi_models", {}).items():
            assert status == "not_benchmarked", (
                f"Kimi model {m_id} should be not_benchmarked, got: {status}"
            )

    def test_benchmark_results_has_note(self):
        resp = client.get("/v1/model-routing/benchmark/results")
        data = resp.json()
        assert "note" in data
        assert "Kimi" in data["note"]
