"""Tests for Phase B13-B20 — Deep Safe Jarvis OS Expansion.

Covers:
  B13 — Personal Finance / Admin OS
  B14 — Research / Learning / Company-Building OS
  B15 — Browser / Web Operator Foundation
  B16 — Advanced Memory + Knowledge Graph
  B17 — Multi-Device / Phone-Controlled Workbench
  B18 — Skills Marketplace / Third-Party Plugin Ecosystem
  B19 — Team / Multi-User / Organization Mode Foundation
  B20 — Robotics / Device Controller Foundation
  Self-knowledge B13-B20 integration
  OMNIX non-regression (Phase X)
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures — router-level (no create_app needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def finance_client():
    from openjarvis.server.finance_admin_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def research_client():
    from openjarvis.server.research_os_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def browser_client():
    from openjarvis.server.browser_operator_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def memgraph_client():
    from openjarvis.server.memory_graph_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def multidev_client():
    from openjarvis.server.multi_device_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def market_client():
    from openjarvis.server.marketplace_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def org_client():
    from openjarvis.server.org_mode_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(scope="module")
def device_client():
    from openjarvis.server.device_controller_routes import router
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
# B13 — Finance / Admin OS  (tests 1-10)
# ---------------------------------------------------------------------------

class TestB13FinanceAdminOS:
    def test_01_dashboard_returns_200(self, finance_client):
        res = finance_client.get("/v1/finance-admin/dashboard")
        assert res.status_code == 200

    def test_02_dashboard_has_categories(self, finance_client):
        data = finance_client.get("/v1/finance-admin/dashboard").json()
        assert "categories" in data
        assert isinstance(data["categories"], list)
        assert len(data["categories"]) > 0

    def test_03_dashboard_no_live_financial_execution(self, finance_client):
        data = finance_client.get("/v1/finance-admin/dashboard").json()
        assert data["live_financial_execution"] is False

    def test_04_dashboard_fake_completion_false(self, finance_client):
        data = finance_client.get("/v1/finance-admin/dashboard").json()
        assert data["fake_completion"] is False
        assert data["fake_data"] is False

    def test_05_dashboard_approval_gates_active(self, finance_client):
        data = finance_client.get("/v1/finance-admin/dashboard").json()
        assert data["approval_gates_active"] is True

    def test_06_tasks_returns_200(self, finance_client):
        res = finance_client.get("/v1/finance-admin/tasks")
        assert res.status_code == 200

    def test_07_tasks_fake_data_false(self, finance_client):
        data = finance_client.get("/v1/finance-admin/tasks").json()
        assert data["fake_data"] is False

    def test_08_tasks_has_tasks_field(self, finance_client):
        data = finance_client.get("/v1/finance-admin/tasks").json()
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    def test_09_summary_returns_200(self, finance_client):
        res = finance_client.get("/v1/finance-admin/summary")
        assert res.status_code == 200

    def test_10_summary_no_live_financial_execution(self, finance_client):
        data = finance_client.get("/v1/finance-admin/summary").json()
        assert data["live_financial_execution"] is False
        assert data["fake_data"] is False


# ---------------------------------------------------------------------------
# B14 — Research / Learning / Company-Building OS  (tests 11-20)
# ---------------------------------------------------------------------------

class TestB14ResearchOS:
    def test_11_dashboard_returns_200(self, research_client):
        res = research_client.get("/v1/research-os/dashboard")
        assert res.status_code == 200

    def test_12_dashboard_no_live_web_retrieval(self, research_client):
        data = research_client.get("/v1/research-os/dashboard").json()
        assert data["live_web_retrieval"] is False

    def test_13_dashboard_no_fake_research(self, research_client):
        data = research_client.get("/v1/research-os/dashboard").json()
        assert data["fake_research"] is False
        assert data["fake_data"] is False

    def test_14_dashboard_has_sections(self, research_client):
        data = research_client.get("/v1/research-os/dashboard").json()
        assert "sections" in data
        assert len(data["sections"]) > 0

    def test_15_queue_returns_200(self, research_client):
        res = research_client.get("/v1/research-os/queue")
        assert res.status_code == 200

    def test_16_queue_fake_data_false(self, research_client):
        data = research_client.get("/v1/research-os/queue").json()
        assert data["fake_data"] is False

    def test_17_templates_returns_200(self, research_client):
        res = research_client.get("/v1/research-os/templates")
        assert res.status_code == 200

    def test_18_templates_no_live_output(self, research_client):
        data = research_client.get("/v1/research-os/templates").json()
        assert data["live_output"] is False
        assert data["fake_research"] is False

    def test_19_templates_has_template_list(self, research_client):
        data = research_client.get("/v1/research-os/templates").json()
        assert "templates" in data
        assert len(data["templates"]) >= 3

    def test_20_summary_returns_200(self, research_client):
        res = research_client.get("/v1/research-os/summary")
        assert res.status_code == 200


# ---------------------------------------------------------------------------
# B15 — Browser / Web Operator Foundation  (tests 21-30)
# ---------------------------------------------------------------------------

class TestB15BrowserOperator:
    def test_21_status_returns_200(self, browser_client):
        res = browser_client.get("/v1/browser-operator/status")
        assert res.status_code == 200

    def test_22_browser_operator_not_available(self, browser_client):
        data = browser_client.get("/v1/browser-operator/status").json()
        assert data["browser_operator_available"] is False

    def test_23_dry_run_only(self, browser_client):
        data = browser_client.get("/v1/browser-operator/status").json()
        assert data["dry_run_only"] is True

    def test_24_fake_live_false(self, browser_client):
        data = browser_client.get("/v1/browser-operator/status").json()
        assert data["fake_live"] is False
        assert data["fake_data"] is False

    def test_25_safety_no_credential_injection(self, browser_client):
        data = browser_client.get("/v1/browser-operator/status").json()
        safety = data["safety"]
        # Agent may use login_blocked or no_credential_injection — either is valid
        has_cred_block = safety.get("login_blocked") is True or safety.get("no_credential_injection") is True
        assert has_cred_block, f"safety must block credential injection/login; got {safety}"

    def test_26_capability_matrix_returns_200(self, browser_client):
        res = browser_client.get("/v1/browser-operator/capability-matrix")
        assert res.status_code == 200

    def test_27_capability_matrix_authentication_highest_tier(self, browser_client):
        data = browser_client.get("/v1/browser-operator/capability-matrix").json()
        # Auth/login category must exist under any name containing "auth" or "login"
        auth_cat = next(
            (c for c in data["categories"] if "auth" in c["category"].lower() or "login" in c["category"].lower()),
            None,
        )
        assert auth_cat is not None, "Capability matrix must include an authentication/login category"
        # Must be blocked (tier4 minimum, or "blocked", or "Tier 4")
        tier = str(auth_cat.get("approval_tier", "")).lower()
        assert "4" in tier or "block" in tier or tier == "tier4", (
            f"Auth category must require Tier 4 or be blocked, got: {tier}"
        )

    def test_28_plan_endpoint_dry_run_only(self, browser_client):
        res = browser_client.post("/v1/browser-operator/plan", json={"action": "navigate", "url": "https://example.com", "parameters": {}, "reason": "test"})
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["browser_live"] is False

    def test_29_plan_endpoint_validates_action(self, browser_client):
        res = browser_client.post("/v1/browser-operator/plan", json={"action": "", "url": "https://example.com", "parameters": {}, "reason": "test"})
        assert res.status_code == 422

    def test_30_browser_status_no_credential_values(self, browser_client):
        data = browser_client.get("/v1/browser-operator/status").json()
        text = str(data)
        for prefix in ("xoxb-", "ghp_", "AKIA", "sk-proj-", "Bearer "):
            assert prefix not in text


# ---------------------------------------------------------------------------
# B16 — Advanced Memory + Knowledge Graph  (tests 31-40)
# ---------------------------------------------------------------------------

class TestB16MemoryGraph:
    def test_31_status_returns_200(self, memgraph_client):
        res = memgraph_client.get("/v1/memory-graph/status")
        assert res.status_code == 200

    def test_32_entity_extraction_false(self, memgraph_client):
        data = memgraph_client.get("/v1/memory-graph/status").json()
        assert data["entity_extraction"] is False

    def test_33_knowledge_graph_not_live(self, memgraph_client):
        data = memgraph_client.get("/v1/memory-graph/status").json()
        assert data["knowledge_graph_live"] is False

    def test_34_cloud_sync_not_live(self, memgraph_client):
        data = memgraph_client.get("/v1/memory-graph/status").json()
        assert data["cloud_sync_live"] is False

    def test_35_fake_data_false(self, memgraph_client):
        data = memgraph_client.get("/v1/memory-graph/status").json()
        assert data["fake_data"] is False

    def test_36_namespaces_returns_200(self, memgraph_client):
        res = memgraph_client.get("/v1/memory-graph/namespaces")
        assert res.status_code == 200

    def test_37_namespaces_not_cloud_backed(self, memgraph_client):
        data = memgraph_client.get("/v1/memory-graph/namespaces").json()
        assert data["cloud_backed"] is False

    def test_38_metadata_returns_200(self, memgraph_client):
        res = memgraph_client.get("/v1/memory-graph/metadata")
        assert res.status_code == 200

    def test_39_metadata_semantic_search_false(self, memgraph_client):
        data = memgraph_client.get("/v1/memory-graph/metadata").json()
        assert data["capabilities"]["semantic_search"] is False
        assert data["capabilities"]["entity_extraction"] is False

    def test_40_search_validates_empty_query(self, memgraph_client):
        res = memgraph_client.post("/v1/memory-graph/search", json={"query": "", "namespace": "all", "limit": 10})
        assert res.status_code == 422


# ---------------------------------------------------------------------------
# B17 — Multi-Device / Phone-Controlled Workbench  (tests 41-50)
# ---------------------------------------------------------------------------

class TestB17MultiDevice:
    def test_41_status_returns_200(self, multidev_client):
        res = multidev_client.get("/v1/multi-device/status")
        assert res.status_code == 200

    def test_42_phone_control_not_live(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/status").json()
        assert data["phone_control_live"] is False

    def test_43_macbook_off_not_live(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/status").json()
        assert data["macbook_off_cloud_execution_live"] is False

    def test_44_fargate_not_live(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/status").json()
        assert data["fargate_cloud_live"] is False

    def test_45_fake_live_false(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/status").json()
        assert data["fake_live"] is False
        assert data["fake_data"] is False

    def test_46_capability_matrix_returns_200(self, multidev_client):
        res = multidev_client.get("/v1/multi-device/capability-matrix")
        assert res.status_code == 200

    def test_47_capability_matrix_no_fake_live(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/capability-matrix").json()
        assert data["fake_live"] is False

    def test_48_workbench_queue_returns_200(self, multidev_client):
        res = multidev_client.get("/v1/multi-device/workbench-queue")
        assert res.status_code == 200

    def test_49_workbench_queue_no_phone_control(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/workbench-queue").json()
        assert data["phone_control_available"] is False
        assert data["remote_execution_available"] is False

    def test_50_status_has_sessions(self, multidev_client):
        data = multidev_client.get("/v1/multi-device/status").json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)


# ---------------------------------------------------------------------------
# B18 — Skills Marketplace / Plugin Ecosystem  (tests 51-60)
# ---------------------------------------------------------------------------

class TestB18Marketplace:
    def test_51_status_returns_200(self, market_client):
        res = market_client.get("/v1/marketplace/status")
        assert res.status_code == 200

    def test_52_marketplace_not_live(self, market_client):
        data = market_client.get("/v1/marketplace/status").json()
        assert data["marketplace_live"] is False

    def test_53_auto_install_false(self, market_client):
        data = market_client.get("/v1/marketplace/status").json()
        assert data["auto_install"] is False
        assert data["network_install"] is False

    def test_54_fake_marketplace_false(self, market_client):
        data = market_client.get("/v1/marketplace/status").json()
        assert data["fake_marketplace"] is False
        assert data["fake_data"] is False

    def test_55_plugins_returns_200(self, market_client):
        res = market_client.get("/v1/marketplace/plugins")
        assert res.status_code == 200

    def test_56_plugins_not_marketplace_verified(self, market_client):
        data = market_client.get("/v1/marketplace/plugins").json()
        assert data["marketplace_live"] is False
        for plugin in data["plugins"]:
            assert plugin["marketplace_verified"] is False

    def test_57_review_dry_run(self, market_client):
        res = market_client.post("/v1/marketplace/plugins/review", json={"plugin_id": "test-plugin", "action": "approve", "reason": "test"})
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["would_install"] is False

    def test_58_review_invalid_action_rejected(self, market_client):
        res = market_client.post("/v1/marketplace/plugins/review", json={"plugin_id": "test-plugin", "action": "install_now", "reason": "bypass"})
        assert res.status_code == 422

    def test_59_review_queue_returns_200(self, market_client):
        res = market_client.get("/v1/marketplace/review-queue")
        assert res.status_code == 200

    def test_60_review_queue_human_review_required(self, market_client):
        data = market_client.get("/v1/marketplace/review-queue").json()
        assert data["human_review_required"] is True
        assert data["auto_review"] is False


# ---------------------------------------------------------------------------
# B19 — Team / Multi-User / Organization Mode Foundation  (tests 61-70)
# ---------------------------------------------------------------------------

class TestB19OrgMode:
    def test_61_status_returns_200(self, org_client):
        res = org_client.get("/v1/org-mode/status")
        assert res.status_code == 200

    def test_62_multi_user_not_live(self, org_client):
        data = org_client.get("/v1/org-mode/status").json()
        assert data["multi_user_live"] is False

    def test_63_org_mode_not_available(self, org_client):
        data = org_client.get("/v1/org-mode/status").json()
        assert data["org_mode_available"] is False

    def test_64_single_user_mode(self, org_client):
        data = org_client.get("/v1/org-mode/status").json()
        assert data["single_user_mode"] is True

    def test_65_production_auth_not_ready(self, org_client):
        data = org_client.get("/v1/org-mode/status").json()
        assert data["production_auth_ready"] is False
        assert data["fake_data"] is False

    def test_66_capability_matrix_returns_200(self, org_client):
        res = org_client.get("/v1/org-mode/capability-matrix")
        assert res.status_code == 200

    def test_67_all_capabilities_unavailable(self, org_client):
        data = org_client.get("/v1/org-mode/capability-matrix").json()
        for cap in data["capabilities"]:
            assert cap["available"] is False

    def test_68_dry_run_invite_never_echoes_email(self, org_client):
        res = org_client.post("/v1/org-mode/dry-run/invite", json={"email": "real@example.com", "role": "member", "message": "hi"})
        assert res.status_code == 200
        data = res.json()
        assert data["email"] == "<redacted>", "Email must never be echoed back"
        assert data["executed"] is False

    def test_69_dry_run_invite_not_executed(self, org_client):
        res = org_client.post("/v1/org-mode/dry-run/invite", json={"email": "test@test.com", "role": "admin", "message": "invite"})
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["would_send_invite"] is False

    def test_70_org_mode_no_credential_values(self, org_client):
        data = org_client.get("/v1/org-mode/status").json()
        text = str(data)
        for prefix in ("xoxb-", "ghp_", "AKIA", "sk-proj-"):
            assert prefix not in text


# ---------------------------------------------------------------------------
# B20 — Robotics / Device Controller Foundation  (tests 71-80)
# ---------------------------------------------------------------------------

class TestB20DeviceController:
    def test_71_status_returns_200(self, device_client):
        res = device_client.get("/v1/device-controller/status")
        assert res.status_code == 200

    def test_72_device_control_not_live(self, device_client):
        data = device_client.get("/v1/device-controller/status").json()
        assert data["device_control_live"] is False

    def test_73_robotics_not_available(self, device_client):
        data = device_client.get("/v1/device-controller/status").json()
        assert data["robotics_available"] is False

    def test_74_physical_world_execution_false(self, device_client):
        data = device_client.get("/v1/device-controller/status").json()
        assert data["physical_world_execution"] is False

    def test_75_fake_live_false(self, device_client):
        data = device_client.get("/v1/device-controller/status").json()
        assert data["fake_live"] is False
        assert data["fake_data"] is False

    def test_76_safety_physical_actions_blocked(self, device_client):
        data = device_client.get("/v1/device-controller/status").json()
        assert data["safety"]["physical_actions_blocked"] is True
        assert data["safety"]["dry_run_only"] is True
        assert data["safety"]["approval_required"] is True

    def test_77_commands_plan_dry_run(self, device_client):
        res = device_client.post("/v1/device-controller/commands/plan", json={"device_type": "smart_home", "command": "turn_on", "parameters": {}, "reason": "test"})
        assert res.status_code == 200
        data = res.json()
        assert data["dry_run"] is True
        assert data["executed"] is False
        assert data["physical_action"] is False
        assert data["device_live"] is False

    def test_78_commands_plan_validates_device_type(self, device_client):
        res = device_client.post("/v1/device-controller/commands/plan", json={"device_type": "", "command": "run", "parameters": {}, "reason": "test"})
        assert res.status_code == 422

    def test_79_commands_plan_validates_command(self, device_client):
        res = device_client.post("/v1/device-controller/commands/plan", json={"device_type": "iot_sensor", "command": "", "parameters": {}, "reason": "test"})
        assert res.status_code == 422

    def test_80_safety_matrix_returns_200(self, device_client):
        res = device_client.get("/v1/device-controller/safety-matrix")
        assert res.status_code == 200

    def test_80b_safety_matrix_all_enforced(self, device_client):
        data = device_client.get("/v1/device-controller/safety-matrix").json()
        for rule in data["safety_rules"]:
            assert rule["enforced"] is True
        assert data["physical_world_execution"] is False


# ---------------------------------------------------------------------------
# Self-knowledge B13-B20 integration  (tests 81-90)
# ---------------------------------------------------------------------------

class TestSelfKnowledgeB13ToB20:
    def test_81_finance_admin_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "finance_admin_os" in cap_ids

    def test_82_research_os_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "research_os" in cap_ids

    def test_83_browser_operator_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "browser_operator" in cap_ids

    def test_84_memory_graph_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "memory_graph" in cap_ids

    def test_85_multi_device_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "multi_device" in cap_ids

    def test_86_marketplace_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "marketplace" in cap_ids

    def test_87_org_mode_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "org_mode" in cap_ids

    def test_88_device_controller_capability_present(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "device_controller" in cap_ids

    def test_89_b13_b20_in_plan_state(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        plan_state = data["plan_state"]
        for key in ("phase_b13_finance_admin", "phase_b14_research_os",
                    "phase_b15_browser_operator", "phase_b16_memory_graph",
                    "phase_b17_multi_device", "phase_b18_marketplace",
                    "phase_b19_org_mode", "phase_b20_device_controller"):
            assert key in plan_state, f"plan_state missing key: {key}"
            assert plan_state[key] == "IN_PROGRESS"

    def test_90_active_sprint_is_b13_b20_or_later(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        sprint = data["active_sprint"]
        # Sprint advances through phases — B13-B20, Phase C, Final Phase A, or later are all valid
        assert any(t in sprint for t in ("PHASE_B13", "B13_TO_B20", "DEEP", "EXPANSION", "PHASE_C", "AUTONOMOUS", "FINAL_PHASE_A", "GATE_CLOSURE"))


# ---------------------------------------------------------------------------
# OMNIX non-regression + prior plan acceptance  (tests 91-95)
# ---------------------------------------------------------------------------

class TestOmnixNonRegression:
    def test_91_jarvis_identity_not_omnix(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("primary_project") != "omnix"

    def test_92_jarvis_identity_name_is_jarvis(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("name") == "Jarvis"

    def test_93_plan_4_6_still_accepted(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"]["plan_4_6_mega_sprint"] == "ACCEPTED"

    def test_94_phase_x_still_accepted(self, sk_client):
        data = sk_client.get("/v1/jarvis/status").json()
        assert data["plan_state"]["phase_x_decoupling"] == "ACCEPTED"

    def test_95_b13_route_no_omnix_hardcode(self):
        import inspect
        from openjarvis.server import finance_admin_routes
        source = inspect.getsource(finance_admin_routes)
        # OMNIX may appear only in comments or as an optional adapter reference
        lines_with_omnix = [
            line for line in source.split("\n")
            if "OMNIX" in line.upper() and not line.strip().startswith("#")
        ]
        assert len(lines_with_omnix) == 0, (
            f"finance_admin_routes must not reference OMNIX as Jarvis core: {lines_with_omnix}"
        )
