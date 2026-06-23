"""Plan 9 mobile proof page — served at GET /mobile on cloud and local backend."""

from __future__ import annotations

from pathlib import Path

from fastapi.responses import HTMLResponse

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "plan9_mobile_proof.html"


def get_mobile_proof_html() -> str:
    """Return the Plan 9 mobile proof HTML (iPhone Safari scroll + auth proof)."""
    return _TEMPLATE_PATH.read_text(encoding="utf-8")


def mobile_proof_response() -> HTMLResponse:
    return HTMLResponse(content=get_mobile_proof_html())


__all__ = ["get_mobile_proof_html", "mobile_proof_response"]
