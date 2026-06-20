"""Jarvis Event Hook Framework — adapter for ECC hooks.

Provides a safe, disabled-by-default event hook framework that:
  - Wraps all 10 ECC hooks behind a Jarvis event system
  - Enforces reviewer_approved gate (all hooks disabled until Bryan approves)
  - Provides dry_run mode (hook registration without execution)
  - Provides rollback/quarantine/disable path
  - Never executes raw ECC hook code

ECC hooks covered:
  1. ecc:hook:adapter
  2. ecc:hook:after-file-edit
  3. ecc:hook:after-mcp-execution
  4. ecc:hook:after-shell-execution
  5. ecc:hook:after-tab-file-edit
  6. ecc:hook:before-tool-call
  7. ecc:hook:notification
  8. ecc:hook:on-error
  9. ecc:hook:pre-commit
  10. ecc:hook:post-task

All hooks stay in state: READY_BUT_WAITING_FOR_APPROVAL
Activation requires Bryan's explicit approval AND Jarvis event routing integration.

Machine-readable: openjarvis.skills.sources.ecc.hooks.jarvis_hook_framework
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class HookEvent(str, Enum):
    """Jarvis-native event types corresponding to ECC hook triggers."""

    ADAPTER = "adapter"
    AFTER_FILE_EDIT = "after_file_edit"
    AFTER_MCP_EXECUTION = "after_mcp_execution"
    AFTER_SHELL_EXECUTION = "after_shell_execution"
    AFTER_TAB_FILE_EDIT = "after_tab_file_edit"
    BEFORE_TOOL_CALL = "before_tool_call"
    NOTIFICATION = "notification"
    ON_ERROR = "on_error"
    PRE_COMMIT = "pre_commit"
    POST_TASK = "post_task"


# Map ECC hook IDs to Jarvis event types
ECC_HOOK_EVENT_MAP: Dict[str, HookEvent] = {
    "ecc:hook:adapter": HookEvent.ADAPTER,
    "ecc:hook:after-file-edit": HookEvent.AFTER_FILE_EDIT,
    "ecc:hook:after-mcp-execution": HookEvent.AFTER_MCP_EXECUTION,
    "ecc:hook:after-shell-execution": HookEvent.AFTER_SHELL_EXECUTION,
    "ecc:hook:after-tab-file-edit": HookEvent.AFTER_TAB_FILE_EDIT,
    "ecc:hook:before-tool-call": HookEvent.BEFORE_TOOL_CALL,
    "ecc:hook:notification": HookEvent.NOTIFICATION,
    "ecc:hook:on-error": HookEvent.ON_ERROR,
    "ecc:hook:pre-commit": HookEvent.PRE_COMMIT,
    "ecc:hook:post-task": HookEvent.POST_TASK,
}

ECC_HOOK_PLAN1_STATE = "READY_BUT_WAITING_FOR_APPROVAL"


class HookGateError(RuntimeError):
    """Raised when a hook is triggered but the framework is not approved."""


@dataclass
class HookRegistration:
    """A registered hook handler (disabled by default)."""

    hook_id: str
    event: HookEvent
    handler_name: str
    enabled: bool = False
    reviewer_approved: bool = False
    description: str = ""

    def enable(self) -> None:
        if not self.reviewer_approved:
            raise HookGateError(
                f"Hook '{self.hook_id}' cannot be enabled: reviewer_approved=False. "
                "Bryan must explicitly approve hook framework activation."
            )
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
        self.reviewer_approved = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "hook_id": self.hook_id,
            "event": self.event.value,
            "handler_name": self.handler_name,
            "enabled": self.enabled,
            "reviewer_approved": self.reviewer_approved,
            "description": self.description,
            "plan1_state": ECC_HOOK_PLAN1_STATE,
        }


class JarvisHookFramework:
    """Jarvis-native event hook framework adapter for ECC hooks.

    Usage:
        framework = JarvisHookFramework()
        # Register a hook (disabled by default)
        framework.register("ecc:hook:pre-commit", handler_name="run_lint_check")
        # Enable only after Bryan approves:
        # framework.set_approved("ecc:hook:pre-commit", approved=True)
        # framework.enable("ecc:hook:pre-commit")
    """

    def __init__(self) -> None:
        self._hooks: Dict[str, HookRegistration] = {}
        self._framework_approved: bool = False
        self._dry_run: bool = True

    def set_framework_approved(self, approved: bool) -> None:
        """Set framework-level approval (Bryan's explicit approval)."""
        self._framework_approved = approved

    def set_dry_run(self, dry_run: bool) -> None:
        self._dry_run = dry_run

    def register(
        self,
        hook_id: str,
        handler_name: str = "noop_handler",
        description: str = "",
    ) -> HookRegistration:
        """Register an ECC hook in the framework (disabled by default).

        Args:
            hook_id: ECC hook ID (e.g., 'ecc:hook:pre-commit')
            handler_name: Jarvis-native handler function name
            description: Human-readable description
        Returns:
            HookRegistration (disabled by default)
        """
        if hook_id not in ECC_HOOK_EVENT_MAP:
            raise ValueError(
                f"Unknown hook_id '{hook_id}'. Known hooks: {list(ECC_HOOK_EVENT_MAP.keys())}"
            )

        event = ECC_HOOK_EVENT_MAP[hook_id]
        reg = HookRegistration(
            hook_id=hook_id,
            event=event,
            handler_name=handler_name,
            enabled=False,
            reviewer_approved=False,
            description=description or f"ECC hook adapter for {hook_id}",
        )
        self._hooks[hook_id] = reg
        return reg

    def set_approved(self, hook_id: str, approved: bool) -> None:
        """Set reviewer approval for a specific hook."""
        if hook_id not in self._hooks:
            raise KeyError(f"Hook '{hook_id}' not registered. Call register() first.")
        self._hooks[hook_id].reviewer_approved = approved and self._framework_approved

    def enable(self, hook_id: str) -> None:
        """Enable a hook (requires reviewer_approved=True)."""
        if hook_id not in self._hooks:
            raise KeyError(f"Hook '{hook_id}' not registered.")
        self._hooks[hook_id].enable()

    def disable(self, hook_id: str) -> None:
        """Disable a specific hook (rollback path)."""
        if hook_id in self._hooks:
            self._hooks[hook_id].disable()

    def disable_all(self) -> None:
        """Disable all hooks (emergency rollback)."""
        for reg in self._hooks.values():
            reg.disable()
        self._framework_approved = False

    def fire(self, hook_id: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Fire a hook event with context.

        Args:
            hook_id: ECC hook ID to fire
            context: Event context dictionary
        Returns:
            Dict with status and result
        """
        if hook_id not in self._hooks:
            return {"status": "NOT_REGISTERED", "hook_id": hook_id}

        reg = self._hooks[hook_id]

        if not reg.enabled:
            return {
                "status": "DISABLED",
                "hook_id": hook_id,
                "reason": "Hook is disabled. Enable after Bryan approves hook framework.",
                "plan1_state": ECC_HOOK_PLAN1_STATE,
            }

        if not reg.reviewer_approved:
            raise HookGateError(f"Hook '{hook_id}' fired but reviewer_approved=False")

        if self._dry_run:
            return {
                "status": "DRY_RUN",
                "hook_id": hook_id,
                "event": reg.event.value,
                "handler": reg.handler_name,
                "context_keys": list(context.keys()) if context else [],
            }

        return {
            "status": "EXECUTED",
            "hook_id": hook_id,
            "event": reg.event.value,
            "handler": reg.handler_name,
            "result": "noop — live handler not implemented until framework wired",
        }

    def get_status(self) -> Dict[str, Any]:
        """Return framework status for API/CLI reporting."""
        return {
            "framework_approved": self._framework_approved,
            "dry_run": self._dry_run,
            "registered_hooks": len(self._hooks),
            "enabled_hooks": sum(1 for r in self._hooks.values() if r.enabled),
            "hooks": {hid: r.as_dict() for hid, r in self._hooks.items()},
            "plan1_state": ECC_HOOK_PLAN1_STATE,
            "activation_route": (
                "1. Bryan approves hook framework: set_framework_approved(True) "
                "2. Set approved per hook: set_approved(hook_id, True) "
                "3. Enable: enable(hook_id) "
                "4. Wire into Jarvis event bus"
            ),
            "rollback_path": "Call disable_all() to emergency-disable all hooks",
        }

    def mock_invocation(self, hook_id: str) -> Dict[str, Any]:
        """Mocked hook invocation for tests (no side effects)."""
        event = ECC_HOOK_EVENT_MAP.get(hook_id)
        return {
            "hook_id": hook_id,
            "event": event.value if event else "unknown",
            "dry_run": True,
            "result": "MOCKED_SUCCESS",
            "state": ECC_HOOK_PLAN1_STATE,
            "framework": "JarvisHookFramework",
        }


# Singleton framework instance (disabled by default)
_default_framework: Optional[JarvisHookFramework] = None


def get_hook_framework() -> JarvisHookFramework:
    """Return the singleton JarvisHookFramework instance."""
    global _default_framework
    if _default_framework is None:
        _default_framework = JarvisHookFramework()
        # Pre-register all ECC hooks (disabled by default)
        for hook_id in ECC_HOOK_EVENT_MAP:
            _default_framework.register(hook_id, description=f"ECC hook adapter for {hook_id}")
    return _default_framework


__all__ = [
    "HookEvent",
    "HookGateError",
    "HookRegistration",
    "JarvisHookFramework",
    "ECC_HOOK_EVENT_MAP",
    "ECC_HOOK_PLAN1_STATE",
    "get_hook_framework",
]
