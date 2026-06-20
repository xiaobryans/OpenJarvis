"""Jarvis Plugin Loading Gate — isolation scaffold for ECC plugins.

Provides a safe, disabled-by-default plugin loading gate that:
  - Wraps all 5 ECC plugins behind an isolation scaffold
  - Enforces reviewer_approved gate (all plugins disabled until Bryan approves)
  - Prevents global state pollution (each plugin loads in isolated namespace)
  - Provides rollback/quarantine/disable path per plugin
  - Never raw-loads ECC plugin code

ECC plugins covered:
  1. ecc:plugin:marketplace
  2. ecc:plugin:ecc-hooks
  3. ecc:plugin:index
  4. ecc:plugin:changed-files-store
  5. ecc:plugin:lib

All plugins stay in state: READY_BUT_WAITING_FOR_APPROVAL
Activation requires: Bryan's approval + isolation test pass + loading gate review.

Machine-readable: openjarvis.skills.sources.ecc.plugins.jarvis_plugin_gate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


ECC_KNOWN_PLUGINS = [
    "ecc:plugin:marketplace",
    "ecc:plugin:ecc-hooks",
    "ecc:plugin:index",
    "ecc:plugin:changed-files-store",
    "ecc:plugin:lib",
]

ECC_PLUGIN_PLAN1_STATE = "READY_BUT_WAITING_FOR_APPROVAL"

# Plugin metadata
ECC_PLUGIN_METADATA: Dict[str, Dict[str, str]] = {
    "ecc:plugin:marketplace": {
        "name": "marketplace",
        "description": "ECC skill marketplace/discovery plugin",
        "risk": "medium — loads external skill manifests",
        "isolation_requirement": "Load in sandboxed namespace; no global state",
    },
    "ecc:plugin:ecc-hooks": {
        "name": "ecc-hooks",
        "description": "ECC event hooks plugin — must not bypass JarvisHookFramework",
        "risk": "high — can intercept Jarvis events",
        "isolation_requirement": "Must go through JarvisHookFramework adapter only",
    },
    "ecc:plugin:index": {
        "name": "index",
        "description": "ECC index/registry plugin",
        "risk": "low — read-only index access",
        "isolation_requirement": "Read-only namespace; no writes to global index",
    },
    "ecc:plugin:changed-files-store": {
        "name": "changed-files-store",
        "description": "Tracks changed files across sessions",
        "risk": "medium — file system read/write",
        "isolation_requirement": "Restrict to workspace directory only; no home dir access",
    },
    "ecc:plugin:lib": {
        "name": "lib",
        "description": "ECC shared library/utilities plugin",
        "risk": "low — shared utility functions",
        "isolation_requirement": "Import-only; no side effects on load",
    },
}


class PluginGateError(RuntimeError):
    """Raised when plugin loading is blocked by safety gate."""


@dataclass
class PluginRegistration:
    """A registered plugin in the loading gate (disabled by default)."""

    plugin_id: str
    name: str
    description: str
    risk: str
    isolation_requirement: str
    enabled: bool = False
    reviewer_approved: bool = False
    isolation_tested: bool = False

    def enable(self) -> None:
        if not self.reviewer_approved:
            raise PluginGateError(
                f"Plugin '{self.plugin_id}' cannot be enabled: reviewer_approved=False. "
                "Bryan must explicitly approve plugin loading gate."
            )
        if not self.isolation_tested:
            raise PluginGateError(
                f"Plugin '{self.plugin_id}' cannot be enabled: isolation test not passed. "
                "Run isolation tests first."
            )
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
        self.reviewer_approved = False

    def quarantine(self) -> None:
        """Quarantine plugin — disable and mark for review."""
        self.enabled = False
        self.reviewer_approved = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "description": self.description,
            "risk": self.risk,
            "isolation_requirement": self.isolation_requirement,
            "enabled": self.enabled,
            "reviewer_approved": self.reviewer_approved,
            "isolation_tested": self.isolation_tested,
            "plan1_state": ECC_PLUGIN_PLAN1_STATE,
        }


class JarvisPluginGate:
    """Jarvis-native plugin loading gate for ECC plugins.

    Usage:
        gate = JarvisPluginGate()
        # Register a plugin (disabled by default)
        gate.register("ecc:plugin:index")
        # Get status
        gate.get_status()
        # Enable only after Bryan approves AND isolation test passes:
        # gate.set_approved("ecc:plugin:index", approved=True)
        # gate.mark_isolation_tested("ecc:plugin:index")
        # gate.enable("ecc:plugin:index")
    """

    def __init__(self) -> None:
        self._plugins: Dict[str, PluginRegistration] = {}
        self._gate_approved: bool = False

    def set_gate_approved(self, approved: bool) -> None:
        """Set gate-level approval (Bryan's explicit approval for plugin loading)."""
        self._gate_approved = approved

    def register(self, plugin_id: str) -> PluginRegistration:
        """Register a plugin in the gate (disabled by default).

        Args:
            plugin_id: ECC plugin ID (e.g., 'ecc:plugin:index')
        Returns:
            PluginRegistration (disabled by default)
        """
        if plugin_id not in ECC_KNOWN_PLUGINS:
            raise ValueError(
                f"Unknown plugin_id '{plugin_id}'. Known plugins: {ECC_KNOWN_PLUGINS}"
            )
        meta = ECC_PLUGIN_METADATA[plugin_id]
        reg = PluginRegistration(
            plugin_id=plugin_id,
            name=meta["name"],
            description=meta["description"],
            risk=meta["risk"],
            isolation_requirement=meta["isolation_requirement"],
            enabled=False,
            reviewer_approved=False,
            isolation_tested=False,
        )
        self._plugins[plugin_id] = reg
        return reg

    def set_approved(self, plugin_id: str, approved: bool) -> None:
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin '{plugin_id}' not registered.")
        self._plugins[plugin_id].reviewer_approved = approved and self._gate_approved

    def mark_isolation_tested(self, plugin_id: str) -> None:
        """Mark a plugin as having passed isolation testing."""
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin '{plugin_id}' not registered.")
        self._plugins[plugin_id].isolation_tested = True

    def enable(self, plugin_id: str) -> None:
        if plugin_id not in self._plugins:
            raise KeyError(f"Plugin '{plugin_id}' not registered.")
        self._plugins[plugin_id].enable()

    def disable(self, plugin_id: str) -> None:
        if plugin_id in self._plugins:
            self._plugins[plugin_id].disable()

    def disable_all(self) -> None:
        """Emergency rollback: disable all plugins."""
        for reg in self._plugins.values():
            reg.disable()
        self._gate_approved = False

    def quarantine(self, plugin_id: str) -> None:
        if plugin_id in self._plugins:
            self._plugins[plugin_id].quarantine()

    def load(self, plugin_id: str) -> Dict[str, Any]:
        """Attempt to load a plugin (blocked unless approved + tested + enabled).

        Args:
            plugin_id: ECC plugin ID to load
        Returns:
            Dict with status and result
        """
        if plugin_id not in self._plugins:
            return {"status": "NOT_REGISTERED", "plugin_id": plugin_id}

        reg = self._plugins[plugin_id]

        if not reg.enabled:
            return {
                "status": "DISABLED",
                "plugin_id": plugin_id,
                "reason": (
                    "Plugin is disabled. Enable after: "
                    "(1) Bryan approves gate, (2) isolation test passes, (3) enable() called."
                ),
                "plan1_state": ECC_PLUGIN_PLAN1_STATE,
            }

        if not reg.reviewer_approved:
            raise PluginGateError(f"Plugin '{plugin_id}' loaded but reviewer_approved=False")

        return {
            "status": "LOAD_ATTEMPTED",
            "plugin_id": plugin_id,
            "name": reg.name,
            "result": "noop — actual ECC plugin loading not implemented; framework scaffold only",
        }

    def get_status(self) -> Dict[str, Any]:
        return {
            "gate_approved": self._gate_approved,
            "registered_plugins": len(self._plugins),
            "enabled_plugins": sum(1 for r in self._plugins.values() if r.enabled),
            "plugins": {pid: r.as_dict() for pid, r in self._plugins.items()},
            "plan1_state": ECC_PLUGIN_PLAN1_STATE,
            "activation_route": (
                "1. Bryan approves gate: set_gate_approved(True) "
                "2. Run isolation tests: mark_isolation_tested(plugin_id) "
                "3. Approve per plugin: set_approved(plugin_id, True) "
                "4. Enable: enable(plugin_id)"
            ),
            "rollback_path": "Call disable_all() to emergency-disable all plugins",
        }

    def mock_invocation(self, plugin_id: str) -> Dict[str, Any]:
        return {
            "plugin_id": plugin_id,
            "dry_run": True,
            "result": "MOCKED_SUCCESS",
            "state": ECC_PLUGIN_PLAN1_STATE,
            "framework": "JarvisPluginGate",
        }


# Singleton gate instance (all plugins disabled by default)
_default_gate: Optional[JarvisPluginGate] = None


def get_plugin_gate() -> JarvisPluginGate:
    """Return the singleton JarvisPluginGate instance."""
    global _default_gate
    if _default_gate is None:
        _default_gate = JarvisPluginGate()
        for plugin_id in ECC_KNOWN_PLUGINS:
            _default_gate.register(plugin_id)
    return _default_gate


__all__ = [
    "ECC_KNOWN_PLUGINS",
    "ECC_PLUGIN_METADATA",
    "ECC_PLUGIN_PLAN1_STATE",
    "PluginGateError",
    "PluginRegistration",
    "JarvisPluginGate",
    "get_plugin_gate",
]
