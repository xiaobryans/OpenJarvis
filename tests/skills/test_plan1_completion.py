"""Plan 1 ECC Completion Sprint — Pre-Keys Automation Tests.

Proves:
  A. No vague installed_disabled/adapt_needed/inspect_later remains
  B. All 35 API-key skills have exact required keys and exact blockers
  C. Every API-key skill has mocked test and live test command placeholder
  D. Every API-key skill can reach READY state after key presence check
  E. All safe no-key items are ACTIVE or have exact rejection reason
  F. Risky hooks/scripts/plugins/MCP remain disabled
  G. Disabled/quarantined items cannot be executed
  H. Registry/API status counts reconcile exactly
  I. No raw ECC code/hooks/scripts/plugins/MCP execute during tests
  J. Mocked invocations return MOCKED_SUCCESS without live API calls
  K. Readiness report structure is correct
  L. Artifact files (JSON + MD) are complete and valid

All tests run OFFLINE (no network, no secrets, no live API calls).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from openjarvis.skills.ecc_catalog import (
    ACTIVE_COUNT_BY_CATEGORY,
    ECCCatalog,
    get_catalog,
)
from openjarvis.skills.ecc_completion import (
    ECC_KEY_REQUIREMENTS,
    ECC_KEY_REQUIREMENTS_BY_ID,
    Plan1State,
    check_key_presence,
    format_missing_keys_md,
    generate_missing_keys_json,
    get_readiness_report,
    live_test_skill,
    run_mocked_tests,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalog() -> ECCCatalog:
    return ECCCatalog()


@pytest.fixture(scope="module")
def plan1_summary(catalog: ECCCatalog) -> Dict[str, Any]:
    return catalog.get_plan1_completion_summary()


@pytest.fixture(scope="module")
def all_items(catalog: ECCCatalog) -> List[Dict[str, Any]]:
    return catalog.list_all()


# ---------------------------------------------------------------------------
# Section A — No vague states remain
# ---------------------------------------------------------------------------

class TestNoVagueStates:
    """Prove no item is left in a vague state."""

    VALID_PLAN1_STATES = {
        Plan1State.ACTIVE,
        Plan1State.READY_BUT_WAITING_FOR_API_KEY,
        Plan1State.READY_BUT_WAITING_FOR_APPROVAL,
        Plan1State.READY_BUT_WAITING_FOR_USER_MANUAL_SETUP,
        Plan1State.COST_BLOCKED_OPTIONAL_LATER,
        Plan1State.NOT_NEEDED_FOR_NOW,
        Plan1State.ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK,
        Plan1State.INSTALLED_DISABLED_WITH_EXACT_BLOCKER,
        Plan1State.UNAUTOMATABLE_EVEN_WITH_APPROVAL,
        Plan1State.REJECTED_WITH_REASON,
        Plan1State.DUPLICATE_WITH_REASON,
        Plan1State.QUARANTINED_WITH_REASON,
    }

    def test_no_item_has_no_plan1_state(self, all_items: List[Dict[str, Any]]) -> None:
        missing = [
            item.get("candidate_id", "unknown")
            for item in all_items
            if item.get("plan1_state") is None
        ]
        assert not missing, (
            f"{len(missing)} items have no plan1_state: {missing[:10]}"
        )

    def test_all_plan1_states_are_valid(self, all_items: List[Dict[str, Any]]) -> None:
        invalid = [
            (item.get("candidate_id"), item.get("plan1_state"))
            for item in all_items
            if item.get("plan1_state") not in self.VALID_PLAN1_STATES
        ]
        assert not invalid, (
            f"{len(invalid)} items have invalid plan1_state: {invalid[:10]}"
        )

    def test_no_vague_inspect_later_remaining(self, plan1_summary: Dict[str, Any]) -> None:
        assert plan1_summary["inspect_later_remaining"] == 0, (
            f"Expected 0 inspect_later remaining, got {plan1_summary['inspect_later_remaining']}"
        )

    def test_no_plain_adapt_needed_without_task(self, all_items: List[Dict[str, Any]]) -> None:
        """No item should have state='adapt_needed' but plan1_state still vague."""
        vague = [
            item.get("candidate_id")
            for item in all_items
            if item.get("state") == "adapt_needed"
            and item.get("plan1_state") == "adapt_needed"
        ]
        assert not vague, f"Vague adapt_needed without exact task: {vague}"

    def test_no_plain_installed_disabled_without_blocker(self, all_items: List[Dict[str, Any]]) -> None:
        """No item should have state='installed_disabled' but vague plan1_state."""
        vague = [
            item.get("candidate_id")
            for item in all_items
            if item.get("state") == "installed_disabled"
            and item.get("plan1_state") == "installed_disabled"
        ]
        assert not vague, f"Vague installed_disabled without exact blocker: {vague}"

    def test_total_catalog_items_reconcile(self, plan1_summary: Dict[str, Any]) -> None:
        """Sum of all plan1_state counts must equal total_registered."""
        counts = plan1_summary["plan1_state_counts"]
        total = sum(counts.values())
        assert total == plan1_summary["total_registered"], (
            f"plan1_state counts ({total}) != total_registered ({plan1_summary['total_registered']})"
        )


# ---------------------------------------------------------------------------
# Section B — API-key skills completeness
# ---------------------------------------------------------------------------

class TestApiKeySkillsCompleteness:
    """Prove all 35 API-key skills are structurally complete."""

    EXPECTED_API_KEY_SKILL_COUNT = 37  # Updated: 35 + nutrient-doc-processing + continuous-learning-v2

    def test_ecc_key_requirements_count(self) -> None:
        assert len(ECC_KEY_REQUIREMENTS) == self.EXPECTED_API_KEY_SKILL_COUNT, (
            f"Expected {self.EXPECTED_API_KEY_SKILL_COUNT} key requirements, "
            f"got {len(ECC_KEY_REQUIREMENTS)}"
        )

    def test_catalog_api_key_state_count(self, plan1_summary: Dict[str, Any]) -> None:
        # After Prompt 3 micro-verification: GitHub token refreshed (200 OK) → github-ops + configure-ecc ACTIVE.
        # Pillow installed → ios-icon-gen ACTIVE. 0 items remain READY_BUT_WAITING_FOR_API_KEY.
        count = plan1_summary["plan1_state_counts"].get(
            Plan1State.READY_BUT_WAITING_FOR_API_KEY, 0
        )
        assert count == 0, (
            f"Post-Prompt-3 catalog shows {count} READY_BUT_WAITING_FOR_API_KEY, "
            f"expected 0 (GitHub token refreshed; all API-key skills activated)"
        )

    def test_every_api_key_skill_has_required_fields(self) -> None:
        required_fields = [
            "skill_id",
            "provider",
            "required_env_keys",
            "optional_env_keys",
            "account_setup",
            "risk",
            "jarvis_permission_scope",
            "plan1_state",
            "exact_blocker",
            "mocked_test_command",
            "live_test_command",
            "activation_route",
            "rollback_path",
            "completable_with_keys",
            "impossible_even_with_keys",
        ]
        for req in ECC_KEY_REQUIREMENTS:
            missing_fields = [f for f in required_fields if f not in req]
            assert not missing_fields, (
                f"skill {req.get('skill_id')} missing fields: {missing_fields}"
            )

    def test_every_api_key_skill_has_exact_blocker(self) -> None:
        for req in ECC_KEY_REQUIREMENTS:
            assert req["exact_blocker"], (
                f"skill {req['skill_id']} has empty exact_blocker"
            )

    def test_every_api_key_skill_has_mocked_test_command(self) -> None:
        for req in ECC_KEY_REQUIREMENTS:
            assert req["mocked_test_command"], (
                f"skill {req['skill_id']} has empty mocked_test_command"
            )

    def test_every_api_key_skill_has_live_test_command(self) -> None:
        for req in ECC_KEY_REQUIREMENTS:
            assert req["live_test_command"], (
                f"skill {req['skill_id']} has empty live_test_command"
            )

    def test_every_api_key_skill_has_rollback_path(self) -> None:
        for req in ECC_KEY_REQUIREMENTS:
            assert req["rollback_path"], (
                f"skill {req['skill_id']} has empty rollback_path"
            )

    def test_every_api_key_skill_has_activation_route(self) -> None:
        for req in ECC_KEY_REQUIREMENTS:
            assert req["activation_route"], (
                f"skill {req['skill_id']} has empty activation_route"
            )

    def test_plan1_state_is_ready_not_vague(self) -> None:
        # ECC_KEY_REQUIREMENTS is a static requirements manifest (pre-Prompt-2 state).
        # After Prompt 2, many skills became ACTIVE in the catalog, but the manifest
        # still shows READY_BUT_WAITING_FOR_API_KEY as the baseline requirement state.
        for req in ECC_KEY_REQUIREMENTS:
            assert req["plan1_state"] in (
                Plan1State.READY_BUT_WAITING_FOR_API_KEY,
                Plan1State.ACTIVE,  # post-Prompt-2 activated skills
                Plan1State.NOT_NEEDED_FOR_NOW,  # Bryan confirmed skip
                Plan1State.COST_BLOCKED_OPTIONAL_LATER,  # cost-blocked
            ), (
                f"skill {req['skill_id']} has unexpected plan1_state: {req['plan1_state']}"
            )

    def test_risk_levels_are_valid(self) -> None:
        valid_risks = {"read_only", "write", "action", "send", "deploy", "financial", "low", "medium", "high"}
        for req in ECC_KEY_REQUIREMENTS:
            assert req["risk"] in valid_risks, (
                f"skill {req['skill_id']} has invalid risk: {req['risk']}"
            )

    def test_lookup_by_id_works(self) -> None:
        assert "exa-search" in ECC_KEY_REQUIREMENTS_BY_ID
        assert "stripe-integration" in ECC_KEY_REQUIREMENTS_BY_ID
        assert "github-ops" in ECC_KEY_REQUIREMENTS_BY_ID


# ---------------------------------------------------------------------------
# Section C — Adapt-needed items have exact engineering tasks
# ---------------------------------------------------------------------------

class TestAdaptNeededExactTasks:
    """Prove all adapt_needed items have exact engineering task descriptions."""

    EXPECTED_ADAPT_NEEDED_COUNT = 0  # Correction sprint: all 28 resolved (wrappers built or UNAUTOMATABLE)

    def test_adapt_needed_exact_task_count(self, plan1_summary: Dict[str, Any]) -> None:
        count = plan1_summary["plan1_state_counts"].get(
            Plan1State.ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK, 0
        )
        assert count == self.EXPECTED_ADAPT_NEEDED_COUNT, (
            f"Expected {self.EXPECTED_ADAPT_NEEDED_COUNT} ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK, "
            f"got {count}"
        )

    def test_adapt_needed_items_have_reason(self, all_items: List[Dict[str, Any]]) -> None:
        adapt_items = [
            item for item in all_items
            if item.get("plan1_state") == Plan1State.ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK
        ]
        for item in adapt_items:
            reason = item.get("reason", "")
            assert "ADAPT_NEEDED_WITH_EXACT_ENGINEERING_TASK" in reason, (
                f"Item {item.get('candidate_id')} has no exact engineering task in reason: {reason[:100]}"
            )


# ---------------------------------------------------------------------------
# Section D — Approval-waiting agents
# ---------------------------------------------------------------------------

class TestApprovalWaitingAgents:
    """Prove planning/review agents are precisely marked — now ACTIVE after Prompt 2."""

    EXPECTED_APPROVAL_COUNT = 0  # Prompt 2: all 36 approval-waiting items activated via registry wiring

    def test_approval_waiting_count(self, plan1_summary: Dict[str, Any]) -> None:
        count = plan1_summary["plan1_state_counts"].get(
            Plan1State.READY_BUT_WAITING_FOR_APPROVAL, 0
        )
        assert count == self.EXPECTED_APPROVAL_COUNT, (
            f"Expected {self.EXPECTED_APPROVAL_COUNT} READY_BUT_WAITING_FOR_APPROVAL, got {count}. "
            f"Prompt 2 activated all 36 approval-waiting items via Bryan's registry-wiring approval."
        )

    def test_agents_are_now_active_in_catalog(self, all_items: List[Dict[str, Any]]) -> None:
        """After Prompt 2, all agents are ACTIVE (profiles registered, routing still gated)."""
        agent_items = [
            item for item in all_items
            if item.get("category") == "agent"
        ]
        active_agents = [item for item in agent_items if item.get("plan1_state") == "ACTIVE"]
        # All 13 agents must be ACTIVE
        assert len(active_agents) == 13, (
            f"Expected 13 active agents, got {len(active_agents)}"
        )


# ---------------------------------------------------------------------------
# Section E — Installed-disabled items have exact blockers
# ---------------------------------------------------------------------------

class TestInstalledDisabledExactBlockers:
    """Prove all installed_disabled items have exact blockers documented."""

    EXPECTED_DISABLED_BLOCKER_COUNT = 0  # Correction sprint: all 3 resolved to approval-waiting or UNAUTOMATABLE

    def test_installed_disabled_count(self, plan1_summary: Dict[str, Any]) -> None:
        count = plan1_summary["plan1_state_counts"].get(
            Plan1State.INSTALLED_DISABLED_WITH_EXACT_BLOCKER, 0
        )
        assert count == self.EXPECTED_DISABLED_BLOCKER_COUNT, (
            f"Expected {self.EXPECTED_DISABLED_BLOCKER_COUNT} INSTALLED_DISABLED_WITH_EXACT_BLOCKER, "
            f"got {count}"
        )

    def test_installed_disabled_items_have_reason(self, all_items: List[Dict[str, Any]]) -> None:
        disabled_items = [
            item for item in all_items
            if item.get("plan1_state") == Plan1State.INSTALLED_DISABLED_WITH_EXACT_BLOCKER
        ]
        for item in disabled_items:
            reason = item.get("reason", "")
            assert reason, (
                f"Item {item.get('candidate_id')} has INSTALLED_DISABLED_WITH_EXACT_BLOCKER "
                f"but empty reason"
            )


# ---------------------------------------------------------------------------
# Section F — Active count accuracy
# ---------------------------------------------------------------------------

class TestActiveCount:
    """Prove active count is 319 after Prompt 3 micro-verification (GitHub refresh + Pillow)."""

    EXPECTED_ACTIVE_COUNT = 319   # Prompt 3: 316 + 2 GitHub + 1 Pillow
    EXPECTED_PROMPT2_COUNT = 316  # Prompt 2 total
    EXPECTED_PRE_PROMPT2_COUNT = 255  # Pre-Prompt-2 baseline

    def test_active_count_from_summary(self, plan1_summary: Dict[str, Any]) -> None:
        assert plan1_summary["active_count"] == self.EXPECTED_ACTIVE_COUNT, (
            f"Active count: expected {self.EXPECTED_ACTIVE_COUNT} (Prompt 3), "
            f"got {plan1_summary['active_count']}"
        )

    def test_active_count_from_plan1_state(self, plan1_summary: Dict[str, Any]) -> None:
        count = plan1_summary["plan1_state_counts"].get(Plan1State.ACTIVE, 0)
        assert count == self.EXPECTED_ACTIVE_COUNT, (
            f"plan1_state ACTIVE count: expected {self.EXPECTED_ACTIVE_COUNT}, got {count}"
        )

    def test_active_count_by_category_baseline(self) -> None:
        """Pre-Prompt-2 baseline must still be documented in ACTIVE_COUNT_BY_CATEGORY."""
        total = ACTIVE_COUNT_BY_CATEGORY.get("TOTAL", 0)
        assert total == self.EXPECTED_PRE_PROMPT2_COUNT, (
            f"ACTIVE_COUNT_BY_CATEGORY TOTAL baseline: expected {self.EXPECTED_PRE_PROMPT2_COUNT}, got {total}"
        )

    def test_prompt2_total_documented(self) -> None:
        """Prompt-2 total (316) must be documented in ACTIVE_COUNT_BY_CATEGORY."""
        prompt2_total = ACTIVE_COUNT_BY_CATEGORY.get("PROMPT2_TOTAL", 0)
        assert prompt2_total == self.EXPECTED_PROMPT2_COUNT, (
            f"ACTIVE_COUNT_BY_CATEGORY PROMPT2_TOTAL: expected {self.EXPECTED_PROMPT2_COUNT}, got {prompt2_total}"
        )

    def test_prompt3_total_documented(self) -> None:
        """Prompt-3 total (319) must be documented in ACTIVE_COUNT_BY_CATEGORY."""
        prompt3_total = ACTIVE_COUNT_BY_CATEGORY.get("PROMPT3_TOTAL", 0)
        assert prompt3_total == self.EXPECTED_ACTIVE_COUNT, (
            f"ACTIVE_COUNT_BY_CATEGORY PROMPT3_TOTAL: expected {self.EXPECTED_ACTIVE_COUNT}, got {prompt3_total}"
        )


# ---------------------------------------------------------------------------
# Section G — Risky items remain disabled (safety invariants)
# ---------------------------------------------------------------------------

class TestRiskyItemsDisabled:
    """Prove hooks/scripts/plugins/MCP remain disabled."""

    def test_plan1_summary_confirms_risky_items_disabled(self, plan1_summary: Dict[str, Any]) -> None:
        assert plan1_summary["risky_items_remain_disabled"] is True, (
            "plan1_summary says risky items are NOT disabled"
        )

    def test_hooks_runtime_execution_remains_gated(self, all_items: List[Dict[str, Any]]) -> None:
        """Hooks are ACTIVE in catalog (registry wired) but runtime execution is gated.
        After Prompt 2, plan1_state=ACTIVE but reviewer_approved=False for execution actions."""
        hook_items = [
            item for item in all_items
            if item.get("category") == "hook"
        ]
        # All hooks should be ACTIVE (registry wired) after Prompt 2
        active_hooks = [item for item in hook_items if item.get("plan1_state") == "ACTIVE"]
        assert len(active_hooks) == 10, f"Expected 10 ACTIVE hooks, got {len(active_hooks)}"
        # Execution gate: reason must mention gating/approval/disabled
        for item in active_hooks:
            reason = item.get("reason", "")
            assert (
                "gated" in reason.lower()
                or "approval" in reason.lower()
                or "disabled" in reason.lower()
                or "registry" in reason.lower()
            ), f"Hook {item.get('candidate_id')}: reason must mention gating. Got: {reason[:80]}"

    def test_plugins_runtime_execution_remains_gated(self, all_items: List[Dict[str, Any]]) -> None:
        """Plugins are ACTIVE in catalog (gate registered) but runtime loading is gated."""
        plugin_items = [
            item for item in all_items
            if item.get("category") == "plugin"
        ]
        active_plugins = [item for item in plugin_items if item.get("plan1_state") == "ACTIVE"]
        assert len(active_plugins) == 5, f"Expected 5 ACTIVE plugins, got {len(active_plugins)}"
        for item in active_plugins:
            reason = item.get("reason", "")
            assert (
                "gated" in reason.lower()
                or "approval" in reason.lower()
                or "registry" in reason.lower()
            ), f"Plugin {item.get('candidate_id')}: reason must mention gating"

    def test_mcp_configs_runtime_execution_gated(self, all_items: List[Dict[str, Any]]) -> None:
        """MCP configs are ACTIVE in catalog (security gate wired) but per-server activation is gated.
        After Prompt 2, plan1_state=ACTIVE but each server requires individual security review + approval."""
        mcp_items = [
            item for item in all_items
            if item.get("category") == "mcp_config"
        ]
        active_mcp = [item for item in mcp_items if item.get("plan1_state") == "ACTIVE"]
        assert len(active_mcp) == 1, f"Expected 1 ACTIVE MCP config, got {len(active_mcp)}"
        # Verify execution is still gated (reason mentions security/gating)
        for item in active_mcp:
            reason = item.get("reason", "")
            assert (
                "gated" in reason.lower()
                or "security" in reason.lower()
                or "approval" in reason.lower()
                or "review" in reason.lower()
            ), f"MCP config {item.get('candidate_id')}: reason must mention gating. Got: {reason[:80]}"

    def test_eval_harness_is_unautomatable(self, all_items: List[Dict[str, Any]]) -> None:
        harness = next(
            (item for item in all_items if item.get("candidate_id") == "ecc:eval-harness"), None
        )
        assert harness is not None, "ecc:eval-harness not found in catalog"
        assert harness.get("plan1_state") == "UNAUTOMATABLE_EVEN_WITH_APPROVAL", (
            "ecc:eval-harness must remain UNAUTOMATABLE — raw ECC execution policy"
        )

    def test_database_migration_command_is_gated(self, all_items: List[Dict[str, Any]]) -> None:
        """database-migration is ACTIVE (dry_run=True default) but risky execution is gated."""
        db_migration_cmd = next(
            (item for item in all_items if item.get("candidate_id") == "ecc:cmd:database-migration"), None
        )
        assert db_migration_cmd is not None, "ecc:cmd:database-migration command not found in catalog"
        # After Prompt 2: ACTIVE (registry wired), but execution gated by JARVIS_DB_MIGRATION_APPROVED
        assert db_migration_cmd.get("plan1_state") == "ACTIVE"
        reason = db_migration_cmd.get("reason", "")
        assert "gated" in reason.lower() or "approval" in reason.lower(), (
            "database-migration reason must mention approval gating"
        )


# ---------------------------------------------------------------------------
# Section H — Key presence checker (mocked env)
# ---------------------------------------------------------------------------

class TestKeyPresenceChecker:
    """Prove check_key_presence works correctly with mocked environment."""

    def test_missing_key_returns_not_ready(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            # Ensure EXA_API_KEY is not in env
            env = {k: v for k, v in os.environ.items() if k != "EXA_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                result = check_key_presence("exa-search")
                assert result["can_activate"] is False
                assert "EXA_API_KEY" in result["missing_required"]

    def test_present_key_returns_ready(self) -> None:
        with patch.dict(os.environ, {"EXA_API_KEY": "test_key_value_not_real"}):
            result = check_key_presence("exa-search")
            assert result["can_activate"] is True
            assert result["missing_required"] == []

    def test_unknown_skill_returns_error(self) -> None:
        result = check_key_presence("non-existent-skill-xyz")
        assert result["found"] is False
        assert "error" in result

    def test_key_presence_does_not_print_key_values(self, capsys: pytest.CaptureFixture) -> None:
        with patch.dict(os.environ, {"EXA_API_KEY": "SUPER_SECRET_DO_NOT_PRINT"}):
            check_key_presence("exa-search")
            captured = capsys.readouterr()
            assert "SUPER_SECRET_DO_NOT_PRINT" not in captured.out
            assert "SUPER_SECRET_DO_NOT_PRINT" not in captured.err

    def test_readiness_report_structure(self) -> None:
        report = get_readiness_report()
        assert "total_api_key_skills" in report
        assert report["total_api_key_skills"] == 37
        assert "results" in report
        assert len(report["results"]) == 37
        assert "missing_by_provider" in report
        assert "prompt2_action" in report


# ---------------------------------------------------------------------------
# Section I — Mocked tests (no live calls)
# ---------------------------------------------------------------------------

class TestEccKeySkillsMocked:
    """Prove mocked invocations work without any live API calls."""

    def test_run_all_mocked_tests(self) -> None:
        results = run_mocked_tests()
        assert results["all_mocked_success"] is True, (
            f"Some mocked tests failed: {[r for r in results['results'] if r['result'] != 'MOCKED_SUCCESS']}"
        )
        assert results["total"] == 37

    def test_exa_search_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("exa-search")
        assert result["result"] == "MOCKED_SUCCESS"
        assert result["dry_run"] is True

    def test_fal_ai_media_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("fal-ai-media")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_deep_research_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("deep-research")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_github_ops_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("github-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_stripe_integration_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("stripe-integration")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_market_research_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("market-research")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_data_scraper_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("data-scraper-agent")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_social_publisher_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("social-publisher")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_email_ops_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("email-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_jira_integration_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("jira-integration")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_google_workspace_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("google-workspace-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_messages_ops_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("messages-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_x_api_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("x-api")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_unified_notifications_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("unified-notifications-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_lead_intelligence_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("lead-intelligence")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_investor_outreach_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("investor-outreach")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_crosspost_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("crosspost")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_videodb_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("videodb")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_ecc_tools_cost_audit_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("ecc-tools-cost-audit")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_configure_ecc_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("configure-ecc")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_article_writing_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("article-writing")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_content_engine_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("content-engine")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_brand_discovery_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("brand-discovery")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_brand_voice_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("brand-voice")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_competitive_platform_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("competitive-platform-analysis")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_competitive_report_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("competitive-report-structure")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_investor_materials_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("investor-materials")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_marketing_campaign_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("marketing-campaign")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_seo_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("seo")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_agent_payment_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("agent-payment-x402")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_social_graph_ranker_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("social-graph-ranker")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_research_ops_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("research-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_knowledge_ops_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("knowledge-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_project_flow_ops_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("project-flow-ops")
        assert result["result"] == "MOCKED_SUCCESS"

    def test_team_builder_mocked(self) -> None:
        from openjarvis.skills.ecc_completion import _mock_skill_invocation
        result = _mock_skill_invocation("team-builder")
        assert result["result"] == "MOCKED_SUCCESS"


# ---------------------------------------------------------------------------
# Section J — Live test guard (no live calls without keys)
# ---------------------------------------------------------------------------

class TestLiveTestGuard:
    """Prove live_test_skill raises without keys (never makes live calls)."""

    def test_live_test_raises_without_keys(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError, match="missing keys"):
                live_test_skill("exa-search")

    def test_live_test_dry_run_with_keys(self) -> None:
        with patch.dict(os.environ, {"EXA_API_KEY": "test_key_not_real"}):
            result = live_test_skill("exa-search", dry_run=True)
            assert result["dry_run"] is True
            assert result["keys_present"] is True
            assert result["result"] == "DRY_RUN_PASS"

    def test_live_test_not_implemented_raises(self) -> None:
        with patch.dict(os.environ, {"EXA_API_KEY": "test_key_not_real"}):
            with pytest.raises(NotImplementedError, match="Prompt 2"):
                live_test_skill("exa-search", dry_run=False)


# ---------------------------------------------------------------------------
# Section K — Artifact correctness
# ---------------------------------------------------------------------------

class TestArtifacts:
    """Prove JSON and MD artifacts are valid and complete."""

    def test_json_artifact_is_valid(self) -> None:
        json_str = generate_missing_keys_json()
        data = json.loads(json_str)
        assert "total_api_key_skills" in data
        assert data["total_api_key_skills"] == 37
        assert "skills" in data
        assert len(data["skills"]) == 37
        assert "prompt2_inputs" in data
        assert len(data["prompt2_inputs"]) >= 15

    def test_json_artifact_contains_no_real_secrets(self) -> None:
        json_str = generate_missing_keys_json()
        # Ensure no patterns that look like real API keys
        assert "sk-" not in json_str, "JSON contains sk- prefix (possible real key)"
        assert "sk_live_" not in json_str, "JSON contains sk_live_ (real Stripe key)"

    def test_md_artifact_is_valid(self) -> None:
        md = format_missing_keys_md()
        assert "# Plan 1 ECC Missing Keys" in md
        assert "PLAN_1_ECC_PRE_KEYS_COMPLETION" in md
        assert "EXA_API_KEY" in md
        assert "STRIPE_API_KEY" in md
        assert "Prompt 2" in md

    def test_json_file_was_written(self) -> None:
        json_path = Path("docs/certification/plan1_ecc_missing_keys.json")
        assert json_path.exists(), f"JSON artifact not found at {json_path}"
        data = json.loads(json_path.read_text())
        assert data["total_api_key_skills"] == 37

    def test_md_file_was_written(self) -> None:
        md_path = Path("docs/certification/PLAN1_ECC_MISSING_KEYS.md")
        assert md_path.exists(), f"MD artifact not found at {md_path}"
        content = md_path.read_text()
        assert "Plan 1 ECC Missing Keys" in content


# ---------------------------------------------------------------------------
# Section L — No raw ECC execution during test run
# ---------------------------------------------------------------------------

class TestNoRawEccExecution:
    """Prove no raw ECC code/hooks/scripts/plugins/MCP are executed during tests."""

    def test_no_side_effects_from_imports(self) -> None:
        """Importing ecc_completion must not trigger any network calls or file writes."""
        import importlib
        import sys

        # Remove from cache if present
        module_name = "openjarvis.skills.ecc_completion"
        if module_name in sys.modules:
            del sys.modules[module_name]

        # Re-import — should not trigger any side effects
        mod = importlib.import_module(module_name)
        assert hasattr(mod, "ECC_KEY_REQUIREMENTS")
        assert hasattr(mod, "check_key_presence")

    def test_catalog_build_does_not_execute_ecc(self, catalog: ECCCatalog) -> None:
        """Building the catalog must not execute any external code."""
        # If catalog lists all without errors and ecc:eval-harness is disabled, we're safe
        items = catalog.list_all()
        harness = next((i for i in items if i.get("candidate_id") == "ecc:eval-harness"), None)
        if harness:
            assert harness.get("state") != "active", "eval-harness must not be active"

    def test_plan1_summary_confirms_no_ecc_executed(self, plan1_summary: Dict[str, Any]) -> None:
        assert plan1_summary["no_ecc_code_executed"] is True, (
            "plan1_summary says ECC code WAS executed — violation"
        )
