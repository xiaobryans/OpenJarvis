"""Jarvis Project Source Linker — source link registry and validation.

Each ProjectSourceLink describes a single configured or missing source for a project.
Sources are validated read-only (no writes, no secrets, no broad scans).

Source types:
  local_repo              — local filesystem path to the project's source repo
  github_remote           — GitHub owner/repo (read-only; requires safe config)
  handoff_file            — path to a handoff markdown file
  handoff_directory       — directory containing handoff files
  openclaw_workspace      — OpenClaw workspace path
  openclaw_handoff        — OpenClaw handoff file path
  runtime_health_endpoint — HTTP GET health check URL (read-only)
  runtime_status_endpoint — HTTP GET status check URL (read-only)
  docs_directory          — local docs path
  memory_namespace        — Jarvis memory namespace string

Source statuses:
  linked              — source configured and validated (read access confirmed)
  placeholder         — path/value exists but points to wrong target
                        (e.g. OMNIX repo_path pointing to Jarvis/OpenJarvis source)
  missing             — source configured but path/URL not accessible
  not_configured      — source not configured at all
  invalid             — source configured but validation raised an error
  blocked             — source requires explicit approval before access
  ready_read_only     — source accessible for reads; writes require approval

Governance rules enforced here:
  - No secrets read or printed
  - No env vars printed
  - No writes to any source
  - GitHub/API: not_configured unless safely configured
  - Local path: read-only existence + is_dir/is_file check only (no broad scan)
  - No broad directory scans (only validate configured paths)
  - Runtime endpoints: not validated without explicit URL (not_configured)
  - OpenClaw: read-only unless explicitly approved
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_JARVIS_REPO_ROOT = Path(__file__).parent.parent.parent.parent.resolve()


def _load_openjarvis_env() -> None:
    """Load ~/.openjarvis/cloud-keys.env (and local.env if present) into os.environ.

    Uses setdefault so already-set env vars are never overwritten.
    Never prints or logs values.
    """
    base = Path.home() / ".openjarvis"
    for fname in ("local.env", "cloud-keys.env"):
        env_file = base / fname
        if not env_file.is_file():
            continue
        try:
            with open(env_file) as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class ProjectSourceLinkType:
    LOCAL_REPO = "local_repo"
    GITHUB_REMOTE = "github_remote"
    HANDOFF_FILE = "handoff_file"
    HANDOFF_DIRECTORY = "handoff_directory"
    OPENCLAW_WORKSPACE = "openclaw_workspace"
    OPENCLAW_HANDOFF = "openclaw_handoff"
    RUNTIME_HEALTH_ENDPOINT = "runtime_health_endpoint"
    RUNTIME_STATUS_ENDPOINT = "runtime_status_endpoint"
    DOCS_DIRECTORY = "docs_directory"
    MEMORY_NAMESPACE = "memory_namespace"


class ProjectSourceStatus:
    LINKED = "linked"
    PLACEHOLDER = "placeholder"
    MISSING = "missing"
    NOT_CONFIGURED = "not_configured"
    INVALID = "invalid"
    BLOCKED = "blocked"
    READY_READ_ONLY = "ready_read_only"


# ---------------------------------------------------------------------------
# ProjectSourceLink dataclass
# ---------------------------------------------------------------------------


@dataclass
class ProjectSourceLink:
    """A single source link for a project.

    Describes one configured (or missing) external source such as a local repo,
    GitHub remote, handoff file, OpenClaw workspace, or runtime endpoint.
    """

    source_id: str
    project_id: str
    link_type: str
    path_or_url: str
    status: str = ProjectSourceStatus.NOT_CONFIGURED
    read_access: bool = False
    write_access: bool = False
    last_checked_at: float = field(default_factory=time.time)
    evidence: Dict[str, Any] = field(default_factory=dict)
    blocker: str = ""
    display_name: str = ""

    def is_operational(self) -> bool:
        """Return True only if this source is genuinely linked and readable."""
        return self.status in (
            ProjectSourceStatus.LINKED,
            ProjectSourceStatus.READY_READ_ONLY,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "project_id": self.project_id,
            "link_type": self.link_type,
            "path_or_url": self.path_or_url,
            "status": self.status,
            "read_access": self.read_access,
            "write_access": self.write_access,
            "last_checked_at": self.last_checked_at,
            "evidence": self.evidence,
            "blocker": self.blocker,
            "display_name": self.display_name,
        }


# ---------------------------------------------------------------------------
# Placeholder detection — read-only, targeted (no broad scan)
# ---------------------------------------------------------------------------


def _is_jarvis_codebase(path: Path) -> bool:
    """Return True if path is the OpenJarvis/Jarvis codebase, not a real project source.

    Uses only two targeted existence checks — no broad directory scan.
    """
    return (path / "src" / "openjarvis" / "governance" / "constitution.py").exists()


def _is_openjarvis_root(path: Path) -> bool:
    """Return True if path is the same as (or inside) the OpenJarvis repo root."""
    try:
        path.resolve().relative_to(_JARVIS_REPO_ROOT)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Validators — all read-only
# ---------------------------------------------------------------------------


def _validate_local_repo(link: ProjectSourceLink) -> ProjectSourceLink:
    """Validate a local_repo source. Read-only: only checks existence and type.

    Marks placeholder if the path is the Jarvis/OpenJarvis codebase itself.
    """
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.read_access = False
        link.blocker = "No local_repo path configured"
        link.evidence["check"] = "path_empty"
        return link

    try:
        p = Path(link.path_or_url).expanduser().resolve()
        link.evidence["resolved_path"] = str(p)

        if not p.exists():
            link.status = ProjectSourceStatus.MISSING
            link.read_access = False
            link.blocker = f"Local repo path does not exist: {p}"
            link.evidence["exists"] = False
            return link

        if not p.is_dir():
            link.status = ProjectSourceStatus.INVALID
            link.read_access = False
            link.blocker = f"Local repo path is not a directory: {p}"
            link.evidence["is_dir"] = False
            return link

        link.evidence["exists"] = True
        link.evidence["is_dir"] = True

        # Placeholder check: is this actually the Jarvis/OpenJarvis codebase?
        if _is_jarvis_codebase(p):
            link.status = ProjectSourceStatus.PLACEHOLDER
            link.read_access = True
            link.evidence["is_jarvis_codebase"] = True
            link.evidence["jarvis_root"] = str(_JARVIS_REPO_ROOT)
            link.blocker = (
                f"repo_path '{p}' points to the Jarvis/OpenJarvis codebase itself, "
                f"not to the real {link.project_id.upper()} product source. "
                f"Configure the real {link.project_id.upper()} repo path or a GitHub/OpenClaw source."
            )
            return link

        # Genuine linked local repo
        link.status = ProjectSourceStatus.READY_READ_ONLY
        link.read_access = True
        link.write_access = False
        link.evidence["is_jarvis_codebase"] = False
        link.evidence["note"] = "Writes require explicit approval"
        link.blocker = ""
        return link

    except Exception as exc:
        link.status = ProjectSourceStatus.INVALID
        link.read_access = False
        link.blocker = f"Validation error: {exc}"
        link.evidence["error"] = str(exc)
        return link


def _validate_handoff_file(link: ProjectSourceLink) -> ProjectSourceLink:
    """Validate a handoff_file source. Read-only: checks existence only."""
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No handoff_file path configured"
        link.evidence["check"] = "path_empty"
        return link

    try:
        p = Path(link.path_or_url).expanduser()
        if not p.is_absolute():
            p = (_JARVIS_REPO_ROOT / p).resolve()
        else:
            p = p.resolve()

        link.evidence["resolved_path"] = str(p)
        if p.exists() and p.is_file():
            stat = p.stat()
            age_days = (time.time() - stat.st_mtime) / 86400
            link.status = ProjectSourceStatus.LINKED
            link.read_access = True
            link.evidence["exists"] = True
            link.evidence["size_bytes"] = stat.st_size
            link.evidence["age_days"] = round(age_days, 1)
            link.blocker = ""
        else:
            link.status = ProjectSourceStatus.MISSING
            link.evidence["exists"] = False
            link.blocker = f"Handoff file not found: {p}"
        return link
    except Exception as exc:
        link.status = ProjectSourceStatus.INVALID
        link.evidence["error"] = str(exc)
        link.blocker = f"Validation error: {exc}"
        return link


def _validate_handoff_directory(link: ProjectSourceLink) -> ProjectSourceLink:
    """Validate a handoff_directory. Read-only: checks existence only."""
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No handoff_directory path configured"
        link.evidence["check"] = "path_empty"
        return link

    try:
        p = Path(link.path_or_url).expanduser().resolve()
        link.evidence["resolved_path"] = str(p)
        if p.exists() and p.is_dir():
            link.status = ProjectSourceStatus.LINKED
            link.read_access = True
            link.evidence["exists"] = True
            link.blocker = ""
        else:
            link.status = ProjectSourceStatus.MISSING
            link.evidence["exists"] = False
            link.blocker = f"Handoff directory not found: {p}"
        return link
    except Exception as exc:
        link.status = ProjectSourceStatus.INVALID
        link.evidence["error"] = str(exc)
        link.blocker = f"Validation error: {exc}"
        return link


def _validate_openclaw(link: ProjectSourceLink) -> ProjectSourceLink:
    """Validate an openclaw_workspace or openclaw_handoff source. Read-only."""
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No OpenClaw path configured"
        link.evidence["check"] = "path_empty"
        return link

    try:
        p = Path(link.path_or_url).expanduser().resolve()
        link.evidence["resolved_path"] = str(p)
        if p.exists():
            link.status = ProjectSourceStatus.READY_READ_ONLY
            link.read_access = True
            link.write_access = False
            link.evidence["exists"] = True
            link.evidence["note"] = "OpenClaw write access requires explicit approval"
            link.blocker = ""
        else:
            link.status = ProjectSourceStatus.MISSING
            link.evidence["exists"] = False
            link.blocker = f"OpenClaw path not found: {p}"
        return link
    except Exception as exc:
        link.status = ProjectSourceStatus.INVALID
        link.evidence["error"] = str(exc)
        link.blocker = f"Validation error: {exc}"
        return link


def _validate_github_remote(link: ProjectSourceLink) -> ProjectSourceLink:
    """GitHub remote: not_configured unless a safe URL is present.

    No live HTTP calls. Status = not_configured or linked (format-only check).
    GitHub API access requires safe configuration and explicit approval.
    """
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No GitHub remote configured (github_remote not set)"
        link.evidence["check"] = "path_empty"
        return link

    url = link.path_or_url.strip()
    link.evidence["raw_url"] = url
    if url.startswith("https://github.com/") or url.startswith("git@github.com:"):
        link.status = ProjectSourceStatus.BLOCKED
        link.read_access = False
        link.blocker = (
            "GitHub remote is configured but live access requires explicit approval. "
            "Status=blocked until safe read access is approved."
        )
        link.evidence["format_valid"] = True
        link.evidence["note"] = "Live GitHub API access requires explicit approval"
    else:
        link.status = ProjectSourceStatus.INVALID
        link.evidence["format_valid"] = False
        link.blocker = f"GitHub remote URL format invalid: {url}"
    return link


def _validate_runtime_endpoint(link: ProjectSourceLink) -> ProjectSourceLink:
    """Runtime endpoint: not_configured unless URL is present.

    No live HTTP calls in this validation (read-only existence check only).
    A future sprint may add safe HTTP GET validation.
    """
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No runtime endpoint URL configured"
        link.evidence["check"] = "url_empty"
        return link

    url = link.path_or_url.strip()
    link.evidence["url"] = url
    if url.startswith("http://") or url.startswith("https://"):
        link.status = ProjectSourceStatus.BLOCKED
        link.read_access = False
        link.blocker = (
            "Runtime endpoint is configured but live HTTP GET requires explicit approval."
        )
        link.evidence["format_valid"] = True
        link.evidence["note"] = "Live runtime health checks require explicit approval"
    else:
        link.status = ProjectSourceStatus.INVALID
        link.evidence["format_valid"] = False
        link.blocker = f"Runtime endpoint URL format invalid: {url}"
    return link


def _validate_docs_directory(link: ProjectSourceLink) -> ProjectSourceLink:
    """Validate docs directory. Read-only existence check."""
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No docs_directory configured"
        link.evidence["check"] = "path_empty"
        return link

    try:
        p = Path(link.path_or_url).expanduser()
        if not p.is_absolute():
            p = (_JARVIS_REPO_ROOT / p).resolve()
        else:
            p = p.resolve()
        link.evidence["resolved_path"] = str(p)
        if p.exists() and p.is_dir():
            link.status = ProjectSourceStatus.LINKED
            link.read_access = True
            link.evidence["exists"] = True
            link.blocker = ""
        else:
            link.status = ProjectSourceStatus.MISSING
            link.evidence["exists"] = False
            link.blocker = f"Docs directory not found: {p}"
        return link
    except Exception as exc:
        link.status = ProjectSourceStatus.INVALID
        link.evidence["error"] = str(exc)
        link.blocker = f"Validation error: {exc}"
        return link


def _validate_memory_namespace(link: ProjectSourceLink) -> ProjectSourceLink:
    """Memory namespace: always linked if non-empty (it's a string key)."""
    if not link.path_or_url:
        link.status = ProjectSourceStatus.NOT_CONFIGURED
        link.blocker = "No memory_namespace configured"
        link.evidence["check"] = "namespace_empty"
        return link

    link.status = ProjectSourceStatus.LINKED
    link.read_access = True
    link.write_access = True
    link.evidence["namespace"] = link.path_or_url
    link.evidence["note"] = "Memory namespace is a logical key — always accessible"
    link.blocker = ""
    return link


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_VALIDATORS = {
    ProjectSourceLinkType.LOCAL_REPO: _validate_local_repo,
    ProjectSourceLinkType.GITHUB_REMOTE: _validate_github_remote,
    ProjectSourceLinkType.HANDOFF_FILE: _validate_handoff_file,
    ProjectSourceLinkType.HANDOFF_DIRECTORY: _validate_handoff_directory,
    ProjectSourceLinkType.OPENCLAW_WORKSPACE: _validate_openclaw,
    ProjectSourceLinkType.OPENCLAW_HANDOFF: _validate_openclaw,
    ProjectSourceLinkType.RUNTIME_HEALTH_ENDPOINT: _validate_runtime_endpoint,
    ProjectSourceLinkType.RUNTIME_STATUS_ENDPOINT: _validate_runtime_endpoint,
    ProjectSourceLinkType.DOCS_DIRECTORY: _validate_docs_directory,
    ProjectSourceLinkType.MEMORY_NAMESPACE: _validate_memory_namespace,
}


def validate_source_link(link: ProjectSourceLink) -> ProjectSourceLink:
    """Validate a single source link. Returns updated link with status/evidence.

    Read-only: no writes, no secrets, no broad scans, no live HTTP.
    """
    validator = _VALIDATORS.get(link.link_type)
    if validator is None:
        link.status = ProjectSourceStatus.INVALID
        link.blocker = f"Unknown link type: {link.link_type}"
        link.evidence["error"] = "no_validator"
        return link

    link.last_checked_at = time.time()
    try:
        return validator(link)
    except Exception as exc:
        link.status = ProjectSourceStatus.INVALID
        link.blocker = f"Validator raised: {exc}"
        link.evidence["error"] = str(exc)
        return link


# ---------------------------------------------------------------------------
# ProjectSourceRegistry — in-memory, bootstrapped from ProjectRegistry
# ---------------------------------------------------------------------------


class ProjectSourceRegistry:
    """In-memory registry of source links, keyed by (project_id, source_id).

    Bootstrapped from ProjectRegistry OMNIX_PROJECT on first access.
    Additional sources can be registered at runtime.
    Safe to call clear() for test isolation.
    """

    _links: Dict[str, Dict[str, ProjectSourceLink]] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if not cls._initialized:
            cls._bootstrap_omnix()
            cls._initialized = True

    @classmethod
    def _bootstrap_omnix(cls) -> None:
        """Bootstrap OMNIX source links from OMNIX_PROJECT profile.

        Reads env vars at call time so that values set in cloud-keys.env or
        local.env (auto-loaded by _load_openjarvis_env) are picked up.

        Priority:
          JARVIS_PROJECT_OMNIX_REPO_PATH > OMNIX_PROJECT.repo_path
          OPENCLAW_WORKSPACE_PATH        > "" (not_configured)
          OPENCLAW_HANDOFF_PATH          > "" (not_configured)
        """
        _load_openjarvis_env()
        from openjarvis.governance.constitution import OMNIX_PROJECT

        project_id = OMNIX_PROJECT.project_id
        sources: List[ProjectSourceLink] = []

        # local_repo — use env var if present, else fall back to profile
        local_repo_path = (
            os.environ.get("JARVIS_PROJECT_OMNIX_REPO_PATH", "").strip()
            or OMNIX_PROJECT.repo_path
        )
        sources.append(ProjectSourceLink(
            source_id="local_repo",
            project_id=project_id,
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url=local_repo_path,
            display_name="OMNIX Local Repository",
        ))

        # github_remote — not configured
        sources.append(ProjectSourceLink(
            source_id="github_remote",
            project_id=project_id,
            link_type=ProjectSourceLinkType.GITHUB_REMOTE,
            path_or_url="",
            display_name="OMNIX GitHub Remote",
        ))

        # handoff_file — primary Jarvis handoff
        handoff_path = ""
        if OMNIX_PROJECT.handoff_paths:
            handoff_path = OMNIX_PROJECT.handoff_paths[0]
        sources.append(ProjectSourceLink(
            source_id="handoff_file",
            project_id=project_id,
            link_type=ProjectSourceLinkType.HANDOFF_FILE,
            path_or_url=handoff_path,
            display_name="OMNIX Primary Handoff File",
        ))

        # openclaw_workspace — use env var if present
        openclaw_ws = os.environ.get("OPENCLAW_WORKSPACE_PATH", "").strip()
        sources.append(ProjectSourceLink(
            source_id="openclaw_workspace",
            project_id=project_id,
            link_type=ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            path_or_url=openclaw_ws,
            display_name="OMNIX OpenClaw Workspace",
        ))

        # openclaw_handoff — use env var if present
        openclaw_hf = os.environ.get("OPENCLAW_HANDOFF_PATH", "").strip()
        sources.append(ProjectSourceLink(
            source_id="openclaw_handoff",
            project_id=project_id,
            link_type=ProjectSourceLinkType.OPENCLAW_HANDOFF,
            path_or_url=openclaw_hf,
            display_name="OMNIX OpenClaw Handoff",
        ))

        # runtime_health_endpoint — not configured
        sources.append(ProjectSourceLink(
            source_id="runtime_health_endpoint",
            project_id=project_id,
            link_type=ProjectSourceLinkType.RUNTIME_HEALTH_ENDPOINT,
            path_or_url="",
            display_name="OMNIX Runtime Health Endpoint",
        ))

        # docs_directory — first docs_paths entry if present
        docs_path = ""
        if OMNIX_PROJECT.docs_paths:
            docs_path = OMNIX_PROJECT.docs_paths[0]
        sources.append(ProjectSourceLink(
            source_id="docs_directory",
            project_id=project_id,
            link_type=ProjectSourceLinkType.DOCS_DIRECTORY,
            path_or_url=docs_path,
            display_name="OMNIX Docs Directory",
        ))

        # memory_namespace
        sources.append(ProjectSourceLink(
            source_id="memory_namespace",
            project_id=project_id,
            link_type=ProjectSourceLinkType.MEMORY_NAMESPACE,
            path_or_url=OMNIX_PROJECT.memory_namespace,
            display_name="OMNIX Memory Namespace",
        ))

        if project_id not in cls._links:
            cls._links[project_id] = {}
        for s in sources:
            cls._links[project_id][s.source_id] = s

    @classmethod
    def register(cls, link: ProjectSourceLink) -> None:
        """Register or overwrite a source link."""
        cls._ensure_initialized()
        if link.project_id not in cls._links:
            cls._links[link.project_id] = {}
        cls._links[link.project_id][link.source_id] = link
        logger.info(
            "Registered source link: %s/%s (%s)",
            link.project_id, link.source_id, link.link_type,
        )

    @classmethod
    def get(cls, project_id: str, source_id: str) -> Optional[ProjectSourceLink]:
        """Get a specific source link."""
        cls._ensure_initialized()
        return cls._links.get(project_id, {}).get(source_id)

    @classmethod
    def list_for_project(cls, project_id: str) -> List[ProjectSourceLink]:
        """List all source links for a project."""
        cls._ensure_initialized()
        return list(cls._links.get(project_id, {}).values())

    @classmethod
    def validate_all_for_project(cls, project_id: str) -> List[ProjectSourceLink]:
        """Validate all source links for a project. Read-only."""
        cls._ensure_initialized()
        links = cls.list_for_project(project_id)
        results = []
        for link in links:
            results.append(validate_source_link(link))
        return results

    # Primary sources: prove the project's *actual product source* is reachable.
    # Secondary sources (handoff_file, docs_directory, memory_namespace,
    # runtime_health_endpoint) are metadata — they do NOT prove operational linkage.
    _PRIMARY_SOURCE_TYPES = frozenset({
        ProjectSourceLinkType.LOCAL_REPO,
        ProjectSourceLinkType.GITHUB_REMOTE,
        ProjectSourceLinkType.OPENCLAW_WORKSPACE,
        ProjectSourceLinkType.OPENCLAW_HANDOFF,
    })

    @classmethod
    def get_linkage_status(cls, project_id: str) -> Dict[str, Any]:
        """Get aggregated linkage status for a project.

        Only primary sources (local_repo, github_remote, openclaw_workspace,
        openclaw_handoff) count toward operational linkage.
        handoff_file, memory_namespace etc. are metadata — they alone cannot
        satisfy linkage.

        Returns overall linkage_status:
          linked             — at least one primary source is linked
          placeholder        — primary source configured but points to wrong target
                               (e.g. OMNIX local_repo=Jarvis/OpenJarvis codebase)
          missing_required   — primary source configured but path not accessible
          not_configured     — no primary sources configured at all
        """
        cls._ensure_initialized()
        links = cls.validate_all_for_project(project_id)
        if not links:
            return {
                "project_id": project_id,
                "linkage_status": "not_configured",
                "blocker": "No source links registered for this project",
                "sources": [],
            }

        primary = [l for l in links if l.link_type in cls._PRIMARY_SOURCE_TYPES]
        all_operational = [l for l in links if l.is_operational()]
        primary_operational = [l for l in primary if l.is_operational()]
        placeholders = [l for l in primary if l.status == ProjectSourceStatus.PLACEHOLDER]
        missing = [l for l in primary if l.status == ProjectSourceStatus.MISSING]
        not_configured_primary = [l for l in primary if l.status == ProjectSourceStatus.NOT_CONFIGURED]
        invalid = [l for l in primary if l.status == ProjectSourceStatus.INVALID]
        blocked = [l for l in primary if l.status == ProjectSourceStatus.BLOCKED]

        if primary_operational:
            linkage_status = "linked"
            blocker = ""
        elif placeholders:
            linkage_status = "placeholder"
            blocker = (
                f"Primary source(s) are placeholders — they point to the wrong target. "
                f"Placeholder sources: {[l.source_id for l in placeholders]}. "
                f"Configure a real source: local_repo pointing to the real "
                f"{project_id.upper()} product (not /Users/user/OpenJarvis which is the "
                f"Jarvis codebase), a GitHub remote, or an OpenClaw workspace."
            )
        elif not primary or all(l.status == ProjectSourceStatus.NOT_CONFIGURED for l in primary):
            linkage_status = "not_configured"
            blocker = (
                f"No primary sources configured for project '{project_id}'. "
                f"Configure local_repo, github_remote, or openclaw_workspace."
            )
        else:
            linkage_status = "missing_required"
            blocker = (
                f"Primary sources configured but not accessible: "
                f"missing={[l.source_id for l in missing]}, "
                f"invalid={[l.source_id for l in invalid]}"
            )

        return {
            "project_id": project_id,
            "linkage_status": linkage_status,
            "blocker": blocker,
            "counts": {
                "total": len(links),
                "primary": len(primary),
                "operational": len(primary_operational),
                "placeholder": len(placeholders),
                "missing": len(missing),
                "not_configured": len(not_configured_primary),
                "invalid": len(invalid),
                "blocked": len(blocked),
            },
            "sources": [l.to_dict() for l in links],
        }

    @classmethod
    def clear(cls) -> None:
        """Reset for test isolation."""
        cls._links.clear()
        cls._initialized = False


# ---------------------------------------------------------------------------
# Future project source profile template
# ---------------------------------------------------------------------------


def make_future_project_source_template(
    project_id: str,
    name: str,
    local_repo: str = "",
    github_remote: str = "",
    handoff_file: str = "",
    openclaw_workspace: str = "",
    runtime_health_endpoint: str = "",
    memory_namespace: str = "",
) -> List[ProjectSourceLink]:
    """Return a list of source links for a new project (all not_configured by default).

    This is the onboarding contract: fill in only the sources you have.
    """
    if not memory_namespace:
        memory_namespace = f"project:{project_id}"

    return [
        ProjectSourceLink(
            source_id="local_repo",
            project_id=project_id,
            link_type=ProjectSourceLinkType.LOCAL_REPO,
            path_or_url=local_repo,
            display_name=f"{name} Local Repository",
        ),
        ProjectSourceLink(
            source_id="github_remote",
            project_id=project_id,
            link_type=ProjectSourceLinkType.GITHUB_REMOTE,
            path_or_url=github_remote,
            display_name=f"{name} GitHub Remote",
        ),
        ProjectSourceLink(
            source_id="handoff_file",
            project_id=project_id,
            link_type=ProjectSourceLinkType.HANDOFF_FILE,
            path_or_url=handoff_file,
            display_name=f"{name} Handoff File",
        ),
        ProjectSourceLink(
            source_id="openclaw_workspace",
            project_id=project_id,
            link_type=ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            path_or_url=openclaw_workspace,
            display_name=f"{name} OpenClaw Workspace",
        ),
        ProjectSourceLink(
            source_id="runtime_health_endpoint",
            project_id=project_id,
            link_type=ProjectSourceLinkType.RUNTIME_HEALTH_ENDPOINT,
            path_or_url=runtime_health_endpoint,
            display_name=f"{name} Runtime Health Endpoint",
        ),
        ProjectSourceLink(
            source_id="memory_namespace",
            project_id=project_id,
            link_type=ProjectSourceLinkType.MEMORY_NAMESPACE,
            path_or_url=memory_namespace,
            display_name=f"{name} Memory Namespace",
        ),
    ]


__all__ = [
    "ProjectSourceLink",
    "ProjectSourceLinkType",
    "ProjectSourceRegistry",
    "ProjectSourceStatus",
    "make_future_project_source_template",
    "validate_source_link",
]
