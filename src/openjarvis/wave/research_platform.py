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


def get_research_platform_status() -> Dict[str, Any]:
    """Return research platform status for Mission Control / doctor."""
    reg = ResearchProviderRegistry()
    providers = reg.list_providers()
    by_status = {}
    for p in providers:
        by_status[p.status] = by_status.get(p.status, 0) + 1
    return {
        "epic": "epic_d",
        "wave": 1,
        "status": "scaffolded",
        "provider_count": len(providers),
        "by_status": by_status,
        "execution_implemented": False,
        "deep_research_loop_implemented": False,
        "approval_gate_enforced": True,
        "web_search_requires_setup": True,
        "note": "ResearchProvider model + registry exist. Live execution is Wave 1 next slice.",
    }


__all__ = [
    "ResearchProvider",
    "ResearchProviderRegistry",
    "PROVIDER_TYPE_WEB_SEARCH",
    "PROVIDER_TYPE_NEWS",
    "PROVIDER_TYPE_ACADEMIC",
    "PROVIDER_TYPE_INTERNAL",
    "POLICY_AUTO",
    "POLICY_REQUIRES_APPROVAL",
    "POLICY_HARD_GATE",
    "get_research_platform_status",
]
