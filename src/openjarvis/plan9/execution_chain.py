"""Plan 9 execution chain — approval validation, audit, safe git helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalRecord, ApprovalStatus
from openjarvis.authority.audit_store import AuditStore

# Harmless workflow edit targets only.
WORKFLOW_ALLOWED_PREFIXES = (
    "tests/fixtures/plan9_",
    "docs/plan9_",
)

BLOCKED_BASENAMES = frozenset({
    "JARVIS_OMNIX_HANDOFF.md",
    ".env",
    ".env.local",
    ".env.save",
})


def repo_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


def get_approval_engine() -> ApprovalEngine:
    return ApprovalEngine()


def get_audit_store() -> AuditStore:
    return AuditStore()


def validate_plan8_approval(
    approval_token: str,
    action_type: str,
    *,
    allowed_action_types: Optional[List[str]] = None,
) -> ApprovalRecord:
    """Validate a Plan 8 approval token for execution."""
    engine = get_approval_engine()
    record = engine.get(approval_token)
    if record is None:
        raise ValueError(f"Invalid approval_token: not found ({approval_token[:8]}...)")

    accepted = allowed_action_types or [action_type]
    if record.action_type not in accepted:
        raise ValueError(
            f"Approval action_type mismatch: expected one of {accepted}, got {record.action_type!r}"
        )

    if record.status != ApprovalStatus.GRANTED:
        raise ValueError(f"Approval not granted (status={record.status.value})")

    if not record.is_active():
        raise ValueError("Approval expired or inactive")

    return record


def mark_approval_used(approval_id: str) -> None:
    get_approval_engine().mark_used(approval_id)


def record_execution_audit(
    *,
    action_type: str,
    actor: str,
    execution_status: str,
    approval_decision: str = "granted",
    affected_resource: str = "",
    rollback_reference: str = "",
    error_message: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    audit = get_audit_store()
    entry = audit.record(
        action_type=action_type,
        actor=actor,
        tier=2,
        risk_level="medium",
        approval_decision=approval_decision,
        execution_status=execution_status,
        affected_resource=affected_resource,
        rollback_metadata=rollback_reference,
        error_info=error_message,
        context=metadata or {},
    )
    return entry.audit_id


def assert_allowed_workflow_file(file_path: str) -> None:
    rel = file_path.strip().lstrip("/")
    if ".." in rel or rel.startswith("/"):
        raise ValueError(f"Path traversal not allowed: {file_path!r}")
    base = Path(rel).name
    if base in BLOCKED_BASENAMES:
        raise ValueError(f"File is blocked from workflow edits: {base}")
    if not any(rel.startswith(p) for p in WORKFLOW_ALLOWED_PREFIXES):
        raise ValueError(
            f"File {rel!r} not in workflow allowlist {WORKFLOW_ALLOWED_PREFIXES}"
        )


def git_current_branch(cwd: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(cwd),
    )
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def git_head_hash(cwd: Path) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(cwd),
    )
    return r.stdout.strip()[:12] if r.returncode == 0 else "unknown"


def rollback_instruction(commit_hash: str) -> str:
    short = commit_hash[:12] if commit_hash else "HEAD"
    return f"git revert {short} --no-edit  # or: git reset --hard HEAD~1 (destructive — owner approval required)"
