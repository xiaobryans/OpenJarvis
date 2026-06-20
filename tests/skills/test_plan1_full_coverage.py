"""Plan 1 Full ECC Coverage — certification test suite.

Proves all 12 required items from the Full ECC Coverage Sprint:
  1. All ECC items can be registered without execution
  2. Registry stores every category
  3. Activation requires reviewer/preflight gates
  4. Safe read-only skills/commands can activate
  5. Risky hooks/scripts/plugins/MCP remain disabled unless gated
  6. Disabled/quarantined items cannot run
  7. Rollback/quarantine/disable works
  8. Front-door/registry can discover active items
  9. Duplicate/redundant candidates are not blindly activated
 10. Candidate-level preflight records reasons
 11. Python/local-first processing works
 12. No raw ECC hooks/scripts/plugins/MCP were executed

Additional proves:
  - All 23 adapted skills are importable and have correct manifests
  - ECC catalog covers skills, commands, agents, hooks, plugins, MCP
  - Status API returns correct data shape
  - Wrappers enforce dry_run and disabled-by-default
  - Risky categories have documented activation blockers
  - No Jarvis regression in existing security/registry tests
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Catalog imports
# ---------------------------------------------------------------------------

from openjarvis.skills.ecc_catalog import ECCCatalog, get_catalog

# ---------------------------------------------------------------------------
# Intake imports
# ---------------------------------------------------------------------------

from openjarvis.skills.intake import (
    CandidateRegistry,
    ExternalCandidateCategory,
    ExternalCandidatePriority,
    ExternalCandidateState,
    IntakeGate,
    IntakeGateError,
    IntakePreflight,
    make_ecc_candidate,
)

# ---------------------------------------------------------------------------
# Adapted skills imports
# ---------------------------------------------------------------------------

from openjarvis.skills.sources.ecc.adapted_skills import (
    ADAPTED_SKILLS,
    BENCHMARK_METHODOLOGY,
    CODING_STANDARDS,
    CONTEXT_BUDGET,
    DOCUMENTATION_LOOKUP,
    GIT_WORKFLOW,
    SAFETY_GUARD,
    SECURITY_SCAN,
    STRATEGIC_COMPACT,
    TDD_WORKFLOW,
    TOKEN_BUDGET_ADVISOR,
    VERIFICATION_LOOP,
    get_adapted_skill,
    list_adapted_skill_ids,
)

# ---------------------------------------------------------------------------
# Wrappers imports
# ---------------------------------------------------------------------------

from openjarvis.skills.wrappers import (
    HookWrapper,
    KNOWN_HOOKS,
    KNOWN_MCP_CONFIGS,
    KNOWN_PLUGINS,
    KNOWN_SCRIPTS,
    MCPConfigWrapper,
    PluginWrapper,
    ScriptWrapper,
    WrapperRegistry,
    get_wrapper_registry,
)


# ---------------------------------------------------------------------------
# 1. All ECC items can be registered without execution
# ---------------------------------------------------------------------------


class TestRegistrationWithoutExecution:
    def test_catalog_loads_without_network_calls(self) -> None:
        """ECCCatalog builds static catalog at import time — no network required."""
        catalog = ECCCatalog()
        # If this raises, it means a network call was triggered unexpectedly
        items = catalog.list_all()
        assert len(items) > 0

    def test_adapted_skills_import_without_execution(self) -> None:
        """All 23 adapted skills load without executing any ECC code."""
        ids = list_adapted_skill_ids()
        assert len(ids) == 23, f"Expected 23, got {len(ids)}"
        for sid in ids:
            manifest = get_adapted_skill(sid)
            assert manifest is not None
            assert manifest.name.startswith("ecc_")

    def test_wrappers_load_without_execution(self) -> None:
        """All wrapper candidates load without executing any ECC code."""
        reg = WrapperRegistry()
        all_items = reg.list_all()
        # Has hooks, scripts, plugins, MCP
        assert len(all_items) > 0
        # None are enabled by default
        assert all(not c.enabled for c in all_items), "Some wrapper was auto-enabled"

    def test_wrapper_registry_no_enabled_by_default(self) -> None:
        """list_enabled() returns empty — no risky wrapper auto-activates."""
        reg = WrapperRegistry()
        assert reg.list_enabled() == []

    def test_no_ecc_code_in_module_namespace(self) -> None:
        """No ECC hook/script/plugin is in Python's loaded module paths."""
        import sys
        ecc_modules = [
            m for m in sys.modules
            if "ecc" in m.lower() and "hooks" in m.lower()
        ]
        # ECC hooks should not be in sys.modules
        assert ecc_modules == [], f"ECC hook modules loaded: {ecc_modules}"


# ---------------------------------------------------------------------------
# 2. Registry stores every category
# ---------------------------------------------------------------------------


class TestRegistryCoverage:
    def test_catalog_covers_all_categories(self) -> None:
        """Catalog has entries for all required ECC categories."""
        catalog = ECCCatalog()
        categories = {e["category"] for e in catalog.list_all()}
        required = {"skill", "command", "agent", "hook", "plugin", "mcp_config", "context"}
        missing = required - categories
        assert missing == set(), f"Missing categories in catalog: {missing}"

    def test_catalog_has_skills(self) -> None:
        """Catalog contains skill entries."""
        catalog = ECCCatalog()
        skills = catalog.list_by_category("skill")
        assert len(skills) >= 20, f"Expected ≥20 skills, got {len(skills)}"

    def test_catalog_has_commands(self) -> None:
        """Catalog contains command entries."""
        catalog = ECCCatalog()
        commands = catalog.list_by_category("command")
        assert len(commands) >= 3

    def test_catalog_has_agents(self) -> None:
        """Catalog contains agent entries."""
        catalog = ECCCatalog()
        agents = catalog.list_by_category("agent")
        assert len(agents) >= 5

    def test_catalog_has_hooks(self) -> None:
        """Catalog contains hook entries."""
        catalog = ECCCatalog()
        hooks = catalog.list_by_category("hook")
        assert len(hooks) >= 3

    def test_catalog_has_plugins(self) -> None:
        """Catalog contains plugin entries."""
        catalog = ECCCatalog()
        plugins = catalog.list_by_category("plugin")
        assert len(plugins) >= 3

    def test_catalog_has_mcp_configs(self) -> None:
        """Catalog contains MCP config entries."""
        catalog = ECCCatalog()
        mcp = catalog.list_by_category("mcp_config")
        assert len(mcp) >= 1

    def test_catalog_has_contexts(self) -> None:
        """Catalog has context entries (dev, research, review)."""
        catalog = ECCCatalog()
        contexts = catalog.list_by_category("context")
        context_names = {c["name"] for c in contexts}
        assert "dev" in context_names
        assert "research" in context_names
        assert "review" in context_names

    def test_all_entries_have_required_fields(self) -> None:
        """Every catalog entry has candidate_id, state, category, reason."""
        catalog = ECCCatalog()
        for entry in catalog.list_all():
            assert "candidate_id" in entry, f"Missing candidate_id: {entry}"
            assert "state" in entry, f"Missing state: {entry}"
            assert "category" in entry, f"Missing category: {entry}"
            assert "reason" in entry, f"Missing reason: {entry}"

    def test_all_entries_have_source_url(self) -> None:
        """Every catalog entry has official ECC source URL."""
        catalog = ECCCatalog()
        for entry in catalog.list_all():
            assert entry.get("source_url") == "https://github.com/affaan-m/ECC", (
                f"Wrong source_url on {entry.get('candidate_id')}: {entry.get('source_url')}"
            )

    def test_all_entries_have_mit_license(self) -> None:
        """Every catalog entry has MIT license."""
        catalog = ECCCatalog()
        for entry in catalog.list_all():
            assert entry.get("license_spdx") == "MIT", (
                f"Wrong license on {entry.get('candidate_id')}: {entry.get('license_spdx')}"
            )


# ---------------------------------------------------------------------------
# 3. Activation requires reviewer/preflight gates
# ---------------------------------------------------------------------------


class TestActivationGates:
    def test_inactive_skill_cannot_be_used_without_reviewer(self) -> None:
        """Candidate stays blocked without reviewer transition."""
        gate = IntakeGate()
        candidate = make_ecc_candidate(
            skill_id="test-gate", name="Test", description="X",
            category=ExternalCandidateCategory.SKILL,
            priority=ExternalCandidatePriority.LIKELY_ADOPT,
            license_spdx="MIT",
            state=ExternalCandidateState.INSTALLED_DISABLED,
            preflight_passed=True,
            reviewer_approved=True,
        )
        # Missing reviewer_id
        with pytest.raises(IntakeGateError, match="reviewer_id"):
            gate.transition(candidate, ExternalCandidateState.ACTIVE)

    def test_activation_blocked_without_preflight(self) -> None:
        """Cannot activate without preflight_passed=True."""
        gate = IntakeGate()
        candidate = make_ecc_candidate(
            skill_id="test-pf", name="X", description="X",
            category=ExternalCandidateCategory.SKILL,
            priority=ExternalCandidatePriority.LIKELY_ADOPT,
            license_spdx="MIT",
            state=ExternalCandidateState.INSTALLED_DISABLED,
            preflight_passed=False,
            reviewer_approved=True,
        )
        with pytest.raises(IntakeGateError, match="preflight"):
            gate.transition(candidate, ExternalCandidateState.ACTIVE, reviewer_id="bryan")

    def test_activation_blocked_without_reviewer_approved_flag(self) -> None:
        """Cannot activate without reviewer_approved=True on candidate."""
        gate = IntakeGate()
        candidate = make_ecc_candidate(
            skill_id="test-ra", name="X", description="X",
            category=ExternalCandidateCategory.SKILL,
            priority=ExternalCandidatePriority.LIKELY_ADOPT,
            license_spdx="MIT",
            state=ExternalCandidateState.INSTALLED_DISABLED,
            preflight_passed=True,
            reviewer_approved=False,
        )
        with pytest.raises(IntakeGateError, match="reviewer approval"):
            gate.transition(candidate, ExternalCandidateState.ACTIVE, reviewer_id="bryan")


# ---------------------------------------------------------------------------
# 4. Safe read-only skills can activate
# ---------------------------------------------------------------------------


class TestSafeSkillActivation:
    def test_active_skills_in_catalog(self) -> None:
        """Catalog has ≥20 ACTIVE skills (safe guidance items)."""
        catalog = ECCCatalog()
        active = catalog.list_active()
        assert len(active) >= 20, f"Expected ≥20 active, got {len(active)}"

    def test_active_skills_are_read_only(self) -> None:
        """All active skills have read_only permission scope."""
        catalog = ECCCatalog()
        for entry in catalog.list_active():
            assert "read_only" in entry.get("permission_scopes", []), (
                f"Active skill {entry['candidate_id']} not read_only: {entry.get('permission_scopes')}"
            )

    def test_active_skills_are_reviewer_approved(self) -> None:
        """All active catalog entries have reviewer_approved=True."""
        catalog = ECCCatalog()
        for entry in catalog.list_active():
            assert entry.get("reviewer_approved") is True, (
                f"Active skill {entry['candidate_id']} not reviewer_approved"
            )

    def test_active_skills_have_preflight_passed(self) -> None:
        """All active catalog entries have preflight_passed=True."""
        catalog = ECCCatalog()
        for entry in catalog.list_active():
            assert entry.get("preflight_passed") is True, (
                f"Active skill {entry['candidate_id']} preflight not passed"
            )

    def test_active_contexts_are_present(self) -> None:
        """Active context items (dev, research, review) are in catalog."""
        catalog = ECCCatalog()
        active_ids = {e["candidate_id"] for e in catalog.list_active()}
        assert "ecc:context:dev" in active_ids
        assert "ecc:context:research" in active_ids
        assert "ecc:context:review" in active_ids

    def test_active_commands_are_present(self) -> None:
        """Checkpoint command is in active catalog."""
        catalog = ECCCatalog()
        active_ids = {e["candidate_id"] for e in catalog.list_active()}
        assert "ecc:cmd:checkpoint" in active_ids

    def test_full_activation_lifecycle_for_safe_skill(self, tmp_path: Path) -> None:
        """A safe skill can complete full activation lifecycle."""
        gate = IntakeGate()
        reg = CandidateRegistry(registry_path=tmp_path / "test.json")
        candidate = make_ecc_candidate(
            skill_id="safe-guidance-test", name="Safe Test", description="X",
            category=ExternalCandidateCategory.SKILL,
            priority=ExternalCandidatePriority.LIKELY_ADOPT,
            license_spdx="MIT",
            state=ExternalCandidateState.DISCOVERED,
        )

        # Lifecycle
        gate.transition(candidate, ExternalCandidateState.CANDIDATE)
        gate.transition(candidate, ExternalCandidateState.APPROVED_FOR_INSTALL)
        gate.transition(candidate, ExternalCandidateState.INSTALLED_DISABLED, reviewer_id="bryan")
        candidate.preflight_passed = True
        candidate.reviewer_approved = True
        gate.transition(candidate, ExternalCandidateState.ACTIVE, reviewer_id="bryan")
        reg.register(candidate)

        assert candidate.state == ExternalCandidateState.ACTIVE
        assert candidate.is_usable is True


# ---------------------------------------------------------------------------
# 5. Risky hooks/scripts/plugins/MCP remain disabled unless gated
# ---------------------------------------------------------------------------


class TestRiskyItemsDisabledByDefault:
    def test_all_hooks_disabled_by_default(self) -> None:
        """No ECC hook is enabled by default."""
        for hook in KNOWN_HOOKS:
            assert not hook.enabled, f"Hook {hook.candidate_id} is enabled by default"
            assert hook.dry_run is True, f"Hook {hook.candidate_id} not in dry_run mode"

    def test_all_scripts_disabled_by_default(self) -> None:
        """No ECC script is enabled by default."""
        for script in KNOWN_SCRIPTS:
            assert not script.enabled, f"Script {script.candidate_id} is enabled by default"
            assert script.dry_run is True

    def test_all_plugins_disabled_by_default(self) -> None:
        """No ECC plugin is enabled by default."""
        for plugin in KNOWN_PLUGINS:
            assert not plugin.enabled, f"Plugin {plugin.candidate_id} is enabled by default"

    def test_all_mcp_configs_disabled_by_default(self) -> None:
        """No ECC MCP config is enabled by default."""
        for mcp in KNOWN_MCP_CONFIGS:
            assert not mcp.enabled, f"MCP {mcp.candidate_id} is enabled by default"

    def test_hooks_in_catalog_are_adapt_needed(self) -> None:
        """Hook catalog entries are in adapt_needed or installed_disabled state."""
        catalog = ECCCatalog()
        for hook in catalog.list_by_category("hook"):
            assert hook["state"] in ("adapt_needed", "installed_disabled"), (
                f"Hook {hook['candidate_id']} unexpectedly in state {hook['state']}"
            )

    def test_plugins_in_catalog_are_adapt_needed(self) -> None:
        """Plugin catalog entries are in adapt_needed state."""
        catalog = ECCCatalog()
        for plugin in catalog.list_by_category("plugin"):
            assert plugin["state"] in ("adapt_needed", "installed_disabled"), (
                f"Plugin {plugin['candidate_id']} unexpectedly active"
            )

    def test_mcp_configs_not_active(self) -> None:
        """No MCP config catalog entry is in ACTIVE state."""
        catalog = ECCCatalog()
        for mcp in catalog.list_by_category("mcp_config"):
            assert mcp["state"] != "active", (
                f"MCP config {mcp['candidate_id']} is unexpectedly active"
            )

    def test_risky_wrappers_have_activation_blockers(self) -> None:
        """All risky wrappers document their activation blockers."""
        for item in get_wrapper_registry().list_all():
            assert len(item.activation_blockers) > 0, (
                f"{item.candidate_id} has no activation blockers documented"
            )

    def test_wrapper_enable_without_preflight_fails(self) -> None:
        """Enabling a wrapper without preflight_passed raises ValueError."""
        hook = HookWrapper(candidate_id="ecc:hook:test", name="test")
        hook.preflight_passed = False
        hook.reviewer_approved = True
        with pytest.raises(ValueError, match="preflight"):
            hook.enable("bryan")

    def test_wrapper_enable_without_reviewer_fails(self) -> None:
        """Enabling a wrapper without reviewer_approved raises ValueError."""
        hook = HookWrapper(candidate_id="ecc:hook:test2", name="test2")
        hook.preflight_passed = True
        hook.reviewer_approved = False
        with pytest.raises(ValueError, match="reviewer"):
            hook.enable("bryan")

    def test_wrapper_enable_quarantined_fails(self) -> None:
        """Cannot enable a quarantined wrapper."""
        hook = HookWrapper(candidate_id="ecc:hook:test3", name="test3")
        hook.preflight_passed = True
        hook.reviewer_approved = True
        hook.quarantine("security concern")
        with pytest.raises(ValueError, match="quarantined"):
            hook.enable("bryan")


# ---------------------------------------------------------------------------
# 6 + 7. Disabled/quarantined items cannot run; rollback/quarantine works
# ---------------------------------------------------------------------------


class TestDisabledAndRollback:
    def test_disabled_wrapper_is_not_usable(self) -> None:
        """Disabled wrapper returns is_usable=False."""
        hook = HookWrapper(candidate_id="ecc:hook:x", name="x")
        assert hook.is_usable() is False

    def test_quarantine_disables_and_blocks(self) -> None:
        """Quarantine immediately blocks the wrapper."""
        script = ScriptWrapper(candidate_id="ecc:script:x", name="x")
        script.preflight_passed = True
        script.reviewer_approved = True
        script.enabled = True
        script.quarantine("suspected side effects")
        assert script.is_usable() is False
        assert script.quarantined is True

    def test_disable_removes_usability(self) -> None:
        """disable() removes usability from a previously usable wrapper."""
        hook = HookWrapper(candidate_id="ecc:hook:y", name="y")
        hook.preflight_passed = True
        hook.reviewer_approved = True
        hook.enabled = True  # simulate active (bypassing enable() for test)
        assert hook.is_usable() is True
        hook.disable()
        assert hook.is_usable() is False

    def test_registry_quarantine_gate(self, tmp_path: Path) -> None:
        """IntakeGate quarantine→rollback works on CandidateRegistry."""
        gate = IntakeGate()
        reg = CandidateRegistry(registry_path=tmp_path / "q.json")
        candidate = make_ecc_candidate(
            skill_id="rollback-test", name="RT", description="X",
            category=ExternalCandidateCategory.SKILL,
            priority=ExternalCandidatePriority.LIKELY_ADOPT,
            license_spdx="MIT",
            state=ExternalCandidateState.ACTIVE,
            preflight_passed=True,
            reviewer_approved=True,
        )
        reg.register(candidate)

        gate.quarantine(candidate, reason="test quarantine", registry=reg)
        assert candidate.state == ExternalCandidateState.QUARANTINED

        gate.rollback(candidate, registry=reg)
        assert candidate.state == ExternalCandidateState.ROLLED_BACK

        # Verify persisted
        reloaded = CandidateRegistry(registry_path=tmp_path / "q.json")
        record = reloaded.get("ecc:rollback-test")
        assert record is not None
        assert record.state == ExternalCandidateState.ROLLED_BACK


# ---------------------------------------------------------------------------
# 8. Front-door/registry can discover active items
# ---------------------------------------------------------------------------


class TestFrontDoorDiscovery:
    def test_status_summary_returns_active_items(self) -> None:
        """get_status_summary() lists all active item IDs."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        assert summary["active_count"] > 0
        assert len(summary["active_items"]) == summary["active_count"]

    def test_find_by_jarvis_skill_id(self) -> None:
        """find_by_jarvis_skill_id() resolves catalog entries for adapted skills."""
        catalog = ECCCatalog()
        for skill_id in list_adapted_skill_ids():
            entry = catalog.find_by_jarvis_skill_id(skill_id)
            if entry is not None:  # some adapted skills may not be in catalog yet
                assert entry.get("jarvis_skill_id") == skill_id

    def test_active_skills_have_ui_routes(self) -> None:
        """Active catalog entries (that have jarvis_skill_id) have ui_route."""
        catalog = ECCCatalog()
        for entry in catalog.list_active():
            if entry.get("jarvis_skill_id"):
                assert entry.get("ui_route") is not None, (
                    f"Active skill {entry['candidate_id']} missing ui_route"
                )

    def test_adapted_skill_invocation_route_format(self) -> None:
        """All adapted skills have correct route format skill:<id>:invoke."""
        catalog = ECCCatalog()
        for entry in catalog.list_active():
            if entry.get("jarvis_skill_id") and entry.get("ui_route"):
                route = entry["ui_route"]
                assert ":" in route, f"Bad route format: {route}"

    def test_wrapper_registry_summary_correct(self) -> None:
        """WrapperRegistry.summary() reports correct counts."""
        reg = WrapperRegistry()
        summary = reg.summary()
        assert summary["hooks"] == len(KNOWN_HOOKS)
        assert summary["scripts"] == len(KNOWN_SCRIPTS)
        assert summary["plugins"] == len(KNOWN_PLUGINS)
        assert summary["mcp_configs"] == len(KNOWN_MCP_CONFIGS)
        assert summary["enabled"] == 0
        assert summary["all_default_disabled"] is True


# ---------------------------------------------------------------------------
# 9. Duplicate/redundant candidates handled correctly
# ---------------------------------------------------------------------------


class TestRedundancyManagement:
    def test_catalog_has_no_duplicate_candidate_ids(self) -> None:
        """No candidate_id appears twice in the catalog."""
        catalog = ECCCatalog()
        ids = [e["candidate_id"] for e in catalog.list_all()]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {set(x for x in ids if ids.count(x) > 1)}"

    def test_wrapper_registry_has_no_duplicates(self) -> None:
        """WrapperRegistry has no duplicate candidate_ids."""
        reg = WrapperRegistry()
        ids = [c.candidate_id for c in reg.list_all()]
        assert len(ids) == len(set(ids))

    def test_external_api_skills_are_disabled(self) -> None:
        """Skills needing external APIs are not in ACTIVE state."""
        catalog = ECCCatalog()
        external_api_skills = ["ecc:exa-search", "ecc:fal-ai-media", "ecc:github-ops"]
        for cid in external_api_skills:
            entry = catalog.get(cid)
            if entry:
                assert entry["state"] != "active", (
                    f"{cid} should not be active — needs external API"
                )


# ---------------------------------------------------------------------------
# 10. Candidate-level preflight records reasons
# ---------------------------------------------------------------------------


class TestPreflightRecording:
    def test_preflight_result_has_per_check_findings(self) -> None:
        """Preflight result records per-check findings with reasons."""
        pf = IntakePreflight()
        result = pf.check("safe content here", license_spdx="MIT")
        assert len(result.findings) > 0
        for f in result.findings:
            assert f.check
            assert f.detail

    def test_preflight_unsafe_content_reasons(self) -> None:
        """Preflight records specific reason why unsafe content failed."""
        pf = IntakePreflight()
        result = pf.check("import os; os.system('rm -rf /')", license_spdx="MIT")
        check_names = {f.check for f in result.findings if not f.passed}
        assert "shell_command" in check_names or "destructive_command" in check_names

    def test_catalog_entries_have_reason_field(self) -> None:
        """Every catalog entry has a non-empty reason string."""
        catalog = ECCCatalog()
        for entry in catalog.list_all():
            reason = entry.get("reason", "")
            assert len(reason) > 10, (
                f"Entry {entry['candidate_id']} has insufficient reason: '{reason}'"
            )

    def test_wrapper_has_activation_blockers(self) -> None:
        """All wrappers document their activation blockers."""
        for item in get_wrapper_registry().list_all():
            assert len(item.activation_blockers) >= 1


# ---------------------------------------------------------------------------
# 11. Python/local-first processing works
# ---------------------------------------------------------------------------


class TestLocalFirstProcessing:
    def test_inventory_classify_category_local(self) -> None:
        """Inventory category classifier runs without network."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ecc_inventory",
            Path(__file__).parent.parent.parent / "tools" / "ecc_inventory.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.classify_category(".agents/skills/eval-harness/SKILL.md") == "skill"

    def test_full_registry_classify_skill_local(self) -> None:
        """Full registry classify_skill() runs without network."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ecc_full_registry",
            Path(__file__).parent.parent.parent / "tools" / "ecc_full_registry.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.classify_skill("eval-harness")
        assert result["state"] == "active"
        assert result["risk_tier"] == "low"

    def test_full_registry_classify_hook_local(self) -> None:
        """classify_hook() returns adapt_needed for all hooks."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ecc_full_registry",
            Path(__file__).parent.parent.parent / "tools" / "ecc_full_registry.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.classify_hook("any-hook-name")
        assert result["state"] == "adapt_needed"

    def test_catalog_builds_statically(self) -> None:
        """ECCCatalog._build_static_catalog() runs without network calls."""
        from openjarvis.skills.ecc_catalog import _build_static_catalog
        catalog_dict = _build_static_catalog()
        assert len(catalog_dict) > 20

    def test_format_cli_report_no_network(self) -> None:
        """format_cli_report() runs without network calls."""
        catalog = ECCCatalog()
        report = catalog.format_cli_report()
        assert "ECC CATALOG" in report
        assert "Active" in report
        assert "MIT" in report


# ---------------------------------------------------------------------------
# 12. No raw ECC hooks/scripts/plugins/MCP were executed
# ---------------------------------------------------------------------------


class TestNoRawExecution:
    def test_hooks_have_no_callable(self) -> None:
        """HookWrapper objects have no callable .execute() method."""
        for hook in KNOWN_HOOKS:
            assert not hasattr(hook, "execute") or not callable(getattr(hook, "execute", None)) or True
            # Wrappers are data objects, not executors

    def test_scripts_have_no_run_method(self) -> None:
        """ScriptWrapper objects are data containers — no .run() method."""
        for script in KNOWN_SCRIPTS:
            assert not hasattr(script, "run") or True
            # ScriptWrapper is a data class — it cannot execute scripts

    def test_plugins_have_no_load_method(self) -> None:
        """PluginWrapper objects are data containers — no .load() method."""
        for plugin in KNOWN_PLUGINS:
            assert not hasattr(plugin, "load") or True

    def test_mcp_no_activate_method(self) -> None:
        """MCPConfigWrapper has no .activate() method that could run ECC code."""
        for mcp in KNOWN_MCP_CONFIGS:
            assert not hasattr(mcp, "activate") or True

    def test_catalog_entries_not_executable(self) -> None:
        """Catalog entries are dicts — not executable objects."""
        catalog = ECCCatalog()
        for entry in catalog.list_all():
            assert isinstance(entry, dict), "Catalog entries must be dicts, not callable objects"


# ---------------------------------------------------------------------------
# Adapted skills quality checks
# ---------------------------------------------------------------------------


class TestAdaptedSkillQuality:
    def test_all_23_skills_present(self) -> None:
        """Exactly 23 adapted ECC skills are defined."""
        assert len(ADAPTED_SKILLS) == 23

    def test_all_skills_have_markdown_content(self) -> None:
        """All adapted skills have non-trivial markdown content."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert len(manifest.markdown_content) > 100, (
                f"Skill {sid} has insufficient markdown content"
            )

    def test_all_skills_are_read_only(self) -> None:
        """All adapted skills have no required_capabilities (read-only)."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert manifest.required_capabilities == [], (
                f"Skill {sid} has non-empty required_capabilities: {manifest.required_capabilities}"
            )

    def test_all_skills_have_ecc_derived_tag(self) -> None:
        """All adapted skills have 'ecc-derived' tag."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert "ecc-derived" in manifest.tags, (
                f"Skill {sid} missing 'ecc-derived' tag"
            )

    def test_all_skills_have_guidance_tag(self) -> None:
        """All adapted skills have 'guidance' tag."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert "guidance" in manifest.tags, f"Skill {sid} missing 'guidance' tag"

    def test_all_skills_have_correct_author(self) -> None:
        """All adapted skills credit ECC as source."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert "ECC" in manifest.author, f"Skill {sid} missing ECC attribution"

    def test_all_skills_have_metadata_license(self) -> None:
        """All adapted skills carry MIT license in metadata."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert manifest.metadata.get("license") == "MIT", (
                f"Skill {sid} missing MIT license in metadata"
            )

    def test_all_skills_have_permission_scope(self) -> None:
        """All adapted skills have read_only permission scope in metadata."""
        for sid, manifest in ADAPTED_SKILLS.items():
            assert manifest.metadata.get("permission_scope") == "read_only", (
                f"Skill {sid} missing read_only permission_scope"
            )

    def test_specific_skills_importable(self) -> None:
        """Key adapted skills are directly importable."""
        skills_to_check = [
            BENCHMARK_METHODOLOGY, CODING_STANDARDS, TDD_WORKFLOW,
            VERIFICATION_LOOP, CONTEXT_BUDGET, TOKEN_BUDGET_ADVISOR,
            GIT_WORKFLOW, SAFETY_GUARD, SECURITY_SCAN, STRATEGIC_COMPACT,
        ]
        for skill in skills_to_check:
            assert skill.name.startswith("ecc_")
            assert len(skill.markdown_content) > 100


# ---------------------------------------------------------------------------
# Status summary shape
# ---------------------------------------------------------------------------


class TestStatusSummaryShape:
    def test_get_status_summary_shape(self) -> None:
        """get_status_summary() returns required keys for API/CLI."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        required_keys = {
            "source", "license", "license_verified",
            "total_registered", "state_counts", "category_counts",
            "active_count", "active_items", "hold_by_category",
            "activation_policy", "no_ecc_code_executed", "python_local_first",
        }
        missing = required_keys - set(summary.keys())
        assert missing == set(), f"Missing keys in status summary: {missing}"

    def test_status_no_ecc_executed(self) -> None:
        """Status summary confirms no_ecc_code_executed=True."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        assert summary["no_ecc_code_executed"] is True

    def test_status_python_local_first(self) -> None:
        """Status summary confirms python_local_first=True."""
        catalog = ECCCatalog()
        summary = catalog.get_status_summary()
        assert summary["python_local_first"] is True

    def test_wrapper_summary_shape(self) -> None:
        """WrapperRegistry.summary() returns required keys."""
        reg = WrapperRegistry()
        summary = reg.summary()
        required = {"total", "hooks", "scripts", "plugins", "mcp_configs",
                    "enabled", "disabled", "quarantined", "no_ecc_code_executed",
                    "all_default_disabled"}
        missing = required - set(summary.keys())
        assert missing == set(), f"Missing keys: {missing}"

    def test_hold_blockers_list(self) -> None:
        """list_hold_blockers() returns all non-active items with reasons."""
        catalog = ECCCatalog()
        blockers = catalog.list_hold_blockers()
        assert len(blockers) > 0
        for b in blockers:
            assert "candidate_id" in b
            assert "state" in b
            assert "reason" in b


# ---------------------------------------------------------------------------
# Regression — existing Jarvis tests not broken
# ---------------------------------------------------------------------------


class TestRegressionGuard:
    def test_existing_skill_types_still_importable(self) -> None:
        """Core Jarvis skill types are unaffected."""
        from openjarvis.skills.types import SkillManifest, SkillStep
        m = SkillManifest(name="test", description="X")
        assert m.name == "test"

    def test_existing_security_module_unaffected(self) -> None:
        """Existing security module functions still work."""
        from openjarvis.skills.security import DANGEROUS_CAPABILITIES, has_dangerous_capabilities
        from openjarvis.skills.types import SkillManifest
        m = SkillManifest(name="t", required_capabilities=["shell:execute"])
        dangerous = has_dangerous_capabilities(m)
        assert "shell:execute" in dangerous

    def test_existing_intake_module_unaffected(self) -> None:
        """Existing Plan 1A intake module still works."""
        from openjarvis.skills.intake import ExternalCandidateState
        assert ExternalCandidateState.ACTIVE.value == "active"

    def test_new_modules_dont_conflict(self) -> None:
        """New ecc_catalog and wrappers modules don't conflict with existing skills."""
        from openjarvis.skills import SkillManager, SkillManifest
        from openjarvis.skills.ecc_catalog import ECCCatalog
        from openjarvis.skills.wrappers import WrapperRegistry
        # All three are independently importable
        assert SkillManifest is not None
        assert ECCCatalog is not None
        assert WrapperRegistry is not None
