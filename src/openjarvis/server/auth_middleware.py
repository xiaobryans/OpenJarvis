"""API key authentication middleware for the OpenJarvis server."""

from __future__ import annotations

import logging
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


def auth_failure_response(reason: str, detail: str) -> JSONResponse:
    """Return 401 with a non-secret ``auth_reason`` code for mobile diagnostics."""
    return JSONResponse(
        {"detail": detail, "auth_reason": reason},
        status_code=401,
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Validates ``Authorization: Bearer <key>`` on ``/v1/*`` and ``/api/*`` routes.

    Webhook routes and health checks are exempt — they use
    per-channel signature verification instead.
    """

    def __init__(self, app, api_key: str = "") -> None:  # noqa: ANN001
        super().__init__(app)
        self._api_key = (api_key or os.environ.get("OPENJARVIS_API_KEY", "")).strip()

    @staticmethod
    def _normalize_bearer_token(raw: str) -> str:
        """Strip whitespace and accidental nested ``Bearer`` prefixes from token."""
        token = raw.strip()
        while token.lower().startswith("bearer "):
            token = token[7:].strip()
        return token

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        # Browsers send unauthenticated OPTIONS preflights for cross-origin /v1 calls.
        if request.method == "OPTIONS":
            return await call_next(request)
        if self._api_key and self._requires_auth(request.url.path):
            auth = request.headers.get("Authorization", "")
            if not auth:
                return auth_failure_response(
                    "missing_authorization_header",
                    "Missing Authorization header",
                )
            scheme, _, token_raw = auth.partition(" ")
            if scheme.lower() != "bearer":
                return auth_failure_response(
                    "invalid_scheme",
                    "Authorization scheme must be Bearer",
                )
            token = self._normalize_bearer_token(token_raw)
            if not token:
                return auth_failure_response(
                    "empty_token_after_normalization",
                    "Empty token after normalization",
                )
            if not secrets.compare_digest(token, self._api_key):
                return auth_failure_response(
                    "token_mismatch",
                    "Invalid API key",
                )
        return await call_next(request)

    # Read-only status endpoints that the mobile page fetches without an auth
    # header.  These paths return non-secret status only — no tokens, no
    # credentials, no write operations.
    _PUBLIC_PATHS: frozenset[str] = frozenset(
        {
            "/v1/continuity/macbook-off-status",
            "/v1/mobile-parity/status",
            "/v1/mobile-parity/connectors",
            "/v1/mobile-parity/files",
        }
    )

    @classmethod
    def _requires_auth(cls, path: str) -> bool:
        """Protect API routes and operational metrics; leave the UI/health open.

        ``/metrics`` exposes request/token counters that should not be readable
        by unauthenticated clients, so it is gated alongside ``/v1`` and
        ``/api``. ``/health`` stays open for liveness probes.

        ``_PUBLIC_PATHS`` lists read-only status endpoints that the mobile PWA
        calls without an Authorization header (the page itself has no way to
        supply one when opened in a phone browser).
        """
        if path in cls._PUBLIC_PATHS:
            return False
        return (
            path.startswith("/v1/")
            or path.startswith("/api/")
            or path == "/metrics"
            or path.startswith("/metrics/")
        )



def generate_api_key() -> str:
    """Generate a new API key with ``oj_sk_`` prefix."""
    return f"oj_sk_{secrets.token_urlsafe(32)}"


def check_bind_safety(host: str, *, api_key: str) -> None:
    """Refuse to bind non-loopback without an API key.

    Raises ``SystemExit`` if *host* is not a loopback address and
    *api_key* is empty.
    """
    import ipaddress
    import sys

    try:
        is_loop = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loop = host in ("localhost", "")

    if not is_loop and not api_key:
        logger.error(
            "Binding to %s requires OPENJARVIS_API_KEY to be set. "
            "Run: jarvis auth generate-key",
            host,
        )
        sys.exit(1)


def websocket_authorized(websocket, expected_key: str) -> bool:  # noqa: ANN001
    """Return ``True`` if a WebSocket connection presents the expected key.

    ``AuthMiddleware`` is a ``BaseHTTPMiddleware`` and never sees WebSocket
    upgrade requests, so streaming endpoints must check the token themselves
    in the handshake before calling ``websocket.accept()``.

    When *expected_key* is empty, authentication is disabled (the loopback /
    local-only default, matching :class:`AuthMiddleware`) and all connections
    are allowed. The token may be supplied either as a ``?token=`` query
    parameter — browsers cannot set headers on a WebSocket handshake — or via
    an ``Authorization: Bearer <key>`` header for programmatic clients.
    """
    if not expected_key:
        return True
    token = websocket.query_params.get("token", "")
    if not token:
        auth = websocket.headers.get("authorization", "")
        scheme, _, value = auth.partition(" ")
        if scheme.lower() == "bearer":
            token = AuthMiddleware._normalize_bearer_token(value)
    if not token:
        return False
    expected = AuthMiddleware._normalize_bearer_token(expected_key)
    return secrets.compare_digest(token, expected)


__all__ = ["AuthMiddleware", "auth_failure_response", "generate_api_key", "check_bind_safety", "websocket_authorized"]
