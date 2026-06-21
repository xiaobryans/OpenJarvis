"""Mobile Capability Parity Matrix — Plan 7 Phase B.

Declares which capabilities are available on mobile and what their status is.
All Plan 7 capabilities must be reachable from mobile (progressive disclosure
allowed, but capability must exist — not a "lite" reduced version).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


CAPABILITY_AVAILABLE = "available"
CAPABILITY_PARTIAL = "partial"
CAPABILITY_BLOCKED = "blocked"
CAPABILITY_MISSING = "missing"


@dataclass
class CapabilityEntry:
    name: str
    status: str
    route: Optional[str] = None
    notes: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status,
            "route": self.route,
            "notes": self.notes,
        }


@dataclass
class MobileCapabilityMatrix:
    """Capability parity matrix for mobile vs desktop."""

    capabilities: List[CapabilityEntry] = field(default_factory=list)

    @classmethod
    def get(cls) -> "MobileCapabilityMatrix":
        """Return the current mobile capability parity matrix."""
        entries = [
            CapabilityEntry("chat", CAPABILITY_AVAILABLE, "/v1/chat/completions", "Identical API to desktop"),
            CapabilityEntry("task_submission", CAPABILITY_AVAILABLE, "/v1/frontdoor/submit", "All intents supported"),
            CapabilityEntry("memory_read", CAPABILITY_AVAILABLE, "/v1/memory/retrieve", "Full memory read"),
            CapabilityEntry("memory_write", CAPABILITY_AVAILABLE, "/v1/memory/store", "Full memory write"),
            CapabilityEntry("approval_read", CAPABILITY_AVAILABLE, "/v1/approvals/pending", "All approvals visible"),
            CapabilityEntry("approval_act", CAPABILITY_AVAILABLE, "/v1/approvals/{id}/approve", "Approve/deny from mobile"),
            CapabilityEntry("project_read", CAPABILITY_AVAILABLE, "/v1/projects", "All projects visible"),
            CapabilityEntry("continuity_snapshot", CAPABILITY_AVAILABLE, "/v1/continuity/snapshot", "Save state from any device"),
            CapabilityEntry("continuity_resume", CAPABILITY_AVAILABLE, "/v1/continuity/resume", "Resume on any device"),
            CapabilityEntry("connector_status", CAPABILITY_AVAILABLE, "/v1/connectors/status", "All connectors visible"),
            CapabilityEntry("research", CAPABILITY_AVAILABLE, "/api/research", "Full research workflow"),
            CapabilityEntry("coding_task", CAPABILITY_AVAILABLE, "/v1/frontdoor/submit", "Via universal front door"),
            CapabilityEntry("personal_task", CAPABILITY_AVAILABLE, "/v1/life-os/tasks", "Full personal task management"),
            CapabilityEntry("long_horizon_goal", CAPABILITY_AVAILABLE, "/v1/goals", "Goal creation and tracking"),
            CapabilityEntry("self_upgrade_request", CAPABILITY_AVAILABLE, "/v1/self-upgrade/request", "Staged upgrade planning"),
            CapabilityEntry("business_project", CAPABILITY_AVAILABLE, "/v1/workstreams", "Business workstream management"),
            CapabilityEntry("multi_agent", CAPABILITY_AVAILABLE, "/v1/orchestrator/routing/dry-run", "Multi-agent routing"),
            CapabilityEntry("finance_admin", CAPABILITY_AVAILABLE, "/v1/frontdoor/submit", "Finance via front door with approval gate"),
            CapabilityEntry("macbook_off_aws", CAPABILITY_AVAILABLE, None, "ECS Fargate always-on backend"),
        ]
        return cls(capabilities=entries)

    def get_status(self, capability_name: str) -> Optional[str]:
        """Return status for a named capability."""
        for cap in self.capabilities:
            if cap.name == capability_name:
                return cap.status
        return None

    def all_available(self) -> bool:
        """Return True if all capabilities are available or partial (not blocked/missing)."""
        return all(
            c.status in (CAPABILITY_AVAILABLE, CAPABILITY_PARTIAL)
            for c in self.capabilities
        )

    def to_dict(self) -> Dict:
        return {
            "capabilities": [c.to_dict() for c in self.capabilities],
            "count": len(self.capabilities),
            "all_available": self.all_available(),
        }


__all__ = [
    "CapabilityEntry",
    "MobileCapabilityMatrix",
    "CAPABILITY_AVAILABLE",
    "CAPABILITY_PARTIAL",
    "CAPABILITY_BLOCKED",
    "CAPABILITY_MISSING",
]
