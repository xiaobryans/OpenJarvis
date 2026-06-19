"""Tests for dynamic agent roster — registry, personas, escalation, routing."""

from __future__ import annotations

import pytest

from openjarvis.agents.roster import (
    AgentPersona,
    AgentRoleType,
    AgentRosterRegistry,
    EscalationLevel,
    PersonaType,
    get_default_registry,
)


class TestRosterDefaults:
    def test_default_roster_has_cos(self):
        registry = AgentRosterRegistry(load_defaults=True)
        cos = registry.get("jarvis-cos")
        assert cos is not None
        assert cos.role_type == AgentRoleType.COS

    def test_default_roster_has_gm(self):
        registry = AgentRosterRegistry()
        gm = registry.get("jarvis-gm")
        assert gm is not None
        assert gm.role_type == AgentRoleType.GM

    def test_default_roster_has_managers(self):
        registry = AgentRosterRegistry()
        managers = registry.list_by_role(AgentRoleType.MANAGER)
        assert len(managers) >= 4
        manager_ids = {m.agent_id for m in managers}
        assert "jarvis-coding-manager" in manager_ids
        assert "jarvis-memory-manager" in manager_ids
        assert "jarvis-connector-manager" in manager_ids
        assert "jarvis-ops-safety-manager" in manager_ids

    def test_default_roster_has_virtual_workers(self):
        registry = AgentRosterRegistry()
        workers = registry.list_virtual_workers()
        assert len(workers) >= 2

    def test_virtual_workers_are_not_real_bots(self):
        registry = AgentRosterRegistry()
        workers = registry.list_virtual_workers()
        for w in workers:
            assert w.persona_type == PersonaType.VIRTUAL
            # Virtual workers should NOT be real Slack bots
            assert w.persona_type != PersonaType.REAL_SLACK_BOT

    def test_real_bots_bounded(self):
        registry = AgentRosterRegistry()
        real_bots = registry.list_real_bots()
        # Must not create 100+ real Slack apps
        assert len(real_bots) <= 20


class TestRegistryDynamic:
    def test_adding_new_manager_updates_roster(self):
        registry = AgentRosterRegistry(load_defaults=False)
        new_manager = AgentPersona(
            agent_id="jarvis-analytics-manager",
            display_name="Jarvis Analytics Manager",
            role_type=AgentRoleType.MANAGER,
            persona_type=PersonaType.REAL_SLACK_BOT,
            escalation_level=EscalationLevel.MANAGER,
            primary_channel="jarvis-tasks",
            description="Analytics manager",
        )
        registry.register(new_manager)
        assert registry.get("jarvis-analytics-manager") is not None
        managers = registry.list_by_role(AgentRoleType.MANAGER)
        assert any(m.agent_id == "jarvis-analytics-manager" for m in managers)

    def test_adding_new_worker_creates_virtual_mapping(self):
        registry = AgentRosterRegistry(load_defaults=False)
        new_worker = AgentPersona(
            agent_id="worker-data-analyst",
            display_name="data-analyst",
            role_type=AgentRoleType.WORKER,
            persona_type=PersonaType.VIRTUAL,
            escalation_level=EscalationLevel.WORKER,
            primary_channel="jarvis-tasks",
            description="Analyzes data",
            parent_agent_id="jarvis-research-manager",
        )
        registry.register(new_worker)
        workers = registry.list_virtual_workers()
        assert any(w.agent_id == "worker-data-analyst" for w in workers)
        # Must remain virtual
        assert registry.get("worker-data-analyst").persona_type == PersonaType.VIRTUAL


class TestEscalationChain:
    def test_worker_escalates_to_manager(self):
        registry = AgentRosterRegistry(load_defaults=True)
        chain = registry.get_escalation_chain("worker-repo-inspector")
        agent_ids = [a.agent_id for a in chain]
        assert "worker-repo-inspector" in agent_ids
        # Manager should be in chain
        assert "jarvis-coding-manager" in agent_ids

    def test_escalation_includes_gm_and_cos(self):
        registry = AgentRosterRegistry(load_defaults=True)
        chain = registry.get_escalation_chain("worker-repo-inspector")
        agent_ids = [a.agent_id for a in chain]
        assert "jarvis-gm" in agent_ids
        assert "jarvis-cos" in agent_ids

    def test_escalation_no_infinite_loop(self):
        registry = AgentRosterRegistry(load_defaults=True)
        chain = registry.get_escalation_chain("jarvis-cos")
        # Should terminate
        assert len(chain) < 20

    def test_escalation_unknown_agent_returns_empty(self):
        registry = AgentRosterRegistry(load_defaults=False)
        chain = registry.get_escalation_chain("nonexistent-agent")
        assert chain == []


class TestChannelRouting:
    def test_routing_to_jarvis_ops(self):
        registry = AgentRosterRegistry(load_defaults=True)
        agents = registry.get_channel_routing("jarvis-ops")
        assert len(agents) > 0

    def test_routing_to_coding_channel(self):
        registry = AgentRosterRegistry(load_defaults=True)
        agents = registry.get_channel_routing("jarvis-coding")
        agent_ids = {a.agent_id for a in agents}
        assert "jarvis-coding-manager" in agent_ids


class TestSlackMessageFormatting:
    def test_manager_format(self):
        registry = AgentRosterRegistry(load_defaults=True)
        msg = registry.format_slack_message("jarvis-gm", "Escalating blocker to Bryan.")
        assert "[Jarvis GM]" in msg
        assert "Escalating blocker" in msg

    def test_worker_format(self):
        registry = AgentRosterRegistry(load_defaults=True)
        msg = registry.format_slack_message("worker-repo-inspector", "Found 3 changed files.")
        assert "[Worker: repo-inspector]" in msg
        assert "Found 3 changed files" in msg

    def test_unknown_agent_format(self):
        registry = AgentRosterRegistry(load_defaults=False)
        msg = registry.format_slack_message("unknown-agent", "Test message")
        assert "[unknown-agent]" in msg


class TestManifestExport:
    def test_to_manifest_has_required_keys(self):
        registry = AgentRosterRegistry(load_defaults=True)
        manifest = registry.to_manifest()
        assert "real_slack_bots" in manifest
        assert "virtual_workers" in manifest
        assert "total_agents" in manifest
        assert "escalation_protocol" in manifest

    def test_manifest_escalation_protocol(self):
        registry = AgentRosterRegistry(load_defaults=True)
        manifest = registry.to_manifest()
        protocol = manifest["escalation_protocol"]
        assert "Worker" in protocol
        assert "COS" in protocol
        assert "Bryan" in protocol


class TestDefaultRegistry:
    def test_default_registry_is_singleton(self):
        r1 = get_default_registry()
        r2 = get_default_registry()
        assert r1 is r2

    def test_default_registry_has_defaults(self):
        registry = get_default_registry()
        assert registry.get("jarvis-cos") is not None
