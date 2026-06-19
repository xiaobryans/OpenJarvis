"""Tests for Post-NUS Orchestrator Governance, NUS Integration, and Capabilities."""

from __future__ import annotations

import pytest

from openjarvis.orchestrator.contracts import (
    TaskRoutingRequest,
    RISK_HIGH,
    RISK_BLOCKED,
    COMPLEXITY_COMPLEX,
)
from openjarvis.orchestrator.activation import DynamicActivationPlanner
from openjarvis.orchestrator.manager_registry import ManagerRegistry
from openjarvis.orchestrator.worker_registry import WorkerRegistry


def make_planner() -> DynamicActivationPlanner:
    return DynamicActivationPlanner(
        manager_registry=ManagerRegistry(),
        worker_registry=WorkerRegistry(),
    )


class TestNUSHierarchyLevels:
    def test_nus_decision_record_covers_all_levels(self):
        from openjarvis.nus.decision_record import get_decision_record_status
        status = get_decision_record_status()
        required = {"jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"}
        covered = set(status.get("nus_hierarchy_coverage", []))
        assert covered >= required, f"Missing NUS hierarchy levels: {required - covered}"

    def test_decision_record_no_raw_cot(self):
        from openjarvis.nus.decision_record import get_decision_record_status
        status = get_decision_record_status()
        assert status.get("no_raw_chain_of_thought") is True

    def test_decision_record_schema_version(self):
        from openjarvis.nus.decision_record import NUS1F_DECISION_RECORD_VERSION
        assert NUS1F_DECISION_RECORD_VERSION

    def test_build_action_decision_record_all_levels(self):
        from openjarvis.nus.decision_record import build_action_decision_record, _VALID_LEVELS
        for level in _VALID_LEVELS:
            record = build_action_decision_record(
                action_type="orchestration_test",
                decision="dry_run",
                reason=f"test_{level}",
                evidence={"test": True},
                hierarchy_level=level,
            )
            assert record.get("hierarchy_level") == level
            assert record.get("no_raw_chain_of_thought") is True
            assert "record_id" in record


class TestSafetyGates:
    def test_dangerous_actions_blocked_in_governance_plan(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="any task",
            intent="implement",
            risk_level=RISK_HIGH,
        )
        plan = planner.plan(req)
        blocked = plan.governance_plan.get("blocked_actions", [])
        for action in ["production_deploy", "auto_push", "auto_merge"]:
            assert action in blocked, f"'{action}' must be in governance blocked_actions"

    def test_stop_conditions_present(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test stop",
            intent="test",
        )
        plan = planner.plan(req)
        assert isinstance(plan.stop_conditions, list)
        assert len(plan.stop_conditions) > 0
        assert "validation_failure_after_max_retries" in plan.stop_conditions

    def test_us13_parked_in_all_plans(self):
        planner = make_planner()
        for intent in ["implement", "debug", "test", "review", "deploy"]:
            req = TaskRoutingRequest.create(
                user_request_summary=f"{intent} task",
                intent=intent,
            )
            plan = planner.plan(req)
            assert plan.governance_plan.get("us13_voice_parked") is True, (
                f"US13 must be parked in plan for intent={intent}"
            )

    def test_policy_gate_worker_for_high_risk(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="high risk op",
            intent="execute",
            risk_level=RISK_HIGH,
            domains_required=["governance"],
            required_skills=["policy_evaluation"],
        )
        plan = planner.plan(req)
        assert "policy_gate_worker" in plan.selected_workers


class TestCapabilitiesRegistered:
    def test_orchestrator_capabilities_registered(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        cap_ids = {c.capability_id for c in caps}
        required_cap_ids = {
            "post_nus_hierarchical_orchestrator",
            "post_nus_manager_registry",
            "post_nus_worker_registry",
            "post_nus_dynamic_activation",
            "post_nus_nus_company_learning",
        }
        for cap_id in required_cap_ids:
            assert cap_id in cap_ids, f"Capability '{cap_id}' not registered"

    def test_orchestrator_capability_status_truthful(self):
        from openjarvis.workbench.capabilities_registry import (
            get_all_capabilities, STATUS_READY, STATUS_NOT_IMPLEMENTED
        )
        caps = get_all_capabilities()
        orch_caps = {
            c.capability_id: c for c in caps
            if c.capability_id.startswith("post_nus_")
        }
        for cap_id, cap in orch_caps.items():
            assert cap.status in {STATUS_READY, STATUS_NOT_IMPLEMENTED}, (
                f"Capability '{cap_id}' has invalid status '{cap.status}'"
            )
            if cap.status == STATUS_READY:
                assert cap.evidence, f"READY capability '{cap_id}' must have evidence"

    def test_capabilities_summary_includes_orchestrator(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary.get("post_nus_orchestrator_status") == "ready"


class TestDoctorCheck:
    def test_doctor_check_passes(self):
        from openjarvis.doctor.checks import check_post_nus_orchestrator, CheckStatus
        result = check_post_nus_orchestrator()
        assert result.status == CheckStatus.PASS, (
            f"Doctor check failed: {result.summary}\nEvidence: {result.evidence}"
        )

    def test_doctor_check_in_all_checks(self):
        from openjarvis.doctor.checks import _ALL_CHECK_FNS, check_post_nus_orchestrator
        assert check_post_nus_orchestrator in _ALL_CHECK_FNS


class TestEventTypes:
    def test_orchestrator_event_types_exported(self):
        from openjarvis.workbench.event_log import (
            EVENT_ORCHESTRATOR_STATUS_CHECKED,
            EVENT_MANAGER_REGISTRY_LOADED,
            EVENT_WORKER_REGISTRY_LOADED,
            EVENT_ACTIVATION_PLAN_CREATED,
            EVENT_ROUTING_DRY_RUN_EVALUATED,
            EVENT_MANAGER_SELECTED,
            EVENT_WORKER_SELECTED,
            EVENT_MANAGER_SKIPPED,
            EVENT_WORKER_SKIPPED,
            EVENT_MODEL_PROVIDER_SUFFICIENCY_GAP,
            EVENT_ORCHESTRATION_DECISION_RECORD_CREATED,
            EVENT_GOVERNANCE_GATE_ATTACHED,
            EVENT_NUS_LEARNING_HOOK_ATTACHED,
        )
        assert EVENT_ORCHESTRATOR_STATUS_CHECKED == "orchestrator_status_checked"
        assert EVENT_MANAGER_REGISTRY_LOADED == "manager_registry_loaded"
        assert EVENT_WORKER_REGISTRY_LOADED == "worker_registry_loaded"
        assert EVENT_ACTIVATION_PLAN_CREATED == "activation_plan_created"
        assert EVENT_MANAGER_SELECTED == "manager_selected"
        assert EVENT_WORKER_SELECTED == "worker_selected"
        assert EVENT_MODEL_PROVIDER_SUFFICIENCY_GAP == "model_provider_sufficiency_gap"


class TestUS13Parked:
    def test_us13_voice_still_parked(self):
        """US13 voice must remain HOLD/UNSAFE/PARKED — unchanged by this sprint."""
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_NEEDS_APPROVAL
        caps = get_all_capabilities()
        voice_cap = next((c for c in caps if c.capability_id == "voice"), None)
        # voice capability should exist and NOT be STATUS_READY (it's parked/disabled)
        if voice_cap:
            assert voice_cap.status != "ready", (
                "US13 voice must NOT be ready — it remains HOLD/UNSAFE/PARKED"
            )

    def test_us13_parked_note_present(self):
        from openjarvis.workbench.capabilities_registry import US13_VOICE_PARKED_NOTE
        assert "HOLD/UNSAFE" in US13_VOICE_PARKED_NOTE
        # Note uses lowercase "parked" in backlog reference
        assert "parked" in US13_VOICE_PARKED_NOTE.lower()
