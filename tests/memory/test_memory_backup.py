"""Tests for Memory Backup / Export / Import (US9 Phase 10)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from openjarvis.memory.backup import (
    BackupManifest,
    backup_before_mutation,
    compute_checksum,
    export_memory,
    get_memory_backup_status,
    import_memory,
    list_backups,
    redact_entry,
    verify_checksum,
)


SAMPLE_ENTRIES = [
    {"id": "1", "type": "note", "content": "Buy groceries", "tags": ["personal"]},
    {"id": "2", "type": "task", "content": "Review PR #123", "tags": ["work"]},
    {"id": "3", "type": "secret_note", "JARVIS_SLACK_BOT_TOKEN": "xoxb-fake", "content": "config"},
]


@pytest.fixture
def tmp_backup_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("openjarvis.memory.backup._BACKUP_DIR", tmp_path)
    return tmp_path


class TestRedaction:
    def test_redacts_token_key(self):
        entry = {"JARVIS_SLACK_BOT_TOKEN": "xoxb-secret", "content": "hello"}
        result = redact_entry(entry)
        assert result["JARVIS_SLACK_BOT_TOKEN"] == "[REDACTED]"
        assert result["content"] == "hello"

    def test_redacts_api_key(self):
        entry = {"TAVILY_API_KEY": "tvly-abc123", "name": "tavily"}
        result = redact_entry(entry)
        assert result["TAVILY_API_KEY"] == "[REDACTED]"

    def test_nested_redaction(self):
        entry = {"config": {"OPENAI_API_KEY": "sk-secret", "model": "gpt-4"}}
        result = redact_entry(entry)
        assert result["config"]["OPENAI_API_KEY"] == "[REDACTED]"
        assert result["config"]["model"] == "gpt-4"

    def test_non_sensitive_passes(self):
        entry = {"id": "1", "content": "safe text", "tags": ["work"]}
        result = redact_entry(entry)
        assert result == entry


class TestChecksum:
    def test_same_data_same_checksum(self):
        data = "hello world"
        assert compute_checksum(data) == compute_checksum(data)

    def test_different_data_different_checksum(self):
        assert compute_checksum("hello") != compute_checksum("world")

    def test_verify_correct_checksum(self):
        data = "test data"
        cs = compute_checksum(data)
        assert verify_checksum(data, cs) is True

    def test_verify_incorrect_checksum_fails(self):
        assert verify_checksum("data", "wronghash") is False


class TestExport:
    def test_export_creates_file(self, tmp_backup_dir):
        result = export_memory(SAMPLE_ENTRIES[:2], source="test_export")
        assert result["ok"] is True
        assert Path(result["backup_path"]).exists()

    def test_export_redacts_sensitive(self, tmp_backup_dir):
        result = export_memory(SAMPLE_ENTRIES, source="test_redact")
        # Read file and verify token not present
        content = Path(result["backup_path"]).read_text(encoding="utf-8")
        assert "xoxb-fake" not in content
        assert result["redacted"] > 0

    def test_export_manifest_in_result(self, tmp_backup_dir):
        result = export_memory(SAMPLE_ENTRIES[:1], source="test")
        assert "manifest" in result
        assert result["manifest"]["entry_count"] == 1
        assert result["manifest"]["checksum"]

    def test_export_entries_count_correct(self, tmp_backup_dir):
        result = export_memory(SAMPLE_ENTRIES, source="count_test")
        assert result["entries_exported"] == len(SAMPLE_ENTRIES)


class TestImport:
    def test_import_roundtrip(self, tmp_backup_dir):
        export_result = export_memory(SAMPLE_ENTRIES[:2], source="roundtrip")
        backup_path = Path(export_result["backup_path"])
        import_result = import_memory(backup_path)
        assert import_result["ok"] is True
        assert import_result["entry_count"] == 2
        assert import_result["checksum_valid"] is True

    def test_import_validates_checksum(self, tmp_backup_dir):
        export_result = export_memory(SAMPLE_ENTRIES[:1], source="checksum_test")
        backup_path = Path(export_result["backup_path"])
        # Tamper with file
        content = backup_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        if len(lines) > 1:
            lines[1] = lines[1] + "TAMPERED"
            backup_path.write_text("\n".join(lines), encoding="utf-8")
        result = import_memory(backup_path, validate_checksum=True)
        assert result["ok"] is False
        assert "checksum" in result["error"].lower() or "mismatch" in result.get("error", "").lower()

    def test_import_missing_file(self, tmp_backup_dir):
        result = import_memory(tmp_backup_dir / "nonexistent.jsonl")
        assert result["ok"] is False

    def test_import_returns_entries(self, tmp_backup_dir):
        export_result = export_memory(SAMPLE_ENTRIES[:2], source="entries_test")
        import_result = import_memory(Path(export_result["backup_path"]))
        assert import_result["ok"] is True
        assert len(import_result["entries"]) == 2


class TestBackupBeforeMutation:
    def test_backup_before_mutation_creates_file(self, tmp_backup_dir):
        result = backup_before_mutation(SAMPLE_ENTRIES[:1])
        assert result["ok"] is True
        assert Path(result["backup_path"]).exists()


class TestListBackups:
    def test_list_empty_when_no_backups(self, tmp_backup_dir):
        backups = list_backups()
        assert isinstance(backups, list)

    def test_list_shows_created_backup(self, tmp_backup_dir):
        export_memory(SAMPLE_ENTRIES[:1], source="list_test")
        backups = list_backups()
        assert len(backups) >= 1


class TestMemoryBackupStatus:
    def test_status_returns_dict(self, tmp_backup_dir):
        s = get_memory_backup_status()
        assert "backup_dir" in s
        assert "backup_count" in s
        assert s["redaction_enabled"] is True
        assert s["checksum_validation"] is True
        assert s["restore_requires_approval"] is True
