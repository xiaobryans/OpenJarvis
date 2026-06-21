"""Plan 7C — GitHub connector tests.

Covers:
  1. Connector importable and registered in ConnectorRegistry
  2. is_connected() returns True when any credential source is available
  3. is_connected() returns False when no credential source is available
  4. get_user_info() returns a safe non-secret dict
  5. get_user_info() returns connected=False when no token
  6. sync() yields Documents on successful API call
  7. sync() handles no-token gracefully (no raise, no yields)
  8. _get_github_token() resolves from env var
  9. _get_github_token() resolves from config file
  10. _get_github_token() resolves from gh CLI (skipped if gh not available)
  11. _credential_source_label() returns safe label (no token value)
  12. No secret values in any public method return
  13. Live GitHub API proof: get_user_info() returns login when credentials exist
  14. list_repos() returns safe repo metadata
  15. sync() documents have correct fields
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from openjarvis.connectors._stubs import Document, SyncStatus
from openjarvis.connectors.github import (
    GitHubConnector,
    _credential_source_label,
    _get_github_token,
)
from openjarvis.core.registry import ConnectorRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_any_credential() -> bool:
    """Return True if any GitHub credential source is available in the current env."""
    return _get_github_token() is not None


# ---------------------------------------------------------------------------
# 1. Importable and registered
# ---------------------------------------------------------------------------


def test_github_connector_importable() -> None:
    """GitHubConnector can be imported."""
    assert GitHubConnector is not None


def test_github_connector_registered_in_registry() -> None:
    """GitHubConnector is registered under 'github' in ConnectorRegistry.

    Uses importlib.reload to re-register after the autouse conftest clears the registry.
    """
    import importlib
    import openjarvis.connectors.github as _github_mod
    importlib.reload(_github_mod)
    assert ConnectorRegistry.contains("github"), (
        "'github' not found in ConnectorRegistry"
    )


def test_github_connector_id_and_display_name() -> None:
    """connector_id and display_name are correct."""
    conn = GitHubConnector()
    assert conn.connector_id == "github"
    assert conn.display_name == "GitHub"
    assert conn.auth_type == "token"


# ---------------------------------------------------------------------------
# 2–3. is_connected()
# ---------------------------------------------------------------------------


def test_is_connected_true_when_env_token(monkeypatch) -> None:
    """is_connected() returns True when GITHUB_TOKEN is set."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakefakefake0000000000000000000000000")
    conn = GitHubConnector()
    assert conn.is_connected() is True


def test_is_connected_false_when_no_credentials(tmp_path, monkeypatch) -> None:
    """is_connected() returns False when no credential source is available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # Point config dir to an empty tmp path so no github.json exists
    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH",
               tmp_path / "connectors" / "github.json"):
        # Mock gh CLI to return nothing
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            conn = GitHubConnector()
            assert conn.is_connected() is False


# ---------------------------------------------------------------------------
# 4–5. get_user_info()
# ---------------------------------------------------------------------------


def test_get_user_info_no_token_returns_safe_dict(tmp_path, monkeypatch) -> None:
    """get_user_info() returns connected=False dict (no raise) when no token."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH",
               tmp_path / "connectors" / "github.json"):
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            conn = GitHubConnector()
            result = conn.get_user_info()
    assert result["connected"] is False
    assert "error" in result
    # No secret values in output
    for v in result.values():
        if isinstance(v, str):
            assert not v.startswith("ghp_"), f"Secret-looking value in output: {v}"
            assert not v.startswith("gho_"), f"Secret-looking value in output: {v}"


def test_get_user_info_mock_api_returns_safe_fields(monkeypatch) -> None:
    """get_user_info() with mocked API returns safe fields only."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakefakefake0000000000000000000000000")

    mock_response = {
        "login": "testuser",
        "name": "Test User",
        "public_repos": 42,
        "followers": 100,
        "following": 50,
        "email": "test@example.com",  # should NOT appear in output
        "token": "should_not_be_in_output",  # should NOT appear in output
    }
    with patch("openjarvis.connectors.github._api_get", return_value=mock_response):
        conn = GitHubConnector()
        result = conn.get_user_info()

    assert result["connected"] is True
    assert result["login"] == "testuser"
    assert result["name"] == "Test User"
    assert result["public_repos"] == 42
    assert result["followers"] == 100
    # No secret fields leaked
    assert "email" not in result
    assert "token" not in result


# ---------------------------------------------------------------------------
# 6–7. sync()
# ---------------------------------------------------------------------------


def test_sync_yields_documents_when_connected(monkeypatch) -> None:
    """sync() yields Document objects when token is available and API returns data."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakefakefake0000000000000000000000000")

    mock_notifications = [
        {
            "id": "1234567",
            "subject": {"title": "Fix the bug", "type": "PullRequest", "url": "https://api.github.com/repos/foo/bar/pulls/1"},
            "reason": "mention",
            "repository": {"full_name": "foo/bar"},
            "unread": True,
            "updated_at": "2026-06-21T10:00:00Z",
        },
        {
            "id": "7654321",
            "subject": {"title": "Release v2", "type": "Release", "url": None},
            "reason": "subscribed",
            "repository": {"full_name": "baz/qux"},
            "unread": True,
            "updated_at": "2026-06-21T09:00:00Z",
        },
    ]
    with patch("openjarvis.connectors.github._api_get", return_value=mock_notifications):
        conn = GitHubConnector()
        docs = list(conn.sync())

    assert len(docs) == 2
    assert all(isinstance(d, Document) for d in docs)
    assert docs[0].source == "github"
    assert docs[0].doc_type == "notification"
    assert "foo/bar" in docs[0].content
    assert docs[0].doc_id == "github-1234567"

    # No secret values in Document fields
    for doc in docs:
        assert not doc.doc_id.startswith("ghp_")
        assert not doc.doc_id.startswith("gho_")
        for v in doc.metadata.values():
            if isinstance(v, str):
                assert not v.startswith("ghp_")
                assert not v.startswith("gho_")


def test_sync_handles_no_token_gracefully(tmp_path, monkeypatch) -> None:
    """sync() yields nothing and sets error on SyncStatus when no token available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH",
               tmp_path / "connectors" / "github.json"):
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            conn = GitHubConnector()
            docs = list(conn.sync())

    assert docs == []
    status = conn.sync_status()
    assert status.error is not None
    assert "no_token" in status.error


def test_sync_handles_api_error_gracefully(monkeypatch) -> None:
    """sync() yields nothing and records error when API call fails."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakefakefake0000000000000000000000000")

    with patch("openjarvis.connectors.github._api_get", side_effect=Exception("API timeout")):
        conn = GitHubConnector()
        docs = list(conn.sync())

    assert docs == []
    status = conn.sync_status()
    assert status.error is not None


# ---------------------------------------------------------------------------
# 8–9. _get_github_token() resolution
# ---------------------------------------------------------------------------


def test_get_github_token_from_env(monkeypatch) -> None:
    """_get_github_token() resolves GITHUB_TOKEN env var first."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_envtest")
    with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="gho_should_not_use")
        token = _get_github_token()
    assert token == "ghp_envtest"


def test_get_github_token_from_config_file(tmp_path, monkeypatch) -> None:
    """_get_github_token() falls back to github.json when env var is absent."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    config_file = tmp_path / "connectors" / "github.json"
    config_file.parent.mkdir(parents=True)
    config_file.write_text(json.dumps({"token": "ghp_fromfile"}))

    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH", config_file):
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            token = _get_github_token()

    assert token == "ghp_fromfile"


def test_get_github_token_from_gh_cli(tmp_path, monkeypatch) -> None:
    """_get_github_token() falls back to gh CLI when env and file are absent."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH",
               tmp_path / "github.json"):  # non-existent file
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="gho_fromcli\n")
            token = _get_github_token()

    assert token == "gho_fromcli"


def test_get_github_token_returns_none_when_all_missing(tmp_path, monkeypatch) -> None:
    """_get_github_token() returns None when no credential source is available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH",
               tmp_path / "github.json"):
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            token = _get_github_token()

    assert token is None


# ---------------------------------------------------------------------------
# 10. gh CLI credential resolution (live — skip if gh not available)
# ---------------------------------------------------------------------------


def test_gh_cli_credential_resolution() -> None:
    """gh auth token resolves a non-empty token from the OS keyring."""
    import shutil
    if not shutil.which("gh"):
        pytest.skip("gh CLI not available")

    import subprocess
    result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True, text=True, timeout=5,
    )
    if result.returncode != 0:
        pytest.skip("gh CLI is not authenticated")

    token = result.stdout.strip()
    assert len(token) > 10, "gh auth token returned an unusually short value"
    # The token itself must not be logged/printed — this test only checks it's non-empty


# ---------------------------------------------------------------------------
# 11. _credential_source_label() — safe, no token values
# ---------------------------------------------------------------------------


def test_credential_source_label_env(monkeypatch) -> None:
    """_credential_source_label() returns 'GITHUB_TOKEN env var' when env is set."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fake")
    label = _credential_source_label()
    assert label == "GITHUB_TOKEN env var"
    assert "ghp_" not in label  # no secret in label


def test_credential_source_label_none(tmp_path, monkeypatch) -> None:
    """_credential_source_label() returns 'none' when no credential is available."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    with patch("openjarvis.connectors.github._DEFAULT_TOKEN_PATH",
               tmp_path / "github.json"):
        with patch("openjarvis.connectors.github.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            label = _credential_source_label()
    assert label == "none"


# ---------------------------------------------------------------------------
# 12. No secret values in public method returns
# ---------------------------------------------------------------------------


def test_no_secret_in_sync_status(monkeypatch) -> None:
    """sync_status() return value contains no secret-looking strings."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakefakefake0000000000000000000000000")
    conn = GitHubConnector()
    status = conn.sync_status()
    # SyncStatus is a dataclass — convert to dict for checking
    status_dict = {
        "state": status.state,
        "items_synced": status.items_synced,
        "error": status.error,
    }
    for v in status_dict.values():
        if isinstance(v, str):
            assert not v.startswith("ghp_"), f"Secret in sync_status: {v}"
            assert not v.startswith("gho_"), f"Secret in sync_status: {v}"


# ---------------------------------------------------------------------------
# 13. Live GitHub API proof (requires real credentials)
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_get_user_info_returns_login() -> None:
    """LIVE: get_user_info() returns a real login from the GitHub API.

    Skipped if no GitHub credential is available.
    """
    if not _has_any_credential():
        pytest.skip("No GitHub credential available — skipping live test")

    conn = GitHubConnector()
    assert conn.is_connected(), "is_connected() returned False despite credential available"

    info = conn.get_user_info()
    assert info["connected"] is True, f"get_user_info returned connected=False: {info}"
    assert info["login"], f"get_user_info returned empty login: {info}"
    assert isinstance(info["public_repos"], int)
    assert info["credential_source"] != "none"
    # No secret values in output
    for v in info.values():
        if isinstance(v, str):
            assert not v.startswith("ghp_"), f"Secret-looking value in output: {v}"
            assert not v.startswith("gho_"), f"Secret-looking value in output: {v}"


# ---------------------------------------------------------------------------
# 14. list_repos() — safe metadata
# ---------------------------------------------------------------------------


@pytest.mark.live
def test_live_list_repos_returns_safe_metadata() -> None:
    """LIVE: list_repos() returns safe repo metadata without secret values."""
    if not _has_any_credential():
        pytest.skip("No GitHub credential available — skipping live test")

    conn = GitHubConnector()
    result = conn.list_repos(limit=5)
    assert result["connected"] is True
    assert isinstance(result["repos"], list)
    for repo in result["repos"]:
        assert "full_name" in repo
        assert "private" in repo
        # No token/secret fields
        assert "token" not in repo
        assert "password" not in repo


# ---------------------------------------------------------------------------
# 15. sync() Document fields correctness
# ---------------------------------------------------------------------------


def test_sync_document_fields(monkeypatch) -> None:
    """sync() Documents have all required fields set correctly."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_fakefakefake0000000000000000000000000")

    mock_notifications = [
        {
            "id": "999",
            "subject": {"title": "CI failure", "type": "CheckSuite", "url": None},
            "reason": "ci_activity",
            "repository": {"full_name": "org/repo"},
            "unread": True,
            "updated_at": "2026-06-21T00:00:00Z",
        },
    ]
    with patch("openjarvis.connectors.github._api_get", return_value=mock_notifications):
        conn = GitHubConnector()
        docs = list(conn.sync())

    assert len(docs) == 1
    doc = docs[0]
    assert doc.source == "github"
    assert doc.doc_type == "notification"
    assert doc.doc_id == "github-999"
    assert "ci_activity" in doc.content or "org/repo" in doc.content
    assert doc.metadata["reason"] == "ci_activity"
    assert doc.metadata["repo"] == "org/repo"
    assert doc.metadata["unread"] is True
