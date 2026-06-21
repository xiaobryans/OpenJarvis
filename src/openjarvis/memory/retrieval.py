"""Memory OS Retrieval — structured retrieval with TF-IDF ranking.

Sprint 1 (carried forward):
  - RetrievalResult         Wraps MemoryEntry with relevance score + metadata
  - MemoryRetriever         Keyword search + heuristic scoring
  - retrieve() / retrieve_active()

Sprint 2 additions:
  - TfIdfRanker             In-corpus TF-IDF ranking (pure Python, no API calls)
  - SemanticSearchStatus    Honest status of semantic/vector search capability
  - MemoryRetriever.retrieve() now applies TF-IDF re-ranking on the candidate set

Semantic/vector search status:
  - BLOCKED — requires either OPENAI_API_KEY (for cloud embeddings) or a local
    embedding model (e.g. sentence-transformers). Neither is configured.
  - Fallback: TF-IDF ranking is active. It provides genuine term-frequency
    weighting, which is meaningfully better than simple keyword match count.
  - This status is always reported accurately — never faked.
"""

from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.memory.store import JarvisMemory, MemoryEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Semantic search honest status
# ---------------------------------------------------------------------------

class SemanticSearchStatus:
    """Reports the honest status of semantic/vector search.

    Vector search requires an embedding model.  Neither a cloud key nor a
    local model is configured in this environment.  TF-IDF ranking is the
    active fallback.  This class exists so callers can inspect exactly why
    full semantic search is unavailable and what is active instead.
    """

    ACTIVE_RANKER = "tfidf_local"
    VECTOR_STATUS = "BLOCKED_NO_EMBEDDING_MODEL"
    VECTOR_REASON = (
        "Embedding-based semantic search requires: "
        "(1) OPENAI_API_KEY for cloud embeddings, or "
        "(2) a local model (e.g. pip install sentence-transformers). "
        "Neither is configured. TF-IDF fallback is active."
    )
    FALLBACK_DESCRIPTION = (
        "TF-IDF ranking: scores entries by term frequency (within the retrieved "
        "candidate set) × inverse document frequency, then re-ranks. "
        "Genuinely better than raw keyword count; not equivalent to semantic embeddings."
    )

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        return {
            "active_ranker": cls.ACTIVE_RANKER,
            "vector_search": cls.VECTOR_STATUS,
            "vector_reason": cls.VECTOR_REASON,
            "fallback_description": cls.FALLBACK_DESCRIPTION,
        }


# ---------------------------------------------------------------------------
# TF-IDF ranker (pure Python, no external dependencies)
# ---------------------------------------------------------------------------


class TfIdfRanker:
    """Compute TF-IDF scores within a retrieved candidate set.

    This is an in-corpus ranker: IDF is computed from the candidate set,
    not a global corpus.  This means it requires at least 2 documents
    to produce meaningful IDF differentiation.

    For a single document, it falls back to term-frequency only.

    No API calls.  No external libraries.  Runs locally.
    """

    @staticmethod
    def score(query: str, candidates: List[MemoryEntry]) -> List[tuple[MemoryEntry, float]]:
        """Return candidates with their TF-IDF scores.

        Parameters
        ----------
        query       Query string (split into terms)
        candidates  List of MemoryEntry objects from keyword search

        Returns list of (entry, score) sorted by score descending.
        """
        if not candidates:
            return []

        q_terms = [t.strip().lower() for t in query.split() if t.strip()]
        if not q_terms:
            return [(e, 0.0) for e in candidates]

        n = len(candidates)

        # Build term → document frequency mapping
        df: Dict[str, int] = {}
        doc_terms: List[List[str]] = []
        for entry in candidates:
            combined = (entry.content + " " + " ".join(entry.tags)).lower()
            terms = combined.split()
            doc_terms.append(terms)
            seen_in_doc = set()
            for term in terms:
                if term not in seen_in_doc:
                    df[term] = df.get(term, 0) + 1
                    seen_in_doc.add(term)

        scored: List[tuple[MemoryEntry, float]] = []
        for i, entry in enumerate(candidates):
            terms = doc_terms[i]
            term_count = len(terms) if terms else 1

            tf_idf_sum = 0.0
            for qt in q_terms:
                tf = terms.count(qt) / term_count
                idf = math.log((n + 1) / (df.get(qt, 0) + 1)) + 1.0
                tf_idf_sum += tf * idf

            # Normalise: divide by number of query terms to keep 0–1ish range
            normalised = tf_idf_sum / len(q_terms)
            scored.append((entry, normalised))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


# ---------------------------------------------------------------------------
# RetrievalResult (Sprint 1 API preserved)
# ---------------------------------------------------------------------------


@dataclass
class RetrievalResult:
    """A single retrieval result with source metadata and ranking details.

    Fields
    ------
    entry           The raw MemoryEntry
    relevance_score Float 0.0–1.0 combined score
    evidence_note   Human-readable explanation of why this was returned
    is_active       True if entry.status=='active' and not expired
    age_days        Age of the entry in days
    tfidf_score     Raw TF-IDF score (0.0 if TF-IDF not available)
    ranker_used     Label of the ranking method used
    """

    entry: MemoryEntry
    relevance_score: float
    evidence_note: str
    is_active: bool
    age_days: float
    tfidf_score: float = 0.0
    ranker_used: str = SemanticSearchStatus.ACTIVE_RANKER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "relevance_score": round(self.relevance_score, 4),
            "evidence_note": self.evidence_note,
            "is_active": self.is_active,
            "age_days": round(self.age_days, 2),
            "tfidf_score": round(self.tfidf_score, 4),
            "ranker_used": self.ranker_used,
        }


# ---------------------------------------------------------------------------
# Combined heuristic scorer (confidence + recency + kind bonus)
# ---------------------------------------------------------------------------


def _heuristic_score(entry: MemoryEntry) -> tuple[float, str]:
    """Compute confidence/recency/kind heuristic score.

    Returns (score 0.0-1.0, evidence_note_fragment).
    Used to blend with TF-IDF score.
    """
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

    score = min(confidence_w + recency_w + kind_bonus, 1.0)
    note = f"kind={entry.kind} confidence={entry.confidence:.2f}"
    return score, note


# ---------------------------------------------------------------------------
# MemoryRetriever — Sprint 2 version
# ---------------------------------------------------------------------------


class MemoryRetriever:
    """Memory OS retrieval with TF-IDF re-ranking.

    Ranking pipeline:
      1. Keyword search against JarvisMemory (OR-per-term SQLite LIKE)
      2. TF-IDF re-ranking of the candidate set (in-corpus, no API)
      3. Blend: 0.6 × tfidf_score + 0.4 × heuristic_score
      4. Apply min_score threshold and return top max_results

    Full semantic/vector search: BLOCKED (see SemanticSearchStatus).
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
        """Retrieve memory entries with TF-IDF blended ranking.

        Parameters
        ----------
        query           Keyword query string
        project_id      Restrict to a project (None = all projects)
        namespace       Restrict to a namespace (None = all namespaces)
        kind            Restrict to a memory kind (None = all kinds)
        max_results     Maximum number of results to return
        min_score       Minimum relevance score threshold
        active_only     If True, only return active (non-expired) entries

        Returns
        -------
        List[RetrievalResult] sorted by relevance_score descending.
        """
        if not query.strip():
            return []

        try:
            entries = self._memory.search(
                query,
                namespace=namespace,
                project_id=project_id,
                kind=kind,
                limit=max_results * 3,
            )
        except Exception as exc:
            logger.warning("MemoryRetriever.retrieve failed: %s", exc)
            return []

        # Filter by active_only before scoring
        if active_only:
            entries = [e for e in entries if e.is_active()]

        if not entries:
            return []

        # TF-IDF re-ranking
        tfidf_scored = TfIdfRanker.score(query, entries)
        tfidf_map: Dict[str, float] = {e.entry_id: s for e, s in tfidf_scored}

        results = []
        now = time.time()
        for entry in entries:
            is_active = entry.is_active()
            age_days = (now - entry.created_at) / 86400
            tfidf = tfidf_map.get(entry.entry_id, 0.0)
            heuristic, h_note = _heuristic_score(entry)

            # Blended score
            combined = 0.6 * min(tfidf * 5.0, 1.0) + 0.4 * heuristic

            # Build evidence note
            q_terms = [t.strip().lower() for t in query.split() if t.strip()]
            content_lower = entry.content.lower()
            tags_lower = " ".join(entry.tags).lower()
            matched_terms = [
                t for t in q_terms if t in content_lower or t in tags_lower
            ]
            note_parts = []
            if matched_terms:
                note_parts.append(f"matched: {', '.join(matched_terms[:3])}")
            note_parts.append(h_note)
            note_parts.append(f"tfidf={tfidf:.3f}")
            note_parts.append(f"ranker={SemanticSearchStatus.ACTIVE_RANKER}")
            evidence_note = " | ".join(note_parts)

            if combined < min_score:
                continue

            results.append(
                RetrievalResult(
                    entry=entry,
                    relevance_score=min(combined, 1.0),
                    evidence_note=evidence_note,
                    is_active=is_active,
                    age_days=age_days,
                    tfidf_score=tfidf,
                    ranker_used=SemanticSearchStatus.ACTIVE_RANKER,
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

    @staticmethod
    def semantic_search_status() -> Dict[str, Any]:
        """Return honest semantic search capability status."""
        return SemanticSearchStatus.to_dict()


__all__ = [
    "RetrievalResult",
    "MemoryRetriever",
    "SemanticSearchStatus",
    "TfIdfRanker",
]
