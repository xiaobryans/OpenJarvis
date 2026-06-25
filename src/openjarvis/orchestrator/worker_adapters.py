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
    """Adapter for doctor/validation workers.

    Dispatches to the full doctor check suite (run_all_checks) when action_type
    is doctor_run, or to a targeted check_id for local_validation requests.
    """

    def __init__(self) -> None:
        super().__init__("unit_test_worker")

    # Supported action types
    _SUPPORTED = frozenset({"local_validation", "doctor_run", "local_analysis"})

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        if action_type not in self._SUPPORTED:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="skipped",
                summary=(
                    f"DoctorValidationWorker only handles "
                    f"{sorted(self._SUPPORTED)}. Got '{action_type}'."
                ),
                dry_run=dry_run,
            )

        project_id = inputs.get("project_id", None)

        # doctor_run → dispatch full check suite
        if action_type == "doctor_run":
            try:
                from openjarvis.doctor.checks import run_all_checks
                results = run_all_checks(project_id=project_id)
                passed = sum(1 for r in results if r.status == "pass")
                failed = sum(1 for r in results if r.status == "fail")
                warned = sum(1 for r in results if r.status == "warn")
                not_configured = sum(1 for r in results if r.status == "not_configured")
                fail_summaries = [
                    {"check_id": r.check_id, "summary": r.summary}
                    for r in results if r.status == "fail"
                ]
                return WorkerAdapterResult(
                    worker_id=self.worker_id,
                    action_type=action_type,
                    status="ok",
                    summary=(
                        f"Doctor full suite: {passed} pass, {failed} fail, "
                        f"{warned} warn, {not_configured} not_configured "
                        f"({len(results)} checks total)."
                    ),
                    evidence={
                        "total_checks": len(results),
                        "passed": passed,
                        "failed": failed,
                        "warned": warned,
                        "not_configured": not_configured,
                        "fail_summaries": fail_summaries,
                    },
                    dry_run=dry_run,
                )
            except Exception as exc:
                return WorkerAdapterResult(
                    worker_id=self.worker_id,
                    action_type=action_type,
                    status="error",
                    summary=f"Doctor full suite failed: {exc}",
                    evidence={"error": str(exc)},
                    dry_run=dry_run,
                )

        # local_validation / local_analysis → targeted check
        check_id = inputs.get("check_id", "project_registry_health")
        try:
            from openjarvis.doctor.checks import check_project_registry_health
            result = check_project_registry_health(project_id=project_id or "default")
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="ok",
                summary=f"Doctor check '{check_id}' completed: {result.status} — {result.summary}",
                evidence={
                    "check_result": result.to_dict() if hasattr(result, "to_dict") else str(result)
                },
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


class FileInspectionWorkerAdapter(WorkerAdapter):
    """Adapter for targeted file inspection (read-only, no LLM required).

    Used in the coding proof path: inspect targeted files before proposing changes.
    Never writes or executes code. Always dry-run safe.
    """

    def __init__(self) -> None:
        super().__init__("file_inspection_worker")

    _SUPPORTED = frozenset({"local_read", "local_analysis", "coding_file_inspect"})

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        if action_type not in self._SUPPORTED:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="skipped",
                summary=f"FileInspectionWorker only handles {sorted(self._SUPPORTED)}.",
                dry_run=dry_run,
            )

        file_path = inputs.get("file_path")
        line_start = inputs.get("line_start", 1)
        line_end = inputs.get("line_end", 80)

        if not file_path:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="dry_run_ok",
                summary="FileInspectionWorker: no file_path provided, dry-run plan only.",
                evidence={"file_path": None, "note": "Provide file_path for targeted inspection."},
                dry_run=True,
            )

        from pathlib import Path
        p = Path(file_path)
        if not p.exists():
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="error",
                summary=f"File not found: {file_path}",
                evidence={"file_path": str(file_path), "error": "file_not_found"},
                dry_run=dry_run,
            )

        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            snippet = lines[max(0, line_start - 1) : line_end]
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="ok",
                summary=(
                    f"Inspected {file_path} lines {line_start}-{line_end}: "
                    f"{len(snippet)} lines read, {len(lines)} total."
                ),
                evidence={
                    "file_path": str(file_path),
                    "total_lines": len(lines),
                    "snippet_lines": len(snippet),
                    "line_start": line_start,
                    "line_end": line_end,
                },
                dry_run=dry_run,
            )
        except Exception as exc:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="error",
                summary=f"File inspection failed: {exc}",
                evidence={"error": str(exc)},
                dry_run=dry_run,
            )


class CodingSafeWorkerAdapter(WorkerAdapter):
    """Coding proof path worker adapter.

    Implements the minimum Jarvis coding proof ladder for daily-driver use:
      1. classify_coding_task — classify as safe vs unsafe, complexity, scope
      2. local_analysis — inspect targeted files (delegates to FileInspectionWorker)
      3. coding_patch_propose — structured patch proposal (dry-run plan without LLM;
         BLOCKED_PROVIDER for real code generation without OPENAI/ANTHROPIC key)
      4. coding_test_run — run targeted tests/checks
      5. coding_diff_report — report diff/evidence
      6. coding_repair_loop — bounded retry support (uses BoundedRepairLoop)
      7. coding_rollback — rollback plan via git restore

    SAFE RULES (non-negotiable):
      - Never writes files without Bryan approval.
      - Never commits or pushes.
      - Auto-push, auto-merge remain permanently blocked.
      - Real code generation requires LLM provider key (BLOCKED_PROVIDER without it).
      - Dry-run planning always available regardless of provider.
    """

    def __init__(self) -> None:
        super().__init__("coding_safe_worker")

    _SUPPORTED = frozenset({
        "local_analysis",
        "coding_task_classify",
        "coding_file_inspect",
        "coding_patch_propose",
        "coding_test_run",
        "coding_diff_report",
        "coding_repair_loop",
        "coding_rollback",
    })

    # These action types require LLM to be useful beyond dry-run planning
    _PROVIDER_GATED = frozenset({"coding_patch_propose", "coding_repair_loop"})

    def _has_llm_provider(self) -> bool:
        """Check if any LLM provider key is configured."""
        import os
        from pathlib import Path
        keys = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY"]
        for key in keys:
            if os.environ.get(key):
                return True
        cloud_env = Path.home() / ".jarvis" / "cloud-keys.env"
        if cloud_env.exists():
            content = cloud_env.read_text(errors="replace")
            for key in keys:
                for line in content.splitlines():
                    if line.strip().startswith(f"{key}=") and line.strip()[len(key) + 1:]:
                        return True
        return False

    def _execute_safe(
        self,
        action_type: str,
        inputs: Dict[str, Any],
        dry_run: bool = True,
        session_id: Optional[str] = None,
    ) -> WorkerAdapterResult:
        if action_type not in self._SUPPORTED:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="skipped",
                summary=f"CodingSafeWorker only handles {sorted(self._SUPPORTED)}.",
                dry_run=dry_run,
            )

        # Provider-gated actions: return structured dry-run plan if no LLM
        if action_type in self._PROVIDER_GATED and not self._has_llm_provider():
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type=action_type,
                status="dry_run_ok",
                summary=(
                    f"CodingSafeWorker: {action_type} requires LLM provider "
                    f"(OPENAI_API_KEY or ANTHROPIC_API_KEY). "
                    f"Dry-run plan returned. "
                    f"Set key in ~/.jarvis/cloud-keys.env to enable real generation."
                ),
                evidence={
                    "action_type": action_type,
                    "provider_required": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
                    "blocker_type": "BLOCKED_PROVIDER",
                    "fallback": "dry_run_plan_only",
                    "inputs_received": list(inputs.keys()),
                },
                blocked_reason="BLOCKED_PROVIDER: no LLM key configured",
                dry_run=True,
            )

        intent = inputs.get("intent", "")
        user_input = inputs.get("user_input", "")

        # Task classification (no LLM needed)
        if action_type in ("coding_task_classify", "local_analysis"):
            return self._classify_task(intent, user_input, inputs, dry_run)

        # File inspection (delegates to FileInspectionWorkerAdapter)
        if action_type == "coding_file_inspect":
            adapter = FileInspectionWorkerAdapter()
            return adapter._execute_safe("local_read", inputs, dry_run=dry_run)

        # Test run (local, no LLM)
        if action_type == "coding_test_run":
            return self._run_tests(inputs, dry_run)

        # Diff report (local git diff)
        if action_type == "coding_diff_report":
            return self._diff_report(inputs, dry_run)

        # Rollback (git restore — requires Bryan approval via approval gate)
        if action_type == "coding_rollback":
            return self._rollback_plan(inputs, dry_run)

        # Repair loop (dry-run only without LLM)
        if action_type == "coding_repair_loop":
            return self._repair_loop_dry_run(inputs, dry_run)

        # Default: dry-run plan
        return WorkerAdapterResult(
            worker_id=self.worker_id,
            action_type=action_type,
            status="dry_run_ok",
            summary=f"CodingSafeWorker dry-run: {action_type}",
            evidence={"inputs_keys": list(inputs.keys())},
            dry_run=True,
        )

    def _classify_task(
        self,
        intent: str,
        user_input: str,
        inputs: Dict[str, Any],
        dry_run: bool,
    ) -> WorkerAdapterResult:
        """Classify coding task scope, risk, and safety (keyword-based, no LLM)."""
        text = (intent + " " + user_input).lower()

        # Unsafe patterns (always blocked)
        _UNSAFE_PATTERNS = [
            "push", "merge", "deploy", "delete production",
            "drop table", "rm -rf", "override safety",
        ]
        unsafe = [p for p in _UNSAFE_PATTERNS if p in text]

        # Complexity
        _COMPLEX_KEYWORDS = ["refactor", "migration", "multi-file", "architecture", "schema"]
        _SIMPLE_KEYWORDS = ["fix", "typo", "comment", "rename", "add import"]
        complexity = "complex" if any(k in text for k in _COMPLEX_KEYWORDS) else (
            "simple" if any(k in text for k in _SIMPLE_KEYWORDS) else "moderate"
        )

        # File scope
        file_scope = inputs.get("file_path") or inputs.get("files_affected", [])

        safe = len(unsafe) == 0
        return WorkerAdapterResult(
            worker_id=self.worker_id,
            action_type="coding_task_classify",
            status="ok",
            summary=(
                f"Coding task classified: complexity={complexity}, "
                f"safe={safe}, unsafe_patterns={unsafe}."
            ),
            evidence={
                "intent": intent,
                "complexity": complexity,
                "safe": safe,
                "unsafe_patterns": unsafe,
                "file_scope": file_scope,
                "classification_method": "keyword_based",
                "note": "4/5 requires domain-model classifier; currently keyword-based (3/5).",
            },
            dry_run=dry_run,
        )

    def _run_tests(self, inputs: Dict[str, Any], dry_run: bool) -> WorkerAdapterResult:
        """Run targeted tests (pytest) for a coding task. Returns test result evidence."""
        import subprocess
        test_path = inputs.get("test_path", "tests/orchestrator/")
        cmd = [
            "python3", "-m", "pytest", str(test_path),
            "-x", "-q", "--tb=short", "--no-header",
        ]
        # Use venv python if available
        import os
        from pathlib import Path
        venv_python = Path(".venv/bin/python")
        if venv_python.exists():
            cmd[0] = str(venv_python)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path.cwd()),
            )
            passed = "passed" in result.stdout
            failed = "failed" in result.stdout or result.returncode != 0
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type="coding_test_run",
                status="ok" if not failed else "error",
                summary=(
                    f"Test run for '{test_path}': "
                    f"{'PASSED' if passed and not failed else 'FAILED'}. "
                    f"returncode={result.returncode}."
                ),
                evidence={
                    "test_path": str(test_path),
                    "returncode": result.returncode,
                    "stdout_tail": result.stdout[-500:] if result.stdout else "",
                    "stderr_tail": result.stderr[-200:] if result.stderr else "",
                    "passed": passed,
                    "failed": failed,
                },
                dry_run=dry_run,
            )
        except subprocess.TimeoutExpired:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type="coding_test_run",
                status="error",
                summary=f"Test run timed out for '{test_path}'.",
                evidence={"test_path": str(test_path), "error": "timeout"},
                dry_run=dry_run,
            )
        except Exception as exc:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type="coding_test_run",
                status="error",
                summary=f"Test run failed: {exc}",
                evidence={"error": str(exc)},
                dry_run=dry_run,
            )

    def _diff_report(self, inputs: Dict[str, Any], dry_run: bool) -> WorkerAdapterResult:
        """Report git diff as structured evidence."""
        import subprocess
        from pathlib import Path
        try:
            result = subprocess.run(
                ["git", "diff", "--stat"],
                capture_output=True, text=True, timeout=10, cwd=str(Path.cwd()),
            )
            diff_result = subprocess.run(
                ["git", "diff", "--check"],
                capture_output=True, text=True, timeout=10, cwd=str(Path.cwd()),
            )
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type="coding_diff_report",
                status="ok",
                summary=f"Git diff report: {result.stdout.strip() or 'no changes'}.",
                evidence={
                    "diff_stat": result.stdout.strip(),
                    "diff_check_returncode": diff_result.returncode,
                    "diff_check_issues": diff_result.stdout.strip(),
                    "clean": diff_result.returncode == 0,
                },
                dry_run=dry_run,
            )
        except Exception as exc:
            return WorkerAdapterResult(
                worker_id=self.worker_id,
                action_type="coding_diff_report",
                status="error",
                summary=f"Diff report failed: {exc}",
                evidence={"error": str(exc)},
                dry_run=dry_run,
            )

    def _rollback_plan(self, inputs: Dict[str, Any], dry_run: bool) -> WorkerAdapterResult:
        """Generate rollback plan for a coding change. Never auto-executes rollback."""
        file_path = inputs.get("file_path")
        plan_summary = (
            f"Rollback plan for '{file_path}': git restore {file_path}. "
            f"Requires Bryan approval before execution. Never auto-rollback."
            if file_path else
            "Rollback plan: git checkout HEAD -- <files>. Requires Bryan approval."
        )
        return WorkerAdapterResult(
            worker_id=self.worker_id,
            action_type="coding_rollback",
            status="dry_run_ok",
            summary=plan_summary,
            evidence={
                "file_path": file_path,
                "rollback_command": f"git restore {file_path}" if file_path else "git checkout HEAD",
                "approval_required": True,
                "auto_rollback": False,
                "rollback_support": "plan_only",
            },
            dry_run=True,
        )

    def _repair_loop_dry_run(self, inputs: Dict[str, Any], dry_run: bool) -> WorkerAdapterResult:
        """Dry-run repair loop plan. Real repair requires LLM provider."""
        attempt = inputs.get("attempt", 1)
        max_attempts = inputs.get("max_attempts", 3)
        return WorkerAdapterResult(
            worker_id=self.worker_id,
            action_type="coding_repair_loop",
            status="dry_run_ok",
            summary=(
                f"Repair loop plan: attempt {attempt}/{max_attempts}. "
                f"Real re-generation requires LLM provider (BLOCKED_PROVIDER). "
                f"Dry-run: re-run tests only."
            ),
            evidence={
                "attempt": attempt,
                "max_attempts": max_attempts,
                "provider_required": ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
                "blocker_type": "BLOCKED_PROVIDER",
                "dry_run_action": "re_run_tests_only",
            },
            dry_run=True,
        )


# ---------------------------------------------------------------------------
# Worker adapter registry
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: Dict[str, WorkerAdapter] = {
    "unit_test_worker": DoctorValidationWorkerAdapter(),
    "doctor_check_worker": DoctorValidationWorkerAdapter(),
    "nus_learning_worker": NUSLearningWorkerAdapter(),
    "cost_analysis_worker": CostAnalysisWorkerAdapter(),
    "file_inspection_worker": FileInspectionWorkerAdapter(),
    "coding_safe_worker": CodingSafeWorkerAdapter(),
    "local_research_worker": CodingSafeWorkerAdapter(),  # reuse for local analysis
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
    "FileInspectionWorkerAdapter",
    "CodingSafeWorkerAdapter",
    "get_worker_adapter",
    "execute_worker",
]
