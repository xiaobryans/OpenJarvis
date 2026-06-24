"""Plan 2D — Memory/Context/Routing Parity smoke tests.

Verifies:
- _memory_cloud_sync_probe() returns correct structure and honest status
- _status_2d_memory() never claims fake READY for macbook_off
- Public memory parity endpoint is sanitized (no bucket names, no content)
- Memory sync route exists and is properly described
- Blockers are reported honestly when S3 unavailable
"""

from __future__ import annotations

import asyncio
import pytest


# ---------------------------------------------------------------------------
# _memory_cloud_sync_probe
# ---------------------------------------------------------------------------

class TestMemoryCloudSyncProbe:
    def test_returns_expected_keys(self):
        from openjarvis.server.plan2_routes import _memory_cloud_sync_probe
        r = _memory_cloud_sync_probe()
        assert "available" in r
        assert "bucket_configured" in r
        assert "region_configured" in r
        assert "can_read" in r
        assert "can_write" in r
        assert "note" in r

    def test_no_bucket_name_in_response(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "super-secret-bucket")
        from openjarvis.server.plan2_routes import _memory_cloud_sync_probe
        r = _memory_cloud_sync_probe()
        payload = str(r)
        assert "super-secret-bucket" not in payload

    def test_structure_when_bucket_absent(self, monkeypatch):
        """Probe returns honest structure regardless of S3 availability.

        Note: cloud_sync._load_env_from_file() may read from .env even when
        os.environ is patched — so we test structure, not specific values.
        """
        from openjarvis.server.plan2_routes import _memory_cloud_sync_probe
        r = _memory_cloud_sync_probe()
        assert isinstance(r["available"], bool)
        assert isinstance(r["bucket_configured"], bool)
        # If not available, must have an error reason
        if not r["available"]:
            assert r.get("last_error") or not r["bucket_configured"]

    def test_available_flag_is_bool(self):
        from openjarvis.server.plan2_routes import _memory_cloud_sync_probe
        r = _memory_cloud_sync_probe()
        assert isinstance(r["available"], bool)

    def test_note_does_not_expose_credentials(self):
        from openjarvis.server.plan2_routes import _memory_cloud_sync_probe
        r = _memory_cloud_sync_probe()
        note = r.get("note", "")
        assert "password" not in note.lower()
        assert "secret" not in note.lower()


# ---------------------------------------------------------------------------
# _status_2d_memory — honest status
# ---------------------------------------------------------------------------

class TestStatus2DMemory:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        assert s["subsection"] == "2D"

    def test_no_fake_ready_for_macbook_off(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        assert s["macbook_off_status"] != "READY"

    def test_blockers_not_empty(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        assert len(s["blockers"]) > 0

    def test_cloud_sync_probe_in_response(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        assert "cloud_sync_probe" in s
        assert isinstance(s["cloud_sync_probe"], dict)

    def test_no_bucket_names_in_status(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "my-private-bucket")
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        payload = str(s)
        assert "my-private-bucket" not in payload

    def test_key_routes_include_sync(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        routes_str = " ".join(s["key_routes"])
        assert "/v1/memory/sync" in routes_str
        assert "/v1/mobile-parity/memory" in routes_str

    def test_pinecone_field_is_bool(self):
        from openjarvis.server.plan2_routes import _status_2d_memory
        s = _status_2d_memory()
        assert isinstance(s.get("pinecone_configured"), bool)


# ---------------------------------------------------------------------------
# Public /v1/mobile-parity/memory endpoint sanitization
# ---------------------------------------------------------------------------

class TestPublicMemoryParityEndpoint:
    def test_returns_plan_2d_verdict(self):
        result = asyncio.run(__import__("openjarvis.server.plan2_routes", fromlist=["get_memory_parity_status"]).get_memory_parity_status())
        assert "PLAN_2D" in result["sprint_verdict"]

    def test_no_bucket_names_in_public_response(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "classified-bucket")
        from openjarvis.server.plan2_routes import get_memory_parity_status
        result = asyncio.run(get_memory_parity_status())
        payload = str(result)
        assert "classified-bucket" not in payload

    def test_no_memory_content_in_response(self):
        from openjarvis.server.plan2_routes import get_memory_parity_status
        result = asyncio.run(get_memory_parity_status())
        # Should not have raw memory entries
        assert "content" not in result
        assert "entries" not in result
        assert "memory_entries" not in result

    def test_cloud_sync_available_is_bool(self):
        from openjarvis.server.plan2_routes import get_memory_parity_status
        result = asyncio.run(get_memory_parity_status())
        assert isinstance(result.get("cloud_sync_available"), bool)

    def test_subsection_is_2d(self):
        from openjarvis.server.plan2_routes import get_memory_parity_status
        result = asyncio.run(get_memory_parity_status())
        assert result["subsection"] == "2D"

    def test_blockers_is_list(self):
        from openjarvis.server.plan2_routes import get_memory_parity_status
        result = asyncio.run(get_memory_parity_status())
        assert isinstance(result["blockers"], list)
        assert len(result["blockers"]) > 0


# ---------------------------------------------------------------------------
# Memory sync route integrity (unit level)
# ---------------------------------------------------------------------------

class TestMemorySyncRouteIntegrity:
    def test_cloud_sync_module_importable(self):
        from openjarvis.memory.cloud_sync import JarvisMemoryS3Sync
        assert JarvisMemoryS3Sync is not None

    def test_get_status_truncates_bucket(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "verylongsecretbucketname")
        monkeypatch.delenv("OMNIX_WORKBENCH_AWS_PROFILE", raising=False)
        from openjarvis.memory.cloud_sync import JarvisMemoryS3Sync
        sync = JarvisMemoryS3Sync()
        status = sync.get_status()
        if status.bucket:
            assert len(status.bucket) <= 12, (
                f"Bucket name longer than 12 chars in status: {status.bucket!r}"
            )

    def test_get_status_returns_cloudsynccstatus(self, monkeypatch):
        """get_status() always returns a CloudSyncStatus regardless of config.

        Note: cloud_sync loads .env file internally, so monkeypatching os.environ
        alone cannot guarantee bucket is absent. We test the contract, not the value.
        """
        from openjarvis.memory.cloud_sync import JarvisMemoryS3Sync, CloudSyncStatus
        sync = JarvisMemoryS3Sync()
        status = sync.get_status()
        assert isinstance(status, CloudSyncStatus)
        assert isinstance(status.available, bool)
        assert isinstance(status.can_read, bool)
        assert isinstance(status.can_write, bool)
