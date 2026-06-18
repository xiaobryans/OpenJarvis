"""US15 Jarvis-only coding dogfood evidence path."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Optional

_EVIDENCE_DIR = Path.home() / ".openjarvis" / "workbench_dogfood"


def record_dogfood_evidence(
    *,
    session_id: str,
    prompt: str,
    verdict: str,
    evidence: Dict[str, Any],
    repo_path: str = ".",
) -> Dict[str, Any]:
    """Persist a workbench coding dogfood evidence record (local only)."""
    _EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    record = {
        "session_id": session_id,
        "prompt_preview": prompt[:200],
        "verdict": verdict,
        "repo_path": repo_path,
        "recorded_at": ts,
        "evidence": evidence,
    }
    path = _EVIDENCE_DIR / f"{session_id}_{int(ts)}.json"
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    return {"ok": True, "path": str(path), "verdict": verdict}


def list_dogfood_evidence(limit: int = 20) -> Dict[str, Any]:
    if not _EVIDENCE_DIR.exists():
        return {"ok": True, "records": [], "count": 0}
    files = sorted(_EVIDENCE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    records = []
    for path in files[:limit]:
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return {"ok": True, "records": records, "count": len(records)}


__all__ = ["record_dogfood_evidence", "list_dogfood_evidence"]
