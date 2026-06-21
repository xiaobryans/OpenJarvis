"""Memory OS Retrieval — structured retrieval with source metadata.

Wraps JarvisMemory keyword search in a clean Memory OS abstraction that:
  - Returns RetrievalResult objects with relevance scoring and evidence notes
  - Exposes source metadata (source, kind, confidence, age) alongside content
  - Distinguishes active entries from archived/deprecated
  - Does not require secrets or model API calls
  - Gracefully degrades to empty list if memory is unavailable

What is NOT in this sprint:
  - Vector/semantic similarity search (planned — will layer onto retrieval.py)
  - Automatic re-ranking (planned)
  - Cross-project federated search (planned)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.memory.store import JarvisMemory, MemoryEntry

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """A single retrieval result with full source metadata.

    Fields
    ------
    entry           The raw MemoryEntry
    relevance_score Float 0.0–1.0 based on keyword match quality
    evidence_note   Human-readable note explaining why this was returned
    is_active       True if entry.status=='active' and not expired
    age_days        Age of the entry in days
    """

    entry: MemoryEntry
    relevance_score: float
    evidence_note: str
    is_active: bool
    age_days: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "relevance_score": round(self.relevance_score, 4),
            "evidence_note": self.evidence_note,
            "is_active": self.is_active,
            "age_days": round(self.age_days, 2),
        }


def _score_entry(query: str, entry: MemoryEntry) -> tuple[float, str]:
    """Compute a simple relevance score for a keyword-matched entry.

    Returns (score 0.0-1.0, evidence_note).

    Scoring heuristic:
      - Confidence weight:  0.0–0.4 based on entry.confidence
      - Recency weight:     0.0–0.3 (entries <7d old score highest)
      - Match depth weight: 0.0–0.2 (how many query terms match)
      - Kind weight:        0.0–0.1 (decisions/preferences score higher)

    This is intentionally simple — the goal is directional ranking, not
    precise similarity.  Vector search (planned sprint) will improve this.
    """
    q_terms = [t.strip().lower() for t in query.split() if t.strip()]
    content_lower = entry.content.lower()
    tags_lower = " ".join(entry.tags).lower()

    matched = sum(1 for t in q_terms if t in content_lower or t in tags_lower)
    match_depth = (matched / max(len(q_terms), 1)) * 0.2

    confidence_w = entry.confidence * 0.4

    age_days = (time.time() - entry.created_at) / 86400
    if age_days < 1:
        recency_w = 0.3
    elif age_days < 7:
        recency_w = 0.25
    elif age_days < 30:
        recency_w = 0.15
    else:
        recency_w = 0.05

    kind_bonus = 0.1 if entry.kind in ("decision", "preference") else 0.0

    score = confidence_w + recency_w + match_depth + kind_bonus

    matched_terms = [t for t in q_terms if t in content_lower or t in tags_lower]
    note_parts = []
    if matched_terms:
        note_parts.append(f"matched terms: {', '.join(matched_terms[:3])}")
    note_parts.append(f"kind={entry.kind}")
    note_parts.append(f"source={entry.source!r}" if entry.source else "source=''")
    note_parts.append(f"confidence={entry.confidence:.2f}")
    evidence_note = " | ".join(note_parts)

    return min(score, 1.0), evidence_note


class MemoryRetriever:
    """Memory OS retrieval — returns structured RetrievalResult objects.

    Wraps JarvisMemory.search() with relevance scoring and metadata.
    No model API calls required.
    """

    def __init__(self, memory: Optional[JarvisMemory] = None) -> None:
        self._memory = memory or JarvisMemory()

    def retrieve(
        self,
        query: str,
        *,
        project_id: Optional[str] = None,
        namespace: Optional[str] = None,
        kind: Optional[str] = None,
        max_results: int = 10,
        min_score: float = 0.0,
        active_only: bool = False,
    ) -> List[RetrievalResult]:
        """Retrieve memory entries matching query, with relevance scoring.

        Parameters
        ----------
        query           Keyword query string
        project_id      Restrict to a project (None = all projects)
        namespace       Restrict to a namespace (None = all namespaces)
        kind            Restrict to a memory kind (None = all kinds)
        max_results     Maximum number of results to return
        min_score       Minimum relevance score threshold (0.0 = no filter)
        active_only     If True, only return active (non-expired) entries

        Returns
        -------
        List[RetrievalResult] sorted by relevance_score descending.
        Empty list if query is empty or memory unavailable.
        """
        if not query.strip():
            return []

        try:
            entries = self._memory.search(
                query,
                namespace=namespace,
                project_id=project_id,
                kind=kind,
                limit=max_results * 3,  # over-fetch for post-scoring filter
            )
        except Exception as exc:
            logger.warning("MemoryRetriever.retrieve failed: %s", exc)
            return []

        results = []
        now = time.time()
        for entry in entries:
            is_active = entry.is_active()
            if active_only and not is_active:
                continue
            age_days = (now - entry.created_at) / 86400
            score, evidence_note = _score_entry(query, entry)
            if score < min_score:
                continue
            results.append(
                RetrievalResult(
                    entry=entry,
                    relevance_score=score,
                    evidence_note=evidence_note,
                    is_active=is_active,
                    age_days=age_days,
                )
            )

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:max_results]

    def retrieve_active(
        self,
        query: str,
        *,
        project_id: Optional[str] = None,
        max_results: int = 5,
    ) -> List[RetrievalResult]:
        """Retrieve only active (non-expired, status=active) entries."""
        return self.retrieve(
            query,
            project_id=project_id,
            max_results=max_results,
            active_only=True,
        )


__all__ = ["RetrievalResult", "MemoryRetriever"]
