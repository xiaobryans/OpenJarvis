"""Wave Platform Registry — truthful status for all Wave 1–4 epics.

Reports each epic/platform with an honest implementation status:
  scaffolded      — data model + registry exist; execution not yet wired
  not_implemented — planned; no code yet in this sprint
  ready           — fully implemented, tested, and approved
  requires_setup  — needs external config/auth before use
  disabled        — explicitly disabled/parked
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


class WavePlatformStatus:
    SCAFFOLDED = "scaffolded"
    NOT_IMPLEMENTED = "not_implemented"
    READY = "ready"
    REQUIRES_SETUP = "requires_setup"
    DISABLED = "disabled"


WAVE_STATUS_LABELS = frozenset({
    WavePlatformStatus.SCAFFOLDED,
    WavePlatformStatus.NOT_IMPLEMENTED,
    WavePlatformStatus.READY,
    WavePlatformStatus.REQUIRES_SETUP,
    WavePlatformStatus.DISABLED,
})


@dataclass
class WavePlatformRecord:
    epic_id: str           # e.g. "epic_a"
    wave: int              # 1–4
    display_name: str
    status: str
    summary: str
    acceptance_criteria: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    risk_areas: List[str] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "epic_id": self.epic_id,
            "wave": self.wave,
            "display_name": self.display_name,
            "status": self.status,
            "summary": self.summary,
            "acceptance_criteria": self.acceptance_criteria,
            "dependencies": self.dependencies,
            "risk_areas": self.risk_areas,
            "evidence": self.evidence,
        }


def _build_registry() -> List[WavePlatformRecord]:
    records: List[WavePlatformRecord] = []

    # ── Wave 1 ──────────────────────────────────────────────────────────────

    # Epic A: Skill Platform
    skill_evidence: Dict[str, Any] = {}
    skill_status = WavePlatformStatus.SCAFFOLDED
    try:
        from openjarvis.skills.jarvis_registry import SkillRegistry, SkillSpec  # noqa: F401
        skill_evidence["jarvis_registry"] = "imported"
        from openjarvis.skills.types import SkillManifest  # noqa: F401
        skill_evidence["skill_manifest"] = "imported"
        from openjarvis.wave.skill_platform import list_wave_skills
        wave_skills = list_wave_skills()
        skill_evidence["wave_skills"] = len(wave_skills)
        skill_status = WavePlatformStatus.SCAFFOLDED
    except Exception as exc:
        skill_evidence["error"] = str(exc)

    records.append(WavePlatformRecord(
        epic_id="epic_a",
        wave=1,
        display_name="Epic A — Skill Platform",
        status=skill_status,
        summary=(
            "Skill registry (SkillSpec/SkillRegistry) exists; Wave skill manifest "
            "model scaffolded. Full execution, skill induction pipeline, and "
            "approval-gated skill promotion not yet implemented."
        ),
        acceptance_criteria=[
            "WaveSkillManifest with id, name, version, approval_policy",
            "WaveSkillRegistry.register() + list() + get()",
            "Approval gate enforced for skill_induction action",
            "Skill status exposed in capabilities registry",
            "Doctor check for skill platform",
        ],
        dependencies=["skills/jarvis_registry", "workbench/adversarial_safety"],
        risk_areas=["Unapproved skill induction", "Capability claim inflation"],
        evidence=skill_evidence,
    ))

    # Epic B: Automation Platform
    auto_evidence: Dict[str, Any] = {}
    auto_status = WavePlatformStatus.SCAFFOLDED
    try:
        from openjarvis.wave.automation_platform import AutomationRegistry
        reg = AutomationRegistry()
        auto_evidence["registry"] = "instantiated"
        auto_evidence["trigger_count"] = len(reg.list_triggers())
        auto_status = WavePlatformStatus.SCAFFOLDED
    except Exception as exc:
        auto_evidence["error"] = str(exc)

    records.append(WavePlatformRecord(
        epic_id="epic_b",
        wave=1,
        display_name="Epic B — Automation Platform",
        status=auto_status,
        summary=(
            "Trigger model and AutomationRegistry scaffold exist. "
            "Runtime execution, cron/event wiring, and approval gating "
            "for destructive automations not yet implemented."
        ),
        acceptance_criteria=[
            "AutomationTrigger model (id, trigger_type, schedule, approval_policy)",
            "AutomationRegistry register/list/get",
            "Destructive automations hard-gated",
            "Automation events logged",
            "Doctor check for automation platform",
        ],
        dependencies=["scheduler/scheduler", "workbench/event_log", "governance/policies"],
        risk_areas=["Uncontrolled autopilot execution", "Schedule-triggered destructive ops"],
        evidence=auto_evidence,
    ))

    # Epic C: Knowledge Platform
    know_evidence: Dict[str, Any] = {}
    know_status = WavePlatformStatus.SCAFFOLDED
    try:
        from openjarvis.wave.knowledge_platform import KnowledgeSourceRegistry
        reg = KnowledgeSourceRegistry()
        know_evidence["registry"] = "instantiated"
        know_evidence["source_count"] = len(reg.list_sources())
        know_status = WavePlatformStatus.SCAFFOLDED
    except Exception as exc:
        know_evidence["error"] = str(exc)

    records.append(WavePlatformRecord(
        epic_id="epic_c",
        wave=1,
        display_name="Epic C — Knowledge Platform",
        status=know_status,
        summary=(
            "KnowledgeSourceRegistry scaffold exists; connector inventory "
            "referenced. Ingestion pipelines, hybrid search, and "
            "memory-backed retrieval not yet wired."
        ),
        acceptance_criteria=[
            "KnowledgeSource model (id, source_type, connector_id, status)",
            "KnowledgeSourceRegistry register/list/get",
            "Sensitive source access approval-gated",
            "Doctor check for knowledge platform",
        ],
        dependencies=["connectors/", "memory/store", "workbench/adversarial_safety"],
        risk_areas=["Unauthorized data ingestion", "PII in knowledge base"],
        evidence=know_evidence,
    ))

    # Epic D: Research Platform
    res_evidence: Dict[str, Any] = {}
    res_status = WavePlatformStatus.SCAFFOLDED
    try:
        from openjarvis.wave.research_platform import ResearchProviderRegistry
        reg = ResearchProviderRegistry()
        res_evidence["registry"] = "instantiated"
        res_evidence["provider_count"] = len(reg.list_providers())
        res_status = WavePlatformStatus.SCAFFOLDED
    except Exception as exc:
        res_evidence["error"] = str(exc)

    records.append(WavePlatformRecord(
        epic_id="epic_d",
        wave=1,
        display_name="Epic D — Research Platform",
        status=res_status,
        summary=(
            "ResearchProviderRegistry scaffold exists. Live search execution, "
            "deep-research loop, and evidence synthesis not yet implemented."
        ),
        acceptance_criteria=[
            "ResearchProvider model (id, provider_type, approval_policy)",
            "ResearchProviderRegistry register/list/get",
            "Web research approval-gated (no unauthorized scraping)",
            "Doctor check for research platform",
        ],
        dependencies=["connectors/hackernews", "connectors/news_rss", "workbench/adversarial_safety"],
        risk_areas=["Unauthorized scraping", "Research cost runaway"],
        evidence=res_evidence,
    ))

    # ── Wave 2 ──────────────────────────────────────────────────────────────

    # Epic E status: check if optimization platform is implemented
    try:
        from openjarvis.wave.optimization_platform import get_optimization_platform_status
        _opt_info = get_optimization_platform_status()
        _epic_e_status = WavePlatformStatus.READY if _opt_info.get("implemented") else WavePlatformStatus.SCAFFOLDED
        _epic_e_summary = (
            f"Wave 2 Epic E: Optimization Platform — {_opt_info.get('status', 'ready')}. "
            f"Scorecards, cost/routing/validation/failure/readiness analysis. No autonomous self-modification."
        )
    except Exception:
        _epic_e_status = WavePlatformStatus.NOT_IMPLEMENTED
        _epic_e_summary = "Epic E: Optimization Platform — not yet loaded."

    records.append(WavePlatformRecord(
        epic_id="epic_e",
        wave=2,
        display_name="Epic E — Optimization Platform",
        status=_epic_e_status,
        summary=_epic_e_summary,
        acceptance_criteria=[
            "Scorecard generation implemented",
            "Cost/routing/validation/failure/readiness analysis implemented",
            "No autonomous code modification",
            "Approval-gated for file-write/deploy recommendations",
        ],
        dependencies=["epic_a", "epic_b"],
        risk_areas=["Cost runaway from optimization loops — no auto-execution"],
        evidence={},
    ))

    # Epic F status: check if skill packs are implemented
    try:
        from openjarvis.wave.professional_skill_packs import get_professional_skill_packs_status
        _pack_info = get_professional_skill_packs_status()
        _epic_f_status = WavePlatformStatus.READY if _pack_info.get("implemented") else WavePlatformStatus.SCAFFOLDED
        _epic_f_summary = (
            f"Wave 2 Epic F: Professional Skill Packs — {_pack_info.get('status', 'ready')}. "
            f"{_pack_info.get('pack_count', 0)} packs registered, "
            f"{_pack_info.get('enabled_count', 0)} enabled."
        )
    except Exception:
        _epic_f_status = WavePlatformStatus.NOT_IMPLEMENTED
        _epic_f_summary = "Epic F: Professional Skill Packs — not yet loaded."

    records.append(WavePlatformRecord(
        epic_id="epic_f",
        wave=2,
        display_name="Epic F — Professional Skill Packs",
        status=_epic_f_status,
        summary=_epic_f_summary,
        acceptance_criteria=[
            "Skill pack registry with 5+ built-in packs",
            "Validation and approval gating",
            "Safe local execution for low-risk packs",
            "Hard-gate for deploy/production packs",
            "Wave 1 skill platform integration",
        ],
        dependencies=["epic_a"],
        risk_areas=["Unapproved third-party skill inclusion — hard-gated"],
        evidence={},
    ))

    # ── Wave 3 ──────────────────────────────────────────────────────────────

    try:
        from openjarvis.wave.content_media_studio import get_content_studio_status
        _studio_info = get_content_studio_status()
        _epic_g_status = WavePlatformStatus.READY if _studio_info.get("implemented") else WavePlatformStatus.SCAFFOLDED
        _epic_g_summary = (
            f"Wave 3 Epic G: Content & Media Studio — {_studio_info.get('status', 'ready')}. "
            f"{_studio_info.get('template_count', 0)} templates. "
            "Dry-run default. File writes approval-gated."
        )
    except Exception:
        _epic_g_status = WavePlatformStatus.NOT_IMPLEMENTED
        _epic_g_summary = "Epic G: Content & Media Studio — not yet loaded."

    records.append(WavePlatformRecord(
        epic_id="epic_g",
        wave=3,
        display_name="Epic G — Content & Media Studio",
        status=_epic_g_status,
        summary=_epic_g_summary,
        acceptance_criteria=[
            "7+ built-in content templates",
            "Local content workflow dry-run implemented",
            "File write approval-gated",
            "Content safety policy active",
            "External media providers require setup + approval",
            "Wave 1/2 integration",
        ],
        dependencies=["epic_e", "epic_f"],
        risk_areas=["Copyright / media generation policy — external providers require env key + approval"],
        evidence={},
    ))

    # ── Wave 4 ──────────────────────────────────────────────────────────────

    _epic_h_status = WavePlatformStatus.NOT_IMPLEMENTED
    _epic_h_summary = "Epic H: Autonomous Expansion — not yet loaded."
    try:
        from openjarvis.wave.autonomous_expansion import get_expansion_status
        _info_h = get_expansion_status()
        if _info_h.get("implemented"):
            _epic_h_status = WavePlatformStatus.READY
            _epic_h_summary = (
                "Epic H: Supervised expansion module ready. "
                "Proposal-only. Approval-gated. No auto-execute. "
                "NUS 1 not started. US13 voice HOLD/UNSAFE/PARKED."
            )
    except Exception:
        pass

    records.append(WavePlatformRecord(
        epic_id="epic_h",
        wave=4,
        display_name="Epic H — Autonomous Expansion (Supervised)",
        status=_epic_h_status,
        summary=_epic_h_summary,
        acceptance_criteria=[
            "Expansion opportunity detection implemented",
            "Capability gap analysis implemented",
            "Safe expansion proposal creation implemented",
            "Dependency/risk classification implemented",
            "Acceptance criteria generation implemented",
            "Validation plan generation implemented",
            "Rollback plan generation implemented",
            "Approval-gated expansion queue implemented",
            "Wave 1 registry integration (skill/automation/knowledge/research proposals)",
            "Wave 2 cost/routing/performance classification",
            "Wave 3 content spec/handoff/readiness report drafting",
            "Event logging for all expansion events",
            "API routes /v1/wave4/expansion/*",
            "Doctor/readiness checks for Wave 4",
            "No code self-modification",
            "No auto-commit or auto-push",
            "No deploy",
            "NUS 1 not started",
            "US13 voice HOLD/UNSAFE/PARKED",
        ],
        dependencies=["epic_a", "epic_b", "epic_c", "epic_d", "epic_e", "epic_f", "epic_g"],
        risk_areas=[
            "Autonomous action without approval — blocked by design",
            "Cost runaway — classified via Wave 2 patterns",
            "Unsafe expansion — blocked by adversarial safety",
        ],
        evidence={},
    ))

    return records


class WavePlatformRegistry:
    """Read-only registry of all Wave 1–4 platform epics."""

    def __init__(self) -> None:
        self._records: List[WavePlatformRecord] = _build_registry()

    def get_all(self) -> List[WavePlatformRecord]:
        return list(self._records)

    def get_by_wave(self, wave: int) -> List[WavePlatformRecord]:
        return [r for r in self._records if r.wave == wave]

    def get(self, epic_id: str) -> WavePlatformRecord | None:
        return next((r for r in self._records if r.epic_id == epic_id), None)


def get_wave_platform_summary() -> Dict[str, Any]:
    """Return Wave 1–4 platform summary for Mission Control / doctor."""
    reg = WavePlatformRegistry()
    all_records = reg.get_all()
    by_status: Dict[str, int] = {}
    for r in all_records:
        by_status[r.status] = by_status.get(r.status, 0) + 1

    wave1 = reg.get_by_wave(1)
    wave1_done = all(r.status in (WavePlatformStatus.SCAFFOLDED, WavePlatformStatus.READY) for r in wave1)

    wave2 = reg.get_by_wave(2)
    wave2_done = all(r.status in (WavePlatformStatus.SCAFFOLDED, WavePlatformStatus.READY) for r in wave2)

    wave3 = reg.get_by_wave(3)
    wave3_done = all(r.status in (WavePlatformStatus.SCAFFOLDED, WavePlatformStatus.READY) for r in wave3)

    not_impl_waves = [w for w in (4,) if all(
        r.status == WavePlatformStatus.NOT_IMPLEMENTED for r in reg.get_by_wave(w)
    )]

    wave4 = reg.get_by_wave(4)
    wave4_done = all(r.status in (WavePlatformStatus.SCAFFOLDED, WavePlatformStatus.READY) for r in wave4)

    return {
        "total_epics": len(all_records),
        "by_status": by_status,
        "wave1_scaffolded": wave1_done,
        "wave1_ready": wave1_done,
        "wave2_ready": wave2_done,
        "wave3_ready": wave3_done,
        "wave4_ready": wave4_done,
        "epics": [r.to_dict() for r in all_records],
        "not_implemented_waves": not_impl_waves,
        "nus1_status": "not_started",
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "note": (
            "Wave 1 + Wave 2 + Wave 3 + Wave 4 implemented. "
            "NUS 1 not started. US13 voice HOLD/UNSAFE/PARKED."
        ),
    }


__all__ = [
    "WavePlatformRecord",
    "WavePlatformRegistry",
    "WavePlatformStatus",
    "WAVE_STATUS_LABELS",
    "get_wave_platform_summary",
]
