"""In-process bus shared by the voice loop (background thread) and the API.

The voice loop runs in the same process as ``vanta serve`` (a daemon thread), so
a module-level singleton is visible to both. It holds:

  - the live transcript ring buffer (for the cockpit's transcript overlay), and
  - a JSONL voice-history writer that ``GET /v1/history`` reads, so every voice
    turn (both Bryan's words and VANTA's spoken reply) is persisted alongside
    typed chat. Turns are also best-effort written to the unified memory backend.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("openjarvis.voice_bus")

_LOCK = threading.Lock()
_TRANSCRIPT: Deque[Dict[str, Any]] = deque(maxlen=40)
_ACTIVE = {"on": False}
_MEM: Dict[str, Any] = {"backend": None}
_HISTORY_PATH = Path.home() / ".openjarvis" / "voice_history.jsonl"


# ── voice-active flag (UI hides the transcript overlay when off) ──────────────
def set_voice_active(on: bool) -> None:
    _ACTIVE["on"] = bool(on)


def voice_active() -> bool:
    return _ACTIVE["on"]


def set_memory_backend(backend: Any) -> None:
    """Wire the unified memory backend so voice turns also land in memory."""
    _MEM["backend"] = backend


# ── live transcript ring buffer ──────────────────────────────────────────────
def push_transcript(speaker: str, text: str, *, final: bool = False) -> None:
    """Append a transcript event. speaker is 'bryan' or 'vanta'. Interim events
    (final=False) update the live display; final events mark a completed line."""
    text = (text or "").strip()
    if not text:
        return
    with _LOCK:
        _TRANSCRIPT.append({"ts": time.time(), "speaker": speaker, "text": text, "final": bool(final)})


def get_transcript(limit: int = 12) -> List[Dict[str, Any]]:
    with _LOCK:
        return list(_TRANSCRIPT)[-max(1, limit):]


def clear_transcript() -> None:
    with _LOCK:
        _TRANSCRIPT.clear()


# ── persistent voice history (read by /v1/history) ───────────────────────────
def save_turn(speaker: str, text: str, *, session_id: str = "", mode: str = "voice") -> None:
    """Persist one voice turn to the JSONL history and (best-effort) to memory.

    speaker: 'bryan' or 'vanta'. Never raises — history is a side benefit.
    """
    text = (text or "").strip()
    if not text:
        return
    entry = {"ts": time.time(), "speaker": speaker, "text": text, "mode": mode, "session_id": session_id}
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _HISTORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:  # pragma: no cover - disk issue, non-fatal
        logger.debug("voice history write failed", exc_info=True)
    backend = _MEM["backend"]
    if backend is not None:
        try:
            backend.store(text, source="voice", metadata={"role": speaker, "mode": mode, "session_id": session_id})
        except Exception:
            logger.debug("voice memory store failed", exc_info=True)


def read_history(limit: int = 50, search: str = "") -> List[Dict[str, Any]]:
    """Return voice-history entries, newest first, optionally filtered by keyword."""
    rows: List[Dict[str, Any]] = []
    try:
        if _HISTORY_PATH.exists():
            for line in _HISTORY_PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        logger.debug("voice history read failed", exc_info=True)
    s = (search or "").strip().lower()
    if s:
        rows = [r for r in rows if s in str(r.get("text", "")).lower()]
    rows.sort(key=lambda r: r.get("ts", 0), reverse=True)
    return rows[: max(1, limit)]


def history_path() -> Optional[Path]:
    return _HISTORY_PATH
