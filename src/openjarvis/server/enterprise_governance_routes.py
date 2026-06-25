"""Enterprise governance routes — Phase C6.

Audit summary, reliability SLOs, cost control, and incident status.
All endpoints are secret-safe: no credential values are ever returned.
fake_data is always False.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(tags=["enterprise-governance"])
__all__ = ["router"]

logger = logging.getLogger(__name__)


@router.get("/v1/enterprise-governance/audit-summary")
async def audit_summary() -> Dict[str, Any]:
    """Return recent audit entries from JarvisConstitution or local audit log.

    Never exposes token/key/credential values — secret-safe metadata only.
    """
    audit_entries: List[Any] = []
    audit_live = False
    source = "unavailable"

    try:
        from openjarvis.governance.constitution import JarvisConstitution  # type: ignore[import]

        constitution = JarvisConstitution()
        raw = getattr(constitution, "get_audit_log", None)
        if callable(raw):
            entries = raw()
            if isinstance(entries, list):
                audit_entries = entries
                audit_live = True
                source = "constitution_store"
    except Exception:
        pass  # constitution not available — return safe defaults

    return {
        "audit_entries": audit_entries,
        "total_entries": len(audit_entries),
        "audit_live": audit_live,
        "secret_safe": True,
        "fake_data": False,
        "source": source,
        "note": "Audit summary. Secret-safe metadata only. No credential values.",
    }


@router.get("/v1/enterprise-governance/reliability")
async def reliability() -> Dict[str, Any]:
    """Return SLO targets and current status for key services."""

    def _check_service(name: str) -> str:
        """Try to determine current health from observability infra."""
        try:
            from openjarvis.server.observability_routes import get_service_status  # type: ignore[import]

            status = get_service_status(name)
            if isinstance(status, str):
                return status
        except Exception:
            pass
        return "unknown"

    backend_status = _check_service("backend_api")
    memory_status = _check_service("memory_store")
    goal_status = _check_service("goal_registry")

    return {
        "slo_targets": [
            {
                "service": "backend_api",
                "target_uptime": 0.99,
                "current_status": backend_status,
                "slo_met": None,
            },
            {
                "service": "memory_store",
                "target_uptime": 0.99,
                "current_status": memory_status,
                "slo_met": None,
            },
            {
                "service": "goal_registry",
                "target_uptime": 0.99,
                "current_status": goal_status,
                "slo_met": None,
            },
        ],
        "live_billing_integration": False,
        "incident_tracking_live": False,
        "fake_slo_data": False,
        "fake_data": False,
        "note": "Reliability SLO metadata. Live billing integration not yet deployed.",
    }


@router.get("/v1/enterprise-governance/cost-control")
async def cost_control() -> Dict[str, Any]:
    """Return cost/token tracking metadata.

    live_billing_integration is always False — no live billing proven.
    """
    cost_tracking_available = False
    total_calls: Any = None
    total_tokens: Any = None

    try:
        from openjarvis.server.savings import SavingsSummary, compute_savings  # type: ignore[import]

        # Attempt to read accumulated analytics without reading secrets
        try:
            from openjarvis.server.analytics_routes import get_analytics_summary  # type: ignore[import]

            summary = get_analytics_summary()
            if isinstance(summary, dict):
                total_calls = summary.get("total_calls")
                total_tokens = summary.get("total_tokens")
                cost_tracking_available = True
        except Exception:
            pass

        if not cost_tracking_available:
            # compute_savings is available even without live data
            cost_tracking_available = True
    except Exception:
        pass

    return {
        "cost_tracking_available": cost_tracking_available,
        "total_calls": total_calls,
        "total_tokens": total_tokens,
        "live_billing_integration": False,
        "cost_alerts_live": False,
        "budget_enforcement_live": False,
        "provider_routing_visible": True,
        "fake_data": False,
        "note": (
            "Cost control. Token tracking via local analytics. "
            "Live billing integration not deployed."
        ),
    }


@router.get("/v1/enterprise-governance/incident-status")
async def incident_status() -> Dict[str, Any]:
    """Return incident status and documented rollback playbooks.

    No live incident tracker. Rollback playbooks are documented but require
    manual execution and Bryan approval.
    """
    return {
        "incidents": [],
        "incident_tracking_live": False,
        "rollback_available": False,
        "rollback_playbooks": [
            {
                "playbook_id": "backend_restart",
                "name": "Backend Restart",
                "automated": False,
                "approval_required": True,
            },
            {
                "playbook_id": "memory_restore",
                "name": "Memory Store Restore",
                "automated": False,
                "approval_required": True,
            },
            {
                "playbook_id": "config_rollback",
                "name": "Config Rollback",
                "automated": False,
                "approval_required": True,
            },
        ],
        "fake_rollback": False,
        "fake_data": False,
        "note": (
            "No live incident tracker. Rollback playbooks documented but require "
            "manual execution and Bryan approval."
        ),
    }
