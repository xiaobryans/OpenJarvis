"""Epic C — Knowledge Platform Foundation (Wave 1 scaffold).

KnowledgeSource model and KnowledgeSourceRegistry scaffold.
References existing connectors/ for data sources.

Status: SCAFFOLDED — source model + registry exist; ingestion pipelines,
hybrid search, and memory-backed retrieval not yet wired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Source types
SOURCE_TYPE_FILE = "file"
SOURCE_TYPE_URL = "url"
SOURCE_TYPE_DATABASE = "database"
SOURCE_TYPE_CONNECTOR = "connector"  # references existing connectors/
SOURCE_TYPE_MEMORY = "memory"        # references memory/store

SOURCE_TYPES = frozenset({
    SOURCE_TYPE_FILE,
    SOURCE_TYPE_URL,
    SOURCE_TYPE_DATABASE,
    SOURCE_TYPE_CONNECTOR,
    SOURCE_TYPE_MEMORY,
})

# Access policies
ACCESS_PUBLIC = "public"
ACCESS_REQUIRES_APPROVAL = "requires_approval"
ACCESS_PRIVATE = "private"

# Source statuses
STATUS_REGISTERED = "registered"
STATUS_INGESTING = "ingesting"
STATUS_READY = "ready"
STATUS_ERROR = "error"
STATUS_BLOCKED = "blocked"


@dataclass
class KnowledgeSource:
    """A knowledge source registered in the Wave 1 knowledge platform.

    Sensitive sources (private files, databases, PII connectors) require
    approval before ingestion.
    """

    source_id: str
    name: str
    source_type: str                # file | url | database | connector | memory
    connector_id: str = ""          # references connectors/ module (if source_type=connector)
    path: str = ""                  # file path or URL
    access_policy: str = ACCESS_REQUIRES_APPROVAL
    pii_risk: bool = False
    status: str = STATUS_REGISTERED
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_type": self.source_type,
            "connector_id": self.connector_id,
            "path": self.path,
            "access_policy": self.access_policy,
            "pii_risk": self.pii_risk,
            "status": self.status,
            "description": self.description,
        }

    def requires_approval(self) -> bool:
        return self.access_policy in (ACCESS_REQUIRES_APPROVAL, ACCESS_PRIVATE) or self.pii_risk


class KnowledgeSourceRegistry:
    """Registry of knowledge sources (Wave 1 scaffold).

    Ingestion is not wired — sources are registered and queued.
    Sensitive sources require approval before ingestion starts.
    """

    def __init__(self) -> None:
        self._sources: Dict[str, KnowledgeSource] = {}
        self._populate_builtins()

    def _populate_builtins(self) -> None:
        """Register scaffolded knowledge sources from existing connectors."""
        # Reference existing connectors — not yet ingested
        connector_map = [
            ("apple_notes", "Apple Notes", SOURCE_TYPE_CONNECTOR, "connectors/apple_notes"),
            ("apple_contacts", "Apple Contacts", SOURCE_TYPE_CONNECTOR, "connectors/apple_contacts"),
            ("dropbox", "Dropbox", SOURCE_TYPE_CONNECTOR, "connectors/dropbox"),
        ]
        for sid, name, stype, conn_id in connector_map:
            self._sources[sid] = KnowledgeSource(
                source_id=sid,
                name=name,
                source_type=stype,
                connector_id=conn_id,
                access_policy=ACCESS_REQUIRES_APPROVAL,
                pii_risk=True,
                status=STATUS_REGISTERED,
                description=f"Scaffolded — connector reference only; ingestion not yet wired.",
            )

    def register(self, source: KnowledgeSource) -> Dict[str, Any]:
        if source.source_type not in SOURCE_TYPES:
            return {"ok": False, "error": f"Unknown source_type: {source.source_type}"}
        if source.requires_approval():
            source.status = STATUS_REGISTERED
            self._sources[source.source_id] = source
            return {
                "ok": False,
                "status": "approval_required",
                "reason": f"Source '{source.source_id}' requires approval before ingestion (pii_risk={source.pii_risk})",
            }
        self._sources[source.source_id] = source
        return {"ok": True, "source_id": source.source_id, "status": STATUS_REGISTERED}

    def get(self, source_id: str) -> Optional[KnowledgeSource]:
        return self._sources.get(source_id)

    def list_sources(self) -> List[KnowledgeSource]:
        return list(self._sources.values())


def get_knowledge_platform_status() -> Dict[str, Any]:
    """Return knowledge platform status for Mission Control / doctor."""
    reg = KnowledgeSourceRegistry()
    sources = reg.list_sources()
    by_status = {}
    for s in sources:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    return {
        "epic": "epic_c",
        "wave": 1,
        "status": "scaffolded",
        "source_count": len(sources),
        "by_status": by_status,
        "ingestion_implemented": False,
        "hybrid_search_implemented": False,
        "approval_gate_enforced": True,
        "pii_sources_require_approval": True,
        "note": "KnowledgeSource model + registry exist. Ingestion pipelines are Wave 1 next slice.",
    }


__all__ = [
    "KnowledgeSource",
    "KnowledgeSourceRegistry",
    "SOURCE_TYPE_FILE",
    "SOURCE_TYPE_URL",
    "SOURCE_TYPE_DATABASE",
    "SOURCE_TYPE_CONNECTOR",
    "SOURCE_TYPE_MEMORY",
    "ACCESS_PUBLIC",
    "ACCESS_REQUIRES_APPROVAL",
    "ACCESS_PRIVATE",
    "get_knowledge_platform_status",
]
