"""Tests for Durable Job Queue (US9 Phase 4)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from openjarvis.autonomy.job_queue import (
    JobState,
    cancel_job,
    claim_next,
    complete_job,
    enqueue,
    fail_job,
    get_job,
    list_jobs,
    queue_stats,
    recover_stale_running,
)


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test_queue.db"


class TestEnqueue:
    def test_enqueue_returns_job_id(self, tmp_db):
        r = enqueue("test_action", {"key": "val"}, db_path=tmp_db)
        assert r["ok"] is True
        assert r["duplicate"] is False
        assert "job_id" in r
        assert r["state"] == JobState.PENDING

    def test_idempotency_key_prevents_duplicate(self, tmp_db):
        r1 = enqueue("action1", {}, idempotency_key="idem-1", db_path=tmp_db)
        r2 = enqueue("action1", {}, idempotency_key="idem-1", db_path=tmp_db)
        assert r1["job_id"] == r2["job_id"]
        assert r2["duplicate"] is True

    def test_different_idempotency_keys_enqueue_separately(self, tmp_db):
        r1 = enqueue("action1", {}, idempotency_key="idem-a", db_path=tmp_db)
        r2 = enqueue("action1", {}, idempotency_key="idem-b", db_path=tmp_db)
        assert r1["job_id"] != r2["job_id"]


class TestClaim:
    def test_claim_returns_job(self, tmp_db):
        enqueue("claimable_action", {"x": 1}, db_path=tmp_db)
        job = claim_next(db_path=tmp_db)
        assert job is not None
        assert job.state == JobState.RUNNING
        assert job.action == "claimable_action"
        assert job.attempts == 1

    def test_claim_empty_queue_returns_none(self, tmp_db):
        job = claim_next(db_path=tmp_db)
        assert job is None

    def test_claim_moves_to_running(self, tmp_db):
        r = enqueue("action_to_run", {}, db_path=tmp_db)
        job_id = r["job_id"]
        claim_next(db_path=tmp_db)
        j = get_job(job_id, db_path=tmp_db)
        assert j.state == JobState.RUNNING


class TestComplete:
    def test_complete_marks_succeeded(self, tmp_db):
        r = enqueue("completable", {}, db_path=tmp_db)
        job_id = r["job_id"]
        claim_next(db_path=tmp_db)
        complete_job(job_id, result={"done": True}, db_path=tmp_db)
        j = get_job(job_id, db_path=tmp_db)
        assert j.state == JobState.SUCCEEDED
        assert j.result == {"done": True}


class TestFail:
    def test_fail_with_retries_reschedules(self, tmp_db):
        r = enqueue("failable", {}, max_attempts=3, db_path=tmp_db)
        job_id = r["job_id"]
        claim_next(db_path=tmp_db)
        result = fail_job(job_id, error="test error", db_path=tmp_db)
        assert result["ok"] is True
        assert result["next_state"] == JobState.PENDING  # retries remain

    def test_fail_no_retries_marks_failed(self, tmp_db):
        r = enqueue("no_retry", {}, max_attempts=1, db_path=tmp_db)
        job_id = r["job_id"]
        claim_next(db_path=tmp_db)
        result = fail_job(job_id, error="permanent", db_path=tmp_db)
        assert result["next_state"] == JobState.FAILED
        j = get_job(job_id, db_path=tmp_db)
        assert j.state == JobState.FAILED
        assert j.error == "permanent"


class TestCancel:
    def test_cancel_pending_job(self, tmp_db):
        r = enqueue("cancellable", {}, db_path=tmp_db)
        job_id = r["job_id"]
        cancel_job(job_id, db_path=tmp_db)
        j = get_job(job_id, db_path=tmp_db)
        assert j.state == JobState.CANCELLED

    def test_cancel_does_not_affect_running(self, tmp_db):
        r = enqueue("running_cancel", {}, db_path=tmp_db)
        job_id = r["job_id"]
        claim_next(db_path=tmp_db)
        cancel_job(job_id, db_path=tmp_db)
        j = get_job(job_id, db_path=tmp_db)
        # Cancel only works on pending — running stays running
        assert j.state == JobState.RUNNING


class TestRecovery:
    def test_recover_stale_running(self, tmp_db):
        r = enqueue("stale_job", {}, db_path=tmp_db)
        job_id = r["job_id"]
        claim_next(db_path=tmp_db)
        # Recover with 0 seconds (immediately stale)
        recovered = recover_stale_running(stale_after_seconds=0, db_path=tmp_db)
        assert recovered >= 1
        j = get_job(job_id, db_path=tmp_db)
        assert j.state == JobState.PENDING


class TestListAndStats:
    def test_list_jobs_by_state(self, tmp_db):
        enqueue("list_test_1", {}, db_path=tmp_db)
        enqueue("list_test_2", {}, db_path=tmp_db)
        jobs = list_jobs(state=JobState.PENDING, db_path=tmp_db)
        assert len(jobs) >= 2

    def test_queue_stats(self, tmp_db):
        enqueue("stats_test", {}, db_path=tmp_db)
        stats = queue_stats(db_path=tmp_db)
        assert "pending" in stats
        assert "running" in stats
        assert "succeeded" in stats
        assert "failed" in stats
        assert stats["total"] >= 1
