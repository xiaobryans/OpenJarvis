"""Plan 4 Sprint 2 — Memory OS Completion tests.

Required proofs:
  1.  Automatic distillation: write raw → auto_distill → retrieve from distilled
  2.  Distillation idempotency: calling auto_distill() twice does not duplicate entries
  3.  Distillation dry_run: reports what would be distilled without writing
  4.  Retrieval ranking: TF-IDF re-ranks results (tfidf_score present, ranker_used)
  5.  Semantic search status: honest BLOCKED — never fakes vector embeddings
  6.  Approval workflow: forget() raises ApprovalRequired for protected entries
  7.  Approval workflow: force=True bypasses approval gate
  8.  High-confidence delete approval required
  9.  Protected kind (decision/preference) requires approval
  10. Immutable audit trail: append → get_all → confirm immutability (triggers)
  11. Audit trail: forget() always creates an audit record
  12. Audit trail: edit() always creates an audit record
  13. Bulk forget dry_run: returns expected candidates without deleting
  14. Bulk forget: actually deletes when dry_run=False
  15. Bulk forget safety: skips protected entries unless force=True
  16. Bulk forget: requires at least one filter
  17. Expiry enforcement: list_expired() returns only expired entries
  18. Expiry enforcement: enforce_expiry() deletes expired, keeps active
  19. Expiry enforcement dry_run: reports expired IDs without deleting
  20. Expiry enforcement: now override for deterministic testing
  21. Cloud/cross-device: status is honest (BLOCKED or local_only)
  22. Cloud status: never claims cloud available if no credentials
  23. MemoryOSStatus Sprint 2: completed_items includes new sprint items
  24. MemoryOSStatus Sprint 2: planned_not_complete is honest list of dicts
  25. Governance status(): reports Sprint 2 items as implemented
  26. GovernanceResult.audit_id is populated after Sprint 2 forget
  27. Regression: existing Sprint 1 tests continue to pass
"""

from __future__ import annotations

import sqlite3
import time

import pytest

from openjarvis.memory.store import JarvisMemory, MemoryEntry
from openjarvis.memory.distilled import DistilledMemory, DistilledEntry
from openjarvis.memory.retrieval import (
    MemoryRetriever,
    RetrievalResult,
    SemanticSearchStatus,
    TfIdfRanker,
)
from openjarvis.memory.context import MemoryContextBuilder
from openjarvis.memory.status import get_memory_os_status
from openjarvis.memory.governance import (
    MemoryGovernance,
    GovernanceAuditLog,
    ApprovalRequired,
    BulkForgetResult,
    ExpiryEnforcementResult,
    HIGH_CONFIDENCE_THRESHOLD,
    PROTECTED_KINDS,
)
from openjarvis.memory.distillation import AutoDistillEngine, DistillationResult, DISTILLABLE_KINDS
from openjarvis.memory.cloud_memory import check_cloud_memory_status, CloudMemoryStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_path(tmp_path):
    return tmp_path / "sprint2_test.db"


@pytest.fixture()
def mem(db_path):
    return JarvisMemory(db_path=db_path)


@pytest.fixture()
def dist(db_path):
    return DistilledMemory(db_path=db_path)


@pytest.fixture()
def gov(db_path):
    return MemoryGovernance(db_path=db_path)


@pytest.fixture()
def engine(db_path):
    return AutoDistillEngine(db_path=db_path)


# ---------------------------------------------------------------------------
# 1–3. Automatic distillation
# ---------------------------------------------------------------------------


class TestAutoDistillation:

    def test_distill_decision_write_reload_retrieve(self, db_path):
        """Write a high-confidence decision → auto_distill → appears in distilled."""
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="global",
            content="Chose Python over JavaScript for backend tooling",
            source="test",
            project_id="omnix",
            kind="decision",
            confidence=0.9,
        )

        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill(project_id="omnix")

        assert result.candidates_found >= 1
        assert result.new_distilled_count >= 1
        assert not result.dry_run

        # Verify distilled entry is persisted (reload from DB)
        dist = DistilledMemory(db_path=db_path)
        entries = dist.list_by_kind("decision", limit=10)
        assert len(entries) >= 1
        contents = [e.content for e in entries]
        assert any("Python" in c for c in contents)

    def test_distill_preference_maps_to_preference_kind(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="global",
            content="Bryan prefers dark mode UI for all dashboards",
            source="test",
            project_id="test",
            kind="preference",
            confidence=0.85,
        )
        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill(project_id="test")
        assert result.new_distilled_count >= 1

        dist = DistilledMemory(db_path=db_path)
        prefs = dist.list_by_kind("preference", limit=5)
        assert len(prefs) >= 1
        assert any("dark mode" in e.content.lower() for e in prefs)

    def test_distill_observation_maps_to_pattern(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="observations",
            content="Observed that async DB writes reduce latency by 40%",
            source="test",
            project_id="perf",
            kind="observation",
            confidence=0.8,
        )
        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill(project_id="perf")
        assert result.new_distilled_count >= 1

        dist = DistilledMemory(db_path=db_path)
        patterns = dist.list_by_kind("pattern", limit=5)
        assert len(patterns) >= 1

    def test_distill_mistake_maps_to_lesson(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="lessons",
            content="Used hardcoded API key in unit test — leaked via GitHub",
            source="test",
            kind="mistake",
            confidence=0.95,
        )
        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill()
        assert result.new_distilled_count >= 1

        dist = DistilledMemory(db_path=db_path)
        lessons = dist.list_by_kind("lesson", limit=5)
        assert len(lessons) >= 1

    def test_distill_idempotent(self, db_path):
        """Calling auto_distill() twice does not duplicate entries."""
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="global",
            content="Always use environment variables for secrets",
            source="test",
            project_id="sec",
            kind="decision",
            confidence=0.92,
        )
        engine = AutoDistillEngine(db_path=db_path)
        r1 = engine.auto_distill(project_id="sec")
        r2 = engine.auto_distill(project_id="sec")

        assert r1.new_distilled_count >= 1
        # Second call: no new entries
        assert r2.new_distilled_count == 0
        assert r2.skipped_already_distilled >= 1

    def test_distill_dry_run_reports_without_writing(self, db_path):
        """dry_run=True: reports what would be created, does not write."""
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="global",
            content="Prefer small focused commits over large bulk commits",
            source="test",
            kind="preference",
            confidence=0.88,
        )
        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill(dry_run=True)

        assert result.dry_run is True
        assert result.new_distilled_count == 0  # nothing written
        assert result.candidates_found >= 1
        assert len(result.new_entry_ids) >= 1  # dry_run reports what would be created

        # Verify nothing written
        dist = DistilledMemory(db_path=db_path)
        assert dist.count() == 0

    def test_distill_below_min_confidence_skipped(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(
            namespace="global",
            content="Low confidence note",
            source="test",
            kind="decision",
            confidence=0.3,
        )
        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill(min_confidence=0.7)
        assert result.candidates_found == 0
        assert result.new_distilled_count == 0

    def test_distill_result_to_dict_fields(self, db_path):
        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill()
        d = result.to_dict()
        assert "new_distilled_count" in d
        assert "dry_run" in d
        assert "candidates_found" in d
        assert "new_entry_ids" in d

    def test_distill_source_ids_provenance(self, db_path):
        """Distilled entries reference source raw entry_id via source_ids."""
        mem = JarvisMemory(db_path=db_path)
        raw_entry = mem.write(
            namespace="global",
            content="Deploy to staging before production always",
            source="test",
            kind="decision",
            confidence=0.9,
        )

        engine = AutoDistillEngine(db_path=db_path)
        result = engine.auto_distill()
        assert result.new_distilled_count >= 1

        dist = DistilledMemory(db_path=db_path)
        decisions = dist.list_by_kind("decision", limit=5)
        assert any(raw_entry.entry_id in d.source_ids for d in decisions)


# ---------------------------------------------------------------------------
# 4–5. Retrieval ranking (TF-IDF + honest semantic blocker)
# ---------------------------------------------------------------------------


class TestRetrievalRanking:

    def test_tfidf_score_present_in_result(self, mem):
        mem.write(namespace="global", content="Python backend microservices architecture", source="t", kind="decision", confidence=0.9)
        mem.write(namespace="global", content="JavaScript frontend React components", source="t", kind="observation", confidence=0.7)
        mem.write(namespace="global", content="Python data pipeline with pandas", source="t", kind="event", confidence=0.8)

        retriever = MemoryRetriever(memory=mem)
        results = retriever.retrieve("Python architecture")

        assert len(results) >= 1
        for r in results:
            assert isinstance(r.tfidf_score, float)
            assert r.tfidf_score >= 0.0
            assert r.ranker_used == SemanticSearchStatus.ACTIVE_RANKER

    def test_tfidf_ranker_scores_multiple_docs(self):
        """TfIdfRanker returns correct shape."""
        entries = [
            MemoryEntry(
                content="Python is used for backend services",
                namespace="test",
                confidence=0.9,
            ),
            MemoryEntry(
                content="JavaScript for the frontend only",
                namespace="test",
                confidence=0.7,
            ),
        ]
        scored = TfIdfRanker.score("Python backend", entries)
        assert len(scored) == 2
        assert all(isinstance(s, tuple) and len(s) == 2 for s in scored)
        # Python-related entry should score higher
        scores = {e.content[:6]: s for e, s in scored}
        assert scores.get("Python") >= scores.get("JavaSc", -1)

    def test_retrieval_result_has_ranker_used_field(self, mem):
        mem.write(namespace="global", content="test entry for ranker label", source="t", kind="event", confidence=0.8)
        retriever = MemoryRetriever(memory=mem)
        results = retriever.retrieve("test entry")
        if results:
            assert results[0].ranker_used == "tfidf_local"

    def test_retrieval_to_dict_includes_tfidf(self, mem):
        mem.write(namespace="global", content="Deep learning model training tips", source="t", confidence=0.85)
        retriever = MemoryRetriever(memory=mem)
        results = retriever.retrieve("deep learning")
        if results:
            d = results[0].to_dict()
            assert "tfidf_score" in d
            assert "ranker_used" in d

    def test_semantic_search_status_is_blocked(self):
        """SemanticSearchStatus reports BLOCKED_NO_EMBEDDING_MODEL honestly."""
        s = SemanticSearchStatus.to_dict()
        assert s["vector_search"] == "BLOCKED_NO_EMBEDDING_MODEL"
        assert "embedding" in s["vector_reason"].lower() or "model" in s["vector_reason"].lower()
        assert s["active_ranker"] == "tfidf_local"

    def test_retriever_semantic_search_status_method(self, mem):
        retriever = MemoryRetriever(memory=mem)
        status = retriever.semantic_search_status()
        assert status["vector_search"] == "BLOCKED_NO_EMBEDDING_MODEL"
        assert "fallback_description" in status

    def test_tfidf_empty_candidates_returns_empty(self):
        result = TfIdfRanker.score("query", [])
        assert result == []


# ---------------------------------------------------------------------------
# 6–9. Approval workflow
# ---------------------------------------------------------------------------


class TestApprovalWorkflow:

    def test_forget_low_confidence_no_approval_needed(self, gov):
        """Entries with confidence < 0.9 and non-protected kind can be deleted freely."""
        gov._memory.write(
            namespace="global",
            content="Low confidence casual note",
            source="test",
            kind="casual_note",
            confidence=0.5,
        )
        entries = gov._memory.search("casual note", limit=5)
        assert len(entries) >= 1
        result = gov.forget(entries[0].entry_id)
        assert result.success is True

    def test_forget_high_confidence_raises_approval_required(self, gov):
        """Entries with confidence >= HIGH_CONFIDENCE_THRESHOLD raise ApprovalRequired."""
        gov._memory.write(
            namespace="global",
            content="Critical production decision: use blue-green deployment",
            source="test",
            kind="event",
            confidence=0.95,
        )
        entries = gov._memory.search("blue-green", limit=5)
        assert len(entries) >= 1
        with pytest.raises(ApprovalRequired) as exc_info:
            gov.forget(entries[0].entry_id)
        assert exc_info.value.entry_id == entries[0].entry_id
        assert "force=True" in str(exc_info.value)

    def test_forget_decision_kind_raises_approval_required(self, gov):
        """Protected kinds (decision) always require approval regardless of confidence."""
        gov._memory.write(
            namespace="global",
            content="Use PostgreSQL as the primary database",
            source="test",
            kind="decision",
            confidence=0.5,  # below 0.9 threshold, but protected kind
        )
        entries = gov._memory.search("PostgreSQL", limit=5)
        assert len(entries) >= 1
        with pytest.raises(ApprovalRequired):
            gov.forget(entries[0].entry_id)

    def test_forget_preference_kind_raises_approval_required(self, gov):
        gov._memory.write(
            namespace="global",
            content="Prefer async await over callbacks",
            source="test",
            kind="preference",
            confidence=0.4,
        )
        entries = gov._memory.search("callbacks", limit=5)
        assert len(entries) >= 1
        with pytest.raises(ApprovalRequired):
            gov.forget(entries[0].entry_id)

    def test_forget_force_true_bypasses_approval(self, gov):
        """force=True allows deletion of protected entries."""
        gov._memory.write(
            namespace="global",
            content="Decision: use monorepo over multi-repo",
            source="test",
            kind="decision",
            confidence=0.95,
        )
        entries = gov._memory.search("monorepo", limit=5)
        assert len(entries) >= 1
        entry_id = entries[0].entry_id

        result = gov.forget(entry_id, force=True)
        assert result.success is True
        assert gov._memory.get(entry_id) is None  # actually deleted

    def test_forget_distilled_approval_gate(self, gov):
        """forget_distilled() also enforces approval for high-confidence entries."""
        gov._distilled.write(
            content="Core architectural decision: event-driven microservices",
            kind="decision",
            confidence=0.95,
        )
        distilled = gov._distilled.list_by_kind("decision", limit=5)
        assert len(distilled) >= 1
        with pytest.raises(ApprovalRequired):
            gov.forget_distilled(distilled[0].entry_id)

    def test_protected_kinds_constant(self):
        assert "decision" in PROTECTED_KINDS
        assert "preference" in PROTECTED_KINDS
        assert "event" not in PROTECTED_KINDS

    def test_high_confidence_threshold_is_sane(self):
        assert 0.8 <= HIGH_CONFIDENCE_THRESHOLD <= 1.0


# ---------------------------------------------------------------------------
# 10–12. Immutable audit trail
# ---------------------------------------------------------------------------


class TestImmutableAuditTrail:

    def test_audit_log_append_and_get_all(self, db_path):
        """Audit log accepts appends and returns records."""
        audit = GovernanceAuditLog(db_path)
        record = audit.append("test_action", entry_id="abc123", detail="test")
        assert record.audit_id
        assert record.action == "test_action"

        records = audit.get_all()
        assert len(records) >= 1
        ids = [r.audit_id for r in records]
        assert record.audit_id in ids

    def test_audit_log_immutable_delete_raises(self, db_path):
        """Attempting to DELETE an audit row triggers SQLite abort."""
        audit = GovernanceAuditLog(db_path)
        audit.append("immutability_test", entry_id="xyz")

        conn = sqlite3.connect(str(db_path))
        # SQLite trigger RAISE(ABORT) raises sqlite3.DatabaseError or subclass
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError)):
            conn.execute("DELETE FROM governance_audit WHERE 1=1")
        conn.close()

    def test_audit_log_immutable_update_raises(self, db_path):
        """Attempting to UPDATE an audit row triggers SQLite abort."""
        audit = GovernanceAuditLog(db_path)
        record = audit.append("update_test", entry_id="xyz")

        conn = sqlite3.connect(str(db_path))
        with pytest.raises((sqlite3.OperationalError, sqlite3.IntegrityError, sqlite3.DatabaseError)):
            conn.execute(
                "UPDATE governance_audit SET detail='hacked' WHERE audit_id=?",
                (record.audit_id,),
            )
        conn.close()

    def test_forget_creates_audit_record(self, gov):
        """Every forget() call creates an audit record."""
        gov._memory.write(
            namespace="global",
            content="Audit trail test entry",
            source="test",
            kind="event",
            confidence=0.3,
        )
        entries = gov._memory.search("Audit trail test", limit=5)
        entry_id = entries[0].entry_id

        before_count = gov.audit_log.count()
        result = gov.forget(entry_id)
        after_count = gov.audit_log.count()

        assert result.success is True
        assert after_count == before_count + 1
        assert result.audit_id is not None

    def test_edit_creates_audit_record(self, gov):
        gov._memory.write(
            namespace="global",
            content="Editable entry for audit test",
            source="test",
            kind="event",
            confidence=0.4,
        )
        entries = gov._memory.search("Editable entry for audit", limit=5)
        entry_id = entries[0].entry_id

        before = gov.audit_log.count()
        result = gov.edit(entry_id, new_content="Updated content")
        after = gov.audit_log.count()

        assert result.success is True
        assert after == before + 1
        assert result.audit_id is not None

    def test_audit_record_to_dict(self, db_path):
        audit = GovernanceAuditLog(db_path)
        record = audit.append(
            "export",
            entry_id="ns:global",
            entry_kind="",
            detail="exported 5 entries",
        )
        d = record.to_dict()
        assert d["action"] == "export"
        assert d["audit_id"] == record.audit_id
        assert "timestamp" in d
        assert "forced" in d

    def test_get_by_entry(self, db_path):
        """get_by_entry() returns only records for that entry_id."""
        audit = GovernanceAuditLog(db_path)
        audit.append("forget", entry_id="entry_A", detail="first")
        audit.append("forget", entry_id="entry_B", detail="other")
        audit.append("edit",   entry_id="entry_A", detail="second")

        records = audit.get_by_entry("entry_A")
        assert len(records) == 2
        assert all(r.entry_id == "entry_A" for r in records)

    def test_audit_count(self, db_path):
        audit = GovernanceAuditLog(db_path)
        for i in range(3):
            audit.append("count_test", entry_id=f"entry_{i}")
        assert audit.count() >= 3


# ---------------------------------------------------------------------------
# 13–16. Bulk forget
# ---------------------------------------------------------------------------


class TestBulkForget:

    def _write_batch(self, mem, n=5, kind="event", confidence=0.5, namespace="bulk_test"):
        for i in range(n):
            mem.write(
                namespace=namespace,
                content=f"bulk test entry {i} content for deletion",
                source="test",
                kind=kind,
                confidence=confidence,
            )

    def test_bulk_forget_dry_run_reports_without_deleting(self, gov):
        self._write_batch(gov._memory, n=3, kind="casual_note", confidence=0.3)
        result = gov.bulk_forget(namespace="bulk_test", dry_run=True)
        assert result.dry_run is True
        assert result.deleted_count == 0
        assert result.entries_matched >= 3

    def test_bulk_forget_actually_deletes(self, gov):
        self._write_batch(gov._memory, n=4, kind="event", confidence=0.4)
        result = gov.bulk_forget(namespace="bulk_test", dry_run=False, kind="event")
        assert result.dry_run is False
        assert result.deleted_count >= 1

    def test_bulk_forget_skips_protected_entries(self, gov):
        """Bulk forget without force=True skips entries with high confidence."""
        gov._memory.write(
            namespace="bulk_test",
            content="High-confidence decision entry",
            source="test",
            kind="decision",
            confidence=0.95,
        )
        gov._memory.write(
            namespace="bulk_test",
            content="Low-confidence casual note",
            source="test",
            kind="casual_note",
            confidence=0.3,
        )
        result = gov.bulk_forget(namespace="bulk_test", dry_run=False)
        # Protected decision (confidence >= threshold) should be skipped
        assert result.skipped_count >= 1
        # Casual note should be deleted
        assert result.deleted_count >= 1

    def test_bulk_forget_force_deletes_protected(self, gov):
        """force=True allows bulk deletion of protected entries."""
        gov._memory.write(
            namespace="bulk_force_test",
            content="Protected entry for bulk test",
            source="test",
            kind="decision",
            confidence=0.95,
        )
        result = gov.bulk_forget(namespace="bulk_force_test", dry_run=False, force=True)
        assert result.deleted_count >= 1
        assert result.skipped_count == 0

    def test_bulk_forget_requires_at_least_one_filter(self, gov):
        """bulk_forget with no filters returns empty result without deleting."""
        result = gov.bulk_forget(dry_run=False)
        assert result.deleted_count == 0
        assert result.entries_matched == 0
        assert "no filters" in result.detail.lower()

    def test_bulk_forget_result_to_dict(self, gov):
        result = gov.bulk_forget(namespace="nonexistent_ns", dry_run=True)
        d = result.to_dict()
        assert "deleted_count" in d
        assert "dry_run" in d
        assert "entries_matched" in d
        assert "skipped_ids" in d
        assert "deleted_ids" in d

    def test_bulk_forget_creates_audit_record(self, gov):
        gov._memory.write(
            namespace="bulk_audit_test",
            content="Audit bulk forget entry",
            source="test",
            kind="event",
            confidence=0.3,
        )
        before = gov.audit_log.count()
        gov.bulk_forget(namespace="bulk_audit_test", dry_run=False)
        after = gov.audit_log.count()
        assert after > before


# ---------------------------------------------------------------------------
# 17–20. Expiry enforcement
# ---------------------------------------------------------------------------


class TestExpiryEnforcement:

    def test_list_expired_returns_only_expired(self, mem):
        past_ts = time.time() - 86400  # yesterday
        future_ts = time.time() + 86400  # tomorrow

        mem.write(namespace="global", content="Expired entry", source="t", expires_at=past_ts)
        mem.write(namespace="global", content="Future entry", source="t", expires_at=future_ts)
        mem.write(namespace="global", content="No expiry entry", source="t")

        expired = mem.list_expired()
        assert len(expired) == 1
        assert "Expired" in expired[0].content

    def test_list_expired_respects_now_override(self, mem):
        """Injectable now parameter allows deterministic testing."""
        future_ts = time.time() + 3600  # 1 hour from now

        mem.write(namespace="global", content="Will expire in an hour", source="t", expires_at=future_ts)

        # With real now: not yet expired
        expired_real = mem.list_expired()
        assert not any("hour" in e.content for e in expired_real)

        # With now = far future: appears as expired
        expired_future = mem.list_expired(now=future_ts + 1)
        assert any("hour" in e.content for e in expired_future)

    def test_enforce_expiry_deletes_expired(self, gov):
        """enforce_expiry() actually deletes expired entries."""
        past_ts = time.time() - 100
        gov._memory.write(
            namespace="global",
            content="Should be expired entry",
            source="test",
            expires_at=past_ts,
            kind="temporary_thought",
        )
        gov._memory.write(namespace="global", content="Still active", source="test")

        result = gov.enforce_expiry(dry_run=False)
        assert result.dry_run is False
        assert result.deleted_count >= 1
        assert result.entries_expired >= 1
        assert len(result.deleted_ids) >= 1

        # Verify deleted
        remaining = gov._memory.list_expired()
        assert len(remaining) == 0

    def test_enforce_expiry_dry_run(self, gov):
        past_ts = time.time() - 100
        gov._memory.write(
            namespace="global",
            content="About to expire entry",
            source="test",
            expires_at=past_ts,
        )

        result = gov.enforce_expiry(dry_run=True)
        assert result.dry_run is True
        assert result.deleted_count == 0  # not deleted
        assert result.entries_expired >= 1

        # Verify entry still present
        expired = gov._memory.list_expired()
        assert len(expired) >= 1

    def test_enforce_expiry_deterministic_now(self, gov):
        """enforce_expiry respects now= override for test determinism."""
        future_ts = time.time() + 3600

        gov._memory.write(
            namespace="global",
            content="Future expiry entry",
            source="test",
            expires_at=future_ts,
        )

        # With now = far past: entry not yet expired
        result_past = gov.enforce_expiry(now=time.time() - 86400, dry_run=True)
        assert result_past.entries_expired == 0

        # With now = beyond expiry
        result_future = gov.enforce_expiry(now=future_ts + 1, dry_run=True)
        assert result_future.entries_expired >= 1

    def test_enforce_expiry_result_to_dict(self, gov):
        result = gov.enforce_expiry(dry_run=True)
        d = result.to_dict()
        assert "deleted_count" in d
        assert "dry_run" in d
        assert "entries_expired" in d
        assert "deleted_ids" in d
        assert "now_ts" in d

    def test_enforce_expiry_creates_audit_record_when_not_dry(self, gov):
        past_ts = time.time() - 100
        gov._memory.write(
            namespace="global",
            content="Expiry audit test entry",
            source="test",
            expires_at=past_ts,
        )

        before = gov.audit_log.count()
        result = gov.enforce_expiry(dry_run=False)
        after = gov.audit_log.count()

        if result.deleted_count > 0:
            assert after > before


# ---------------------------------------------------------------------------
# 21–22. Cloud sync / cross-device honest status
# ---------------------------------------------------------------------------


class TestCloudSyncStatus:

    def test_cloud_status_returns_valid_object(self):
        status = check_cloud_memory_status()
        assert isinstance(status, CloudMemoryStatus)

    def test_cloud_status_to_dict_fields(self):
        status = check_cloud_memory_status()
        d = status.to_dict()
        assert "local_db_path" in d
        assert "local_db_exists" in d
        assert "cloud_backends" in d
        assert "active_backend" in d
        assert "sync_status" in d
        assert "summary" in d

    def test_cloud_sync_status_is_local_only_without_credentials(self):
        """Without credentials, sync_status must be local_only."""
        import os

        aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        sb_url = os.environ.get("SUPABASE_URL", "")
        sb_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

        if not (aws_key and aws_secret) and not (sb_url and sb_key):
            status = check_cloud_memory_status()
            assert status.sync_status == "local_only"
            assert status.active_backend == "local_sqlite"

    def test_cloud_backends_report_blocked_no_credentials(self):
        """All unavailable cloud backends must be honestly BLOCKED."""
        status = check_cloud_memory_status()
        valid_blocked_statuses = {
            "BLOCKED_CREDENTIALS",
            "BLOCKED_IMPLEMENTATION",
            "PLANNED_IN_EXISTING_PROMPT",
            "OPTIONAL_BACKLOG",
        }
        for backend in status.cloud_backends:
            if not backend.available:
                assert backend.status.value in valid_blocked_statuses

    def test_local_sqlite_always_available(self, tmp_path):
        """Local SQLite backend is always available."""
        status = check_cloud_memory_status(db_path=tmp_path / "test.db")
        assert status.local_status.value == "DAILY_DRIVER_ACCEPT"

    def test_cloud_status_does_not_leak_credentials_in_to_dict(self):
        """to_dict() output must not contain raw credential values."""
        status = check_cloud_memory_status()
        d = status.to_dict()
        # cloud_backends list items should not expose raw credential values
        for b in d["cloud_backends"]:
            assert "credential_env_vars" not in b


# ---------------------------------------------------------------------------
# 23–26. MemoryOSStatus Sprint 2 + governance_status
# ---------------------------------------------------------------------------


class TestMemoryOSStatusSprint2:

    def test_status_sprint_is_sprint2(self, tmp_path):
        status = get_memory_os_status(db_path=tmp_path / "s2_status.db")
        d = status.to_dict()
        assert d["sprint"] == "plan4_sprint2_memory_os_completion"

    def test_completed_items_includes_sprint2(self, tmp_path):
        status = get_memory_os_status(db_path=tmp_path / "s2_status2.db")
        d = status.to_dict()
        completed = d.get("completed_items", [])
        assert "automatic_distillation_from_raw" in completed
        assert "immutable_audit_trail_for_governance" in completed
        assert "approval_workflow_for_protected_entries" in completed
        assert "bulk_forget_with_safety_gates" in completed
        assert "expiry_enforcement_scheduler" in completed

    def test_planned_not_complete_is_honest_list_of_dicts(self, tmp_path):
        status = get_memory_os_status(db_path=tmp_path / "s2_status3.db")
        d = status.to_dict()
        pnc = d.get("planned_not_complete", [])
        assert isinstance(pnc, list)
        assert len(pnc) >= 1
        for item in pnc:
            assert isinstance(item, dict)
            assert "item" in item
            assert "status" in item

    def test_semantic_vector_search_in_planned_not_complete(self, tmp_path):
        status = get_memory_os_status(db_path=tmp_path / "s2_status4.db")
        items = [i["item"] for i in status.planned_not_complete]
        assert "semantic_vector_search" in items

    def test_cloud_sync_in_planned_not_complete(self, tmp_path):
        status = get_memory_os_status(db_path=tmp_path / "s2_status5.db")
        items = [i["item"] for i in status.planned_not_complete]
        assert "cloud_sync_cross_device" in items

    def test_governance_status_reports_sprint2_implemented(self):
        s = MemoryGovernance.governance_status()
        implemented = s.get("implemented", [])
        assert any("bulk_forget" in i for i in implemented)
        assert any("enforce_expiry" in i for i in implemented)
        assert any("audit_trail" in i or "immutable" in i for i in implemented)
        assert any("approval" in i for i in implemented)

    def test_governance_result_has_audit_id_after_sprint2_forget(self, gov):
        gov._memory.write(
            namespace="global",
            content="Audit ID test entry for governance",
            source="test",
            kind="event",
            confidence=0.3,
        )
        entries = gov._memory.search("Audit ID test entry", limit=5)
        result = gov.forget(entries[0].entry_id)
        assert result.audit_id is not None
        assert len(result.audit_id) > 0


# ---------------------------------------------------------------------------
# 27. Regression: Sprint 1 features still work
# ---------------------------------------------------------------------------


class TestSprint1Regression:

    def test_store_write_reload_retrieve(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(namespace="global", content="Regression: basic write test", source="t", confidence=0.8)
        mem2 = JarvisMemory(db_path=db_path)
        results = mem2.search("Regression basic write")
        assert len(results) >= 1

    def test_distilled_write_search(self, db_path):
        dist = DistilledMemory(db_path=db_path)
        dist.write(content="Regression: distilled entry for Sprint 1 check", kind="summary")
        results = dist.search("distilled Sprint 1")
        assert len(results) >= 1

    def test_retrieval_active_only(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(namespace="global", content="Active entry regression", source="t", kind="event", confidence=0.7, status="active")
        mem.write(namespace="global", content="Archived entry regression", source="t", kind="event", confidence=0.7, status="archived")

        retriever = MemoryRetriever(memory=mem)
        active = retriever.retrieve_active("regression")
        assert all(r.is_active for r in active)

    def test_context_injection_disabled_returns_empty(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        mem.write(namespace="global", content="Context injection test entry", source="t", confidence=0.8)

        builder = MemoryContextBuilder(memory=mem)
        result = builder.build_context(
            "context injection test",
            context_from_memory=False,
        )
        assert result.context_enabled is False
        assert result.context_text == ""

    def test_governance_forget_still_works_low_confidence(self, gov):
        gov._memory.write(
            namespace="global",
            content="Low confidence event for sprint1 regression",
            source="test",
            kind="event",
            confidence=0.3,
        )
        entries = gov._memory.search("sprint1 regression", limit=5)
        assert len(entries) >= 1
        result = gov.forget(entries[0].entry_id)
        assert result.success is True

    def test_kind_status_expires_at_fields_preserved(self, db_path):
        mem = JarvisMemory(db_path=db_path)
        future_ts = time.time() + 3600
        mem.write(
            namespace="global",
            content="Field test entry",
            source="t",
            kind="temporary_thought",
            status="active",
            expires_at=future_ts,
        )
        mem2 = JarvisMemory(db_path=db_path)
        results = mem2.search("Field test entry")
        assert len(results) >= 1
        entry = results[0]
        assert entry.kind == "temporary_thought"
        assert entry.status == "active"
        assert entry.expires_at is not None
        assert abs(entry.expires_at - future_ts) < 1.0
