"""Jarvis Coding Workbench — US14A Cursor/Windsurf replacement backend.

Provides:
  - CodingManager: orchestrates coding tasks, routes workers, owns commit/push
  - JobQueue: SQLite-backed background job queue
  - CostLedger: cost tracking per task and session
  - CheckpointStore: task memory and accepted checkpoint persistence
"""

from openjarvis.workbench.job_queue import JobQueue, Job, JobStatus
from openjarvis.workbench.cost_ledger import CostLedger, CostEntry
from openjarvis.workbench.checkpoint import CheckpointStore, Checkpoint
from openjarvis.workbench.coding_manager import CodingManager, TaskPlan, Subtask
from openjarvis.workbench.model_router import (
    ModelRouter,
    ModelTier,
    BudgetConfig,
    ProviderConfig,
    RoutingDecision,
    EscalationDecision,
    EscalationAction,
    MockModelAdapter,
)

__all__ = [
    "JobQueue",
    "Job",
    "JobStatus",
    "CostLedger",
    "CostEntry",
    "CheckpointStore",
    "Checkpoint",
    "CodingManager",
    "TaskPlan",
    "Subtask",
    "ModelRouter",
    "ModelTier",
    "BudgetConfig",
    "ProviderConfig",
    "RoutingDecision",
    "EscalationDecision",
    "EscalationAction",
    "MockModelAdapter",
]
