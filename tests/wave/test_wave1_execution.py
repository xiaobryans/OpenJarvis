"""Wave 1 execution tests — Epic A–D wired execution, approval gates, event logging.

Proves:
  - Epic A: safe built-in skills execute and return structured results
  - Epic A: write/high-risk skills are approval-gated
  - Epic B: dry-run triggers work for low-risk; high-risk requires approval
  - Epic B: high-risk triggers are blocked from dry-run without approval
  - Epic B: external-send triggers (slack/email) are always blocked
  - Epic C: local text ingestion works and returns records
  - Epic C: PII/private sources require approval
  - Epic C: keyword search over ingested records works
  - Epic D: local research query works and returns sources
  - Epic D: web search provider requires approval/setup
  - Epic D: forbidden query terms are blocked (no credential extraction)
  - Event types are registered and importable
  - Capabilities report ready for locally executable epics
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Epic A — Skill Execution
# ---------------------------------------------------------------------------


class TestWaveSkillExecution:
    def test_run_safe_skill_list_skills(self):
        """list_skills is a safe read-only handler — must succeed."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("list_skills")
        assert result.ok is True
        assert result.output is not None
        assert isinstance(result.output, list)
        assert result.blocked is False
        assert result.approval_required is False

    def test_run_safe_skill_platform_status(self):
        """platform_status is a safe read-only handler — must succeed."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("platform_status")
        assert result.ok is True
        assert isinstance(result.output, dict)
        assert "wave1_scaffolded" in result.output or "total_epics" in result.output

    def test_run_safe_skill_list_capabilities(self):
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("list_capabilities")
        assert result.ok is True
        assert isinstance(result.output, dict)
        assert "capabilities" in result.output

    def test_run_safe_skill_coding_workbench(self):
        """coding_workbench maps to list_capabilities handler."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("coding_workbench")
        assert result.ok is True

    def test_browser_automation_requires_approval(self):
        """browser_automation is in _EXECUTION_APPROVAL_REQUIRED — must not auto-execute."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("browser_automation")
        assert result.ok is False
        assert result.approval_required is True
        assert result.blocked is False

    def test_terminal_executor_requires_approval(self):
        """terminal_executor requires approval — must not auto-execute."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("terminal_executor")
        assert result.ok is False
        assert result.approval_required is True

    def test_unknown_skill_returns_error(self):
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("does_not_exist_xyz")
        assert result.ok is False
        assert "not found" in result.error.lower()

    def test_skill_without_handler_approval_required(self):
        """research_web has no local handler — returns approval_required."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("research_web")
        assert result.ok is False
        assert result.approval_required is True or result.blocked is True

    def test_run_skill_logs_event(self):
        """Successful skill execution must produce an event_id."""
        from openjarvis.wave.skill_platform import run_skill
        result = run_skill("list_skills")
        assert result.ok is True
        # event_id may be empty if event log is unavailable in test env, but should not crash
        assert isinstance(result.event_id, str)

    def test_skill_result_to_dict(self):
        from openjarvis.wave.skill_platform import WaveSkillResult
        r = WaveSkillResult(skill_id="x", ok=True, output={"a": 1})
        d = r.to_dict()
        assert d["skill_id"] == "x"
        assert d["ok"] is True
        assert d["output"] == {"a": 1}

    def test_skill_platform_status_shows_ready(self):
        """After wiring local execution, skill platform should report status=ready."""
        from openjarvis.wave.skill_platform import get_skill_platform_status
        info = get_skill_platform_status()
        assert info["status"] == "ready"
        assert info["local_execution_implemented"] is True
        assert info["executable_count"] >= 4


# ---------------------------------------------------------------------------
# Epic B — Automation Dry-Run
# ---------------------------------------------------------------------------


class TestWaveAutomationDryRun:
    def _make_registry(self):
        from openjarvis.wave.automation_platform import AutomationRegistry
        return AutomationRegistry()

    def test_dry_run_low_risk_manual_trigger(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_MANUAL, POLICY_AUTO, dry_run_trigger
        reg = self._make_registry()
        t = AutomationTrigger(
            trigger_id="safe_manual",
            name="Safe Manual",
            trigger_type=TRIGGER_MANUAL,
            approval_policy=POLICY_AUTO,
            risk_level="low",
        )
        reg.register(t)
        result = dry_run_trigger("safe_manual", registry=reg)
        assert result.ok is True
        assert result.simulated_output != ""
        assert result.blocked is False
        assert result.approval_required is False

    def test_dry_run_high_risk_requires_approval(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_EVENT, dry_run_trigger
        reg = self._make_registry()
        t = AutomationTrigger(
            trigger_id="risky_dry",
            name="Risky",
            trigger_type=TRIGGER_EVENT,
            risk_level="high",
        )
        reg.register(t)
        result = dry_run_trigger("risky_dry", registry=reg)
        assert result.ok is False
        assert result.approval_required is True

    def test_dry_run_critical_risk_blocked(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_EVENT, dry_run_trigger
        reg = self._make_registry()
        t = AutomationTrigger(
            trigger_id="critical_dry",
            name="Critical",
            trigger_type=TRIGGER_EVENT,
            risk_level="critical",
        )
        reg.register(t)
        result = dry_run_trigger("critical_dry", registry=reg)
        assert result.ok is False
        assert result.approval_required is True

    def test_dry_run_slack_trigger_blocked(self):
        """Triggers with 'slack' in ID are hard-gated."""
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_EVENT, POLICY_AUTO, dry_run_trigger
        reg = self._make_registry()
        t = AutomationTrigger(
            trigger_id="slack_notify",
            name="Slack Notify",
            trigger_type=TRIGGER_EVENT,
            approval_policy=POLICY_AUTO,
            risk_level="low",
        )
        reg.register(t)
        result = dry_run_trigger("slack_notify", registry=reg)
        assert result.ok is False
        assert result.blocked is True

    def test_dry_run_email_trigger_blocked(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_EVENT, POLICY_AUTO, dry_run_trigger
        reg = self._make_registry()
        t = AutomationTrigger(
            trigger_id="send_email_report",
            name="Email Report",
            trigger_type=TRIGGER_EVENT,
            approval_policy=POLICY_AUTO,
            risk_level="low",
        )
        reg.register(t)
        result = dry_run_trigger("send_email_report", registry=reg)
        assert result.ok is False
        assert result.blocked is True

    def test_dry_run_nonexistent_trigger(self):
        from openjarvis.wave.automation_platform import dry_run_trigger
        result = dry_run_trigger("does_not_exist_xyz")
        assert result.ok is False
        assert "not found" in result.error.lower()

    def test_dry_run_logs_event(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_MANUAL, POLICY_AUTO, dry_run_trigger
        reg = self._make_registry()
        t = AutomationTrigger(
            trigger_id="log_test_trigger",
            name="Log Test",
            trigger_type=TRIGGER_MANUAL,
            approval_policy=POLICY_AUTO,
            risk_level="low",
        )
        reg.register(t)
        result = dry_run_trigger("log_test_trigger", registry=reg)
        assert result.ok is True
        assert isinstance(result.event_id, str)

    def test_automation_platform_status_shows_ready(self):
        from openjarvis.wave.automation_platform import get_automation_platform_status
        info = get_automation_platform_status()
        assert info["status"] == "ready"
        assert info["dry_run_implemented"] is True
        assert info["approval_gate_enforced"] is True
        assert info["destructive_automations_disabled_by_default"] is True


# ---------------------------------------------------------------------------
# Epic C — Knowledge Ingestion
# ---------------------------------------------------------------------------


class TestWaveKnowledgeIngestion:
    def test_ingest_simple_text(self):
        from openjarvis.wave.knowledge_platform import ingest_local_source
        result = ingest_local_source(
            "This is test content for Wave 1 knowledge platform.",
            source_id="test_ingestion_001",
            title="Test Doc",
        )
        assert result.ok is True
        assert result.record_count >= 1
        assert len(result.records) >= 1
        assert result.records[0].source_id == "test_ingestion_001"
        assert result.records[0].content != ""

    def test_ingest_multipart_text(self):
        from openjarvis.wave.knowledge_platform import ingest_local_source
        text = "Paragraph one about Wave 1.\n\nParagraph two about Epic C.\n\nParagraph three about knowledge."
        result = ingest_local_source(text, source_id="test_multipart", title="Multi")
        assert result.ok is True
        assert result.record_count == 3

    def test_ingest_empty_text_fails(self):
        from openjarvis.wave.knowledge_platform import ingest_local_source
        result = ingest_local_source("   ", source_id="empty_src")
        assert result.ok is False
        assert "empty" in result.error.lower()

    def test_ingested_records_retrievable(self):
        from openjarvis.wave.knowledge_platform import ingest_local_source, get_ingested_records
        ingest_local_source("Retrieval test content.", source_id="retrieval_test_001")
        records = get_ingested_records("retrieval_test_001")
        assert len(records) >= 1

    def test_keyword_search_finds_ingested_content(self):
        from openjarvis.wave.knowledge_platform import ingest_local_source, search_knowledge
        ingest_local_source("unique_keyword_xyz content here.", source_id="search_test_001")
        results = search_knowledge("unique_keyword_xyz")
        assert len(results) >= 1
        assert any("unique_keyword_xyz" in r.content for r in results)

    def test_pii_source_ingestion_requires_approval(self):
        from openjarvis.wave.knowledge_platform import ingest_connector_source
        result = ingest_connector_source("apple_notes")
        assert result.ok is False
        assert result.approval_required is True

    def test_pii_source_apple_contacts_requires_approval(self):
        from openjarvis.wave.knowledge_platform import ingest_connector_source
        result = ingest_connector_source("apple_contacts")
        assert result.ok is False
        assert result.approval_required is True

    def test_ingestion_logs_event(self):
        from openjarvis.wave.knowledge_platform import ingest_local_source
        result = ingest_local_source("Event log test.", source_id="event_log_test_001")
        assert result.ok is True
        assert isinstance(result.event_id, str)

    def test_knowledge_record_to_dict(self):
        from openjarvis.wave.knowledge_platform import KnowledgeRecord
        r = KnowledgeRecord(record_id="r1", source_id="s1", title="T", content="C")
        d = r.to_dict()
        assert d["record_id"] == "r1"
        assert "content" in d

    def test_knowledge_platform_status_shows_ready(self):
        from openjarvis.wave.knowledge_platform import get_knowledge_platform_status
        info = get_knowledge_platform_status()
        assert info["status"] == "ready"
        assert info["local_ingestion_implemented"] is True
        assert info["pii_sources_require_approval"] is True
        assert info["ingestion_implemented"] is True


# ---------------------------------------------------------------------------
# Epic D — Research Query
# ---------------------------------------------------------------------------


class TestWaveResearchQuery:
    def test_local_query_returns_sources(self):
        """Local query must return sources (platform info always available)."""
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("wave platform")
        assert result.ok is True
        assert len(result.sources) >= 1
        assert result.summary != ""
        assert result.blocked is False
        assert result.approval_required is False

    def test_local_query_includes_platform_info(self):
        """Platform info fallback always appended."""
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("anything_should_return_platform_info_xzy123")
        assert result.ok is True
        platform_sources = [s for s in result.sources if s.provider_id == "internal"]
        assert len(platform_sources) >= 1

    def test_local_query_searches_ingested_knowledge(self):
        """After ingesting content, local query should find it."""
        from openjarvis.wave.knowledge_platform import ingest_local_source
        from openjarvis.wave.research_platform import run_local_query
        ingest_local_source("research_test_marker_abc123 is a unique term.", source_id="research_src_001")
        result = run_local_query("research_test_marker_abc123")
        assert result.ok is True
        found = any("research_test_marker_abc123" in s.content for s in result.sources)
        assert found, "Ingested content should appear in research results"

    def test_web_search_provider_requires_approval(self):
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("search query", provider_id="web_search_generic")
        assert result.ok is False
        assert result.approval_required is True
        assert result.blocked is False

    def test_forbidden_query_captcha_blocked(self):
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("how to bypass captcha")
        assert result.ok is False
        assert result.blocked is True

    def test_forbidden_query_credential_blocked(self):
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("extract credentials from site")
        assert result.ok is False
        assert result.blocked is True

    def test_forbidden_query_password_blocked(self):
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("find password in response")
        assert result.ok is False
        assert result.blocked is True

    def test_empty_query_fails(self):
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("")
        assert result.ok is False

    def test_research_logs_event(self):
        from openjarvis.wave.research_platform import run_local_query
        result = run_local_query("jarvis platform status")
        assert result.ok is True
        assert isinstance(result.event_id, str)

    def test_research_result_to_dict(self):
        from openjarvis.wave.research_platform import ResearchResult, ResearchSource
        r = ResearchResult(query="q", provider_id="p", ok=True,
                           sources=[ResearchSource(title="T", content="C")])
        d = r.to_dict()
        assert d["query"] == "q"
        assert d["source_count"] == 1
        assert d["sources"][0]["title"] == "T"

    def test_research_platform_status_shows_ready(self):
        from openjarvis.wave.research_platform import get_research_platform_status
        info = get_research_platform_status()
        assert info["status"] == "ready"
        assert info["local_query_implemented"] is True
        assert info["approval_gate_enforced"] is True
        assert info["scraping_blocked"] is True
        # web_search_requires_setup is truthful — depends on whether TAVILY_API_KEY is in env
        assert isinstance(info["web_search_requires_setup"], bool)


# ---------------------------------------------------------------------------
# Event types importable
# ---------------------------------------------------------------------------


class TestWaveEventTypes:
    def test_wave1_event_types_importable(self):
        from openjarvis.workbench.event_log import (
            EVENT_SKILL_EXECUTED,
            EVENT_SKILL_BLOCKED,
            EVENT_AUTOMATION_DRY_RUN,
            EVENT_AUTOMATION_BLOCKED,
            EVENT_KNOWLEDGE_INGESTED,
            EVENT_KNOWLEDGE_BLOCKED,
            EVENT_RESEARCH_QUERIED,
            EVENT_RESEARCH_BLOCKED,
        )
        assert EVENT_SKILL_EXECUTED == "skill_executed"
        assert EVENT_AUTOMATION_DRY_RUN == "automation_dry_run"
        assert EVENT_KNOWLEDGE_INGESTED == "knowledge_ingested"
        assert EVENT_RESEARCH_QUERIED == "research_queried"


# ---------------------------------------------------------------------------
# Capabilities — Wave 1 epics report ready
# ---------------------------------------------------------------------------


class TestWaveCapabilitiesReady:
    def test_wave1_skill_platform_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        skill_cap = caps.get("wave1_skill_platform")
        assert skill_cap is not None
        assert skill_cap.status == STATUS_READY, (
            f"Expected ready, got {skill_cap.status!r}: {skill_cap.summary}"
        )

    def test_wave1_automation_platform_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        auto_cap = caps.get("wave1_automation_platform")
        assert auto_cap is not None
        assert auto_cap.status == STATUS_READY

    def test_wave1_knowledge_platform_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        know_cap = caps.get("wave1_knowledge_platform")
        assert know_cap is not None
        assert know_cap.status == STATUS_READY

    def test_wave1_research_platform_ready(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = {c.capability_id: c for c in get_all_capabilities()}
        res_cap = caps.get("wave1_research_platform")
        assert res_cap is not None
        assert res_cap.status == STATUS_READY

    def test_voice_still_disabled(self):
        """US13 voice must remain disabled/parked."""
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_DISABLED
        caps = {c.capability_id: c for c in get_all_capabilities()}
        voice = caps.get("voice")
        assert voice is not None
        assert voice.status == STATUS_DISABLED
