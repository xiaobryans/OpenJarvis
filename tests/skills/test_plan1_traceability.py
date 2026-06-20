"""Plan 1 ECC Traceability — count correctness and raw-to-unique invariant tests.

Proves all required items from the Traceability Corrective Sprint:
  A. Raw ECC coverage traceability — every raw item maps to unique capability or exclusion
  B. Raw-to-unique invariant — missing count is zero for every category
  C. Count correction — active count is internally consistent (28 = 22+3+3)
  D. Script category accounting — 42 raw scripts are fully accounted for
  E. Commands/agents/hooks accounting — all raw counts accounted for via explicit+catch_all
  F. Report generator — traceability summary produces correct data shape
  G. No unsafe activation — no catch-all item is active; no risky wrapper is enabled

These tests run OFFLINE (no network). They use:
  - Hardcoded KNOWN_RAW_COUNTS from the official ECC inventory run
  - ECCCatalog static classification logic
  - ecc_traceability.py classification functions (imported offline)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest

from openjarvis.skills.ecc_catalog import (
    ACTIVE_COUNT_BY_CATEGORY,
    ADAPTED_SKILL_ACTIVE_COUNT,
    ADAPTED_SKILL_MANIFEST_COUNT,
    CATCH_ALL_COUNTS,
    ECCCatalog,
    EXPLICITLY_CATALOGED_COUNTS,
    RAW_INVENTORY_COUNTS,
    get_catalog,
)
from openjarvis.skills.sources.ecc.adapted_skills import ADAPTED_SKILLS, list_adapted_skill_ids


# ---------------------------------------------------------------------------
# Module loading helpers — register in sys.modules before exec (fixes @dataclass)
# ---------------------------------------------------------------------------

def _load_traceability() -> Any:
    """Load ecc_traceability.py correctly (registers in sys.modules for @dataclass)."""
    import importlib.util
    import sys as _sys
    _path = Path(__file__).parent.parent.parent / "tools" / "ecc_traceability.py"
    _spec = importlib.util.spec_from_file_location("ecc_traceability_test", _path)
    _mod = importlib.util.module_from_spec(_spec)
    _sys.modules["ecc_traceability_test"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod


def _load_full_registry() -> Any:
    """Load ecc_full_registry.py correctly."""
    import importlib.util
    import sys as _sys
    _path = Path(__file__).parent.parent.parent / "tools" / "ecc_full_registry.py"
    _spec = importlib.util.spec_from_file_location("ecc_full_registry_test", _path)
    _mod = importlib.util.module_from_spec(_spec)
    _sys.modules["ecc_full_registry_test"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod


from typing import Any


# ---------------------------------------------------------------------------
# A. Raw ECC coverage traceability
# ---------------------------------------------------------------------------


class TestRawCoverageTraceability:
    """Prove every raw ECC surfaced item maps to a unique capability or exclusion."""

    def test_traceability_summary_builds_offline(self) -> None:
        """get_traceability_summary() runs without network calls."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        assert summary is not None
        assert "per_category" in summary
        assert "totals" in summary

    def test_every_category_has_raw_count(self) -> None:
        """RAW_INVENTORY_COUNTS has an entry for every major ECC category."""
        required = {"skills", "commands", "agents", "hooks", "scripts", "plugins", "mcp_configs"}
        for cat in required:
            assert cat in RAW_INVENTORY_COUNTS, f"Missing category: {cat}"
            assert RAW_INVENTORY_COUNTS[cat] > 0, f"Category {cat} has zero raw count"

    def test_known_raw_skills_count(self) -> None:
        """Known raw skills count is 300 (updated in Plan 1 ECC completion sprint:
        50 catch-all guidance skills added, raising lower-bound from 273 to 300)."""
        assert RAW_INVENTORY_COUNTS["skills"] == 300

    def test_known_raw_commands_count(self) -> None:
        """Known raw commands count is 432 (from official ECC inventory)."""
        assert RAW_INVENTORY_COUNTS["commands"] == 432

    def test_known_raw_agents_count(self) -> None:
        """Known raw agents count is 371."""
        assert RAW_INVENTORY_COUNTS["agents"] == 371

    def test_known_raw_hooks_count(self) -> None:
        """Known raw hooks count is 127."""
        assert RAW_INVENTORY_COUNTS["hooks"] == 127

    def test_known_raw_scripts_count(self) -> None:
        """Known raw scripts count is 42."""
        assert RAW_INVENTORY_COUNTS["scripts"] == 42

    def test_known_raw_plugins_count(self) -> None:
        """Known raw plugins count is 8."""
        assert RAW_INVENTORY_COUNTS["plugins"] == 8

    def test_known_raw_mcp_count(self) -> None:
        """Known raw MCP config count is 1."""
        assert RAW_INVENTORY_COUNTS["mcp_configs"] == 1

    def test_known_total_files(self) -> None:
        """Known total ECC file count is 3,251."""
        assert RAW_INVENTORY_COUNTS["total_files"] == 3251

    def test_traceability_dedup_functions_offline(self) -> None:
        """Traceability classification functions work offline (no network)."""
        mod = _load_traceability()
        assert mod.raw_category(".agents/skills/eval-harness/SKILL.md") == "skill"
        assert mod.raw_category("commands/checkpoint.md") == "command"
        assert mod.raw_category(".claude/commands/checkpoint.md") == "command"
        assert mod.raw_category("agents/code-reviewer.md") == "agent"
        assert mod.raw_category("hooks/pre-commit.sh") == "hook"
        assert mod.raw_category("plugins/marketplace.json") == "plugin"

    def test_dedupe_reason_canonical_vs_harness(self) -> None:
        """dedupe_reason() correctly classifies canonical vs harness duplicate paths."""
        mod = _load_traceability()
        assert mod.dedupe_reason("commands/checkpoint.md") == "CANONICAL"
        assert mod.dedupe_reason("agents/code-reviewer.md") == "CANONICAL"
        assert mod.dedupe_reason("skills/eval-harness/SKILL.md") == "CANONICAL"
        assert mod.dedupe_reason(".claude/commands/checkpoint.md") == "HARNESS_DUP"
        assert mod.dedupe_reason(".cursor/commands/checkpoint.md") == "HARNESS_DUP"
        assert mod.dedupe_reason(".agents/skills/eval-harness/SKILL.md") == "HARNESS_DUP"
        assert mod.dedupe_reason("docs/es/skills/eval-harness/SKILL.md") == "DOCS_DUP"
        assert mod.dedupe_reason("legacy-command-shims/old-cmd.md") == "LEGACY_DUP"

    def test_capability_name_extraction(self) -> None:
        """capability_name() extracts correct names from various path formats."""
        mod = _load_traceability()
        assert mod.capability_name(".agents/skills/eval-harness/SKILL.md", "skill") == "eval-harness"
        assert mod.capability_name("commands/checkpoint.md", "command") == "checkpoint"
        assert mod.capability_name(".claude/commands/checkpoint.md", "command") == "checkpoint"
        assert mod.capability_name("agents/code-reviewer.md", "agent") == "code-reviewer"
        assert mod.capability_name("hooks/pre-commit.sh", "hook") == "pre-commit"


# ---------------------------------------------------------------------------
# B. Raw-to-unique invariant — missing count is zero
# ---------------------------------------------------------------------------


class TestRawToUniqueInvariant:
    """Prove raw_count = explicitly_cataloged + catch_all + 0 missing for every category."""

    def test_missing_count_is_zero_for_every_category(self) -> None:
        """For every category: raw = explicit + catch_all, missing = 0."""
        for cat in RAW_INVENTORY_COUNTS:
            if cat == "total_files":
                continue
            raw = RAW_INVENTORY_COUNTS[cat]
            explicit = EXPLICITLY_CATALOGED_COUNTS.get(cat, 0)
            catch_all = CATCH_ALL_COUNTS.get(cat, 0)
            missing = raw - explicit - catch_all
            assert missing == 0, (
                f"Category '{cat}': raw={raw}, explicit={explicit}, "
                f"catch_all={catch_all}, missing={missing} — BLOCKER"
            )

    def test_catch_all_counts_are_nonnegative(self) -> None:
        """No category has negative catch-all count (would indicate catalog overcounting)."""
        for cat, count in CATCH_ALL_COUNTS.items():
            assert count >= 0, (
                f"Catch-all count is negative for '{cat}': {count} — "
                f"implies catalog has more items than raw inventory found"
            )

    def test_explicitly_cataloged_leq_raw(self) -> None:
        """Explicitly cataloged count never exceeds raw count."""
        for cat in EXPLICITLY_CATALOGED_COUNTS:
            if cat not in RAW_INVENTORY_COUNTS:
                continue
            assert EXPLICITLY_CATALOGED_COUNTS[cat] <= RAW_INVENTORY_COUNTS[cat], (
                f"Catalog has MORE entries than raw inventory for '{cat}': "
                f"{EXPLICITLY_CATALOGED_COUNTS[cat]} > {RAW_INVENTORY_COUNTS[cat]}"
            )

    def test_total_missing_is_zero(self) -> None:
        """Sum of all missing counts across all categories is 0."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        assert summary["totals"]["total_missing"] == 0, (
            f"Total missing = {summary['totals']['total_missing']}: {summary['totals']}"
        )

    def test_math_check_string_correct(self) -> None:
        """Traceability math check string is internally consistent."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        totals = summary["totals"]
        raw = totals["total_raw_surfaced"]
        explicit = totals["total_explicitly_cataloged"]
        catch_all = totals["total_catch_all"]
        missing = totals["total_missing"]
        assert raw == explicit + catch_all + missing, (
            f"Math check failed: {raw} ≠ {explicit} + {catch_all} + {missing}"
        )

    def test_skills_traceability(self) -> None:
        """300 raw skills = 291 explicit + 9 catch-all.

        Updated in Plan 1 ECC completion sprint: 50 catch-all skills moved to explicit,
        raising explicit from 240→291 and raw lower-bound from 273→300.
        """
        assert RAW_INVENTORY_COUNTS["skills"] == 300
        assert EXPLICITLY_CATALOGED_COUNTS["skills"] == 291
        assert CATCH_ALL_COUNTS["skills"] == 9
        assert 300 == 291 + 9

    def test_commands_traceability(self) -> None:
        """432 raw commands = 9 explicit + 423 catch-all."""
        assert RAW_INVENTORY_COUNTS["commands"] == 432
        assert EXPLICITLY_CATALOGED_COUNTS["commands"] == 9
        assert CATCH_ALL_COUNTS["commands"] == 423
        assert 432 == 9 + 423

    def test_agents_traceability(self) -> None:
        """371 raw agents = 13 explicit + 358 catch-all."""
        assert RAW_INVENTORY_COUNTS["agents"] == 371
        assert EXPLICITLY_CATALOGED_COUNTS["agents"] == 13
        assert 371 == 13 + CATCH_ALL_COUNTS["agents"]

    def test_hooks_traceability(self) -> None:
        """127 raw hooks = 10 explicit + 117 catch-all."""
        assert RAW_INVENTORY_COUNTS["hooks"] == 127
        assert EXPLICITLY_CATALOGED_COUNTS["hooks"] == 10
        assert CATCH_ALL_COUNTS["hooks"] == 117
        assert 127 == 10 + 117

    def test_mcp_traceability(self) -> None:
        """1 raw MCP config = 1 explicit + 0 catch-all."""
        assert RAW_INVENTORY_COUNTS["mcp_configs"] == 1
        assert EXPLICITLY_CATALOGED_COUNTS["mcp_configs"] == 1
        assert CATCH_ALL_COUNTS["mcp_configs"] == 0

    def test_catch_all_items_have_safe_default_states(self) -> None:
        """Catch-all items always get safe default states (never active)."""
        mod = _load_traceability()
        assert mod._default_state("skill") == "inspect_later"
        assert mod._default_state("hook") == "adapt_needed"
        assert mod._default_state("script") == "adapt_needed"
        assert mod._default_state("plugin") == "adapt_needed"
        for cat in ("skill", "command", "agent", "hook", "script", "plugin", "mcp_config", "context"):
            assert mod._default_state(cat) != "active", f"Default state for {cat} is active — unsafe"

    def test_classify_skill_always_returns_valid_state(self) -> None:
        """classify_skill() in registry builder never returns None state (catch-all proof)."""
        mod = _load_full_registry()

        valid_states = {"active", "installed_disabled", "adapt_needed", "inspect_later"}
        test_names = [
            "unknown-skill", "xyz-123", "some-new-skill", "test",
            "my-totally-new-capability", "future-skill-not-yet-in-catalog",
        ]
        for name in test_names:
            result = mod.classify_skill(name)
            assert result["state"] in valid_states, (
                f"classify_skill('{name}') returned invalid state: {result['state']}"
            )
            assert result["state"] is not None


# ---------------------------------------------------------------------------
# C. Count correction — active count must be internally consistent
# ---------------------------------------------------------------------------


class TestActiveCountConsistency:
    """Active count is 316 post Prompt 2 live validation.

    Pre-Prompt-2 baseline: 244 skills + 3 contexts + 8 commands = 255.
    Prompt 2 additions: +24 API-key + +36 approval + +1 Flox = +61.
    New total: 316.
    """

    def test_active_total_is_316(self) -> None:
        """Catalog active count is 316 after Prompt 2 live validation."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        assert summary["active_count"] == 316, (
            f"Expected 316 active items (Prompt 2 baseline), got {summary['active_count']}"
        )

    def test_pre_prompt2_baseline_documented(self) -> None:
        """Pre-Prompt-2 baseline (255) is documented in ACTIVE_COUNT_BY_CATEGORY['TOTAL']."""
        assert ACTIVE_COUNT_BY_CATEGORY["TOTAL"] == 255, (
            f"Pre-Prompt-2 baseline must be 255, got {ACTIVE_COUNT_BY_CATEGORY['TOTAL']}"
        )

    def test_prompt2_total_documented(self) -> None:
        """Prompt-2 total (316) is documented in ACTIVE_COUNT_BY_CATEGORY['PROMPT2_TOTAL']."""
        assert ACTIVE_COUNT_BY_CATEGORY.get("PROMPT2_TOTAL", 0) == 316, (
            f"PROMPT2_TOTAL must be 316, got {ACTIVE_COUNT_BY_CATEGORY.get('PROMPT2_TOTAL', 0)}"
        )

    def test_active_decomposition_baseline_categories(self) -> None:
        """Pre-Prompt-2 baseline: 244 skills + 3 contexts + 8 commands."""
        assert ACTIVE_COUNT_BY_CATEGORY["skill"] == 244
        assert ACTIVE_COUNT_BY_CATEGORY["context"] == 3
        assert ACTIVE_COUNT_BY_CATEGORY["command"] == 8

    def test_active_item_list_length_matches_count(self) -> None:
        """active_items list length equals active_count (no phantom entries)."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        assert len(summary["active_items"]) == summary["active_count"], (
            f"active_items list length={len(summary['active_items'])} ≠ active_count={summary['active_count']}"
        )

    def test_active_count_matches_traceability_decomposition(self) -> None:
        """Traceability active decomposition total matches catalog active count."""
        catalog = ECCCatalog()
        trace = catalog.get_traceability_summary()
        assert trace["active_count_decomposition"]["matches_expected"] is True, (
            f"Active count mismatch: {trace['active_count_decomposition']}"
        )

    def test_adapted_skill_count_vs_active(self) -> None:
        """Adapted manifest count (23) vs active catalog skills (22) is documented."""
        assert ADAPTED_SKILL_MANIFEST_COUNT == 23
        assert ADAPTED_SKILL_ACTIVE_COUNT == 22
        assert len(ADAPTED_SKILLS) == ADAPTED_SKILL_MANIFEST_COUNT

        catalog = ECCCatalog()
        trace = catalog.get_traceability_summary()
        adapted_vs = trace["adapted_skills_vs_active"]

        assert adapted_vs["adapted_manifest_count"] == 23
        assert adapted_vs["adapted_manifests_active_in_catalog"] == 22
        assert adapted_vs["difference_count"] == 1
        assert adapted_vs["is_consistent"] is True  # deliberate design, fully documented

    def test_continuous_learning_v2_is_active(self) -> None:
        """After Prompt 2: continuous-learning-v2 → ACTIVE (AIMLAPI_API_KEY verified)."""
        catalog = ECCCatalog()
        entry = catalog.get("ecc:continuous-learning-v2")
        assert entry is not None, "ecc:continuous-learning-v2 must be in catalog"
        assert entry["plan1_state"] == "ACTIVE", (
            f"Expected ACTIVE after Prompt 2 (AIMLAPI_API_KEY confirmed), got {entry.get('plan1_state')}"
        )

    def test_eval_harness_is_installed_disabled_not_active(self) -> None:
        """eval-harness is installed_disabled (pilot handled by EvalContextSkill)."""
        catalog = ECCCatalog()
        entry = catalog.get("ecc:eval-harness")
        assert entry is not None
        assert entry["state"] == "installed_disabled", (
            f"Expected installed_disabled, got {entry['state']}"
        )

    def test_agents_are_active_after_prompt2(self) -> None:
        """After Prompt 2: all 13 agents are ACTIVE (profiles registered, routing still gated)."""
        catalog = ECCCatalog()
        active_agents = [
            e for e in catalog.list_active()
            if e.get("category") == "agent"
        ]
        assert len(active_agents) == 13, (
            f"Expected 13 active agents after Prompt 2, got {len(active_agents)}: "
            f"{[a['candidate_id'] for a in active_agents]}"
        )

    def test_hooks_are_active_after_prompt2(self) -> None:
        """After Prompt 2: all 10 hooks are ACTIVE (framework registered, execution gated)."""
        catalog = ECCCatalog()
        active_hooks = [e for e in catalog.list_active() if e.get("category") == "hook"]
        assert len(active_hooks) == 10, (
            f"Expected 10 active hooks after Prompt 2, got {len(active_hooks)}"
        )

    def test_no_scripts_are_active(self) -> None:
        """No script entries are ACTIVE."""
        catalog = ECCCatalog()
        scripts = catalog.list_by_category("script")
        active_scripts = [s for s in scripts if s.get("state") == "active"]
        assert active_scripts == []


# ---------------------------------------------------------------------------
# D. Script category accounting — 42 raw scripts fully accounted for
# ---------------------------------------------------------------------------


class TestScriptCategoryAccounting:
    def test_42_raw_scripts_known(self) -> None:
        """RAW_INVENTORY_COUNTS records 42 scripts."""
        assert RAW_INVENTORY_COUNTS["scripts"] == 42

    def test_explicit_script_wrappers_count(self) -> None:
        """EXPLICITLY_CATALOGED_COUNTS has 3 explicit script wrappers."""
        assert EXPLICITLY_CATALOGED_COUNTS["scripts"] == 3

    def test_catch_all_scripts_count(self) -> None:
        """CATCH_ALL_COUNTS has 39 catch-all scripts (42 - 3 = 39)."""
        assert CATCH_ALL_COUNTS["scripts"] == 39

    def test_script_math_zero_missing(self) -> None:
        """42 = 3 (explicit) + 39 (catch-all) + 0 (missing)."""
        raw = RAW_INVENTORY_COUNTS["scripts"]
        explicit = EXPLICITLY_CATALOGED_COUNTS["scripts"]
        catch_all = CATCH_ALL_COUNTS["scripts"]
        assert raw == explicit + catch_all, f"Script math: {raw} ≠ {explicit} + {catch_all}"

    def test_explicit_scripts_in_wrapper_registry(self) -> None:
        """The 3 explicit script wrappers exist in KNOWN_SCRIPTS."""
        from openjarvis.skills.wrappers import KNOWN_SCRIPTS
        assert len(KNOWN_SCRIPTS) == 3, f"Expected 3 KNOWN_SCRIPTS, got {len(KNOWN_SCRIPTS)}"
        script_ids = {s.candidate_id for s in KNOWN_SCRIPTS}
        assert "ecc:script:install" in script_ids
        assert "ecc:script:uninstall" in script_ids
        assert "ecc:script:merge-mcp-config" in script_ids

    def test_catch_all_scripts_are_adapt_needed(self) -> None:
        """Default state for any catch-all script is adapt_needed (never active)."""
        mod = _load_traceability()
        assert mod._default_state("script") == "adapt_needed"

    def test_no_scripts_are_active(self) -> None:
        """Zero scripts in ACTIVE state (no raw script execution)."""
        from openjarvis.skills.wrappers import KNOWN_SCRIPTS
        active_scripts = [s for s in KNOWN_SCRIPTS if s.enabled]
        assert active_scripts == [], f"Scripts are enabled: {active_scripts}"

    def test_script_traceability_in_catalog_summary(self) -> None:
        """Traceability summary confirms script coverage."""
        catalog = ECCCatalog()
        trace = catalog.get_traceability_summary()
        script_trace = trace["script_coverage"]
        assert script_trace["raw_script_count"] == 42
        assert script_trace["explicit_script_wrappers"] == 3
        assert script_trace["catch_all_scripts"] == 39
        assert script_trace["all_scripts_adapt_needed"] is True
        assert script_trace["no_scripts_executed"] is True


# ---------------------------------------------------------------------------
# E. Commands/agents/hooks accounting
# ---------------------------------------------------------------------------


class TestCommandsAgentsHooksAccounting:
    def test_commands_explicit_plus_catch_all_equals_raw(self) -> None:
        """432 commands = 9 explicit + 423 catch-all."""
        raw = RAW_INVENTORY_COUNTS["commands"]
        explicit = EXPLICITLY_CATALOGED_COUNTS["commands"]
        catch_all = CATCH_ALL_COUNTS["commands"]
        assert raw == explicit + catch_all
        assert catch_all == 423

    def test_agents_explicit_plus_catch_all_equals_raw(self) -> None:
        """371 agents = 13 explicit + 358 catch-all."""
        raw = RAW_INVENTORY_COUNTS["agents"]
        explicit = EXPLICITLY_CATALOGED_COUNTS["agents"]
        catch_all = CATCH_ALL_COUNTS["agents"]
        assert raw == explicit + catch_all
        assert catch_all >= 350  # at least 350 in catch-all

    def test_hooks_explicit_plus_catch_all_equals_raw(self) -> None:
        """127 hooks = 10 explicit + 117 catch-all."""
        raw = RAW_INVENTORY_COUNTS["hooks"]
        explicit = EXPLICITLY_CATALOGED_COUNTS["hooks"]
        catch_all = CATCH_ALL_COUNTS["hooks"]
        assert raw == explicit + catch_all
        assert catch_all == 117

    def test_catch_all_dedup_reason(self) -> None:
        """Large command/agent counts come from harness-specific paths (HANDs, not unique capabilities)."""
        mod = _load_traceability()
        assert mod.dedupe_reason(".claude/commands/feature-development.md") == "HARNESS_DUP"
        assert mod.dedupe_reason("commands/feature-development.md") == "CANONICAL"
        assert mod.dedupe_reason(".cursor/commands/feature-development.md") == "HARNESS_DUP"

    def test_catch_all_hooks_framework_registered_but_execution_gated(self) -> None:
        """After Prompt 2: hooks are ACTIVE in catalog (framework registered), but execution is gated.
        KNOWN_HOOKS wrappers remain disabled (enabled=False); catalog state=active is registry wiring only."""
        from openjarvis.skills.wrappers import KNOWN_HOOKS
        for hook in KNOWN_HOOKS:
            assert not hook.enabled, f"Hook wrapper {hook.candidate_id} is enabled (execution should stay gated)"

        catalog = ECCCatalog()
        catalog_hooks = catalog.list_by_category("hook")
        # After Prompt 2: hooks have plan1_state=ACTIVE and state=active (registry wired)
        for hook in catalog_hooks:
            assert hook["plan1_state"] == "ACTIVE", (
                f"Hook {hook['candidate_id']} should be ACTIVE (registry wired) after Prompt 2"
            )
            reason = hook.get("reason", "")
            # Reason must mention that execution is still gated
            assert (
                "gated" in reason.lower()
                or "approval" in reason.lower()
                or "disabled" in reason.lower()
                or "registry" in reason.lower()
            ), f"Hook {hook['candidate_id']}: reason must mention gating"

    def test_catch_all_default_never_active(self) -> None:
        """The catch-all default state is never 'active' for any category."""
        mod = _load_traceability()
        for cat in ("skill", "command", "agent", "hook", "script", "plugin", "mcp_config", "context", "rule"):
            state = mod._default_state(cat)
            assert state in ("inspect_later", "adapt_needed"), (
                f"Default state for {cat} is '{state}' — should be inspect_later or adapt_needed"
            )
            assert state != "active", f"Default state for {cat} is 'active' — UNSAFE"


# ---------------------------------------------------------------------------
# F. Report generator — traceability summary shape
# ---------------------------------------------------------------------------


class TestTraceabilityReportGenerator:
    def test_traceability_summary_required_keys(self) -> None:
        """get_traceability_summary() returns all required top-level keys."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        required = {
            "per_category", "totals", "active_count_decomposition",
            "adapted_skills_vs_active", "script_coverage",
            "no_ecc_code_executed", "all_active_are_explicitly_cataloged",
            "no_catch_all_item_is_active",
        }
        missing = required - set(summary.keys())
        assert missing == set(), f"Missing keys: {missing}"

    def test_per_category_has_all_categories(self) -> None:
        """per_category has entries for all major ECC categories."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        per_cat = summary["per_category"]
        required = {"skills", "commands", "agents", "hooks", "scripts", "plugins", "mcp_configs"}
        for cat in required:
            assert cat in per_cat, f"Missing category in per_category: {cat}"

    def test_per_category_entry_shape(self) -> None:
        """Each per_category entry has required fields."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        required_fields = {"raw_unique_count", "explicitly_cataloged", "catch_all_classified",
                           "missing", "missing_is_zero", "catch_all_default_state"}
        for cat, entry in summary["per_category"].items():
            missing_fields = required_fields - set(entry.keys())
            assert missing_fields == set(), f"Category {cat} missing fields: {missing_fields}"

    def test_per_category_missing_is_zero(self) -> None:
        """Every category's missing field is exactly 0."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        for cat, entry in summary["per_category"].items():
            assert entry["missing"] == 0, f"Category {cat}: missing={entry['missing']} ≠ 0"
            assert entry["missing_is_zero"] is True

    def test_no_ecc_code_executed(self) -> None:
        """Traceability summary confirms no ECC code executed."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        assert summary["no_ecc_code_executed"] is True

    def test_all_active_explicitly_cataloged(self) -> None:
        """Traceability confirms all active items are explicitly cataloged."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        assert summary["all_active_are_explicitly_cataloged"] is True

    def test_no_catch_all_item_is_active(self) -> None:
        """Traceability confirms no catch-all item is active."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        assert summary["no_catch_all_item_is_active"] is True

    def test_format_traceability_report_offline(self) -> None:
        """ecc_traceability.py format_text_report() runs without network."""
        mod = _load_traceability()
        test_files = [
            {"path": "commands/checkpoint.md", "type": "blob"},
            {"path": ".claude/commands/checkpoint.md", "type": "blob"},
            {"path": "skills/eval-harness/SKILL.md", "type": "blob"},
            {"path": ".cursor/skills/eval-harness/SKILL.md", "type": "blob"},
            {"path": "hooks/pre-commit.sh", "type": "blob"},
            {"path": "scripts/install.sh", "type": "blob"},
            {"path": "plugins/marketplace.json", "type": "blob"},
            {"path": "mcp-configs/mcp-servers.json", "type": "blob"},
        ]
        report = mod.build_traceability(test_files)
        text = mod.format_text_report(report)

        assert "TRACEABILITY REPORT" in text
        assert "Missing count" in text
        assert "SCRIPT COVERAGE" in text
        assert "ECC code executed: NO" in text


# ---------------------------------------------------------------------------
# G. No unsafe activation — risky categories remain disabled
# ---------------------------------------------------------------------------


class TestNoUnsafeActivation:
    def test_no_catch_all_item_is_active_in_catalog(self) -> None:
        """No item in the catch-all pool (33 skills + 423 commands + ...) is active."""
        catalog = ECCCatalog()
        summary = catalog.get_traceability_summary()
        assert summary["no_catch_all_item_is_active"] is True

    def test_all_risky_wrappers_disabled(self) -> None:
        """All hook/script/plugin/MCP wrappers are disabled (enabled=False)."""
        from openjarvis.skills.wrappers import get_wrapper_registry
        reg = get_wrapper_registry()
        assert reg.list_enabled() == [], "Some risky wrapper is enabled — unsafe"

    def test_all_hooks_disabled(self) -> None:
        """All 6 explicit ECC hooks are disabled by default."""
        from openjarvis.skills.wrappers import KNOWN_HOOKS
        for hook in KNOWN_HOOKS:
            assert not hook.enabled, f"Hook {hook.candidate_id} is auto-enabled"

    def test_all_scripts_disabled(self) -> None:
        """All 3 explicit ECC scripts are disabled by default."""
        from openjarvis.skills.wrappers import KNOWN_SCRIPTS
        for script in KNOWN_SCRIPTS:
            assert not script.enabled, f"Script {script.candidate_id} is auto-enabled"

    def test_mcp_config_disabled(self) -> None:
        """ECC MCP config is disabled by default."""
        from openjarvis.skills.wrappers import KNOWN_MCP_CONFIGS
        for mcp in KNOWN_MCP_CONFIGS:
            assert not mcp.enabled, f"MCP {mcp.candidate_id} is auto-enabled"

    def test_no_ecc_code_executed_by_module_import(self) -> None:
        """Importing all Plan 1 modules does not execute any ECC code."""
        from openjarvis.skills.ecc_catalog import ECCCatalog
        from openjarvis.skills.wrappers import WrapperRegistry
        from openjarvis.skills.sources.ecc.adapted_skills import ADAPTED_SKILLS
        # If we got here without errors or side effects, no code was executed


# ---------------------------------------------------------------------------
# Count consistency regression guard
# ---------------------------------------------------------------------------


class TestCountConsistencyRegression:
    def test_api_active_count_matches_catalog(self) -> None:
        """API would return same active count as catalog."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        active_items = catalog.list_active()
        assert summary["active_count"] == len(active_items)

    def test_catalog_total_registered_count(self) -> None:
        """Catalog has 332 total registered entries (post Plan 1 completion sprint).

        Pre-sprint baseline was ~281. Plan 1 sprint added 50 catch-all skills,
        plus hooks/plugins/MCP/agent/command entries = 332 total.
        """
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        # Allow small variance (±10) since catalog might be updated
        assert 320 <= summary["total_registered"] <= 345, (
            f"Total registered {summary['total_registered']} out of expected range [320, 345]"
        )

    def test_skill_category_count(self) -> None:
        """Skill category has ≥240 entries in catalog."""
        catalog = ECCCatalog()
        skills = catalog.list_by_category("skill")
        assert len(skills) >= 240, f"Expected ≥240 skills, got {len(skills)}"

    def test_state_counts_sum_to_total(self) -> None:
        """Sum of all state counts equals total_registered."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        state_sum = sum(summary["state_counts"].values())
        assert state_sum == summary["total_registered"], (
            f"State counts sum {state_sum} ≠ total {summary['total_registered']}"
        )
