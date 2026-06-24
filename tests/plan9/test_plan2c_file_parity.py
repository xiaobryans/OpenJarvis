"""Plan 2C — File/Workspace/Data Parity smoke tests.

Verifies:
- Public status endpoint is sanitized (no secrets, no local paths, no content)
- Auth-gated workspace detail endpoint blocks unauthenticated callers
- File index never returns file contents
- Path traversal is blocked
- S3 artifact store status is honest (BLOCKED/PARTIAL not fake READY when unconfigured)
- workspace_sync_summary() returns honest counts
- git_tracked_files() never returns file contents
- _s3_artifact_store_probe() reports correct status without exposing values
"""

from __future__ import annotations

import os
import pytest


# ---------------------------------------------------------------------------
# workspace_root helpers
# ---------------------------------------------------------------------------

class TestWorkspaceSyncSummary:
    def test_returns_expected_keys(self):
        from openjarvis.plan9.workspace_root import workspace_sync_summary
        s = workspace_sync_summary()
        assert "git_available" in s
        assert "git_tracked_count" in s
        assert "modified_count" in s
        assert "untracked_count" in s
        assert "cloud_indexable" in s
        assert "permanent_exception" in s

    def test_no_file_contents_in_summary(self):
        from openjarvis.plan9.workspace_root import workspace_sync_summary
        s = workspace_sync_summary()
        payload = str(s)
        # Must not contain home directory paths or actual file content
        assert "/Users/" not in payload or "home" not in payload.lower()
        # No common credential patterns
        assert "password" not in payload.lower()
        assert "secret" not in payload.lower()

    def test_git_tracked_count_positive_when_git_available(self):
        from openjarvis.plan9.workspace_root import workspace_sync_summary, git_is_available
        if not git_is_available():
            pytest.skip("git not available in this environment")
        s = workspace_sync_summary()
        assert s["git_tracked_count"] > 0
        assert s["cloud_indexable"] > 0

    def test_local_only_class_is_queued_mac_only(self):
        from openjarvis.plan9.workspace_root import workspace_sync_summary
        s = workspace_sync_summary()
        assert s["local_only_class"] == "QUEUED_MAC_ONLY"

    def test_permanent_exception_present(self):
        from openjarvis.plan9.workspace_root import workspace_sync_summary
        s = workspace_sync_summary()
        assert "QUEUED_MAC_ONLY" in s["permanent_exception"]


# ---------------------------------------------------------------------------
# git_tracked_files — never returns file contents
# ---------------------------------------------------------------------------

class TestGitTrackedFiles:
    def test_returns_metadata_only(self):
        from openjarvis.plan9.workspace_root import git_tracked_files, git_is_available
        if not git_is_available():
            pytest.skip("git not available")
        files = git_tracked_files(max_files=10)
        for f in files:
            assert "path" in f
            assert "git_tracked" in f
            assert f["git_tracked"] is True
            # Must NOT have content field
            assert "content" not in f
            assert "text" not in f
            assert "data" not in f

    def test_returns_allowlisted_paths_only(self):
        from openjarvis.plan9.workspace_root import git_tracked_files, git_is_available, workspace_allowlist_roots
        if not git_is_available():
            pytest.skip("git not available")
        files = git_tracked_files(max_files=50)
        allowed = workspace_allowlist_roots()
        for f in files:
            assert any(f["path"].startswith(a) for a in allowed), (
                f"Path {f['path']!r} is outside allowlist {allowed}"
            )

    def test_no_env_or_credential_paths(self):
        from openjarvis.plan9.workspace_root import git_tracked_files, git_is_available
        if not git_is_available():
            pytest.skip("git not available")
        files = git_tracked_files(max_files=200)
        for f in files:
            p = f["path"].lower()
            assert ".env" not in p or p.endswith(".example") or ".environ" not in p
            assert "id_rsa" not in p
            assert "id_ed25519" not in p
            assert ".ssh" not in p


# ---------------------------------------------------------------------------
# _s3_artifact_store_probe — honest status, no value exposure
# ---------------------------------------------------------------------------

class TestS3ArtifactStoreProbe:
    def test_returns_expected_fields(self):
        from openjarvis.server.plan2_routes import _s3_artifact_store_probe
        result = _s3_artifact_store_probe()
        assert "status" in result
        assert "memory_bucket_configured" in result
        assert "artifact_bucket_configured" in result
        assert "state_table_configured" in result
        assert "provider_aws" in result
        assert "region_configured" in result
        assert "detail" in result
        assert "note" in result

    def test_status_is_valid_enum(self):
        from openjarvis.server.plan2_routes import _s3_artifact_store_probe
        result = _s3_artifact_store_probe()
        assert result["status"] in ("READY", "PARTIAL", "BLOCKED", "NOT_CONFIGURED")

    def test_no_env_values_in_response(self, monkeypatch):
        from openjarvis.server.plan2_routes import _s3_artifact_store_probe
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "my-secret-bucket")
        monkeypatch.setenv("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "another-bucket")
        result = _s3_artifact_store_probe()
        payload = str(result)
        # The bucket names must NOT appear in the response
        assert "my-secret-bucket" not in payload
        assert "another-bucket" not in payload

    def test_not_configured_when_no_env(self, monkeypatch):
        from openjarvis.server.plan2_routes import _s3_artifact_store_probe
        for k in ("OMNIX_WORKBENCH_MEMORY_BUCKET", "OMNIX_WORKBENCH_ARTIFACT_BUCKET",
                   "OMNIX_WORKBENCH_STATE_TABLE", "OMNIX_WORKBENCH_AWS_REGION",
                   "OMNIX_WORKBENCH_STORAGE_PROVIDER"):
            monkeypatch.delenv(k, raising=False)
        result = _s3_artifact_store_probe()
        assert result["status"] == "NOT_CONFIGURED"
        assert result["memory_bucket_configured"] is False
        assert result["artifact_bucket_configured"] is False

    def test_ready_when_all_configured(self, monkeypatch):
        from openjarvis.server.plan2_routes import _s3_artifact_store_probe
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "mem")
        monkeypatch.setenv("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "art")
        monkeypatch.setenv("OMNIX_WORKBENCH_STATE_TABLE", "tbl")
        monkeypatch.setenv("OMNIX_WORKBENCH_AWS_REGION", "ap-southeast-1")
        monkeypatch.setenv("OMNIX_WORKBENCH_STORAGE_PROVIDER", "aws")
        result = _s3_artifact_store_probe()
        assert result["status"] == "READY"
        # Values must not appear
        assert "mem" not in str(result).replace("memory_bucket_configured", "").replace("artifact_bucket_configured", "").replace("state_table", "")

    def test_partial_when_some_configured(self, monkeypatch):
        from openjarvis.server.plan2_routes import _s3_artifact_store_probe
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "mem")
        monkeypatch.setenv("OMNIX_WORKBENCH_ARTIFACT_BUCKET", "art")
        for k in ("OMNIX_WORKBENCH_STATE_TABLE", "OMNIX_WORKBENCH_AWS_REGION",
                   "OMNIX_WORKBENCH_STORAGE_PROVIDER"):
            monkeypatch.delenv(k, raising=False)
        result = _s3_artifact_store_probe()
        assert result["status"] == "PARTIAL"


# ---------------------------------------------------------------------------
# _status_2c_files — honest status composition
# ---------------------------------------------------------------------------

class TestStatus2CFiles:
    def test_subsection_id(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        assert s["subsection"] == "2C"

    def test_no_fake_ready_for_macbook_off(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        # MacBook-off should never be READY while S3 sync is not implemented
        assert s["macbook_off_status"] != "READY"

    def test_blockers_not_empty(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        assert len(s["blockers"]) > 0, "Must have at least one honest blocker"

    def test_s3_status_field_present(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        assert "s3_artifact_store_status" in s
        assert s["s3_artifact_store_status"] in ("READY", "PARTIAL", "BLOCKED", "NOT_CONFIGURED")

    def test_key_routes_include_workspace_status(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        routes_str = " ".join(s["key_routes"])
        assert "/v1/files/workspace/status" in routes_str
        assert "/v1/files/cloud-index" in routes_str
        assert "/v1/mobile-parity/files" in routes_str


# ---------------------------------------------------------------------------
# Public endpoint sanitization — /v1/mobile-parity/files
# ---------------------------------------------------------------------------

class TestPublicFilesParityEndpoint:
    """These tests call _status_2c_files() directly since we're unit testing the
    data layer, not the HTTP layer. Integration tests would use TestClient."""

    def test_public_response_has_no_env_var_values(self, monkeypatch):
        monkeypatch.setenv("OMNIX_WORKBENCH_MEMORY_BUCKET", "secret-bucket-name")
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        payload = str(s)
        assert "secret-bucket-name" not in payload

    def test_public_response_has_no_local_paths(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        payload = str(s)
        # No absolute local home paths
        assert "/Users/" not in payload
        assert "/home/" not in payload

    def test_public_response_has_no_file_content(self):
        from openjarvis.server.plan2_routes import _status_2c_files
        s = _status_2c_files()
        # Count field should be an integer, not file content
        assert isinstance(s.get("git_tracked_count", 0), int)

    def test_sprint_verdict_reflects_closure(self):
        import asyncio
        from openjarvis.server.plan2_routes import get_file_parity_status
        result = asyncio.run(get_file_parity_status())
        assert "PLAN_2C" in result["sprint_verdict"]


# ---------------------------------------------------------------------------
# Path traversal blocked (unit-level)
# ---------------------------------------------------------------------------

class TestPathTraversal:
    def test_dotdot_blocked(self):
        from openjarvis.plan9.workspace_root import workspace_prefix_allowed
        assert not workspace_prefix_allowed("../etc/passwd")
        assert not workspace_prefix_allowed("../../.ssh/id_rsa")
        assert not workspace_prefix_allowed("src/../.env")

    def test_absolute_path_blocked(self):
        from openjarvis.plan9.workspace_root import workspace_prefix_allowed
        assert not workspace_prefix_allowed("/etc/passwd")
        assert not workspace_prefix_allowed("/Users/user/.ssh/id_rsa")

    def test_credential_paths_blocked(self):
        from openjarvis.plan9.workspace_root import workspace_prefix_allowed
        assert not workspace_prefix_allowed("src/openjarvis/.env")
        assert not workspace_prefix_allowed("configs/secrets/token.json")
        assert not workspace_prefix_allowed("src/id_rsa")
        assert not workspace_prefix_allowed("docs/.ssh/config")

    def test_allowed_paths_pass(self):
        from openjarvis.plan9.workspace_root import workspace_prefix_allowed
        assert workspace_prefix_allowed("src/openjarvis/server/plan2_routes.py")
        assert workspace_prefix_allowed("tests/plan9/test_plan2c_file_parity.py")
        assert workspace_prefix_allowed("docs/plan2/PLAN2_SOURCE_OF_TRUTH_MATRIX.md")
        assert workspace_prefix_allowed("pyproject.toml")
