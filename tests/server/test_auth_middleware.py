"""Tests for API key authentication middleware."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi", reason="openjarvis[server] not installed")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from starlette.requests import Request

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
        data = resp.json()
        assert "missing" in data["detail"].lower()
        assert data.get("auth_reason") == "missing_authorization_header"

    def test_rejects_wrong_key(self, client):
        resp = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer wrong"},
        )
        assert resp.status_code == 401
        data = resp.json()
        assert "invalid" in data["detail"].lower()
        assert data.get("auth_reason") == "token_mismatch"

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


def _request(host: str | None, headers: dict[str, str] | None = None) -> Request:
    """Build a minimal Starlette Request with a given socket peer + headers."""
    raw_headers = [
        (k.lower().encode(), v.encode()) for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/models",
        "headers": raw_headers,
        "client": (host, 50000) if host is not None else None,
    }
    return Request(scope)


class TestLoopbackBypass:
    """Loopback callers are exempt; remote/proxied callers stay gated (#localhost)."""

    @pytest.mark.parametrize("host", ["127.0.0.1", "::1", "127.0.0.5", "localhost"])
    def test_loopback_peer_is_trusted(self, host):
        assert AuthMiddleware._is_trusted_local(_request(host)) is True

    @pytest.mark.parametrize("host", ["10.0.0.5", "192.168.1.10", "testclient", "8.8.8.8"])
    def test_non_loopback_peer_not_trusted(self, host):
        assert AuthMiddleware._is_trusted_local(_request(host)) is False

    def test_missing_client_not_trusted(self):
        assert AuthMiddleware._is_trusted_local(_request(None)) is False

    @pytest.mark.parametrize("header", ["x-forwarded-for", "x-real-ip", "forwarded"])
    def test_forwarding_header_revokes_loopback_bypass(self, header):
        # A same-host reverse proxy connects from loopback but relays a remote
        # client — the forwarding header must force auth back on (fail-safe).
        req = _request("127.0.0.1", {header: "203.0.113.7"})
        assert AuthMiddleware._is_trusted_local(req) is False

    def test_loopback_request_bypasses_auth_end_to_end(self):
        """A loopback GET to a gated route returns 200 with no Authorization."""
        app = _make_app("oj_sk_test123")
        # TestClient lets us set the ASGI scope's client peer to loopback.
        client = TestClient(app, client=("127.0.0.1", 50000))
        resp = client.get("/v1/models")
        assert resp.status_code == 200

    def test_loopback_request_with_forwarded_header_still_401(self):
        app = _make_app("oj_sk_test123")
        client = TestClient(app, client=("127.0.0.1", 50000))
        resp = client.get("/v1/models", headers={"X-Forwarded-For": "203.0.113.7"})
        assert resp.status_code == 401
