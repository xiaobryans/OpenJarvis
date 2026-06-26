"""Option A — request audit trail.

Append-only log of every chat request's routing decision and outcome, so Bryan
can ask "what did you do for that request?" and get a real answer. One JSON line
per request at ``~/.openjarvis/audit/requests.jsonl``.

This stage records: timestamp, request id, tier + reason + score (from the
Stage-1 classifier), model, and (when available) elapsed time + outcome. Later
Option-A stages extend each record with the managers/workers invoked, per-layer
timings, retries, and token usage. Best-effort: never raises into the request
path.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger("openjarvis.audit")

_AUDIT_DIR = Path.home() / ".openjarvis" / "audit"
_AUDIT_FILE = _AUDIT_DIR / "requests.jsonl"
_LOCK = threading.Lock()


def record_request(
    *,
    request_id: str,
    tier: str,
    reason: str,
    score: float,
    model: str = "",
    query_preview: str = "",
    elapsed_ms: int | None = None,
    outcome: str = "",
    extra: Dict[str, Any] | None = None,
) -> None:
    """Append one audit record. Best-effort; never raises."""
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "request_id": request_id,
        "tier": tier,
        "reason": reason,
        "score": round(float(score), 3),
        "model": model,
        # First ~120 chars only — enough to identify the request, not a full dump.
        "query_preview": (query_preview or "")[:120],
        "elapsed_ms": elapsed_ms,
        "outcome": outcome,
    }
    if extra:
        rec.update(extra)
    try:
        with _LOCK:
            _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            with _AUDIT_FILE.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec) + "\n")
    except Exception:
        logger.debug("audit record failed", exc_info=True)


def recent_requests(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent audit records (newest last). Best-effort."""
    try:
        if not _AUDIT_FILE.exists():
            return []
        lines = _AUDIT_FILE.read_text("utf-8").splitlines()[-limit:]
        out = []
        for ln in lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out
    except Exception:
        logger.debug("audit read failed", exc_info=True)
        return []


__all__ = ["record_request", "recent_requests"]
