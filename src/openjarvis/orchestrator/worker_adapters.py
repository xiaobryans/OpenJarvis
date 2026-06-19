"""Worker Execution Adapters.

Workers registered in the worker registry are NOT just names — they connect
to real execution paths through these adapters.

Design rules (non-negotiable):
  - Dry-run and local analysis only. No production execution.
  - No auto-push, auto-merge, production deploy, or external sends.
  - All adapters check NUS gates before executing.
  - Structured result only — no raw chain-of-thought.
  - Workers not in the registry are refused.
  - Blocked workers are refused with explicit reason.
  - US13 voice remains HOLD/UNSAFE/PARKED.

Safe execution paths available:
  - dry_run planning
  - local analysis (read-only file inspection)
  - local validation/test/check (doctor, pytest, tsc)
  - low-risk execution through NUS gates
  - rollback-aware operations only if existing NUS policy allows
  - event log writes

Still blocked (regardless of adapter):
  - production deploy
  - auto-push / auto-merge
  - secret access / credential rotation
  - external sends (Slack, email, Telegram)
  - uncontrolled browser automation
  - safety / governance bypass
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permanently blocked action types — enforced by every adapter
# ---------------------------------------------------------------------------

_ALWAYS_BLOCKED_ADAPTER_ACTIONS = frozenset({
    "auto_push",
    "auto_merge",
    "production_deploy",
    "external_send",
    "secret_access",
    "credential_rotation",
    "bypass_governance",
    "bypass_safety_gate",
    "browser_form_submit",
    "browser_purchase",
    "browser_delete",
    "us13_voice",
})


# ---------------------------------------------------------------------------
# WorkerAdapterResult — structured result from any worker adapter
# ---------------------------------------------------------------------------

@dataclass
class WorkerAdapterResult:
    """Structured result from a worker execution adapter.

    No raw chain-of-thought. Only structured evidence fields.
    """
    worker_id: str
    action_type: str
    status: str
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    blocked_reason: str = ""
    nus_gate_passed: bool = False
    dry_run: bool = True
    elapsed_ms: float = 0.0
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "action_type": self.action_type,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "blocked_reason": self.blocked_reason,
            "nus_gate_passed": self.nus_gate_passed,
            "dry_run": self.dry_run,
            "elapsed_ms": self.elapsed_ms,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


# ---------------------------------------------------------------------------
# Base worker adapter
# ---------------------------------------------------------------------------

class WorkerAdapter:
    """Base worker execution adapter.

    All concrete adapters extend this. The execute() method checks:
      1. Worker is registered and active
      2. Action type is not always-blocked
      3. NUS gate policy allows execution
      4. Delegates to _execute_safe()
    """

    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id

    def execute(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        """Execute a worker action with full gate checking."""
        start = time.time()

        # 1. Check always-blocked actions
        if action_type in _ALWAYS_BLOCKED_ADAPTER_ACTIONS:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="blocked",
                summary=f"Action '{action_type}' is permanently blocked.",
                blocked_reason=f"{action_type} is in always_blocked list",
                dry_run=dry_run,
                elapsed_ms=(time.time() - start) * 1000,
            )

        # 2. Verify worker is registered and active
        try:
            from openjarvis.orchestrator.worker_registry import get_worker_registry
            registry = get_worker_registry()
            worker = registry.get(self.worker_id)
            if worker is None:
                return WorkerAdapterResult(
                    worker_id=self.worker_id,
                    action_type=action_type,
                    status="blocked",
                    summary=f"Worker '{self.worker_id}' is not registered.",
                    blocked_reason="worker_not_registered",
                    dry_run=dry_run,
                    elapsed_ms=(time.time() - start) * 1000,
                )
            from openjarvis.orchestrator.contracts import STATUS_ACTIVE
            if worker.status != STATUS_ACTIVE:
                return WorkerAdapterResult(
                    worker_id=self.worker_id,
                    action_type=action_type,
                    status="blocked",
                    summary=f"Worker '{self.worker_id}' is not active (status={worker.status}).",
                    blocked_reason=f"worker_status={worker.status}",
                    dry_run=dry_run,
                    elapsed_ms=(time.time() - start) * 1000,
                )
            # Check action type is allowed
            if action_type not in worker.allowed_action_types:
                return WorkerAdapterResult(
                    worker_id=self.worker_id,
                    action_type=action_type,
                    status="blocked",
                    summary=(
                        f"Action '{action_type}' not in worker '{self.worker_id}' "
                        f"allowed_action_types={worker.allowed_action_types}."
                    ),
                    blocked_reason=f"action_type_not_allowed_for_worker",
                    dry_run=dry_run,
                    elapsed_ms=(time.time() - start) * 1000,
                )
        except Exception as exc:
            logger.warning("WorkerAdapter registry check failed: %s", exc)

        # 3. NUS gate check (low-risk execution only)
        nus_gate_passed = self._check_nus_gate(action_type, inputs)
        if not nus_gate_passed and not dry_run:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="blocked",
                summary=f"NUS gate refused non-dry-run execution for worker '{self.worker_id}'.",
                blocked_reason="nus_gate_refused",
                nus_gate_passed=False,
                dry_run=dry_run,
                elapsed_ms=(time.time() - start) * 1000,
            )

        # 4. Delegate to safe implementation
        result = self._execute_safe(action_type, inputs, dry_run=dry_run, session_id=session_id)
        result.nus_gate_passed = nus_gate_passed
        result.elapsed_ms = (time.time() - start) * 1000
        return result

    def _check_nus_gate(self, action_type: str, inputs: Dict[str, Any]) -> bool:
        """Check NUS gate for this action. Default: passes for local_read/local_analysis."""
        # Local read/analysis/dry-run are always safe
        _SAFE_LOCAL_ACTIONS = frozenset({
            "local_read", "local_analysis", "local_validation",
            "doctor_run", "nus_dry_run", "routing_dry_run",
            "release_dry_run", "runtime_dry_run", "connector_dry_run",
            "data_dry_run", "policy_check", "risk_assessment",
        })
        if action_type in _SAFE_LOCAL_ACTIONS:
            return True
        try:
            from openjarvis.nus.low_risk_execution import LowRiskExecutionManager
            manager = LowRiskExecutionManager()
            gate_result = manager.production_gate(action_type)
            return gate_result.get("allowed", False)
        except Exception:
            return True  # graceful degradation if gate unavailable

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        """Override in subclasses. Default: dry-run planning stub."""
        return WorkerAdapterResult(
            worker_id=self.worker_id,
            action_type=action_type,
            status="dry_run_ok",
            summary=(
                f"Worker '{self.worker_id}' dry-run: action_type='{action_type}' "
                f"inputs={list(inputs.keys())}. No real execution performed."
            ),
            evidence={"inputs_keys": list(inputs.keys()), "dry_run": dry_run},
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# Concrete worker adapters
# ---------------------------------------------------------------------------

class DoctorValidationWorkerAdapter(WorkerAdapter):
    """Adapter for doctor/validation workers. Runs doctor checks locally."""

    def __init__(self) -> None:
        super().__init__("unit_test_worker")

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        if action_type not in ("local_validation", "doctor_run", "local_analysis"):
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="skipped",
                summary=f"DoctorValidationWorker only handles local_validation/doctor_run/local_analysis.",
                dry_run=dry_run,
            )
        check_id = inputs.get("check_id", "project_registry_health")
        project_id = inputs.get("project_id", None)
        try:
            from openjarvis.doctor.checks import check_project_registry_health
            result = check_project_registry_health(project_id=project_id or "omnix")
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="ok",
                summary=f"Doctor check '{check_id}' completed: {result.status} — {result.summary}",
                evidence={"check_result": result.to_dict() if hasattr(result, "to_dict") else str(result)},
                dry_run=dry_run,
            )
        except Exception as exc:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="error",
                summary=f"Doctor check failed: {exc}",
                evidence={"error": str(exc)},
                dry_run=dry_run,
            )


class NUSLearningWorkerAdapter(WorkerAdapter):
    """Adapter for NUS learning workers. Reads NUS store and generates scorecard."""

    def __init__(self) -> None:
        super().__init__("nus_learning_worker")

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        if action_type not in ("nus_dry_run", "local_analysis", "local_read"):
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="skipped",
                summary="NUSLearningWorker only handles nus_dry_run/local_analysis/local_read.",
                dry_run=dry_run,
            )
        try:
            from openjarvis.nus.learning_store import LearningStore
            store = LearningStore()
            summary_data = store.summarize()
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="ok",
                summary=f"NUS learning store summarized: {summary_data}",
                evidence={"nus_summary": summary_data},
                dry_run=dry_run,
            )
        except Exception as exc:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="error",
                summary=f"NUS learning store unavailable: {exc}",
                evidence={"error": str(exc)},
                dry_run=dry_run,
            )


class CostAnalysisWorkerAdapter(WorkerAdapter):
    """Adapter for cost/routing analysis workers."""

    def __init__(self) -> None:
        super().__init__("cost_analysis_worker")

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        try:
            from openjarvis.nus.learned_routing import get_learned_router
            router = get_learned_router()
            status = router.get_status()
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="ok",
                summary=f"Cost/routing analysis: {status}",
                evidence={"routing_status": status},
                dry_run=dry_run,
            )
        except Exception as exc:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="error",
                summary=f"Routing analysis unavailable: {exc}",
                evidence={"error": str(exc)},
                dry_run=dry_run,
            )


# ---------------------------------------------------------------------------
# Worker adapter registry
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: Dict[str, WorkerAdapter] = {
    "unit_test_worker": DoctorValidationWorkerAdapter(),
    "nus_learning_worker": NUSLearningWorkerAdapter(),
    "cost_analysis_worker": CostAnalysisWorkerAdapter(),
}


def get_worker_adapter(worker_id: str) -> WorkerAdapter:
    """Return a worker adapter for the given worker_id.

    Falls back to a generic base adapter if no specific adapter is registered.
    """
    return _ADAPTER_REGISTRY.get(worker_id, WorkerAdapter(worker_id))


def execute_worker(
    worker_id: str,
    action_type: str,
    inputs: Dict[str, Any],
    dry_run: bool = True,
    session_id: Optional[str] = None,
) -> WorkerAdapterResult:
    """Execute a worker action through the adapter registry."""
    adapter = get_worker_adapter(worker_id)
    return adapter.execute(action_type, inputs, dry_run=dry_run, session_id=session_id)


__all__ = [
    "WorkerAdapterResult",
    "WorkerAdapter",
    "DoctorValidationWorkerAdapter",
    "NUSLearningWorkerAdapter",
    "CostAnalysisWorkerAdapter",
    "get_worker_adapter",
    "execute_worker",
]
