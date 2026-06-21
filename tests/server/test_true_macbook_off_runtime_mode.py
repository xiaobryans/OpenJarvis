"""Tests for runtime_mode and cloud_url fields in /v1/mobile/continuity/status.

Validates:
1. runtime_mode is 'local_lan' when no cloud env vars set.
2. runtime_mode is 'cloud' when CLOUD_RUNTIME_DEPLOYMENT is set.
3. cloud_url is None when JARVIS_CLOUD_URL is not set.
4. cloud_url returns configured value when JARVIS_CLOUD_URL is set.
5. /v1/mobile/continuity/status response includes both new fields.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openjarvis.server.autonomy_routes import (
    _runtime_mode,
    _cloud_url,
    _is_cloud_runtime,
    router,
)


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRuntimeModeHelpers:
    def test_local_lan_when_no_cloud_env(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("CLOUD_RUNTIME_DEPLOYMENT", "ECS_CONTAINER_METADATA_URI", "ECS_CONTAINER_METADATA_URI_V4"):
                os.environ.pop(key, None)
            assert _runtime_mode() == "local_lan"

    def test_cloud_when_cloud_runtime_deployment_set(self):
        with patch.dict(os.environ, {"CLOUD_RUNTIME_DEPLOYMENT": "aws-ecs-fargate"}):
            assert _runtime_mode() == "cloud"

    def test_cloud_when_ecs_metadata_uri_set(self):
        with patch.dict(os.environ, {"ECS_CONTAINER_METADATA_URI": "http://169.254.170.2/v3/abc"}):
            assert _runtime_mode() == "cloud"

    def test_cloud_url_none_when_not_configured(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_CLOUD_URL", None)
            assert _cloud_url() is None

    def test_cloud_url_returns_configured_value(self):
        url = "https://2r8dnzlz1h.execute-api.ap-southeast-1.amazonaws.com"
        with patch.dict(os.environ, {"JARVIS_CLOUD_URL": url}):
            assert _cloud_url() == url

    def test_runtime_mode_values_are_valid(self):
        valid_modes = {"local_lan", "cloud"}
        mode = _runtime_mode()
        assert mode in valid_modes, f"Unexpected runtime_mode: {mode!r}"


class TestMobileContinuityStatusEndpoint:
    def test_endpoint_includes_runtime_mode(self, client):
        resp = client.get("/v1/mobile/continuity/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "runtime_mode" in data, "runtime_mode field missing from response"
        assert data["runtime_mode"] in ("local_lan", "cloud")

    def test_endpoint_includes_cloud_url(self, client):
        resp = client.get("/v1/mobile/continuity/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "cloud_url" in data, "cloud_url field missing from response"

    def test_cloud_url_is_none_without_env(self, client):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("JARVIS_CLOUD_URL", None)
            resp = client.get("/v1/mobile/continuity/status")
            data = resp.json()
            assert data.get("cloud_url") is None

    def test_cloud_url_reflects_env_var(self, client):
        url = "https://example.execute-api.ap-southeast-1.amazonaws.com"
        with patch.dict(os.environ, {"JARVIS_CLOUD_URL": url}):
            resp = client.get("/v1/mobile/continuity/status")
            data = resp.json()
            assert data.get("cloud_url") == url

    def test_runtime_mode_is_local_lan_without_cloud_env(self, client):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("CLOUD_RUNTIME_DEPLOYMENT", "ECS_CONTAINER_METADATA_URI", "ECS_CONTAINER_METADATA_URI_V4"):
                os.environ.pop(key, None)
            resp = client.get("/v1/mobile/continuity/status")
            data = resp.json()
            assert data.get("runtime_mode") == "local_lan"

    def test_existing_fields_still_present(self, client):
        resp = client.get("/v1/mobile/continuity/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "state_sync_macbook_off_capable" in data
        assert "runtime_macbook_off_capable" in data
        assert "runtime_deployment" in data
        assert "runtime_always_on_status" in data
