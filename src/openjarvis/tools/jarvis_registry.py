"""Jarvis Tool Registry — ToolSpec model + ToolRegistry.

A tool is REAL only if it has:
  - tool_id, name/description
  - input/output schema
  - executor or explicit not_configured/blocked implementation
  - risk_level, required_permissions, governance/action-gate policy
  - implementation_status in: available | degraded | blocked | not_configured | planned

Tools with status != 'available' are registered but not counted as implemented.
No fake count inflation. No silent skips.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Implementation Status
# ---------------------------------------------------------------------------


class ToolStatus:
    AVAILABLE = "available"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_CONFIGURED = "not_configured"
    PLANNED = "planned"


# ---------------------------------------------------------------------------
# ToolSpec — canonical contract
# ---------------------------------------------------------------------------


@dataclass
class ToolSpec:
    """Contract definition for a single Jarvis tool.

    Fields
    ------
    tool_id             Unique identifier (e.g. 'mission.list')
    display_name        Human-readable name
    description         What the tool does
    category            Grouping (e.g. 'mission', 'memory', 'notify', 'project')
    input_schema        JSON-Schema dict describing required/optional inputs
    output_schema       JSON-Schema dict describing the output shape
    required_permissions  Permissions/capabilities needed (e.g. ['read:missions'])
    risk_level          'low' | 'medium' | 'high' | 'critical'
    project_scope       List of project_ids this applies to; [] = all projects
    enabled             Admin-level on/off switch
    configured          Whether the required env/credentials are present
    approval_required   Whether owner approval is needed before execution
    owning_agent_id     Which specialist agent owns this tool
    executor_ref        Class or function name of the executor (informational)
    implementation_status  ToolStatus constant
    blocker             Human-readable reason if not available
    created_at          Unix timestamp
    updated_at          Unix timestamp
    """

    tool_id: str
    display_name: str
    description: str
    category: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    required_permissions: List[str]
    risk_level: str
    project_scope: List[str]
    enabled: bool
    configured: bool
    approval_required: bool
    owning_agent_id: str
    executor_ref: str
    implementation_status: str = ToolStatus.AVAILABLE
    blocker: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def is_available(self) -> bool:
        return (
            self.enabled
            and self.configured
            and self.implementation_status == ToolStatus.AVAILABLE
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "required_permissions": list(self.required_permissions),
            "risk_level": self.risk_level,
            "project_scope": list(self.project_scope),
            "enabled": self.enabled,
            "configured": self.configured,
            "approval_required": self.approval_required,
            "owning_agent_id": self.owning_agent_id,
            "executor_ref": self.executor_ref,
            "implementation_status": self.implementation_status,
            "blocker": self.blocker,
            "is_available": self.is_available(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# ToolRegistry — singleton class-level store
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Registry of all Jarvis tools.

    REAL tools have implementation_status='available'.
    PLANNED/DEGRADED/BLOCKED/NOT_CONFIGURED tools are registered but not available.

    No tool is counted as implemented unless it is truly available.
    """

    _tools: Dict[str, ToolSpec] = {}
    _executors: Dict[str, Callable[..., Any]] = {}
    _initialized: bool = False

    @classmethod
    def register(
        cls,
        spec: ToolSpec,
        executor: Optional[Callable[..., Any]] = None,
    ) -> None:
        """Register a tool.

        Raises ValueError if status=available but no executor is provided.
        Non-available tools (planned/blocked/not_configured/degraded) may omit executor.
        """
        if executor is None and spec.implementation_status == ToolStatus.AVAILABLE:
            raise ValueError(
                f"Tool '{spec.tool_id}' claims status=available but has no executor. "
                "Mark it not_configured/planned or provide an executor."
            )
        cls._tools[spec.tool_id] = spec
        if executor is not None:
            cls._executors[spec.tool_id] = executor

    @classmethod
    def get(cls, tool_id: str) -> Optional[ToolSpec]:
        return cls._tools.get(tool_id)

    @classmethod
    def get_executor(cls, tool_id: str) -> Optional[Callable[..., Any]]:
        return cls._executors.get(tool_id)

    @classmethod
    def list_all(cls) -> List[ToolSpec]:
        """All registered tools sorted by tool_id."""
        return sorted(cls._tools.values(), key=lambda t: t.tool_id)

    @classmethod
    def list_available(cls) -> List[ToolSpec]:
        """Only tools with implementation_status='available' and enabled+configured."""
        return [t for t in cls.list_all() if t.is_available()]

    @classmethod
    def list_unavailable(cls) -> List[ToolSpec]:
        """Tools that are registered but NOT available (planned/degraded/blocked/not_configured)."""
        return [t for t in cls.list_all() if not t.is_available()]

    @classmethod
    def stats(cls) -> Dict[str, Any]:
        all_tools = cls.list_all()
        available = cls.list_available()
        unavailable = cls.list_unavailable()
        return {
            "total_registered": len(all_tools),
            "available": len(available),
            "unavailable": len(unavailable),
            "by_status": {
                status: sum(1 for t in all_tools if t.implementation_status == status)
                for status in [
                    ToolStatus.AVAILABLE,
                    ToolStatus.DEGRADED,
                    ToolStatus.BLOCKED,
                    ToolStatus.NOT_CONFIGURED,
                    ToolStatus.PLANNED,
                ]
            },
        }

    @classmethod
    def clear(cls) -> None:
        """Reset — for tests only."""
        cls._tools.clear()
        cls._executors.clear()
        cls._initialized = False


__all__ = [
    "ToolRegistry",
    "ToolSpec",
    "ToolStatus",
]
