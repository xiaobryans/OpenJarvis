"""Lean orchestration hierarchy (Option A, Approach A — fresh clean build).

A new, lean COS/GM -> Domain Managers -> Workers path that actually executes,
separate from the parked legacy cos_gm/worker_adapters stubs. Workers are real
tool calls; planning and synthesis use a capable cloud model. See
docs/ORCHESTRATOR.md for the target architecture.
"""

from openjarvis.orchestrator.lean.managers import MANAGERS, ManagerSpec, get_manager
from openjarvis.orchestrator.lean.orchestrator import LeanOrchestrator, OrchestratorResult

__all__ = [
    "MANAGERS",
    "ManagerSpec",
    "get_manager",
    "LeanOrchestrator",
    "OrchestratorResult",
]
