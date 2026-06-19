"""Tests for Obsidian knowledge mirror — export, frontmatter, redaction, idempotency."""

from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from openjarvis.knowledge.obsidian_mirror import ObsidianMirror, VaultNote, redact


class TestRedaction:
    def test_redacts_slack_bot_token(self):
        text = "Token: xoxb-12345-67890-abcdefghijk is secret"
        assert "[REDACTED]" in redact(text)
        assert "xoxb-" not in redact(text)

    def test_redacts_openai_key(self):
        text = "Key: sk-abcdefghijklmnopqrstuvwxyz1234567890"
        assert "[REDACTED]" in redact(text)

    def test_redacts_aws_key(self):
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        assert "[REDACTED]" in redact(text)

    def test_does_not_alter_safe_text(self):
        text = "Sprint summary: all tests passed. No credentials."
        result = redact(text)
        assert result == text

    def test_redacts_password_field(self):
        text = "password: mysecretpassword123"
        result = redact(text)
        assert "[REDACTED]" in result


class TestObsidianMirrorBasic:
    def test_creates_vault_dir(self, tmp_path):
        vault = tmp_path / "vault"
        mirror = ObsidianMirror(vault_path=vault)
        note = VaultNote(title="Test Note", body="Hello world", folder="")
        path = mirror.write_note(note)
        assert vault.exists()
        assert path.exists()

    def test_frontmatter_fields_present(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        note = VaultNote(
            title="My Note",
            body="Content here",
            source="jarvis-test",
            project="openjarvis",
            status="DAILY_DRIVER_ACCEPT",
            tags=["test", "sprint"],
            trace_id="trace-abc123",
        )
        path = mirror.write_note(note)
        content = path.read_text()
        assert "title:" in content
        assert "date:" in content
        assert "source:" in content
        assert "project:" in content
        assert "status:" in content
        assert "trace_id:" in content
        assert "tags:" in content

    def test_idempotent_write(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        note = VaultNote(title="Idempotent", body="First write")
        path1 = mirror.write_note(note)
        note2 = VaultNote(title="Idempotent", body="Second write")
        path2 = mirror.write_note(note2)
        # Same filename (slug)
        assert path1 == path2
        # Content is latest
        assert "Second write" in path2.read_text()

    def test_vault_path_from_env(self, tmp_path):
        vault = tmp_path / "env-vault"
        with mock.patch.dict(os.environ, {"JARVIS_OBSIDIAN_VAULT": str(vault)}):
            mirror = ObsidianMirror()
        assert mirror.vault_path == vault

    def test_default_vault_path_fallback(self):
        with mock.patch.dict(os.environ, {"JARVIS_OBSIDIAN_VAULT": ""}):
            mirror = ObsidianMirror()
        expected = Path.home() / ".jarvis" / "obsidian-vault"
        assert mirror.vault_path == expected

    def test_folder_created_on_write(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        note = VaultNote(title="Sprint note", body="body", folder="sprints")
        path = mirror.write_note(note)
        assert (tmp_path / "v" / "sprints").exists()
        assert path.parent.name == "sprints"


class TestObsidianExportTypes:
    def test_export_sprint_summary(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        path = mirror.export_sprint_summary(
            sprint_name="Cloud-Memory-Sprint",
            body="All parts completed.",
            project="openjarvis",
        )
        assert path.exists()
        content = path.read_text()
        assert "Sprint Summary" in content
        assert "sprint" in path.parent.name

    def test_export_accepted_decisions(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        decisions = [
            {"title": "Use SQLite fallback", "status": "DAILY_DRIVER_ACCEPT", "notes": "Verified."},
        ]
        path = mirror.export_accepted_decisions(decisions)
        assert path.exists()
        content = path.read_text()
        assert "Use SQLite fallback" in content
        assert "DAILY_DRIVER_ACCEPT" in content

    def test_export_blocker_ledger(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        blockers = [
            {
                "item": "AWS credentials",
                "owner": "Bryan",
                "priority": "high",
                "status": "BLOCKED_CREDENTIALS",
                "blocks_sprint": False,
                "blocks_final": False,
                "clearing_steps": "Set AWS env vars",
            }
        ]
        path = mirror.export_blocker_ledger(blockers)
        assert path.exists()
        content = path.read_text()
        assert "AWS credentials" in content
        assert "BLOCKED_CREDENTIALS" in content

    def test_export_redacts_secrets_in_body(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        note = VaultNote(
            title="Secret test",
            body="Token: xoxb-12345-67890-abcdefghijk",
        )
        path = mirror.write_note(note)
        content = path.read_text()
        assert "xoxb-" not in content
        assert "[REDACTED]" in content

    def test_list_notes_empty_when_no_vault(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "nonexistent")
        notes = mirror.list_notes()
        assert notes == []

    def test_vault_summary_when_empty(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        summary = mirror.get_vault_summary()
        assert summary["vault_exists"] is False

    def test_vault_summary_after_writes(self, tmp_path):
        mirror = ObsidianMirror(vault_path=tmp_path / "v")
        mirror.write_note(VaultNote(title="A", body="body"))
        mirror.write_note(VaultNote(title="B", body="body", folder="ops"))
        summary = mirror.get_vault_summary()
        assert summary["vault_exists"] is True
        assert summary["note_count"] == 2
