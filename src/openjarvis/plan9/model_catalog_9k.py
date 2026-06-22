"""Plan 9K — Normalized Multi-Provider Model Catalog with Capability Tagging.

Covers: OpenAI, AIMLAPI, OpenRouter, Kimi/MoonshotAI, Perplexity/Sonar,
Anthropic/Claude, Gemini/Google, DeepSeek, Mistral, xAI/Grok, Ollama/local.

Rules enforced by this catalog:
- Kimi is NOT default for any role. Benchmark-gated for coding tasks.
- Ollama/Qwen/local models are OFFLINE_FALLBACK only.
  Forbidden for: normal_chat, default_chat, cloud_work.
- PA/front-door uses GPT/OpenAI-style stable route only.
- Security/billing/IAM/secrets/deploy/final_review: high_reasoning + trusted
  providers only. Local/cheap models FORBIDDEN for these roles.
- Perplexity/Sonar preferred for research/web-grounded tasks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Capability tags
# ---------------------------------------------------------------------------

class CapabilityTag(str, Enum):
    """All capability/specialty tags that can be assigned to a model."""
    DEFAULT_CHAT = "default_chat"
    CODING = "coding"
    REPO_SCALE_REFACTOR = "repo_scale_refactor"
    FRONTEND_UI = "frontend_ui"
    BACKEND_API = "backend_api"
    TEST_GENERATION = "test_generation"
    DEBUGGING = "debugging"
    RESEARCH = "research"
    WEB_GROUNDED = "web_grounded"
    CITATIONS = "citations"
    SOURCE_SYNTHESIS = "source_synthesis"
    LONG_CONTEXT = "long_context"
    DOCUMENT_ANALYSIS = "document_analysis"
    VISION = "vision"
    MULTIMODAL = "multimodal"
    STRUCTURED_OUTPUT = "structured_output"
    JSON_RELIABILITY = "json_reliability"
    TOOL_CALLING = "tool_calling"
    EXTRACTION = "extraction"
    SUMMARIZATION = "summarization"
    PLANNING = "planning"
    SECURITY_REVIEW = "security_review"
    BILLING_IAM_REVIEW = "billing_iam_review"
    SECRETS_REVIEW = "secrets_review"
    DEPLOY_REVIEW = "deploy_review"
    FINAL_REVIEW = "final_review"
    CHEAP_FAST = "cheap_fast"
    HIGH_REASONING = "high_reasoning"
    OFFLINE_FALLBACK = "offline_fallback"


# ---------------------------------------------------------------------------
# Latency / risk / benchmark
# ---------------------------------------------------------------------------

class LatencyClass(str, Enum):
    FAST = "fast"         # < 2s typical TTFT
    MEDIUM = "medium"     # 2–8s
    SLOW = "slow"         # > 8s (deep reasoning)


class AllowedRiskLevel(str, Enum):
    LOW = "low"           # safe for low-risk tasks (formatting, reads, extraction)
    MEDIUM = "medium"     # normal coding, planning, testing
    HIGH = "high"         # security, architecture, deploy decisions
    CRITICAL = "critical" # final review, billing, IAM, secrets, prod deploys


class BenchmarkStatus(str, Enum):
    NOT_BENCHMARKED = "not_benchmarked"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ModelStatus(str, Enum):
    """Lifecycle status of a model in the catalog."""
    AVAILABLE = "available"                       # known good, ready to route
    UNKNOWN_NEEDS_METADATA = "unknown_needs_metadata"  # discovered but no capability tags yet
    UNKNOWN_NEEDS_BENCHMARK = "unknown_needs_benchmark"  # discovered, tagged, not benchmarked
    UNAVAILABLE = "unavailable"                   # provider reports model gone / deprecated
    FALLBACK_ONLY = "fallback_only"               # valid but restricted to offline/fallback path
    STATIC_METADATA = "static_metadata"          # local normalized metadata, not live-discovered


# ---------------------------------------------------------------------------
# Provider entry
# ---------------------------------------------------------------------------

@dataclass
class ProviderEntry:
    provider_id: str
    display_name: str
    api_key_env: str          # env var name (no value stored)
    base_url: Optional[str]
    supports_model_list: bool  # does provider API expose /models endpoint?
    is_local: bool
    notes: str = ""
    health_status: str = "unknown"

    def to_dict(self) -> Dict:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "api_key_env": self.api_key_env,
            "api_key_configured": False,  # never reveal actual key
            "base_url": self.base_url,
            "supports_model_list": self.supports_model_list,
            "is_local": self.is_local,
            "notes": self.notes,
            "health_status": self.health_status,
        }


# ---------------------------------------------------------------------------
# Model entry
# ---------------------------------------------------------------------------

@dataclass
class ModelEntry9K:
    """Normalized model metadata for Plan 9K routing."""
    model_id: str              # canonical routing ID (e.g. "openai/gpt-4o")
    display_name: str
    provider_id: str
    context_window: int        # tokens; 0 = unknown
    input_cost_per_mtok: float  # USD per million input tokens; 0 = unknown/local
    output_cost_per_mtok: float
    latency_class: LatencyClass
    capability_tags: FrozenSet[CapabilityTag]
    allowed_risk_level: AllowedRiskLevel
    benchmark_status: BenchmarkStatus = BenchmarkStatus.NOT_BENCHMARKED
    benchmark_scores: Dict[str, float] = field(default_factory=dict)
    failure_history: List[str] = field(default_factory=list)
    is_available: bool = True
    model_status: ModelStatus = ModelStatus.STATIC_METADATA
    discovery_source: str = "static"   # "static" | "live_api" | "openrouter" | "ollama_local"
    notes: str = ""

    @property
    def is_offline_fallback(self) -> bool:
        return CapabilityTag.OFFLINE_FALLBACK in self.capability_tags

    @property
    def is_kimi(self) -> bool:
        return self.provider_id == "kimi"

    def has_capability(self, tag: CapabilityTag) -> bool:
        return tag in self.capability_tags

    def has_any_capability(self, tags: List[CapabilityTag]) -> bool:
        return any(t in self.capability_tags for t in tags)

    def to_dict(self) -> Dict:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "provider_id": self.provider_id,
            "context_window": self.context_window,
            "input_cost_per_mtok": self.input_cost_per_mtok,
            "output_cost_per_mtok": self.output_cost_per_mtok,
            "latency_class": self.latency_class.value,
            "capability_tags": sorted(t.value for t in self.capability_tags),
            "allowed_risk_level": self.allowed_risk_level.value,
            "benchmark_status": self.benchmark_status.value,
            "benchmark_scores": self.benchmark_scores,
            "is_available": self.is_available,
            "is_offline_fallback": self.is_offline_fallback,
            "is_kimi": self.is_kimi,
            "model_status": self.model_status.value,
            "discovery_source": self.discovery_source,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Static provider registry
# ---------------------------------------------------------------------------

PROVIDERS: Dict[str, ProviderEntry] = {
    "openai": ProviderEntry(
        provider_id="openai",
        display_name="OpenAI",
        api_key_env="OPENAI_API_KEY",
        base_url="https://api.openai.com/v1",
        supports_model_list=True,
        is_local=False,
    ),
    "anthropic": ProviderEntry(
        provider_id="anthropic",
        display_name="Anthropic",
        api_key_env="ANTHROPIC_API_KEY",
        base_url="https://api.anthropic.com/v1",
        supports_model_list=False,
        is_local=False,
    ),
    "kimi": ProviderEntry(
        provider_id="kimi",
        display_name="Kimi / MoonshotAI",
        api_key_env="KIMI_API_KEY",
        base_url="https://api.moonshot.cn/v1",
        supports_model_list=True,
        is_local=False,
        notes="Benchmark-gated. Not default for any role until PLAN_9K_BENCHMARK_ACCEPTED.",
    ),
    "perplexity": ProviderEntry(
        provider_id="perplexity",
        display_name="Perplexity / Sonar",
        api_key_env="PERPLEXITY_API_KEY",
        base_url="https://api.perplexity.ai",
        supports_model_list=False,
        is_local=False,
        notes="Preferred for web-grounded research, citations, source synthesis.",
    ),
    "google": ProviderEntry(
        provider_id="google",
        display_name="Google / Gemini",
        api_key_env="GOOGLE_API_KEY",
        base_url="https://generativelanguage.googleapis.com/v1beta",
        supports_model_list=True,
        is_local=False,
    ),
    "deepseek": ProviderEntry(
        provider_id="deepseek",
        display_name="DeepSeek",
        api_key_env="DEEPSEEK_API_KEY",
        base_url="https://api.deepseek.com/v1",
        supports_model_list=True,
        is_local=False,
    ),
    "mistral": ProviderEntry(
        provider_id="mistral",
        display_name="Mistral AI",
        api_key_env="MISTRAL_API_KEY",
        base_url="https://api.mistral.ai/v1",
        supports_model_list=True,
        is_local=False,
    ),
    "xai": ProviderEntry(
        provider_id="xai",
        display_name="xAI / Grok",
        api_key_env="XAI_API_KEY",
        base_url="https://api.x.ai/v1",
        supports_model_list=False,
        is_local=False,
    ),
    "openrouter": ProviderEntry(
        provider_id="openrouter",
        display_name="OpenRouter (aggregator)",
        api_key_env="OPENROUTER_API_KEY",
        base_url="https://openrouter.ai/api/v1",
        supports_model_list=True,
        is_local=False,
        notes="Aggregator: routes to DeepSeek, Mistral, Kimi, xAI, etc.",
    ),
    "aimlapi": ProviderEntry(
        provider_id="aimlapi",
        display_name="AIMLAPI (aggregator)",
        api_key_env="AIMLAPI_KEY",
        base_url="https://api.aimlapi.com/v1",
        supports_model_list=True,
        is_local=False,
        notes="Aggregator for many providers.",
    ),
    "ollama": ProviderEntry(
        provider_id="ollama",
        display_name="Ollama (local)",
        api_key_env="",
        base_url="http://localhost:11434",
        supports_model_list=True,
        is_local=True,
        notes="OFFLINE FALLBACK ONLY. Forbidden for normal chat and cloud work.",
    ),
}


# ---------------------------------------------------------------------------
# Static normalized model catalog
# ---------------------------------------------------------------------------

# Helper to build frozenset of tags
def _tags(*tags: CapabilityTag) -> FrozenSet[CapabilityTag]:
    return frozenset(tags)


CATALOG: List[ModelEntry9K] = [

    # =========================================================================
    # OpenAI
    # =========================================================================
    ModelEntry9K(
        model_id="openai/gpt-4o",
        display_name="GPT-4o",
        provider_id="openai",
        context_window=128_000,
        input_cost_per_mtok=2.50,
        output_cost_per_mtok=10.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.DEFAULT_CHAT,
            CapabilityTag.CODING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.PLANNING,
            CapabilityTag.SUMMARIZATION,
            CapabilityTag.VISION,
            CapabilityTag.MULTIMODAL,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
        notes="Primary PA front-door model. Stable, reliable, GPT route.",
    ),
    ModelEntry9K(
        model_id="openai/gpt-4o-mini",
        display_name="GPT-4o Mini",
        provider_id="openai",
        context_window=128_000,
        input_cost_per_mtok=0.15,
        output_cost_per_mtok=0.60,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.DEFAULT_CHAT,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.EXTRACTION,
            CapabilityTag.SUMMARIZATION,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
            CapabilityTag.TOOL_CALLING,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="Primary cheap route: extraction, reads, formatting, PA cheap tasks.",
    ),
    ModelEntry9K(
        model_id="openai/gpt-5-mini",
        display_name="GPT-5 Mini",
        provider_id="openai",
        context_window=400_000,
        input_cost_per_mtok=0.25,
        output_cost_per_mtok=2.00,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.DEFAULT_CHAT,
            CapabilityTag.CODING,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.LONG_CONTEXT,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
    ),
    ModelEntry9K(
        model_id="openai/o3-mini",
        display_name="o3-mini",
        provider_id="openai",
        context_window=200_000,
        input_cost_per_mtok=1.10,
        output_cost_per_mtok=4.40,
        latency_class=LatencyClass.SLOW,
        capability_tags=_tags(
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.PLANNING,
            CapabilityTag.CODING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.STRUCTURED_OUTPUT,
        ),
        allowed_risk_level=AllowedRiskLevel.HIGH,
        notes="High-reasoning route when architecture/security work requires o-series.",
    ),

    # =========================================================================
    # Anthropic
    # =========================================================================
    ModelEntry9K(
        model_id="anthropic/claude-sonnet-4-20250514",
        display_name="Claude Sonnet 4",
        provider_id="anthropic",
        context_window=200_000,
        input_cost_per_mtok=3.00,
        output_cost_per_mtok=15.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.FRONTEND_UI,
            CapabilityTag.TEST_GENERATION,
            CapabilityTag.DEBUGGING,
            CapabilityTag.SECURITY_REVIEW,
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.PLANNING,
            CapabilityTag.DOCUMENT_ANALYSIS,
            CapabilityTag.LONG_CONTEXT,
        ),
        allowed_risk_level=AllowedRiskLevel.HIGH,
        notes="Primary balanced+best coding model. Trusted for security and high-risk work.",
    ),
    ModelEntry9K(
        model_id="anthropic/claude-opus-4-20250514",
        display_name="Claude Opus 4",
        provider_id="anthropic",
        context_window=200_000,
        input_cost_per_mtok=15.00,
        output_cost_per_mtok=75.00,
        latency_class=LatencyClass.SLOW,
        capability_tags=_tags(
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.SECURITY_REVIEW,
            CapabilityTag.BILLING_IAM_REVIEW,
            CapabilityTag.SECRETS_REVIEW,
            CapabilityTag.DEPLOY_REVIEW,
            CapabilityTag.FINAL_REVIEW,
            CapabilityTag.CODING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.PLANNING,
            CapabilityTag.DOCUMENT_ANALYSIS,
            CapabilityTag.LONG_CONTEXT,
        ),
        allowed_risk_level=AllowedRiskLevel.CRITICAL,
        notes="Best model. Reserved for security, billing, IAM, deploy, final review.",
    ),
    ModelEntry9K(
        model_id="anthropic/claude-haiku-4-5",
        display_name="Claude Haiku 4.5",
        provider_id="anthropic",
        context_window=200_000,
        input_cost_per_mtok=1.00,
        output_cost_per_mtok=5.00,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.FRONTEND_UI,
            CapabilityTag.SUMMARIZATION,
            CapabilityTag.EXTRACTION,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="Fast Anthropic model. Good for UI work, reads, light summarization.",
    ),
    ModelEntry9K(
        model_id="anthropic/claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        provider_id="anthropic",
        context_window=200_000,
        input_cost_per_mtok=3.00,
        output_cost_per_mtok=15.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.FRONTEND_UI,
            CapabilityTag.SECURITY_REVIEW,
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.LONG_CONTEXT,
        ),
        allowed_risk_level=AllowedRiskLevel.HIGH,
    ),

    # =========================================================================
    # Kimi / MoonshotAI — BENCHMARK-GATED, NOT DEFAULT
    # =========================================================================
    ModelEntry9K(
        model_id="kimi/kimi-k2",
        display_name="Kimi K2 (MoonshotAI)",
        provider_id="kimi",
        context_window=131_072,
        input_cost_per_mtok=0.60,
        output_cost_per_mtok=2.50,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.REPO_SCALE_REFACTOR,
            CapabilityTag.BACKEND_API,
            CapabilityTag.FRONTEND_UI,
            CapabilityTag.LONG_CONTEXT,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.DOCUMENT_ANALYSIS,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
        benchmark_status=BenchmarkStatus.NOT_BENCHMARKED,
        notes=(
            "BENCHMARK-GATED. NOT DEFAULT for any role. "
            "May be used for coding/long_context/repo_scale/UI/docs after "
            "PLAN_9K_BENCHMARK_ACCEPTED verdict. "
            "Must not be used for final high-risk judgment. "
            "Fallback to Claude Sonnet if benchmark fails or validation fails."
        ),
    ),
    ModelEntry9K(
        model_id="kimi/kimi-k2-0711-preview",
        display_name="Kimi K2 Preview (MoonshotAI)",
        provider_id="kimi",
        context_window=131_072,
        input_cost_per_mtok=0.60,
        output_cost_per_mtok=2.50,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.REPO_SCALE_REFACTOR,
            CapabilityTag.BACKEND_API,
            CapabilityTag.LONG_CONTEXT,
            CapabilityTag.TOOL_CALLING,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
        benchmark_status=BenchmarkStatus.NOT_BENCHMARKED,
        notes="BENCHMARK-GATED. Preview variant. Not default.",
    ),
    # Kimi via OpenRouter
    ModelEntry9K(
        model_id="openrouter/moonshotai/kimi-k2",
        display_name="Kimi K2 (via OpenRouter)",
        provider_id="openrouter",
        context_window=131_072,
        input_cost_per_mtok=0.60,
        output_cost_per_mtok=2.50,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.REPO_SCALE_REFACTOR,
            CapabilityTag.BACKEND_API,
            CapabilityTag.LONG_CONTEXT,
            CapabilityTag.TOOL_CALLING,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
        benchmark_status=BenchmarkStatus.NOT_BENCHMARKED,
        notes="BENCHMARK-GATED. Kimi via OpenRouter route. Not default.",
    ),

    # =========================================================================
    # Perplexity / Sonar — preferred for web-grounded research
    # =========================================================================
    ModelEntry9K(
        model_id="perplexity/sonar-pro",
        display_name="Perplexity Sonar Pro",
        provider_id="perplexity",
        context_window=200_000,
        input_cost_per_mtok=3.00,
        output_cost_per_mtok=15.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.WEB_GROUNDED,
            CapabilityTag.CITATIONS,
            CapabilityTag.RESEARCH,
            CapabilityTag.SOURCE_SYNTHESIS,
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.DOCUMENT_ANALYSIS,
            CapabilityTag.LONG_CONTEXT,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
        notes="Best research model. Real-time web grounding + citations. Preferred for research roles.",
    ),
    ModelEntry9K(
        model_id="perplexity/sonar",
        display_name="Perplexity Sonar",
        provider_id="perplexity",
        context_window=127_072,
        input_cost_per_mtok=1.00,
        output_cost_per_mtok=1.00,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.WEB_GROUNDED,
            CapabilityTag.CITATIONS,
            CapabilityTag.RESEARCH,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.SUMMARIZATION,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="Cheap web-grounded research. Good for simple lookup tasks with current info.",
    ),

    # =========================================================================
    # Google / Gemini
    # =========================================================================
    ModelEntry9K(
        model_id="google/gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        provider_id="google",
        context_window=1_000_000,
        input_cost_per_mtok=0.30,
        output_cost_per_mtok=2.50,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.VISION,
            CapabilityTag.MULTIMODAL,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.LONG_CONTEXT,
            CapabilityTag.DOCUMENT_ANALYSIS,
            CapabilityTag.SUMMARIZATION,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="Very large context, fast, cheap. Good for document analysis and long-context reads.",
    ),
    ModelEntry9K(
        model_id="google/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        provider_id="google",
        context_window=1_000_000,
        input_cost_per_mtok=1.25,
        output_cost_per_mtok=10.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.VISION,
            CapabilityTag.MULTIMODAL,
            CapabilityTag.LONG_CONTEXT,
            CapabilityTag.DOCUMENT_ANALYSIS,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.PLANNING,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
    ),

    # =========================================================================
    # DeepSeek Cloud — cheap coding specialist
    # =========================================================================
    ModelEntry9K(
        model_id="deepseek/deepseek-chat",
        display_name="DeepSeek Chat V3",
        provider_id="deepseek",
        context_window=65_536,
        input_cost_per_mtok=0.27,
        output_cost_per_mtok=1.10,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.BACKEND_API,
            CapabilityTag.TEST_GENERATION,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
            CapabilityTag.DEBUGGING,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="Cheap coding specialist. Good for coding/test gen cheap tier.",
    ),
    ModelEntry9K(
        model_id="deepseek/deepseek-r1",
        display_name="DeepSeek R1",
        provider_id="deepseek",
        context_window=65_536,
        input_cost_per_mtok=0.55,
        output_cost_per_mtok=2.19,
        latency_class=LatencyClass.SLOW,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.HIGH_REASONING,
            CapabilityTag.PLANNING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.STRUCTURED_OUTPUT,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
        notes="DeepSeek R1 reasoning model. Good for planning and hard coding.",
    ),
    # DeepSeek via OpenRouter (common path)
    ModelEntry9K(
        model_id="openrouter/deepseek/deepseek-chat",
        display_name="DeepSeek Chat (via OpenRouter)",
        provider_id="openrouter",
        context_window=65_536,
        input_cost_per_mtok=0.27,
        output_cost_per_mtok=1.10,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.BACKEND_API,
            CapabilityTag.TEST_GENERATION,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
    ),

    # =========================================================================
    # Mistral
    # =========================================================================
    ModelEntry9K(
        model_id="mistral/mistral-large-latest",
        display_name="Mistral Large (Latest)",
        provider_id="mistral",
        context_window=131_072,
        input_cost_per_mtok=2.00,
        output_cost_per_mtok=6.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.BACKEND_API,
            CapabilityTag.STRUCTURED_OUTPUT,
            CapabilityTag.JSON_RELIABILITY,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.PLANNING,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
    ),
    ModelEntry9K(
        model_id="mistral/codestral-latest",
        display_name="Codestral (Latest)",
        provider_id="mistral",
        context_window=262_144,
        input_cost_per_mtok=0.30,
        output_cost_per_mtok=0.90,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.BACKEND_API,
            CapabilityTag.TEST_GENERATION,
            CapabilityTag.STRUCTURED_OUTPUT,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="Mistral coding specialist. Cheap and fast for coding tasks.",
    ),

    # =========================================================================
    # xAI / Grok
    # =========================================================================
    ModelEntry9K(
        model_id="xai/grok-3",
        display_name="Grok 3",
        provider_id="xai",
        context_window=131_072,
        input_cost_per_mtok=3.00,
        output_cost_per_mtok=15.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.RESEARCH,
            CapabilityTag.BACKEND_API,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.HIGH_REASONING,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
    ),
    ModelEntry9K(
        model_id="xai/grok-3-mini",
        display_name="Grok 3 Mini",
        provider_id="xai",
        context_window=131_072,
        input_cost_per_mtok=0.30,
        output_cost_per_mtok=0.50,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.CHEAP_FAST,
            CapabilityTag.RESEARCH,
            CapabilityTag.SUMMARIZATION,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
    ),
    # Grok via OpenRouter
    ModelEntry9K(
        model_id="openrouter/x-ai/grok-3",
        display_name="Grok 3 (via OpenRouter)",
        provider_id="openrouter",
        context_window=131_072,
        input_cost_per_mtok=3.00,
        output_cost_per_mtok=15.00,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.CODING,
            CapabilityTag.RESEARCH,
            CapabilityTag.TOOL_CALLING,
            CapabilityTag.HIGH_REASONING,
        ),
        allowed_risk_level=AllowedRiskLevel.MEDIUM,
    ),

    # =========================================================================
    # Ollama / local — OFFLINE FALLBACK ONLY
    # =========================================================================
    ModelEntry9K(
        model_id="ollama/qwen3:4b",
        display_name="Qwen3 4B (Local Ollama)",
        provider_id="ollama",
        context_window=262_144,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_class=LatencyClass.FAST,
        capability_tags=_tags(
            CapabilityTag.OFFLINE_FALLBACK,
            CapabilityTag.CHEAP_FAST,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="OFFLINE FALLBACK ONLY. Forbidden for normal chat. Only on provider outage/quota fail/offline.",
    ),
    ModelEntry9K(
        model_id="ollama/qwen3:14b",
        display_name="Qwen3 14B (Local Ollama)",
        provider_id="ollama",
        context_window=40_960,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.OFFLINE_FALLBACK,
            CapabilityTag.CODING,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="OFFLINE FALLBACK ONLY.",
    ),
    ModelEntry9K(
        model_id="ollama/qwen3:30b",
        display_name="Qwen3 30B (Local Ollama)",
        provider_id="ollama",
        context_window=262_144,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_class=LatencyClass.SLOW,
        capability_tags=_tags(
            CapabilityTag.OFFLINE_FALLBACK,
            CapabilityTag.CODING,
            CapabilityTag.HIGH_REASONING,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="OFFLINE FALLBACK ONLY.",
    ),
    ModelEntry9K(
        model_id="ollama/llama3.3:70b",
        display_name="Llama 3.3 70B (Local Ollama)",
        provider_id="ollama",
        context_window=131_072,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_class=LatencyClass.SLOW,
        capability_tags=_tags(
            CapabilityTag.OFFLINE_FALLBACK,
            CapabilityTag.CODING,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="OFFLINE FALLBACK ONLY.",
    ),
    ModelEntry9K(
        model_id="ollama/deepseek-coder-v2:16b",
        display_name="DeepSeek Coder V2 16B (Local Ollama)",
        provider_id="ollama",
        context_window=131_072,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        latency_class=LatencyClass.MEDIUM,
        capability_tags=_tags(
            CapabilityTag.OFFLINE_FALLBACK,
            CapabilityTag.CODING,
        ),
        allowed_risk_level=AllowedRiskLevel.LOW,
        notes="OFFLINE FALLBACK ONLY.",
    ),
]


# ---------------------------------------------------------------------------
# Provider catalog class
# ---------------------------------------------------------------------------

class ProviderCatalog9K:
    """Normalized multi-provider model catalog.

    Rules:
    - Ollama/local models are offline_fallback only.
    - Kimi is not default — benchmark-gated.
    - PA front-door only uses OpenAI GPT models.
    - Security/billing/IAM/secrets/deploy/final_review: Anthropic only, high_reasoning required.
    """

    def __init__(self, models: List[ModelEntry9K], providers: Dict[str, ProviderEntry]) -> None:
        self._models = list(models)
        self._providers = dict(providers)
        self._by_id: Dict[str, ModelEntry9K] = {m.model_id: m for m in self._models}

    @property
    def all_models(self) -> List[ModelEntry9K]:
        return list(self._models)

    @property
    def all_providers(self) -> List[ProviderEntry]:
        return list(self._providers.values())

    def provider_count(self) -> int:
        return len(self._providers)

    def model_count(self) -> int:
        return len(self._models)

    def get_model(self, model_id: str) -> Optional[ModelEntry9K]:
        return self._by_id.get(model_id)

    def models_with_capability(self, tag: CapabilityTag) -> List[ModelEntry9K]:
        return [m for m in self._models if m.has_capability(tag) and m.is_available]

    def models_for_provider(self, provider_id: str) -> List[ModelEntry9K]:
        return [m for m in self._models if m.provider_id == provider_id and m.is_available]

    def non_fallback_models(self) -> List[ModelEntry9K]:
        """Models safe for normal cloud work (excludes offline_fallback)."""
        return [m for m in self._models if not m.is_offline_fallback and m.is_available]

    def kimi_models(self) -> List[ModelEntry9K]:
        return [m for m in self._models if m.is_kimi and m.is_available]

    def kimi_benchmarked(self) -> bool:
        """True only if any Kimi model has ACCEPTED benchmark status."""
        return any(
            m.benchmark_status == BenchmarkStatus.ACCEPTED
            for m in self.kimi_models()
        )

    def update_benchmark_status(
        self,
        model_id: str,
        status: BenchmarkStatus,
        scores: Optional[Dict[str, float]] = None,
    ) -> bool:
        m = self._by_id.get(model_id)
        if m is None:
            return False
        m.benchmark_status = status
        if scores:
            m.benchmark_scores.update(scores)
        return True

    def mark_provider_health(self, provider_id: str, status: str) -> None:
        p = self._providers.get(provider_id)
        if p:
            p.health_status = status

    def capability_summary(self) -> Dict[str, List[str]]:
        """Map each capability tag → list of model_ids that have it."""
        result: Dict[str, List[str]] = {}
        for tag in CapabilityTag:
            result[tag.value] = [
                m.model_id for m in self._models
                if m.has_capability(tag) and m.is_available
            ]
        return result

    def score_candidates(
        self,
        required_caps: List[CapabilityTag],
        preferred_caps: List[CapabilityTag],
        forbidden_providers: List[str],
        risk_threshold: str = "medium",
        cost_ceiling: str = "any",
        exclude_model_ids: Optional[List[str]] = None,
        include_fallback: bool = False,
    ) -> List[str]:
        """Score ALL eligible catalog models and return sorted model_id list (best first).

        This is the core of dynamic candidate selection. Every role uses this to find
        eligible models from the FULL catalog — not just a hardcoded fallback_chain.

        Scoring factors:
          +10 per required capability matched (hard requirement, already filtered)
          +3 per preferred capability matched
          +2 fast latency bonus
          +5 benchmark ACCEPTED bonus
          -5 cost ceiling violation (cheap ceiling, expensive model)
          -3 medium ceiling violation
          -10 high-risk model assigned to low-risk role
        """
        _RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        _COST_LIMITS = {"cheap": 0.50, "medium": 5.00, "high": 20.00, "any": float("inf")}
        role_risk_idx = _RISK_ORDER.get(risk_threshold, 1)
        cost_limit = _COST_LIMITS.get(cost_ceiling, float("inf"))
        exclude = set(exclude_model_ids or [])

        scores: Dict[str, float] = {}
        for m in self._models:
            if not m.is_available:
                continue
            if m.model_id in exclude:
                continue
            if m.is_offline_fallback and not include_fallback:
                continue
            if m.provider_id in forbidden_providers:
                continue
            if "offline_fallback" in forbidden_providers and m.is_offline_fallback:
                continue

            # Hard capability filter
            if not all(m.has_capability(cap) for cap in required_caps):
                continue

            # Risk-level filter: model must be at least as permissive as role requires
            model_risk_idx = _RISK_ORDER.get(m.allowed_risk_level.value, 0)
            if model_risk_idx < role_risk_idx:
                continue

            score = float(len(required_caps) * 10)
            score += sum(3.0 for cap in preferred_caps if m.has_capability(cap))
            if m.latency_class == LatencyClass.FAST:
                score += 2.0
            if m.benchmark_status == BenchmarkStatus.ACCEPTED:
                score += 5.0
            if cost_ceiling != "any":
                if m.input_cost_per_mtok > cost_limit * 2:
                    score -= 5.0
                elif m.input_cost_per_mtok > cost_limit:
                    score -= 3.0

            scores[m.model_id] = score

        return sorted(scores.keys(), key=lambda mid: scores[mid], reverse=True)

    def add_discovered_model(self, model: "ModelEntry9K") -> None:
        """Add a dynamically discovered model to the catalog (merge/overwrite)."""
        existing = self._by_id.get(model.model_id)
        if existing is not None:
            # Preserve local metadata overrides (capability_tags stay from static if already tagged)
            if existing.capability_tags and not model.capability_tags:
                model.capability_tags = existing.capability_tags
            self._models = [m for m in self._models if m.model_id != model.model_id]
        self._models.append(model)
        self._by_id[model.model_id] = model

    def catalog_summary(self) -> Dict:
        """Return catalog counts summary for HUD/API display."""
        total = len(self._models)
        available = [m for m in self._models if m.is_available and not m.is_offline_fallback]
        fallback_only = [m for m in self._models if m.is_offline_fallback]
        unknown_needs_meta = [
            m for m in self._models
            if m.model_status == ModelStatus.UNKNOWN_NEEDS_METADATA
        ]
        unknown_needs_bench = [
            m for m in self._models
            if m.model_status == ModelStatus.UNKNOWN_NEEDS_BENCHMARK
        ]
        by_provider: Dict[str, int] = {}
        for m in self._models:
            by_provider[m.provider_id] = by_provider.get(m.provider_id, 0) + 1
        return {
            "total_models": total,
            "total_providers": self.provider_count(),
            "active_cloud_models": len(available),
            "fallback_only_models": len(fallback_only),
            "unknown_needs_metadata": len(unknown_needs_meta),
            "unknown_needs_benchmark": len(unknown_needs_bench),
            "kimi_benchmarked": self.kimi_benchmarked(),
            "by_provider": by_provider,
        }

    def to_providers_dict(self) -> Dict:
        return {
            "total": self.provider_count(),
            "providers": [p.to_dict() for p in self.all_providers],
        }

    def to_models_dict(self) -> Dict:
        return {
            "total": self.model_count(),
            "non_fallback_count": len(self.non_fallback_models()),
            "kimi_benchmarked": self.kimi_benchmarked(),
            "models": [m.to_dict() for m in self._models],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_CATALOG_INSTANCE: Optional[ProviderCatalog9K] = None


def get_provider_catalog() -> ProviderCatalog9K:
    """Return the singleton ProviderCatalog9K instance."""
    global _CATALOG_INSTANCE
    if _CATALOG_INSTANCE is None:
        _CATALOG_INSTANCE = ProviderCatalog9K(models=CATALOG, providers=PROVIDERS)
    return _CATALOG_INSTANCE


# Forbidden model classes for high-risk roles
FORBIDDEN_FOR_SECURITY = frozenset({"ollama", "offline_fallback"})
FORBIDDEN_FOR_DEPLOY = frozenset({"ollama", "offline_fallback"})
FORBIDDEN_FOR_IAM = frozenset({"ollama", "offline_fallback", "cheap_fast_only"})

# PA front-door model IDs (stable, GPT/OpenAI-style)
PA_STABLE_MODELS = [
    "openai/gpt-4o",        # primary PA balanced
    "openai/gpt-4o-mini",   # PA cheap tier
    "openai/gpt-5-mini",    # PA balanced alternative
]

__all__ = [
    "CapabilityTag",
    "LatencyClass",
    "AllowedRiskLevel",
    "BenchmarkStatus",
    "ModelStatus",
    "ProviderEntry",
    "ModelEntry9K",
    "ProviderCatalog9K",
    "CATALOG",
    "PROVIDERS",
    "PA_STABLE_MODELS",
    "FORBIDDEN_FOR_SECURITY",
    "FORBIDDEN_FOR_DEPLOY",
    "FORBIDDEN_FOR_IAM",
    "get_provider_catalog",
]
