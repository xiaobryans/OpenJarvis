"""US15 Jarvis capability registry — truthful status for Mission Control / doctor.

Each capability reports one of:
  ready | disabled | requires_setup | needs_approval | not_implemented | insufficient_data

US13 voice is explicitly PARKED — never reported as ready for hands-free use.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

CapabilityStatus = str

STATUS_READY = "ready"
STATUS_DISABLED = "disabled"
STATUS_REQUIRES_SETUP = "requires_setup"
STATUS_NEEDS_APPROVAL = "needs_approval"
STATUS_NOT_IMPLEMENTED = "not_implemented"
STATUS_INSUFFICIENT_DATA = "insufficient_data"

US13_VOICE_PARKED_NOTE = (
    "US13 voice HOLD/UNSAFE — hands-free wake excluded from release readiness. "
    "Backlog: docs/US15_US16_FOUNDATION.md § US13 parked voice backlog."
)


@dataclass
class CapabilityRecord:
    capability_id: str
    display_name: str
    status: CapabilityStatus
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "display_name": self.display_name,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
        }


def _workbench_modules_present() -> bool:
    root = Path(__file__).parent
    required = ("coding_manager.py", "model_router.py", "cost_ledger.py", "event_log.py")
    return all((root / name).exists() for name in required)


def _assistant_status() -> CapabilityRecord:
    try:
        from openjarvis.engine import discover_engines
        from openjarvis.core.config import load_config

        config = load_config()
        engines = discover_engines(config)
        if engines:
            return CapabilityRecord(
                capability_id="assistant",
                display_name="Assistant",
                status=STATUS_READY,
                summary="Chat/inference path available via configured engines.",
                evidence={"engine_count": len(engines)},
            )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="assistant",
            display_name="Assistant",
            status=STATUS_INSUFFICIENT_DATA,
            summary=f"Insufficient data to verify assistant readiness: {exc}",
            evidence={"error": str(exc)},
        )
    return CapabilityRecord(
        capability_id="assistant",
        display_name="Assistant",
        status=STATUS_REQUIRES_SETUP,
        summary="No inference engine configured.",
        evidence={},
    )


def _workbench_status() -> CapabilityRecord:
    if not _workbench_modules_present():
        return CapabilityRecord(
            capability_id="workbench_coding",
            display_name="Workbench / Coding",
            status=STATUS_NOT_IMPLEMENTED,
            summary="Workbench modules missing.",
            evidence={},
        )
    return CapabilityRecord(
        capability_id="workbench_coding",
        display_name="Workbench / Coding",
        status=STATUS_READY,
        summary="US14A/US15 workbench path: plan → execute → validate → diff → git (approval-gated).",
        evidence={
            "routes": [
                "/v1/workbench/plan",
                "/v1/workbench/execute",
                "/v1/workbench/validate",
                "/v1/workbench/diff",
                "/v1/workbench/repo-index",
            ],
            "dry_run_default": True,
        },
    )


def _reviewer_status() -> CapabilityRecord:
    if not _workbench_modules_present():
        return CapabilityRecord(
            capability_id="reviewer_validator",
            display_name="Reviewer / Validator",
            status=STATUS_NOT_IMPLEMENTED,
            summary="Workbench validation path not available.",
            evidence={},
        )
    return CapabilityRecord(
        capability_id="reviewer_validator",
        display_name="Reviewer / Validator",
        status=STATUS_READY,
        summary="Validation profiles + diff review via Workbench; local-first pytest profiles.",
        evidence={"endpoint": "/v1/workbench/validate", "profiles": "/v1/workbench/validation-profiles"},
    )


def _voice_status() -> CapabilityRecord:
    try:
        from openjarvis.autonomy.voice_pipeline import get_voice_status

        vs = get_voice_status()
        worker_running = vs.get("true_wakeword_worker_running", False)
        voice_readiness = vs.get("voice_readiness", "HOLD")
        return CapabilityRecord(
            capability_id="voice",
            display_name="Voice",
            status=STATUS_DISABLED,
            summary=US13_VOICE_PARKED_NOTE,
            evidence={
                "us13_verdict": "HOLD/UNSAFE — not accepted for release",
                "voice_readiness": voice_readiness,
                "worker_running": worker_running,
                "hands_free_excluded": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="voice",
            display_name="Voice",
            status=STATUS_DISABLED,
            summary=US13_VOICE_PARKED_NOTE,
            evidence={"check_error": str(exc), "hands_free_excluded": True},
        )


def _browser_status() -> CapabilityRecord:
    from openjarvis.workbench.auto_browser_provider import get_auto_browser_status

    auto = get_auto_browser_status()
    playwright_ok = False
    try:
        from openjarvis.tools.browser import BrowserNavigateTool  # noqa: F401

        playwright_ok = True
    except Exception:
        playwright_ok = False

    if auto.get("integration_status") == "blocked":
        status = STATUS_REQUIRES_SETUP
        summary = auto.get("summary", "Auto Browser evaluation blocked.")
    elif playwright_ok:
        status = STATUS_NEEDS_APPROVAL
        summary = "Playwright browser tools available; approval-gated. Auto Browser connector not merged."
    else:
        status = STATUS_REQUIRES_SETUP
        summary = "Install browser extra (uv sync --extra browser) for Playwright tools."

    return CapabilityRecord(
        capability_id="browser_automation",
        display_name="Browser Automation / Auto Browser",
        status=status,
        summary=summary,
        evidence={"auto_browser": auto, "playwright_tools": playwright_ok},
    )


def _research_status() -> CapabilityRecord:
    try:
        from openjarvis.tools.jarvis_registry import ToolRegistry

        tools = ToolRegistry.list_all()
        research_ids = [t.tool_id for t in tools if "research" in t.tool_id or "search" in t.tool_id]
        if research_ids:
            return CapabilityRecord(
                capability_id="research",
                display_name="Research",
                status=STATUS_READY,
                summary="Research/search tools registered.",
                evidence={"tool_ids": research_ids[:10]},
            )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="research",
            display_name="Research",
            status=STATUS_INSUFFICIENT_DATA,
            summary=f"Insufficient data to verify research tools: {exc}",
            evidence={"error": str(exc)},
        )
    return CapabilityRecord(
        capability_id="research",
        display_name="Research",
        status=STATUS_REQUIRES_SETUP,
        summary="No research tools registered.",
        evidence={},
    )


def _automation_status() -> CapabilityRecord:
    try:
        from openjarvis.server.workbench_routes import workbench_autopilot_guard

        guard = workbench_autopilot_guard()
        runtime_enabled = guard.get("autopilot_runtime_enabled", False)
        if runtime_enabled:
            return CapabilityRecord(
                capability_id="automation",
                display_name="Automation",
                status=STATUS_NEEDS_APPROVAL,
                summary="Autopilot runtime enabled — Manager approval required for protected actions.",
                evidence=guard,
            )
        return CapabilityRecord(
            capability_id="automation",
            display_name="Automation",
            status=STATUS_DISABLED,
            summary="Autopilot runtime disabled by default; guarded preview only.",
            evidence=guard,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="automation",
            display_name="Automation",
            status=STATUS_INSUFFICIENT_DATA,
            summary=f"Insufficient data to verify automation policy: {exc}",
            evidence={"error": str(exc)},
        )


def get_all_capabilities() -> List[CapabilityRecord]:
    """Return all US15 capability records with truthful status."""
    return [
        _assistant_status(),
        _workbench_status(),
        _reviewer_status(),
        _voice_status(),
        _browser_status(),
        _research_status(),
        _automation_status(),
    ]


def get_capabilities_summary() -> Dict[str, Any]:
    caps = get_all_capabilities()
    by_status: Dict[str, int] = {}
    for c in caps:
        by_status[c.status] = by_status.get(c.status, 0) + 1
    return {
        "capabilities": [c.to_dict() for c in caps],
        "count": len(caps),
        "by_status": by_status,
        "us13_voice_parked": True,
    }


__all__ = [
    "CapabilityRecord",
    "CapabilityStatus",
    "STATUS_READY",
    "STATUS_DISABLED",
    "STATUS_REQUIRES_SETUP",
    "STATUS_NEEDS_APPROVAL",
    "STATUS_NOT_IMPLEMENTED",
    "STATUS_INSUFFICIENT_DATA",
    "US13_VOICE_PARKED_NOTE",
    "get_all_capabilities",
    "get_capabilities_summary",
]
