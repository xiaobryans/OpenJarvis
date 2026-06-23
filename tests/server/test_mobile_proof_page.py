"""Tests for Plan 9 mobile proof page at GET /mobile."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.company_org_routes import router as mobile_router


@pytest.fixture(scope="module")
def mobile_client():
    app = FastAPI()
    app.include_router(mobile_router)
    return TestClient(app)


class TestPlan9MobileProofPage:
    def test_mobile_page_is_200(self, mobile_client):
        resp = mobile_client.get("/mobile")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_proof_summary_and_sentinel(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert "Mobile Proof Summary" in html
        assert "END OF MOBILE PROOF" in html
        assert "AUTHENTICATED" in html
        assert "KEY_SET_BUT_AUTH_FAILED" in html
        assert "NO_AUTH_KEY" in html

    def test_test_api_key_button_and_registry_probe(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert "Test API Key" in html
        assert "/v1/plan9/registry" in html
        assert "testApiKey" in html
        assert "normalizeApiKey" in html
        assert "Raw API key only" in html

    def test_header_mode_diagnostics(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert "header-mode" in html
        assert "Authorization: Bearer &lt;hidden&gt;" in html

    def test_required_panel_paths(self, mobile_client):
        html = mobile_client.get("/mobile").text
        for path in (
            "/v1/plan9/registry",
            "/v1/authority/approvals/pending",
            "/v1/authority/audit",
            "/v1/coding/workflow/status",
            "/v1/model-routing/status",
            "/v1/memory/status",
            "/v1/connectors",
        ):
            assert path in html, f"missing panel path {path}"

    def test_scroll_css_uses_dvh(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert "100dvh" in html

    def test_text_fallback_preserved(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert "text-input" in html
        assert "submitText" in html
        assert "/v1/chat/completions" in html

    def test_macbook_off_probe_reference(self, mobile_client):
        html = mobile_client.get("/mobile").text
        assert "/v1/continuity/macbook-off-status" in html
