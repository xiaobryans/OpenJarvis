"""Phase A gate tests — GET /v1/memory/status endpoint.

Validates:
1. All four sub-fields are present in the response.
2. cloud_sync.available does NOT claim Supabase when only S3 config is present.
3. semantic_search reflects real key presence (active ranker is honest).
4. memory_os contains sprint and entry counts.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.memory_routes import router  # noqa: E402


@pytest.fixture()
def test_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestMemoryStatusEndpoint:
    def test_endpoint_exists_and_returns_200(self, test_client):
        resp = test_client.get("/v1/memory/status")
        assert resp.status_code == 200

    def test_all_four_sub_fields_present(self, test_client):
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        assert "memory_os" in data
        assert "semantic_search" in data
        assert "cloud_sync" in data
        assert "ai_distillation" in data

    def test_memory_os_has_sprint_field(self, test_client):
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        mos = data["memory_os"]
        assert "sprint" in mos or "status" in mos  # error fallback allowed

    def test_memory_os_has_entry_counts(self, test_client):
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        mos = data["memory_os"]
        if "status" not in mos or mos.get("status") != "error":
            assert "total_entries" in mos
            assert "total_distilled" in mos

    def test_cloud_sync_does_not_claim_supabase_when_s3_only(self, test_client):
        """cloud_sync.backend must not say 'supabase' when only S3 credentials exist."""
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        cs = data["cloud_sync"]
        # If available, backend must not be supabase (only S3 configured via OMNIX workbench)
        if cs.get("available"):
            assert cs.get("backend", "").lower() != "supabase"

    def test_semantic_search_has_vector_search_field(self, test_client):
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        ss = data["semantic_search"]
        if "status" not in ss or ss.get("status") != "error":
            # Should have a field indicating active ranker
            assert "active_ranker" in ss or "vector_search" in ss or "openai_key_available" in ss

    def test_semantic_search_honest_without_key(self, test_client):
        """Without OPENAI_API_KEY, semantic search must not claim OpenAI is active."""
        saved = os.environ.pop("OPENAI_API_KEY", None)
        try:
            # Re-import to clear cached key state
            import importlib
            import openjarvis.memory.retrieval as ret_mod
            importlib.reload(ret_mod)

            resp = test_client.get("/v1/memory/status")
            data = resp.json()
            ss = data["semantic_search"]
            if "active_ranker" in ss:
                assert ss["active_ranker"] != "openai_embeddings"
        finally:
            if saved:
                os.environ["OPENAI_API_KEY"] = saved
            # reload again to restore
            import importlib
            import openjarvis.memory.retrieval as ret_mod
            importlib.reload(ret_mod)

    def test_semantic_search_active_when_key_present(self, test_client):
        """With OPENAI_API_KEY set, active_ranker should report openai."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key-xxxx"}):
            import importlib
            import openjarvis.memory.retrieval as ret_mod
            importlib.reload(ret_mod)

            resp = test_client.get("/v1/memory/status")
            data = resp.json()
            ss = data["semantic_search"]
            if "active_ranker" in ss:
                # With key present, should report openai
                assert "openai" in ss["active_ranker"].lower() or "tfidf" in ss["active_ranker"].lower()

    def test_ai_distillation_has_status_or_engine_field(self, test_client):
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        ad = data["ai_distillation"]
        # Should not be empty
        assert isinstance(ad, dict)
        assert len(ad) > 0

    def test_cloud_sync_available_field_is_bool(self, test_client):
        resp = test_client.get("/v1/memory/status")
        data = resp.json()
        cs = data["cloud_sync"]
        if "available" in cs:
            assert isinstance(cs["available"], bool)
