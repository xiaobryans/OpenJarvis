"""Tests for Post-NUS Manager Registry."""

from __future__ import annotations

import pytest

from openjarvis.orchestrator.contracts import (
    ManagerContract,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    STATUS_ACTIVE,
)
from openjarvis.orchestrator.manager_registry import ManagerRegistry, get_manager_registry


class TestManagerRegistryLoads:
    def test_registry_loads(self):
        reg = ManagerRegistry()
        assert reg.count() > 0

    def test_manager_count_matches_initial(self):
        reg = ManagerRegistry()
        assert reg.count() == 17

    def test_no_duplicate_ids(self):
        reg = ManagerRegistry()
        assert not reg.has_duplicate_ids()

    def test_all_ids_unique(self):
        reg = ManagerRegistry()
        ids = reg.ids()
        assert len(ids) == len(set(ids))

    def test_known_managers_present(self):
        reg = ManagerRegistry()
        ids = reg.ids()
        expected = [
            "coding_manager", "architecture_manager", "testing_validation_manager",
            "governance_safety_manager", "nus_learning_manager", "cost_routing_manager",
        ]
        for eid in expected:
            assert eid in ids, f"Expected manager '{eid}' not found"

    def test_manager_contracts_valid(self):
        reg = ManagerRegistry()
        errors = {mid: errs for mid, errs in reg.validate_all().items() if errs}
        assert not errors, f"Manager contract errors: {errors}"

    def test_get_manager_by_id(self):
        reg = ManagerRegistry()
        m = reg.get("coding_manager")
        assert m is not None
        assert m.name == "Coding Manager"
        assert m.department == "Engineering"

    def test_list_active_returns_active_only(self):
        reg = ManagerRegistry()
        active = reg.list_active()
        for m in active:
            assert m.status == STATUS_ACTIVE

    def test_list_by_domain(self):
        reg = ManagerRegistry()
        backend_managers = reg.list_by_domain("backend")
        assert any(m.manager_id == "coding_manager" for m in backend_managers)

    def test_get_missing_returns_none(self):
        reg = ManagerRegistry()
        assert reg.get("nonexistent_manager_xyz") is None

    def test_to_dict(self):
        reg = ManagerRegistry()
        d = reg.to_dict()
        assert "count" in d
        assert "manager_ids" in d
        assert "managers" in d
        assert d["count"] == reg.count()


class TestManagerRegistryDuplicatePrevention:
    def test_duplicate_id_raises(self):
        reg = ManagerRegistry()
        existing = reg.list_all()[0]
        dup = ManagerContract(
            manager_id=existing.manager_id,
            name="Duplicate",
            department="Test",
            responsibility="duplicate test",
            input_contract={},
            output_contract={},
            skill_domains=[],
            worker_pool=[],
            allowed_action_types=[],
            blocked_action_types=[],
            model_pool=["mid"],
            risk_ceiling=RISK_LOW,
            tool_policy={},
            validation_policy={},
            escalation_policy={},
            telemetry_policy={},
            nus_learning_hooks={},
        )
        with pytest.raises(ValueError, match="Duplicate manager_id"):
            reg.register(dup)

    def test_valid_new_manager_registers(self):
        reg = ManagerRegistry()
        before = reg.count()
        new = ManagerContract(
            manager_id="test_new_manager_unique_1",
            name="Test New Manager",
            department="Test",
            responsibility="Test responsibility",
            input_contract={"format": "TaskRoutingRequest"},
            output_contract={"format": "ActivationPlan_partial"},
            skill_domains=["test_domain"],
            worker_pool=[],
            allowed_action_types=["local_read"],
            blocked_action_types=["production_deploy"],
            model_pool=["mid"],
            risk_ceiling=RISK_MEDIUM,
            tool_policy={"allowed_by_default": False},
            validation_policy={"require_structured_output": True},
            escalation_policy={"escalate_to": "cos_gm"},
            telemetry_policy={"emit_events": True},
            nus_learning_hooks={"learning_enabled": True},
        )
        reg.register(new)
        assert reg.count() == before + 1
        assert reg.get("test_new_manager_unique_1") is not None


class TestManagerContractRequiredFields:
    def test_required_fields_present(self):
        reg = ManagerRegistry()
        for m in reg.list_all():
            assert m.manager_id
            assert m.name
            assert m.department
            assert m.responsibility
            assert isinstance(m.input_contract, dict)
            assert isinstance(m.output_contract, dict)
            assert isinstance(m.skill_domains, list)
            assert isinstance(m.worker_pool, list)
            assert isinstance(m.allowed_action_types, list)
            assert isinstance(m.blocked_action_types, list)
            assert isinstance(m.model_pool, list)
            assert m.risk_ceiling
            assert isinstance(m.tool_policy, dict)
            assert isinstance(m.validation_policy, dict)
            assert isinstance(m.escalation_policy, dict)
            assert isinstance(m.telemetry_policy, dict)
            assert isinstance(m.nus_learning_hooks, dict)
            assert m.status

    def test_dangerous_actions_blocked(self):
        reg = ManagerRegistry()
        blocked_forever = [
            "production_deploy", "auto_push", "auto_merge",
            "send_external_message", "access_secrets",
        ]
        for m in reg.list_all():
            for action in blocked_forever:
                assert action in m.blocked_action_types, (
                    f"Manager '{m.manager_id}' must block '{action}'"
                )

    def test_singleton_returns_same_instance(self):
        reg1 = get_manager_registry()
        reg2 = get_manager_registry()
        assert reg1 is reg2


class TestFutureSyntheticManager:
    def test_synthetic_manager_via_metadata(self):
        """Future managers work through metadata — no code changes required."""
        m = ManagerContract(
            manager_id="future_ai_ethics_manager",
            name="AI Ethics Manager",
            department="Governance",
            responsibility="Reviews AI ethics and bias in model outputs",
            input_contract={"format": "TaskRoutingRequest"},
            output_contract={"format": "ActivationPlan_partial"},
            skill_domains=["ai_ethics", "bias_detection"],
            worker_pool=["ethics_worker"],
            allowed_action_types=["local_read", "analysis"],
            blocked_action_types=["production_deploy", "auto_push"],
            model_pool=["premium"],
            risk_ceiling=RISK_HIGH,
            tool_policy={"allowed_by_default": False},
            validation_policy={"require_structured_output": True},
            escalation_policy={"escalate_to": "cos_gm"},
            telemetry_policy={"emit_events": True},
            nus_learning_hooks={"learning_enabled": True},
            metadata={"added_in_sprint": "future", "experimental": True},
        )
        errors = m.validate()
        assert not errors, f"Synthetic manager must be valid: {errors}"
        reg = ManagerRegistry()
        reg.register(m)
        assert reg.get("future_ai_ethics_manager") is not None
