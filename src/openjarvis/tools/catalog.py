"""Jarvis Tool Catalog — registers the minimum safe real tool pack.

Tools registered here are REAL only if they have a working executor.
Slack/Telegram return not_configured when tokens are absent — that is the
honest implementation, not a fake one.

Real tool count comes from ToolRegistry.list_available() — never inflated.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Optional

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Executor helpers
# ---------------------------------------------------------------------------


def _make_executor(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap an executor so it always receives (inputs, context)."""
    def _wrapped(inputs: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Any:
        return fn(inputs, context or {})
    return _wrapped


# ---------------------------------------------------------------------------
# Tool executors — one per tool
# ---------------------------------------------------------------------------


def _exec_mission_list(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.store import MissionStore
    store = MissionStore()
    missions = store.list_missions()
    return {"missions": [m.to_dict() for m in missions], "count": len(missions)}


def _exec_mission_get(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.store import MissionStore
    mission_id = inputs.get("mission_id", "")
    if not mission_id:
        raise ValueError("mission_id is required")
    store = MissionStore()
    mission = store.get_mission(mission_id)
    if mission is None:
        return {"ok": False, "error": f"Mission '{mission_id}' not found"}
    tasks = store.list_tasks(mission_id)
    return {
        "mission": mission.to_dict(),
        "tasks": [t.to_dict() for t in tasks],
    }


def _exec_mission_run_pass(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.runner import MissionRunner
    mission_id = inputs.get("mission_id", "")
    max_steps = int(inputs.get("max_steps", 20))
    if not mission_id:
        raise ValueError("mission_id is required")
    store = MissionStore()
    runner = MissionRunner(store=store)
    result = runner.run_mission_pass(mission_id, max_steps=max_steps)
    return result.to_dict()


def _exec_task_get(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.store import MissionStore
    task_id = inputs.get("task_id", "")
    if not task_id:
        raise ValueError("task_id is required")
    store = MissionStore()
    task = store.get_task(task_id)
    if task is None:
        return {"ok": False, "error": f"Task '{task_id}' not found"}
    return {"task": task.to_dict()}


def _exec_task_update_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.store import MissionStore
    from openjarvis.mission.models import TaskStatus
    task_id = inputs.get("task_id", "")
    new_status = inputs.get("status", "")
    allowed_statuses = {"pending", "assigned", "cancelled"}
    if not task_id:
        raise ValueError("task_id is required")
    if new_status not in allowed_statuses:
        raise ValueError(
            f"status '{new_status}' not in safe set {sorted(allowed_statuses)}. "
            "Use mission_routes approve/deny endpoints for approval workflows."
        )
    store = MissionStore()
    task = store.get_task(task_id)
    if task is None:
        return {"ok": False, "error": f"Task '{task_id}' not found"}
    status_enum = TaskStatus(new_status)
    ok = store.update_task_status(task_id, status_enum)
    return {"ok": ok, "task_id": task_id, "new_status": new_status}


def _exec_event_list_recent(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.store import MissionStore
    limit = int(inputs.get("limit", 50))
    store = MissionStore()
    events = store.list_recent_events(limit=limit)
    return {"events": [e.to_dict() for e in events], "count": len(events)}


def _exec_agent_list(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.agent_registry import SpecialistRegistry
    agents = SpecialistRegistry.all()
    return {"agents": [a.to_dict() for a in agents], "count": len(agents)}


def _exec_governance_gate_check(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.governance.policies import gate_check
    action_type = inputs.get("action_type", "")
    risk_level = inputs.get("risk_level", "low")
    agent_id = inputs.get("agent_id", "")
    if not action_type:
        raise ValueError("action_type is required")
    return gate_check(action_type=action_type, risk_level=risk_level, agent_id=agent_id)


def _exec_memory_write(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.memory.store import JarvisMemory
    namespace = inputs.get("namespace", "global")
    content = inputs.get("content", "")
    tags = inputs.get("tags", [])
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    mission_id = inputs.get("mission_id") or ctx.get("mission_id")
    agent_id = inputs.get("agent_id") or ctx.get("agent_id")
    source = inputs.get("source", "tool")
    confidence = float(inputs.get("confidence", 1.0))
    if not content:
        raise ValueError("content is required")
    mem = JarvisMemory()
    entry = mem.write(
        namespace=namespace,
        content=content,
        source=source,
        tags=tags if isinstance(tags, list) else [],
        project_id=project_id,
        mission_id=mission_id,
        agent_id=agent_id,
        confidence=confidence,
    )
    return {"ok": True, "entry_id": entry.entry_id, "namespace": namespace}


def _exec_memory_search(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.memory.store import JarvisMemory
    query = inputs.get("query", "")
    namespace = inputs.get("namespace")
    project_id = inputs.get("project_id", "") or ctx.get("project_id", "")
    limit = int(inputs.get("limit", 20))
    if not query:
        raise ValueError("query is required")
    mem = JarvisMemory()
    results = mem.search(
        query=query,
        namespace=namespace,
        project_id=project_id or None,
        limit=limit,
    )
    return {"results": [r.to_dict() for r in results], "count": len(results)}


def _exec_notify_status(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.mission.notifier import SlackNotifier, TelegramNotifier
    slack_ok = SlackNotifier().is_configured()
    tg_ok = TelegramNotifier().is_configured()
    return {
        "slack": {
            "configured": slack_ok,
            "status": "ready" if slack_ok else "not_configured",
        },
        "telegram": {
            "configured": tg_ok,
            "status": "ready" if tg_ok else "not_configured",
        },
    }


def _exec_slack_notify_mission(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Returns not_configured without token. Never auto-sends. Explicit only."""
    from openjarvis.mission.notifier import SlackNotifier
    notifier = SlackNotifier()
    if not notifier.is_configured():
        return {
            "ok": False,
            "error_type": "not_configured",
            "error": "Slack not configured — set OPENCLAW_SLACK_BOT_TOKEN",
        }
    # Explicit-only: we return not_configured even when configured unless
    # caller provides explicit_approved=True.
    if not inputs.get("explicit_approved"):
        return {
            "ok": False,
            "error_type": "approval_required",
            "error": (
                "Slack notify requires explicit_approved=True in inputs. "
                "Real messages are only sent with explicit approval."
            ),
        }
    mission_id = inputs.get("mission_id", "")
    message = inputs.get("message", "")
    if not message and not mission_id:
        raise ValueError("Either message or mission_id is required")
    if not message and mission_id:
        from openjarvis.mission.store import MissionStore
        from openjarvis.mission.runner import _build_mission_notify_message
        store = MissionStore()
        mission = store.get_mission(mission_id)
        if mission is None:
            return {"ok": False, "error": f"Mission '{mission_id}' not found"}
        tasks = store.list_tasks(mission_id)
        message = _build_mission_notify_message(mission, tasks=tasks)
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(notifier.send(message))
    return result


def _exec_telegram_notify_mission(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Returns not_configured without token. Never auto-sends. Explicit only."""
    from openjarvis.mission.notifier import TelegramNotifier
    notifier = TelegramNotifier()
    if not notifier.is_configured():
        return {
            "ok": False,
            "error_type": "not_configured",
            "error": (
                "Telegram not configured — set JARVIS_TELEGRAM_BOT_TOKEN "
                "and JARVIS_TELEGRAM_CHAT_ID"
            ),
        }
    if not inputs.get("explicit_approved"):
        return {
            "ok": False,
            "error_type": "approval_required",
            "error": (
                "Telegram notify requires explicit_approved=True in inputs. "
                "Real messages are only sent with explicit approval."
            ),
        }
    mission_id = inputs.get("mission_id", "")
    message = inputs.get("message", "")
    if not message and not mission_id:
        raise ValueError("Either message or mission_id is required")
    if not message and mission_id:
        from openjarvis.mission.store import MissionStore
        from openjarvis.mission.runner import _build_mission_notify_message
        store = MissionStore()
        mission = store.get_mission(mission_id)
        if mission is None:
            return {"ok": False, "error": f"Mission '{mission_id}' not found"}
        tasks = store.list_tasks(mission_id)
        message = _build_mission_notify_message(mission, tasks=tasks)
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(notifier.send(message))
    return result


def _exec_project_list(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.governance.constitution import ProjectRegistry
    projects = ProjectRegistry.list_projects()
    return {"projects": [p.to_dict() for p in projects], "count": len(projects)}


def _exec_project_get(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    from openjarvis.governance.constitution import ProjectRegistry
    project_id = inputs.get("project_id", "")
    if not project_id:
        raise ValueError("project_id is required")
    project = ProjectRegistry.get(project_id)
    if project is None:
        return {"ok": False, "error": f"Project '{project_id}' not found"}
    return {"project": project.to_dict()}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_TOOL_DEFS = [
    # ---- Mission tools ----
    (
        ToolSpec(
            tool_id="mission.list",
            display_name="List Missions",
            description="List all missions in MissionStore.",
            category="mission",
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={
                "type": "object",
                "properties": {
                    "missions": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:missions"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mission_list",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mission_list,
    ),
    (
        ToolSpec(
            tool_id="mission.get",
            display_name="Get Mission",
            description="Get a mission by ID with its tasks.",
            category="mission",
            input_schema={
                "type": "object",
                "properties": {"mission_id": {"type": "string"}},
                "required": ["mission_id"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "mission": {"type": "object"},
                    "tasks": {"type": "array"},
                },
            },
            required_permissions=["read:missions"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mission_get",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mission_get,
    ),
    (
        ToolSpec(
            tool_id="mission.run_pass",
            display_name="Run Mission Pass",
            description="Execute one controlled pass of runnable tasks for a mission.",
            category="mission",
            input_schema={
                "type": "object",
                "properties": {
                    "mission_id": {"type": "string"},
                    "max_steps": {"type": "integer", "default": 20},
                },
                "required": ["mission_id"],
            },
            output_schema={"type": "object"},
            required_permissions=["execute:missions"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mission_run_pass",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mission_run_pass,
    ),
    # ---- Task tools ----
    (
        ToolSpec(
            tool_id="task.get",
            display_name="Get Task",
            description="Get a task by ID.",
            category="mission",
            input_schema={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            output_schema={
                "type": "object",
                "properties": {"task": {"type": "object"}},
            },
            required_permissions=["read:tasks"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_task_get",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_task_get,
    ),
    (
        ToolSpec(
            tool_id="task.update_status",
            display_name="Update Task Status",
            description=(
                "Update a task's status. Only safe statuses allowed: "
                "pending, assigned, cancelled. "
                "Use mission approval routes for approve/deny workflows."
            ),
            category="mission",
            input_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["pending", "assigned", "cancelled"]},
                },
                "required": ["task_id", "status"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "task_id": {"type": "string"},
                    "new_status": {"type": "string"},
                },
            },
            required_permissions=["write:tasks"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_task_update_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_task_update_status,
    ),
    # ---- Event tools ----
    (
        ToolSpec(
            tool_id="event.list_recent",
            display_name="List Recent Events",
            description="List the most recent mission events across all missions.",
            category="mission",
            input_schema={
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 50}},
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "events": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:events"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_event_list_recent",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_event_list_recent,
    ),
    # ---- Agent tools ----
    (
        ToolSpec(
            tool_id="agent.list",
            display_name="List Agents",
            description="List all registered specialist agents.",
            category="agent",
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={
                "type": "object",
                "properties": {
                    "agents": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:agents"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_agent_list",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_agent_list,
    ),
    # ---- Governance tools ----
    (
        ToolSpec(
            tool_id="governance.gate_check",
            display_name="Governance Gate Check",
            description=(
                "Run a governance gate check on a proposed action. "
                "Returns allowed/blocked/UNSAFE verdict."
            ),
            category="governance",
            input_schema={
                "type": "object",
                "properties": {
                    "action_type": {"type": "string"},
                    "risk_level": {"type": "string", "default": "low"},
                    "agent_id": {"type": "string", "default": ""},
                },
                "required": ["action_type"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "allowed": {"type": "boolean"},
                    "category": {"type": "string"},
                    "verdict": {"type": "string"},
                    "requires_approval": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
            },
            required_permissions=["read:governance"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_governance_gate_check",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_governance_gate_check,
    ),
    # ---- Memory tools ----
    (
        ToolSpec(
            tool_id="memory.write",
            display_name="Memory Write",
            description="Write an entry to project-scoped Jarvis memory.",
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "namespace": {"type": "string"},
                    "content": {"type": "string"},
                    "project_id": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "source": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["namespace", "content"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "entry_id": {"type": "string"},
                    "namespace": {"type": "string"},
                },
            },
            required_permissions=["write:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_write",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_write,
    ),
    (
        ToolSpec(
            tool_id="memory.search",
            display_name="Memory Search",
            description="Search project-scoped Jarvis memory by keyword/namespace.",
            category="memory",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "namespace": {"type": "string"},
                    "project_id": {"type": "string"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
            output_schema={
                "type": "object",
                "properties": {
                    "results": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:memory"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_memory_search",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_memory_search,
    ),
    # ---- Notify tools ----
    (
        ToolSpec(
            tool_id="notify.status",
            display_name="Notify Status",
            description=(
                "Check the configuration status of all notification channels "
                "(Slack, Telegram). Does not send any messages."
            ),
            category="notify",
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={
                "type": "object",
                "properties": {
                    "slack": {"type": "object"},
                    "telegram": {"type": "object"},
                },
            },
            required_permissions=["read:notify"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_notify_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_notify_status,
    ),
    (
        ToolSpec(
            tool_id="slack.notify_mission",
            display_name="Slack Notify Mission",
            description=(
                "Send a mission summary to Slack. Requires explicit_approved=True. "
                "Returns not_configured without token. Never auto-sends."
            ),
            category="notify",
            input_schema={
                "type": "object",
                "properties": {
                    "mission_id": {"type": "string"},
                    "message": {"type": "string"},
                    "explicit_approved": {"type": "boolean"},
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}, "error": {"type": "string"}},
            },
            required_permissions=["notify:slack"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=bool(
                os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "")
                and not os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "").startswith("<")
            ),
            approval_required=True,
            owning_agent_id="manager",
            executor_ref="_exec_slack_notify_mission",
            implementation_status=(
                ToolStatus.AVAILABLE
                if (
                    os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "")
                    and not os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "").startswith("<")
                )
                else ToolStatus.NOT_CONFIGURED
            ),
            blocker=(
                ""
                if (
                    os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "")
                    and not os.environ.get("OPENCLAW_SLACK_BOT_TOKEN", "").startswith("<")
                )
                else "OPENCLAW_SLACK_BOT_TOKEN not set or placeholder"
            ),
        ),
        _exec_slack_notify_mission,
    ),
    (
        ToolSpec(
            tool_id="telegram.notify_mission",
            display_name="Telegram Notify Mission",
            description=(
                "Send a mission summary to Telegram. Requires explicit_approved=True. "
                "Returns not_configured without token. Never auto-sends."
            ),
            category="notify",
            input_schema={
                "type": "object",
                "properties": {
                    "mission_id": {"type": "string"},
                    "message": {"type": "string"},
                    "explicit_approved": {"type": "boolean"},
                },
                "required": [],
            },
            output_schema={
                "type": "object",
                "properties": {"ok": {"type": "boolean"}, "error": {"type": "string"}},
            },
            required_permissions=["notify:telegram"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=bool(
                os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "")
                and os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
                and not os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "").startswith("<")
            ),
            approval_required=True,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_notify_mission",
            implementation_status=(
                ToolStatus.AVAILABLE
                if (
                    os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "")
                    and os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
                    and not os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "").startswith("<")
                )
                else ToolStatus.NOT_CONFIGURED
            ),
            blocker=(
                ""
                if (
                    os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "")
                    and os.environ.get("JARVIS_TELEGRAM_CHAT_ID", "")
                    and not os.environ.get("JARVIS_TELEGRAM_BOT_TOKEN", "").startswith("<")
                )
                else "JARVIS_TELEGRAM_BOT_TOKEN or JARVIS_TELEGRAM_CHAT_ID not set"
            ),
        ),
        _exec_telegram_notify_mission,
    ),
    # ---- Project tools ----
    (
        ToolSpec(
            tool_id="project.list",
            display_name="List Projects",
            description="List all projects registered in the Jarvis ProjectRegistry.",
            category="project",
            input_schema={"type": "object", "properties": {}, "required": []},
            output_schema={
                "type": "object",
                "properties": {
                    "projects": {"type": "array"},
                    "count": {"type": "integer"},
                },
            },
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_list",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_list,
    ),
    (
        ToolSpec(
            tool_id="project.get",
            display_name="Get Project",
            description="Get a project profile by project_id.",
            category="project",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
                "required": ["project_id"],
            },
            output_schema={
                "type": "object",
                "properties": {"project": {"type": "object"}},
            },
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_get",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_get,
    ),
]


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def _is_already_initialized() -> bool:
    return ToolRegistry.get("mission.list") is not None


def initialize_catalog() -> None:
    """Register all catalog tools into ToolRegistry.

    Safe to call multiple times — skips if already initialized.
    """
    if _is_already_initialized():
        return
    for spec, executor in _TOOL_DEFS:
        ToolRegistry.register(spec, executor=executor)
    # Sprint 5 workflow pack — registered after Sprint 4 base tools
    from openjarvis.tools.workflow_catalog import initialize_workflow_catalog
    initialize_workflow_catalog()
    # Sprint 6 autonomy/watchdog/alert/mobile/voice pack
    from openjarvis.tools.autonomy_catalog import initialize_autonomy_catalog
    initialize_autonomy_catalog()
    stats = ToolRegistry.stats()
    logger.info(
        "Tool catalog initialized: %d total, %d available, %d unavailable",
        stats["total_registered"],
        stats["available"],
        stats["unavailable"],
    )


def get_catalog_stats() -> Dict[str, Any]:
    initialize_catalog()
    return ToolRegistry.stats()


__all__ = [
    "initialize_catalog",
    "get_catalog_stats",
]
