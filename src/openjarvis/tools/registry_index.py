"""Unified, read-only view over OpenJarvis's tool registries.

The system intentionally runs two tool registries at different layers:

- **Agent registry** (:class:`openjarvis.core.registry.ToolRegistry`) — the
  classic LLM-facing tools the agent can call (``current_time``, ``calculator``,
  ``web_search``, ``file_read``, ...). Snake_case single-token names.
- **Catalog registry** (:class:`openjarvis.tools.jarvis_registry.ToolRegistry`)
  — the server-side capability catalog (``web.search``, ``mission.*``,
  ``openclaw.*``, ...). Dotted-namespace ids, with availability/RBAC metadata.

They serve different consumers and use different naming conventions, so this
module does **not** merge them (that would change behavior). Instead it provides
a single place to *see* everything and to detect drift — i.e. a tool name that
ends up registered in both layers, which would be a maintenance hazard.

Everything here is read-only and side-effect-free (beyond importing the tool
packages so registration has fired).
"""

from __future__ import annotations

from typing import Dict, List, Set


def agent_tool_names() -> Set[str]:
    """Names registered in the LLM-facing agent registry (System A)."""
    import openjarvis.tools  # noqa: F401 — trigger @ToolRegistry.register
    from openjarvis.core.registry import ToolRegistry as _CoreReg

    return set(_CoreReg.keys())


def catalog_tool_ids() -> Set[str]:
    """Tool ids registered in the server-side capability catalog (System B).

    Returns an empty set if the catalog has not been initialized in this
    process (the catalog is populated lazily by ``initialize_catalog()``).
    """
    try:
        from openjarvis.tools.jarvis_registry import ToolRegistry as _JReg

        return {
            getattr(spec, "tool_id", "") or getattr(spec, "name", "")
            for spec in _JReg.list_all()
        } - {""}
    except Exception:
        return set()


def detect_drift() -> List[str]:
    """Return tool names present in BOTH registries (potential drift).

    By design the two layers use disjoint naming conventions, so this should be
    empty. A non-empty result flags a name that has leaked across layers and
    should be reconciled.
    """
    return sorted(agent_tool_names() & catalog_tool_ids())


def unified_index() -> Dict[str, object]:
    """A single read-only snapshot across all tool registries."""
    agent = agent_tool_names()
    catalog = catalog_tool_ids()
    collisions = sorted(agent & catalog)
    return {
        "agent_tools": sorted(agent),
        "catalog_tools": sorted(catalog),
        "agent_count": len(agent),
        "catalog_count": len(catalog),
        "total_unique": len(agent | catalog),
        "collisions": collisions,
        "has_drift": bool(collisions),
    }


__all__ = [
    "agent_tool_names",
    "catalog_tool_ids",
    "detect_drift",
    "unified_index",
]
