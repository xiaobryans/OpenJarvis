"""Tests for canonical local env loader."""

from __future__ import annotations

import os

import pytest

from openjarvis.core.env_loader import (
    find_project_root,
    load_local_env,
    provider_key_status_table,
)


def test_find_project_root():
    root = find_project_root()
    assert (root / "pyproject.toml").is_file()


def test_load_local_env_sets_openrouter_if_in_dotenv():
    """If .env exists with OPENROUTER_API_KEY, loader must surface PRESENT."""
    root = find_project_root()
    if not (root / ".env").is_file():
        pytest.skip(".env not present in workspace")
    summary = load_local_env(project_root=root)
    assert summary["project_root"] == str(root)
    table = provider_key_status_table()
    # At least one provider key should be present when Bryan's .env is configured
    statuses = [v["status"] for v in table.values()]
    assert "PRESENT" in statuses, "Expected at least one provider key PRESENT from .env"


def test_provider_key_status_never_returns_values():
    table = provider_key_status_table()
    for entry in table.values():
        assert entry["status"] in ("PRESENT", "MISSING")
        assert "value" not in entry
        for v in entry.values():
            if isinstance(v, str) and v.startswith("sk-"):
                pytest.fail("Secret value leaked in status table")
