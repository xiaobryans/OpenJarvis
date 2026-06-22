"""Plan 9 — Role-Based Model Routing Matrix.

Every discovered manager, worker, and agent role has three tiers:
  CHEAP  — easy, small, low-risk tasks (classification, formatting, reads, extraction)
  BALANCED — normal serious work (coding, planning, testing, review, connector work)
  BEST   — hard/high-risk work only when justified (architecture, security, deploy risk)

Core rule: Use the lowest-cost model that safely completes the task with enough quality.

This extends (does not replace) the existing JARVIS_ROUTING_MODEL_POLICY.md and
LearnedRouter. Routing here is the role-based default policy table that feeds into
LearnedRouter.recommend_for_task() and CosGmOrchestrator routing decisions.

Future-proof: newly registered managers/workers inherit DEFAULT_ROUTING unless they
declare a custom override. Missing model policy is a validation failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Tier constants
# ---------------------------------------------------------------------------

class ModelTier(str, Enum):
    CHEAP = "cheap"          # qwen3:0.6b–4b, gpt-4o-mini, claude-haiku
    BALANCED = "balanced"    # qwen3:8b–14b, gpt-4o, claude-sonnet
    BEST = "best"            # qwen3:30b+, claude-opus, o1, gpt-4.5
    STOP = "stop"            # 3+ failures — break approach, do not escalate


# Concrete model suggestions per tier (advisory — actual model set in config)
CHEAP_MODELS = ["gpt-4o-mini", "claude-3-haiku", "qwen3:4b", "local/qwen3:0.6b"]
BALANCED_MODELS = ["gpt-4o", "claude-sonnet-4-5", "qwen3:14b"]
BEST_MODELS = ["claude-opus-4", "o1", "gpt-4.5", "qwen3:30b"]


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
        }


# ---------------------------------------------------------------------------
# Default routing (inherited by all future managers/workers)
# ---------------------------------------------------------------------------

DEFAULT_ROUTING = ModelRoutingEntry(
    role_id="__default__",
    role_type="any",
    cheap_model="gpt-4o-mini",
    balanced_model="gpt-4o",
    best_model="claude-opus-4",
    escalation_rule="Escalate to best when: risk=high/critical OR complexity=complex OR failures>=2",
    fallback_rule="If primary unavailable: try same-tier alternative; if none, use balanced",
    cost_justification="Default policy: balanced for normal work, cheap for reads/formatting, best for architecture/security",
    evidence_requirements="Structured output + decision record for all tiers",
    default_tier=ModelTier.BALANCED,
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
        return errors

    def to_list(self) -> List[Dict]:
        return [e.to_dict() for e in self.entries]


# ---------------------------------------------------------------------------
# Factory — all 17 managers + 30 workers
# ---------------------------------------------------------------------------

def _cheap(base: str = "gpt-4o-mini") -> str:
    return base

def _balanced(base: str = "gpt-4o") -> str:
    return base

def _best(base: str = "claude-opus-4") -> str:
    return base

_STD_ESC = "Escalate balanced→best when: risk=high/critical OR complexity=complex OR failures>=2"
_STD_FALLBACK = "Fall back to balanced if best unavailable; fall back to cheap if only reads needed"
_STD_EVIDENCE = "Structured output + decision record required"


def get_role_routing_matrix() -> RoleModelRoutingMatrix:
    """Return the full Plan 9 role-model routing matrix.

    Covers all 17 managers and 30 workers. All entries inherit DEFAULT_ROUTING
    semantics. Custom overrides are documented with override_reason.
    """
    entries = [
        # ===================================================================
        # MANAGERS (17)
        # ===================================================================
        ModelRoutingEntry(
            role_id="coding_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC + "; also escalate for cross-system refactors",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Normal coding = balanced. Architecture/security = best.",
            evidence_requirements=_STD_EVIDENCE + "; test pass required for all coding tasks",
        ),
        ModelRoutingEntry(
            role_id="architecture_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Architecture tasks default to best; simple reads use cheap",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Architecture decisions are inherently high-reasoning; best justified",
            evidence_requirements=_STD_EVIDENCE + "; design doc required",
            default_tier=ModelTier.BEST,
            override_reason="Architecture is default-best per cost law: high failure cost justifies it",
        ),
        ModelRoutingEntry(
            role_id="testing_validation_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Test planning and review = balanced; simple log reads = cheap",
            evidence_requirements=_STD_EVIDENCE + "; test outputs required",
        ),
        ModelRoutingEntry(
            role_id="code_review_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC + "; security diffs always best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Review of simple diffs = balanced; security-sensitive diffs = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="debugging_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC + "; hard failures after 2 attempts = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Log reads = cheap; normal debugging = balanced; critical regressions = best",
            evidence_requirements=_STD_EVIDENCE + "; root cause trace required",
        ),
        ModelRoutingEntry(
            role_id="research_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Complex multi-hop research = best; simple lookup = cheap",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Research complexity varies widely; cheap for simple lookups",
            evidence_requirements=_STD_EVIDENCE + "; source citations required",
        ),
        ModelRoutingEntry(
            role_id="memory_knowledge_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Memory reads = cheap; knowledge synthesis = balanced; critical memory ops = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Most memory ops are reads (cheap); synthesis is balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Memory manager default is cheap: most work is retrieval not reasoning",
        ),
        ModelRoutingEntry(
            role_id="documentation_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Simple formatting/updates = cheap; full docs generation = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Docs work is mostly low-risk; cheap tier handles most cases",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Docs manager default is cheap: formatting/text work is cheap-sufficient",
        ),
        ModelRoutingEntry(
            role_id="product_ux_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="UI/UX review = balanced; critical UX decisions = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="operations_automation_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Automation = balanced; destructive/critical ops = best with approval",
            evidence_requirements=_STD_EVIDENCE + "; destructive ops require Bryan approval",
        ),
        ModelRoutingEntry(
            role_id="governance_safety_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Policy reads = cheap; gate checks = balanced; security decisions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Governance requires correctness; best for security/deploy decisions",
            evidence_requirements=_STD_EVIDENCE + "; audit event required for all gate checks",
        ),
        ModelRoutingEntry(
            role_id="release_packaging_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Release planning = best; simple packaging = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Deploy risk is high; best justified for release decisions",
            evidence_requirements=_STD_EVIDENCE + "; Bryan approval required before deploy execution",
            default_tier=ModelTier.BEST,
            override_reason="Release/deploy = default-best: deploy risk justifies it per cost law",
        ),
        ModelRoutingEntry(
            role_id="data_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Data reads = cheap; transforms = balanced; schema changes = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="cost_routing_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Cost analysis = balanced; routing policy changes = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Ironic but necessary: cost manager must itself be cost-aware",
            evidence_requirements=_STD_EVIDENCE + "; routing changes require cost ledger evidence",
            default_tier=ModelTier.CHEAP,
            override_reason="Cost manager default cheap: most cost analysis is reads/math, not reasoning",
        ),
        ModelRoutingEntry(
            role_id="nus_learning_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="NUS recommendations = balanced; learning model updates = best",
            evidence_requirements=_STD_EVIDENCE + "; scorecard data required",
        ),
        ModelRoutingEntry(
            role_id="connector_auth_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Connector status reads = cheap; OAuth changes = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Connector reads are cheap; auth changes are high-risk = best",
            evidence_requirements=_STD_EVIDENCE + "; secrets must never appear in evidence",
        ),
        ModelRoutingEntry(
            role_id="runtime_ops_manager",
            role_type="manager",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Health reads = cheap; recovery plans = balanced; infra changes = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Ops reads are cheap; infra changes require careful reasoning = best",
            evidence_requirements=_STD_EVIDENCE + "; infra changes require Bryan approval",
        ),

        # ===================================================================
        # WORKERS (30)
        # ===================================================================
        ModelRoutingEntry(
            role_id="backend_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Backend coding = balanced; complex multi-service = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="frontend_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Frontend changes = balanced; most are cheap for simple UI",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Frontend worker default cheap: CSS/simple UI changes are cheap-sufficient",
        ),
        ModelRoutingEntry(
            role_id="test_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Test generation = balanced; test analysis = cheap",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="debug_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Log reads = cheap; stack trace analysis = balanced; deep regressions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Debug log reads are cheap; root cause requires balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
            override_reason="Debug worker first-pass is cheap (log reads); escalates as needed",
        ),
        ModelRoutingEntry(
            role_id="refactor_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Refactors = balanced; cross-module = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="integration_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Integration work = balanced; cross-system = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="security_code_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Security checks always start at best; reads can be cheap",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Security is high-risk; best justified as default for execution",
            evidence_requirements=_STD_EVIDENCE + "; secret scan evidence required",
            default_tier=ModelTier.BEST,
            override_reason="Security worker default best: high-risk, failure cost is very high",
        ),
        ModelRoutingEntry(
            role_id="performance_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Performance reads = cheap; optimization = balanced; profiling = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="dependency_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Dep reads = cheap; version conflicts = balanced; security deps = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Most dependency work is reads = cheap",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="git_commit_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Commit msg generation = cheap; diff review = balanced; secret scan = cheap",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Git commit workflow is mostly cheap; reasoning only for edge cases",
            evidence_requirements=_STD_EVIDENCE + "; secret scan before every push",
            default_tier=ModelTier.CHEAP,
            override_reason="Commit worker default cheap: message generation + secret scan = cheap",
        ),
        ModelRoutingEntry(
            role_id="system_architecture_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="All system arch work defaults to best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="System arch decisions are high-reasoning; best always justified",
            evidence_requirements=_STD_EVIDENCE + "; design doc required",
            default_tier=ModelTier.BEST,
        ),
        ModelRoutingEntry(
            role_id="contract_design_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Contract design = balanced; API design changes = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="integration_architecture_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Integration arch = best; simple mapping = balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.BEST,
        ),
        ModelRoutingEntry(
            role_id="scalability_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Scalability analysis = best when risk is high",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="unit_test_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Simple tests = cheap; complex test logic = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Unit tests are straightforward = cheap/balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="integration_test_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Integration test work = balanced",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="regression_test_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC + "; critical regressions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Regression review = balanced; critical regressions = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="doctor_check_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Health checks = cheap; diagnostic reasoning = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Doctor checks are structured reads = cheap",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="acceptance_evidence_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Evidence collection = cheap; evidence synthesis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Evidence collection is structured extraction = cheap",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="secret_safety_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Secret scan = cheap deterministic; policy analysis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Secret scanning is pattern matching = cheap",
            evidence_requirements=_STD_EVIDENCE + "; scan result required before any commit/push",
            default_tier=ModelTier.CHEAP,
            override_reason="Secret worker uses cheap deterministic scan, not reasoning",
        ),
        ModelRoutingEntry(
            role_id="policy_gate_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Policy reads = cheap; gate evaluation = balanced; hard gates = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Policy gate evaluation is structured; cheap for simple gates",
            evidence_requirements=_STD_EVIDENCE + "; gate result required",
        ),
        ModelRoutingEntry(
            role_id="risk_classification_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Risk reads = cheap; classification = balanced; borderline = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Risk classification is structured evaluation = cheap/balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="approval_scope_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Scope reads = cheap; boundary analysis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Approval scope is structured classification = cheap",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="local_research_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Context reads = cheap; synthesis = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Local research is context retrieval = cheap by default",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="documentation_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Formatting = cheap; full generation = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Docs writing is cheap; complex synthesis = balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="release_packaging_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Packaging = balanced; deploy prep = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Release packaging has high risk = best for deploy steps",
            evidence_requirements=_STD_EVIDENCE + "; Bryan approval required before deploy execution",
            default_tier=ModelTier.BEST,
        ),
        ModelRoutingEntry(
            role_id="runtime_ops_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Health reads = cheap; ops actions = balanced; infra changes = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Ops reads are cheap; infra actions need careful reasoning",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="cost_analysis_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Cost reads = cheap; optimization = balanced",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Cost analysis is structured math = cheap",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),
        ModelRoutingEntry(
            role_id="data_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="Data reads = cheap; transforms = balanced; schema = best",
            evidence_requirements=_STD_EVIDENCE,
        ),
        ModelRoutingEntry(
            role_id="nus_learning_worker",
            role_type="worker",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule=_STD_ESC,
            fallback_rule=_STD_FALLBACK,
            cost_justification="NUS data reads = cheap; model updates = balanced",
            evidence_requirements=_STD_EVIDENCE,
            default_tier=ModelTier.CHEAP,
        ),

        # ===================================================================
        # SPECIAL ROLES
        # ===================================================================
        ModelRoutingEntry(
            role_id="jarvis_pa",
            role_type="agent",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="PA coordination = balanced; hard approval decisions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Jarvis PA is front-door; uses stable balanced model by default",
            evidence_requirements="Final report must include files changed, tests, proof, blockers",
            default_tier=ModelTier.BALANCED,
        ),
        ModelRoutingEntry(
            role_id="cos_gm",
            role_type="agent",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="COS/GM routing = balanced; org-level decisions = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="COS/GM orchestrates all managers; balanced is sufficient for routing",
            evidence_requirements=_STD_EVIDENCE + "; activation plan required",
        ),
        ModelRoutingEntry(
            role_id="retrieval_worker",
            role_type="worker",
            cheap_model=_cheap("gpt-4o-mini"),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Retrieval is always cheap; never escalate for pure reads",
            fallback_rule="If cheap unavailable, use local deterministic search",
            cost_justification="Retrieval = pattern matching + extraction = cheap deterministic",
            evidence_requirements="Evidence packet with sources; compact not raw context",
            default_tier=ModelTier.CHEAP,
            override_reason="Retrieval workers are always cheap — reasoning not needed for reads",
        ),
        ModelRoutingEntry(
            role_id="batch_integration_manager",
            role_type="agent",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Patch integration = balanced; conflict resolution = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Batch integration requires careful merging = balanced minimum",
            evidence_requirements=_STD_EVIDENCE + "; all worker patches must appear in final diff",
            default_tier=ModelTier.BALANCED,
        ),
        ModelRoutingEntry(
            role_id="integration_review_manager",
            role_type="agent",
            cheap_model=_cheap(),
            balanced_model=_balanced(),
            best_model=_best(),
            escalation_rule="Integration review = balanced; security-sensitive = best",
            fallback_rule=_STD_FALLBACK,
            cost_justification="Independent review catches integration errors; balanced sufficient",
            evidence_requirements=_STD_EVIDENCE + "; must verify all assigned items in final diff",
            default_tier=ModelTier.BALANCED,
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
