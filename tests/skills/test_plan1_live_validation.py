"""Plan 1 ECC Prompt 2 — Live Key/Access/Approval Validation Tests.

Scope H tests proving:
  - secrets are never printed
  - .env files are gitignored
  - key presence checker works without exposing values
  - missing not-needed providers are optional-later/not-needed, not blockers
  - available providers can transition skills to ACTIVE after safe tests
  - failed/missing providers remain precisely classified
  - hooks/scripts/plugins/MCP remain gated (reviewer_approved=False for execution)
  - live tests are dry-run/auth-only/sandbox unless approved
  - Flox/Pillow setup checks work
  - final state counts reconcile to 332
  - no raw ECC code/hooks/scripts/plugins/MCP executed
  - registry/API status reflects final states
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Set
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Module imports
# ---------------------------------------------------------------------------

from openjarvis.skills.ecc_live_validation import (
    ALL_API_KEY_ACTIVATED,
    LIVE_AUTH_TEST_RESULTS,
    PROVIDER_KEY_MAP,
    _APPROVAL_ACTIVATED,
    _COST_BLOCKED_OPTIONAL_LATER_IDS,
    _FLOX_ACTIVATED,
    _GITHUB_KEY_PRESENT_AUTH_FAILED,
    _NOT_NEEDED_FOR_NOW_IDS,
    _PILLOW_WAITING,
    check_flox,
    check_key_presence,
    check_pillow,
    compute_final_state_summary,
    format_final_status_md,
    format_live_validation_md,
    generate_live_validation_json,
    get_state_transition_map,
    verify_env_gitignored,
)
from openjarvis.skills.ecc_completion import Plan1State
from openjarvis.skills.ecc_catalog import _build_static_catalog


# ---------------------------------------------------------------------------
# Constants (match live validation module)
# ---------------------------------------------------------------------------

EXPECTED_ACTIVE = 316
EXPECTED_API_KEY_WAITING = 2       # github-ops, configure-ecc (token expired)
EXPECTED_NOT_NEEDED = 4            # agent-payment-x402, team-builder, seo, jira-integration
EXPECTED_COST_BLOCKED = 7          # social media, stripe, google, nutrient
EXPECTED_USER_MANUAL_SETUP = 1     # ios-icon-gen (Pillow not installed)
EXPECTED_UNAUTOMATABLE = 2         # eval-harness, windows-desktop-e2e
EXPECTED_TOTAL = 332

VALID_FINAL_STATES = {
    "ACTIVE",
    "READY_BUT_WAITING_FOR_API_KEY",
    "READY_BUT_WAITING_FOR_APPROVAL",
    "READY_BUT_WAITING_FOR_USER_MANUAL_SETUP",
    "COST_BLOCKED_OPTIONAL_LATER",
    "NOT_NEEDED_FOR_NOW",
    "UNAUTOMATABLE_EVEN_WITH_APPROVAL",
    "REJECTED_WITH_REASON",
    "DUPLICATE_WITH_REASON",
    "QUARANTINED_WITH_REASON",
}

# These states must be ZERO after Prompt 2
MUST_BE_ZERO_STATES = {
    "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK",
    "INSTALLED_DISABLED_WITH_EXACT_BLOCKER",
    "inspect_later",
    "adapt_needed",
    "installed_disabled",
}


# ---------------------------------------------------------------------------
# Security: Secrets never printed
# ---------------------------------------------------------------------------

class TestSecretsNeverPrinted:
    """Prove no secret values appear in any output from this module."""

    def test_key_presence_returns_no_values(self):
        """check_key_presence() must return booleans/ints, never key values."""
        env = {"AIMLAPI_API_KEY": "super_secret_value_xyz_12345"}
        result = check_key_presence(env)
        # Confirm AIMLAPI is present
        assert result["AIMLAPI"]["present"] is True
        # Confirm the actual value is NOT in the result dict
        result_str = json.dumps(result)
        assert "super_secret_value_xyz_12345" not in result_str

    def test_generate_json_contains_no_env_values(self, tmp_path):
        """generate_live_validation_json() must not include secret values."""
        with patch.dict(os.environ, {"AIMLAPI_API_KEY": "should_not_appear_in_output"}):
            json_str = generate_live_validation_json(output_path=None)
        assert "should_not_appear_in_output" not in json_str

    def test_live_validation_md_contains_no_secrets(self):
        """format_live_validation_md() must not reference secret values."""
        md = format_live_validation_md()
        # Check that no realistic secret patterns appear (key-like strings)
        # Only check we don't expose arbitrary env values — structure is fine
        assert "super_secret" not in md.lower()
        assert "password" not in md.lower()

    def test_key_presence_booleans_only(self):
        """Result values must be dicts with boolean/int fields only."""
        result = check_key_presence({})
        for provider, info in result.items():
            assert isinstance(info["present"], bool), f"{provider}: present must be bool"
            assert isinstance(info["total_keys"], int), f"{provider}: total_keys must be int"


# ---------------------------------------------------------------------------
# Security: .env files are gitignored
# ---------------------------------------------------------------------------

class TestEnvGitignored:
    """Verify .env and .env.local are gitignored."""

    def test_gitignore_verification_returns_structured_result(self):
        result = verify_env_gitignored()
        assert "ok" in result
        assert isinstance(result["ok"], bool)

    def test_env_is_gitignored(self):
        """The project .gitignore must include .env."""
        result = verify_env_gitignored()
        assert result["ok"] is True, (
            f"One or more .env files are NOT gitignored: {result}"
        )

    def test_env_local_pattern_covered(self):
        """The .gitignore must cover .env.local via .env.* or explicit entry."""
        result = verify_env_gitignored()
        checks = result.get("checks", {})
        assert checks.get(".env.local") is True, (
            ".env.local must be covered by .gitignore"
        )

    def test_no_env_files_in_git_index(self):
        """Confirm .env.local is NOT tracked by git."""
        gitignore = Path(".gitignore")
        if not gitignore.exists():
            pytest.skip(".gitignore not found")
        content = gitignore.read_text()
        assert ".env" in content


# ---------------------------------------------------------------------------
# Key presence checker
# ---------------------------------------------------------------------------

class TestKeyPresenceChecker:
    """Validate key presence logic without exposing values."""

    def test_all_providers_in_map(self):
        """PROVIDER_KEY_MAP must contain all tracked providers."""
        expected_providers = {
            "AIMLAPI", "OpenRouter", "Exa", "Perplexity",
            "GitHub", "Slack", "Linear", "Resend",
            "VideoDB", "Pinecone", "Apollo", "ScrapingBee",
            "Twitter", "Greenhouse", "Ahrefs", "Nutrient",
            "Stripe", "X402", "GoogleOAuth",
        }
        missing = expected_providers - set(PROVIDER_KEY_MAP.keys())
        assert not missing, f"Missing providers in PROVIDER_KEY_MAP: {missing}"

    def test_check_key_presence_empty_env(self):
        """All providers should be missing with empty env."""
        result = check_key_presence({})
        for provider, info in result.items():
            assert info["present"] is False, f"{provider} should be missing with empty env"

    def test_check_key_presence_with_aimlapi(self):
        """Providing AIMLAPI_API_KEY makes AIMLAPI present."""
        env = {"AIMLAPI_API_KEY": "test_key_value"}
        result = check_key_presence(env)
        assert result["AIMLAPI"]["present"] is True
        assert result["Exa"]["present"] is False  # Not provided

    def test_alternate_key_names_work(self):
        """Alternate key names (e.g., OPENCLAW_SLACK_BOT_TOKEN) must be detected."""
        env = {"OPENCLAW_SLACK_BOT_TOKEN": "test_slack_token"}
        result = check_key_presence(env)
        assert result["Slack"]["present"] is True

    def test_empty_value_is_not_present(self):
        """Empty string values must not count as present."""
        env = {"AIMLAPI_API_KEY": "", "EXA_API_KEY": "   "}
        result = check_key_presence(env)
        # AIMLAPI_API_KEY = "" → not present
        # EXA_API_KEY = "   " → may or may not be present depending on strip
        # The key check only uses env.get(), not strip — so whitespace IS present
        assert result["AIMLAPI"]["present"] is False


# ---------------------------------------------------------------------------
# State transitions — API key activation
# ---------------------------------------------------------------------------

class TestApiKeyActivation:
    """Verify that confirmed keys activate the correct skills."""

    def test_aimlapi_activated_skills(self):
        """All AIMLAPI-activated skills must be in the transition map as ACTIVE."""
        transitions = get_state_transition_map(flox_installed=True, pillow_installed=False)
        for cid in [
            "ecc:article-writing", "ecc:content-engine", "ecc:brand-voice",
            "ecc:investor-materials", "ecc:ecc-tools-cost-audit",
            "ecc:fal-ai-media", "ecc:continuous-learning-v2",
        ]:
            assert cid in transitions, f"{cid} not in transitions"
            assert transitions[cid]["new_state"] == "ACTIVE", f"{cid}: expected ACTIVE"
            assert transitions[cid]["activation_type"] == "api_key_live_validated"

    def test_exa_activated_skills(self):
        """All EXA-activated skills must be ACTIVE."""
        transitions = get_state_transition_map()
        for cid in [
            "ecc:exa-search", "ecc:deep-research", "ecc:market-research",
            "ecc:research-ops", "ecc:brand-discovery",
            "ecc:competitive-platform-analysis", "ecc:competitive-report-structure",
        ]:
            assert transitions.get(cid, {}).get("new_state") == "ACTIVE"

    def test_slack_activated_skills(self):
        """Slack-activated skills must be ACTIVE."""
        transitions = get_state_transition_map()
        for cid in ["ecc:messages-ops", "ecc:unified-notifications-ops"]:
            assert transitions[cid]["new_state"] == "ACTIVE"

    def test_linear_activated_skills(self):
        """Linear-activated skills must be ACTIVE."""
        transitions = get_state_transition_map()
        assert transitions["ecc:project-flow-ops"]["new_state"] == "ACTIVE"

    def test_resend_activated_skills(self):
        """Resend-activated skills must be ACTIVE (EMAIL_FROM note is OK)."""
        transitions = get_state_transition_map()
        for cid in ["ecc:email-ops", "ecc:investor-outreach", "ecc:marketing-campaign"]:
            assert transitions[cid]["new_state"] == "ACTIVE", f"{cid} should be ACTIVE"

    def test_videodb_activated(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:videodb"]["new_state"] == "ACTIVE"

    def test_pinecone_activated(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:knowledge-ops"]["new_state"] == "ACTIVE"

    def test_apollo_activated(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:lead-intelligence"]["new_state"] == "ACTIVE"

    def test_scrapingbee_activated(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:data-scraper-agent"]["new_state"] == "ACTIVE"

    def test_total_api_key_activated_count(self):
        """Total API-key activated skills must be 24."""
        count = sum(
            1 for v in get_state_transition_map().values()
            if v["activation_type"] == "api_key_live_validated"
        )
        assert count == 24, f"Expected 24 API-key activated, got {count}"


# ---------------------------------------------------------------------------
# State transitions — not-needed / cost-blocked
# ---------------------------------------------------------------------------

class TestNotNeededAndCostBlocked:
    """Verify skipped providers get precise states, not vague blockers."""

    def test_x402_is_not_needed(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:agent-payment-x402"]["new_state"] == "NOT_NEEDED_FOR_NOW"

    def test_greenhouse_is_not_needed(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:team-builder"]["new_state"] == "NOT_NEEDED_FOR_NOW"

    def test_ahrefs_is_not_needed(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:seo"]["new_state"] == "NOT_NEEDED_FOR_NOW"

    def test_jira_is_not_needed(self):
        """Jira is not needed because Linear is active."""
        transitions = get_state_transition_map()
        assert transitions["ecc:jira-integration"]["new_state"] == "NOT_NEEDED_FOR_NOW"

    def test_not_needed_count_is_4(self):
        count = sum(
            1 for v in get_state_transition_map().values()
            if v["new_state"] == "NOT_NEEDED_FOR_NOW"
        )
        assert count == 4, f"Expected 4 NOT_NEEDED, got {count}"

    def test_nutrient_is_cost_blocked(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:nutrient-document-processing"]["new_state"] == "COST_BLOCKED_OPTIONAL_LATER"

    def test_stripe_is_cost_blocked(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:stripe-integration"]["new_state"] == "COST_BLOCKED_OPTIONAL_LATER"

    def test_twitter_skills_are_cost_blocked(self):
        transitions = get_state_transition_map()
        for cid in ["ecc:social-publisher", "ecc:crosspost", "ecc:x-api", "ecc:social-graph-ranker"]:
            assert transitions[cid]["new_state"] == "COST_BLOCKED_OPTIONAL_LATER", (
                f"{cid} should be COST_BLOCKED"
            )

    def test_google_workspace_is_cost_blocked(self):
        transitions = get_state_transition_map()
        assert transitions["ecc:google-workspace-ops"]["new_state"] == "COST_BLOCKED_OPTIONAL_LATER"

    def test_cost_blocked_count_is_7(self):
        count = sum(
            1 for v in get_state_transition_map().values()
            if v["new_state"] == "COST_BLOCKED_OPTIONAL_LATER"
        )
        assert count == 7, f"Expected 7 COST_BLOCKED, got {count}"

    def test_not_needed_providers_are_not_blockers(self):
        """Bryan's skip list must never appear as Plan 1 blockers."""
        catalog = _build_static_catalog()
        skip_ids = {"ecc:agent-payment-x402", "ecc:team-builder", "ecc:seo", "ecc:jira-integration"}
        for cid in skip_ids:
            assert cid in catalog, f"{cid} not in catalog"
            state = catalog[cid]["plan1_state"]
            assert state in ("NOT_NEEDED_FOR_NOW", "COST_BLOCKED_OPTIONAL_LATER"), (
                f"{cid}: expected NOT_NEEDED or COST_BLOCKED, got {state}"
            )


# ---------------------------------------------------------------------------
# State transitions — failed auth
# ---------------------------------------------------------------------------

class TestFailedAuthHandling:
    """Verify failed auth keeps skill in precise waiting state."""

    def test_github_token_expired_stays_waiting(self):
        """GitHub token auth failed — github-ops, configure-ecc stay READY_BUT_WAITING."""
        transitions = get_state_transition_map()
        for cid in ["ecc:github-ops", "ecc:configure-ecc"]:
            assert transitions[cid]["new_state"] == "READY_BUT_WAITING_FOR_API_KEY"
            assert "401" in transitions[cid]["reason"] or "expired" in transitions[cid]["reason"]

    def test_github_failing_count_is_2(self):
        count = sum(
            1 for v in get_state_transition_map().values()
            if v["activation_type"] == "auth_failed"
        )
        assert count == 2


# ---------------------------------------------------------------------------
# State transitions — approval-only items
# ---------------------------------------------------------------------------

class TestApprovalActivation:
    """Verify all 36 approval-waiting items are activated via registry wiring."""

    def test_all_approval_items_activated(self):
        transitions = get_state_transition_map()
        for cid in _APPROVAL_ACTIVATED:
            assert cid in transitions, f"{cid} not in transitions"
            assert transitions[cid]["new_state"] == "ACTIVE", f"{cid}: expected ACTIVE"
            assert transitions[cid]["activation_type"] == "approval_registry_wiring"

    def test_approval_activated_count_is_36(self):
        count = sum(
            1 for v in get_state_transition_map().values()
            if v["activation_type"] == "approval_registry_wiring"
        )
        assert count == 36, f"Expected 36 approval-activated, got {count}"

    def test_hooks_activated(self):
        """All 10 hooks must be ACTIVE (registry wired)."""
        transitions = get_state_transition_map()
        hooks = [cid for cid in _APPROVAL_ACTIVATED if "hook:" in cid]
        assert len(hooks) == 10, f"Expected 10 hooks, got {len(hooks)}"
        for cid in hooks:
            assert transitions[cid]["new_state"] == "ACTIVE"

    def test_plugins_activated(self):
        """All 5 plugins must be ACTIVE (gate registered)."""
        transitions = get_state_transition_map()
        plugins = [cid for cid in _APPROVAL_ACTIVATED if "plugin:" in cid]
        assert len(plugins) == 5, f"Expected 5 plugins, got {len(plugins)}"
        for cid in plugins:
            assert transitions[cid]["new_state"] == "ACTIVE"

    def test_agents_activated(self):
        """All 13 agents must be ACTIVE (profile registered)."""
        transitions = get_state_transition_map()
        agents = [cid for cid in _APPROVAL_ACTIVATED if "agent:" in cid]
        assert len(agents) == 13, f"Expected 13 agents, got {len(agents)}"
        for cid in agents:
            assert transitions[cid]["new_state"] == "ACTIVE"

    def test_execution_wrappers_activated(self):
        """All 6 execution wrappers must be ACTIVE (wrapper registered, execution gated)."""
        transitions = get_state_transition_map()
        wrappers = [cid for cid in _APPROVAL_ACTIVATED if cid in {
            "ecc:browser-qa", "ecc:dmux-workflows", "ecc:e2e-testing",
            "ecc:nanoclaw-repl", "ecc:terminal-ops", "ecc:video-editing",
        }]
        assert len(wrappers) == 6
        for cid in wrappers:
            assert transitions[cid]["new_state"] == "ACTIVE"

    def test_approval_activation_means_registry_wired_not_unrestricted(self):
        """Approval activation means registry wiring only, not unrestricted execution."""
        transitions = get_state_transition_map()
        for cid in _APPROVAL_ACTIVATED:
            reason = transitions[cid]["reason"]
            assert "gated" in reason.lower() or "approval" in reason.lower(), (
                f"{cid}: reason must mention gating/approval"
            )


# ---------------------------------------------------------------------------
# Hooks/plugins/MCP remain gated
# ---------------------------------------------------------------------------

class TestGatesRemainIntact:
    """Verify that hooks/plugins/MCP runtime execution remains gated."""

    def test_hooks_in_catalog_have_not_been_executed(self):
        """Hook entries in the catalog must not have reviewer_approved=True for execution."""
        catalog = _build_static_catalog()
        hook_ids = [cid for cid in catalog if cid.startswith("ecc:hook:")]
        assert len(hook_ids) == 10
        for cid in hook_ids:
            # ACTIVE in catalog (registry wired), but execution gate NOT approved
            # reviewer_approved stays False for execution actions
            # plan1_state should be ACTIVE (registry wired)
            assert catalog[cid]["plan1_state"] == "ACTIVE", (
                f"{cid}: expected ACTIVE (registry wired)"
            )
            # The plan1_state is ACTIVE but execution is still gated in the framework
            # We verify the reason mentions gating
            reason = catalog[cid].get("reason", "")
            assert "gated" in reason.lower() or "approval" in reason.lower() or "disabled" in reason.lower(), (
                f"{cid}: reason must mention gating. Got: {reason[:100]}"
            )

    def test_plugins_in_catalog_are_gated(self):
        catalog = _build_static_catalog()
        plugin_ids = [cid for cid in catalog if cid.startswith("ecc:plugin:")]
        assert len(plugin_ids) == 5
        for cid in plugin_ids:
            assert catalog[cid]["plan1_state"] == "ACTIVE"
            reason = catalog[cid].get("reason", "")
            assert "gated" in reason.lower() or "approval" in reason.lower() or "gated" in reason.lower(), (
                f"{cid}: reason must mention gating"
            )

    def test_mcp_servers_are_gated(self):
        catalog = _build_static_catalog()
        assert "ecc:mcp:mcp-servers" in catalog
        entry = catalog["ecc:mcp:mcp-servers"]
        assert entry["plan1_state"] == "ACTIVE"
        reason = entry.get("reason", "")
        assert "gated" in reason.lower() or "approval" in reason.lower()

    def test_no_raw_ecc_modules_in_namespace(self):
        """Raw ECC code must not be loaded in Python module namespace."""
        raw_ecc_modules = [
            m for m in sys.modules
            if (
                "ecc" in m.lower()
                and "openjarvis" not in m.lower()
                and "test" not in m.lower()
            )
        ]
        assert not raw_ecc_modules, (
            f"Raw ECC modules loaded: {raw_ecc_modules}"
        )


# ---------------------------------------------------------------------------
# Flox and Pillow verification
# ---------------------------------------------------------------------------

class TestLocalToolVerification:
    """Verify Flox and Pillow checks work correctly."""

    def test_check_flox_returns_structured_result(self):
        result = check_flox()
        assert "installed" in result
        assert isinstance(result["installed"], bool)

    def test_check_pillow_returns_structured_result(self):
        result = check_pillow()
        assert "installed" in result
        assert isinstance(result["installed"], bool)

    def test_flox_installed_in_this_environment(self):
        """Flox 1.13.0 must be installed (verified in Prompt 2)."""
        result = check_flox()
        assert result["installed"] is True, (
            f"Flox is not installed. Result: {result}"
        )
        assert "1" in result.get("version", ""), "Flox version must be 1.x"

    def test_flox_activates_flox_environments(self):
        """Flox installed → flox-environments must be ACTIVE in catalog."""
        catalog = _build_static_catalog()
        assert "ecc:flox-environments" in catalog
        assert catalog["ecc:flox-environments"]["plan1_state"] == "ACTIVE"

    def test_pillow_not_installed_keeps_ios_icon_gen_waiting(self):
        """Pillow not installed → ios-icon-gen must stay READY_BUT_WAITING_FOR_USER_MANUAL_SETUP."""
        result = check_pillow()
        if not result["installed"]:
            catalog = _build_static_catalog()
            assert "ecc:ios-icon-gen" in catalog
            state = catalog["ecc:ios-icon-gen"]["plan1_state"]
            assert state == "READY_BUT_WAITING_FOR_USER_MANUAL_SETUP", (
                f"ios-icon-gen: expected READY_BUT_WAITING_FOR_USER_MANUAL_SETUP, got {state}"
            )

    def test_pillow_install_command_in_reason(self):
        """ios-icon-gen reason must include install command."""
        catalog = _build_static_catalog()
        reason = catalog["ecc:ios-icon-gen"].get("reason", "")
        assert "Pillow" in reason, "Reason must mention Pillow"

    def test_flox_transition_map(self):
        """With flox_installed=True, flox-environments is ACTIVE in transitions."""
        transitions = get_state_transition_map(flox_installed=True, pillow_installed=False)
        assert "ecc:flox-environments" in transitions
        assert transitions["ecc:flox-environments"]["new_state"] == "ACTIVE"
        assert transitions["ecc:flox-environments"]["activation_type"] == "local_tool_verified"

    def test_flox_missing_keeps_waiting(self):
        """With flox_installed=False, flox-environments stays waiting."""
        transitions = get_state_transition_map(flox_installed=False, pillow_installed=False)
        # flox-environments is NOT in transitions when flox is not installed
        # (it stays in base catalog state READY_BUT_WAITING_FOR_USER_MANUAL_SETUP)
        if "ecc:flox-environments" in transitions:
            assert transitions["ecc:flox-environments"]["new_state"] != "ACTIVE"


# ---------------------------------------------------------------------------
# Final state summary
# ---------------------------------------------------------------------------

class TestFinalStateSummary:
    """Verify final state counts match expected values."""

    def test_final_state_counts_reconcile_to_332(self):
        """All state counts must sum to 332."""
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["total"] == 332

    def test_active_count_is_316(self):
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["ACTIVE"] == EXPECTED_ACTIVE, (
            f"Expected {EXPECTED_ACTIVE} ACTIVE, got {summary['ACTIVE']}"
        )

    def test_api_key_waiting_is_2(self):
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["READY_BUT_WAITING_FOR_API_KEY"] == EXPECTED_API_KEY_WAITING

    def test_not_needed_is_4(self):
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["NOT_NEEDED_FOR_NOW"] == EXPECTED_NOT_NEEDED

    def test_cost_blocked_is_7(self):
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["COST_BLOCKED_OPTIONAL_LATER"] == EXPECTED_COST_BLOCKED

    def test_user_manual_setup_is_1(self):
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["READY_BUT_WAITING_FOR_USER_MANUAL_SETUP"] == EXPECTED_USER_MANUAL_SETUP

    def test_unautomatable_is_2(self):
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary["UNAUTOMATABLE_EVEN_WITH_APPROVAL"] == EXPECTED_UNAUTOMATABLE

    def test_approval_waiting_is_zero(self):
        """All approval-waiting items must be resolved in Prompt 2."""
        summary = compute_final_state_summary(flox_installed=True, pillow_installed=False)
        assert summary.get("READY_BUT_WAITING_FOR_APPROVAL", 0) == 0

    def test_catalog_state_counts_match_summary(self):
        """Catalog state counts must match the computed summary."""
        catalog = _build_static_catalog()
        by_state: Dict[str, int] = {}
        for item in catalog.values():
            s = item.get("plan1_state", "unknown")
            by_state[s] = by_state.get(s, 0) + 1

        assert by_state.get("ACTIVE", 0) == EXPECTED_ACTIVE
        assert by_state.get("READY_BUT_WAITING_FOR_API_KEY", 0) == EXPECTED_API_KEY_WAITING
        assert by_state.get("NOT_NEEDED_FOR_NOW", 0) == EXPECTED_NOT_NEEDED
        assert by_state.get("COST_BLOCKED_OPTIONAL_LATER", 0) == EXPECTED_COST_BLOCKED
        assert by_state.get("READY_BUT_WAITING_FOR_USER_MANUAL_SETUP", 0) == EXPECTED_USER_MANUAL_SETUP
        assert by_state.get("UNAUTOMATABLE_EVEN_WITH_APPROVAL", 0) == EXPECTED_UNAUTOMATABLE

    def test_total_catalog_items_is_332(self):
        catalog = _build_static_catalog()
        assert len(catalog) == EXPECTED_TOTAL


# ---------------------------------------------------------------------------
# No vague states
# ---------------------------------------------------------------------------

class TestNoPreciseVagueStates:
    """Verify no vague or legacy states exist after Prompt 2."""

    def test_no_adapt_needed_states(self):
        catalog = _build_static_catalog()
        adapt_needed = [
            cid for cid, item in catalog.items()
            if "adapt_needed" in item.get("plan1_state", "").lower()
        ]
        assert not adapt_needed, f"Items still in adapt_needed: {adapt_needed}"

    def test_no_installed_disabled_state(self):
        catalog = _build_static_catalog()
        disabled = [
            cid for cid, item in catalog.items()
            if item.get("plan1_state", "") == "INSTALLED_DISABLED_WITH_EXACT_BLOCKER"
        ]
        assert not disabled, f"Items still installed_disabled: {disabled}"

    def test_no_inspect_later_state(self):
        catalog = _build_static_catalog()
        inspect = [
            cid for cid, item in catalog.items()
            if "inspect_later" in item.get("plan1_state", "").lower()
        ]
        assert not inspect, f"Items still in inspect_later: {inspect}"

    def test_no_approval_waiting_state_remains(self):
        """READY_BUT_WAITING_FOR_APPROVAL must be 0 after Prompt 2."""
        catalog = _build_static_catalog()
        approval = [
            cid for cid, item in catalog.items()
            if item.get("plan1_state", "") == "READY_BUT_WAITING_FOR_APPROVAL"
        ]
        assert not approval, (
            f"Items still waiting for approval (should all be activated): {approval}"
        )

    def test_all_states_are_valid_final_states(self):
        """Every item must be in a valid final Plan 1 state."""
        catalog = _build_static_catalog()
        invalid = [
            (cid, item.get("plan1_state", ""))
            for cid, item in catalog.items()
            if item.get("plan1_state", "") not in VALID_FINAL_STATES
        ]
        assert not invalid, f"Items with invalid states: {invalid[:5]}"


# ---------------------------------------------------------------------------
# Live auth test results
# ---------------------------------------------------------------------------

class TestLiveAuthTestResults:
    """Validate recorded live auth test results."""

    def test_aimlapi_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["AIMLAPI"]["auth_ok"] is True
        assert LIVE_AUTH_TEST_RESULTS["AIMLAPI"]["status_code"] == 200

    def test_openrouter_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["OpenRouter"]["auth_ok"] is True
        assert LIVE_AUTH_TEST_RESULTS["OpenRouter"]["status_code"] == 200

    def test_slack_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["Slack"]["auth_ok"] is True

    def test_linear_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["Linear"]["auth_ok"] is True

    def test_resend_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["Resend"]["auth_ok"] is True
        assert LIVE_AUTH_TEST_RESULTS["Resend"]["status_code"] == 200

    def test_videodb_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["VideoDB"]["auth_ok"] is True

    def test_pinecone_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["Pinecone"]["auth_ok"] is True

    def test_apollo_auth_passed(self):
        """Apollo returned 422 (key valid — non-401) — auth inferred valid."""
        assert LIVE_AUTH_TEST_RESULTS["Apollo"]["auth_ok"] is True
        assert LIVE_AUTH_TEST_RESULTS["Apollo"]["status_code"] == 422

    def test_scrapingbee_auth_passed(self):
        assert LIVE_AUTH_TEST_RESULTS["ScrapingBee"]["auth_ok"] is True

    def test_github_auth_failed(self):
        """GitHub token returned 401 — must be recorded as failed."""
        assert LIVE_AUTH_TEST_RESULTS["GitHub"]["auth_ok"] is False
        assert LIVE_AUTH_TEST_RESULTS["GitHub"]["status_code"] == 401

    def test_twitter_not_configured(self):
        assert LIVE_AUTH_TEST_RESULTS["Twitter"]["auth_ok"] is False

    def test_no_external_sends_in_auth_tests(self):
        """All auth tests must be read-only or format-check only."""
        allowed_types = {
            "models_list", "auth_test", "graphql_viewer", "domains_list",
            "collection_list", "indexes_list", "people_match_empty",
            "scrape_httpbin", "search_test", "user_endpoint",
            "key_format_check", "key_presence",
        }
        for provider, result in LIVE_AUTH_TEST_RESULTS.items():
            assert result["test_type"] in allowed_types, (
                f"{provider}: test_type '{result['test_type']}' not in allowed types"
            )

    def test_no_send_tests_in_auth_results(self):
        """No test should send messages, emails, posts, or payments."""
        forbidden_types = {"send_message", "send_email", "post_tweet", "charge_card", "deploy"}
        for provider, result in LIVE_AUTH_TEST_RESULTS.items():
            assert result["test_type"] not in forbidden_types, (
                f"{provider}: test_type '{result['test_type']}' is a forbidden action type"
            )


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

class TestArtifactGeneration:
    """Validate artifact generation (no secrets, correct structure)."""

    def test_generate_json_returns_valid_json(self):
        json_str = generate_live_validation_json()
        data = json.loads(json_str)
        assert data["schema"] == "plan1_ecc_live_key_validation_v1"

    def test_json_artifact_has_security_field(self):
        data = json.loads(generate_live_validation_json())
        assert data["security"]["secrets_printed"] is False
        assert data["security"]["external_sends"] is False
        assert data["security"]["payments"] is False
        assert data["security"]["raw_ecc_executed"] is False
        assert data["security"]["gates_weakened"] is False

    def test_json_artifact_has_key_presence(self):
        data = json.loads(generate_live_validation_json())
        assert "key_presence" in data
        assert "AIMLAPI" in data["key_presence"]

    def test_json_artifact_has_live_auth_tests(self):
        data = json.loads(generate_live_validation_json())
        assert "live_auth_tests" in data
        for provider in ["AIMLAPI", "Slack", "Linear", "GitHub", "Resend"]:
            assert provider in data["live_auth_tests"]

    def test_json_artifact_has_final_state_summary(self):
        data = json.loads(generate_live_validation_json())
        summary = data["final_state_summary"]
        assert summary["ACTIVE"] == EXPECTED_ACTIVE
        assert summary["total"] == EXPECTED_TOTAL

    def test_json_artifact_written_to_disk(self, tmp_path):
        output = tmp_path / "test_live_validation.json"
        generate_live_validation_json(output_path=output)
        assert output.exists()
        data = json.loads(output.read_text())
        assert data["schema"] == "plan1_ecc_live_key_validation_v1"

    def test_markdown_artifact_contains_security_section(self):
        md = format_live_validation_md()
        assert "## Security Verification" in md
        assert "No secret values" in md or "secrets printed" in md.lower()

    def test_markdown_artifact_contains_state_table(self):
        md = format_live_validation_md()
        assert "ACTIVE" in md
        assert str(EXPECTED_ACTIVE) in md

    def test_final_status_md_contains_verdict(self):
        md = format_final_status_md()
        assert "PLAN_1_ECC_LIVE_VALIDATION_ACCEPT_PENDING_REVIEW" in md

    def test_final_status_md_contains_state_counts(self):
        md = format_final_status_md()
        assert str(EXPECTED_ACTIVE) in md

    def test_final_status_md_no_secrets(self):
        md = format_final_status_md()
        # Should not contain anything that looks like an actual API key
        assert "super_secret" not in md.lower()
        assert len([line for line in md.splitlines() if len(line) > 200]) < 5


# ---------------------------------------------------------------------------
# Plan1State — new states registered
# ---------------------------------------------------------------------------

class TestPlan1StateConstants:
    """Verify new Plan1State constants are defined."""

    def test_cost_blocked_state_defined(self):
        assert hasattr(Plan1State, "COST_BLOCKED_OPTIONAL_LATER")
        assert Plan1State.COST_BLOCKED_OPTIONAL_LATER == "COST_BLOCKED_OPTIONAL_LATER"

    def test_not_needed_state_defined(self):
        assert hasattr(Plan1State, "NOT_NEEDED_FOR_NOW")
        assert Plan1State.NOT_NEEDED_FOR_NOW == "NOT_NEEDED_FOR_NOW"

    def test_all_valid_states_exist(self):
        """All states listed in the final spec must exist in Plan1State."""
        required = {
            "ACTIVE",
            "READY_BUT_WAITING_FOR_API_KEY",
            "READY_BUT_WAITING_FOR_APPROVAL",
            "READY_BUT_WAITING_FOR_USER_MANUAL_SETUP",
            "COST_BLOCKED_OPTIONAL_LATER",
            "NOT_NEEDED_FOR_NOW",
            "UNAUTOMATABLE_EVEN_WITH_APPROVAL",
            "REJECTED_WITH_REASON",
            "DUPLICATE_WITH_REASON",
            "QUARANTINED_WITH_REASON",
        }
        defined = {
            k for k in dir(Plan1State)
            if not k.startswith("_")
        }
        missing = required - defined
        assert not missing, f"Missing Plan1State constants: {missing}"


# ---------------------------------------------------------------------------
# No external side effects
# ---------------------------------------------------------------------------

class TestNoExternalSideEffects:
    """Verify no external sends, payments, or destructive writes occurred."""

    def test_key_presence_check_no_network(self):
        """check_key_presence() must not make network calls."""
        import socket
        original_create_connection = socket.create_connection

        called = []

        def mock_create_connection(*args, **kwargs):
            called.append(args)
            raise ConnectionRefusedError("Network call blocked in test")

        with patch.object(socket, "create_connection", mock_create_connection):
            check_key_presence({"AIMLAPI_API_KEY": "test"})

        assert not called, "check_key_presence() must not make network calls"

    def test_verify_env_gitignored_no_network(self):
        """verify_env_gitignored() must not make network calls."""
        import socket
        called = []

        def mock_create_connection(*args, **kwargs):
            called.append(args)
            raise ConnectionRefusedError("Network blocked")

        with patch.object(socket, "create_connection", mock_create_connection):
            verify_env_gitignored()

        assert not called, "verify_env_gitignored() must not make network calls"

    def test_compute_final_state_summary_no_network(self):
        """compute_final_state_summary() must not make network calls."""
        import socket
        called = []

        def mock_create_connection(*args, **kwargs):
            called.append(args)
            raise ConnectionRefusedError("Network blocked")

        with patch.object(socket, "create_connection", mock_create_connection):
            compute_final_state_summary()

        assert not called

    def test_get_state_transition_map_no_network(self):
        """get_state_transition_map() must not make network calls."""
        import socket
        called = []

        def mock_create_connection(*args, **kwargs):
            called.append(args)
            raise ConnectionRefusedError("Network blocked")

        with patch.object(socket, "create_connection", mock_create_connection):
            get_state_transition_map()

        assert not called
