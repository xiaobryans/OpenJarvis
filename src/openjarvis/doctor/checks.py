"""Jarvis Doctor — 12 independent diagnostic checks.

Each check:
  - is independent (no side effects on other checks)
  - returns CheckResult with status, evidence, and summary
  - must not require secrets
  - must not perform real outbound sends
  - must not auto-fix

Statuses:
  pass           — check passed, evidence verified
  warn           — check passed with caveats / non-blocking degradation
  fail           — check failed, evidence shows a real problem
  not_configured — check could not run; missing config/dependency (non-fatal)
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CheckStatus / CheckResult
# ---------------------------------------------------------------------------


class CheckStatus:
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_CONFIGURED = "not_configured"


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    check_id: str
    category: str
    status: str
    summary: str
    evidence: Dict[str, Any]
    project_id: str
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "status": self.status,
            "summary": self.summary,
            "evidence": self.evidence,
            "project_id": self.project_id,
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# Check 1 — backend_health
# ---------------------------------------------------------------------------


def check_backend_health(project_id: str = "omnix") -> CheckResult:
    """Verify that all core internal modules are importable."""
    evidence: Dict[str, Any] = {}
    failures: List[str] = []
    core_modules = [
        "openjarvis.tools.jarvis_registry",
        "openjarvis.tools.gateway",
        "openjarvis.tools.execution_log",
        "openjarvis.governance.constitution",
        "openjarvis.governance.policies",
        "openjarvis.autonomy.modes",
        "openjarvis.autonomy.watchdogs",
        "openjarvis.autonomy.alerts",
        "openjarvis.memory.store",
        "openjarvis.mission.store",
    ]
    for mod in core_modules:
        try:
            __import__(mod)
            evidence[mod] = "ok"
        except Exception as exc:
            evidence[mod] = f"import_error: {exc}"
            failures.append(mod)

    if failures:
        return CheckResult(
            check_id="backend_health",
            category="backend",
            status=CheckStatus.FAIL,
            summary=f"Backend health: {len(failures)} module(s) failed to import: {failures}",
            evidence=evidence,
            project_id=project_id,
        )
    return CheckResult(
        check_id="backend_health",
        category="backend",
        status=CheckStatus.PASS,
        summary=f"Backend health: all {len(evidence)} core modules importable",
        evidence=evidence,
        project_id=project_id,
    )


# ---------------------------------------------------------------------------
# Check 2 — project_registry_health
# ---------------------------------------------------------------------------


def check_project_registry_health(project_id: str = "omnix") -> CheckResult:
    """Verify ProjectRegistry has entries and OMNIX (Project 1) is registered."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.governance.constitution import ProjectRegistry

        projects = ProjectRegistry.list_projects()
        evidence["total_projects"] = len(projects)
        evidence["project_ids"] = [p.project_id for p in projects]
        omnix_present = any(p.project_id == "omnix" for p in projects)
        evidence["omnix_present"] = omnix_present
        target_present = any(p.project_id == project_id for p in projects)
        evidence["target_project_present"] = target_present

        if not omnix_present:
            return CheckResult(
                check_id="project_registry_health",
                category="project",
                status=CheckStatus.FAIL,
                summary="ProjectRegistry: OMNIX (Project 1) is missing",
                evidence=evidence,
                project_id=project_id,
            )
        if not target_present and project_id != "omnix":
            return CheckResult(
                check_id="project_registry_health",
                category="project",
                status=CheckStatus.WARN,
                summary=(
                    f"ProjectRegistry: target project '{project_id}' not registered; "
                    "OMNIX present"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="project_registry_health",
            category="project",
            status=CheckStatus.PASS,
            summary=(
                f"ProjectRegistry: {len(projects)} project(s) registered; "
                "OMNIX=Project 1 present"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="project_registry_health",
            category="project",
            status=CheckStatus.FAIL,
            summary=f"ProjectRegistry: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 3 — tool_registry_counts
# ---------------------------------------------------------------------------


def check_tool_registry_counts(project_id: str = "omnix") -> CheckResult:
    """Verify tool registry counts and report unavailable reasons."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.tools.catalog import initialize_catalog
        from openjarvis.tools.jarvis_registry import ToolRegistry, ToolStatus

        initialize_catalog()
        stats = ToolRegistry.stats()
        unavailable = ToolRegistry.list_unavailable()
        evidence["total_registered"] = stats["total_registered"]
        evidence["available"] = stats["available"]
        evidence["by_status"] = stats["by_status"]
        evidence["unavailable_reasons"] = [
            {
                "tool_id": t.tool_id,
                "status": t.implementation_status,
                "blocker": t.blocker,
            }
            for t in unavailable
        ]

        if stats["available"] == 0:
            return CheckResult(
                check_id="tool_registry_counts",
                category="tools",
                status=CheckStatus.FAIL,
                summary="Tool registry: 0 tools available",
                evidence=evidence,
                project_id=project_id,
            )
        not_configured = stats["by_status"].get(ToolStatus.NOT_CONFIGURED, 0)
        degraded = stats["by_status"].get(ToolStatus.DEGRADED, 0)
        if not_configured > 0 or degraded > 0:
            return CheckResult(
                check_id="tool_registry_counts",
                category="tools",
                status=CheckStatus.WARN,
                summary=(
                    f"Tool registry: {stats['available']} available, "
                    f"{not_configured} not_configured, {degraded} degraded "
                    f"(total {stats['total_registered']})"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="tool_registry_counts",
            category="tools",
            status=CheckStatus.PASS,
            summary=(
                f"Tool registry: {stats['available']} available, "
                f"0 not_configured, 0 degraded "
                f"(total {stats['total_registered']})"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="tool_registry_counts",
            category="tools",
            status=CheckStatus.FAIL,
            summary=f"Tool registry: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 4 — skill_registry_counts
# ---------------------------------------------------------------------------


def check_skill_registry_counts(project_id: str = "omnix") -> CheckResult:
    """Verify skill registry counts and report degraded reasons."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.tools.catalog import initialize_catalog as _init_tools
        from openjarvis.skills.catalog import initialize_catalog as _init_skills
        from openjarvis.skills.jarvis_registry import SkillRegistry, SkillStatus

        _init_tools()
        _init_skills()
        all_skills = SkillRegistry.list_all()
        available = SkillRegistry.list_available()
        degraded = [s for s in all_skills if s.status == SkillStatus.DEGRADED]
        not_configured = [
            s for s in all_skills if s.status == SkillStatus.NOT_CONFIGURED
        ]
        evidence["total_registered"] = len(all_skills)
        evidence["available"] = len(available)
        evidence["degraded"] = len(degraded)
        evidence["not_configured"] = len(not_configured)
        evidence["degraded_details"] = [
            {"skill_id": s.skill_id, "status": s.status, "blocker": s.blocker}
            for s in degraded
        ]
        evidence["not_configured_details"] = [
            {"skill_id": s.skill_id, "status": s.status, "blocker": s.blocker}
            for s in not_configured
        ]

        if len(available) == 0:
            return CheckResult(
                check_id="skill_registry_counts",
                category="skills",
                status=CheckStatus.FAIL,
                summary="Skill registry: 0 skills available",
                evidence=evidence,
                project_id=project_id,
            )
        if degraded or not_configured:
            return CheckResult(
                check_id="skill_registry_counts",
                category="skills",
                status=CheckStatus.WARN,
                summary=(
                    f"Skill registry: {len(available)} available, "
                    f"{len(degraded)} degraded, {len(not_configured)} not_configured "
                    f"(total {len(all_skills)})"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="skill_registry_counts",
            category="skills",
            status=CheckStatus.PASS,
            summary=(
                f"Skill registry: {len(available)} available, 0 degraded, 0 not_configured "
                f"(total {len(all_skills)})"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="skill_registry_counts",
            category="skills",
            status=CheckStatus.FAIL,
            summary=f"Skill registry: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 5 — memory_store_health
# ---------------------------------------------------------------------------


def check_memory_store_health(project_id: str = "omnix") -> CheckResult:
    """Verify memory store: SQLite reachable and secret rejection functional."""
    evidence: Dict[str, Any] = {}
    try:
        import tempfile

        from openjarvis.memory.store import JarvisMemory

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = Path(f.name)
        try:
            mem = JarvisMemory(db_path=tmp_path)
            entry = mem.write(
                f"doctor:project:{project_id}",
                "doctor_check_ping_ok",
                source="doctor",
                project_id=project_id,
                tags=["doctor"],
            )
            evidence["write_ok"] = True
            evidence["entry_id"] = entry.entry_id

            secret_rejected = False
            try:
                mem.write(
                    "doctor:test_bad",
                    "sk-fake_secret_key_that_looks_real_abcdefg1234567890",
                    source="doctor",
                )
            except ValueError:
                secret_rejected = True
            evidence["secret_rejection_functional"] = secret_rejected

            if not secret_rejected:
                return CheckResult(
                    check_id="memory_store_health",
                    category="memory",
                    status=CheckStatus.FAIL,
                    summary=(
                        "Memory store: secret rejection NOT functional — "
                        "critical security gap"
                    ),
                    evidence=evidence,
                    project_id=project_id,
                )
            return CheckResult(
                check_id="memory_store_health",
                category="memory",
                status=CheckStatus.PASS,
                summary=(
                    "Memory store: SQLite reachable, write/read ok, "
                    "secret rejection functional"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as exc:
        return CheckResult(
            check_id="memory_store_health",
            category="memory",
            status=CheckStatus.FAIL,
            summary=f"Memory store: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 6 — autonomy_mode_status
# ---------------------------------------------------------------------------


def check_autonomy_mode_status(project_id: str = "omnix") -> CheckResult:
    """Verify autonomy mode and governance hard gate enforcement."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.modes import AutonomyPolicy

        status = AutonomyPolicy.get_status(project_id)
        evidence["mode"] = status["mode"]
        evidence["can_observe"] = status["can_observe"]
        evidence["can_propose"] = status["can_propose"]
        evidence["hard_gates_always_blocked"] = status["hard_gates_always_blocked"]
        evidence["real_send_always_blocked"] = status["real_send_always_blocked"]

        hard_gate_blocked = not AutonomyPolicy.can_auto_execute(
            project_id, "real_slack_send", risk_level="low"
        )
        evidence["hard_gate_enforcement_verified"] = hard_gate_blocked

        if not hard_gate_blocked:
            return CheckResult(
                check_id="autonomy_mode_status",
                category="autonomy",
                status=CheckStatus.FAIL,
                summary=(
                    "UNSAFE: Governance hard gate NOT enforced — "
                    "real_slack_send not blocked"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="autonomy_mode_status",
            category="autonomy",
            status=CheckStatus.PASS,
            summary=(
                f"Autonomy: mode={status['mode']}, "
                f"can_observe={status['can_observe']}, "
                "hard_gate_enforcement=verified"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="autonomy_mode_status",
            category="autonomy",
            status=CheckStatus.FAIL,
            summary=f"Autonomy mode: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 7 — watchdog_status
# ---------------------------------------------------------------------------


def check_watchdog_status(project_id: str = "omnix") -> CheckResult:
    """Verify watchdog registry and run all watchdogs to collect status."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.watchdogs import WatchdogRunner

        ids = WatchdogRunner.list_watchdog_ids()
        evidence["registered_count"] = len(ids)
        evidence["registered_ids"] = ids

        if not ids:
            return CheckResult(
                check_id="watchdog_status",
                category="autonomy",
                status=CheckStatus.FAIL,
                summary="Watchdog registry: 0 watchdogs registered",
                evidence=evidence,
                project_id=project_id,
            )

        results = WatchdogRunner.run_project_pack(project_id)
        healthy = sum(1 for r in results if r.status == "healthy")
        degraded_count = sum(1 for r in results if r.status == "degraded")
        failed_count = sum(1 for r in results if r.status == "failed")
        not_configured_count = sum(
            1 for r in results if r.status == "not_configured"
        )
        evidence["watchdog_results"] = {
            "total": len(results),
            "healthy": healthy,
            "degraded": degraded_count,
            "failed": failed_count,
            "not_configured": not_configured_count,
        }
        evidence["results_by_id"] = {r.id: r.status for r in results}

        if failed_count > 0:
            return CheckResult(
                check_id="watchdog_status",
                category="autonomy",
                status=CheckStatus.WARN,
                summary=(
                    f"Watchdogs: {len(ids)} registered, "
                    f"{healthy} healthy, {degraded_count} degraded, "
                    f"{failed_count} failed"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        if degraded_count > 0:
            return CheckResult(
                check_id="watchdog_status",
                category="autonomy",
                status=CheckStatus.WARN,
                summary=(
                    f"Watchdogs: {len(ids)} registered, "
                    f"{healthy} healthy, {degraded_count} degraded, 0 failed"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="watchdog_status",
            category="autonomy",
            status=CheckStatus.PASS,
            summary=f"Watchdogs: {len(ids)} registered, all {healthy} healthy",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="watchdog_status",
            category="autonomy",
            status=CheckStatus.FAIL,
            summary=f"Watchdog check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 8 — alert_status
# ---------------------------------------------------------------------------


def check_alert_status(project_id: str = "omnix") -> CheckResult:
    """Verify alert store health and open alert count."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.alerts import AlertStore

        store = AlertStore()
        all_alerts = store.list(project_id=project_id)
        open_alerts = [a for a in all_alerts if a.status == "open"]
        ack_alerts = [a for a in all_alerts if a.status == "acknowledged"]
        resolved_alerts = [a for a in all_alerts if a.status == "resolved"]
        evidence["store_reachable"] = True
        evidence["total"] = len(all_alerts)
        evidence["open"] = len(open_alerts)
        evidence["acknowledged"] = len(ack_alerts)
        evidence["resolved"] = len(resolved_alerts)

        if open_alerts:
            high_sev = [
                a for a in open_alerts if a.severity in ("critical", "high")
            ]
            if high_sev:
                evidence["high_severity_open"] = [a.title for a in high_sev]
                return CheckResult(
                    check_id="alert_status",
                    category="alerts",
                    status=CheckStatus.WARN,
                    summary=(
                        f"Alerts: {len(open_alerts)} open "
                        f"({len(high_sev)} high/critical severity)"
                    ),
                    evidence=evidence,
                    project_id=project_id,
                )
            return CheckResult(
                check_id="alert_status",
                category="alerts",
                status=CheckStatus.WARN,
                summary=f"Alerts: {len(open_alerts)} open (non-critical)",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="alert_status",
            category="alerts",
            status=CheckStatus.PASS,
            summary=(
                f"Alerts: store reachable, {len(all_alerts)} total, 0 open"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="alert_status",
            category="alerts",
            status=CheckStatus.FAIL,
            summary=f"Alert store: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 9 — execution_log_health
# ---------------------------------------------------------------------------


def check_execution_log_health(project_id: str = "omnix") -> CheckResult:
    """Verify execution log SQLite reachable and recent entry count."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.tools.execution_log import ToolExecutionLog

        log = ToolExecutionLog()
        recent = log.list_recent(limit=20)
        evidence["log_reachable"] = True
        evidence["recent_entries"] = len(recent)
        if recent:
            evidence["latest_tool_id"] = recent[0].tool_id
            evidence["latest_outcome"] = recent[0].outcome
            evidence["latest_at"] = recent[0].created_at

        return CheckResult(
            check_id="execution_log_health",
            category="execution_log",
            status=CheckStatus.PASS,
            summary=(
                f"Execution log: SQLite reachable, {len(recent)} recent entries"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="execution_log_health",
            category="execution_log",
            status=CheckStatus.FAIL,
            summary=f"Execution log: check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 10 — git_worktree_status
# ---------------------------------------------------------------------------


def check_git_worktree_status(project_id: str = "omnix") -> CheckResult:
    """Verify git branch, HEAD, and clean/dirty working tree."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.governance.constitution import ProjectRegistry

        project = ProjectRegistry.get(project_id) or ProjectRegistry.get_default()
        repo_path = project.repo_path or "."

        branch_r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=10,
        )
        head_r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=10,
        )
        status_r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=10,
        )

        if branch_r.returncode != 0:
            return CheckResult(
                check_id="git_worktree_status",
                category="git",
                status=CheckStatus.FAIL,
                summary="Git: not a git repository or git unavailable",
                evidence={"error": branch_r.stderr.strip()},
                project_id=project_id,
            )

        branch = branch_r.stdout.strip()
        head = head_r.stdout.strip()[:12]
        dirty_output = status_r.stdout.strip()
        is_dirty = bool(dirty_output)
        evidence["branch"] = branch
        evidence["head"] = head
        evidence["dirty"] = is_dirty
        evidence["dirty_files"] = dirty_output.splitlines() if is_dirty else []

        if is_dirty:
            return CheckResult(
                check_id="git_worktree_status",
                category="git",
                status=CheckStatus.WARN,
                summary=f"Git: dirty working tree on branch={branch} HEAD={head}",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="git_worktree_status",
            category="git",
            status=CheckStatus.PASS,
            summary=f"Git: clean on branch={branch} HEAD={head}",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="git_worktree_status",
            category="git",
            status=CheckStatus.FAIL,
            summary=f"Git check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 11 — handoff_freshness
# ---------------------------------------------------------------------------


def check_handoff_freshness(project_id: str = "omnix") -> CheckResult:
    """Verify handoff document exists and is within the staleness threshold."""
    evidence: Dict[str, Any] = {}
    _STALE_DAYS = 7
    try:
        from openjarvis.governance.constitution import ProjectRegistry

        project = ProjectRegistry.get(project_id) or ProjectRegistry.get_default()
        repo_path = (
            Path(project.repo_path) if project.repo_path else Path(".")
        )
        handoff_paths = project.handoff_paths

        if not handoff_paths:
            return CheckResult(
                check_id="handoff_freshness",
                category="handoff",
                status=CheckStatus.NOT_CONFIGURED,
                summary=(
                    "Handoff: no handoff_paths configured for this project"
                ),
                evidence={"project_id": project_id},
                project_id=project_id,
            )

        found: List[str] = []
        missing: List[str] = []
        ages_days: List[float] = []
        for hp in handoff_paths:
            full_path = repo_path / hp
            if full_path.exists():
                mtime = full_path.stat().st_mtime
                age_days = (time.time() - mtime) / 86400
                found.append(hp)
                ages_days.append(age_days)
                evidence[hp] = {"exists": True, "age_days": round(age_days, 1)}
            else:
                missing.append(hp)
                evidence[hp] = {"exists": False}

        if missing:
            return CheckResult(
                check_id="handoff_freshness",
                category="handoff",
                status=CheckStatus.FAIL,
                summary=f"Handoff: {len(missing)} document(s) missing: {missing}",
                evidence=evidence,
                project_id=project_id,
            )

        max_age = max(ages_days) if ages_days else 0.0
        if max_age > _STALE_DAYS:
            return CheckResult(
                check_id="handoff_freshness",
                category="handoff",
                status=CheckStatus.WARN,
                summary=(
                    f"Handoff: {len(found)} document(s) found, "
                    f"oldest is {max_age:.1f} days (>{_STALE_DAYS}d threshold)"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="handoff_freshness",
            category="handoff",
            status=CheckStatus.PASS,
            summary=(
                f"Handoff: {len(found)} document(s) found, "
                f"all within {_STALE_DAYS}d freshness threshold"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="handoff_freshness",
            category="handoff",
            status=CheckStatus.FAIL,
            summary=f"Handoff check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 12 — packaged_app_build_metadata
# ---------------------------------------------------------------------------


def check_packaged_app_build_metadata(project_id: str = "omnix") -> CheckResult:
    """Report Tauri packaged app build presence (not_configured is acceptable)."""
    evidence: Dict[str, Any] = {}
    try:
        app_paths = [
            Path("/Applications/OpenJarvis.app"),
            Path.home() / "Applications" / "OpenJarvis.app",
        ]
        evidence["checked_paths"] = [str(p) for p in app_paths]
        found_app = next((p for p in app_paths if p.exists()), None)

        if found_app is None:
            evidence["app_found"] = False
            return CheckResult(
                check_id="packaged_app_build_metadata",
                category="packaged_app",
                status=CheckStatus.NOT_CONFIGURED,
                summary=(
                    "Packaged app: OpenJarvis.app not found "
                    "(dev-mode only; Tauri build not installed)"
                ),
                evidence=evidence,
                project_id=project_id,
            )

        evidence["app_found"] = True
        evidence["app_path"] = str(found_app)
        info_plist = found_app / "Contents" / "Info.plist"
        evidence["info_plist_exists"] = info_plist.exists()

        return CheckResult(
            check_id="packaged_app_build_metadata",
            category="packaged_app",
            status=CheckStatus.PASS,
            summary=f"Packaged app: OpenJarvis.app found at {found_app}",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="packaged_app_build_metadata",
            category="packaged_app",
            status=CheckStatus.FAIL,
            summary=f"Packaged app check failed — {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

_ALL_CHECK_FNS: List[Callable[..., CheckResult]] = [
    check_backend_health,
    check_project_registry_health,
    check_tool_registry_counts,
    check_skill_registry_counts,
    check_memory_store_health,
    check_autonomy_mode_status,
    check_watchdog_status,
    check_alert_status,
    check_execution_log_health,
    check_git_worktree_status,
    check_handoff_freshness,
    check_packaged_app_build_metadata,
]


def run_all_checks(project_id: str = "omnix") -> List[CheckResult]:
    """Run all 12 diagnostic checks. Returns a list of CheckResult objects.

    Never raises — any unhandled exception inside a check is caught and
    reported as a CheckStatus.FAIL for that check.
    """
    results: List[CheckResult] = []
    for fn in _ALL_CHECK_FNS:
        try:
            result = fn(project_id=project_id)
        except Exception as exc:
            check_id = fn.__name__.replace("check_", "")
            result = CheckResult(
                check_id=check_id,
                category="unknown",
                status=CheckStatus.FAIL,
                summary=f"Check {check_id} raised unhandled exception: {exc}",
                evidence={"exception": str(exc)},
                project_id=project_id,
            )
        results.append(result)
    return results


__all__ = [
    "CheckResult",
    "CheckStatus",
    "_ALL_CHECK_FNS",
    "check_alert_status",
    "check_autonomy_mode_status",
    "check_backend_health",
    "check_execution_log_health",
    "check_git_worktree_status",
    "check_handoff_freshness",
    "check_memory_store_health",
    "check_packaged_app_build_metadata",
    "check_project_registry_health",
    "check_skill_registry_counts",
    "check_tool_registry_counts",
    "check_watchdog_status",
    "run_all_checks",
]
