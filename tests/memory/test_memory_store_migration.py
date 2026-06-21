"""Plan 7C — SQLite Memory Store Schema Migration Tests.

Covers:
  1. Fresh DB — all columns present from _init_db (no migration needed)
  2. Old DB missing kind/status/expires_at — migration adds all three
  3. Rerunning migration on already-migrated DB — idempotent, no error
  4. Data preservation — existing rows survive migration with correct defaults
  5. Startup compatibility — write/search/read works on a migrated DB
  6. Backup created when existing data exists and columns are missing
  7. No backup created for empty DB (no rows to lose)
  8. Migration handles partially-migrated DB (some columns present, some missing)
  9. _row_to_entry handles rows missing kind/status/expires_at columns (defensive)
  10. Live DB path is the expected default (~/.jarvis/memory.db)
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import List

import pytest

from openjarvis.memory.store import JarvisMemory, MemoryEntry, _DEFAULT_DB


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_old_schema_db(db_path: Path, rows: int = 0) -> None:
    """Create a DB with the original schema (no kind/status/expires_at columns).

    This simulates a database created before the Plan 7 migration sprint.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE memory_entries (
            entry_id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '',
            project_id TEXT NOT NULL DEFAULT '',
            mission_id TEXT,
            agent_id TEXT,
            tags TEXT NOT NULL DEFAULT '[]',
            confidence REAL NOT NULL DEFAULT 1.0,
            created_at REAL NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_namespace ON memory_entries(namespace)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_project ON memory_entries(project_id)")

    for i in range(rows):
        conn.execute(
            "INSERT INTO memory_entries "
            "(entry_id, namespace, content, source, project_id, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"pre_migration_id_{i:04d}",
                f"namespace_{i % 3}",
                f"Pre-migration content {i}",
                "legacy",
                f"project_{i % 2}",
                time.time() - (rows - i),
            ),
        )
    conn.commit()
    conn.close()


def _get_columns(db_path: Path) -> List[str]:
    conn = sqlite3.connect(str(db_path))
    cols = [row[1] for row in conn.execute("PRAGMA table_info(memory_entries)")]
    conn.close()
    return cols


def _get_row_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# 1. Fresh DB — all columns present
# ---------------------------------------------------------------------------


def test_fresh_db_has_all_columns(tmp_path: Path) -> None:
    """A freshly created DB has kind, status, and expires_at from _init_db."""
    db = tmp_path / "fresh.db"
    _ = JarvisMemory(db_path=db)
    cols = _get_columns(db)
    assert "kind" in cols, "kind column missing from fresh DB"
    assert "status" in cols, "status column missing from fresh DB"
    assert "expires_at" in cols, "expires_at column missing from fresh DB"


def test_fresh_db_no_migration_needed(tmp_path: Path) -> None:
    """A fresh DB initialised twice causes no errors and requires no migration."""
    db = tmp_path / "fresh2.db"
    m1 = JarvisMemory(db_path=db)
    m2 = JarvisMemory(db_path=db)
    # Both instances should work normally
    e = m1.write("global", "hello", source="test")
    fetched = m2.get(e.entry_id)
    assert fetched is not None
    assert fetched.content == "hello"


# ---------------------------------------------------------------------------
# 2. Old DB missing all three columns → migration adds them
# ---------------------------------------------------------------------------


def test_old_db_migration_adds_columns(tmp_path: Path) -> None:
    """Old schema DB (no kind/status/expires_at) gets all columns after JarvisMemory init."""
    db = tmp_path / "old.db"
    _create_old_schema_db(db, rows=0)

    cols_before = _get_columns(db)
    assert "kind" not in cols_before
    assert "status" not in cols_before
    assert "expires_at" not in cols_before

    _ = JarvisMemory(db_path=db)

    cols_after = _get_columns(db)
    assert "kind" in cols_after, "kind not added by migration"
    assert "status" in cols_after, "status not added by migration"
    assert "expires_at" in cols_after, "expires_at not added by migration"


# ---------------------------------------------------------------------------
# 3. Idempotent — running migration twice does not raise
# ---------------------------------------------------------------------------


def test_migration_is_idempotent(tmp_path: Path) -> None:
    """Calling JarvisMemory twice on an old DB runs the migration safely both times."""
    db = tmp_path / "old_twice.db"
    _create_old_schema_db(db, rows=5)

    # First init — runs migration
    m1 = JarvisMemory(db_path=db)
    # Second init — migration already done; should not raise
    m2 = JarvisMemory(db_path=db)

    cols = _get_columns(db)
    assert "kind" in cols
    assert "status" in cols
    assert "expires_at" in cols


# ---------------------------------------------------------------------------
# 4. Data preservation — existing rows survive with correct defaults
# ---------------------------------------------------------------------------


def test_migration_preserves_existing_rows(tmp_path: Path) -> None:
    """Pre-migration rows are preserved with default kind='event', status='active'."""
    db = tmp_path / "preserved.db"
    _create_old_schema_db(db, rows=10)

    assert _get_row_count(db) == 10

    _ = JarvisMemory(db_path=db)

    assert _get_row_count(db) == 10, "Rows were lost during migration!"

    # Verify defaults were applied
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT entry_id, kind, status, expires_at FROM memory_entries").fetchall()
    conn.close()

    for entry_id, kind, status, expires_at in rows:
        assert kind == "event", f"Row {entry_id}: expected kind='event', got '{kind}'"
        assert status == "active", f"Row {entry_id}: expected status='active', got '{status}'"
        assert expires_at is None, f"Row {entry_id}: expected expires_at=NULL, got {expires_at}"


def test_migration_preserves_content_and_namespace(tmp_path: Path) -> None:
    """Pre-migration row content, namespace, and project_id are unchanged after migration."""
    db = tmp_path / "content_check.db"
    _create_old_schema_db(db, rows=3)

    conn = sqlite3.connect(str(db))
    original = conn.execute(
        "SELECT entry_id, content, namespace, project_id FROM memory_entries ORDER BY entry_id"
    ).fetchall()
    conn.close()

    _ = JarvisMemory(db_path=db)

    conn = sqlite3.connect(str(db))
    migrated = conn.execute(
        "SELECT entry_id, content, namespace, project_id FROM memory_entries ORDER BY entry_id"
    ).fetchall()
    conn.close()

    assert original == migrated, "Content/namespace/project_id changed during migration!"


# ---------------------------------------------------------------------------
# 5. Startup compatibility — write/search/read works on migrated DB
# ---------------------------------------------------------------------------


def test_write_and_search_after_migration(tmp_path: Path) -> None:
    """After migrating an old DB, write/search/read all function correctly."""
    db = tmp_path / "compat.db"
    _create_old_schema_db(db, rows=5)

    mem = JarvisMemory(db_path=db)

    # Can write new entries with kind/status fields
    entry = mem.write(
        "project:omnix",
        "Post-migration note about Plan 7C",
        source="test",
        kind="decision",
        status="active",
        tags=["plan7c", "migration"],
        project_id="omnix",
    )
    assert entry.kind == "decision"
    assert entry.status == "active"

    # Can retrieve the new entry
    fetched = mem.get(entry.entry_id)
    assert fetched is not None
    assert fetched.content == "Post-migration note about Plan 7C"
    assert fetched.kind == "decision"
    assert fetched.status == "active"

    # Can search across migrated + new entries
    results = mem.search("migration note", project_id="omnix")
    assert len(results) >= 1
    assert any("Plan 7C" in r.content for r in results)

    # Pre-migration rows are still accessible
    all_entries = mem.list_by_namespace("namespace_0")
    assert len(all_entries) >= 1


def test_kind_status_filter_works_after_migration(tmp_path: Path) -> None:
    """Filtering by status works on a migrated DB."""
    db = tmp_path / "filter.db"
    _create_old_schema_db(db, rows=3)

    mem = JarvisMemory(db_path=db)

    # All pre-migration rows default to status='active'
    results = mem.search("content", status="active")
    assert len(results) >= 3

    # Archived entries are not included in active searches
    mem.write("global", "archived note", source="test", status="archived")
    active_results = mem.search("note", status="active")
    for r in active_results:
        assert r.status == "active", f"Non-active entry returned: status={r.status}"


# ---------------------------------------------------------------------------
# 6. Backup created when existing data + missing columns
# ---------------------------------------------------------------------------


def test_backup_created_for_existing_data(tmp_path: Path) -> None:
    """A timestamped backup file is created before migrating a DB with existing rows."""
    db = tmp_path / "backup_test.db"
    _create_old_schema_db(db, rows=10)

    backups_before = list(tmp_path.glob("backup_test.db.backup_*"))
    assert len(backups_before) == 0

    _ = JarvisMemory(db_path=db)

    backups_after = list(tmp_path.glob("backup_test.db.backup_*"))
    assert len(backups_after) == 1, (
        f"Expected 1 backup file, found {len(backups_after)}: {backups_after}"
    )

    # Backup is a valid SQLite file with original schema and data
    backup_path = backups_after[0]
    conn = sqlite3.connect(str(backup_path))
    backup_cols = [row[1] for row in conn.execute("PRAGMA table_info(memory_entries)")]
    backup_count = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    conn.close()

    # Backup has the OLD schema (pre-migration)
    assert "kind" not in backup_cols, "Backup should have pre-migration schema"
    assert backup_count == 10, f"Backup should have 10 rows, got {backup_count}"


# ---------------------------------------------------------------------------
# 7. No backup created for empty DB
# ---------------------------------------------------------------------------


def test_no_backup_for_empty_old_db(tmp_path: Path) -> None:
    """No backup is created when migrating an empty old-schema DB (no rows to lose)."""
    db = tmp_path / "empty_old.db"
    _create_old_schema_db(db, rows=0)

    _ = JarvisMemory(db_path=db)

    backups = list(tmp_path.glob("empty_old.db.backup_*"))
    assert len(backups) == 0, (
        f"Unexpected backup for empty DB: {backups}"
    )


# ---------------------------------------------------------------------------
# 8. Partially-migrated DB (e.g. kind present, status/expires_at missing)
# ---------------------------------------------------------------------------


def test_partial_migration_adds_remaining_columns(tmp_path: Path) -> None:
    """A DB with only 'kind' column gets 'status' and 'expires_at' added correctly."""
    db = tmp_path / "partial.db"
    _create_old_schema_db(db, rows=5)

    # Manually add only 'kind' (simulates partial migration from a previous run)
    conn = sqlite3.connect(str(db))
    conn.execute("ALTER TABLE memory_entries ADD COLUMN kind TEXT NOT NULL DEFAULT 'event'")
    conn.commit()
    conn.close()

    cols_before = _get_columns(db)
    assert "kind" in cols_before
    assert "status" not in cols_before
    assert "expires_at" not in cols_before

    _ = JarvisMemory(db_path=db)

    cols_after = _get_columns(db)
    assert "kind" in cols_after
    assert "status" in cols_after
    assert "expires_at" in cols_after

    # Data still intact
    assert _get_row_count(db) == 5


# ---------------------------------------------------------------------------
# 9. _row_to_entry defensive fallback for rows missing columns
# ---------------------------------------------------------------------------


def test_row_to_entry_handles_missing_columns(tmp_path: Path) -> None:
    """_row_to_entry falls back to defaults when kind/status columns are absent in result row."""
    db = tmp_path / "defensive.db"
    _create_old_schema_db(db, rows=2)

    # Before migration, directly read via the old connection (columns absent)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM memory_entries LIMIT 1").fetchone()
    conn.close()

    # _row_to_entry should not raise — uses defensive 'in keys' check
    entry = JarvisMemory._row_to_entry(row)
    assert entry.kind == "event"
    assert entry.status == "active"
    assert entry.expires_at is None


# ---------------------------------------------------------------------------
# 10. Default DB path
# ---------------------------------------------------------------------------


def test_default_db_path() -> None:
    """_DEFAULT_DB points to ~/.jarvis/memory.db."""
    expected = Path.home() / ".jarvis" / "memory.db"
    assert _DEFAULT_DB == expected, f"Default DB path mismatch: {_DEFAULT_DB}"


def test_live_db_migration_if_exists() -> None:
    """If the live ~/.jarvis/memory.db exists, opening JarvisMemory() migrates it safely.

    This test is non-destructive: it opens the live DB (creating a backup if needed),
    verifies all three columns are present, and confirms row count is preserved.
    Skipped if the DB doesn't exist yet (fresh environment).
    """
    live_db = Path.home() / ".jarvis" / "memory.db"
    if not live_db.exists():
        pytest.skip("No live ~/.jarvis/memory.db — skipping live migration test")

    conn = sqlite3.connect(str(live_db))
    cols_before = [row[1] for row in conn.execute("PRAGMA table_info(memory_entries)")]
    count_before = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    conn.close()

    # Open JarvisMemory — this triggers migration if needed
    mem = JarvisMemory()

    conn = sqlite3.connect(str(live_db))
    cols_after = [row[1] for row in conn.execute("PRAGMA table_info(memory_entries)")]
    count_after = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    conn.close()

    assert "kind" in cols_after, "kind column missing after live migration"
    assert "status" in cols_after, "status column missing after live migration"
    assert "expires_at" in cols_after, "expires_at column missing after live migration"
    assert count_after == count_before, (
        f"Row count changed: {count_before} → {count_after}"
    )

    # A backup should exist if we had rows and missing columns
    had_missing = any(c not in cols_before for c in ["kind", "status", "expires_at"])
    if had_missing and count_before > 0:
        backups = list(live_db.parent.glob("memory.db.backup_*"))
        assert len(backups) >= 1, "Backup should have been created for live DB migration"
