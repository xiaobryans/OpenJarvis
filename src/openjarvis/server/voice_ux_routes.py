"""Voice UX endpoints — live transcript + unified history for the cockpit.

  - GET /v1/voice/transcript  : current live transcript events + voice-active flag
                                (polled by the cockpit overlay every 500ms)
  - GET /v1/history           : unified voice history, newest first, searchable
                                (typed-chat history is merged client-side from the
                                 frontend store; this serves the voice side)
"""

from __future__ import annotations

from fastapi import APIRouter

from openjarvis.speech import voice_bus

router = APIRouter()


@router.get("/v1/voice/transcript")
async def voice_transcript(limit: int = 12) -> dict:
    """Live transcript events + current voice state for the cockpit overlay/orb."""
    return {
        "active": voice_bus.voice_active(),
        "state": voice_bus.get_voice_state(),
        "events": voice_bus.get_transcript(limit),
    }


@router.get("/v1/voice/state")
async def voice_state() -> dict:
    """Current voice-pipeline state for the orb/indicator (polled by the cockpit)."""
    return {"active": voice_bus.voice_active(), "state": voice_bus.get_voice_state()}


@router.get("/v1/history")
async def history(limit: int = 50, search: str = "") -> dict:
    """Unified history (voice turns), newest first, optional keyword filter."""
    entries = voice_bus.read_history(limit=limit, search=search)
    return {"entries": entries, "count": len(entries)}
