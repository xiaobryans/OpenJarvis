"""Tests for Mobile/iOS/Productization status routes (B3)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.productization_routes import router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestProductizationStatus:
    def test_status_ok(self, client):
        r = client.get("/v1/productization/status")
        assert r.status_code == 200
        data = r.json()
        assert "mobile_web_pwa" in data
        assert "native_ios" in data
        assert "app_store" in data
        assert "gates" in data
        assert "summary" in data

    def test_pwa_is_implemented(self, client):
        r = client.get("/v1/productization/status")
        pwa = r.json()["mobile_web_pwa"]
        assert pwa["status"] == "implemented"

    def test_ios_scaffold_not_present(self, client):
        r = client.get("/v1/productization/status")
        ios = r.json()["native_ios"]
        assert ios["scaffold_status"] == "not_scaffolded"
        assert ios["scaffold_status"] != "present"

    def test_desktop_scaffold_present(self, client):
        r = client.get("/v1/productization/status")
        ios = r.json()["native_ios"]
        assert ios["desktop_scaffold_status"] == "present"
        assert "src-tauri" in ios["desktop_scaffold_path"]

    def test_desktop_scaffold_separate_from_ios_scaffold(self, client):
        r = client.get("/v1/productization/status")
        ios = r.json()["native_ios"]
        assert ios["desktop_scaffold_status"] == "present"
        assert ios["scaffold_status"] == "not_scaffolded"
        assert ios["desktop_scaffold_status"] != ios["scaffold_status"]

    def test_no_fake_app_store_claim(self, client):
        r = client.get("/v1/productization/status")
        data = r.json()
        assert data["app_store"]["status"] == "not_submitted"
        assert data["app_store"]["fake_claim"] is False
        assert data["summary"]["app_store_ready"] is False
        assert data["summary"]["fake_claims"] is False

    def test_pwa_ready_true(self, client):
        r = client.get("/v1/productization/status")
        assert r.json()["summary"]["pwa_ready"] is True

    def test_ios_scaffold_ready_false(self, client):
        r = client.get("/v1/productization/status")
        assert r.json()["summary"]["ios_scaffold_ready"] is False

    def test_desktop_scaffold_ready_true(self, client):
        r = client.get("/v1/productization/status")
        assert r.json()["summary"]["desktop_scaffold_ready"] is True

    def test_apple_developer_account_is_external_gate(self, client):
        r = client.get("/v1/productization/status")
        gates = r.json()["gates"]
        apple_gate = next((g for g in gates if g["gate"] == "apple_developer_account"), None)
        assert apple_gate is not None
        assert apple_gate["status"] == "EXTERNAL_GATE"

    def test_gates_summary_counts(self, client):
        r = client.get("/v1/productization/status")
        s = r.json()["summary"]
        assert s["gates_total"] == len(r.json()["gates"])
        assert s["gates_pass"] >= 1

    def test_next_steps_present(self, client):
        r = client.get("/v1/productization/status")
        assert len(r.json()["next_steps"]) >= 1


class TestIOSRoute:
    def test_ios_ok(self, client):
        r = client.get("/v1/productization/ios")
        assert r.status_code == 200
        data = r.json()
        assert "native_ios" in data
        assert "app_store" in data

    def test_ios_no_fake_submission(self, client):
        r = client.get("/v1/productization/ios")
        assert r.json()["app_store"]["status"] == "not_submitted"


class TestMobileRoute:
    def test_mobile_ok(self, client):
        r = client.get("/v1/productization/mobile")
        assert r.status_code == 200
        data = r.json()
        assert data["installable"] is True
        assert data["api_parity"] is True
        assert data["responsive_ui"] is True

    def test_mobile_pwa_implemented(self, client):
        r = client.get("/v1/productization/mobile")
        assert r.json()["mobile_web_pwa"]["status"] == "implemented"
