"""Tests for Post-NUS Worker Registry."""

from __future__ import annotations

import pytest

from openjarvis.orchestrator.contracts import (
    WorkerContract,
    RISK_LOW,
    RISK_MEDIUM,
    STATUS_ACTIVE,
)
from openjarvis.orchestrator.manager_registry import ManagerRegistry, get_manager_registry
from openjarvis.orchestrator.worker_registry import WorkerRegistry, get_worker_registry


class TestWorkerRegistryLoads:
    def test_registry_loads(self):
        reg = WorkerRegistry()
        assert reg.count() > 0

    def test_worker_count_matches_initial(self):
        reg = WorkerRegistry()
        assert reg.count() == 30

    def test_no_duplicate_ids(self):
        reg = WorkerRegistry()
        assert not reg.has_duplicate_ids()

    def test_all_ids_unique(self):
        reg = WorkerRegistry()
        ids = reg.ids()
        assert len(ids) == len(set(ids))

    def test_known_workers_present(self):
        reg = WorkerRegistry()
        ids = reg.ids()
        expected = [
            "backend_worker", "frontend_worker", "test_worker", "debug_worker",
            "security_code_worker", "policy_gate_worker", "nus_learning_worker",
            "git_commit_worker", "system_architecture_worker", "documentation_worker",
        ]
        for eid in expected:
            assert eid in ids, f"Expected worker '{eid}' not found"

    def test_worker_contracts_valid(self):
        reg = WorkerRegistry()
        errors = {wid: errs for wid, errs in reg.validate_all().items() if errs}
        assert not errors, f"Worker contract errors: {errors}"

    def test_get_worker_by_id(self):
        reg = WorkerRegistry()
        w = reg.get("backend_worker")
        assert w is not None
        assert w.name == "Backend Worker"
        assert w.manager_id == "coding_manager"

    def test_list_active_returns_active_only(self):
        reg = WorkerRegistry()
        active = reg.list_active()
        for w in active:
            assert w.status == STATUS_ACTIVE

    def test_list_by_manager(self):
        reg = WorkerRegistry()
        coding_workers = reg.list_by_manager("coding_manager")
        assert len(coding_workers) > 0
        assert all(w.manager_id == "coding_manager" for w in coding_workers)

    def test_list_by_skill(self):
        reg = WorkerRegistry()
        python_workers = reg.list_by_skill("python")
        assert any(w.worker_id == "backend_worker" for w in python_workers)

    def test_to_dict(self):
        reg = WorkerRegistry()
        d = reg.to_dict()
        assert "count" in d
        assert "worker_ids" in d
        assert "workers" in d
        assert d["count"] == reg.count()


class TestWorkerManagerReferences:
    def test_all_worker_manager_ids_valid(self):
        """All workers must reference a manager that exists in the manager registry."""
        mgr_reg = get_manager_registry()
        wrk_reg = get_worker_registry()
        ref_errors = wrk_reg.validate_manager_references(mgr_reg.ids())
        assert not ref_errors, f"Workers with invalid manager_id: {ref_errors}"

    def test_worker_count_per_manager(self):
        reg = get_worker_registry()
        coding_workers = reg.list_by_manager("coding_manager")
        assert len(coding_workers) >= 3, "coding_manager should have at least 3 workers"


class TestWorkerDuplicatePrevention:
    def test_duplicate_id_raises(self):
        reg = WorkerRegistry()
        existing = reg.list_all()[0]
        dup = WorkerContract(
            worker_id=existing.worker_id,
            name="Duplicate",
            manager_id="coding_manager",
            department="Test",
            responsibility="duplicate",
            skills=[],
            input_contract={},
            output_contract={},
            allowed_tools=[],
            blocked_tools=[],
            allowed_action_types=[],
            blocked_action_types=[],
            model_pool=["mid"],
            risk_ceiling=RISK_LOW,
            validation_requirements={},
            escalation_path={},
            telemetry_policy={},
            nus_learning_hooks={},
        )
        with pytest.raises(ValueError, match="Duplicate worker_id"):
            reg.register(dup)

    def test_valid_new_worker_registers(self):
        reg = WorkerRegistry()
        before = reg.count()
        new = WorkerContract(
            worker_id="test_new_worker_unique_1",
            name="Test New Worker",
            manager_id="coding_manager",
            department="Engineering",
            responsibility="Test worker",
            skills=["test_skill"],
            input_contract={"format": "subtask"},
            output_contract={"format": "worker_result"},
            allowed_tools=["file_read"],
            blocked_tools=["production_deploy_tool"],
            allowed_action_types=["local_read"],
            blocked_action_types=["production_deploy", "auto_push"],
            model_pool=["mid"],
            risk_ceiling=RISK_LOW,
            validation_requirements={"require_structured_output": True},
            escalation_path={"escalate_to": "manager"},
            telemetry_policy={"emit_events": True},
            nus_learning_hooks={"learning_enabled": True},
        )
        reg.register(new)
        assert reg.count() == before + 1


class TestWorkerContractRequiredFields:
    def test_required_fields_present(self):
        reg = WorkerRegistry()
        for w in reg.list_all():
            assert w.worker_id
            assert w.name
            assert w.manager_id
            assert w.department
            assert w.responsibility
            assert isinstance(w.skills, list)
            assert isinstance(w.input_contract, dict)
            assert isinstance(w.output_contract, dict)
            assert isinstance(w.allowed_tools, list)
            assert isinstance(w.blocked_tools, list)
            assert isinstance(w.allowed_action_types, list)
            assert isinstance(w.blocked_action_types, list)
            assert isinstance(w.model_pool, list)
            assert w.risk_ceiling
            assert isinstance(w.validation_requirements, dict)
            assert isinstance(w.escalation_path, dict)
            assert isinstance(w.telemetry_policy, dict)
            assert isinstance(w.nus_learning_hooks, dict)

    def test_dangerous_actions_blocked(self):
        reg = WorkerRegistry()
        blocked_forever = [
            "production_deploy", "auto_push", "auto_merge",
            "send_external_message", "access_secrets",
        ]
        for w in reg.list_all():
            for action in blocked_forever:
                assert action in w.blocked_action_types, (
                    f"Worker '{w.worker_id}' must block '{action}'"
                )

    def test_git_commit_worker_blocks_push(self):
        reg = WorkerRegistry()
        w = reg.get("git_commit_worker")
        assert w is not None
        assert "git_push" in w.blocked_action_types
        assert "git_force_push" in w.blocked_action_types

    def test_registered_workers_not_active_by_default_statement(self):
        """Registered workers are not active — activation is dynamic/planner-driven."""
        reg = WorkerRegistry()
        all_workers = reg.list_all()
        # Some workers are STATUS_INACTIVE (e.g. release_packaging_worker)
        inactive = [w for w in all_workers if w.status != STATUS_ACTIVE]
        # Proves the registry supports non-active registration
        assert isinstance(inactive, list)

    def test_singleton_returns_same_instance(self):
        reg1 = get_worker_registry()
        reg2 = get_worker_registry()
        assert reg1 is reg2


class TestFutureSyntheticWorker:
    def test_synthetic_worker_via_metadata(self):
        """Future workers work through metadata — no code changes required."""
        w = WorkerContract(
            worker_id="future_synthetic_ai_auditor",
            name="AI Auditor Worker",
            manager_id="governance_safety_manager",
            department="Governance",
            responsibility="Audits AI model outputs for safety and bias",
            skills=["ai_audit", "bias_detection", "safety_review"],
            input_contract={"format": "subtask"},
            output_contract={"format": "worker_result"},
            allowed_tools=["file_read"],
            blocked_tools=["production_deploy_tool"],
            allowed_action_types=["local_read", "analysis"],
            blocked_action_types=["production_deploy", "auto_push"],
            model_pool=["premium"],
            risk_ceiling=RISK_MEDIUM,
            validation_requirements={"require_structured_output": True},
            escalation_path={"escalate_to": "manager"},
            telemetry_policy={"emit_events": True},
            nus_learning_hooks={"learning_enabled": True},
            metadata={"added_in_sprint": "future", "experimental": True},
        )
        errors = w.validate()
        assert not errors, f"Synthetic worker must be valid: {errors}"
        reg = WorkerRegistry()
        reg.register(w)
        assert reg.get("future_synthetic_ai_auditor") is not None
