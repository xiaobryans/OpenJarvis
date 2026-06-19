"""Prompt/Context Cache Optimization — cost/latency layer for Jarvis LLM calls.

IMPORTANT DISTINCTION:
  - Prompt/context cache is NOT long-term memory.
  - It does NOT replace cloud memory or Obsidian.
  - It is a cost/latency optimization for repeated stable context prefixes.

Architecture:
  Context blocks are split into stability tiers:

  STABLE (place first — cache prefix benefits):
    1. jarvis_constitution      — governance/safety rules (rarely changes)
    2. safety_rules             — safety constitution (rarely changes)
    3. tool_schemas             — tool definitions (changes on tool updates)
    4. provider_matrix          — model/provider config (changes on model updates)

  SEMI-STABLE (middle — may benefit from caching):
    5. repo_map                 — project structure (changes on file updates)
    6. project_context          — accepted state, decisions (changes on sprint)
    7. current_sprint_state     — sprint progress (changes per sprint)

  DYNAMIC (last — never cache):
    8. dynamic_user_request     — current user request (always unique)
    9. live_tool_results        — live tool outputs (always unique)

Hash Registry:
  Each stable/semi-stable block has a content hash. Hashes are compared to detect
  invalidation. Only invalidated blocks are rebuilt.

Provider-specific behavior:
  - OpenAI: cached_tokens in usage response signals cache hit
  - Anthropic: cache_control support (planned; only if safely implemented)
  - OpenRouter: provider-dependent; do not assume caching
  - Gemini/local: no caching assumed

Never cache/send:
  - secrets, tokens, private key material
  - raw chain-of-thought
  - unredacted credentials
  - sensitive connector payloads
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Context block stability tiers
# ---------------------------------------------------------------------------

class ContextStability(str, Enum):
    STABLE = "stable"           # Place first; cache prefix benefits
    SEMI_STABLE = "semi_stable" # Middle; may benefit from caching
    DYNAMIC = "dynamic"         # Last; never cache


@dataclass
class ContextBlock:
    """A single named context block for assembly."""
    name: str
    content: str
    stability: ContextStability
    source: str = ""
    content_hash: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        if not self.content_hash:
            self.content_hash = _hash_content(self.content)


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Hash Registry — tracks stable block hashes for invalidation
# ---------------------------------------------------------------------------

@dataclass
class ContextHashRegistry:
    """Registry of content hashes for stable/semi-stable context blocks.

    Tracks which blocks have changed since last assembly.
    """
    constitution_hash: str = ""
    safety_rules_hash: str = ""
    repo_map_hash: str = ""
    tool_schema_hash: str = ""
    provider_matrix_hash: str = ""
    project_context_hash: str = ""
    roadmap_hash: str = ""
    last_updated: float = field(default_factory=time.time)

    def update(self, block_name: str, content_hash: str) -> bool:
        """Update hash for a block. Returns True if hash changed (invalidated)."""
        attr = f"{block_name}_hash"
        if hasattr(self, attr):
            old = getattr(self, attr)
            changed = old != content_hash
            setattr(self, attr, content_hash)
            if changed:
                self.last_updated = time.time()
            return changed
        return False

    def get(self, block_name: str) -> str:
        attr = f"{block_name}_hash"
        return getattr(self, attr, "")

    def invalidate(self, block_name: str) -> None:
        """Explicitly invalidate a block (set hash to empty)."""
        attr = f"{block_name}_hash"
        if hasattr(self, attr):
            setattr(self, attr, "")
            self.last_updated = time.time()

    def to_dict(self) -> Dict[str, str]:
        return {
            k: v for k, v in self.__dict__.items()
            if k.endswith("_hash")
        }


# ---------------------------------------------------------------------------
# Invalidation rules
# ---------------------------------------------------------------------------

INVALIDATION_RULES: Dict[str, str] = {
    "repo_map": "Invalidate when project files change",
    "tool_schema": "Invalidate when tool definitions change",
    "provider_matrix": "Invalidate when model/provider configuration changes",
    "project_context": "Invalidate when accepted state or decisions change",
    "roadmap": "Invalidate when sprint/roadmap state changes",
    "constitution": "Invalidate when governance constitution changes (rare)",
    "safety_rules": "Invalidate when safety rules change (rare)",
}


# ---------------------------------------------------------------------------
# Cache telemetry
# ---------------------------------------------------------------------------

@dataclass
class CacheTelemetry:
    """Telemetry from a single LLM call with cache metrics."""
    provider: str
    model: str
    prompt_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    cache_hit_ratio: float = 0.0
    estimated_cost_saved_usd: float = 0.0
    latency_ms: float = 0.0
    cache_supported: bool = False
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_tokens": self.prompt_tokens,
            "cached_tokens": self.cached_tokens,
            "output_tokens": self.output_tokens,
            "cache_hit_ratio": round(self.cache_hit_ratio, 4),
            "estimated_cost_saved_usd": round(self.estimated_cost_saved_usd, 6),
            "latency_ms": round(self.latency_ms, 1),
            "cache_supported": self.cache_supported,
            "notes": self.notes,
        }


def parse_cache_telemetry(
    provider: str,
    model: str,
    usage: Optional[Dict[str, Any]],
    latency_ms: float = 0.0,
) -> CacheTelemetry:
    """Parse provider usage response into cache telemetry.

    Never raises. Returns degraded telemetry if provider does not expose cache metrics.
    """
    if usage is None:
        return CacheTelemetry(
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            notes="No usage data returned by provider",
        )

    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0

    # OpenAI: cached_tokens in prompt_tokens_details
    cached_tokens = 0
    cache_supported = False

    if provider in ("openai", "openrouter"):
        details = usage.get("prompt_tokens_details") or {}
        cached_tokens = details.get("cached_tokens", 0) or 0
        cache_supported = "prompt_tokens_details" in usage
    elif provider == "anthropic":
        # Anthropic: cache_read_input_tokens in usage when cache_control used
        cached_tokens = usage.get("cache_read_input_tokens", 0) or 0
        cache_supported = "cache_read_input_tokens" in usage

    ratio = (cached_tokens / prompt_tokens) if prompt_tokens > 0 else 0.0

    # Estimate cost savings: cached tokens typically cost ~10% of prompt tokens
    # Using rough OpenAI pricing as estimate; actual savings vary by provider
    est_saved = cached_tokens * 0.0000015 * 0.9  # ~90% discount for cached

    notes = ""
    if provider == "openrouter":
        notes = "OpenRouter: cache metrics are provider-dependent; not guaranteed"
    elif not cache_supported:
        notes = f"Provider {provider!r} did not return cache metrics in this response"

    return CacheTelemetry(
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        cached_tokens=cached_tokens,
        output_tokens=output_tokens,
        cache_hit_ratio=ratio,
        estimated_cost_saved_usd=est_saved,
        latency_ms=latency_ms,
        cache_supported=cache_supported,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Context assembler
# ---------------------------------------------------------------------------

# Stability ordering — stable blocks MUST come first
_STABILITY_ORDER = {
    ContextStability.STABLE: 0,
    ContextStability.SEMI_STABLE: 1,
    ContextStability.DYNAMIC: 2,
}

# Built-in stable block names
STABLE_BLOCK_NAMES = [
    "jarvis_constitution",
    "safety_rules",
    "tool_schemas",
    "provider_matrix",
]

SEMI_STABLE_BLOCK_NAMES = [
    "repo_map",
    "project_context",
    "current_sprint_state",
]

DYNAMIC_BLOCK_NAMES = [
    "dynamic_user_request",
    "live_tool_results",
]

# Secrets must never be cached
_SECRET_PREFIXES = ("xoxb-", "xoxp-", "sk-", "ghp_", "gho_", "AKIA", "eyJ")


def _contains_secret(content: str) -> bool:
    """Heuristic check — refuse to assemble if content looks like a secret."""
    for prefix in _SECRET_PREFIXES:
        if prefix in content and len(content) > 15:
            return True
    return False


class CacheAwareContextAssembler:
    """Assembles context blocks in stability order for prompt caching.

    Stable blocks are placed first to maximize prefix cache hits.
    Dynamic blocks are placed last and never cached.

    Usage:
        assembler = CacheAwareContextAssembler()
        assembler.add_block("jarvis_constitution", constitution_text, ContextStability.STABLE)
        assembler.add_block("dynamic_user_request", user_msg, ContextStability.DYNAMIC)
        assembled = assembler.assemble()
    """

    def __init__(self, registry: Optional[ContextHashRegistry] = None) -> None:
        self._blocks: List[ContextBlock] = []
        self._registry = registry or ContextHashRegistry()

    def add_block(
        self,
        name: str,
        content: str,
        stability: ContextStability,
        source: str = "",
    ) -> None:
        """Add a context block. Raises ValueError if content contains secrets."""
        if _contains_secret(content):
            raise ValueError(
                f"Context block {name!r} refused: content appears to contain "
                "a secret/token. Redact before adding to context."
            )
        block = ContextBlock(name=name, content=content, stability=stability, source=source)
        self._blocks.append(block)

        # Update registry hash for stable/semi-stable blocks
        if stability in (ContextStability.STABLE, ContextStability.SEMI_STABLE):
            # Strip trailing _hash suffix from block name if needed
            reg_key = name.replace("-", "_")
            self._registry.update(reg_key, block.content_hash)

    def assemble(self) -> str:
        """Assemble blocks in stability order.

        Order: STABLE → SEMI_STABLE → DYNAMIC
        Within each tier, preserve insertion order.
        """
        sorted_blocks = sorted(
            self._blocks,
            key=lambda b: _STABILITY_ORDER[b.stability],
        )
        return "\n\n".join(b.content for b in sorted_blocks if b.content.strip())

    def assemble_with_metadata(self) -> Dict[str, Any]:
        """Return assembled context plus metadata for debugging/telemetry."""
        sorted_blocks = sorted(
            self._blocks,
            key=lambda b: _STABILITY_ORDER[b.stability],
        )
        return {
            "assembled": "\n\n".join(b.content for b in sorted_blocks if b.content.strip()),
            "block_order": [
                {"name": b.name, "stability": b.stability.value, "hash": b.content_hash}
                for b in sorted_blocks
            ],
            "registry": self._registry.to_dict(),
            "total_blocks": len(sorted_blocks),
            "stable_count": sum(1 for b in sorted_blocks if b.stability == ContextStability.STABLE),
            "semi_stable_count": sum(1 for b in sorted_blocks if b.stability == ContextStability.SEMI_STABLE),
            "dynamic_count": sum(1 for b in sorted_blocks if b.stability == ContextStability.DYNAMIC),
        }

    def get_registry(self) -> ContextHashRegistry:
        return self._registry

    def invalidate(self, block_name: str) -> None:
        """Explicitly invalidate a block in the registry."""
        self._registry.invalidate(block_name)
        # Remove block from assembled list so it must be re-added
        self._blocks = [b for b in self._blocks if b.name != block_name]


# ---------------------------------------------------------------------------
# Provider-specific cache support matrix
# ---------------------------------------------------------------------------

PROVIDER_CACHE_SUPPORT: Dict[str, Dict[str, Any]] = {
    "openai": {
        "supported": True,
        "mechanism": "automatic_prefix_cache",
        "telemetry_field": "prompt_tokens_details.cached_tokens",
        "notes": "Automatic caching of repeated prefixes ≥1024 tokens",
        "status": "DAILY_DRIVER_ACCEPT",
    },
    "anthropic": {
        "supported": True,
        "mechanism": "explicit_cache_control",
        "telemetry_field": "usage.cache_read_input_tokens",
        "notes": "Requires explicit cache_control in message content. Planned safe implementation.",
        "status": "PLANNED_IN_EXISTING_PROMPT",
    },
    "openrouter": {
        "supported": False,
        "mechanism": "provider_dependent",
        "telemetry_field": "prompt_tokens_details.cached_tokens",
        "notes": "OpenRouter forwards to underlying provider; cache support varies. Do not assume.",
        "status": "PLANNED_IN_EXISTING_PROMPT",
    },
    "gemini": {
        "supported": False,
        "mechanism": "unknown",
        "telemetry_field": None,
        "notes": "Gemini context caching may exist but is not verified. Classify as not supported.",
        "status": "PLANNED_IN_EXISTING_PROMPT",
    },
    "local": {
        "supported": False,
        "mechanism": "none",
        "telemetry_field": None,
        "notes": "Local models do not support prompt caching.",
        "status": "OPTIONAL_BACKLOG",
    },
}


def get_provider_cache_status(provider: str) -> Dict[str, Any]:
    """Return cache support info for a provider without assuming capability."""
    return PROVIDER_CACHE_SUPPORT.get(
        provider.lower(),
        {
            "supported": False,
            "mechanism": "unknown",
            "telemetry_field": None,
            "notes": f"Provider {provider!r} not in cache support matrix. Assume unsupported.",
            "status": "PLANNED_IN_EXISTING_PROMPT",
        },
    )


__all__ = [
    "ContextStability",
    "ContextBlock",
    "ContextHashRegistry",
    "CacheTelemetry",
    "CacheAwareContextAssembler",
    "parse_cache_telemetry",
    "get_provider_cache_status",
    "PROVIDER_CACHE_SUPPORT",
    "INVALIDATION_RULES",
]
