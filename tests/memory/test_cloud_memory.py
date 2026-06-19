"""Tests for cloud memory architecture — readiness, fallback, and status."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from openjarvis.memory.cloud_memory import (
    BackendReadiness,
    CloudMemoryBackendStatus,
    CloudMemoryGateway,
    CloudMemoryStatus,
    check_cloud_memory_status,
)


class TestLocalMemoryStatus:
    def test_local_always_daily_driver(self, tmp_path):
        db = tmp_path / "memory.db"
        status = check_cloud_memory_status(db_path=db)
        assert status.local_status == CloudMemoryBackendStatus.DAILY_DRIVER_ACCEPT

    def test_local_db_path_reported(self, tmp_path):
        db = tmp_path / "test.db"
        status = check_cloud_memory_status(db_path=db)
        assert str(db) in status.local_db_path

    def test_local_db_exists_false_when_missing(self, tmp_path):
        db = tmp_path / "nonexistent.db"
        status = check_cloud_memory_status(db_path=db)
        assert status.local_db_exists is False

    def test_local_db_exists_true_when_present(self, tmp_path):
        db = tmp_path / "memory.db"
        db.touch()
        status = check_cloud_memory_status(db_path=db)
        assert status.local_db_exists is True


class TestCloudBackendStatus:
    def test_s3_blocked_when_no_credentials(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "JARVIS_MEMORY_S3_BUCKET": "",
        }):
            status = check_cloud_memory_status(db_path=tmp_path / "m.db")
        s3 = next(b for b in status.cloud_backends if b.backend == "s3_aws")
        assert s3.status == CloudMemoryBackendStatus.BLOCKED_CREDENTIALS
        assert s3.available is False

    def test_s3_blocked_when_bucket_missing(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
            "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "JARVIS_MEMORY_S3_BUCKET": "",
        }):
            status = check_cloud_memory_status(db_path=tmp_path / "m.db")
        s3 = next(b for b in status.cloud_backends if b.backend == "s3_aws")
        assert s3.status == CloudMemoryBackendStatus.BLOCKED_CREDENTIALS
        assert s3.credential_present is True

    def test_supabase_blocked_when_no_credentials(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
        }):
            status = check_cloud_memory_status(db_path=tmp_path / "m.db")
        sb = next(b for b in status.cloud_backends if b.backend == "supabase")
        assert sb.status == CloudMemoryBackendStatus.BLOCKED_CREDENTIALS
        assert sb.available is False


class TestFallbackBehavior:
    def test_fallback_chain_local_when_no_cloud(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "JARVIS_MEMORY_S3_BUCKET": "",
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
        }):
            status = check_cloud_memory_status(db_path=tmp_path / "m.db")
        assert status.active_backend == "local_sqlite"
        assert status.sync_status == "local_only"
        assert "local_sqlite" in status.fallback_chain

    def test_summary_mentions_blocked_backends(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "JARVIS_MEMORY_S3_BUCKET": "",
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
        }):
            status = check_cloud_memory_status(db_path=tmp_path / "m.db")
        assert "s3_aws" in status.summary or "local_only" in status.summary

    def test_to_dict_has_all_fields(self, tmp_path):
        status = check_cloud_memory_status(db_path=tmp_path / "m.db")
        d = status.to_dict()
        assert "local_db_path" in d
        assert "cloud_backends" in d
        assert "active_backend" in d
        assert "fallback_chain" in d
        assert "sync_status" in d


class TestCloudMemoryGateway:
    def test_gateway_reports_cloud_unavailable_without_creds(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
            "JARVIS_MEMORY_S3_BUCKET": "",
            "SUPABASE_URL": "",
            "SUPABASE_SERVICE_ROLE_KEY": "",
        }):
            gw = CloudMemoryGateway(db_path=tmp_path / "m.db")
        assert gw.is_cloud_available() is False
        assert gw.get_active_backend() == "local_sqlite"

    def test_gateway_describe_blockers_no_secrets(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
        }):
            gw = CloudMemoryGateway(db_path=tmp_path / "m.db")
        blockers = gw.describe_blockers()
        assert isinstance(blockers, list)
        # No secrets should appear in blocker descriptions
        for b in blockers:
            assert "xoxb-" not in str(b)
            assert "sk-" not in str(b)
            assert "AKIA" not in str(b.get("notes", ""))

    def test_gateway_clearing_steps_present(self, tmp_path):
        with mock.patch.dict(os.environ, {
            "AWS_ACCESS_KEY_ID": "",
            "AWS_SECRET_ACCESS_KEY": "",
        }):
            gw = CloudMemoryGateway(db_path=tmp_path / "m.db")
        blockers = gw.describe_blockers()
        s3_blocker = next((b for b in blockers if b["backend"] == "s3_aws"), None)
        assert s3_blocker is not None
        assert len(s3_blocker["clearing_steps"]) > 0
