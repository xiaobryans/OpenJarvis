"""Tests for Final Phase A — Installed App UI Unification Corrective Sprint.

Covers:
  - active_sprint reflects the UI unification corrective sprint
  - installed_app_smoke remains blocked (not auto-passed)
  - daily_driver not claimed as certified (needs Bryan usage proof)
  - smoke status is pending, no fake smoke result
  - roadmap note reflects the UI unification work
  - No fake acceptance of Final Phase A
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sk_client():
    from openjarvis.server.self_knowledge_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def tower_client():
    from openjarvis.server.control_tower_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def smoke_client():
    from openjarvis.server.final_smoke_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture(scope="module")
def score_client():
    from openjarvis.server.control_tower_routes import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: active sprint reflects UI unification
# ---------------------------------------------------------------------------

class TestActiveSprintUIUnification:
    def test_sk_roadmap_active_sprint_is_ui_unification(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        sprint = data["active_sprint"]
        assert "UI_UNIFICATION" in sprint or "FINAL_PHASE_A" in sprint, (
            f"Expected UI unification or Final Phase A sprint, got: {sprint}"
        )

    def test_tower_active_sprint_is_ui_unification(self, tower_client):
        data = tower_client.get("/v1/control-tower/status").json()
        sprint = data["active_sprint"]
        assert "UI_UNIFICATION" in sprint or "CORRECTIVE" in sprint or "FINAL_PHASE_A" in sprint, (
            f"Expected UI unification sprint in control tower, got: {sprint}"
        )

    def test_sk_roadmap_note_mentions_ui_or_rebuild(self, sk_client):
        data = sk_client.get("/v1/jarvis/roadmap").json()
        note = data.get("next", "")
        # Note should mention UI fix or rebuild or Bryan proof requirement
        assert any(k in note.lower() for k in ("ui", "unified", "rebuild", "notarize", "visual proof", "corrective")), (
            f"Roadmap note should mention UI unification work, got: {note}"
        )

    def test_no_fake_acceptance_in_tower(self, tower_client):
        data = tower_client.get("/v1/control-tower/status").json()
        assert data["fake_acceptance"] is False

    def test_no_fake_data_in_tower(self, tower_client):
        data = tower_client.get("/v1/control-tower/status").json()
        assert data["fake_data"] is False


# ---------------------------------------------------------------------------
# Tests: installed_app_smoke not auto-passed
# ---------------------------------------------------------------------------

class TestInstalledAppSmokeHonesty:
    def test_smoke_status_is_pending(self, smoke_client):
        data = smoke_client.get("/v1/final-smoke/status").json()
        assert data["smoke_status"] == "pending", (
            f"Smoke status must be pending until Bryan confirms, got: {data['smoke_status']}"
        )

    def test_claimed_passed_is_false(self, smoke_client):
        data = smoke_client.get("/v1/final-smoke/status").json()
        assert data["claimed_passed"] is False

    def test_fake_smoke_result_is_false(self, smoke_client):
        data = smoke_client.get("/v1/final-smoke/status").json()
        assert data["fake_smoke_result"] is False

    def test_installed_app_smoke_blocked(self, smoke_client):
        data = smoke_client.get("/v1/final-smoke/status").json()
        smoke_val = data.get("installed_app_smoke", "")
        assert "blocked" in smoke_val.lower(), (
            f"Installed app smoke must be blocked pending rebuild and Bryan proof, got: {smoke_val}"
        )

    def test_manual_proof_required(self, smoke_client):
        data = smoke_client.get("/v1/final-smoke/status").json()
        assert data["manual_proof_required"] is True


# ---------------------------------------------------------------------------
# Tests: daily_driver not auto-certified
# ---------------------------------------------------------------------------

class TestDailyDriverHonesty:
    def test_daily_driver_not_certified(self, score_client):
        data = score_client.get("/v1/control-tower/completion-score").json()
        capabilities = data.get("capability_coverage", {})
        assert capabilities.get("daily_driver_certified") is False, (
            "daily_driver_certified must remain False until Bryan completes usage sessions"
        )

    def test_installed_app_smoke_visual_not_claimed(self, score_client):
        data = score_client.get("/v1/control-tower/completion-score").json()
        capabilities = data.get("capability_coverage", {})
        assert capabilities.get("installed_app_smoke_visual") is False, (
            "installed_app_smoke_visual must remain False until Bryan confirms after rebuild"
        )

    def test_no_fake_data_in_score(self, score_client):
        data = score_client.get("/v1/control-tower/completion-score").json()
        assert data.get("fake_data") is False
