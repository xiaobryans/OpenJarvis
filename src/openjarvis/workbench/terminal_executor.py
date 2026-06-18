"""US15 Terminal Executor — approval-gated command runner for Jarvis Workbench.

Safety rules (non-negotiable):
- Blocklisted commands are always rejected.
- Destructive/risky commands require explicit approval.
- Secrets/env-var values are scrubbed from displayed output.
- Max output displayed is capped to prevent log flooding.
- No shell injection: commands run as argv list via subprocess, not shell=True.
- Command, status, exit code, duration, blocked reason all reported.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Safety policy
# ---------------------------------------------------------------------------

# Commands always blocked — no approval overrides these.
_ALWAYS_BLOCKED: List[str] = [
    "rm -rf /",
    "rm -rf /*",
    "sudo rm",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",  # fork bomb
    "curl | bash",
    "wget | bash",
    "curl | sh",
    "wget | sh",
    "chmod 777 /",
]

# First tokens that require explicit approval (not auto-approved).
_APPROVAL_REQUIRED_FIRST_TOKENS: frozenset = frozenset({
    "rm",
    "mv",
    "cp",
    "sudo",
    "chmod",
    "chown",
    "kill",
    "pkill",
    "killall",
    "git",
    "npm",
    "pip",
    "uv",
    "brew",
    "apt",
    "apt-get",
    "curl",
    "wget",
    "ssh",
    "scp",
    "rsync",
    "docker",
    "kubectl",
    "terraform",
    "aws",
    "gcloud",
    "az",
    "python",
    "python3",
    "node",
    "ruby",
    "bash",
    "sh",
    "zsh",
    "fish",
})

# Commands auto-approved for local non-destructive inspection.
_SAFE_AUTO_APPROVE_FIRST_TOKENS: frozenset = frozenset({
    "ls",
    "pwd",
    "echo",
    "cat",
    "head",
    "tail",
    "grep",
    "rg",
    "find",
    "which",
    "type",
    "wc",
    "sort",
    "uniq",
    "diff",
    "date",
    "env",
    "printenv",
    "id",
    "whoami",
    "uname",
    "hostname",
    "uptime",
    "df",
    "du",
    "ps",
    "top",
    "git",  # git read-only commands are safe; git commit/push require approval
})

_GIT_READ_ONLY_SUBCOMMANDS = frozenset({
    "status", "log", "diff", "branch", "remote", "show", "describe",
    "rev-parse", "rev-list", "cat-file", "ls-files", "blame", "stash list",
})

_SECRET_SCRUB_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|auth|credential|bearer)[^\n]{0,120}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile(r"gho_[A-Za-z0-9]{36,}"),
    re.compile(r"eyJ[A-Za-z0-9._-]{40,}"),  # JWT
]

MAX_OUTPUT_CHARS = 8000
MAX_OUTPUT_LINES = 200


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class ExecutionResult:
    exec_id: str
    command: str
    argv: List[str]
    status: str  # "success" | "failed" | "blocked" | "timeout" | "approval_required"
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_ms: float
    blocked_reason: str
    approved: bool
    approval_required: bool
    approval_token: Optional[str]
    cwd: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "exec_id": self.exec_id,
            "command": self.command,
            "status": self.status,
            "exit_code": self.exit_code,
            "stdout_preview": self.stdout[:2000] if self.stdout else "",
            "stderr_preview": self.stderr[:1000] if self.stderr else "",
            "duration_ms": self.duration_ms,
            "blocked_reason": self.blocked_reason,
            "approved": self.approved,
            "approval_required": self.approval_required,
            "approval_token": self.approval_token,
            "cwd": self.cwd,
            "line_count": len(self.stdout.splitlines()) if self.stdout else 0,
        }


@dataclass
class PendingApproval:
    exec_id: str
    command: str
    argv: List[str]
    cwd: str
    reason: str
    created_at: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def _is_always_blocked(command: str) -> bool:
    cmd_lower = command.lower().strip()
    for pattern in _ALWAYS_BLOCKED:
        if pattern in cmd_lower:
            return True
    return False


def _requires_approval(argv: List[str]) -> tuple[bool, str]:
    """Return (needs_approval, reason) based on argv."""
    if not argv:
        return False, ""
    first = argv[0].lower().split("/")[-1]  # basename only

    if first == "git" and len(argv) >= 2:
        sub = argv[1].lower()
        if sub in _GIT_READ_ONLY_SUBCOMMANDS:
            return False, ""
        return True, f"git {sub} requires approval (non-read-only git operation)"

    if first in _SAFE_AUTO_APPROVE_FIRST_TOKENS:
        return False, ""
    if first in _APPROVAL_REQUIRED_FIRST_TOKENS:
        return True, f"{first} command requires explicit approval"
    return True, f"Unknown command '{first}' — approval required by default"


def _scrub_secrets(text: str) -> str:
    """Remove likely secrets from output before display."""
    for pattern in _SECRET_SCRUB_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _trim_output(text: str) -> str:
    lines = text.splitlines()
    if len(lines) > MAX_OUTPUT_LINES:
        lines = lines[:MAX_OUTPUT_LINES] + [f"... ({len(lines) - MAX_OUTPUT_LINES} more lines truncated)"]
    result = "\n".join(lines)
    if len(result) > MAX_OUTPUT_CHARS:
        result = result[:MAX_OUTPUT_CHARS] + f"\n... (truncated at {MAX_OUTPUT_CHARS} chars)"
    return result


# ---------------------------------------------------------------------------
# Terminal Executor
# ---------------------------------------------------------------------------


class TerminalExecutor:
    """Approval-gated terminal command executor for Jarvis Workbench."""

    def __init__(self, cwd: str = ".") -> None:
        self._cwd = cwd
        self._pending: Dict[str, PendingApproval] = {}

    def _make_result(
        self,
        *,
        exec_id: str,
        command: str,
        argv: List[str],
        status: str,
        exit_code: Optional[int] = None,
        stdout: str = "",
        stderr: str = "",
        duration_ms: float = 0.0,
        blocked_reason: str = "",
        approved: bool = False,
        approval_required: bool = False,
        approval_token: Optional[str] = None,
        cwd: str = "",
    ) -> ExecutionResult:
        return ExecutionResult(
            exec_id=exec_id,
            command=command,
            argv=argv,
            status=status,
            exit_code=exit_code,
            stdout=_trim_output(_scrub_secrets(stdout)),
            stderr=_trim_output(_scrub_secrets(stderr)),
            duration_ms=duration_ms,
            blocked_reason=blocked_reason,
            approved=approved,
            approval_required=approval_required,
            approval_token=approval_token,
            cwd=cwd or self._cwd,
        )

    def submit(
        self,
        command: str,
        *,
        cwd: Optional[str] = None,
        timeout: int = 30,
        pre_approved: bool = False,
        approval_token: Optional[str] = None,
    ) -> ExecutionResult:
        """Submit a command for execution.

        Returns immediately with status='approval_required' if approval is needed
        and pre_approved is False.  Caller must call approve() to execute.
        """
        exec_id = uuid.uuid4().hex[:12]
        run_cwd = cwd or self._cwd

        if _is_always_blocked(command):
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=[],
                status="blocked",
                blocked_reason="Command matches always-blocked safety pattern",
                cwd=run_cwd,
            )

        try:
            argv = shlex.split(command)
        except ValueError as exc:
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=[],
                status="blocked",
                blocked_reason=f"Cannot parse command: {exc}",
                cwd=run_cwd,
            )

        needs_approval, approval_reason = _requires_approval(argv)

        if needs_approval and not pre_approved:
            if approval_token and approval_token in self._pending:
                pa = self._pending.pop(approval_token)
                if pa.exec_id == exec_id or pa.command == command:
                    return self._execute(exec_id, command, argv, run_cwd, timeout, approved=True)
            # Store pending approval
            token = uuid.uuid4().hex[:16]
            self._pending[token] = PendingApproval(
                exec_id=exec_id,
                command=command,
                argv=argv,
                cwd=run_cwd,
                reason=approval_reason,
            )
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=argv,
                status="approval_required",
                blocked_reason=approval_reason,
                approval_required=True,
                approval_token=token,
                cwd=run_cwd,
            )

        return self._execute(exec_id, command, argv, run_cwd, timeout, approved=pre_approved)

    def approve(self, approval_token: str, *, timeout: int = 30) -> ExecutionResult:
        """Execute a previously submitted command after approval."""
        if approval_token not in self._pending:
            exec_id = uuid.uuid4().hex[:12]
            return self._make_result(
                exec_id=exec_id,
                command="",
                argv=[],
                status="blocked",
                blocked_reason=f"Unknown approval token: {approval_token}",
            )
        pa = self._pending.pop(approval_token)
        return self._execute(pa.exec_id, pa.command, pa.argv, pa.cwd, timeout, approved=True)

    def _execute(
        self,
        exec_id: str,
        command: str,
        argv: List[str],
        cwd: str,
        timeout: int,
        approved: bool,
    ) -> ExecutionResult:
        start = time.perf_counter()
        try:
            proc = subprocess.run(
                argv,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=None,  # inherit env but do not expose it in output
            )
            duration_ms = (time.perf_counter() - start) * 1000
            status = "success" if proc.returncode == 0 else "failed"
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=argv,
                status=status,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                duration_ms=duration_ms,
                approved=approved,
                cwd=cwd,
            )
        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start) * 1000
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=argv,
                status="timeout",
                exit_code=None,
                blocked_reason=f"Command timed out after {timeout}s",
                duration_ms=duration_ms,
                approved=approved,
                cwd=cwd,
            )
        except FileNotFoundError:
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=argv,
                status="blocked",
                exit_code=127,
                blocked_reason=f"Command not found: {argv[0]}",
                cwd=cwd,
            )
        except Exception as exc:
            return self._make_result(
                exec_id=exec_id,
                command=command,
                argv=argv,
                status="failed",
                exit_code=-1,
                blocked_reason=str(exc),
                cwd=cwd,
            )

    def get_pending(self) -> List[Dict[str, Any]]:
        """Return all pending approval requests."""
        return [
            {
                "approval_token": tok,
                "exec_id": pa.exec_id,
                "command": pa.command,
                "cwd": pa.cwd,
                "reason": pa.reason,
                "age_s": time.time() - pa.created_at,
            }
            for tok, pa in self._pending.items()
        ]


def is_command_safe_for_auto_approval(command: str) -> bool:
    """Return True if command is safe for auto-approval (no approval gate needed)."""
    if _is_always_blocked(command):
        return False
    try:
        argv = shlex.split(command)
    except ValueError:
        return False
    needs_approval, _ = _requires_approval(argv)
    return not needs_approval


__all__ = [
    "TerminalExecutor",
    "ExecutionResult",
    "PendingApproval",
    "is_command_safe_for_auto_approval",
]
