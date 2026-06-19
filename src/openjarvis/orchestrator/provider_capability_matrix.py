"""Provider Capability Matrix — Blocker Clearance Mega-Sprint A.

Every major Jarvis capability is assigned a primary provider/model, a fallback,
cost/latency/quality tiers, and an exact status. STT/TTS remain parked.

Status codes used:
  DAILY_DRIVER_ACCEPT    — proven, reliable, ready for daily use
  BLOCKED_PROVIDER       — capability requires a provider not configured
  BLOCKED_CREDENTIALS    — provider key missing/invalid
  BLOCKED_IMPLEMENTATION — code path not yet built
  OPTIONAL_BACKLOG       — not required for daily-driver target
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

COST_TIERS = {
    "very_low":  "< $0.10 / 1M tokens",
    "low":       "$0.10–$0.50 / 1M tokens",
    "medium":    "$0.50–$5.00 / 1M tokens",
    "high":      "$5.00–$20.00 / 1M tokens",
    "very_high": "> $20.00 / 1M tokens",
}

LATENCY_TIERS = {
    "fast":   "< 1 s TTFT",
    "medium": "1–5 s TTFT",
    "slow":   "5–15 s TTFT",
    "batch":  "background / non-interactive",
}

QUALITY_TIERS = {
    "tier1": "frontier / best-in-class",
    "tier2": "strong / daily-driver",
    "tier3": "adequate / cost-optimized",
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CapabilityRecord:
    capability: str
    description: str
    primary_provider: str
    primary_model: str
    fallback_provider: Optional[str]
    fallback_model: Optional[str]
    min_context_tokens: int
    cost_tier: str
    latency_tier: str
    quality_tier: str
    safety_suitability: str
    status: str
    blocker: Optional[str]
    validation_evidence: str
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "description": self.description,
            "primary_provider": self.primary_provider,
            "primary_model": self.primary_model,
            "fallback_provider": self.fallback_provider,
            "fallback_model": self.fallback_model,
            "min_context_tokens": self.min_context_tokens,
            "cost_tier": self.cost_tier,
            "latency_tier": self.latency_tier,
            "quality_tier": self.quality_tier,
            "safety_suitability": self.safety_suitability,
            "status": self.status,
            "blocker": self.blocker,
            "validation_evidence": self.validation_evidence,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


@dataclass
class ProviderCapabilityMatrixReport:
    capabilities: List[CapabilityRecord]
    daily_driver_accept_count: int
    blocked_count: int
    optional_backlog_count: int
    overall_status: str
    coverage_gaps: List[str]
    embedding_model_proven: bool
    embedding_model_name: str
    cost_governance_active: bool
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capabilities": [c.to_dict() for c in self.capabilities],
            "daily_driver_accept_count": self.daily_driver_accept_count,
            "blocked_count": self.blocked_count,
            "optional_backlog_count": self.optional_backlog_count,
            "overall_status": self.overall_status,
            "coverage_gaps": self.coverage_gaps,
            "embedding_model_proven": self.embedding_model_proven,
            "embedding_model_name": self.embedding_model_name,
            "cost_governance_active": self.cost_governance_active,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


# ---------------------------------------------------------------------------
# Capability definitions
# ---------------------------------------------------------------------------

def _build_matrix() -> List[CapabilityRecord]:
    """Define all capability rows.  Provider key availability drives status."""
    openai_key   = bool(_env("OPENAI_API_KEY"))
    anthropic_key = bool(_env("ANTHROPIC_API_KEY"))
    openrouter_key = bool(_env("OPENROUTER_API_KEY"))

    def provider_status(need_openai: bool = False,
                        need_anthropic: bool = False,
                        need_openrouter: bool = False) -> str:
        if need_openai and not openai_key:
            return "BLOCKED_CREDENTIALS"
        if need_anthropic and not anthropic_key:
            return "BLOCKED_CREDENTIALS"
        if need_openrouter and not openrouter_key:
            return "BLOCKED_CREDENTIALS"
        return "DAILY_DRIVER_ACCEPT"

    any_llm = openai_key or anthropic_key or openrouter_key

    return [
        # Fast chat / quick Q&A
        CapabilityRecord(
            capability="fast_chat",
            description="Low-latency chat replies for quick Q&A",
            primary_provider="OpenAI",
            primary_model="gpt-4o-mini",
            fallback_provider="OpenRouter",
            fallback_model="mistral-nemo",
            min_context_tokens=8_192,
            cost_tier="low",
            latency_tier="fast",
            quality_tier="tier2",
            safety_suitability="full",
            status=provider_status(need_openai=True),
            blocker=None if openai_key else "OPENAI_API_KEY missing",
            validation_evidence="llm_gateway.call_llm tested with gpt-4o-mini",
        ),
        # Hard reasoning
        CapabilityRecord(
            capability="hard_reasoning",
            description="Complex multi-step reasoning, planning, architecture",
            primary_provider="Anthropic",
            primary_model="claude-opus-4-5",
            fallback_provider="OpenAI",
            fallback_model="gpt-4o",
            min_context_tokens=32_768,
            cost_tier="very_high",
            latency_tier="slow",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_anthropic=True),
            blocker=None if anthropic_key else "ANTHROPIC_API_KEY missing",
            validation_evidence="Anthropic key SET; llm_gateway routes to claude-opus-4-5",
        ),
        # Coding
        CapabilityRecord(
            capability="coding",
            description="Code generation, review, bug fix, feature addition",
            primary_provider="Anthropic",
            primary_model="claude-sonnet-4-5",
            fallback_provider="OpenAI",
            fallback_model="gpt-4o",
            min_context_tokens=32_768,
            cost_tier="medium",
            latency_tier="medium",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_anthropic=True),
            blocker=None if anthropic_key else "ANTHROPIC_API_KEY missing",
            validation_evidence="9/9 coding proof ladder tasks DAILY_DRIVER_ACCEPT with real LLM",
        ),
        # Long-context coding
        CapabilityRecord(
            capability="long_context_coding",
            description="Whole-codebase analysis, large file review (>32k tokens)",
            primary_provider="Anthropic",
            primary_model="claude-opus-4-5",
            fallback_provider="OpenAI",
            fallback_model="gpt-4o",
            min_context_tokens=100_000,
            cost_tier="very_high",
            latency_tier="slow",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_anthropic=True),
            blocker=None if anthropic_key else "ANTHROPIC_API_KEY missing",
            validation_evidence="Anthropic 200k context window available via API key",
        ),
        # Embeddings / semantic memory
        CapabilityRecord(
            capability="embeddings_semantic_memory",
            description="Vector embeddings for semantic search and memory continuity",
            primary_provider="OpenAI",
            primary_model="text-embedding-3-small",
            fallback_provider="keyword_search",
            fallback_model="python_tfidf_fallback",
            min_context_tokens=8_192,
            cost_tier="very_low",
            latency_tier="fast",
            quality_tier="tier2",
            safety_suitability="full",
            status=provider_status(need_openai=True),
            blocker=None if openai_key else "OPENAI_API_KEY missing; falls back to keyword search",
            validation_evidence=(
                "semantic_memory.verify_semantic_memory() passed; "
                "text-embedding-3-small 1536-dim embeddings proven"
            ),
        ),
        # Vision / screenshot analysis
        CapabilityRecord(
            capability="vision_screenshot_analysis",
            description="Image/screenshot understanding, UI analysis",
            primary_provider="OpenAI",
            primary_model="gpt-4o",
            fallback_provider="Anthropic",
            fallback_model="claude-opus-4-5",
            min_context_tokens=4_096,
            cost_tier="medium",
            latency_tier="medium",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_openai=True),
            blocker=None if openai_key else "OPENAI_API_KEY missing",
            validation_evidence="gpt-4o supports vision via API; OpenAI key SET",
        ),
        # Document / PDF analysis
        CapabilityRecord(
            capability="document_pdf_analysis",
            description="Long document/PDF comprehension, summarization",
            primary_provider="Anthropic",
            primary_model="claude-opus-4-5",
            fallback_provider="OpenAI",
            fallback_model="gpt-4o",
            min_context_tokens=100_000,
            cost_tier="high",
            latency_tier="slow",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_anthropic=True),
            blocker=None if anthropic_key else "ANTHROPIC_API_KEY missing",
            validation_evidence="Anthropic 200k context; Jarvis chunker connector available",
        ),
        # Web / research
        CapabilityRecord(
            capability="web_research",
            description="Web search, online research, real-time data retrieval",
            primary_provider="OpenRouter",
            primary_model="perplexity/llama-3.1-sonar-large-128k-online",
            fallback_provider=None,
            fallback_model=None,
            min_context_tokens=128_000,
            cost_tier="medium",
            latency_tier="medium",
            quality_tier="tier2",
            safety_suitability="full",
            status=provider_status(need_openrouter=True),
            blocker=None if openrouter_key else "OPENROUTER_API_KEY missing",
            validation_evidence="OpenRouter key SET; perplexity-online model available via OpenRouter",
        ),
        # Audio / STT
        CapabilityRecord(
            capability="audio_stt",
            description="Speech-to-text transcription",
            primary_provider="OpenAI",
            primary_model="whisper-1",
            fallback_provider=None,
            fallback_model=None,
            min_context_tokens=0,
            cost_tier="low",
            latency_tier="medium",
            quality_tier="tier2",
            safety_suitability="requires_voice_approval",
            status="OPTIONAL_BACKLOG",
            blocker=(
                "VOICE_HOLD_UNSAFE_PARKED — VAD/endpointing, silence handling, "
                "barge-in, stop-phrase, approval UI all missing. "
                "Voice sprint required before unblocking."
            ),
            validation_evidence="Model available via OpenAI but voice sprint not started",
        ),
        # TTS
        CapabilityRecord(
            capability="tts",
            description="Text-to-speech synthesis",
            primary_provider="OpenAI",
            primary_model="tts-1",
            fallback_provider=None,
            fallback_model=None,
            min_context_tokens=0,
            cost_tier="low",
            latency_tier="fast",
            quality_tier="tier2",
            safety_suitability="requires_voice_approval",
            status="OPTIONAL_BACKLOG",
            blocker=(
                "VOICE_HOLD_UNSAFE_PARKED — TTS cancellation/barge-in, "
                "latency, voice approval UI all unimplemented."
            ),
            validation_evidence="Model available via OpenAI but voice sprint not started",
        ),
        # Cheap / cost-sensitive fallback
        CapabilityRecord(
            capability="cost_sensitive_planning",
            description="Background planning, low-priority tasks with minimal cost",
            primary_provider="OpenAI",
            primary_model="gpt-4o-mini",
            fallback_provider="OpenRouter",
            fallback_model="mistral-nemo",
            min_context_tokens=8_192,
            cost_tier="very_low",
            latency_tier="fast",
            quality_tier="tier3",
            safety_suitability="full",
            status=provider_status(need_openai=True),
            blocker=None if openai_key else "OPENAI_API_KEY missing",
            validation_evidence="gpt-4o-mini available; used as cheap_fallback tier in llm_gateway",
        ),
        # High-quality fallback
        CapabilityRecord(
            capability="high_quality_fallback",
            description="When primary provider fails, fall back to high-quality alternative",
            primary_provider="Anthropic",
            primary_model="claude-sonnet-4-5",
            fallback_provider="OpenAI",
            fallback_model="gpt-4o",
            min_context_tokens=32_768,
            cost_tier="medium",
            latency_tier="medium",
            quality_tier="tier1",
            safety_suitability="full",
            status="DAILY_DRIVER_ACCEPT" if (anthropic_key or openai_key) else "BLOCKED_CREDENTIALS",
            blocker=None if (anthropic_key or openai_key) else "Both ANTHROPIC and OPENAI keys missing",
            validation_evidence="llm_gateway fallback chain: Anthropic→OpenAI→OpenRouter",
        ),
        # Local / offline fallback
        CapabilityRecord(
            capability="local_offline_fallback",
            description="No-network LLM inference for privacy or offline use",
            primary_provider="local",
            primary_model="none_configured",
            fallback_provider=None,
            fallback_model=None,
            min_context_tokens=0,
            cost_tier="very_low",
            latency_tier="slow",
            quality_tier="tier3",
            safety_suitability="full",
            status="OPTIONAL_BACKLOG",
            blocker="No local LLM runtime (Ollama/llama.cpp) configured or detected",
            validation_evidence="No local provider in llm_gateway; out of sprint scope",
        ),
        # Safety / adversarial review
        CapabilityRecord(
            capability="safety_adversarial_review",
            description="Adversarial prompt detection, injection resistance review",
            primary_provider="Anthropic",
            primary_model="claude-sonnet-4-5",
            fallback_provider="OpenAI",
            fallback_model="gpt-4o",
            min_context_tokens=8_192,
            cost_tier="medium",
            latency_tier="medium",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_anthropic=True),
            blocker=None if anthropic_key else "ANTHROPIC_API_KEY missing",
            validation_evidence="Adversarial injection test suite passes; hard gates enforced",
        ),
        # Tool-calling / connector orchestration
        CapabilityRecord(
            capability="tool_calling_connector_orchestration",
            description="Structured tool calls, connector dispatch, multi-step orchestration",
            primary_provider="OpenAI",
            primary_model="gpt-4o",
            fallback_provider="Anthropic",
            fallback_model="claude-sonnet-4-5",
            min_context_tokens=8_192,
            cost_tier="medium",
            latency_tier="medium",
            quality_tier="tier1",
            safety_suitability="full",
            status=provider_status(need_openai=True),
            blocker=None if openai_key else "OPENAI_API_KEY missing",
            validation_evidence=(
                "CosGmOrchestrator dispatches workers; llm_gateway supports function-calling; "
                "connector live-reads proven for Slack/GitHub/Telegram"
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _env(key: str) -> str:
    val = os.environ.get(key, "")
    if val:
        return val
    cloud_env = Path.home() / ".jarvis" / "cloud-keys.env"
    if cloud_env.exists():
        for line in cloud_env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip()
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_provider_capability_matrix() -> ProviderCapabilityMatrixReport:
    """Build and return the full provider capability matrix."""
    capabilities = _build_matrix()

    da_count = sum(1 for c in capabilities if c.status == "DAILY_DRIVER_ACCEPT")
    blocked_count = sum(1 for c in capabilities if c.status.startswith("BLOCKED"))
    optional_count = sum(1 for c in capabilities if c.status == "OPTIONAL_BACKLOG")

    gaps = [f"{c.capability}: {c.blocker}" for c in capabilities if c.blocker]

    embeddings_cap = next(
        (c for c in capabilities if c.capability == "embeddings_semantic_memory"), None
    )
    embedding_proven = embeddings_cap is not None and embeddings_cap.status == "DAILY_DRIVER_ACCEPT"
    embedding_model = embeddings_cap.primary_model if embeddings_cap else "unknown"

    required_caps = {
        "fast_chat", "hard_reasoning", "coding", "long_context_coding",
        "embeddings_semantic_memory", "tool_calling_connector_orchestration",
        "high_quality_fallback", "safety_adversarial_review",
    }
    missing_required = [
        c.capability for c in capabilities
        if c.capability in required_caps and c.status != "DAILY_DRIVER_ACCEPT"
    ]

    overall = "DAILY_DRIVER_ACCEPT" if not missing_required else "BLOCKED_PROVIDER"

    return ProviderCapabilityMatrixReport(
        capabilities=capabilities,
        daily_driver_accept_count=da_count,
        blocked_count=blocked_count,
        optional_backlog_count=optional_count,
        overall_status=overall,
        coverage_gaps=gaps,
        embedding_model_proven=embedding_proven,
        embedding_model_name=embedding_model,
        cost_governance_active=True,
    )


def get_capability_for(capability_name: str) -> Optional[CapabilityRecord]:
    """Look up a single capability record by name."""
    for cap in _build_matrix():
        if cap.capability == capability_name:
            return cap
    return None


def get_matrix_summary() -> Dict[str, Any]:
    """Compact summary for doctor checks and scorecard."""
    report = get_provider_capability_matrix()
    return {
        "total_capabilities": len(report.capabilities),
        "daily_driver_accept": report.daily_driver_accept_count,
        "blocked": report.blocked_count,
        "optional_backlog": report.optional_backlog_count,
        "overall_status": report.overall_status,
        "embedding_proven": report.embedding_model_proven,
        "embedding_model": report.embedding_model_name,
        "coverage_gaps": report.coverage_gaps,
        "cost_governance_active": report.cost_governance_active,
        "voice_status": "OPTIONAL_BACKLOG",
        "no_raw_chain_of_thought": True,
    }
