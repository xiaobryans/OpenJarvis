"""Epic D — Research Platform Foundation (Wave 1 scaffold).

ResearchProvider model and ResearchProviderRegistry scaffold.
References existing connectors (hackernews, news_rss) and deep_research agent.

Status: SCAFFOLDED — provider model + registry exist; live search execution,
deep-research loop, and evidence synthesis not yet implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Provider types
PROVIDER_TYPE_WEB_SEARCH = "web_search"
PROVIDER_TYPE_NEWS = "news"
PROVIDER_TYPE_ACADEMIC = "academic"
PROVIDER_TYPE_INTERNAL = "internal"

PROVIDER_TYPES = frozenset({
    PROVIDER_TYPE_WEB_SEARCH,
    PROVIDER_TYPE_NEWS,
    PROVIDER_TYPE_ACADEMIC,
    PROVIDER_TYPE_INTERNAL,
})

# Approval policies
POLICY_AUTO = "auto"
POLICY_REQUIRES_APPROVAL = "requires_approval"
POLICY_HARD_GATE = "hard_gate"

# Provider statuses
STATUS_REGISTERED = "registered"
STATUS_CONFIGURED = "configured"
STATUS_READY = "ready"
STATUS_REQUIRES_SETUP = "requires_setup"
STATUS_BLOCKED = "blocked"


@dataclass
class ResearchProvider:
    """A research provider registered in the Wave 1 research platform.

    Web search providers require approval (no unauthorized scraping).
    Internal providers can be auto-approved.
    """

    provider_id: str
    name: str
    provider_type: str          # web_search | news | academic | internal
    connector_id: str = ""      # references existing connectors/ (if available)
    requires_api_key: bool = False
    approval_policy: str = POLICY_REQUIRES_APPROVAL
    status: str = STATUS_REGISTERED
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "name": self.name,
            "provider_type": self.provider_type,
            "connector_id": self.connector_id,
            "requires_api_key": self.requires_api_key,
            "approval_policy": self.approval_policy,
            "status": self.status,
            "description": self.description,
        }

    def requires_approval(self) -> bool:
        return self.approval_policy in (POLICY_REQUIRES_APPROVAL, POLICY_HARD_GATE)


class ResearchProviderRegistry:
    """Registry of research providers (Wave 1 scaffold).

    Providers are registered here. Actual execution is not yet implemented.
    Web/external providers require approval to prevent unauthorized scraping.
    """

    def __init__(self) -> None:
        self._providers: Dict[str, ResearchProvider] = {}
        self._populate_builtins()

    def _populate_builtins(self) -> None:
        """Register scaffolded providers from existing connector inventory."""
        builtins = [
            ResearchProvider(
                provider_id="hackernews",
                name="Hacker News",
                provider_type=PROVIDER_TYPE_NEWS,
                connector_id="connectors/hackernews",
                requires_api_key=False,
                approval_policy=POLICY_AUTO,
                status=STATUS_REGISTERED,
                description="Public HN API — no auth required. Scaffolded, not yet wired.",
            ),
            ResearchProvider(
                provider_id="news_rss",
                name="News RSS",
                provider_type=PROVIDER_TYPE_NEWS,
                connector_id="connectors/news_rss",
                requires_api_key=False,
                approval_policy=POLICY_AUTO,
                status=STATUS_REGISTERED,
                description="RSS feed ingestion. Scaffolded, not yet wired.",
            ),
            ResearchProvider(
                provider_id="web_search_generic",
                name="Web Search (Generic)",
                provider_type=PROVIDER_TYPE_WEB_SEARCH,
                connector_id="",
                requires_api_key=True,
                approval_policy=POLICY_REQUIRES_APPROVAL,
                status=STATUS_REQUIRES_SETUP,
                description=(
                    "Generic web search — requires API key (Serper/Tavily/Brave) and "
                    "approval before use. No unauthorized scraping."
                ),
            ),
            ResearchProvider(
                provider_id="deep_research_agent",
                name="Deep Research Agent",
                provider_type=PROVIDER_TYPE_INTERNAL,
                connector_id="agents/deep_research",
                requires_api_key=False,
                approval_policy=POLICY_REQUIRES_APPROVAL,
                status=STATUS_REGISTERED,
                description=(
                    "Jarvis deep_research agent scaffold. Requires approval before "
                    "running multi-step research loops."
                ),
            ),
        ]
        for p in builtins:
            self._providers[p.provider_id] = p

    def register(self, provider: ResearchProvider) -> Dict[str, Any]:
        if provider.provider_type not in PROVIDER_TYPES:
            return {"ok": False, "error": f"Unknown provider_type: {provider.provider_type}"}
        if provider.requires_approval():
            provider.status = STATUS_REGISTERED
            self._providers[provider.provider_id] = provider
            return {
                "ok": False,
                "status": "approval_required",
                "reason": f"Research provider '{provider.provider_id}' requires approval before activation.",
            }
        self._providers[provider.provider_id] = provider
        return {"ok": True, "provider_id": provider.provider_id, "status": STATUS_REGISTERED}

    def get(self, provider_id: str) -> Optional[ResearchProvider]:
        return self._providers.get(provider_id)

    def list_providers(self) -> List[ResearchProvider]:
        return list(self._providers.values())


# ---------------------------------------------------------------------------
# Research result
# ---------------------------------------------------------------------------

@dataclass
class ResearchSource:
    title: str
    content: str
    url: str = ""
    provider_id: str = ""
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content[:300],
            "url": self.url,
            "provider_id": self.provider_id,
            "score": self.score,
        }


@dataclass
class ResearchResult:
    query: str
    provider_id: str
    ok: bool
    sources: List[ResearchSource] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "provider_id": self.provider_id,
            "ok": self.ok,
            "source_count": len(self.sources),
            "sources": [s.to_dict() for s in self.sources],
            "summary": self.summary,
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "event_id": self.event_id,
        }


def _log_research_event(
    provider_id: str,
    query: str,
    ok: bool,
    blocked: bool,
    approval_required: bool,
    detail: str,
) -> str:
    try:
        from openjarvis.workbench.event_log import (
            WorkbenchEventLog,
            EVENT_RESEARCH_QUERIED,
            EVENT_RESEARCH_BLOCKED,
            EVENT_APPROVAL_REQUIRED,
        )
        log = WorkbenchEventLog()
        etype = EVENT_RESEARCH_BLOCKED if blocked else (
            EVENT_APPROVAL_REQUIRED if approval_required else EVENT_RESEARCH_QUERIED
        )
        ev = log.push(
            session_id="wave1_research",
            task_id=f"{provider_id}:{query[:30]}",
            event_type=etype,
            title=f"Research {'blocked' if blocked else 'completed'}: {provider_id}",
            detail=detail,
            tone="error" if blocked else ("warning" if approval_required else "success"),
            metadata={"provider_id": provider_id, "query": query[:100], "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


def _query_local_knowledge(query: str) -> List[ResearchSource]:
    """Query local ingested knowledge store (no external deps)."""
    try:
        from openjarvis.wave.knowledge_platform import search_knowledge
        records = search_knowledge(query, max_results=5)
        return [
            ResearchSource(
                title=r.title,
                content=r.content,
                url="",
                provider_id="local_knowledge",
                score=1.0,
                metadata=r.metadata,
            )
            for r in records
        ]
    except Exception:
        return []


def _query_platform_info(query: str) -> List[ResearchSource]:
    """Return local platform information as research sources (always safe)."""
    try:
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        summary = get_wave_platform_summary()
        content = (
            f"Wave Platform Status: {summary['total_epics']} epics total. "
            f"Wave 1 scaffolded: {summary['wave1_scaffolded']}. "
            f"Wave 2-4 not implemented."
        )
        return [ResearchSource(
            title="Jarvis Wave Platform Status",
            content=content,
            url="",
            provider_id="internal",
            score=0.5,
            metadata={"type": "platform_info"},
        )]
    except Exception:
        return []


def run_local_query(
    query: str,
    provider_id: str = "local_knowledge",
) -> ResearchResult:
    """Run a local research query — no external API or key required.

    Query order:
    1. Local ingested knowledge records (from knowledge_platform)
    2. Local platform info (always available)

    External providers (web_search_generic, hackernews live) require approval or setup.
    """
    if not query or not query.strip():
        return ResearchResult(
            query=query,
            provider_id=provider_id,
            ok=False,
            error="Empty query",
        )

    # Safety check: unauthorized scraping patterns
    forbidden = ["captcha", "bypass", "credential", "password", "token", "secret"]
    q_lower = query.lower()
    for term in forbidden:
        if term in q_lower:
            eid = _log_research_event(provider_id, query, False, True, False,
                                       f"Query blocked: forbidden term '{term}'")
            return ResearchResult(
                query=query,
                provider_id=provider_id,
                ok=False,
                blocked=True,
                error=f"Research query blocked: contains forbidden term '{term}'",
                event_id=eid,
            )

    # Tavily provider — env-gated, approval-gated
    if provider_id == "tavily":
        try:
            from openjarvis.wave.tavily_provider import run_tavily_query, get_tavily_provider_status
            status = get_tavily_provider_status()
            if not status["key_configured"]:
                eid = _log_research_event(provider_id, query, False, False, True,
                                           "TAVILY_API_KEY not set")
                return ResearchResult(
                    query=query,
                    provider_id=provider_id,
                    ok=False,
                    approval_required=True,
                    error="TAVILY_API_KEY not configured. Set env var to enable Tavily queries.",
                    event_id=eid,
                )
            tr = run_tavily_query(query, approved=False)  # approval gate enforced
            if tr.blocked:
                return ResearchResult(
                    query=query, provider_id=provider_id, ok=False,
                    blocked=tr.blocked, error=tr.error, event_id=tr.event_id,
                )
            if tr.approval_required:
                return ResearchResult(
                    query=query, provider_id=provider_id, ok=False,
                    approval_required=True, error=tr.error, event_id=tr.event_id,
                )
            sources = [
                ResearchSource(
                    title=s.get("title", ""),
                    content=s.get("content", ""),
                    url=s.get("url", ""),
                    provider_id="tavily",
                    score=s.get("score", 0.0),
                )
                for s in tr.sources
            ]
            return ResearchResult(
                query=query, provider_id="tavily", ok=True,
                sources=sources, summary=tr.answer or f"{len(sources)} results",
                event_id=tr.event_id,
            )
        except Exception as exc:
            return ResearchResult(query=query, provider_id=provider_id, ok=False, error=str(exc))

    # web_search_generic — requires key + approval
    if provider_id == "web_search_generic":
        eid = _log_research_event(provider_id, query, False, False, True,
                                   "web_search_generic requires API key + approval")
        return ResearchResult(
            query=query,
            provider_id=provider_id,
            ok=False,
            approval_required=True,
            error=(
                "Web search provider requires API key (Serper/Tavily/Brave) and approval. "
                "Set TAVILY_API_KEY and use provider_id='tavily' to enable."
            ),
            event_id=eid,
        )

    # Local knowledge search
    sources = _query_local_knowledge(query)

    # Always append platform info as a fallback source
    sources.extend(_query_platform_info(query))

    if not sources:
        sources = [ResearchSource(
            title="No results",
            content=f"No local knowledge records found for query: {query}",
            url="",
            provider_id="local_knowledge",
            score=0.0,
        )]

    summary = f"Found {len(sources)} source(s) for query '{query}' via {provider_id}."
    eid = _log_research_event(provider_id, query, True, False, False,
                               f"Query returned {len(sources)} sources")

    return ResearchResult(
        query=query,
        provider_id=provider_id,
        ok=True,
        sources=sources,
        summary=summary,
        event_id=eid,
    )


def get_research_platform_status() -> Dict[str, Any]:
    """Return research platform status for Mission Control / doctor."""
    reg = ResearchProviderRegistry()
    providers = reg.list_providers()
    by_status: Dict[str, int] = {}
    for p in providers:
        by_status[p.status] = by_status.get(p.status, 0) + 1

    tavily_status = "requires_setup"
    try:
        from openjarvis.wave.tavily_provider import get_tavily_provider_status
        ts = get_tavily_provider_status()
        tavily_status = ts["status"]
    except Exception:
        pass

    return {
        "epic": "epic_d",
        "wave": 1,
        "status": "ready",
        "provider_count": len(providers),
        "by_status": by_status,
        "local_query_implemented": True,
        "execution_implemented": True,
        "tavily_adapter_implemented": True,
        "tavily_status": tavily_status,
        "deep_research_loop_implemented": False,
        "approval_gate_enforced": True,
        "web_search_requires_setup": tavily_status != "ready",
        "scraping_blocked": True,
        "note": (
            f"Local knowledge query + Tavily adapter implemented. "
            f"Tavily: {tavily_status}. Web search approval-gated. Deep research loop: next slice."
        ),
    }


__all__ = [
    "ResearchProvider",
    "ResearchSource",
    "ResearchResult",
    "ResearchProviderRegistry",
    "PROVIDER_TYPE_WEB_SEARCH",
    "PROVIDER_TYPE_NEWS",
    "PROVIDER_TYPE_ACADEMIC",
    "PROVIDER_TYPE_INTERNAL",
    "POLICY_AUTO",
    "POLICY_REQUIRES_APPROVAL",
    "POLICY_HARD_GATE",
    "run_local_query",
    "get_research_platform_status",
]
