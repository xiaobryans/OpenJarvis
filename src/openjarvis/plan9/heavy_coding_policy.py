"""Plan 9K — Temporary heavy-coding route preference (benchmark sprint ON HOLD).

Normal heavy coding / implementation tasks prefer GLM-5.2, then Kimi K2.6,
then best eligible coding-specialized catalog model. Sonnet remains
high-risk/final-review only. This is dynamic candidate-based routing, not a
permanent fixed global model assignment.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

from openjarvis.plan9.model_catalog_9k import (
    CapabilityTag,
    ModelEntry9K,
    ProviderCatalog9K,
)

# ---------------------------------------------------------------------------
# Policy labels (audit / HUD)
# ---------------------------------------------------------------------------

class RoutingPolicyLabel(str, Enum):
    GLM_5_2_CURRENT_PREFERRED_HEAVY_CODING_ROUTE_PENDING_BENCHMARK = (
        "GLM_5_2_CURRENT_PREFERRED_HEAVY_CODING_ROUTE_PENDING_BENCHMARK"
    )
    KIMI_K2_6_SECONDARY_HEAVY_CODING_ROUTE_PENDING_BENCHMARK = (
        "KIMI_K2_6_SECONDARY_HEAVY_CODING_ROUTE_PENDING_BENCHMARK"
    )
    KIMI_NOT_BENCHMARKED = "KIMI_NOT_BENCHMARKED"
    GLM_NOT_FULLY_BENCHMARK_ACCEPTED = "GLM_NOT_FULLY_BENCHMARK_ACCEPTED"
    SONNET_HIGH_RISK_FINAL_REVIEW_ROUTE = "SONNET_HIGH_RISK_FINAL_REVIEW_ROUTE"
    OLLAMA_LOCAL_FALLBACK_ONLY = "OLLAMA_LOCAL_FALLBACK_ONLY"


# Task classifications that trigger heavy-coding preference
HEAVY_CODING_CLASSIFICATIONS = frozenset({
    "normal_heavy_coding",
    "normal_implementation",
    "backend_implementation",
    "frontend_implementation",
    "test_fix",
    "repo_refactor",
    "coding",
    "implementation",
})

# Roles that are coding-oriented (manager/worker with CODING cap, not high-risk review)
HEAVY_CODING_ROLE_IDS = frozenset({
    "coding_manager",
    "frontend_worker",
    "backend_worker",
    "documentation_worker",
    "testing_validation_manager",
})

# Roles explicitly excluded from GLM/Kimi heavy-coding preference
HEAVY_CODING_EXCLUDED_ROLES = frozenset({
    "jarvis_pa",
    "cos_gm",
    "architecture_manager",
    "security_review_manager",
    "billing_iam_review_manager",
    "secrets_review_manager",
    "deploy_review_manager",
    "final_review_manager",
    "integration_review_manager",
    "research_manager",
    "local_research_worker",
    "code_review_manager",
})

HIGH_RISK_CAPABILITY_TRIGGERS = frozenset({
    CapabilityTag.SECURITY_REVIEW,
    CapabilityTag.BILLING_IAM_REVIEW,
    CapabilityTag.SECRETS_REVIEW,
    CapabilityTag.DEPLOY_REVIEW,
    CapabilityTag.FINAL_REVIEW,
    CapabilityTag.HIGH_REASONING,
})

# Canonical model id substrings (case-insensitive)
GLM_5_2_PATTERNS = (
    "glm-5.2",
    "glm-5-2",
    "glm5.2",
    "glm-5_2",
    "z-ai/glm-5",
    "zhipu/glm-5",
)

KIMI_K2_6_PATTERNS = (
    "kimi-k2.6",
    "kimi-k2-6",
    "k2.6",
    "k2-6",
    "moonshotai/kimi-k2.6",
    "moonshotai/kimi-k2-6",
)

# Provider env var aliases (presence only — never read values)
PROVIDER_KEY_ENV_VARS: Dict[str, Tuple[str, ...]] = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "aimlapi": ("AIMLAPI_API_KEY", "AIMLAPI_KEY"),
    "zai": ("ZAI_API_KEY", "GLM_API_KEY"),
    "kimi": ("KIMI_API_KEY", "MOONSHOT_API_KEY"),
}

TARGET_MODELS = {
    "glm-5.2": {
        "display": "GLM-5.2",
        "patterns": GLM_5_2_PATTERNS,
        "providers": ("openrouter", "aimlapi", "zai"),
    },
    "kimi-k2.6": {
        "display": "Kimi K2.6",
        "patterns": KIMI_K2_6_PATTERNS,
        "providers": ("openrouter", "aimlapi", "kimi"),
    },
}


def _norm(mid: str) -> str:
    return mid.lower().replace("_", "-")


def matches_model_pattern(model_id: str, patterns: Sequence[str]) -> bool:
    n = _norm(model_id)
    return any(p.lower().replace("_", "-") in n for p in patterns)


def is_glm_model(model_id: str) -> bool:
    n = _norm(model_id)
    return "glm" in n or n.startswith("zai/")


def is_glm_52_model(model_id: str) -> bool:
    return matches_model_pattern(model_id, GLM_5_2_PATTERNS)


def is_kimi_family_model(model_id: str, provider_id: str = "") -> bool:
    n = _norm(model_id)
    if provider_id == "kimi":
        return True
    return "kimi" in n or "moonshot" in n


def is_kimi_k26_model(model_id: str) -> bool:
    return matches_model_pattern(model_id, KIMI_K2_6_PATTERNS)


def is_sonnet_model(model_id: str) -> bool:
    n = _norm(model_id)
    return "claude-sonnet" in n or "claude-sonnet" in n


def env_key_configured(*env_names: str) -> Tuple[bool, str]:
    """Return (configured, primary_env_var_name). Never exposes key value."""
    from openjarvis.core.env_loader import ensure_local_env_loaded
    ensure_local_env_loaded()
    for name in env_names:
        if os.environ.get(name, "").strip():
            return True, name
    return False, env_names[0] if env_names else ""


def provider_key_status(provider_id: str) -> Dict[str, Any]:
    """Report API key presence for a provider without exposing values."""
    env_names = PROVIDER_KEY_ENV_VARS.get(provider_id)
    if not env_names:
        return {"configured": True, "env_var": "", "status": "NO_KEY_REQUIRED"}
    configured, primary = env_key_configured(*env_names)
    if configured:
        return {"configured": True, "env_var": primary, "status": "KEY_CONFIGURED"}
    return {
        "configured": False,
        "env_var": env_names[0],
        "alternate_env_vars": list(env_names[1:]),
        "status": "API_KEY_MISSING",
    }


def all_provider_key_status() -> Dict[str, Dict[str, Any]]:
    from openjarvis.core.env_loader import ensure_local_env_loaded, provider_key_status_table
    ensure_local_env_loaded()
    table = provider_key_status_table()
    # Map to legacy shape used by routes
    legacy: Dict[str, Dict[str, Any]] = {}
    pid_map = {
        "OPENROUTER_API_KEY": "openrouter",
        "AIMLAPI_API_KEY": "aimlapi",
        "ZAI_API_KEY": "zai",
        "KIMI_API_KEY": "kimi",
    }
    for canonical, info in table.items():
        pid = pid_map.get(canonical, canonical.lower())
        legacy[pid] = {
            "configured": info["status"] == "PRESENT",
            "env_var": info["env_var"],
            "status": "KEY_CONFIGURED" if info["status"] == "PRESENT" else "API_KEY_MISSING",
            "source": info.get("source", "not_found"),
            "alternate_env_vars": info.get("alternate_env_vars", []),
        }
    return legacy


def is_high_risk_role(
    required_capabilities: List[CapabilityTag],
    risk_threshold: str,
    role_id: str = "",
) -> bool:
    if role_id in HEAVY_CODING_EXCLUDED_ROLES:
        if role_id in {
            "architecture_manager",
            "security_review_manager",
            "billing_iam_review_manager",
            "secrets_review_manager",
            "deploy_review_manager",
            "final_review_manager",
            "integration_review_manager",
        }:
            return True
    if risk_threshold in ("high", "critical"):
        if any(c in required_capabilities for c in HIGH_RISK_CAPABILITY_TRIGGERS):
            return True
    return any(c in required_capabilities for c in HIGH_RISK_CAPABILITY_TRIGGERS)


def is_heavy_coding_context(
    role_id: str,
    task_classification: str,
    required_capabilities: List[CapabilityTag],
    preferred_capabilities: Optional[List[CapabilityTag]] = None,
) -> bool:
    """True when temporary GLM/Kimi heavy-coding preference applies."""
    if role_id in HEAVY_CODING_EXCLUDED_ROLES:
        return False
    if task_classification in HEAVY_CODING_CLASSIFICATIONS:
        return True
    if role_id in HEAVY_CODING_ROLE_IDS:
        return True
    caps = set(required_capabilities) | set(preferred_capabilities or [])
    if CapabilityTag.CODING in caps and CapabilityTag.HIGH_REASONING not in caps:
        if role_id.endswith("_worker") or role_id.endswith("_manager"):
            if role_id not in HEAVY_CODING_EXCLUDED_ROLES:
                return True
    return False


def is_heavy_coding_context_for_decl(
    role_id: str,
    task_classification: str,
    required_capabilities: List[CapabilityTag],
    preferred_capabilities: List[CapabilityTag],
    risk_threshold: str,
) -> bool:
    if is_high_risk_role(required_capabilities, risk_threshold.value if hasattr(risk_threshold, "value") else str(risk_threshold), role_id):
        return False
    return is_heavy_coding_context(
        role_id, task_classification, required_capabilities, preferred_capabilities
    )


def model_matches_target(model: ModelEntry9K, target: str) -> bool:
    info = TARGET_MODELS.get(target)
    if not info:
        return False
    return matches_model_pattern(model.model_id, info["patterns"])


def find_catalog_models_for_target(
    catalog: ProviderCatalog9K,
    target: str,
    provider_id: Optional[str] = None,
) -> List[ModelEntry9K]:
    info = TARGET_MODELS.get(target)
    if not info:
        return []
    results: List[ModelEntry9K] = []
    for m in catalog.all_models:
        if provider_id and m.provider_id != provider_id:
            continue
        if matches_model_pattern(m.model_id, info["patterns"]):
            results.append(m)
    return results


def get_target_model_availability(catalog: ProviderCatalog9K) -> Dict[str, Any]:
    """Report GLM-5.2 and Kimi K2.6 availability per provider (no secrets)."""
    report: Dict[str, Any] = {
        "provider_keys": all_provider_key_status(),
        "glm_5_2": {},
        "kimi_k2_6": {},
        "keys_still_needed": [],
    }

    for target, key in (("glm-5.2", "glm_5_2"), ("kimi-k2.6", "kimi_k2_6")):
        info = TARGET_MODELS[target]
        target_report: Dict[str, Any] = {}
        for provider_id in info["providers"]:
            key_status = provider_key_status(provider_id)
            matches = find_catalog_models_for_target(catalog, target, provider_id)
            available = [m for m in matches if m.is_available]
            if available:
                status = "AVAILABLE"
                model_ids = [m.model_id for m in available]
            elif matches:
                status = "MODEL_UNAVAILABLE"
                model_ids = [m.model_id for m in matches]
            elif not key_status["configured"] and provider_id != "openrouter":
                status = "API_KEY_MISSING"
                model_ids = []
            else:
                status = "MODEL_UNAVAILABLE"
                model_ids = []
                # Closest coding alternatives from same provider
            alts: List[str] = []
            if not available and key_status["configured"]:
                for m in catalog.models_for_provider(provider_id):
                    if CapabilityTag.CODING in m.capability_tags and m.is_available:
                        alts.append(m.model_id)
                        if len(alts) >= 3:
                            break
            target_report[provider_id] = {
                "status": status,
                "model_ids": model_ids,
                "api_key_status": key_status["status"],
                "required_env_var": key_status.get("env_var", ""),
                "closest_alternatives": alts[:3] if not available else [],
            }
            if key_status["status"] == "API_KEY_MISSING":
                report["keys_still_needed"].append({
                    "provider": provider_id,
                    "env_var": key_status["env_var"],
                    "alternate_env_vars": key_status.get("alternate_env_vars", []),
                })
        report[key] = target_report

    return report


def reorder_heavy_coding_candidates(
    candidates: List[str],
    catalog: ProviderCatalog9K,
    inject_from_catalog: bool = True,
) -> Tuple[List[str], List[str]]:
    """Reorder candidates: GLM-5.2 first, Kimi K2.6 second, then rest.

    Returns (reordered_candidates, policy_labels_applied).
    """
    seen: set = set()
    glm_ids: List[str] = []
    kimi_ids: List[str] = []
    rest: List[str] = []

    def _classify(mid: str) -> None:
        if mid in seen:
            return
        seen.add(mid)
        if is_glm_52_model(mid):
            glm_ids.append(mid)
        elif is_kimi_k26_model(mid):
            kimi_ids.append(mid)
        else:
            rest.append(mid)

    for mid in candidates:
        _classify(mid)

    if inject_from_catalog:
        for m in catalog.all_models:
            if not m.is_available or m.is_offline_fallback:
                continue
            if is_glm_52_model(m.model_id):
                _classify(m.model_id)
            elif is_kimi_k26_model(m.model_id):
                _classify(m.model_id)

    labels: List[str] = []
    if glm_ids:
        labels.append(
            RoutingPolicyLabel.GLM_5_2_CURRENT_PREFERRED_HEAVY_CODING_ROUTE_PENDING_BENCHMARK.value
        )
    if kimi_ids:
        labels.append(
            RoutingPolicyLabel.KIMI_K2_6_SECONDARY_HEAVY_CODING_ROUTE_PENDING_BENCHMARK.value
        )

    return glm_ids + kimi_ids + rest, labels


def kimi_allowed_for_route(
    model: ModelEntry9K,
    kimi_benchmarked: bool,
    heavy_coding: bool,
) -> Tuple[bool, Optional[str]]:
    """Whether Kimi model may be selected. Returns (allowed, rejection_reason)."""
    if not is_kimi_family_model(model.model_id, model.provider_id):
        return True, None
    if kimi_benchmarked:
        return True, None
    if heavy_coding and is_kimi_k26_model(model.model_id):
        return True, None
    if heavy_coding and is_kimi_family_model(model.model_id, model.provider_id):
        # Older Kimi K2 variants: secondary only if K2.6 not the target
        return True, None
    return False, "Kimi requires benchmark proof (KIMI_NOT_BENCHMARKED)"


def glm_allowed_for_route(
    model: ModelEntry9K,
    glm_benchmarked: bool,
    heavy_coding: bool,
    high_risk: bool,
) -> Tuple[bool, Optional[str]]:
    if not is_glm_model(model.model_id):
        return True, None
    if high_risk:
        return False, "GLM forbidden for high-risk/security/deploy/final-review roles"
    if glm_benchmarked:
        return True, None
    if heavy_coding and is_glm_52_model(model.model_id):
        return True, None
    if heavy_coding:
        return True, None
    return False, "GLM not fully benchmark-accepted for this route class"


def build_policy_labels_for_decision(
    model: ModelEntry9K,
    heavy_coding: bool,
    high_risk: bool,
    force_fallback: bool,
    kimi_benchmarked: bool,
    glm_benchmarked: bool,
    heavy_coding_labels: List[str],
) -> List[str]:
    labels = list(heavy_coding_labels)
    if force_fallback or model.is_offline_fallback:
        labels.append(RoutingPolicyLabel.OLLAMA_LOCAL_FALLBACK_ONLY.value)
    if is_kimi_family_model(model.model_id, model.provider_id) and not kimi_benchmarked:
        labels.append(RoutingPolicyLabel.KIMI_NOT_BENCHMARKED.value)
    if is_glm_model(model.model_id) and not glm_benchmarked:
        labels.append(RoutingPolicyLabel.GLM_NOT_FULLY_BENCHMARK_ACCEPTED.value)
    if high_risk and is_sonnet_model(model.model_id):
        labels.append(RoutingPolicyLabel.SONNET_HIGH_RISK_FINAL_REVIEW_ROUTE.value)
    return list(dict.fromkeys(labels))  # dedupe preserve order


def glm_benchmarked(catalog: ProviderCatalog9K) -> bool:
    from openjarvis.plan9.model_catalog_9k import BenchmarkStatus
    for m in catalog.all_models:
        if is_glm_model(m.model_id) and m.benchmark_status == BenchmarkStatus.ACCEPTED:
            return True
    return False
