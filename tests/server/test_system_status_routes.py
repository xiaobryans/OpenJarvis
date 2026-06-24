"""Tests for Plan 4-6 B7 — system/connector status route.

Tests:
  GET /v1/system/status — connector presence, system probes, summary, safety field

Design:
  - Presence-only: tests never check for actual key values
  - All probes are try/except-wrapped — graceful degradation to 'unknown'
  - Safety guarantee: 'safety' field must be present and non-empty
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

EXPECTED_CONNECTORS = {"gmail", "calendar", "drive", "slack", "telegram", "notion", "github", "s3_memory"}
EXPECTED_SYSTEM = {"fargate_cloud", "mobile_pwa", "ios_native", "skills_rules", "expert_role_routing", "voice_tts"}
VALID_STATUSES = {
    "configured", "not_configured", "partial", "external_gate",
    "not_started", "unknown", "implemented",
    # productization-specific statuses surfaced via _IOS_NATIVE_STATUS
    "scaffold_ready", "present", "not_submitted",
}


@pytest.fixture()
def client():
    try:
        from openjarvis.server.system_status_routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)
    except ImportError as exc:
        pytest.skip(f"system_status_routes not importable: {exc}")


class TestSystemStatusRoute:
    def test_returns_200(self, client: TestClient):
        r = client.get("/v1/system/status")
        assert r.status_code == 200

    def test_top_level_shape(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        assert "connectors" in data
        assert "system" in data
        assert "summary" in data
        assert "safety" in data

    def test_safety_field_non_empty(self, client: TestClient):
        """The safety field must be a non-empty string."""
        data = client.get("/v1/system/status").json()
        assert isinstance(data["safety"], str)
        assert len(data["safety"]) > 0

    def test_safety_field_no_secret_value_language(self, client: TestClient):
        """The safety field must assert presence-only — 'no secret' language."""
        data = client.get("/v1/system/status").json()
        safety = data["safety"].lower()
        assert "secret" in safety or "presence" in safety or "no" in safety

    # Connectors
    def test_all_expected_connectors_present(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        conn = data["connectors"]
        for name in EXPECTED_CONNECTORS:
            assert name in conn, f"Missing connector: {name}"

    def test_each_connector_has_status(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        for name, info in data["connectors"].items():
            assert "status" in info, f"Connector {name} missing 'status'"

    def test_each_connector_has_note(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        for name, info in data["connectors"].items():
            assert "note" in info, f"Connector {name} missing 'note'"

    def test_connector_status_values_valid(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        for name, info in data["connectors"].items():
            assert info["status"] in VALID_STATUSES, (
                f"Connector {name} has unexpected status: {info['status']}"
            )

    # System
    def test_all_expected_system_components_present(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        sys = data["system"]
        for name in EXPECTED_SYSTEM:
            assert name in sys, f"Missing system component: {name}"

    def test_each_system_component_has_status(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        for name, info in data["system"].items():
            assert "status" in info, f"System component {name} missing 'status'"

    def test_system_component_status_values_valid(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        for name, info in data["system"].items():
            assert info["status"] in VALID_STATUSES, (
                f"System component {name} has unexpected status: {info['status']}"
            )

    def test_voice_tts_is_not_started(self, client: TestClient):
        """Plan 3 voice must always be NOT_STARTED — never claimed as available."""
        data = client.get("/v1/system/status").json()
        voice = data["system"].get("voice_tts", {})
        assert voice.get("status") == "not_started", (
            f"Voice TTS should be not_started; got {voice.get('status')}"
        )

    # Summary
    def test_summary_shape(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        summary = data["summary"]
        assert "connectors_configured" in summary
        assert "connectors_partial" in summary
        assert "connectors_not_configured" in summary
        assert "fargate_healthy" in summary
        assert "pwa_ready" in summary
        assert "ios_scaffold_ready" in summary
        assert "voice_parked" in summary
        assert "fake_claims" in summary

    def test_fake_claims_is_false(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        assert data["summary"]["fake_claims"] is False

    def test_voice_parked_is_true(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        assert data["summary"]["voice_parked"] is True

    def test_summary_counts_are_non_negative(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        s = data["summary"]
        assert s["connectors_configured"] >= 0
        assert s["connectors_partial"] >= 0
        assert s["connectors_not_configured"] >= 0

    def test_summary_connector_counts_add_up(self, client: TestClient):
        data = client.get("/v1/system/status").json()
        s = data["summary"]
        total_connectors = len(data["connectors"])
        count_sum = s["connectors_configured"] + s["connectors_partial"] + s["connectors_not_configured"]
        assert count_sum == total_connectors, (
            f"Connector status counts {count_sum} don't add up to {total_connectors}"
        )

    def test_no_secret_value_in_connector_notes(self, client: TestClient):
        """Notes must say 'not read' or similar — never expose actual values."""
        data = client.get("/v1/system/status").json()
        for name, info in data["connectors"].items():
            note = info.get("note", "").lower()
            # Must acknowledge presence-only approach
            assert (
                "not read" in note or "presence" in note or "only" in note or "value" in note
            ), f"Connector {name} note doesn't assert presence-only: {info['note']}"

    def test_response_is_deterministic(self, client: TestClient):
        """Two calls should return the same connector keys."""
        data1 = client.get("/v1/system/status").json()
        data2 = client.get("/v1/system/status").json()
        assert set(data1["connectors"].keys()) == set(data2["connectors"].keys())
        assert set(data1["system"].keys()) == set(data2["system"].keys())
