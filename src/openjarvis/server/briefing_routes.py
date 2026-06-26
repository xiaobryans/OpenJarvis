"""Briefing API — serves the latest morning briefing to the cockpit UI.

The scheduled/CLI morning briefing persists markdown to
``~/.openjarvis/briefings/latest.md``. This endpoint lets the desktop cockpit
fetch it on load, show it if unread (the client compares ``generated_at`` to the
last value it dismissed), and display when it was generated.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_LATEST = Path.home() / ".openjarvis" / "briefings" / "latest.md"


@router.get("/v1/briefing/latest")
async def latest_briefing() -> dict:
    """Return the latest morning briefing (markdown + generation time).

    Response: ``{exists, markdown, generated_at, id}``. ``id`` is the file's
    mtime epoch — the client stores the last id it dismissed and treats a newer
    id as unread. Never raises; returns ``exists=False`` when no briefing yet.
    """
    try:
        if not _LATEST.exists():
            return {"exists": False, "markdown": "", "generated_at": None, "id": None}
        stat = _LATEST.stat()
        generated = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        return {
            "exists": True,
            "markdown": _LATEST.read_text("utf-8"),
            "generated_at": generated.isoformat(),
            "id": int(stat.st_mtime),
        }
    except Exception as exc:  # never break the UI on a briefing read
        return {"exists": False, "markdown": "", "generated_at": None,
                "id": None, "error": str(exc)}
