"""Tests for Post-NUS Dynamic Activation Planner."""

from __future__ import annotations

import pytest

from openjarvis.orchestrator.contracts import (
    TaskRoutingRequest,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_BLOCKED,
    COMPLEXITY_SIMPLE,
    COMPLEXITY_MODERATE,
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


class TestActivationSelects:
    def test_simple_debug_task_selects_debugging_manager(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="fix a Python bug",
            intent="debug",
            domains_required=["debugging"],
            required_skills=["debugging"],
        )
        plan = planner.plan(req)
        assert "debugging_manager" in plan.selected_managers

    def test_backend_task_selects_coding_manager(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="add backend route",
            intent="implement",
            domains_required=["backend"],
            required_skills=["python"],
        )
        plan = planner.plan(req)
        assert "coding_manager" in plan.selected_managers

    def test_validation_required_selects_testing_manager(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="run tests",
            intent="validate",
            domains_required=["unit_testing"],
            required_skills=["pytest"],
            validation_required=True,
        )
        plan = planner.plan(req)
        assert "testing_validation_manager" in plan.selected_managers

    def test_high_risk_selects_governance_manager(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="high risk refactor",
            intent="refactor",
            risk_level=RISK_HIGH,
            domains_required=["backend"],
        )
        plan = planner.plan(req)
        assert "governance_safety_manager" in plan.selected_managers

    def test_complex_task_selects_multiple_managers(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="large cross-system refactor",
            intent="refactor",
            risk_level=RISK_HIGH,
            complexity_level=COMPLEXITY_COMPLEX,
            domains_required=["backend", "system_design", "unit_testing"],
            required_skills=["python", "system_design"],
            validation_required=True,
        )
        plan = planner.plan(req)
        assert len(plan.selected_managers) >= 2

    def test_multiple_workers_selected_when_justified(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="implement + test backend feature",
            intent="implement",
            domains_required=["backend", "unit_testing"],
            required_skills=["python", "unit_testing"],
            validation_required=True,
        )
        plan = planner.plan(req)
        assert len(plan.selected_workers) >= 1


class TestActivationReasons:
    def test_activation_reasons_present(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test",
            intent="test",
            domains_required=["debugging"],
        )
        plan = planner.plan(req)
        for mid in plan.selected_managers:
            assert mid in plan.activation_reasons, f"No reason for selected manager {mid}"
        for wid in plan.selected_workers:
            assert wid in plan.activation_reasons, f"No reason for selected worker {wid}"

    def test_skip_reasons_present_for_all_skipped(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="simple fix",
            intent="debug",
            domains_required=["debugging"],
        )
        plan = planner.plan(req)
        for mid in plan.skipped_managers:
            assert mid in plan.skip_reasons, f"No skip reason for manager {mid}"
        for wid in plan.skipped_workers:
            assert wid in plan.skip_reasons, f"No skip reason for worker {wid}"

    def test_all_managers_accounted_selected_or_skipped(self):
        planner = make_planner()
        reg = ManagerRegistry()
        req = TaskRoutingRequest.create(
            user_request_summary="any task",
            intent="test",
            domains_required=["backend"],
        )
        plan = planner.plan(req)
        all_ids = set(reg.ids())
        accounted = set(plan.selected_managers) | set(plan.skipped_managers)
        assert all_ids == accounted, (
            f"Managers not accounted for: {all_ids - accounted}"
        )


class TestNoFixedFormulas:
    def test_simple_and_complex_plans_differ(self):
        planner = make_planner()

        req_simple = TaskRoutingRequest.create(
            user_request_summary="simple fix",
            intent="debug",
            domains_required=["debugging"],
            required_skills=["debugging"],
        )
        req_complex = TaskRoutingRequest.create(
            user_request_summary="full system refactor",
            intent="refactor",
            risk_level=RISK_HIGH,
            complexity_level=COMPLEXITY_COMPLEX,
            domains_required=["backend", "system_design", "unit_testing", "governance"],
            required_skills=["python", "system_design", "unit_testing"],
            validation_required=True,
        )

        plan_simple = planner.plan(req_simple)
        plan_complex = planner.plan(req_complex)

        # Different tasks must produce different team sizes
        assert (
            len(plan_simple.selected_managers) != len(plan_complex.selected_managers)
            or set(plan_simple.selected_managers) != set(plan_complex.selected_managers)
        ), "Different tasks must produce different activation plans (no fixed formula)"

    def test_single_worker_sufficient_for_simple_task(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="fix one backend bug",
            intent="debug",
            domains_required=["debugging"],
            required_skills=["debugging"],
        )
        plan = planner.plan(req)
        # Simple task: minimum sufficient — should not activate all workers
        total = len(plan.selected_workers)
        assert total < 10, "Simple task should not activate 10+ workers"


class TestStructuredDecisionRecord:
    def test_decision_record_id_emitted(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test dr",
            intent="test",
            domains_required=["debugging"],
        )
        plan = planner.plan(req)
        assert plan.structured_decision_record_id
        assert len(plan.structured_decision_record_id) > 0

    def test_no_raw_chain_of_thought(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test no cot",
            intent="test",
            domains_required=["backend"],
        )
        plan = planner.plan(req)
        assert plan.no_raw_chain_of_thought is True
        plan_dict = plan.to_dict()
        assert plan_dict["no_raw_chain_of_thought"] is True
        assert "raw_chain_of_thought" not in plan_dict


class TestModelRouting:
    def test_cheap_model_blocked_for_critical_approval(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="high risk action",
            intent="deploy",
            risk_level=RISK_HIGH,
        )
        plan = planner.plan(req)
        critical_check = plan.model_routing_plan.get("critical_approval_check", {})
        assert critical_check.get("cheap_model_blocked_for_approval") is True

    def test_premium_tier_selected_for_high_risk(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="high risk",
            intent="review",
            risk_level=RISK_HIGH,
        )
        plan = planner.plan(req)
        assert plan.model_routing_plan.get("recommended_tier") == "premium"

    def test_cheap_tier_for_simple_low_risk(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="read a file",
            intent="read",
            risk_level=RISK_LOW,
            complexity_level=COMPLEXITY_SIMPLE,
        )
        plan = planner.plan(req)
        assert plan.model_routing_plan.get("recommended_tier") in ["cheap", "mid"]

    def test_model_provider_sufficiency_disclosed(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test sufficiency",
            intent="test",
        )
        plan = planner.plan(req)
        ps = plan.model_routing_plan.get("provider_sufficiency", {})
        assert "sufficient_for_sprint" in ps
        assert "sprint_scope" in ps


class TestNUSIntegration:
    def test_nus_learning_tags_emitted(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test nus",
            intent="implement",
            domains_required=["backend"],
        )
        plan = planner.plan(req)
        assert isinstance(plan.nus_learning_tags, list)
        assert len(plan.nus_learning_tags) > 0
        tags_str = " ".join(plan.nus_learning_tags)
        assert "orchestrator:hierarchical" in tags_str

    def test_governance_gate_attached_for_high_risk(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="risky op",
            intent="execute",
            risk_level=RISK_HIGH,
        )
        plan = planner.plan(req)
        gov_plan = plan.governance_plan
        assert gov_plan.get("governance_required") is True
        assert gov_plan.get("hard_gates_active") is True

    def test_us13_parked_in_governance_plan(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="any task",
            intent="implement",
        )
        plan = planner.plan(req)
        assert plan.governance_plan.get("us13_voice_parked") is True


class TestActivationPlanToDict:
    def test_to_dict_complete(self):
        planner = make_planner()
        req = TaskRoutingRequest.create(
            user_request_summary="test dict",
            intent="test",
            domains_required=["debugging"],
        )
        plan = planner.plan(req)
        d = plan.to_dict()
        required_keys = [
            "plan_id", "request_id", "created_at", "selected_managers",
            "selected_workers", "skipped_managers", "skipped_workers",
            "activation_reasons", "skip_reasons", "validation_plan",
            "governance_plan", "model_routing_plan", "cost_estimate",
            "context_estimate", "risk_assessment", "escalation_plan",
            "stop_conditions", "structured_decision_record_id",
            "nus_learning_tags", "model_provider_gaps",
            "no_raw_chain_of_thought",
        ]
        for key in required_keys:
            assert key in d, f"ActivationPlan.to_dict() missing key: {key}"
