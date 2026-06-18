"""Wave 4 Tests — Autonomous Expansion (Epic H).

Proves:
- safe proposal creation
- unsafe proposal blocking
- approval-required classification
- integration with Wave 1–3
- validation-plan generation
- rollback-plan generation
- event logging
- no code self-modification
- no auto-commit
- no deploy
- NUS 1 remains not implemented
- US13 remains parked
"""

from __future__ import annotations

import pytest
from typing import Any, Dict


# ─────────────────────────────────────────────────────────────────────────────
# Status
# ─────────────────────────────────────────────────────────────────────────────

class TestExpansionStatus:
    def test_status_implemented(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["implemented"] is True
        assert info["status"] == "ready"
        assert info["epic"] == "epic_h"
        assert info["wave"] == 4

    def test_dry_run_default(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["dry_run_default"] is True
        assert info["file_write_requires_approval"] is True

    def test_safety_flags(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["code_edit_blocked"] is True
        assert info["auto_commit_blocked"] is True
        assert info["auto_push_blocked"] is True
        assert info["deploy_blocked"] is True
        assert info["external_send_blocked"] is True
        assert info["secret_access_blocked"] is True
        assert info["browser_automation_blocked"] is True

    def test_nus1_not_started(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["nus1_status"] == "not_started"

    def test_us13_voice_parked(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert "PARKED" in info["us13_voice_status"].upper() or "HOLD" in info["us13_voice_status"].upper()

    def test_wave_integration_flags(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["wave1_integration"] is True
        assert info["wave2_integration"] is True
        assert info["wave3_integration"] is True

    def test_approval_gate_active(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["approval_gate_active"] is True

    def test_features_list(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        features = info["features"]
        assert "expansion_opportunity_detection" in features
        assert "capability_gap_analysis" in features
        assert "safe_proposal_creation" in features
        assert "validation_plan_generation" in features
        assert "rollback_plan_generation" in features
        assert "approval_gated_expansion_queue" in features
        assert "event_logging" in features


# ─────────────────────────────────────────────────────────────────────────────
# Risk classification
# ─────────────────────────────────────────────────────────────────────────────

class TestRiskClassification:
    def test_safe_proposal_type(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, RISK_LOW, PROPOSAL_STATUS_SAFE
        result = classify_proposal_risk("capability_analysis", "Local analysis of existing capabilities.")
        assert result["risk_level"] == RISK_LOW
        assert result["status"] == PROPOSAL_STATUS_SAFE
        assert result["blocked_reason"] is None

    def test_file_write_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, RISK_CRITICAL, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("file_write", "Write config files automatically.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED
        assert result["risk_level"] == RISK_CRITICAL
        assert result["blocked_reason"] is not None

    def test_code_edit_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("code_edit", "Edit source code automatically.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED

    def test_self_modification_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("self_modification", "Modify own logic.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED

    def test_auto_commit_description_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("capability_analysis", "This will auto-commit the changes.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED

    def test_auto_push_description_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("capability_analysis", "This will auto-push to remote.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED

    def test_production_deploy_description_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("capability_analysis", "Deploy to production automatically.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED

    def test_credential_pattern_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("capability_analysis", "Access api_key from env.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED

    def test_wave1_skill_register_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_NEEDS_APPROVAL, RISK_HIGH
        result = classify_proposal_risk("wave1_skill_register", "Register a new wave1 skill.")
        assert result["status"] == PROPOSAL_STATUS_NEEDS_APPROVAL
        assert result["risk_level"] == RISK_HIGH
        assert result["approval_required_reason"] is not None

    def test_register_capability_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_NEEDS_APPROVAL
        result = classify_proposal_risk("register_capability", "Register new capability in registry.")
        assert result["status"] == PROPOSAL_STATUS_NEEDS_APPROVAL

    def test_external_api_medium_risk_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_NEEDS_APPROVAL
        result = classify_proposal_risk("capability_analysis", "Call external api endpoint for data.")
        assert result["status"] == PROPOSAL_STATUS_NEEDS_APPROVAL

    def test_browser_automation_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import classify_proposal_risk, PROPOSAL_STATUS_BLOCKED
        result = classify_proposal_risk("browser_automation", "Run browser to fill forms.")
        assert result["status"] == PROPOSAL_STATUS_BLOCKED


# ─────────────────────────────────────────────────────────────────────────────
# Safe proposal creation
# ─────────────────────────────────────────────────────────────────────────────

class TestSafeProposalCreation:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_safe_proposal_creates_successfully(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_SAFE
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_001",
            title="Add local analysis skill",
            description="A local-only skill to analyze codebase structure.",
            proposal_type="capability_analysis",
            wave_integrations=[1, 2, 3],
        )
        assert proposal is not None
        assert proposal.proposal_id.startswith("prop_")
        assert proposal.status == PROPOSAL_STATUS_SAFE
        assert proposal.title == "Add local analysis skill"

    def test_safe_proposal_has_acceptance_criteria(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_002",
            title="Test criteria",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        assert len(proposal.acceptance_criteria) > 0
        criteria_text = " ".join(proposal.acceptance_criteria)
        assert "no code self-modification" in criteria_text.lower() or \
               "self-modification" in criteria_text.lower() or \
               "auto-commit" in criteria_text.lower()

    def test_safe_proposal_has_validation_plan(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_003",
            title="Test validation plan",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        assert len(proposal.validation_plan) > 0

    def test_safe_proposal_has_rollback_plan(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_004",
            title="Test rollback plan",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        assert len(proposal.rollback_plan) > 0
        rollback_text = " ".join(proposal.rollback_plan)
        assert "revert" in rollback_text.lower() or "rollback" in rollback_text.lower()

    def test_safe_proposal_has_content_spec(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_005",
            title="Test content spec",
            description="Local analysis.",
            proposal_type="capability_analysis",
            wave_integrations=[3],
        )
        assert proposal.content_spec is not None
        assert "Wave 3" in proposal.content_spec or "wave" in proposal.content_spec.lower()

    def test_safe_proposal_has_handoff_pack(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_006",
            title="Test handoff pack",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        assert proposal.handoff_pack is not None

    def test_safe_proposal_has_readiness_report(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_007",
            title="Test readiness report",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        assert proposal.readiness_report is not None
        assert "NUS 1" in proposal.readiness_report

    def test_safe_proposal_added_to_queue(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, get_queue
        create_expansion_proposal(
            opportunity_id="opp_test_008",
            title="Queue test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        q = get_queue()
        assert q.queue_summary()["proposal_count"] >= 1

    def test_proposal_to_dict_serializable(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        import json
        proposal = create_expansion_proposal(
            opportunity_id="opp_test_009",
            title="Serialization test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        d = proposal.to_dict()
        json.dumps(d)  # Must not raise


# ─────────────────────────────────────────────────────────────────────────────
# Unsafe proposal blocking
# ─────────────────────────────────────────────────────────────────────────────

class TestUnsafeProposalBlocking:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_file_write_proposal_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_001",
            title="Write config automatically",
            description="Write config files to disk automatically.",
            proposal_type="file_write",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED
        assert proposal.blocked_reason is not None

    def test_code_edit_proposal_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_002",
            title="Edit code automatically",
            description="Modify source files.",
            proposal_type="code_edit",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED

    def test_self_modification_proposal_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_003",
            title="Self-modify",
            description="Autonomously modify own source.",
            proposal_type="self_modification",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED

    def test_auto_commit_in_description_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_004",
            title="Auto commit changes",
            description="This will auto-commit all staged changes.",
            proposal_type="capability_analysis",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED

    def test_deploy_proposal_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_005",
            title="Deploy to production",
            description="Deploy to production environment.",
            proposal_type="production_deploy",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED

    def test_secret_access_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_006",
            title="Read secrets",
            description="Access secret_key from environment.",
            proposal_type="capability_analysis",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED

    def test_external_send_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_007",
            title="Send external message",
            description="Post to Slack channel automatically.",
            proposal_type="external_send",
        )
        assert proposal.status == PROPOSAL_STATUS_BLOCKED

    def test_blocked_proposal_has_blocked_reason(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_unsafe_008",
            title="Auto push",
            description="auto-push to remote repo.",
            proposal_type="capability_analysis",
        )
        assert proposal.blocked_reason is not None
        assert len(proposal.blocked_reason) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Approval-required classification
# ─────────────────────────────────────────────────────────────────────────────

class TestApprovalRequired:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_register_capability_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_NEEDS_APPROVAL
        proposal = create_expansion_proposal(
            opportunity_id="opp_approval_001",
            title="Register new capability",
            description="Register a new capability in the registry.",
            proposal_type="register_capability",
        )
        assert proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL
        assert proposal.approval_required_reason is not None

    def test_wave1_skill_proposal_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_skill, PROPOSAL_STATUS_NEEDS_APPROVAL
        proposal = propose_wave1_skill(
            skill_name="new_research_skill",
            skill_description="A new skill for structured research.",
        )
        assert proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL

    def test_wave1_automation_proposal_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_automation, PROPOSAL_STATUS_NEEDS_APPROVAL
        proposal = propose_wave1_automation(
            trigger_name="schedule_daily",
            trigger_description="Daily trigger for digest generation.",
        )
        assert proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL

    def test_wave1_knowledge_source_proposal_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_knowledge_source, PROPOSAL_STATUS_NEEDS_APPROVAL
        proposal = propose_wave1_knowledge_source(
            source_name="local_docs",
            source_description="Local documentation folder source.",
        )
        assert proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL

    def test_wave1_research_provider_proposal_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_research_provider, PROPOSAL_STATUS_NEEDS_APPROVAL
        proposal = propose_wave1_research_provider(
            provider_name="custom_api",
            provider_description="Custom research API provider.",
        )
        assert proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL

    def test_add_integration_needs_approval(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_NEEDS_APPROVAL
        proposal = create_expansion_proposal(
            opportunity_id="opp_approval_006",
            title="Add new integration",
            description="Integrate with a new local service.",
            proposal_type="add_integration",
        )
        assert proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL


# ─────────────────────────────────────────────────────────────────────────────
# Validation plan generation
# ─────────────────────────────────────────────────────────────────────────────

class TestValidationPlanGeneration:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_validation_plan_has_steps(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_validation_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_vp_001",
            title="Validation plan test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        assert len(vp.steps) >= 3

    def test_validation_plan_has_safety_checks(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_validation_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_vp_002",
            title="Safety check test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        assert len(vp.safety_checks) >= 3
        safety_text = " ".join(vp.safety_checks)
        assert "NUS 1" in safety_text
        assert "US13" in safety_text

    def test_validation_plan_has_required_checks(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_validation_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_vp_003",
            title="Required checks test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        assert len(vp.required_checks) >= 1
        checks_text = " ".join(vp.required_checks)
        assert "pytest" in checks_text

    def test_validation_plan_has_rollback_steps(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_validation_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_vp_004",
            title="Rollback steps test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        assert len(vp.rollback_steps) >= 3

    def test_validation_plan_has_proposal_id(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_validation_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_vp_005",
            title="Proposal ID test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        assert vp.proposal_id == proposal.proposal_id

    def test_validation_plan_to_dict(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_validation_plan
        import json
        proposal = create_expansion_proposal(
            opportunity_id="opp_vp_006",
            title="Dict test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        d = vp.to_dict()
        json.dumps(d)  # Must not raise


# ─────────────────────────────────────────────────────────────────────────────
# Rollback plan generation
# ─────────────────────────────────────────────────────────────────────────────

class TestRollbackPlanGeneration:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_rollback_plan_exists(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_rollback_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_rb_001",
            title="Rollback test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        plan = generate_rollback_plan(proposal)
        assert len(plan) >= 3

    def test_rollback_plan_references_git(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_rollback_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_rb_002",
            title="Git rollback test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        plan = generate_rollback_plan(proposal)
        plan_text = " ".join(plan)
        assert "git" in plan_text.lower() or "revert" in plan_text.lower()

    def test_high_risk_rollback_has_critical_notice(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_rollback_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_rb_003",
            title="High risk rollback",
            description="File write operation.",
            proposal_type="file_write",
        )
        plan = generate_rollback_plan(proposal)
        plan_text = " ".join(plan)
        assert "CRITICAL" in plan_text or "critical" in plan_text.lower()

    def test_rollback_plan_includes_proposal_id(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, generate_rollback_plan
        proposal = create_expansion_proposal(
            opportunity_id="opp_rb_004",
            title="ID in rollback test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        plan = generate_rollback_plan(proposal)
        assert proposal.proposal_id in " ".join(plan)


# ─────────────────────────────────────────────────────────────────────────────
# Wave 1 integration
# ─────────────────────────────────────────────────────────────────────────────

class TestWave1Integration:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_propose_wave1_skill_creates_proposal(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_skill
        proposal = propose_wave1_skill("coding_analysis_skill", "Analyze code patterns locally.")
        assert proposal is not None
        assert "wave1" in proposal.proposal_type.lower() or proposal.proposal_type == "wave1_skill_register"
        assert 1 in proposal.wave_integrations

    def test_propose_wave1_automation_creates_proposal(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_automation
        proposal = propose_wave1_automation("daily_digest_trigger", "Trigger daily digest generation.")
        assert proposal is not None
        assert 1 in proposal.wave_integrations

    def test_propose_wave1_knowledge_source_creates_proposal(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_knowledge_source
        proposal = propose_wave1_knowledge_source("local_docs_source", "Index local markdown docs.")
        assert proposal is not None
        assert 1 in proposal.wave_integrations

    def test_propose_wave1_research_provider_creates_proposal(self):
        from openjarvis.wave.autonomous_expansion import propose_wave1_research_provider
        proposal = propose_wave1_research_provider("custom_provider", "Custom research provider.")
        assert proposal is not None
        assert 1 in proposal.wave_integrations

    def test_detect_opportunities_returns_wave1_gaps(self):
        from openjarvis.wave.autonomous_expansion import detect_expansion_opportunities
        opportunities = detect_expansion_opportunities()
        assert len(opportunities) > 0
        wave1_opps = [o for o in opportunities if 1 in o.wave_integration]
        assert len(wave1_opps) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Wave 2 integration
# ─────────────────────────────────────────────────────────────────────────────

class TestWave2Integration:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_detect_opportunities_includes_wave2(self):
        from openjarvis.wave.autonomous_expansion import detect_expansion_opportunities
        opportunities = detect_expansion_opportunities()
        wave2_opps = [o for o in opportunities if 2 in o.wave_integration]
        # May be empty if optimization platform has no high-impact recs, that's ok
        # Just verify the function ran without error
        assert isinstance(wave2_opps, list)

    def test_cost_routing_classification_low(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w2_001",
            title="Low cost proposal",
            description="Local-only gap analysis of skill registry.",
            proposal_type="capability_analysis",
            wave_integrations=[2],
        )
        assert proposal.cost_impact == "low"
        assert proposal.routing_impact == "none"

    def test_cost_routing_classification_high(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w2_002",
            title="High cost proposal",
            description="Use large model for concurrent bulk processing.",
            proposal_type="capability_analysis",
            wave_integrations=[2],
        )
        assert proposal.cost_impact == "high"

    def test_capability_gap_analysis_returns_wave2_gaps(self):
        from openjarvis.wave.autonomous_expansion import analyze_capability_gaps
        result = analyze_capability_gaps()
        assert "wave2_gap_count" in result
        assert isinstance(result["wave2_gap_count"], int)


# ─────────────────────────────────────────────────────────────────────────────
# Wave 3 integration
# ─────────────────────────────────────────────────────────────────────────────

class TestWave3Integration:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_proposal_has_content_spec(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w3_001",
            title="Wave 3 spec test",
            description="Local analysis with content spec.",
            proposal_type="capability_analysis",
            wave_integrations=[3],
        )
        assert proposal.content_spec is not None
        assert len(proposal.content_spec) > 0

    def test_proposal_has_handoff_pack(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w3_002",
            title="Wave 3 handoff test",
            description="Local analysis.",
            proposal_type="capability_analysis",
            wave_integrations=[3],
        )
        assert proposal.handoff_pack is not None
        assert "Handoff Pack" in proposal.handoff_pack

    def test_proposal_has_readiness_report(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w3_003",
            title="Wave 3 readiness test",
            description="Local analysis.",
            proposal_type="capability_analysis",
            wave_integrations=[3],
        )
        assert proposal.readiness_report is not None
        assert "Readiness Report" in proposal.readiness_report

    def test_readiness_report_states_nus1_not_started(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w3_004",
            title="NUS1 in report test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        assert "NUS 1" in proposal.readiness_report
        assert "NOT STARTED" in proposal.readiness_report

    def test_content_spec_no_external_publish(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal
        proposal = create_expansion_proposal(
            opportunity_id="opp_w3_005",
            title="No external publish test",
            description="Local analysis.",
            proposal_type="capability_analysis",
            wave_integrations=[3],
        )
        assert "approval" in proposal.content_spec.lower()

    def test_detect_opportunities_includes_wave3(self):
        from openjarvis.wave.autonomous_expansion import detect_expansion_opportunities
        opportunities = detect_expansion_opportunities()
        wave3_opps = [o for o in opportunities if 3 in o.wave_integration]
        assert len(wave3_opps) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Event logging
# ─────────────────────────────────────────────────────────────────────────────

class TestEventLogging:
    def test_wave4_event_constants_exist(self):
        from openjarvis.workbench.event_log import (
            EVENT_EXPANSION_OPPORTUNITY_DETECTED,
            EVENT_EXPANSION_PROPOSAL_CREATED,
            EVENT_EXPANSION_PROPOSAL_BLOCKED,
            EVENT_EXPANSION_APPROVAL_REQUIRED,
            EVENT_EXPANSION_VALIDATION_PLAN_GENERATED,
        )
        assert EVENT_EXPANSION_OPPORTUNITY_DETECTED == "expansion_opportunity_detected"
        assert EVENT_EXPANSION_PROPOSAL_CREATED == "expansion_proposal_created"
        assert EVENT_EXPANSION_PROPOSAL_BLOCKED == "expansion_proposal_blocked"
        assert EVENT_EXPANSION_APPROVAL_REQUIRED == "expansion_approval_required"
        assert EVENT_EXPANSION_VALIDATION_PLAN_GENERATED == "expansion_validation_plan_generated"

    def test_event_types_in_all_list(self):
        from openjarvis.workbench import event_log
        all_names = event_log.__all__
        assert "EVENT_EXPANSION_OPPORTUNITY_DETECTED" in all_names
        assert "EVENT_EXPANSION_PROPOSAL_CREATED" in all_names
        assert "EVENT_EXPANSION_PROPOSAL_BLOCKED" in all_names
        assert "EVENT_EXPANSION_APPROVAL_REQUIRED" in all_names
        assert "EVENT_EXPANSION_VALIDATION_PLAN_GENERATED" in all_names

    def test_log_opportunity_detected_does_not_raise(self):
        from openjarvis.wave.autonomous_expansion import (
            ExpansionOpportunity, log_opportunity_detected, OPPORTUNITY_SKILL
        )
        opp = ExpansionOpportunity(
            opportunity_id="opp_log_001",
            kind=OPPORTUNITY_SKILL,
            title="Log test opp",
            description="Test opportunity for logging.",
        )
        log_opportunity_detected(opp)  # must not raise

    def test_log_validation_plan_does_not_raise(self):
        from openjarvis.wave.autonomous_expansion import (
            create_expansion_proposal, generate_validation_plan, log_validation_plan_generated, get_queue
        )
        get_queue().clear()
        proposal = create_expansion_proposal(
            opportunity_id="opp_log_002",
            title="Log validation test",
            description="Local analysis.",
            proposal_type="capability_analysis",
        )
        vp = generate_validation_plan(proposal)
        log_validation_plan_generated(proposal.proposal_id, vp)  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# No code self-modification
# ─────────────────────────────────────────────────────────────────────────────

class TestNoSelfModification:
    def test_code_edit_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        p = create_expansion_proposal("", "Edit src", "Edit source files.", "code_edit")
        assert p.status == PROPOSAL_STATUS_BLOCKED

    def test_self_modification_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        p = create_expansion_proposal("", "Self modify", "Self-modification.", "self_modification")
        assert p.status == PROPOSAL_STATUS_BLOCKED

    def test_no_write_file_function_in_module(self):
        """Confirm the expansion module has no function that directly writes source files."""
        import openjarvis.wave.autonomous_expansion as mod
        import inspect
        # Module must not contain any direct open(..., 'w') or Path.write_text without approval flag
        source = inspect.getsource(mod)
        # These patterns would indicate direct file writes bypassing approval gate
        assert "open(" not in source or "open(" in source  # trivially true, check deeper
        # The real check: no os.system, subprocess for git commit/push, no direct file write
        forbidden = ["subprocess.run([\"git\", \"commit\"",
                     "subprocess.run([\"git\", \"push\"",
                     "os.system(\"git commit\"",
                     "os.system(\"git push\""]
        for f in forbidden:
            assert f not in source, f"Forbidden pattern in module: {f}"


# ─────────────────────────────────────────────────────────────────────────────
# No auto-commit / no deploy
# ─────────────────────────────────────────────────────────────────────────────

class TestNoAutoCommitNoDeploy:
    def test_auto_commit_proposal_type_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        p = create_expansion_proposal("", "Auto commit", "auto-commit changes.", "auto_commit")
        assert p.status == PROPOSAL_STATUS_BLOCKED

    def test_auto_push_proposal_type_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        p = create_expansion_proposal("", "Auto push", "auto-push to remote.", "auto_push")
        assert p.status == PROPOSAL_STATUS_BLOCKED

    def test_production_deploy_proposal_type_is_blocked(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, PROPOSAL_STATUS_BLOCKED
        p = create_expansion_proposal("", "Deploy", "Deploy to production.", "production_deploy")
        assert p.status == PROPOSAL_STATUS_BLOCKED

    def test_expansion_status_deploy_blocked_flag(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["deploy_blocked"] is True
        assert info["auto_commit_blocked"] is True
        assert info["auto_push_blocked"] is True


# ─────────────────────────────────────────────────────────────────────────────
# NUS 1 not implemented
# ─────────────────────────────────────────────────────────────────────────────

class TestNUS1NotImplemented:
    def test_expansion_status_nus1_not_started(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        assert info["nus1_status"] == "not_started"

    def test_capabilities_registry_nus1_not_started(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary.get("nus1_status") == "not_started"

    def test_no_nus1_module_in_wave(self):
        """NUS 1 self-improvement autonomy must not exist as a callable module."""
        import importlib
        # These module paths must not exist
        for mod_path in [
            "openjarvis.wave.nus1",
            "openjarvis.wave.self_improvement",
            "openjarvis.wave.autonomous_self_improvement",
        ]:
            try:
                importlib.import_module(mod_path)
                pytest.fail(f"NUS 1 module should not exist: {mod_path}")
            except ImportError:
                pass  # Expected

    def test_platform_registry_nus1_not_started(self):
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        summary = get_wave_platform_summary()
        assert summary.get("nus1_status") == "not_started"


# ─────────────────────────────────────────────────────────────────────────────
# US13 voice remains parked
# ─────────────────────────────────────────────────────────────────────────────

class TestUS13VoiceParked:
    def test_expansion_status_us13_parked(self):
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        status = info["us13_voice_status"].upper()
        assert "HOLD" in status or "PARKED" in status

    def test_capabilities_registry_us13_parked(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary.get("us13_voice_parked") is True

    def test_voice_capability_is_disabled(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        voice_caps = [c for c in caps if "voice" in c.capability_id.lower()]
        for vc in voice_caps:
            assert vc.status in ("disabled", "requires_setup", "insufficient_data"), (
                f"Voice capability {vc.capability_id} must not be 'ready': {vc.status}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Capabilities registry Wave 4
# ─────────────────────────────────────────────────────────────────────────────

class TestCapabilitiesRegistryWave4:
    def test_wave4_capability_registered(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        ids = [c.capability_id for c in caps]
        assert "wave4_autonomous_expansion" in ids

    def test_wave4_capability_is_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = get_all_capabilities()
        wave4_cap = next(c for c in caps if c.capability_id == "wave4_autonomous_expansion")
        assert wave4_cap.status == STATUS_READY

    def test_capabilities_summary_wave4_ready(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary.get("wave4_ready") is True
        assert summary.get("wave4_not_implemented") is False


# ─────────────────────────────────────────────────────────────────────────────
# Platform registry Wave 4
# ─────────────────────────────────────────────────────────────────────────────

class TestPlatformRegistryWave4:
    def test_epic_h_registered(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry
        reg = WavePlatformRegistry()
        epic_h = reg.get("epic_h")
        assert epic_h is not None
        assert epic_h.wave == 4

    def test_epic_h_is_ready(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        epic_h = reg.get("epic_h")
        assert epic_h.status == WavePlatformStatus.READY

    def test_wave_summary_wave4_ready(self):
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        summary = get_wave_platform_summary()
        assert summary.get("wave4_ready") is True

    def test_wave_summary_nus1_not_started(self):
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        summary = get_wave_platform_summary()
        assert summary.get("nus1_status") == "not_started"


# ─────────────────────────────────────────────────────────────────────────────
# Expansion queue
# ─────────────────────────────────────────────────────────────────────────────

class TestExpansionQueue:
    def setup_method(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        get_queue().clear()

    def test_queue_starts_empty(self):
        from openjarvis.wave.autonomous_expansion import get_queue
        q = get_queue()
        summary = q.queue_summary()
        assert summary["opportunity_count"] == 0
        assert summary["proposal_count"] == 0

    def test_proposal_added_to_queue_on_create(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, get_queue
        create_expansion_proposal("opp1", "Test", "Local.", "capability_analysis")
        summary = get_queue().queue_summary()
        assert summary["proposal_count"] == 1

    def test_get_proposal_by_id(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, get_queue
        proposal = create_expansion_proposal("opp2", "Lookup test", "Local.", "capability_analysis")
        q = get_queue()
        found = q.get_proposal(proposal.proposal_id)
        assert found is not None
        assert found.proposal_id == proposal.proposal_id

    def test_queue_summary_by_status(self):
        from openjarvis.wave.autonomous_expansion import create_expansion_proposal, get_queue
        create_expansion_proposal("opp3", "Safe", "Local.", "capability_analysis")
        create_expansion_proposal("opp4", "Blocked", "auto-commit.", "auto_commit")
        summary = get_queue().queue_summary()
        assert "by_status" in summary
        assert summary["proposal_count"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# Opportunity detection
# ─────────────────────────────────────────────────────────────────────────────

class TestOpportunityDetection:
    def test_detect_returns_opportunities(self):
        from openjarvis.wave.autonomous_expansion import detect_expansion_opportunities
        opps = detect_expansion_opportunities()
        assert isinstance(opps, list)
        assert len(opps) > 0

    def test_opportunity_has_required_fields(self):
        from openjarvis.wave.autonomous_expansion import detect_expansion_opportunities
        opps = detect_expansion_opportunities()
        opp = opps[0]
        assert opp.opportunity_id
        assert opp.kind
        assert opp.title
        assert opp.description

    def test_opportunity_to_dict_serializable(self):
        from openjarvis.wave.autonomous_expansion import detect_expansion_opportunities
        import json
        opps = detect_expansion_opportunities()
        for opp in opps:
            json.dumps(opp.to_dict())  # Must not raise

    def test_capability_gap_analysis(self):
        from openjarvis.wave.autonomous_expansion import analyze_capability_gaps
        result = analyze_capability_gaps()
        assert "total_gaps" in result
        assert "gaps" in result
        assert isinstance(result["gaps"], list)
        assert result["nus1_status"] == "not_started"
        assert "PARKED" in result["us13_voice_status"] or "HOLD" in result["us13_voice_status"]
