"""Memory OS Automatic Distillation — rule-based local-first distillation engine.

What this does:
  Scans raw JarvisMemory entries for high-confidence decisions, preferences, and
  patterns and automatically creates or updates distilled DistilledMemory entries.

Algorithm:
  1. Fetch raw entries with confidence >= min_confidence and kind in target_kinds
  2. Skip entries whose entry_id already appears in source_ids of existing
     distilled entries (idempotent)
  3. Group new candidates by kind
  4. For each group, create a DistilledEntry of the matching kind, referencing
     the source entry_ids
  5. Return DistillationResult with counts and new distilled entry IDs

This is deliberately rule-based and local-first.  It does not use AI model calls
or external services.  A model-assisted distillation pipeline is planned for a
future sprint.

Honest status:
  - AI-assisted distillation: NOT_IMPLEMENTED (planned future sprint)
  - Cross-project aggregation: NOT_IMPLEMENTED
  - Incremental delta distillation: NOT_IMPLEMENTED (full re-scan per call)
"""

from __future__ import annotations

import logging
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
    result = engine.auto_distill(project_id="omnix")

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


__all__ = [
    "AutoDistillEngine",
    "DistillationResult",
    "DISTILLABLE_KINDS",
    "DEFAULT_MIN_CONFIDENCE",
]
