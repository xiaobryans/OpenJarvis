"""Sprint 2B — Memory OS Blocker Closure Test Suite.

Tests for:
1. Semantic/vector search (OpenAI embeddings) — active when OPENAI_API_KEY present,
   honest TF-IDF fallback when not.
2. Cloud sync (OMNIX S3) — push/pull/merge logic, conflict resolution.
3. Cloud audit replication — push_audit to S3.
4. AI-assisted distillation (OpenRouter) — active when OPENROUTER_API_KEY present,
   rule-based fallback when not.
5. Status honesty — planned_not_complete reflects Sprint 2B completions.
6. Regression — Sprint 1+2 tests still pass.

Tests that require live network calls (S3, OpenAI, OpenRouter) are either
mocked or guarded by checking config presence before asserting.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from openjarvis.memory.retrieval import (
    MemoryRetriever,
    RetrievalResult,
    SemanticSearchStatus,
    TfIdfRanker,
    _get_openai_embedding,
    _cosine_similarity,
)
from openjarvis.memory.store import JarvisMemory, MemoryEntry
from openjarvis.memory.distillation import (
    AutoDistillEngine,
    AIDistillEngine,
    AIDistillationResult,
    DISTILLABLE_KINDS,
    _call_openrouter_distill,
    _detect_kind_from_text,
    _openrouter_key_available,
)
from openjarvis.memory.cloud_sync import (
    JarvisMemoryS3Sync,
    CloudSyncResult,
    CloudSyncStatus,
    _merge_entries,
    _merge_audit_records,
    _encode_jsonl,
    _decode_jsonl,
)
from openjarvis.memory.status import MemoryOSStatus, get_memory_os_status
from openjarvis.memory.distilled import DistilledMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db() -> tuple[Path, JarvisMemory]:
    tmp = tempfile.mktemp(suffix=".db")
    return Path(tmp), JarvisMemory(db_path=Path(tmp))


def _write(mem: JarvisMemory, content: str, **kw) -> MemoryEntry:
    return mem.write(namespace=kw.pop("namespace", "test"), content=content, **kw)


# ============================================================================
# 1. SemanticSearchStatus — honest reporting
# ============================================================================


class TestSemanticSearchStatusHonesty(unittest.TestCase):

    def test_to_dict_has_required_keys(self):
        d = SemanticSearchStatus.to_dict()
        assert "active_ranker" in d
        assert "vector_search" in d
        assert "vector_reason" in d
        assert "openai_key_present" in d

    def test_blocked_when_no_openai_key(self):
        with patch.dict(os.environ, {}, clear=False):
            # Remove key if present
            orig = os.environ.pop("OPENAI_API_KEY", None)
            try:
                d = SemanticSearchStatus.to_dict()
                assert d["openai_key_present"] is False
                assert d["active_ranker"] == SemanticSearchStatus.ACTIVE_RANKER_TFIDF
                assert "BLOCKED" in d["vector_search"]
            finally:
                if orig:
                    os.environ["OPENAI_API_KEY"] = orig

    def test_active_when_openai_key_present(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-dummy-key"}):
            d = SemanticSearchStatus.to_dict()
            assert d["openai_key_present"] is True
            assert d["active_ranker"] == SemanticSearchStatus.ACTIVE_RANKER_OPENAI
            assert "ACTIVE" in d["vector_search"]
            assert "BLOCKED" not in d["vector_search"]

    def test_ranker_changes_with_key(self):
        with patch.dict(os.environ, {}, clear=False):
            orig = os.environ.pop("OPENAI_API_KEY", None)
            try:
                no_key = SemanticSearchStatus.active_ranker()
                os.environ["OPENAI_API_KEY"] = "sk-test-dummy"
                with_key = SemanticSearchStatus.active_ranker()
                assert no_key == SemanticSearchStatus.ACTIVE_RANKER_TFIDF
                assert with_key == SemanticSearchStatus.ACTIVE_RANKER_OPENAI
            finally:
                if orig:
                    os.environ["OPENAI_API_KEY"] = orig
                else:
                    os.environ.pop("OPENAI_API_KEY", None)


# ============================================================================
# 2. Semantic/vector search integration — MemoryRetriever
# ============================================================================


class TestSemanticSearchIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp, self.mem = _make_db()

    def test_retriever_falls_back_to_tfidf_without_key(self):
        _write(self.mem, "Python async patterns are important", namespace="global")
        retriever = MemoryRetriever(memory=self.mem)
        with patch.dict(os.environ, {}, clear=False):
            orig = os.environ.pop("OPENAI_API_KEY", None)
            try:
                results = retriever.retrieve("Python async", max_results=5)
                if results:
                    assert results[0].ranker_used == SemanticSearchStatus.ACTIVE_RANKER_TFIDF
                    assert results[0].semantic_score == 0.0
            finally:
                if orig:
                    os.environ["OPENAI_API_KEY"] = orig

    def test_retriever_uses_semantic_when_key_present_and_embedding_succeeds(self):
        """When key present and mock embedding succeeds, ranker should be openai."""
        _write(self.mem, "use async patterns everywhere", namespace="global")
        retriever = MemoryRetriever(memory=self.mem)

        # Mock the embedding calls to return fake vectors
        fake_embedding = [0.1] * 1536
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-fake"}):
            with patch(
                "openjarvis.memory.retrieval._get_openai_embedding",
                return_value=fake_embedding,
            ):
                with patch(
                    "openjarvis.memory.retrieval._get_openai_embeddings_batch",
                    return_value=[fake_embedding],
                ):
                    results = retriever.retrieve("async patterns")
                    if results:
                        assert results[0].ranker_used == SemanticSearchStatus.ACTIVE_RANKER_OPENAI
                        assert results[0].semantic_score > 0

    def test_retriever_falls_back_to_tfidf_when_embedding_fails(self):
        """When key present but embedding call fails, should fall back to TF-IDF."""
        _write(self.mem, "Python patterns for AI agents", namespace="global")
        retriever = MemoryRetriever(memory=self.mem)

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-fake"}):
            with patch(
                "openjarvis.memory.retrieval._get_openai_embedding",
                return_value=None,
            ):
                results = retriever.retrieve("Python patterns")
                if results:
                    # Falls back to TF-IDF when query embedding fails
                    assert results[0].ranker_used == SemanticSearchStatus.ACTIVE_RANKER_TFIDF

    def test_result_has_ranker_used_field(self):
        _write(self.mem, "Always test your code thoroughly", namespace="global")
        retriever = MemoryRetriever(memory=self.mem)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            try:
                results = retriever.retrieve("test code")
                if results:
                    assert "ranker_used" in results[0].to_dict()
                    assert "semantic_score" in results[0].to_dict()
            finally:
                pass


# ============================================================================
# 3. TF-IDF still works — regression (Sprint 2 feature preserved)
# ============================================================================


class TestTfIdfRegressionSprint2B(unittest.TestCase):

    def test_tfidf_scores_are_non_negative(self):
        _, mem = _make_db()
        entries = [
            _write(mem, "decision to use Python for backend", kind="decision"),
            _write(mem, "preference for async frameworks", kind="preference"),
            _write(mem, "learned that tests prevent bugs", kind="lesson"),
        ]
        scored = TfIdfRanker.score("Python backend", entries)
        assert len(scored) == 3
        for entry, score in scored:
            assert score >= 0.0

    def test_tfidf_top_result_matches_query(self):
        _, mem = _make_db()
        entries = [
            _write(mem, "Python is great for data science", kind="decision"),
            _write(mem, "use Docker for deployment", kind="decision"),
            _write(mem, "Python backend performance tuning", kind="decision"),
        ]
        scored = TfIdfRanker.score("Python", entries)
        # Both Python entries should score higher than Docker
        top_2_contents = [e.content for e, _ in scored[:2]]
        assert any("Python" in c for c in top_2_contents)

    def test_tfidf_fallback_still_returns_results_without_openai_key(self):
        _, mem = _make_db()
        _write(mem, "decision about database schema", kind="decision")
        retriever = MemoryRetriever(memory=mem)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OPENAI_API_KEY", None)
            try:
                results = retriever.retrieve("database")
                assert len(results) > 0
            finally:
                pass


# ============================================================================
# 4. Cosine similarity — unit tests
# ============================================================================


class TestCosineSimilarity(unittest.TestCase):

    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.5]
        sim = _cosine_similarity(v, v)
        assert abs(sim - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        sim = _cosine_similarity(a, b)
        assert abs(sim) < 1e-6

    def test_zero_vector(self):
        a = [0.0, 0.0]
        b = [1.0, 2.0]
        sim = _cosine_similarity(a, b)
        assert sim == 0.0


# ============================================================================
# 5. Cloud sync — merge logic (no network required)
# ============================================================================


class TestCloudSyncMergeLogic(unittest.TestCase):

    def _make_entry(self, entry_id: str, ts: float, content: str = "test") -> Dict[str, Any]:
        return {"entry_id": entry_id, "created_at": ts, "content": content}

    def test_merge_entries_deduplicates_by_id(self):
        local = [self._make_entry("a1", 100.0, "local content")]
        remote = [self._make_entry("a1", 90.0, "remote content")]
        merged = _merge_entries(local, remote)
        assert len(merged) == 1
        # Local wins when local is newer (100 > 90)
        assert merged[0]["content"] == "local content"

    def test_merge_entries_remote_wins_when_newer(self):
        local = [self._make_entry("a1", 90.0, "old local")]
        remote = [self._make_entry("a1", 100.0, "newer remote")]
        merged = _merge_entries(local, remote)
        assert len(merged) == 1
        assert merged[0]["content"] == "newer remote"

    def test_merge_entries_local_wins_on_tie(self):
        local = [self._make_entry("a1", 100.0, "local tie")]
        remote = [self._make_entry("a1", 100.0, "remote tie")]
        merged = _merge_entries(local, remote)
        assert len(merged) == 1
        assert merged[0]["content"] == "local tie"

    def test_merge_entries_keeps_unique_from_both(self):
        local = [self._make_entry("a1", 100.0, "from local")]
        remote = [self._make_entry("a2", 100.0, "from remote")]
        merged = _merge_entries(local, remote)
        assert len(merged) == 2
        ids = {e["entry_id"] for e in merged}
        assert ids == {"a1", "a2"}

    def test_merge_entries_empty_local(self):
        remote = [self._make_entry("x1", 100.0, "remote only")]
        merged = _merge_entries([], remote)
        assert len(merged) == 1
        assert merged[0]["entry_id"] == "x1"

    def test_merge_entries_empty_remote(self):
        local = [self._make_entry("x1", 100.0, "local only")]
        merged = _merge_entries(local, [])
        assert len(merged) == 1

    def test_merge_audit_records_deduplicates_by_audit_id(self):
        r1 = {"audit_id": "aa1", "timestamp": 100.0, "action": "forget"}
        r2 = {"audit_id": "aa1", "timestamp": 100.0, "action": "forget"}  # dup
        r3 = {"audit_id": "aa2", "timestamp": 200.0, "action": "bulk_forget"}
        merged = _merge_audit_records([r1, r3], [r2])
        assert len(merged) == 2
        assert {r["audit_id"] for r in merged} == {"aa1", "aa2"}

    def test_merge_audit_records_sorted_by_timestamp(self):
        r1 = {"audit_id": "aa1", "timestamp": 200.0, "action": "a"}
        r2 = {"audit_id": "aa2", "timestamp": 100.0, "action": "b"}
        merged = _merge_audit_records([r1], [r2])
        assert merged[0]["timestamp"] <= merged[1]["timestamp"]

    def test_merge_audit_records_no_duplicates_same_side(self):
        r1 = {"audit_id": "aa1", "timestamp": 100.0, "action": "a"}
        merged = _merge_audit_records([r1, r1], [])
        assert len(merged) == 1


# ============================================================================
# 6. JSONL encode/decode round trip
# ============================================================================


class TestJsonlRoundTrip(unittest.TestCase):

    def test_encode_decode_roundtrip(self):
        records = [
            {"id": "1", "content": "hello", "score": 0.95},
            {"id": "2", "content": "world", "score": 0.7},
        ]
        encoded = _encode_jsonl(records)
        decoded = _decode_jsonl(encoded)
        assert len(decoded) == 2
        assert decoded[0]["id"] == "1"
        assert decoded[1]["score"] == 0.7

    def test_decode_skips_invalid_lines(self):
        raw = b'{"id":"1"}\nNOT_JSON\n{"id":"2"}'
        decoded = _decode_jsonl(raw)
        assert len(decoded) == 2
        assert decoded[0]["id"] == "1"
        assert decoded[1]["id"] == "2"

    def test_encode_empty(self):
        encoded = _encode_jsonl([])
        assert encoded == b""

    def test_decode_empty(self):
        decoded = _decode_jsonl(b"")
        assert decoded == []


# ============================================================================
# 7. CloudSyncStatus — structure and fields
# ============================================================================


class TestCloudSyncStatus(unittest.TestCase):

    def test_status_to_dict_has_required_keys(self):
        status = CloudSyncStatus(
            available=True,
            bucket="test-bucket",
            region="ap-southeast-1",
            profile_configured=True,
            can_read=True,
            can_write=True,
        )
        d = status.to_dict()
        assert "available" in d
        assert "bucket" in d
        assert "region" in d
        assert "can_read" in d
        assert "can_write" in d
        assert "profile_configured" in d

    def test_status_bucket_truncated_in_dict(self):
        status = CloudSyncStatus(
            available=True,
            bucket="my-secret-bucket-name-12345",
            region="us-east-1",
            profile_configured=True,
            can_read=True,
            can_write=True,
        )
        d = status.to_dict()
        # Bucket should be truncated (not full name)
        assert len(d["bucket"]) <= 12


# ============================================================================
# 8. JarvisMemoryS3Sync.get_status() without network
# ============================================================================


class TestS3SyncGetStatus(unittest.TestCase):

    def test_get_status_returns_unavailable_when_no_bucket_configured(self):
        with patch.dict(os.environ, {"OMNIX_WORKBENCH_MEMORY_BUCKET": ""}, clear=False):
            sync = JarvisMemoryS3Sync()
            status = sync.get_status()
            assert status.available is False
            assert "OMNIX_WORKBENCH_MEMORY_BUCKET" in status.last_error

    def test_get_status_returns_available_when_s3_reachable(self):
        """Mock boto3 list_objects to simulate reachable bucket."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {"Contents": []}
        with patch.dict(os.environ, {
            "OMNIX_WORKBENCH_MEMORY_BUCKET": "test-bucket",
            "OMNIX_WORKBENCH_AWS_REGION": "ap-southeast-1",
        }, clear=False):
            with patch("boto3.Session") as mock_session_cls:
                mock_session = MagicMock()
                mock_session.client.return_value = mock_s3
                mock_session_cls.return_value = mock_session
                sync = JarvisMemoryS3Sync()
                status = sync.get_status()
                assert status.available is True
                assert status.can_read is True

    def test_get_status_returns_unavailable_on_boto3_error(self):
        """Mock boto3 to raise an exception."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.side_effect = Exception("AccessDenied")
        with patch.dict(os.environ, {
            "OMNIX_WORKBENCH_MEMORY_BUCKET": "test-bucket",
            "OMNIX_WORKBENCH_AWS_REGION": "ap-southeast-1",
        }, clear=False):
            with patch("boto3.Session") as mock_session_cls:
                mock_session = MagicMock()
                mock_session.client.return_value = mock_s3
                mock_session_cls.return_value = mock_session
                sync = JarvisMemoryS3Sync()
                status = sync.get_status()
                assert status.available is False
                assert "AccessDenied" in (status.last_error or "")


# ============================================================================
# 9. JarvisMemoryS3Sync push/pull — mocked S3
# ============================================================================


class TestS3SyncPushPull(unittest.TestCase):

    def _make_mock_s3(self, existing_content: bytes = b"") -> MagicMock:
        mock_s3 = MagicMock()
        # get_object returns empty by default (simulating first push)
        if existing_content:
            mock_s3.get_object.return_value = {
                "Body": MagicMock(read=MagicMock(return_value=existing_content))
            }
        else:
            mock_s3.get_object.side_effect = Exception("NoSuchKey")
        mock_s3.put_object.return_value = {}
        mock_s3.list_objects_v2.return_value = {}
        return mock_s3

    def _patch_s3(self, mock_s3: MagicMock, bucket: str = "test-bucket"):
        """Context manager that patches _make_s3_client."""
        from unittest.mock import patch as _patch
        return _patch(
            "openjarvis.memory.cloud_sync._make_s3_client",
            return_value=(mock_s3, bucket),
        )

    def test_push_raw_first_push_succeeds(self):
        mock_s3 = self._make_mock_s3()
        entries = [{"entry_id": "e1", "created_at": 100.0, "content": "test"}]
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            result = sync.push_raw(entries)
        assert result.success is True
        assert result.entries_transferred == 1
        assert mock_s3.put_object.called

    def test_push_raw_merges_with_existing(self):
        existing = [{"entry_id": "e_old", "created_at": 50.0, "content": "old"}]
        existing_bytes = _encode_jsonl(existing)
        mock_s3 = self._make_mock_s3(existing_bytes)
        new_entries = [{"entry_id": "e_new", "created_at": 100.0, "content": "new"}]
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            result = sync.push_raw(new_entries)
        assert result.success is True
        assert result.entries_transferred == 2  # old + new
        assert result.entries_merged == 1  # 1 new

    def test_push_raw_last_write_wins_on_conflict(self):
        existing = [{"entry_id": "e1", "created_at": 50.0, "content": "old"}]
        existing_bytes = _encode_jsonl(existing)
        mock_s3 = self._make_mock_s3(existing_bytes)
        # Local entry has same ID but newer timestamp
        new_entries = [{"entry_id": "e1", "created_at": 100.0, "content": "newer local"}]
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            result = sync.push_raw(new_entries)
        assert result.success is True
        # Verify put_object was called with updated content
        call_kwargs = mock_s3.put_object.call_args[1]
        body = call_kwargs["Body"]
        decoded = _decode_jsonl(body)
        assert len(decoded) == 1
        assert decoded[0]["content"] == "newer local"

    def test_push_distilled_succeeds(self):
        mock_s3 = self._make_mock_s3()
        entries = [{"entry_id": "d1", "created_at": 100.0, "content": "distilled"}]
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            result = sync.push_distilled(entries)
        assert result.success is True
        assert result.s3_key.endswith("distilled_entries.jsonl")

    def test_push_audit_append_only_merge(self):
        existing = [{"audit_id": "a1", "timestamp": 100.0, "action": "forget"}]
        existing_bytes = _encode_jsonl(existing)
        mock_s3 = self._make_mock_s3(existing_bytes)
        new_records = [{"audit_id": "a2", "timestamp": 200.0, "action": "bulk_forget"}]
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            result = sync.push_audit(new_records)
        assert result.success is True
        assert result.entries_transferred == 2  # existing + new
        assert result.entries_merged == 1

    def test_push_audit_no_duplicate_audit_ids(self):
        existing = [{"audit_id": "a1", "timestamp": 100.0, "action": "forget"}]
        existing_bytes = _encode_jsonl(existing)
        mock_s3 = self._make_mock_s3(existing_bytes)
        # Push same record again
        same_records = [{"audit_id": "a1", "timestamp": 100.0, "action": "forget"}]
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            result = sync.push_audit(same_records)
        assert result.success is True
        assert result.entries_transferred == 1  # no duplicate

    def test_push_fails_gracefully_on_s3_error(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("NoSuchKey")
        mock_s3.put_object.side_effect = Exception("AccessDenied")
        with patch(
            "openjarvis.memory.cloud_sync._make_s3_client",
            return_value=(mock_s3, "test-bucket"),
        ):
            sync = JarvisMemoryS3Sync()
            result = sync.push_raw([{"entry_id": "e1", "content": "test"}])
        assert result.success is False
        assert result.error is not None

    def test_pull_raw_returns_entries(self):
        records = [{"entry_id": "e1", "content": "retrieved"}]
        mock_s3 = self._make_mock_s3(_encode_jsonl(records))
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            success, entries, err = sync.pull_raw()
        assert success is True
        assert len(entries) == 1
        assert entries[0]["entry_id"] == "e1"

    def test_pull_raw_fails_gracefully(self):
        mock_s3 = MagicMock()
        mock_s3.get_object.side_effect = Exception("key not found")
        with patch(
            "openjarvis.memory.cloud_sync._make_s3_client",
            return_value=(mock_s3, "test-bucket"),
        ):
            sync = JarvisMemoryS3Sync()
            success, entries, err = sync.pull_raw()
        assert success is False
        assert entries == []

    def test_full_sync_calls_all_three_operations(self):
        mock_s3 = self._make_mock_s3()
        with self._patch_s3(mock_s3):
            sync = JarvisMemoryS3Sync()
            results = sync.full_sync(
                raw_entries=[{"entry_id": "r1", "content": "raw"}],
                distilled_entries=[{"entry_id": "d1", "content": "dist"}],
                audit_records=[{"audit_id": "a1", "timestamp": 1.0}],
            )
        assert "raw" in results
        assert "distilled" in results
        assert "audit" in results
        assert all(r.success for r in results.values())


# ============================================================================
# 10. Cloud sync result fields
# ============================================================================


class TestCloudSyncResultFields(unittest.TestCase):

    def test_to_dict_has_required_keys(self):
        r = CloudSyncResult(
            operation="push_raw",
            success=True,
            entries_transferred=5,
            entries_merged=2,
            entries_skipped=3,
            bucket="my-bucket",
            s3_key="jarvis_memory/raw_entries.jsonl",
            elapsed_ms=123.4,
            detail="ok",
        )
        d = r.to_dict()
        for key in ("operation", "success", "entries_transferred", "entries_merged",
                    "entries_skipped", "bucket", "s3_key", "elapsed_ms", "detail"):
            assert key in d, f"Missing key: {key}"

    def test_error_field_default_none(self):
        r = CloudSyncResult(
            operation="push_raw", success=True,
            entries_transferred=1, entries_merged=1, entries_skipped=0,
            bucket="b", s3_key="k", elapsed_ms=10.0, detail="ok",
        )
        assert r.error is None


# ============================================================================
# 11. AI-assisted distillation — AIDistillEngine
# ============================================================================


class TestAIDistillEngine(unittest.TestCase):

    def setUp(self):
        self.tmp, self.mem = _make_db()
        self.dist = DistilledMemory(db_path=self.tmp)
        self.engine = AIDistillEngine(
            db_path=self.tmp, memory=self.mem, distilled=self.dist
        )

    def test_is_ai_available_false_without_key(self):
        with patch.dict(os.environ, {}, clear=False):
            orig = os.environ.pop("OPENROUTER_API_KEY", None)
            try:
                assert AIDistillEngine.is_ai_available() is False
            finally:
                if orig:
                    os.environ["OPENROUTER_API_KEY"] = orig

    def test_is_ai_available_true_with_key(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-key"}):
            assert AIDistillEngine.is_ai_available() is True

    def test_falls_back_to_rule_based_without_key(self):
        """When no OpenRouter key, AIDistillEngine uses rule-based fallback."""
        _write(self.mem, "decided to use pytest for testing", kind="decision", confidence=0.9)
        with patch.dict(os.environ, {}, clear=False):
            orig = os.environ.pop("OPENROUTER_API_KEY", None)
            try:
                result = self.engine.distill(dry_run=False)
                assert result.distillation_method == "rule_based_fallback"
                assert result.ai_available is False
            finally:
                if orig:
                    os.environ["OPENROUTER_API_KEY"] = orig

    def test_ai_distill_with_mocked_openrouter(self):
        """When OpenRouter key present and API call succeeds, method is 'ai'."""
        _write(self.mem, "decided to use PostgreSQL for persistence", kind="decision", confidence=0.9)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-key"}):
            with patch(
                "openjarvis.memory.distillation._call_openrouter_distill",
                return_value="Key decision: use PostgreSQL for persistence",
            ):
                result = self.engine.distill(dry_run=False)
                assert result.distillation_method == "ai"
                assert result.ai_available is True
                assert result.new_distilled_count >= 1

    def test_ai_distill_dry_run_does_not_write(self):
        _write(self.mem, "preferred Python over Java", kind="preference", confidence=0.85)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-key"}):
            with patch(
                "openjarvis.memory.distillation._call_openrouter_distill",
                return_value="Preference: Python over Java",
            ):
                result = self.engine.distill(dry_run=True)
                assert result.dry_run is True
                assert result.new_distilled_count == 0  # no actual writes
                assert len(result.new_entry_ids) > 0  # dry-run placeholders

    def test_ai_distill_falls_back_per_batch_on_api_failure(self):
        """If OpenRouter call fails for a batch, falls back to rule-based for that batch."""
        _write(self.mem, "decision about caching strategy", kind="decision", confidence=0.9)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-key"}):
            with patch(
                "openjarvis.memory.distillation._call_openrouter_distill",
                return_value=None,  # Simulate API failure
            ):
                result = self.engine.distill(dry_run=False)
                # Should still produce results via rule-based fallback
                assert result.new_distilled_count >= 1
                assert result.ai_available is True  # key was present

    def test_ai_distill_idempotent_second_run(self):
        """Second run should produce no new entries for already-distilled entries."""
        _write(self.mem, "decided on microservices architecture", kind="decision", confidence=0.9)
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test-key"}):
            with patch(
                "openjarvis.memory.distillation._call_openrouter_distill",
                return_value="Key decision: microservices architecture",
            ):
                result1 = self.engine.distill()
                assert result1.new_distilled_count >= 1
                result2 = self.engine.distill()
                assert result2.new_distilled_count == 0

    def test_ai_distill_result_has_required_fields(self):
        result = AIDistillationResult(
            new_distilled_count=0,
            candidates_used=0,
            distillation_method="rule_based_fallback",
            new_entry_ids=[],
            project_id="test",
            dry_run=False,
            ai_available=False,
            detail="no candidates",
        )
        d = result.to_dict()
        for key in ("new_distilled_count", "candidates_used", "distillation_method",
                    "new_entry_ids", "project_id", "dry_run", "ai_available", "detail"):
            assert key in d, f"Missing key: {key}"

    def test_distillation_status_reflects_key_presence(self):
        with patch.dict(os.environ, {}, clear=False):
            orig = os.environ.pop("OPENROUTER_API_KEY", None)
            try:
                status = AIDistillEngine.distillation_status()
                assert status["ai_available"] is False
                assert status["status"] == "RULE_BASED_ONLY"
                os.environ["OPENROUTER_API_KEY"] = "sk-or-test"
                status2 = AIDistillEngine.distillation_status()
                assert status2["ai_available"] is True
                assert status2["status"] == "AI_ACTIVE"
            finally:
                if orig:
                    os.environ["OPENROUTER_API_KEY"] = orig
                else:
                    os.environ.pop("OPENROUTER_API_KEY", None)


# ============================================================================
# 12. _detect_kind_from_text — unit tests
# ============================================================================


class TestDetectKind(unittest.TestCase):

    def test_detects_decision(self):
        assert _detect_kind_from_text("We decided to use Redis for caching") == "decision"

    def test_detects_preference(self):
        assert _detect_kind_from_text("I prefer async patterns for I/O bound work") == "preference"

    def test_detects_lesson(self):
        assert _detect_kind_from_text("Learned that tight coupling leads to bugs") == "lesson"

    def test_detects_pattern(self):
        assert _detect_kind_from_text("Recurring pattern in this codebase") == "pattern"

    def test_defaults_to_summary(self):
        assert _detect_kind_from_text("The weather is nice today") == "summary"


# ============================================================================
# 13. MemoryOSStatus — Sprint 2B completions reflected
# ============================================================================


class TestMemoryOSStatusSprint2B(unittest.TestCase):

    def test_completed_items_includes_sprint2b(self):
        status = MemoryOSStatus()
        assert "semantic_vector_search_openai_embeddings" in status.completed_items
        assert "cloud_sync_omnix_s3_push_pull_merge" in status.completed_items
        assert "cloud_audit_replication_to_s3" in status.completed_items
        assert "ai_assisted_distillation_openrouter" in status.completed_items

    def test_planned_not_complete_no_longer_has_old_sprint2_blockers(self):
        status = MemoryOSStatus()
        remaining_items = [d["item"] for d in status.planned_not_complete]
        # These were Sprint 2 blockers — Sprint 2B cleared them
        assert "semantic_vector_search" not in remaining_items
        assert "cloud_sync_cross_device" not in remaining_items
        assert "cloud_audit_replication" not in remaining_items
        assert "ai_assisted_distillation" not in remaining_items

    def test_sprint_field_updated(self):
        status = MemoryOSStatus()
        d = status.to_dict()
        assert "2b" in d["sprint"].lower()

    def test_get_memory_os_status_returns_valid_status(self):
        _, mem = _make_db()
        path = mem._db_path
        status = get_memory_os_status(db_path=path)
        assert status.backend_available is True
        assert len(status.completed_items) >= 14  # Sprint 1+2+2B

    def test_planned_not_complete_is_list_of_dicts(self):
        status = MemoryOSStatus()
        for item in status.planned_not_complete:
            assert isinstance(item, dict)
            assert "item" in item
            assert "status" in item


# ============================================================================
# 14. Regression — Sprint 1+2 features still work
# ============================================================================


class TestRegressionSprint1And2(unittest.TestCase):

    def setUp(self):
        self.tmp, self.mem = _make_db()

    def test_write_and_search_still_works(self):
        _write(self.mem, "test entry for regression", kind="decision")
        results = self.mem.search("regression")
        assert len(results) >= 1

    def test_governance_approval_required_still_raised(self):
        from openjarvis.memory.governance import MemoryGovernance, ApprovalRequired
        gov = MemoryGovernance(db_path=self.tmp)
        e = _write(self.mem, "critical decision", kind="decision", confidence=0.95)
        with self.assertRaises(ApprovalRequired):
            gov.forget(e.entry_id, force=False)

    def test_audit_log_immutability_still_enforced(self):
        import sqlite3
        from openjarvis.memory.governance import GovernanceAuditLog, MemoryGovernance
        gov = MemoryGovernance(db_path=self.tmp)
        e = _write(self.mem, "low confidence entry", kind="observation", confidence=0.3)
        gov.forget(e.entry_id, force=True)
        audit = GovernanceAuditLog(self.tmp)
        records = audit.get_all(limit=10)
        assert len(records) >= 1
        # Attempt to delete from audit — should raise
        with self.assertRaises(
            (sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError)
        ):
            with audit._connect() as conn:
                conn.execute("DELETE FROM governance_audit WHERE 1=1")
                conn.commit()

    def test_bulk_forget_still_works(self):
        from openjarvis.memory.governance import MemoryGovernance
        gov = MemoryGovernance(db_path=self.tmp)
        for i in range(3):
            _write(self.mem, f"low confidence entry {i}", kind="observation", confidence=0.2)
        result = gov.bulk_forget(
            namespace="test", max_confidence=0.5, dry_run=False
        )
        assert result.deleted_count >= 3

    def test_expiry_enforcement_still_works(self):
        from openjarvis.memory.governance import MemoryGovernance
        gov = MemoryGovernance(db_path=self.tmp)
        past_ts = time.time() - 100
        _write(self.mem, "expired entry", kind="observation", expires_at=past_ts)
        result = gov.enforce_expiry()
        assert result.deleted_count >= 1

    def test_auto_distill_engine_still_works(self):
        dist = DistilledMemory(db_path=self.tmp)
        engine = AutoDistillEngine(memory=self.mem, distilled=dist)
        _write(self.mem, "decided on microservices", kind="decision", confidence=0.9)
        result = engine.auto_distill()
        assert result.new_distilled_count >= 1

    def test_tfidf_ranker_still_scores(self):
        entries = [
            _write(self.mem, "use caching for performance", kind="decision"),
            _write(self.mem, "prefer lazy evaluation patterns", kind="preference"),
        ]
        scored = TfIdfRanker.score("caching performance", entries)
        assert len(scored) == 2
        # entry about caching should score higher
        assert scored[0][0].content == "use caching for performance"


# ============================================================================
# 15. Sprint 1 starter hygiene tests referenced (regression guard)
# ============================================================================


class TestStarterHygieneRegression(unittest.TestCase):
    """Guard: verify we haven't broken the module import chain."""

    def test_memory_module_importable(self):
        from openjarvis.memory import (
            JarvisMemory, MemoryRetriever, MemoryGovernance,
            get_memory_os_status, AutoDistillEngine,
        )

    def test_cloud_sync_importable(self):
        from openjarvis.memory.cloud_sync import JarvisMemoryS3Sync, CloudSyncResult

    def test_ai_distill_engine_importable(self):
        from openjarvis.memory.distillation import AIDistillEngine, AIDistillationResult

    def test_semantic_search_status_importable(self):
        from openjarvis.memory.retrieval import SemanticSearchStatus
        d = SemanticSearchStatus.to_dict()
        assert "active_ranker" in d


if __name__ == "__main__":
    unittest.main()
