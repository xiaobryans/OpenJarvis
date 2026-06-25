"""Phase B7-B12 backend behavior tests for OpenJarvis.

Covers:
  Phase B7  — Skills / Plugin Expansion (GET /v1/skills/catalog/summary, /v1/skills/permissions,
               POST /v1/skills/intake/dry-run, GET /v1/skills/intake/queue)
  Phase B8  — Connector Workflows (GET /v1/connector-workflows,
               GET /v1/connector-workflows/summary,
               POST /v1/connector-workflows/{workflow_id}/dry-run)
  Phase B9  — Proactive Operator (GET /v1/proactive/suggestions,
               GET /v1/proactive/stale-items, GET /v1/proactive/next-actions)
  Phase B10 — Business / Admin Operator (GET /v1/business-admin/dashboard,
               GET /v1/business-admin/workflows, GET /v1/business-admin/summary)
  Phase B11 — Observability (GET /v1/observability/health-summary,
               GET /v1/observability/reliability-metrics, GET /v1/observability/audit-log)
  Phase B12 — Long-Horizon Goals (GET /v1/long-horizon/goals,
               GET /v1/long-horizon/summary,
               POST /v1/long-horizon/goals/{goal_id}/plan-step)
  Self-Knowledge integration (GET /v1/jarvis/capabilities, /v1/jarvis/status, /v1/jarvis/roadmap)
  OMNIX non-regression

Test rules:
  - No shared mutable state.
  - All body access via response.json().
  - No secret reads, no env inspection.
  - File must parse cleanly.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.skills_expansion_routes import router as skills_expansion_router
from openjarvis.server.connector_workflow_routes import router as connector_workflow_router
from openjarvis.server.proactive_routes import router as proactive_router
from openjarvis.server.business_admin_routes import router as business_admin_router
from openjarvis.server.observability_routes import router as observability_router
from openjarvis.server.long_horizon_routes import router as long_horizon_router
from openjarvis.server.self_knowledge_routes import router as self_knowledge_router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(skills_expansion_router)
    app.include_router(connector_workflow_router)
    app.include_router(proactive_router)
    app.include_router(business_admin_router)
    app.include_router(observability_router)
    app.include_router(long_horizon_router)
    app.include_router(self_knowledge_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# B7 Skills / Plugin Expansion (tests 1-10)
# ---------------------------------------------------------------------------


def test_skills_catalog_summary_200(client: TestClient) -> None:
    """GET /v1/skills/catalog/summary returns 200."""
    response = client.get("/v1/skills/catalog/summary")
    assert response.status_code == 200


def test_skills_catalog_summary_no_fake_data(client: TestClient) -> None:
    """Response has fake_data=False."""
    response = client.get("/v1/skills/catalog/summary")
    data = response.json()
    assert data["fake_data"] is False


def test_skills_catalog_summary_shape(client: TestClient) -> None:
    """Response has required keys: total, available, blocked, disabled, planned, has_intake_queue, marketplace_live."""
    response = client.get("/v1/skills/catalog/summary")
    data = response.json()
    for key in ("total", "available", "blocked", "disabled", "planned", "has_intake_queue", "marketplace_live"):
        assert key in data, f"missing key: {key}"


def test_skills_catalog_marketplace_not_live(client: TestClient) -> None:
    """marketplace_live=False — third-party marketplace not active."""
    response = client.get("/v1/skills/catalog/summary")
    data = response.json()
    assert data["marketplace_live"] is False


def test_skills_catalog_intake_not_automated(client: TestClient) -> None:
    """has_intake_queue=False — no automated third-party intake pipeline."""
    response = client.get("/v1/skills/catalog/summary")
    data = response.json()
    assert data["has_intake_queue"] is False


def test_skills_permissions_200(client: TestClient) -> None:
    """GET /v1/skills/permissions returns 200."""
    response = client.get("/v1/skills/permissions")
    assert response.status_code == 200


def test_skills_permissions_gates_active(client: TestClient) -> None:
    """Response has permission_gates_active==True."""
    response = client.get("/v1/skills/permissions")
    data = response.json()
    assert data["permission_gates_active"] is True


def test_skills_intake_dry_run_valid_manifest(client: TestClient) -> None:
    """POST /v1/skills/intake/dry-run with valid manifest returns 200, would_install=False."""
    payload = {
        "manifest": {
            "name": "test",
            "description": "test skill",
            "safety_level": "low",
            "actions": [],
        }
    }
    response = client.post("/v1/skills/intake/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["would_install"] is False


def test_skills_intake_dry_run_invalid_manifest(client: TestClient) -> None:
    """POST /v1/skills/intake/dry-run with missing name returns 200 with valid=False."""
    payload = {"manifest": {}}
    response = client.post("/v1/skills/intake/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


def test_skills_intake_queue_empty(client: TestClient) -> None:
    """GET /v1/skills/intake/queue returns 200, intake_automated=False, review_required=True."""
    response = client.get("/v1/skills/intake/queue")
    assert response.status_code == 200
    data = response.json()
    assert data["intake_automated"] is False
    assert data["review_required"] is True


# ---------------------------------------------------------------------------
# B8 Connector Workflows (tests 11-20)
# ---------------------------------------------------------------------------


def test_connector_workflows_200(client: TestClient) -> None:
    """GET /v1/connector-workflows returns 200."""
    response = client.get("/v1/connector-workflows")
    assert response.status_code == 200


def test_connector_workflows_no_fake_data(client: TestClient) -> None:
    """Response has fake_data=False."""
    response = client.get("/v1/connector-workflows")
    data = response.json()
    assert data["fake_data"] is False


def test_connector_workflows_no_fake_live(client: TestClient) -> None:
    """Top-level response has fake_live=False."""
    response = client.get("/v1/connector-workflows")
    data = response.json()
    assert data["fake_live"] is False


def test_connector_workflows_shape(client: TestClient) -> None:
    """Response has: connectors (list), live_connector_count (int), configured_count (int), total (int)."""
    response = client.get("/v1/connector-workflows")
    data = response.json()
    assert isinstance(data["connectors"], list)
    assert isinstance(data["live_connector_count"], int)
    assert isinstance(data["configured_count"], int)
    assert isinstance(data["total"], int)


def test_connector_workflows_all_have_fake_live_false(client: TestClient) -> None:
    """Every connector object in connectors has fake_live=False."""
    response = client.get("/v1/connector-workflows")
    data = response.json()
    for connector in data["connectors"]:
        assert connector["fake_live"] is False, (
            f"connector {connector.get('connector_id')} has fake_live != False"
        )


def test_connector_workflows_dry_run_only_unconfigured(client: TestClient) -> None:
    """For connectors with status=='not_configured', all their workflows have dry_run_only=True."""
    response = client.get("/v1/connector-workflows")
    data = response.json()
    for connector in data["connectors"]:
        if connector.get("status") == "not_configured":
            for wf in connector.get("available_workflows", []):
                assert wf["dry_run_only"] is True, (
                    f"connector {connector.get('connector_id')} workflow "
                    f"{wf.get('workflow_id')} not marked dry_run_only despite not_configured"
                )


def test_connector_workflows_summary_200(client: TestClient) -> None:
    """GET /v1/connector-workflows/summary returns 200."""
    response = client.get("/v1/connector-workflows/summary")
    assert response.status_code == 200


def test_connector_workflows_summary_no_fake_data(client: TestClient) -> None:
    """Connector workflows summary has fake_data=False."""
    response = client.get("/v1/connector-workflows/summary")
    data = response.json()
    assert data["fake_data"] is False


def test_connector_dry_run_endpoint_unknown(client: TestClient) -> None:
    """POST /v1/connector-workflows/nonexistent_workflow_id/dry-run returns 404."""
    response = client.post(
        "/v1/connector-workflows/nonexistent_workflow_id/dry-run",
        json={"connector_id": "slack", "parameters": {}},
    )
    assert response.status_code == 404


def test_connector_dry_run_no_execution(client: TestClient) -> None:
    """POST /v1/connector-workflows/slack_send_message/dry-run returns 200 with would_execute=False, or 404."""
    response = client.post(
        "/v1/connector-workflows/slack_send_message/dry-run",
        json={"connector_id": "slack", "parameters": {}},
    )
    if response.status_code == 200:
        data = response.json()
        assert data["would_execute"] is False
    else:
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# B9 Proactive Operator (tests 21-30)
# ---------------------------------------------------------------------------


def test_proactive_suggestions_200(client: TestClient) -> None:
    """GET /v1/proactive/suggestions returns 200."""
    response = client.get("/v1/proactive/suggestions")
    assert response.status_code == 200


def test_proactive_suggestions_no_fake_data(client: TestClient) -> None:
    """Proactive suggestions response has fake_data=False."""
    response = client.get("/v1/proactive/suggestions")
    data = response.json()
    assert data["fake_data"] is False


def test_proactive_suggestions_execution_blocked(client: TestClient) -> None:
    """Proactive suggestions response has execution_blocked=True."""
    response = client.get("/v1/proactive/suggestions")
    data = response.json()
    assert data["execution_blocked"] is True


def test_proactive_suggestions_approval_gates_preserved(client: TestClient) -> None:
    """Proactive suggestions response has approval_gates_preserved=True."""
    response = client.get("/v1/proactive/suggestions")
    data = response.json()
    assert data["approval_gates_preserved"] is True


def test_proactive_suggestions_no_auto_execute(client: TestClient) -> None:
    """Proactive suggestions response does not contain auto_execute set to True."""
    response = client.get("/v1/proactive/suggestions")
    data = response.json()
    # If the key exists it must not be True
    if "auto_execute" in data:
        assert data["auto_execute"] is not True
    # Also ensure the raw JSON string does not carry '"auto_execute": true'
    raw = json.dumps(data)
    assert '"auto_execute": true' not in raw


def test_proactive_stale_items_200(client: TestClient) -> None:
    """GET /v1/proactive/stale-items returns 200."""
    response = client.get("/v1/proactive/stale-items")
    assert response.status_code == 200


def test_proactive_stale_items_action_blocked(client: TestClient) -> None:
    """Stale-items response has action_blocked=True."""
    response = client.get("/v1/proactive/stale-items")
    data = response.json()
    assert data["action_blocked"] is True


def test_proactive_stale_items_no_fake_data(client: TestClient) -> None:
    """Stale-items response has fake_data=False."""
    response = client.get("/v1/proactive/stale-items")
    data = response.json()
    assert data["fake_data"] is False


def test_proactive_next_actions_200(client: TestClient) -> None:
    """GET /v1/proactive/next-actions returns 200."""
    response = client.get("/v1/proactive/next-actions")
    assert response.status_code == 200


def test_proactive_next_actions_no_auto_execute(client: TestClient) -> None:
    """Next-actions response has auto_execute=False and approval_required_for_any_action=True."""
    response = client.get("/v1/proactive/next-actions")
    data = response.json()
    assert data["auto_execute"] is False
    assert data["approval_required_for_any_action"] is True


# ---------------------------------------------------------------------------
# B10 Business / Admin (tests 31-40)
# ---------------------------------------------------------------------------


def test_business_admin_dashboard_200(client: TestClient) -> None:
    """GET /v1/business-admin/dashboard returns 200."""
    response = client.get("/v1/business-admin/dashboard")
    assert response.status_code == 200


def test_business_admin_no_fake_data(client: TestClient) -> None:
    """Business-admin dashboard has fake_data=False."""
    response = client.get("/v1/business-admin/dashboard")
    data = response.json()
    assert data["fake_data"] is False


def test_business_admin_no_fake_completion(client: TestClient) -> None:
    """Business-admin dashboard top-level has fake_completion=False."""
    response = client.get("/v1/business-admin/dashboard")
    data = response.json()
    assert data["fake_completion"] is False


def test_business_admin_approval_gates_active(client: TestClient) -> None:
    """Business-admin dashboard has approval_gates_active=True."""
    response = client.get("/v1/business-admin/dashboard")
    data = response.json()
    assert data["approval_gates_active"] is True


def test_business_admin_categories_shape(client: TestClient) -> None:
    """Response has 'categories' as a list with at least 1 item; each has required fields."""
    response = client.get("/v1/business-admin/dashboard")
    data = response.json()
    categories = data["categories"]
    assert isinstance(categories, list)
    assert len(categories) >= 1
    for cat in categories:
        for field in ("category_id", "name", "status", "actions", "fake_completion"):
            assert field in cat, f"category missing field: {field}"


def test_business_admin_no_fake_completion_in_categories(client: TestClient) -> None:
    """Every category in business-admin dashboard has fake_completion=False."""
    response = client.get("/v1/business-admin/dashboard")
    data = response.json()
    for cat in data["categories"]:
        assert cat["fake_completion"] is False, (
            f"category {cat.get('category_id')} has fake_completion != False"
        )


def test_business_admin_workflows_200(client: TestClient) -> None:
    """GET /v1/business-admin/workflows returns 200."""
    response = client.get("/v1/business-admin/workflows")
    assert response.status_code == 200


def test_business_admin_workflows_no_fake_data(client: TestClient) -> None:
    """Business-admin workflows response has fake_data=False."""
    response = client.get("/v1/business-admin/workflows")
    data = response.json()
    assert data["fake_data"] is False


def test_business_admin_summary_200(client: TestClient) -> None:
    """GET /v1/business-admin/summary returns 200."""
    response = client.get("/v1/business-admin/summary")
    assert response.status_code == 200


def test_business_admin_summary_approval_gates(client: TestClient) -> None:
    """Business-admin summary has approval_gates_active=True and fake_completion=False."""
    response = client.get("/v1/business-admin/summary")
    data = response.json()
    assert data["approval_gates_active"] is True
    assert data["fake_completion"] is False


# ---------------------------------------------------------------------------
# B11 Observability (tests 41-50)
# ---------------------------------------------------------------------------


def test_observability_health_summary_200(client: TestClient) -> None:
    """GET /v1/observability/health-summary returns 200."""
    response = client.get("/v1/observability/health-summary")
    assert response.status_code == 200


def test_observability_health_no_fake_data(client: TestClient) -> None:
    """Observability health summary has fake_data=False."""
    response = client.get("/v1/observability/health-summary")
    data = response.json()
    assert data["fake_data"] is False


def test_observability_health_shape(client: TestClient) -> None:
    """Response has: components (list), healthy_count (int), overall_status (str)."""
    response = client.get("/v1/observability/health-summary")
    data = response.json()
    assert isinstance(data["components"], list)
    assert isinstance(data["healthy_count"], int)
    assert isinstance(data["overall_status"], str)


def test_observability_health_no_secrets(client: TestClient) -> None:
    """Response JSON does not contain credential value patterns (presence-only check)."""
    response = client.get("/v1/observability/health-summary")
    data = response.json()
    raw = json.dumps(data).lower()
    # Check for token/password/apikey values (not field names like secret_safe which are safe metadata)
    # These patterns indicate actual credential leakage, not metadata field names
    forbidden_values = ("password", "apikey", "key_value")
    for term in forbidden_values:
        assert term not in raw, f"credential-value term '{term}' found in health-summary response"
    # 'secret_safe' is a boolean metadata field — safe. Check no raw token prefix patterns.
    import re
    assert not re.search(r'(sk-|xoxb-|ghp_|AKIA|AIza)', json.dumps(data)), "token prefix found in health-summary"


def test_observability_health_backend_api_healthy(client: TestClient) -> None:
    """The component with component_id=='backend_api' has status=='healthy'."""
    response = client.get("/v1/observability/health-summary")
    data = response.json()
    backend_component = next(
        (c for c in data["components"] if c["component_id"] == "backend_api"), None
    )
    assert backend_component is not None, "backend_api component not found"
    assert backend_component["status"] == "healthy"


def test_observability_reliability_200(client: TestClient) -> None:
    """GET /v1/observability/reliability-metrics returns 200."""
    response = client.get("/v1/observability/reliability-metrics")
    assert response.status_code == 200


def test_observability_reliability_no_fake_data(client: TestClient) -> None:
    """Reliability metrics response has fake_data=False."""
    response = client.get("/v1/observability/reliability-metrics")
    data = response.json()
    assert data["fake_data"] is False


def test_observability_reliability_secret_safe(client: TestClient) -> None:
    """Reliability metrics response has secret_safe=True."""
    response = client.get("/v1/observability/reliability-metrics")
    data = response.json()
    assert data["secret_safe"] is True


def test_observability_reliability_cost_not_live(client: TestClient) -> None:
    """Reliability metrics cost_tracking has live_cost_data=False."""
    response = client.get("/v1/observability/reliability-metrics")
    data = response.json()
    assert data["cost_tracking"]["live_cost_data"] is False


def test_observability_audit_200(client: TestClient) -> None:
    """GET /v1/observability/audit-log returns 200, secret_safe=True, fake_data=False."""
    response = client.get("/v1/observability/audit-log")
    assert response.status_code == 200
    data = response.json()
    assert data["secret_safe"] is True
    assert data["fake_data"] is False


# ---------------------------------------------------------------------------
# B12 Long-Horizon Goals (tests 51-60)
# ---------------------------------------------------------------------------


def test_long_horizon_goals_200(client: TestClient) -> None:
    """GET /v1/long-horizon/goals returns 200."""
    response = client.get("/v1/long-horizon/goals")
    assert response.status_code == 200


def test_long_horizon_goals_no_fake_data(client: TestClient) -> None:
    """Long-horizon goals response has fake_data=False."""
    response = client.get("/v1/long-horizon/goals")
    data = response.json()
    assert data["fake_data"] is False


def test_long_horizon_goals_no_auto_execute(client: TestClient) -> None:
    """Long-horizon goals response has auto_execute=False."""
    response = client.get("/v1/long-horizon/goals")
    data = response.json()
    assert data["auto_execute"] is False


def test_long_horizon_goals_shape(client: TestClient) -> None:
    """Response has: goals (list), count (int), active_count (int)."""
    response = client.get("/v1/long-horizon/goals")
    data = response.json()
    assert isinstance(data["goals"], list)
    assert isinstance(data["count"], int)
    assert isinstance(data["active_count"], int)


def test_long_horizon_goals_all_have_auto_execute_false(client: TestClient) -> None:
    """Every goal in goals list has auto_execute==False."""
    response = client.get("/v1/long-horizon/goals")
    data = response.json()
    for goal in data["goals"]:
        assert goal["auto_execute"] is False, (
            f"goal {goal.get('goal_id')} has auto_execute != False"
        )


def test_long_horizon_goals_all_require_approval(client: TestClient) -> None:
    """Every goal in goals list has approval_required_for_actions==True."""
    response = client.get("/v1/long-horizon/goals")
    data = response.json()
    for goal in data["goals"]:
        assert goal["approval_required_for_actions"] is True, (
            f"goal {goal.get('goal_id')} has approval_required_for_actions != True"
        )


def test_long_horizon_summary_200(client: TestClient) -> None:
    """GET /v1/long-horizon/summary returns 200."""
    response = client.get("/v1/long-horizon/summary")
    assert response.status_code == 200


def test_long_horizon_summary_approval_gated(client: TestClient) -> None:
    """Long-horizon summary has approval_required_for_execution=True and auto_execute=False."""
    response = client.get("/v1/long-horizon/summary")
    data = response.json()
    assert data["approval_required_for_execution"] is True
    assert data["auto_execute"] is False


def test_long_horizon_plan_step_no_execute(client: TestClient) -> None:
    """POST /v1/long-horizon/goals/nonexistent_id/plan-step returns 404 (goal not found)."""
    response = client.post(
        "/v1/long-horizon/goals/nonexistent_id/plan-step",
        json={
            "step_type": "milestone",
            "title": "test step",
            "description": "",
            "requires_approval": True,
        },
    )
    assert response.status_code == 404


def test_long_horizon_plan_step_executed_false(client: TestClient) -> None:
    """If any goal exists, POST plan-step for it returns executed=False. Otherwise skip."""
    goals_response = client.get("/v1/long-horizon/goals")
    goals_data = goals_response.json()
    if goals_data.get("count", 0) == 0:
        pytest.skip("no goals to test plan step")
    goal_id = goals_data["goals"][0]["goal_id"]
    response = client.post(
        f"/v1/long-horizon/goals/{goal_id}/plan-step",
        json={
            "step_type": "milestone",
            "title": "test step",
            "description": "",
            "requires_approval": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["executed"] is False


# ---------------------------------------------------------------------------
# Self-knowledge integration (tests 61-68)
# ---------------------------------------------------------------------------


def test_sk_b7_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has capability id='skills_plugin_expansion' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    assert response.status_code == 200
    data = response.json()
    caps = data["capabilities"]
    match = next((c for c in caps if c.get("id") == "skills_plugin_expansion"), None)
    assert match is not None, "capability 'skills_plugin_expansion' not found"
    assert match["status"] == "available"


def test_sk_b8_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has capability id='connector_workflow_expansion'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    caps = data["capabilities"]
    match = next((c for c in caps if c.get("id") == "connector_workflow_expansion"), None)
    assert match is not None, "capability 'connector_workflow_expansion' not found"


def test_sk_b9_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has capability id='proactive_operator' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    caps = data["capabilities"]
    match = next((c for c in caps if c.get("id") == "proactive_operator"), None)
    assert match is not None, "capability 'proactive_operator' not found"
    assert match["status"] == "available"


def test_sk_b10_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has capability id='business_admin_operator' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    caps = data["capabilities"]
    match = next((c for c in caps if c.get("id") == "business_admin_operator"), None)
    assert match is not None, "capability 'business_admin_operator' not found"
    assert match["status"] == "available"


def test_sk_b11_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has capability id='observability_reliability' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    caps = data["capabilities"]
    match = next((c for c in caps if c.get("id") == "observability_reliability"), None)
    assert match is not None, "capability 'observability_reliability' not found"
    assert match["status"] == "available"


def test_sk_b12_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has capability id='long_horizon_goals' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    caps = data["capabilities"]
    match = next((c for c in caps if c.get("id") == "long_horizon_goals"), None)
    assert match is not None, "capability 'long_horizon_goals' not found"
    assert match["status"] == "available"


def test_sk_active_sprint_b7_b12(client: TestClient) -> None:
    """GET /v1/jarvis/roadmap active_sprint is a B-phase or later sprint."""
    response = client.get("/v1/jarvis/roadmap")
    assert response.status_code == 200
    data = response.json()
    active_sprint = data.get("active_sprint", "")
    # Sprint advances through phases — any B7+, C, Final Phase A, or later is valid
    assert any(t in active_sprint for t in ("PHASE_B", "ADVANCED", "EXPANSION", "DEEP", "PHASE_C", "AUTONOMOUS", "FINAL_PHASE_A", "GATE_CLOSURE", "ONE_MEGA_SPRINT", "PHASE_D", "GATE_CLEARANCE")), (
        f"active_sprint '{active_sprint}' must be a B-phase, C-phase, or later sprint"
    )


def test_sk_plan_state_b12(client: TestClient) -> None:
    """GET /v1/jarvis/status plan_state has 'phase_b12_long_horizon'=='IN_PROGRESS'."""
    response = client.get("/v1/jarvis/status")
    assert response.status_code == 200
    data = response.json()
    plan_state = data.get("plan_state", {})
    assert plan_state.get("phase_b12_long_horizon") == "IN_PROGRESS", (
        f"phase_b12_long_horizon is '{plan_state.get('phase_b12_long_horizon')}', expected 'IN_PROGRESS'"
    )


# ---------------------------------------------------------------------------
# OMNIX non-regression (tests 69-70)
# ---------------------------------------------------------------------------


def test_omnix_not_in_jarvis_identity_b12(client: TestClient) -> None:
    """GET /v1/jarvis/status response['identity'] does not contain 'OMNIX'."""
    response = client.get("/v1/jarvis/status")
    assert response.status_code == 200
    data = response.json()
    identity = data.get("identity", "")
    assert "OMNIX" not in identity, (
        f"OMNIX found in jarvis identity: '{identity}'"
    )


def test_b1_b6_regression_not_broken(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities has at least 20 capabilities (B1-B12 all present), summary['available'] >= 15."""
    response = client.get("/v1/jarvis/capabilities")
    assert response.status_code == 200
    data = response.json()
    caps = data["capabilities"]
    assert len(caps) >= 20, (
        f"Expected at least 20 capabilities (B1-B12 coverage), got {len(caps)}"
    )
    summary = data.get("summary", {})
    available = summary.get("available", 0)
    assert available >= 15, (
        f"Expected at least 15 available capabilities, got {available}"
    )
