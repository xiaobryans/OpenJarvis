"""Memory OS Context Injection — build agent prompt context from JarvisMemory.

This module is the Memory OS layer for context injection.  It is separate from
openjarvis.tools.storage.context (which serves the vector/BM25 knowledge base).

Design:
  - Retrieves relevant active memories by keyword query
  - Formats them into a compact, auditable context block
  - Distinguishes "active context" (recent, high-confidence, relevant) from
    the raw archive (older, lower-confidence entries)
  - Never injects everything — bounded by max_items and max_chars
  - Includes full metadata for auditability (source, kind, age, confidence)
  - No model API calls required

Integration:
  - Used by AgentExecutor when context_from_memory=True AND JarvisMemory
    has a db_path configured (or defaults to ~/.jarvis/memory.db)
  - Returns InjectedContext that can be prepended to agent input_text
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.memory.retrieval import MemoryRetriever, RetrievalResult
from openjarvis.memory.store import JarvisMemory

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ITEMS = 5
_DEFAULT_MAX_CHARS = 2000
_DEFAULT_MIN_SCORE = 0.15


@dataclass
class InjectedContext:
    """Result of a memory context injection build.

    Fields
    ------
    context_text        Formatted context block ready to prepend to input
    entries_used        Number of entries included in context_text
    entries_searched    Number of entries searched (before filtering)
    query               The query used for retrieval
    project_id          Project scope used ('' = global)
    context_enabled     Whether context_from_memory was True
    metadata_summary    Short summary for audit logging
    results             The RetrievalResult objects that were included
    """

    context_text: str = ""
    entries_used: int = 0
    entries_searched: int = 0
    query: str = ""
    project_id: str = ""
    context_enabled: bool = False
    metadata_summary: str = ""
    results: List[RetrievalResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_text": self.context_text,
            "entries_used": self.entries_used,
            "entries_searched": self.entries_searched,
            "query": self.query[:80] if self.query else "",
            "project_id": self.project_id,
            "context_enabled": self.context_enabled,
            "metadata_summary": self.metadata_summary,
        }


def _format_entry_line(result: RetrievalResult) -> str:
    """Format a single memory entry as a compact context line."""
    entry = result.entry
    ts = _dt.datetime.fromtimestamp(
        entry.created_at, tz=_dt.timezone.utc
    ).strftime("%Y-%m-%d")
    parts = [f"[{ts}]"]
    if entry.source:
        parts.append(f"[src:{entry.source}]")
    parts.append(f"[{entry.kind}]")
    if entry.project_id:
        parts.append(f"[project:{entry.project_id}]")
    if entry.confidence < 0.8:
        parts.append(f"[conf:{entry.confidence:.1f}]")
    parts.append(entry.content)
    return " ".join(parts)


class MemoryContextBuilder:
    """Build agent context from JarvisMemory entries.

    Active context: recent, high-confidence, status=active entries.
    Archive: older or lower-confidence entries (not injected by default).

    Usage:
        builder = MemoryContextBuilder(db_path=...)
        ctx = builder.build_context(
            query="user preferences for code review",
            project_id="omnix",
            context_from_memory=True,
        )
        if ctx.context_text:
            input_text = ctx.context_text + "\\n\\n" + input_text
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        memory: Optional[JarvisMemory] = None,
    ) -> None:
        self._memory = memory or JarvisMemory(db_path=db_path)
        self._retriever = MemoryRetriever(self._memory)

    def build_context(
        self,
        query: str,
        *,
        project_id: str = "",
        context_from_memory: bool = True,
        max_items: int = _DEFAULT_MAX_ITEMS,
        max_chars: int = _DEFAULT_MAX_CHARS,
        min_score: float = _DEFAULT_MIN_SCORE,
        active_only: bool = True,
    ) -> InjectedContext:
        """Build memory context for injection into agent input.

        Parameters
        ----------
        query               The agent's current input/question (used for retrieval)
        project_id          Restrict retrieval to a project
        context_from_memory Whether injection is enabled
        max_items           Max number of memory entries to include
        max_chars           Max character budget for context block
        min_score           Minimum relevance score (0.0–1.0)
        active_only         Only include active (non-expired) entries

        Returns
        -------
        InjectedContext — context_text is '' if no relevant memories found
        or context_from_memory is False.
        """
        if not context_from_memory or not query.strip():
            return InjectedContext(
                query=query,
                project_id=project_id,
                context_enabled=context_from_memory,
                metadata_summary="context_from_memory=False or empty query — skipped",
            )

        try:
            results = self._retriever.retrieve(
                query,
                project_id=project_id or None,
                max_results=max_items * 2,
                min_score=min_score,
                active_only=active_only,
            )
        except Exception as exc:
            logger.warning("MemoryContextBuilder.build_context retrieval error: %s", exc)
            return InjectedContext(
                query=query,
                project_id=project_id,
                context_enabled=True,
                metadata_summary=f"retrieval_error={exc!r}",
            )

        entries_searched = len(results)
        # Apply char budget
        selected: List[RetrievalResult] = []
        char_budget = max_chars - 80  # reserve for header
        for r in results[:max_items]:
            line = _format_entry_line(r)
            if char_budget - len(line) < 0:
                break
            selected.append(r)
            char_budget -= len(line) + 1

        if not selected:
            return InjectedContext(
                query=query,
                project_id=project_id,
                context_enabled=True,
                entries_searched=entries_searched,
                metadata_summary=f"no_relevant_memories: retrieved={entries_searched}",
            )

        header = "[Memory OS — Active Context]"
        if project_id:
            header += f" [project:{project_id}]"
        lines = [header]
        for r in selected:
            lines.append("• " + _format_entry_line(r))
        context_text = "\n".join(lines)

        summary = (
            f"injected={len(selected)}/{entries_searched} memories "
            f"for query={query[:40]!r} project={project_id!r}"
        )
        logger.debug("MemoryContextBuilder: %s", summary)

        return InjectedContext(
            context_text=context_text,
            entries_used=len(selected),
            entries_searched=entries_searched,
            query=query,
            project_id=project_id,
            context_enabled=True,
            metadata_summary=summary,
            results=selected,
        )


__all__ = ["InjectedContext", "MemoryContextBuilder"]
