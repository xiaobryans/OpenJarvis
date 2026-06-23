"""Tests for Plan 9 workspace root resolution."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from openjarvis.plan9.workspace_root import (
    workspace_index_summary,
    workspace_prefix_allowed,
    workspace_root,
)


def test_workspace_root_from_env(monkeypatch, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("hi")
    monkeypatch.setenv("OPENJARVIS_ROOT", str(tmp_path))
    workspace_root.cache_clear()
    assert workspace_root() == tmp_path.resolve()
    summary = workspace_index_summary()
    assert summary["pyproject_present"] is True
    assert summary["indexed_file_count"] >= 2
    workspace_root.cache_clear()


def test_workspace_prefix_allowlist():
    assert workspace_prefix_allowed("docs/plan9_x.md")
    assert workspace_prefix_allowed("pyproject.toml")
    assert not workspace_prefix_allowed("../etc/passwd")
    assert not workspace_prefix_allowed(".env")
