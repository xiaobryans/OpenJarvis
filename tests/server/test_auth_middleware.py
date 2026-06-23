"""Tests for API key authentication middleware."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="openjarvis[server] not installed")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from openjarvis.server.auth_middleware import AuthMiddleware


def _make_app(api_key: str) -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuthMiddleware, api_key=api_key)

    @app.get("/v1/models")
    async def models():
        return {"models": []}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.post("/webhooks/twilio")
    async def twilio_webhook():
        return {"status": "received"}

    @app.get("/metrics")
    async def metrics():
        return {"requests": 0}

    return app


@pytest.fixture
def client():
    return TestClient(_make_app("oj_sk_test123"))


class TestAuthMiddleware:
    def test_rejects_missing_auth_header(self, client):
        resp = client.get("/v1/models")
        assert resp.status_code == 401
        assert "missing" in resp.json()["detail"].lower()

    def test_rejects_wrong_key(self, client):
        resp = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    def test_accepts_valid_key(self, client):
        resp = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer oj_sk_test123"},
        )
        assert resp.status_code == 200

    def test_accepts_key_with_accidental_bearer_prefix_in_token(self, client):
        """Mobile clients may send Bearer Bearer <key> if user pasted prefix — normalize token."""
        resp = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer Bearer oj_sk_test123"},
        )
        assert resp.status_code == 200

    def test_accepts_key_with_whitespace(self, client):
        app = _make_app(" oj_sk_test123 ")
        resp = TestClient(app).get(
            "/v1/models",
            headers={"Authorization": "Bearer oj_sk_test123"},
        )
        assert resp.status_code == 200

    def test_health_exempt(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_webhooks_exempt(self, client):
        resp = client.post("/webhooks/twilio")
        assert resp.status_code == 200

    def test_metrics_requires_auth(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 401

    def test_options_preflight_not_auth_blocked(self, client):
        resp = client.options(
            "/v1/models",
            headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert resp.status_code == 200

    def test_metrics_accepts_valid_key(self, client):
        resp = client.get(
            "/metrics", headers={"Authorization": "Bearer oj_sk_test123"}
        )
        assert resp.status_code == 200

    def test_no_key_configured_allows_all(self):
        client = TestClient(_make_app(""))
        resp = client.get("/v1/models")
        assert resp.status_code == 200
        assert client.get("/metrics").status_code == 200
