"""Tests for Plan 1 ECC Pre-Keys Correction Sprint.

Validates all correction pass requirements:
  - ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK is zero
  - INSTALLED_DISABLED_WITH_EXACT_BLOCKER is zero
  - Provider consolidation is correct
  - Wrappers work and are gated
  - Hook framework works and is gated
  - Plugin gate works and is gated
  - Agent profiles are defined
  - Active reachability proof
  - 53 → 35 → 37 reconciliation
  - No raw ECC execution
  - All risky items disabled
"""

import json
import os
import pathlib
import pytest
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog():
    from openjarvis.skills.ecc_catalog import ECCCatalog
    return ECCCatalog()


@pytest.fixture(scope="module")
def all_items(catalog):
    return catalog.list_all()


@pytest.fixture(scope="module")
def active_items(all_items):
    return [i for i in all_items if i.get("state") == "active"]


@pytest.fixture(scope="module")
def reachability_report(all_items):
    from openjarvis.skills.ecc_active_reachability import build_reachability_report
    return build_reachability_report(all_items)


# ---------------------------------------------------------------------------
# Scope F: State model cleanup — ZERO vague states
# ---------------------------------------------------------------------------

class TestStateModelCleanup:

    def test_zero_adapt_needed_with_exact_engineering_task(self, all_items):
        """After correction sprint: no items should remain as ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK."""
        adapt_needed = [
            i["candidate_id"] for i in all_items
            if i.get("plan1_state") == "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK"
        ]
        assert adapt_needed == [], (
            f"Expected 0 ADAPT_NEEDED items; got {len(adapt_needed)}: {adapt_needed}"
        )

    def test_zero_installed_disabled_with_exact_blocker(self, all_items):
        """After correction sprint: no items should remain as INSTALLED_DISABLED_WITH_EXACT_BLOCKER."""
        blocked = [
            i["candidate_id"] for i in all_items
            if i.get("plan1_state") == "INSTALLED_DISABLED_WITH_EXACT_BLOCKER"
        ]
        assert blocked == [], (
            f"Expected 0 INSTALLED_DISABLED items; got {len(blocked)}: {blocked}"
        )

    def test_zero_inspect_later(self, all_items):
        """inspect_later state must remain zero."""
        vague = [
            i["candidate_id"] for i in all_items
            if i.get("plan1_state") in ("inspect_later", "INSPECT_LATER")
            or i.get("state") == "inspect_later"
        ]
        assert vague == [], f"Found inspect_later items: {vague}"

    def test_all_items_have_valid_plan1_state(self, all_items):
        """Every item must have a valid precise plan1_state."""
        VALID_STATES = {
            "ACTIVE",
            "READY_BUT_WAITING_FOR_API_KEY",
            "READY_BUT_WAITING_FOR_APPROVAL",
            "READY_BUT_WAITING_FOR_USER_MANUAL_SETUP",
            "COST_BLOCKED_OPTIONAL_LATER",   # Added in Prompt 2
            "NOT_NEEDED_FOR_NOW",             # Added in Prompt 2
            "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK",
            "UNAUTOMATABLE_EVEN_WITH_APPROVAL",
            "REJECTED_WITH_REASON",
            "DUPLICATE_WITH_REASON",
            "QUARANTINED_WITH_REASON",
            "INSTALLED_DISABLED_WITH_EXACT_BLOCKER",
        }
        invalid = [
            (i["candidate_id"], i.get("plan1_state"))
            for i in all_items
            if i.get("plan1_state") not in VALID_STATES
        ]
        assert invalid == [], f"Items with invalid plan1_state: {invalid}"

    def test_state_counts_sum_to_total(self, catalog):
        """State counts must sum to total_registered."""
        summary = catalog.get_plan1_completion_summary()
        total = summary["total_registered"]
        state_sum = sum(summary["plan1_state_counts"].values())
        assert state_sum == total, f"State counts {state_sum} != total {total}"

    def test_final_state_breakdown(self, catalog):
        """Verify final state breakdown after Prompt 2 live validation."""
        summary = catalog.get_plan1_completion_summary()
        states = summary["plan1_state_counts"]
        assert states.get("ACTIVE", 0) == 319, f"Expected 319 ACTIVE (Prompt 3), got {states.get('ACTIVE')}"
        assert states.get("ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK", 0) == 0, "ADAPT_NEEDED must be 0"
        assert states.get("INSTALLED_DISABLED_WITH_EXACT_BLOCKER", 0) == 0, "INSTALLED_DISABLED must be 0"
        assert states.get("UNAUTOMATABLE_EVEN_WITH_APPROVAL", 0) >= 2, "Must have >= 2 UNAUTOMATABLE"
        assert states.get("READY_BUT_WAITING_FOR_APPROVAL", 0) == 0, "Must have 0 APPROVAL-WAITING after Prompt 2"


# ---------------------------------------------------------------------------
# Scope A: Engineering items (28) resolved
# ---------------------------------------------------------------------------

class TestEngineeringItemsResolved:

    def test_browser_qa_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:browser-qa"), None)
        assert item is not None, "browser-qa must be in catalog"
        assert item["plan1_state"] == "ACTIVE", (
            f"browser-qa state after Prompt 2 approval: {item['plan1_state']}"
        )

    def test_terminal_ops_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:terminal-ops"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE"

    def test_video_editing_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:video-editing"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE"

    def test_dmux_workflows_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:dmux-workflows"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE"

    def test_e2e_testing_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:e2e-testing"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE"

    def test_nanoclaw_repl_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:nanoclaw-repl"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE"

    def test_continuous_learning_v2_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:continuous-learning-v2"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"continuous-learning-v2 activated via AIMLAPI in Prompt 2; got {item['plan1_state']}"
        )

    def test_flox_environments_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:flox-environments"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"flox-environments activated after Flox CLI confirmed installed; got {item['plan1_state']}"
        )

    def test_ios_icon_gen_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:ios-icon-gen"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"ios-icon-gen activated after Pillow installed (Prompt 3); got {item['plan1_state']}"
        )

    def test_nutrient_doc_processing_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:nutrient-document-processing"), None)
        assert item is not None
        assert item["plan1_state"] == "COST_BLOCKED_OPTIONAL_LATER", (
            f"nutrient is cost-blocked optional-later; got {item['plan1_state']}"
        )

    def test_windows_desktop_e2e_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:windows-desktop-e2e"), None)
        assert item is not None
        assert item["plan1_state"] == "UNAUTOMATABLE_EVEN_WITH_APPROVAL", (
            f"windows-desktop-e2e should be UNAUTOMATABLE; got {item['plan1_state']}"
        )

    def test_agent_e2e_runner_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:agent:e2e-runner"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"e2e-runner agent activated (registry wired) in Prompt 2; got {item['plan1_state']}"
        )

    def test_agent_docs_researcher_state_correct(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:agent:docs-researcher"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"docs-researcher agent activated in Prompt 2; got {item['plan1_state']}"
        )

    def test_all_hooks_state_correct(self, all_items):
        hooks = [i for i in all_items if i.get("category") == "hook"]
        assert len(hooks) == 10, f"Expected 10 hooks, got {len(hooks)}"
        wrong = [(i["candidate_id"], i["plan1_state"]) for i in hooks if i["plan1_state"] != "ACTIVE"]
        assert wrong == [], f"Hooks not ACTIVE after Prompt 2 registry wiring: {wrong}"

    def test_all_plugins_state_correct(self, all_items):
        plugins = [i for i in all_items if i.get("category") == "plugin"]
        assert len(plugins) == 5, f"Expected 5 plugins, got {len(plugins)}"
        wrong = [(i["candidate_id"], i["plan1_state"]) for i in plugins if i["plan1_state"] != "ACTIVE"]
        assert wrong == [], f"Plugins not ACTIVE after Prompt 2 registry wiring: {wrong}"


# ---------------------------------------------------------------------------
# Scope B: Approval-waiting items (11) verified
# ---------------------------------------------------------------------------

class TestApprovalWaitingItems:

    APPROVAL_AGENT_IDS = [
        "ecc:agent:code-reviewer", "ecc:agent:security-reviewer", "ecc:agent:planner",
        "ecc:agent:architect", "ecc:agent:tdd-guide", "ecc:agent:spec-miner",
        "ecc:agent:refactor-cleaner", "ecc:agent:doc-updater", "ecc:agent:build-error-resolver",
        "ecc:agent:reviewer", "ecc:agent:explorer",
    ]

    def test_all_11_approval_agents_present(self, all_items):
        for aid in self.APPROVAL_AGENT_IDS:
            item = next((i for i in all_items if i.get("candidate_id") == aid), None)
            assert item is not None, f"Approval agent {aid} missing from catalog"

    def test_all_11_approval_agents_in_correct_state(self, all_items):
        for aid in self.APPROVAL_AGENT_IDS:
            item = next((i for i in all_items if i.get("candidate_id") == aid), None)
            assert item["plan1_state"] == "ACTIVE", (
                f"{aid} should be ACTIVE after Prompt 2 registry wiring, got {item['plan1_state']}"
            )

    def test_approval_agents_have_profiles(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ALL_AGENT_PROFILES
        for aid in self.APPROVAL_AGENT_IDS:
            assert aid in ALL_AGENT_PROFILES, f"Agent profile missing for {aid}"

    def test_approval_agents_not_enabled(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ALL_AGENT_PROFILES
        for aid in self.APPROVAL_AGENT_IDS:
            profile = ALL_AGENT_PROFILES[aid]
            assert not profile.enabled, f"{aid} should not be enabled without approval"
            assert not profile.reviewer_approved, f"{aid} should not have reviewer_approved=True"


# ---------------------------------------------------------------------------
# Scope C: Installed-disabled blockers (3) resolved
# ---------------------------------------------------------------------------

class TestInstalledDisabledBlockersResolved:

    def test_eval_harness_is_unautomatable(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:eval-harness"), None)
        assert item is not None
        assert item["plan1_state"] == "UNAUTOMATABLE_EVEN_WITH_APPROVAL", (
            f"eval-harness should be UNAUTOMATABLE; got {item['plan1_state']}"
        )
        assert item["reviewer_approved"] is False

    def test_database_migration_is_active_gated(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:cmd:database-migration"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"database-migration is ACTIVE (registry wired) after Prompt 2; got {item['plan1_state']}"
        )
        # reviewer_approved=False: activation logged, but destructive execution remains gated
        assert item["reviewer_approved"] is False

    def test_mcp_servers_is_active_gated(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:mcp:mcp-servers"), None)
        assert item is not None
        assert item["plan1_state"] == "ACTIVE", (
            f"mcp-servers is ACTIVE (security gate wired) after Prompt 2; got {item['plan1_state']}"
        )
        # reviewer_approved=False: per-server activation still requires explicit approval
        assert item["reviewer_approved"] is False

    def test_eval_harness_has_reason_documenting_policy(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:eval-harness"), None)
        reason = item.get("reason", "")
        assert "UNAUTOMATABLE_EVEN_WITH_APPROVAL" in reason
        assert "permanently" in reason.lower() or "policy" in reason.lower()


# ---------------------------------------------------------------------------
# Execution wrappers
# ---------------------------------------------------------------------------

class TestExecutionWrappers:

    def test_wrapper_registry_complete(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import WRAPPER_REGISTRY
        expected_ids = {
            "ecc:browser-qa", "ecc:terminal-ops", "ecc:video-editing",
            "ecc:nanoclaw-repl", "ecc:dmux-workflows", "ecc:e2e-testing",
            "ecc:ios-icon-gen", "ecc:flox-environments", "ecc:nutrient-document-processing",
            "ecc:continuous-learning-v2", "ecc:windows-desktop-e2e",
        }
        assert set(WRAPPER_REGISTRY.keys()) == expected_ids

    def test_browser_qa_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import BrowserQAWrapper
        wrapper = BrowserQAWrapper()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_APPROVAL"

    def test_browser_qa_blocked_without_approval(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import BrowserQAWrapper, WrapperGateError
        wrapper = BrowserQAWrapper(reviewer_approved=False)
        with pytest.raises(WrapperGateError):
            wrapper.run_tests(dry_run=False)

    def test_terminal_sandbox_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import TerminalSandbox
        wrapper = TerminalSandbox()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_APPROVAL"

    def test_terminal_sandbox_allowlist_enforced(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import TerminalSandbox, WrapperGateError
        wrapper = TerminalSandbox(reviewer_approved=True)
        result = wrapper.run(command="rm -rf /tmp/test", dry_run=True)
        assert result["status"] == "BLOCKED", "rm command should be blocked by allowlist"

    def test_terminal_sandbox_allowed_command_dry_run(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import TerminalSandbox
        wrapper = TerminalSandbox(reviewer_approved=True)
        result = wrapper.run(command="ls", dry_run=True)
        assert result["status"] == "DRY_RUN"

    def test_video_edit_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import VideoEditWrapper
        wrapper = VideoEditWrapper()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_APPROVAL"

    def test_repl_sandbox_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import ReplSandbox
        wrapper = ReplSandbox()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert "python" in result["allowed_languages"]

    def test_repl_sandbox_disallowed_language(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import ReplSandbox
        wrapper = ReplSandbox(reviewer_approved=True)
        result = wrapper.execute("eval(input())", language="ruby", dry_run=True)
        assert result["status"] == "BLOCKED"

    def test_dmux_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import DmuxSessionManager
        wrapper = DmuxSessionManager()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_e2e_testing_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import E2ETestRunner
        wrapper = E2ETestRunner()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_ios_icon_gen_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import IosIconGenWrapper
        wrapper = IosIconGenWrapper()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_USER_MANUAL_SETUP"
        assert 1024 in result["icon_sizes"]

    def test_flox_env_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import FloxEnvWrapper
        wrapper = FloxEnvWrapper()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_USER_MANUAL_SETUP"

    def test_nutrient_doc_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import NutrientDocWrapper
        wrapper = NutrientDocWrapper()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_API_KEY"
        assert "NUTRIENT_API_KEY" in result["required_key"]

    def test_nutrient_doc_blocked_without_key(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import NutrientDocWrapper
        env_backup = os.environ.pop("NUTRIENT_API_KEY", None)
        try:
            wrapper = NutrientDocWrapper(reviewer_approved=True, dry_run=True)
            result = wrapper.process_document("test.pdf")
            assert result["status"] == "BLOCKED"
            assert "NUTRIENT_API_KEY" in result["reason"]
        finally:
            if env_backup:
                os.environ["NUTRIENT_API_KEY"] = env_backup

    def test_continuous_learning_mocked(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import ContinuousLearningV2Wrapper
        wrapper = ContinuousLearningV2Wrapper()
        result = wrapper.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_API_KEY"

    def test_continuous_learning_blocked_without_key(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import ContinuousLearningV2Wrapper
        for key in ("AIMLAPI_API_KEY", "OPENROUTER_API_KEY"):
            os.environ.pop(key, None)
        try:
            wrapper = ContinuousLearningV2Wrapper(reviewer_approved=True, dry_run=True)
            result = wrapper.run_training_cycle()
            assert result["status"] == "BLOCKED"
        finally:
            pass

    def test_windows_desktop_e2e_is_unautomatable(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import WindowsDesktopE2EWrapper
        wrapper = WindowsDesktopE2EWrapper()
        result = wrapper.mock_invocation()
        assert result["state"] == "UNAUTOMATABLE_EVEN_WITH_APPROVAL"

    def test_wrappers_disable_rollback(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import BrowserQAWrapper
        wrapper = BrowserQAWrapper(reviewer_approved=True)
        wrapper.disable()
        assert not wrapper.reviewer_approved, "disable() should clear reviewer_approved"


# ---------------------------------------------------------------------------
# Hook framework tests
# ---------------------------------------------------------------------------

class TestHookFramework:

    def test_hook_framework_registers_all_hooks(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import get_hook_framework, ECC_HOOK_EVENT_MAP
        fw = get_hook_framework()
        for hook_id in ECC_HOOK_EVENT_MAP:
            assert hook_id in fw._hooks, f"Hook {hook_id} not registered"

    def test_all_hooks_disabled_by_default(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import get_hook_framework
        fw = get_hook_framework()
        for hook_id, reg in fw._hooks.items():
            assert not reg.enabled, f"Hook {hook_id} should be disabled by default"
            assert not reg.reviewer_approved, f"Hook {hook_id} should not be approved by default"

    def test_hook_fire_returns_disabled_when_not_enabled(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import get_hook_framework
        fw = get_hook_framework()
        result = fw.fire("ecc:hook:pre-commit", context={"files": ["test.py"]})
        assert result["status"] == "DISABLED"

    def test_hook_cannot_enable_without_framework_approval(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import JarvisHookFramework, HookGateError
        fw = JarvisHookFramework()
        fw.register("ecc:hook:on-error")
        fw.set_approved("ecc:hook:on-error", True)  # framework not approved
        # Should fail because framework_approved=False
        reg = fw._hooks["ecc:hook:on-error"]
        assert not reg.reviewer_approved, "Per-hook approval should fail if framework not approved"

    def test_hook_mock_invocation(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import get_hook_framework
        fw = get_hook_framework()
        result = fw.mock_invocation("ecc:hook:pre-commit")
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_APPROVAL"

    def test_hook_disable_all_rollback(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import JarvisHookFramework
        fw = JarvisHookFramework()
        fw.register("ecc:hook:post-task")
        fw.set_framework_approved(True)
        fw.disable_all()
        assert not fw._framework_approved
        for reg in fw._hooks.values():
            assert not reg.enabled

    def test_hook_framework_status_has_expected_keys(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import get_hook_framework
        fw = get_hook_framework()
        status = fw.get_status()
        assert "framework_approved" in status
        assert "registered_hooks" in status
        assert "enabled_hooks" in status
        assert status["registered_hooks"] == 10
        assert status["enabled_hooks"] == 0


# ---------------------------------------------------------------------------
# Plugin gate tests
# ---------------------------------------------------------------------------

class TestPluginGate:

    def test_plugin_gate_registers_all_plugins(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import get_plugin_gate, ECC_KNOWN_PLUGINS
        gate = get_plugin_gate()
        for plugin_id in ECC_KNOWN_PLUGINS:
            assert plugin_id in gate._plugins, f"Plugin {plugin_id} not registered"

    def test_all_plugins_disabled_by_default(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import get_plugin_gate
        gate = get_plugin_gate()
        for pid, reg in gate._plugins.items():
            assert not reg.enabled, f"Plugin {pid} should be disabled by default"
            assert not reg.reviewer_approved, f"Plugin {pid} should not be approved by default"

    def test_plugin_load_blocked_when_disabled(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import get_plugin_gate
        gate = get_plugin_gate()
        result = gate.load("ecc:plugin:index")
        assert result["status"] == "DISABLED"

    def test_plugin_cannot_enable_without_isolation_test(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import JarvisPluginGate, PluginGateError
        gate = JarvisPluginGate()
        gate.register("ecc:plugin:lib")
        gate.set_gate_approved(True)
        gate.set_approved("ecc:plugin:lib", True)
        reg = gate._plugins["ecc:plugin:lib"]
        with pytest.raises(PluginGateError, match="isolation"):
            reg.enable()

    def test_plugin_mock_invocation(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import get_plugin_gate
        gate = get_plugin_gate()
        result = gate.mock_invocation("ecc:plugin:index")
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["state"] == "READY_BUT_WAITING_FOR_APPROVAL"

    def test_plugin_quarantine_path(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import JarvisPluginGate
        gate = JarvisPluginGate()
        gate.register("ecc:plugin:marketplace")
        gate.quarantine("ecc:plugin:marketplace")
        reg = gate._plugins["ecc:plugin:marketplace"]
        assert not reg.enabled
        assert not reg.reviewer_approved

    def test_plugin_disable_all_rollback(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import JarvisPluginGate
        gate = JarvisPluginGate()
        for pid in ["ecc:plugin:index", "ecc:plugin:lib"]:
            gate.register(pid)
        gate.set_gate_approved(True)
        gate.disable_all()
        assert not gate._gate_approved


# ---------------------------------------------------------------------------
# Agent profiles tests
# ---------------------------------------------------------------------------

class TestAgentProfiles:

    def test_all_agent_profiles_defined(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ALL_AGENT_PROFILES
        expected_ids = [
            "ecc:agent:e2e-runner", "ecc:agent:docs-researcher",
            "ecc:agent:code-reviewer", "ecc:agent:security-reviewer",
            "ecc:agent:planner", "ecc:agent:architect", "ecc:agent:tdd-guide",
            "ecc:agent:spec-miner", "ecc:agent:refactor-cleaner", "ecc:agent:doc-updater",
            "ecc:agent:build-error-resolver", "ecc:agent:reviewer", "ecc:agent:explorer",
        ]
        for aid in expected_ids:
            assert aid in ALL_AGENT_PROFILES, f"Agent profile missing: {aid}"

    def test_all_agents_disabled_by_default(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ALL_AGENT_PROFILES
        for aid, profile in ALL_AGENT_PROFILES.items():
            assert not profile.enabled, f"{aid} should be disabled by default"
            assert not profile.reviewer_approved, f"{aid} should not have reviewer_approved=True"

    def test_e2e_runner_agent_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_E2E_RUNNER_AGENT
        result = ECC_E2E_RUNNER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["plan1_state"] == "READY_BUT_WAITING_FOR_APPROVAL"

    def test_docs_researcher_agent_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_DOCS_RESEARCHER_AGENT
        result = ECC_DOCS_RESEARCHER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_code_reviewer_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_CODE_REVIEWER_AGENT
        result = ECC_CODE_REVIEWER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_security_reviewer_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_SECURITY_REVIEWER_AGENT
        result = ECC_SECURITY_REVIEWER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_planner_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_PLANNER_AGENT
        result = ECC_PLANNER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_architect_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_ARCHITECT_AGENT
        result = ECC_ARCHITECT_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_tdd_guide_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_TDD_GUIDE_AGENT
        result = ECC_TDD_GUIDE_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_spec_miner_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_SPEC_MINER_AGENT
        result = ECC_SPEC_MINER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_refactor_cleaner_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_REFACTOR_CLEANER_AGENT
        result = ECC_REFACTOR_CLEANER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_doc_updater_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_DOC_UPDATER_AGENT
        result = ECC_DOC_UPDATER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_build_error_resolver_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_BUILD_ERROR_RESOLVER_AGENT
        result = ECC_BUILD_ERROR_RESOLVER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_reviewer_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_REVIEWER_AGENT
        result = ECC_REVIEWER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_explorer_mocked(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_EXPLORER_AGENT
        result = ECC_EXPLORER_AGENT.mock_invocation()
        assert result["result"] == "MOCKED_SUCCESS"

    def test_agent_enable_blocked_without_approval(self):
        from openjarvis.skills.sources.ecc.agents.ecc_agent_profiles import ECC_PLANNER_AGENT
        with pytest.raises(RuntimeError):
            ECC_PLANNER_AGENT.enable()


# ---------------------------------------------------------------------------
# Provider consolidation tests
# ---------------------------------------------------------------------------

class TestProviderConsolidation:

    def test_consolidation_table_not_empty(self):
        from openjarvis.skills.ecc_provider_consolidation import PROVIDER_CONSOLIDATION_TABLE
        assert len(PROVIDER_CONSOLIDATION_TABLE) >= 35

    def test_aimlapi_consolidatable_skills_identified(self):
        from openjarvis.skills.ecc_provider_consolidation import AIMLAPI_CONSOLIDATABLE
        expected_consolidatable = [
            "ecc-tools-cost-audit", "article-writing", "content-engine",
            "brand-voice", "investor-materials", "continuous-learning-v2", "fal-ai-media",
        ]
        for skill_id in expected_consolidatable:
            assert skill_id in AIMLAPI_CONSOLIDATABLE, f"{skill_id} should be AIMLAPI-consolidatable"

    def test_native_service_connectors_not_consolidated(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        native_skills = [
            "exa-search", "github-ops", "jira-integration", "stripe-integration",
            "messages-ops", "email-ops", "videodb", "knowledge-ops",
        ]
        for skill_id in native_skills:
            entry = CONSOLIDATION_BY_ID.get(skill_id)
            assert entry is not None, f"{skill_id} not in consolidation table"
            assert entry["native_provider_required"] is True, f"{skill_id} should require native provider"
            assert entry["can_use_aimlapi"] is False, f"{skill_id} should not be AIMLAPI-consolidatable"

    def test_ecc_tools_cost_audit_uses_gateway(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        entry = CONSOLIDATION_BY_ID["ecc-tools-cost-audit"]
        assert entry["can_use_aimlapi"] is True
        assert "AIMLAPI_API_KEY" in entry["final_required_env_keys"]

    def test_article_writing_uses_gateway(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        entry = CONSOLIDATION_BY_ID["article-writing"]
        assert entry["can_use_aimlapi"] is True
        assert "AIMLAPI_API_KEY" in entry["final_required_env_keys"]

    def test_content_engine_uses_gateway(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        entry = CONSOLIDATION_BY_ID["content-engine"]
        assert entry["can_use_aimlapi"] is True

    def test_brand_voice_uses_gateway(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        entry = CONSOLIDATION_BY_ID["brand-voice"]
        assert entry["can_use_aimlapi"] is True

    def test_investor_materials_uses_gateway(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        entry = CONSOLIDATION_BY_ID["investor-materials"]
        assert entry["can_use_aimlapi"] is True

    def test_fal_ai_uses_aimlapi(self):
        from openjarvis.skills.ecc_provider_consolidation import CONSOLIDATION_BY_ID
        entry = CONSOLIDATION_BY_ID["fal-ai-media"]
        assert entry["can_use_aimlapi"] is True

    def test_minimal_shopping_list_has_gateway_section(self):
        from openjarvis.skills.ecc_provider_consolidation import MINIMAL_PROVIDER_SHOPPING_LIST
        assert "A_gateway_keys" in MINIMAL_PROVIDER_SHOPPING_LIST
        gw = MINIMAL_PROVIDER_SHOPPING_LIST["A_gateway_keys"]
        assert "AIMLAPI_API_KEY" in gw["keys"]

    def test_minimal_shopping_list_excludes_individual_model_keys(self):
        from openjarvis.skills.ecc_provider_consolidation import PROVIDER_CONSOLIDATION_TABLE
        for entry in PROVIDER_CONSOLIDATION_TABLE:
            if entry["can_use_aimlapi"]:
                final_keys = entry["final_required_env_keys"]
                assert "ANTHROPIC_API_KEY" not in final_keys, (
                    f"{entry['skill_id']} final keys should not include ANTHROPIC_API_KEY "
                    f"when AIMLAPI can substitute"
                )
                assert "OPENAI_API_KEY" not in final_keys, (
                    f"{entry['skill_id']} final keys should not include OPENAI_API_KEY "
                    f"when AIMLAPI can substitute"
                )

    def test_every_entry_has_required_fields(self):
        from openjarvis.skills.ecc_provider_consolidation import PROVIDER_CONSOLIDATION_TABLE
        required_fields = [
            "skill_id", "provider_category", "can_use_aimlapi", "can_use_openrouter",
            "native_provider_required", "final_required_env_keys", "final_recommended_provider",
            "mocked_test_command", "live_test_command", "activation_route", "rollback_path",
        ]
        for entry in PROVIDER_CONSOLIDATION_TABLE:
            for field in required_fields:
                assert field in entry, f"Entry {entry.get('skill_id')} missing field '{field}'"

    def test_native_provider_has_reason_when_required(self):
        from openjarvis.skills.ecc_provider_consolidation import PROVIDER_CONSOLIDATION_TABLE
        for entry in PROVIDER_CONSOLIDATION_TABLE:
            if entry["native_provider_required"]:
                assert entry.get("native_provider_reason"), (
                    f"{entry['skill_id']} requires native provider but has no reason"
                )

    def test_json_artifact_exists(self):
        path = pathlib.Path("docs/certification/plan1_ecc_minimal_provider_keys.json")
        assert path.exists(), "Provider keys JSON artifact must be generated"

    def test_json_artifact_valid(self):
        path = pathlib.Path("docs/certification/plan1_ecc_minimal_provider_keys.json")
        if path.exists():
            data = json.loads(path.read_text())
            assert "per_skill_table" in data
            assert "minimal_shopping_list" in data
            assert len(data["per_skill_table"]) >= 35

    def test_md_artifact_exists(self):
        path = pathlib.Path("docs/certification/PLAN1_ECC_MINIMAL_PROVIDER_KEYS.md")
        assert path.exists(), "Provider keys MD artifact must be generated"

    def test_md_artifact_mentions_aimlapi(self):
        path = pathlib.Path("docs/certification/PLAN1_ECC_MINIMAL_PROVIDER_KEYS.md")
        if path.exists():
            content = path.read_text()
            assert "AIMLAPI_API_KEY" in content
            assert "AIMLAPI" in content

    def test_md_artifact_shows_eliminated_keys(self):
        path = pathlib.Path("docs/certification/PLAN1_ECC_MINIMAL_PROVIDER_KEYS.md")
        if path.exists():
            content = path.read_text()
            assert "ANTHROPIC_API_KEY" in content, "Should mention eliminated Anthropic key"


# ---------------------------------------------------------------------------
# 53 → 35 → 37 reconciliation tests
# ---------------------------------------------------------------------------

class TestApiKeyDeltaReconciliation:

    def test_reconciliation_report_exists(self):
        from openjarvis.skills.ecc_api_key_reconciliation import get_reconciliation_report
        report = get_reconciliation_report()
        assert "source_of_truth" in report
        assert "authoritative_counts" in report

    def test_correction_sprint_count_is_37(self):
        from openjarvis.skills.ecc_api_key_reconciliation import AUTHORITATIVE_COUNTS
        assert AUTHORITATIVE_COUNTS["correction_sprint"]["count"] == 37
        assert AUTHORITATIVE_COUNTS["correction_sprint"]["is_authoritative"] is True

    def test_completion_sprint_count_is_35(self):
        from openjarvis.skills.ecc_api_key_reconciliation import AUTHORITATIVE_COUNTS
        assert AUTHORITATIVE_COUNTS["completion_sprint"]["count"] == 35
        assert AUTHORITATIVE_COUNTS["completion_sprint"]["is_authoritative"] is True

    def test_53_was_not_authoritative(self):
        from openjarvis.skills.ecc_api_key_reconciliation import AUTHORITATIVE_COUNTS
        assert AUTHORITATIVE_COUNTS["pre_sprint_approximation"]["is_authoritative"] is False

    def test_correction_sprint_additions_documented(self):
        from openjarvis.skills.ecc_api_key_reconciliation import CORRECTION_SPRINT_ADDITIONS
        addition_ids = [a["skill_id"] for a in CORRECTION_SPRINT_ADDITIONS]
        assert "ecc:nutrient-document-processing" in addition_ids
        assert "ecc:continuous-learning-v2" in addition_ids

    def test_actual_catalog_api_key_count_after_prompt3(self, all_items):
        api_key_items = [i for i in all_items if i.get("plan1_state") == "READY_BUT_WAITING_FOR_API_KEY"]
        assert len(api_key_items) == 0, (
            f"After Prompt 3: expected 0 API-key skills remaining (GitHub refreshed, all activated), got {len(api_key_items)}"
        )


# ---------------------------------------------------------------------------
# Scope E: Active reachability proof
# ---------------------------------------------------------------------------

class TestActiveReachability:

    def test_active_count_is_319(self, reachability_report):
        assert reachability_report["total_active"] == 319, (
            f"After Prompt 3: expected 319 ACTIVE, got {reachability_report['total_active']}"
        )

    def test_all_active_have_invocation_route(self, reachability_report):
        assert reachability_report["all_have_invocation_route"] is True
        items_without = [
            i["candidate_id"] for i in reachability_report["per_item"]
            if not i.get("invocation_route")
        ]
        assert items_without == [], f"Items missing invocation route: {items_without}"

    def test_all_active_have_permission_scope(self, reachability_report):
        assert reachability_report["all_have_permission_scope"] is True

    def test_all_active_have_rollback_path(self, reachability_report):
        assert reachability_report["all_have_rollback_path"] is True

    def test_executable_count_is_33(self, reachability_report):
        assert reachability_report["executable_count"] == 33, (
            f"Expected 33 executable active items, got {reachability_report['executable_count']}"
        )

    def test_guidance_count_is_286(self, reachability_report):
        assert reachability_report["guidance_only_count"] == 286, (
            f"Expected 286 guidance-only active items (319-33), got {reachability_report['guidance_only_count']}"
        )

    def test_guidance_items_labeled_as_guidance(self, reachability_report):
        """Guidance items must be explicitly labeled — not falsely treated as executable."""
        guidance_items = [
            i for i in reachability_report["per_item"]
            if i["item_type"] == "guidance_only"
        ]
        assert len(guidance_items) == 286
        for item in guidance_items:
            assert item["invocation_route"].startswith("GET /v1/intake/skill/"), (
                f"Guidance item {item['candidate_id']} should have catalog API route"
            )

    def test_executable_items_have_ui_routes(self, reachability_report):
        executable_items = [
            i for i in reachability_report["per_item"]
            if i["item_type"] == "executable"
        ]
        for item in executable_items:
            assert item["has_ui_route"], (
                f"Executable item {item['candidate_id']} missing ui_route"
            )

    def test_reachability_proof_string_present(self, reachability_report):
        proof = reachability_report.get("reachability_proof", "")
        assert "319" in proof
        assert "guidance" in proof.lower() or "catalog" in proof.lower()


# ---------------------------------------------------------------------------
# Safety: no raw ECC execution
# ---------------------------------------------------------------------------

class TestNoRawEccExecution:

    def test_wrappers_require_approval_before_execution(self):
        from openjarvis.skills.sources.ecc.wrappers.execution_wrappers import (
            BrowserQAWrapper, VideoEditWrapper, ReplSandbox, TerminalSandbox,
            WrapperGateError
        )
        wrappers = [
            (BrowserQAWrapper(), lambda w: w.run_tests(dry_run=False)),
            (VideoEditWrapper(), lambda w: w.process_video("in.mp4", "out.mp4", dry_run=False)),
            (ReplSandbox(), lambda w: w.execute("print('hi')", dry_run=False)),
        ]
        for wrapper, fn in wrappers:
            with pytest.raises(WrapperGateError):
                fn(wrapper)

    def test_hooks_require_approval_to_fire(self):
        from openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework import JarvisHookFramework, HookGateError
        fw = JarvisHookFramework()
        fw.register("ecc:hook:pre-commit")
        # Force enable without approval (bypass check for test)
        fw._hooks["ecc:hook:pre-commit"].enabled = True
        fw._hooks["ecc:hook:pre-commit"].reviewer_approved = False
        with pytest.raises(HookGateError):
            fw.fire("ecc:hook:pre-commit")

    def test_plugins_require_approval_to_load(self):
        from openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate import JarvisPluginGate, PluginGateError
        gate = JarvisPluginGate()
        gate.register("ecc:plugin:lib")
        # Force enable without approval
        gate._plugins["ecc:plugin:lib"].enabled = True
        gate._plugins["ecc:plugin:lib"].reviewer_approved = False
        with pytest.raises(PluginGateError):
            gate.load("ecc:plugin:lib")

    def test_eval_harness_not_executable(self, all_items):
        item = next((i for i in all_items if i.get("candidate_id") == "ecc:eval-harness"), None)
        assert item is not None
        assert item.get("ui_route") is None, "eval-harness must not have a ui_route"
        assert item.get("reviewer_approved") is False

    def test_no_vague_states_remain(self, all_items):
        VAGUE_STATES = {"inspect_later", "adapt_needed", "ADAPT_NEEDED", "INSPECT_LATER"}
        vague = [
            i["candidate_id"] for i in all_items
            if i.get("plan1_state") in VAGUE_STATES or i.get("state") in VAGUE_STATES
        ]
        assert vague == [], f"Items with vague states: {vague}"
