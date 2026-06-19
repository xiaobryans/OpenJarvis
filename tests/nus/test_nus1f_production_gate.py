"""NUS 1F — Production Gate tests.

Tests:
  - Production gate dry-run only
  - No real deploy
  - No auto-push
  - No auto-merge
  - No secret access
  - Always-blocked categories (deploy, push, merge, secret)
  - Preconditions tracked
  - Outcome is always dry_run or blocked (never approved in NUS 1F)
  - Structured decision records emitted
  - US13 remains parked
"""

import pytest


class TestProductionGateBasic:
    def _gate(self):
        from openjarvis.nus.production_gate import ProductionGate
        return ProductionGate()

    def test_status_production_disabled(self):
        gate = self._gate()
        s = gate.get_status()
        assert s["production_autonomy_enabled"] is False
        assert s["nus1f_execution_mode"] == "blocked_dry_run_only"
        assert s["real_deploy_blocked"] is True
        assert s["auto_push_blocked"] is True
        assert s["auto_merge_blocked"] is True

    def test_staging_deploy_dry_run(self):
        from openjarvis.nus.production_gate import create_production_gate_request
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="staging",
        )
        result = gate.evaluate(req)
        assert result.is_dry_run is True
        assert result.is_real_execution is False
        assert result.to_dict()["nus1f_production_autonomy_enabled"] is False

    def test_production_deploy_always_blocked(self):
        from openjarvis.nus.production_gate import (
            create_production_gate_request, GATE_OUTCOME_BLOCKED,
        )
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="production_deploy", environment="production",
        )
        result = gate.evaluate(req)
        assert result.outcome == GATE_OUTCOME_BLOCKED
        assert not result.is_real_execution

    def test_auto_push_always_blocked(self):
        from openjarvis.nus.production_gate import (
            create_production_gate_request, GATE_OUTCOME_BLOCKED,
        )
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="auto_push", environment="local",
        )
        result = gate.evaluate(req)
        assert result.outcome == GATE_OUTCOME_BLOCKED

    def test_auto_merge_always_blocked(self):
        from openjarvis.nus.production_gate import (
            create_production_gate_request, GATE_OUTCOME_BLOCKED,
        )
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="auto_merge", environment="local",
        )
        result = gate.evaluate(req)
        assert result.outcome == GATE_OUTCOME_BLOCKED

    def test_secret_access_always_blocked(self):
        from openjarvis.nus.production_gate import (
            create_production_gate_request, GATE_OUTCOME_BLOCKED,
        )
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="secret_access", environment="local",
        )
        result = gate.evaluate(req)
        assert result.outcome == GATE_OUTCOME_BLOCKED

    def test_merge_to_main_always_blocked(self):
        from openjarvis.nus.production_gate import (
            create_production_gate_request, GATE_OUTCOME_BLOCKED,
        )
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="merge_to_main", environment="local",
        )
        result = gate.evaluate(req)
        assert result.outcome == GATE_OUTCOME_BLOCKED


class TestProductionGatePreconditions:
    def _gate(self):
        from openjarvis.nus.production_gate import ProductionGate
        return ProductionGate()

    def test_missing_preconditions_tracked(self):
        from openjarvis.nus.production_gate import create_production_gate_request, GATE_OUTCOME_PRECONDITIONS_FAILED
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="staging",
            # All preconditions missing
        )
        result = gate.evaluate(req)
        assert "rollback_plan_missing" in result.preconditions_failed
        assert "validation_plan_missing" in result.preconditions_failed
        assert "secret_leakage_not_checked" in result.preconditions_failed
        assert result.outcome == GATE_OUTCOME_PRECONDITIONS_FAILED
        assert result.is_dry_run is True  # even failed is dry-run

    def test_met_preconditions_tracked(self):
        from openjarvis.nus.production_gate import create_production_gate_request, GATE_OUTCOME_DRY_RUN_ONLY
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="staging",
            rollback_plan={"steps": ["revert"]},
            validation_plan={"checks": ["smoke_test"]},
            audit_log_id="audit-123",
            risk_review={"approved": True},
            secret_leakage_checked=True,
            kill_switch_available=True,
            owner_authorization="founder_token_xyz",
        )
        result = gate.evaluate(req)
        assert "rollback_plan_present" in result.preconditions_met
        assert "validation_plan_present" in result.preconditions_met
        assert "secret_leakage_checked" in result.preconditions_met
        # Even with all preconditions met, still dry-run in NUS 1F
        assert result.is_dry_run is True
        assert not result.is_real_execution

    def test_production_environment_fails_precondition(self):
        from openjarvis.nus.production_gate import create_production_gate_request
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="production",
        )
        result = gate.evaluate(req)
        assert "production_environment_not_safe_for_nus1f" in result.preconditions_failed

    def test_staging_environment_meets_precondition(self):
        from openjarvis.nus.production_gate import create_production_gate_request
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="staging",
        )
        result = gate.evaluate(req)
        assert "non_production_environment" in result.preconditions_met


class TestProductionGateDecisionRecords:
    def _gate(self):
        from openjarvis.nus.production_gate import ProductionGate
        return ProductionGate()

    def test_decision_record_emitted(self):
        from openjarvis.nus.production_gate import create_production_gate_request
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="staging",
        )
        result = gate.evaluate(req)
        dr = result.structured_decision_record
        assert isinstance(dr, dict)
        assert "record_id" in dr
        assert dr.get("no_raw_chain_of_thought") is True

    def test_blocked_decision_record_emitted(self):
        from openjarvis.nus.production_gate import create_production_gate_request
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="production_deploy", environment="production",
        )
        result = gate.evaluate(req)
        dr = result.structured_decision_record
        assert dr["decision"] == "blocked"
        assert dr.get("no_raw_chain_of_thought") is True

    def test_to_dict_confirms_safety(self):
        from openjarvis.nus.production_gate import create_production_gate_request
        gate = self._gate()
        req = create_production_gate_request(
            owner="founder", action_type="staging_deploy", environment="staging",
        )
        result = gate.evaluate(req)
        d = result.to_dict()
        assert d["no_real_deploy"] is True
        assert d["no_auto_push"] is True
        assert d["no_auto_merge"] is True
        assert d["nus1f_production_autonomy_enabled"] is False


class TestProductionGateSingleton:
    def test_singleton_works(self):
        from openjarvis.nus.production_gate import get_production_gate
        g1 = get_production_gate()
        g2 = get_production_gate()
        assert g1 is g2

    def test_us13_parked(self):
        from openjarvis.nus.production_gate import get_production_gate
        gate = get_production_gate()
        s = gate.get_status()
        assert s["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
