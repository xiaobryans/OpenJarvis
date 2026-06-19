"""Dynamic Agent Roster — registry-driven manager personas and virtual workers.

Architecture:
  - Real Slack personas = leadership + managers + notifications (bounded set)
  - Virtual personas = workers/sub-workers/specialist agents (unlimited)
  - Slack threads = task conversations (one task = one thread)
  - Slack channels = departments/workstreams
  - Telegram = Bryan fallback alerts

Escalation protocol:
  Worker → Manager → GM → COS → Bryan

Future-proofing:
  When a new manager, worker, COS/GM role, connector agent, or specialist is added,
  Jarvis MUST update:
    - internal agent registry
    - Slack persona/roster manifest
    - channel routing
    - escalation policy
    - notification mapping
    - docs/status

Do NOT create real Slack apps for workers by default.
Workers are virtual personas — they post via the manager's or Notifications bot.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent role types
# ---------------------------------------------------------------------------

class AgentRoleType(str, Enum):
    COS = "cos"                   # Chief of Staff
    GM = "gm"                     # General Manager
    MANAGER = "manager"           # Department manager
    WORKER = "worker"             # Virtual worker
    NOTIFICATIONS = "notifications"  # Notification bot
    CONNECTOR = "connector"       # External connector agent
    SPECIALIST = "specialist"     # Specialist sub-agent


class PersonaType(str, Enum):
    REAL_SLACK_BOT = "real_slack_bot"       # Real Slack app/bot persona
    VIRTUAL = "virtual"                      # Virtual — posts via parent bot


class EscalationLevel(int, Enum):
    WORKER = 1
    MANAGER = 2
    GM = 3
    COS = 4
    BRYAN = 5


# ---------------------------------------------------------------------------
# Manager persona / agent record
# ---------------------------------------------------------------------------

@dataclass
class AgentPersona:
    """Registry record for a Jarvis agent persona."""
    agent_id: str
    display_name: str
    role_type: AgentRoleType
    persona_type: PersonaType
    escalation_level: EscalationLevel
    primary_channel: str           # Primary Slack channel (without #)
    description: str
    slack_username: Optional[str] = None      # e.g. jarvis-cos
    slack_bot_configured: bool = False
    parent_agent_id: Optional[str] = None    # For workers: which manager owns them
    channel_routing: List[str] = field(default_factory=list)   # Channels this agent routes to
    tags: List[str] = field(default_factory=list)
    status: str = "DAILY_DRIVER_ACCEPT"
    registered_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "display_name": self.display_name,
            "role_type": self.role_type.value,
            "persona_type": self.persona_type.value,
            "escalation_level": self.escalation_level.value,
            "primary_channel": self.primary_channel,
            "description": self.description,
            "slack_username": self.slack_username,
            "slack_bot_configured": self.slack_bot_configured,
            "parent_agent_id": self.parent_agent_id,
            "channel_routing": self.channel_routing,
            "tags": self.tags,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Built-in roster (initial manifest)
# ---------------------------------------------------------------------------

def _build_default_roster() -> List[AgentPersona]:
    """Default Jarvis agent roster — real Slack bots (bounded) + virtual workers."""
    return [
        # ── Leadership tier ──────────────────────────────────────────────
        AgentPersona(
            agent_id="jarvis-hq",
            display_name="Jarvis HQ / Front Desk",
            role_type=AgentRoleType.NOTIFICATIONS,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.BRYAN,
            primary_channel="jarvis-ops",
            description="Main Jarvis HQ bot. Front desk, announcements, and ops notifications.",
            slack_username="jarvis-hq",
            channel_routing=["jarvis-ops", "jarvis-tasks", "jarvis-approvals"],
            tags=["hq", "notifications", "front-desk"],
        ),
        AgentPersona(
            agent_id="jarvis-cos",
            display_name="Jarvis COS",
            role_type=AgentRoleType.COS,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.COS,
            primary_channel="jarvis-ops",
            description="Chief of Staff. Coordinates GM and managers. Escalates to Bryan.",
            slack_username="jarvis-cos",
            channel_routing=["jarvis-ops", "jarvis-approvals"],
            tags=["cos", "leadership", "escalation"],
        ),
        AgentPersona(
            agent_id="jarvis-gm",
            display_name="Jarvis GM",
            role_type=AgentRoleType.GM,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.GM,
            primary_channel="jarvis-ops",
            description="General Manager. Oversees all department managers. Reports to COS.",
            slack_username="jarvis-gm",
            channel_routing=["jarvis-ops", "jarvis-tasks"],
            tags=["gm", "leadership"],
        ),

        # ── Department Managers ──────────────────────────────────────────
        AgentPersona(
            agent_id="jarvis-coding-manager",
            display_name="Jarvis Coding Manager",
            role_type=AgentRoleType.MANAGER,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-coding",
            description="Manages coding workers: repo-inspector, test-runner, linter, refactor agents.",
            slack_username="jarvis-coding-mgr",
            channel_routing=["jarvis-coding", "jarvis-debug", "jarvis-tasks"],
            tags=["coding", "manager"],
        ),
        AgentPersona(
            agent_id="jarvis-research-manager",
            display_name="Jarvis Research Manager",
            role_type=AgentRoleType.MANAGER,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-tasks",
            description="Manages research and intelligence workers.",
            slack_username="jarvis-research-mgr",
            channel_routing=["jarvis-tasks"],
            tags=["research", "manager"],
        ),
        AgentPersona(
            agent_id="jarvis-memory-manager",
            display_name="Jarvis Memory Manager",
            role_type=AgentRoleType.MANAGER,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-memory",
            description="Manages memory workers: cloud sync, Obsidian export, correction agents.",
            slack_username="jarvis-memory-mgr",
            channel_routing=["jarvis-memory", "jarvis-debug"],
            tags=["memory", "manager"],
        ),
        AgentPersona(
            agent_id="jarvis-connector-manager",
            display_name="Jarvis Connector Manager",
            role_type=AgentRoleType.MANAGER,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-connectors",
            description="Manages connector agents: Slack, Telegram, Gmail (when enabled), etc.",
            slack_username="jarvis-connector-mgr",
            channel_routing=["jarvis-connectors", "jarvis-ops"],
            tags=["connectors", "manager"],
        ),
        AgentPersona(
            agent_id="jarvis-ops-safety-manager",
            display_name="Jarvis Ops/Safety Manager",
            role_type=AgentRoleType.MANAGER,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-ops",
            description="Manages safety policy, audit, and ops compliance. Blocks unsafe actions.",
            slack_username="jarvis-ops-safety-mgr",
            channel_routing=["jarvis-ops", "jarvis-debug", "jarvis-approvals"],
            tags=["ops", "safety", "manager"],
        ),
        AgentPersona(
            agent_id="jarvis-notifications",
            display_name="Jarvis Notifications",
            role_type=AgentRoleType.NOTIFICATIONS,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-alerts",
            description="Notification bot. Posts alerts, summaries, and Telegram fallback triggers.",
            slack_username="jarvis-notifications",
            channel_routing=["jarvis-alerts", "jarvis-ops", "jarvis-approvals"],
            tags=["notifications", "alerts"],
        ),

        # ── Virtual Workers (default set — extensible via registry) ──────
        AgentPersona(
            agent_id="worker-repo-inspector",
            display_name="repo-inspector",
            role_type=AgentRoleType.WORKER,
            persona_type=PersonaType.VIRTUAL,
            escalation_level=EscalationLevel.WORKER,
            primary_channel="jarvis-coding",
            description="Scans changed files, diffs, and structure. Reports to Coding Manager.",
            parent_agent_id="jarvis-coding-manager",
            tags=["coding", "worker", "inspector"],
        ),
        AgentPersona(
            agent_id="worker-test-runner",
            display_name="test-runner",
            role_type=AgentRoleType.WORKER,
            persona_type=PersonaType.VIRTUAL,
            escalation_level=EscalationLevel.WORKER,
            primary_channel="jarvis-coding",
            description="Runs targeted tests. Reports pass/fail to Coding Manager.",
            parent_agent_id="jarvis-coding-manager",
            tags=["coding", "worker", "testing"],
        ),
        AgentPersona(
            agent_id="worker-obsidian-exporter",
            display_name="obsidian-exporter",
            role_type=AgentRoleType.WORKER,
            persona_type=PersonaType.VIRTUAL,
            escalation_level=EscalationLevel.WORKER,
            primary_channel="jarvis-memory",
            description="Exports sprint summaries, decisions, blocker ledger to Obsidian vault.",
            parent_agent_id="jarvis-memory-manager",
            tags=["memory", "worker", "obsidian"],
        ),
        AgentPersona(
            agent_id="worker-memory-sync",
            display_name="memory-sync",
            role_type=AgentRoleType.WORKER,
            persona_type=PersonaType.VIRTUAL,
            escalation_level=EscalationLevel.WORKER,
            primary_channel="jarvis-memory",
            description="Syncs local memory to cloud backend when credentials are available.",
            parent_agent_id="jarvis-memory-manager",
            tags=["memory", "worker", "cloud"],
        ),
    ]


# ---------------------------------------------------------------------------
# Agent Registry
# ---------------------------------------------------------------------------

class AgentRosterRegistry:
    """Registry-driven agent roster.

    Supports:
    - Manager/COS/GM persona registration
    - Virtual worker registration
    - Channel routing lookup
    - Escalation chain computation
    - Slack message formatting
    - Future manager/worker addition without hardcoded lists
    """

    def __init__(self, load_defaults: bool = True) -> None:
        self._agents: Dict[str, AgentPersona] = {}
        if load_defaults:
            for persona in _build_default_roster():
                self._agents[persona.agent_id] = persona

    def register(self, persona: AgentPersona) -> None:
        """Register a new agent. Updates routing and escalation automatically."""
        self._agents[persona.agent_id] = persona
        logger.info(
            "AgentRoster: registered %s (%s / %s)",
            persona.agent_id, persona.role_type.value, persona.persona_type.value,
        )

    def get(self, agent_id: str) -> Optional[AgentPersona]:
        return self._agents.get(agent_id)

    def list_all(self) -> List[AgentPersona]:
        return list(self._agents.values())

    def list_by_role(self, role_type: AgentRoleType) -> List[AgentPersona]:
        return [a for a in self._agents.values() if a.role_type == role_type]

    def list_real_bots(self) -> List[AgentPersona]:
        return [a for a in self._agents.values() if a.persona_type == PersonaType.REAL_SLACK_BOT]

    def list_virtual_workers(self) -> List[AgentPersona]:
        return [a for a in self._agents.values() if a.persona_type == PersonaType.VIRTUAL]

    def get_escalation_chain(self, agent_id: str) -> List[AgentPersona]:
        """Return escalation chain: worker → manager → GM → COS → Bryan.

        Stops at highest registered level.
        """
        chain: List[AgentPersona] = []
        current = self._agents.get(agent_id)
        if not current:
            return chain

        chain.append(current)

        # Follow parent_agent_id chain
        visited = {agent_id}
        while current.parent_agent_id and current.parent_agent_id not in visited:
            parent = self._agents.get(current.parent_agent_id)
            if not parent:
                break
            chain.append(parent)
            visited.add(parent.agent_id)
            current = parent

        # Ensure GM and COS are at top if not already in chain
        for top_id in ("jarvis-gm", "jarvis-cos"):
            if top_id not in {a.agent_id for a in chain}:
                top = self._agents.get(top_id)
                if top:
                    chain.append(top)

        return chain

    def get_channel_routing(self, channel: str) -> List[AgentPersona]:
        """Return agents that route to a given channel."""
        channel = channel.lstrip("#")
        return [
            a for a in self._agents.values()
            if channel in a.channel_routing or a.primary_channel == channel
        ]

    def format_slack_message(
        self,
        agent_id: str,
        content: str,
        worker_name: Optional[str] = None,
    ) -> str:
        """Format a Slack message in visible Jarvis persona format.

        Examples:
            [Jarvis Coding Manager] Assigning task to repo-inspector.
            [Worker: repo-inspector] Found 3 changed files.
            [Jarvis GM] Escalating blocker to Bryan.
        """
        agent = self._agents.get(agent_id)
        if agent and agent.persona_type == PersonaType.VIRTUAL:
            prefix = f"[Worker: {agent.display_name}]"
        elif agent:
            prefix = f"[{agent.display_name}]"
        elif worker_name:
            prefix = f"[Worker: {worker_name}]"
        else:
            prefix = f"[{agent_id}]"
        return f"{prefix} {content}"

    def to_manifest(self) -> Dict[str, Any]:
        """Export full roster manifest."""
        return {
            "real_slack_bots": [a.to_dict() for a in self.list_real_bots()],
            "virtual_workers": [a.to_dict() for a in self.list_virtual_workers()],
            "total_agents": len(self._agents),
            "escalation_protocol": "Worker → Manager → GM → COS → Bryan",
        }


# ---------------------------------------------------------------------------
# Default global registry
# ---------------------------------------------------------------------------

_DEFAULT_REGISTRY: Optional[AgentRosterRegistry] = None


def get_default_registry() -> AgentRosterRegistry:
    """Get the default global agent roster registry (singleton per process)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = AgentRosterRegistry(load_defaults=True)
    return _DEFAULT_REGISTRY


__all__ = [
    "AgentPersona",
    "AgentRosterRegistry",
    "AgentRoleType",
    "PersonaType",
    "EscalationLevel",
    "get_default_registry",
]
