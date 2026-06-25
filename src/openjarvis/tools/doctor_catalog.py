"""Jarvis Doctor Catalog — Ultra Sprint 7 doctor/readiness tools.

Tools (5 total, all available):
  doctor category (3):
    doctor.run           — run all 12 diagnostic checks for a project
    doctor.project       — run project-specific checks only (subset)
    doctor.report        — generate machine-readable diagnostic report

  readiness category (2):
    readiness.evaluate   — evaluate readiness gate (8 categories, 4 verdicts)
    readiness.evidence_summary — summarize evidence for all readiness categories

Governance:
  - No secrets in any output
  - No real outbound sends
  - No auto-fix
  - All outputs are evidence-backed (pass/warn/fail/not_configured only)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _exec_doctor_run(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.doctor.checks import run_all_checks

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    results = run_all_checks(project_id=project_id)
    by_status: Dict[str, int] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "project_id": project_id,
        "total_checks": len(results),
        "by_status": by_status,
        "checks": [r.to_dict() for r in results],
    }


def _exec_doctor_project(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.doctor.checks import (
        check_project_registry_health,
        check_git_worktree_status,
        check_handoff_freshness,
        check_packaged_app_build_metadata,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    checks = [
        check_project_registry_health(project_id),
        check_git_worktree_status(project_id),
        check_handoff_freshness(project_id),
        check_packaged_app_build_metadata(project_id),
    ]
    by_status: Dict[str, int] = {}
    for r in checks:
        by_status[r.status] = by_status.get(r.status, 0) + 1
    return {
        "project_id": project_id,
        "total_checks": len(checks),
        "by_status": by_status,
        "checks": [r.to_dict() for r in checks],
    }


def _exec_doctor_report(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.doctor.checks import run_all_checks

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    results = run_all_checks(project_id=project_id)
    by_status: Dict[str, int] = {}
    by_category: Dict[str, Any] = {}
    for r in results:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_category[r.category] = by_category.get(r.category, [])
        by_category[r.category].append(
            {"check_id": r.check_id, "status": r.status, "summary": r.summary}
        )
    return {
        "project_id": project_id,
        "total_checks": len(results),
        "by_status": by_status,
        "by_category": by_category,
        "checks": [r.to_dict() for r in results],
    }


def _exec_readiness_evaluate(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.doctor.readiness import evaluate_readiness

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    report = evaluate_readiness(project_id=project_id)
    return report.to_dict()


def _exec_readiness_evidence_summary(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.doctor.readiness import generate_v1_report

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    return generate_v1_report(project_id=project_id)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_DOCTOR_TOOLS = [
    (
        ToolSpec(
            tool_id="doctor.run",
            display_name="Doctor Run",
            description=(
                "Run all 12 Jarvis diagnostic checks for a project. "
                "Returns pass/warn/fail/not_configured for each check with evidence. "
                "No secrets, no real sends, no auto-fix."
            ),
            category="doctor",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project to diagnose (default: omnix)",
                    }
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "total_checks": {"type": "integer"},
                    "by_status": {"type": "object"},
                    "checks": {"type": "array"},
                },
            },
            required_permissions=["read:diagnostics"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_doctor_run",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_doctor_run,
    ),
    (
        ToolSpec(
            tool_id="doctor.project",
            display_name="Doctor Project",
            description=(
                "Run project-specific diagnostic checks: registry health, "
                "git status, handoff freshness, packaged app metadata. "
                "Subset of doctor.run focused on project awareness."
            ),
            category="doctor",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project to check (default: omnix)",
                    }
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "total_checks": {"type": "integer"},
                    "by_status": {"type": "object"},
                    "checks": {"type": "array"},
                },
            },
            required_permissions=["read:diagnostics"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_doctor_project",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_doctor_project,
    ),
    (
        ToolSpec(
            tool_id="doctor.report",
            display_name="Doctor Report",
            description=(
                "Generate a full machine-readable diagnostic report grouped "
                "by category. Includes all 12 checks with evidence. "
                "Honest: no fake green status."
            ),
            category="doctor",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project to report on (default: omnix)",
                    }
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "total_checks": {"type": "integer"},
                    "by_status": {"type": "object"},
                    "by_category": {"type": "object"},
                    "checks": {"type": "array"},
                },
            },
            required_permissions=["read:diagnostics"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_doctor_report",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_doctor_report,
    ),
    (
        ToolSpec(
            tool_id="readiness.evaluate",
            display_name="Readiness Evaluate",
            description=(
                "Evaluate Jarvis V1 daily-driver readiness gate for a project. "
                "8 categories, 4 verdicts: ready/warn/hold/unsafe. "
                "Never self-accepts without evidence. "
                "References cost-control law in behavior."
            ),
            category="readiness",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project to evaluate (default: omnix)",
                    }
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "verdict": {
                        "type": "string",
                        "enum": ["ready", "warn", "hold", "unsafe"],
                    },
                    "summary": {"type": "string"},
                    "categories": {"type": "object"},
                    "fake_capability_check": {"type": "object"},
                    "accepted_checkpoints": {"type": "array"},
                },
            },
            required_permissions=["read:diagnostics"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_readiness_evaluate",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_readiness_evaluate,
    ),
    (
        ToolSpec(
            tool_id="readiness.evidence_summary",
            display_name="Readiness Evidence Summary",
            description=(
                "Generate V1 readiness evidence summary: "
                "available/degraded/not_configured/planned counts for tools, skills, "
                "watchdogs; accepted checkpoints carried forward; unsafe actions blocked; "
                "remaining limitations; post-V1 roadmap."
            ),
            category="readiness",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "string",
                        "description": "Project to summarize (default: omnix)",
                    }
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "verdict": {"type": "string"},
                    "counts": {"type": "object"},
                    "accepted_checkpoints": {"type": "array"},
                    "unsafe_actions_blocked": {"type": "array"},
                    "remaining_limitations": {"type": "array"},
                    "post_v1_roadmap": {"type": "array"},
                },
            },
            required_permissions=["read:diagnostics"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_readiness_evidence_summary",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_readiness_evidence_summary,
    ),
]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _is_already_initialized() -> bool:
    return ToolRegistry.get("doctor.run") is not None


def initialize_doctor_catalog() -> None:
    """Register all doctor/readiness tools into ToolRegistry.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_already_initialized():
        return
    for spec, executor in _DOCTOR_TOOLS:
        ToolRegistry.register(spec, executor=executor)
    logger.info(
        "Doctor catalog initialized: %d doctor/readiness tools registered",
        len(_DOCTOR_TOOLS),
    )


__all__ = [
    "initialize_doctor_catalog",
]
