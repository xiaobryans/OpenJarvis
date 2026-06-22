"""Plan 9K — Model Catalog and Dynamic Routing API Routes.

Routes:
  GET  /v1/model-catalog/providers       — all configured providers
  GET  /v1/model-catalog/models          — full model catalog
  GET  /v1/model-catalog/capabilities    — capability tag → model mapping
  GET  /v1/model-routing/status          — routing system status
  POST /v1/model-routing/explain         — explain routing for a role/task
  POST /v1/model-routing/select          — select model for role/task (dry-run)
  GET  /v1/model-routing/audit           — routing audit log (in-memory, session only)
  POST /v1/model-routing/benchmark/plan  — plan Kimi benchmark (dry-run only)
  GET  /v1/model-routing/benchmark/results — benchmark results

Safety:
  - No secrets exposed in any response.
  - Benchmark plan/run is DRY_RUN only — no live model calls here.
  - Kimi benchmark status is visible but not settable from this route.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Query
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for model_catalog_routes")

from openjarvis.plan9.catalog_discovery import (
    get_last_discovery_report,
    run_catalog_discovery,
    run_catalog_discovery_sync,
)
from openjarvis.plan9.inheritance_policy import (
    get_default_policy,
    get_inheritance_coverage,
    RoleInheritanceValidator,
)
from openjarvis.plan9.model_catalog_9k import (
    BenchmarkStatus,
    CapabilityTag,
    ModelStatus,
    get_provider_catalog,
)
from openjarvis.plan9.specialized_router import (
    get_role_declarations,
    get_specialized_router,
)

router = APIRouter(tags=["model-catalog"])

# In-memory routing audit log (session only, not persisted)
_ROUTING_AUDIT_LOG: List[Dict[str, Any]] = []
_MAX_AUDIT_ENTRIES = 200


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ModelRouteExplainRequest9K(BaseModel):
    role: str = Field(..., description="Role ID (e.g. coding_manager, jarvis_pa)")
    task: str = Field("", description="Task description for context")
    task_classification: str = Field("normal", description="Task classification (normal | security | research | etc.)")
    force_fallback: bool = Field(False, description="Simulate provider failure to test offline fallback")


class BenchmarkPlanRequest(BaseModel):
    model_id: str = Field(..., description="Model ID to benchmark (e.g. kimi/kimi-k2)")
    task_types: List[str] = Field(
        default_factory=lambda: [
            "backend_route_task",
            "frontend_ui_task",
            "test_fix_task",
            "broad_file_repo_understanding",
            "documentation_task",
            "code_review_task",
        ],
        description="Task types to benchmark",
    )
    dry_run: bool = Field(True, description="Always dry-run here. Real benchmark requires separate approval.")


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/providers
# ---------------------------------------------------------------------------

@router.get("/v1/model-catalog/providers")
async def get_model_catalog_providers() -> Dict[str, Any]:
    """Return all configured providers in the normalized model catalog."""
    catalog = get_provider_catalog()
    providers_dict = catalog.to_providers_dict()

    import os
    for p in providers_dict["providers"]:
        env_key = p.get("api_key_env", "")
        if env_key:
            p["api_key_configured"] = bool(os.environ.get(env_key, "").strip())
        else:
            p["api_key_configured"] = True  # local/no-key providers
        # Annotate per-provider model count from catalog
        pid = p.get("provider_id", "")
        p["model_count"] = len(catalog.models_for_provider(pid))

    provider_count = providers_dict.get("total", 0)
    return {
        **providers_dict,
        "provider_count": provider_count,
        "total_models": catalog.model_count(),
        "note": "api_key_configured shows whether env var is set. No key values are returned.",
        "kimi_benchmark_status": (
            "BENCHMARK_ACCEPTED" if catalog.kimi_benchmarked() else "NOT_BENCHMARKED"
        ),
        "ollama_policy": "Ollama/local models are OFFLINE FALLBACK ONLY. Not for normal chat or cloud work.",
        "pa_front_door_policy": "PA uses GPT/OpenAI stable route only (openai/gpt-4o, openai/gpt-4o-mini).",
    }


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/models
# ---------------------------------------------------------------------------

@router.get("/v1/model-catalog/models")
async def get_model_catalog_models(
    provider_id: Optional[str] = Query(None, description="Filter by provider"),
    capability: Optional[str] = Query(None, description="Filter by capability tag"),
    exclude_fallback: bool = Query(False, description="Exclude offline_fallback models"),
    kimi_only: bool = Query(False, description="Show only Kimi models"),
) -> Dict[str, Any]:
    """Return full normalized model catalog with capability tags and metadata."""
    catalog = get_provider_catalog()
    models = catalog.all_models

    if provider_id:
        models = [m for m in models if m.provider_id == provider_id]

    if capability:
        try:
            cap_tag = CapabilityTag(capability)
            models = [m for m in models if m.has_capability(cap_tag)]
        except ValueError:
            pass

    if exclude_fallback:
        models = [m for m in models if not m.is_offline_fallback]

    if kimi_only:
        models = [m for m in models if m.is_kimi]

    return {
        "total": len(models),
        "total_catalog": catalog.model_count(),
        "total_non_fallback": len(catalog.non_fallback_models()),
        "kimi_benchmarked": catalog.kimi_benchmarked(),
        "filters_applied": {
            "provider_id": provider_id,
            "capability": capability,
            "exclude_fallback": exclude_fallback,
            "kimi_only": kimi_only,
        },
        "models": [m.to_dict() for m in models],
    }


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/capabilities
# ---------------------------------------------------------------------------

@router.get("/v1/model-catalog/capabilities")
async def get_model_catalog_capabilities() -> Dict[str, Any]:
    """Return all capability tags and which models support each."""
    catalog = get_provider_catalog()
    summary = catalog.capability_summary()

    return {
        "total_capability_tags": len(summary),
        "capability_tags": sorted(summary.keys()),
        "capabilities": {
            tag: {
                "models": model_ids,
                "model_count": len(model_ids),
            }
            for tag, model_ids in sorted(summary.items())
        },
        "note": (
            "offline_fallback models are included in capability lists "
            "but are only selected in fallback/offline mode. "
            "kimi models require benchmark acceptance before routing."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/model-routing/status
# ---------------------------------------------------------------------------

@router.get("/v1/model-routing/status")
async def get_model_routing_status() -> Dict[str, Any]:
    """Return current routing system status for HUD display."""
    from openjarvis.plan9.heavy_coding_policy import (
        all_provider_key_status,
        get_target_model_availability,
    )
    router_inst = get_specialized_router()
    catalog = get_provider_catalog()
    decls = get_role_declarations()

    status = router_inst.routing_status()
    key_status = all_provider_key_status()
    target_avail = get_target_model_availability(catalog)

    # Provider health summary (supports alternate env var names)
    provider_health = {}
    for p in catalog.all_providers:
        if p.is_local:
            provider_health[p.provider_id] = "local"
        elif p.provider_id in key_status:
            provider_health[p.provider_id] = (
                "configured" if key_status[p.provider_id]["configured"] else "not_configured"
            )
        elif p.api_key_env:
            import os
            configured = bool(os.environ.get(p.api_key_env, "").strip())
            provider_health[p.provider_id] = "configured" if configured else "not_configured"
        else:
            provider_health[p.provider_id] = "no_key_required"

    return {
        **status,
        "provider_health": provider_health,
        "provider_key_status": key_status,
        "target_model_availability": target_avail,
        "active_routing_policy": (
            "dynamic_specialized_per_role; "
            "heavy_coding: GLM-5.2 > Kimi K2.6 > catalog > Sonnet(high-risk only)"
        ),
        "heavy_coding_route_preference": status.get(
            "heavy_coding_route_preference",
            "GLM-5.2 → Kimi K2.6 → best coding catalog model",
        ),
        "current_task_route": None,
        "fallback_events": [],
        "benchmark_status": {
            "kimi": "KIMI_NOT_BENCHMARKED" if not catalog.kimi_benchmarked() else "ACCEPTED",
            "glm": (
                "GLM_NOT_FULLY_BENCHMARK_ACCEPTED"
                if not status.get("glm_benchmarked")
                else "ACCEPTED"
            ),
        },
        "policy_labels": status.get("policy_labels", {}),
        "glm_5_2_available": any(
            v.get("status") == "AVAILABLE"
            for v in target_avail.get("glm_5_2", {}).values()
        ),
        "kimi_k2_6_available": any(
            v.get("status") == "AVAILABLE"
            for v in target_avail.get("kimi_k2_6", {}).values()
        ),
        "blocked_providers": [
            p.provider_id for p in catalog.all_providers
            if provider_health.get(p.provider_id) == "not_configured"
            and not p.is_local and p.provider_id != "openrouter"
        ],
        "role_declaration_coverage": len(decls),
        "pa_front_door_model": "openai/gpt-4o",
        "pa_cheap_model": "openai/gpt-4o-mini",
        "unknown_needs_metadata": status.get("catalog_summary", {}).get(
            "unknown_needs_metadata", 0
        ),
        "last_updated": time.time(),
    }


# ---------------------------------------------------------------------------
# POST /v1/model-routing/explain
# ---------------------------------------------------------------------------

@router.post("/v1/model-routing/explain")
async def explain_model_routing_9k(req: ModelRouteExplainRequest9K) -> Dict[str, Any]:
    """Explain why a specific model would be selected for a role/task."""
    router_inst = get_specialized_router()
    explanation = router_inst.explain(
        role_id=req.role,
        task_description=req.task,
        task_classification=req.task_classification,
        force_fallback=req.force_fallback,
    )

    # Append to audit log
    _append_audit(
        action="explain",
        role_id=req.role,
        task=req.task,
        chosen_model=explanation["decision"]["chosen_model_id"],
        route_reason=explanation["decision"]["route_reason"],
    )

    return {
        "role": req.role,
        "task": req.task,
        "task_classification": req.task_classification,
        "temporary_heavy_coding_policy_applied": explanation["decision"].get(
            "heavy_coding_preference_applied", False
        ),
        "policy_labels": explanation["decision"].get("policy_labels", []),
        **explanation,
    }


# ---------------------------------------------------------------------------
# POST /v1/model-routing/select
# ---------------------------------------------------------------------------

@router.post("/v1/model-routing/select")
async def select_model_for_role(req: ModelRouteExplainRequest9K) -> Dict[str, Any]:
    """Select the best model for a role/task and return the routing decision.

    This is a read-only routing selection — no actual model call is made.
    """
    router_inst = get_specialized_router()
    decision = router_inst.select(
        role_id=req.role,
        task_description=req.task,
        task_classification=req.task_classification,
        force_fallback=req.force_fallback,
    )

    _append_audit(
        action="select",
        role_id=req.role,
        task=req.task,
        chosen_model=decision.chosen_model_id,
        route_reason=decision.route_reason,
    )

    return {
        "role": req.role,
        "task": req.task,
        "force_fallback": req.force_fallback,
        "decision": decision.to_dict(),
        "audit_note": "Routing selection logged to /v1/model-routing/audit",
    }


# ---------------------------------------------------------------------------
# GET /v1/model-routing/audit
# ---------------------------------------------------------------------------

@router.get("/v1/model-routing/audit")
async def get_routing_audit(
    role_filter: Optional[str] = Query(None, description="Filter by role_id"),
    limit: int = Query(50, ge=1, le=200, description="Max entries to return"),
) -> Dict[str, Any]:
    """Return routing audit log (session-only, not persisted to disk)."""
    entries = list(_ROUTING_AUDIT_LOG)

    if role_filter:
        entries = [e for e in entries if e.get("role_id") == role_filter]

    entries = entries[-limit:]

    return {
        "total": len(_ROUTING_AUDIT_LOG),
        "returned": len(entries),
        "role_filter": role_filter,
        "entries": entries,
        "note": "Audit log is session-only (in-memory). Not persisted to disk.",
    }


# ---------------------------------------------------------------------------
# POST /v1/model-routing/benchmark/plan
# ---------------------------------------------------------------------------

@router.post("/v1/model-routing/benchmark/plan")
async def benchmark_plan(req: BenchmarkPlanRequest) -> Dict[str, Any]:
    """Plan a Kimi benchmark. Always dry-run from this route.

    Real benchmark execution requires Bryan approval and explicit activation.
    This route returns the benchmark plan, task list, and what evidence would
    be collected, without running any actual model calls.
    """
    catalog = get_provider_catalog()
    model = catalog.get_model(req.model_id)

    if model is None:
        return {
            "status": "MODEL_NOT_FOUND",
            "model_id": req.model_id,
            "message": f"Model {req.model_id!r} not in catalog. Cannot plan benchmark.",
        }

    if not model.is_kimi and req.model_id not in ["kimi/kimi-k2", "kimi/kimi-k2-0711-preview", "openrouter/moonshotai/kimi-k2"]:
        return {
            "status": "NOT_KIMI_MODEL",
            "model_id": req.model_id,
            "message": "Benchmark plan is currently only for Kimi models. Use explain/select for other models.",
        }

    benchmark_tasks = [
        {
            "task_type": t,
            "description": _BENCHMARK_TASK_DESCRIPTIONS.get(t, t),
            "comparison_model": "anthropic/claude-sonnet-4-20250514",
            "evaluation_criteria": ["pass/fail", "tests_passed", "diff_quality", "hallucination_notes", "cost_latency"],
        }
        for t in req.task_types
    ]

    return {
        "status": "DRY_RUN_PLAN",
        "mode": "DRY_RUN",
        "model_id": req.model_id,
        "current_benchmark_status": model.benchmark_status.value,
        "current_kimi_default_status": "NOT_DEFAULT_PENDING_BENCHMARK",
        "dry_run": True,
        "approval_required": True,
        "approval_note": (
            "Benchmark execution requires Bryan approval. "
            "This plan shows what would be tested. "
            "No model calls are made from this endpoint."
        ),
        "benchmark_plan": {
            "model_to_test": req.model_id,
            "baseline_comparison_model": "anthropic/claude-sonnet-4-20250514",
            "task_count": len(benchmark_tasks),
            "tasks": benchmark_tasks,
            "evidence_required": [
                "task_description",
                "model_used",
                "pass_fail",
                "tests_passed",
                "diff_quality",
                "hallucination_missed_requirement_notes",
                "cost_usd_if_available",
                "latency_ms_if_available",
                "reviewer_verdict",
            ],
            "acceptance_threshold": (
                "All 6 task types must pass. "
                "No hallucination of repo structure. "
                "Diff quality >= baseline. "
                "Reviewer verdict: ACCEPT. "
                "Then: update benchmark_status=ACCEPTED and Kimi becomes eligible for routing."
            ),
        },
    }


# ---------------------------------------------------------------------------
# GET /v1/model-routing/benchmark/results
# ---------------------------------------------------------------------------

@router.get("/v1/model-routing/benchmark/results")
async def get_benchmark_results() -> Dict[str, Any]:
    """Return benchmark results for all models that have been benchmarked."""
    catalog = get_provider_catalog()

    results = []
    for model in catalog.all_models:
        if model.benchmark_status != BenchmarkStatus.NOT_BENCHMARKED:
            results.append({
                "model_id": model.model_id,
                "provider_id": model.provider_id,
                "benchmark_status": model.benchmark_status.value,
                "benchmark_scores": model.benchmark_scores,
                "is_kimi": model.is_kimi,
            })

    kimi_models = catalog.kimi_models()
    kimi_statuses = {m.model_id: m.benchmark_status.value for m in kimi_models}

    return {
        "total_benchmarked": len(results),
        "kimi_benchmarked": catalog.kimi_benchmarked(),
        "kimi_eligible_for_routing": catalog.kimi_benchmarked(),
        "kimi_models": kimi_statuses,
        "results": results,
        "note": (
            "Kimi models are eligible for routing ONLY after benchmark_status=ACCEPTED. "
            "Currently: all Kimi models are NOT_BENCHMARKED. "
            "Use POST /v1/model-routing/benchmark/plan to plan a benchmark run."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/model-catalog/summary
# ---------------------------------------------------------------------------

@router.get("/v1/model-catalog/summary")
async def get_model_catalog_summary() -> Dict[str, Any]:
    """Return model catalog summary including discovery status."""
    catalog = get_provider_catalog()
    summary = catalog.catalog_summary()
    last_report = get_last_discovery_report()

    import os
    from openjarvis.plan9.heavy_coding_policy import (
        all_provider_key_status,
        get_target_model_availability,
    )
    discovery_status: Dict[str, Any] = {}
    key_status = all_provider_key_status()
    for p in catalog.all_providers:
        env_key = p.api_key_env
        alt = key_status.get(p.provider_id, {})
        has_key = alt.get("configured", False) if alt else (
            bool(os.environ.get(env_key, "").strip()) if env_key else True
        )
        discovery_status[p.provider_id] = {
            "has_key": has_key,
            "is_local": p.is_local,
            "supports_model_list": p.supports_model_list,
            "static_model_count": len(catalog.models_for_provider(p.provider_id)),
            "status": (
                "key_configured" if has_key and not p.is_local
                else "local" if p.is_local
                else "key_missing"
            ),
            "required_env_var": alt.get("env_var", env_key),
        }

    return {
        **summary,
        "target_model_availability": get_target_model_availability(catalog),
        "provider_key_status": key_status,
        "discovery_status_per_provider": discovery_status,
        "last_discovery_run": last_report.to_dict() if last_report else None,
        "discovery_note": (
            "Use POST /v1/model-catalog/discover to trigger live discovery. "
            "Providers without API keys use static metadata baseline."
        ),
    }


# ---------------------------------------------------------------------------
# POST /v1/model-catalog/discover  (triggers live discovery, returns report)
# ---------------------------------------------------------------------------

@router.post("/v1/model-catalog/discover")
async def trigger_model_catalog_discovery(
    providers: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Trigger model catalog discovery from configured provider APIs.

    Results are merged into the running catalog. New models without
    capability metadata are marked UNKNOWN_NEEDS_METADATA.

    Safe to call repeatedly; results are cached for 5 minutes.
    """
    catalog = get_provider_catalog()
    before = catalog.model_count()

    try:
        report = await run_catalog_discovery(catalog=catalog, providers=providers)
    except Exception as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
            "models_before": before,
            "models_after": catalog.model_count(),
        }

    return {
        "status": "COMPLETE",
        "models_before": report.total_models_before,
        "models_after": report.total_models_after,
        "new_models_discovered": report.total_new_models_added,
        "providers_live": report.total_live,
        "duration_ms": report.duration_ms,
        "providers": {pid: r.to_dict() for pid, r in report.results.items()},
        "note": (
            "New models without capability tags are marked UNKNOWN_NEEDS_METADATA "
            "and excluded from routing until tagged."
        ),
    }


# ---------------------------------------------------------------------------
# GET /v1/model-routing/inheritance
# ---------------------------------------------------------------------------

@router.get("/v1/model-routing/inheritance")
async def get_routing_inheritance() -> Dict[str, Any]:
    """Return Plan 9K inheritance policy and role coverage report."""
    coverage = get_inheritance_coverage()
    return {
        **coverage,
        "summary": (
            "All new roles automatically inherit dynamic catalog routing, "
            "fallback/escalation behavior, audit requirements, and capability declarations. "
            "Roles without explicit declarations use the default policy. "
            "Roles missing required_capabilities fail validation."
        ),
    }


# ---------------------------------------------------------------------------
# POST /v1/model-routing/validate-role  (validate a new role definition)
# ---------------------------------------------------------------------------

@router.post("/v1/model-routing/validate-role")
async def validate_new_role(
    role_id: str,
    role_type: str = "worker",
    required_capabilities: Optional[List[str]] = Query(None),
    override_reason: str = "",
) -> Dict[str, Any]:
    """Validate a new role declaration against Plan 9K inheritance policy.

    Returns validation result: valid, errors, warnings, and the resolved declaration.
    """
    validator = RoleInheritanceValidator()

    from openjarvis.plan9.model_catalog_9k import CapabilityTag as CT
    caps = None
    if required_capabilities is not None:
        try:
            caps = [CT(c) for c in required_capabilities]
        except ValueError as exc:
            return {"valid": False, "errors": [str(exc)], "warnings": [], "declaration": None}

    result = validator.validate_new_role(
        role_id=role_id,
        role_type=role_type,
        required_capabilities=caps,
        override_reason=override_reason,
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _append_audit(
    action: str,
    role_id: str,
    task: str,
    chosen_model: str,
    route_reason: str,
) -> None:
    global _ROUTING_AUDIT_LOG
    _ROUTING_AUDIT_LOG.append({
        "action": action,
        "role_id": role_id,
        "task": task[:100],
        "chosen_model": chosen_model,
        "route_reason": route_reason[:200],
        "timestamp": time.time(),
    })
    # Keep log bounded
    if len(_ROUTING_AUDIT_LOG) > _MAX_AUDIT_ENTRIES:
        _ROUTING_AUDIT_LOG = _ROUTING_AUDIT_LOG[-_MAX_AUDIT_ENTRIES:]


_BENCHMARK_TASK_DESCRIPTIONS: Dict[str, str] = {
    "backend_route_task": "Implement a FastAPI route with proper validation, error handling, and tests",
    "frontend_ui_task": "Build a React component with TypeScript and proper styling",
    "test_fix_task": "Fix a failing test suite and explain root cause",
    "broad_file_repo_understanding": "Analyze repository structure and explain architecture across 20+ files",
    "documentation_task": "Generate comprehensive API documentation from source code",
    "code_review_task": "Review a PR diff for bugs, security issues, and code quality",
}


__all__ = ["router"]
