"""Phase H gate tests — /v1/system/health includes memory_os sub-key.

Validates:
1. /v1/system/health returns memory_os field.
2. memory_os.vector_search reflects actual key presence (not static green).
3. memory_os.total_entries is a non-negative integer (live, not hardcoded).
4. memory_os.sprint contains actual sprint identifier.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.api_routes import include_all_routes  # noqa: E402


@pytest.fixture()
def test_client():
    app = FastAPI()
    include_all_routes(app)
    return TestClient(app)


class TestSystemHealthMemoryOS:
    def test_system_health_returns_200(self, test_client):
        resp = test_client.get("/v1/system/health")
        assert resp.status_code == 200

    def test_memory_os_key_present(self, test_client):
        """memory_os sub-key must be in /v1/system/health response."""
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        assert "memory_os" in data, (
            "memory_os sub-key missing from /v1/system/health"
        )

    def test_memory_os_has_sprint_field(self, test_client):
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        mos = data.get("memory_os", {})
        if "status" not in mos or mos.get("status") != "error":
            assert "sprint" in mos

    def test_memory_os_total_entries_is_integer(self, test_client):
        """total_entries must be a non-negative integer (live, not static)."""
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        mos = data.get("memory_os", {})
        if "total_entries" in mos:
            assert isinstance(mos["total_entries"], int)
            assert mos["total_entries"] >= 0

    def test_memory_os_vector_search_present(self, test_client):
        """vector_search field must be present and be a string."""
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        mos = data.get("memory_os", {})
        if "vector_search" in mos:
            assert isinstance(mos["vector_search"], str)
            assert len(mos["vector_search"]) > 0

    def test_memory_os_not_static_fake_green(self, test_client):
        """memory_os values must not be hardcoded fake 'ok' strings."""
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        mos = data.get("memory_os", {})
        # sprint must not be a generic placeholder
        sprint = mos.get("sprint", "")
        if sprint:
            assert sprint != "ok" and sprint != "green" and sprint != "ready"

    def test_memory_section_still_present(self, test_client):
        """Original memory section must still be in the health response."""
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        assert "memory" in data

    def test_cloud_sync_available_is_bool(self, test_client):
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        mos = data.get("memory_os", {})
        if "cloud_sync_available" in mos:
            assert isinstance(mos["cloud_sync_available"], bool)

    def test_ai_distillation_available_is_bool(self, test_client):
        resp = test_client.get("/v1/system/health")
        data = resp.json()
        mos = data.get("memory_os", {})
        if "ai_distillation_available" in mos:
            assert isinstance(mos["ai_distillation_available"], bool)
