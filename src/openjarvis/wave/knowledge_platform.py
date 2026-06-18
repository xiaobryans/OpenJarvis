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


# ---------------------------------------------------------------------------
# Knowledge record + in-memory store
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeRecord:
    """A normalized knowledge unit produced by ingestion."""
    record_id: str
    source_id: str
    title: str = ""
    content: str = ""
    content_type: str = "text"  # text | markdown | json
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source_id": self.source_id,
            "title": self.title,
            "content": self.content[:500],  # truncate for display
            "content_type": self.content_type,
            "metadata": self.metadata,
        }


# In-memory knowledge store: source_id → list of records
_knowledge_store: Dict[str, List[KnowledgeRecord]] = {}


def _log_knowledge_event(
    source_id: str,
    ok: bool,
    blocked: bool,
    approval_required: bool,
    detail: str,
) -> str:
    try:
        from openjarvis.workbench.event_log import (
            WorkbenchEventLog,
            EVENT_KNOWLEDGE_INGESTED,
            EVENT_KNOWLEDGE_BLOCKED,
            EVENT_APPROVAL_REQUIRED,
        )
        log = WorkbenchEventLog()
        etype = EVENT_KNOWLEDGE_BLOCKED if blocked else (
            EVENT_APPROVAL_REQUIRED if approval_required else EVENT_KNOWLEDGE_INGESTED
        )
        ev = log.push(
            session_id="wave1_knowledge",
            task_id=source_id,
            event_type=etype,
            title=f"Knowledge ingestion {'blocked' if blocked else 'complete'}: {source_id}",
            detail=detail,
            tone="error" if blocked else ("warning" if approval_required else "success"),
            metadata={"source_id": source_id, "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


@dataclass
class IngestionResult:
    source_id: str
    ok: bool
    record_count: int = 0
    records: List[KnowledgeRecord] = field(default_factory=list)
    error: str = ""
    blocked: bool = False
    approval_required: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "ok": self.ok,
            "record_count": self.record_count,
            "records": [r.to_dict() for r in self.records],
            "error": self.error,
            "blocked": self.blocked,
            "approval_required": self.approval_required,
            "event_id": self.event_id,
        }


def ingest_local_source(
    text: str,
    source_id: str,
    title: str = "",
    content_type: str = "text",
    metadata: Optional[Dict[str, Any]] = None,
) -> IngestionResult:
    """Ingest plain text/markdown as a knowledge source (local, no external deps).

    This is the safe local ingestion path for Wave 1.
    External connectors (apple_notes, dropbox) remain requires_approval.
    """
    import hashlib
    import time

    if not text or not text.strip():
        return IngestionResult(
            source_id=source_id,
            ok=False,
            error="Empty content — nothing to ingest",
        )

    # Split into chunks (simple paragraph split, max 1000 chars each)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [text[:1000]]

    records: List[KnowledgeRecord] = []
    ts = str(int(time.time()))
    for i, para in enumerate(paragraphs[:20]):  # max 20 chunks per call
        rid = hashlib.md5(f"{source_id}:{i}:{para[:50]}".encode()).hexdigest()[:12]
        records.append(KnowledgeRecord(
            record_id=rid,
            source_id=source_id,
            title=title or f"{source_id} chunk {i+1}",
            content=para,
            content_type=content_type,
            metadata={**(metadata or {}), "chunk_index": i, "ingested_at": ts},
        ))

    _knowledge_store.setdefault(source_id, []).extend(records)
    detail = f"Ingested {len(records)} records from local source '{source_id}'"
    eid = _log_knowledge_event(source_id, True, False, False, detail)

    return IngestionResult(
        source_id=source_id,
        ok=True,
        record_count=len(records),
        records=records,
        event_id=eid,
    )


def ingest_connector_source(source_id: str) -> IngestionResult:
    """Attempt ingestion from a registered connector source.

    Only public/non-PII sources are auto-approved.
    PII or private sources always require approval.
    """
    reg = KnowledgeSourceRegistry()
    source = reg.get(source_id)
    if source is None:
        return IngestionResult(source_id=source_id, ok=False, error=f"Source not found: {source_id}")

    if source.requires_approval():
        eid = _log_knowledge_event(source_id, False, False, True,
                                    f"Source {source_id} requires approval (pii_risk={source.pii_risk})")
        return IngestionResult(
            source_id=source_id,
            ok=False,
            approval_required=True,
            error=f"Source '{source_id}' requires approval before ingestion (pii_risk={source.pii_risk})",
            event_id=eid,
        )

    # Only public no-PII sources reach here
    return ingest_local_source(
        text=f"Connector source: {source.name}\nConnector ID: {source.connector_id}",
        source_id=source_id,
        title=source.name,
        metadata={"connector_id": source.connector_id},
    )


def get_ingested_records(source_id: str) -> List[KnowledgeRecord]:
    return _knowledge_store.get(source_id, [])


def get_all_ingested_records() -> Dict[str, List[KnowledgeRecord]]:
    return dict(_knowledge_store)


def search_knowledge(query: str, max_results: int = 5) -> List[KnowledgeRecord]:
    """Simple keyword search over ingested knowledge records."""
    query_lower = query.lower()
    results: List[KnowledgeRecord] = []
    for recs in _knowledge_store.values():
        for r in recs:
            if query_lower in r.content.lower() or query_lower in r.title.lower():
                results.append(r)
                if len(results) >= max_results:
                    return results
    return results


def get_knowledge_platform_status() -> Dict[str, Any]:
    """Return knowledge platform status for Mission Control / doctor."""
    reg = KnowledgeSourceRegistry()
    sources = reg.list_sources()
    by_status: Dict[str, int] = {}
    for s in sources:
        by_status[s.status] = by_status.get(s.status, 0) + 1
    total_records = sum(len(v) for v in _knowledge_store.values())
    return {
        "epic": "epic_c",
        "wave": 1,
        "status": "ready",
        "source_count": len(sources),
        "by_status": by_status,
        "ingested_sources": len(_knowledge_store),
        "total_records": total_records,
        "ingestion_implemented": True,
        "local_ingestion_implemented": True,
        "connector_ingestion_implemented": False,
        "hybrid_search_implemented": False,
        "approval_gate_enforced": True,
        "pii_sources_require_approval": True,
        "note": "Local text ingestion + keyword search implemented. Connector/hybrid search is next slice.",
    }


__all__ = [
    "KnowledgeSource",
    "KnowledgeRecord",
    "IngestionResult",
    "KnowledgeSourceRegistry",
    "SOURCE_TYPE_FILE",
    "SOURCE_TYPE_URL",
    "SOURCE_TYPE_DATABASE",
    "SOURCE_TYPE_CONNECTOR",
    "SOURCE_TYPE_MEMORY",
    "ACCESS_PUBLIC",
    "ACCESS_REQUIRES_APPROVAL",
    "ACCESS_PRIVATE",
    "ingest_local_source",
    "ingest_connector_source",
    "get_ingested_records",
    "get_all_ingested_records",
    "search_knowledge",
    "get_knowledge_platform_status",
]
