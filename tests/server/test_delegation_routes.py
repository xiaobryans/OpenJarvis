"""Tests for Plan 4-6 B7 — delegation queue routes.

Tests:
  GET /v1/delegation/queue          — aggregate response shape, graceful degradation
  GET /v1/delegation/queue/summary  — count summary shape

Design:
  - All probes are try/except-wrapped — import errors surface as errors[], not failures
  - No real approval/reject calls in unit tests (those hit live endpoints)
  - Secret safety: DelegationItem.extra never contains raw payload
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Minimal app fixture (import guards for missing deps)
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    try:
        from openjarvis.server.delegation_routes import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        return TestClient(app, raise_server_exceptions=False)
    except ImportError as exc:
        pytest.skip(f"delegation_routes not importable: {exc}")


# ---------------------------------------------------------------------------
# GET /v1/delegation/queue
# ---------------------------------------------------------------------------

class TestDelegationQueue:
    def test_returns_200(self, client: TestClient):
        r = client.get("/v1/delegation/queue")
        assert r.status_code == 200

    def test_response_shape(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        assert "items" in data
        assert "count" in data
        assert "by_source" in data
        assert "errors" in data
        assert "sources_probed" in data
        assert "note" in data

    def test_by_source_keys(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        by_src = data["by_source"]
        assert "life_os" in by_src
        assert "agent_action" in by_src
        assert "mission" in by_src

    def test_count_matches_items(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        assert data["count"] == len(data["items"])

    def test_count_matches_by_source_sum(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        by_src = data["by_source"]
        assert data["count"] == by_src["life_os"] + by_src["agent_action"] + by_src["mission"]

    def test_items_are_list(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        assert isinstance(data["items"], list)

    def test_errors_are_list(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        assert isinstance(data["errors"], list)

    def test_sources_probed_are_list(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        assert isinstance(data["sources_probed"], list)

    def test_all_three_sources_probed(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        probed = set(data["sources_probed"])
        assert {"life_os", "agent_action", "mission"} == probed

    def test_item_shape_if_any(self, client: TestClient):
        """If items exist, each must have required fields."""
        data = client.get("/v1/delegation/queue").json()
        for item in data["items"]:
            assert "delegation_id" in item
            assert "source" in item
            assert "title" in item
            assert "status" in item
            assert "category" in item
            assert "authority_tier" in item
            assert "audit_id" in item
            assert "tags" in item
            assert "extra" in item

    def test_item_source_values_valid(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        valid_sources = {"life_os", "agent_action", "mission"}
        for item in data["items"]:
            assert item["source"] in valid_sources, f"Unexpected source: {item['source']}"

    def test_no_raw_payload_in_items(self, client: TestClient):
        """Agent action items must not leak raw payload — only payload_present bool."""
        data = client.get("/v1/delegation/queue").json()
        for item in data["items"]:
            # 'payload' as a top-level field is forbidden
            assert "payload" not in item, "Raw payload field leaked into delegation item"
            # extra may contain payload_present bool, but not the actual payload
            extra = item.get("extra", {})
            assert "payload" not in extra, "Raw payload leaked into extra field"

    def test_count_is_non_negative(self, client: TestClient):
        data = client.get("/v1/delegation/queue").json()
        assert data["count"] >= 0
        assert data["by_source"]["life_os"] >= 0
        assert data["by_source"]["agent_action"] >= 0
        assert data["by_source"]["mission"] >= 0


# ---------------------------------------------------------------------------
# GET /v1/delegation/queue/summary
# ---------------------------------------------------------------------------

class TestDelegationSummary:
    def test_returns_200(self, client: TestClient):
        r = client.get("/v1/delegation/queue/summary")
        assert r.status_code == 200

    def test_summary_shape(self, client: TestClient):
        data = client.get("/v1/delegation/queue/summary").json()
        assert "total" in data
        assert "by_source" in data
        assert "has_pending" in data

    def test_has_pending_is_bool(self, client: TestClient):
        data = client.get("/v1/delegation/queue/summary").json()
        assert isinstance(data["has_pending"], bool)

    def test_total_matches_by_source_sum(self, client: TestClient):
        data = client.get("/v1/delegation/queue/summary").json()
        by_src = data["by_source"]
        assert data["total"] == by_src["life_os"] + by_src["agent_action"] + by_src["mission"]

    def test_has_pending_consistent_with_total(self, client: TestClient):
        data = client.get("/v1/delegation/queue/summary").json()
        if data["total"] > 0:
            assert data["has_pending"] is True
        else:
            assert data["has_pending"] is False

    def test_total_non_negative(self, client: TestClient):
        data = client.get("/v1/delegation/queue/summary").json()
        assert data["total"] >= 0
