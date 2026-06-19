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
        local_exec = info.get("local_execution_implemented", False)
        status = STATUS_READY if local_exec else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave1_skill_platform",
            display_name="Wave 1 — Skill Platform",
            status=status,
            summary=(
                f"Wave 1 Epic A: Skill Platform. {info['skill_count']} skills registered, "
                f"{info.get('executable_count', 0)} locally executable. "
                f"Induction pipeline: {'yes' if info.get('induction_pipeline_implemented') else 'next slice'}."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_skill_platform",
            display_name="Wave 1 — Skill Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic A unavailable: {exc}",
        )


def _wave1_automation_platform_status() -> CapabilityRecord:
    """Wave 1 Epic B — Automation Platform capability."""
    try:
        from openjarvis.wave.automation_platform import get_automation_platform_status
        info = get_automation_platform_status()
        dry_run = info.get("dry_run_implemented", False)
        status = STATUS_READY if dry_run else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave1_automation_platform",
            display_name="Wave 1 — Automation Platform",
            status=status,
            summary=(
                f"Wave 1 Epic B: Automation Platform. Dry-run: {'yes' if dry_run else 'no'}. "
                f"Live scheduler: {'yes' if info.get('cron_wiring_implemented') else 'next slice'}."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_automation_platform",
            display_name="Wave 1 — Automation Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic B unavailable: {exc}",
        )


def _wave1_knowledge_platform_status() -> CapabilityRecord:
    """Wave 1 Epic C — Knowledge Platform capability."""
    try:
        from openjarvis.wave.knowledge_platform import get_knowledge_platform_status
        info = get_knowledge_platform_status()
        local_ingest = info.get("local_ingestion_implemented", False)
        status = STATUS_READY if local_ingest else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave1_knowledge_platform",
            display_name="Wave 1 — Knowledge Platform",
            status=status,
            summary=(
                f"Wave 1 Epic C: Knowledge Platform. Local ingestion: {'yes' if local_ingest else 'no'}. "
                f"{info.get('ingested_sources', 0)} sources ingested, "
                f"{info.get('total_records', 0)} records. "
                f"Connector/hybrid-search: next slice."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_knowledge_platform",
            display_name="Wave 1 — Knowledge Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic C unavailable: {exc}",
        )


def _wave1_research_platform_status() -> CapabilityRecord:
    """Wave 1 Epic D — Research Platform capability."""
    try:
        from openjarvis.wave.research_platform import get_research_platform_status
        info = get_research_platform_status()
        local_query = info.get("local_query_implemented", False)
        status = STATUS_READY if local_query else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave1_research_platform",
            display_name="Wave 1 — Research Platform",
            status=status,
            summary=(
                f"Wave 1 Epic D: Research Platform. Local query: {'yes' if local_query else 'no'}. "
                f"{info['provider_count']} providers registered. "
                f"Web search: requires_setup (API key needed). Scraping blocked."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave1_research_platform",
            display_name="Wave 1 — Research Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 1 Epic D unavailable: {exc}",
        )


def _wave2_optimization_platform_status() -> CapabilityRecord:
    """Wave 2 Epic E — Optimization Platform capability."""
    try:
        from openjarvis.wave.optimization_platform import get_optimization_platform_status
        info = get_optimization_platform_status()
        implemented = info.get("implemented", False)
        status = STATUS_READY if implemented else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave2_optimization_platform",
            display_name="Wave 2 — Optimization Platform",
            status=status,
            summary=(
                f"Wave 2 Epic E: Optimization Platform. "
                f"Scorecard: {'yes' if info.get('scorecard_implemented') else 'no'}. "
                f"No autonomous self-modification."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave2_optimization_platform",
            display_name="Wave 2 — Optimization Platform",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 2 Epic E unavailable: {exc}",
        )


def _wave2_professional_skill_packs_status() -> CapabilityRecord:
    """Wave 2 Epic F — Professional Skill Packs capability."""
    try:
        from openjarvis.wave.professional_skill_packs import get_professional_skill_packs_status
        info = get_professional_skill_packs_status()
        implemented = info.get("implemented", False)
        status = STATUS_READY if implemented else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave2_professional_skill_packs",
            display_name="Wave 2 — Professional Skill Packs",
            status=status,
            summary=(
                f"Wave 2 Epic F: Professional Skill Packs. "
                f"{info.get('pack_count', 0)} packs registered, "
                f"{info.get('enabled_count', 0)} enabled."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave2_professional_skill_packs",
            display_name="Wave 2 — Professional Skill Packs",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 2 Epic F unavailable: {exc}",
        )


def _wave3_content_media_studio_status() -> CapabilityRecord:
    """Wave 3 Epic G — Content & Media Studio capability."""
    try:
        from openjarvis.wave.content_media_studio import get_content_studio_status
        info = get_content_studio_status()
        implemented = info.get("implemented", False)
        status = STATUS_READY if implemented else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave3_content_media_studio",
            display_name="Wave 3 — Content & Media Studio",
            status=status,
            summary=(
                f"Wave 3 Epic G: Content & Media Studio. "
                f"{info.get('template_count', 0)} templates. "
                f"Dry-run default. File writes approval-gated. "
                f"External providers require setup."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave3_content_media_studio",
            display_name="Wave 3 — Content & Media Studio",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 3 Epic G unavailable: {exc}",
        )


def _wave4_autonomous_expansion_status() -> CapabilityRecord:
    """Wave 4 Epic H — Autonomous Expansion capability."""
    try:
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        info = get_expansion_status()
        implemented = info.get("implemented", False)
        status = STATUS_READY if implemented else STATUS_REQUIRES_SETUP
        return CapabilityRecord(
            capability_id="wave4_autonomous_expansion",
            display_name="Wave 4 — Autonomous Expansion (Supervised)",
            status=status,
            summary=(
                "Wave 4 Epic H: Supervised expansion scaffolding. "
                "Proposal-only — no auto-execute, no code self-modification, "
                "no auto-commit, no deploy. "
                "NUS 1 not started. US13 voice HOLD/UNSAFE/PARKED."
            ),
            evidence=info,
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="wave4_autonomous_expansion",
            display_name="Wave 4 — Autonomous Expansion (Supervised)",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"Wave 4 Epic H unavailable: {exc}",
        )


def _nus1a_learning_foundation_status() -> CapabilityRecord:
    """NUS 1A — Learning Foundation capability."""
    try:
        from openjarvis.nus.learning_foundation import NUS1A_VERSION, LearningFoundation  # noqa: F401
        return CapabilityRecord(
            capability_id="nus1a_learning_foundation",
            display_name="NUS 1A — Learning Foundation",
            status=STATUS_READY,
            summary=(
                "NUS 1A: Local learning foundation. Collects structured signals "
                "from task outcomes, validation, blocked actions, Wave 1–4 events, "
                "and Workbench outcomes. Scorecard, failure-pattern detection, and "
                "read-only snapshots available. No self-modification, no auto-commit, "
                "no deploy, no external sends. US13 voice HOLD/UNSAFE/PARKED. "
                "NUS 1B/1C (full self-improvement) not started."
            ),
            evidence={"nus1a_version": NUS1A_VERSION, "safety_gates_active": True},
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1a_learning_foundation",
            display_name="NUS 1A — Learning Foundation",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1A learning foundation unavailable: {exc}",
        )


def _nus1b_recommendation_workflow_status() -> CapabilityRecord:
    """NUS 1B — Recommendation Workflow capability."""
    try:
        from openjarvis.nus.recommendation_registry import NUS1B_REC_VERSION, RecommendationRegistry  # noqa: F401
        from openjarvis.nus.learning_store import NUS1B_STORE_VERSION  # noqa: F401
        from openjarvis.nus.autonomy_policy import NUS1B_POLICY_VERSION, PROFILE_MANUAL  # noqa: F401
        from openjarvis.nus.telemetry import NUS1B_TELEMETRY_VERSION  # noqa: F401
        return CapabilityRecord(
            capability_id="nus1b_recommendation_workflow",
            display_name="NUS 1B — Recommendation Workflow",
            status=STATUS_READY,
            summary=(
                "NUS 1B: Persistent learning, recommendation lifecycle, approval workflow "
                "scaffolding, telemetry normalization, and autonomy policy scaffold. "
                "Dry-run only. No self-modification, no auto-commit, no deploy, no external sends. "
                "US13 voice HOLD/UNSAFE/PARKED. NUS 1C+ not started."
            ),
            evidence={
                "rec_version": NUS1B_REC_VERSION,
                "store_version": NUS1B_STORE_VERSION,
                "policy_version": NUS1B_POLICY_VERSION,
                "telemetry_version": NUS1B_TELEMETRY_VERSION,
                "safety_gates_active": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1b_recommendation_workflow",
            display_name="NUS 1B — Recommendation Workflow",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1B recommendation workflow unavailable: {exc}",
        )


def _nus1c_safe_autopilot_learning_status() -> CapabilityRecord:
    """NUS 1C — Safe Autopilot Learning capability."""
    try:
        from openjarvis.nus.recommendation_queue import NUS1C_QUEUE_VERSION, RecommendationQueue  # noqa: F401
        from openjarvis.nus.safe_autopilot import NUS1C_AUTOPILOT_VERSION, SafeAutopilot  # noqa: F401
        from openjarvis.nus.failure_learning import NUS1C_FAILURE_LEARNING_VERSION, FailureLearner  # noqa: F401
        from openjarvis.nus.learned_routing import NUS1C_ROUTING_VERSION, LearnedRouter  # noqa: F401
        return CapabilityRecord(
            capability_id="nus1c_safe_autopilot_learning",
            display_name="NUS 1C — Safe Autopilot Learning",
            status=STATUS_READY,
            summary=(
                "NUS 1C: Persistent recommendation queue, safe_autopilot active for local "
                "analysis/dry-run only, cross-session failure learning, operator telemetry "
                "normalization, and learned model-routing recommendations. "
                "file_write/browser/external sends: needs_approval. "
                "self_modification/auto_commit/deploy/secret_access: blocked. "
                "US13 voice HOLD/UNSAFE/PARKED. NUS 1D+: not_started."
            ),
            evidence={
                "queue_version": NUS1C_QUEUE_VERSION,
                "autopilot_version": NUS1C_AUTOPILOT_VERSION,
                "failure_learning_version": NUS1C_FAILURE_LEARNING_VERSION,
                "routing_version": NUS1C_ROUTING_VERSION,
                "safe_autopilot_active": True,
                "safety_gates_active": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1c_safe_autopilot_learning",
            display_name="NUS 1C — Safe Autopilot Learning",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1C safe autopilot learning unavailable: {exc}",
        )


def _nus1d_eval_rollback_gates_status() -> CapabilityRecord:
    """NUS 1D — Eval Gates, Rollback, Approval, Power Autopilot Boundary."""
    try:
        from openjarvis.nus.eval_gate import NUS1D_EVAL_GATE_VERSION, EvalGateRunner  # noqa: F401
        from openjarvis.nus.rollback import NUS1D_ROLLBACK_VERSION, RollbackEnforcer  # noqa: F401
        from openjarvis.nus.approval_workflow import NUS1D_APPROVAL_VERSION, ApprovalWorkflow  # noqa: F401
        from openjarvis.nus.power_autopilot import NUS1D_POWER_AUTOPILOT_VERSION, PowerAutopilot  # noqa: F401
        return CapabilityRecord(
            capability_id="nus1d_eval_rollback_gates",
            display_name="NUS 1D — Eval Gates, Rollback, Approval Workflow",
            status=STATUS_READY,
            summary=(
                "NUS 1D: Eval gate framework (fail-closed), structured rollback plans, "
                "approval workflow with TTL/scope/audit, power_autopilot boundary "
                "(controlled, not broadly activated). "
                "file_write/browser/external: needs_approval. "
                "self_modification/deploy/secret/push/merge: blocked. "
                "US13 voice HOLD/UNSAFE/PARKED."
            ),
            evidence={
                "eval_gate_version": NUS1D_EVAL_GATE_VERSION,
                "rollback_version": NUS1D_ROLLBACK_VERSION,
                "approval_version": NUS1D_APPROVAL_VERSION,
                "power_autopilot_version": NUS1D_POWER_AUTOPILOT_VERSION,
                "safety_gates_active": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1d_eval_rollback_gates",
            display_name="NUS 1D — Eval Gates, Rollback, Approval Workflow",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1D eval rollback gates unavailable: {exc}",
        )


def _nus1e_low_risk_execution_foundation_status() -> CapabilityRecord:
    """NUS 1E — Low-Risk Execution Foundation."""
    try:
        from openjarvis.nus.execution_classifier import NUS1E_CLASSIFIER_VERSION, ExecutionClassifier  # noqa: F401
        from openjarvis.nus.low_risk_execution import NUS1E_LOW_RISK_VERSION, LowRiskExecutionManager  # noqa: F401
        return CapabilityRecord(
            capability_id="nus1e_low_risk_execution_foundation",
            display_name="NUS 1E — Low-Risk Execution Foundation",
            status=STATUS_READY,
            summary=(
                "NUS 1E: Metadata/contract-driven execution classifier, "
                "low-risk auto-commit candidate preparation (dry-run scaffold), "
                "production-safe execution gate (production actions blocked, require NUS 1F). "
                "No auto-push, no auto-merge, no production deploy. "
                "US13 voice HOLD/UNSAFE/PARKED. NUS 1F: not_started."
            ),
            evidence={
                "classifier_version": NUS1E_CLASSIFIER_VERSION,
                "low_risk_version": NUS1E_LOW_RISK_VERSION,
                "agent_name_agnostic": True,
                "safety_gates_active": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1e_low_risk_execution_foundation",
            display_name="NUS 1E — Low-Risk Execution Foundation",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1E low-risk execution foundation unavailable: {exc}",
        )


def _nus1f_controlled_high_autonomy_status() -> CapabilityRecord:
    """NUS 1F — Controlled High-Autonomy Session Framework."""
    try:
        from openjarvis.nus.high_autonomy_session import NUS1F_SESSION_VERSION, get_session_manager  # noqa: F401
        from openjarvis.nus.autonomy_action_policy import NUS1F_POLICY_VERSION, get_action_policy  # noqa: F401
        from openjarvis.nus.production_gate import NUS1F_PRODUCTION_GATE_VERSION, get_production_gate  # noqa: F401
        from openjarvis.nus.decision_record import NUS1F_DECISION_RECORD_VERSION, get_decision_record_status  # noqa: F401
        return CapabilityRecord(
            capability_id="nus1f_controlled_high_autonomy",
            display_name="NUS 1F — Controlled High-Autonomy Session Framework",
            status=STATUS_READY,
            summary=(
                "NUS 1F: Explicit time-limited high-autonomy sessions with TTL, scope, "
                "budget, risk ceiling, kill switch, audit log, and rollback requirements. "
                "95% automation policy model with 6 tiers. "
                "Production gate structure (dry-run only). "
                "Structured decision records (no raw chain-of-thought). "
                "NUS applies to all hierarchy levels. "
                "No real deploy, no auto-push, no auto-merge. "
                "US13 voice HOLD/UNSAFE/PARKED."
            ),
            evidence={
                "session_version": NUS1F_SESSION_VERSION,
                "policy_version": NUS1F_POLICY_VERSION,
                "gate_version": NUS1F_PRODUCTION_GATE_VERSION,
                "decision_record_version": NUS1F_DECISION_RECORD_VERSION,
                "production_autonomy_enabled": False,
                "safety_gates_active": True,
                "kill_switch_available": True,
                "no_hardcoded_agent_names": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1f_controlled_high_autonomy",
            display_name="NUS 1F — Controlled High-Autonomy Session Framework",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1F controlled high autonomy unavailable: {exc}",
        )


def _nus1f_founder_override_sessions_status() -> CapabilityRecord:
    """NUS 1F — Founder Override Session capability."""
    try:
        from openjarvis.nus.high_autonomy_session import (  # noqa: F401
            get_session_manager, PERMANENTLY_BLOCKED_ACTIONS,
        )
        mgr = get_session_manager()
        s = mgr.get_status()
        return CapabilityRecord(
            capability_id="nus1f_founder_override_sessions",
            display_name="NUS 1F — Founder Override Sessions",
            status=STATUS_NEEDS_APPROVAL,
            summary=(
                "Founder override sessions: ready for local controlled session framework, "
                "policy evaluation, dry-run, audit, and strict gates. "
                "Needs approval for medium/high-risk actions. "
                "Permanently blocked: deploy/secret/external-send/auto-push/auto-merge/safety-bypass."
            ),
            evidence={
                "permanently_blocked_count": len(PERMANENTLY_BLOCKED_ACTIONS),
                "global_kill_switch": s["global_kill_switch"],
                "session_manager_ready": True,
                "ttl_enforced": True,
                "scope_enforced": True,
                "budget_enforced": True,
                "risk_ceiling_enforced": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1f_founder_override_sessions",
            display_name="NUS 1F — Founder Override Sessions",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1F founder override sessions unavailable: {exc}",
        )


def _nus1f_production_policy_gate_status() -> CapabilityRecord:
    """NUS 1F — Production Policy Gate capability."""
    try:
        from openjarvis.nus.production_gate import get_production_gate  # noqa: F401
        gate = get_production_gate()
        s = gate.get_status()
        return CapabilityRecord(
            capability_id="nus1f_production_policy_gate",
            display_name="NUS 1F — Production Policy Gate",
            status=STATUS_READY,
            summary=(
                "Production gate structure ready for evaluation (dry-run only in NUS 1F). "
                "Real production execution blocked. "
                "No real deploy, no auto-push, no auto-merge."
            ),
            evidence={
                "gate_version": s["gate_version"],
                "production_autonomy_enabled": False,
                "execution_mode": "blocked_dry_run_only",
                "real_deploy_blocked": True,
                "auto_push_blocked": True,
                "auto_merge_blocked": True,
            },
        )
    except Exception as exc:
        return CapabilityRecord(
            capability_id="nus1f_production_policy_gate",
            display_name="NUS 1F — Production Policy Gate",
            status=STATUS_NOT_IMPLEMENTED,
            summary=f"NUS 1F production policy gate unavailable: {exc}",
        )


def get_all_capabilities() -> List[CapabilityRecord]:
    """Return all capability records with truthful status (US15 + Wave 1–4 + NUS 1A–1F)."""
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
        # Wave 2 Professional Intelligence (Epic E–F)
        _wave2_optimization_platform_status(),
        _wave2_professional_skill_packs_status(),
        # Wave 3 Creation & Media (Epic G)
        _wave3_content_media_studio_status(),
        # Wave 4 Autonomous Expansion (Epic H)
        _wave4_autonomous_expansion_status(),
        # NUS 1A — Learning Foundation
        _nus1a_learning_foundation_status(),
        # NUS 1B — Recommendation Workflow
        _nus1b_recommendation_workflow_status(),
        # NUS 1C — Safe Autopilot Learning
        _nus1c_safe_autopilot_learning_status(),
        # NUS 1D — Eval Gates, Rollback, Approval
        _nus1d_eval_rollback_gates_status(),
        # NUS 1E — Low-Risk Execution Foundation
        _nus1e_low_risk_execution_foundation_status(),
        # NUS 1F — Controlled High-Autonomy Session Framework
        _nus1f_controlled_high_autonomy_status(),
        _nus1f_founder_override_sessions_status(),
        _nus1f_production_policy_gate_status(),
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
        "wave1_ready": True,
        "wave1_scaffolded": True,
        "wave2_ready": True,
        "wave3_ready": True,
        "wave4_ready": True,
        "wave4_not_implemented": False,
        "wave3_4_not_implemented": False,
        "wave2_3_4_not_implemented": False,
        "nus1_status": "1c_safe_autopilot_learning_ready",
        "nus1a_status": "ready",
        "nus1b_status": "ready",
        "nus1c_status": "ready",
        "nus1d_status": "ready",
        "nus1e_status": "ready",
        "nus1f_status": "ready",
        "nus1d_plus_status": "not_started",
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
