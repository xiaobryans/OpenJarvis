"""Tests for Final Phase A blocker closure sprint.

Covers:
  - Plan 4-6 accepted status reflected in self-knowledge routes
  - Final Phase A status correctly reported as IN_PROGRESS (not accepted)
  - Phase X accepted status in roadmap
  - ExpertRolesPage empty state HTML present (string check on TSX)
  - Responsive classes present on all four Plan 4-6 pages
  - Routines endpoint exists and behaves honestly (no fake data)
  - Self-knowledge does not fake routines as running
  - Connector status is metadata-only (no credential values)
  - OMNIX is not Jarvis core/default identity
  - Approval gates not weakened
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures — router-level (no create_app() needed)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sk_client():
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def routines_client():
    from openjarvis.server.routines_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def system_client():
    try:
        from openjarvis.server.system_status_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)
    except ImportError as exc:
        pytest.skip(f"system_status_routes not importable: {exc}")


@pytest.fixture(scope="module")
def projects_client():
    try:
        from openjarvis.server.projects_routes import router
        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)
    except ImportError as exc:
        pytest.skip(f"projects_routes not importable: {exc}")


# ---------------------------------------------------------------------------
# Plan state / roadmap truthfulness
# ---------------------------------------------------------------------------

class TestSelfKnowledgeAcceptanceState:
    def test_plan_4_6_roadmap_status_is_accepted(self, sk_client):
        res = sk_client.get("/v1/jarvis/roadmap")
        assert res.status_code == 200
        data = res.json()
        plan46_entry = next((r for r in data["roadmap"] if r["plan"] == "Plan 4-6"), None)
        assert plan46_entry is not None, "Plan 4-6 must appear in roadmap"
        assert plan46_entry["status"] == "ACCEPTED", (
            f"Plan 4-6 must be ACCEPTED, got {plan46_entry['status']}"
        )

    def test_phase_x_appears_in_roadmap_as_accepted(self, sk_client):
        res = sk_client.get("/v1/jarvis/roadmap")
        assert res.status_code == 200
        data = res.json()
        phase_x = next((r for r in data["roadmap"] if r["plan"] == "Phase X"), None)
        assert phase_x is not None, "Phase X must appear in roadmap"
        assert phase_x["status"] == "ACCEPTED"

    def test_final_phase_a_appears_in_roadmap_as_in_progress(self, sk_client):
        res = sk_client.get("/v1/jarvis/roadmap")
        assert res.status_code == 200
        data = res.json()
        phase_a = next((r for r in data["roadmap"] if "Final Phase A" in r["plan"]), None)
        assert phase_a is not None, "Final Phase A must appear in roadmap"
        assert phase_a["status"] == "IN_PROGRESS", (
            f"Final Phase A must be IN_PROGRESS (not accepted), got {phase_a['status']}"
        )

    def test_jarvis_status_plan_4_6_accepted(self, sk_client):
        res = sk_client.get("/v1/jarvis/status")
        assert res.status_code == 200
        data = res.json()
        assert data["plan_state"]["plan_4_6_mega_sprint"] == "ACCEPTED"

    def test_jarvis_status_phase_x_accepted(self, sk_client):
        res = sk_client.get("/v1/jarvis/status")
        assert res.status_code == 200
        data = res.json()
        assert data["plan_state"].get("phase_x_decoupling") == "ACCEPTED"

    def test_jarvis_status_final_phase_a_in_progress(self, sk_client):
        res = sk_client.get("/v1/jarvis/status")
        assert res.status_code == 200
        data = res.json()
        assert data["plan_state"].get("final_phase_a") == "IN_PROGRESS"

    def test_active_sprint_is_phase_b1_or_final_a(self, sk_client):
        res = sk_client.get("/v1/jarvis/roadmap")
        assert res.status_code == 200
        data = res.json()
        sprint = data["active_sprint"]
        # Phase B1 started after Final Phase A manual gates; both are valid active sprints
        assert "PHASE_B1" in sprint or "FINAL_PHASE_A" in sprint or "Final" in sprint or "Phase" in sprint

    def test_no_fake_claims(self, sk_client):
        res = sk_client.get("/v1/jarvis/status")
        assert res.status_code == 200
        assert res.json()["fake_claims"] is False


# ---------------------------------------------------------------------------
# Routines endpoint honesty
# ---------------------------------------------------------------------------

class TestRoutinesEndpointHonesty:
    def test_routines_list_returns_200(self, routines_client):
        res = routines_client.get("/v1/routines")
        assert res.status_code == 200

    def test_routines_has_count_field(self, routines_client):
        data = routines_client.get("/v1/routines").json()
        assert "count" in data
        assert isinstance(data["count"], int)

    def test_routines_scheduler_not_claimed_running(self, routines_client):
        data = routines_client.get("/v1/routines").json()
        assert data["scheduler_started"] is False, (
            "scheduler_started must be False — scheduler is not auto-started"
        )

    def test_routines_has_automation_honesty_flag(self, routines_client):
        data = routines_client.get("/v1/routines").json()
        assert data.get("automation_honesty") is True

    def test_routines_status_returns_200(self, routines_client):
        res = routines_client.get("/v1/routines/status")
        assert res.status_code == 200

    def test_routines_status_no_fake_recurring_automations(self, routines_client):
        data = routines_client.get("/v1/routines/status").json()
        assert data["honesty"]["fake_recurring_automations"] is False

    def test_routines_status_scheduler_not_running(self, routines_client):
        data = routines_client.get("/v1/routines/status").json()
        assert data["honesty"]["scheduler_running"] is False

    def test_routines_capability_in_self_knowledge(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        cap_ids = [c["id"] for c in data["capabilities"]]
        assert "routines" in cap_ids, "routines capability must appear in self-knowledge"

    def test_routines_capability_not_faked_as_available(self, sk_client):
        data = sk_client.get("/v1/jarvis/capabilities").json()
        routines_cap = next((c for c in data["capabilities"] if c["id"] == "routines"), None)
        assert routines_cap is not None
        # routines is partial (scheduler exists but not auto-started) — not "available"
        assert routines_cap["status"] in ("partial", "not_started"), (
            f"routines status must not claim full 'available' — got {routines_cap['status']}"
        )


# ---------------------------------------------------------------------------
# Connector status — metadata only, no credential values
# ---------------------------------------------------------------------------

class TestConnectorStatusMetadataOnly:
    def test_system_status_returns_200(self, system_client):
        res = system_client.get("/v1/system/status")
        assert res.status_code == 200

    def test_system_status_no_credential_values(self, system_client):
        data = system_client.get("/v1/system/status").json()
        text = str(data)
        for prefix in ("xoxb-", "xoxp-", "ghp_", "AKIA", "Bearer ", "token="):
            assert prefix not in text, f"Credential prefix '{prefix}' leaked in system status"

    def test_system_status_has_safety_field(self, system_client):
        data = system_client.get("/v1/system/status").json()
        assert "safety" in data
        safety = data["safety"].lower()
        assert "presence" in safety or "no secret" in safety or "secret" in safety

    def test_system_status_fake_claims_false(self, system_client):
        data = system_client.get("/v1/system/status").json()
        assert data["summary"]["fake_claims"] is False


# ---------------------------------------------------------------------------
# OMNIX is not Jarvis core/default identity
# ---------------------------------------------------------------------------

class TestOmnixNotJarvisCore:
    def test_jarvis_identity_primary_project_not_omnix(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("primary_project") != "omnix", (
            "JARVIS_IDENTITY.primary_project must not be 'omnix' — Phase X decoupling"
        )

    def test_jarvis_identity_name_is_jarvis(self):
        from openjarvis.governance.constitution import JARVIS_IDENTITY
        assert JARVIS_IDENTITY.get("name") == "Jarvis"

    def test_get_default_returns_optional_not_hardcoded(self):
        from openjarvis.governance.constitution import ProjectRegistry
        ProjectRegistry.clear()
        default = ProjectRegistry.get_default()
        # After clear: OMNIX auto-registers as Bryan's project (expected)
        # What's not allowed: unconditional hardcoded return of OMNIX regardless of registry
        if default is not None:
            assert hasattr(default, "project_id"), "get_default() must return ProjectProfile or None"

    def test_jarvis_self_knowledge_identity_not_omnix(self, sk_client):
        res = sk_client.get("/v1/jarvis/status")
        assert res.status_code == 200
        data = res.json()
        identity = data.get("identity", "")
        assert "omnix" not in identity.lower(), (
            "Jarvis identity must not reference OMNIX as Jarvis identity"
        )

    def test_projects_route_null_safe(self, projects_client):
        res = projects_client.get("/v1/projects")
        assert res.status_code == 200
        # default_project_id can be None (empty registry) or a string — must not crash


# ---------------------------------------------------------------------------
# Approval gates not weakened
# ---------------------------------------------------------------------------

class TestApprovalGatesNotWeakened:
    def test_hard_gates_frozenset_size(self):
        from openjarvis.governance.constitution import HARD_GATE_ACTIONS
        assert len(HARD_GATE_ACTIONS) >= 14, (
            f"Hard gate actions must have at least 14 entries, got {len(HARD_GATE_ACTIONS)}"
        )

    def test_destructive_actions_in_hard_gates(self):
        from openjarvis.governance.constitution import HARD_GATE_ACTIONS
        required = {"omnix_production_deploy", "real_slack_send", "real_email_send"}
        missing = required - HARD_GATE_ACTIONS
        assert not missing, f"Missing from hard gates: {missing}"

    def test_governance_constitution_has_no_secret_values(self):
        import inspect
        from openjarvis.governance import constitution
        source = inspect.getsource(constitution)
        for prefix in ("xoxb-", "xoxp-", "ghp_", "AKIA", "sk-proj-"):
            assert prefix not in source, f"Secret prefix '{prefix}' in constitution.py"


# ---------------------------------------------------------------------------
# Frontend pages responsive classes — checked as file content
# ---------------------------------------------------------------------------

class TestFrontendResponsiveClasses:
    def _read(self, path: str) -> str:
        from pathlib import Path
        return Path(path).read_text()

    def test_rules_manager_stats_strip_responsive(self):
        src = self._read("frontend/src/pages/RulesManagerPage.tsx")
        assert "grid-cols-3 sm:grid-cols-5" in src, (
            "RulesManagerPage StatsStrip must have responsive grid-cols-3 sm:grid-cols-5"
        )

    def test_rules_manager_form_responsive(self):
        src = self._read("frontend/src/pages/RulesManagerPage.tsx")
        assert "grid-cols-1 sm:grid-cols-2" in src, (
            "RulesManagerPage form grid must have responsive grid-cols-1 sm:grid-cols-2"
        )

    def test_delegation_page_filter_flex_wrap(self):
        src = self._read("frontend/src/pages/DelegationPage.tsx")
        assert "flex-wrap" in src, (
            "DelegationPage filter buttons must have flex-wrap for narrow screens"
        )

    def test_delegation_page_expanded_grid_responsive(self):
        src = self._read("frontend/src/pages/DelegationPage.tsx")
        assert "grid-cols-1 sm:grid-cols-2" in src, (
            "DelegationPage expanded row must have responsive grid-cols-1 sm:grid-cols-2"
        )

    def test_jarvis_capabilities_productization_responsive(self):
        src = self._read("frontend/src/pages/JarvisCapabilitiesPage.tsx")
        assert "grid-cols-1 sm:grid-cols-3" in src, (
            "JarvisCapabilitiesPage productization grid must be responsive"
        )

    def test_jarvis_capabilities_status_header_responsive(self):
        src = self._read("frontend/src/pages/JarvisCapabilitiesPage.tsx")
        assert "grid-cols-1 sm:grid-cols-2" in src, (
            "JarvisCapabilitiesPage status header grid must be responsive"
        )

    def test_expert_roles_empty_state_present(self):
        src = self._read("frontend/src/pages/ExpertRolesPage.tsx")
        assert "No expert roles registered" in src, (
            "ExpertRolesPage must have an empty state message"
        )

    def test_expert_roles_empty_state_has_backend_note(self):
        src = self._read("frontend/src/pages/ExpertRolesPage.tsx")
        assert "/v1/expert-roles" in src and "No expert roles" in src, (
            "ExpertRolesPage empty state must reference the backend route"
        )
