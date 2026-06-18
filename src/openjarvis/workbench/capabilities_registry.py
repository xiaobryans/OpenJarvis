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
    from openjarvis.workbench.auto_browser_provider import health_check, get_auto_browser_status

    hc = health_check()
    auto = get_auto_browser_status()

    client_ok = hc.get("client_sdk_installed", False)
    playwright_ok = hc.get("playwright_available", False)
    mcp_reachable = hc.get("mcp_reachable", False)

    if mcp_reachable:
        status = STATUS_NEEDS_APPROVAL
        summary = "Auto Browser fully configured — approval-gated sessions available."
    elif client_ok and playwright_ok:
        status = STATUS_REQUIRES_SETUP
        summary = (
            "Auto Browser client SDK + Playwright installed. "
            "MCP server requires Docker to start — see server_setup_steps."
        )
    else:
        status = STATUS_REQUIRES_SETUP
        summary = auto.get("summary", "Auto Browser partial setup.")

    return CapabilityRecord(
        capability_id="browser_automation",
        display_name="Browser Automation / Auto Browser",
        status=status,
        summary=summary,
        evidence={
            "client_sdk_installed": client_ok,
            "playwright_installed": playwright_ok,
            "mcp_reachable": mcp_reachable,
            "integration_status": auto.get("integration_status"),
            "local_clone": auto.get("local_clone"),
        },
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
    # Autopilot guard policy is hardcoded — does not require FastAPI at runtime.
    # The workbench_autopilot_guard() function is importable once fastapi is installed.
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
            evidence={"autopilot_runtime_enabled": False, "approval_bypass_allowed": False},
        )
    except ImportError:
        # FastAPI not installed — report truthfully without claiming insufficient_data.
        return CapabilityRecord(
            capability_id="automation",
            display_name="Automation",
            status=STATUS_REQUIRES_SETUP,
            summary="Automation routes require 'uv sync --extra server' to activate FastAPI.",
            evidence={"fastapi_installed": False, "fix": "uv sync --extra server"},
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="automation",
            display_name="Automation",
            status=STATUS_INSUFFICIENT_DATA,
            summary=f"Insufficient data to verify automation policy: {exc}",
            evidence={"error": str(exc)},
        )


def _wave1_skill_platform_status() -> CapabilityRecord:
    """Wave 1 Epic A — Skill Platform capability."""
    try:
        from openjarvis.wave.skill_platform import get_skill_platform_status
        info = get_skill_platform_status()
        return CapabilityRecord(
            capability_id="wave1_skill_platform",
            display_name="Wave 1 — Skill Platform",
            status=STATUS_REQUIRES_SETUP,
            summary=f"Wave 1 Epic A: Skill Platform scaffolded. {info['skill_count']} skills registered.",
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_skill_platform",
            display_name="Wave 1 — Skill Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic A scaffold unavailable: {exc}",
        )


def _wave1_automation_platform_status() -> CapabilityRecord:
    """Wave 1 Epic B — Automation Platform capability."""
    try:
        from openjarvis.wave.automation_platform import get_automation_platform_status
        info = get_automation_platform_status()
        return CapabilityRecord(
            capability_id="wave1_automation_platform",
            display_name="Wave 1 — Automation Platform",
            status=STATUS_REQUIRES_SETUP,
            summary="Wave 1 Epic B: Automation Platform scaffolded. Runtime execution not yet implemented.",
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_automation_platform",
            display_name="Wave 1 — Automation Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic B scaffold unavailable: {exc}",
        )


def _wave1_knowledge_platform_status() -> CapabilityRecord:
    """Wave 1 Epic C — Knowledge Platform capability."""
    try:
        from openjarvis.wave.knowledge_platform import get_knowledge_platform_status
        info = get_knowledge_platform_status()
        return CapabilityRecord(
            capability_id="wave1_knowledge_platform",
            display_name="Wave 1 — Knowledge Platform",
            status=STATUS_REQUIRES_SETUP,
            summary=(
                f"Wave 1 Epic C: Knowledge Platform scaffolded. "
                f"{info['source_count']} sources registered. Ingestion not yet wired."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_knowledge_platform",
            display_name="Wave 1 — Knowledge Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic C scaffold unavailable: {exc}",
        )


def _wave1_research_platform_status() -> CapabilityRecord:
    """Wave 1 Epic D — Research Platform capability."""
    try:
        from openjarvis.wave.research_platform import get_research_platform_status
        info = get_research_platform_status()
        return CapabilityRecord(
            capability_id="wave1_research_platform",
            display_name="Wave 1 — Research Platform",
            status=STATUS_REQUIRES_SETUP,
            summary=(
                f"Wave 1 Epic D: Research Platform scaffolded. "
                f"{info['provider_count']} providers registered. Execution not yet implemented."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_research_platform",
            display_name="Wave 1 — Research Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic D scaffold unavailable: {exc}",
        )


def get_all_capabilities() -> List[CapabilityRecord]:
    """Return all capability records with truthful status (US15 + Wave 1)."""
    return [
        _assistant_status(),
        _workbench_status(),
        _reviewer_status(),
        _voice_status(),
        _browser_status(),
        _research_status(),
        _automation_status(),
        # Wave 1 Foundation (Epic A–D)
        _wave1_skill_platform_status(),
        _wave1_automation_platform_status(),
        _wave1_knowledge_platform_status(),
        _wave1_research_platform_status(),
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
        "wave1_scaffolded": True,
        "wave2_3_4_not_implemented": True,
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
    "_wave1_skill_platform_status",
    "_wave1_automation_platform_status",
    "_wave1_knowledge_platform_status",
    "_wave1_research_platform_status",
]
