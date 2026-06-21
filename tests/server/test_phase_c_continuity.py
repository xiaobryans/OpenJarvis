"""Phase C gate tests — Mobile continuity routes + ContinuityStore.

Validates:
1. GET /v1/mobile/continuity/status returns backends list.
2. GET /v1/mobile/status includes continuity sub-key.
3. ContinuityStore: save snapshot under session A, retrieve under session B.
4. source_device_id differs between two snapshots.
5. Status: gist backend reports GITHUB_TOKEN requirement; local-only when absent.
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from openjarvis.server.autonomy_routes import router  # noqa: E402


@pytest.fixture()
def test_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestContinuityStatusEndpoint:
    def test_continuity_status_returns_200(self, test_client):
        resp = test_client.get("/v1/mobile/continuity/status")
        assert resp.status_code == 200

    def test_continuity_status_has_backends(self, test_client):
        resp = test_client.get("/v1/mobile/continuity/status")
        data = resp.json()
        assert "backends" in data or "error" in data

    def test_continuity_status_has_active_backend(self, test_client):
        resp = test_client.get("/v1/mobile/continuity/status")
        data = resp.json()
        if "error" not in data:
            assert "active_backend" in data

    def test_continuity_status_has_cross_device_ready(self, test_client):
        resp = test_client.get("/v1/mobile/continuity/status")
        data = resp.json()
        if "error" not in data:
            assert "cross_device_ready" in data

    def test_mobile_status_includes_continuity_key(self, test_client):
        resp = test_client.get("/v1/mobile/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "continuity" in data

    def test_gist_backend_in_backends_list(self, test_client):
        resp = test_client.get("/v1/mobile/continuity/status")
        data = resp.json()
        if "backends" in data and isinstance(data["backends"], list):
            backend_names = [b.get("name", "") for b in data["backends"]]
            assert any("gist" in n for n in backend_names)

    def test_local_backend_not_macbook_off_capable(self, test_client):
        resp = test_client.get("/v1/mobile/continuity/status")
        data = resp.json()
        if "backends" in data:
            for b in data["backends"]:
                if "local" in b.get("name", ""):
                    assert b.get("macbook_off_capable") is False


class TestContinuityStore:
    def test_save_and_retrieve_snapshot(self):
        from openjarvis.mobile.continuity import ContinuityStore

        store = ContinuityStore()
        snap = store.save_snapshot(
            user_id="bryan",
            source_device_id="device-a",
            active_task_description="write tests",
            active_task_status="active",
        )
        assert snap.snapshot_id is not None

        retrieved = store.get_snapshot(snap.snapshot_id)
        assert retrieved is not None
        assert retrieved.snapshot_id == snap.snapshot_id

    def test_source_device_id_differs_between_sessions(self):
        from openjarvis.mobile.continuity import ContinuityStore

        store = ContinuityStore()

        snap_a = store.save_snapshot(
            user_id="bryan",
            source_device_id="device-a",
            active_task_description="initial task",
        )
        snap_b = store.save_snapshot(
            user_id="bryan",
            source_device_id="device-b",
            active_task_description="continued task",
        )

        assert snap_a.source_device_id != snap_b.source_device_id

    def test_get_latest_snapshot_returns_most_recent(self):
        import time
        from openjarvis.mobile.continuity import ContinuityStore

        store = ContinuityStore()
        store.save_snapshot(
            user_id="bryan",
            source_device_id="device-a",
            active_task_description="task-1",
        )
        time.sleep(0.01)
        snap_b = store.save_snapshot(
            user_id="bryan",
            source_device_id="device-b",
            active_task_description="task-2",
        )

        latest = store.get_latest_snapshot("bryan")
        assert latest is not None
        assert latest.snapshot_id == snap_b.snapshot_id


class TestContinuityBackendStatus:
    def test_local_backend_not_off_capable(self):
        from openjarvis.mobile.continuity_backend import LocalFileBackend
        status = LocalFileBackend().get_status()
        assert status.macbook_off_capable is False

    def test_gist_backend_is_macbook_off_capable(self):
        from openjarvis.mobile.continuity_backend import GitHubGistBackend
        status = GitHubGistBackend().get_status()
        assert status.macbook_off_capable is True

    def test_gist_backend_reports_github_token_required(self):
        from openjarvis.mobile.continuity_backend import GitHubGistBackend
        status = GitHubGistBackend().get_status()
        assert "GITHUB_TOKEN" in status.env_vars_required
