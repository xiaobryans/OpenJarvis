"""Shared Google OAuth helpers: access token read + one-shot 401 refresh.

All Google connectors (Gmail, Calendar, Contacts, Drive, Tasks) authenticate
with the same OAuth flow and store identical token payloads at
``~/.openjarvis/connectors/*.json`` — typically a shared ``google.json`` file
plus per-product copies. They all need the same refresh-on-401 behavior, so
the wrapper lives here instead of being duplicated per connector.

Cloud path (Fargate): When ``GOOGLE_OAUTH_REFRESH_TOKEN`` is present in the
environment (injected via AWS Secrets Manager), credentials are loaded from env
vars instead of local files. ``GOOGLE_OAUTH_CLIENT_ID`` and
``GOOGLE_CLIENT_SECRET`` must also be present (they are already in the task def
since rev 18). No local file reads occur in the cloud path.

Use ``call_with_refresh(api_fn, credentials_path, *args, **kwargs)`` around
any token-taking API helper. On a 401 the wrapper exchanges the stored
``refresh_token`` for a new ``access_token``, updates the credentials file,
and retries the call once. All other status codes propagate.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

import httpx

from openjarvis.connectors.oauth import load_tokens, save_tokens

logger = logging.getLogger(__name__)


_GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class GoogleAuthError(RuntimeError):
    """Raised when Google credentials are missing or refresh-token grant fails."""


# ---------------------------------------------------------------------------
# Cloud credential path (Fargate / env-var-backed)
# ---------------------------------------------------------------------------

def _load_cloud_google_credentials() -> Optional[Dict[str, Any]]:
    """Return Google OAuth credentials built from Fargate env vars, or None.

    Requires all three env vars to be non-empty:
      GOOGLE_OAUTH_REFRESH_TOKEN  — injected via Secrets Manager (B1 migration)
      GOOGLE_OAUTH_CLIENT_ID      — injected via Secrets Manager (since rev 18)
      GOOGLE_CLIENT_SECRET        — injected via Secrets Manager (since rev 18)

    Returns None if any required var is missing, so callers fall through to the
    local file path.
    """
    refresh_token = os.environ.get("GOOGLE_OAUTH_REFRESH_TOKEN", "").strip()
    client_id = (
        os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
        or os.environ.get("GOOGLE_CLIENT_ID", "")
    ).strip()
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()

    if refresh_token and client_id and client_secret:
        return {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "access_token": "",
            "token": "",
        }
    return None


def is_cloud_auth_available() -> bool:
    """Return True if all Google OAuth env vars are present (Fargate cloud path)."""
    return _load_cloud_google_credentials() is not None


# ---------------------------------------------------------------------------
# Token accessors
# ---------------------------------------------------------------------------

def current_access_token(credentials_path: str) -> str:
    """Return the current access token from credentials (cloud env or local file).

    Cloud path: returns empty string (triggers 401 → auto-refresh on first API call).
    Local path: reads from the JSON file at credentials_path.
    """
    cloud = _load_cloud_google_credentials()
    if cloud is not None:
        # In cloud there is no cached access token — return "" so the caller's
        # first API attempt gets a 401, which call_with_refresh turns into a
        # token refresh.  This is the expected first-call behaviour.
        return cloud.get("access_token", "")
    tokens = load_tokens(credentials_path) or {}
    return tokens.get("access_token", tokens.get("token", ""))


def refresh_access_token(credentials_path: str) -> str:
    """Exchange the stored refresh_token for a fresh access_token.

    Cloud path: credentials come from env vars (GOOGLE_OAUTH_REFRESH_TOKEN etc.).
    Local path: credentials come from the JSON file at credentials_path.

    Returns the new access_token. Raises :class:`GoogleAuthError` when
    credentials are missing or Google rejects the refresh grant.
    """
    # Cloud path: use env vars; never write back to disk
    cloud = _load_cloud_google_credentials()
    if cloud is not None:
        tokens = cloud
        _save_to_disk = False
    else:
        tokens = load_tokens(credentials_path)
        _save_to_disk = True
        if not tokens:
            raise GoogleAuthError(
                f"No credentials at {credentials_path}; re-run the connector OAuth flow."
            )

    refresh_token = tokens.get("refresh_token", "")
    client_id = tokens.get("client_id", "")
    client_secret = tokens.get("client_secret", "")
    if not (refresh_token and client_id and client_secret):
        raise GoogleAuthError(
            "Stored Google credentials are missing refresh_token / client_id / "
            "client_secret; re-run the connector OAuth flow to mint a full token."
        )

    resp = httpx.post(
        _GOOGLE_TOKEN_ENDPOINT,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise GoogleAuthError(
            f"Google token refresh failed ({resp.status_code}): {resp.text[:200]}"
        )
    payload = resp.json()
    new_token = payload.get("access_token", "")
    if not new_token:
        raise GoogleAuthError(
            "Google token refresh returned 200 but no access_token in payload."
        )

    if _save_to_disk:
        tokens["access_token"] = new_token
        tokens["token"] = new_token
        if "expires_in" in payload:
            tokens["expires_in"] = payload["expires_in"]
        save_tokens(credentials_path, tokens)

    logger.info(
        "Refreshed Google access token via %s path (expires_in=%s)",
        "cloud" if cloud is not None else "local",
        payload.get("expires_in"),
    )
    return new_token


def call_with_refresh(
    api_fn: Callable[..., Dict[str, Any]],
    credentials_path: str,
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Invoke ``api_fn(token, *args, **kwargs)`` with one-shot 401 auto-refresh.

    Works for both the local file path and the cloud env-var path.
    In cloud mode, the first call always gets a 401 (empty access token),
    which triggers a refresh and one retry.
    """
    token = current_access_token(credentials_path)
    try:
        return api_fn(token, *args, **kwargs)
    except httpx.HTTPStatusError as exc:
        if exc.response is None or exc.response.status_code != 401:
            raise
        logger.info(
            "Google returned 401 on %s — refreshing access token and retrying.",
            getattr(api_fn, "__name__", "<api_fn>"),
        )
        new_token = refresh_access_token(credentials_path)
        return api_fn(new_token, *args, **kwargs)


__all__ = [
    "GoogleAuthError",
    "current_access_token",
    "refresh_access_token",
    "call_with_refresh",
    "is_cloud_auth_available",
]
