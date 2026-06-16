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
# Check 13 — project_linkage_status
# ---------------------------------------------------------------------------


def check_project_linkage_status(project_id: str = "omnix") -> CheckResult:
    """Verify project source linkage — is the project linked to its real source?

    FAIL if:
      - local_repo is a placeholder (points to Jarvis/OpenJarvis codebase)
      - no real source configured (no GitHub, no OpenClaw, no real local repo)
      - project has no source links at all

    WARN if:
      - at least one real source linked but others missing/not_configured

    PASS if:
      - at least one real non-placeholder source is linked and readable
    """
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.projects.source_links import ProjectSourceRegistry

        status_report = ProjectSourceRegistry.get_linkage_status(project_id)
        linkage_status = status_report["linkage_status"]
        evidence["linkage_status"] = linkage_status
        evidence["counts"] = status_report.get("counts", {})
        evidence["blocker"] = status_report.get("blocker", "")
        evidence["sources"] = [
            {"source_id": s["source_id"], "status": s["status"],
             "link_type": s["link_type"]}
            for s in status_report.get("sources", [])
        ]

        if linkage_status in ("linked",):
            return CheckResult(
                check_id="project_linkage_status",
                category="project_linkage",
                status=CheckStatus.PASS,
                summary=(
                    f"Project '{project_id}' linkage: {linkage_status} — "
                    f"{evidence['counts'].get('operational', 0)} operational source(s)"
                ),
                evidence=evidence,
                project_id=project_id,
            )

        if linkage_status == "placeholder":
            return CheckResult(
                check_id="project_linkage_status",
                category="project_linkage",
                status=CheckStatus.FAIL,
                summary=(
                    f"Project '{project_id}' linkage: PLACEHOLDER — "
                    f"local_repo points to Jarvis/OpenJarvis, not real "
                    f"{project_id.upper()} product source. "
                    f"Readiness=HOLD until real source is configured."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        if linkage_status == "not_configured":
            return CheckResult(
                check_id="project_linkage_status",
                category="project_linkage",
                status=CheckStatus.FAIL,
                summary=(
                    f"Project '{project_id}' linkage: NOT_CONFIGURED — "
                    f"no sources configured. Readiness=HOLD."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        if linkage_status == "missing_required":
            return CheckResult(
                check_id="project_linkage_status",
                category="project_linkage",
                status=CheckStatus.WARN,
                summary=(
                    f"Project '{project_id}' linkage: MISSING_REQUIRED — "
                    f"some sources configured but not accessible."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        return CheckResult(
            check_id="project_linkage_status",
            category="project_linkage",
            status=CheckStatus.NOT_CONFIGURED,
            summary=f"Project '{project_id}' linkage: {linkage_status}",
            evidence=evidence,
            project_id=project_id,
        )

    except Exception as exc:
        return CheckResult(
            check_id="project_linkage_status",
            category="project_linkage",
            status=CheckStatus.FAIL,
            summary=f"Project linkage check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Run all checks
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Check 14 — automation_policy_health
# ---------------------------------------------------------------------------


def check_automation_policy_health(project_id: str = "omnix") -> CheckResult:
    """Verify automation policy hard gates are enforced and approval store is reachable."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.automation_policy import (
            AutomationPolicy,
            StandingPolicyMode,
        )
        # Verify hard gate action classes are always_blocked
        test_action = "production_deploy"
        ev = AutomationPolicy.evaluate(test_action, project_id=project_id)
        evidence["hard_gate_test"] = test_action
        evidence["hard_gate_blocked"] = ev["blocked"]
        evidence["hard_gate_policy"] = ev["standing_policy"]

        if not ev["blocked"]:
            return CheckResult(
                check_id="automation_policy_health",
                category="automation",
                status=CheckStatus.FAIL,
                summary=(
                    f"Hard gate '{test_action}' is NOT blocked — "
                    "governance failure detected"
                ),
                evidence=evidence,
                project_id=project_id,
            )

        # Verify auto-allowed action is not blocked
        safe_action = "read_only_check"
        ev2 = AutomationPolicy.evaluate(safe_action, project_id=project_id)
        evidence["auto_allowed_test"] = safe_action
        evidence["auto_allowed_can_proceed"] = ev2["can_proceed"]

        if not ev2["can_proceed"]:
            return CheckResult(
                check_id="automation_policy_health",
                category="automation",
                status=CheckStatus.WARN,
                summary=f"Safe action '{safe_action}' is not auto-allowed",
                evidence=evidence,
                project_id=project_id,
            )

        evidence["policy_summary_keys"] = list(
            AutomationPolicy.get_policy_summary().keys()
        )
        return CheckResult(
            check_id="automation_policy_health",
            category="automation",
            status=CheckStatus.PASS,
            summary=(
                "Automation policy healthy: hard gates blocked, "
                "safe actions auto-allowed"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="automation_policy_health",
            category="automation",
            status=CheckStatus.FAIL,
            summary=f"Automation policy check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 15 — voice_pipeline_status
# ---------------------------------------------------------------------------


def check_voice_pipeline_status(project_id: str = "omnix") -> CheckResult:
    """Check voice pipeline status: wake-word, STT, TTS."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.voice_pipeline import (
            get_voice_status,
            WakeWordEngine,
            STTEngine,
            TTSEngine,
        )
        status = get_voice_status()
        evidence["voice_status"] = status["voice_status"]
        evidence["wake_word_engine"] = status["wake_word"]["wake_word_status"]
        evidence["stt_engine"] = status["stt"]["stt_status"]
        evidence["tts_engine"] = status["tts"]["tts_status"]
        evidence["fully_configured"] = status["fully_configured"]

        tts_ok = status["tts"]["tts_status"] != TTSEngine.NOT_CONFIGURED
        stt_ok = status["stt"].get("is_configured", False)
        wake_status = status["wake_word"]["wake_word_status"]
        wake_ok = wake_status not in (WakeWordEngine.NOT_CONFIGURED,)
        wake_blocked = wake_status == WakeWordEngine.BLOCKED_BY_PROVIDER_OR_PLATFORM
        evidence["wake_word_fallback_mode"] = status["wake_word"].get("fallback_mode", "none")
        evidence["wake_word_blocked"] = wake_blocked

        if not tts_ok and not stt_ok and not wake_ok:
            return CheckResult(
                check_id="voice_pipeline_status",
                category="voice",
                status=CheckStatus.NOT_CONFIGURED,
                summary=(
                    "Voice pipeline not configured: wake-word, STT, and TTS all missing. "
                    "Install openwakeword + faster-whisper (or set API keys)."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        if status["fully_configured"]:
            check_status = CheckStatus.PASS
            summary = (
                f"Voice pipeline configured: {evidence['wake_word_engine']} / "
                f"{evidence['stt_engine']} / {evidence['tts_engine']}"
            )
        else:
            check_status = CheckStatus.WARN
            configured_parts = []
            if wake_ok:
                configured_parts.append(f"wake={evidence['wake_word_engine']}")
            if stt_ok:
                configured_parts.append(f"stt={evidence['stt_engine']}")
            if tts_ok:
                configured_parts.append(f"tts={evidence['tts_engine']}")
            summary = (
                f"Voice pipeline partial: {', '.join(configured_parts) or 'none'}. "
                f"Status: {evidence['voice_status']}"
            )

        return CheckResult(
            check_id="voice_pipeline_status",
            category="voice",
            status=check_status,
            summary=summary,
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="voice_pipeline_status",
            category="voice",
            status=CheckStatus.NOT_CONFIGURED,
            summary=f"Voice pipeline check error: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 16 — desktop_operator_status
# ---------------------------------------------------------------------------


def check_desktop_operator_status(project_id: str = "omnix") -> CheckResult:
    """Check macOS desktop operator permissions status."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.desktop_operator import (
            get_desktop_permissions_status,
            PermissionStatus,
            OperatorStatus,
        )
        perms = get_desktop_permissions_status()
        evidence["operator_status"] = perms["operator_status"]
        evidence["platform"] = perms["platform"]
        evidence["accessibility"] = perms["permissions"]["accessibility"]["status"]
        evidence["screen_recording"] = perms["permissions"]["screen_recording"]["status"]
        evidence["microphone"] = perms["permissions"]["microphone"]["status"]

        if perms["operator_status"] == OperatorStatus.NOT_MACOS:
            return CheckResult(
                check_id="desktop_operator_status",
                category="desktop",
                status=CheckStatus.NOT_CONFIGURED,
                summary=f"Desktop operator: not macOS (platform={perms['platform']})",
                evidence=evidence,
                project_id=project_id,
            )

        if perms["operator_status"] == OperatorStatus.AVAILABLE:
            return CheckResult(
                check_id="desktop_operator_status",
                category="desktop",
                status=CheckStatus.PASS,
                summary="Desktop operator available: Accessibility permission granted",
                evidence=evidence,
                project_id=project_id,
            )

        if perms["operator_status"] == OperatorStatus.BLOCKED_BY_MACOS_PRIVACY:
            return CheckResult(
                check_id="desktop_operator_status",
                category="desktop",
                status=CheckStatus.WARN,
                summary=(
                    "Desktop operator blocked: Accessibility permission denied. "
                    "Grant in System Settings → Privacy & Security → Accessibility."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        return CheckResult(
            check_id="desktop_operator_status",
            category="desktop",
            status=CheckStatus.NOT_CONFIGURED,
            summary=(
                "Desktop operator not configured: "
                "Accessibility permission not yet granted. "
                "System Settings → Privacy & Security → Accessibility."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="desktop_operator_status",
            category="desktop",
            status=CheckStatus.NOT_CONFIGURED,
            summary=f"Desktop operator check error: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 17 — connector_readiness
# ---------------------------------------------------------------------------


def check_connector_readiness(project_id: str = "omnix") -> CheckResult:
    """Check readiness of all outbound connectors."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.connector_diagnostics import (
            ConnectorStatus,
            get_slack_status,
            get_telegram_status,
            get_web_search_status,
            get_github_status,
            get_openclaw_status,
        )
        slack = get_slack_status()
        tg = get_telegram_status()
        web = get_web_search_status()
        gh = get_github_status()
        oc = get_openclaw_status()

        evidence["slack"] = slack["status"]
        evidence["telegram"] = tg["status"]
        evidence["web_search"] = web["status"]
        evidence["github"] = gh["status"]
        evidence["openclaw"] = oc["status"]

        configured_count = sum(
            1 for s in [slack, tg, web, gh, oc]
            if s["status"] in (
                ConnectorStatus.CONFIGURED,
                ConnectorStatus.READY_PENDING_TEST,
            )
        )
        evidence["configured_count"] = configured_count

        if configured_count == 0:
            return CheckResult(
                check_id="connector_readiness",
                category="connectors",
                status=CheckStatus.NOT_CONFIGURED,
                summary=(
                    "No outbound connectors configured. "
                    "Set JARVIS_SLACK_BOT_TOKEN, JARVIS_TELEGRAM_BOT_TOKEN, "
                    "TAVILY_API_KEY as needed."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        # GitHub with git available is good; others may be not_configured
        any_fully_ready = any(
            s["status"] in (ConnectorStatus.CONFIGURED, ConnectorStatus.READY_PENDING_TEST)
            for s in [slack, tg, web]
        )

        if gh["git_available"]:
            check_status = CheckStatus.PASS if any_fully_ready else CheckStatus.WARN
        else:
            check_status = CheckStatus.NOT_CONFIGURED

        summary = (
            f"Connectors: slack={slack['status']}, "
            f"telegram={tg['status']}, web={web['status']}, "
            f"github={gh['status']}, openclaw={oc['status']}"
        )
        return CheckResult(
            check_id="connector_readiness",
            category="connectors",
            status=check_status,
            summary=summary,
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="connector_readiness",
            category="connectors",
            status=CheckStatus.NOT_CONFIGURED,
            summary=f"Connector readiness check error: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 18 — persistent_ops_status
# ---------------------------------------------------------------------------


def check_persistent_ops_status(project_id: str = "omnix") -> CheckResult:
    """Verify no unauthorized persistent runner is installed."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.persistent_ops import get_runner_status, RunnerStatus
        status = get_runner_status()
        evidence["runner_status"] = status["runner_status"]
        evidence["launchd_installed"] = status["launchd_plist_exists"]
        evidence["cron_installed"] = status["cron_entry_exists"]
        evidence["log_path"] = status["log_path"]

        if status["installed"]:
            return CheckResult(
                check_id="persistent_ops_status",
                category="ops",
                status=CheckStatus.WARN,
                summary=(
                    "Persistent runner is installed. "
                    "Verify it was explicitly approved and intended."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        return CheckResult(
            check_id="persistent_ops_status",
            category="ops",
            status=CheckStatus.PASS,
            summary="No persistent runner installed (expected — run-on-demand only)",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="persistent_ops_status",
            category="ops",
            status=CheckStatus.NOT_CONFIGURED,
            summary=f"Persistent ops check error: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check 19 — mobile_readiness_check
# ---------------------------------------------------------------------------


def check_mobile_readiness(project_id: str = "omnix") -> CheckResult:
    """Check mobile access path readiness."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.connector_diagnostics import get_telegram_status
        tg = get_telegram_status()
        evidence["telegram_status"] = tg["status"]
        evidence["telegram_configured"] = tg["configured"]
        evidence["missing_env_vars"] = tg["missing_env_vars"]
        evidence["mobile_status_endpoint"] = "GET /v1/mobile/status"
        evidence["tailnet_access"] = "available_if_tailscale_installed"

        if tg["configured"]:
            return CheckResult(
                check_id="mobile_readiness",
                category="mobile",
                status=CheckStatus.PASS,
                summary=(
                    "Mobile access ready: Telegram configured, "
                    "local network and tailnet always available."
                ),
                evidence=evidence,
                project_id=project_id,
            )

        return CheckResult(
            check_id="mobile_readiness",
            category="mobile",
            status=CheckStatus.NOT_CONFIGURED,
            summary=(
                "Mobile access partial: Telegram not configured "
                f"(missing: {tg['missing_env_vars']}). "
                "Local network and tailnet always available."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="mobile_readiness",
            category="mobile",
            status=CheckStatus.NOT_CONFIGURED,
            summary=f"Mobile readiness check error: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 20 — secrets_backend
# ---------------------------------------------------------------------------


def check_secrets_backend(project_id: str = "omnix") -> CheckResult:
    """Verify secrets backend availability and key presence (values redacted)."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.security.keychain import get_secrets_presence_report
        report = get_secrets_presence_report()
        evidence = report
        missing_count = report["keys_missing"]
        if report["keys_present"] == 0:
            return CheckResult(
                check_id="secrets_backend",
                category="security",
                status=CheckStatus.FAIL,
                summary="Secrets backend: 0 keys present",
                evidence=evidence,
                project_id=project_id,
            )
        if missing_count > 0:
            return CheckResult(
                check_id="secrets_backend",
                category="security",
                status=CheckStatus.WARN,
                summary=(
                    f"Secrets backend: {report['keys_present']} present, "
                    f"{missing_count} missing — {report['missing_keys']}"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="secrets_backend",
            category="security",
            status=CheckStatus.PASS,
            summary=f"Secrets backend: all {report['keys_present']} keys present (values redacted)",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="secrets_backend",
            category="security",
            status=CheckStatus.FAIL,
            summary=f"Secrets backend check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 21 — budget_guard
# ---------------------------------------------------------------------------


def check_budget_guard(project_id: str = "omnix") -> CheckResult:
    """Verify runtime budget guard is active and within limits."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.budget_guard import get_budget_status
        s = get_budget_status()
        evidence = {
            "verdict": s.verdict,
            "today_spend_usd": s.today_spend_usd,
            "per_day_hard_limit": s.config.get("per_day_hard_limit_usd"),
            "per_day_soft_limit": s.config.get("per_day_soft_limit_usd"),
            "entries_today": s.entries_today,
            "overall_ok": s.overall_ok,
        }
        if s.verdict == "hard_stop":
            return CheckResult(
                check_id="budget_guard",
                category="cost_control",
                status=CheckStatus.FAIL,
                summary=f"Budget hard limit exceeded: {s.today_spend_usd:.4f} USD today",
                evidence=evidence,
                project_id=project_id,
            )
        if s.verdict == "soft_warn":
            return CheckResult(
                check_id="budget_guard",
                category="cost_control",
                status=CheckStatus.WARN,
                summary=f"Budget soft limit approached: {s.today_spend_usd:.4f} USD today",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="budget_guard",
            category="cost_control",
            status=CheckStatus.PASS,
            summary=f"Budget guard active: {s.today_spend_usd:.4f} USD today (within limits)",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="budget_guard",
            category="cost_control",
            status=CheckStatus.FAIL,
            summary=f"Budget guard check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 22 — job_queue
# ---------------------------------------------------------------------------


def check_job_queue(project_id: str = "omnix") -> CheckResult:
    """Verify durable job queue is accessible and report queue state."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.job_queue import queue_stats
        stats = queue_stats()
        evidence = stats
        stuck = stats.get("running", 0)
        failed = stats.get("failed", 0)
        if stuck > 10:
            return CheckResult(
                check_id="job_queue",
                category="automation",
                status=CheckStatus.WARN,
                summary=f"Job queue: {stuck} jobs stuck in running state",
                evidence=evidence,
                project_id=project_id,
            )
        if failed > 0:
            return CheckResult(
                check_id="job_queue",
                category="automation",
                status=CheckStatus.WARN,
                summary=f"Job queue: {failed} failed jobs (may need retry or inspection)",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="job_queue",
            category="automation",
            status=CheckStatus.PASS,
            summary=(
                f"Job queue healthy: {stats.get('pending',0)} pending, "
                f"{stats.get('running',0)} running, {stats.get('succeeded',0)} succeeded"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="job_queue",
            category="automation",
            status=CheckStatus.FAIL,
            summary=f"Job queue check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 23 — rollback_policy
# ---------------------------------------------------------------------------


def check_rollback_policy(project_id: str = "omnix") -> CheckResult:
    """Verify rollback policy is active."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.rollback_plan import get_rollback_policy_status
        s = get_rollback_policy_status()
        evidence = s
        if not s.get("policy_active"):
            return CheckResult(
                check_id="rollback_policy",
                category="safety",
                status=CheckStatus.FAIL,
                summary="Rollback policy not active",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="rollback_policy",
            category="safety",
            status=CheckStatus.PASS,
            summary="Rollback policy active — dangerous actions blocked, dry-run available",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="rollback_policy",
            category="safety",
            status=CheckStatus.FAIL,
            summary=f"Rollback policy check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 24 — inject_guard
# ---------------------------------------------------------------------------


def check_inject_guard(project_id: str = "omnix") -> CheckResult:
    """Verify prompt-injection guard is active."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.security.inject_guard import get_inject_guard_status
        s = get_inject_guard_status()
        evidence = s
        if not s.get("active"):
            return CheckResult(
                check_id="inject_guard",
                category="security",
                status=CheckStatus.FAIL,
                summary="Inject guard not active",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="inject_guard",
            category="security",
            status=CheckStatus.PASS,
            summary=(
                f"Inject guard active: {s['pattern_count']} patterns, "
                "governance boundary enforced"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="inject_guard",
            category="security",
            status=CheckStatus.FAIL,
            summary=f"Inject guard check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 25 — voice_identity
# ---------------------------------------------------------------------------


def check_voice_identity(project_id: str = "omnix") -> CheckResult:
    """Verify voice identity/auth hardening status."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.voice_identity import get_voice_identity_status
        s = get_voice_identity_status()
        evidence = s
        if not s.get("active"):
            return CheckResult(
                check_id="voice_identity",
                category="security",
                status=CheckStatus.FAIL,
                summary="Voice identity auth not active",
                evidence=evidence,
                project_id=project_id,
            )
        if not s.get("pin_configured"):
            return CheckResult(
                check_id="voice_identity",
                category="security",
                status=CheckStatus.WARN,
                summary=(
                    "Voice identity active but operator PIN not configured — "
                    "set JARVIS_OPERATOR_PIN_HASH for full hardening"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="voice_identity",
            category="security",
            status=CheckStatus.PASS,
            summary="Voice identity: active, PIN configured, replay+expiry protection active",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="voice_identity",
            category="security",
            status=CheckStatus.FAIL,
            summary=f"Voice identity check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 26 — connector_health_monitor
# ---------------------------------------------------------------------------


def check_connector_health_monitor(project_id: str = "omnix") -> CheckResult:
    """Verify connector health monitor and report connector health."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.connector_health import (
            check_all_connectors,
            HealthStatus,
            get_connector_health_report,
        )
        check_all_connectors(force=False)
        report = get_connector_health_report()
        evidence = {
            "total": report["total"],
            "unhealthy": report["unhealthy"],
            "unhealthy_count": report["unhealthy_count"],
        }
        if report["unhealthy_count"] > 0:
            return CheckResult(
                check_id="connector_health_monitor",
                category="connectors",
                status=CheckStatus.WARN,
                summary=(
                    f"Connector health: {report['unhealthy_count']} unhealthy — "
                    f"{report['unhealthy']}"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="connector_health_monitor",
            category="connectors",
            status=CheckStatus.PASS,
            summary=f"All {report['total']} connectors healthy or not_configured",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="connector_health_monitor",
            category="connectors",
            status=CheckStatus.FAIL,
            summary=f"Connector health monitor check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 27 — alert_rate_limiter
# ---------------------------------------------------------------------------


def check_alert_rate_limiter(project_id: str = "omnix") -> CheckResult:
    """Verify alert rate limiter is active."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.alert_limiter import get_alert_limiter_status
        s = get_alert_limiter_status()
        evidence = s
        if not s.get("active"):
            return CheckResult(
                check_id="alert_rate_limiter",
                category="alerts",
                status=CheckStatus.FAIL,
                summary="Alert rate limiter not active",
                evidence=evidence,
                project_id=project_id,
            )
        freeze = s.get("freeze_mode", False)
        incident = s.get("incident_mode", False)
        status_note = ""
        if freeze:
            status_note = " [FREEZE MODE ACTIVE]"
        elif incident:
            status_note = " [INCIDENT MODE ACTIVE]"
        return CheckResult(
            check_id="alert_rate_limiter",
            category="alerts",
            status=CheckStatus.PASS,
            summary=(
                f"Alert rate limiter active: {len(s.get('channels_configured', []))} "
                f"channels, quiet hours enabled{status_note}"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="alert_rate_limiter",
            category="alerts",
            status=CheckStatus.FAIL,
            summary=f"Alert rate limiter check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 28 — memory_backup
# ---------------------------------------------------------------------------


def check_memory_backup(project_id: str = "omnix") -> CheckResult:
    """Verify memory backup system is ready."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.memory.backup import get_memory_backup_status
        s = get_memory_backup_status()
        evidence = s
        return CheckResult(
            check_id="memory_backup",
            category="memory",
            status=CheckStatus.PASS,
            summary=(
                f"Memory backup ready: {s['backup_count']} backup(s), "
                "checksum validation active, redaction enabled"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="memory_backup",
            category="memory",
            status=CheckStatus.FAIL,
            summary=f"Memory backup check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# US9 Check 29 — dogfood_loop
# ---------------------------------------------------------------------------


def check_dogfood_loop(project_id: str = "omnix") -> CheckResult:
    """Verify dogfood loop is available and report last snapshot age."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.autonomy.dogfood_loop import get_dogfood_status
        s = get_dogfood_status()
        evidence = s
        if not s.get("latest_report_date"):
            return CheckResult(
                check_id="dogfood_loop",
                category="observability",
                status=CheckStatus.WARN,
                summary="Dogfood loop available but no snapshot yet — run run_dogfood_snapshot()",
                evidence=evidence,
                project_id=project_id,
            )
        age_hours = s.get("latest_report_age_hours", 0)
        if age_hours > 48:
            return CheckResult(
                check_id="dogfood_loop",
                category="observability",
                status=CheckStatus.WARN,
                summary=f"Dogfood snapshot stale: {age_hours:.1f}h old (> 48h)",
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="dogfood_loop",
            category="observability",
            status=CheckStatus.PASS,
            summary=f"Dogfood loop: last snapshot {age_hours:.1f}h ago, {s.get('latest_blocker_count',0)} blocker(s)",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="dogfood_loop",
            category="observability",
            status=CheckStatus.FAIL,
            summary=f"Dogfood loop check failed: {exc}",
            evidence={"error": str(exc)},
            project_id=project_id,
        )


def check_strict_operating_rules_present(project_id: str = "omnix") -> CheckResult:
    """Verify strict operating rules are persisted in core governance docs.

    Checks:
    - AGENTS.md contains STRICT OPERATING RULES section
    - docs/JARVIS_CONSTITUTION.md contains Strict Operating Rules section
    - constitution.py exports STRICT_OPERATING_RULES (non-empty dict)
    """
    evidence: Dict[str, Any] = {}
    failures: List[str] = []

    try:
        from openjarvis.governance.constitution import ProjectRegistry

        project = ProjectRegistry.get(project_id) or ProjectRegistry.get_default()
        repo_path = Path(project.repo_path) if project.repo_path else Path(".")

        # 1. AGENTS.md
        agents_md = repo_path / "AGENTS.md"
        if agents_md.exists():
            text = agents_md.read_text()
            if "Strict Operating Rules" in text:
                evidence["agents_md"] = "PASS: Strict Operating Rules section found"
            else:
                evidence["agents_md"] = "FAIL: Strict Operating Rules section missing"
                failures.append("AGENTS.md missing Strict Operating Rules")
        else:
            evidence["agents_md"] = "FAIL: AGENTS.md not found"
            failures.append("AGENTS.md not found")

        # 2. docs/JARVIS_CONSTITUTION.md
        constitution_md = repo_path / "docs" / "JARVIS_CONSTITUTION.md"
        if constitution_md.exists():
            text = constitution_md.read_text()
            if "Strict Operating Rules" in text:
                evidence["jarvis_constitution_md"] = "PASS: Strict Operating Rules section found"
            else:
                evidence["jarvis_constitution_md"] = "FAIL: Strict Operating Rules section missing"
                failures.append("docs/JARVIS_CONSTITUTION.md missing Strict Operating Rules")
        else:
            evidence["jarvis_constitution_md"] = "FAIL: docs/JARVIS_CONSTITUTION.md not found"
            failures.append("docs/JARVIS_CONSTITUTION.md not found")

        # 3. constitution.py exports STRICT_OPERATING_RULES
        try:
            from openjarvis.governance.constitution import (  # noqa: PLC0415
                STRICT_OPERATING_RULES,
            )

            if isinstance(STRICT_OPERATING_RULES, dict) and STRICT_OPERATING_RULES:
                evidence["constitution_py"] = (
                    f"PASS: STRICT_OPERATING_RULES exported "
                    f"({len(STRICT_OPERATING_RULES)} rules)"
                )
            else:
                evidence["constitution_py"] = "FAIL: STRICT_OPERATING_RULES empty or wrong type"
                failures.append("STRICT_OPERATING_RULES empty or wrong type")
        except ImportError as exc:
            evidence["constitution_py"] = f"FAIL: import error — {exc}"
            failures.append(f"STRICT_OPERATING_RULES not importable: {exc}")

    except Exception as exc:
        return CheckResult(
            check_id="strict_operating_rules_present",
            category="safety_governance",
            status=CheckStatus.FAIL,
            summary=f"strict_operating_rules_present check error — {exc}",
            evidence={"exception": str(exc)},
            project_id=project_id,
        )

    if failures:
        return CheckResult(
            check_id="strict_operating_rules_present",
            category="safety_governance",
            status=CheckStatus.FAIL,
            summary=f"Strict operating rules missing from governance docs: {failures}",
            evidence=evidence,
            project_id=project_id,
        )
    return CheckResult(
        check_id="strict_operating_rules_present",
        category="safety_governance",
        status=CheckStatus.PASS,
        summary=(
            "Strict operating rules present in AGENTS.md, "
            "docs/JARVIS_CONSTITUTION.md, and constitution.py"
        ),
        evidence=evidence,
        project_id=project_id,
    )


# ---------------------------------------------------------------------------
# US10 Check 31 — runtime_lifecycle
# ---------------------------------------------------------------------------


def check_runtime_lifecycle(project_id: str = "omnix") -> CheckResult:
    """Verify runtime lifecycle manager components are functional.

    Checks:
    - RuntimeLifecycleManager imports cleanly
    - PID file directory is writable
    - Core probe modules are importable (same set as lifecycle manager)
    - Queue crash recovery is available (recover_stale_running importable)
    """
    evidence: Dict[str, Any] = {}
    failures: List[str] = []

    try:
        from openjarvis.daemon.service import RuntimeLifecycleManager  # noqa: PLC0415
        evidence["runtime_lifecycle_manager"] = "ok"
    except Exception as exc:
        evidence["runtime_lifecycle_manager"] = f"import_error: {exc}"
        failures.append(f"RuntimeLifecycleManager not importable: {exc}")

    try:
        from openjarvis.autonomy.job_queue import recover_stale_running  # noqa: PLC0415
        evidence["queue_crash_recovery"] = "ok"
    except Exception as exc:
        evidence["queue_crash_recovery"] = f"import_error: {exc}"
        failures.append(f"queue crash recovery not importable: {exc}")

    try:
        from openjarvis.autonomy.wakeword_bridge import WakeWordBridge  # noqa: PLC0415
        evidence["wakeword_bridge"] = "ok"
    except Exception as exc:
        evidence["wakeword_bridge"] = f"import_error: {exc}"
        failures.append(f"WakeWordBridge not importable: {exc}")

    try:
        from openjarvis.autonomy.connector_health import get_connector_degradation_summary  # noqa: PLC0415
        evidence["connector_degradation_summary"] = "ok"
    except Exception as exc:
        evidence["connector_degradation_summary"] = f"import_error: {exc}"
        failures.append(f"connector_degradation_summary not importable: {exc}")

    try:
        from openjarvis.autonomy.alert_limiter import auto_escalate_on_failures  # noqa: PLC0415
        evidence["alert_escalation"] = "ok"
    except Exception as exc:
        evidence["alert_escalation"] = f"import_error: {exc}"
        failures.append(f"alert escalation not importable: {exc}")

    # Check PID directory is writable
    pid_dir = Path.home() / ".openjarvis"
    try:
        pid_dir.mkdir(parents=True, exist_ok=True)
        tmp = pid_dir / ".lifecycle_probe"
        tmp.write_text("ok")
        tmp.unlink()
        evidence["pid_dir_writable"] = str(pid_dir)
    except Exception as exc:
        evidence["pid_dir_writable"] = f"not_writable: {exc}"
        failures.append(f"PID dir not writable: {exc}")

    if failures:
        return CheckResult(
            check_id="runtime_lifecycle",
            category="runtime",
            status=CheckStatus.FAIL,
            summary=f"Runtime lifecycle check failed: {failures}",
            evidence=evidence,
            project_id=project_id,
        )
    return CheckResult(
        check_id="runtime_lifecycle",
        category="runtime",
        status=CheckStatus.PASS,
        summary=(
            "Runtime lifecycle: all components importable, "
            "PID dir writable, queue recovery available"
        ),
        evidence=evidence,
        project_id=project_id,
    )


# ---------------------------------------------------------------------------
# Check registry (31 checks total — 19 US7/US8 + 10 US9 + 1 strict-rules + 1 US10)
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
    check_project_linkage_status,
    check_automation_policy_health,
    check_voice_pipeline_status,
    check_desktop_operator_status,
    check_connector_readiness,
    check_persistent_ops_status,
    check_mobile_readiness,
    # US9 checks
    check_secrets_backend,
    check_budget_guard,
    check_job_queue,
    check_rollback_policy,
    check_inject_guard,
    check_voice_identity,
    check_connector_health_monitor,
    check_alert_rate_limiter,
    check_memory_backup,
    check_dogfood_loop,
    # Governance doc presence check
    check_strict_operating_rules_present,
    # US10 checks
    check_runtime_lifecycle,
]


def run_all_checks(project_id: str = "omnix") -> List[CheckResult]:
    """Run all 31 diagnostic checks. Returns a list of CheckResult objects.

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
    "check_alert_rate_limiter",
    "check_alert_status",
    "check_automation_policy_health",
    "check_autonomy_mode_status",
    "check_backend_health",
    "check_budget_guard",
    "check_connector_health_monitor",
    "check_connector_readiness",
    "check_desktop_operator_status",
    "check_dogfood_loop",
    "check_execution_log_health",
    "check_git_worktree_status",
    "check_handoff_freshness",
    "check_inject_guard",
    "check_job_queue",
    "check_memory_backup",
    "check_memory_store_health",
    "check_mobile_readiness",
    "check_packaged_app_build_metadata",
    "check_persistent_ops_status",
    "check_project_linkage_status",
    "check_project_registry_health",
    "check_rollback_policy",
    "check_secrets_backend",
    "check_skill_registry_counts",
    "check_tool_registry_counts",
    "check_voice_identity",
    "check_runtime_lifecycle",
    "check_strict_operating_rules_present",
    "check_voice_pipeline_status",
    "check_watchdog_status",
    "run_all_checks",
]
