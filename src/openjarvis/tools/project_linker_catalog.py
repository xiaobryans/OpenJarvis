"""Jarvis Project Linker Catalog — US7 Hold Fix.

10 tools for project source linking, validation, and operational linkage diagnosis.

Tools:
  project.sources.list            — list all source links for a project
  project.sources.validate_all    — validate all sources for a project (read-only)
  project.source.validate         — validate a single source link
  project.link_local_repo_plan    — plan what linking a local repo would do (dry-run)
  project.link_local_repo         — register and validate a local repo source (read-only)
  project.link_handoff_file       — register and validate a handoff file source
  project.link_openclaw_workspace — register and validate an OpenClaw workspace source
  project.link_runtime_endpoint   — register a runtime endpoint (blocked until approved)
  project.link_memory_namespace   — register a memory namespace source
  project.linkage_doctor          — full linkage health report + readiness impact

Governance:
  - All validations are read-only (no writes to any external source)
  - No secrets read or printed
  - No env vars printed
  - No broad scans — only validate explicitly configured paths
  - GitHub/API/runtime: not_configured or blocked until explicitly approved
  - OpenClaw: read-only unless explicitly approved
  - No mutate: OMNIX, OpenClaw, GitHub, runtime, deploy, Vercel, Supabase, Stripe
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Executors
# ---------------------------------------------------------------------------


def _exec_sources_list(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import ProjectSourceRegistry

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    links = ProjectSourceRegistry.list_for_project(project_id)
    return {
        "project_id": project_id,
        "total": len(links),
        "sources": [l.to_dict() for l in links],
    }


def _exec_sources_validate_all(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import ProjectSourceRegistry

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    report = ProjectSourceRegistry.get_linkage_status(project_id)
    return report


def _exec_source_validate(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceRegistry,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    source_id = inputs.get("source_id", "")
    if not source_id:
        return {"error": "source_id is required", "project_id": project_id}

    link = ProjectSourceRegistry.get(project_id, source_id)
    if link is None:
        return {
            "error": f"Source '{source_id}' not found for project '{project_id}'",
            "project_id": project_id,
            "source_id": source_id,
        }

    validated = validate_source_link(link)
    return validated.to_dict()


def _exec_link_local_repo_plan(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from pathlib import Path
    from openjarvis.projects.source_links import (
        ProjectSourceLink,
        ProjectSourceLinkType,
        ProjectSourceStatus,
        _is_jarvis_codebase,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    repo_path = inputs.get("repo_path", "")

    if not repo_path:
        return {
            "project_id": project_id,
            "action": "plan",
            "result": "no_op",
            "reason": "repo_path not provided — nothing to plan",
        }

    p = Path(repo_path).expanduser().resolve()
    is_jarvis = _is_jarvis_codebase(p)
    exists = p.exists()
    is_dir = p.is_dir() if exists else False

    would_be_status = "unknown"
    blocker = ""
    if not exists:
        would_be_status = ProjectSourceStatus.MISSING
        blocker = f"Path does not exist: {p}"
    elif not is_dir:
        would_be_status = ProjectSourceStatus.INVALID
        blocker = f"Path is not a directory: {p}"
    elif is_jarvis:
        would_be_status = ProjectSourceStatus.PLACEHOLDER
        blocker = (
            f"Path '{p}' is the Jarvis/OpenJarvis codebase. "
            f"This would be registered as a placeholder, not as a real "
            f"{project_id.upper()} source. Provide the real {project_id.upper()} repo path."
        )
    else:
        would_be_status = ProjectSourceStatus.READY_READ_ONLY
        blocker = ""

    return {
        "project_id": project_id,
        "action": "plan",
        "repo_path": str(p),
        "would_be_status": would_be_status,
        "blocker": blocker,
        "is_jarvis_codebase": is_jarvis,
        "path_exists": exists,
        "is_directory": is_dir,
        "note": (
            "This is a dry-run plan. Call project.link_local_repo to apply. "
            "Linking is read-only — no writes to the repo."
        ),
    }


def _exec_link_local_repo(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceLink,
        ProjectSourceLinkType,
        ProjectSourceRegistry,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    repo_path = inputs.get("repo_path", "")

    if not repo_path:
        return {
            "error": "repo_path is required",
            "project_id": project_id,
        }

    link = ProjectSourceLink(
        source_id="local_repo",
        project_id=project_id,
        link_type=ProjectSourceLinkType.LOCAL_REPO,
        path_or_url=repo_path,
        display_name=f"{project_id.upper()} Local Repository",
    )
    validated = validate_source_link(link)
    ProjectSourceRegistry.register(validated)
    return {
        "project_id": project_id,
        "action": "link_local_repo",
        "source": validated.to_dict(),
        "note": "Registered as read-only. Writes require explicit approval.",
    }


def _exec_link_handoff_file(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceLink,
        ProjectSourceLinkType,
        ProjectSourceRegistry,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    file_path = inputs.get("file_path", "")

    if not file_path:
        return {"error": "file_path is required", "project_id": project_id}

    link = ProjectSourceLink(
        source_id="handoff_file",
        project_id=project_id,
        link_type=ProjectSourceLinkType.HANDOFF_FILE,
        path_or_url=file_path,
        display_name=f"{project_id.upper()} Handoff File",
    )
    validated = validate_source_link(link)
    ProjectSourceRegistry.register(validated)
    return {
        "project_id": project_id,
        "action": "link_handoff_file",
        "source": validated.to_dict(),
    }


def _exec_link_openclaw_workspace(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceLink,
        ProjectSourceLinkType,
        ProjectSourceRegistry,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    workspace_path = inputs.get("workspace_path", "")
    source_type = inputs.get("source_type", "openclaw_workspace")

    if source_type not in ("openclaw_workspace", "openclaw_handoff"):
        source_type = "openclaw_workspace"

    if not workspace_path:
        return {
            "project_id": project_id,
            "source_id": source_type,
            "status": "not_configured",
            "note": (
                "workspace_path not provided. "
                "Provide a path to register an OpenClaw source. "
                "OpenClaw access is read-only unless explicitly approved."
            ),
        }

    link = ProjectSourceLink(
        source_id=source_type,
        project_id=project_id,
        link_type=source_type,
        path_or_url=workspace_path,
        display_name=f"{project_id.upper()} OpenClaw {'Workspace' if source_type == 'openclaw_workspace' else 'Handoff'}",
    )
    validated = validate_source_link(link)
    ProjectSourceRegistry.register(validated)
    return {
        "project_id": project_id,
        "action": "link_openclaw_workspace",
        "source": validated.to_dict(),
        "note": "OpenClaw write access requires explicit approval.",
    }


def _exec_link_runtime_endpoint(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceLink,
        ProjectSourceLinkType,
        ProjectSourceRegistry,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    url = inputs.get("url", "")
    endpoint_type = inputs.get("endpoint_type", "runtime_health_endpoint")

    if endpoint_type not in ("runtime_health_endpoint", "runtime_status_endpoint"):
        endpoint_type = "runtime_health_endpoint"

    if not url:
        return {
            "project_id": project_id,
            "source_id": endpoint_type,
            "status": "not_configured",
            "note": (
                "url not provided. Provide an HTTP/HTTPS URL to register a runtime endpoint. "
                "Live HTTP checks require explicit approval."
            ),
        }

    link = ProjectSourceLink(
        source_id=endpoint_type,
        project_id=project_id,
        link_type=endpoint_type,
        path_or_url=url,
        display_name=f"{project_id.upper()} Runtime {'Health' if endpoint_type == 'runtime_health_endpoint' else 'Status'} Endpoint",
    )
    validated = validate_source_link(link)
    ProjectSourceRegistry.register(validated)
    return {
        "project_id": project_id,
        "action": "link_runtime_endpoint",
        "source": validated.to_dict(),
        "note": "Live runtime endpoint checks require explicit approval.",
    }


def _exec_link_memory_namespace(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceLink,
        ProjectSourceLinkType,
        ProjectSourceRegistry,
        validate_source_link,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    namespace = inputs.get("namespace", "") or f"project:{project_id}"

    link = ProjectSourceLink(
        source_id="memory_namespace",
        project_id=project_id,
        link_type=ProjectSourceLinkType.MEMORY_NAMESPACE,
        path_or_url=namespace,
        display_name=f"{project_id.upper()} Memory Namespace",
    )
    validated = validate_source_link(link)
    ProjectSourceRegistry.register(validated)
    return {
        "project_id": project_id,
        "action": "link_memory_namespace",
        "source": validated.to_dict(),
    }


def _exec_linkage_doctor(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.projects.source_links import ProjectSourceRegistry
    from openjarvis.doctor.checks import check_project_linkage_status

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"

    linkage_report = ProjectSourceRegistry.get_linkage_status(project_id)
    check_result = check_project_linkage_status(project_id)

    readiness_impact = "unknown"
    if check_result.status == "fail":
        readiness_impact = "HOLD — project_linkage category fails; readiness gate blocked"
    elif check_result.status == "warn":
        readiness_impact = "WARN — partial linkage; some sources missing"
    elif check_result.status == "pass":
        readiness_impact = "PASS — project linked to real source"
    else:
        readiness_impact = f"NOT_CONFIGURED — {check_result.summary}"

    unblock_steps = []
    lstat = linkage_report.get("linkage_status", "")
    if lstat in ("placeholder", "not_configured"):
        unblock_steps = [
            f"Option A: Register real {project_id.upper()} local repo path "
            f"(not /Users/user/OpenJarvis which is the Jarvis codebase): "
            f"call project.link_local_repo with the correct path",
            f"Option B: Register GitHub remote: call project.link_runtime_endpoint "
            f"with owner/repo (requires approval)",
            f"Option C: Register OpenClaw workspace: call project.link_openclaw_workspace "
            f"with workspace path",
            f"Option D: Register OpenClaw handoff: call project.link_openclaw_workspace "
            f"with source_type=openclaw_handoff",
        ]

    return {
        "project_id": project_id,
        "linkage_status": lstat,
        "readiness_impact": readiness_impact,
        "check_result": check_result.to_dict(),
        "linkage_report": linkage_report,
        "unblock_steps": unblock_steps,
        "note": (
            "This is a read-only diagnostic. No sources are modified. "
            "Use project.link_* tools to configure sources."
        ),
    }


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_PROJECT_LINKER_TOOLS = [
    (
        ToolSpec(
            tool_id="project.sources.list",
            display_name="Project Sources List",
            description=(
                "List all configured source links for a project. "
                "Shows local_repo, GitHub, handoff, OpenClaw, runtime, memory namespace. "
                "Read-only. No secrets printed."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project ID (default: omnix)"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_sources_list",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_sources_list,
    ),
    (
        ToolSpec(
            tool_id="project.sources.validate_all",
            display_name="Project Sources Validate All",
            description=(
                "Validate all source links for a project. Read-only. "
                "Returns linkage_status: linked/placeholder/missing/not_configured. "
                "OMNIX local_repo=OpenJarvis → placeholder (HOLD blocker)."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_sources_validate_all",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_sources_validate_all,
    ),
    (
        ToolSpec(
            tool_id="project.source.validate",
            display_name="Project Source Validate",
            description=(
                "Validate a single source link by source_id. Read-only. "
                "Returns status, read_access, evidence, and blocker."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "source_id": {"type": "string", "description": "e.g. local_repo, handoff_file"},
                },
                "required": ["source_id"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_source_validate",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_source_validate,
    ),
    (
        ToolSpec(
            tool_id="project.link_local_repo_plan",
            display_name="Project Link Local Repo Plan",
            description=(
                "Dry-run plan: what would happen if you linked repo_path as local_repo? "
                "Detects placeholder (Jarvis codebase), missing path, or ready_read_only. "
                "No changes made. Safe to call."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string", "description": "Absolute path to test"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_link_local_repo_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_link_local_repo_plan,
    ),
    (
        ToolSpec(
            tool_id="project.link_local_repo",
            display_name="Project Link Local Repo",
            description=(
                "Register a local repo path as the project's local_repo source. "
                "Validates existence; detects placeholder (OpenJarvis path). "
                "Read-only link — no writes to the repo."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "repo_path": {"type": "string", "description": "Absolute path to local repo"},
                },
                "required": ["repo_path"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects", "write:project_config"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_link_local_repo",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_link_local_repo,
    ),
    (
        ToolSpec(
            tool_id="project.link_handoff_file",
            display_name="Project Link Handoff File",
            description=(
                "Register and validate a handoff file as a project source. "
                "Checks file exists and reports age. Read-only."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "file_path": {"type": "string"},
                },
                "required": ["file_path"],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_link_handoff_file",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_link_handoff_file,
    ),
    (
        ToolSpec(
            tool_id="project.link_openclaw_workspace",
            display_name="Project Link OpenClaw Workspace",
            description=(
                "Register an OpenClaw workspace or handoff path as a project source. "
                "Read-only unless explicitly approved. "
                "source_type: openclaw_workspace | openclaw_handoff."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "workspace_path": {"type": "string"},
                    "source_type": {
                        "type": "string",
                        "enum": ["openclaw_workspace", "openclaw_handoff"],
                    },
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_link_openclaw_workspace",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_link_openclaw_workspace,
    ),
    (
        ToolSpec(
            tool_id="project.link_runtime_endpoint",
            display_name="Project Link Runtime Endpoint",
            description=(
                "Register a runtime health or status endpoint URL. "
                "Status=blocked until live HTTP check is explicitly approved. "
                "endpoint_type: runtime_health_endpoint | runtime_status_endpoint."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "url": {"type": "string"},
                    "endpoint_type": {
                        "type": "string",
                        "enum": ["runtime_health_endpoint", "runtime_status_endpoint"],
                    },
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_link_runtime_endpoint",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_link_runtime_endpoint,
    ),
    (
        ToolSpec(
            tool_id="project.link_memory_namespace",
            display_name="Project Link Memory Namespace",
            description=(
                "Register a memory namespace for a project. "
                "Namespace is a logical key — always linked once set."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "namespace": {"type": "string"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_link_memory_namespace",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_link_memory_namespace,
    ),
    (
        ToolSpec(
            tool_id="project.linkage_doctor",
            display_name="Project Linkage Doctor",
            description=(
                "Full project linkage health report. "
                "Shows linkage_status, readiness_impact (HOLD/WARN/PASS), "
                "exact blocker, and unblock steps. "
                "OMNIX with OpenJarvis repo → linkage_status=placeholder → HOLD."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                },
                "required": [],
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects", "read:diagnostics"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_linkage_doctor",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_linkage_doctor,
    ),
]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _is_already_initialized() -> bool:
    return ToolRegistry.get("project.sources.list") is not None


def initialize_project_linker_catalog() -> None:
    """Register all project-linker tools into ToolRegistry.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_already_initialized():
        return
    for spec, executor in _PROJECT_LINKER_TOOLS:
        ToolRegistry.register(spec, executor=executor)
    logger.info(
        "Project linker catalog initialized: %d tools registered",
        len(_PROJECT_LINKER_TOOLS),
    )


__all__ = ["initialize_project_linker_catalog"]
