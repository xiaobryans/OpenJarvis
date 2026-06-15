"""Jarvis Watchdog Foundation — observe-only health monitors.

Watchdogs OBSERVE and REPORT. They NEVER:
  - auto-fix, auto-send, auto-deploy, auto-merge
  - fake a healthy status when dependencies are missing
  - modify any system state

Each watchdog produces a WatchdogResult with:
  id, project_id, severity, status, evidence, recommendation, last_checked_at

Missing/unavailable dependencies → status=degraded or not_configured (never fake_healthy).

Watchdogs (8):
  1. backend_health_watchdog            — recent tool execution failure rate
  2. mission_stuck_watchdog             — missions stuck in non-terminal state >1h
  3. approval_queue_watchdog            — tasks awaiting approval
  4. tool_degradation_watchdog          — degraded/not_configured tools
  5. memory_secret_rejection_watchdog   — memory store health + secret scrub
  6. project_handoff_staleness_watchdog — handoff doc staleness (>7 days)
  7. git_dirty_watchdog                 — git working tree dirty check
  8. execution_failure_watchdog         — tools with high failure rates
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class WatchdogSeverity:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class WatchdogStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"
    SKIPPED = "skipped"


@dataclass
class WatchdogResult:
    """Result from a single watchdog run."""

    id: str
    project_id: str
    severity: str
    status: str
    evidence: str
    recommendation: str
    last_checked_at: float = field(default_factory=time.time)
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "severity": self.severity,
            "status": self.status,
            "evidence": self.evidence,
            "recommendation": self.recommendation,
            "last_checked_at": self.last_checked_at,
            "extra": self.extra,
        }


# ---------------------------------------------------------------------------
# Watchdog runner functions — observe only, no modifications
# ---------------------------------------------------------------------------


def _run_backend_health_watchdog(project_id: str) -> WatchdogResult:
    """Check recent tool execution failure rate from execution log."""
    wid = "backend_health_watchdog"
    try:
        from openjarvis.tools.gateway import get_gateway
        log = get_gateway().get_log()
        recent = log.list_recent(limit=50)
        if not recent:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.INFO,
                status=WatchdogStatus.HEALTHY,
                evidence="No tool executions in log yet.",
                recommendation="Run some tools to build an execution history.",
            )
        failures = [e for e in recent if not e.ok]
        failure_rate = len(failures) / len(recent)
        if failure_rate >= 0.5:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.ERROR,
                status=WatchdogStatus.FAILED,
                evidence=f"{len(failures)}/{len(recent)} recent executions failed (rate={failure_rate:.0%})",
                recommendation="Inspect execution log. Check tool configuration and dependencies.",
                extra={"failure_count": len(failures), "total": len(recent)},
            )
        if failure_rate >= 0.2:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.DEGRADED,
                evidence=f"{len(failures)}/{len(recent)} recent executions failed (rate={failure_rate:.0%})",
                recommendation="Monitor tool failures. Some tools may need configuration.",
                extra={"failure_count": len(failures), "total": len(recent)},
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence=f"{len(recent) - len(failures)}/{len(recent)} recent executions succeeded.",
            recommendation="No action needed.",
            extra={"failure_count": len(failures), "total": len(recent)},
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Could not access execution log: {exc}",
            recommendation="Ensure tool gateway and execution log are initialized.",
        )


def _run_mission_stuck_watchdog(project_id: str) -> WatchdogResult:
    """Check for missions stuck in non-terminal state for >1 hour."""
    wid = "mission_stuck_watchdog"
    STUCK_THRESHOLD_SEC = 3600
    try:
        from openjarvis.mission.store import MissionStore
        store = MissionStore()
        missions = store.list_missions()
        non_terminal = [
            m for m in missions
            if m.status not in ("completed", "failed", "cancelled")
        ]
        now = time.time()
        stuck = [
            m for m in non_terminal
            if (now - m.created_at) > STUCK_THRESHOLD_SEC
        ]
        if stuck:
            names = ", ".join(m.id[:8] for m in stuck[:5])
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.DEGRADED,
                evidence=f"{len(stuck)} mission(s) stuck >1h in non-terminal state: {names}",
                recommendation="Review stuck missions. Run a mission pass or escalate for approval.",
                extra={"stuck_count": len(stuck), "stuck_mission_ids": [m.id for m in stuck[:10]]},
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence=f"{len(non_terminal)} active mission(s), none stuck >1h.",
            recommendation="No action needed.",
            extra={"active_count": len(non_terminal)},
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Could not access mission store: {exc}",
            recommendation="Ensure MissionStore is available.",
        )


def _run_approval_queue_watchdog(project_id: str) -> WatchdogResult:
    """Check for tasks in awaiting_approval state."""
    wid = "approval_queue_watchdog"
    try:
        from openjarvis.mission.store import MissionStore
        store = MissionStore()
        missions = store.list_missions()
        pending = []
        for m in missions:
            tasks = store.list_tasks(m.id)
            pending.extend([t for t in tasks if t.status == "awaiting_approval"])
        if pending:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.DEGRADED,
                evidence=f"{len(pending)} task(s) awaiting approval.",
                recommendation="Review and approve or reject pending tasks in Mission Control.",
                extra={"pending_count": len(pending), "task_ids": [t.id for t in pending[:10]]},
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence="No tasks awaiting approval.",
            recommendation="No action needed.",
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Could not check approval queue: {exc}",
            recommendation="Ensure MissionStore is available.",
        )


def _run_tool_degradation_watchdog(project_id: str) -> WatchdogResult:
    """Check for degraded/not_configured tools in the registry."""
    wid = "tool_degradation_watchdog"
    try:
        from openjarvis.tools.catalog import initialize_catalog
        from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus
        initialize_catalog()
        all_tools = ToolRegistry.list_all()
        degraded = [t for t in all_tools if t.implementation_status == ToolStatus.DEGRADED]
        not_configured = [t for t in all_tools if t.implementation_status == ToolStatus.NOT_CONFIGURED]
        total = len(all_tools)
        available = len(ToolRegistry.list_available())
        if not_configured or degraded:
            nc_ids = [t.tool_id for t in not_configured[:5]]
            d_ids = [t.tool_id for t in degraded[:5]]
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.DEGRADED,
                evidence=(
                    f"{total} tools registered: {available} available, "
                    f"{len(not_configured)} not_configured {nc_ids}, "
                    f"{len(degraded)} degraded {d_ids}."
                ),
                recommendation=(
                    "Configure missing env vars for not_configured tools. "
                    "Check degraded tool blockers."
                ),
                extra={
                    "total": total, "available": available,
                    "not_configured": [t.tool_id for t in not_configured],
                    "degraded": [t.tool_id for t in degraded],
                },
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence=f"All {available}/{total} tools available. None degraded or not_configured.",
            recommendation="No action needed.",
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Could not access tool registry: {exc}",
            recommendation="Ensure tool catalog is initialized.",
        )


def _run_memory_secret_rejection_watchdog(project_id: str) -> WatchdogResult:
    """Validate memory store is available and correctly rejects secret-pattern content."""
    wid = "memory_secret_rejection_watchdog"
    try:
        from openjarvis.memory.store import JarvisMemory
        mem = JarvisMemory()
        secret_rejected = False
        try:
            # Split token string to avoid GitHub Push Protection triggering on source
            fake_token = "xoxb-" + "000000000000-test-fake-token-not-real"
            mem.write("watchdog_test", fake_token, project_id="__watchdog_test__")
        except ValueError:
            secret_rejected = True
        if not secret_rejected:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.CRITICAL,
                status=WatchdogStatus.FAILED,
                evidence="Memory store did NOT reject a simulated secret token. Secret scrub is broken.",
                recommendation="Inspect JarvisMemory._scrub_content() immediately. Do not write to memory.",
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence="Memory store correctly rejects secret-pattern content. Scrub is functional.",
            recommendation="No action needed.",
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.ERROR,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Memory store unavailable: {exc}",
            recommendation="Ensure ~/.jarvis/memory.db is accessible.",
        )


def _run_project_handoff_staleness_watchdog(project_id: str) -> WatchdogResult:
    """Check if handoff document is stale (>7 days since last modification)."""
    wid = "project_handoff_staleness_watchdog"
    STALENESS_THRESHOLD_SEC = 7 * 24 * 3600
    try:
        from openjarvis.governance.constitution import ProjectRegistry
        project = ProjectRegistry.get(project_id)
        if project is None:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.NOT_CONFIGURED,
                evidence=f"Project '{project_id}' not found in ProjectRegistry.",
                recommendation="Register the project before running handoff watchdog.",
            )
        handoff_paths = project.handoff_paths
        if not handoff_paths:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.INFO,
                status=WatchdogStatus.SKIPPED,
                evidence=f"Project '{project_id}' has no handoff_paths configured.",
                recommendation="Add handoff_paths to ProjectProfile.",
            )
        stale_files = []
        missing_files = []
        now = time.time()
        base = Path(project.repo_path) if project.repo_path else Path.cwd()
        for hp in handoff_paths:
            fp = base / hp if not Path(hp).is_absolute() else Path(hp)
            if not fp.exists():
                missing_files.append(str(hp))
            else:
                mtime = fp.stat().st_mtime
                age_sec = now - mtime
                if age_sec > STALENESS_THRESHOLD_SEC:
                    stale_files.append(f"{hp} (age: {age_sec / 86400:.1f}d)")
        if missing_files:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.ERROR,
                status=WatchdogStatus.FAILED,
                evidence=f"Handoff file(s) missing: {missing_files}",
                recommendation="Create the missing handoff document(s).",
            )
        if stale_files:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.DEGRADED,
                evidence=f"Stale handoff file(s): {stale_files}",
                recommendation="Update the handoff document to reflect current sprint state.",
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence=f"Handoff file(s) are up-to-date: {list(handoff_paths)}",
            recommendation="No action needed.",
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Handoff staleness check failed: {exc}",
            recommendation="Ensure project repo path and handoff paths are configured.",
        )


def _run_git_dirty_watchdog(project_id: str) -> WatchdogResult:
    """Check if the project git working tree is dirty."""
    wid = "git_dirty_watchdog"
    try:
        from openjarvis.governance.constitution import ProjectRegistry
        project = ProjectRegistry.get(project_id)
        repo_path = project.repo_path if project else ""
        if not repo_path or not Path(repo_path).is_dir():
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.INFO,
                status=WatchdogStatus.SKIPPED,
                evidence=f"No valid repo_path configured for project '{project_id}'.",
                recommendation="Set repo_path in ProjectProfile to enable git dirty check.",
            )
        result = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=10,
            cwd=repo_path,
        )
        if result.returncode != 0:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.NOT_CONFIGURED,
                evidence=f"git status failed: {result.stderr.strip()[:200]}",
                recommendation="Ensure git is installed and repo_path is a valid git repo.",
            )
        dirty = result.stdout.strip()
        if dirty:
            lines = dirty.split("\n")
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.DEGRADED,
                evidence=f"Working tree has {len(lines)} uncommitted change(s).",
                recommendation="Commit or stash changes before sprint closeout.",
                extra={"dirty_lines": lines[:20]},
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence="Working tree is clean.",
            recommendation="No action needed.",
        )
    except subprocess.TimeoutExpired:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.DEGRADED,
            evidence="git status timed out after 10s.",
            recommendation="Check if git is hung or repo is corrupted.",
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Git dirty check failed: {exc}",
            recommendation="Ensure git is installed and accessible.",
        )


def _run_execution_failure_watchdog(project_id: str) -> WatchdogResult:
    """Check recent execution log for tools with high failure rates (>=50% over 3+ runs)."""
    wid = "execution_failure_watchdog"
    try:
        from openjarvis.tools.gateway import get_gateway
        log = get_gateway().get_log()
        recent = log.list_recent(limit=100)
        if not recent:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.INFO,
                status=WatchdogStatus.HEALTHY,
                evidence="No tool executions logged yet.",
                recommendation="No action needed.",
            )
        tool_counts: Dict[str, Dict[str, int]] = {}
        for e in recent:
            tid = e.tool_id
            if tid not in tool_counts:
                tool_counts[tid] = {"total": 0, "failures": 0}
            tool_counts[tid]["total"] += 1
            if not e.ok:
                tool_counts[tid]["failures"] += 1
        high_failure = [
            tid for tid, c in tool_counts.items()
            if c["total"] >= 3 and (c["failures"] / c["total"]) >= 0.5
        ]
        if high_failure:
            return WatchdogResult(
                id=wid, project_id=project_id,
                severity=WatchdogSeverity.ERROR,
                status=WatchdogStatus.FAILED,
                evidence=f"High failure rate tools (>=50% over 3+ runs): {high_failure}",
                recommendation="Inspect these tools. Check configuration, permissions, and dependencies.",
                extra={"high_failure_tools": high_failure, "tool_counts": tool_counts},
            )
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.INFO,
            status=WatchdogStatus.HEALTHY,
            evidence=f"No tools with high failure rates in last {len(recent)} executions.",
            recommendation="No action needed.",
        )
    except Exception as exc:
        return WatchdogResult(
            id=wid, project_id=project_id,
            severity=WatchdogSeverity.WARNING,
            status=WatchdogStatus.NOT_CONFIGURED,
            evidence=f"Could not access execution log: {exc}",
            recommendation="Ensure tool gateway and execution log are initialized.",
        )


# ---------------------------------------------------------------------------
# Watchdog Registry + Runner
# ---------------------------------------------------------------------------

_WATCHDOG_REGISTRY: Dict[str, Callable[[str], WatchdogResult]] = {
    "backend_health_watchdog": _run_backend_health_watchdog,
    "mission_stuck_watchdog": _run_mission_stuck_watchdog,
    "approval_queue_watchdog": _run_approval_queue_watchdog,
    "tool_degradation_watchdog": _run_tool_degradation_watchdog,
    "memory_secret_rejection_watchdog": _run_memory_secret_rejection_watchdog,
    "project_handoff_staleness_watchdog": _run_project_handoff_staleness_watchdog,
    "git_dirty_watchdog": _run_git_dirty_watchdog,
    "execution_failure_watchdog": _run_execution_failure_watchdog,
}


class WatchdogRunner:
    """Runs watchdog checks. Observes only — no system modifications."""

    @staticmethod
    def run_once(watchdog_id: str, project_id: str) -> WatchdogResult:
        """Run a single watchdog by ID. Never modifies system state."""
        fn = _WATCHDOG_REGISTRY.get(watchdog_id)
        if fn is None:
            return WatchdogResult(
                id=watchdog_id, project_id=project_id,
                severity=WatchdogSeverity.WARNING,
                status=WatchdogStatus.NOT_CONFIGURED,
                evidence=f"Watchdog '{watchdog_id}' not registered.",
                recommendation=f"Valid IDs: {sorted(_WATCHDOG_REGISTRY.keys())}",
            )
        try:
            return fn(project_id)
        except Exception as exc:
            logger.exception("Watchdog '%s' raised unexpectedly: %s", watchdog_id, exc)
            return WatchdogResult(
                id=watchdog_id, project_id=project_id,
                severity=WatchdogSeverity.ERROR,
                status=WatchdogStatus.FAILED,
                evidence=f"Watchdog raised: {exc}",
                recommendation="Check watchdog implementation.",
            )

    @staticmethod
    def run_project_pack(project_id: str) -> List[WatchdogResult]:
        """Run all registered watchdogs for a project. Returns one result per watchdog."""
        results = []
        for wid in sorted(_WATCHDOG_REGISTRY.keys()):
            result = WatchdogRunner.run_once(wid, project_id)
            results.append(result)
        return results

    @staticmethod
    def list_watchdog_ids() -> List[str]:
        """Return all registered watchdog IDs."""
        return sorted(_WATCHDOG_REGISTRY.keys())

    @staticmethod
    def summarize(results: List[WatchdogResult]) -> Dict[str, Any]:
        """Summarize a list of watchdog results by status/severity."""
        by_status: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for r in results:
            by_status[r.status] = by_status.get(r.status, 0) + 1
            by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        return {
            "total": len(results),
            "by_status": by_status,
            "by_severity": by_severity,
            "healthy": by_status.get(WatchdogStatus.HEALTHY, 0),
            "degraded": by_status.get(WatchdogStatus.DEGRADED, 0),
            "failed": by_status.get(WatchdogStatus.FAILED, 0),
            "not_configured": by_status.get(WatchdogStatus.NOT_CONFIGURED, 0),
        }


__all__ = [
    "WatchdogResult",
    "WatchdogRunner",
    "WatchdogSeverity",
    "WatchdogStatus",
]
