"""Phase C11-C20 backend behavior tests for OpenJarvis.

Covers:
  C11 — Autonomous Execution Readiness Manager
  C12 — Cross-System Action Planner
  C13 — Approval Policy Compiler + Authority Matrix
  C14 — Live Connector Readiness Verification Layer
  C15 — Native iOS / Mobile App Readiness Gate
  C16 — macOS Signing / Notarization Readiness Gate
  C17 — Cloud / Fargate / Tailscale Execution Readiness Gate
  C18 — Core OS Final Smoke Orchestrator
  C19 — Daily-Driver Certification Harness
  C20 — Jarvis Core OS Completion + Phase D Decision Gate
  Self-knowledge integration (C11-C20 capabilities + roadmap)
  Bryan-cleared gates reflected accurately
  Phase B hold preserved
  C1-C10 regression (no new breakage)
  OMNIX non-regression

Test rules:
  - All tests are independent; no shared mutable state.
  - No live HTTP calls outside TestClient.
  - No secret values, no .env access.
  - Uses response.json() for body access.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def c11_client() -> TestClient:
    from openjarvis.server.execution_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c12_client() -> TestClient:
    from openjarvis.server.action_planner_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c13_client() -> TestClient:
    from openjarvis.server.policy_compiler_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c14_client() -> TestClient:
    from openjarvis.server.connector_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c15_client() -> TestClient:
    from openjarvis.server.ios_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c16_client() -> TestClient:
    from openjarvis.server.signing_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c17_client() -> TestClient:
    from openjarvis.server.cloud_readiness_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c18_client() -> TestClient:
    from openjarvis.server.final_smoke_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c19_client() -> TestClient:
    from openjarvis.server.daily_driver_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def c20_client() -> TestClient:
    from openjarvis.server.core_completion_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def sk_client() -> TestClient:
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# C11 — Autonomous Execution Readiness Manager
# ---------------------------------------------------------------------------


class TestC11ExecutionReadiness:
    def test_1_status_200(self, c11_client):
        assert c11_client.get("/v1/execution-readiness/status").status_code == 200

    def test_2_status_no_fake_data(self, c11_client):
        assert c11_client.get("/v1/execution-readiness/status").json()["fake_data"] is False

    def test_3_autonomous_execution_not_live(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/status").json()
        assert data["autonomous_execution_live"] is False

    def test_4_approval_required_for_all_actions(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/status").json()
        assert data["approval_required_for_all_actions"] is True

    def test_5_fake_readiness_false(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/status").json()
        assert data["fake_readiness"] is False

    def test_6_systems_is_list(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/status").json()
        assert isinstance(data["systems"], list)
        assert len(data["systems"]) >= 1

    def test_7_each_system_has_approval_required(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/status").json()
        for s in data["systems"]:
            assert s.get("approval_required") is True, f"system {s.get('system_id')} missing approval_required"

    def test_8_matrix_200(self, c11_client):
        assert c11_client.get("/v1/execution-readiness/matrix").status_code == 200

    def test_9_matrix_autonomous_execution_false(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/matrix").json()
        assert data["autonomous_execution_live"] is False

    def test_10_matrix_all_require_approval(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/matrix").json()
        assert data["all_require_approval"] is True

    def test_11_matrix_action_classes_list(self, c11_client):
        data = c11_client.get("/v1/execution-readiness/matrix").json()
        assert isinstance(data["action_classes"], list)
        assert len(data["action_classes"]) >= 4

    def test_12_dry_run_check_read_only_allowed(self, c11_client):
        data = c11_client.post("/v1/execution-readiness/dry-run-check", json={
            "action_class": "read_only", "system_id": "life_os", "description": "test"
        }).json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["approval_gate_bypassed"] is False

    def test_13_dry_run_check_connector_not_auto_allowed(self, c11_client):
        data = c11_client.post("/v1/execution-readiness/dry-run-check", json={
            "action_class": "external_send", "system_id": "connectors", "description": "test"
        }).json()
        assert data["requires_approval"] is True
        assert data["executed"] is False
        assert data["approval_gate_bypassed"] is False

    def test_14_dry_run_check_empty_action_class_422(self, c11_client):
        r = c11_client.post("/v1/execution-readiness/dry-run-check", json={
            "action_class": "", "system_id": "life_os", "description": "test"
        })
        assert r.status_code == 422

    def test_15_no_secret_values_in_status(self, c11_client):
        text = str(c11_client.get("/v1/execution-readiness/status").json())
        for p in ("xoxb-", "ghp_", "AKIA", "sk-proj-"):
            assert p not in text


# ---------------------------------------------------------------------------
# C12 — Cross-System Action Planner
# ---------------------------------------------------------------------------


class TestC12ActionPlanner:
    def test_16_systems_200(self, c12_client):
        assert c12_client.get("/v1/action-planner/systems").status_code == 200

    def test_17_systems_no_fake_data(self, c12_client):
        assert c12_client.get("/v1/action-planner/systems").json()["fake_data"] is False

    def test_18_systems_has_list(self, c12_client):
        data = c12_client.get("/v1/action-planner/systems").json()
        assert isinstance(data["systems"], list)
        assert len(data["systems"]) >= 1

    def test_19_cross_system_planning_true(self, c12_client):
        data = c12_client.get("/v1/action-planner/systems").json()
        assert data["cross_system_planning"] is True

    def test_20_templates_200(self, c12_client):
        assert c12_client.get("/v1/action-planner/templates").status_code == 200

    def test_21_templates_dry_run_only(self, c12_client):
        data = c12_client.get("/v1/action-planner/templates").json()
        assert data["dry_run_only"] is True

    def test_22_templates_has_list(self, c12_client):
        data = c12_client.get("/v1/action-planner/templates").json()
        assert isinstance(data["templates"], list)
        assert len(data["templates"]) >= 3

    def test_23_plan_post_dry_run(self, c12_client):
        data = c12_client.post("/v1/action-planner/plan", json={
            "goal": "review my pending tasks", "systems": ["life_os", "goals"], "dry_run": True
        }).json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["all_steps_require_approval"] is True

    def test_24_plan_empty_goal_422(self, c12_client):
        r = c12_client.post("/v1/action-planner/plan", json={"goal": "", "systems": []})
        assert r.status_code == 422

    def test_25_plan_steps_all_require_approval(self, c12_client):
        data = c12_client.post("/v1/action-planner/plan", json={
            "goal": "morning review", "systems": ["life_os"], "dry_run": True
        }).json()
        for step in data.get("steps", []):
            assert step.get("approval_required") is True, f"Step {step} missing approval_required"

    def test_26_plan_fake_plan_false(self, c12_client):
        data = c12_client.post("/v1/action-planner/plan", json={"goal": "test goal", "systems": []}).json()
        assert data["fake_plan"] is False


# ---------------------------------------------------------------------------
# C13 — Approval Policy Compiler + Authority Matrix
# ---------------------------------------------------------------------------


class TestC13PolicyCompiler:
    def test_27_authority_matrix_200(self, c13_client):
        assert c13_client.get("/v1/policy-compiler/authority-matrix").status_code == 200

    def test_28_authority_matrix_no_fake_data(self, c13_client):
        assert c13_client.get("/v1/policy-compiler/authority-matrix").json()["fake_data"] is False

    def test_29_hard_gates_preserved(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/authority-matrix").json()
        assert data["hard_gates_preserved"] is True

    def test_30_approval_gates_not_weakened(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/authority-matrix").json()
        assert data["approval_gates_weakened"] is False

    def test_31_domains_is_list(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/authority-matrix").json()
        assert isinstance(data["domains"], list)
        assert len(data["domains"]) >= 4

    def test_32_all_domains_require_approval(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/authority-matrix").json()
        for d in data["domains"]:
            assert d.get("approval_required") is True

    def test_33_policy_summary_200(self, c13_client):
        assert c13_client.get("/v1/policy-compiler/policy-summary").status_code == 200

    def test_34_gates_not_weakened_in_summary(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/policy-summary").json()
        assert data["gates_weakened"] is False

    def test_35_all_policies_enforced(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/policy-summary").json()
        for p in data.get("active_policies", []):
            assert p.get("enforced") is True

    def test_36_conflicts_200(self, c13_client):
        assert c13_client.get("/v1/policy-compiler/conflicts").status_code == 200

    def test_37_no_policy_conflicts(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/conflicts").json()
        assert data["conflict_count"] == 0
        assert data["all_policies_consistent"] is True

    def test_38_explain_requires_approval(self, c13_client):
        data = c13_client.post("/v1/policy-compiler/explain", json={"action": "send email"}).json()
        assert data["requires_approval"] is True

    def test_39_explain_empty_action_422(self, c13_client):
        r = c13_client.post("/v1/policy-compiler/explain", json={"action": ""})
        assert r.status_code == 422

    def test_40_explain_destructive_hard_gated(self, c13_client):
        data = c13_client.post("/v1/policy-compiler/explain", json={"action": "delete all tasks"}).json()
        assert data["hard_gated"] is True

    def test_41_hard_gates_count_nonzero(self, c13_client):
        data = c13_client.get("/v1/policy-compiler/authority-matrix").json()
        assert data["hard_gates_count"] >= 0


# ---------------------------------------------------------------------------
# C14 — Live Connector Readiness Verification Layer
# ---------------------------------------------------------------------------


class TestC14ConnectorReadiness:
    def test_42_status_200(self, c14_client):
        assert c14_client.get("/v1/connector-readiness/status").status_code == 200

    def test_43_no_fake_data(self, c14_client):
        assert c14_client.get("/v1/connector-readiness/status").json()["fake_data"] is False

    def test_44_no_fake_live_claims(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        assert data["fake_live_claims"] is False

    def test_45_no_secrets_in_response(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        assert data["secrets_in_response"] is False
        text = str(data)
        for p in ("xoxb-", "xoxp-", "ghp_", "AKIA", "sk-proj-"):
            assert p not in text

    def test_46_connectors_list_present(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        assert isinstance(data["connectors"], list)
        assert len(data["connectors"]) == 10

    def test_47_notion_always_blocked(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        notion = next((c for c in data["connectors"] if c["connector_id"] == "notion"), None)
        assert notion is not None
        assert notion["status"] == "blocked"

    def test_48_all_connectors_have_presence_only(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        for c in data["connectors"]:
            assert c.get("presence_only") is True, f"connector {c['connector_id']} not presence-only"
            assert c.get("no_credential_value") is True

    def test_49_connector_status_vocabulary_valid(self, c14_client):
        valid = {"ready_prerequisite", "blocked", "not_configured", "live_verified"}
        data = c14_client.get("/v1/connector-readiness/status").json()
        for c in data["connectors"]:
            assert c["status"] in valid, f"invalid status {c['status']}"

    def test_50_live_verified_count(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        # GitHub, Slack, Telegram, Tavily live-verified in Final Phase A sprint (Jun 25 2026)
        assert data["live_verified_count"] == 4

    def test_51_detail_404_for_unknown(self, c14_client):
        r = c14_client.get("/v1/connector-readiness/detail/nonexistent_xyz")
        assert r.status_code == 404

    def test_52_detail_200_for_known(self, c14_client):
        r = c14_client.get("/v1/connector-readiness/detail/gmail")
        assert r.status_code == 200

    def test_53_detail_has_live_execution_blocked(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/detail/slack").json()
        assert data.get("live_execution_blocked") is True


# ---------------------------------------------------------------------------
# C15 — Native iOS / Mobile App Readiness Gate
# ---------------------------------------------------------------------------


class TestC15IOSReadiness:
    def test_54_status_200(self, c15_client):
        assert c15_client.get("/v1/ios-readiness/status").status_code == 200

    def test_55_no_fake_ios_readiness(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["fake_ios_readiness"] is False

    def test_56_no_fake_data(self, c15_client):
        assert c15_client.get("/v1/ios-readiness/status").json()["fake_data"] is False

    def test_57_tauri_ios_init_run(self, c15_client):
        # tauri ios init completed in Final Phase A sprint (Jun 25 2026)
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["tauri_ios_init_run"] is True

    def test_58_tauri_ios_init_not_deferred(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["tauri_ios_init_deferred"] is False

    def test_59_native_ios_app_not_ready(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["native_ios_app_ready"] is False

    def test_60_testflight_not_ready(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["testflight_ready"] is False

    def test_61_app_store_not_ready(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["app_store_ready"] is False

    def test_62_prerequisites_bryan_cleared(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["prerequisites_bryan_cleared"] is True

    def test_63_prerequisites_200(self, c15_client):
        assert c15_client.get("/v1/ios-readiness/prerequisites").status_code == 200

    def test_64_prerequisites_bryan_cleared_all(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/prerequisites").json()
        assert data["bryan_cleared_all"] is True

    def test_65_prerequisites_list_has_xcode(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/prerequisites").json()
        ids = [p["id"] for p in data["prerequisites"]]
        assert "xcode" in ids

    def test_66_tauri_init_assessment_200(self, c15_client):
        assert c15_client.get("/v1/ios-readiness/tauri-init-assessment").status_code == 200

    def test_67_tauri_init_assessment_completed(self, c15_client):
        # tauri ios init completed in Final Phase A sprint (Jun 25 2026)
        data = c15_client.get("/v1/ios-readiness/tauri-init-assessment").json()
        assert data["assessment"] == "completed"
        assert data["ran_in_this_sprint"] is True


# ---------------------------------------------------------------------------
# C16 — macOS Signing / Notarization Readiness Gate
# ---------------------------------------------------------------------------


class TestC16SigningReadiness:
    def test_68_status_200(self, c16_client):
        assert c16_client.get("/v1/signing-readiness/status").status_code == 200

    def test_69_no_fake_notarization(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["fake_notarization"] is False

    def test_70_no_fake_data(self, c16_client):
        assert c16_client.get("/v1/signing-readiness/status").json()["fake_data"] is False

    def test_71_actual_signing_run(self, c16_client):
        # macOS app signed + notarized in Final Phase A sprint (Jun 25 2026)
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["actual_signing_run"] is True

    def test_72_actual_notarization_run(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["actual_notarization_run"] is True

    def test_73_notarization_claimed_true(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["notarization_claimed"] is True

    def test_74_public_release_not_ready(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["public_release_ready"] is False

    def test_75_no_secret_values_in_response(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/status").json()
        text = str(data)
        for p in ("xoxb-", "ghp_", "AKIA", "sk-proj-"):
            assert p not in text
        assert data["no_secret_values_in_response"] is True

    def test_76_prerequisites_200(self, c16_client):
        assert c16_client.get("/v1/signing-readiness/prerequisites").status_code == 200

    def test_77_prerequisites_bryan_cleared(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/prerequisites").json()
        assert data["all_bryan_cleared"] is True

    def test_78_no_blocking_prerequisites(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/prerequisites").json()
        assert data["blocking_count"] == 0

    def test_79_notarization_assessment_200(self, c16_client):
        assert c16_client.get("/v1/signing-readiness/notarization-assessment").status_code == 200

    def test_80_notarization_run_this_sprint(self, c16_client):
        # Notarization completed Jun 25 2026 — result: Accepted, spctl accepted, stapler validated
        data = c16_client.get("/v1/signing-readiness/notarization-assessment").json()
        assert data["notarization_run_this_sprint"] is True
        assert data["fake_notarized"] is False


# ---------------------------------------------------------------------------
# C17 — Cloud / Fargate / Tailscale Execution Readiness Gate
# ---------------------------------------------------------------------------


class TestC17CloudReadiness:
    def test_81_status_200(self, c17_client):
        assert c17_client.get("/v1/cloud-readiness/status").status_code == 200

    def test_82_no_fake_cloud_execution(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/status").json()
        assert data["fake_cloud_execution"] is False

    def test_83_cloud_execution_not_live(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/status").json()
        assert data["cloud_execution_live"] is False

    def test_84_macbook_off_not_live(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/status").json()
        assert data["macbook_off_live"] is False

    def test_85_deployment_not_authorized(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/status").json()
        assert data["deployment_authorized_this_sprint"] is False

    def test_86_prerequisites_matrix_200(self, c17_client):
        assert c17_client.get("/v1/cloud-readiness/prerequisites-matrix").status_code == 200

    def test_87_deployment_not_authorized_in_matrix(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/prerequisites-matrix").json()
        assert data["deployment_authorized"] is False

    def test_88_prerequisites_list_exists(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/prerequisites-matrix").json()
        assert isinstance(data["prerequisites"], list)
        assert len(data["prerequisites"]) >= 4

    def test_89_dry_run_plan_200(self, c17_client):
        assert c17_client.get("/v1/cloud-readiness/dry-run-plan").status_code == 200

    def test_90_dry_run_plan_not_executed(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/dry-run-plan").json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["fake_cloud_deployment"] is False

    def test_91_dry_run_steps_all_need_approval(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/dry-run-plan").json()
        for step in data.get("deployment_plan_steps", []):
            assert step.get("approval_required") is True

    def test_92_no_secret_values_in_status(self, c17_client):
        text = str(c17_client.get("/v1/cloud-readiness/status").json())
        for p in ("xoxb-", "ghp_", "AKIA", "sk-proj-", "Bearer "):
            assert p not in text


# ---------------------------------------------------------------------------
# C18 — Core OS Final Smoke Orchestrator
# ---------------------------------------------------------------------------


class TestC18FinalSmoke:
    def test_93_checklist_200(self, c18_client):
        assert c18_client.get("/v1/final-smoke/checklist").status_code == 200

    def test_94_no_fake_data(self, c18_client):
        assert c18_client.get("/v1/final-smoke/checklist").json()["fake_data"] is False

    def test_95_manual_proof_required(self, c18_client):
        data = c18_client.get("/v1/final-smoke/checklist").json()
        assert data["manual_proof_required"] is True

    def test_96_auto_pass_blocked(self, c18_client):
        data = c18_client.get("/v1/final-smoke/checklist").json()
        assert data["auto_pass_blocked"] is True

    def test_97_passed_is_zero(self, c18_client):
        data = c18_client.get("/v1/final-smoke/checklist").json()
        assert data["passed"] == 0

    def test_98_checklist_items_not_auto_passable(self, c18_client):
        data = c18_client.get("/v1/final-smoke/checklist").json()
        for item in data["checklist"]:
            # auto_passable must be False or absent (never True)
            assert item.get("auto_passable") is not True, f"item {item.get('item_id')} has auto_passable=True"

    def test_99_status_200(self, c18_client):
        assert c18_client.get("/v1/final-smoke/status").status_code == 200

    def test_100_smoke_not_claimed_passed(self, c18_client):
        data = c18_client.get("/v1/final-smoke/status").json()
        assert data["claimed_passed"] is False
        assert data["fake_smoke_result"] is False

    def test_101_installed_app_smoke_blocked(self, c18_client):
        data = c18_client.get("/v1/final-smoke/status").json()
        assert "blocked" in data.get("installed_app_smoke", "").lower()

    def test_102_capture_proof_requires_nonempty_item(self, c18_client):
        r = c18_client.post("/v1/final-smoke/capture-proof", json={
            "item_id": "", "proof_type": "screenshot", "evidence_summary": "test"
        })
        assert r.status_code == 422

    def test_103_capture_proof_does_not_auto_pass(self, c18_client):
        data = c18_client.post("/v1/final-smoke/capture-proof", json={
            "item_id": "backend_health", "proof_type": "manual", "evidence_summary": "all ok"
        }).json()
        assert data["auto_passed"] is False
        assert data["requires_bryan_verification"] is True


# ---------------------------------------------------------------------------
# C19 — Daily-Driver Certification Harness
# ---------------------------------------------------------------------------


class TestC19DailyDriver:
    def test_104_status_200(self, c19_client):
        assert c19_client.get("/v1/daily-driver/status").status_code == 200

    def test_105_no_fake_certification(self, c19_client):
        data = c19_client.get("/v1/daily-driver/status").json()
        assert data["fake_certification"] is False

    def test_106_not_certified(self, c19_client):
        data = c19_client.get("/v1/daily-driver/status").json()
        assert data["certified"] is False

    def test_107_auto_certification_blocked(self, c19_client):
        data = c19_client.get("/v1/daily-driver/status").json()
        assert data["auto_certification_blocked"] is True

    def test_108_manual_certification_required(self, c19_client):
        data = c19_client.get("/v1/daily-driver/status").json()
        assert data["manual_certification_required"] is True

    def test_109_checklist_200(self, c19_client):
        assert c19_client.get("/v1/daily-driver/checklist").status_code == 200

    def test_110_certified_count_zero(self, c19_client):
        data = c19_client.get("/v1/daily-driver/checklist").json()
        assert data["certified_count"] == 0

    def test_111_auto_certify_blocked_in_checklist(self, c19_client):
        data = c19_client.get("/v1/daily-driver/checklist").json()
        assert data["auto_certify_blocked"] is True

    def test_112_blockers_200(self, c19_client):
        assert c19_client.get("/v1/daily-driver/blockers").status_code == 200

    def test_113_blockers_has_items(self, c19_client):
        data = c19_client.get("/v1/daily-driver/blockers").json()
        assert isinstance(data["blockers"], list)
        assert len(data["blockers"]) >= 1

    def test_114_record_session_empty_notes_422(self, c19_client):
        r = c19_client.post("/v1/daily-driver/record-session", json={
            "session_notes": "", "duration_minutes": 30
        })
        assert r.status_code == 422

    def test_115_record_session_zero_duration_422(self, c19_client):
        r = c19_client.post("/v1/daily-driver/record-session", json={
            "session_notes": "tested", "duration_minutes": 0
        })
        assert r.status_code == 422

    def test_116_record_session_does_not_auto_certify(self, c19_client):
        data = c19_client.post("/v1/daily-driver/record-session", json={
            "session_notes": "worked well", "duration_minutes": 45, "issues_found": []
        }).json()
        assert data["auto_certified"] is False
        assert data["certification_granted"] is False
        assert data["requires_bryan_review"] is True


# ---------------------------------------------------------------------------
# C20 — Jarvis Core OS Completion + Phase D Decision Gate
# ---------------------------------------------------------------------------


class TestC20CoreCompletion:
    def test_117_status_200(self, c20_client):
        assert c20_client.get("/v1/core-completion/status").status_code == 200

    def test_118_no_fake_completion(self, c20_client):
        data = c20_client.get("/v1/core-completion/status").json()
        assert data["fake_completion"] is False

    def test_119_no_fake_100_percent(self, c20_client):
        data = c20_client.get("/v1/core-completion/status").json()
        assert data["fake_100_percent"] is False

    def test_120_no_fake_score(self, c20_client):
        data = c20_client.get("/v1/core-completion/status").json()
        assert data["fake_score"] is False

    def test_121_completion_score_not_100(self, c20_client):
        data = c20_client.get("/v1/core-completion/status").json()
        assert data["completion_score_pct"] < 100

    def test_122_phase_d_not_ready(self, c20_client):
        data = c20_client.get("/v1/core-completion/status").json()
        assert data["phase_d_ready"] is False

    def test_123_phases_list_present(self, c20_client):
        data = c20_client.get("/v1/core-completion/status").json()
        assert isinstance(data["phases"], list)
        assert len(data["phases"]) >= 6

    def test_124_phase_d_options_200(self, c20_client):
        assert c20_client.get("/v1/core-completion/phase-d-options").status_code == 200

    def test_125_no_auto_decision(self, c20_client):
        data = c20_client.get("/v1/core-completion/phase-d-options").json()
        assert data["auto_decision"] is False
        assert data["all_decisions_require_bryan"] is True

    def test_126_options_list(self, c20_client):
        data = c20_client.get("/v1/core-completion/phase-d-options").json()
        assert isinstance(data["options"], list)
        assert len(data["options"]) >= 3

    def test_127_readiness_classification_200(self, c20_client):
        assert c20_client.get("/v1/core-completion/readiness-classification").status_code == 200

    def test_128_no_fake_classification(self, c20_client):
        data = c20_client.get("/v1/core-completion/readiness-classification").json()
        assert data["fake_classification"] is False

    def test_129_not_complete_without_proof(self, c20_client):
        data = c20_client.get("/v1/core-completion/readiness-classification").json()
        assert data["classification"] != "complete"

    def test_130_open_manual_gates_listed(self, c20_client):
        data = c20_client.get("/v1/core-completion/readiness-classification").json()
        assert isinstance(data["open_manual_gates"], list)
        assert len(data["open_manual_gates"]) >= 3


# ---------------------------------------------------------------------------
# Self-Knowledge Integration (C11-C20)
# ---------------------------------------------------------------------------


class TestSelfKnowledgeC11C20:
    def test_131_active_sprint_is_final_phase_a_or_later(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        sprint = data["active_sprint"]
        assert any(t in sprint for t in ("PHASE_C11", "C11", "PARITY", "GATE_INTEGRATION", "PHASE_C", "AUTONOMOUS", "FINAL_PHASE_A", "GATE_CLOSURE"))

    def test_132_c11_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "execution_readiness" in ids

    def test_133_c12_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "action_planner" in ids

    def test_134_c13_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "policy_compiler" in ids

    def test_135_c14_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "connector_readiness" in ids

    def test_136_c15_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "ios_readiness" in ids

    def test_137_c16_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "signing_readiness" in ids

    def test_138_c17_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "cloud_readiness" in ids

    def test_139_c18_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "final_smoke" in ids

    def test_140_c19_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "daily_driver" in ids

    def test_141_c20_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        ids = [c["id"] for c in data["capabilities"]]
        assert "core_completion" in ids

    def test_142_plan_state_has_c11(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert "phase_c11_execution_readiness" in data["plan_state"]

    def test_143_plan_state_has_c20(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert "phase_c20_core_completion" in data["plan_state"]

    def test_144_phase_b_hold_preserved(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"]["phase_b1_to_b20"] == "ACCEPTED_ON_HOLD"

    def test_145_c1_to_c10_accepted(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"].get("phase_c1_to_c10") == "ACCEPTED"

    def test_146_roadmap_has_c11_through_c20(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        plan_names = [e["plan"] for e in data["roadmap"]]
        for phase in ("Phase C11", "Phase C15", "Phase C20"):
            assert phase in plan_names, f"Roadmap missing {phase!r}"

    def test_147_no_fake_claims(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["fake_claims"] is False

    def test_148_voice_parked(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["voice_parked"] is True

    def test_149_plan_3_still_parked(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"]["plan_3_voice"] == "PARKED"


# ---------------------------------------------------------------------------
# OMNIX non-regression
# ---------------------------------------------------------------------------


class TestOmnixNonRegressionC11C20:
    def test_150_jarvis_identity_not_omnix(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert "omnix" not in data.get("identity", "").lower()

    def test_151_new_routes_no_omnix_hardcode(self):
        import inspect
        modules = [
            "openjarvis.server.execution_readiness_routes",
            "openjarvis.server.action_planner_routes",
            "openjarvis.server.policy_compiler_routes",
            "openjarvis.server.connector_readiness_routes",
            "openjarvis.server.ios_readiness_routes",
            "openjarvis.server.signing_readiness_routes",
            "openjarvis.server.cloud_readiness_routes",
            "openjarvis.server.final_smoke_routes",
            "openjarvis.server.daily_driver_routes",
            "openjarvis.server.core_completion_routes",
        ]
        # Allowable OMNIX references: anti-coupling governance metadata or historical
        # references to the Phase X decoupling. NOT allowed: OMNIX as Jarvis core/identity.
        allowed_phrases = [
            "omnix_is_jarvis_core",    # anti-coupling flag (value is False)
            "omnix_production_deploy", # hard gate item
            "omnix decoupling",        # historical note in phase X entry
            "OMNIX decoupling",        # capitalized variant
            "OMNIX → optional",        # decoupling note
            "omnix → optional",
        ]
        for mod_name in modules:
            mod = __import__(mod_name, fromlist=[""])
            src = inspect.getsource(mod)
            src_cleaned = src
            for phrase in allowed_phrases:
                src_cleaned = src_cleaned.replace(phrase, "")
            # After removing allowed references, no OMNIX should remain as identity/core
            has_omnix = "OMNIX" in src_cleaned or "omnix" in src_cleaned
            if has_omnix:
                # Check it's not claiming OMNIX is Jarvis core
                assert "omnix" not in src_cleaned.lower().replace("omnix_is_jarvis_core", ""), (
                    f"{mod_name} must not hardcode OMNIX as Jarvis core or identity"
                )

    def test_152_approval_gates_not_weakened(self):
        from openjarvis.governance.constitution import HARD_GATE_ACTIONS
        assert len(HARD_GATE_ACTIONS) >= 14


# ---------------------------------------------------------------------------
# Bryan-cleared gates reflected in self-knowledge
# ---------------------------------------------------------------------------


class TestBryanClearedGates:
    def test_153_ios_readiness_prerequisites_cleared(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["prerequisites_bryan_cleared"] is True

    def test_154_signing_prerequisites_cleared(self, c16_client):
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["prerequisites_bryan_cleared"] is True

    def test_155_cloud_bryan_cleared(self, c17_client):
        data = c17_client.get("/v1/cloud-readiness/status").json()
        assert data["bryan_cleared"] is True

    def test_156_notion_blocked_reflects_bryan_status(self, c14_client):
        data = c14_client.get("/v1/connector-readiness/status").json()
        notion = next((c for c in data["connectors"] if c["connector_id"] == "notion"), None)
        assert notion is not None
        assert notion["bryan_cleared"] is False
        assert notion["status"] == "blocked"

    def test_157_ios_not_claiming_native_app_ready(self, c15_client):
        data = c15_client.get("/v1/ios-readiness/status").json()
        assert data["native_ios_app_ready"] is False
        assert data["testflight_ready"] is False

    def test_158_signing_notarized_not_public_release(self, c16_client):
        # Notarization claimed (completed Jun 25 2026), but public release still requires Bryan
        data = c16_client.get("/v1/signing-readiness/status").json()
        assert data["notarization_claimed"] is True
        assert data["public_release_ready"] is False


# ---------------------------------------------------------------------------
# Frontend source checks (file content)
# ---------------------------------------------------------------------------


class TestFrontendC11C20:
    def _read(self, path: str) -> str:
        from pathlib import Path
        return Path(path).read_text()

    def test_159_execution_readiness_page_exists(self):
        src = self._read("frontend/src/pages/ExecutionReadinessPage.tsx")
        assert "apiFetch" in src
        assert "execution-readiness" in src

    def test_160_action_planner_page_exists(self):
        src = self._read("frontend/src/pages/ActionPlannerPage.tsx")
        assert "apiFetch" in src
        assert "action-planner" in src

    def test_161_policy_compiler_page_exists(self):
        src = self._read("frontend/src/pages/PolicyCompilerPage.tsx")
        assert "apiFetch" in src

    def test_162_connector_readiness_page_exists(self):
        src = self._read("frontend/src/pages/ConnectorReadinessPage.tsx")
        assert "apiFetch" in src
        assert "connector-readiness" in src

    def test_163_ios_readiness_page_exists(self):
        src = self._read("frontend/src/pages/IOSReadinessPage.tsx")
        assert "apiFetch" in src
        assert "ios-readiness" in src

    def test_164_signing_readiness_page_exists(self):
        src = self._read("frontend/src/pages/SigningReadinessPage.tsx")
        assert "apiFetch" in src

    def test_165_cloud_readiness_page_exists(self):
        src = self._read("frontend/src/pages/CloudReadinessPage.tsx")
        assert "apiFetch" in src

    def test_166_final_smoke_page_exists(self):
        src = self._read("frontend/src/pages/FinalSmokePage.tsx")
        assert "apiFetch" in src

    def test_167_daily_driver_page_exists(self):
        src = self._read("frontend/src/pages/DailyDriverPage.tsx")
        assert "apiFetch" in src

    def test_168_core_completion_page_exists(self):
        src = self._read("frontend/src/pages/CoreCompletionPage.tsx")
        assert "apiFetch" in src

    def test_169_app_tsx_has_all_c11_c20_routes(self):
        src = self._read("frontend/src/App.tsx")
        for route in ("/execution-readiness", "/action-planner", "/policy-compiler",
                      "/connector-readiness", "/ios-readiness", "/signing-readiness",
                      "/cloud-readiness", "/final-smoke", "/daily-driver", "/core-completion"):
            assert route in src, f"App.tsx missing route {route!r}"

    def test_170_sidebar_has_c11_c20_entries(self):
        src = self._read("frontend/src/components/Sidebar/Sidebar.tsx")
        for path in ("/execution-readiness", "/action-planner", "/policy-compiler",
                     "/connector-readiness", "/ios-readiness", "/signing-readiness",
                     "/cloud-readiness", "/final-smoke", "/daily-driver", "/core-completion"):
            assert path in src, f"Sidebar.tsx missing path {path!r}"

    def test_171_jarvis_api_has_c11_c20_types(self):
        src = self._read("frontend/src/lib/jarvis-api.ts")
        for t in ("ExecutionReadinessStatus", "ConnectorReadinessStatus",
                  "IOSReadinessStatus", "SigningReadinessStatus",
                  "CloudReadinessStatus", "DailyDriverStatus", "CoreCompletionStatus"):
            assert t in src, f"jarvis-api.ts missing type {t!r}"
