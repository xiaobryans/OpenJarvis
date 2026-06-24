"""Plan 9 — Jarvis PA vs Brain/Model Layer Architecture.

Defines the formal distinction between:
  - Jarvis PA  : front-door for Bryan (summarize, coordinate, approve, report)
  - Brain layer: COS/GM + all managers + all workers + reviewers + specialists

AI Organization Structure:
  Bryan
  → Jarvis PA
    → COS/GM
      → Managers (17 discovered)
        → Workers / specialists (30 discovered)
          → Reviewers / validators / auditors
          ← Aggregated results
        ← Manager reports
      ← COS/GM summary
    ← Jarvis PA final status report
  ← Bryan

Every manager/worker must have:
  - clear ownership
  - assigned scope
  - acceptance criteria
  - evidence requirements
  - model tier policy (from model_routing.py)
  - report format
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class JarvisLayer(str, Enum):
    JARVIS_PA = "jarvis_pa"
    COS_GM = "cos_gm"
    MANAGER = "manager"
    WORKER = "worker"
    REVIEWER = "reviewer"    # independent verification layer — not a manager child
    TESTER = "tester"        # independent testing layer — not a manager child
    VALIDATOR = "validator"  # independent audit gate — not a manager child


@dataclass(frozen=True)
class JarvisPAConfig:
    """Configuration for the Jarvis PA (Personal Assistant) layer.

    Jarvis PA is Bryan's front-door. It does NOT do deep reasoning or
    multi-provider routing itself — it delegates to COS/GM and brain layer.
    """

    layer: JarvisLayer = JarvisLayer.JARVIS_PA
    role: str = "Personal Assistant front-door for Bryan"
    responsibilities: tuple = (
        "Receive requests from Bryan",
        "Summarize outputs from COS/GM",
        "Coordinate approval requests",
        "Ask for clarification when required",
        "Report final status to Bryan",
        "Gate hard-approval actions",
    )
    stable_model_count: int = 2          # PA uses only 1-2 stable models
    model_preference: str = "balanced"   # PA uses balanced tier, not best
    never_delegates_to: tuple = ()       # PA does not bypass COS/GM
    report_format: str = (
        "1. Summary of what was done. "
        "2. Files changed. "
        "3. Tests run. "
        "4. Validation proof. "
        "5. Blockers. "
        "6. Rollback notes. "
        "7. Secret scan result."
    )

    def to_dict(self) -> Dict:
        return {
            "layer": self.layer.value,
            "role": self.role,
            "responsibilities": list(self.responsibilities),
            "stable_model_count": self.stable_model_count,
            "model_preference": self.model_preference,
            "report_format": self.report_format,
        }


@dataclass(frozen=True)
class JarvisBrainLayerConfig:
    """Configuration for the Jarvis Brain/Model layer.

    The brain layer includes COS/GM, all managers, all workers, all reviewers,
    researchers, testers, deployers, security, memory, connectors, UI, docs,
    operations, and every other discovered or future manager/team.

    The brain layer may route across:
      - GPT/ChatGPT (OpenAI, OpenRouter)
      - Claude (Anthropic, OpenRouter)
      - Perplexity / research-style routes
      - Local/cheap models (Qwen, Llama, Mistral)
      - Coding models (specialized)
      - Verification models
      - Any configured provider in model_catalog.py
    """

    layer: JarvisLayer = JarvisLayer.COS_GM
    role: str = "Brain layer: COS/GM + all managers + workers + reviewers"
    routing_policy: str = "role-based cheap/balanced/best per model_routing.py"
    multi_provider: bool = True
    provider_routes: tuple = (
        "OpenAI (gpt-4o, gpt-4o-mini)",
        "Anthropic (claude-sonnet, claude-opus)",
        "OpenRouter (multi-provider)",
        "Perplexity (research routes)",
        "Local models (Ollama, vllm — when MacBook on)",
    )
    escalation_rule: str = (
        "Use lowest-cost model sufficient for task quality. "
        "Escalate only with complexity/risk/failure-count justification."
    )

    def to_dict(self) -> Dict:
        return {
            "layer": self.layer.value,
            "role": self.role,
            "routing_policy": self.routing_policy,
            "multi_provider": self.multi_provider,
            "provider_routes": list(self.provider_routes),
            "escalation_rule": self.escalation_rule,
        }


@dataclass
class OrgNode:
    """Node in the AI organization hierarchy."""
    node_id: str
    display_name: str
    layer: JarvisLayer
    reports_to: Optional[str] = None      # node_id of parent
    ownership: str = ""
    scope: str = ""
    acceptance_criteria: str = ""
    evidence_requirements: str = ""
    model_tier_ref: str = ""              # points to model_routing.py entry
    report_format: str = ""
    children: List[str] = field(default_factory=list)  # child node_ids


def get_org_hierarchy() -> List[OrgNode]:
    """Return the full AI organization hierarchy for Plan 9.

    Canonical chain:
      Bryan
      → Jarvis PA                 (user-facing front door; only interaction point)
        → COS/GM                  (command coordinator; activates managers)
          → Domain Managers       (domain owners; supervise worker pools)
            → Worker Teams        (execution cells; dry-run safe by default)
            ← Manager reports
          → Reviewer/Tester/Verifier Layer  (INDEPENDENT — not a manager child)
            (wired into COS/GM after worker execution, before returning to Jarvis PA)
          ← COS/GM integration
        ← Jarvis PA summary / approval request
      ← Bryan

    Approval chain:
      Worker/Manager requests action
      → Domain Manager validates need
      → Reviewer/Authority layer checks risk where applicable
      → COS/GM escalates
      → Jarvis PA asks Bryan
      → Bryan approves/denies through Jarvis only
      → COS/GM routes decision back down
    """
    return [
        OrgNode(
            node_id="bryan",
            display_name="Bryan (Owner)",
            layer=JarvisLayer.JARVIS_PA,
            reports_to=None,
            ownership="System owner. Ultimate approver.",
            scope="All of Jarvis. All projects. All decisions.",
            children=["jarvis_pa"],
        ),
        OrgNode(
            node_id="jarvis_pa",
            display_name="Jarvis PA",
            layer=JarvisLayer.JARVIS_PA,
            reports_to="bryan",
            ownership="Front-door assistant. Summarizer. Approval gatekeeper.",
            scope=(
                "Sole user-facing interaction point. "
                "Coordinate all managers via COS/GM. Report to Bryan. "
                "Workers, managers, reviewers, and testers must NOT directly "
                "produce user-facing final responses."
            ),
            acceptance_criteria="Bryan receives complete, honest, evidence-backed summary",
            evidence_requirements="Final report with all 7 fields (files/tests/proof/blockers/rollback/secret scan)",
            model_tier_ref="jarvis_pa",
            report_format="7-field final report format per p9.truth.report_format",
            children=["cos_gm"],
        ),
        OrgNode(
            node_id="cos_gm",
            display_name="COS / GM (Chief of Staff / General Manager)",
            layer=JarvisLayer.COS_GM,
            reports_to="jarvis_pa",
            ownership="Orchestrates all domain managers. Owns activation plans.",
            scope=(
                "Task routing to managers. Cross-manager coordination. Goal tracking. "
                "After workers execute, routes results through reviewer_layer before "
                "returning to Jarvis PA when validation_required=True."
            ),
            acceptance_criteria="All managers activated, results aggregated, reviewer integrated, no orphaned tasks",
            evidence_requirements=(
                "ActivationPlan with all managers assigned and results collected + "
                "VerificationReport when validation_required=True"
            ),
            model_tier_ref="cos_gm",
            children=[
                "coding_manager", "architecture_manager", "testing_validation_manager",
                "code_review_manager", "debugging_manager", "research_manager",
                "memory_knowledge_manager", "documentation_manager", "product_ux_manager",
                "operations_automation_manager", "governance_safety_manager",
                "release_packaging_manager", "data_manager", "cost_routing_manager",
                "nus_learning_manager", "connector_auth_manager", "runtime_ops_manager",
                "reviewer_layer",
            ],
        ),
        # Independent Reviewer/Tester/Verifier Layer
        # This is a child of COS/GM (receives work after workers complete) but is
        # INDEPENDENT from managers — it never verifies its own output (self-verify blocked).
        OrgNode(
            node_id="reviewer_layer",
            display_name="Reviewer / Tester / Verifier (Independent)",
            layer=JarvisLayer.REVIEWER,
            reports_to="cos_gm",
            ownership="Independent verification of worker/manager outputs",
            scope=(
                "Audit worker execution results for evidence, contradictions, staleness. "
                "Verify tester outputs. Gate COS/GM integration before Jarvis PA response. "
                "Self-verify is permanently blocked. Cannot verify own output."
            ),
            acceptance_criteria=(
                "VerificationReport produced with ACCEPTED or REJECTED outcome. "
                "Fix list provided on rejection. Trace includes reviewer_verification event."
            ),
            evidence_requirements=(
                "VerificationReport.acceptance_trace for ACCEPTED; "
                "VerificationReport.fix_list for REJECTED"
            ),
            model_tier_ref="reviewer_layer",
            report_format="VerificationReport.to_dict() — structured, no raw chain-of-thought",
            children=[],
        ),
        # Managers
        OrgNode(
            node_id="coding_manager",
            display_name="Coding Manager",
            layer=JarvisLayer.MANAGER,
            reports_to="cos_gm",
            ownership="All software coding tasks and code quality",
            scope="Backend, frontend, test generation, refactoring, debugging",
            acceptance_criteria="Code compiles, tests pass, no regressions, diff reviewed",
            evidence_requirements="Test results + diff + no linter errors",
            model_tier_ref="coding_manager",
            children=["backend_worker", "frontend_worker", "test_worker", "debug_worker",
                      "refactor_worker", "integration_worker", "security_code_worker",
                      "performance_worker", "dependency_worker", "git_commit_worker"],
        ),
        OrgNode(
            node_id="architecture_manager",
            display_name="Architecture Manager",
            layer=JarvisLayer.MANAGER,
            reports_to="cos_gm",
            ownership="System architecture and design decisions",
            scope="Architecture reviews, design docs, contracts, scalability",
            acceptance_criteria="Design doc produced, risks identified, integration plan reviewed",
            evidence_requirements="Design doc + risk analysis",
            model_tier_ref="architecture_manager",
            children=["system_architecture_worker", "contract_design_worker",
                      "integration_architecture_worker", "scalability_worker"],
        ),
        OrgNode(
            node_id="testing_validation_manager",
            display_name="Testing & Validation Manager",
            layer=JarvisLayer.MANAGER,
            reports_to="cos_gm",
            ownership="All testing, validation, and acceptance evidence",
            scope="Unit/integration/regression tests, doctor checks, acceptance evidence",
            acceptance_criteria="All targeted tests pass, no regressions, evidence captured",
            evidence_requirements="Test output + coverage + acceptance evidence",
            model_tier_ref="testing_validation_manager",
            children=["unit_test_worker", "integration_test_worker", "regression_test_worker",
                      "doctor_check_worker", "acceptance_evidence_worker"],
        ),
        OrgNode(
            node_id="governance_safety_manager",
            display_name="Governance & Safety Manager",
            layer=JarvisLayer.MANAGER,
            reports_to="cos_gm",
            ownership="Policy, security, approvals, audit, rollback",
            scope="Gate checks, secret scanning, authority classification, audit logs",
            acceptance_criteria="All gates checked, secrets clean, audit trail complete",
            evidence_requirements="Gate check results + secret scan + audit events",
            model_tier_ref="governance_safety_manager",
            children=["secret_safety_worker", "policy_gate_worker", "risk_classification_worker",
                      "approval_scope_worker"],
        ),
        # (Other managers follow same pattern — abbreviated for brevity in this node list)
    ]


def get_pa_config() -> JarvisPAConfig:
    return JarvisPAConfig()


def get_brain_layer_config() -> JarvisBrainLayerConfig:
    return JarvisBrainLayerConfig()
