"""Tests for Phase C1-C10 — Autonomous Jarvis Ecosystem Scale Sprint.

Covers:
  C1  — Autonomous Jarvis Organization Kernel
  C2  — Long-Horizon Mission Control
  C3  — Multi-Agent Review / Governance / Arbitration
  C4  — Product / Multi-User Readiness Layer
  C5  — Plugin / Marketplace Governance Layer
  C6  — Enterprise-Grade Audit / Observability / Cost / Reliability
  C7  — Cross-Device / Cloud / Workbench Scale Control Plane
  C8  — Autonomous Business / Company OS Scale Layer
  C9  — Safety / Policy / Rollback / Simulation Framework
  C10 — Phase C Control Tower + Core OS Completion Gate
  Self-knowledge C1-C10 integration
  Phase B regression
  OMNIX non-regression
  Approval gate integrity
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures — router-level (no create_app needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def auto_org_client():
    from openjarvis.server.autonomous_org_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def mc_client():
    from openjarvis.server.mission_control_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def gov_client():
    from openjarvis.server.review_governance_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def prod_client():
    from openjarvis.server.product_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def mktgov_client():
    from openjarvis.server.marketplace_governance_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def entgov_client():
    from openjarvis.server.enterprise_governance_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def scale_client():
    from openjarvis.server.scale_control_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def company_client():
    from openjarvis.server.company_os_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def safety_client():
    from openjarvis.server.safety_simulation_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def tower_client():
    from openjarvis.server.control_tower_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def sk_client():
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# C1 — Autonomous Jarvis Organization Kernel  (1-10)
# ---------------------------------------------------------------------------

class TestC1AutonomousOrg:
    def test_01_status_returns_200(self, auto_org_client):
        res = auto_org_client.get("/v1/autonomous-org/status")
        assert res.status_code == 200

    def test_02_one_jarvis_pa_identity(self, auto_org_client):
        data = auto_org_client.get("/v1/autonomous-org/status").json()
        assert data["one_jarvis_pa_identity"] is True
        assert data["single_pa_voice"] == "Jarvis"

    def test_03_autonomous_execution_not_live(self, auto_org_client):
        data = auto_org_client.get("/v1/autonomous-org/status").json()
        assert data["autonomous_execution_live"] is False

    def test_04_omnix_not_jarvis_core(self, auto_org_client):
        data = auto_org_client.get("/v1/autonomous-org/status").json()
        assert data["omnix_is_jarvis_core"] is False

    def test_05_fake_ai_company_false(self, auto_org_client):
        data = auto_org_client.get("/v1/autonomous-org/status").json()
        assert data["fake_ai_company_running"] is False
        assert data["fake_data"] is False

    def test_06_capability_matrix_returns_200(self, auto_org_client):
        res = auto_org_client.get("/v1/autonomous-org/capability-matrix")
        assert res.status_code == 200

    def test_07_capability_matrix_one_identity(self, auto_org_client):
        data = auto_org_client.get("/v1/autonomous-org/capability-matrix").json()
        assert data["one_jarvis_pa_identity"] is True
        assert data["external_personalities_live"] is False

    def test_08_route_query_dry_run(self, auto_org_client):
        res = auto_org_client.post("/v1/autonomous-org/route-query", json={"query": "plan a mission", "context": "test"})
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["one_pa_voice"] == "Jarvis"

    def test_09_route_query_validates_empty(self, auto_org_client):
        res = auto_org_client.post("/v1/autonomous-org/route-query", json={"query": "", "context": ""})
        assert res.status_code == 422

    def test_10_no_credential_values_in_status(self, auto_org_client):
        text = str(auto_org_client.get("/v1/autonomous-org/status").json())
        for prefix in ("xoxb-", "ghp_", "AKIA", "sk-proj-"):
            assert prefix not in text


# ---------------------------------------------------------------------------
# C2 — Long-Horizon Mission Control  (11-20)
# ---------------------------------------------------------------------------

class TestC2MissionControl:
    def test_11_dashboard_returns_200(self, mc_client):
        res = mc_client.get("/v1/mission-control/dashboard")
        assert res.status_code == 200

    def test_12_unapproved_execution_false(self, mc_client):
        data = mc_client.get("/v1/mission-control/dashboard").json()
        assert data["unapproved_execution"] is False

    def test_13_fake_data_false(self, mc_client):
        data = mc_client.get("/v1/mission-control/dashboard").json()
        assert data["fake_data"] is False

    def test_14_missions_is_list(self, mc_client):
        data = mc_client.get("/v1/mission-control/dashboard").json()
        assert isinstance(data["missions"], list)

    def test_15_all_missions_approval_required(self, mc_client):
        data = mc_client.get("/v1/mission-control/dashboard").json()
        for m in data["missions"]:
            assert m.get("approval_required") is True
            assert m.get("auto_execute") is False

    def test_16_dependency_graph_returns_200_or_404(self, mc_client):
        res = mc_client.get("/v1/mission-control/missions/nonexistent-mission-xyz/dependency-graph")
        assert res.status_code in (200, 404)

    def test_17_risk_assessment_returns_200_or_404(self, mc_client):
        res = mc_client.get("/v1/mission-control/missions/nonexistent-mission-xyz/risk-assessment")
        assert res.status_code in (200, 404)

    def test_18_dry_run_next_step_no_execution(self, mc_client):
        res = mc_client.post(
            "/v1/mission-control/missions/test-mission/dry-run-next-step",
            json={"step_type": "milestone", "title": "Test Milestone", "reason": "testing"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["executed"] is False
        assert data["auto_execute"] is False
        assert data["approval_required"] is True

    def test_19_dry_run_validates_empty_fields(self, mc_client):
        res = mc_client.post(
            "/v1/mission-control/missions/test/dry-run-next-step",
            json={"step_type": "", "title": "", "reason": ""}
        )
        assert res.status_code == 422

    def test_20_mission_control_prefix_no_conflict(self, mc_client):
        # /v1/mission-control/* must be distinct from /v1/missions/* (existing route)
        res = mc_client.get("/v1/mission-control/dashboard")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# C3 — Review / Governance / Arbitration  (21-30)
# ---------------------------------------------------------------------------

class TestC3ReviewGovernance:
    def test_21_status_returns_200(self, gov_client):
        res = gov_client.get("/v1/review-governance/status")
        assert res.status_code == 200

    def test_22_approval_gates_active(self, gov_client):
        data = gov_client.get("/v1/review-governance/status").json()
        assert data["approval_gates_active"] is True

    def test_23_not_bypassing_approval_gates(self, gov_client):
        data = gov_client.get("/v1/review-governance/status").json()
        assert data["bypassing_approval_gates"] is False

    def test_24_no_fake_certifications(self, gov_client):
        data = gov_client.get("/v1/review-governance/status").json()
        assert data["fake_legal_certification"] is False
        assert data["fake_financial_certification"] is False
        assert data["fake_data"] is False

    def test_25_decisions_returns_200(self, gov_client):
        res = gov_client.get("/v1/review-governance/decisions")
        assert res.status_code == 200

    def test_26_decisions_fake_data_false(self, gov_client):
        data = gov_client.get("/v1/review-governance/decisions").json()
        assert data["fake_data"] is False

    def test_27_review_request_dry_run(self, gov_client):
        res = gov_client.post("/v1/review-governance/review-request", json={
            "item_id": "test-item-1",
            "title": "Test Review",
            "review_lane": "quality_review",
            "reason": "testing"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["submitted"] is False
        assert data["auto_approve"] is False
        assert data["bypassing_gates"] is False

    def test_28_review_request_validates_fields(self, gov_client):
        res = gov_client.post("/v1/review-governance/review-request", json={
            "item_id": "",
            "title": "",
            "review_lane": "",
            "reason": ""
        })
        assert res.status_code == 422

    def test_29_arbitration_returns_200(self, gov_client):
        res = gov_client.get("/v1/review-governance/arbitration")
        assert res.status_code == 200

    def test_30_arbitration_no_auto_resolve(self, gov_client):
        data = gov_client.get("/v1/review-governance/arbitration").json()
        assert data["auto_resolve"] is False
        assert data["fake_arbitration"] is False


# ---------------------------------------------------------------------------
# C4 — Product / Multi-User Readiness  (31-40)
# ---------------------------------------------------------------------------

class TestC4ProductReadiness:
    def test_31_matrix_returns_200(self, prod_client):
        res = prod_client.get("/v1/product-readiness/matrix")
        assert res.status_code == 200

    def test_32_production_multi_user_not_ready(self, prod_client):
        data = prod_client.get("/v1/product-readiness/matrix").json()
        assert data["production_multi_user_ready"] is False

    def test_33_not_claiming_production_support(self, prod_client):
        data = prod_client.get("/v1/product-readiness/matrix").json()
        assert data["claiming_production_support"] is False
        assert data["fake_data"] is False

    def test_34_has_readiness_dimensions(self, prod_client):
        data = prod_client.get("/v1/product-readiness/matrix").json()
        assert "readiness_dimensions" in data
        assert len(data["readiness_dimensions"]) > 0

    def test_35_multi_user_status_returns_200(self, prod_client):
        res = prod_client.get("/v1/product-readiness/multi-user-status")
        assert res.status_code == 200

    def test_36_multi_user_not_live(self, prod_client):
        data = prod_client.get("/v1/product-readiness/multi-user-status").json()
        assert data["multi_user_live"] is False

    def test_37_not_inviting_real_users(self, prod_client):
        data = prod_client.get("/v1/product-readiness/multi-user-status").json()
        assert data["inviting_real_users"] is False

    def test_38_not_changing_auth_security(self, prod_client):
        data = prod_client.get("/v1/product-readiness/multi-user-status").json()
        assert data["changing_auth_security"] is False
        assert data["exposing_user_data"] is False

    def test_39_data_isolation_returns_200(self, prod_client):
        res = prod_client.get("/v1/product-readiness/data-isolation")
        assert res.status_code == 200

    def test_40_data_isolation_multi_user_not_ready(self, prod_client):
        data = prod_client.get("/v1/product-readiness/data-isolation").json()
        assert data["multi_user_isolation"] is False
        assert data["production_multi_user_ready"] is False


# ---------------------------------------------------------------------------
# C5 — Marketplace Governance  (41-50)
# ---------------------------------------------------------------------------

class TestC5MarketplaceGovernance:
    def test_41_status_returns_200(self, mktgov_client):
        res = mktgov_client.get("/v1/marketplace-governance/status")
        assert res.status_code == 200

    def test_42_review_pipeline_not_live(self, mktgov_client):
        data = mktgov_client.get("/v1/marketplace-governance/status").json()
        assert data["review_pipeline_live"] is False

    def test_43_no_live_marketplace_claims(self, mktgov_client):
        data = mktgov_client.get("/v1/marketplace-governance/status").json()
        assert data["live_marketplace_claims"] is False
        assert data["fake_data"] is False

    def test_44_dry_run_only(self, mktgov_client):
        data = mktgov_client.get("/v1/marketplace-governance/status").json()
        assert data["dry_run_only"] is True

    def test_45_review_queue_returns_200(self, mktgov_client):
        res = mktgov_client.get("/v1/marketplace-governance/review-queue")
        assert res.status_code == 200

    def test_46_review_queue_human_review_required(self, mktgov_client):
        data = mktgov_client.get("/v1/marketplace-governance/review-queue").json()
        assert data["human_review_required"] is True
        assert data["auto_review"] is False

    def test_47_dry_run_review_not_activated(self, mktgov_client):
        res = mktgov_client.post("/v1/marketplace-governance/review/test-plugin/dry-run")
        assert res.status_code == 200
        data = res.json()
        assert data["approved"] is False
        assert data["activated"] is False

    def test_48_policy_returns_200(self, mktgov_client):
        res = mktgov_client.get("/v1/marketplace-governance/policy")
        assert res.status_code == 200

    def test_49_policy_no_live_marketplace(self, mktgov_client):
        data = mktgov_client.get("/v1/marketplace-governance/policy").json()
        assert data["live_marketplace"] is False

    def test_50_policy_has_enforced_policies(self, mktgov_client):
        data = mktgov_client.get("/v1/marketplace-governance/policy").json()
        enforced = [p for p in data["policies"] if p["enforced"]]
        assert len(enforced) >= 1, "At least one policy must be enforced"


# ---------------------------------------------------------------------------
# C6 — Enterprise Governance  (51-60)
# ---------------------------------------------------------------------------

class TestC6EnterpriseGovernance:
    def test_51_audit_returns_200(self, entgov_client):
        res = entgov_client.get("/v1/enterprise-governance/audit-summary")
        assert res.status_code == 200

    def test_52_audit_secret_safe(self, entgov_client):
        data = entgov_client.get("/v1/enterprise-governance/audit-summary").json()
        assert data["secret_safe"] is True

    def test_53_audit_no_credential_values(self, entgov_client):
        text = str(entgov_client.get("/v1/enterprise-governance/audit-summary").json())
        for prefix in ("xoxb-", "ghp_", "AKIA", "sk-proj-", "Bearer "):
            assert prefix not in text

    def test_54_reliability_returns_200(self, entgov_client):
        res = entgov_client.get("/v1/enterprise-governance/reliability")
        assert res.status_code == 200

    def test_55_reliability_no_live_billing(self, entgov_client):
        data = entgov_client.get("/v1/enterprise-governance/reliability").json()
        assert data["live_billing_integration"] is False
        assert data["fake_data"] is False

    def test_56_cost_control_returns_200(self, entgov_client):
        res = entgov_client.get("/v1/enterprise-governance/cost-control")
        assert res.status_code == 200

    def test_57_cost_control_no_live_billing(self, entgov_client):
        data = entgov_client.get("/v1/enterprise-governance/cost-control").json()
        assert data["live_billing_integration"] is False
        assert data["fake_data"] is False

    def test_58_incident_status_returns_200(self, entgov_client):
        res = entgov_client.get("/v1/enterprise-governance/incident-status")
        assert res.status_code == 200

    def test_59_incident_no_fake_rollback(self, entgov_client):
        data = entgov_client.get("/v1/enterprise-governance/incident-status").json()
        assert data.get("fake_rollback") is False

    def test_60_incident_fake_data_false(self, entgov_client):
        data = entgov_client.get("/v1/enterprise-governance/incident-status").json()
        assert data["fake_data"] is False


# ---------------------------------------------------------------------------
# C7 — Scale Control  (61-70)
# ---------------------------------------------------------------------------

class TestC7ScaleControl:
    def test_61_status_returns_200(self, scale_client):
        res = scale_client.get("/v1/scale-control/status")
        assert res.status_code == 200

    def test_62_cloud_execution_not_live(self, scale_client):
        data = scale_client.get("/v1/scale-control/status").json()
        assert data["cloud_execution_live"] is False

    def test_63_no_fake_cloud_readiness(self, scale_client):
        data = scale_client.get("/v1/scale-control/status").json()
        assert data["fake_cloud_readiness"] is False
        assert data["fake_data"] is False

    def test_64_approval_gates_active(self, scale_client):
        data = scale_client.get("/v1/scale-control/status").json()
        assert data["approval_gates_active"] is True

    def test_65_macbook_off_not_live(self, scale_client):
        data = scale_client.get("/v1/scale-control/macbook-off-readiness").json()
        assert data["macbook_off_live"] is False

    def test_66_macbook_off_requirements_unmet(self, scale_client):
        data = scale_client.get("/v1/scale-control/macbook-off-readiness").json()
        assert data["requirements_met"] == 0
        assert data["fake_cloud_readiness"] is False

    def test_67_queue_status_returns_200(self, scale_client):
        res = scale_client.get("/v1/scale-control/queue-status")
        assert res.status_code == 200

    def test_68_queue_no_remote_execution(self, scale_client):
        data = scale_client.get("/v1/scale-control/queue-status").json()
        assert data["remote_execution_live"] is False

    def test_69_parity_status_returns_200(self, scale_client):
        res = scale_client.get("/v1/scale-control/parity-status")
        assert res.status_code == 200

    def test_70_parity_not_achieved_honestly(self, scale_client):
        data = scale_client.get("/v1/scale-control/parity-status").json()
        assert data["parity_achieved"] is False
        assert data["fake_parity"] is False


# ---------------------------------------------------------------------------
# C8 — Company OS  (71-80)
# ---------------------------------------------------------------------------

class TestC8CompanyOS:
    def test_71_dashboard_returns_200(self, company_client):
        res = company_client.get("/v1/company-os/dashboard")
        assert res.status_code == 200

    def test_72_no_live_business_execution(self, company_client):
        data = company_client.get("/v1/company-os/dashboard").json()
        assert data["live_business_execution"] is False

    def test_73_no_fake_company_operation(self, company_client):
        data = company_client.get("/v1/company-os/dashboard").json()
        assert data["fake_company_operation"] is False
        assert data["fake_data"] is False

    def test_74_not_sending_external_messages(self, company_client):
        data = company_client.get("/v1/company-os/dashboard").json()
        assert data["sending_external_messages"] is False

    def test_75_workflow_lanes_returns_200(self, company_client):
        res = company_client.get("/v1/company-os/workflow-lanes")
        assert res.status_code == 200

    def test_76_lanes_no_unsupervised_decisions(self, company_client):
        data = company_client.get("/v1/company-os/workflow-lanes").json()
        assert data["unsupervised_decisions"] is False
        assert data["live_business_execution"] is False

    def test_77_dry_run_plan_no_execution(self, company_client):
        res = company_client.post("/v1/company-os/dry-run-plan", json={
            "lane_id": "research",
            "goal": "Write competitive analysis",
            "context": "testing"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["approval_required"] is True

    def test_78_dry_run_validates_fields(self, company_client):
        res = company_client.post("/v1/company-os/dry-run-plan", json={
            "lane_id": "",
            "goal": "",
            "context": ""
        })
        assert res.status_code == 422

    def test_79_mission_linkage_returns_200(self, company_client):
        res = company_client.get("/v1/company-os/mission-linkage")
        assert res.status_code == 200

    def test_80_mission_linkage_no_auto_linking(self, company_client):
        data = company_client.get("/v1/company-os/mission-linkage").json()
        assert data["auto_linking"] is False
        assert data["fake_data"] is False


# ---------------------------------------------------------------------------
# C9 — Safety Simulation  (81-90)
# ---------------------------------------------------------------------------

class TestC9SafetySimulation:
    def test_81_status_returns_200(self, safety_client):
        res = safety_client.get("/v1/safety-simulation/status")
        assert res.status_code == 200

    def test_82_dry_run_only(self, safety_client):
        data = safety_client.get("/v1/safety-simulation/status").json()
        assert data["dry_run_only"] is True

    def test_83_real_execution_false(self, safety_client):
        data = safety_client.get("/v1/safety-simulation/status").json()
        assert data["real_execution"] is False

    def test_84_destructive_actions_blocked(self, safety_client):
        data = safety_client.get("/v1/safety-simulation/status").json()
        assert data["destructive_actions_blocked"] is True

    def test_85_simulate_dry_run(self, safety_client):
        res = safety_client.post("/v1/safety-simulation/simulate", json={
            "action": "send notification",
            "parameters": {},
            "reason": "test"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["would_execute"] is False

    def test_86_simulate_destructive_detected(self, safety_client):
        res = safety_client.post("/v1/safety-simulation/simulate", json={
            "action": "delete all memory entries",
            "parameters": {},
            "reason": "test"
        })
        assert res.status_code == 200
        data = res.json()
        assert data["destructive"] is True
        assert data["executed"] is False

    def test_87_simulate_validates_empty_action(self, safety_client):
        res = safety_client.post("/v1/safety-simulation/simulate", json={
            "action": "",
            "parameters": {},
            "reason": ""
        })
        assert res.status_code == 422

    def test_88_rollback_matrix_returns_200(self, safety_client):
        res = safety_client.get("/v1/safety-simulation/rollback-matrix")
        assert res.status_code == 200

    def test_89_rollback_no_automated_rollback(self, safety_client):
        data = safety_client.get("/v1/safety-simulation/rollback-matrix").json()
        assert data["automated_rollback_live"] is False
        assert data["fake_rollback"] is False

    def test_90_policy_checks_gates_enforced(self, safety_client):
        data = safety_client.get("/v1/safety-simulation/policy-checks").json()
        assert data["gates_enforced"] is True
        assert data["bypassing_gates"] is False


# ---------------------------------------------------------------------------
# C10 — Control Tower  (91-100)
# ---------------------------------------------------------------------------

class TestC10ControlTower:
    def test_91_status_returns_200(self, tower_client):
        res = tower_client.get("/v1/control-tower/status")
        assert res.status_code == 200

    def test_92_no_fake_acceptance(self, tower_client):
        data = tower_client.get("/v1/control-tower/status").json()
        assert data["fake_acceptance"] is False
        assert data["fake_data"] is False

    def test_93_active_sprint_is_phase_c(self, tower_client):
        data = tower_client.get("/v1/control-tower/status").json()
        assert "C" in data["active_sprint"] or "PHASE_C" in data["active_sprint"] or "AUTONOMOUS" in data["active_sprint"]

    def test_94_final_phase_a_active(self, tower_client):
        # Final Phase A moved from ON_HOLD to IN_PROGRESS in Final Phase A Live Gate Closure sprint
        data = tower_client.get("/v1/control-tower/status").json()
        final_a = next((p for p in data["phases"] if "Final Phase A" in p["phase"] or "Phase A" in p["phase"]), None)
        assert final_a is not None, "Final Phase A must appear in control tower phases"
        valid_statuses = {"IN_PROGRESS", "ON_HOLD", "ACTIVE"}
        assert final_a["status"] in valid_statuses or "HOLD" in final_a["status"], (
            f"Final Phase A status must be active or on-hold, got: {final_a['status']}"
        )

    def test_95_gate_registry_returns_200(self, tower_client):
        res = tower_client.get("/v1/control-tower/gate-registry")
        assert res.status_code == 200

    def test_96_gate_registry_no_fake_closure(self, tower_client):
        data = tower_client.get("/v1/control-tower/gate-registry").json()
        assert data["fake_gate_closure"] is False

    def test_97_next_decisions_no_auto_decide(self, tower_client):
        data = tower_client.get("/v1/control-tower/next-decisions").json()
        assert data["auto_decide"] is False

    def test_98_completion_score_honest(self, tower_client):
        data = tower_client.get("/v1/control-tower/completion-score").json()
        score = data["core_os_completion"]["completion_score_pct"]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100
        assert data["core_os_completion"]["fake_score"] is False

    def test_99_completion_voice_not_live(self, tower_client):
        data = tower_client.get("/v1/control-tower/completion-score").json()
        coverage = data["capability_coverage"]
        assert coverage.get("voice_wake") is False

    def test_100_completion_native_ios_not_live(self, tower_client):
        data = tower_client.get("/v1/control-tower/completion-score").json()
        coverage = data["capability_coverage"]
        assert coverage.get("native_ios_distributed") is False


# ---------------------------------------------------------------------------
# Self-knowledge C1-C10 integration  (101-112)
# ---------------------------------------------------------------------------

class TestSelfKnowledgeC1ToC10:
    def test_101_autonomous_org_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "autonomous_org_kernel" in caps

    def test_102_mission_control_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "mission_control_c" in caps

    def test_103_review_governance_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "review_governance" in caps

    def test_104_product_readiness_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "product_readiness" in caps

    def test_105_marketplace_governance_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "marketplace_governance_c" in caps

    def test_106_enterprise_governance_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "enterprise_governance" in caps

    def test_107_scale_control_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "scale_control" in caps

    def test_108_company_os_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "company_os_c" in caps

    def test_109_safety_simulation_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "safety_simulation" in caps

    def test_110_control_tower_capability(self, sk_client):
        caps = [c["id"] for c in sk_client.get("/v1/jarvis/capabilities").json()["capabilities"]]
        assert "control_tower" in caps

    def test_111_c1_c10_in_plan_state(self, sk_client):
        # C1-C10 phases moved to ACCEPTED in Final Phase A Live Gate Closure sprint
        plan_state = sk_client.get("/v1/jarvis/status").json()["plan_state"]
        for key in (
            "phase_c1_autonomous_org", "phase_c2_mission_control", "phase_c3_review_governance",
            "phase_c4_product_readiness", "phase_c5_marketplace_governance",
            "phase_c6_enterprise_governance", "phase_c7_scale_control",
            "phase_c8_company_os", "phase_c9_safety_simulation", "phase_c10_control_tower",
        ):
            assert key in plan_state, f"Missing plan_state key: {key}"
            assert plan_state[key] == "ACCEPTED"

    def test_112_phase_b_on_hold_in_plan_state(self, sk_client):
        plan_state = sk_client.get("/v1/jarvis/status").json()["plan_state"]
        assert "phase_b1_to_b20" in plan_state
        assert plan_state["phase_b1_to_b20"] == "ACCEPTED_ON_HOLD"

    def test_113_active_sprint_is_phase_c(self, sk_client):
        sprint = sk_client.get("/v1/jarvis/roadmap").json()["active_sprint"]
        assert "C" in sprint or "AUTONOMOUS" in sprint

    def test_114_plan_4_6_still_accepted(self, sk_client):
        assert sk_client.get("/v1/jarvis/status").json()["plan_state"]["plan_4_6_mega_sprint"] == "ACCEPTED"

    def test_115_phase_x_still_accepted(self, sk_client):
        assert sk_client.get("/v1/jarvis/status").json()["plan_state"]["phase_x_decoupling"] == "ACCEPTED"


# ---------------------------------------------------------------------------
# OMNIX non-regression + approval gates  (116-120)
# ---------------------------------------------------------------------------

class TestOmnixAndGates:
    def test_116_jarvis_identity_not_omnix(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("primary_project") != "omnix"
        assert JARVIS_IDENTITY.get("name") == "Jarvis"

    def test_117_hard_gates_still_present(self):
        from openjarvis.governance.constitution import HARD_GATE_ACTIONS
        assert len(HARD_GATE_ACTIONS) >= 14

    def test_118_autonomous_org_no_omnix_as_core(self):
        import inspect
        from openjarvis.server import autonomous_org_routes
        source = inspect.getsource(autonomous_org_routes)
        # Allow omnix_is_jarvis_core: False (governance field proving OMNIX is NOT core)
        # Block: hardcoded OMNIX as primary_project, default_project, or Jarvis identity
        dangerous = [
            l for l in source.split("\n")
            if ("OMNIX" in l.upper() and not l.strip().startswith("#"))
            and "omnix_is_jarvis_core" not in l.lower()  # governance field is fine
            and "omnix_production_deploy" not in l.lower()  # hard gate reference is fine
        ]
        assert len(dangerous) == 0, f"Dangerous OMNIX reference in autonomous_org_routes: {dangerous}"

    def test_119_control_tower_no_omnix_as_core(self):
        import inspect
        from openjarvis.server import control_tower_routes
        source = inspect.getsource(control_tower_routes)
        bad_lines = [l for l in source.split("\n") if "omnix_is_jarvis" in l.lower() or "OMNIX_CORE" in l]
        assert len(bad_lines) == 0

    def test_120_phase_b_b20_regression(self):
        """Phase B1-B20 baseline tests still importable — not checking all here, just that modules load."""
        from openjarvis.server import (
            follow_up_center_routes,
            routines_routes,
            memory_routes,
            command_center_routes,
            expert_roles_routes,
            skills_expansion_routes,
            connector_workflow_routes,
            proactive_routes,
            business_admin_routes,
            observability_routes,
            long_horizon_routes,
            finance_admin_routes,
            research_os_routes,
            browser_operator_routes,
            memory_graph_routes,
            multi_device_routes,
            marketplace_routes,
            org_mode_routes,
            device_controller_routes,
        )
        assert all([
            follow_up_center_routes,
            routines_routes,
            memory_routes,
            command_center_routes,
            expert_roles_routes,
            skills_expansion_routes,
            connector_workflow_routes,
            proactive_routes,
            business_admin_routes,
            observability_routes,
            long_horizon_routes,
            finance_admin_routes,
            research_os_routes,
            browser_operator_routes,
            memory_graph_routes,
            multi_device_routes,
            marketplace_routes,
            org_mode_routes,
            device_controller_routes,
        ])
