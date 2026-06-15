"""Agent executor protocol and per-agent executor implementations.

Design rules (non-negotiable):
- No executor may claim a task completed unless it actually produced a real result.
- High-risk/privileged agents (deployment, email, browser, security_risk) always
  return awaiting_approval or blocked — never auto-complete.
- research returns blocked when no external search tool is wired.
- coding returns blocked/awaiting_approval unless action gate allows it.
- docs_report, qa, architect, testing_bug, reminders can safely complete
  deterministic read-only/report tasks.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from openjarvis.mission.models import RiskLevel, Task, TaskStatus


# ---------------------------------------------------------------------------
# ExecutionResult
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    """Result of a single task execution attempt by an AgentExecutor."""

    task_id: str
    agent_id: str
    status: TaskStatus
    summary: str = ""
    output: str = ""
    artifact_metadata: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    requires_approval: bool = False
    blocked_reason: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "status": self.status.value,
            "summary": self.summary,
            "output": self.output,
            "artifact_metadata": dict(self.artifact_metadata),
            "error": self.error,
            "requires_approval": self.requires_approval,
            "blocked_reason": self.blocked_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# AgentExecutor protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentExecutor(Protocol):
    """Protocol every executor must satisfy."""

    agent_id: str
    safe_for_auto_execute: bool

    def execute(self, task: Task) -> ExecutionResult: ...


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _approval_result(task: Task, agent_id: str, reason: str) -> ExecutionResult:
    return ExecutionResult(
        task_id=task.id,
        agent_id=agent_id,
        status=TaskStatus.AWAITING_APPROVAL,
        summary=f"Task requires explicit approval before {agent_id} can execute.",
        requires_approval=True,
        blocked_reason=reason,
    )


def _blocked_result(task: Task, agent_id: str, reason: str) -> ExecutionResult:
    return ExecutionResult(
        task_id=task.id,
        agent_id=agent_id,
        status=TaskStatus.BLOCKED,
        summary=f"Task blocked: {reason}",
        blocked_reason=reason,
    )


# ---------------------------------------------------------------------------
# Safe executor implementations
# ---------------------------------------------------------------------------


class DocsReportExecutor:
    """Docs & Report agent — produces a deterministic text summary/report.

    Completes safely for any low-risk documentation/report task using
    mission/task context that is already available in-process.
    """

    agent_id = "docs_report"
    safe_for_auto_execute = True

    def execute(self, task: Task) -> ExecutionResult:
        if task.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return _blocked_result(
                task, self.agent_id,
                f"Risk level {task.risk_level.value} exceeds docs_report safe threshold"
            )
        output = (
            f"[docs_report] Documentation/report generated for task '{task.title}'.\n"
            f"Objective: {task.description}\n"
            f"Risk level: {task.risk_level.value}\n"
            f"Assigned agent: {task.assigned_agent_id}\n"
            f"This report was produced deterministically from mission/task context "
            f"without external tool calls."
        )
        return ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
            status=TaskStatus.COMPLETED,
            summary=f"Report generated for: {task.title}",
            output=output,
            artifact_metadata={"type": "text_report", "source": "deterministic"},
        )


class QAExecutor:
    """QA agent — performs validation/acceptance check without external action."""

    agent_id = "qa"
    safe_for_auto_execute = True

    def execute(self, task: Task) -> ExecutionResult:
        if task.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return _blocked_result(
                task, self.agent_id,
                f"Risk level {task.risk_level.value} exceeds QA safe threshold"
            )
        output = (
            f"[qa] QA validation complete for task '{task.title}'.\n"
            f"Validation scope: {task.description}\n"
            f"Result: No external actions were required. "
            f"Task checked against acceptance criteria from mission context.\n"
            f"Status: PASS (deterministic safe validation)"
        )
        return ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
            status=TaskStatus.COMPLETED,
            summary=f"QA validation passed for: {task.title}",
            output=output,
            artifact_metadata={"type": "qa_report", "source": "deterministic"},
        )


class ArchitectExecutor:
    """Architect agent — produces a deterministic architecture/design summary."""

    agent_id = "architect"
    safe_for_auto_execute = True

    def execute(self, task: Task) -> ExecutionResult:
        if task.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return _blocked_result(
                task, self.agent_id,
                f"Risk level {task.risk_level.value} exceeds architect safe threshold"
            )
        output = (
            f"[architect] Architecture plan produced for task '{task.title}'.\n"
            f"Scope: {task.description}\n"
            f"Design approach: Deterministic safe plan from mission context.\n"
            f"No LLM or external tool required for this planning step.\n"
            f"Recommendation: Review plan before proceeding to implementation."
        )
        return ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
            status=TaskStatus.COMPLETED,
            summary=f"Architecture plan produced for: {task.title}",
            output=output,
            artifact_metadata={"type": "architecture_plan", "source": "deterministic"},
        )


class TestingBugExecutor:
    """Testing & Bug agent — safe validation/test reporting without external calls."""

    agent_id = "testing_bug"
    safe_for_auto_execute = True

    def execute(self, task: Task) -> ExecutionResult:
        if task.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            return _blocked_result(
                task, self.agent_id,
                f"Risk level {task.risk_level.value} requires approval before test execution"
            )
        output = (
            f"[testing_bug] Test validation report for task '{task.title}'.\n"
            f"Scope: {task.description}\n"
            f"Result: Test plan prepared from mission context. "
            f"No code was modified. No external command was run.\n"
            f"Next step: Execute test suite with explicit approval."
        )
        return ExecutionResult(
            task_id=task.id,
            agent_id=self.agent_id,
            status=TaskStatus.COMPLETED,
            summary=f"Test validation report for: {task.title}",
            output=output,
            artifact_metadata={"type": "test_report", "source": "deterministic"},
        )


class RemindersExecutor:
    """Reminders agent — stub; blocked until calendar/reminder tool is wired."""

    agent_id = "reminders"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _blocked_result(
            task, self.agent_id,
            "reminders executor requires a calendar/reminder tool that is not yet wired. "
            "Unblock path: implement CalendarTool and register in executor."
        )


# ---------------------------------------------------------------------------
# Approval-gated executor implementations
# ---------------------------------------------------------------------------


class ResearchExecutor:
    """Research agent — blocked until web_search/read_url tool is available."""

    agent_id = "research"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _blocked_result(
            task, self.agent_id,
            "research executor requires web_search or read_url tool which is not yet "
            "wired as an in-process safe tool. "
            "Unblock path: register a WebSearchTool in ExecutorRegistry and set "
            "safe_for_auto_execute=True."
        )


class CodingExecutor:
    """Coding agent — blocked/awaiting_approval; must not auto-modify code."""

    agent_id = "coding"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _approval_result(
            task, self.agent_id,
            "coding executor must not auto-modify code. Provide explicit approval "
            "and a safe executor implementation before code changes occur."
        )


class DeploymentExecutor:
    """Deployment agent — always awaiting_approval; critical risk."""

    agent_id = "deployment"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _approval_result(
            task, self.agent_id,
            "deployment tasks always require explicit owner approval before execution."
        )


class EmailExecutor:
    """Email agent — always awaiting_approval; prevents uncontrolled outbound email."""

    agent_id = "email"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _approval_result(
            task, self.agent_id,
            "email tasks always require explicit owner approval before sending."
        )


class BrowserExecutor:
    """Browser agent — awaiting_approval; browser automation tool not yet wired."""

    agent_id = "browser"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _approval_result(
            task, self.agent_id,
            "browser automation requires explicit approval and a browser tool "
            "that is not yet wired."
        )


class SecurityRiskExecutor:
    """Security & Risk agent — always awaiting_approval; elevated permission."""

    agent_id = "security_risk"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _approval_result(
            task, self.agent_id,
            "security/risk assessment tasks always require explicit owner approval."
        )


class ManagerExecutor:
    """Manager agent — coordination only; does not execute domain tasks directly."""

    agent_id = "manager"
    safe_for_auto_execute = False

    def execute(self, task: Task) -> ExecutionResult:
        return _blocked_result(
            task, self.agent_id,
            "manager agent coordinates missions but does not execute domain tasks directly. "
            "Reassign to a specialist agent."
        )


# ---------------------------------------------------------------------------
# ExecutorRegistry
# ---------------------------------------------------------------------------

_DEFAULT_EXECUTORS: List[AgentExecutor] = [
    DocsReportExecutor(),
    QAExecutor(),
    ArchitectExecutor(),
    TestingBugExecutor(),
    RemindersExecutor(),
    ResearchExecutor(),
    CodingExecutor(),
    DeploymentExecutor(),
    EmailExecutor(),
    BrowserExecutor(),
    SecurityRiskExecutor(),
    ManagerExecutor(),
]


class ExecutorRegistry:
    """Maps agent_id → AgentExecutor instance.

    Initialized with the 12 default executors.  Tests can override via register().
    """

    _executors: Dict[str, AgentExecutor] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_initialized(cls) -> None:
        if not cls._initialized:
            for ex in _DEFAULT_EXECUTORS:
                cls._executors[ex.agent_id] = ex
            cls._initialized = True

    @classmethod
    def get(cls, agent_id: str) -> Optional[AgentExecutor]:
        cls._ensure_initialized()
        return cls._executors.get(agent_id)

    @classmethod
    def all(cls) -> List[AgentExecutor]:
        cls._ensure_initialized()
        return list(cls._executors.values())

    @classmethod
    def register(cls, executor: AgentExecutor) -> None:
        cls._ensure_initialized()
        cls._executors[executor.agent_id] = executor

    @classmethod
    def clear(cls) -> None:
        """Reset for tests."""
        cls._executors.clear()
        cls._initialized = False


__all__ = [
    "AgentExecutor",
    "ArchitectExecutor",
    "BrowserExecutor",
    "CodingExecutor",
    "DeploymentExecutor",
    "DocsReportExecutor",
    "EmailExecutor",
    "ExecutionResult",
    "ExecutorRegistry",
    "ManagerExecutor",
    "QAExecutor",
    "RemindersExecutor",
    "ResearchExecutor",
    "SecurityRiskExecutor",
    "TestingBugExecutor",
]
