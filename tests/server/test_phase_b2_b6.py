"""Phase B2-B6 backend behavior tests for OpenJarvis.

Covers:
  Phase B2 — Routines (GET /v1/routines/summary)
  Phase B3 — Memory OS (GET /v1/memory/dashboard, /v1/memory/namespaces)
  Phase B4 — Command Center (GET /v1/command-center, /v1/command-center/summary)
  Phase B5 — Expert Org (GET /v1/expert-roles/routing-status)
  Self-knowledge integration (GET /v1/jarvis/capabilities, /v1/jarvis/status, /v1/jarvis/roadmap)
  OMNIX decoupling regression
  Approval gate non-regression (read-only command center)

Test rules:
  - All tests are independent; no shared mutable state.
  - No live HTTP calls outside TestClient.
  - No secret values, no .env access.
  - Uses response.json() for body access.
"""

from __future__ import annotations

import json
from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.routines_routes import router as routines_router
from openjarvis.server.memory_routes import router as memory_router
from openjarvis.server.command_center_routes import router as command_center_router
from openjarvis.server.expert_roles_routes import router as expert_roles_router
from openjarvis.server.self_knowledge_routes import router as self_knowledge_router


@pytest.fixture(scope="module")
def client() -> TestClient:
    app = FastAPI()
    app.include_router(routines_router)
    app.include_router(memory_router)
    app.include_router(command_center_router)
    app.include_router(expert_roles_router)
    app.include_router(self_knowledge_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Phase B2 — Routines
# ---------------------------------------------------------------------------


def test_routines_summary_200(client: TestClient) -> None:
    """GET /v1/routines/summary returns 200."""
    response = client.get("/v1/routines/summary")
    assert response.status_code == 200


def test_routines_summary_no_fake_data(client: TestClient) -> None:
    """Response has fake_data=False."""
    response = client.get("/v1/routines/summary")
    data = response.json()
    assert data["fake_data"] is False


def test_routines_summary_shape(client: TestClient) -> None:
    """Response has required keys: total, active, paused, completed, failed, scheduler_started, automation_honesty."""
    response = client.get("/v1/routines/summary")
    data = response.json()
    required_keys = {"total", "active", "paused", "completed", "failed", "scheduler_started", "automation_honesty"}
    for key in required_keys:
        assert key in data, f"Missing key: {key}"


def test_routines_summary_automation_honesty(client: TestClient) -> None:
    """automation_honesty=True in routines summary."""
    response = client.get("/v1/routines/summary")
    data = response.json()
    assert data["automation_honesty"] is True


def test_routines_summary_scheduler_not_claimed_running(client: TestClient) -> None:
    """scheduler_started is a boolean (could be False — do NOT assert True)."""
    response = client.get("/v1/routines/summary")
    data = response.json()
    assert isinstance(data["scheduler_started"], bool)


def test_routines_no_credential_leak(client: TestClient) -> None:
    """Response body has scheduler_started and automation_honesty; no secret-looking fields."""
    response = client.get("/v1/routines/summary")
    data = response.json()
    # Required honest fields present
    assert "scheduler_started" in data
    assert "automation_honesty" in data
    # No credential-like top-level keys
    credential_like = {"token", "secret", "password", "api_key", "access_key"}
    actual_keys = {k.lower() for k in data.keys()}
    assert actual_keys.isdisjoint(credential_like), (
        f"Credential-like key(s) found in response: {actual_keys & credential_like}"
    )


# ---------------------------------------------------------------------------
# Phase B3 — Memory OS
# ---------------------------------------------------------------------------


def test_memory_dashboard_200(client: TestClient) -> None:
    """GET /v1/memory/dashboard returns 200."""
    response = client.get("/v1/memory/dashboard")
    assert response.status_code == 200


def test_memory_dashboard_no_fake_data(client: TestClient) -> None:
    """Response has fake_data=False."""
    response = client.get("/v1/memory/dashboard")
    data = response.json()
    assert data["fake_data"] is False


def test_memory_dashboard_shape(client: TestClient) -> None:
    """Response has required keys: store_ok, namespace_count, total_entries, namespaces, search_available, cloud_sync_configured, cloud_sync_live_claimed."""
    response = client.get("/v1/memory/dashboard")
    data = response.json()
    required_keys = {
        "store_ok",
        "namespace_count",
        "total_entries",
        "namespaces",
        "search_available",
        "cloud_sync_configured",
        "cloud_sync_live_claimed",
    }
    for key in required_keys:
        assert key in data, f"Missing key: {key}"


def test_memory_dashboard_cloud_sync_live_not_claimed(client: TestClient) -> None:
    """cloud_sync_live_claimed=False — never claimed without proof."""
    response = client.get("/v1/memory/dashboard")
    data = response.json()
    assert data["cloud_sync_live_claimed"] is False


def test_memory_namespaces_200(client: TestClient) -> None:
    """GET /v1/memory/namespaces returns 200."""
    response = client.get("/v1/memory/namespaces")
    assert response.status_code == 200


def test_memory_dashboard_no_credential_in_response(client: TestClient) -> None:
    """Response JSON keys do not include credential-like field names."""
    response = client.get("/v1/memory/dashboard")
    data = response.json()
    credential_like = {"token", "secret", "password"}
    actual_keys = {k.lower() for k in data.keys()}
    assert actual_keys.isdisjoint(credential_like), (
        f"Credential-like key(s) found in memory dashboard response: {actual_keys & credential_like}"
    )


# ---------------------------------------------------------------------------
# Phase B4 — Command Center
# ---------------------------------------------------------------------------


def test_command_center_200(client: TestClient) -> None:
    """GET /v1/command-center returns 200."""
    response = client.get("/v1/command-center")
    assert response.status_code == 200


def test_command_center_no_fake_data(client: TestClient) -> None:
    """Response has fake_data=False."""
    response = client.get("/v1/command-center")
    data = response.json()
    assert data["fake_data"] is False


def test_command_center_shape(client: TestClient) -> None:
    """Response has: items (list), count (int), by_source (dict), by_status (dict), sources_probed (list)."""
    response = client.get("/v1/command-center")
    data = response.json()
    assert isinstance(data["items"], list)
    assert isinstance(data["count"], int)
    assert isinstance(data["by_source"], dict)
    assert isinstance(data["by_status"], dict)
    assert isinstance(data["sources_probed"], list)


def test_command_center_summary_200(client: TestClient) -> None:
    """GET /v1/command-center/summary returns 200."""
    response = client.get("/v1/command-center/summary")
    assert response.status_code == 200


def test_command_center_summary_shape(client: TestClient) -> None:
    """Response has: tasks (dict with total/pending/in_progress/waiting_approval), goals (dict with total/active/paused), projects (dict with total/active), grand_total (int), fake_data (bool)."""
    response = client.get("/v1/command-center/summary")
    data = response.json()

    assert isinstance(data["tasks"], dict)
    assert "total" in data["tasks"]
    assert "pending" in data["tasks"]
    assert "in_progress" in data["tasks"]
    assert "waiting_approval" in data["tasks"]

    assert isinstance(data["goals"], dict)
    assert "total" in data["goals"]
    assert "active" in data["goals"]
    assert "paused" in data["goals"]

    assert isinstance(data["projects"], dict)
    assert "total" in data["projects"]
    assert "active" in data["projects"]

    assert isinstance(data["grand_total"], int)
    assert isinstance(data["fake_data"], bool)


def test_command_center_summary_no_fake_data(client: TestClient) -> None:
    """fake_data=False in command center summary."""
    response = client.get("/v1/command-center/summary")
    data = response.json()
    assert data["fake_data"] is False


def test_command_center_items_all_have_source(client: TestClient) -> None:
    """Every item in items list has a non-empty 'source' field."""
    response = client.get("/v1/command-center")
    data = response.json()
    for item in data["items"]:
        assert "source" in item, f"Item missing 'source': {item}"
        assert item["source"], f"Item has empty 'source': {item}"


def test_command_center_items_no_approval_gate_bypass(client: TestClient) -> None:
    """Every item with approval_required=True must have a source_route (not empty/null)."""
    response = client.get("/v1/command-center")
    data = response.json()
    for item in data["items"]:
        if item.get("approval_required") is True:
            assert item.get("source_route"), (
                f"Item with approval_required=True has no source_route: {item}"
            )


def test_command_center_source_filter(client: TestClient) -> None:
    """GET /v1/command-center?source=life_os_task returns 200 (may be empty, must not 422)."""
    response = client.get("/v1/command-center?source=life_os_task")
    assert response.status_code == 200


def test_command_center_status_filter(client: TestClient) -> None:
    """GET /v1/command-center?status=pending returns 200."""
    response = client.get("/v1/command-center?status=pending")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Phase B5 — Expert Org
# ---------------------------------------------------------------------------


def test_expert_routing_status_200(client: TestClient) -> None:
    """GET /v1/expert-roles/routing-status returns 200."""
    response = client.get("/v1/expert-roles/routing-status")
    assert response.status_code == 200


def test_expert_routing_status_no_fake_data(client: TestClient) -> None:
    """Response has fake_data=False."""
    response = client.get("/v1/expert-roles/routing-status")
    data = response.json()
    assert data["fake_data"] is False


def test_expert_routing_status_single_voice(client: TestClient) -> None:
    """response['jarvis_pa_identity']['single_voice'] == True."""
    response = client.get("/v1/expert-roles/routing-status")
    data = response.json()
    assert data["jarvis_pa_identity"]["single_voice"] is True


def test_expert_routing_status_internal_only(client: TestClient) -> None:
    """response['jarvis_pa_identity']['internal_routing_only'] == True."""
    response = client.get("/v1/expert-roles/routing-status")
    data = response.json()
    assert data["jarvis_pa_identity"]["internal_routing_only"] is True


def test_expert_routing_status_no_multi_personality(client: TestClient) -> None:
    """response['jarvis_pa_identity']['no_multi_personality_output'] == True."""
    response = client.get("/v1/expert-roles/routing-status")
    data = response.json()
    assert data["jarvis_pa_identity"]["no_multi_personality_output"] is True


def test_expert_routing_status_audit_fields(client: TestClient) -> None:
    """Response has 'audit' with routing_is_internal=True, approval_gates_unaffected=True, no_autonomous_role_switching=True."""
    response = client.get("/v1/expert-roles/routing-status")
    data = response.json()
    audit = data["audit"]
    assert audit["routing_is_internal"] is True
    assert audit["approval_gates_unaffected"] is True
    assert audit["no_autonomous_role_switching"] is True


def test_expert_routing_status_role_counts(client: TestClient) -> None:
    """role_count >= 0 and active_role_count >= 0."""
    response = client.get("/v1/expert-roles/routing-status")
    data = response.json()
    assert data["role_count"] >= 0
    assert data["active_role_count"] >= 0


# ---------------------------------------------------------------------------
# Self-knowledge integration
# ---------------------------------------------------------------------------


def _find_capability(data: Dict[str, Any], cap_id: str) -> Dict[str, Any] | None:
    """Find a capability by id in capabilities list."""
    return next((c for c in data["capabilities"] if c["id"] == cap_id), None)


def test_self_knowledge_b2_capability(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities returns capability id='routines_command_center' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    assert response.status_code == 200
    data = response.json()
    cap = _find_capability(data, "routines_command_center")
    assert cap is not None, "Capability 'routines_command_center' not found"
    assert cap["status"] == "available"


def test_self_knowledge_b3_capability(client: TestClient) -> None:
    """Capability id='memory_os' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    cap = _find_capability(data, "memory_os")
    assert cap is not None, "Capability 'memory_os' not found"
    assert cap["status"] == "available"


def test_self_knowledge_b4_capability(client: TestClient) -> None:
    """Capability id='command_center' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    cap = _find_capability(data, "command_center")
    assert cap is not None, "Capability 'command_center' not found"
    assert cap["status"] == "available"


def test_self_knowledge_b5_capability(client: TestClient) -> None:
    """Capability id='expert_org' with status='available'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    cap = _find_capability(data, "expert_org")
    assert cap is not None, "Capability 'expert_org' not found"
    assert cap["status"] == "available"


def test_self_knowledge_active_sprint_b2_b6(client: TestClient) -> None:
    """GET /v1/jarvis/roadmap returns active_sprint containing 'B2' or 'B6' or 'EXPANSION'."""
    response = client.get("/v1/jarvis/roadmap")
    assert response.status_code == 200
    data = response.json()
    active = data.get("active_sprint", "")
    assert any(token in active for token in ("B2", "B6", "EXPANSION")), (
        f"active_sprint does not reference B2/B6/EXPANSION: {active!r}"
    )


def test_self_knowledge_plan_state_b2(client: TestClient) -> None:
    """GET /v1/jarvis/status returns plan_state with 'phase_b2_routines' = 'IN_PROGRESS'."""
    response = client.get("/v1/jarvis/status")
    assert response.status_code == 200
    data = response.json()
    assert data["plan_state"]["phase_b2_routines"] == "IN_PROGRESS"


def test_self_knowledge_plan_state_b6(client: TestClient) -> None:
    """plan_state has 'phase_b6_ui_polish' = 'IN_PROGRESS'."""
    response = client.get("/v1/jarvis/status")
    data = response.json()
    assert data["plan_state"]["phase_b6_ui_polish"] == "IN_PROGRESS"


def test_roadmap_has_b2_through_b6(client: TestClient) -> None:
    """Roadmap list includes entries for Phase B2, B3, B4, B5, B6."""
    response = client.get("/v1/jarvis/roadmap")
    data = response.json()
    roadmap = data["roadmap"]
    plan_names = [entry.get("plan", "") for entry in roadmap]
    for phase in ("Phase B2", "Phase B3", "Phase B4", "Phase B5", "Phase B6"):
        assert phase in plan_names, f"Roadmap missing entry for {phase!r}. Found: {plan_names}"


# ---------------------------------------------------------------------------
# OMNIX decoupling — not regressed
# ---------------------------------------------------------------------------


def test_omnix_not_jarvis_identity(client: TestClient) -> None:
    """GET /v1/jarvis/status response['identity'] does not contain 'OMNIX' (case insensitive)."""
    response = client.get("/v1/jarvis/status")
    data = response.json()
    identity = data.get("identity", "")
    assert "omnix" not in identity.lower(), (
        f"identity field contains 'OMNIX': {identity!r}"
    )


def test_omnix_not_primary_in_capabilities(client: TestClient) -> None:
    """GET /v1/jarvis/capabilities response['identity'] does not contain 'OMNIX'."""
    response = client.get("/v1/jarvis/capabilities")
    data = response.json()
    identity = data.get("identity", "")
    assert "omnix" not in identity.lower(), (
        f"capabilities identity field contains 'OMNIX': {identity!r}"
    )


# ---------------------------------------------------------------------------
# Approval gates — not weakened
# ---------------------------------------------------------------------------


def test_command_center_read_only(client: TestClient) -> None:
    """There is no POST /v1/command-center route — POST must return 405 or 404, not 200."""
    response = client.post("/v1/command-center")
    assert response.status_code in (404, 405), (
        f"POST /v1/command-center returned {response.status_code}; expected 404 or 405 (read-only endpoint)"
    )
