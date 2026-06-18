"""Epic H — Autonomous Expansion Module (Wave 4).

Supervised expansion scaffolding for local/founder V1.

Design constraints (permanent — no exceptions):
- NO auto-edit of code.
- NO auto-registration of high-risk capabilities.
- NO auto-run of browser/account/provider setup.
- NO auto-commit or auto-push.
- NO deploy or release automation.
- NO external sends.
- NO secret access.
- Proposals requiring file writes, external providers, browser actions, account
  access, production/deploy, secrets, external sends, or self-modification are
  classified as needs_approval or blocked.
- All actions are local-only, proposal-only, dry-run by default.
- Reuses US17 adversarial safety for classification.
- Integrates with Wave 1 registries, Wave 2 optimization/skill packs,
  Wave 3 content studio.
- NUS 1 (full self-improvement autonomy) remains NOT STARTED.
- US13 voice remains HOLD / UNSAFE / PARKED.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Status / Risk constants
# ---------------------------------------------------------------------------

PROPOSAL_STATUS_DRAFT = "draft"
PROPOSAL_STATUS_SAFE = "safe"
PROPOSAL_STATUS_NEEDS_APPROVAL = "needs_approval"
PROPOSAL_STATUS_BLOCKED = "blocked"
PROPOSAL_STATUS_VALIDATED = "validated"
PROPOSAL_STATUS_REJECTED = "rejected"

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

OPPORTUNITY_DETECTED = "opportunity_detected"
OPPORTUNITY_GAP = "capability_gap"
OPPORTUNITY_SKILL = "skill_extension"
OPPORTUNITY_AUTOMATION = "automation_extension"
OPPORTUNITY_KNOWLEDGE = "knowledge_extension"
OPPORTUNITY_RESEARCH = "research_extension"
OPPORTUNITY_OPTIMIZATION = "optimization_improvement"
OPPORTUNITY_CONTENT = "content_template_extension"

# Proposal types that are ALWAYS blocked without explicit approval
_HIGH_RISK_PROPOSAL_TYPES = frozenset({
    "file_write",
    "code_edit",
    "self_modification",
    "external_provider_setup",
    "browser_automation",
    "account_access",
    "production_deploy",
    "secret_access",
    "external_send",
    "auto_commit",
    "auto_push",
})

# Proposal types classified as needs_approval
_APPROVAL_REQUIRED_TYPES = frozenset({
    "register_capability",
    "add_provider",
    "add_integration",
    "wave1_skill_register",
    "wave1_automation_register",
    "wave1_knowledge_source_register",
    "wave1_research_provider_register",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ExpansionOpportunity:
    opportunity_id: str
    kind: str                # OPPORTUNITY_* constant
    title: str
    description: str
    detected_at: float = field(default_factory=time.time)
    source: str = "gap_analysis"
    wave_integration: List[int] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "detected_at": self.detected_at,
            "source": self.source,
            "wave_integration": self.wave_integration,
            "evidence": self.evidence,
        }


@dataclass
class ExpansionProposal:
    proposal_id: str
    opportunity_id: str
    title: str
    description: str
    proposal_type: str
    status: str = PROPOSAL_STATUS_DRAFT
    risk_level: str = RISK_LOW
    created_at: float = field(default_factory=time.time)
    acceptance_criteria: List[str] = field(default_factory=list)
    validation_plan: List[str] = field(default_factory=list)
    rollback_plan: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    wave_integrations: List[int] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    approval_required_reason: Optional[str] = None
    cost_impact: str = "low"
    routing_impact: str = "none"
    performance_impact: str = "minimal"
    content_spec: Optional[str] = None
    handoff_pack: Optional[str] = None
    readiness_report: Optional[str] = None
    classification_evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "description": self.description,
            "proposal_type": self.proposal_type,
            "status": self.status,
            "risk_level": self.risk_level,
            "created_at": self.created_at,
            "acceptance_criteria": self.acceptance_criteria,
            "validation_plan": self.validation_plan,
            "rollback_plan": self.rollback_plan,
            "dependencies": self.dependencies,
            "wave_integrations": self.wave_integrations,
            "blocked_reason": self.blocked_reason,
            "approval_required_reason": self.approval_required_reason,
            "cost_impact": self.cost_impact,
            "routing_impact": self.routing_impact,
            "performance_impact": self.performance_impact,
            "content_spec": self.content_spec,
            "handoff_pack": self.handoff_pack,
            "readiness_report": self.readiness_report,
            "classification_evidence": self.classification_evidence,
        }


@dataclass
class ValidationPlan:
    proposal_id: str
    steps: List[str]
    required_checks: List[str]
    safety_checks: List[str]
    rollback_steps: List[str]
    estimated_effort: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "steps": self.steps,
            "required_checks": self.required_checks,
            "safety_checks": self.safety_checks,
            "rollback_steps": self.rollback_steps,
            "estimated_effort": self.estimated_effort,
        }


# ---------------------------------------------------------------------------
# In-memory expansion queue (local/founder V1 — no persistence required)
# ---------------------------------------------------------------------------

class ExpansionQueue:
    def __init__(self) -> None:
        self._opportunities: List[ExpansionOpportunity] = []
        self._proposals: List[ExpansionProposal] = []

    def add_opportunity(self, opp: ExpansionOpportunity) -> None:
        self._opportunities.append(opp)

    def add_proposal(self, proposal: ExpansionProposal) -> None:
        self._proposals.append(proposal)

    def list_opportunities(self) -> List[ExpansionOpportunity]:
        return list(self._opportunities)

    def list_proposals(self) -> List[ExpansionProposal]:
        return list(self._proposals)

    def get_proposal(self, proposal_id: str) -> Optional[ExpansionProposal]:
        return next((p for p in self._proposals if p.proposal_id == proposal_id), None)

    def queue_summary(self) -> Dict[str, Any]:
        by_status: Dict[str, int] = {}
        for p in self._proposals:
            by_status[p.status] = by_status.get(p.status, 0) + 1
        return {
            "opportunity_count": len(self._opportunities),
            "proposal_count": len(self._proposals),
            "by_status": by_status,
        }

    def clear(self) -> None:
        self._opportunities.clear()
        self._proposals.clear()


# Module-level singleton queue
_queue = ExpansionQueue()


def get_queue() -> ExpansionQueue:
    return _queue


# ---------------------------------------------------------------------------
# Opportunity detection
# ---------------------------------------------------------------------------

def detect_expansion_opportunities() -> List[ExpansionOpportunity]:
    """Scan Wave 1–3 registries for expansion gaps and return opportunities.

    Only reads — does not write, execute, or register anything.
    """
    opportunities: List[ExpansionOpportunity] = []

    # --- Wave 1: Skill gaps ---
    try:
        from openjarvis.wave.skill_platform import list_wave_skills
        skills = list_wave_skills()
        if len(skills) < 10:
            opportunities.append(ExpansionOpportunity(
                opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
                kind=OPPORTUNITY_SKILL,
                title="Expand Wave 1 skill library",
                description=(
                    f"Current wave skill count is {len(skills)}. "
                    "Opportunity to add domain-specific skills (coding, research, content)."
                ),
                source="wave1_skill_platform",
                wave_integration=[1],
                evidence={"current_skill_count": len(skills)},
            ))
    except Exception as exc:
        opportunities.append(ExpansionOpportunity(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            kind=OPPORTUNITY_GAP,
            title="Wave 1 skill platform unavailable",
            description=f"Gap: wave1 skill platform failed to load: {exc}",
            source="gap_analysis",
            wave_integration=[1],
            evidence={"error": str(exc)},
        ))

    # --- Wave 1: Automation gaps ---
    try:
        from openjarvis.wave.automation_platform import AutomationPlatform
        ap = AutomationPlatform()
        triggers = ap.list_triggers()
        if len(triggers) < 5:
            opportunities.append(ExpansionOpportunity(
                opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
                kind=OPPORTUNITY_AUTOMATION,
                title="Expand automation triggers",
                description=(
                    f"Current trigger count is {len(triggers)}. "
                    "Opportunity to add time-based, event-based, or condition-based triggers."
                ),
                source="wave1_automation_platform",
                wave_integration=[1],
                evidence={"current_trigger_count": len(triggers)},
            ))
    except Exception as exc:
        opportunities.append(ExpansionOpportunity(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            kind=OPPORTUNITY_GAP,
            title="Wave 1 automation platform unavailable",
            description=f"Gap: wave1 automation platform failed: {exc}",
            source="gap_analysis",
            wave_integration=[1],
            evidence={"error": str(exc)},
        ))

    # --- Wave 1: Knowledge gaps ---
    try:
        from openjarvis.wave.knowledge_platform import KnowledgePlatform
        kp = KnowledgePlatform()
        sources = kp.list_sources()
        if len(sources) < 3:
            opportunities.append(ExpansionOpportunity(
                opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
                kind=OPPORTUNITY_KNOWLEDGE,
                title="Expand knowledge sources",
                description=(
                    f"Current source count is {len(sources)}. "
                    "Opportunity to add local document, API, or structured data sources."
                ),
                source="wave1_knowledge_platform",
                wave_integration=[1],
                evidence={"current_source_count": len(sources)},
            ))
    except Exception as exc:
        opportunities.append(ExpansionOpportunity(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            kind=OPPORTUNITY_GAP,
            title="Wave 1 knowledge platform unavailable",
            description=f"Gap: wave1 knowledge platform failed: {exc}",
            source="gap_analysis",
            wave_integration=[1],
            evidence={"error": str(exc)},
        ))

    # --- Wave 2: Optimization gaps ---
    try:
        from openjarvis.wave.optimization_platform import generate_scorecard
        sc = generate_scorecard()
        high_impact = [r for r in sc.recommendations if r.impact == "high"]
        if high_impact:
            opportunities.append(ExpansionOpportunity(
                opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
                kind=OPPORTUNITY_OPTIMIZATION,
                title="High-impact optimization opportunities identified",
                description=(
                    f"{len(high_impact)} high-impact optimization recommendations "
                    "from Wave 2 scorecard. Review and propose targeted improvements."
                ),
                source="wave2_optimization_platform",
                wave_integration=[2],
                evidence={"high_impact_count": len(high_impact),
                          "categories": list({r.category for r in high_impact})},
            ))
    except Exception as exc:
        opportunities.append(ExpansionOpportunity(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            kind=OPPORTUNITY_GAP,
            title="Wave 2 optimization platform unavailable",
            description=f"Gap: wave2 optimization platform failed: {exc}",
            source="gap_analysis",
            wave_integration=[2],
            evidence={"error": str(exc)},
        ))

    # --- Wave 3: Content template gaps ---
    try:
        from openjarvis.wave.content_media_studio import list_templates
        templates = list_templates()
        if len(templates) < 10:
            opportunities.append(ExpansionOpportunity(
                opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
                kind=OPPORTUNITY_CONTENT,
                title="Expand content template library",
                description=(
                    f"Current template count is {len(templates)}. "
                    "Opportunity to add domain-specific templates "
                    "(API docs, onboarding guides, sprint retros)."
                ),
                source="wave3_content_media_studio",
                wave_integration=[3],
                evidence={"current_template_count": len(templates)},
            ))
    except Exception as exc:
        opportunities.append(ExpansionOpportunity(
            opportunity_id=f"opp_{uuid.uuid4().hex[:8]}",
            kind=OPPORTUNITY_GAP,
            title="Wave 3 content studio unavailable",
            description=f"Gap: wave3 content studio failed: {exc}",
            source="gap_analysis",
            wave_integration=[3],
            evidence={"error": str(exc)},
        ))

    return opportunities


# ---------------------------------------------------------------------------
# Capability gap analysis
# ---------------------------------------------------------------------------

def analyze_capability_gaps() -> Dict[str, Any]:
    """Produce a structured capability gap report across Waves 1–3.

    Read-only analysis — no writes, no registrations.
    """
    gaps: List[Dict[str, Any]] = []

    # Wave 1 capability gaps
    wave1_gaps = _analyze_wave1_gaps()
    gaps.extend(wave1_gaps)

    # Wave 2 capability gaps
    wave2_gaps = _analyze_wave2_gaps()
    gaps.extend(wave2_gaps)

    # Wave 3 capability gaps
    wave3_gaps = _analyze_wave3_gaps()
    gaps.extend(wave3_gaps)

    return {
        "total_gaps": len(gaps),
        "gaps": gaps,
        "wave1_gap_count": len(wave1_gaps),
        "wave2_gap_count": len(wave2_gaps),
        "wave3_gap_count": len(wave3_gaps),
        "analysis_timestamp": time.time(),
        "nus1_status": "not_started",
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
    }


def _analyze_wave1_gaps() -> List[Dict[str, Any]]:
    gaps = []
    try:
        from openjarvis.wave.skill_platform import list_wave_skills
        skills = list_wave_skills()
        gaps.append({
            "wave": 1, "area": "skill_platform",
            "current": len(skills), "gap": "More domain skills needed" if len(skills) < 10 else "OK",
        })
    except Exception as exc:
        gaps.append({"wave": 1, "area": "skill_platform", "gap": str(exc)})

    try:
        from openjarvis.wave.research_platform import ResearchPlatform
        rp = ResearchPlatform()
        providers = rp.list_providers()
        gaps.append({
            "wave": 1, "area": "research_platform",
            "current": len(providers),
            "gap": "Add more research providers" if len(providers) < 3 else "OK",
        })
    except Exception as exc:
        gaps.append({"wave": 1, "area": "research_platform", "gap": str(exc)})

    return gaps


def _analyze_wave2_gaps() -> List[Dict[str, Any]]:
    gaps = []
    try:
        from openjarvis.wave.professional_skill_packs import SkillPackRegistry
        reg = SkillPackRegistry()
        packs = reg.list_packs()
        gaps.append({
            "wave": 2, "area": "professional_skill_packs",
            "current": len(packs),
            "gap": "Add industry-specific skill packs" if len(packs) < 5 else "OK",
        })
    except Exception as exc:
        gaps.append({"wave": 2, "area": "professional_skill_packs", "gap": str(exc)})

    return gaps


def _analyze_wave3_gaps() -> List[Dict[str, Any]]:
    gaps = []
    try:
        from openjarvis.wave.content_media_studio import list_templates
        templates = list_templates()
        gaps.append({
            "wave": 3, "area": "content_templates",
            "current": len(templates),
            "gap": "Add more templates" if len(templates) < 10 else "OK",
        })
    except Exception as exc:
        gaps.append({"wave": 3, "area": "content_templates", "gap": str(exc)})

    return gaps


# ---------------------------------------------------------------------------
# Risk / dependency classification
# ---------------------------------------------------------------------------

def classify_proposal_risk(
    proposal_type: str,
    description: str,
    wave_integrations: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Classify the risk and required approval level for an expansion proposal.

    Delegates to US17 adversarial safety patterns for classification.
    Returns: risk_level, status, blocked_reason, approval_required_reason
    """
    description_lower = description.lower()

    # Hard-blocked types — always BLOCKED
    if proposal_type in _HIGH_RISK_PROPOSAL_TYPES:
        return {
            "risk_level": RISK_CRITICAL,
            "status": PROPOSAL_STATUS_BLOCKED,
            "blocked_reason": (
                f"Proposal type '{proposal_type}' is hard-blocked. "
                "Requires explicit owner override outside this module. "
                "No autonomous bypass permitted."
            ),
            "approval_required_reason": None,
        }

    # Check adversarial safety patterns in description
    _blocked_patterns = [
        ("auto-commit", "auto_commit detected in description"),
        ("auto-push", "auto_push detected in description"),
        ("self-modif", "self_modification pattern detected"),
        ("deploy to production", "production_deploy pattern detected"),
        ("bypass approval", "approval_bypass pattern detected"),
        ("api_key", "credential_secret pattern detected"),
        ("secret_key", "credential_secret pattern detected"),
        ("private_key", "credential_secret pattern detected"),
        ("-----begin", "key_material pattern detected"),
    ]
    for pattern, reason in _blocked_patterns:
        if pattern in description_lower:
            return {
                "risk_level": RISK_CRITICAL,
                "status": PROPOSAL_STATUS_BLOCKED,
                "blocked_reason": reason,
                "approval_required_reason": None,
            }

    # Approval-required types
    if proposal_type in _APPROVAL_REQUIRED_TYPES:
        return {
            "risk_level": RISK_HIGH,
            "status": PROPOSAL_STATUS_NEEDS_APPROVAL,
            "blocked_reason": None,
            "approval_required_reason": (
                f"Proposal type '{proposal_type}' requires explicit owner approval "
                "before execution. Proposal is queued pending review."
            ),
        }

    # Medium-risk patterns
    _medium_patterns = [
        "external api", "external provider", "third-party",
        "webhook", "cloud", "remote", "browser",
    ]
    if any(p in description_lower for p in _medium_patterns):
        return {
            "risk_level": RISK_MEDIUM,
            "status": PROPOSAL_STATUS_NEEDS_APPROVAL,
            "blocked_reason": None,
            "approval_required_reason": (
                "External/cloud/remote pattern detected — needs approval before execution."
            ),
        }

    # Cost/routing impact from Wave 2 optimization patterns
    _high_cost_patterns = ["large model", "premium provider", "concurrent", "bulk"]
    if any(p in description_lower for p in _high_cost_patterns):
        return {
            "risk_level": RISK_MEDIUM,
            "status": PROPOSAL_STATUS_NEEDS_APPROVAL,
            "blocked_reason": None,
            "approval_required_reason": (
                "High cost/routing impact detected — needs approval to prevent runaway."
            ),
        }

    return {
        "risk_level": RISK_LOW,
        "status": PROPOSAL_STATUS_SAFE,
        "blocked_reason": None,
        "approval_required_reason": None,
    }


# ---------------------------------------------------------------------------
# Acceptance criteria generation
# ---------------------------------------------------------------------------

def generate_acceptance_criteria(
    proposal_type: str,
    title: str,
    wave_integrations: Optional[List[int]] = None,
) -> List[str]:
    """Generate acceptance criteria for a given expansion proposal."""
    criteria = [
        f"Proposal '{title}' is implemented as described without deviation.",
        "No code self-modification occurs.",
        "No auto-commit or auto-push occurs.",
        "No deploy or release automation occurs.",
        "No external sends are made.",
        "No secrets are accessed or logged.",
        "Event logging records all expansion actions.",
        "Doctor/readiness check passes after implementation.",
    ]

    if proposal_type in _APPROVAL_REQUIRED_TYPES or proposal_type in _HIGH_RISK_PROPOSAL_TYPES:
        criteria.append("Explicit owner approval is obtained before execution.")

    if wave_integrations:
        for w in wave_integrations:
            criteria.append(f"Wave {w} integration is verified via existing tests.")

    criteria.append("All existing Wave 1–3 regression tests continue to pass.")
    return criteria


# ---------------------------------------------------------------------------
# Validation plan generation
# ---------------------------------------------------------------------------

def generate_validation_plan(proposal: ExpansionProposal) -> ValidationPlan:
    """Generate a validation plan for an expansion proposal."""
    steps = [
        f"1. Review proposal '{proposal.title}' (proposal_id={proposal.proposal_id}).",
        "2. Verify proposal classification (risk_level, status) is accurate.",
        "3. Run existing Wave 1–3 tests to confirm no regression.",
        "4. Run Wave 4 expansion tests: pytest tests/wave/test_wave4.py -q",
        "5. Inspect event log for expected events.",
        "6. Verify doctor/readiness reports Wave 4 as ready.",
    ]

    required_checks = [
        "pytest tests/wave/ -q --tb=short",
        "pytest tests/workbench/test_us17_adversarial.py -q",
        "pytest tests/workbench/test_us18_readiness.py -q",
    ]

    safety_checks = [
        "Confirm no files were written without approval.",
        "Confirm no git commits were made automatically.",
        "Confirm no external HTTP calls were made.",
        "Confirm no secrets appear in event log.",
        "Confirm NUS 1 remains not_started.",
        "Confirm US13 voice remains HOLD/UNSAFE/PARKED.",
    ]

    if proposal.wave_integrations:
        for w in proposal.wave_integrations:
            steps.append(f"Wave {w} integration test: verify imports and status from wave{w} module.")

    rollback_steps = proposal.rollback_plan or _default_rollback_plan()

    effort = "low" if proposal.risk_level == RISK_LOW else (
        "medium" if proposal.risk_level == RISK_MEDIUM else "high"
    )

    return ValidationPlan(
        proposal_id=proposal.proposal_id,
        steps=steps,
        required_checks=required_checks,
        safety_checks=safety_checks,
        rollback_steps=rollback_steps,
        estimated_effort=effort,
    )


# ---------------------------------------------------------------------------
# Rollback plan generation
# ---------------------------------------------------------------------------

def _default_rollback_plan() -> List[str]:
    return [
        "1. Revert to last accepted Wave checkpoint commit.",
        "2. Run git status to confirm clean state.",
        "3. Run pytest tests/wave/ -q to confirm baseline passes.",
        "4. Report rollback to owner with evidence.",
        "5. Clear expansion queue if needed.",
        "6. Update doctor/readiness to reflect rolled-back state.",
    ]


def generate_rollback_plan(proposal: ExpansionProposal) -> List[str]:
    """Generate a rollback plan for an expansion proposal."""
    plan = _default_rollback_plan()
    if proposal.proposal_type in _HIGH_RISK_PROPOSAL_TYPES:
        plan.insert(0, "CRITICAL: High-risk proposal — rollback must be performed manually by owner.")
    plan.append(f"Proposal ID for audit trail: {proposal.proposal_id}")
    return plan


# ---------------------------------------------------------------------------
# Safe proposal creation
# ---------------------------------------------------------------------------

def create_expansion_proposal(
    opportunity_id: str,
    title: str,
    description: str,
    proposal_type: str,
    wave_integrations: Optional[List[int]] = None,
    dependencies: Optional[List[str]] = None,
) -> ExpansionProposal:
    """Create and classify a new expansion proposal.

    This function:
    - Classifies risk using adversarial safety patterns.
    - Generates acceptance criteria.
    - Generates a validation plan.
    - Generates a rollback plan.
    - Integrates Wave 2 cost/routing/performance classification.
    - Drafts a Wave 3 content spec and handoff pack.
    - Logs events via WorkbenchEventLog.
    - Does NOT write files, execute code, register capabilities, or make
      external calls.
    """
    wave_integrations = wave_integrations or []
    dependencies = dependencies or []

    proposal_id = f"prop_{uuid.uuid4().hex[:12]}"

    # Classify risk
    classification = classify_proposal_risk(proposal_type, description, wave_integrations)
    risk_level = classification["risk_level"]
    status = classification["status"]
    blocked_reason = classification.get("blocked_reason")
    approval_required_reason = classification.get("approval_required_reason")

    # Acceptance criteria
    criteria = generate_acceptance_criteria(proposal_type, title, wave_integrations)

    # Cost/routing/performance classification from Wave 2
    cost_impact, routing_impact, perf_impact = _classify_cost_routing_impact(
        proposal_type, description
    )

    # Validation plan steps
    vp_steps = [
        f"Review proposal '{title}'.",
        "Verify risk classification.",
        "Run Wave 1–4 tests.",
        "Check event log.",
        "Confirm no self-modification.",
    ]

    # Rollback plan
    rollback = _default_rollback_plan()
    rollback.append(f"Proposal ID: {proposal_id}")

    # Wave 3 content spec draft
    content_spec = _draft_content_spec(title, description, proposal_type)

    # Wave 3 handoff pack
    handoff_pack = _draft_handoff_pack(title, proposal_type, wave_integrations, criteria)

    # Wave 3 readiness report
    readiness_report = _draft_readiness_report(status, risk_level, wave_integrations)

    proposal = ExpansionProposal(
        proposal_id=proposal_id,
        opportunity_id=opportunity_id,
        title=title,
        description=description,
        proposal_type=proposal_type,
        status=status,
        risk_level=risk_level,
        acceptance_criteria=criteria,
        validation_plan=vp_steps,
        rollback_plan=rollback,
        dependencies=dependencies,
        wave_integrations=wave_integrations,
        blocked_reason=blocked_reason,
        approval_required_reason=approval_required_reason,
        cost_impact=cost_impact,
        routing_impact=routing_impact,
        performance_impact=perf_impact,
        content_spec=content_spec,
        handoff_pack=handoff_pack,
        readiness_report=readiness_report,
        classification_evidence=classification,
    )

    # Add to queue
    _queue.add_proposal(proposal)

    # Event logging
    _log_proposal_event(proposal)

    return proposal


def _classify_cost_routing_impact(
    proposal_type: str, description: str
) -> tuple[str, str, str]:
    """Classify cost, routing, and performance impact using Wave 2 patterns."""
    description_lower = description.lower()

    cost = "low"
    routing = "none"
    perf = "minimal"

    if any(p in description_lower for p in ["large model", "premium", "concurrent", "bulk"]):
        cost = "high"
        routing = "elevated"
        perf = "significant"
    elif any(p in description_lower for p in ["api call", "external", "cloud", "model"]):
        cost = "medium"
        routing = "standard"
        perf = "moderate"

    if proposal_type in _HIGH_RISK_PROPOSAL_TYPES:
        cost = "blocked"
        routing = "blocked"
        perf = "blocked"

    return cost, routing, perf


def _draft_content_spec(title: str, description: str, proposal_type: str) -> str:
    """Draft a Wave 3 content spec for the proposal."""
    return (
        f"# Expansion Spec: {title}\n\n"
        f"**Type:** {proposal_type}\n\n"
        f"**Description:**\n{description}\n\n"
        f"**Note:** This spec is a draft. No external publish. "
        f"File write requires explicit approval.\n"
        f"**Wave 3 Integration:** Uses content studio template format. "
        f"Dry-run only until approved.\n"
    )


def _draft_handoff_pack(
    title: str,
    proposal_type: str,
    wave_integrations: List[int],
    criteria: List[str],
) -> str:
    """Draft a Wave 3 handoff/prompt pack for the proposal."""
    wave_str = ", ".join(f"Wave {w}" for w in wave_integrations) if wave_integrations else "none"
    criteria_str = "\n".join(f"- {c}" for c in criteria[:5])
    return (
        f"# Handoff Pack: {title}\n\n"
        f"**Proposal Type:** {proposal_type}\n"
        f"**Wave Integrations:** {wave_str}\n\n"
        f"## Acceptance Criteria (top 5)\n{criteria_str}\n\n"
        f"## Instructions\n"
        f"- Review this proposal with owner before execution.\n"
        f"- No auto-execution permitted.\n"
        f"- Log all actions via WorkbenchEventLog.\n"
    )


def _draft_readiness_report(
    status: str, risk_level: str, wave_integrations: List[int]
) -> str:
    """Draft a Wave 3 readiness report for the proposal."""
    wave_str = ", ".join(f"Wave {w}" for w in wave_integrations) if wave_integrations else "none"
    return (
        f"# Readiness Report\n\n"
        f"**Status:** {status}\n"
        f"**Risk:** {risk_level}\n"
        f"**Wave Integrations:** {wave_str}\n\n"
        f"## Safety\n"
        f"- NUS 1: NOT STARTED\n"
        f"- US13 voice: HOLD / UNSAFE / PARKED\n"
        f"- No code self-modification.\n"
        f"- No auto-commit or auto-push.\n"
        f"- No deploy.\n\n"
        f"**Ready for review.** Execution requires explicit owner approval.\n"
    )


def _log_proposal_event(proposal: ExpansionProposal) -> None:
    """Log proposal creation/blocking to WorkbenchEventLog."""
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        from openjarvis.workbench.event_log import (
            EVENT_EXPANSION_PROPOSAL_CREATED,
            EVENT_EXPANSION_PROPOSAL_BLOCKED,
            EVENT_EXPANSION_APPROVAL_REQUIRED,
        )
        log = WorkbenchEventLog()
        session_id = "wave4_expansion"
        if proposal.status == PROPOSAL_STATUS_BLOCKED:
            log.push(
                session_id=session_id,
                task_id=proposal.proposal_id,
                event_type=EVENT_EXPANSION_PROPOSAL_BLOCKED,
                title=f"Expansion proposal blocked: {proposal.title}",
                detail=proposal.blocked_reason or "blocked",
                tone="error",
            )
        elif proposal.status == PROPOSAL_STATUS_NEEDS_APPROVAL:
            log.push(
                session_id=session_id,
                task_id=proposal.proposal_id,
                event_type=EVENT_EXPANSION_APPROVAL_REQUIRED,
                title=f"Expansion proposal needs approval: {proposal.title}",
                detail=proposal.approval_required_reason or "needs_approval",
                tone="warning",
            )
        else:
            log.push(
                session_id=session_id,
                task_id=proposal.proposal_id,
                event_type=EVENT_EXPANSION_PROPOSAL_CREATED,
                title=f"Expansion proposal created: {proposal.title}",
                detail=f"risk={proposal.risk_level} type={proposal.proposal_type}",
                tone="info",
            )
    except Exception:
        pass  # Event log failure never blocks proposal creation


def log_opportunity_detected(opp: ExpansionOpportunity) -> None:
    """Log an expansion opportunity detection event."""
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        from openjarvis.workbench.event_log import EVENT_EXPANSION_OPPORTUNITY_DETECTED
        log = WorkbenchEventLog()
        log.push(
            session_id="wave4_expansion",
            task_id=opp.opportunity_id,
            event_type=EVENT_EXPANSION_OPPORTUNITY_DETECTED,
            title=f"Expansion opportunity detected: {opp.title}",
            detail=opp.description,
            tone="info",
        )
    except Exception:
        pass


def log_validation_plan_generated(proposal_id: str, vp: ValidationPlan) -> None:
    """Log a validation plan generation event."""
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        from openjarvis.workbench.event_log import EVENT_EXPANSION_VALIDATION_PLAN_GENERATED
        log = WorkbenchEventLog()
        log.push(
            session_id="wave4_expansion",
            task_id=proposal_id,
            event_type=EVENT_EXPANSION_VALIDATION_PLAN_GENERATED,
            title=f"Validation plan generated for proposal {proposal_id}",
            detail=f"{len(vp.steps)} steps, {len(vp.safety_checks)} safety checks",
            tone="info",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Wave 1 integration: propose new Wave 1 resources
# ---------------------------------------------------------------------------

def propose_wave1_skill(
    skill_name: str,
    skill_description: str,
    opportunity_id: str = "",
) -> ExpansionProposal:
    """Create a proposal to add a new Wave 1 skill.

    Classified as needs_approval — no auto-registration.
    """
    return create_expansion_proposal(
        opportunity_id=opportunity_id or f"opp_{uuid.uuid4().hex[:8]}",
        title=f"Propose new Wave 1 skill: {skill_name}",
        description=skill_description,
        proposal_type="wave1_skill_register",
        wave_integrations=[1],
    )


def propose_wave1_automation(
    trigger_name: str,
    trigger_description: str,
    opportunity_id: str = "",
) -> ExpansionProposal:
    """Create a proposal to add a new Wave 1 automation trigger.

    Classified as needs_approval — no auto-registration.
    """
    return create_expansion_proposal(
        opportunity_id=opportunity_id or f"opp_{uuid.uuid4().hex[:8]}",
        title=f"Propose new Wave 1 automation trigger: {trigger_name}",
        description=trigger_description,
        proposal_type="wave1_automation_register",
        wave_integrations=[1],
    )


def propose_wave1_knowledge_source(
    source_name: str,
    source_description: str,
    opportunity_id: str = "",
) -> ExpansionProposal:
    """Create a proposal to add a new Wave 1 knowledge source.

    Classified as needs_approval — no auto-registration.
    """
    return create_expansion_proposal(
        opportunity_id=opportunity_id or f"opp_{uuid.uuid4().hex[:8]}",
        title=f"Propose new Wave 1 knowledge source: {source_name}",
        description=source_description,
        proposal_type="wave1_knowledge_source_register",
        wave_integrations=[1],
    )


def propose_wave1_research_provider(
    provider_name: str,
    provider_description: str,
    opportunity_id: str = "",
) -> ExpansionProposal:
    """Create a proposal to add a new Wave 1 research provider.

    Classified as needs_approval — no auto-registration.
    """
    return create_expansion_proposal(
        opportunity_id=opportunity_id or f"opp_{uuid.uuid4().hex[:8]}",
        title=f"Propose new Wave 1 research provider: {provider_name}",
        description=provider_description,
        proposal_type="wave1_research_provider_register",
        wave_integrations=[1],
    )


# ---------------------------------------------------------------------------
# Module status
# ---------------------------------------------------------------------------

def get_expansion_status() -> Dict[str, Any]:
    """Return the current Wave 4 expansion module status."""
    queue_summary = _queue.queue_summary()
    return {
        "implemented": True,
        "status": "ready",
        "epic": "epic_h",
        "wave": 4,
        "dry_run_default": True,
        "file_write_requires_approval": True,
        "code_edit_blocked": True,
        "auto_commit_blocked": True,
        "auto_push_blocked": True,
        "deploy_blocked": True,
        "external_send_blocked": True,
        "secret_access_blocked": True,
        "browser_automation_blocked": True,
        "nus1_status": "not_started",
        "us13_voice_status": "HOLD/UNSAFE/PARKED",
        "wave1_integration": True,
        "wave2_integration": True,
        "wave3_integration": True,
        "adversarial_safety_reused": True,
        "approval_gate_active": True,
        "queue": queue_summary,
        "features": [
            "expansion_opportunity_detection",
            "capability_gap_analysis",
            "safe_proposal_creation",
            "dependency_risk_classification",
            "acceptance_criteria_generation",
            "validation_plan_generation",
            "rollback_plan_generation",
            "approval_gated_expansion_queue",
            "wave1_skill_proposal",
            "wave1_automation_proposal",
            "wave1_knowledge_source_proposal",
            "wave1_research_provider_proposal",
            "wave2_cost_routing_classification",
            "wave3_content_spec_drafting",
            "wave3_handoff_pack_drafting",
            "wave3_readiness_report_drafting",
            "event_logging",
        ],
    }


__all__ = [
    "ExpansionOpportunity",
    "ExpansionProposal",
    "ValidationPlan",
    "ExpansionQueue",
    "get_queue",
    "detect_expansion_opportunities",
    "analyze_capability_gaps",
    "classify_proposal_risk",
    "generate_acceptance_criteria",
    "generate_validation_plan",
    "generate_rollback_plan",
    "create_expansion_proposal",
    "propose_wave1_skill",
    "propose_wave1_automation",
    "propose_wave1_knowledge_source",
    "propose_wave1_research_provider",
    "log_opportunity_detected",
    "log_validation_plan_generated",
    "get_expansion_status",
    "PROPOSAL_STATUS_DRAFT",
    "PROPOSAL_STATUS_SAFE",
    "PROPOSAL_STATUS_NEEDS_APPROVAL",
    "PROPOSAL_STATUS_BLOCKED",
    "PROPOSAL_STATUS_VALIDATED",
    "PROPOSAL_STATUS_REJECTED",
    "RISK_LOW",
    "RISK_MEDIUM",
    "RISK_HIGH",
    "RISK_CRITICAL",
    "OPPORTUNITY_DETECTED",
    "OPPORTUNITY_GAP",
    "OPPORTUNITY_SKILL",
    "OPPORTUNITY_AUTOMATION",
    "OPPORTUNITY_KNOWLEDGE",
    "OPPORTUNITY_RESEARCH",
    "OPPORTUNITY_OPTIMIZATION",
    "OPPORTUNITY_CONTENT",
]
