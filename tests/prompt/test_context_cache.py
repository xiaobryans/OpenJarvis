"""Tests for prompt/context cache optimization layer."""

from __future__ import annotations

import pytest

from openjarvis.prompt.context_cache import (
    CacheAwareContextAssembler,
    CacheTelemetry,
    ContextBlock,
    ContextHashRegistry,
    ContextStability,
    INVALIDATION_RULES,
    PROVIDER_CACHE_SUPPORT,
    get_provider_cache_status,
    parse_cache_telemetry,
)


class TestContextStabilityOrdering:
    def test_stable_blocks_before_dynamic(self):
        assembler = CacheAwareContextAssembler()
        assembler.add_block("dynamic_user_request", "user query", ContextStability.DYNAMIC)
        assembler.add_block("jarvis_constitution", "constitution text", ContextStability.STABLE)

        meta = assembler.assemble_with_metadata()
        order = [b["name"] for b in meta["block_order"]]
        assert order.index("jarvis_constitution") < order.index("dynamic_user_request")

    def test_stable_semi_stable_dynamic_order(self):
        assembler = CacheAwareContextAssembler()
        assembler.add_block("dynamic_user_request", "query", ContextStability.DYNAMIC)
        assembler.add_block("repo_map", "map content", ContextStability.SEMI_STABLE)
        assembler.add_block("safety_rules", "rules", ContextStability.STABLE)

        meta = assembler.assemble_with_metadata()
        order = [b["name"] for b in meta["block_order"]]
        assert order.index("safety_rules") < order.index("repo_map")
        assert order.index("repo_map") < order.index("dynamic_user_request")

    def test_counts_by_stability(self):
        assembler = CacheAwareContextAssembler()
        assembler.add_block("a", "text", ContextStability.STABLE)
        assembler.add_block("b", "text", ContextStability.STABLE)
        assembler.add_block("c", "text", ContextStability.SEMI_STABLE)
        assembler.add_block("d", "text", ContextStability.DYNAMIC)
        meta = assembler.assemble_with_metadata()
        assert meta["stable_count"] == 2
        assert meta["semi_stable_count"] == 1
        assert meta["dynamic_count"] == 1


class TestHashRegistry:
    def test_update_detects_change(self):
        registry = ContextHashRegistry()
        changed = registry.update("constitution", "abc")
        assert changed is True   # was empty before

    def test_update_no_change_when_same_hash(self):
        registry = ContextHashRegistry()
        registry.update("constitution", "abc")
        changed = registry.update("constitution", "abc")
        assert changed is False

    def test_update_detects_hash_change(self):
        registry = ContextHashRegistry()
        registry.update("constitution", "hash1")
        changed = registry.update("constitution", "hash2")
        assert changed is True

    def test_invalidate_clears_hash(self):
        registry = ContextHashRegistry()
        registry.update("constitution", "abc")
        registry.invalidate("constitution")
        assert registry.get("constitution") == ""

    def test_to_dict_contains_all_hashes(self):
        registry = ContextHashRegistry()
        d = registry.to_dict()
        assert "constitution_hash" in d
        assert "repo_map_hash" in d
        assert "tool_schema_hash" in d
        assert "provider_matrix_hash" in d
        assert "project_context_hash" in d


class TestHashCalculation:
    def test_content_hash_stable(self):
        assembler = CacheAwareContextAssembler()
        assembler.add_block("constitution", "same text", ContextStability.STABLE)
        assembler2 = CacheAwareContextAssembler()
        assembler2.add_block("constitution", "same text", ContextStability.STABLE)
        b1 = [b for b in assembler.assemble_with_metadata()["block_order"] if b["name"] == "constitution"][0]
        b2 = [b for b in assembler2.assemble_with_metadata()["block_order"] if b["name"] == "constitution"][0]
        assert b1["hash"] == b2["hash"]

    def test_different_content_different_hash(self):
        b1 = ContextBlock("x", "content A", ContextStability.STABLE)
        b2 = ContextBlock("x", "content B", ContextStability.STABLE)
        assert b1.content_hash != b2.content_hash


class TestSecretRedactionInContext:
    def test_secret_in_block_raises(self):
        assembler = CacheAwareContextAssembler()
        with pytest.raises(ValueError, match="secret"):
            assembler.add_block("bad", "xoxb-12345-67890-abcdefghijk", ContextStability.STABLE)

    def test_safe_content_accepted(self):
        assembler = CacheAwareContextAssembler()
        assembler.add_block("safe", "This is safe context", ContextStability.STABLE)
        result = assembler.assemble()
        assert "safe context" in result


class TestCacheTelemetry:
    def test_openai_cached_tokens_parsed(self):
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "prompt_tokens_details": {"cached_tokens": 800},
        }
        t = parse_cache_telemetry("openai", "gpt-4o", usage, latency_ms=250.0)
        assert t.cached_tokens == 800
        assert t.prompt_tokens == 1000
        assert t.cache_hit_ratio == pytest.approx(0.8)
        assert t.cache_supported is True
        assert t.latency_ms == 250.0

    def test_anthropic_cached_tokens_parsed(self):
        usage = {
            "input_tokens": 500,
            "cache_read_input_tokens": 400,
            "output_tokens": 50,
        }
        t = parse_cache_telemetry("anthropic", "claude-3-opus", usage)
        assert t.cached_tokens == 400
        assert t.cache_supported is True

    def test_openrouter_notes_provider_dependent(self):
        usage = {"prompt_tokens": 500, "completion_tokens": 50}
        t = parse_cache_telemetry("openrouter", "gpt-4o", usage)
        assert "provider-dependent" in t.notes.lower() or "not guaranteed" in t.notes.lower()

    def test_no_usage_graceful_fallback(self):
        t = parse_cache_telemetry("openai", "gpt-4o", None)
        assert t.cached_tokens == 0
        assert "No usage data" in t.notes

    def test_to_dict_has_required_fields(self):
        t = parse_cache_telemetry("openai", "gpt-4o", {"prompt_tokens": 100})
        d = t.to_dict()
        assert "provider" in d
        assert "model" in d
        assert "cached_tokens" in d
        assert "cache_hit_ratio" in d
        assert "estimated_cost_saved_usd" in d
        assert "latency_ms" in d
        assert "cache_supported" in d


class TestProviderCacheSupport:
    def test_openai_supported(self):
        info = get_provider_cache_status("openai")
        assert info["supported"] is True
        assert info["status"] == "DAILY_DRIVER_ACCEPT"

    def test_anthropic_planned(self):
        info = get_provider_cache_status("anthropic")
        assert info["status"] == "PLANNED_IN_EXISTING_PROMPT"

    def test_openrouter_no_assumption(self):
        info = get_provider_cache_status("openrouter")
        assert info["supported"] is False

    def test_unknown_provider_safe_default(self):
        info = get_provider_cache_status("mystery_provider")
        assert info["supported"] is False
        assert "not in cache support matrix" in info["notes"]

    def test_invalidation_rules_present(self):
        assert "repo_map" in INVALIDATION_RULES
        assert "tool_schema" in INVALIDATION_RULES
        assert "provider_matrix" in INVALIDATION_RULES
        assert "project_context" in INVALIDATION_RULES
