"""Tool Execution Gateway — single choke-point for all tool execution.

All tool execution goes through here. The gateway:
  - Validates the tool exists and is available
  - Applies governance hard gates and approval checks
  - Logs every attempt (success/blocked/not_configured/failed)
  - Returns structured ToolExecutionResult — never raises silently
  - Does not leak secrets
  - Supports project_id/context
  - Emits mission/tool events when mission/task context exists

No agent may bypass this gateway.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from openjarvis.governance.policies import gate_check, audit_log
from openjarvis.tools.execution_log import (
    ExecutionOutcome,
    ToolExecutionLog,
    ToolExecutionResult,
)
from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus

logger = logging.getLogger(__name__)

_DEFAULT_LOG_DB = Path.home() / ".jarvis" / "tool_executions.db"


class ToolExecutionGateway:
    """Single gateway for all tool execution.

    Usage
    -----
    gateway = ToolExecutionGateway()
    result = gateway.execute("mission.list", inputs={}, project_id="default")

    The gateway never raises.  Always returns a ToolExecutionResult.
    """

    def __init__(
        self,
        log_db_path: Optional[Path] = None,
    ) -> None:
        self._log = ToolExecutionLog(db_path=log_db_path or _DEFAULT_LOG_DB)

    def execute(
        self,
        tool_id: str,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        project_id: str = "",
        mission_id: Optional[str] = None,
        task_id: Optional[str] = None,
        agent_id: str = "",
    ) -> ToolExecutionResult:
        """Execute a tool through the governance gateway.

        Returns ToolExecutionResult.  Never raises.
        """
        inputs = inputs or {}
        start_ms = time.monotonic()

        # 1. Lookup tool in registry
        spec = ToolRegistry.get(tool_id)
        if spec is None:
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.FAILED,
                ok=False,
                error=f"Tool '{tool_id}' not found in ToolRegistry.",
                error_type="tool_not_found",
                governance_verdict="HOLD",
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            return result

        # 2. Check enabled
        if not spec.enabled:
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.BLOCKED,
                ok=False,
                error=f"Tool '{tool_id}' is disabled.",
                error_type="tool_disabled",
                governance_verdict="HOLD",
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            return result

        # 3. Check configured
        if not spec.configured:
            blocker = spec.blocker or f"Tool '{tool_id}' is not configured."
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.NOT_CONFIGURED,
                ok=False,
                error=blocker,
                error_type="not_configured",
                governance_verdict="HOLD",
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            return result

        # 4. Check implementation_status
        if spec.implementation_status != ToolStatus.AVAILABLE:
            blocker = spec.blocker or f"Tool '{tool_id}' status={spec.implementation_status}."
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.BLOCKED,
                ok=False,
                error=blocker,
                error_type=f"tool_{spec.implementation_status}",
                governance_verdict="HOLD",
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            return result

        # 5. Governance gate check — hard gates and approval requirements
        gov = gate_check(
            action_type=tool_id,
            risk_level=spec.risk_level,
            agent_id=agent_id or spec.owning_agent_id,
        )
        if not gov["allowed"]:
            outcome = (
                ExecutionOutcome.HARD_GATE
                if gov.get("verdict") == "UNSAFE"
                else ExecutionOutcome.BLOCKED
            )
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=outcome,
                ok=False,
                error=gov["reason"],
                error_type="governance_blocked",
                governance_verdict=gov.get("verdict", "HOLD"),
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            logger.warning(
                "Tool '%s' blocked by governance: %s", tool_id, gov["reason"]
            )
            return result

        # 6. Get executor
        executor = ToolRegistry.get_executor(tool_id)
        if executor is None:
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.NOT_CONFIGURED,
                ok=False,
                error=f"Tool '{tool_id}' has no executor registered.",
                error_type="no_executor",
                governance_verdict="HOLD",
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            return result

        # 7. Execute — catch all errors
        try:
            context: Dict[str, Any] = {
                "project_id": project_id,
                "mission_id": mission_id,
                "task_id": task_id,
                "agent_id": agent_id,
            }
            output = executor(inputs, context)
            execution_ms = (time.monotonic() - start_ms) * 1000
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.SUCCESS,
                ok=True,
                output=output,
                governance_verdict=gov.get("verdict", "ACCEPT"),
                execution_ms=execution_ms,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            logger.info(
                "Tool '%s' executed successfully in %.1fms", tool_id, execution_ms
            )

            # Emit mission event if mission context exists
            if mission_id:
                self._emit_tool_event(tool_id, mission_id, task_id, outcome="success")

            return result

        except Exception as exc:
            execution_ms = (time.monotonic() - start_ms) * 1000
            result = ToolExecutionResult(
                tool_id=tool_id,
                outcome=ExecutionOutcome.FAILED,
                ok=False,
                output=None,
                error=str(exc),
                error_type="executor_error",
                governance_verdict="HOLD",
                execution_ms=execution_ms,
                project_id=project_id,
                mission_id=mission_id,
                task_id=task_id,
            )
            self._log.save(result, inputs)
            logger.exception("Tool '%s' executor raised: %s", tool_id, exc)
            return result

    def _emit_tool_event(
        self,
        tool_id: str,
        mission_id: str,
        task_id: Optional[str],
        outcome: str,
    ) -> None:
        """Emit a mission event when tool runs in mission context. Best-effort."""
        try:
            from openjarvis.core.events import EventType, get_event_bus
            bus = get_event_bus()
            bus.publish(
                EventType.TASK_UPDATED,
                data={
                    "tool_id": tool_id,
                    "mission_id": mission_id,
                    "task_id": task_id,
                    "tool_outcome": outcome,
                },
            )
        except Exception as exc:
            logger.debug("Tool event emit skipped: %s", exc)

    def get_log(self) -> ToolExecutionLog:
        return self._log


# ---------------------------------------------------------------------------
# Module-level singleton gateway
# ---------------------------------------------------------------------------

_gateway: Optional[ToolExecutionGateway] = None


def get_gateway() -> ToolExecutionGateway:
    """Return the module-level singleton ToolExecutionGateway."""
    global _gateway
    if _gateway is None:
        _gateway = ToolExecutionGateway()
    return _gateway


__all__ = [
    "ToolExecutionGateway",
    "get_gateway",
]
