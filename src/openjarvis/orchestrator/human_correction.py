"""Human Correction Ingestion — structured mechanism for Bryan to correct Jarvis.

Provides:
  - CorrectionRecord: schema for a single Bryan correction
  - HumanCorrectionStore: disk-backed store at ~/.jarvis/corrections.jsonl
  - NUS hook: writes corrections to NUS LearningStore if available
  - Doctor-observable via get_correction_status()

Design rules:
  - No raw chain-of-thought stored.
  - Corrections are structured — source/provenance always required.
  - Affected project/task always recorded.
  - Action taken or pending always recorded.
  - NUS hook is best-effort — failure does not break correction ingestion.
  - Corrections do not auto-apply to routing/memory — they are inputs for human review
    or future NUS learning.
  - Bounded retention: last 500 corrections.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CORRECTIONS_FILE = Path.home() / ".jarvis" / "corrections.jsonl"
_MAX_CORRECTIONS = 500

# Correction categories
CORRECTION_ROUTING = "routing"          # wrong manager/worker selected
CORRECTION_MEMORY = "memory"            # wrong/stale memory recalled
CORRECTION_PROVIDER = "provider"        # wrong model/provider used
CORRECTION_SAFETY = "safety"            # safety gate too strict or too loose
CORRECTION_OUTPUT = "output"            # Jarvis response was wrong/incomplete
CORRECTION_CLASSIFICATION = "classification"  # task misclassified

ALL_CORRECTION_CATEGORIES = frozenset({
    CORRECTION_ROUTING,
    CORRECTION_MEMORY,
    CORRECTION_PROVIDER,
    CORRECTION_SAFETY,
    CORRECTION_OUTPUT,
    CORRECTION_CLASSIFICATION,
})


@dataclass
class CorrectionRecord:
    """A single Bryan correction to Jarvis behavior.

    Never stores raw chain-of-thought or secret values.
    """
    correction_id: str
    recorded_at: float
    category: str                      # one of ALL_CORRECTION_CATEGORIES
    source: str                        # "bryan" always for now
    provenance: str                    # e.g. "session:abc/request:xyz" or "manual"
    affected_project: Optional[str]    # project_id or None for global
    affected_task_intent: str          # what task was being performed
    what_was_wrong: str                # concise description (no raw CoT)
    correct_behavior: str              # what should have happened
    action_taken: str                  # "pending_review" | "applied_to_nus" | "applied_to_routing"
    trace_id: Optional[str]            # if linked to a specific trace
    request_id: Optional[str]
    applied: bool = False
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correction_id": self.correction_id,
            "recorded_at": self.recorded_at,
            "category": self.category,
            "source": self.source,
            "provenance": self.provenance,
            "affected_project": self.affected_project,
            "affected_task_intent": self.affected_task_intent,
            "what_was_wrong": self.what_was_wrong,
            "correct_behavior": self.correct_behavior,
            "action_taken": self.action_taken,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "applied": self.applied,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CorrectionRecord":
        return cls(
            correction_id=d.get("correction_id", uuid.uuid4().hex[:12]),
            recorded_at=d.get("recorded_at", 0.0),
            category=d.get("category", CORRECTION_OUTPUT),
            source=d.get("source", "bryan"),
            provenance=d.get("provenance", "manual"),
            affected_project=d.get("affected_project"),
            affected_task_intent=d.get("affected_task_intent", ""),
            what_was_wrong=d.get("what_was_wrong", ""),
            correct_behavior=d.get("correct_behavior", ""),
            action_taken=d.get("action_taken", "pending_review"),
            trace_id=d.get("trace_id"),
            request_id=d.get("request_id"),
            applied=d.get("applied", False),
        )


class HumanCorrectionStore:
    """Disk-backed store for Bryan corrections.

    Appends to ~/.jarvis/corrections.jsonl (one record per line).
    Provides NUS hook for routing/learning improvements.
    """

    def __init__(self) -> None:
        self._corrections: List[CorrectionRecord] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not _CORRECTIONS_FILE.exists():
            return
        try:
            for line in _CORRECTIONS_FILE.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                self._corrections.append(CorrectionRecord.from_dict(data))
        except Exception as exc:
            logger.warning("HumanCorrectionStore load failed (non-fatal): %s", exc)

    def _append_to_disk(self, record: CorrectionRecord) -> bool:
        """Append a single correction to disk (JSONL append-only)."""
        try:
            _CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with _CORRECTIONS_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
            return True
        except Exception as exc:
            logger.debug("CorrectionRecord disk append failed (non-fatal): %s", exc)
            return False

    def ingest(
        self,
        category: str,
        affected_task_intent: str,
        what_was_wrong: str,
        correct_behavior: str,
        affected_project: Optional[str] = None,
        provenance: str = "manual",
        trace_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> CorrectionRecord:
        """Ingest a Bryan correction. Validates category. Hooks NUS if available.

        Returns the CorrectionRecord.
        """
        self._ensure_loaded()

        if category not in ALL_CORRECTION_CATEGORIES:
            category = CORRECTION_OUTPUT  # safe default

        record = CorrectionRecord(
            correction_id=uuid.uuid4().hex[:12],
            recorded_at=time.time(),
            category=category,
            source="bryan",
            provenance=provenance,
            affected_project=affected_project,
            affected_task_intent=affected_task_intent,
            what_was_wrong=what_was_wrong,
            correct_behavior=correct_behavior,
            action_taken="pending_review",
            trace_id=trace_id,
            request_id=request_id,
        )
        self._corrections.append(record)

        # Trim in memory
        if len(self._corrections) > _MAX_CORRECTIONS:
            self._corrections = self._corrections[-_MAX_CORRECTIONS:]

        self._append_to_disk(record)

        # NUS hook (best-effort)
        self._hook_nus(record)

        return record

    def _hook_nus(self, record: CorrectionRecord) -> None:
        """Attempt to write correction to NUS LearningStore. Non-fatal."""
        try:
            from openjarvis.nus.learning_store import LearningStore
            store = LearningStore()
            store.record_outcome(
                task_id=record.correction_id,
                manager_id="human_correction",
                worker_id=record.category,
                success=False,  # correction implies something failed
                metadata={
                    "category": record.category,
                    "affected_project": record.affected_project,
                    "what_was_wrong": record.what_was_wrong,
                    "correct_behavior": record.correct_behavior,
                    "no_raw_chain_of_thought": True,
                },
            )
        except Exception as exc:
            logger.debug("NUS hook for correction failed (non-fatal): %s", exc)

    def get_pending(self) -> List[CorrectionRecord]:
        self._ensure_loaded()
        return [c for c in self._corrections if not c.applied]

    def get_correction_status(self) -> Dict[str, Any]:
        """Return structured correction status for doctor/status checks."""
        self._ensure_loaded()
        pending = self.get_pending()
        by_category: Dict[str, int] = {}
        for c in self._corrections:
            by_category[c.category] = by_category.get(c.category, 0) + 1
        return {
            "file_path": str(_CORRECTIONS_FILE),
            "file_exists": _CORRECTIONS_FILE.exists(),
            "total_corrections": len(self._corrections),
            "pending_corrections": len(pending),
            "by_category": by_category,
            "recent_pending": [
                {
                    "correction_id": c.correction_id,
                    "category": c.category,
                    "affected_task_intent": c.affected_task_intent,
                    "what_was_wrong": c.what_was_wrong[:100],
                }
                for c in pending[-5:]
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[HumanCorrectionStore] = None


def get_correction_store() -> HumanCorrectionStore:
    global _store
    if _store is None:
        _store = HumanCorrectionStore()
    return _store


def ingest_correction(
    category: str,
    affected_task_intent: str,
    what_was_wrong: str,
    correct_behavior: str,
    **kwargs: Any,
) -> CorrectionRecord:
    """Convenience function: ingest a correction via the singleton store."""
    return get_correction_store().ingest(
        category=category,
        affected_task_intent=affected_task_intent,
        what_was_wrong=what_was_wrong,
        correct_behavior=correct_behavior,
        **kwargs,
    )


__all__ = [
    "CorrectionRecord",
    "HumanCorrectionStore",
    "get_correction_store",
    "ingest_correction",
    "CORRECTION_ROUTING",
    "CORRECTION_MEMORY",
    "CORRECTION_PROVIDER",
    "CORRECTION_SAFETY",
    "CORRECTION_OUTPUT",
    "CORRECTION_CLASSIFICATION",
    "ALL_CORRECTION_CATEGORIES",
]
