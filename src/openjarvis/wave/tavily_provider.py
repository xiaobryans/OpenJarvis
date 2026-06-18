"""Epic D — Tavily Web Research Provider (Wave 1).

Env-gated adapter for Tavily search API.
- Reads TAVILY_API_KEY from environment (never prints/logs/stores the value).
- ready if key present; requires_setup if absent.
- Live queries are approval-gated.
- Unsafe queries (captcha bypass, credential extraction, scraping) are blocked.
- NEVER logs, prints, or persists the API key value.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_TAVILY_BASE_URL = "https://api.tavily.com/search"
_TAVILY_ENV_VAR = "TAVILY_API_KEY"

# Query safety: these terms are always blocked
_BLOCKED_QUERY_TERMS = [
    "captcha", "bypass", "credential", "password", "token",
    "secret", "api_key", "login session", "scrape", "unauthorized",
]

# Approval is required for any live external query
_LIVE_QUERY_REQUIRES_APPROVAL = True


def _get_api_key() -> Optional[str]:
    """Return API key from env or None. Never print/log the value."""
    return os.environ.get(_TAVILY_ENV_VAR) or None


def get_tavily_provider_status() -> Dict[str, Any]:
    """Return truthful provider status — ready if key in env, else requires_setup."""
    key_present = _get_api_key() is not None
    return {
        "provider_id": "tavily",
        "env_var": _TAVILY_ENV_VAR,
        "status": "ready" if key_present else "requires_setup",
        "key_configured": key_present,
        "live_query_approval_required": _LIVE_QUERY_REQUIRES_APPROVAL,
        "unsafe_queries_blocked": True,
        "note": (
            f"Set {_TAVILY_ENV_VAR} environment variable to enable live Tavily queries. "
            "All live queries remain approval-gated."
            if not key_present
            else f"Tavily key configured via {_TAVILY_ENV_VAR}. Live queries require approval."
        ),
    }


@dataclass
class TavilyResult:
    query: str
    ok: bool
    sources: List[Dict[str, Any]] = field(default_factory=list)
    answer: str = ""
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "ok": self.ok,
            "source_count": len(self.sources),
            "sources": self.sources[:5],
            "answer": self.answer,
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
        }


def _log_tavily_event(query: str, ok: bool, blocked: bool, detail: str) -> str:
    try:
        from openjarvis.workbench.event_log import (
            WorkbenchEventLog,
            EVENT_RESEARCH_QUERIED,
            EVENT_RESEARCH_BLOCKED,
        )
        log = WorkbenchEventLog()
        etype = EVENT_RESEARCH_BLOCKED if blocked else EVENT_RESEARCH_QUERIED
        ev = log.push(
            session_id="wave1_tavily",
            task_id=f"tavily:{query[:30]}",
            event_type=etype,
            title=f"Tavily {'blocked' if blocked else 'query'}",
            detail=detail,
            tone="error" if blocked else "success",
            metadata={"provider": "tavily", "ok": ok, "query_len": len(query)},
        )
        return ev.id
    except Exception:
        return ""


def _check_query_safety(query: str) -> Optional[str]:
    """Return blocking reason if query is unsafe, else None."""
    q_lower = query.lower()
    for term in _BLOCKED_QUERY_TERMS:
        if term in q_lower:
            return f"Query contains forbidden term: '{term}'"
    return None


def run_tavily_query(
    query: str,
    *,
    max_results: int = 5,
    approved: bool = False,
) -> TavilyResult:
    """Run a Tavily web search query.

    Safety:
    - Unsafe queries are always blocked.
    - Live queries require approved=True (approval gate enforced by caller).
    - Key must be set in TAVILY_API_KEY env var.

    The API key value is NEVER logged, printed, or returned.
    """
    if not query or not query.strip():
        return TavilyResult(query=query, ok=False, error="Empty query")

    # Safety check
    block_reason = _check_query_safety(query)
    if block_reason:
        eid = _log_tavily_event(query, False, True, block_reason)
        return TavilyResult(
            query=query,
            ok=False,
            blocked=True,
            error=block_reason,
            event_id=eid,
        )

    # Approval gate
    if _LIVE_QUERY_REQUIRES_APPROVAL and not approved:
        eid = _log_tavily_event(query, False, False,
                                 "Live Tavily query requires approval=True")
        return TavilyResult(
            query=query,
            ok=False,
            approval_required=True,
            error=(
                "Live web research requires explicit approval. "
                "Pass approved=True after getting owner approval."
            ),
            event_id=eid,
        )

    # Key check
    key = _get_api_key()
    if not key:
        return TavilyResult(
            query=query,
            ok=False,
            error=f"TAVILY_API_KEY not set. Set this env var to enable live queries.",
        )

    # Execute live query
    try:
        import httpx

        payload = {
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": True,
        }
        # Headers use key directly — never stored/logged
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

        resp = httpx.post(_TAVILY_BASE_URL, json=payload, headers=headers, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

        sources = []
        for r in data.get("results", []):
            sources.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")[:300],
                "score": r.get("score", 0.0),
            })

        answer = data.get("answer", "")
        eid = _log_tavily_event(query, True, False,
                                 f"Tavily returned {len(sources)} results")
        return TavilyResult(
            query=query,
            ok=True,
            sources=sources,
            answer=answer,
            event_id=eid,
        )

    except Exception as exc:
        eid = _log_tavily_event(query, False, False, str(exc))
        return TavilyResult(
            query=query,
            ok=False,
            error=f"Tavily query failed: {exc}",
            event_id=eid,
        )


__all__ = [
    "TavilyResult",
    "get_tavily_provider_status",
    "run_tavily_query",
]
