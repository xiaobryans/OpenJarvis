"""Memory Quality Matrix and Stale Conflict Handling.

Extends JarvisMemory with:
  - MemoryQualityMatrix: per-namespace quality assessment
  - StaleConflictDetector: detect and report stale or conflicting entries
  - "Insufficient evidence to verify" behavior for unknown/unverifiable memories
  - Provenance requirement enforcement

Design rules:
  - No invented memory — entries without provenance are flagged, not used.
  - Stale entries (older than threshold) are reported as STALE, not silently used.
  - Conflicting entries are reported with both candidates — never auto-resolved.
  - Unknown/unverifiable memories produce "Insufficient evidence to verify" result.
  - Project-scoped: quality checks respect namespace and project_id isolation.
  - No raw chain-of-thought in any quality record.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_DEFAULT_STALE_THRESHOLD_DAYS = 30  # entries older than this are flagged stale
_MIN_CONFIDENCE = 0.3               # below this → LOW_CONFIDENCE


# ---------------------------------------------------------------------------
# MemoryQualityRecord
# ---------------------------------------------------------------------------

@dataclass
class MemoryQualityRecord:
    """Quality assessment for a single memory entry."""
    entry_id: str
    namespace: str
    project_id: str
    quality_status: str     # "ok" | "stale" | "low_confidence" | "no_provenance" | "conflict"
    quality_note: str
    confidence: float
    age_days: float
    has_provenance: bool    # source field is non-empty
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "namespace": self.namespace,
            "project_id": self.project_id,
            "quality_status": self.quality_status,
            "quality_note": self.quality_note,
            "confidence": self.confidence,
            "age_days": round(self.age_days, 1),
            "has_provenance": self.has_provenance,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


@dataclass
class ConflictRecord:
    """Two conflicting memory entries for the same subject in the same namespace."""
    namespace: str
    project_id: str
    entry_id_a: str
    entry_id_b: str
    conflict_summary: str
    resolution: str = "UNRESOLVED — requires Bryan review"
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "namespace": self.namespace,
            "project_id": self.project_id,
            "entry_id_a": self.entry_id_a,
            "entry_id_b": self.entry_id_b,
            "conflict_summary": self.conflict_summary,
            "resolution": self.resolution,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


# ---------------------------------------------------------------------------
# MemoryQualityMatrix
# ---------------------------------------------------------------------------

class MemoryQualityMatrix:
    """Assess the quality of entries in a JarvisMemory namespace.

    Usage:
        matrix = MemoryQualityMatrix(memory)
        report = matrix.assess(namespace="project:omnix", project_id="omnix")
    """

    def __init__(
        self,
        memory: Any,   # JarvisMemory instance
        stale_threshold_days: float = _DEFAULT_STALE_THRESHOLD_DAYS,
    ) -> None:
        self._memory = memory
        self._stale_threshold_sec = stale_threshold_days * 86400

    def assess(
        self,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """Assess memory quality for a namespace/project.

        Returns structured quality report.
        """
        ns = namespace or "global"
        try:
            entries = self._memory.list_by_namespace(
                ns,
                project_id=project_id,
                limit=limit,
            )
        except Exception as exc:
            return {
                "status": "error",
                "error": str(exc),
                "message": "Insufficient evidence to verify — memory store unavailable.",
            }

        if not entries:
            return {
                "status": "empty",
                "namespace": namespace,
                "project_id": project_id,
                "entry_count": 0,
                "message": "No memory entries found for this namespace/project.",
            }

        now = time.time()
        quality_records: List[MemoryQualityRecord] = []
        stale_count = 0
        no_provenance_count = 0
        low_confidence_count = 0
        ok_count = 0

        for entry in entries:
            age_sec = now - entry.created_at
            age_days = age_sec / 86400
            has_provenance = bool(getattr(entry, "source", ""))
            confidence = getattr(entry, "confidence", 1.0)
            is_stale = age_sec > self._stale_threshold_sec

            if is_stale:
                status = "stale"
                note = (
                    f"Entry is {age_days:.0f} days old "
                    f"(threshold: {self._stale_threshold_sec / 86400:.0f}d). "
                    "May no longer reflect current state. Verify before use."
                )
                stale_count += 1
            elif not has_provenance:
                status = "no_provenance"
                note = (
                    "Entry has no source/provenance. "
                    "Insufficient evidence to verify origin. "
                    "Treat with caution."
                )
                no_provenance_count += 1
            elif confidence < _MIN_CONFIDENCE:
                status = "low_confidence"
                note = f"Confidence {confidence:.2f} below minimum {_MIN_CONFIDENCE}."
                low_confidence_count += 1
            else:
                status = "ok"
                note = "Entry meets quality standards."
                ok_count += 1

            quality_records.append(MemoryQualityRecord(
                entry_id=entry.entry_id,
                namespace=getattr(entry, "namespace", namespace or ""),
                project_id=getattr(entry, "project_id", project_id or ""),
                quality_status=status,
                quality_note=note,
                confidence=confidence,
                age_days=age_days,
                has_provenance=has_provenance,
            ))

        total = len(quality_records)
        return {
            "status": "assessed",
            "namespace": namespace,
            "project_id": project_id,
            "entry_count": total,
            "ok_count": ok_count,
            "stale_count": stale_count,
            "no_provenance_count": no_provenance_count,
            "low_confidence_count": low_confidence_count,
            "quality_score": round(ok_count / total, 2) if total > 0 else 0.0,
            "quality_records": [r.to_dict() for r in quality_records[:20]],  # sample
            "stale_threshold_days": self._stale_threshold_sec / 86400,
            "no_raw_chain_of_thought": True,
        }


# ---------------------------------------------------------------------------
# StaleConflictDetector
# ---------------------------------------------------------------------------

class StaleConflictDetector:
    """Detect stale entries and potential content conflicts in memory.

    Conflict detection: two entries in the same namespace with very similar
    short content (exact match on first 60 chars trimmed) → flagged as conflict.

    Full semantic deduplication is PLANNED (requires embedding model).
    This is keyword/prefix-based detection only.
    """

    def __init__(self, memory: Any) -> None:
        self._memory = memory

    def find_stale(
        self,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
        stale_threshold_days: float = _DEFAULT_STALE_THRESHOLD_DAYS,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """Return entries older than stale_threshold_days."""
        ns = namespace or "global"
        try:
            entries = self._memory.list_by_namespace(
                ns,
                project_id=project_id,
                limit=limit,
            )
        except Exception:
            return []

        threshold_sec = stale_threshold_days * 86400
        now = time.time()
        stale = []
        for entry in entries:
            age_sec = now - entry.created_at
            if age_sec > threshold_sec:
                stale.append({
                    "entry_id": entry.entry_id,
                    "namespace": getattr(entry, "namespace", ""),
                    "age_days": round(age_sec / 86400, 1),
                    "source": getattr(entry, "source", ""),
                    "content_preview": entry.content[:80] if entry.content else "",
                    "resolution": "STALE — verify or delete before trusting.",
                })
        return stale

    def find_conflicts(
        self,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
        limit: int = 200,
    ) -> List[ConflictRecord]:
        """Find potentially conflicting entries (prefix-based, not semantic).

        Note: semantic deduplication requires embedding model (PLANNED).
        """
        ns = namespace or "global"
        try:
            entries = self._memory.list_by_namespace(
                ns,
                project_id=project_id,
                limit=limit,
            )
        except Exception:
            return []

        conflicts: List[ConflictRecord] = []
        seen: Dict[str, str] = {}  # prefix → entry_id
        for entry in entries:
            prefix = (entry.content or "").strip()[:60].lower()
            if not prefix:
                continue
            if prefix in seen:
                conflicts.append(ConflictRecord(
                    namespace=getattr(entry, "namespace", namespace or ""),
                    project_id=getattr(entry, "project_id", project_id or ""),
                    entry_id_a=seen[prefix],
                    entry_id_b=entry.entry_id,
                    conflict_summary=(
                        f"Two entries share the same 60-char content prefix. "
                        f"Possible duplicate or conflict. "
                        f"Content preview: '{prefix[:40]}...'"
                    ),
                ))
            else:
                seen[prefix] = entry.entry_id
        return conflicts

    def get_conflict_summary(
        self,
        namespace: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return structured conflict/stale summary for doctor checks."""
        stale = self.find_stale(namespace=namespace, project_id=project_id)
        conflicts = self.find_conflicts(namespace=namespace, project_id=project_id)
        return {
            "namespace": namespace,
            "project_id": project_id,
            "stale_count": len(stale),
            "conflict_count": len(conflicts),
            "stale_entries": stale[:5],
            "conflicts": [c.to_dict() for c in conflicts[:5]],
            "resolution_policy": (
                "Stale: verify or delete before trusting. "
                "Conflicts: require Bryan review — never auto-resolved. "
                "Unknown/unverifiable: 'Insufficient evidence to verify'."
            ),
            "no_raw_chain_of_thought": True,
        }


# ---------------------------------------------------------------------------
# Insufficient evidence helper
# ---------------------------------------------------------------------------

def insufficient_evidence(context: str = "") -> Dict[str, Any]:
    """Return a structured 'Insufficient evidence to verify' response.

    Used when a memory recall has no verifiable provenance or is stale.
    """
    return {
        "status": "insufficient_evidence",
        "message": "Insufficient evidence to verify.",
        "context": context,
        "action": "Do not use this memory without verification.",
        "no_raw_chain_of_thought": True,
    }


__all__ = [
    "MemoryQualityRecord",
    "ConflictRecord",
    "MemoryQualityMatrix",
    "StaleConflictDetector",
    "insufficient_evidence",
]
