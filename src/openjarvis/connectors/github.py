"""GitHub connector — read-only REST API access via authenticated token.

Credential resolution (in priority order):
  1. ``GITHUB_TOKEN`` environment variable
  2. ``~/.openjarvis/connectors/github.json``  ({"token": "..."})
  3. ``gh auth token`` via subprocess (OS keyring / GitHub CLI)

All operations are read-only. No writes, no PR creation, no push.
No secret values are returned in any public method output.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

import httpx

from openjarvis.connectors._stubs import BaseConnector, Document, SyncStatus
from openjarvis.core.config import DEFAULT_CONFIG_DIR
from openjarvis.core.registry import ConnectorRegistry

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_DEFAULT_TOKEN_PATH = DEFAULT_CONFIG_DIR / "connectors" / "github.json"


# ---------------------------------------------------------------------------
# Token resolution
# ---------------------------------------------------------------------------


def _get_github_token() -> Optional[str]:
    """Return a GitHub token from available credential sources.

    Priority:
      1. ``GITHUB_TOKEN`` env var
      2. ``~/.openjarvis/connectors/github.json``
      3. ``gh auth token`` (GitHub CLI, stores token in OS keyring)

    Returns ``None`` if no credential source is available.
    Never prints or logs the token value.
    """
    # 1. Env var
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        return token

    # 2. Config file
    try:
        if _DEFAULT_TOKEN_PATH.exists():
            data = json.loads(_DEFAULT_TOKEN_PATH.read_text(encoding="utf-8"))
            t = data.get("token", "").strip()
            if t:
                return t
    except Exception:
        pass

    # 3. gh CLI (uses OS keyring — no secret written to disk by this code)
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            t = result.stdout.strip()
            if t:
                return t
    except Exception:
        pass

    return None


def _credential_source_label() -> str:
    """Return a human-readable label for the active credential source (no token value)."""
    if os.environ.get("GITHUB_TOKEN", "").strip():
        return "GITHUB_TOKEN env var"
    if _DEFAULT_TOKEN_PATH.exists():
        try:
            data = json.loads(_DEFAULT_TOKEN_PATH.read_text(encoding="utf-8"))
            if data.get("token", "").strip():
                return "github.json config file"
        except Exception:
            pass
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return "gh CLI keyring"
    except Exception:
        pass
    return "none"


# ---------------------------------------------------------------------------
# Low-level API helper
# ---------------------------------------------------------------------------


def _api_get(path: str, token: str, params: Optional[Dict[str, str]] = None) -> Any:
    """Perform a read-only GET request to the GitHub REST API."""
    resp = httpx.get(
        f"{_GITHUB_API}/{path.lstrip('/')}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        params=params or {},
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Connector
# ---------------------------------------------------------------------------


@ConnectorRegistry.register("github")
class GitHubConnector(BaseConnector):
    """Read-only GitHub connector using the GitHub REST API.

    Credential sources (in order of preference):
      1. GITHUB_TOKEN env var
      2. ~/.openjarvis/connectors/github.json
      3. gh CLI auth token (OS keyring)

    Safe operations only — no writes, no PR creation, no push.
    """

    connector_id = "github"
    display_name = "GitHub"
    auth_type = "token"

    def __init__(self) -> None:
        self._status = SyncStatus()

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        """True if any token credential source resolves successfully."""
        return _get_github_token() is not None

    def disconnect(self) -> None:
        """No-op: token is managed by external credential source."""

    def sync(
        self,
        *,
        since: Optional[datetime] = None,
        cursor: Optional[str] = None,
    ) -> Iterator[Document]:
        """Yield Documents for unread GitHub notifications (read-only)."""
        token = _get_github_token()
        if not token:
            self._status.error = "no_token: no GitHub credential found"
            return

        params: Dict[str, str] = {"all": "false"}
        if since is not None:
            params["since"] = since.isoformat() + "Z"

        try:
            notifications = _api_get("/notifications", token, params)
        except Exception as exc:
            self._status.error = str(exc)
            logger.warning("GitHub sync failed: %s", exc)
            return

        count = 0
        for notif in notifications:
            subject = notif.get("subject", {})
            repo = notif.get("repository", {}).get("full_name", "")
            reason = notif.get("reason", "")
            notif_id = str(notif.get("id", ""))
            title = subject.get("title", "")
            updated_at = notif.get("updated_at", "")

            ts = datetime.now()
            if updated_at:
                try:
                    ts = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                except ValueError:
                    pass

            yield Document(
                doc_id=f"github-{notif_id}",
                source="github",
                doc_type="notification",
                content=f"Reason: {reason}, Repository: {repo}",
                title=title,
                timestamp=ts,
                url=subject.get("url"),
                metadata={
                    "reason": reason,
                    "repo": repo,
                    "type": subject.get("type", ""),
                    "unread": notif.get("unread", True),
                    "credential_source": _credential_source_label(),
                },
            )
            count += 1

        self._status.items_synced += count
        self._status.last_sync = datetime.now()
        self._status.state = "idle"
        logger.info("GitHub sync complete: %d notifications", count)

    def sync_status(self) -> SyncStatus:
        return self._status

    # ------------------------------------------------------------------
    # Public read-only helpers
    # ------------------------------------------------------------------

    def get_user_info(self) -> Dict[str, Any]:
        """Fetch authenticated GitHub user metadata (read-only, no secret values).

        Returns a dict with safe non-credential fields only.
        """
        token = _get_github_token()
        if not token:
            return {
                "connected": False,
                "error": "no_token",
                "credential_source": "none",
            }
        try:
            data = _api_get("/user", token)
        except Exception as exc:
            return {
                "connected": False,
                "error": str(exc),
                "credential_source": _credential_source_label(),
            }

        return {
            "connected": True,
            "login": data.get("login"),
            "name": data.get("name"),
            "public_repos": data.get("public_repos"),
            "followers": data.get("followers"),
            "following": data.get("following"),
            "credential_source": _credential_source_label(),
        }

    def list_repos(self, *, limit: int = 10) -> Dict[str, Any]:
        """List accessible repositories (read-only metadata, no secret values)."""
        token = _get_github_token()
        if not token:
            return {"connected": False, "error": "no_token", "repos": []}
        try:
            repos = _api_get(f"/user/repos?per_page={limit}&sort=updated", token)
        except Exception as exc:
            return {"connected": False, "error": str(exc), "repos": []}

        return {
            "connected": True,
            "credential_source": _credential_source_label(),
            "repos": [
                {
                    "full_name": r.get("full_name"),
                    "private": r.get("private"),
                    "description": r.get("description"),
                    "pushed_at": r.get("pushed_at"),
                    "default_branch": r.get("default_branch"),
                }
                for r in repos
            ],
        }


__all__ = ["GitHubConnector", "_get_github_token", "_credential_source_label"]
