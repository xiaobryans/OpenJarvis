"""NUS 1E — Low-Risk Execution Foundation.

Provides:
  1. Low-risk auto-commit candidate preparation (dry-run scaffold).
  2. Production-safe execution foundation with strict policy gate.
  3. Auto-commit safety preconditions (git clean check, diff classification,
     validation pass, rollback plan, audit log, kill-switch check,
     no secret files, no package artifacts).

Rules:
  - No auto-push.
  - No auto-merge.
  - No production deploy.
  - Auto-commit is scaffold/dry-run in NUS 1E — no real commit unless
    all preconditions pass AND it is tested in temp git repo only.
  - Production actions remain blocked.

Hard safety constraints:
  - No source-code mutation by auto-commit outside temp dir test.
  - No auto-push, auto-merge, deploy.
  - No secret access.
  - No external sends.
  - Kill-switch must be disabled before any auto-action.
  - US13 voice HOLD/UNSAFE/PARKED.
"""

from __future__ import annotations

import logging
import re
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional

logger = logging.getLogger(__name__)

NUS1E_LOW_RISK_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Secret and package artifact patterns (shared with execution_classifier)
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = re.compile(
    r"(\.env|\.env\.local|credentials|\.ssh|\.aws|secrets|api_key"
    r"|password|passwd|token|private_key|id_rsa|id_ed25519|pgpass|\.netrc"
    r"|keychain|vault|\.htpasswd)",
    re.IGNORECASE,
)

_DEPLOY_ARTIFACT_PATTERNS = re.compile(
    r"(\.dmg|\.pkg|notarization|node_modules/|\.next/|dist/|build/|__pycache__|\.pyc$)",
    re.IGNORECASE,
)

# Low-risk safe diff patterns
_SAFE_DIFF_PATTERNS = re.compile(
    r"\.(md|txt|rst|json|yaml|yml|toml|csv)$", re.IGNORECASE
)

# Actions that are permanently blocked from auto-commit
_BLOCKED_FROM_AUTO_COMMIT: FrozenSet[str] = frozenset({
    "auto_push", "auto_merge", "deploy", "secret_access",
    "self_modification", "safety_policy_change", "production_action",
})


# ---------------------------------------------------------------------------
# AutoCommitCandidate — metadata scaffold (no real git ops)
# ---------------------------------------------------------------------------


@dataclass
class AutoCommitCandidate:
    """Metadata for a potential auto-commit action.

    In NUS 1E this is dry-run only — no real git commit unless:
    1. All preconditions pass.
    2. Repo is a temp directory (tests only).
    3. Kill-switch is disabled.
    """

    candidate_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: float = field(default_factory=time.time)

    # What would be committed
    message: str = ""
    files_to_add: List[str] = field(default_factory=list)
    diff_summary: str = ""

    # Preconditions
    git_clean: Optional[bool] = None          # True = working tree clean
    diff_classified: bool = False             # True = diff reviewed + classified
    validation_passed: Optional[bool] = None  # True = tests/lint passed
    rollback_plan_id: Optional[str] = None    # Required before commit
    kill_switch_disabled: bool = False
    no_secret_files: Optional[bool] = None    # True = no .env/.ssh/etc
    no_deploy_artifacts: Optional[bool] = None # True = no .dmg/.pkg/etc

    # Audit
    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    # Result
    status: str = "pending"   # pending | ready | blocked | dry_run_ok | committed (temp only)
    blocked_reason: Optional[str] = None
    dry_run_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "created_at": self.created_at,
            "message": self.message,
            "files_to_add": self.files_to_add[:20],
            "diff_summary": self.diff_summary[:200],
            "git_clean": self.git_clean,
            "diff_classified": self.diff_classified,
            "validation_passed": self.validation_passed,
            "rollback_plan_id": self.rollback_plan_id,
            "kill_switch_disabled": self.kill_switch_disabled,
            "no_secret_files": self.no_secret_files,
            "no_deploy_artifacts": self.no_deploy_artifacts,
            "status": self.status,
            "blocked_reason": self.blocked_reason,
            "dry_run_result": self.dry_run_result,
            "audit_log": self.audit_log[-10:],
        }

    def _audit(self, event: str, detail: str = "") -> None:
        self.audit_log.append({
            "event": event,
            "detail": detail,
            "timestamp": time.time(),
        })


# ---------------------------------------------------------------------------
# Precondition checker
# ---------------------------------------------------------------------------


def _check_secret_files(files: List[str]) -> List[str]:
    """Return list of secret/credential files found in targets."""
    return [f for f in files if _SECRET_PATTERNS.search(f)]


def _check_deploy_artifacts(files: List[str]) -> List[str]:
    """Return list of deploy/package artifact files found in targets."""
    return [f for f in files if _DEPLOY_ARTIFACT_PATTERNS.search(f)]


# ---------------------------------------------------------------------------
# LowRiskExecutionManager
# ---------------------------------------------------------------------------


class LowRiskExecutionManager:
    """NUS 1E low-risk execution manager.

    Prepares auto-commit candidates and validates all preconditions.
    Auto-commit is scaffold/dry-run only in NUS 1E.
    Real commits are only allowed in temp git repos (tests only).

    Production actions remain blocked.
    """

    def __init__(self, kill_switch: bool = True) -> None:
        self._kill_switch = kill_switch
        self._candidates: Dict[str, AutoCommitCandidate] = []  # type: ignore[assignment]
        self._candidates_dict: Dict[str, AutoCommitCandidate] = {}

    @property
    def kill_switch(self) -> bool:
        return self._kill_switch

    @kill_switch.setter
    def kill_switch(self, value: bool) -> None:
        self._kill_switch = value

    # ------------------------------------------------------------------ #
    # Candidate creation                                                    #
    # ------------------------------------------------------------------ #

    def create_candidate(
        self,
        message: str,
        files_to_add: Optional[List[str]] = None,
        diff_summary: str = "",
    ) -> AutoCommitCandidate:
        """Create an auto-commit candidate. Validates files for secrets/artifacts."""
        files = files_to_add or []

        candidate = AutoCommitCandidate(
            message=message,
            files_to_add=files,
            diff_summary=diff_summary,
        )

        # Immediately check for secret files
        secret_files = _check_secret_files(files)
        if secret_files:
            candidate.status = "blocked"
            candidate.blocked_reason = f"Secret/credential files detected: {secret_files[:3]}"
            candidate.no_secret_files = False
            candidate._audit("blocked", f"Secret files: {secret_files[:3]}")
        else:
            candidate.no_secret_files = True

        # Check for deploy artifacts
        deploy_artifacts = _check_deploy_artifacts(files)
        if deploy_artifacts and candidate.status != "blocked":
            candidate.status = "blocked"
            candidate.blocked_reason = f"Deploy/package artifacts detected: {deploy_artifacts[:3]}"
            candidate.no_deploy_artifacts = False
            candidate._audit("blocked", f"Deploy artifacts: {deploy_artifacts[:3]}")
        else:
            candidate.no_deploy_artifacts = len(deploy_artifacts) == 0

        self._candidates_dict[candidate.candidate_id] = candidate
        self._log_event(
            "low_risk_execution_candidate_created",
            f"Candidate {candidate.candidate_id} status={candidate.status} files={len(files)}",
        )
        return candidate

    # ------------------------------------------------------------------ #
    # Precondition validation                                               #
    # ------------------------------------------------------------------ #

    def validate_preconditions(
        self,
        candidate_id: str,
        git_clean: bool,
        diff_classified: bool,
        validation_passed: bool,
        rollback_plan_id: Optional[str],
    ) -> Dict[str, Any]:
        """Validate all auto-commit preconditions. Returns pass/fail with reasons."""
        candidate = self._candidates_dict.get(candidate_id)
        if not candidate:
            return {"ok": False, "reason": "Candidate not found."}

        if candidate.status == "blocked":
            return {
                "ok": False,
                "reason": f"Candidate already blocked: {candidate.blocked_reason}",
                "blocked": True,
            }

        failures = []

        # Kill-switch
        if self._kill_switch:
            failures.append("kill_switch is enabled — auto-commit disabled")
            candidate.kill_switch_disabled = False
        else:
            candidate.kill_switch_disabled = True

        # Git clean
        candidate.git_clean = git_clean
        if not git_clean:
            failures.append("git working tree is not clean")

        # Diff classified
        candidate.diff_classified = diff_classified
        if not diff_classified:
            failures.append("diff has not been classified")

        # Validation passed
        candidate.validation_passed = validation_passed
        if not validation_passed:
            failures.append("validation has not passed")

        # Rollback plan
        candidate.rollback_plan_id = rollback_plan_id
        if not rollback_plan_id:
            failures.append("rollback plan is missing")

        if failures:
            candidate.status = "blocked"
            candidate.blocked_reason = "; ".join(failures)
            candidate._audit("precondition_failed", "; ".join(failures))
            self._log_event("low_risk_execution_blocked", f"Preconditions failed: {failures}")
            return {
                "ok": False,
                "candidate_id": candidate_id,
                "failures": failures,
                "blocked": True,
            }

        candidate.status = "ready"
        candidate._audit("preconditions_passed", "All preconditions met.")
        return {
            "ok": True,
            "candidate_id": candidate_id,
            "status": "ready",
            "all_preconditions_met": True,
        }

    # ------------------------------------------------------------------ #
    # Dry-run                                                               #
    # ------------------------------------------------------------------ #

    def dry_run(self, candidate_id: str) -> Dict[str, Any]:
        """Simulate auto-commit dry-run. Returns dry-run result.

        No real git commit. No auto-push. No auto-merge.
        """
        candidate = self._candidates_dict.get(candidate_id)
        if not candidate:
            return {"ok": False, "reason": "Candidate not found."}
        if candidate.status == "blocked":
            return {"ok": False, "reason": f"Blocked: {candidate.blocked_reason}", "blocked": True}
        if candidate.status != "ready":
            return {"ok": False, "reason": f"Cannot dry-run from status={candidate.status}"}

        result = {
            "dry_run": True,
            "candidate_id": candidate_id,
            "message": candidate.message,
            "files_to_add_count": len(candidate.files_to_add),
            "executed_at": time.time(),
            "result": "simulated_ok",
            "note": (
                "NUS 1E dry-run only — no real git commit. "
                "No auto-push, no auto-merge, no deploy."
            ),
        }
        candidate.dry_run_result = result
        candidate.status = "dry_run_ok"
        candidate._audit("dry_run_executed", "Dry-run simulated successfully.")
        self._log_event(
            "low_risk_execution_dry_run_passed",
            f"Dry-run OK: {candidate_id} message='{candidate.message[:50]}'",
        )
        return {"ok": True, **result}

    def commit_to_temp_repo(
        self,
        candidate_id: str,
        repo_path: Path,
    ) -> Dict[str, Any]:
        """Execute real git commit in a TEMP repo only.

        This is the ONLY path where a real git commit may be made.
        Validates that repo_path is a temp directory before proceeding.
        No auto-push. No auto-merge. No production deploy.
        """
        import tempfile as _tempfile

        candidate = self._candidates_dict.get(candidate_id)
        if not candidate:
            return {"ok": False, "reason": "Candidate not found."}

        # Strict temp dir check
        resolved = str(repo_path.resolve())
        tmp_dirs = ["/tmp", "/var/folders", "/private/var/folders", "/private/tmp"]
        is_tmp = any(resolved.startswith(t) for t in tmp_dirs)
        if not is_tmp:
            return {
                "ok": False,
                "reason": (
                    f"commit_to_temp_repo only allowed in temp directories. "
                    f"Path '{resolved}' is not a temp dir. "
                    "NUS 1E: no real commits outside temp repos."
                ),
                "blocked": True,
            }

        if candidate.status not in ("ready", "dry_run_ok"):
            return {"ok": False, "reason": f"Cannot commit from status={candidate.status}"}

        if self._kill_switch:
            return {"ok": False, "reason": "Kill switch active — real commit disabled.", "blocked": True}

        try:
            # Only add/commit — no push, no merge
            for f in candidate.files_to_add:
                fpath = repo_path / f
                if fpath.exists():
                    subprocess.run(["git", "add", str(fpath)], cwd=repo_path, check=True, capture_output=True)

            result = subprocess.run(
                ["git", "commit", "-m", candidate.message, "--allow-empty"],
                cwd=repo_path, check=True, capture_output=True, text=True,
            )
            candidate.status = "committed"
            candidate._audit("committed_temp_repo", f"Committed to temp repo: {resolved}")
            self._log_event(
                "low_risk_execution_dry_run_passed",
                f"Temp repo commit OK: {candidate_id}",
            )
            return {
                "ok": True,
                "committed": True,
                "temp_repo": True,
                "candidate_id": candidate_id,
                "stdout": result.stdout[:200],
                "note": "Committed to temp repo only — no push, no merge, no production deploy.",
            }
        except subprocess.CalledProcessError as exc:
            return {
                "ok": False,
                "reason": f"git commit failed: {exc.stderr[:200] if exc.stderr else str(exc)}",
            }
        except Exception as exc:
            return {"ok": False, "reason": f"commit_to_temp_repo error: {exc}"}

    # ------------------------------------------------------------------ #
    # Production gate (always blocked in NUS 1E)
    # ------------------------------------------------------------------ #

    def production_gate(self, action_type: str) -> Dict[str, Any]:
        """Production-safe execution gate.

        All production actions remain blocked in NUS 1E.
        Requires NUS 1F explicit gate for any real production execution.
        """
        if action_type in _BLOCKED_FROM_AUTO_COMMIT:
            self._log_event("low_risk_execution_blocked", f"Production gate blocked: {action_type}")
            return {
                "ok": False,
                "reason": (
                    f"action_type={action_type} is blocked in NUS 1E production gate. "
                    "Requires NUS 1F explicit production gate activation."
                ),
                "blocked": True,
                "requires_nus_1f": True,
            }
        return {
            "ok": False,
            "reason": (
                f"Production gate is not active in NUS 1E. "
                f"action_type={action_type} requires NUS 1F activation."
            ),
            "blocked": True,
            "requires_nus_1f": True,
        }

    # ------------------------------------------------------------------ #
    # Queries                                                               #
    # ------------------------------------------------------------------ #

    def get_candidate(self, candidate_id: str) -> Optional[AutoCommitCandidate]:
        return self._candidates_dict.get(candidate_id)

    def list_candidates(self) -> List[AutoCommitCandidate]:
        return list(self._candidates_dict.values())

    def get_status(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for c in self._candidates_dict.values():
            by_status[c.status] = by_status.get(c.status, 0) + 1
        return {
            "version": NUS1E_LOW_RISK_VERSION,
            "kill_switch": self._kill_switch,
            "candidate_count": len(self._candidates_dict),
            "by_status": by_status,
            "auto_commit_scaffold": "dry_run_only_in_nus1e",
            "temp_repo_commit_allowed": True,
            "production_commit_allowed": False,
            "no_auto_push": True,
            "no_auto_merge": True,
            "no_production_deploy": True,
            "us13_voice_status": "HOLD/UNSAFE/PARKED",
            "safety_gates_active": True,
        }

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1e",
                task_id="low_risk_execution",
                event_type=event_type,
                title=f"NUS 1E: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1E low risk execution event log skipped: %s", exc)
