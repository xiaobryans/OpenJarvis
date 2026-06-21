"""Memory OS Retrieval — TF-IDF + OpenAI semantic ranking.

Sprint 1: keyword search + heuristic scoring.
Sprint 2: TF-IDF re-ranking + SemanticSearchStatus (honest BLOCKED).
Sprint 2B: Semantic/vector search activated when OPENAI_API_KEY present.

Ranking pipeline (when OpenAI key available):
  1. Keyword search against JarvisMemory (OR-per-term SQLite LIKE)
  2. OpenAI text-embedding-3-small embeddings for query and candidates
  3. Cosine similarity ranking
  4. Blend: 0.7 × semantic_score + 0.3 × heuristic_score

Ranking pipeline (when OpenAI key NOT available — TF-IDF fallback):
  1. Keyword search
  2. TF-IDF re-ranking (in-corpus, pure Python)
  3. Blend: 0.6 × tfidf_score + 0.4 × heuristic_score

SemanticSearchStatus honestly reports which ranker is active.
"""

from __future__ import annotations

import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.memory.store import JarvisMemory, MemoryEntry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Semantic search status — reports actual active ranker honestly
# ---------------------------------------------------------------------------


def _openai_key_available() -> bool:
    """True if OPENAI_API_KEY is set to a non-empty value."""
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


class SemanticSearchStatus:
    """Reports the honest status of semantic/vector search.

    Updated in Sprint 2B: when OPENAI_API_KEY is present, vector search via
    OpenAI text-embedding-3-small is active.  When not present, TF-IDF fallback
    is active.

    Call SemanticSearchStatus.to_dict() to get the current status.
    """

    ACTIVE_RANKER_TFIDF = "tfidf_local"
    ACTIVE_RANKER_OPENAI = "openai_text-embedding-3-small"
    EMBED_MODEL = "text-embedding-3-small"

    @classmethod
    def _is_semantic_active(cls) -> bool:
        return _openai_key_available()

    @classmethod
    def active_ranker(cls) -> str:
        return cls.ACTIVE_RANKER_OPENAI if cls._is_semantic_active() else cls.ACTIVE_RANKER_TFIDF

    VECTOR_STATUS_BLOCKED = "BLOCKED_NO_EMBEDDING_MODEL"
    VECTOR_STATUS_ACTIVE = "ACTIVE_OPENAI_EMBEDDINGS"
    VECTOR_REASON_BLOCKED = (
        "Embedding-based semantic search requires: "
        "(1) OPENAI_API_KEY for cloud embeddings, or "
        "(2) a local model (e.g. pip install sentence-transformers). "
        "Neither is configured. TF-IDF fallback is active."
    )
    VECTOR_REASON_ACTIVE = (
        "OPENAI_API_KEY is configured. Semantic search uses "
        "text-embedding-3-small via OpenAI embeddings API. "
        "TF-IDF is retained as fallback if embedding call fails."
    )
    FALLBACK_DESCRIPTION = (
        "TF-IDF ranking: scores entries by term frequency × inverse document "
        "frequency, then re-ranks. Active when OpenAI key unavailable."
    )

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        active = cls._is_semantic_active()
        return {
            "active_ranker": cls.active_ranker(),
            "vector_search": cls.VECTOR_STATUS_ACTIVE if active else cls.VECTOR_STATUS_BLOCKED,
            "vector_reason": cls.VECTOR_REASON_ACTIVE if active else cls.VECTOR_REASON_BLOCKED,
            "fallback_description": cls.FALLBACK_DESCRIPTION,
            "openai_key_present": active,
        }

    # Keep old constant for backward compat with Sprint 2 tests
    ACTIVE_RANKER = ACTIVE_RANKER_TFIDF


# ---------------------------------------------------------------------------
# TF-IDF ranker (pure Python, no external dependencies)
# ---------------------------------------------------------------------------


class TfIdfRanker:
    """Compute TF-IDF scores within a retrieved candidate set."""

    @staticmethod
    def score(query: str, candidates: List[MemoryEntry]) -> List[tuple[MemoryEntry, float]]:
        if not candidates:
            return []
        q_terms = [t.strip().lower() for t in query.split() if t.strip()]
        if not q_terms:
            return [(e, 0.0) for e in candidates]

        n = len(candidates)
        df: Dict[str, int] = {}
        doc_terms: List[List[str]] = []
        for entry in candidates:
            combined = (entry.content + " " + " ".join(entry.tags)).lower()
            terms = combined.split()
            doc_terms.append(terms)
            seen_in_doc: set = set()
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
            normalised = tf_idf_sum / len(q_terms)
            scored.append((entry, normalised))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored


# ---------------------------------------------------------------------------
# OpenAI embedding helpers (inline, no openai package required)
# ---------------------------------------------------------------------------


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _get_openai_embedding(text: str, key: str, timeout: int = 15) -> Optional[List[float]]:
    """Get OpenAI embedding via direct HTTP. No openai package required."""
    import json
    import urllib.request

    body = json.dumps({
        "input": text[:8000],
        "model": SemanticSearchStatus.EMBED_MODEL,
        "dimensions": 1536,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        return data["data"][0]["embedding"]
    except Exception as exc:
        logger.debug("Embedding call failed (non-fatal): %s", exc)
        return None


def _get_openai_embeddings_batch(
    texts: List[str], key: str, timeout: int = 15
) -> List[Optional[List[float]]]:
    """Get embeddings for a batch of texts."""
    import json
    import urllib.request

    if not texts:
        return []
    body = json.dumps({
        "input": [t[:8000] for t in texts],
        "model": SemanticSearchStatus.EMBED_MODEL,
        "dimensions": 1536,
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/embeddings",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.load(resp)
        result: List[Optional[List[float]]] = [None] * len(texts)
        for item in data["data"]:
            result[item["index"]] = item["embedding"]
        return result
    except Exception as exc:
        logger.debug("Batch embedding failed (non-fatal): %s", exc)
        return [None] * len(texts)


# ---------------------------------------------------------------------------
# RetrievalResult (Sprint 1 API preserved, Sprint 2B extended)
# ---------------------------------------------------------------------------


@dataclass
class RetrievalResult:
    """A single retrieval result with source metadata and ranking details.

    Fields
    ------
    entry           The raw MemoryEntry
    relevance_score Float 0.0–1.0 combined score
    evidence_note   Human-readable explanation
    is_active       True if entry.status=='active' and not expired
    age_days        Age in days
    tfidf_score     TF-IDF score (0.0 if semantic is active)
    ranker_used     Active ranker: 'tfidf_local' or 'openai_text-embedding-3-small'
    semantic_score  Cosine similarity (0.0 if TF-IDF is active)
    """

    entry: MemoryEntry
    relevance_score: float
    evidence_note: str
    is_active: bool
    age_days: float
    tfidf_score: float = 0.0
    ranker_used: str = ""
    semantic_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "relevance_score": round(self.relevance_score, 4),
            "evidence_note": self.evidence_note,
            "is_active": self.is_active,
            "age_days": round(self.age_days, 2),
            "tfidf_score": round(self.tfidf_score, 4),
            "ranker_used": self.ranker_used,
            "semantic_score": round(self.semantic_score, 4),
        }


# ---------------------------------------------------------------------------
# Heuristic scorer (confidence + recency + kind bonus)
# ---------------------------------------------------------------------------


def _heuristic_score(entry: MemoryEntry) -> tuple[float, str]:
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
# MemoryRetriever — Sprint 2B: semantic when key available, TF-IDF fallback
# ---------------------------------------------------------------------------


class MemoryRetriever:
    """Memory OS retrieval with dynamic ranking.

    When OPENAI_API_KEY is present:
      Uses OpenAI text-embedding-3-small embeddings + cosine similarity.
      Blend: 0.7 × semantic_score + 0.3 × heuristic_score.

    When OPENAI_API_KEY is not present:
      Falls back to TF-IDF re-ranking.
      Blend: 0.6 × tfidf_score_normalised + 0.4 × heuristic_score.

    SemanticSearchStatus.to_dict() always reports which ranker is active.
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
        """Retrieve memory entries with dynamic ranking.

        Uses semantic (OpenAI) when key available, TF-IDF otherwise.
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

        if active_only:
            entries = [e for e in entries if e.is_active()]
        if not entries:
            return []

        key = os.environ.get("OPENAI_API_KEY", "").strip()
        if key:
            return self._rank_semantic(query, entries, key, max_results, min_score)
        return self._rank_tfidf(query, entries, max_results, min_score)

    def _rank_semantic(
        self,
        query: str,
        entries: List[MemoryEntry],
        key: str,
        max_results: int,
        min_score: float,
    ) -> List[RetrievalResult]:
        """Rank using OpenAI embeddings + cosine similarity."""
        query_emb = _get_openai_embedding(query, key)
        if query_emb is None:
            logger.debug("Query embedding failed; falling back to TF-IDF")
            return self._rank_tfidf(query, entries, max_results, min_score)

        texts = [e.content for e in entries]
        embeddings = _get_openai_embeddings_batch(texts, key)

        now = time.time()
        results = []
        for entry, emb in zip(entries, embeddings):
            semantic = _cosine_similarity(query_emb, emb) if emb else 0.0
            heuristic, h_note = _heuristic_score(entry)
            combined = min(0.7 * semantic + 0.3 * heuristic, 1.0)

            q_terms = [t.strip().lower() for t in query.split() if t.strip()]
            matched = [t for t in q_terms if t in entry.content.lower()]
            note = (
                f"semantic={semantic:.3f} | {h_note} "
                + (f"| matched: {', '.join(matched[:3])}" if matched else "")
                + " | ranker=openai_text-embedding-3-small"
            )

            if combined < min_score:
                continue
            results.append(
                RetrievalResult(
                    entry=entry,
                    relevance_score=combined,
                    evidence_note=note,
                    is_active=entry.is_active(),
                    age_days=(now - entry.created_at) / 86400,
                    tfidf_score=0.0,
                    ranker_used=SemanticSearchStatus.ACTIVE_RANKER_OPENAI,
                    semantic_score=semantic,
                )
            )

        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results[:max_results]

    def _rank_tfidf(
        self,
        query: str,
        entries: List[MemoryEntry],
        max_results: int,
        min_score: float,
    ) -> List[RetrievalResult]:
        """Rank using TF-IDF (fallback)."""
        tfidf_scored = TfIdfRanker.score(query, entries)
        tfidf_map: Dict[str, float] = {e.entry_id: s for e, s in tfidf_scored}

        now = time.time()
        results = []
        q_terms = [t.strip().lower() for t in query.split() if t.strip()]
        for entry in entries:
            tfidf = tfidf_map.get(entry.entry_id, 0.0)
            heuristic, h_note = _heuristic_score(entry)
            combined = 0.6 * min(tfidf * 5.0, 1.0) + 0.4 * heuristic

            matched = [t for t in q_terms if t in entry.content.lower()]
            note = (
                f"tfidf={tfidf:.3f} | {h_note} "
                + (f"| matched: {', '.join(matched[:3])}" if matched else "")
                + " | ranker=tfidf_local"
            )

            if combined < min_score:
                continue
            results.append(
                RetrievalResult(
                    entry=entry,
                    relevance_score=min(combined, 1.0),
                    evidence_note=note,
                    is_active=entry.is_active(),
                    age_days=(now - entry.created_at) / 86400,
                    tfidf_score=tfidf,
                    ranker_used=SemanticSearchStatus.ACTIVE_RANKER_TFIDF,
                    semantic_score=0.0,
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
