"""US15 Terminal Executor tests — approval-gated command runner."""

from __future__ import annotations

import pytest


class TestTerminalExecutorSafety:
    def test_always_blocked_commands_rejected(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.submit("rm -rf /")
        assert result.status == "blocked"
        assert result.exit_code is None

    def test_safe_commands_auto_approved(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.submit("ls .")
        assert result.status in ("success", "failed")  # executed, not blocked
        assert result.approval_required is False

    def test_risky_command_requires_approval(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.submit("rm -f /tmp/test_jarvis_dummy")
        assert result.status == "approval_required"
        assert result.approval_token is not None

    def test_approve_executes_pending_command(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd="/tmp")
        result = te.submit("python3 --version")
        if result.status == "approval_required":
            approved = te.approve(result.approval_token)
            assert approved.status in ("success", "failed", "blocked")
        else:
            assert result.status in ("success", "failed")

    def test_unknown_token_blocked(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.approve("nonexistent_token_xyz")
        assert result.status == "blocked"

    def test_git_read_only_auto_approved(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.submit("git status")
        # git status is read-only — auto-approved
        assert result.status in ("success", "failed")
        assert result.approval_required is False

    def test_git_commit_requires_approval(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.submit("git commit -m 'test'")
        assert result.status == "approval_required"

    def test_secret_scrubbing(self):
        from openjarvis.workbench.terminal_executor import _scrub_secrets

        text = "API_KEY=sk-abc123456789012345678901234567890 and some other text"
        scrubbed = _scrub_secrets(text)
        assert "sk-abc" not in scrubbed or "[REDACTED]" in scrubbed

    def test_output_trimmed(self):
        from openjarvis.workbench.terminal_executor import _trim_output

        big = "\n".join(f"line {i}" for i in range(300))
        trimmed = _trim_output(big)
        assert "truncated" in trimmed

    def test_result_to_dict_complete(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        result = te.submit("ls .")
        d = result.to_dict()
        assert "exec_id" in d
        assert "command" in d
        assert "status" in d
        assert "exit_code" in d
        assert "duration_ms" in d
        assert "blocked_reason" in d
        assert "approval_required" in d
        assert "cwd" in d

    def test_pending_list(self):
        from openjarvis.workbench.terminal_executor import TerminalExecutor

        te = TerminalExecutor(cwd=".")
        te.submit("rm -f /tmp/dummy_test_file_jarvis")
        pending = te.get_pending()
        assert len(pending) >= 1
        assert "approval_token" in pending[0]
        assert "command" in pending[0]
        assert "reason" in pending[0]


class TestSafetyClassification:
    def test_is_command_safe_for_auto_approval(self):
        from openjarvis.workbench.terminal_executor import is_command_safe_for_auto_approval

        assert is_command_safe_for_auto_approval("ls -la") is True
        assert is_command_safe_for_auto_approval("grep -r foo .") is True
        assert is_command_safe_for_auto_approval("rm -rf /tmp/x") is False
        assert is_command_safe_for_auto_approval("rm -rf /") is False
        assert is_command_safe_for_auto_approval("git commit -m test") is False
        assert is_command_safe_for_auto_approval("git status") is True

    def test_blocked_patterns_comprehensive(self):
        from openjarvis.workbench.terminal_executor import _is_always_blocked

        assert _is_always_blocked("rm -rf /") is True
        assert _is_always_blocked("sudo rm /important") is True
        assert _is_always_blocked("ls -la") is False
        assert _is_always_blocked("git status") is False
