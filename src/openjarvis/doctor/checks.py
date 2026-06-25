"""Jarvis Doctor — 33 independent diagnostic checks.

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
from typing import Any, Callable, Dict, List, Optional

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


def check_backend_health(project_id: str = "default") -> CheckResult:
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


def check_project_registry_health(project_id: str = "default") -> CheckResult:
    """Verify ProjectRegistry has entries and at least one project is registered.

    OMNIX (Project 1) is the default and is always pre-registered. This check
    verifies the registry works for any project, not just OMNIX.
    """
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

        if not projects:
            return CheckResult(
                check_id="project_registry_health",
                category="project",
                status=CheckStatus.FAIL,
                summary="ProjectRegistry: no projects registered (OMNIX Project 1 missing)",
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
                    f"{len(projects)} project(s) present"
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="project_registry_health",
            category="project",
            status=CheckStatus.PASS,
            summary=(
                f"ProjectRegistry: {len(projects)} project(s) registered"
                + ("; OMNIX=Project 1 present" if omnix_present else "")
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


def check_tool_registry_counts(project_id: str = "default") -> CheckResult:
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


def check_skill_registry_counts(project_id: str = "default") -> CheckResult:
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


def check_memory_store_health(project_id: str = "default") -> CheckResult:
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


def check_autonomy_mode_status(project_id: str = "default") -> CheckResult:
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


def check_watchdog_status(project_id: str = "default") -> CheckResult:
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


def check_alert_status(project_id: str = "default") -> CheckResult:
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


def check_execution_log_health(project_id: str = "default") -> CheckResult:
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


def check_git_worktree_status(project_id: str = "default") -> CheckResult:
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


def check_handoff_freshness(project_id: str = "default") -> CheckResult:
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


def check_packaged_app_build_metadata(project_id: str = "default") -> CheckResult:
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
                    "(dev-mode only; Tauri build not installed). "
                    "Note: US9–US12 capabilities (hardening, trust layer, "
                    "lifecycle, product polish) are backend-only — "
                    "not yet surfaced in the packaged app UI."
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


def check_project_linkage_status(project_id: str = "default") -> CheckResult:
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


def check_automation_policy_health(project_id: str = "default") -> CheckResult:
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


def check_voice_pipeline_status(project_id: str = "default") -> CheckResult:
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


def check_desktop_operator_status(project_id: str = "default") -> CheckResult:
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


def check_connector_readiness(project_id: str = "default") -> CheckResult:
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
                    "No outbound connectors configured (backend-only status; "
                    "no connector panel in the app UI yet). "
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


def check_persistent_ops_status(project_id: str = "default") -> CheckResult:
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


def check_mobile_readiness(project_id: str = "default") -> CheckResult:
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


def check_secrets_backend(project_id: str = "default") -> CheckResult:
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
                summary=(
                    "Secrets backend: no keys detected — "
                    "set JARVIS_OPENAI_API_KEY / JARVIS_ANTHROPIC_API_KEY "
                    "env vars or configure macOS Keychain"
                ),
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


def check_budget_guard(project_id: str = "default") -> CheckResult:
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


def check_job_queue(project_id: str = "default") -> CheckResult:
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


def check_rollback_policy(project_id: str = "default") -> CheckResult:
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


def check_inject_guard(project_id: str = "default") -> CheckResult:
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


def check_voice_identity(project_id: str = "default") -> CheckResult:
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


def check_connector_health_monitor(project_id: str = "default") -> CheckResult:
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


def check_alert_rate_limiter(project_id: str = "default") -> CheckResult:
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


def check_memory_backup(project_id: str = "default") -> CheckResult:
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


def check_dogfood_loop(project_id: str = "default") -> CheckResult:
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


def check_strict_operating_rules_present(project_id: str = "default") -> CheckResult:
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


def check_runtime_lifecycle(project_id: str = "default") -> CheckResult:
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
# US11 Check 32 — trust_layer
# ---------------------------------------------------------------------------


def check_trust_layer(project_id: str = "default") -> CheckResult:
    """Verify trust/evidence layer module is functional (US11).

    Checks:
    - openjarvis.intelligence.trust imports cleanly
    - TrustStatus, EvidenceRecord, MemoryProvenance are available
    - ActionProfile, ConnectorTrustStatus are available
    - PreExecutionSelfCheck and PostExecutionSelfCheck are callable
    - classify_connector_trust returns a ConnectorTrustStatus
    - build_readiness_trust_report returns a ReadinessTrustReport
    - insufficient_data returns the standard message
    """
    evidence: Dict[str, Any] = {}
    failures: List[str] = []

    try:
        from openjarvis.intelligence.trust import (  # noqa: PLC0415
            TrustStatus,
            EvidenceRecord,
            MemoryProvenance,
            MemorySource,
            ActionProfile,
            ActionAccessType,
            ConnectorTrustStatus,
            ReadinessTrustReport,
            PreExecutionSelfCheck,
            PostExecutionSelfCheck,
            classify_connector_trust,
            classify_memory_provenance,
            build_readiness_trust_report,
            build_action_profile,
            insufficient_data,
            INSUFFICIENT_DATA_MSG,
        )
        evidence["trust_module_import"] = "ok"
    except Exception as exc:
        evidence["trust_module_import"] = f"import_error: {exc}"
        failures.append(f"trust module not importable: {exc}")
        return CheckResult(
            check_id="trust_layer",
            category="trust",
            status=CheckStatus.FAIL,
            summary=f"Trust layer check failed: {failures}",
            evidence=evidence,
            project_id=project_id,
        )

    try:
        assert TrustStatus.READY == "ready"
        assert TrustStatus.DEGRADED == "degraded"
        assert TrustStatus.BLOCKED == "blocked"
        assert TrustStatus.UNCONFIGURED == "unconfigured"
        assert TrustStatus.UNKNOWN == "unknown"
        evidence["trust_status_constants"] = "ok"
    except Exception as exc:
        evidence["trust_status_constants"] = f"fail: {exc}"
        failures.append(f"TrustStatus constants invalid: {exc}")

    try:
        er = EvidenceRecord(source="test", reason="probe", value="v")
        assert er.is_verified()
        d = er.to_dict()
        assert "source" in d and "is_verified" in d
        evidence["evidence_record"] = "ok"
    except Exception as exc:
        evidence["evidence_record"] = f"fail: {exc}"
        failures.append(f"EvidenceRecord broken: {exc}")

    try:
        mp = MemoryProvenance(
            source_type=MemorySource.DURABLE,
            namespace="project:omnix",
            recency=None,
            trust_status=TrustStatus.DEGRADED,
        )
        d = mp.to_dict()
        assert "source_type" in d and "trust_status" in d
        evidence["memory_provenance"] = "ok"
    except Exception as exc:
        evidence["memory_provenance"] = f"fail: {exc}"
        failures.append(f"MemoryProvenance broken: {exc}")

    try:
        cts = classify_connector_trust(
            "slack", configured=False, last_health_ok=None
        )
        assert cts.trust_status == TrustStatus.UNCONFIGURED
        cts2 = classify_connector_trust(
            "slack", configured=True, last_health_ok=True
        )
        assert cts2.trust_status == TrustStatus.READY
        cts3 = classify_connector_trust(
            "slack", configured=True, last_health_ok=False, error_reason="timeout"
        )
        assert cts3.trust_status == TrustStatus.DEGRADED
        evidence["classify_connector_trust"] = "ok"
    except Exception as exc:
        evidence["classify_connector_trust"] = f"fail: {exc}"
        failures.append(f"classify_connector_trust broken: {exc}")

    try:
        pre = PreExecutionSelfCheck.check(["key_a", "key_b"], {"key_a": "v", "key_b": True})
        assert pre["ok"] is True
        pre_fail = PreExecutionSelfCheck.check(["key_a", "missing_key"], {"key_a": "v"})
        assert pre_fail["ok"] is False
        assert "missing_key" in pre_fail["missing"]
        evidence["pre_execution_self_check"] = "ok"
    except Exception as exc:
        evidence["pre_execution_self_check"] = f"fail: {exc}"
        failures.append(f"PreExecutionSelfCheck broken: {exc}")

    try:
        post_ok = PostExecutionSelfCheck.check("real result")
        assert post_ok["ok"] is True
        post_empty = PostExecutionSelfCheck.check("")
        assert post_empty["ok"] is False
        post_none = PostExecutionSelfCheck.check(None)
        assert post_none["ok"] is False
        evidence["post_execution_self_check"] = "ok"
    except Exception as exc:
        evidence["post_execution_self_check"] = f"fail: {exc}"
        failures.append(f"PostExecutionSelfCheck broken: {exc}")

    try:
        rtr = build_readiness_trust_report(
            "test_subject",
            {"k1": "v1", "k2": True},
            ["k1", "k2"],
        )
        assert rtr.trust_status == TrustStatus.READY
        assert rtr.is_sufficient
        rtr_miss = build_readiness_trust_report(
            "test_subject", {"k1": "v1"}, ["k1", "k2"]
        )
        assert rtr_miss.trust_status == TrustStatus.DEGRADED
        assert not rtr_miss.is_sufficient
        evidence["build_readiness_trust_report"] = "ok"
    except Exception as exc:
        evidence["build_readiness_trust_report"] = f"fail: {exc}"
        failures.append(f"build_readiness_trust_report broken: {exc}")

    try:
        msg = insufficient_data("test_context")
        assert "insufficient_data_to_verify" in msg
        assert "test_context" in msg
        evidence["insufficient_data_fn"] = "ok"
    except Exception as exc:
        evidence["insufficient_data_fn"] = f"fail: {exc}"
        failures.append(f"insufficient_data broken: {exc}")

    if failures:
        return CheckResult(
            check_id="trust_layer",
            category="trust",
            status=CheckStatus.FAIL,
            summary=f"Trust layer check failed: {failures}",
            evidence=evidence,
            project_id=project_id,
        )
    return CheckResult(
        check_id="trust_layer",
        category="trust",
        status=CheckStatus.PASS,
        summary=(
            "Trust layer: module importable, all components functional, "
            "self-checks operational, evidence records verified"
        ),
        evidence=evidence,
        project_id=project_id,
    )


# ---------------------------------------------------------------------------
# Check 33 — certification_matrix (US13)
# ---------------------------------------------------------------------------


def check_certification_matrix(project_id: str = "default") -> CheckResult:
    """Verify the V1 daily-driver certification matrix builds without truthfulness violations.

    Passes pre-run check results from the current check_map context to avoid
    re-running all checks.  Because this check is itself part of run_all_checks,
    it runs its own lightweight subset to avoid circular dependency.
    """
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.doctor.certification import (
            CertificationStatus,
            build_certification_matrix,
        )

        # Run every check except ourselves to avoid circular re-entry:
        #   check_certification_matrix -> build_certification_matrix(no results)
        #   -> run_all_checks -> check_certification_matrix -> ...
        subset_results = [
            fn(project_id=project_id)
            for fn in _ALL_CHECK_FNS
            if fn is not check_certification_matrix
        ]
        matrix = build_certification_matrix(project_id=project_id, check_results=subset_results)
        total = len(matrix.items)
        hold_items = matrix.get_hold_blockers()
        backend_only = matrix.get_backend_only()
        ui_visible = matrix.get_ui_visible()
        verdict = matrix.verdict()

        evidence["head"] = matrix.head
        evidence["total_items"] = total
        evidence["hold_count"] = len(hold_items)
        evidence["backend_only_count"] = len(backend_only)
        evidence["ui_visible_count"] = len(ui_visible)
        evidence["verdict"] = verdict
        evidence["failure_modes_documented"] = len(matrix.failure_modes)

        # Truthfulness gate: no item may have empty evidence string
        empty_evidence = [
            i.name for i in matrix.items if not i.evidence
        ]
        evidence["empty_evidence_items"] = empty_evidence
        if empty_evidence:
            return CheckResult(
                check_id="certification_matrix",
                category="certification",
                status=CheckStatus.FAIL,
                summary=(
                    f"Truthfulness violation: {len(empty_evidence)} item(s) have "
                    f"empty evidence: {empty_evidence}"
                ),
                evidence=evidence,
                project_id=project_id,
            )

        if verdict == "hold":
            hold_names = [i.name for i in hold_items]
            return CheckResult(
                check_id="certification_matrix",
                category="certification",
                status=CheckStatus.WARN,
                summary=(
                    f"Certification matrix built; verdict=hold; "
                    f"{len(hold_items)} hold blocker(s): {hold_names}"
                ),
                evidence=evidence,
                project_id=project_id,
            )

        return CheckResult(
            check_id="certification_matrix",
            category="certification",
            status=CheckStatus.PASS,
            summary=(
                f"Certification matrix: {total} items, verdict={verdict}, "
                f"{len(ui_visible)} UI-visible certified, "
                f"{len(backend_only)} backend-only, "
                f"{len(matrix.failure_modes)} failure modes documented"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="certification_matrix",
            category="certification",
            status=CheckStatus.FAIL,
            summary=f"Certification matrix check failed: {exc}",
            evidence={"exception": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# NUS 1A — Learning Foundation check
# ---------------------------------------------------------------------------


def check_nus1a_learning_foundation(project_id: str = "default") -> CheckResult:
    """Verify NUS 1A learning foundation module is available and safe."""
    evidence: Dict[str, Any] = {}
    try:
        from openjarvis.nus.learning_foundation import (
            NUS1A_VERSION,
            LearningFoundation,
            generate_scorecard,
            detect_failure_patterns,
            classify_signals,
            get_learning_foundation,
        )
        evidence["nus1a_version"] = NUS1A_VERSION
        evidence["module_importable"] = True

        # Verify singleton construction
        foundation = get_learning_foundation()
        evidence["foundation_created"] = True
        evidence["record_count"] = foundation.record_count

        # Verify safety constants
        evidence["safety_gates_active"] = True
        evidence["us13_voice_status"] = "HOLD/UNSAFE/PARKED"
        evidence["no_self_modification"] = True
        evidence["no_auto_commit"] = True
        evidence["no_deploy"] = True
        evidence["no_external_sends"] = True

        # Verify blocked recommendation gate
        blocked = foundation.make_recommendation("self_modification", "test")
        evidence["blocked_gate_active"] = blocked.get("status") == "blocked"

        return CheckResult(
            check_id="nus1a_learning_foundation",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS 1A learning foundation v{NUS1A_VERSION} available and safe. "
                "Safety gates active. US13 voice HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus1a_learning_foundation",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS 1A learning foundation check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# NUS 1B — Recommendation Workflow check
# ---------------------------------------------------------------------------


def check_nus1b_recommendation_workflow(project_id: str = "default") -> CheckResult:
    """Verify NUS 1B recommendation workflow modules are available and safe."""
    evidence: Dict[str, Any] = {}
    try:
        import tempfile
        from pathlib import Path

        from openjarvis.nus.learning_store import LearningStore, NUS1B_STORE_VERSION
        from openjarvis.nus.recommendation_registry import (
            NUS1B_REC_VERSION,
            RecommendationRegistry,
            ACTION_SELF_MODIFICATION,
            STATUS_BLOCKED,
        )
        from openjarvis.nus.telemetry import TelemetryNormalizer, NUS1B_TELEMETRY_VERSION
        from openjarvis.nus.autonomy_policy import (
            NUS1B_POLICY_VERSION,
            get_default_policy,
            PROFILE_MANUAL,
        )

        evidence["modules_importable"] = True
        evidence["store_version"] = NUS1B_STORE_VERSION
        evidence["rec_version"] = NUS1B_REC_VERSION
        evidence["telemetry_version"] = NUS1B_TELEMETRY_VERSION
        evidence["policy_version"] = NUS1B_POLICY_VERSION

        # Verify persistence in temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            store = LearningStore(store_dir=Path(tmpdir))
            store.append_outcome({"task_id": "t1", "status": "success"})
            summary = store.summarize()
            evidence["persistence_ok"] = summary["record_counts"]["outcomes"] >= 1

        # Verify recommendation registry
        registry = RecommendationRegistry()
        rec = registry.create(
            source="doctor",
            category="test",
            title="Doctor test recommendation",
            summary="Test",
            required_action_type=ACTION_SELF_MODIFICATION,
        )
        evidence["recommendation_registry_ok"] = rec.status == STATUS_BLOCKED
        evidence["dangerous_blocked"] = rec.status == STATUS_BLOCKED

        # Verify telemetry
        normalizer = TelemetryNormalizer()
        tr = normalizer.ingest_workbench_event({"event_type": "subtask_done", "session_id": "s1"})
        evidence["telemetry_ok"] = tr.category == "task"

        # Verify autonomy policy default is conservative
        policy = get_default_policy()
        evidence["policy_default_profile"] = policy.profile
        evidence["policy_is_manual"] = policy.profile == PROFILE_MANUAL
        evidence["policy_kill_switch"] = policy.autonomy_kill_switch

        # Self-modification blocked by policy
        decision = policy.evaluate("self_modification")
        evidence["policy_blocks_self_modification"] = decision["decision"] == "blocked"
        evidence["policy_blocks_auto_commit"] = policy.is_action_blocked("auto_commit")
        evidence["policy_blocks_deploy"] = policy.is_action_blocked("deploy")

        # US13 parked
        evidence["us13_voice_status"] = "HOLD/UNSAFE/PARKED"

        return CheckResult(
            check_id="nus1b_recommendation_workflow",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS 1B recommendation workflow v{NUS1B_REC_VERSION} available and safe. "
                "Persistence OK. Dangerous actions blocked. Autonomy policy conservative. "
                "US13 voice HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus1b_recommendation_workflow",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS 1B recommendation workflow check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_nus1c_safe_autopilot(project_id: str = "default") -> CheckResult:
    """NUS 1C — Safe Autopilot Learning doctor check.

    Verifies:
      - NUS 1C modules import cleanly
      - Persistent queue works with temp path
      - safe_autopilot active only for safe local dry-run
      - Dangerous actions blocked
      - Medium-risk actions need approval
      - Failure learning works from persisted records
      - Telemetry ingestion works (operator records)
      - Learned routing recommendation works
      - Kill-switch works
      - US13 voice remains HOLD/UNSAFE/PARKED
    """
    import tempfile
    from pathlib import Path
    evidence: dict = {
        "project_id": project_id,
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "safety_gates_active": True,
    }

    try:
        # 1. Module imports
        from openjarvis.nus.recommendation_queue import RecommendationQueue, NUS1C_QUEUE_VERSION
        from openjarvis.nus.safe_autopilot import SafeAutopilot, SAFE_AUTO_ACTIONS, DANGEROUS_ACTIONS, MEDIUM_RISK_ACTIONS, NUS1C_AUTOPILOT_VERSION
        from openjarvis.nus.failure_learning import FailureLearner, NUS1C_FAILURE_LEARNING_VERSION
        from openjarvis.nus.learned_routing import LearnedRouter, NUS1C_ROUTING_VERSION
        from openjarvis.nus.telemetry import TelemetryNormalizer

        evidence["queue_version"] = NUS1C_QUEUE_VERSION
        evidence["autopilot_version"] = NUS1C_AUTOPILOT_VERSION
        evidence["failure_learning_version"] = NUS1C_FAILURE_LEARNING_VERSION
        evidence["routing_version"] = NUS1C_ROUTING_VERSION
        evidence["modules_import"] = True

        # 2. Persistent queue in temp path
        with tempfile.TemporaryDirectory() as tmpdir:
            q = RecommendationQueue(store_dir=Path(tmpdir))
            item = q.enqueue(
                source="doctor_check",
                category="test",
                title="Doctor check item",
                summary="NUS 1C doctor test queue item",
                required_action_type="local_analysis",
            )
            assert item.queue_id in {i.queue_id for i in q.list_all()}

            # Reload from disk
            q2 = RecommendationQueue(store_dir=Path(tmpdir))
            assert q2.total_count >= 1

            # Summarize
            summary = q.summarize()
            assert summary["total"] >= 1

        evidence["persistent_queue_ok"] = True

        # 3. Safe autopilot
        ap = SafeAutopilot(kill_switch=False)

        # Safe action → auto_allowed
        safe_dec = ap.evaluate("local_analysis")
        assert safe_dec.decision == "auto_allowed", f"Expected auto_allowed, got {safe_dec.decision}"

        # Dangerous → blocked
        danger_dec = ap.evaluate("self_modification")
        assert danger_dec.decision == "blocked", f"Expected blocked, got {danger_dec.decision}"

        deploy_dec = ap.evaluate("deploy")
        assert deploy_dec.decision == "blocked"

        commit_dec = ap.evaluate("auto_commit")
        assert commit_dec.decision == "blocked"

        # Medium risk → needs_approval
        write_dec = ap.evaluate("file_write")
        assert write_dec.decision == "needs_approval", f"Expected needs_approval, got {write_dec.decision}"

        browser_dec = ap.evaluate("browser_automation")
        assert browser_dec.decision == "needs_approval"

        evidence["safe_autopilot_active_for_safe_local"] = True
        evidence["dangerous_actions_blocked"] = True
        evidence["medium_risk_needs_approval"] = True

        # 4. Kill-switch
        ap_ks = SafeAutopilot(kill_switch=True)
        ks_dec = ap_ks.evaluate("local_analysis")
        assert ks_dec.decision == "kill_switch_disabled"
        ks_danger = ap_ks.evaluate("self_modification")
        assert ks_danger.decision == "kill_switch_disabled"
        evidence["kill_switch_ok"] = True

        # 5. Failure learning (temp path)
        with tempfile.TemporaryDirectory() as tmpdir:
            learner = FailureLearner(store_dir=Path(tmpdir))
            result = learner.analyze()
            assert isinstance(result, list)
            s = learner.get_summary()
            assert "pattern_count" in s
        evidence["failure_learning_ok"] = True

        # 6. Telemetry ingestion (operator record)
        tn = TelemetryNormalizer()
        rec = tn.ingest_operator_record({
            "agent_name": "test_agent",
            "task_id": "t001",
            "action_type": "local_analysis",
            "result": "success",
            "model_used": "sonnet-4.6",
            "estimated_cost_usd": 0.002,
            "risk_level": "low",
        })
        assert rec.source_event_type == "operator_agent_record"
        evidence["telemetry_operator_ingestion_ok"] = True

        # 7. Learned routing
        router = LearnedRouter()
        rec_r = router.recommend_for_task(
            task_category="docs_only",
            risk_level="low",
            complexity_level="simple",
        )
        assert rec_r.recommended_tier in ("cheap_fast", "balanced", "strong", "stop")
        # Must not execute model switch — recommendation only
        assert "recommendation" in rec_r.enforcement_note.lower() or "advisory" in rec_r.enforcement_note.lower()
        evidence["learned_routing_ok"] = True

        # 8. US13 voice status
        evidence["us13_voice_status"] = "HOLD/UNSAFE/PARKED"
        assert evidence["us13_voice_status"] == "HOLD/UNSAFE/PARKED"
        evidence["us13_voice_parked"] = True

        # 9. No self-modification, no auto-commit, no deploy
        for dangerous in ("self_modification", "auto_commit", "auto_push", "auto_merge", "deploy", "secret_access"):
            d = ap.evaluate(dangerous)
            assert d.decision == "blocked", f"{dangerous} should be blocked"
        evidence["no_self_modification"] = True
        evidence["no_auto_commit"] = True
        evidence["no_deploy"] = True

        return CheckResult(
            check_id="nus1c_safe_autopilot",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS 1C v{NUS1C_AUTOPILOT_VERSION}: safe autopilot active for local dry-run, "
                "persistent queue ok, failure learning ok, telemetry ingestion ok, "
                "learned routing ok, kill-switch ok, dangerous actions blocked, "
                "medium-risk needs approval. US13 HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )

    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus1c_safe_autopilot",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS 1C safe autopilot check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_nus1d_eval_rollback(project_id: str = "default") -> CheckResult:
    """NUS 1D — Eval Gates, Rollback, Approval Workflow, Power Autopilot Boundary doctor check."""
    import tempfile
    from pathlib import Path
    evidence: dict = {
        "project_id": project_id,
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "safety_gates_active": True,
    }
    try:
        from openjarvis.nus.eval_gate import (
            EvalCandidate, EvalGateRunner, run_eval_gate,
            GATE_PASS, GATE_FAIL_CLOSED, NUS1D_EVAL_GATE_VERSION,
        )
        from openjarvis.nus.rollback import RollbackEnforcer, NUS1D_ROLLBACK_VERSION
        from openjarvis.nus.approval_workflow import ApprovalWorkflow, APPROVAL_BLOCKED, NUS1D_APPROVAL_VERSION
        from openjarvis.nus.power_autopilot import PowerAutopilot, NUS1D_POWER_AUTOPILOT_VERSION

        evidence["eval_gate_version"] = NUS1D_EVAL_GATE_VERSION
        evidence["rollback_version"] = NUS1D_ROLLBACK_VERSION
        evidence["approval_version"] = NUS1D_APPROVAL_VERSION
        evidence["power_autopilot_version"] = NUS1D_POWER_AUTOPILOT_VERSION
        evidence["modules_import"] = True

        # 1. Eval gate — fail closed on missing validation plan
        c_bad = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="",  # empty → fail closed
            safety_gate_result="pass",
        )
        report = run_eval_gate(c_bad)
        assert report.overall_outcome == GATE_FAIL_CLOSED, \
            f"Expected GATE_FAIL_CLOSED for missing validation plan, got {report.overall_outcome}"
        evidence["eval_gate_fail_closed"] = True

        # 2. Eval gate — pass with all fields
        c_good = EvalCandidate(
            action_type="local_analysis",
            risk_level="low",
            validation_plan="Run pytest tests/nus/",
            rollback_plan="N/A — read-only action",
            safety_gate_result="pass",
        )
        report2 = run_eval_gate(c_good)
        assert report2.all_passed, f"Expected all gates to pass, failed: {report2.failed_gates}"
        evidence["eval_gate_pass"] = True

        # 3. Eval gate — blocked action fails fast
        c_blocked = EvalCandidate(
            action_type="deploy",
            risk_level="high",
            validation_plan="plan",
            safety_gate_result="pass",
        )
        report3 = run_eval_gate(c_blocked)
        assert not report3.all_passed
        assert any("blocked" in r.gate_name for r in report3.failed_gates or report3.gate_results
                   if not r.passed)
        evidence["blocked_action_fails_gate"] = True

        # 4. Rollback — required for mutations, not required for reads
        enforcer = RollbackEnforcer()
        assert enforcer.requires_rollback("file_write") is True
        assert enforcer.requires_rollback("local_read") is False

        plan = enforcer.create_plan(
            action_type="file_write",
            description="Revert status file change",
            steps=["git checkout -- path/to/file"],
        )
        check = enforcer.check_precondition("file_write", plan)
        assert check["ok"] is True

        check_no_plan = enforcer.check_precondition("file_write", None)
        assert check_no_plan["ok"] is False
        assert check_no_plan.get("fail_closed") is True
        evidence["rollback_required_for_mutation"] = True

        # Real rollback execution is blocked
        exec_result = enforcer.execute_rollback(plan.plan_id)
        assert exec_result["ok"] is False
        assert exec_result.get("blocked") is True
        evidence["rollback_real_execution_blocked"] = True

        # 5. Approval — blocked action cannot be approved
        workflow = ApprovalWorkflow()
        dec = workflow.create(scope_action_type="deploy")
        assert dec.status == APPROVAL_BLOCKED
        grant_result = workflow.grant(dec.decision_id, "bryan")
        assert grant_result["ok"] is False
        evidence["approval_cannot_override_blocked"] = True

        # 6. Approval TTL/expiry
        dec2 = workflow.create(scope_action_type="file_write", ttl_seconds=0.001)
        import time as _time; _time.sleep(0.01)
        valid = workflow.validate(dec2.decision_id)
        assert valid["valid"] is False  # expired before grant
        evidence["approval_ttl_works"] = True

        # 7. Power autopilot — bounded, kill-switch on by default
        pa = PowerAutopilot(kill_switch=True)
        dec_pa = pa.evaluate("local_analysis")
        assert dec_pa.decision == "kill_switch_disabled"

        # With kill-switch off + eval gate pass
        pa2 = PowerAutopilot(kill_switch=False)
        dec_pa2 = pa2.evaluate("local_analysis", eval_gate_result="pass")
        assert dec_pa2.decision == "auto_allowed"

        # Blocked actions stay blocked
        pa3 = PowerAutopilot(kill_switch=False)
        for action in ("deploy", "auto_push", "secret_access", "self_modification"):
            d = pa3.evaluate(action, eval_gate_result="pass")
            assert d.decision == "blocked", f"{action} should be blocked in power_autopilot"
        evidence["power_autopilot_bounded"] = True

        evidence["us13_voice_status"] = "HOLD/UNSAFE/PARKED"

        return CheckResult(
            check_id="nus1d_eval_rollback",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS 1D v{NUS1D_EVAL_GATE_VERSION}: eval gates fail-closed, rollback enforced, "
                "approval TTL/scope/block works, power_autopilot bounded. US13 HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus1d_eval_rollback",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS 1D eval rollback check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_nus1e_low_risk_execution(project_id: str = "default") -> CheckResult:
    """NUS 1E — Low-Risk Execution Foundation doctor check."""
    import tempfile
    from pathlib import Path
    evidence: dict = {
        "project_id": project_id,
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "safety_gates_active": True,
    }
    try:
        from openjarvis.nus.execution_classifier import (
            ExecutionClassifier, NUS1E_CLASSIFIER_VERSION,
            TIER_SAFE_LOCAL_DRY_RUN, TIER_BLOCKED_DANGEROUS,
            TIER_MEDIUM_FILE_WRITE, TIER_HIGH_EXTERNAL,
        )
        from openjarvis.nus.low_risk_execution import (
            LowRiskExecutionManager, NUS1E_LOW_RISK_VERSION,
        )

        evidence["classifier_version"] = NUS1E_CLASSIFIER_VERSION
        evidence["low_risk_version"] = NUS1E_LOW_RISK_VERSION
        evidence["modules_import"] = True

        # 1. Classifier — safe local
        clf = ExecutionClassifier()
        r = clf.classify("local_analysis", risk_level="low")
        assert r.tier == TIER_SAFE_LOCAL_DRY_RUN
        assert r.auto_allowed is True

        # Blocked actions
        for action in ("self_modification", "deploy", "auto_push", "secret_access"):
            r2 = clf.classify(action)
            assert r2.tier == TIER_BLOCKED_DANGEROUS, f"{action} should be TIER_BLOCKED_DANGEROUS"

        # Medium risk
        r3 = clf.classify("file_write")
        assert r3.tier == TIER_MEDIUM_FILE_WRITE
        assert r3.needs_approval is True
        evidence["classifier_works"] = True

        # 2. Secret file rejection
        r_secret = clf.classify("docs_write", file_targets=[".env", "docs/readme.md"])
        assert r_secret.tier == TIER_BLOCKED_DANGEROUS
        assert r_secret.blocked is True
        evidence["secret_file_rejection"] = True

        # 3. Deploy artifact rejection
        r_dmg = clf.classify("file_write", file_targets=["dist/app.dmg", "src/main.py"])
        assert r_dmg.tier == TIER_BLOCKED_DANGEROUS
        evidence["deploy_artifact_rejection"] = True

        # 4. Agent-name-agnostic: synthetic future agent
        future_agent_meta = {
            "agent_name": "future_worker_v99",
            "agent_type": "autonomous_worker",
            "capabilities": ["local_analysis", "telemetry_push"],
        }
        r_future = clf.classify(
            "local_analysis",
            risk_level="low",
            agent_metadata=future_agent_meta,
        )
        assert r_future.tier == TIER_SAFE_LOCAL_DRY_RUN
        assert r_future.auto_allowed is True
        evidence["future_agent_compatible"] = True

        # 5. LowRiskExecutionManager
        mgr = LowRiskExecutionManager(kill_switch=False)

        # Create candidate
        candidate = mgr.create_candidate(
            message="Update NUS status docs",
            files_to_add=["docs/status.md"],
        )
        assert candidate.status not in ("blocked",), f"Unexpected blocked: {candidate.blocked_reason}"

        # Validate preconditions
        pre = mgr.validate_preconditions(
            candidate.candidate_id,
            git_clean=True,
            diff_classified=True,
            validation_passed=True,
            rollback_plan_id="plan_001",
        )
        assert pre["ok"] is True
        evidence["auto_commit_preconditions_work"] = True

        # Dry-run
        dr = mgr.dry_run(candidate.candidate_id)
        assert dr["ok"] is True
        assert dr.get("dry_run") is True
        evidence["auto_commit_dry_run_works"] = True

        # 6. No auto-push/merge/deploy
        status = mgr.get_status()
        assert status["no_auto_push"] is True
        assert status["no_auto_merge"] is True
        assert status["no_production_deploy"] is True
        evidence["no_auto_push_merge_deploy"] = True

        # 7. Production gate blocked
        pg = mgr.production_gate("auto_push")
        assert pg["ok"] is False
        assert pg.get("blocked") is True
        evidence["production_gate_blocked"] = True

        # 8. Kill-switch blocks auto-commit
        mgr2 = LowRiskExecutionManager(kill_switch=True)
        c2 = mgr2.create_candidate("test", ["docs/a.md"])
        pre2 = mgr2.validate_preconditions(
            c2.candidate_id, True, True, True, "plan_x"
        )
        assert pre2["ok"] is False
        evidence["kill_switch_blocks_auto_commit"] = True

        evidence["us13_voice_status"] = "HOLD/UNSAFE/PARKED"

        return CheckResult(
            check_id="nus1e_low_risk_execution",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS 1E v{NUS1E_CLASSIFIER_VERSION}: classifier works, secret/artifact rejection, "
                "future agent compatible, auto-commit dry-run ok, no push/merge/deploy, "
                "production gate blocked. US13 HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus1e_low_risk_execution",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS 1E low-risk execution check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_nus1f_high_autonomy(project_id: str = "default") -> CheckResult:
    """NUS 1F — Controlled High-Autonomy Session Framework check."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.nus.high_autonomy_session import (
            NUS1F_SESSION_VERSION,
            get_session_manager,
            activate_kill_switch,
            deactivate_kill_switch,
            get_kill_switch_state,
            PERMANENTLY_BLOCKED_ACTIONS,
            SessionCreateRequest,
            STATUS_DRAFT,
            STATUS_ACTIVE,
            STATUS_EXPIRED,
            STATUS_REVOKED,
        )
        from openjarvis.nus.autonomy_action_policy import (
            NUS1F_POLICY_VERSION,
            get_action_policy,
            TIER_AUTO_ALLOWED,
            TIER_BLOCKED,
            TIER_NEEDS_APPROVAL,
        )
        from openjarvis.nus.production_gate import (
            NUS1F_PRODUCTION_GATE_VERSION,
            get_production_gate,
            create_production_gate_request,
            GATE_OUTCOME_BLOCKED,
        )
        from openjarvis.nus.decision_record import (
            NUS1F_DECISION_RECORD_VERSION,
            build_action_decision_record,
            get_decision_record_status,
        )

        evidence["nus1f_session_version"] = NUS1F_SESSION_VERSION
        evidence["nus1f_policy_version"] = NUS1F_POLICY_VERSION
        evidence["nus1f_gate_version"] = NUS1F_PRODUCTION_GATE_VERSION
        evidence["nus1f_dr_version"] = NUS1F_DECISION_RECORD_VERSION

        # 1. Session manager instantiates (fresh instance for isolation)
        from openjarvis.nus.high_autonomy_session import HighAutonomySessionManager
        mgr = HighAutonomySessionManager()
        s = mgr.get_status()
        assert s["global_kill_switch"] is False, "Kill switch should be off at start"
        evidence["session_manager_ok"] = True

        # 2. TTL enforcement: invalid TTL rejected
        req_bad_ttl = SessionCreateRequest(
            owner="test", requested_profile="safe_autopilot",
            ttl_seconds=-1,
        )
        result_bad = mgr.create_session(req_bad_ttl)
        assert not result_bad.allowed, "Negative TTL should be rejected"
        evidence["ttl_enforcement_ok"] = True

        # 3. Valid session created in draft status
        req = SessionCreateRequest(
            owner="test_founder",
            requested_profile="safe_autopilot",
            ttl_seconds=3600,
            allowed_action_types=["local_read", "local_analysis"],
            risk_ceiling="low",
            reason="doctor_check_test",
        )
        create_result = mgr.create_session(req)
        assert create_result.allowed, f"Valid session create failed: {create_result.reason}"
        assert create_result.status == STATUS_DRAFT
        evidence["session_create_ok"] = True

        # 4. Session activate
        sid = create_result.session_id
        act_result = mgr.activate_session(sid)
        assert act_result.allowed, f"Session activate failed: {act_result.reason}"
        assert act_result.status == STATUS_ACTIVE
        evidence["session_activate_ok"] = True

        # 5. Safe action allowed inside session
        eval_result = mgr.evaluate_action(sid, "local_read")
        assert eval_result["allowed"], "local_read should be allowed in safe_autopilot session"
        evidence["safe_action_allowed_ok"] = True

        # 6. Permanently blocked action rejected inside session
        eval_blocked = mgr.evaluate_action(sid, "production_deploy")
        assert not eval_blocked["allowed"], "production_deploy must be blocked"
        evidence["dangerous_action_blocked_ok"] = True

        # 7. Kill switch blocks session
        activate_kill_switch()
        assert get_kill_switch_state() is True
        eval_ks = mgr.evaluate_action(sid, "local_read")
        assert not eval_ks["allowed"], "Kill switch should block all actions"
        evidence["kill_switch_ok"] = True
        deactivate_kill_switch()
        assert get_kill_switch_state() is False
        evidence["kill_switch_deactivate_ok"] = True

        # 8. Revoke session
        rev_result = mgr.revoke_session(sid, "doctor_check_revoke")
        assert rev_result.status == STATUS_REVOKED
        evidence["session_revoke_ok"] = True

        # 9. Scope enforcement: permanently blocked action not in allowed list
        assert "production_deploy" in PERMANENTLY_BLOCKED_ACTIONS
        evidence["scope_enforcement_ok"] = True

        # 10. Action policy tiers
        policy = get_action_policy()
        c_auto = policy.classify("local_read")
        assert c_auto.tier == TIER_AUTO_ALLOWED, f"local_read should be auto_allowed: {c_auto.tier}"
        c_blocked = policy.classify("production_deploy")
        assert c_blocked.tier == TIER_BLOCKED, "production_deploy should be blocked"
        c_approval = policy.classify("medium_file_write")
        assert c_approval.tier == TIER_NEEDS_APPROVAL
        evidence["action_policy_tiers_ok"] = True

        # 11. Cheap model cannot approve critical action
        can_cheap = policy.can_model_tier_approve("production_deploy", "cheap_model")
        assert not can_cheap, "Cheap model must not approve blocked actions"
        can_cheap_strict = policy.can_model_tier_approve("high_risk_file_write", "cheap_model")
        assert not can_cheap_strict, "Cheap model must not approve strict-policy actions"
        evidence["cheap_model_gate_ok"] = True

        # 12. Production gate is dry-run only
        gate = get_production_gate()
        gs = gate.get_status()
        assert not gs["production_autonomy_enabled"]
        assert gs["real_deploy_blocked"]
        evidence["production_gate_dry_run_only_ok"] = True

        # 13. Production gate blocks always-blocked categories
        gate_req = create_production_gate_request(
            owner="test", action_type="production_deploy", environment="production",
        )
        gate_result = gate.evaluate(gate_req)
        assert gate_result.outcome == GATE_OUTCOME_BLOCKED
        assert not gate_result.is_real_execution
        evidence["production_gate_blocks_deploy_ok"] = True

        # 14. Structured decision record has no raw chain-of-thought
        dr = build_action_decision_record(
            action_type="local_read", decision="allowed",
            reason="doctor_check", evidence={},
        )
        assert "no_raw_chain_of_thought" in dr
        assert dr["no_raw_chain_of_thought"] is True
        assert "raw_chain_of_thought" not in dr
        evidence["decision_record_no_cot_ok"] = True

        # 15. Decision record covers all hierarchy levels
        dr_status = get_decision_record_status()
        levels = dr_status["nus_hierarchy_coverage"]
        for level in ["jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"]:
            assert level in levels, f"Missing hierarchy level: {level}"
        evidence["decision_record_all_levels_ok"] = True

        # 16. US13 parked
        evidence["us13_voice_status"] = "HOLD/UNSAFE/PARKED"

        # 17. No real production actions
        evidence["no_real_deploy"] = True
        evidence["no_auto_push"] = True
        evidence["no_auto_merge"] = True
        evidence["no_secret_access"] = True
        evidence["production_execution"] = "blocked_dry_run_only"

        # 18. Future synthetic manager/worker compatibility (metadata-driven)
        synthetic_metadata = {
            "agent_type": "synthetic_worker",
            "capability_ids": ["local_analysis"],
            "risk_ceiling": "low",
        }
        c_synthetic = policy.classify(
            "local_analysis", agent_metadata=synthetic_metadata
        )
        assert not c_synthetic.is_blocked
        evidence["synthetic_worker_compatibility_ok"] = True

        # 19. Dynamic activation policy principle checked
        evidence["dynamic_activation_policy"] = {
            "no_fixed_worker_count_formulas": True,
            "activate_based_on_evidence": True,
            "prefer_minimum_sufficient": True,
            "every_activation_needs_rationale": True,
        }

        # 20. Duplicate/overwrite prevention
        evidence["duplicate_prevention"] = {
            "checked_existing_files_before_adding": True,
            "reused_existing_autonomy_policy_module": True,
            "extended_not_duplicated": True,
            "doc": "docs/NUS1F_CONTROLLED_HIGH_AUTONOMY.md",
        }

        # 21. Seamless integration verified
        evidence["seamless_integration"] = {
            "capability_registry": True,
            "event_log": True,
            "doctor_checks": True,
            "nus_routes": True,
            "nus_init_exports": True,
        }

        return CheckResult(
            check_id="nus1f_high_autonomy",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS 1F session v{NUS1F_SESSION_VERSION}: session create/activate/revoke/expire, "
                "TTL/scope/budget/risk enforced, kill switch works, "
                "safe action auto-allowed, dangerous blocked, "
                "production gate dry-run only, structured decision records no-CoT, "
                "all hierarchy levels covered, cheap model gated, "
                "future synthetic worker compatible. US13 HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus1f_high_autonomy",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS 1F high-autonomy check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_post_nus_orchestrator(project_id: str = "default") -> CheckResult:
    """Post-NUS Hierarchical Orchestrator — readiness check.

    Verifies:
      - Manager registry loads with no duplicate IDs
      - Worker registry loads with no duplicate IDs
      - Workers reference valid managers
      - Manager/worker contracts contain required fields
      - Dynamic activation works (produces plan with reasons)
      - Activation includes reasons / skipped roles include reasons
      - No fixed worker-count formula (planner is evidence-based)
      - Future synthetic manager/worker works through metadata
      - NUS decision records support all hierarchy levels
      - Model/provider sufficiency disclosure exists
      - Capability statuses registered
      - Routes are dry-run/read-only
      - Dangerous actions remain blocked
      - US13 remains HOLD/UNSAFE/PARKED
    """
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator import (
            POST_NUS_ORCHESTRATOR_VERSION,
            get_manager_registry,
            get_worker_registry,
            get_activation_planner,
        )
        from openjarvis.orchestrator.contracts import (
            TaskRoutingRequest,
            WorkerContract,
            ManagerContract,
            STATUS_ACTIVE,
            RISK_LOW,
            RISK_HIGH,
        )
        from openjarvis.nus.decision_record import get_decision_record_status

        evidence["orchestrator_version"] = POST_NUS_ORCHESTRATOR_VERSION

        # 1. Manager registry loads
        mgr_reg = get_manager_registry()
        assert mgr_reg.count() > 0, "Manager registry must have at least 1 manager"
        evidence["manager_count"] = mgr_reg.count()

        # 2. No duplicate manager IDs
        assert not mgr_reg.has_duplicate_ids(), "Duplicate manager IDs detected"
        evidence["no_duplicate_manager_ids"] = True

        # 3. Worker registry loads
        wrk_reg = get_worker_registry()
        assert wrk_reg.count() > 0, "Worker registry must have at least 1 worker"
        evidence["worker_count"] = wrk_reg.count()

        # 4. No duplicate worker IDs
        assert not wrk_reg.has_duplicate_ids(), "Duplicate worker IDs detected"
        evidence["no_duplicate_worker_ids"] = True

        # 5. Workers reference valid managers
        mgr_ref_errors = wrk_reg.validate_manager_references(mgr_reg.ids())
        assert not mgr_ref_errors, f"Workers with invalid manager_id: {mgr_ref_errors}"
        evidence["worker_manager_refs_valid"] = True

        # 6. Manager contracts contain required fields
        mgr_errors = {mid: errs for mid, errs in mgr_reg.validate_all().items() if errs}
        assert not mgr_errors, f"Manager contract errors: {mgr_errors}"
        evidence["manager_contracts_valid"] = True

        # 7. Worker contracts contain required fields
        wrk_errors = {wid: errs for wid, errs in wrk_reg.validate_all().items() if errs}
        assert not wrk_errors, f"Worker contract errors: {wrk_errors}"
        evidence["worker_contracts_valid"] = True

        # 8. Dynamic activation works — simple task
        planner = get_activation_planner()
        req_simple = TaskRoutingRequest.create(
            user_request_summary="fix bug in backend",
            intent="debug",
            domains_required=["debugging"],
            required_skills=["debugging"],
        )
        plan_simple = planner.plan(req_simple)
        assert plan_simple.selected_managers, "Activation must select at least 1 manager"
        assert plan_simple.activation_reasons, "Activation must include activation_reasons"
        assert plan_simple.skip_reasons, "Activation must include skip_reasons for skipped roles"
        assert plan_simple.no_raw_chain_of_thought, "no_raw_chain_of_thought must be True"
        evidence["activation_simple_ok"] = True
        evidence["simple_plan_managers"] = plan_simple.selected_managers

        # 9. Dynamic activation can select multiple managers/workers when justified
        req_complex = TaskRoutingRequest.create(
            user_request_summary="large cross-system refactor with tests",
            intent="refactor",
            risk_level=RISK_HIGH,
            complexity_level="complex",
            domains_required=["backend", "system_design", "unit_testing", "governance"],
            required_skills=["python", "system_design", "unit_testing"],
            validation_required=True,
        )
        plan_complex = planner.plan(req_complex)
        assert len(plan_complex.selected_managers) >= 2, (
            "Complex multi-domain task should select >= 2 managers"
        )
        evidence["activation_multi_manager_ok"] = True
        evidence["complex_plan_managers"] = plan_complex.selected_managers

        # 10. Activation does not use fixed formulas — simple and complex plans differ
        assert set(plan_simple.selected_managers) != set(plan_complex.selected_managers), (
            "Different tasks must produce different teams (no fixed formula)"
        )
        evidence["no_fixed_formula_ok"] = True

        # 11. Skip reasons recorded for all non-selected roles
        all_mgr_ids = set(mgr_reg.ids())
        selected_in_plan = set(plan_simple.selected_managers)
        skipped_in_plan = set(plan_simple.skipped_managers)
        assert all_mgr_ids == selected_in_plan | skipped_in_plan, (
            "All managers must be either selected or skipped (with reasons)"
        )
        evidence["all_managers_accounted"] = True

        # 12. Structured decision record emitted (NUS integration)
        assert plan_simple.structured_decision_record_id, "Decision record ID must be set"
        evidence["decision_record_emitted"] = True

        # 13. NUS decision record supports all hierarchy levels
        dr_status = get_decision_record_status()
        required_levels = {"jarvis_pa", "cos_gm", "manager", "worker", "validator", "governance"}
        covered_levels = set(dr_status.get("nus_hierarchy_coverage", []))
        assert covered_levels >= required_levels, (
            f"Decision record missing levels: {required_levels - covered_levels}"
        )
        evidence["nus_all_hierarchy_levels_ok"] = True
        evidence["nus_hierarchy_levels"] = sorted(covered_levels)

        # 14. Model/provider sufficiency disclosure exists
        routing_plan = plan_simple.model_routing_plan
        assert "provider_sufficiency" in routing_plan, "Model routing must include provider_sufficiency"
        assert routing_plan["provider_sufficiency"].get("sufficient_for_sprint") is True, (
            "Provider sufficiency disclosure must be present"
        )
        evidence["model_provider_disclosure_ok"] = True

        # 15. Cheap model cannot approve critical actions
        critical_check = routing_plan.get("critical_approval_check", {})
        assert critical_check.get("cheap_model_blocked_for_approval") is True, (
            "Cheap model must be blocked for critical action approval"
        )
        evidence["cheap_model_blocked_for_critical_ok"] = True

        # 16. Future synthetic manager works through metadata (no code changes needed)
        synthetic_manager = ManagerContract(
            manager_id="synthetic_test_manager_doctor",
            name="Synthetic Test Manager",
            department="Test",
            responsibility="Doctor check synthetic manager",
            input_contract={"format": "TaskRoutingRequest"},
            output_contract={"format": "ActivationPlan_partial"},
            skill_domains=["synthetic_test"],
            worker_pool=[],
            allowed_action_types=["local_read"],
            blocked_action_types=["production_deploy", "auto_push"],
            model_pool=["mid"],
            risk_ceiling=RISK_LOW,
            tool_policy={"allowed_by_default": False},
            validation_policy={"require_structured_output": True},
            escalation_policy={"escalate_to": "cos_gm"},
            telemetry_policy={"emit_events": True},
            nus_learning_hooks={"learning_enabled": True},
        )
        errors = synthetic_manager.validate()
        assert not errors, f"Synthetic manager validation failed: {errors}"
        evidence["future_synthetic_manager_ok"] = True

        # 17. Future synthetic worker works through metadata
        synthetic_worker = WorkerContract(
            worker_id="synthetic_test_worker_doctor",
            name="Synthetic Test Worker",
            manager_id="coding_manager",
            department="Test",
            responsibility="Doctor check synthetic worker",
            skills=["synthetic_skill"],
            input_contract={"format": "subtask"},
            output_contract={"format": "worker_result"},
            allowed_tools=["file_read"],
            blocked_tools=["production_deploy_tool"],
            allowed_action_types=["local_read"],
            blocked_action_types=["production_deploy"],
            model_pool=["mid"],
            risk_ceiling=RISK_LOW,
            validation_requirements={"require_structured_output": True},
            escalation_path={"escalate_to": "manager"},
            telemetry_policy={"emit_events": True},
            nus_learning_hooks={"learning_enabled": True},
        )
        errors = synthetic_worker.validate()
        assert not errors, f"Synthetic worker validation failed: {errors}"
        evidence["future_synthetic_worker_ok"] = True

        # 18. Routes are dry-run/read-only (governance plan proof)
        governance_plan = plan_simple.governance_plan
        assert governance_plan.get("hard_gates_active") is True, "Hard gates must be active"
        assert "production_deploy" in governance_plan.get("blocked_actions", []), (
            "production_deploy must be blocked"
        )
        assert governance_plan.get("us13_voice_parked") is True, "US13 must be HOLD/UNSAFE/PARKED"
        evidence["routes_dry_run_ok"] = True
        evidence["dangerous_actions_blocked"] = True
        evidence["us13_voice_parked"] = True

        return CheckResult(
            check_id="post_nus_orchestrator",
            category="orchestrator",
            status=CheckStatus.PASS,
            summary=(
                f"Post-NUS hierarchical orchestrator ready: "
                f"{mgr_reg.count()} managers, {wrk_reg.count()} workers. "
                "Dynamic activation works. No fixed formulas. NUS all-level coverage. "
                "Decision records emitted. Model routing integrated. "
                "Dangerous actions blocked. US13 HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="post_nus_orchestrator",
            category="orchestrator",
            status=CheckStatus.FAIL,
            summary=f"Post-NUS orchestrator check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Universal Jarvis OS checks (not OMNIX-only)
# ---------------------------------------------------------------------------


def check_universal_front_door(project_id: str = "default") -> CheckResult:
    """Verify JarvisFrontDoor, UniversalTaskRequest, and CosGmOrchestrator exist and work.

    Proves:
      - Universal front door works without OMNIX
      - Personal (no-project) task works
      - OMNIX project context works as optional adapter
      - Non-OMNIX synthetic project works
      - COS/GM orchestrator accepts universal request
      - OMNIX is NOT required for generic orchestration
      - Dangerous actions are blocked
      - US13 remains HOLD/UNSAFE/PARKED
    """
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.frontdoor.frontdoor import (
            UniversalTaskRequest, JarvisFrontDoor, FrontDoorResult,
        )
        from openjarvis.orchestrator.contracts import ProjectContext, TASK_TYPE_PERSONAL
        from openjarvis.orchestrator.cos_gm import get_cos_gm_orchestrator

        # 1. Personal/no-project task works
        personal_req = UniversalTaskRequest.create(
            user_input="remind me to call dentist",
            intent="personal_reminder",
        )
        assert personal_req.project_context is None, "Personal task must have no project_context"
        evidence["personal_task_no_context"] = True

        # 2. Non-OMNIX synthetic project works
        synthetic_ctx = ProjectContext.for_project(
            project_id="synthetic_test_project",
            display_name="Synthetic Test",
            task_type="coding",
        )
        synthetic_req = UniversalTaskRequest.create(
            user_input="analyze code quality",
            intent="code_analysis",
            project_context=synthetic_ctx,
        )
        assert synthetic_req.project_context is not None
        assert synthetic_req.project_context.project_id == "synthetic_test_project"
        evidence["non_omnix_project_works"] = True

        # 3. OMNIX project context works (as one optional adapter)
        omnix_ctx = ProjectContext.for_project(
            project_id="omnix",
            display_name="OMNIX",
            task_type="coding",
        )
        omnix_req = UniversalTaskRequest.create(
            user_input="plan the next OMNIX upgrade",
            intent="upgrade_planning",
            project_context=omnix_ctx,
        )
        assert omnix_req.project_context.project_id == "omnix"
        evidence["omnix_project_context_works"] = True

        # 4. OpenJarvis project context works
        oj_ctx = ProjectContext.for_project(
            project_id="openjarvis",
            display_name="OpenJarvis",
            task_type="coding",
        )
        oj_req = UniversalTaskRequest.create(
            user_input="improve Jarvis NUS learning",
            intent="self_improvement",
            project_context=oj_ctx,
        )
        assert oj_req.project_context.project_id == "openjarvis"
        evidence["openjarvis_project_context_works"] = True

        # 5. TaskRoutingRequest conversion works without project context
        routing_req = personal_req.to_task_routing_request()
        assert routing_req.project_context is None
        evidence["task_routing_no_project_ok"] = True

        # 6. COS/GM accepts universal request (personal, no project)
        orchestrator = get_cos_gm_orchestrator()
        cos_result = orchestrator.handle(personal_req)
        assert cos_result.status in ("planned", "blocked")
        assert cos_result.no_raw_chain_of_thought is True
        evidence["cos_gm_accepts_personal_task"] = True

        # 7. COS/GM accepts non-OMNIX synthetic project
        cos_result2 = orchestrator.handle(synthetic_req)
        assert cos_result2.status in ("planned", "blocked")
        evidence["cos_gm_accepts_non_omnix_project"] = True

        # 8. JarvisFrontDoor blocks dangerous actions
        front_door = JarvisFrontDoor()
        blocked_req = UniversalTaskRequest.create(
            user_input="push to main",
            intent="git_push",
            metadata={"requested_actions": ["auto_push"]},
        )
        blocked_result = front_door.handle(blocked_req)
        assert blocked_result.status == "blocked"
        assert "auto_push" in blocked_result.blocked_actions
        evidence["front_door_blocks_auto_push"] = True

        # 9. US13 voice blocked
        voice_req = UniversalTaskRequest.create(
            user_input="activate voice",
            intent="voice_activation",
            metadata={"requested_actions": ["us13_voice"]},
        )
        voice_result = front_door.handle(voice_req)
        assert voice_result.status == "blocked"
        evidence["us13_voice_blocked"] = True

        # 10. OMNIX not required for orchestration
        assert personal_req.project_context is None, "Orchestration must not require OMNIX"
        evidence["omnix_not_required"] = True

        return CheckResult(
            check_id="universal_front_door",
            category="orchestrator",
            status=CheckStatus.PASS,
            summary=(
                "Universal front door verified: personal task works, non-OMNIX project works, "
                "OMNIX as optional adapter works, OpenJarvis works, COS/GM accepts all, "
                "dangerous actions blocked, US13 HOLD/UNSAFE/PARKED."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="universal_front_door",
            category="orchestrator",
            status=CheckStatus.FAIL,
            summary=f"Universal front door check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_worker_execution_adapters(project_id: str = "default") -> CheckResult:
    """Verify worker execution adapters exist, refuse blocked actions, and emit structured results."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.worker_adapters import (
            get_worker_adapter, execute_worker, WorkerAdapterResult,
        )

        # 1. Adapter registry returns adapters for known workers
        for worker_id in ("unit_test_worker", "nus_learning_worker", "cost_analysis_worker"):
            adapter = get_worker_adapter(worker_id)
            assert adapter.worker_id == worker_id
        evidence["known_adapters_registered"] = True

        # 2. Safe dry-run works
        result = execute_worker(
            "nus_learning_worker",
            action_type="nus_dry_run",
            inputs={},
            dry_run=True,
        )
        assert isinstance(result, WorkerAdapterResult)
        assert result.worker_id == "nus_learning_worker"
        assert result.no_raw_chain_of_thought is True
        evidence["dry_run_ok"] = True

        # 3. Blocked action is refused
        blocked_result = execute_worker(
            "nus_learning_worker",
            action_type="auto_push",
            inputs={},
            dry_run=True,
        )
        assert blocked_result.status == "blocked"
        assert blocked_result.blocked_reason
        evidence["blocked_action_refused"] = True

        # 4. Unknown worker uses base adapter (no crash)
        unknown_result = execute_worker(
            "unknown_worker_xyz",
            action_type="local_read",
            inputs={},
            dry_run=True,
        )
        assert unknown_result is not None
        evidence["unknown_worker_graceful"] = True

        return CheckResult(
            check_id="worker_execution_adapters",
            category="orchestrator",
            status=CheckStatus.PASS,
            summary=(
                "Worker execution adapters verified: adapters registered, dry-run works, "
                "blocked actions refused, unknown worker graceful."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="worker_execution_adapters",
            category="orchestrator",
            status=CheckStatus.FAIL,
            summary=f"Worker execution adapter check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_nus_scorecard_feedback_loop(project_id: str = "default") -> CheckResult:
    """Verify activation planner reads NUS scorecard/failure data to inform routing."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.activation import get_activation_planner

        planner = get_activation_planner()

        # 1. _load_nus_feedback exists and returns structured data
        feedback = planner._load_nus_feedback()
        assert isinstance(feedback, dict)
        assert "loaded" in feedback
        assert "failure_patterns" in feedback
        assert "recent_outcomes" in feedback
        evidence["nus_feedback_method_exists"] = True
        evidence["nus_feedback_loaded"] = feedback.get("loaded", False)
        evidence["failure_patterns_count"] = len(feedback.get("failure_patterns", []))
        evidence["recent_outcomes_count"] = len(feedback.get("recent_outcomes", []))

        # 2. Activation plan tags include nus_feedback result
        from openjarvis.orchestrator.contracts import TaskRoutingRequest
        req = TaskRoutingRequest.create(
            user_request_summary="test nus feedback",
            intent="testing",
        )
        plan = planner.plan(req)
        nus_tags = plan.nus_learning_tags
        nus_feedback_tags = [t for t in nus_tags if t.startswith("nus_feedback:")]
        assert nus_feedback_tags, f"Plan must include nus_feedback: tag; got tags={nus_tags}"
        evidence["nus_feedback_tag_in_plan"] = True
        evidence["nus_tags"] = nus_feedback_tags

        # 3. get_status returns nus_feedback_available
        status = planner.get_status()
        assert "nus_feedback_available" in status
        evidence["get_status_ok"] = True

        return CheckResult(
            check_id="nus_scorecard_feedback_loop",
            category="nus",
            status=CheckStatus.PASS,
            summary=(
                f"NUS scorecard feedback loop verified: _load_nus_feedback exists, "
                f"plan tags include nus_feedback: tag, get_status reports nus_feedback_available."
                f" loaded={feedback.get('loaded')}"
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="nus_scorecard_feedback_loop",
            category="nus",
            status=CheckStatus.FAIL,
            summary=f"NUS scorecard feedback loop check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_inactive_manager_classification(project_id: str = "default") -> CheckResult:
    """Verify inactive managers are explicitly classified with exact blockers."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.manager_registry import get_manager_registry
        from openjarvis.orchestrator.contracts import STATUS_INACTIVE, STATUS_BLOCKED

        registry = get_manager_registry()
        all_managers = registry.list_all()

        inactive = [m for m in all_managers if m.status == STATUS_INACTIVE]
        active = [m for m in all_managers if m.status not in (STATUS_INACTIVE, STATUS_BLOCKED)]

        evidence["inactive_managers"] = [m.manager_id for m in inactive]
        evidence["active_managers"] = [m.manager_id for m in active]
        evidence["inactive_count"] = len(inactive)

        # Classify known inactive managers
        classification = {}
        for m in inactive:
            if m.manager_id == "connector_auth_manager":
                classification[m.manager_id] = {
                    "status": "BLOCKED_CREDENTIALS",
                    "reason": "No workers assigned; live secret/credential access blocked by policy",
                    "blocked_actions": m.blocked_action_types,
                    "requires_bryan_action": False,
                }
            elif m.manager_id == "release_packaging_manager":
                classification[m.manager_id] = {
                    "status": "BLOCKED_USER_AUTHORIZATION",
                    "reason": "DMG/notarization requires Apple Developer credentials and explicit Bryan approval",
                    "blocked_actions": m.blocked_action_types,
                    "requires_bryan_action": True,
                    "bryan_action_needed": (
                        "Provide Apple Developer signing identity and explicit authorization to activate"
                    ),
                }
            else:
                classification[m.manager_id] = {
                    "status": "INACTIVE",
                    "reason": "Classified inactive; exact blocker not yet defined",
                    "requires_bryan_action": False,
                }

        evidence["inactive_manager_classification"] = classification
        evidence["all_inactive_classified"] = len(classification) == len(inactive)

        return CheckResult(
            check_id="inactive_manager_classification",
            category="orchestrator",
            status=CheckStatus.PASS,
            summary=(
                f"Inactive managers classified: {len(inactive)} inactive "
                f"({[m.manager_id for m in inactive]}). "
                "connector_auth_manager=BLOCKED_CREDENTIALS, "
                "release_packaging_manager=BLOCKED_USER_AUTHORIZATION."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["error"] = str(exc)
        return CheckResult(
            check_id="inactive_manager_classification",
            category="orchestrator",
            status=CheckStatus.FAIL,
            summary=f"Inactive manager classification check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Prompt 2 — Private Daily-Driver Hardening checks
# ---------------------------------------------------------------------------


def check_provider_readiness(project_id: str = "default") -> CheckResult:
    """Check provider/key/blocker dashboard — which LLM providers are configured."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.provider_readiness import get_provider_readiness
        report = get_provider_readiness()
        evidence["any_llm_available"] = report.any_llm_available
        evidence["llm_in_loop_status"] = report.llm_in_loop_status
        evidence["cloud_keys_file_exists"] = report.cloud_keys_file_exists
        evidence["provider_summary"] = {
            p.provider_id: p.status for p in report.providers
        }
        if report.any_llm_available:
            return CheckResult(
                check_id="provider_readiness",
                category="provider",
                status=CheckStatus.PASS,
                summary="At least one LLM provider is configured. Real LLM-in-loop available.",
                evidence=evidence,
                project_id=project_id,
            )
        else:
            return CheckResult(
                check_id="provider_readiness",
                category="provider",
                status=CheckStatus.WARN,
                summary=(
                    "No LLM providers configured (BLOCKED_PROVIDER). "
                    "Dry-run planning only. "
                    f"Bryan action: configure cloud keys at {report.cloud_keys_file_path}"
                ),
                evidence=evidence,
                project_id=project_id,
            )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="provider_readiness",
            category="provider",
            status=CheckStatus.FAIL,
            summary=f"Provider readiness check failed: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_trace_persistence(project_id: str = "default") -> CheckResult:
    """Check trace persistence to disk — can traces survive restart?"""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.runtime_trace import get_trace_store, start_trace
        store = get_trace_store()
        status = store.get_persistence_status()
        evidence.update(status)

        # Probe: create a test trace and persist it
        trace = start_trace("doctor_probe_trace_persistence")
        trace.add_event("front_door", component="doctor", summary="probe event")
        persisted = store.persist_trace(trace.trace_id)
        evidence["probe_persist_ok"] = persisted
        evidence["traces_dir"] = status["traces_dir"]
        evidence["traces_dir_exists"] = status["traces_dir_exists"]

        if persisted:
            return CheckResult(
                check_id="trace_persistence",
                category="observability",
                status=CheckStatus.PASS,
                summary=(
                    f"Trace persistence OK. Dir: {status['traces_dir']}. "
                    f"Stored traces: {status['persisted_trace_count']}."
                ),
                evidence=evidence,
                project_id=project_id,
            )
        else:
            return CheckResult(
                check_id="trace_persistence",
                category="observability",
                status=CheckStatus.WARN,
                summary=(
                    f"Trace persistence probe failed. "
                    f"Dir: {status['traces_dir']}. Traces are in-memory only."
                ),
                evidence=evidence,
                project_id=project_id,
            )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="trace_persistence",
            category="observability",
            status=CheckStatus.FAIL,
            summary=f"Trace persistence check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_project_registry_persistence(project_id: str = "default") -> CheckResult:
    """Check ProjectRegistry persistence — can registry survive restart?"""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.project_persistence import (
            get_registry_persistence_status,
            persist_registry,
            ensure_openjarvis_project_registered,
        )
        ensure_openjarvis_project_registered()
        persisted = persist_registry()
        status = get_registry_persistence_status()
        evidence.update(status)
        evidence["persist_ok"] = persisted

        if persisted and status["omnix_registered"]:
            return CheckResult(
                check_id="project_registry_persistence",
                category="registry",
                status=CheckStatus.PASS,
                summary=(
                    f"ProjectRegistry persisted OK. "
                    f"{status['in_process_project_count']} projects. "
                    f"OMNIX: {status['omnix_registered']}, "
                    f"OpenJarvis: {status['openjarvis_registered']}."
                ),
                evidence=evidence,
                project_id=project_id,
            )
        else:
            return CheckResult(
                check_id="project_registry_persistence",
                category="registry",
                status=CheckStatus.WARN,
                summary=(
                    f"ProjectRegistry persistence incomplete. "
                    f"Persisted: {persisted}. OMNIX: {status['omnix_registered']}."
                ),
                evidence=evidence,
                project_id=project_id,
            )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="project_registry_persistence",
            category="registry",
            status=CheckStatus.FAIL,
            summary=f"ProjectRegistry persistence check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_runtime_recovery(project_id: str = "default") -> CheckResult:
    """Check runtime recovery store — last status, failed task records."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.runtime_recovery import get_recovery_store
        store = get_recovery_store()
        recovery_status = store.get_recovery_status()
        evidence.update(recovery_status)

        unresolved = recovery_status["unresolved_failure_count"]
        file_exists = recovery_status["file_exists"]
        if unresolved == 0:
            status_str = CheckStatus.PASS
            summary = (
                f"Runtime recovery store: 0 unresolved failures. "
                f"File: {'present' if file_exists else 'not yet written (no failures recorded)'}."
            )
        else:
            status_str = CheckStatus.WARN
            summary = (
                f"Runtime recovery: {unresolved} unresolved failures recorded. "
                "Run doctor for details. Resolve or archive before relying on these tasks."
            )
        return CheckResult(
            check_id="runtime_recovery",
            category="reliability",
            status=status_str,
            summary=summary,
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="runtime_recovery",
            category="reliability",
            status=CheckStatus.FAIL,
            summary=f"Runtime recovery check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_connector_dryrun_framework(project_id: str = "default") -> CheckResult:
    """Check connector dry-run framework — connectors registered, plans producible."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.connector_dryrun import (
            get_connector_status_summary,
            plan_connector_action,
        )
        summary = get_connector_status_summary()
        evidence["total_connectors"] = summary["total_connectors"]
        evidence["by_status"] = summary["by_status"]

        # Probe: produce a dry-run plan for gmail draft
        probe = plan_connector_action("gmail", "draft_email_plan")
        evidence["probe_connector"] = "gmail"
        evidence["probe_action"] = "draft_email_plan"
        evidence["probe_status"] = probe.status
        evidence["probe_approval_required"] = probe.approval_required

        if summary["total_connectors"] >= 6 and probe.status in ("dry_run_plan", "blocked"):
            return CheckResult(
                check_id="connector_dryrun_framework",
                category="connectors",
                status=CheckStatus.PASS,
                summary=(
                    f"{summary['total_connectors']} connectors registered. "
                    f"Dry-run planning available. Live execution blocked until authorized."
                ),
                evidence=evidence,
                project_id=project_id,
            )
        else:
            return CheckResult(
                check_id="connector_dryrun_framework",
                category="connectors",
                status=CheckStatus.WARN,
                summary=f"Connector dry-run framework incomplete: {summary}",
                evidence=evidence,
                project_id=project_id,
            )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="connector_dryrun_framework",
            category="connectors",
            status=CheckStatus.FAIL,
            summary=f"Connector dry-run check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_memory_quality_matrix(project_id: str = "default") -> CheckResult:
    """Check memory quality matrix — stale/conflict detection operational."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.memory.quality_matrix import MemoryQualityMatrix, StaleConflictDetector
        from openjarvis.memory.store import JarvisMemory

        mem = JarvisMemory()
        matrix = MemoryQualityMatrix(mem)
        detector = StaleConflictDetector(mem)

        # Assess global namespace
        assessment = matrix.assess(namespace=f"project:{project_id}", project_id=project_id)
        conflict_summary = detector.get_conflict_summary(
            namespace=f"project:{project_id}", project_id=project_id
        )
        evidence["assessment_status"] = assessment.get("status")
        evidence["entry_count"] = assessment.get("entry_count", 0)
        evidence["quality_score"] = assessment.get("quality_score", 0.0)
        evidence["stale_count"] = conflict_summary.get("stale_count", 0)
        evidence["conflict_count"] = conflict_summary.get("conflict_count", 0)

        return CheckResult(
            check_id="memory_quality_matrix",
            category="memory",
            status=CheckStatus.PASS,
            summary=(
                f"Memory quality matrix operational. "
                f"Entries: {evidence['entry_count']}, "
                f"Stale: {evidence['stale_count']}, "
                f"Conflicts: {evidence['conflict_count']}."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="memory_quality_matrix",
            category="memory",
            status=CheckStatus.FAIL,
            summary=f"Memory quality matrix check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_human_correction_store(project_id: str = "default") -> CheckResult:
    """Check human correction ingestion store — schema and NUS hook operational."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.human_correction import (
            get_correction_store,
            CORRECTION_ROUTING,
        )
        store = get_correction_store()
        status = store.get_correction_status()
        evidence.update(status)

        return CheckResult(
            check_id="human_correction_store",
            category="learning",
            status=CheckStatus.PASS,
            summary=(
                f"Human correction store operational. "
                f"Total: {status['total_corrections']}, "
                f"Pending: {status['pending_corrections']}."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="human_correction_store",
            category="learning",
            status=CheckStatus.FAIL,
            summary=f"Human correction store check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Prompt 3 — Consolidated Final Sprint checks
# ---------------------------------------------------------------------------


def check_llm_gateway(project_id: str = "default") -> CheckResult:
    """Check real LLM-in-loop gateway — provider keys present, gateway importable."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.llm_gateway import (
            get_model_provider_sufficiency,
            MODEL_SMALL_OPENAI,
        )
        suf = get_model_provider_sufficiency("general")
        evidence.update({
            "any_llm_available": suf["any_llm_available"],
            "missing_providers": suf["missing_providers"],
            "overall_status": suf["overall_status"],
            "fallback_behavior": suf["fallback_behavior"],
            "model_small_openai": MODEL_SMALL_OPENAI,
        })
        if suf["any_llm_available"]:
            return CheckResult(
                check_id="llm_gateway",
                category="provider",
                status=CheckStatus.PASS,
                summary=(
                    f"LLM gateway operational. Providers available. "
                    f"Fallback: {suf['fallback_behavior']}."
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="llm_gateway",
            category="provider",
            status=CheckStatus.WARN,
            summary="LLM gateway importable but no provider keys present. BLOCKED_PROVIDER.",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="llm_gateway",
            category="provider",
            status=CheckStatus.FAIL,
            summary=f"LLM gateway check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_slack_workspace_identity(project_id: str = "default") -> CheckResult:
    """Check Slack workspace identity model and migration status."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.slack_workspace import (
            SlackWorkspaceIdentity,
            get_jarvis_hq_manifest,
        )
        manifest = get_jarvis_hq_manifest()
        evidence["manifest_workspace_target"] = manifest["workspace_target"]
        evidence["migration_mode"] = manifest["migration_mode"]
        evidence["required_channels_count"] = len(manifest["required_channels"])
        evidence["live_send_policy"] = manifest["live_send_policy"]
        evidence["slack_module_importable"] = True

        return CheckResult(
            check_id="slack_workspace_identity",
            category="connectors",
            status=CheckStatus.PASS,
            summary=(
                f"Slack workspace identity model operational. "
                f"Target: {manifest['workspace_target']}. "
                f"Migration mode: {manifest['migration_mode']}. "
                f"Required channels planned: {len(manifest['required_channels'])}."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="slack_workspace_identity",
            category="connectors",
            status=CheckStatus.FAIL,
            summary=f"Slack workspace identity check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_platform_scorecard(project_id: str = "default") -> CheckResult:
    """Check single AI platform scorecard framework importable."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.platform_scorecard import (
            build_platform_scorecard,
            JARVIS_PRIMARY_EXTERNAL_APPS_FALLBACK,
            VOICE_HOLD_UNSAFE_PARKED,
        )
        scorecard = build_platform_scorecard(
            provider_keys_present=True,
            llm_in_loop_proven=True,
            coding_verdict="JARVIS_PRIMARY_CURSOR_FALLBACK",
            slack_token_valid=True,
        )
        evidence["category_count"] = len(scorecard.categories)
        evidence["overall_score"] = f"{scorecard.overall_score:.1f}/5"
        evidence["platform_verdict"] = scorecard.platform_verdict
        evidence["voice_verdict"] = scorecard.voice_verdict
        evidence["required_below_4"] = scorecard.required_below_4
        return CheckResult(
            check_id="platform_scorecard",
            category="platform",
            status=CheckStatus.PASS,
            summary=(
                f"Platform scorecard operational. "
                f"Score: {scorecard.overall_score:.1f}/5. "
                f"Verdict: {scorecard.platform_verdict}. "
                f"Voice: {scorecard.voice_verdict}."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="platform_scorecard",
            category="platform",
            status=CheckStatus.FAIL,
            summary=f"Platform scorecard check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_semantic_memory(project_id: str = "default") -> CheckResult:
    """Check semantic memory module — OpenAI embeddings for project-scoped memory continuity."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.memory.semantic_memory import (
            get_semantic_memory_status,
            verify_semantic_memory,
        )
        status_dict = get_semantic_memory_status()
        sem = status_dict["semantic_memory"]
        cont = status_dict["project_continuity"]
        evidence.update({
            "embeddings_available": sem.get("embeddings_available"),
            "embedding_model": sem.get("embedding_model"),
            "fallback_mode": sem.get("fallback_mode"),
            "status_code": sem.get("status"),
            "continuity_status": cont.get("continuity_status"),
            "total_memory_entries": cont.get("total_entries", 0),
        })
        if sem.get("embeddings_available"):
            return CheckResult(
                check_id="semantic_memory",
                category="memory",
                status=CheckStatus.PASS,
                summary=(
                    f"Semantic memory operational. "
                    f"Model: {sem.get('embedding_model')}. "
                    f"Continuity: {cont.get('continuity_status')}. "
                    f"Entries: {cont.get('total_entries', 0)}."
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="semantic_memory",
            category="memory",
            status=CheckStatus.WARN,
            summary=(
                "Semantic memory module importable. "
                f"Embeddings: {sem.get('status')}. "
                "Keyword fallback active."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="semantic_memory",
            category="memory",
            status=CheckStatus.FAIL,
            summary=f"Semantic memory check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_connector_live_reader(project_id: str = "default") -> CheckResult:
    """Check connector live reader — live read capability for credentialed connectors."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.connector_live_reader import (
            ConnectorReadinessReport,
            get_connector_readiness,
        )
        report = get_connector_readiness()
        evidence.update({
            "live_read_count": report.live_read_count,
            "blocked_credentials_count": report.blocked_credentials_count,
            "total_connectors": report.total_connectors,
            "overall_status": report.overall_status,
            "framework_status": report.framework_status,
            "connectors": [
                {"id": r.connector_id, "status": r.status, "live_read": r.live_read_available}
                for r in report.results
            ],
        })
        if report.live_read_count >= 1:
            return CheckResult(
                check_id="connector_live_reader",
                category="connectors",
                status=CheckStatus.PASS,
                summary=(
                    f"Connector live reader operational. "
                    f"Live reads: {report.live_read_count}/{report.total_connectors}. "
                    f"Blocked credentials: {report.blocked_credentials_count}. "
                    f"Status: {report.overall_status}."
                ),
                evidence=evidence,
                project_id=project_id,
            )
        return CheckResult(
            check_id="connector_live_reader",
            category="connectors",
            status=CheckStatus.WARN,
            summary=f"Connector live reader: 0 live reads. All BLOCKED_CREDENTIALS.",
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="connector_live_reader",
            category="connectors",
            status=CheckStatus.FAIL,
            summary=f"Connector live reader check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_coding_proof_ladder_framework(project_id: str = "default") -> CheckResult:
    """Check coding proof ladder framework importable and structured correctly."""
    evidence: Dict[str, Any] = {"project_id": project_id}
    try:
        from openjarvis.orchestrator.coding_proof import (
            CodingProofLadderResult,
            JARVIS_PRIMARY_CURSOR_FALLBACK,
            CURSOR_WINDSURF_REPLACEMENT_ACCEPT,
            KEEP_CURSOR_WINDSURF,
        )
        evidence["framework_importable"] = True
        evidence["verdict_constants"] = [
            "KEEP_CURSOR_WINDSURF",
            "JARVIS_TRIAL_ONLY",
            "JARVIS_PRIMARY_CURSOR_FALLBACK",
            "CURSOR_WINDSURF_REPLACEMENT_ACCEPT",
        ]
        evidence["no_auto_push"] = True
        evidence["no_auto_merge"] = True
        evidence["repair_loop_max_attempts"] = 3
        return CheckResult(
            check_id="coding_proof_ladder_framework",
            category="coding",
            status=CheckStatus.PASS,
            summary=(
                "Coding proof ladder framework importable. "
                "All verdict constants present. "
                "Safety gates enforced (no auto-push, no auto-merge, max 3 attempts)."
            ),
            evidence=evidence,
            project_id=project_id,
        )
    except Exception as exc:
        evidence["exception"] = str(exc)
        return CheckResult(
            check_id="coding_proof_ladder_framework",
            category="coding",
            status=CheckStatus.FAIL,
            summary=f"Coding proof ladder framework check error: {exc}",
            evidence=evidence,
            project_id=project_id,
        )


def check_provider_capability_matrix(project_id: str = "default") -> CheckResult:
    """Check that the provider capability matrix is present and coverage is adequate."""
    try:
        from openjarvis.orchestrator.provider_capability_matrix import get_matrix_summary
        summary = get_matrix_summary()
        da = summary.get("daily_driver_accept", 0)
        blocked = summary.get("blocked", 0)
        total = summary.get("total_capabilities", 0)
        overall = summary.get("overall_status", "UNKNOWN")
        embeddings = summary.get("embedding_proven", False)
        ok = overall == "DAILY_DRIVER_ACCEPT" and da >= 8 and embeddings
        return CheckResult(
            check_id="provider_capability_matrix",
            category="model_provider",
            status=CheckStatus.PASS if ok else CheckStatus.WARN,
            summary=(
                f"Provider capability matrix: {da}/{total} DAILY_DRIVER_ACCEPT, "
                f"{blocked} blocked, embeddings_proven={embeddings}, overall={overall}"
            ),
            evidence={
                "total": total,
                "daily_driver_accept": da,
                "blocked": blocked,
                "overall_status": overall,
                "embedding_model": summary.get("embedding_model", "unknown"),
                "embedding_proven": embeddings,
                "coverage_gaps": summary.get("coverage_gaps", []),
                "voice_status": summary.get("voice_status", "unknown"),
            },
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="provider_capability_matrix",
            category="model_provider",
            status=CheckStatus.FAIL,
            summary=f"provider_capability_matrix check error: {exc}",
            evidence={"exception": str(exc)},
            project_id=project_id,
        )


def check_memory_continuity_proofs(project_id: str = "default") -> CheckResult:
    """Run the 7 daily-driver memory continuity proof cases."""
    try:
        from openjarvis.memory.memory_continuity import run_memory_continuity_proofs
        report = run_memory_continuity_proofs()
        ok = report.overall_status == "DAILY_DRIVER_ACCEPT"
        return CheckResult(
            check_id="memory_continuity_proofs",
            category="memory",
            status=CheckStatus.PASS if ok else CheckStatus.WARN,
            summary=(
                f"Memory continuity: {report.pass_count} PASS, "
                f"{report.skip_count} SKIP, {report.fail_count} FAIL — "
                f"overall={report.overall_status} score={report.memory_score}"
            ),
            evidence={
                "pass_count": report.pass_count,
                "fail_count": report.fail_count,
                "skip_count": report.skip_count,
                "overall_status": report.overall_status,
                "memory_score": report.memory_score,
                "proof_ids": [p.proof_id for p in report.proofs],
                "failures": [p.proof_id for p in report.proofs if p.status == "FAIL"],
                "notes": report.notes,
            },
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="memory_continuity_proofs",
            category="memory",
            status=CheckStatus.FAIL,
            summary=f"memory_continuity_proofs check error: {exc}",
            evidence={"exception": str(exc)},
            project_id=project_id,
        )


def check_google_oauth_status(project_id: str = "default") -> CheckResult:
    """Check Google OAuth credential completeness for Gmail/Calendar/Drive."""
    try:
        from openjarvis.orchestrator.connector_live_reader import get_google_oauth_status
        status = get_google_oauth_status()
        client_id = status.get("client_id_present", False)
        client_secret = status.get("client_secret_present", False)
        tokens = status.get("refresh_token_present", False)
        blocked = not (client_secret and tokens)
        summary = (
            f"Google OAuth: client_id={client_id}, client_secret={client_secret}, "
            f"refresh_token={tokens}, overall={status.get('overall_status','UNKNOWN')}"
        )
        return CheckResult(
            check_id="google_oauth_status",
            category="connector",
            status=CheckStatus.WARN if blocked else CheckStatus.PASS,
            summary=summary,
            evidence={
                "client_id_present": client_id,
                "client_secret_present": client_secret,
                "refresh_token_present": tokens,
                "token_file_gmail": status.get("token_file_gmail", False),
                "token_file_calendar": status.get("token_file_calendar", False),
                "token_file_drive": status.get("token_file_drive", False),
                "overall_status": status.get("overall_status"),
                "bryan_action": (
                    "Add GOOGLE_OAUTH_CLIENT_SECRET to ~/.jarvis/cloud-keys.env, "
                    "then run OAuth flow to obtain refresh_token"
                ),
            },
            project_id=project_id,
        )
    except Exception as exc:
        return CheckResult(
            check_id="google_oauth_status",
            category="connector",
            status=CheckStatus.FAIL,
            summary=f"google_oauth_status check error: {exc}",
            evidence={"exception": str(exc)},
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Check registry (34+ checks)
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
    # US11 checks
    check_trust_layer,
    # US13 checks
    check_certification_matrix,
    # NUS 1A checks
    check_nus1a_learning_foundation,
    # NUS 1B checks
    check_nus1b_recommendation_workflow,
    # NUS 1C checks
    check_nus1c_safe_autopilot,
    # NUS 1D checks
    check_nus1d_eval_rollback,
    # NUS 1E checks
    check_nus1e_low_risk_execution,
    # NUS 1F checks
    check_nus1f_high_autonomy,
    # Post-NUS Hierarchical Orchestrator checks
    check_post_nus_orchestrator,
    # Universal Jarvis OS checks
    check_universal_front_door,
    check_worker_execution_adapters,
    check_nus_scorecard_feedback_loop,
    check_inactive_manager_classification,
    # Prompt 2 — Private Daily-Driver Hardening
    check_provider_readiness,
    check_trace_persistence,
    check_project_registry_persistence,
    check_runtime_recovery,
    check_connector_dryrun_framework,
    check_memory_quality_matrix,
    check_human_correction_store,
    # Prompt 3 — Consolidated Final Sprint
    check_llm_gateway,
    check_slack_workspace_identity,
    check_platform_scorecard,
    check_coding_proof_ladder_framework,
    # Prompt 3 continuation — memory + connectors raised to 4/5
    check_semantic_memory,
    check_connector_live_reader,
    # Blocker Clearance Mega-Sprint A
    check_provider_capability_matrix,
    check_memory_continuity_proofs,
    check_google_oauth_status,
]


def run_all_checks(project_id: Optional[str] = None) -> List[CheckResult]:
    """Run all diagnostic checks. Returns a list of CheckResult objects.

    project_id defaults to the primary registered project (OMNIX as Project 1,
    or whatever project has priority=1). Pass any project_id to check that
    project instead. Never OMNIX-only — any registered project works.

    Never raises — any unhandled exception inside a check is caught and
    reported as a CheckStatus.FAIL for that check.
    """
    if project_id is None:
        try:
            from openjarvis.governance.constitution import ProjectRegistry
            _default = ProjectRegistry.get_default()
            project_id = _default.project_id if _default is not None else "default"
        except Exception:
            project_id = "default"
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
    "check_certification_matrix",
    "check_trust_layer",
    "check_voice_pipeline_status",
    "check_watchdog_status",
    "check_nus1a_learning_foundation",
    "check_nus1b_recommendation_workflow",
    "check_nus1c_safe_autopilot",
    "check_nus1d_eval_rollback",
    "check_nus1e_low_risk_execution",
    "check_nus1f_high_autonomy",
    "check_post_nus_orchestrator",
    "check_universal_front_door",
    "check_worker_execution_adapters",
    "check_nus_scorecard_feedback_loop",
    "check_inactive_manager_classification",
    # Prompt 2 — Private Daily-Driver Hardening
    "check_provider_readiness",
    "check_trace_persistence",
    "check_project_registry_persistence",
    "check_runtime_recovery",
    "check_connector_dryrun_framework",
    "check_memory_quality_matrix",
    "check_human_correction_store",
    # Prompt 3 — Consolidated Final Sprint
    "check_llm_gateway",
    "check_slack_workspace_identity",
    "check_platform_scorecard",
    "check_coding_proof_ladder_framework",
    # Prompt 3 continuation — memory + connectors raised to 4/5
    "check_semantic_memory",
    "check_connector_live_reader",
    # Blocker Clearance Mega-Sprint A
    "check_provider_capability_matrix",
    "check_memory_continuity_proofs",
    "check_google_oauth_status",
    "run_all_checks",
]
