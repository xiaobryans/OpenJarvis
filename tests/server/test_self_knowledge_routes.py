"""Tests for Jarvis self-knowledge routes."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from openjarvis.server.self_knowledge_routes import router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestCapabilitiesRoute:
    def test_list_capabilities_ok(self, client):
        r = client.get("/v1/jarvis/capabilities")
        assert r.status_code == 200
        data = r.json()
        assert "capabilities" in data
        assert "summary" in data
        assert data["text_first"] is True

    def test_capabilities_no_fake_available(self, client):
        r = client.get("/v1/jarvis/capabilities")
        data = r.json()
        # Voice must be parked, not available
        voice = next((c for c in data["capabilities"] if c["id"] == "voice_tts"), None)
        assert voice is not None
        assert voice["status"] == "parked"

    def test_capabilities_plan3_parked(self, client):
        r = client.get("/v1/jarvis/capabilities")
        data = r.json()
        assert data["voice_status"] == "PARKED"

    def test_capabilities_filter_by_status(self, client):
        r = client.get("/v1/jarvis/capabilities?status=parked")
        data = r.json()
        for cap in data["capabilities"]:
            assert cap["status"] == "parked"

    def test_capabilities_summary_counts(self, client):
        r = client.get("/v1/jarvis/capabilities")
        data = r.json()
        s = data["summary"]
        assert s["total"] == len(data["capabilities"])


class TestStatusRoute:
    def test_status_ok(self, client):
        r = client.get("/v1/jarvis/status")
        assert r.status_code == 200
        data = r.json()
        assert data["plan_state"]["plan_1"] == "ACCEPTED"
        assert data["plan_state"]["plan_2"] == "ACCEPTED"
        assert data["plan_state"]["plan_3_voice"] == "PARKED"
        assert data["fake_claims"] is False
        assert data["text_first"] is True
        assert data["voice_parked"] is True

    def test_status_plan46_in_progress(self, client):
        r = client.get("/v1/jarvis/status")
        data = r.json()
        assert "IN_PROGRESS" in data["plan_state"]["plan_4_6_mega_sprint"]


class TestRoadmapRoute:
    def test_roadmap_ok(self, client):
        r = client.get("/v1/jarvis/roadmap")
        assert r.status_code == 200
        data = r.json()
        assert "roadmap" in data
        assert len(data["roadmap"]) > 0

    def test_roadmap_plan3_parked(self, client):
        r = client.get("/v1/jarvis/roadmap")
        data = r.json()
        plan3 = next((p for p in data["roadmap"] if p["plan"] == "Plan 3"), None)
        assert plan3 is not None
        assert "PARKED" in plan3["status"]

    def test_roadmap_no_accepted_claim(self, client):
        r = client.get("/v1/jarvis/roadmap")
        data = r.json()
        assert "only Bryan" in data["note"].lower() or "Bryan" in data["note"]
