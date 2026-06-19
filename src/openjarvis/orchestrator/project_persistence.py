"""ProjectRegistry Persistence — JSONL-backed project registry that survives restart.

Extends the in-process ProjectRegistry (governance/constitution.py) with:
  - persist_registry(): write current registry to ~/.jarvis/project_registry.json
  - load_registry(): load from disk and re-register projects into ProjectRegistry
  - check_registry_health(): doctor-style status check

Design rules:
  - OMNIX remains pre-registered in constitution.py as Project 1. Persistence
    supplements — does not replace — that initialization.
  - Personal tasks (no project_context) still work without any persisted project.
  - No OMNIX hardcoding: any project in the registry is persisted equally.
  - No secrets stored in registry file.
  - Graceful degradation: if file is missing or corrupt, in-process registry
    is used and a rebuild warning is emitted.
  - OpenJarvis project is bootstrapped automatically (mirrors
    _bootstrap_openjarvis() in source_links.py).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_REGISTRY_FILE = Path.home() / ".jarvis" / "project_registry.json"
_BACKUP_FILE = Path.home() / ".jarvis" / "project_registry.json.bak"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _project_to_dict(project: Any) -> Dict[str, Any]:
    """Serialize a ProjectProfile to a plain dict (no secrets)."""
    return {
        "project_id": project.project_id,
        "display_name": project.display_name,
        "priority": project.priority,
        "active": project.active,
        "notes": getattr(project, "notes", ""),
    }


def _dict_to_project(data: Dict[str, Any]) -> Any:
    """Deserialize a dict back to a ProjectProfile."""
    from openjarvis.governance.constitution import ProjectProfile
    return ProjectProfile(
        project_id=data["project_id"],
        display_name=data.get("display_name", data["project_id"]),
        priority=data.get("priority", 99),
        active=data.get("active", True),
        notes=data.get("notes", ""),
    )


# ---------------------------------------------------------------------------
# Persist / Load
# ---------------------------------------------------------------------------

def persist_registry() -> bool:
    """Write the current ProjectRegistry to ~/.jarvis/project_registry.json.

    Returns True on success, False on failure (never raises).
    """
    try:
        from openjarvis.governance.constitution import ProjectRegistry
        projects = ProjectRegistry.list_projects()
        payload: Dict[str, Any] = {
            "schema_version": 1,
            "persisted_at": time.time(),
            "projects": [_project_to_dict(p) for p in projects],
        }
        _REGISTRY_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write via temp + rename
        tmp = _REGISTRY_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        # Back up existing before replacing
        if _REGISTRY_FILE.exists():
            import shutil
            shutil.copy2(_REGISTRY_FILE, _BACKUP_FILE)
        tmp.replace(_REGISTRY_FILE)
        logger.debug("ProjectRegistry persisted: %d projects", len(projects))
        return True
    except Exception as exc:
        logger.warning("ProjectRegistry persist failed (non-fatal): %s", exc)
        return False


def load_registry() -> Dict[str, Any]:
    """Load ProjectRegistry from disk and re-register projects.

    Returns a status dict:
      {"loaded": bool, "project_count": int, "projects": [...], "error": str|None}

    OMNIX is always present via _ensure_initialized(); this adds any
    additional projects persisted from previous sessions.
    """
    if not _REGISTRY_FILE.exists():
        return {
            "loaded": False,
            "project_count": 0,
            "projects": [],
            "source": "none",
            "error": "registry file not found — using in-process defaults",
        }
    try:
        from openjarvis.governance.constitution import ProjectRegistry
        data = json.loads(_REGISTRY_FILE.read_text(encoding="utf-8"))
        projects_data = data.get("projects", [])
        registered = []
        for p_data in projects_data:
            project = _dict_to_project(p_data)
            ProjectRegistry.register(project)
            registered.append(p_data["project_id"])
        return {
            "loaded": True,
            "project_count": len(registered),
            "projects": registered,
            "source": str(_REGISTRY_FILE),
            "schema_version": data.get("schema_version", "unknown"),
            "persisted_at": data.get("persisted_at"),
            "error": None,
        }
    except Exception as exc:
        logger.warning("ProjectRegistry load failed (non-fatal): %s", exc)
        return {
            "loaded": False,
            "project_count": 0,
            "projects": [],
            "source": str(_REGISTRY_FILE),
            "error": str(exc),
        }


def ensure_openjarvis_project_registered() -> bool:
    """Ensure the OpenJarvis project is registered (survives restart).

    Returns True if it was already registered or successfully registered now.
    """
    try:
        from openjarvis.governance.constitution import ProjectRegistry, ProjectProfile
        if ProjectRegistry.get("openjarvis") is not None:
            return True
        openjarvis = ProjectProfile(
            project_id="openjarvis",
            display_name="OpenJarvis",
            priority=2,
            active=True,
            notes="Jarvis self-improvement project. Priority 2 after OMNIX.",
        )
        ProjectRegistry.register(openjarvis)
        return True
    except Exception as exc:
        logger.warning("OpenJarvis project registration failed: %s", exc)
        return False


def get_registry_persistence_status() -> Dict[str, Any]:
    """Return current registry persistence status for doctor checks."""
    from openjarvis.governance.constitution import ProjectRegistry
    projects = ProjectRegistry.list_projects()
    return {
        "file_path": str(_REGISTRY_FILE),
        "file_exists": _REGISTRY_FILE.exists(),
        "backup_exists": _BACKUP_FILE.exists(),
        "in_process_project_count": len(projects),
        "in_process_projects": [p.project_id for p in projects],
        "openjarvis_registered": any(p.project_id == "openjarvis" for p in projects),
        "omnix_registered": any(p.project_id == "omnix" for p in projects),
    }


# ---------------------------------------------------------------------------
# Initialization helper — call at startup
# ---------------------------------------------------------------------------

def initialize_persistence() -> Dict[str, Any]:
    """Initialize runtime persistence at startup.

    Call once at application startup to:
      1. Load registry from disk
      2. Ensure OpenJarvis project is registered
      3. Re-persist (to capture any newly registered projects)

    Returns status dict for logging/observability.
    """
    results: Dict[str, Any] = {}
    results["registry_load"] = load_registry()
    results["openjarvis_ensured"] = ensure_openjarvis_project_registered()
    results["registry_persisted"] = persist_registry()
    results["status"] = "ok" if results["registry_load"]["loaded"] or results["registry_persisted"] else "warn"
    return results


__all__ = [
    "persist_registry",
    "load_registry",
    "ensure_openjarvis_project_registered",
    "get_registry_persistence_status",
    "initialize_persistence",
]
