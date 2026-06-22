"""Plan 9K — Provider Model Discovery Layer.

Attempts to discover available models from configured provider APIs.
Falls back to static metadata when API keys are missing or APIs fail.

Discovery status per provider:
  LIVE              - models actively fetched from provider API
  API_KEY_MISSING   - env var set in PROVIDERS but no key found at runtime
  API_UNREACHABLE   - key present but HTTP call failed/timed out
  NOT_APPLICABLE    - provider does not expose model list endpoint
  STATIC_METADATA   - using local normalized static catalog entries
  LOCAL_ONLY        - Ollama/local — uses local /api/tags endpoint

Merge policy:
  - Static metadata is the authoritative source for capability_tags, allowed_risk_level,
    and notes (provider APIs don't expose these).
  - Live-discovered models that have no static metadata entry are added as
    UNKNOWN_NEEDS_METADATA and excluded from routing until tagged.
  - Static metadata entries that are NOT in the live list are marked UNAVAILABLE
    (if the provider was reachable).

This module never makes blocking calls at import time. All discovery is triggered
explicitly via `CatalogDiscoveryManager.discover()` or the API endpoint.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

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


# ---------------------------------------------------------------------------
# Discovery status
# ---------------------------------------------------------------------------

class ProviderDiscoveryStatus(str, Enum):
    LIVE = "live"
    API_KEY_MISSING = "api_key_missing"
    API_UNREACHABLE = "api_unreachable"
    NOT_APPLICABLE = "not_applicable"       # provider has no model-list API
    STATIC_METADATA = "static_metadata"
    LOCAL_ONLY = "local_only"
    NOT_ATTEMPTED = "not_attempted"


@dataclass
class ProviderDiscoveryResult:
    provider_id: str
    status: ProviderDiscoveryStatus
    models_found: int = 0
    models_new: int = 0             # models not in static catalog
    models_unavailable: int = 0     # in static but not in live list
    blocker: str = ""
    elapsed_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "status": self.status.value,
            "models_found": self.models_found,
            "models_new": self.models_new,
            "models_unavailable": self.models_unavailable,
            "blocker": self.blocker,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Per-provider discovery adapters
# ---------------------------------------------------------------------------

_DISCOVERY_TIMEOUT = 8.0   # seconds per provider


async def _get_json(url: str, headers: Optional[Dict] = None, timeout: float = _DISCOVERY_TIMEOUT) -> Optional[Any]:
    """Async GET returning parsed JSON, or None on any error."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers or {})
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


async def _discover_openai(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="openai", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "OPENAI_API_KEY not set; using static metadata (3 models)"
        result.models_found = len(catalog.models_for_provider("openai"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.openai.com/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "OpenAI /v1/models call failed or timed out"
        return result

    models_data = data.get("data", [])
    _merge_discovered_models(
        catalog, "openai", models_data,
        id_field="id", name_field="id",
        result=result,
    )
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_openrouter(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    """OpenRouter public model list — no auth required for listing."""
    result = ProviderDiscoveryResult(provider_id="openrouter", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    t0 = time.time()

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    data = await _get_json("https://openrouter.ai/api/v1/models", headers=headers)
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "OpenRouter /api/v1/models unreachable"
        result.models_found = len(catalog.models_for_provider("openrouter"))
        return result

    models_data = data.get("data", [])
    _merge_discovered_openrouter(catalog, models_data, result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


def _merge_discovered_openrouter(
    catalog: ProviderCatalog9K,
    models_data: List[Dict],
    result: ProviderDiscoveryResult,
) -> None:
    """Merge OpenRouter model list into catalog.

    OpenRouter model IDs look like 'anthropic/claude-sonnet-4-20250514'.
    We prefix them with 'openrouter/' to disambiguate.
    """
    static_or_ids = {m.model_id for m in catalog.models_for_provider("openrouter")}

    for raw in models_data:
        raw_id = raw.get("id", "")
        if not raw_id:
            continue

        catalog_id = f"openrouter/{raw_id}"
        result.models_found += 1

        if catalog_id in {m.model_id for m in catalog.all_models}:
            continue  # Already in catalog (static entry)

        # New model — add as UNKNOWN_NEEDS_METADATA
        ctx = raw.get("context_length") or 0
        pricing = raw.get("pricing", {})
        try:
            in_cost = float(pricing.get("prompt", 0)) * 1_000_000  # per-token → per-mtok
        except (TypeError, ValueError):
            in_cost = 0.0
        try:
            out_cost = float(pricing.get("completion", 0)) * 1_000_000
        except (TypeError, ValueError):
            out_cost = 0.0

        new_model = ModelEntry9K(
            model_id=catalog_id,
            display_name=raw.get("name", raw_id),
            provider_id="openrouter",
            context_window=int(ctx),
            input_cost_per_mtok=in_cost,
            output_cost_per_mtok=out_cost,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset(),    # UNKNOWN until tagged
            allowed_risk_level=AllowedRiskLevel.LOW,
            model_status=ModelStatus.UNKNOWN_NEEDS_METADATA,
            discovery_source="openrouter",
            notes=f"Discovered via OpenRouter API. Capability tags required before routing.",
        )
        catalog.add_discovered_model(new_model)
        result.models_new += 1


async def _discover_anthropic(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="anthropic", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "ANTHROPIC_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("anthropic"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.anthropic.com/v1/models",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "Anthropic /v1/models call failed or timed out"
        result.models_found = len(catalog.models_for_provider("anthropic"))
        return result

    models_data = data.get("data", [])
    _merge_discovered_models(
        catalog, "anthropic", models_data,
        id_field="id", name_field="display_name",
        result=result,
    )
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_kimi(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="kimi", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = (
        os.environ.get("KIMI_API_KEY", "").strip()
        or os.environ.get("MOONSHOT_API_KEY", "").strip()
    )
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "KIMI_API_KEY or MOONSHOT_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("kimi"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.moonshot.cn/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "Kimi /v1/models call failed or timed out"
        result.models_found = len(catalog.models_for_provider("kimi"))
        return result

    models_data = data.get("data", [])
    _merge_discovered_models(catalog, "kimi", models_data, id_field="id", name_field="id", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_google(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="google", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "GOOGLE_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("google"))
        return result

    t0 = time.time()
    data = await _get_json(
        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "Google Gemini models call failed"
        result.models_found = len(catalog.models_for_provider("google"))
        return result

    models_data = data.get("models", [])
    _merge_discovered_models(catalog, "google", models_data, id_field="name", name_field="displayName", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_deepseek(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="deepseek", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "DEEPSEEK_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("deepseek"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.deepseek.com/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "DeepSeek /models call failed"
        result.models_found = len(catalog.models_for_provider("deepseek"))
        return result

    models_data = data.get("data", [])
    _merge_discovered_models(catalog, "deepseek", models_data, id_field="id", name_field="id", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_mistral(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="mistral", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "MISTRAL_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("mistral"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.mistral.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "Mistral /v1/models call failed"
        result.models_found = len(catalog.models_for_provider("mistral"))
        return result

    models_data = data.get("data", [])
    _merge_discovered_models(catalog, "mistral", models_data, id_field="id", name_field="name", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_xai(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="xai", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "XAI_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("xai"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.x.ai/v1/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "xAI /v1/models call failed"
        result.models_found = len(catalog.models_for_provider("xai"))
        return result

    models_data = data.get("data", [])
    _merge_discovered_models(catalog, "xai", models_data, id_field="id", name_field="id", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_perplexity(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    """Perplexity does not expose a model listing API. Static metadata only."""
    result = ProviderDiscoveryResult(
        provider_id="perplexity",
        status=ProviderDiscoveryStatus.NOT_APPLICABLE,
        models_found=len(catalog.models_for_provider("perplexity")),
        blocker="Perplexity has no public model-list API. Using static metadata (sonar, sonar-pro).",
    )
    return result


async def _discover_aimlapi(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    result = ProviderDiscoveryResult(provider_id="aimlapi", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = (
        os.environ.get("AIMLAPI_API_KEY", "").strip()
        or os.environ.get("AIMLAPI_KEY", "").strip()
    )
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "AIMLAPI_API_KEY or AIMLAPI_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("aimlapi"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.aimlapi.com/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "AIMLAPI /models call failed"
        result.models_found = len(catalog.models_for_provider("aimlapi"))
        return result

    models_data = data if isinstance(data, list) else data.get("data", [])
    _merge_discovered_models(catalog, "aimlapi", models_data, id_field="id", name_field="name", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


async def _discover_ollama(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    """Ollama local server — no auth, offline only."""
    result = ProviderDiscoveryResult(provider_id="ollama", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    t0 = time.time()
    data = await _get_json("http://localhost:11434/api/tags", timeout=3.0)
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "Ollama server not running at localhost:11434; using static fallback entries"
        result.models_found = len(catalog.models_for_provider("ollama"))
        return result

    models_data = data.get("models", [])
    for raw in models_data:
        raw_id = raw.get("name", "")
        if not raw_id:
            continue
        catalog_id = f"ollama/{raw_id}"
        result.models_found += 1
        if catalog_id in {m.model_id for m in catalog.all_models}:
            continue
        # New local model — add as FALLBACK_ONLY
        new_model = ModelEntry9K(
            model_id=catalog_id,
            display_name=f"{raw_id} (Local Ollama)",
            provider_id="ollama",
            context_window=0,
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset({CapabilityTag.OFFLINE_FALLBACK}),
            allowed_risk_level=AllowedRiskLevel.LOW,
            model_status=ModelStatus.FALLBACK_ONLY,
            discovery_source="ollama_local",
            notes="OFFLINE FALLBACK ONLY. Discovered from local Ollama.",
        )
        catalog.add_discovered_model(new_model)
        result.models_new += 1

    result.status = ProviderDiscoveryStatus.LOCAL_ONLY
    return result


def _merge_discovered_models(
    catalog: ProviderCatalog9K,
    provider_id: str,
    models_data: List[Dict],
    id_field: str,
    name_field: str,
    result: ProviderDiscoveryResult,
) -> None:
    """Generic merge: add new models as UNKNOWN_NEEDS_METADATA if not in static catalog."""
    static_ids = {m.model_id for m in catalog.models_for_provider(provider_id)}

    for raw in models_data:
        raw_id = raw.get(id_field, "")
        if not raw_id:
            continue

        # Normalize: some providers use "provider/model" paths, others use bare IDs
        catalog_id = f"{provider_id}/{raw_id}" if "/" not in raw_id else raw_id
        result.models_found += 1

        if catalog_id in {m.model_id for m in catalog.all_models}:
            continue  # Already in catalog from static metadata

        raw_name = raw.get(name_field, raw_id) or raw_id
        new_model = ModelEntry9K(
            model_id=catalog_id,
            display_name=str(raw_name),
            provider_id=provider_id,
            context_window=int(raw.get("context_window") or raw.get("context_length") or 0),
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
            latency_class=LatencyClass.MEDIUM,
            capability_tags=frozenset(),    # UNKNOWN until tagged
            allowed_risk_level=AllowedRiskLevel.LOW,
            model_status=ModelStatus.UNKNOWN_NEEDS_METADATA,
            discovery_source="live_api",
            notes=f"Discovered via {provider_id} API. Requires capability tagging before routing.",
        )
        catalog.add_discovered_model(new_model)
        result.models_new += 1


# ---------------------------------------------------------------------------
# Discovery manager (orchestrates all providers)
# ---------------------------------------------------------------------------

async def _discover_zai(catalog: ProviderCatalog9K) -> ProviderDiscoveryResult:
    """Z.ai / GLM direct provider."""
    result = ProviderDiscoveryResult(provider_id="zai", status=ProviderDiscoveryStatus.NOT_ATTEMPTED)
    api_key = (
        os.environ.get("ZAI_API_KEY", "").strip()
        or os.environ.get("GLM_API_KEY", "").strip()
        or os.environ.get("Z.AI_API_KEY", "").strip()
    )
    if not api_key:
        result.status = ProviderDiscoveryStatus.API_KEY_MISSING
        result.blocker = "ZAI_API_KEY, GLM_API_KEY, or Z.AI_API_KEY not set; using static metadata"
        result.models_found = len(catalog.models_for_provider("zai"))
        return result

    t0 = time.time()
    data = await _get_json(
        "https://api.z.ai/api/paas/v4/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    result.elapsed_ms = (time.time() - t0) * 1000

    if data is None:
        result.status = ProviderDiscoveryStatus.API_UNREACHABLE
        result.blocker = "Z.ai /models call failed or timed out"
        result.models_found = len(catalog.models_for_provider("zai"))
        return result

    models_data = data.get("data", data if isinstance(data, list) else [])
    if isinstance(models_data, dict):
        models_data = models_data.get("data", [])
    _merge_discovered_models(catalog, "zai", models_data, id_field="id", name_field="id", result=result)
    result.status = ProviderDiscoveryStatus.LIVE
    return result


_ADAPTERS = {
    "openai": _discover_openai,
    "anthropic": _discover_anthropic,
    "kimi": _discover_kimi,
    "perplexity": _discover_perplexity,
    "google": _discover_google,
    "deepseek": _discover_deepseek,
    "mistral": _discover_mistral,
    "xai": _discover_xai,
    "openrouter": _discover_openrouter,
    "aimlapi": _discover_aimlapi,
    "zai": _discover_zai,
    "ollama": _discover_ollama,
}


@dataclass
class CatalogDiscoveryReport:
    results: Dict[str, ProviderDiscoveryResult] = field(default_factory=dict)
    total_providers_attempted: int = 0
    total_live: int = 0
    total_models_before: int = 0
    total_models_after: int = 0
    total_new_models_added: int = 0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "total_providers_attempted": self.total_providers_attempted,
            "total_live": self.total_live,
            "total_models_before": self.total_models_before,
            "total_models_after": self.total_models_after,
            "total_new_models_added": self.total_new_models_added,
            "duration_ms": round(self.duration_ms, 1),
            "timestamp": self.timestamp,
            "providers": {pid: r.to_dict() for pid, r in self.results.items()},
        }


# Cache: last discovery report (expires after TTL)
_LAST_REPORT: Optional[CatalogDiscoveryReport] = None
_REPORT_TTL = 300.0   # 5 minutes


async def run_catalog_discovery(
    catalog: Optional[ProviderCatalog9K] = None,
    providers: Optional[List[str]] = None,
) -> CatalogDiscoveryReport:
    """Run discovery for all (or specified) providers. Updates catalog in-place.

    This is intentionally async: do not call at import time.
    """
    from openjarvis.core.env_loader import ensure_local_env_loaded
    ensure_local_env_loaded()

    global _LAST_REPORT

    cat = catalog or get_provider_catalog()
    targets = providers or list(_ADAPTERS.keys())

    report = CatalogDiscoveryReport()
    report.total_models_before = cat.model_count()
    t0 = time.time()

    tasks = {pid: _ADAPTERS[pid](cat) for pid in targets if pid in _ADAPTERS}
    report.total_providers_attempted = len(tasks)

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    for pid, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            report.results[pid] = ProviderDiscoveryResult(
                provider_id=pid,
                status=ProviderDiscoveryStatus.API_UNREACHABLE,
                blocker=f"Exception: {result!r}",
            )
        else:
            report.results[pid] = result
            if result.status == ProviderDiscoveryStatus.LIVE:
                report.total_live += 1
            report.total_new_models_added += result.models_new

    report.total_models_after = cat.model_count()
    report.duration_ms = (time.time() - t0) * 1000
    _LAST_REPORT = report
    return report


def run_catalog_discovery_sync(
    catalog: Optional[ProviderCatalog9K] = None,
    providers: Optional[List[str]] = None,
) -> CatalogDiscoveryReport:
    """Synchronous wrapper for use in FastAPI route handlers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context — use asyncio.run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                run_catalog_discovery(catalog, providers), loop
            )
            return future.result(timeout=60)
        else:
            return loop.run_until_complete(run_catalog_discovery(catalog, providers))
    except RuntimeError:
        return asyncio.run(run_catalog_discovery(catalog, providers))


def get_last_discovery_report() -> Optional[CatalogDiscoveryReport]:
    """Return cached discovery report if within TTL."""
    global _LAST_REPORT
    if _LAST_REPORT is None:
        return None
    if time.time() - _LAST_REPORT.timestamp > _REPORT_TTL:
        return None
    return _LAST_REPORT


__all__ = [
    "ProviderDiscoveryStatus",
    "ProviderDiscoveryResult",
    "CatalogDiscoveryReport",
    "run_catalog_discovery",
    "run_catalog_discovery_sync",
    "get_last_discovery_report",
]
