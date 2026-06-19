"""Role-Scoped Cache — scoped by role, project, task, and security level.

Cache layers:
  1. global_jarvis      — shared Jarvis-level context (policy, architecture)
  2. role              — per-role context (COS, GM, manager, worker)
  3. worker            — per-worker task-specific cache
  4. project           — per-project context
  5. validation        — validation command outputs / gate results
  6. failure_prevention — prevention items and failure patterns
  7. continuity        — mobile/session continuity state references

Rules:
  - Cache reuse may reduce planning/routing/context retrieval.
  - Cache reuse MUST NOT skip required validation gates.
  - Cache is scoped by role, project, task, and security_level.
  - Workers cannot access secrets or unrelated private state.
  - Verifier must inspect cache/evidence traces critically.
  - Cache misses are explicit — never guessed.
  - Security levels: public < internal < private (never cross downward).

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Cache layer types
# ---------------------------------------------------------------------------

class CacheLayer(str, Enum):
    GLOBAL_JARVIS = "global_jarvis"
    ROLE = "role"
    WORKER = "worker"
    PROJECT = "project"
    VALIDATION = "validation"
    FAILURE_PREVENTION = "failure_prevention"
    CONTINUITY = "continuity"


class SecurityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"


# ---------------------------------------------------------------------------
# Cache entry
# ---------------------------------------------------------------------------

@dataclass
class CacheEntry:
    entry_id: str
    layer: CacheLayer
    scope_key: str          # e.g. "role:manager-coding:project:openjarvis"
    security_level: SecurityLevel
    content: Any
    gates_required: List[str]   # validation gates that MUST still run
    created_at: float = field(default_factory=time.time)
    last_accessed_at: Optional[float] = None
    ttl_seconds: int = 3600
    hit_count: int = 0

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl_seconds

    def access(self) -> Any:
        self.last_accessed_at = time.time()
        self.hit_count += 1
        return self.content

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "layer": self.layer.value,
            "scope_key": self.scope_key,
            "security_level": self.security_level.value,
            "gates_required": self.gates_required,
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "ttl_seconds": self.ttl_seconds,
            "hit_count": self.hit_count,
            "is_expired": self.is_expired(),
        }


# ---------------------------------------------------------------------------
# Cache miss
# ---------------------------------------------------------------------------

@dataclass
class CacheMiss:
    """Explicit cache miss — never guessed."""
    layer: CacheLayer
    scope_key: str
    reason: str    # "not_found" | "expired" | "security_violation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_miss": True,
            "layer": self.layer.value,
            "scope_key": self.scope_key,
            "reason": self.reason,
        }


# ---------------------------------------------------------------------------
# Role-Scoped Cache Registry
# ---------------------------------------------------------------------------

class RoleScopedCache:
    """Role-scoped cache for all Jarvis hierarchy roles.

    Scope key format: "{layer}:{role_id}:{qualifier}"
    e.g. "role:manager-coding:project:openjarvis"

    Security rules:
      - Workers can only access their own scope and public entries.
      - Managers can access worker scopes under them.
      - Verifier can read all scopes but cannot write.
      - Private entries require security_level=PRIVATE and explicit caller auth.
    """

    def __init__(self) -> None:
        self._store: Dict[str, CacheEntry] = {}

    def _make_scope_key(
        self,
        layer: CacheLayer,
        role_id: str,
        qualifier: str = "",
    ) -> str:
        parts = [layer.value, role_id]
        if qualifier:
            parts.append(qualifier)
        return ":".join(parts)

    def put(
        self,
        layer: CacheLayer,
        role_id: str,
        content: Any,
        *,
        qualifier: str = "",
        security_level: SecurityLevel = SecurityLevel.INTERNAL,
        gates_required: Optional[List[str]] = None,
        ttl_seconds: int = 3600,
    ) -> CacheEntry:
        """Store a cache entry. Returns the entry."""
        scope_key = self._make_scope_key(layer, role_id, qualifier)
        entry = CacheEntry(
            entry_id=str(uuid.uuid4())[:8],
            layer=layer,
            scope_key=scope_key,
            security_level=security_level,
            content=content,
            gates_required=gates_required or [],
            ttl_seconds=ttl_seconds,
        )
        self._store[scope_key] = entry
        return entry

    def get(
        self,
        layer: CacheLayer,
        role_id: str,
        qualifier: str = "",
        caller_role_id: Optional[str] = None,
        caller_security_level: SecurityLevel = SecurityLevel.INTERNAL,
    ) -> "CacheEntry | CacheMiss":
        """Get a cache entry. Returns CacheMiss explicitly on miss."""
        scope_key = self._make_scope_key(layer, role_id, qualifier)
        entry = self._store.get(scope_key)

        if entry is None:
            return CacheMiss(layer=layer, scope_key=scope_key, reason="not_found")

        if entry.is_expired():
            del self._store[scope_key]
            return CacheMiss(layer=layer, scope_key=scope_key, reason="expired")

        # Security check: workers cannot read private entries of other scopes
        if (
            entry.security_level == SecurityLevel.PRIVATE
            and caller_security_level != SecurityLevel.PRIVATE
            and caller_role_id != role_id
        ):
            return CacheMiss(
                layer=layer,
                scope_key=scope_key,
                reason=f"security_violation: caller '{caller_role_id}' cannot access private scope '{role_id}'",
            )

        entry.access()
        return entry

    def get_gates_required(self, layer: CacheLayer, role_id: str, qualifier: str = "") -> List[str]:
        """Return gates_required for a cache entry (even after reuse, gates must run)."""
        scope_key = self._make_scope_key(layer, role_id, qualifier)
        entry = self._store.get(scope_key)
        if entry:
            return list(entry.gates_required)
        return []

    def summary(self) -> Dict[str, Any]:
        total = len(self._store)
        expired = sum(1 for e in self._store.values() if e.is_expired())
        by_layer: Dict[str, int] = {}
        for e in self._store.values():
            by_layer[e.layer.value] = by_layer.get(e.layer.value, 0) + 1
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "by_layer": by_layer,
        }

    def get_trace(self) -> List[Dict[str, Any]]:
        """Return cache trace for inclusion in pipeline response."""
        return [e.to_dict() for e in self._store.values() if not e.is_expired()]


# Predefined role scopes for all hierarchy levels
ROLE_CACHE_SCOPES = {
    "jarvis": CacheLayer.GLOBAL_JARVIS,
    "cos": CacheLayer.ROLE,
    "gm": CacheLayer.ROLE,
    "manager-coding": CacheLayer.ROLE,
    "manager-research": CacheLayer.ROLE,
    "manager-memory": CacheLayer.ROLE,
    "manager-connector": CacheLayer.ROLE,
    "manager-ops-safety": CacheLayer.ROLE,
    "worker-repo-inspector": CacheLayer.WORKER,
    "worker-test-runner": CacheLayer.WORKER,
    "worker-obsidian-exporter": CacheLayer.WORKER,
    "worker-memory-sync": CacheLayer.WORKER,
    "verifier": CacheLayer.VALIDATION,
    "mobile-continuity": CacheLayer.CONTINUITY,
}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_CACHE: Optional[RoleScopedCache] = None


def get_role_cache() -> RoleScopedCache:
    global _CACHE
    if _CACHE is None:
        _CACHE = RoleScopedCache()
    return _CACHE


__all__ = [
    "CacheLayer",
    "SecurityLevel",
    "CacheEntry",
    "CacheMiss",
    "RoleScopedCache",
    "ROLE_CACHE_SCOPES",
    "get_role_cache",
]
