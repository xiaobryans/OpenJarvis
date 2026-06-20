"""Safety wrappers for risky ECC candidate categories.

Provides scaffolding for hooks, scripts, plugins, and MCP configs that are
NOT yet safe to activate but need a defined path toward activation.

Key design rules:
  - No ECC code is executed by this module.
  - All wrappers default to DISABLED.
  - All wrappers carry dry_run=True by default.
  - All wrappers have an explicit enable/disable/quarantine path.
  - All wrappers require preflight_passed + reviewer_approved to activate.
  - Wrappers are not activated merely by constructing them.

Machine-readable: openjarvis.skills.wrappers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Base wrapper
# ---------------------------------------------------------------------------


@dataclass
class RiskyCandidate:
    """Base class for risky candidate wrappers (hooks/scripts/plugins/MCP).

    All risky candidates:
      - Start disabled (enabled=False, dry_run=True)
      - Require preflight_passed=True before enable
      - Require reviewer_approved=True before enable
      - Have a quarantine path
      - Have a rollback command
      - Cannot self-activate
    """
    candidate_id: str
    name: str
    category: str = ""                      # hook | script | plugin | mcp_config — set by subclass __post_init__
    source_url: str = "https://github.com/affaan-m/ECC"
    license_spdx: str = "MIT"
    enabled: bool = False                   # ALWAYS False by default
    dry_run: bool = True                    # ALWAYS True by default
    preflight_passed: bool = False
    reviewer_approved: bool = False
    reviewer_id: Optional[str] = None
    quarantined: bool = False
    quarantine_reason: Optional[str] = None
    permission_scopes: List[str] = field(default_factory=list)
    rollback_command: Optional[str] = None
    test_command: Optional[str] = None
    activation_blockers: List[str] = field(default_factory=list)
    notes: str = ""

    def is_usable(self) -> bool:
        """True only if enabled, not quarantined, preflight_passed, reviewer_approved."""
        return (
            self.enabled
            and not self.quarantined
            and self.preflight_passed
            and self.reviewer_approved
        )

    def enable(self, reviewer_id: str) -> None:
        """Enable this wrapper. Raises ValueError if gates not met."""
        if self.quarantined:
            raise ValueError(f"Cannot enable {self.candidate_id}: quarantined ({self.quarantine_reason})")
        if not self.preflight_passed:
            raise ValueError(f"Cannot enable {self.candidate_id}: preflight not passed")
        if not self.reviewer_approved:
            raise ValueError(f"Cannot enable {self.candidate_id}: reviewer not approved")
        self.enabled = True
        self.reviewer_id = reviewer_id

    def disable(self) -> None:
        """Disable this wrapper (soft disable)."""
        self.enabled = False

    def quarantine(self, reason: str) -> None:
        """Emergency quarantine — immediately blocks the wrapper."""
        self.enabled = False
        self.quarantined = True
        self.quarantine_reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "name": self.name,
            "category": self.category,
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "preflight_passed": self.preflight_passed,
            "reviewer_approved": self.reviewer_approved,
            "quarantined": self.quarantined,
            "quarantine_reason": self.quarantine_reason,
            "activation_blockers": self.activation_blockers,
            "is_usable": self.is_usable(),
        }


# ---------------------------------------------------------------------------
# Hook wrapper
# ---------------------------------------------------------------------------


@dataclass
class HookWrapper(RiskyCandidate):
    """Safety wrapper for ECC hook candidates.

    Hooks require Jarvis event system integration before activation.
    They must support:
      - dry_run mode (no side effects)
      - explicit event_scope (only specific events)
      - disable switch
      - rollback (remove from event registry)

    Activation blockers for all hooks:
      1. Jarvis event system integration not yet wired
      2. Event scope must be explicitly defined
      3. Dry-run mode required first
      4. Hook output must be logged and reviewable

    No ECC hook is executed by this module.
    """
    event_scope: List[str] = field(default_factory=list)   # e.g., ["after:file_edit"]
    hook_type: str = "unknown"                              # before | after | on_error
    can_abort: bool = False                                 # can hook abort the triggering event?
    timeout_ms: int = 5000

    def __post_init__(self) -> None:
        self.category = "hook"
        self.activation_blockers = [
            "Jarvis event system not yet wired for ECC hooks",
            "Requires explicit event_scope definition",
            "Must run in dry_run mode first",
            "Hook output must be logged for reviewer review",
        ]
        self.rollback_command = f"event_registry.remove_hook('{self.candidate_id}')"


@dataclass
class ScriptWrapper(RiskyCandidate):
    """Safety wrapper for ECC script candidates.

    Scripts require dry-run, command allowlist, and sandbox isolation.
    They must NOT be executed from this module.

    Activation blockers for all scripts:
      1. Command allowlist not yet defined
      2. Dry-run mode required first
      3. Sandbox/isolation not yet configured
      4. File system write scope must be bounded
      5. Network access must be explicitly approved

    No ECC script is executed by this module.
    """
    command_allowlist: List[str] = field(default_factory=list)
    working_dir: Optional[str] = None
    env_allowlist: List[str] = field(default_factory=list)   # allowed env var names
    max_runtime_sec: int = 30
    has_file_writes: Optional[bool] = None
    has_network: Optional[bool] = None

    def __post_init__(self) -> None:
        self.category = "script"
        self.activation_blockers = [
            "Command allowlist not yet defined for this script",
            "Dry-run mode required before live execution",
            "Sandbox/isolation not yet configured",
            "File system write scope must be bounded",
        ]
        self.rollback_command = f"script_registry.unregister('{self.candidate_id}')"


@dataclass
class PluginWrapper(RiskyCandidate):
    """Safety wrapper for ECC plugin candidates.

    Plugins require compatibility wrapper, isolation testing, and
    explicit loading gate before activation.

    No ECC plugin is loaded by this module.
    """
    plugin_format: str = "unknown"        # js | ts | python | other
    load_isolated: bool = True
    api_surface: List[str] = field(default_factory=list)
    conflicts_with: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.category = "plugin"
        self.activation_blockers = [
            "Plugin compatibility wrapper not yet built",
            "Isolation testing required before load",
            "API surface compatibility with Jarvis not verified",
            "Plugin loading gate not yet wired",
        ]
        self.rollback_command = f"plugin_registry.unload('{self.candidate_id}')"


@dataclass
class MCPConfigWrapper(RiskyCandidate):
    """Safety wrapper for ECC MCP config candidates.

    MCP configs require security review, permission scope audit, and
    explicit activation gate. They are disabled by default.

    No ECC MCP config is activated by this module.
    """
    server_names: List[str] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    requires_network: bool = True
    requires_filesystem: bool = False
    requires_shell: bool = False

    def __post_init__(self) -> None:
        self.category = "mcp_config"
        self.activation_blockers = [
            "Security review of MCP server permissions required",
            "Tool permission scope audit required",
            "MCP server must be sandboxed or explicitly trusted",
            "Each tool capability requires individual approval",
        ]
        self.rollback_command = f"mcp_registry.disable('{self.candidate_id}')"


# ---------------------------------------------------------------------------
# Pre-built wrappers for known ECC risky candidates
# ---------------------------------------------------------------------------

# Hooks from ECC (.cursor/hooks/)
KNOWN_HOOKS: List[HookWrapper] = [
    HookWrapper(
        candidate_id="ecc:hook:adapter",
        name="adapter",
        event_scope=["any"],
        hook_type="middleware",
        notes="ECC adapter hook — converts between harness event formats. Needs Jarvis event wiring.",
    ),
    HookWrapper(
        candidate_id="ecc:hook:after-file-edit",
        name="after-file-edit",
        event_scope=["after:file_edit"],
        hook_type="after",
        notes="ECC post-edit hook — may run formatters or validators. Needs dry-run first.",
    ),
    HookWrapper(
        candidate_id="ecc:hook:after-mcp-execution",
        name="after-mcp-execution",
        event_scope=["after:mcp_tool_call"],
        hook_type="after",
        notes="ECC post-MCP hook — logs MCP results. Needs MCP event integration.",
    ),
    HookWrapper(
        candidate_id="ecc:hook:after-shell-execution",
        name="after-shell-execution",
        event_scope=["after:shell_command"],
        hook_type="after",
        notes="ECC post-shell hook — risk: can read shell output and send to external. Hold.",
    ),
    HookWrapper(
        candidate_id="ecc:hook:before-tool-call",
        name="before-tool-call",
        event_scope=["before:tool_call"],
        hook_type="before",
        can_abort=True,
        notes="ECC pre-tool hook — can abort tool calls. High-risk; needs careful gate.",
    ),
    HookWrapper(
        candidate_id="ecc:hook:notification",
        name="notification",
        event_scope=["on:notification"],
        hook_type="event",
        notes="ECC notification hook — may send to external. HOLD until outbound gate verified.",
    ),
]

# Scripts from ECC (register but do not execute)
KNOWN_SCRIPTS: List[ScriptWrapper] = [
    ScriptWrapper(
        candidate_id="ecc:script:install",
        name="install",
        has_network=True,
        has_file_writes=True,
        notes="ECC install.sh — installs ECC components. HOLD: destructive, network, file writes.",
    ),
    ScriptWrapper(
        candidate_id="ecc:script:uninstall",
        name="uninstall",
        has_network=False,
        has_file_writes=True,
        notes="ECC uninstall.sh — removes ECC files. HOLD: destructive file operations.",
    ),
    ScriptWrapper(
        candidate_id="ecc:script:merge-mcp-config",
        name="merge-mcp-config",
        has_network=False,
        has_file_writes=True,
        notes="ECC MCP config merger. HOLD: file writes to MCP config; needs security review.",
    ),
]

# Plugins from ECC
KNOWN_PLUGINS: List[PluginWrapper] = [
    PluginWrapper(
        candidate_id="ecc:plugin:marketplace",
        name="marketplace",
        plugin_format="json",
        notes="ECC plugin marketplace manifest. Low risk (JSON only), but needs compatibility check.",
    ),
    PluginWrapper(
        candidate_id="ecc:plugin:ecc-hooks",
        name="ecc-hooks",
        plugin_format="ts",
        api_surface=["hooks"],
        notes="ECC hooks plugin (TypeScript). Needs Jarvis plugin loading gate and isolation.",
    ),
    PluginWrapper(
        candidate_id="ecc:plugin:index",
        name="index",
        plugin_format="ts",
        notes="ECC plugin index. Entry point for ECC plugin system. Needs compatibility wrapper.",
    ),
    PluginWrapper(
        candidate_id="ecc:plugin:changed-files-store",
        name="changed-files-store",
        plugin_format="ts",
        api_surface=["filesystem:read"],
        notes="ECC changed-files tracker. Reads filesystem — needs read-only scope verification.",
    ),
]

# MCP configs from ECC
KNOWN_MCP_CONFIGS: List[MCPConfigWrapper] = [
    MCPConfigWrapper(
        candidate_id="ecc:mcp:mcp-servers",
        name="mcp-servers",
        requires_network=True,
        requires_filesystem=True,
        notes="ECC MCP servers config — registers multiple MCP servers. HOLD: security review required.",
    ),
]


# ---------------------------------------------------------------------------
# Wrapper registry — query interface
# ---------------------------------------------------------------------------


class WrapperRegistry:
    """Registry for all risky candidate wrappers."""

    def __init__(self) -> None:
        self._hooks: Dict[str, HookWrapper] = {h.candidate_id: h for h in KNOWN_HOOKS}
        self._scripts: Dict[str, ScriptWrapper] = {s.candidate_id: s for s in KNOWN_SCRIPTS}
        self._plugins: Dict[str, PluginWrapper] = {p.candidate_id: p for p in KNOWN_PLUGINS}
        self._mcp: Dict[str, MCPConfigWrapper] = {m.candidate_id: m for m in KNOWN_MCP_CONFIGS}

    def get(self, candidate_id: str) -> Optional[RiskyCandidate]:
        return (
            self._hooks.get(candidate_id)
            or self._scripts.get(candidate_id)
            or self._plugins.get(candidate_id)
            or self._mcp.get(candidate_id)
        )

    def list_all(self) -> List[RiskyCandidate]:
        return (
            list(self._hooks.values())
            + list(self._scripts.values())
            + list(self._plugins.values())
            + list(self._mcp.values())
        )

    def list_enabled(self) -> List[RiskyCandidate]:
        return [c for c in self.list_all() if c.is_usable()]

    def list_hooks(self) -> List[HookWrapper]:
        return list(self._hooks.values())

    def list_scripts(self) -> List[ScriptWrapper]:
        return list(self._scripts.values())

    def list_plugins(self) -> List[PluginWrapper]:
        return list(self._plugins.values())

    def list_mcp_configs(self) -> List[MCPConfigWrapper]:
        return list(self._mcp.values())

    def register_hook(self, hook: HookWrapper) -> None:
        self._hooks[hook.candidate_id] = hook

    def register_script(self, script: ScriptWrapper) -> None:
        self._scripts[script.candidate_id] = script

    def register_plugin(self, plugin: PluginWrapper) -> None:
        self._plugins[plugin.candidate_id] = plugin

    def register_mcp(self, mcp: MCPConfigWrapper) -> None:
        self._mcp[mcp.candidate_id] = mcp

    def summary(self) -> Dict[str, Any]:
        """Return a summary of all risky candidates."""
        all_items = self.list_all()
        return {
            "total": len(all_items),
            "hooks": len(self._hooks),
            "scripts": len(self._scripts),
            "plugins": len(self._plugins),
            "mcp_configs": len(self._mcp),
            "enabled": len(self.list_enabled()),
            "disabled": sum(1 for c in all_items if not c.enabled),
            "quarantined": sum(1 for c in all_items if c.quarantined),
            "no_ecc_code_executed": True,
            "all_default_disabled": all(not c.enabled for c in all_items),
        }


# Module-level singleton
_DEFAULT_REGISTRY = WrapperRegistry()


def get_wrapper_registry() -> WrapperRegistry:
    """Return the default wrapper registry singleton."""
    return _DEFAULT_REGISTRY


__all__ = [
    "RiskyCandidate",
    "HookWrapper",
    "ScriptWrapper",
    "PluginWrapper",
    "MCPConfigWrapper",
    "WrapperRegistry",
    "get_wrapper_registry",
    "KNOWN_HOOKS",
    "KNOWN_SCRIPTS",
    "KNOWN_PLUGINS",
    "KNOWN_MCP_CONFIGS",
]
