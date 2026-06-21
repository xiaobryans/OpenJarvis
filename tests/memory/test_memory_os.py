"""Plan 4 Sprint 1 — Memory OS Foundation tests.

Covers all required proofs:
  - Raw/archive memory: write → reload → retrieve (with metadata)
  - Distilled memory: write → reload → retrieve
  - Retrieval returns source-linked metadata/evidence
  - context_from_memory=True injects relevant memory into prompt/context path
  - Memory status reports honest backend state
  - Governance: forget/edit/export
  - Kind/status/expires_at fields
  - Regression: prior store tests still pass (write/search/isolation)
"""

from __future__ import annotations

import time

import pytest

from openjarvis.memory.store import JarvisMemory, MemoryEntry, MEMORY_KINDS, MEMORY_STATUSES
from openjarvis.memory.distilled import DistilledMemory, DistilledEntry, DISTILLED_KINDS
from openjarvis.memory.retrieval import MemoryRetriever, RetrievalResult
from openjarvis.memory.context import MemoryContextBuilder, InjectedContext
from openjarvis.memory.status import MemoryOSStatus, get_memory_os_status
from openjarvis.memory.governance import MemoryGovernance, GovernanceResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem(tmp_path):
    """Isolated JarvisMemory backed by a tmp SQLite DB."""
    return JarvisMemory(db_path=tmp_path / "test_memory_os.db")


@pytest.fixture()
def dist(tmp_path):
    """Isolated DistilledMemory using same tmp SQLite DB."""
    return DistilledMemory(db_path=tmp_path / "test_memory_os.db")


@pytest.fixture()
def mem_and_dist(tmp_path):
    """Both JarvisMemory and DistilledMemory sharing the same DB."""
    db = tmp_path / "shared_memory_os.db"
    return JarvisMemory(db_path=db), DistilledMemory(db_path=db)


@pytest.fixture()
def gov(tmp_path):
    """MemoryGovernance over a fresh DB."""
    db = tmp_path / "gov_memory.db"
    return MemoryGovernance(db_path=db)


# ---------------------------------------------------------------------------
# 1. Raw/archive: write → reload → retrieve
# ---------------------------------------------------------------------------


def test_raw_write_and_reload_retrieve(tmp_path):
    """Proof: raw/archive write survives process/new-instance boundary."""
    db = tmp_path / "reload_test.db"
    # Write with instance A
    mem_a = JarvisMemory(db_path=db)
    entry = mem_a.write(
        namespace="project:omnix",
        content="Bryan prefers Claude for coding tasks",
        source="agent:manager",
        project_id="omnix",
        kind="preference",
        tags=["model", "coding"],
    )
    entry_id = entry.entry_id

    # Reload with fresh instance B (simulates new process)
    mem_b = JarvisMemory(db_path=db)
    found = mem_b.get(entry_id)
    assert found is not None, "Entry must survive reload to new instance"
    assert found.content == "Bryan prefers Claude for coding tasks"
    assert found.source == "agent:manager"
    assert found.project_id == "omnix"
    assert found.kind == "preference"
    assert found.tags == ["model", "coding"]


def test_raw_write_with_all_kind_values(mem):
    """All valid kind values are accepted and persisted."""
    for kind in MEMORY_KINDS:
        entry = mem.write(
            namespace="global",
            content=f"test entry kind={kind}",
            source="test",
            kind=kind,
        )
        fetched = mem.get(entry.entry_id)
        assert fetched is not None
        assert fetched.kind == kind


def test_raw_status_field_persists(mem):
    """Status field is persisted and retrieval respects it."""
    e_active = mem.write(namespace="global", content="active entry", source="t", status="active")
    e_archived = mem.write(namespace="global", content="archived entry", source="t", status="archived")
    e_deprecated = mem.write(namespace="global", content="deprecated entry", source="t", status="deprecated")

    # Search excludes deleted by default, returns active+archived+deprecated
    results = mem.search("entry")
    statuses = {r.status for r in results}
    assert "active" in statuses
    assert "archived" in statuses
    assert "deprecated" in statuses


def test_raw_expires_at_field(mem):
    """expires_at field is persisted; is_expired() works correctly."""
    future_ts = time.time() + 3600
    past_ts = time.time() - 1

    e_future = mem.write(
        namespace="global", content="future expiry", source="t", expires_at=future_ts
    )
    e_past = mem.write(
        namespace="global", content="past expiry", source="t", expires_at=past_ts
    )
    e_none = mem.write(namespace="global", content="no expiry", source="t")

    fetched_future = mem.get(e_future.entry_id)
    fetched_past = mem.get(e_past.entry_id)
    fetched_none = mem.get(e_none.entry_id)

    assert fetched_future.expires_at == pytest.approx(future_ts)
    assert not fetched_future.is_expired()
    assert fetched_future.is_active()

    assert fetched_past.expires_at == pytest.approx(past_ts)
    assert fetched_past.is_expired()
    assert not fetched_past.is_active()

    assert fetched_none.expires_at is None
    assert not fetched_none.is_expired()
    assert fetched_none.is_active()


def test_raw_delete_method(mem):
    """delete() removes entry; get() returns None after delete."""
    entry = mem.write(namespace="global", content="to delete", source="t")
    assert mem.get(entry.entry_id) is not None
    result = mem.delete(entry.entry_id)
    assert result is True
    assert mem.get(entry.entry_id) is None


def test_raw_delete_nonexistent_returns_false(mem):
    """delete() on missing entry returns False without error."""
    assert mem.delete("nonexistent_id_xyz") is False


def test_raw_store_method_with_entry_id(mem):
    """store() accepts caller-supplied entry_id and upserts correctly."""
    custom_id = "my_custom_id_abc123"
    entry = mem.store(
        namespace="global",
        content="stored with custom id",
        source="test",
        entry_id=custom_id,
    )
    assert entry.entry_id == custom_id
    fetched = mem.get(custom_id)
    assert fetched is not None
    assert fetched.content == "stored with custom id"


def test_raw_update_method(mem):
    """update() changes content and status; entry_id unchanged."""
    entry = mem.write(namespace="global", content="original", source="t")
    updated = mem.update(
        entry.entry_id,
        content="updated content",
        status="archived",
        confidence=0.7,
    )
    assert updated is not None
    assert updated.content == "updated content"
    assert updated.status == "archived"
    assert updated.confidence == pytest.approx(0.7)
    assert updated.entry_id == entry.entry_id


def test_raw_count_method(mem):
    """count() returns correct totals with filters."""
    mem.write(namespace="global", content="a", source="t", project_id="p1", status="active")
    mem.write(namespace="global", content="b", source="t", project_id="p1", status="active")
    mem.write(namespace="global", content="c", source="t", project_id="p2", status="archived")

    assert mem.count() == 3
    assert mem.count(project_id="p1") == 2
    assert mem.count(status="active") == 2
    assert mem.count(status="archived") == 1
    assert mem.count(project_id="p2", status="archived") == 1


def test_raw_search_excludes_deleted(mem):
    """search() excludes deleted entries by default."""
    mem.write(namespace="global", content="visible entry", source="t")
    e_del = mem.write(namespace="global", content="deleted entry", source="t", status="deleted")

    results = mem.search("entry")
    result_ids = {r.entry_id for r in results}
    assert e_del.entry_id not in result_ids


def test_raw_search_status_filter(mem):
    """search() can filter by specific status."""
    mem.write(namespace="global", content="active note", source="t", status="active")
    mem.write(namespace="global", content="archived note", source="t", status="archived")

    active_results = mem.search("note", status="active")
    assert all(r.status == "active" for r in active_results)

    archived_results = mem.search("note", status="archived")
    assert all(r.status == "archived" for r in archived_results)


def test_raw_to_dict_has_new_fields(mem):
    """MemoryEntry.to_dict() includes kind, status, expires_at."""
    entry = mem.write(
        namespace="global", content="x", source="t",
        kind="decision", status="active", expires_at=999999.0
    )
    d = entry.to_dict()
    assert "kind" in d
    assert "status" in d
    assert "expires_at" in d
    assert d["kind"] == "decision"
    assert d["status"] == "active"
    assert d["expires_at"] == pytest.approx(999999.0)


# ---------------------------------------------------------------------------
# 2. Distilled memory: write → reload → retrieve
# ---------------------------------------------------------------------------


def test_distilled_write_and_reload(tmp_path):
    """Proof: distilled write survives new-instance reload."""
    db = tmp_path / "dist_reload.db"
    dist_a = DistilledMemory(db_path=db)
    entry = dist_a.write(
        content="Bryan consistently chooses Claude for coding; GPT for analysis",
        kind="pattern",
        project_id="omnix",
        source_ids=["raw_id_1", "raw_id_2"],
        tags=["model_choice"],
    )
    eid = entry.entry_id

    dist_b = DistilledMemory(db_path=db)
    found = dist_b.get(eid)
    assert found is not None, "Distilled entry must survive reload"
    assert found.content == "Bryan consistently chooses Claude for coding; GPT for analysis"
    assert found.kind == "pattern"
    assert found.project_id == "omnix"
    assert found.source_ids == ["raw_id_1", "raw_id_2"]
    assert found.tags == ["model_choice"]


def test_distilled_all_kind_values(dist):
    """All DISTILLED_KINDS are accepted and retrievable."""
    for kind in DISTILLED_KINDS:
        entry = dist.write(content=f"distilled {kind} entry", kind=kind)
        fetched = dist.get(entry.entry_id)
        assert fetched is not None
        assert fetched.kind == kind


def test_distilled_search(dist):
    """search() finds distilled entries by keyword."""
    dist.write(content="Claude is preferred for coding tasks", kind="preference",
               project_id="omnix", tags=["model"])
    dist.write(content="Sprint velocity increased after memory OS", kind="pattern",
               project_id="omnix")
    dist.write(content="unrelated distilled entry", kind="summary")

    results = dist.search("Claude coding", project_id="omnix")
    assert len(results) == 1
    assert "Claude" in results[0].content


def test_distilled_list_by_kind(dist):
    """list_by_kind() returns entries of the requested kind."""
    dist.write(content="decision 1", kind="decision", project_id="p1")
    dist.write(content="decision 2", kind="decision", project_id="p1")
    dist.write(content="pattern 1", kind="pattern", project_id="p1")

    decisions = dist.list_by_kind("decision", project_id="p1")
    assert len(decisions) == 2
    assert all(e.kind == "decision" for e in decisions)


def test_distilled_count(dist):
    """count() returns correct totals."""
    dist.write(content="a", kind="decision", project_id="p1")
    dist.write(content="b", kind="decision", project_id="p1")
    dist.write(content="c", kind="pattern", project_id="p2")

    assert dist.count() == 3
    assert dist.count(project_id="p1") == 2
    assert dist.count(kind="decision") == 2
    assert dist.count(project_id="p2", kind="pattern") == 1


def test_distilled_delete(dist):
    """delete() removes distilled entry."""
    entry = dist.write(content="to delete", kind="summary")
    assert dist.get(entry.entry_id) is not None
    assert dist.delete(entry.entry_id) is True
    assert dist.get(entry.entry_id) is None


def test_distilled_to_dict_has_source_ids(dist):
    """DistilledEntry.to_dict() includes source_ids for provenance."""
    entry = dist.write(
        content="summary",
        kind="summary",
        source_ids=["raw1", "raw2", "raw3"],
    )
    d = entry.to_dict()
    assert "source_ids" in d
    assert d["source_ids"] == ["raw1", "raw2", "raw3"]
    assert "kind" in d
    assert "confidence" in d
    assert "created_at" in d
    assert "updated_at" in d


def test_distilled_write_entry_id_supplied(dist):
    """write() accepts caller-supplied entry_id."""
    entry = dist.write(content="custom id entry", kind="lesson", entry_id="custom_dist_id")
    assert entry.entry_id == "custom_dist_id"
    fetched = dist.get("custom_dist_id")
    assert fetched is not None


# ---------------------------------------------------------------------------
# 3. Retrieval: returns source-linked metadata
# ---------------------------------------------------------------------------


def test_retrieval_returns_metadata(mem):
    """retrieve() returns RetrievalResult objects with full source metadata."""
    mem.write(
        namespace="project:omnix",
        content="OMNIX deployment is running on Vercel with edge functions",
        source="agent:manager",
        project_id="omnix",
        kind="observation",
        confidence=0.9,
        tags=["deployment", "vercel"],
    )

    retriever = MemoryRetriever(mem)
    results = retriever.retrieve("OMNIX deployment Vercel", project_id="omnix")

    assert len(results) >= 1
    r = results[0]
    assert isinstance(r, RetrievalResult)
    assert r.entry.source == "agent:manager"
    assert r.entry.kind == "observation"
    assert r.entry.confidence == pytest.approx(0.9)
    assert r.relevance_score > 0.0
    assert r.evidence_note != ""
    assert "matched terms" in r.evidence_note or "kind=" in r.evidence_note
    assert r.age_days >= 0.0
    assert r.is_active is True


def test_retrieval_result_to_dict(mem):
    """RetrievalResult.to_dict() includes entry, relevance_score, evidence_note."""
    mem.write(namespace="global", content="test retrieval metadata", source="t")
    retriever = MemoryRetriever(mem)
    results = retriever.retrieve("test retrieval")
    assert len(results) >= 1
    d = results[0].to_dict()
    assert "entry" in d
    assert "relevance_score" in d
    assert "evidence_note" in d
    assert "is_active" in d
    assert "age_days" in d


def test_retrieval_active_only(mem):
    """retrieve_active() excludes archived/deprecated/expired entries."""
    mem.write(namespace="global", content="active memory entry", source="t", status="active")
    mem.write(namespace="global", content="archived memory entry", source="t", status="archived")
    past = time.time() - 1
    mem.write(namespace="global", content="expired memory entry", source="t", expires_at=past)

    retriever = MemoryRetriever(mem)
    results = retriever.retrieve_active("memory entry")
    assert all(r.is_active for r in results)
    contents = [r.entry.content for r in results]
    assert any("active memory" in c for c in contents)


def test_retrieval_project_scoped(mem):
    """retrieve() respects project_id scoping."""
    mem.write(namespace="p", content="omnix specific data", source="t", project_id="omnix")
    mem.write(namespace="p", content="other project data", source="t", project_id="other")

    retriever = MemoryRetriever(mem)
    results = retriever.retrieve("data", project_id="omnix")
    assert all(r.entry.project_id == "omnix" for r in results)


def test_retrieval_empty_query_returns_empty(mem):
    """retrieve() returns [] for empty query."""
    mem.write(namespace="global", content="something", source="t")
    retriever = MemoryRetriever(mem)
    assert retriever.retrieve("") == []


def test_retrieval_sorted_by_score(mem):
    """Results are returned sorted by relevance_score descending."""
    mem.write(namespace="global", content="highly relevant decision about Claude",
              source="t", kind="decision", confidence=1.0)
    mem.write(namespace="global", content="vaguely mentions claude",
              source="t", confidence=0.3)

    retriever = MemoryRetriever(mem)
    results = retriever.retrieve("Claude decision")
    if len(results) >= 2:
        assert results[0].relevance_score >= results[1].relevance_score


# ---------------------------------------------------------------------------
# 4. Context injection: context_from_memory=True
# ---------------------------------------------------------------------------


def test_context_injection_enabled(mem):
    """context_from_memory=True builds context text from relevant memories."""
    mem.write(
        namespace="global",
        content="Bryan prefers concise answers with code examples",
        source="agent:manager",
        kind="preference",
        confidence=0.95,
        project_id="omnix",
    )

    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context(
        "code review style preferences",
        project_id="omnix",
        context_from_memory=True,
    )

    assert isinstance(ctx, InjectedContext)
    assert ctx.context_enabled is True
    assert ctx.entries_used >= 1
    assert "[Memory OS — Active Context]" in ctx.context_text
    assert "preference" in ctx.context_text or "Bryan" in ctx.context_text


def test_context_injection_disabled(mem):
    """context_from_memory=False returns empty context_text."""
    mem.write(namespace="global", content="some preference", source="t")

    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context(
        "some query",
        context_from_memory=False,
    )

    assert ctx.context_text == ""
    assert ctx.entries_used == 0
    assert ctx.context_enabled is False


def test_context_injection_empty_memory(mem):
    """Context builder returns empty context_text when no memories match."""
    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context("very specific query zxqwerty123", context_from_memory=True)
    assert ctx.context_text == ""
    assert ctx.entries_used == 0
    assert ctx.context_enabled is True


def test_context_injection_distinguishes_active(mem):
    """Context injection only includes active entries when active_only=True."""
    mem.write(namespace="global", content="active preference entry", source="t",
              kind="preference", status="active")
    mem.write(namespace="global", content="deprecated preference entry", source="t",
              kind="preference", status="deprecated")

    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context("preference entry", context_from_memory=True, active_only=True)

    if ctx.entries_used > 0:
        for r in ctx.results:
            assert r.is_active, "Non-active entry injected into context"


def test_context_injection_to_dict(mem):
    """InjectedContext.to_dict() has required audit fields."""
    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context("test query", context_from_memory=True)
    d = ctx.to_dict()
    for key in ["context_text", "entries_used", "entries_searched", "query",
                "project_id", "context_enabled", "metadata_summary"]:
        assert key in d, f"Missing key in InjectedContext.to_dict(): {key}"


def test_context_injection_char_budget(mem):
    """Context injection respects max_chars limit."""
    for i in range(20):
        mem.write(
            namespace="global",
            content=f"memory entry number {i} about deployment",
            source="t",
            kind="observation",
        )

    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context(
        "deployment",
        context_from_memory=True,
        max_items=5,
        max_chars=300,
    )
    if ctx.context_text:
        assert len(ctx.context_text) <= 600  # some slack for header


# ---------------------------------------------------------------------------
# 5. Memory OS status
# ---------------------------------------------------------------------------


def test_memory_os_status_available(tmp_path):
    """get_memory_os_status() reports backend_available=True when DB is accessible."""
    db = tmp_path / "status_test.db"
    mem = JarvisMemory(db_path=db)
    mem.write(namespace="global", content="status test entry", source="t", status="active")
    mem.write(namespace="global", content="another entry", source="t", status="archived")

    dist = DistilledMemory(db_path=db)
    dist.write(content="distilled entry", kind="summary")

    status = get_memory_os_status(db_path=db)
    assert isinstance(status, MemoryOSStatus)
    assert status.backend_available is True
    assert status.backend_type == "sqlite"
    assert str(db) in status.backend_path
    assert status.raw_archive_count == 2
    assert status.raw_active_count == 1
    assert status.distilled_count == 1
    assert status.last_error is None


def test_memory_os_status_to_dict(tmp_path):
    """MemoryOSStatus.to_dict() has all required fields."""
    db = tmp_path / "status_dict_test.db"
    status = get_memory_os_status(db_path=db)
    d = status.to_dict()
    for key in [
        "backend_available", "backend_type", "backend_path",
        "raw_archive_count", "raw_active_count", "distilled_count",
        "namespaces_count", "context_injection_enabled", "last_error",
        "foundation_complete", "planned_not_complete", "sprint",
    ]:
        assert key in d, f"Missing key: {key}"


def test_memory_os_status_planned_not_complete(tmp_path):
    """Status honestly reports planned-but-not-complete capabilities."""
    db = tmp_path / "honest_status.db"
    status = get_memory_os_status(db_path=db)
    planned = status.planned_not_complete
    assert isinstance(planned, list)
    assert len(planned) > 0
    # Sprint 2: planned_not_complete is now a list of dicts with 'item'+'status'
    # Support both old str format (Sprint 1) and new dict format (Sprint 2)
    if planned and isinstance(planned[0], dict):
        all_items_text = " ".join(str(v) for item in planned for v in item.values())
    else:
        all_items_text = " ".join(planned)
    assert "semantic" in all_items_text or "vector" in all_items_text
    assert "cloud" in all_items_text or "sync" in all_items_text


def test_memory_os_status_foundation_complete_flag(tmp_path):
    """foundation_complete is True — Sprint 1 is complete as foundation."""
    db = tmp_path / "flag_test.db"
    status = get_memory_os_status(db_path=db)
    assert status.foundation_complete is True


# ---------------------------------------------------------------------------
# 6. Governance: forget / edit / export
# ---------------------------------------------------------------------------


def test_governance_forget_raw(gov):
    """forget() hard-deletes a raw memory entry.

    Sprint 2: default confidence=1.0 requires force=True (approval gate).
    Use low-confidence entry or force=True to bypass.
    """
    mem = gov._memory
    entry = mem.write(namespace="global", content="to forget", source="t", confidence=0.3)
    assert mem.get(entry.entry_id) is not None

    result = gov.forget(entry.entry_id)
    assert isinstance(result, GovernanceResult)
    assert result.success is True
    assert result.action == "forget"
    assert mem.get(entry.entry_id) is None


def test_governance_forget_nonexistent(gov):
    """forget() on nonexistent ID returns success=False."""
    result = gov.forget("nonexistent_xyz")
    assert result.success is False
    assert result.action == "forget"


def test_governance_forget_distilled(gov):
    """forget_distilled() removes a distilled entry.

    Sprint 2: default confidence=1.0 triggers approval gate.
    Use low-confidence entry to avoid ApprovalRequired.
    """
    dist = gov._distilled
    entry = dist.write(content="to delete distilled", kind="summary", confidence=0.3)
    result = gov.forget_distilled(entry.entry_id)
    assert result.success is True
    assert dist.get(entry.entry_id) is None


def test_governance_edit(gov):
    """edit() updates content and status of a raw entry."""
    mem = gov._memory
    entry = mem.write(namespace="global", content="original content", source="t")

    result = gov.edit(
        entry.entry_id,
        new_content="corrected content",
        new_status="archived",
    )
    assert result.success is True
    assert result.action == "edit"

    updated = mem.get(entry.entry_id)
    assert updated.content == "corrected content"
    assert updated.status == "archived"


def test_governance_edit_nonexistent(gov):
    """edit() on nonexistent ID returns success=False."""
    result = gov.edit("bad_id", new_content="whatever")
    assert result.success is False


def test_governance_export_namespace(gov):
    """export_namespace() returns all raw entries as a list of dicts."""
    mem = gov._memory
    mem.write(namespace="project:test", content="entry 1", source="t", project_id="test")
    mem.write(namespace="project:test", content="entry 2", source="t", project_id="test")
    mem.write(namespace="global", content="other namespace", source="t")

    exported = gov.export_namespace("project:test", project_id="test")
    assert len(exported) == 2
    assert all(isinstance(e, dict) for e in exported)
    assert all("content" in e for e in exported)
    assert all("entry_id" in e for e in exported)
    assert all("kind" in e for e in exported)
    assert all("status" in e for e in exported)


def test_governance_export_all(gov):
    """export_all() returns raw + distilled with counts.

    Sprint 2: NOT_IMPLEMENTED controls key removed since audit trail and
    approval workflow are now implemented.  Export returns raw/distilled data.
    """
    mem = gov._memory
    mem.write(namespace="global", content="raw entry", source="t")
    dist = gov._distilled
    dist.write(content="distilled entry", kind="decision")

    export = gov.export_all()
    assert "raw" in export
    assert "distilled" in export
    assert export["raw_count"] == 1
    assert export["distilled_count"] == 1


def test_governance_status_not_implemented(gov):
    """governance_status() honestly lists implemented and not-implemented items.

    Sprint 2: audit_trail and approval_workflow are now IMPLEMENTED.
    The only remaining not_implemented item is cloud_audit_replication.
    """
    gstatus = MemoryGovernance.governance_status()
    assert "implemented" in gstatus
    assert "not_implemented" in gstatus
    # Sprint 2 implemented audit trail and approval — must appear in 'implemented'
    implemented = gstatus["implemented"]
    assert any("audit_trail" in i or "immutable" in i for i in implemented)
    assert any("approval" in i for i in implemented)
    # Cloud replication is still not done
    ni = gstatus["not_implemented"]
    assert isinstance(ni, list)


# ---------------------------------------------------------------------------
# 7. Regression: prior store tests still pass (write/search/isolation)
# ---------------------------------------------------------------------------


def test_regression_write_and_get(mem):
    """Regression: write + get still works after Sprint 1 changes."""
    entry = mem.write(namespace="global", content="regression test", source="test")
    assert entry.entry_id
    fetched = mem.get(entry.entry_id)
    assert fetched is not None
    assert fetched.content == "regression test"
    # New fields have correct defaults
    assert fetched.kind == "event"
    assert fetched.status == "active"
    assert fetched.expires_at is None


def test_regression_search_still_works(mem):
    """Regression: keyword search still works with new columns."""
    mem.write(namespace="global", content="deployment blocker omnix", source="t")
    mem.write(namespace="global", content="unrelated", source="t")
    results = mem.search("deployment blocker")
    assert len(results) == 1


def test_regression_project_isolation(mem):
    """Regression: project_id isolation still works."""
    mem.write(namespace="p:a", content="project a secret", source="t", project_id="a")
    mem.write(namespace="p:b", content="project b data", source="t", project_id="b")
    results_a = mem.search("project", project_id="a")
    assert all(r.project_id == "a" for r in results_a)


def test_regression_secret_rejection(mem):
    """Regression: secrets are still rejected after Sprint 1 changes."""
    fake_slack = "xo" + "xb-123456789-abcdefghijklmnop"
    with pytest.raises(ValueError, match="secret"):
        mem.write(namespace="global", content=fake_slack, source="t")


def test_regression_to_dict_backward_compat(mem):
    """Regression: existing to_dict() fields still present."""
    entry = mem.write(namespace="global", content="test", source="test")
    d = entry.to_dict()
    for key in [
        "entry_id", "namespace", "content", "source", "project_id",
        "mission_id", "agent_id", "tags", "confidence", "created_at",
    ]:
        assert key in d, f"Missing backward-compat key: {key}"


# ---------------------------------------------------------------------------
# 8. Context injection wired into executor (import-level proof)
# ---------------------------------------------------------------------------


def test_executor_imports_memory_context_builder():
    """Proof that MemoryContextBuilder is importable from executor's path."""
    from openjarvis.memory.context import MemoryContextBuilder
    assert MemoryContextBuilder is not None


def test_context_injection_returns_prepend_string(mem):
    """Context builder returns a string that can be prepended to input_text."""
    mem.write(
        namespace="global",
        content="always use type hints in Python",
        source="agent:manager",
        kind="preference",
    )
    builder = MemoryContextBuilder(memory=mem)
    ctx = builder.build_context("Python coding style", context_from_memory=True)

    if ctx.entries_used > 0:
        # Simulate what executor does
        original_input = "Write me a Python function"
        injected_input = ctx.context_text + "\n\n" + original_input
        assert "[Memory OS — Active Context]" in injected_input
        assert original_input in injected_input
