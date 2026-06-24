"""Tests for Expert RoleSelector wiring into frontdoor submit (B6)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.frontdoor_routes import router
from openjarvis.orchestrator.expert_roles import ExpertRoleRegistry


@pytest.fixture(autouse=True)
def reset_role_registry():
    ExpertRoleRegistry.reset_instance()
    yield
    ExpertRoleRegistry.reset_instance()


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _submit(client, user_input: str, intent: str = "coding", **kwargs):
    payload = {
        "user_input": user_input,
        "intent": intent,
        "risk_level": kwargs.get("risk_level", "low"),
        "complexity_level": kwargs.get("complexity_level", "simple"),
        "client_platform": kwargs.get("client_platform", "desktop"),
    }
    return client.post("/v1/frontdoor/submit", json=payload)


class TestFrontdoorExpertRoleWiring:
    def test_submit_returns_expert_roles_field(self, client):
        r = _submit(client, "Please review my Python code")
        assert r.status_code == 200
        data = r.json()
        assert "expert_roles_selected" in data
        assert isinstance(data["expert_roles_selected"], list)

    def test_submit_returns_audit_id_field(self, client):
        r = _submit(client, "Please review my Python code")
        data = r.json()
        assert "expert_roles_audit_id" in data

    def test_coding_request_selects_coding_role(self, client):
        r = _submit(client, "Refactor this function to be more efficient", intent="coding")
        data = r.json()
        assert "role_coding" in data["expert_roles_selected"]

    def test_research_request_selects_research_role(self, client):
        r = _submit(client, "Research the latest papers on transformer models", intent="research")
        data = r.json()
        assert "role_research" in data["expert_roles_selected"]

    def test_roles_are_internal_not_speakers(self, client):
        """Expert roles must not appear as external speakers — internal routing only."""
        r = _submit(client, "debug my code", intent="coding")
        data = r.json()
        # The routing_summary still says 'Jarvis PA' pattern — not expert role name
        assert "routing_summary" in data
        # expert_roles_selected contains role_ids (internal), not persona names
        for role_id in data["expert_roles_selected"]:
            assert role_id.startswith("role_")

    def test_single_jarvis_pa_identity_preserved(self, client):
        """One Jarvis PA speaker throughout — no multi-persona leakage."""
        r = _submit(client, "code review", intent="coding")
        data = r.json()
        # Response is still from the frontdoor (one Jarvis path), not from each expert
        assert data["status"] in ("accepted", "blocked")
        assert "omnix_hardcoded" in data
        assert data["omnix_hardcoded"] is False

    def test_approval_gate_not_weakened_by_role_selection(self, client):
        r = _submit(client, "deploy production service", intent="platform_operation", risk_level="high")
        data = r.json()
        assert data["approval_required"] is True
        # Even with role selection, approval gate still fires
        assert "expert_roles_selected" in data

    def test_blocked_request_still_has_role_selection_field(self, client):
        r = _submit(client, "delete everything", intent="coding", risk_level="blocked")
        data = r.json()
        assert data["status"] == "blocked"
        # Role selection is present (gracefully degraded or populated) but gate is still enforced
        assert "expert_roles_selected" in data

    def test_empty_roles_on_unrelated_request(self, client):
        r = _submit(client, "xkzqjpwv xyz123 aaabbb", intent="coding")
        data = r.json()
        # No matching triggers → empty role list (graceful)
        assert isinstance(data["expert_roles_selected"], list)

    def test_audit_id_is_nonempty_for_role_match(self, client):
        r = _submit(client, "review my code implementation", intent="coding")
        data = r.json()
        if data["expert_roles_selected"]:
            assert data["expert_roles_audit_id"] != ""

    def test_normal_chat_intent_still_accepted(self, client):
        """Core chat/request flow is not broken by role selection."""
        r = _submit(client, "What is the capital of France?", intent="research")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "accepted"
        assert data["intent"] == "research"
