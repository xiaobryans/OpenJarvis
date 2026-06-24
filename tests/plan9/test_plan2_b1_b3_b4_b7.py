"""Plan 2 blocker closure tests — B1, B3, B4, B7.

Tests the following requirements:
  - B1: Google OAuth tokens are honestly reported as LOCAL_FILE_ONLY; vault not configured
  - B3: Telegram token detection works for BOTH canonical and legacy env var names (CODE_CLOSED)
  - B4: Notion is NOT_CONFIGURED when no token set; detected when env var set
  - B7: Life-OS cloud sync honestly tracks layers; sync_executed always requires_deployment
  - Endpoint safety: public /v1/mobile-parity/life-os does not expose S3 names, paths, secrets
  - Overall Plan 2 verdict remains HOLD while any blocker remains

Hard rules verified:
  - No secret values in any response
  - No env var names on public responses
  - No bucket names in public responses
  - No fake READY while blockers remain
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


# ---------------------------------------------------------------------------
# Helper: import plan2_routes safely
# ---------------------------------------------------------------------------

def _import_plan2():
    from openjarvis.server import plan2_routes
    return plan2_routes


# ===========================================================================
# B3 — Telegram dual alias (CODE_CLOSED verification)
# ===========================================================================

class TestB3TelegramDualAlias:
    """B3 is fully code-closed: both canonical and legacy env var names work."""

    def test_telegram_present_canonical(self):
        r = _import_plan2()
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "tok123"}, clear=False):
            assert r._telegram_present() is True

    def test_telegram_present_legacy(self):
        r = _import_plan2()
        env = {k: v for k, v in os.environ.items()
               if k not in ("TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN")}
        with patch.dict(os.environ, {**env, "JARVIS_TELEGRAM_BOT_TOKEN": "tok456"}, clear=True):
            assert r._telegram_present() is True

    def test_telegram_absent_when_neither_set(self):
        r = _import_plan2()
        env = {k: v for k, v in os.environ.items()
               if k not in ("TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN")}
        with patch.dict(os.environ, env, clear=True):
            assert r._telegram_present() is False

    def test_connector_token_present_telegram_canonical(self):
        r = _import_plan2()
        telegram_rec = next(
            (c for c in r._CONNECTOR_REGISTRY if c["connector_id"] == "telegram"), None
        )
        assert telegram_rec is not None
        env = {k: v for k, v in os.environ.items()
               if k not in ("TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN")}
        with patch.dict(os.environ, {**env, "TELEGRAM_BOT_TOKEN": "tok789"}, clear=True):
            assert r._connector_token_present(telegram_rec) is True

    def test_connector_token_present_telegram_legacy(self):
        r = _import_plan2()
        telegram_rec = next(
            (c for c in r._CONNECTOR_REGISTRY if c["connector_id"] == "telegram"), None
        )
        assert telegram_rec is not None
        env = {k: v for k, v in os.environ.items()
               if k not in ("TELEGRAM_BOT_TOKEN", "JARVIS_TELEGRAM_BOT_TOKEN")}
        with patch.dict(os.environ, {**env, "JARVIS_TELEGRAM_BOT_TOKEN": "tokLeg"}, clear=True):
            assert r._connector_token_present(telegram_rec) is True

    def test_b3_note_in_status_2b(self):
        """_status_2b_connectors() notes must reference B3 closure."""
        r = _import_plan2()
        status = r._status_2b_connectors()
        notes = " ".join(status.get("notes", []))
        assert "B3" in notes
        assert "TELEGRAM" in notes.upper() or "telegram" in notes.lower()


# ===========================================================================
# B1 — Google OAuth vault status
# ===========================================================================

class TestB1GoogleOAuthVaultStatus:
    """B1: Google OAuth tokens are local-file only; vault not configured; migration required."""

    def test_vault_never_configured(self):
        r = _import_plan2()
        result = r._google_oauth_local_status()
        assert result["cloud_vault_configured"] is False

    def test_vault_migration_needed_always_true(self):
        r = _import_plan2()
        result = r._google_oauth_local_status()
        assert result["vault_migration_needed"] is True

    def test_b1_status_local_file_only(self):
        r = _import_plan2()
        result = r._google_oauth_local_status()
        assert result["b1_status"] == "LOCAL_FILE_ONLY"

    def test_b1_action_required_present(self):
        r = _import_plan2()
        result = r._google_oauth_local_status()
        assert "b1_action_required" in result
        assert len(result["b1_action_required"]) > 20

    def test_b1_no_token_values(self):
        r = _import_plan2()
        result = r._google_oauth_local_status()
        result_str = json.dumps(result)
        # Should not contain any token-like patterns
        assert "ya29." not in result_str
        assert "Bearer " not in result_str

    def test_b1_status_in_2b_connectors(self):
        r = _import_plan2()
        status = r._status_2b_connectors()
        assert "b1_google_oauth_vault_status" in status
        assert status["b1_google_oauth_vault_status"] == "LOCAL_FILE_ONLY"
        assert status["b1_vault_migration_needed"] is True

    def test_b1_blocker_in_connectors(self):
        r = _import_plan2()
        status = r._status_2b_connectors()
        blockers = " ".join(status.get("blockers", []))
        assert "B1" in blockers
        assert "vault" in blockers.lower() or "migration" in blockers.lower()


# ===========================================================================
# B4 — Notion NOT_CONFIGURED
# ===========================================================================

class TestB4NotionNotConfigured:
    """B4: Notion is NOT_CONFIGURED when no token set; recognized when env var set."""

    def _clean_env(self):
        return {k: v for k, v in os.environ.items()
                if k not in ("NOTION_API_TOKEN", "NOTION_TOKEN", "NOTION_INTEGRATION_TOKEN")}

    def test_notion_absent_when_no_token(self):
        r = _import_plan2()
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch.object(Path, "exists", return_value=False):
                assert r._notion_present() is False

    def test_notion_present_canonical_env(self):
        r = _import_plan2()
        env = {**self._clean_env(), "NOTION_API_TOKEN": "secret_token_xyz"}
        with patch.dict(os.environ, env, clear=True):
            assert r._notion_present() is True

    def test_notion_present_legacy_env(self):
        r = _import_plan2()
        env = {**self._clean_env(), "NOTION_TOKEN": "secret_notion_tok"}
        with patch.dict(os.environ, env, clear=True):
            assert r._notion_present() is True

    def test_notion_connector_token_present_via_env(self):
        r = _import_plan2()
        notion_rec = next(
            (c for c in r._CONNECTOR_REGISTRY if c["connector_id"] == "notion"), None
        )
        assert notion_rec is not None
        env = {**self._clean_env(), "NOTION_INTEGRATION_TOKEN": "secret_int_token"}
        with patch.dict(os.environ, env, clear=True):
            assert r._connector_token_present(notion_rec) is True

    def test_notion_connector_token_absent_with_no_env_no_file(self):
        r = _import_plan2()
        notion_rec = next(
            (c for c in r._CONNECTOR_REGISTRY if c["connector_id"] == "notion"), None
        )
        assert notion_rec is not None
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch.object(Path, "exists", return_value=False):
                assert r._connector_token_present(notion_rec) is False

    def test_b4_blocker_present_when_not_configured(self):
        r = _import_plan2()
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch.object(Path, "exists", return_value=False):
                status = r._status_2b_connectors()
                blockers = " ".join(status.get("blockers", []))
                assert "B4" in blockers
                assert "notion" in blockers.lower()

    def test_b4_notion_configured_false_in_status_when_absent(self):
        r = _import_plan2()
        with patch.dict(os.environ, self._clean_env(), clear=True):
            with patch.object(Path, "exists", return_value=False):
                status = r._status_2b_connectors()
                assert status["b4_notion_configured"] is False

    def test_public_endpoint_no_notion_token_values(self):
        r = _import_plan2()
        status = r._status_2b_connectors()
        result_str = json.dumps(status)
        # Must not leak notion token values
        assert "secret" not in result_str.lower()
        assert "ntn_" not in result_str  # Notion token format
        assert "Bearer" not in result_str


# ===========================================================================
# B7 — Life-OS cloud sync honest layer tracking
# ===========================================================================

class TestB7LifeOSCloudSyncStatus:
    """B7: Life-OS cloud sync layers are honestly reported."""

    def test_sync_executed_always_requires_deployment(self):
        from openjarvis.jarvis_os.life_os_cloud_sync_status import get_life_os_cloud_sync_status, LAYER_REQUIRES_DEPLOYMENT
        result = get_life_os_cloud_sync_status()
        assert result.sync_executed == LAYER_REQUIRES_DEPLOYMENT

    def test_worker_access_always_requires_deployment(self):
        from openjarvis.jarvis_os.life_os_cloud_sync_status import get_life_os_cloud_sync_status, LAYER_REQUIRES_DEPLOYMENT
        result = get_life_os_cloud_sync_status()
        assert result.worker_access == LAYER_REQUIRES_DEPLOYMENT

    def test_status_never_ready_without_deployment(self):
        from openjarvis.jarvis_os.life_os_cloud_sync_status import get_life_os_cloud_sync_status, STATUS_READY
        result = get_life_os_cloud_sync_status()
        assert result.status != STATUS_READY

    def test_to_dict_has_all_layers(self):
        from openjarvis.jarvis_os.life_os_cloud_sync_status import get_life_os_cloud_sync_status
        result = get_life_os_cloud_sync_status()
        d = result.to_dict()
        assert "local_store_type" in d
        assert "s3_configured" in d
        assert "sync_code_present" in d
        assert "sync_executed" in d
        assert "worker_access" in d
        assert "status" in d

    def test_no_secret_values_in_dict(self):
        from openjarvis.jarvis_os.life_os_cloud_sync_status import get_life_os_cloud_sync_status
        result = get_life_os_cloud_sync_status()
        result_str = json.dumps(result.to_dict())
        assert "AKIA" not in result_str  # AWS key prefix
        assert "ya29." not in result_str
        assert ".env" not in result_str

    def test_life_os_probe_in_plan2_routes(self):
        r = _import_plan2()
        probe = r._life_os_cloud_sync_probe()
        assert "sync_executed" in probe
        assert probe["sync_executed"] == "requires_deployment"
        assert "worker_access" in probe
        assert probe["worker_access"] == "requires_deployment"

    def test_status_2e_has_b7_layers(self):
        r = _import_plan2()
        status = r._status_2e_life_os()
        assert "b7_cloud_sync_status" in status
        assert "b7_cloud_sync_layers" in status
        layers = status["b7_cloud_sync_layers"]
        assert layers["sync_executed"] == "requires_deployment"
        assert layers["worker_access"] == "requires_deployment"

    def test_status_2e_b7_blocker_present(self):
        r = _import_plan2()
        status = r._status_2e_life_os()
        blockers = " ".join(status.get("blockers", []))
        assert "B7" in blockers


# ===========================================================================
# B7 — SQLite store (life_os_store.py)
# ===========================================================================

class TestB7SQLiteStore:
    """B7: SQLitePersonalTaskStore persists tasks correctly."""

    def test_sqlite_store_creates_db(self):
        from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "test_tasks.db"
            store = SQLitePersonalTaskStore(db_path=db)
            assert db.exists()

    def test_add_and_get_task(self):
        from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
        from openjarvis.jarvis_os.personal_os import PersonalTask
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLitePersonalTaskStore(db_path=Path(tmpdir) / "test.db")
            task = PersonalTask.create("Test task", priority="medium")
            store.add(task)
            retrieved = store.get(task.task_id)
            assert retrieved is not None
            assert retrieved.title == "Test task"

    def test_tasks_survive_store_reload(self):
        from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
        from openjarvis.jarvis_os.personal_os import PersonalTask
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Path(tmpdir) / "test.db"
            store1 = SQLitePersonalTaskStore(db_path=db)
            task = PersonalTask.create("Persistent task")
            store1.add(task)
            # Reload from same DB file
            store2 = SQLitePersonalTaskStore(db_path=db)
            assert store2.get(task.task_id) is not None

    def test_update_status(self):
        from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
        from openjarvis.jarvis_os.personal_os import PersonalTask
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLitePersonalTaskStore(db_path=Path(tmpdir) / "test.db")
            task = PersonalTask.create("Status test")
            store.add(task)
            assert store.update_status(task.task_id, "done") is True
            updated = store.get(task.task_id)
            assert updated.status.value == "done"

    def test_list_tasks(self):
        from openjarvis.jarvis_os.life_os_store import SQLitePersonalTaskStore
        from openjarvis.jarvis_os.personal_os import PersonalTask
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SQLitePersonalTaskStore(db_path=Path(tmpdir) / "test.db")
            for i in range(3):
                store.add(PersonalTask.create(f"Task {i}"))
            assert len(store.list_tasks()) == 3

    def test_get_store_type(self):
        from openjarvis.jarvis_os.life_os_store import get_store_type, STORE_TYPE_SQLITE
        assert get_store_type() == STORE_TYPE_SQLITE


# ===========================================================================
# Public endpoint safety — no secrets, no env var names, no paths
# ===========================================================================

class TestPublicEndpointSafetyB1B4B7:
    """Public endpoints must not expose sensitive fields from B1/B4/B7 status."""

    _SENSITIVE_PATTERNS = [
        "OMNIX_WORKBENCH_MEMORY_BUCKET",
        "OMNIX_WORKBENCH_ARTIFACT_BUCKET",
        "OMNIX_WORKBENCH_STORAGE_PROVIDER",
        "OMNIX_WORKBENCH_STATE_TABLE",
        "OPENJARVIS_API_KEY",
        "NOTION_API_TOKEN",
        "NOTION_TOKEN",
        "SLACK_BOT_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "JARVIS_TELEGRAM_BOT_TOKEN",
        "GITHUB_TOKEN",
        "~/.openjarvis",
        "/home/",
        "/Users/",
        "access_token",
        "refresh_token",
        "client_secret",
        "ya29.",
        "ntn_",
        "xoxb-",
        "ghp_",
    ]

    def test_life_os_public_no_sensitive(self):
        r = _import_plan2()
        import asyncio
        result = asyncio.run(r.get_life_os_parity_status())
        result_str = json.dumps(result).lower()
        for pattern in self._SENSITIVE_PATTERNS:
            assert pattern.lower() not in result_str, (
                f"Public /v1/mobile-parity/life-os leaks pattern: {pattern!r}"
            )

    def test_life_os_public_b7_sync_executed_is_requires_deployment(self):
        r = _import_plan2()
        import asyncio
        result = asyncio.run(r.get_life_os_parity_status())
        assert result["b7_sync_executed"] == "requires_deployment"
        assert result["b7_worker_access"] == "requires_deployment"

    def test_life_os_not_ready(self):
        r = _import_plan2()
        import asyncio
        result = asyncio.run(r.get_life_os_parity_status())
        assert result.get("macbook_off_status") != "READY"


# ===========================================================================
# Overall Plan 2 HOLD verdict
# ===========================================================================

class TestPlan2HoldWithBlockers:
    """Overall Plan 2 verdict must be HOLD while any B1-B8 blocker remains."""

    def test_sprint_verdict_is_hold(self):
        r = _import_plan2()
        import asyncio
        result = asyncio.run(r.get_mobile_parity_status())
        assert result["sprint_verdict"] == "PLAN_2_FULL_MOBILE_MACBOOK_OFF_PARITY_RUNTIME_HOLD"

    def test_macbook_off_ready_is_zero(self):
        r = _import_plan2()
        import asyncio
        result = asyncio.run(r.get_mobile_parity_status())
        assert result["summary"]["macbook_off_ready"] == 0

    def test_b7_sync_not_ready(self):
        from openjarvis.jarvis_os.life_os_cloud_sync_status import get_life_os_cloud_sync_status, STATUS_READY
        result = get_life_os_cloud_sync_status()
        assert result.status != STATUS_READY

    def test_b1_vault_not_configured(self):
        r = _import_plan2()
        result = r._google_oauth_local_status()
        assert result["cloud_vault_configured"] is False

    def test_b4_notion_not_ready(self):
        r = _import_plan2()
        # Without env vars or files, notion should not be configured
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in ("NOTION_API_TOKEN", "NOTION_TOKEN", "NOTION_INTEGRATION_TOKEN")}
        with patch.dict(os.environ, clean_env, clear=True):
            with patch.object(Path, "exists", return_value=False):
                assert r._notion_present() is False
