"""Plan 9 mobile proof page — served at GET /mobile on cloud and local backend."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import HTMLResponse

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "plan9_mobile_proof.html"
AUTH_NORM_VERSION = "v2"

_MOBILE_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def get_mobile_proof_html() -> str:
    """Return the Plan 9 mobile proof HTML (iPhone Safari scroll + auth proof)."""
    html = _TEMPLATE_PATH.read_text(encoding="utf-8")
    build = os.environ.get("JARVIS_BUILD_COMMIT", "unknown")
    return (
        html.replace("{{MOBILE_BUILD_COMMIT}}", build)
        .replace("{{AUTH_NORM_VERSION}}", AUTH_NORM_VERSION)
    )


def mobile_proof_response() -> HTMLResponse:
    return HTMLResponse(content=get_mobile_proof_html(), headers=_MOBILE_NO_CACHE_HEADERS)


__all__ = [
    "AUTH_NORM_VERSION",
    "get_mobile_proof_html",
    "mobile_proof_response",
]
