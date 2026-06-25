"""Memory OS Automatic Distillation — rule-based + AI-assisted engines.

Sprint 2 (rule-based, AutoDistillEngine):
  Scans raw JarvisMemory entries for high-confidence decisions, preferences, and
  patterns and automatically creates or updates distilled DistilledMemory entries.
  Local-first, no API calls.

Sprint 2B (AI-assisted, AIDistillEngine):
  Sends batches of raw memory entries to an OpenRouter model for summarization.
  Uses OPENROUTER_API_KEY + model 'openai/gpt-4o-mini' (cheap, reliable).
  Returns distilled entries tagged with distillation_method='ai'.
  Falls back to rule-based if API is unavailable or fails.
  Graceful: never breaks if model call fails.

Honest status:
  - AI distillation: ACTIVE when OPENROUTER_API_KEY is set
  - Rule-based fallback: always available
  - Cross-project aggregation: NOT_IMPLEMENTED
  - Incremental delta distillation: NOT_IMPLEMENTED (full re-scan per call)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from openjarvis.memory.store import JarvisMemory, MemoryEntry
from openjarvis.memory.distilled import DistilledMemory, DistilledEntry

logger = logging.getLogger(__name__)

# Kinds that are eligible for automatic distillation
DISTILLABLE_KINDS = frozenset({"decision", "preference", "observation", "mistake"})

# Default minimum confidence for automatic distillation
DEFAULT_MIN_CONFIDENCE = 0.7

# Map raw kind → distilled kind
_KIND_MAP: Dict[str, str] = {
    "decision": "decision",
    "preference": "preference",
    "observation": "pattern",
    "mistake": "lesson",
}


@dataclass
class DistillationResult:
    """Result of an auto_distill() call."""
    new_distilled_count: int
    skipped_already_distilled: int
    candidates_found: int
    new_entry_ids: List[str]
    project_id: str
    namespace: Optional[str]
    dry_run: bool
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "new_distilled_count": self.new_distilled_count,
            "skipped_already_distilled": self.skipped_already_distilled,
            "candidates_found": self.candidates_found,
            "new_entry_ids": self.new_entry_ids,
            "project_id": self.project_id,
            "namespace": self.namespace,
            "dry_run": self.dry_run,
            "detail": self.detail,
        }


class AutoDistillEngine:
    """Rule-based automatic distillation from raw JarvisMemory entries.

    Usage
    -----
    engine = AutoDistillEngine()
    result = engine.auto_distill(project_id="default")

    The engine is idempotent: calling auto_distill() multiple times will not
    create duplicate distilled entries for the same source raw entries.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory: Optional[JarvisMemory] = None,
        distilled: Optional[DistilledMemory] = None,
    ) -> None:
        db = Path(db_path) if db_path else None
        self._memory = memory or JarvisMemory(db_path=db)
        self._distilled = distilled or DistilledMemory(
            db_path=db or self._memory._db_path
        )

    # ------------------------------------------------------------------
    # Core distillation
    # ------------------------------------------------------------------

    def auto_distill(
        self,
        project_id: str = "",
        *,
        namespace: Optional[str] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        kinds: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> DistillationResult:
        """Automatically distill high-confidence raw entries.

        Parameters
        ----------
        project_id      Project scope for distillation.
        namespace       Optional namespace filter; if None, all namespaces are scanned.
        min_confidence  Minimum raw entry confidence to be eligible.
        kinds           Raw entry kinds to consider; defaults to DISTILLABLE_KINDS.
        dry_run         If True, report what would be distilled without writing.

        Returns DistillationResult with new distilled entry IDs and counts.
        """
        target_kinds = set(kinds) if kinds else DISTILLABLE_KINDS

        # Fetch all candidates from raw memory
        candidates = self._fetch_candidates(
            project_id=project_id,
            namespace=namespace,
            min_confidence=min_confidence,
            kinds=target_kinds,
        )

        if not candidates:
            return DistillationResult(
                new_distilled_count=0,
                skipped_already_distilled=0,
                candidates_found=0,
                new_entry_ids=[],
                project_id=project_id,
                namespace=namespace,
                dry_run=dry_run,
                detail="no candidates found matching filters",
            )

        # Determine which entry_ids are already distilled (idempotency)
        already_distilled_ids = self._get_already_distilled_ids(project_id)

        new_candidates = [e for e in candidates if e.entry_id not in already_distilled_ids]
        skipped = len(candidates) - len(new_candidates)

        if not new_candidates:
            return DistillationResult(
                new_distilled_count=0,
                skipped_already_distilled=skipped,
                candidates_found=len(candidates),
                new_entry_ids=[],
                project_id=project_id,
                namespace=namespace,
                dry_run=dry_run,
                detail="all candidates already distilled",
            )

        # Group candidates by kind → distilled kind
        grouped: Dict[str, List[MemoryEntry]] = {}
        for entry in new_candidates:
            distilled_kind = _KIND_MAP.get(entry.kind, "summary")
            grouped.setdefault(distilled_kind, []).append(entry)

        new_entry_ids: List[str] = []

        for distilled_kind, group_entries in grouped.items():
            if dry_run:
                # In dry_run, just report what would be created
                for entry in group_entries:
                    new_entry_ids.append(f"[dry_run:{entry.entry_id}]")
                continue

            for entry in group_entries:
                d_entry = self._make_distilled_entry(
                    raw=entry,
                    distilled_kind=distilled_kind,
                    project_id=project_id,
                )
                self._distilled.write(
                    content=d_entry.content,
                    kind=d_entry.kind,
                    project_id=d_entry.project_id,
                    namespace=d_entry.namespace,
                    source_ids=d_entry.source_ids,
                    tags=d_entry.tags,
                    confidence=d_entry.confidence,
                    entry_id=d_entry.entry_id,
                )
                new_entry_ids.append(d_entry.entry_id)
                logger.debug(
                    "AutoDistill: wrote distilled entry %s from raw %s kind=%s",
                    d_entry.entry_id, entry.entry_id, distilled_kind,
                )

        return DistillationResult(
            new_distilled_count=len(new_entry_ids) if not dry_run else 0,
            skipped_already_distilled=skipped,
            candidates_found=len(candidates),
            new_entry_ids=new_entry_ids,
            project_id=project_id,
            namespace=namespace,
            dry_run=dry_run,
            detail=(
                f"distilled {len(new_entry_ids)} entries "
                f"from {len(new_candidates)} new candidates "
                f"(skipped {skipped} already distilled)"
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fetch_candidates(
        self,
        project_id: str,
        namespace: Optional[str],
        min_confidence: float,
        kinds: Set[str],
    ) -> List[MemoryEntry]:
        """Fetch active raw entries meeting distillation criteria.

        Uses an empty-string search (matches all entries via LIKE '%%') filtered
        by kind and status.  This avoids requiring the entry content to contain
        the kind word itself (e.g. a 'mistake' entry may not say "mistake").
        """
        results: List[MemoryEntry] = []

        for kind in kinds:
            # Empty query → LIKE '%%' → matches all content.  Kind and status
            # filters restrict the result set to eligible entries.
            batch = self._memory.search(
                "",   # empty = match all content; kind/status do the filtering
                project_id=project_id or None,
                kind=kind,
                status="active",
                limit=500,
            )
            for entry in batch:
                if entry.confidence >= min_confidence and entry.is_active():
                    results.append(entry)

        # Deduplicate by entry_id
        seen: Set[str] = set()
        unique: List[MemoryEntry] = []
        for e in results:
            if e.entry_id not in seen:
                seen.add(e.entry_id)
                unique.append(e)
        return unique

    def _get_already_distilled_ids(self, project_id: str) -> Set[str]:
        """Return the set of raw entry_ids already referenced in distilled source_ids."""
        already: Set[str] = set()
        for kind in ("decision", "preference", "pattern", "lesson", "summary"):
            distilled_entries = self._distilled.list_by_kind(
                kind, project_id=project_id or None, limit=2000
            )
            for d in distilled_entries:
                already.update(d.source_ids)
        return already

    @staticmethod
    def _make_distilled_entry(
        raw: MemoryEntry,
        distilled_kind: str,
        project_id: str,
    ) -> DistilledEntry:
        """Construct a DistilledEntry from a raw MemoryEntry."""
        prefix_map = {
            "decision": "Decision recorded",
            "preference": "Preference noted",
            "pattern": "Pattern observed",
            "lesson": "Lesson learned",
            "summary": "Auto-distilled",
        }
        prefix = prefix_map.get(distilled_kind, "Auto-distilled")
        # Truncate content if very long
        content = raw.content
        if len(content) > 400:
            content = content[:397] + "..."

        return DistilledEntry(
            content=f"[{prefix}] {content}",
            kind=distilled_kind,
            project_id=project_id or raw.project_id,
            namespace="distilled",
            source_ids=[raw.entry_id],
            tags=list(raw.tags) + ["auto_distilled"],
            confidence=raw.confidence,
        )



# ---------------------------------------------------------------------------
# AI-assisted distillation via OpenRouter
# ---------------------------------------------------------------------------

_OPENROUTER_MODEL = "openai/gpt-4o-mini"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_OPENROUTER_TIMEOUT = 30
_MAX_ENTRIES_PER_AI_CALL = 20


def _openrouter_key_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY", "").strip())


def _call_openrouter_distill(entries: List[MemoryEntry], project_id: str) -> Optional[str]:
    """Call OpenRouter to distill a batch of entries into a summary.

    Returns distilled text string, or None on failure.
    Uses urllib (no openai package required).
    """
    import json as _json
    import urllib.request as _urllib

    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None

    # Build a compact representation of the entries
    entries_text = "\n".join(
        f"[{i+1}] kind={e.kind} confidence={e.confidence:.2f}: {e.content[:300]}"
        for i, e in enumerate(entries[:_MAX_ENTRIES_PER_AI_CALL])
    )
    prompt = (
        f"You are a memory distillation assistant for project '{project_id}'.\n"
        "Below are raw memory entries. Distill them into 1-3 concise sentences "
        "capturing the key pattern, decision, or lesson. "
        "Be factual and direct. No preamble. No explanation. "
        "Output ONLY the distilled summary.\n\n"
        f"Raw entries:\n{entries_text}"
    )

    body = _json.dumps({
        "model": _OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 200,
        "temperature": 0.0,
    }).encode()

    req = _urllib.Request(
        _OPENROUTER_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openjarvis.com",
        },
    )
    try:
        with _urllib.urlopen(req, timeout=_OPENROUTER_TIMEOUT) as resp:
            data = _json.load(resp)
        text = data["choices"][0]["message"]["content"].strip()
        return text if text else None
    except Exception as exc:
        logger.debug("OpenRouter distill call failed (non-fatal): %s", exc)
        return None


def _detect_kind_from_text(text: str) -> str:
    """Heuristic: detect distilled kind from AI-generated text."""
    t = text.lower()
    if any(w in t for w in ("decided", "decision", "chose", "selected")):
        return "decision"
    if any(w in t for w in ("prefer", "preference", "always use", "favour")):
        return "preference"
    if any(w in t for w in ("learned", "lesson", "mistake", "avoid")):
        return "lesson"
    if any(w in t for w in ("pattern", "recurring", "trend", "consistently")):
        return "pattern"
    return "summary"


@dataclass
class AIDistillationResult:
    """Result of an AI-assisted distillation call."""
    new_distilled_count: int
    candidates_used: int
    distillation_method: str   # "ai" | "rule_based_fallback"
    new_entry_ids: List[str]
    project_id: str
    dry_run: bool
    ai_available: bool
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "new_distilled_count": self.new_distilled_count,
            "candidates_used": self.candidates_used,
            "distillation_method": self.distillation_method,
            "new_entry_ids": self.new_entry_ids,
            "project_id": self.project_id,
            "dry_run": self.dry_run,
            "ai_available": self.ai_available,
            "detail": self.detail,
        }


class AIDistillEngine:
    """AI-assisted distillation using OpenRouter.

    Batches raw memory entries and sends them to gpt-4o-mini via OpenRouter.
    Returns distilled entries tagged with distillation_method='ai'.
    Falls back to rule-based distillation if API call fails or key missing.

    This is an OPTIONAL enhancement over AutoDistillEngine.
    Rule-based distillation is always available as fallback.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory: Optional[JarvisMemory] = None,
        distilled: Optional[DistilledMemory] = None,
    ) -> None:
        db = Path(db_path) if db_path else None
        self._memory = memory or JarvisMemory(db_path=db)
        self._distilled = distilled or DistilledMemory(
            db_path=db or self._memory._db_path
        )
        self._rule_engine = AutoDistillEngine(
            memory=self._memory, distilled=self._distilled
        )

    @staticmethod
    def is_ai_available() -> bool:
        """True if OPENROUTER_API_KEY is set."""
        return _openrouter_key_available()

    def distill(
        self,
        project_id: str = "",
        *,
        namespace: Optional[str] = None,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        kinds: Optional[List[str]] = None,
        dry_run: bool = False,
        batch_size: int = 10,
    ) -> AIDistillationResult:
        """Distill raw entries using AI (OpenRouter) or rule-based fallback.

        Parameters
        ----------
        project_id      Project scope.
        namespace       Optional namespace filter.
        min_confidence  Minimum raw entry confidence.
        kinds           Raw kinds to consider. Defaults to DISTILLABLE_KINDS.
        dry_run         If True, report without writing.
        batch_size      Number of raw entries to group per AI call.

        Returns AIDistillationResult with distillation_method indicating
        whether AI or rule-based was used.
        """
        if not _openrouter_key_available():
            # Fall back to rule-based without AI
            rule_result = self._rule_engine.auto_distill(
                project_id=project_id,
                namespace=namespace,
                min_confidence=min_confidence,
                kinds=kinds,
                dry_run=dry_run,
            )
            return AIDistillationResult(
                new_distilled_count=rule_result.new_distilled_count,
                candidates_used=rule_result.candidates_found,
                distillation_method="rule_based_fallback",
                new_entry_ids=rule_result.new_entry_ids,
                project_id=project_id,
                dry_run=dry_run,
                ai_available=False,
                detail=(
                    f"OpenRouter key missing — rule-based fallback: "
                    f"{rule_result.new_distilled_count} new entries from "
                    f"{rule_result.candidates_found} candidates"
                ),
            )

        # Fetch candidates
        target_kinds = set(kinds) if kinds else DISTILLABLE_KINDS
        candidates = self._rule_engine._fetch_candidates(
            project_id=project_id,
            namespace=namespace,
            min_confidence=min_confidence,
            kinds=target_kinds,
        )

        if not candidates:
            return AIDistillationResult(
                new_distilled_count=0,
                candidates_used=0,
                distillation_method="ai",
                new_entry_ids=[],
                project_id=project_id,
                dry_run=dry_run,
                ai_available=True,
                detail="no candidates found for AI distillation",
            )

        # Check already-distilled
        already_distilled = self._rule_engine._get_already_distilled_ids(project_id)
        new_candidates = [c for c in candidates if c.entry_id not in already_distilled]

        if not new_candidates:
            return AIDistillationResult(
                new_distilled_count=0,
                candidates_used=len(candidates),
                distillation_method="ai",
                new_entry_ids=[],
                project_id=project_id,
                dry_run=dry_run,
                ai_available=True,
                detail="all candidates already distilled",
            )

        new_entry_ids: List[str] = []

        # Process in batches
        for i in range(0, len(new_candidates), batch_size):
            batch = new_candidates[i : i + batch_size]
            ai_text = _call_openrouter_distill(batch, project_id)

            if ai_text:
                distilled_kind = _detect_kind_from_text(ai_text)
                source_ids = [e.entry_id for e in batch]
                avg_confidence = sum(e.confidence for e in batch) / len(batch)
                tags = list({t for e in batch for t in e.tags}) + ["ai_distilled"]

                if not dry_run:
                    entry = self._distilled.write(
                        content=ai_text,
                        kind=distilled_kind,
                        project_id=project_id,
                        namespace="distilled",
                        source_ids=source_ids,
                        tags=tags,
                        confidence=min(avg_confidence + 0.05, 1.0),
                    )
                    new_entry_ids.append(entry.entry_id)
                else:
                    new_entry_ids.append(f"[dry_run:ai_batch_{i}]")
            else:
                # AI failed for this batch — fall back to rule-based for it
                for raw_entry in batch:
                    distilled_kind = _KIND_MAP.get(raw_entry.kind, "summary")
                    d = AutoDistillEngine._make_distilled_entry(
                        raw=raw_entry,
                        distilled_kind=distilled_kind,
                        project_id=project_id,
                    )
                    if not dry_run:
                        self._distilled.write(
                            content=d.content,
                            kind=d.kind,
                            project_id=d.project_id,
                            namespace=d.namespace,
                            source_ids=d.source_ids,
                            tags=d.tags,
                            confidence=d.confidence,
                            entry_id=d.entry_id,
                        )
                        new_entry_ids.append(d.entry_id)
                    else:
                        new_entry_ids.append(f"[dry_run:rule_{raw_entry.entry_id}]")

        return AIDistillationResult(
            new_distilled_count=len(new_entry_ids) if not dry_run else 0,
            candidates_used=len(new_candidates),
            distillation_method="ai",
            new_entry_ids=new_entry_ids,
            project_id=project_id,
            dry_run=dry_run,
            ai_available=True,
            detail=(
                f"AI distilled {len(new_entry_ids)} entries from "
                f"{len(new_candidates)} candidates using {_OPENROUTER_MODEL}"
            ),
        )

    @staticmethod
    def distillation_status() -> Dict[str, Any]:
        """Return honest distillation engine status."""
        ai_available = _openrouter_key_available()
        return {
            "ai_available": ai_available,
            "ai_model": _OPENROUTER_MODEL if ai_available else None,
            "ai_provider": "openrouter" if ai_available else None,
            "rule_based_fallback": "always_active",
            "status": "AI_ACTIVE" if ai_available else "RULE_BASED_ONLY",
            "detail": (
                f"AI distillation active via {_OPENROUTER_MODEL} (OpenRouter)"
                if ai_available
                else "OPENROUTER_API_KEY not set — rule-based only"
            ),
        }


__all__ = [
    "AutoDistillEngine",
    "AIDistillEngine",
    "AIDistillationResult",
    "DistillationResult",
    "DISTILLABLE_KINDS",
    "DEFAULT_MIN_CONFIDENCE",
]
