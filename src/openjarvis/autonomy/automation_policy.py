"""Jarvis Automation Policy — 7-level automation ladder with standing approval policy.

Automation levels:
  Level 1: observe/read/check              — auto_allowed, no approval needed
  Level 2: report/summarize/alert draft    — auto_allowed, no approval needed
  Level 3: plan/propose                    — auto_allowed, no approval needed
  Level 4: safe local execute (allowlisted)— auto_allowed if allowlisted
  Level 5: pre-approved autopilot          — no per-action approval within standing policy
  Level 6: sensitive action                — explicit approval required
  Level 7: dangerous/production            — always explicit + strongest confirmation

Standing Approval Policy per action_class:
  auto_allowed              — no approval needed
  voice_approval_allowed    — voice approve/reject accepted
  explicit_click_required   — must click approve in UI
  passphrase_required       — must enter passphrase to confirm
  always_blocked            — never allowed regardless of approval

Hard gates (always Level 7, always_blocked — cannot be overridden by any standing policy):
  real_slack_send_public, real_telegram_send_public, production_deploy,
  aws_infrastructure_change, billing_change, stripe_change, vercel_deploy,
  supabase_change, provider_routing_change, secrets_mutation, env_mutation,
  browser_form_submit, browser_purchase, browser_account_mutation, browser_delete,
  destructive_delete, destructive_git_op, open_public_endpoint, tailscale_funnel,
  persistent_daemon_install
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


# ---------------------------------------------------------------------------
# Automation levels
# ---------------------------------------------------------------------------


class AutomationLevel(IntEnum):
    OBSERVE_READ_CHECK = 1
    REPORT_DRAFT = 2
    PLAN_PROPOSE = 3
    SAFE_LOCAL_EXECUTE = 4
    PRE_APPROVED_AUTOPILOT = 5
    SENSITIVE_ACTION = 6
    DANGEROUS_PRODUCTION = 7


# ---------------------------------------------------------------------------
# Standing policy modes
# ---------------------------------------------------------------------------


class StandingPolicyMode:
    AUTO_ALLOWED = "auto_allowed"
    VOICE_APPROVAL_ALLOWED = "voice_approval_allowed"
    EXPLICIT_CLICK_REQUIRED = "explicit_click_required"
    PASSPHRASE_REQUIRED = "passphrase_required"
    ALWAYS_BLOCKED = "always_blocked"


# ---------------------------------------------------------------------------
# Approval status
# ---------------------------------------------------------------------------


class ApprovalStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    VOICE_CONFIRMED = "voice_confirmed"
    PASSPHRASE_CONFIRMED = "passphrase_confirmed"


# ---------------------------------------------------------------------------
# Hard-gated action classes (always Level 7, always_blocked)
# ---------------------------------------------------------------------------

_HARD_GATE_ACTION_CLASSES: frozenset = frozenset({
    "real_slack_send_public",
    "real_telegram_send_public",
    "production_deploy",
    "aws_infrastructure_change",
    "billing_change",
    "stripe_change",
    "vercel_deploy",
    "supabase_change",
    "provider_routing_change",
    "secrets_mutation",
    "env_mutation",
    "browser_form_submit",
    "browser_purchase",
    "browser_account_mutation",
    "browser_delete",
    "destructive_delete",
    "destructive_git_op",
    "open_public_endpoint",
    "tailscale_funnel",
    "persistent_daemon_install",
})

# Level 1-4 action classes (auto-allowed)
_AUTO_ALLOWED_ACTION_CLASSES: frozenset = frozenset({
    "read_only_check",
    "watchdog_run",
    "doctor_run",
    "memory_write_no_secrets",
    "handoff_update",
    "targeted_test",
    "draft_report",
    "local_diagnostic",
    "branch_commit_configured",
    "list_tools",
    "list_skills",
    "list_missions",
    "get_status",
    "get_readiness",
    "get_project",
    "get_alert",
    "run_checks",
    "generate_plan",
    "local_git_read",
    "local_repo_read",
    "local_file_read",
    "draft_slack_message",
    "draft_telegram_message",
    "draft_email",
    "automation_policy_get",
    "automation_policy_evaluate",
    "voice_status_check",
    "desktop_permissions_status",
    "mobile_status_check",
    "connector_diagnostics",
    "ops_schedule_plan",
    "ops_install_plan",
    "ops_dry_run",
    "ops_run_once_safe",
})

# Approval-required (Level 6) — require explicit click
_APPROVAL_REQUIRED_ACTION_CLASSES: frozenset = frozenset({
    "git_push_to_fork",
    "git_merge",
    "real_slack_send_private",
    "real_telegram_send_private",
    "browser_deploy_dry_run",
    "runner_install",
})


# ---------------------------------------------------------------------------
# Approval record
# ---------------------------------------------------------------------------


@dataclass
class ApprovalRecord:
    approval_id: str
    action_class: str
    description: str
    automation_level: int
    standing_policy: str
    status: str
    challenge_token: str
    project_id: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    decided_at: Optional[float] = None
    decided_by: str = ""
    confirmation_phrase: str = ""
    audit_notes: str = ""

    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "action_class": self.action_class,
            "description": self.description,
            "automation_level": self.automation_level,
            "standing_policy": self.standing_policy,
            "status": self.status,
            "challenge_token": self.challenge_token,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "is_expired": self.is_expired(),
        }


# ---------------------------------------------------------------------------
# SQLite-backed approval store
# ---------------------------------------------------------------------------

_JARVIS_DIR = Path.home() / ".jarvis"
_DB_PATH = _JARVIS_DIR / "automation_approvals.db"
_DEFAULT_TTL = 300  # 5 minutes


@contextmanager
def _get_conn(db_path: Path = _DB_PATH) -> Iterator[sqlite3.Connection]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema(db_path: Path = _DB_PATH) -> None:
    with _get_conn(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS approval_records (
                approval_id TEXT PRIMARY KEY,
                action_class TEXT NOT NULL,
                description TEXT NOT NULL,
                automation_level INTEGER NOT NULL,
                standing_policy TEXT NOT NULL,
                status TEXT NOT NULL,
                challenge_token TEXT NOT NULL,
                project_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                decided_at REAL,
                decided_by TEXT NOT NULL DEFAULT '',
                confirmation_phrase TEXT NOT NULL DEFAULT '',
                audit_notes TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_approvals_project "
            "ON approval_records(project_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_approvals_status "
            "ON approval_records(status)"
        )


# ---------------------------------------------------------------------------
# In-memory standing policy overrides
# ---------------------------------------------------------------------------

_STANDING_POLICIES: Dict[str, str] = {}


def _default_policy_for(action_class: str) -> str:
    if action_class in _HARD_GATE_ACTION_CLASSES:
        return StandingPolicyMode.ALWAYS_BLOCKED
    if action_class in _AUTO_ALLOWED_ACTION_CLASSES:
        return StandingPolicyMode.AUTO_ALLOWED
    if action_class in _APPROVAL_REQUIRED_ACTION_CLASSES:
        return StandingPolicyMode.EXPLICIT_CLICK_REQUIRED
    return StandingPolicyMode.EXPLICIT_CLICK_REQUIRED


# ---------------------------------------------------------------------------
# AutomationPolicy — main interface
# ---------------------------------------------------------------------------


class AutomationPolicy:
    """Evaluate automation policy for proposed actions.

    Contract:
      - Hard gates always return ALWAYS_BLOCKED (not overridable)
      - Level 1-4 auto_allowed actions never need approval
      - Level 6 actions require explicit click or passphrase
      - Level 7 actions are always_blocked (hard gate)
      - Expired approvals cannot be reused
    """

    _db_path: Path = _DB_PATH

    @classmethod
    def classify_action(cls, action_class: str) -> int:
        if action_class in _HARD_GATE_ACTION_CLASSES:
            return AutomationLevel.DANGEROUS_PRODUCTION
        if action_class in _AUTO_ALLOWED_ACTION_CLASSES:
            if any(action_class.startswith(p) for p in (
                "read_only", "list_", "get_", "watchdog_", "doctor_", "voice_status",
                "desktop_permissions", "mobile_status", "connector_diagnostics",
            )):
                return AutomationLevel.OBSERVE_READ_CHECK
            if any(action_class.startswith(p) for p in (
                "draft_", "generate_plan", "ops_schedule", "ops_install", "ops_dry_run",
            )):
                return AutomationLevel.REPORT_DRAFT
            if any(action_class.startswith(p) for p in (
                "run_checks", "targeted_test", "local_diagnostic", "automation_policy",
                "memory_write", "handoff_update",
            )):
                return AutomationLevel.PLAN_PROPOSE
            return AutomationLevel.SAFE_LOCAL_EXECUTE
        if action_class in _APPROVAL_REQUIRED_ACTION_CLASSES:
            return AutomationLevel.SENSITIVE_ACTION
        return AutomationLevel.SENSITIVE_ACTION

    @classmethod
    def get_standing_policy(cls, action_class: str) -> str:
        return _STANDING_POLICIES.get(action_class, _default_policy_for(action_class))

    @classmethod
    def set_standing_policy(cls, action_class: str, policy_mode: str) -> None:
        if action_class in _HARD_GATE_ACTION_CLASSES:
            raise ValueError(
                f"Hard-gated action '{action_class}' standing policy cannot be changed. "
                "Hard gates are always ALWAYS_BLOCKED."
            )
        valid = {
            StandingPolicyMode.AUTO_ALLOWED,
            StandingPolicyMode.VOICE_APPROVAL_ALLOWED,
            StandingPolicyMode.EXPLICIT_CLICK_REQUIRED,
            StandingPolicyMode.PASSPHRASE_REQUIRED,
        }
        if policy_mode not in valid:
            raise ValueError(f"Invalid policy mode '{policy_mode}'. Valid: {sorted(valid)}")
        _STANDING_POLICIES[action_class] = policy_mode

    @classmethod
    def evaluate(
        cls,
        action_class: str,
        description: str = "",
        project_id: str = "omnix",
    ) -> Dict[str, Any]:
        """Evaluate whether an action requires approval."""
        level = cls.classify_action(action_class)
        policy = cls.get_standing_policy(action_class)
        blocked = policy == StandingPolicyMode.ALWAYS_BLOCKED
        requires_approval = blocked or policy in (
            StandingPolicyMode.EXPLICIT_CLICK_REQUIRED,
            StandingPolicyMode.PASSPHRASE_REQUIRED,
            StandingPolicyMode.VOICE_APPROVAL_ALLOWED,
        )
        blocker = ""
        if blocked:
            blocker = (
                f"Action class '{action_class}' is always_blocked "
                "(hard gate or standing policy)"
            )
        return {
            "action_class": action_class,
            "description": description,
            "automation_level": int(level),
            "standing_policy": policy,
            "requires_approval": requires_approval,
            "blocked": blocked,
            "blocker": blocker,
            "can_proceed": not requires_approval and not blocked,
            "project_id": project_id,
        }

    @classmethod
    def request_approval(
        cls,
        action_class: str,
        description: str,
        project_id: str = "omnix",
        ttl_seconds: int = _DEFAULT_TTL,
    ) -> ApprovalRecord:
        eval_result = cls.evaluate(action_class, description, project_id)
        if eval_result["blocked"]:
            raise ValueError(
                f"Cannot request approval for always_blocked action: '{action_class}'. "
                f"Blocker: {eval_result['blocker']}"
            )
        _ensure_schema(cls._db_path)
        approval_id = str(uuid.uuid4())
        challenge = hashlib.sha256(
            f"{approval_id}:{action_class}:{time.time()}".encode()
        ).hexdigest()[:12]
        record = ApprovalRecord(
            approval_id=approval_id,
            action_class=action_class,
            description=description,
            automation_level=eval_result["automation_level"],
            standing_policy=eval_result["standing_policy"],
            status=ApprovalStatus.PENDING,
            challenge_token=challenge,
            project_id=project_id,
            expires_at=time.time() + ttl_seconds,
        )
        with _get_conn(cls._db_path) as conn:
            conn.execute(
                "INSERT INTO approval_records "
                "(approval_id, action_class, description, automation_level, "
                "standing_policy, status, challenge_token, project_id, "
                "created_at, expires_at, decided_at, decided_by, "
                "confirmation_phrase, audit_notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.approval_id, record.action_class, record.description,
                    record.automation_level, record.standing_policy, record.status,
                    record.challenge_token, record.project_id,
                    record.created_at, record.expires_at, None, "", "", "",
                ),
            )
        return record

    @classmethod
    def approve(
        cls,
        approval_id: str,
        decided_by: str = "bryan",
        confirmation_phrase: str = "",
    ) -> ApprovalRecord:
        _ensure_schema(cls._db_path)
        record = cls._load(approval_id)
        if record is None:
            raise ValueError(f"Approval '{approval_id}' not found")
        if record.is_expired():
            cls._update_status(approval_id, ApprovalStatus.EXPIRED, decided_by)
            raise ValueError(
                f"Approval '{approval_id}' has expired — cannot reuse expired approval"
            )
        if record.status != ApprovalStatus.PENDING:
            raise ValueError(
                f"Approval '{approval_id}' is not pending (status={record.status})"
            )
        if record.standing_policy == StandingPolicyMode.PASSPHRASE_REQUIRED:
            if not confirmation_phrase:
                raise ValueError(
                    "Passphrase required for this action but not provided"
                )
        status = (
            ApprovalStatus.PASSPHRASE_CONFIRMED
            if confirmation_phrase
            else ApprovalStatus.APPROVED
        )
        cls._update_status(
            approval_id, status, decided_by,
            confirmation_phrase=confirmation_phrase,
        )
        record.status = status
        record.decided_at = time.time()
        record.decided_by = decided_by
        return record

    @classmethod
    def reject(cls, approval_id: str, decided_by: str = "bryan") -> ApprovalRecord:
        _ensure_schema(cls._db_path)
        record = cls._load(approval_id)
        if record is None:
            raise ValueError(f"Approval '{approval_id}' not found")
        cls._update_status(approval_id, ApprovalStatus.REJECTED, decided_by)
        record.status = ApprovalStatus.REJECTED
        record.decided_at = time.time()
        record.decided_by = decided_by
        return record

    @classmethod
    def list_pending(cls, project_id: str = "omnix") -> List[ApprovalRecord]:
        try:
            _ensure_schema(cls._db_path)
            with _get_conn(cls._db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM approval_records "
                    "WHERE project_id=? AND status=? "
                    "ORDER BY created_at DESC",
                    (project_id, ApprovalStatus.PENDING),
                ).fetchall()
            records = [cls._from_row(r) for r in rows]
            now = time.time()
            for r in records:
                if r.expires_at > 0 and now > r.expires_at:
                    r.status = ApprovalStatus.EXPIRED
            return records
        except Exception:
            return []

    @classmethod
    def run_autopilot_once(cls, project_id: str = "omnix") -> Dict[str, Any]:
        """Simulate running pre-approved safe actions. All simulated — no real execution."""
        safe_actions = [
            {"action": "watchdog.run_project_pack", "class": "watchdog_run"},
            {"action": "doctor.run", "class": "doctor_run"},
            {"action": "alert.daily_digest", "class": "draft_report"},
        ]
        results = []
        for item in safe_actions:
            ev = cls.evaluate(item["class"], item["action"], project_id)
            results.append({
                "action": item["action"],
                "action_class": item["class"],
                "can_proceed": ev["can_proceed"],
                "requires_approval": ev["requires_approval"],
                "blocked": ev["blocked"],
                "simulated": True,
            })
        return {
            "project_id": project_id,
            "run_type": "autopilot_once",
            "simulated": True,
            "note": "Autopilot once is a dry-run simulation. No real actions executed.",
            "actions_evaluated": results,
            "ran_at": time.time(),
        }

    @classmethod
    def get_policy_summary(cls) -> Dict[str, Any]:
        return {
            "hard_gate_action_classes": sorted(_HARD_GATE_ACTION_CLASSES),
            "auto_allowed_action_classes": sorted(_AUTO_ALLOWED_ACTION_CLASSES),
            "approval_required_action_classes": sorted(_APPROVAL_REQUIRED_ACTION_CLASSES),
            "standing_policy_overrides": dict(_STANDING_POLICIES),
            "levels": {
                "1": "observe/read/check — auto_allowed",
                "2": "report/draft — auto_allowed",
                "3": "plan/propose — auto_allowed",
                "4": "safe local execute (allowlisted) — auto_allowed",
                "5": "pre-approved autopilot — standing policy",
                "6": "sensitive action — explicit_click_required",
                "7": "dangerous/production — always_blocked or strongest",
            },
        }

    @classmethod
    def _load(cls, approval_id: str) -> Optional[ApprovalRecord]:
        try:
            with _get_conn(cls._db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM approval_records WHERE approval_id=?",
                    (approval_id,),
                ).fetchone()
            if row is None:
                return None
            return cls._from_row(row)
        except Exception:
            return None

    @classmethod
    def _update_status(
        cls,
        approval_id: str,
        status: str,
        decided_by: str,
        confirmation_phrase: str = "",
    ) -> None:
        with _get_conn(cls._db_path) as conn:
            conn.execute(
                "UPDATE approval_records "
                "SET status=?, decided_at=?, decided_by=?, confirmation_phrase=? "
                "WHERE approval_id=?",
                (status, time.time(), decided_by, confirmation_phrase, approval_id),
            )

    @staticmethod
    def _from_row(row: sqlite3.Row) -> ApprovalRecord:
        return ApprovalRecord(
            approval_id=row["approval_id"],
            action_class=row["action_class"],
            description=row["description"],
            automation_level=row["automation_level"],
            standing_policy=row["standing_policy"],
            status=row["status"],
            challenge_token=row["challenge_token"],
            project_id=row["project_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            decided_at=row["decided_at"],
            decided_by=row["decided_by"] or "",
            confirmation_phrase=row["confirmation_phrase"] or "",
            audit_notes=row["audit_notes"] or "",
        )

    @classmethod
    def clear_for_tests(cls) -> None:
        """Reset all in-memory state and DB for test isolation."""
        _STANDING_POLICIES.clear()
        try:
            db = cls._db_path
            if db.exists():
                with _get_conn(db) as conn:
                    conn.execute("DELETE FROM approval_records")
        except Exception:
            pass


__all__ = [
    "AutomationLevel",
    "StandingPolicyMode",
    "ApprovalStatus",
    "ApprovalRecord",
    "AutomationPolicy",
]
