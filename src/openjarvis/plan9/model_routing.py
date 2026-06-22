"""Plan 9K — Role-Based Model Routing Matrix.

Every discovered manager, worker, and agent role has three tiers:
  CHEAP    — capability-specific cheap model (not one universal cheap model)
  BALANCED — capability-specific balanced model
  BEST     — high-reasoning trusted model for high-risk work

Core rules (Plan 9K):
  - cheap routing MUST be capability-specific (not one universal gpt-4o-mini for all)
  - cheap_coding uses deepseek/deepseek-chat (coding specialist)
  - cheap_research uses perplexity/sonar (web-grounded specialist)
  - cheap_extraction/reads uses openai/gpt-4o-mini (reliable structured output)
  - security/billing/IAM/secrets/deploy/final_review: NEVER cheap or local models
  - PA/front-door: GPT/OpenAI stable route only
  - Kimi: NOT default — requires benchmark proof
  - Ollama/Qwen/local: FORBIDDEN for normal cloud work

This extends (does not replace) the existing JARVIS_ROUTING_MODEL_POLICY.md and
LearnedRouter. Routing here feeds into LearnedRouter.recommend_for_task() and
CosGmOrchestrator routing decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Tier constants
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    CHEAP = "cheap"
    BALANCED = "balanced"
    BEST = "best"
    STOP = "stop"            # 3+ failures — break approach, do not escalate


# ---------------------------------------------------------------------------
# Plan 9K: capability-specific model assignments (not one universal model)
# ---------------------------------------------------------------------------

# Cheap models — specialized by use case
_CHEAP_CODING = "deepseek/deepseek-chat"          # coding specialist, cheap
_CHEAP_FAST = "openai/gpt-4o-mini"                # reads, extraction, formatting
_CHEAP_RESEARCH = "perplexity/sonar"              # web-grounded, cheap research
_CHEAP_UI = "openai/gpt-4o-mini"                  # structured output for UI
_CHEAP_TEST = "deepseek/deepseek-chat"            # test generation specialist

# Balanced models — specialized by use case
_BALANCED_CODING = "anthropic/claude-sonnet-4-20250514"   # strong coding/balanced
_BALANCED_DEFAULT = "openai/gpt-4o"               # stable, reliable balanced
_BALANCED_RESEARCH = "perplexity/sonar-pro"       # deep web-grounded research
_BALANCED_UI = "anthropic/claude-haiku-4-5"       # fast UI generation

# Best models — high-reasoning, trusted providers only
_BEST_TRUSTED = "anthropic/claude-opus-4-20250514"    # max trust, high-risk work
_BEST_CODING = "anthropic/claude-sonnet-4-20250514"   # best practical coding

# PA front-door models — GPT/OpenAI stable route
_PA_CHEAP = "openai/gpt-4o-mini"
_PA_BALANCED = "openai/gpt-4o"
_PA_BEST = "anthropic/claude-sonnet-4-20250514"   # escalation only

# Security/billing/IAM/deploy/final review — Anthropic only, no cheap/local
_SECURITY_BALANCED = "anthropic/claude-sonnet-4-20250514"
_SECURITY_BEST = "anthropic/claude-opus-4-20250514"


# ---------------------------------------------------------------------------
# Routing entry
# ---------------------------------------------------------------------------

@dataclass
class ModelRoutingEntry:
    """Role-based model routing policy for a single manager or worker role."""

    role_id: str
    role_type: str            # "manager" | "worker" | "agent" | "validator"
    cheap_model: str
    balanced_model: str
    best_model: str
    escalation_rule: str      # when to escalate from balanced → best
    fallback_rule: str        # when provider unavailable
    cost_justification: str   # why these tiers are appropriate
    evidence_requirements: str
    default_tier: ModelTier = ModelTier.BALANCED
    override_reason: Optional[str] = None  # if this differs from default inheritance
    # Plan 9K additions
    required_capabilities: List[str] = field(default_factory=list)
    preferred_capabilities: List[str] = field(default_factory=list)
    forbidden_model_classes: List[str] = field(default_factory=list)
    fallback_chain: List[str] = field(default_factory=list)
    risk_threshold: str = "medium"

    def tier_for_task(self, risk: str, complexity: str, failures: int) -> ModelTier:
        """Advisory tier selection for a given task context."""
        if failures >= 3:
            return ModelTier.STOP
        if risk in ("high", "critical") or complexity == "complex":
            return ModelTier.BEST
        if risk == "low" and complexity == "simple":
            return ModelTier.CHEAP
        return ModelTier.BALANCED

    def to_dict(self) -> Dict:
        return {
            "role_id": self.role_id,
            "role_type": self.role_type,
            "cheap_model": self.cheap_model,
            "balanced_model": self.balanced_model,
            "best_model": self.best_model,
            "escalation_rule": self.escalation_rule,
            "fallback_rule": self.fallback_rule,
            "cost_justification": self.cost_justification,
            "evidence_requirements": self.evidence_requirements,
            "default_tier": self.default_tier.value,
            "override_reason": self.override_reason,
            "required_capabilities": self.required_capabilities,
            "preferred_capabilities": self.preferred_capabilities,
            "forbidden_model_classes": self.forbidden_model_classes,
            "fallback_chain": self.fallback_chain,
            "risk_threshold": self.risk_threshold,
        }


# ---------------------------------------------------------------------------
# Default routing (inherited by all future managers/workers)
# ---------------------------------------------------------------------------

DEFAULT_ROUTING = ModelRoutingEntry(
    role_id="__default__",
    role_type="any",
    cheap_model=_CHEAP_FAST,
    balanced_model=_BALANCED_DEFAULT,
    best_model=_BEST_TRUSTED,
    escalation_rule="Escalate to best when: risk=high/critical OR complexity=complex OR failures>=2",
    fallback_rule="If primary unavailable: try same-tier alternative from catalog; never fall to Ollama/local",
    cost_justification="Default policy: balanced for normal work, cheap for reads/formatting, best for architecture/security",
    evidence_requirements="Structured output + decision record for all tiers",
    default_tier=ModelTier.BALANCED,
    required_capabilities=["default_chat"],
    forbidden_model_classes=["ollama", "offline_fallback"],
    fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BEST_TRUSTED],
    risk_threshold="medium",
)


# ---------------------------------------------------------------------------
# Role routing matrix
# ---------------------------------------------------------------------------

@dataclass
class RoleModelRoutingMatrix:
    entries: List[ModelRoutingEntry] = field(default_factory=list)
    _index: Dict[str, ModelRoutingEntry] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        for e in self.entries:
            self._index[e.role_id] = e

    def get(self, role_id: str) -> ModelRoutingEntry:
        """Return routing for role_id, falling back to DEFAULT_ROUTING."""
        return self._index.get(role_id, DEFAULT_ROUTING)

    def all_role_ids(self) -> List[str]:
        return [e.role_id for e in self.entries]

    def validate(self) -> List[str]:
        """Return list of validation errors. Empty = valid."""
        errors = []
        for e in self.entries:
            if not e.cheap_model:
                errors.append(f"{e.role_id}: missing cheap_model")
            if not e.balanced_model:
                errors.append(f"{e.role_id}: missing balanced_model")
            if not e.best_model:
                errors.append(f"{e.role_id}: missing best_model")
            if not e.escalation_rule:
                errors.append(f"{e.role_id}: missing escalation_rule")
            if not e.required_capabilities:
                errors.append(f"{e.role_id}: missing required_capabilities (Plan 9K requirement)")
            if not e.fallback_chain:
                errors.append(f"{e.role_id}: missing fallback_chain (Plan 9K requirement)")
            # Validate no ollama/local in security/deploy/iam roles
            if "security" in e.role_id or "release" in e.role_id or "governance" in e.role_id:
                if any("qwen" in m or "ollama" in m or "local" in m.lower()
                       for m in [e.cheap_model, e.balanced_model, e.best_model]):
                    errors.append(f"{e.role_id}: local/ollama model FORBIDDEN in security/release/governance roles")
        return errors

    def validate_no_universal_cheap(self) -> List[str]:
        """Validate that roles are NOT all using the same universal cheap model."""
        cheap_counts: Dict[str, int] = {}
        for e in self.entries:
            cheap_counts[e.cheap_model] = cheap_counts.get(e.cheap_model, 0) + 1

        violations = []
        total = len(self.entries)
        for model, count in cheap_counts.items():
            pct = count / total
            # If >80% of roles use the same cheap model, flag it
            if pct > 0.8:
                violations.append(
                    f"Universal cheap model detected: {model!r} used by {count}/{total} roles "
                    f"({pct:.0%}). Plan 9K requires capability-specific cheap routing."
                )
        return violations

    def to_list(self) -> List[Dict]:
        return [e.to_dict() for e in self.entries]


# ---------------------------------------------------------------------------
# Standard rules shared across roles
# ---------------------------------------------------------------------------

_STD_ESC = "Escalate balanced→best when: risk=high/critical OR complexity=complex OR failures>=2"
_STD_FALLBACK = "Fall back to balanced if best unavailable; cloud fallback only — never fall to Ollama/local unless provider_outage/offline mode"
_STD_EVIDENCE = "Structured output + decision record required"
_SEC_FALLBACK = "Security roles: never use cheap/local. Escalate Sonnet→Opus. HOLD if Opus unavailable."


def get_role_routing_matrix() -> RoleModelRoutingMatrix:
    """Return the full Plan 9K role-model routing matrix.

    Plan 9K guarantees:
    - No role uses a universal fixed cheap/balanced/best model
    - Coding roles use coding-specialist cheap models (deepseek)
    - Research roles use web-grounded cheap models (perplexity/sonar)
    - Security/deploy/IAM roles NEVER use cheap or local models
    - PA/front-door uses GPT/OpenAI stable route
    - Kimi NOT default — benchmark-gated
    - Ollama/local OFFLINE FALLBACK ONLY
    """
    entries = [
        # ===================================================================
        # MANAGERS (17) — Plan 9K: capability-specific models per role
        # ===================================================================
        ModelRoutingEntry(
            role_id="coding_manager",
            role_type="manager",
            cheap_model=_CHEAP_CODING,          # deepseek: coding specialist cheap
            balanced_model=_BALANCED_CODING,     # claude-sonnet: strong coding
            best_model=_BEST_TRUSTED,
            escalation_rule=_STD_ESC + "; also escalate for cross-system refactors",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=coding-specialist (deepseek). Balanced=claude-sonnet (strong coding). Best=claude-opus.",
            evidence_requirements=_STD_EVIDENCE + "; test pass required for all coding tasks",
            required_capabilities=["coding"],
            preferred_capabilities=["backend_api", "tool_calling", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_CODING, _BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="architecture_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # reads/analysis: gpt-4o-mini
            balanced_model=_BALANCED_CODING,    # claude-sonnet: strong reasoning
            best_model=_BEST_TRUSTED,
            escalation_rule="Architecture tasks default to best; simple reads use cheap",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Architecture decisions are inherently high-reasoning; Sonnet balanced, Opus best.",
            evidence_requirements=_STD_EVIDENCE + "; design doc required",
            default_tier=ModelTier.BEST,
            override_reason="Architecture is default-best per cost law: high failure cost justifies it",
            required_capabilities=["high_reasoning", "planning"],
            preferred_capabilities=["coding", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="testing_validation_manager",
            role_type="manager",
            cheap_model=_CHEAP_TEST,            # deepseek: test gen specialist
            balanced_model=_BALANCED_DEFAULT,   # gpt-4o: reliable balanced
            best_model=_BALANCED_CODING,        # claude-sonnet: best for test review
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=deepseek (test gen). Balanced=gpt-4o. Best=claude-sonnet for complex test logic.",
            evidence_requirements=_STD_EVIDENCE + "; test outputs required",
            required_capabilities=["test_generation"],
            preferred_capabilities=["coding", "structured_output", "json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_TEST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="code_review_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # diff reads: gpt-4o-mini
            balanced_model=_BALANCED_CODING,    # review: claude-sonnet
            best_model=_BEST_TRUSTED,
            escalation_rule=_STD_ESC + "; security diffs always best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=diff reads (gpt-4o-mini). Balanced=claude-sonnet review. Best=claude-opus for security diffs.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["coding"],
            preferred_capabilities=["security_review", "backend_api"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="debugging_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # log reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # debugging: gpt-4o
            best_model=_BALANCED_CODING,        # hard failures: claude-sonnet
            escalation_rule=_STD_ESC + "; hard failures after 2 attempts = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=log reads (gpt-4o-mini). Balanced=gpt-4o. Best=claude-sonnet for hard regressions.",
            evidence_requirements=_STD_EVIDENCE + "; root cause trace required",
            required_capabilities=["debugging"],
            preferred_capabilities=["coding", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="research_manager",
            role_type="manager",
            cheap_model=_CHEAP_RESEARCH,        # perplexity/sonar: web-grounded cheap
            balanced_model=_BALANCED_RESEARCH,  # perplexity/sonar-pro: deep research
            best_model=_BALANCED_CODING,        # claude-sonnet fallback if perplexity unavailable
            escalation_rule="Web/current-info research → Perplexity. Complex multi-hop = sonar-pro. synthesis = claude-sonnet",
            fallback_rule="If Perplexity unavailable: fall back to claude-sonnet for synthesis",
            cost_justification="Cheap=perplexity/sonar (web-grounded). Balanced=sonar-pro. Best=claude-sonnet if web not needed.",
            evidence_requirements=_STD_EVIDENCE + "; source citations required",
            required_capabilities=["research"],
            preferred_capabilities=["web_grounded", "citations", "source_synthesis"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_RESEARCH, _BALANCED_RESEARCH, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="memory_knowledge_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # retrieval: gpt-4o-mini
            balanced_model=_CHEAP_FAST,         # knowledge synthesis: still cheap
            best_model=_BALANCED_DEFAULT,       # critical memory ops: gpt-4o
            escalation_rule="Memory reads = cheap; knowledge synthesis = cheap; critical memory ops = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Most memory ops are reads/extraction: gpt-4o-mini is sufficient.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Memory manager default cheap: most work is retrieval not reasoning",
            required_capabilities=["extraction"],
            preferred_capabilities=["summarization", "json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="documentation_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # formatting: gpt-4o-mini
            balanced_model=_CHEAP_FAST,         # docs gen: still gpt-4o-mini (sufficient)
            best_model=_BALANCED_DEFAULT,       # complex synthesis: gpt-4o
            escalation_rule="Simple formatting/updates = cheap; full docs generation = cheap; complex synthesis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Docs work is text generation: gpt-4o-mini handles most cases. gpt-4o for complex synthesis.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Docs manager default cheap: formatting/text work is cheap-sufficient",
            required_capabilities=["summarization"],
            preferred_capabilities=["structured_output", "cheap_fast"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="product_ux_manager",
            role_type="manager",
            cheap_model=_CHEAP_UI,              # UI reviews: gpt-4o-mini
            balanced_model=_BALANCED_UI,        # UI work: claude-haiku (fast UI)
            best_model=_BALANCED_CODING,        # critical UX: claude-sonnet
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=gpt-4o-mini (UI reviews). Balanced=claude-haiku (fast UI). Best=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["frontend_ui"],
            preferred_capabilities=["planning", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_UI, _BALANCED_UI, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="operations_automation_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # automation: gpt-4o
            best_model=_BALANCED_CODING,        # critical/destructive ops: claude-sonnet
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Reads=gpt-4o-mini. Automation=gpt-4o. Destructive=claude-sonnet (approval required).",
            evidence_requirements=_STD_EVIDENCE + "; destructive ops require Bryan approval",
            required_capabilities=["planning"],
            preferred_capabilities=["structured_output", "tool_calling"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="governance_safety_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # policy reads only (gpt-4o-mini)
            balanced_model=_SECURITY_BALANCED,  # gate checks: claude-sonnet
            best_model=_SECURITY_BEST,          # security decisions: claude-opus
            escalation_rule="Policy reads = cheap; gate checks = claude-sonnet; security decisions = claude-opus",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Governance: sonnet for gate checks, opus for security. Never cheap for execution.",
            evidence_requirements=_STD_EVIDENCE + "; audit event required for all gate checks",
            required_capabilities=["security_review", "high_reasoning"],
            preferred_capabilities=["final_review", "billing_iam_review"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="critical",
        ),
        ModelRoutingEntry(
            role_id="release_packaging_manager",
            role_type="manager",
            cheap_model=_SECURITY_BALANCED,     # NEVER cheap for deploy — sonnet minimum
            balanced_model=_SECURITY_BALANCED,  # packaging: claude-sonnet
            best_model=_SECURITY_BEST,          # deploy decisions: claude-opus
            escalation_rule="Release planning = claude-opus; packaging = claude-sonnet. Never cheap or local.",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Deploy risk too high for cheap. Sonnet minimum, opus for final deploy decisions.",
            evidence_requirements=_STD_EVIDENCE + "; Bryan approval required before deploy execution",
            default_tier=ModelTier.BEST,
            override_reason="Release/deploy = default-best: deploy risk justifies it per cost law",
            required_capabilities=["deploy_review", "high_reasoning"],
            preferred_capabilities=["final_review", "planning"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="critical",
        ),
        ModelRoutingEntry(
            role_id="data_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # data reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # transforms: gpt-4o
            best_model=_BALANCED_CODING,        # schema changes: claude-sonnet
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Data reads=gpt-4o-mini. Transforms=gpt-4o. Schema=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["structured_output"],
            preferred_capabilities=["json_reliability", "extraction"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="cost_routing_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # cost analysis: gpt-4o-mini (reads/math)
            balanced_model=_BALANCED_DEFAULT,   # routing policy changes: gpt-4o
            best_model=_BALANCED_CODING,        # critical policy: claude-sonnet
            escalation_rule="Cost analysis = cheap; routing policy changes = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cost manager default cheap: analysis is reads/math not reasoning.",
            evidence_requirements=_STD_EVIDENCE + "; routing changes require cost ledger evidence",
            default_tier=ModelTier.CHEAP,
            override_reason="Cost manager default cheap: most cost analysis is reads/math, not reasoning",
            required_capabilities=["extraction"],
            preferred_capabilities=["structured_output", "json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="nus_learning_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # scorecard reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # model updates: gpt-4o
            best_model=_BALANCED_CODING,        # learning policy: claude-sonnet
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="NUS reads=gpt-4o-mini. Updates=gpt-4o. Policy=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE + "; scorecard data required",
            required_capabilities=["structured_output"],
            preferred_capabilities=["planning", "extraction"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="connector_auth_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # connector reads: gpt-4o-mini
            balanced_model=_SECURITY_BALANCED,  # OAuth changes: claude-sonnet
            best_model=_SECURITY_BEST,          # secrets/auth: claude-opus
            escalation_rule="Connector status reads = cheap; OAuth changes = claude-sonnet; secrets = claude-opus",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Reads=gpt-4o-mini. Auth=claude-sonnet. Secrets=claude-opus (never cheap).",
            evidence_requirements=_STD_EVIDENCE + "; secrets must never appear in evidence",
            required_capabilities=["tool_calling"],
            preferred_capabilities=["security_review", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_CHEAP_FAST, _SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="runtime_ops_manager",
            role_type="manager",
            cheap_model=_CHEAP_FAST,            # health reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # recovery plans: gpt-4o
            best_model=_BALANCED_CODING,        # infra changes: claude-sonnet
            escalation_rule="Health reads = cheap; recovery plans = balanced; infra changes = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Ops reads=gpt-4o-mini. Recovery=gpt-4o. Infra=claude-sonnet (Bryan approval required).",
            evidence_requirements=_STD_EVIDENCE + "; infra changes require Bryan approval",
            required_capabilities=["planning"],
            preferred_capabilities=["structured_output", "tool_calling"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="high",
        ),

        # ===================================================================
        # WORKERS (30) — Plan 9K: capability-specific models per role
        # ===================================================================
        ModelRoutingEntry(
            role_id="backend_worker",
            role_type="worker",
            cheap_model=_CHEAP_CODING,          # backend coding: deepseek
            balanced_model=_BALANCED_CODING,    # backend work: claude-sonnet
            best_model=_BEST_TRUSTED,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=deepseek (backend specialist). Balanced=claude-sonnet. Best=claude-opus for multi-service.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["coding", "backend_api"],
            preferred_capabilities=["structured_output", "tool_calling"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_CODING, _BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="frontend_worker",
            role_type="worker",
            cheap_model=_CHEAP_UI,              # CSS/simple UI: gpt-4o-mini
            balanced_model=_BALANCED_UI,        # UI generation: claude-haiku
            best_model=_BALANCED_CODING,        # complex UI: claude-sonnet
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=gpt-4o-mini (CSS/UI). Balanced=claude-haiku (fast UI). Best=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Frontend worker default cheap: CSS/simple UI changes are cheap-sufficient",
            required_capabilities=["frontend_ui"],
            preferred_capabilities=["structured_output", "cheap_fast"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_UI, _BALANCED_UI, _BALANCED_CODING],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="test_worker",
            role_type="worker",
            cheap_model=_CHEAP_TEST,            # test gen: deepseek
            balanced_model=_BALANCED_DEFAULT,   # complex tests: gpt-4o
            best_model=_BALANCED_CODING,        # test review: claude-sonnet
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=deepseek (test gen). Balanced=gpt-4o. Best=claude-sonnet for complex logic.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["test_generation"],
            preferred_capabilities=["coding", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_TEST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="debug_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,            # log reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # stack trace: gpt-4o
            best_model=_BALANCED_CODING,        # deep regressions: claude-sonnet
            escalation_rule="Log reads = cheap; stack trace analysis = balanced; deep regressions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Reads=gpt-4o-mini. Stack trace=gpt-4o. Deep regressions=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Debug worker first-pass is cheap (log reads); escalates as needed",
            required_capabilities=["debugging"],
            preferred_capabilities=["extraction", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="refactor_worker",
            role_type="worker",
            cheap_model=_CHEAP_CODING,          # simple refactor: deepseek
            balanced_model=_BALANCED_CODING,    # complex refactor: claude-sonnet
            best_model=_BEST_TRUSTED,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=deepseek. Balanced=claude-sonnet. Best=claude-opus for cross-module.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["coding"],
            preferred_capabilities=["repo_scale_refactor", "backend_api"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_CODING, _BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="integration_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Reads=gpt-4o-mini. Integration=gpt-4o. Cross-system=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["coding", "tool_calling"],
            preferred_capabilities=["backend_api", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="security_code_worker",
            role_type="worker",
            cheap_model=_SECURITY_BALANCED,     # NEVER cheap for security — sonnet minimum
            balanced_model=_SECURITY_BALANCED,  # security work: claude-sonnet
            best_model=_SECURITY_BEST,          # critical security: claude-opus
            escalation_rule="Security checks always start at claude-sonnet; critical = claude-opus. Never cheap or local.",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Security is high-risk: sonnet minimum, opus for critical. Cheap/local FORBIDDEN.",
            evidence_requirements=_STD_EVIDENCE + "; secret scan evidence required",
            default_tier=ModelTier.BEST,
            override_reason="Security worker default best: high-risk, failure cost is very high",
            required_capabilities=["security_review", "high_reasoning"],
            preferred_capabilities=["secrets_review", "final_review"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi", "deepseek", "xai"],
            fallback_chain=[_SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="critical",
        ),
        ModelRoutingEntry(
            role_id="performance_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Perf reads=gpt-4o-mini. Optimization=gpt-4o. Profiling=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["coding"],
            preferred_capabilities=["backend_api", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="dependency_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,            # dep reads: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # conflict resolution: gpt-4o
            best_model=_BALANCED_CODING,        # security deps: claude-sonnet
            escalation_rule="Dep reads = cheap; version conflicts = balanced; security deps = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Most dependency work is reads: gpt-4o-mini. Security deps=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction"],
            preferred_capabilities=["structured_output", "cheap_fast"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="git_commit_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,            # commit msg gen + secret scan
            balanced_model=_BALANCED_DEFAULT,   # diff review
            best_model=_BALANCED_DEFAULT,       # edge cases
            escalation_rule="Commit msg generation = cheap; diff review = balanced; secret scan = cheap",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Commit workflow is mostly cheap: msg gen + secret scan. gpt-4o-mini sufficient.",
            evidence_requirements=_STD_EVIDENCE + "; secret scan before every push",
            default_tier=ModelTier.CHEAP,
            override_reason="Commit worker default cheap: message generation + secret scan = cheap",
            required_capabilities=["extraction", "cheap_fast"],
            preferred_capabilities=["structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="system_architecture_worker",
            role_type="worker",
            cheap_model=_BALANCED_CODING,       # NEVER cheap for system arch
            balanced_model=_BALANCED_CODING,    # system arch: claude-sonnet
            best_model=_BEST_TRUSTED,
            escalation_rule="All system arch work defaults to best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="System arch decisions are high-reasoning: sonnet minimum, opus best.",
            evidence_requirements=_STD_EVIDENCE + "; design doc required",
            default_tier=ModelTier.BEST,
            required_capabilities=["high_reasoning", "planning"],
            preferred_capabilities=["coding", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="contract_design_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Reads=gpt-4o-mini. Design=gpt-4o. API design changes=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["structured_output"],
            preferred_capabilities=["backend_api", "planning"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="integration_architecture_worker",
            role_type="worker",
            cheap_model=_BALANCED_CODING,       # never cheap for integration arch
            balanced_model=_BALANCED_CODING,
            best_model=_BEST_TRUSTED,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Integration arch: sonnet minimum, opus best.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.BEST,
            required_capabilities=["high_reasoning", "planning"],
            preferred_capabilities=["backend_api", "tool_calling"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="scalability_worker",
            role_type="worker",
            cheap_model=_BALANCED_DEFAULT,
            balanced_model=_BALANCED_CODING,
            best_model=_BEST_TRUSTED,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Scalability: gpt-4o balanced, claude-sonnet best.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["planning", "high_reasoning"],
            preferred_capabilities=["backend_api"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_BALANCED_DEFAULT, _BALANCED_CODING, _BEST_TRUSTED],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="unit_test_worker",
            role_type="worker",
            cheap_model=_CHEAP_TEST,            # deepseek: test gen specialist
            balanced_model=_BALANCED_DEFAULT,   # complex tests: gpt-4o
            best_model=_BALANCED_CODING,
            escalation_rule="Simple tests = cheap; complex test logic = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Unit test gen=deepseek (cheap). Complex logic=gpt-4o.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["test_generation"],
            preferred_capabilities=["cheap_fast", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_TEST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="integration_test_worker",
            role_type="worker",
            cheap_model=_CHEAP_TEST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cheap=deepseek (test gen). Balanced=gpt-4o. Best=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["test_generation", "coding"],
            preferred_capabilities=["backend_api", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_TEST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="regression_test_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule=_STD_ESC + "; critical regressions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Reads=gpt-4o-mini. Review=gpt-4o. Critical regressions=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["test_generation", "debugging"],
            preferred_capabilities=["coding"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="doctor_check_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_CHEAP_FAST,         # health checks = cheap structured reads
            best_model=_BALANCED_DEFAULT,
            escalation_rule="Health checks = cheap; diagnostic reasoning = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Doctor checks are structured reads: gpt-4o-mini sufficient.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction", "cheap_fast"],
            preferred_capabilities=["structured_output", "json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="acceptance_evidence_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_DEFAULT,
            escalation_rule="Evidence collection = cheap; evidence synthesis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Evidence collection is structured extraction: gpt-4o-mini.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction", "structured_output"],
            preferred_capabilities=["summarization", "json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="secret_safety_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_CHEAP_FAST,         # pattern matching = cheap
            best_model=_BALANCED_CODING,        # policy analysis if needed
            escalation_rule="Secret scan = cheap deterministic; policy analysis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Secret scanning is pattern matching = cheap. gpt-4o-mini sufficient.",
            evidence_requirements=_STD_EVIDENCE + "; scan result required before any commit/push",
            default_tier=ModelTier.CHEAP,
            override_reason="Secret worker uses cheap deterministic scan, not reasoning",
            required_capabilities=["extraction", "cheap_fast"],
            preferred_capabilities=["secrets_review"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_CODING],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="policy_gate_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,            # policy reads
            balanced_model=_SECURITY_BALANCED,  # gate evaluation: claude-sonnet
            best_model=_SECURITY_BEST,          # hard gates: claude-opus
            escalation_rule="Policy reads = cheap; gate evaluation = claude-sonnet; hard gates = claude-opus",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Policy reads=gpt-4o-mini. Gates=claude-sonnet. Hard gates=claude-opus.",
            evidence_requirements=_STD_EVIDENCE + "; gate result required",
            required_capabilities=["structured_output"],
            preferred_capabilities=["json_reliability", "extraction"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_CHEAP_FAST, _SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="risk_classification_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule="Risk reads = cheap; classification = balanced; borderline = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Risk classification is structured evaluation: gpt-4o-mini cheap, gpt-4o balanced.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction", "structured_output"],
            preferred_capabilities=["json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="approval_scope_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_CHEAP_FAST,
            best_model=_BALANCED_DEFAULT,
            escalation_rule="Scope reads = cheap; boundary analysis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Scope classification is cheap structured work.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction", "structured_output"],
            preferred_capabilities=["cheap_fast"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="local_research_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,            # context retrieval: gpt-4o-mini
            balanced_model=_BALANCED_DEFAULT,   # synthesis: gpt-4o
            best_model=_BALANCED_RESEARCH,      # web context needed: perplexity
            escalation_rule="Context reads = cheap; synthesis = balanced; web context = perplexity/sonar-pro",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Local research: reads=gpt-4o-mini, synthesis=gpt-4o, web=perplexity/sonar-pro.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["research"],
            preferred_capabilities=["summarization", "extraction"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_RESEARCH],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="documentation_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_CHEAP_FAST,         # docs gen is cheap
            best_model=_BALANCED_DEFAULT,
            escalation_rule="Formatting = cheap; full generation = cheap; complex synthesis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Docs writing: gpt-4o-mini handles almost everything. gpt-4o for complex.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["summarization"],
            preferred_capabilities=["cheap_fast", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="release_packaging_worker",
            role_type="worker",
            cheap_model=_SECURITY_BALANCED,     # NEVER cheap for deploy
            balanced_model=_SECURITY_BALANCED,
            best_model=_SECURITY_BEST,
            escalation_rule="Packaging = claude-sonnet; deploy prep = claude-opus. Never cheap or local.",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Release packaging: high risk. Sonnet minimum, opus for deploy steps.",
            evidence_requirements=_STD_EVIDENCE + "; Bryan approval required before deploy execution",
            default_tier=ModelTier.BEST,
            required_capabilities=["deploy_review", "high_reasoning"],
            preferred_capabilities=["planning"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="critical",
        ),
        ModelRoutingEntry(
            role_id="runtime_ops_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule="Health reads = cheap; ops actions = balanced; infra changes = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Health reads=gpt-4o-mini. Actions=gpt-4o. Infra=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["structured_output"],
            preferred_capabilities=["planning", "tool_calling"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="high",
        ),
        ModelRoutingEntry(
            role_id="cost_analysis_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_CHEAP_FAST,         # cost analysis = cheap reads/math
            best_model=_BALANCED_DEFAULT,
            escalation_rule="Cost reads = cheap; optimization = cheap; policy = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cost analysis is structured math: gpt-4o-mini sufficient.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction", "cheap_fast"],
            preferred_capabilities=["structured_output", "json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="data_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,
            best_model=_BALANCED_CODING,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Data reads=gpt-4o-mini. Transforms=gpt-4o. Schema=claude-sonnet.",
            evidence_requirements=_STD_EVIDENCE,
            required_capabilities=["structured_output", "extraction"],
            preferred_capabilities=["json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="nus_learning_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,
            balanced_model=_CHEAP_FAST,         # NUS reads = cheap
            best_model=_BALANCED_DEFAULT,
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="NUS data reads: gpt-4o-mini sufficient. Updates=gpt-4o.",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            required_capabilities=["extraction"],
            preferred_capabilities=["structured_output", "cheap_fast"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),

        # ===================================================================
        # SPECIAL ROLES
        # ===================================================================
        ModelRoutingEntry(
            role_id="jarvis_pa",
            role_type="agent",
            cheap_model=_PA_CHEAP,              # PA cheap: gpt-4o-mini (GPT stable)
            balanced_model=_PA_BALANCED,        # PA balanced: gpt-4o (GPT stable)
            best_model=_PA_BEST,               # PA best: claude-sonnet (approval decisions)
            escalation_rule="PA coordination = gpt-4o; hard approval decisions = claude-sonnet. Always GPT/OpenAI route.",
            fallback_rule="PA uses GPT/OpenAI stable route. Never Ollama/Qwen for normal chat.",
            cost_justification="PA front-door uses stable GPT/OpenAI models for consistency. Not Ollama/Qwen/Kimi.",
            evidence_requirements="Final report must include files changed, tests, proof, blockers",
            default_tier=ModelTier.BALANCED,
            override_reason="PA uses GPT/OpenAI stable route for reliability. Not local or experimental models.",
            required_capabilities=["default_chat", "tool_calling"],
            preferred_capabilities=["planning", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_PA_CHEAP, _PA_BALANCED, _PA_BEST],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="cos_gm",
            role_type="agent",
            cheap_model=_PA_CHEAP,
            balanced_model=_PA_BALANCED,
            best_model=_BEST_TRUSTED,
            escalation_rule="COS/GM routing = gpt-4o; org-level decisions = claude-opus",
            fallback_rule=_STD_FALLBACK,
            cost_justification="COS/GM orchestrates all managers; gpt-4o sufficient for routing.",
            evidence_requirements=_STD_EVIDENCE + "; activation plan required",
            required_capabilities=["default_chat", "planning"],
            preferred_capabilities=["tool_calling", "structured_output"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_PA_CHEAP, _PA_BALANCED, _BEST_TRUSTED],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="retrieval_worker",
            role_type="worker",
            cheap_model=_CHEAP_FAST,            # retrieval = always cheap extraction
            balanced_model=_CHEAP_FAST,
            best_model=_BALANCED_DEFAULT,
            escalation_rule="Retrieval is always cheap; never escalate for pure reads",
            fallback_rule="If cheap unavailable, use local deterministic search",
            cost_justification="Retrieval = pattern matching + extraction = cheap deterministic.",
            evidence_requirements="Evidence packet with sources; compact not raw context",
            default_tier=ModelTier.CHEAP,
            override_reason="Retrieval workers are always cheap — reasoning not needed for reads",
            required_capabilities=["extraction", "cheap_fast"],
            preferred_capabilities=["json_reliability"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT],
            risk_threshold="low",
        ),
        ModelRoutingEntry(
            role_id="batch_integration_manager",
            role_type="agent",
            cheap_model=_CHEAP_FAST,
            balanced_model=_BALANCED_DEFAULT,   # patch integration: gpt-4o
            best_model=_BALANCED_CODING,        # conflict resolution: claude-sonnet
            escalation_rule="Patch integration = gpt-4o; conflict resolution = claude-sonnet",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Batch integration: gpt-4o balanced. claude-sonnet for conflicts.",
            evidence_requirements=_STD_EVIDENCE + "; all worker patches must appear in final diff",
            default_tier=ModelTier.BALANCED,
            required_capabilities=["coding", "structured_output"],
            preferred_capabilities=["json_reliability", "tool_calling"],
            forbidden_model_classes=["ollama", "offline_fallback"],
            fallback_chain=[_CHEAP_FAST, _BALANCED_DEFAULT, _BALANCED_CODING],
            risk_threshold="medium",
        ),
        ModelRoutingEntry(
            role_id="integration_review_manager",
            role_type="agent",
            cheap_model=_SECURITY_BALANCED,     # review: claude-sonnet minimum
            balanced_model=_SECURITY_BALANCED,
            best_model=_SECURITY_BEST,          # security-sensitive: claude-opus
            escalation_rule="Integration review = claude-sonnet; security-sensitive = claude-opus",
            fallback_rule=_SEC_FALLBACK,
            cost_justification="Independent review: sonnet minimum. Security diffs=claude-opus.",
            evidence_requirements=_STD_EVIDENCE + "; must verify all assigned items in final diff",
            default_tier=ModelTier.BALANCED,
            required_capabilities=["coding", "security_review"],
            preferred_capabilities=["final_review", "high_reasoning"],
            forbidden_model_classes=["ollama", "offline_fallback", "kimi"],
            fallback_chain=[_SECURITY_BALANCED, _SECURITY_BEST],
            risk_threshold="high",
        ),
    ]

    return RoleModelRoutingMatrix(entries=entries)


# Singleton
_MATRIX: Optional[RoleModelRoutingMatrix] = None


def get_routing_matrix() -> RoleModelRoutingMatrix:
    global _MATRIX
    if _MATRIX is None:
        _MATRIX = get_role_routing_matrix()
    return _MATRIX
