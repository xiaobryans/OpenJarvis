"""Wave 2 Tests — Professional Intelligence.

Epic E: Optimization Platform (optimization_platform.py)
Epic F: Professional Skill Packs (professional_skill_packs.py)
"""

from __future__ import annotations

import pytest
from typing import Any, Dict


# ─────────────────────────────────────────────────────────────────────────────
# EPIC E — Optimization Platform
# ─────────────────────────────────────────────────────────────────────────────


class TestOptimizationPlatformStatus:
    def test_status_implemented(self):
        from openjarvis.wave.optimization_platform import get_optimization_platform_status
        info = get_optimization_platform_status()
        assert info["implemented"] is True
        assert info["status"] == "ready"
        assert info["epic"] == "epic_e"
        assert info["wave"] == 2

    def test_auto_modify_disabled(self):
        from openjarvis.wave.optimization_platform import get_optimization_platform_status
        info = get_optimization_platform_status()
        assert info["auto_modify_disabled"] is True
        assert info["auto_commit_disabled"] is True
        assert info["auto_deploy_disabled"] is True

    def test_approval_gated_actions_present(self):
        from openjarvis.wave.optimization_platform import get_optimization_platform_status
        info = get_optimization_platform_status()
        gated = info["approval_gated_actions"]
        assert "deploy" in gated
        assert "file_write" in gated
        assert "git_commit" in gated
        assert "self_upgrade" in gated


class TestScorecardGeneration:
    def test_scorecard_generates(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        assert sc.scorecard_id
        assert 0.0 <= sc.overall_score <= 1.0

    def test_scorecard_has_all_sub_scores(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        assert 0.0 <= sc.cost_score <= 1.0
        assert 0.0 <= sc.routing_score <= 1.0
        assert 0.0 <= sc.validation_score <= 1.0
        assert 0.0 <= sc.failure_score <= 1.0
        assert 0.0 <= sc.readiness_score <= 1.0

    def test_scorecard_has_recommendations(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        assert len(sc.recommendations) > 0

    def test_scorecard_has_summary(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        assert sc.summary

    def test_scorecard_to_dict(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        d = sc.to_dict()
        assert "overall_score" in d
        assert "recommendations" in d
        assert "scorecard_id" in d
        assert "summary" in d

    def test_scorecard_generated_at_set(self):
        import time
        from openjarvis.wave.optimization_platform import generate_scorecard
        before = time.time()
        sc = generate_scorecard()
        after = time.time()
        assert before <= sc.generated_at <= after


class TestRecommendationGeneration:
    def test_cost_recommendations_present(self):
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, REC_CATEGORY_COST
        )
        sc = generate_scorecard()
        cost_recs = [r for r in sc.recommendations if r.category == REC_CATEGORY_COST]
        assert len(cost_recs) >= 1

    def test_routing_recommendations_present(self):
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, REC_CATEGORY_ROUTING
        )
        sc = generate_scorecard()
        routing_recs = [r for r in sc.recommendations if r.category == REC_CATEGORY_ROUTING]
        assert len(routing_recs) >= 1

    def test_validation_recommendations_present(self):
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, REC_CATEGORY_VALIDATION
        )
        sc = generate_scorecard()
        val_recs = [r for r in sc.recommendations if r.category == REC_CATEGORY_VALIDATION]
        assert len(val_recs) >= 1

    def test_failure_detection_recommendations_present(self):
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, REC_CATEGORY_FAILURE
        )
        sc = generate_scorecard()
        fail_recs = [r for r in sc.recommendations if r.category == REC_CATEGORY_FAILURE]
        assert len(fail_recs) >= 1

    def test_readiness_recommendations_present(self):
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, REC_CATEGORY_READINESS
        )
        sc = generate_scorecard()
        ready_recs = [r for r in sc.recommendations if r.category == REC_CATEGORY_READINESS]
        assert len(ready_recs) >= 1

    def test_approval_gated_deploy_actions(self):
        """Recommendations with deploy/file_write actions must be approval_required."""
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        for rec in sc.recommendations:
            if rec.action in ("deploy", "file_write", "git_commit", "self_upgrade"):
                assert rec.approval_required, (
                    f"Recommendation '{rec.rec_id}' with action='{rec.action}' "
                    "must be approval_required=True"
                )

    def test_get_recommendations_by_category(self):
        from openjarvis.wave.optimization_platform import (
            get_recommendations_by_category, REC_CATEGORY_COST
        )
        recs = get_recommendations_by_category(REC_CATEGORY_COST)
        assert isinstance(recs, list)
        for r in recs:
            assert r.category == REC_CATEGORY_COST

    def test_recommendation_levels_valid(self):
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, REC_LEVEL_INFO, REC_LEVEL_WARN, REC_LEVEL_CRITICAL
        )
        valid_levels = {REC_LEVEL_INFO, REC_LEVEL_WARN, REC_LEVEL_CRITICAL}
        sc = generate_scorecard()
        for rec in sc.recommendations:
            assert rec.level in valid_levels, f"Invalid level: {rec.level}"


class TestCostAnalysis:
    def test_zero_cost_baseline(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard(ledger_summary={"total_cost_usd": 0.0, "entry_count": 0})
        assert sc.cost_score == 1.0

    def test_high_cost_reduces_score(self):
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard(ledger_summary={"total_cost_usd": 10.0, "entry_count": 100})
        assert sc.cost_score < 1.0

    def test_moderate_cost_recommendation(self):
        from openjarvis.wave.optimization_platform import generate_scorecard, REC_CATEGORY_COST
        sc = generate_scorecard(ledger_summary={"total_cost_usd": 2.0, "entry_count": 50})
        cost_recs = [r for r in sc.recommendations if r.category == REC_CATEGORY_COST]
        assert any("cost" in r.detail.lower() or "cost" in r.title.lower() for r in cost_recs)


class TestNoAutonomousSelfModification:
    def test_scorecard_does_not_write_files(self):
        """Scorecard generation must not modify any files."""
        import os
        import time
        from openjarvis.wave.optimization_platform import generate_scorecard
        # Check a known source file's mtime doesn't change
        target = "src/openjarvis/wave/optimization_platform.py"
        if os.path.exists(target):
            before_mtime = os.path.getmtime(target)
        sc = generate_scorecard()
        if os.path.exists(target):
            after_mtime = os.path.getmtime(target)
            assert before_mtime == after_mtime, "Scorecard must not modify source files"

    def test_no_git_commit_in_scorecard(self):
        """generate_scorecard must not trigger git operations."""
        from openjarvis.wave.optimization_platform import generate_scorecard
        from unittest.mock import patch
        with patch("subprocess.run") as mock_run:
            sc = generate_scorecard()
        mock_run.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# EPIC F — Professional Skill Packs
# ─────────────────────────────────────────────────────────────────────────────


class TestSkillPackRegistry:
    def test_builtin_packs_registered(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        packs = reg.list_packs()
        assert len(packs) >= 5

    def test_coding_workflow_pack_exists(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        pack = reg.get("coding_workflow")
        assert pack is not None
        assert pack.risk_level == "low"

    def test_research_workflow_pack_exists(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        assert reg.get("research_workflow") is not None

    def test_project_operations_pack_exists(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        assert reg.get("project_operations") is not None

    def test_release_readiness_pack_exists(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        assert reg.get("package_release_readiness") is not None

    def test_safety_review_pack_exists(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        assert reg.get("safety_review") is not None

    def test_deploy_pack_hard_gated(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, PACK_POLICY_HARD_GATE
        reg = SkillPackRegistry()
        deploy = reg.get("deploy_release")
        assert deploy is not None
        assert deploy.is_hard_gate()
        assert deploy.risk_level == "critical"

    def test_register_custom_pack(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, SkillPackManifest
        reg = SkillPackRegistry()
        pack = SkillPackManifest(
            pack_id="test_custom_pack",
            name="Test Custom Pack",
            version="1.0.0",
            purpose="Test",
            included_skill_ids=["list_skills"],
            risk_level="low",
        )
        result = reg.register(pack)
        assert result["ok"]
        assert reg.get("test_custom_pack") is not None

    def test_list_enabled_only_returns_enabled(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, PACK_STATUS_ENABLED
        reg = SkillPackRegistry()
        enabled = reg.list_enabled()
        for p in enabled:
            assert p.status == PACK_STATUS_ENABLED

    def test_status(self):
        from openjarvis.wave.professional_skill_packs import get_professional_skill_packs_status
        info = get_professional_skill_packs_status()
        assert info["implemented"]
        assert info["status"] == "ready"
        assert info["wave"] == 2
        assert info["pack_count"] >= 5
        assert info["approval_gate_enforced"]
        assert info["hard_gate_enforced"]
        assert info["wave1_integration"]


class TestSkillPackValidation:
    def test_valid_safe_pack(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, validate_skill_pack
        reg = SkillPackRegistry()
        pack = reg.get("coding_workflow")
        result = validate_skill_pack(pack)
        assert result.valid
        assert not result.hard_gate
        assert not result.approval_required

    def test_deploy_pack_invalid_hard_gate(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, validate_skill_pack
        reg = SkillPackRegistry()
        pack = reg.get("deploy_release")
        result = validate_skill_pack(pack)
        assert not result.valid
        assert result.hard_gate

    def test_missing_pack_id_invalid(self):
        from openjarvis.wave.professional_skill_packs import SkillPackManifest, validate_skill_pack
        pack = SkillPackManifest(
            pack_id="",
            name="No ID Pack",
            version="1.0.0",
            purpose="Test",
        )
        result = validate_skill_pack(pack)
        assert not result.valid
        assert any("pack_id" in i for i in result.issues)

    def test_high_risk_pack_requires_approval(self):
        from openjarvis.wave.professional_skill_packs import (
            SkillPackManifest, validate_skill_pack, PACK_POLICY_REQUIRES_APPROVAL
        )
        pack = SkillPackManifest(
            pack_id="high_risk_test",
            name="High Risk Test",
            version="1.0.0",
            purpose="High risk",
            risk_level="high",
            approval_policy=PACK_POLICY_REQUIRES_APPROVAL,
        )
        result = validate_skill_pack(pack)
        assert result.valid  # no violations — just approval required
        assert result.approval_required

    def test_browser_tag_requires_approval(self):
        from openjarvis.wave.professional_skill_packs import SkillPackManifest, validate_skill_pack
        pack = SkillPackManifest(
            pack_id="browser_pack",
            name="Browser Pack",
            version="1.0.0",
            purpose="Browser automation",
            tags=["browser"],
            risk_level="medium",
        )
        result = validate_skill_pack(pack)
        assert result.valid
        assert result.approval_required


class TestSkillPackExecution:
    def test_safe_coding_pack_executes(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("coding_workflow", registry=reg)
        assert result.ok, f"Expected ok=True, error={result.error}"
        assert len(result.skills_run) > 0

    def test_safe_research_pack_executes(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("research_workflow", registry=reg)
        assert result.ok, f"error={result.error}"

    def test_safe_project_ops_pack_executes(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("project_operations", registry=reg)
        assert result.ok, f"error={result.error}"

    def test_deploy_pack_blocked(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("deploy_release", registry=reg)
        assert not result.ok
        assert result.blocked

    def test_unknown_pack_returns_error(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("nonexistent_pack_xyz", registry=reg)
        assert not result.ok
        assert "not found" in result.error.lower()

    def test_high_risk_pack_blocked_without_approval(self):
        from openjarvis.wave.professional_skill_packs import (
            SkillPackRegistry, SkillPackManifest, run_skill_pack, PACK_POLICY_REQUIRES_APPROVAL
        )
        reg = SkillPackRegistry()
        pack = SkillPackManifest(
            pack_id="high_risk_exec_test",
            name="High Risk Exec",
            version="1.0.0",
            purpose="High risk execution test",
            risk_level="high",
            approval_policy=PACK_POLICY_REQUIRES_APPROVAL,
        )
        reg.register(pack)
        result = run_skill_pack("high_risk_exec_test", registry=reg)
        assert not result.ok
        assert result.approval_required

    def test_execution_returns_output_dict(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("coding_workflow", registry=reg)
        assert result.ok
        assert isinstance(result.output, dict)

    def test_event_logged_on_execution(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("coding_workflow", registry=reg)
        assert isinstance(result.event_id, str)

    def test_event_logged_on_block(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("deploy_release", registry=reg)
        assert isinstance(result.event_id, str)


class TestSkillPackEnabling:
    def test_enable_safe_pack_ok(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, enable_skill_pack
        reg = SkillPackRegistry()
        result = enable_skill_pack("coding_workflow", registry=reg)
        assert result["ok"]

    def test_enable_hard_gate_pack_blocked(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, enable_skill_pack
        reg = SkillPackRegistry()
        result = enable_skill_pack("deploy_release", registry=reg)
        assert not result["ok"]
        assert result.get("blocked")

    def test_enable_nonexistent_pack_fails(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, enable_skill_pack
        reg = SkillPackRegistry()
        result = enable_skill_pack("does_not_exist_xyz", registry=reg)
        assert not result["ok"]


class TestWave2Integration:
    def test_wave1_skills_accessible_from_pack(self):
        """Coding pack should successfully call list_skills (Wave 1 skill)."""
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("coding_workflow", registry=reg)
        assert result.ok
        assert "list_skills" in result.skills_run

    def test_project_ops_pack_uses_wave2_capability(self):
        """Project ops pack uses list_capabilities — bridges Wave 1 and Wave 2."""
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        result = run_skill_pack("project_operations", registry=reg)
        assert result.ok
        # Wave 2 capability ID must be in capabilities output
        if isinstance(result.output, dict):
            caps_output = result.output.get("list_capabilities", {})
            if isinstance(caps_output, dict):
                cap_ids = [c.get("capability_id") for c in caps_output.get("capabilities", [])]
                # Wave 2 capabilities should appear
                assert any("wave2" in str(cid) for cid in cap_ids), (
                    f"Wave 2 capabilities not found in output: {cap_ids}"
                )

    def test_wave2_capabilities_in_registry(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        cap_ids = [c["capability_id"] for c in summary["capabilities"]]
        assert "wave2_optimization_platform" in cap_ids
        assert "wave2_professional_skill_packs" in cap_ids

    def test_wave2_capabilities_show_ready(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        caps = {c["capability_id"]: c["status"] for c in summary["capabilities"]}
        assert caps["wave2_optimization_platform"] == "ready"
        assert caps["wave2_professional_skill_packs"] == "ready"

    def test_wave4_in_registry(self):
        """Wave 4 capability is now registered (supervised expansion, local/founder V1)."""
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        cap_ids = [c["capability_id"] for c in summary["capabilities"]]
        assert "wave4_autonomous_expansion" in cap_ids, "Wave 4 capability must be registered"

    def test_wave2_platform_registry_shows_ready(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        wave2_items = reg.get_by_wave(2)
        assert len(wave2_items) == 2
        for item in wave2_items:
            assert item.status in (WavePlatformStatus.READY, WavePlatformStatus.SCAFFOLDED), (
                f"Wave 2 item {item.epic_id} should be ready/scaffolded, got {item.status}"
            )

    def test_wave4_now_implemented(self):
        """Wave 4 Epic H is now implemented (supervised expansion, local/founder V1)."""
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        for item in reg.get_by_wave(4):
            assert item.status in (WavePlatformStatus.READY, WavePlatformStatus.SCAFFOLDED), (
                f"Wave 4 item {item.epic_id} should be ready/scaffolded, got {item.status}"
            )

    def test_us13_voice_still_parked(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        caps = {c["capability_id"]: c["status"] for c in summary["capabilities"]}
        if "hands_free_voice" in caps:
            assert caps["hands_free_voice"] in ("disabled", "not_implemented", "requires_setup")


# ─────────────────────────────────────────────────────────────────────────────
# Safety Gate Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestWave2SafetyGates:
    def test_no_autonomous_code_modification_in_scorecard(self):
        """generate_scorecard must not call any file-write or git operations."""
        from openjarvis.wave.optimization_platform import generate_scorecard
        from unittest.mock import patch, MagicMock
        # Patch open() to detect unauthorized writes
        with patch("builtins.open", MagicMock(side_effect=lambda *a, **kw: open(*a, **kw) if "r" in str(a) else (_ for _ in ()).throw(AssertionError("Scorecard should not write files")))):
            try:
                sc = generate_scorecard()
                # If we get here without file writes, good
            except AssertionError as e:
                if "Scorecard should not write files" in str(e):
                    pytest.fail(str(e))

    def test_deploy_pack_hard_gate_cannot_be_bypassed(self):
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry, run_skill_pack
        reg = SkillPackRegistry()
        # Even with context provided, deploy pack must be blocked
        result = run_skill_pack("deploy_release", registry=reg, context={"bypass": True})
        assert not result.ok
        assert result.blocked

    def test_optimization_safe_actions_no_approval_needed(self):
        """Safe recommendation actions (review, log, report) must NOT be approval_required."""
        from openjarvis.wave.optimization_platform import (
            generate_scorecard, _SAFE_RECOMMENDATION_ACTIONS
        )
        sc = generate_scorecard()
        for rec in sc.recommendations:
            if rec.action in _SAFE_RECOMMENDATION_ACTIONS:
                assert not rec.approval_required, (
                    f"Safe action '{rec.action}' should not require approval"
                )

    def test_nus1_not_implemented(self):
        """NUS 1 (auto-upgrade) must not be implemented in Wave 2."""
        try:
            import openjarvis.wave.autonomous_upgrade  # noqa
            pytest.fail("NUS 1 auto-upgrade module should not exist in Wave 2")
        except ImportError:
            pass  # Expected — not implemented

    def test_wave3_content_studio_module_exists(self):
        """Wave 3 content media studio module must exist (now implemented)."""
        from openjarvis.wave.content_media_studio import get_content_studio_status  # noqa
        info = get_content_studio_status()
        assert info["implemented"] is True

    def test_wave4_autonomous_expansion_module_exists(self):
        """Wave 4 autonomous expansion module must exist (now implemented)."""
        from openjarvis.wave.autonomous_expansion import get_expansion_status  # noqa
        info = get_expansion_status()
        assert info["implemented"] is True
        assert info["nus1_status"] == "not_started"
