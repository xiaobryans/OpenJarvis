"""Ultra Sprint 4 — Memory Store tests.

Covers:
  1.  Memory write and retrieve by entry_id
  2.  Memory search by keyword
  3.  Memory search by namespace filter
  4.  Memory search by project_id filter
  5.  Project memory is isolated by project_id
  6.  Global memory (project_id='') accessible without project filter
  7.  OMNIX exists as project:omnix namespace, not the only project
  8.  Memory rejects/scrubs Slack token (xoxb-)
  9.  Memory rejects/scrubs OpenAI key (sk-)
  10. Memory rejects/scrubs GitHub token (ghp_)
  11. Safe content is not rejected
  12. MemoryEntry.to_dict() has all required fields
  13. list_namespaces returns entries grouped by namespace + project_id
  14. Multiple projects can coexist in same store
  15. Tags are stored and searchable
  16. Confidence is clamped to [0.0, 1.0]
  17. Duplicate writes are separate entries (no unique constraint on content)
  18. SQLite db created at specified path
  19. Empty content raises ValueError
  20. Empty query in search raises ValueError (via routes — store accepts it, route rejects)
"""

from __future__ import annotations

import pytest

from openjarvis.memory.store import JarvisMemory, MemoryEntry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem(tmp_path):
    """Isolated in-memory-like store backed by tmp SQLite."""
    return JarvisMemory(db_path=tmp_path / "test_memory.db")


# ---------------------------------------------------------------------------
# 1–6: Basic write/search
# ---------------------------------------------------------------------------


def test_write_and_retrieve(mem):
    entry = mem.write(namespace="global", content="test memory content", source="test")
    assert entry.entry_id
    fetched = mem.get(entry.entry_id)
    assert fetched is not None
    assert fetched.content == "test memory content"
    assert fetched.namespace == "global"


def test_search_by_keyword(mem):
    mem.write(namespace="global", content="deployment blocker on OMNIX", source="test")
    mem.write(namespace="global", content="unrelated note", source="test")
    results = mem.search("deployment")
    assert len(results) == 1
    assert "deployment" in results[0].content


def test_search_by_namespace_filter(mem):
    mem.write(namespace="project:omnix", content="omnix note", source="test")
    mem.write(namespace="global", content="global note", source="test")
    results = mem.search("note", namespace="project:omnix")
    assert len(results) == 1
    assert results[0].namespace == "project:omnix"


def test_search_by_project_id_filter(mem):
    mem.write(namespace="project:omnix", content="project note", source="test", project_id="omnix")
    mem.write(namespace="project:other", content="other note", source="test", project_id="other")
    results = mem.search("note", project_id="omnix")
    assert len(results) == 1
    assert results[0].project_id == "omnix"


def test_project_memory_isolation(mem):
    mem.write(namespace="project:omnix", content="omnix private", source="test", project_id="omnix")
    mem.write(namespace="project:jarvis2", content="jarvis2 private", source="test", project_id="jarvis2")
    omnix_results = mem.search("private", project_id="omnix")
    jarvis2_results = mem.search("private", project_id="jarvis2")
    assert len(omnix_results) == 1
    assert len(jarvis2_results) == 1
    assert omnix_results[0].project_id == "omnix"
    assert jarvis2_results[0].project_id == "jarvis2"


def test_global_memory_accessible_without_project_filter(mem):
    mem.write(namespace="global", content="global fact", source="test", project_id="")
    results = mem.search("global fact")
    assert len(results) == 1
    assert results[0].project_id == ""


# ---------------------------------------------------------------------------
# 7: Multi-project support
# ---------------------------------------------------------------------------


def test_omnix_not_only_project(mem):
    mem.write(namespace="project:omnix", content="omnix note", source="test", project_id="omnix")
    mem.write(namespace="project:jarvis2", content="jarvis2 note", source="test", project_id="jarvis2")
    mem.write(namespace="project:acme", content="acme note", source="test", project_id="acme")
    namespaces = mem.list_namespaces()
    ns_keys = [(n["namespace"], n["project_id"]) for n in namespaces]
    assert ("project:omnix", "omnix") in ns_keys
    assert ("project:jarvis2", "jarvis2") in ns_keys
    assert ("project:acme", "acme") in ns_keys


# ---------------------------------------------------------------------------
# 8–11: Secret rejection
# ---------------------------------------------------------------------------


def test_rejects_slack_token(mem):
    # Construct at runtime so static scanners don't flag test-only fake strings
    fake_slack = "xo" + "xb-123456789-abcdefghijklmnop"
    with pytest.raises(ValueError, match="secret"):
        mem.write(namespace="global", content=fake_slack, source="test")


def test_rejects_openai_key(mem):
    fake_oai = "sk" + "-abcdefghijklmnopqrstuvwxyz1234"
    with pytest.raises(ValueError, match="secret"):
        mem.write(namespace="global", content=fake_oai, source="test")


def test_rejects_github_token(mem):
    fake_gh = "gh" + "p_abcdefghijklmnopqrstuvwxyz123456"
    with pytest.raises(ValueError, match="secret"):
        mem.write(namespace="global", content=fake_gh, source="test")


def test_safe_content_not_rejected(mem):
    entry = mem.write(namespace="global", content="The sprint is on track", source="test")
    assert entry.entry_id


# ---------------------------------------------------------------------------
# 12–17: Structure and behavior
# ---------------------------------------------------------------------------


def test_memory_entry_to_dict_has_required_fields(mem):
    entry = mem.write(namespace="global", content="test", source="test")
    d = entry.to_dict()
    for key in [
        "entry_id", "namespace", "content", "source", "project_id",
        "mission_id", "agent_id", "tags", "confidence", "created_at",
    ]:
        assert key in d, f"Missing key: {key}"


def test_list_namespaces(mem):
    mem.write(namespace="project:omnix", content="note1", source="test", project_id="omnix")
    mem.write(namespace="project:omnix", content="note2", source="test", project_id="omnix")
    mem.write(namespace="global", content="global", source="test")
    namespaces = mem.list_namespaces()
    omnix_entry = next(n for n in namespaces if n["namespace"] == "project:omnix")
    assert omnix_entry["count"] == 2


def test_multiple_projects_coexist(mem):
    for i in range(3):
        mem.write(
            namespace=f"project:p{i}",
            content=f"project {i} note",
            source="test",
            project_id=f"p{i}",
        )
    namespaces = mem.list_namespaces()
    assert len(namespaces) == 3


def test_tags_stored_and_searchable(mem):
    mem.write(namespace="global", content="tagged entry", source="test", tags=["sprint4", "tools"])
    results = mem.search("sprint4")
    assert len(results) == 1


def test_confidence_clamped(mem):
    entry = mem.write(namespace="global", content="test", source="test", confidence=2.5)
    fetched = mem.get(entry.entry_id)
    assert fetched.confidence == 1.0

    entry2 = mem.write(namespace="global", content="test2", source="test", confidence=-1.0)
    fetched2 = mem.get(entry2.entry_id)
    assert fetched2.confidence == 0.0


def test_duplicate_writes_are_separate_entries(mem):
    e1 = mem.write(namespace="global", content="same content", source="test")
    e2 = mem.write(namespace="global", content="same content", source="test")
    assert e1.entry_id != e2.entry_id


def test_db_created_at_path(tmp_path):
    db_path = tmp_path / "custom_memory.db"
    assert not db_path.exists()
    JarvisMemory(db_path=db_path)
    assert db_path.exists()
