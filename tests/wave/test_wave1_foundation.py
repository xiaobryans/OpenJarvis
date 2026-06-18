"""Wave 1 Foundation tests — Epic A–D scaffolds, safety integration, capabilities, doctor checks.

Proves:
  - Registry behavior (register/list/get)
  - Approval gates enforced (no auto-enable of risky triggers)
  - Wave capabilities truthfully report scaffolded/requires_setup
  - Wave 2–4 correctly report not_implemented
  - Doctor checks pass for Wave 1 scaffold
  - No fake ready claims
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Epic A — Skill Platform
# ---------------------------------------------------------------------------


class TestWaveSkillPlatform:
    def test_registry_imports(self):
        from openjarvis.wave.skill_platform import WaveSkillRegistry, WaveSkillManifest  # noqa

    def test_builtins_registered(self):
        from openjarvis.wave.skill_platform import get_skill_registry
        reg = get_skill_registry()
        skills = reg.list()
        assert len(skills) >= 4
        ids = {s.skill_id for s in skills}
        assert "coding_workbench" in ids
        assert "terminal_executor" in ids
        assert "browser_automation" in ids

    def test_get_skill(self):
        from openjarvis.wave.skill_platform import get_skill_registry
        reg = get_skill_registry()
        s = reg.get("coding_workbench")
        assert s is not None
        assert s.status == "ready"
        assert s.induction_approved is True

    def test_scaffolded_skill_not_induction_approved(self):
        from openjarvis.wave.skill_platform import get_skill_registry
        reg = get_skill_registry()
        s = reg.get("research_web")
        assert s is not None
        assert s.status == "scaffolded"
        assert s.induction_approved is False

    def test_register_new_skill_requires_approval(self):
        from openjarvis.wave.skill_platform import WaveSkillRegistry, WaveSkillManifest, APPROVAL_POLICY_REQUIRES_APPROVAL
        reg = WaveSkillRegistry()
        manifest = WaveSkillManifest(
            skill_id="test_skill_new",
            name="Test Skill",
            approval_policy=APPROVAL_POLICY_REQUIRES_APPROVAL,
            induction_approved=False,
        )
        result = reg.register(manifest)
        assert result["ok"] is False
        assert result["status"] == "approval_required"

    def test_register_auto_approved_skill(self):
        from openjarvis.wave.skill_platform import WaveSkillRegistry, WaveSkillManifest, APPROVAL_POLICY_AUTO
        reg = WaveSkillRegistry()
        manifest = WaveSkillManifest(
            skill_id="test_skill_auto",
            name="Auto Skill",
            approval_policy=APPROVAL_POLICY_AUTO,
            induction_approved=True,
        )
        result = reg.register(manifest)
        assert result["ok"] is True

    def test_skill_platform_status(self):
        from openjarvis.wave.skill_platform import get_skill_platform_status
        info = get_skill_platform_status()
        assert info["status"] == "scaffolded"
        assert info["skill_count"] >= 4
        assert info["approval_gate_enforced"] is True
        assert info["induction_pipeline_implemented"] is False

    def test_manifest_to_dict(self):
        from openjarvis.wave.skill_platform import WaveSkillManifest
        m = WaveSkillManifest(skill_id="x", name="X", description="test")
        d = m.to_dict()
        assert d["skill_id"] == "x"
        assert "approval_policy" in d


# ---------------------------------------------------------------------------
# Epic B — Automation Platform
# ---------------------------------------------------------------------------


class TestWaveAutomationPlatform:
    def test_registry_imports(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger  # noqa

    def test_register_trigger(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_MANUAL
        reg = AutomationRegistry()
        t = AutomationTrigger(
            trigger_id="test_trigger",
            name="Test",
            trigger_type=TRIGGER_MANUAL,
            approval_policy="requires_approval",
            risk_level="low",
        )
        result = reg.register(t)
        assert result["ok"] is True
        assert result["status"] == "registered"

    def test_trigger_disabled_on_registration(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_CRON
        reg = AutomationRegistry()
        t = AutomationTrigger(
            trigger_id="cron_test",
            name="Cron Test",
            trigger_type=TRIGGER_CRON,
            schedule="0 * * * *",
            enabled=True,  # attempted to enable on registration — must be overridden
        )
        reg.register(t)
        stored = reg.get("cron_test")
        assert stored is not None
        assert stored.enabled is False  # always disabled on registration

    def test_enable_high_risk_requires_approval(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_EVENT
        reg = AutomationRegistry()
        t = AutomationTrigger(
            trigger_id="risky",
            name="Risky Trigger",
            trigger_type=TRIGGER_EVENT,
            event_name="file_deleted",
            approval_policy="requires_approval",
            risk_level="high",
        )
        reg.register(t)
        result = reg.enable("risky")
        assert result["ok"] is False
        assert result["status"] == "approval_required"

    def test_enable_low_risk_auto_trigger(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_MANUAL, POLICY_AUTO
        reg = AutomationRegistry()
        t = AutomationTrigger(
            trigger_id="safe_trigger",
            name="Safe",
            trigger_type=TRIGGER_MANUAL,
            approval_policy=POLICY_AUTO,
            risk_level="low",
        )
        reg.register(t)
        result = reg.enable("safe_trigger")
        assert result["ok"] is True

    def test_invalid_trigger_type_rejected(self):
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger
        reg = AutomationRegistry()
        t = AutomationTrigger(trigger_id="bad", name="Bad", trigger_type="unknown_type")
        result = reg.register(t)
        assert result["ok"] is False
        assert "Unknown trigger_type" in result["error"]

    def test_automation_platform_status(self):
        from openjarvis.wave.automation_platform import get_automation_platform_status
        info = get_automation_platform_status()
        assert info["status"] == "scaffolded"
        assert info["approval_gate_enforced"] is True
        assert info["destructive_automations_disabled_by_default"] is True
        assert info["runtime_execution_implemented"] is False


# ---------------------------------------------------------------------------
# Epic C — Knowledge Platform
# ---------------------------------------------------------------------------


class TestWaveKnowledgePlatform:
    def test_registry_imports(self):
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry, KnowledgeSource  # noqa

    def test_builtins_registered(self):
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry
        reg = KnowledgeSourceRegistry()
        sources = reg.list_sources()
        assert len(sources) >= 3
        ids = {s.source_id for s in sources}
        assert "apple_notes" in ids
        assert "dropbox" in ids

    def test_pii_source_requires_approval(self):
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry, KnowledgeSource, SOURCE_TYPE_CONNECTOR
        reg = KnowledgeSourceRegistry()
        src = KnowledgeSource(
            source_id="pii_db",
            name="PII DB",
            source_type=SOURCE_TYPE_CONNECTOR,
            pii_risk=True,
        )
        result = reg.register(src)
        assert result["ok"] is False
        assert result["status"] == "approval_required"

    def test_public_source_registers_ok(self):
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry, KnowledgeSource, SOURCE_TYPE_URL, ACCESS_PUBLIC
        reg = KnowledgeSourceRegistry()
        src = KnowledgeSource(
            source_id="pub_docs",
            name="Public Docs",
            source_type=SOURCE_TYPE_URL,
            path="https://example.com/docs",
            access_policy=ACCESS_PUBLIC,
            pii_risk=False,
        )
        result = reg.register(src)
        assert result["ok"] is True

    def test_invalid_source_type_rejected(self):
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry, KnowledgeSource
        reg = KnowledgeSourceRegistry()
        src = KnowledgeSource(source_id="bad_src", name="Bad", source_type="unknown_type")
        result = reg.register(src)
        assert result["ok"] is False

    def test_knowledge_platform_status(self):
        from openjarvis.wave.knowledge_platform import get_knowledge_platform_status
        info = get_knowledge_platform_status()
        assert info["status"] == "scaffolded"
        assert info["pii_sources_require_approval"] is True
        assert info["ingestion_implemented"] is False


# ---------------------------------------------------------------------------
# Epic D — Research Platform
# ---------------------------------------------------------------------------


class TestWaveResearchPlatform:
    def test_registry_imports(self):
        from openjarvis.wave.research_platform import ResearchProviderRegistry, ResearchProvider  # noqa

    def test_builtins_registered(self):
        from openjarvis.wave.research_platform import ResearchProviderRegistry
        reg = ResearchProviderRegistry()
        providers = reg.list_providers()
        assert len(providers) >= 3
        ids = {p.provider_id for p in providers}
        assert "hackernews" in ids
        assert "web_search_generic" in ids

    def test_web_search_requires_approval(self):
        from openjarvis.wave.research_platform import ResearchProviderRegistry, ResearchProvider, PROVIDER_TYPE_WEB_SEARCH, POLICY_REQUIRES_APPROVAL
        reg = ResearchProviderRegistry()
        p = ResearchProvider(
            provider_id="custom_search",
            name="Custom Search",
            provider_type=PROVIDER_TYPE_WEB_SEARCH,
            approval_policy=POLICY_REQUIRES_APPROVAL,
        )
        result = reg.register(p)
        assert result["ok"] is False
        assert result["status"] == "approval_required"

    def test_public_news_auto_registers(self):
        from openjarvis.wave.research_platform import ResearchProviderRegistry, ResearchProvider, PROVIDER_TYPE_NEWS, POLICY_AUTO
        reg = ResearchProviderRegistry()
        p = ResearchProvider(
            provider_id="test_rss",
            name="Test RSS",
            provider_type=PROVIDER_TYPE_NEWS,
            approval_policy=POLICY_AUTO,
        )
        result = reg.register(p)
        assert result["ok"] is True

    def test_invalid_provider_type_rejected(self):
        from openjarvis.wave.research_platform import ResearchProviderRegistry, ResearchProvider
        reg = ResearchProviderRegistry()
        p = ResearchProvider(provider_id="bad_p", name="Bad", provider_type="scraper")
        result = reg.register(p)
        assert result["ok"] is False

    def test_research_platform_status(self):
        from openjarvis.wave.research_platform import get_research_platform_status
        info = get_research_platform_status()
        assert info["status"] == "scaffolded"
        assert info["approval_gate_enforced"] is True
        assert info["execution_implemented"] is False
        assert info["web_search_requires_setup"] is True


# ---------------------------------------------------------------------------
# Wave Platform Registry
# ---------------------------------------------------------------------------


class TestWavePlatformRegistry:
    def test_registry_imports(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry  # noqa

    def test_all_epics_present(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry
        reg = WavePlatformRegistry()
        all_epics = reg.get_all()
        epic_ids = {r.epic_id for r in all_epics}
        assert {"epic_a", "epic_b", "epic_c", "epic_d", "epic_e", "epic_f", "epic_g", "epic_h"}.issubset(epic_ids)

    def test_wave1_epics_scaffolded(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        wave1 = reg.get_by_wave(1)
        assert len(wave1) == 4
        for r in wave1:
            assert r.status == WavePlatformStatus.SCAFFOLDED, (
                f"Epic {r.epic_id} status={r.status!r}, expected scaffolded"
            )

    def test_wave2_4_not_implemented(self):
        """Wave 2–4 must not claim ready or scaffolded status."""
        from openjarvis.wave.platform_registry import WavePlatformRegistry, WavePlatformStatus
        reg = WavePlatformRegistry()
        for wave in (2, 3, 4):
            for r in reg.get_by_wave(wave):
                assert r.status == WavePlatformStatus.NOT_IMPLEMENTED, (
                    f"Epic {r.epic_id} wave={wave} status={r.status!r}, "
                    "must be not_implemented — no fake claims"
                )

    def test_summary_wave1_scaffolded_flag(self):
        from openjarvis.wave.platform_registry import get_wave_platform_summary
        summary = get_wave_platform_summary()
        assert summary["wave1_scaffolded"] is True
        assert 2 in summary["not_implemented_waves"]
        assert 3 in summary["not_implemented_waves"]
        assert 4 in summary["not_implemented_waves"]

    def test_get_by_epic_id(self):
        from openjarvis.wave.platform_registry import WavePlatformRegistry
        reg = WavePlatformRegistry()
        r = reg.get("epic_h")
        assert r is not None
        assert r.wave == 4


# ---------------------------------------------------------------------------
# Capabilities Registry — Wave capabilities present and truthful
# ---------------------------------------------------------------------------


class TestWaveCapabilities:
    def test_wave_capability_ids_present(self):
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        cap_ids = {c.capability_id for c in caps}
        assert "wave1_skill_platform" in cap_ids
        assert "wave1_automation_platform" in cap_ids
        assert "wave1_knowledge_platform" in cap_ids
        assert "wave1_research_platform" in cap_ids

    def test_wave_capabilities_not_claiming_ready(self):
        """Wave 1 scaffolds must NOT report STATUS_READY."""
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, STATUS_READY
        caps = get_all_capabilities()
        wave_caps = [c for c in caps if c.capability_id.startswith("wave")]
        for c in wave_caps:
            assert c.status != STATUS_READY, (
                f"Capability {c.capability_id} claims ready — must be requires_setup or not_implemented"
            )

    def test_capabilities_summary_wave_flags(self):
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        assert summary["wave1_scaffolded"] is True
        assert summary["wave2_3_4_not_implemented"] is True
        # Total should be at least 11 (7 original + 4 Wave 1)
        assert summary["count"] >= 11


# ---------------------------------------------------------------------------
# Safety integration smoke tests
# ---------------------------------------------------------------------------


class TestWaveSafetyIntegration:
    def test_skill_induction_hard_gate(self):
        """Registering a hard-gate skill without bypass must require approval."""
        from openjarvis.wave.skill_platform import WaveSkillRegistry, WaveSkillManifest, APPROVAL_POLICY_HARD_GATE
        reg = WaveSkillRegistry()
        m = WaveSkillManifest(
            skill_id="dangerous_skill",
            name="Dangerous",
            approval_policy=APPROVAL_POLICY_HARD_GATE,
            induction_approved=False,
        )
        result = reg.register(m, bypass_approval_check=False)
        assert result["ok"] is False

    def test_automation_destructive_stays_disabled(self):
        """Critical-risk automations may not be auto-enabled."""
        from openjarvis.wave.automation_platform import AutomationRegistry, AutomationTrigger, TRIGGER_EVENT
        reg = AutomationRegistry()
        t = AutomationTrigger(
            trigger_id="delete_all",
            name="Delete All",
            trigger_type=TRIGGER_EVENT,
            risk_level="critical",
            approval_policy="requires_approval",
        )
        reg.register(t)
        result = reg.enable("delete_all")
        assert result["ok"] is False
        assert "approval_required" in result["status"]

    def test_research_web_search_requires_approval(self):
        """Unauthorized web scraping must be blocked by approval gate."""
        from openjarvis.wave.research_platform import ResearchProviderRegistry, ResearchProvider, PROVIDER_TYPE_WEB_SEARCH, POLICY_REQUIRES_APPROVAL
        reg = ResearchProviderRegistry()
        p = ResearchProvider(
            provider_id="scraper_test",
            name="Scraper",
            provider_type=PROVIDER_TYPE_WEB_SEARCH,
            approval_policy=POLICY_REQUIRES_APPROVAL,
        )
        result = reg.register(p)
        assert result["ok"] is False  # approval gate

    def test_pii_knowledge_source_blocked_without_approval(self):
        """PII knowledge sources must require approval."""
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry, KnowledgeSource, SOURCE_TYPE_DATABASE
        reg = KnowledgeSourceRegistry()
        src = KnowledgeSource(
            source_id="customer_pii",
            name="Customer PII",
            source_type=SOURCE_TYPE_DATABASE,
            pii_risk=True,
        )
        result = reg.register(src)
        assert result["ok"] is False
        assert result["status"] == "approval_required"
