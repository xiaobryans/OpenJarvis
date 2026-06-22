"""Plan 9K — Dynamic Specialized Routing Engine.

Every manager/worker/COS/brain role declares capability requirements.
The router selects the best available model from the catalog based on:
  - required capabilities
  - preferred capabilities
  - forbidden model classes
  - fallback chain
  - escalation rules
  - cost ceiling
  - latency preference
  - risk threshold
  - benchmark requirements

Routing decisions are audit-visible: every decision explains why the model
was chosen, why cheaper alternatives were rejected, and the fallback reason
if applicable.

Rules:
- PA/front-door uses stable GPT/OpenAI-style route only.
- Ollama/Qwen/local are fallback_only — not selected for normal cloud work.
- Kimi is NOT selected unless benchmark_status == ACCEPTED.
- Security/billing/IAM/secrets/deploy/final_review: requires high_reasoning
  and trusted providers (anthropic/openai). Local/cheap FORBIDDEN.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from openjarvis.plan9.model_catalog_9k import (
    AllowedRiskLevel,
    BenchmarkStatus,
    CapabilityTag,
    LatencyClass,
    ModelEntry9K,
    PA_STABLE_MODELS,
    ProviderCatalog9K,
    get_provider_catalog,
)


# ---------------------------------------------------------------------------
# Role capability declarations
# ---------------------------------------------------------------------------

class RiskThreshold(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    def allows_risk(self, model_risk: AllowedRiskLevel) -> bool:
        order = ["low", "medium", "high", "critical"]
        role_idx = order.index(self.value)
        model_idx = order.index(model_risk.value)
        return model_idx >= role_idx


@dataclass
class RoleCapabilityDeclaration:
    """What a manager/worker/COS/brain role needs from the routing engine."""
    role_id: str
    role_type: str                          # manager | worker | agent | validator
    required_capabilities: List[CapabilityTag]
    preferred_capabilities: List[CapabilityTag]
    forbidden_provider_classes: List[str]   # e.g. ["ollama", "offline_fallback"]
    fallback_chain: List[str]               # ordered list of model_ids to try
    escalation_model: str                   # model to use on escalation/failure
    cost_ceiling: str                       # "cheap" | "medium" | "high" | "any"
    latency_preference: LatencyClass
    risk_threshold: RiskThreshold
    benchmark_required_for: List[str]       # model_ids that require benchmark proof
    audit_required: bool = True

    def is_high_risk_role(self) -> bool:
        return self.risk_threshold in (RiskThreshold.HIGH, RiskThreshold.CRITICAL)

    def is_pa_role(self) -> bool:
        return self.role_id in ("jarvis_pa", "cos_gm")

    def to_dict(self) -> Dict:
        return {
            "role_id": self.role_id,
            "role_type": self.role_type,
            "required_capabilities": [t.value for t in self.required_capabilities],
            "preferred_capabilities": [t.value for t in self.preferred_capabilities],
            "forbidden_provider_classes": self.forbidden_provider_classes,
            "fallback_chain": self.fallback_chain,
            "escalation_model": self.escalation_model,
            "cost_ceiling": self.cost_ceiling,
            "latency_preference": self.latency_preference.value,
            "risk_threshold": self.risk_threshold.value,
            "benchmark_required_for": self.benchmark_required_for,
            "audit_required": self.audit_required,
            "is_high_risk_role": self.is_high_risk_role(),
            "is_pa_role": self.is_pa_role(),
        }


# ---------------------------------------------------------------------------
# Role declarations registry
# ---------------------------------------------------------------------------

def _build_role_declarations() -> Dict[str, RoleCapabilityDeclaration]:
    """Build capability declarations for all 17 managers + 30 workers + special roles."""
    decls: Dict[str, RoleCapabilityDeclaration] = {}

    # ---- Jarvis PA (front-door) ----
    # Must use stable GPT/OpenAI-style route. Not Ollama/Qwen.
    decls["jarvis_pa"] = RoleCapabilityDeclaration(
        role_id="jarvis_pa",
        role_type="agent",
        required_capabilities=[CapabilityTag.DEFAULT_CHAT, CapabilityTag.TOOL_CALLING],
        preferred_capabilities=[CapabilityTag.PLANNING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "openai/gpt-5-mini",
            "anthropic/claude-haiku-4-5",
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2", "kimi/kimi-k2-0711-preview"],
        audit_required=True,
    )

    # ---- COS/GM ----
    decls["cos_gm"] = RoleCapabilityDeclaration(
        role_id="cos_gm",
        role_type="agent",
        required_capabilities=[CapabilityTag.DEFAULT_CHAT, CapabilityTag.PLANNING],
        preferred_capabilities=[CapabilityTag.TOOL_CALLING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # =========================================================================
    # MANAGERS
    # =========================================================================

    # ---- Coding Manager ----
    decls["coding_manager"] = RoleCapabilityDeclaration(
        role_id="coding_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.CODING],
        preferred_capabilities=[CapabilityTag.BACKEND_API, CapabilityTag.TOOL_CALLING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",          # cheap coding
            "anthropic/claude-sonnet-4-20250514",  # balanced
            "anthropic/claude-opus-4-20250514",    # best
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2", "kimi/kimi-k2-0711-preview", "openrouter/moonshotai/kimi-k2"],
        audit_required=True,
    )

    # ---- Architecture Manager ----
    decls["architecture_manager"] = RoleCapabilityDeclaration(
        role_id="architecture_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.HIGH_REASONING, CapabilityTag.PLANNING],
        preferred_capabilities=[CapabilityTag.CODING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",  # balanced
            "anthropic/claude-opus-4-20250514",    # best
            "openai/o3-mini",                      # alternative high-reasoning
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Testing/Validation Manager ----
    decls["testing_validation_manager"] = RoleCapabilityDeclaration(
        role_id="testing_validation_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.TEST_GENERATION],
        preferred_capabilities=[CapabilityTag.CODING, CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",          # cheap test gen
            "openai/gpt-4o",                   # balanced
            "anthropic/claude-sonnet-4-20250514",  # best
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Code Review Manager ----
    decls["code_review_manager"] = RoleCapabilityDeclaration(
        role_id="code_review_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.CODING],
        preferred_capabilities=[CapabilityTag.SECURITY_REVIEW, CapabilityTag.BACKEND_API],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # cheap diff reads
            "anthropic/claude-sonnet-4-20250514",  # balanced review
            "anthropic/claude-opus-4-20250514",    # security diffs = best
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Debugging Manager ----
    decls["debugging_manager"] = RoleCapabilityDeclaration(
        role_id="debugging_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.DEBUGGING],
        preferred_capabilities=[CapabilityTag.CODING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # cheap log reads
            "openai/gpt-4o",                   # balanced debug
            "anthropic/claude-sonnet-4-20250514",  # hard failures
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Research Manager ----
    # Prefers web-grounded/citation-capable route
    decls["research_manager"] = RoleCapabilityDeclaration(
        role_id="research_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.RESEARCH],
        preferred_capabilities=[CapabilityTag.WEB_GROUNDED, CapabilityTag.CITATIONS, CapabilityTag.SOURCE_SYNTHESIS],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "perplexity/sonar",                # cheap web-grounded
            "perplexity/sonar-pro",            # balanced deep research
            "anthropic/claude-sonnet-4-20250514",  # fallback if perplexity unavailable
        ],
        escalation_model="perplexity/sonar-pro",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Memory/Knowledge Manager ----
    decls["memory_knowledge_manager"] = RoleCapabilityDeclaration(
        role_id="memory_knowledge_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.EXTRACTION],
        preferred_capabilities=[CapabilityTag.SUMMARIZATION, CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",   # cheap: retrieval is extraction
            "openai/gpt-4o",        # balanced: knowledge synthesis
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Documentation Manager ----
    decls["documentation_manager"] = RoleCapabilityDeclaration(
        role_id="documentation_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.SUMMARIZATION],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.CHEAP_FAST],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cheap: formatting/updates
            "openai/gpt-4o",       # balanced: full docs generation
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Product/UX Manager ----
    decls["product_ux_manager"] = RoleCapabilityDeclaration(
        role_id="product_ux_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.FRONTEND_UI],
        preferred_capabilities=[CapabilityTag.PLANNING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # cheap UI reviews
            "anthropic/claude-haiku-4-5",      # fast UI work
            "anthropic/claude-sonnet-4-20250514",  # best UX decisions
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Operations/Automation Manager ----
    decls["operations_automation_manager"] = RoleCapabilityDeclaration(
        role_id="operations_automation_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.PLANNING],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.TOOL_CALLING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # cheap: reads
            "openai/gpt-4o",                   # balanced: automation
            "anthropic/claude-sonnet-4-20250514",  # critical/destructive ops
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Governance/Safety Manager ----
    # MUST use high_reasoning trusted models for security decisions
    decls["governance_safety_manager"] = RoleCapabilityDeclaration(
        role_id="governance_safety_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.SECURITY_REVIEW, CapabilityTag.HIGH_REASONING],
        preferred_capabilities=[CapabilityTag.FINAL_REVIEW, CapabilityTag.BILLING_IAM_REVIEW],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # policy reads only
            "anthropic/claude-sonnet-4-20250514",  # gate checks
            "anthropic/claude-opus-4-20250514",    # security decisions
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.CRITICAL,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Release/Packaging Manager ----
    # MUST use trusted models — deploy risk is too high for cheap/local
    decls["release_packaging_manager"] = RoleCapabilityDeclaration(
        role_id="release_packaging_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.DEPLOY_REVIEW, CapabilityTag.HIGH_REASONING],
        preferred_capabilities=[CapabilityTag.FINAL_REVIEW, CapabilityTag.PLANNING],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",  # balanced packaging
            "anthropic/claude-opus-4-20250514",    # deploy decisions
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.CRITICAL,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Data Manager ----
    decls["data_manager"] = RoleCapabilityDeclaration(
        role_id="data_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.JSON_RELIABILITY, CapabilityTag.EXTRACTION],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cheap: data reads
            "openai/gpt-4o",       # balanced: transforms
            "anthropic/claude-sonnet-4-20250514",  # schema changes
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Cost/Routing Manager ----
    decls["cost_routing_manager"] = RoleCapabilityDeclaration(
        role_id="cost_routing_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.EXTRACTION],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cheap: cost analysis is reads/math
            "openai/gpt-4o",       # routing policy changes
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- NUS Learning Manager ----
    decls["nus_learning_manager"] = RoleCapabilityDeclaration(
        role_id="nus_learning_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.PLANNING, CapabilityTag.EXTRACTION],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cheap: scorecard reads
            "openai/gpt-4o",       # balanced: model updates
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Connector/Auth Manager ----
    # Auth changes are high-risk; reads are cheap
    decls["connector_auth_manager"] = RoleCapabilityDeclaration(
        role_id="connector_auth_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.TOOL_CALLING],
        preferred_capabilities=[CapabilityTag.SECURITY_REVIEW, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # cheap: status reads
            "anthropic/claude-sonnet-4-20250514",  # OAuth changes
            "anthropic/claude-opus-4-20250514",    # secrets handling
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Runtime Ops Manager ----
    decls["runtime_ops_manager"] = RoleCapabilityDeclaration(
        role_id="runtime_ops_manager",
        role_type="manager",
        required_capabilities=[CapabilityTag.PLANNING],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.TOOL_CALLING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # health reads
            "openai/gpt-4o",                   # recovery plans
            "anthropic/claude-sonnet-4-20250514",  # infra changes
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # =========================================================================
    # WORKERS
    # =========================================================================

    decls["backend_worker"] = RoleCapabilityDeclaration(
        role_id="backend_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.CODING, CapabilityTag.BACKEND_API],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.TOOL_CALLING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",           # cheap backend coding
            "anthropic/claude-sonnet-4-20250514",  # balanced
            "anthropic/claude-opus-4-20250514",    # complex multi-service
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["frontend_worker"] = RoleCapabilityDeclaration(
        role_id="frontend_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.FRONTEND_UI],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.CHEAP_FAST],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # cheap: CSS/simple UI
            "anthropic/claude-haiku-4-5",       # fast UI generation
            "anthropic/claude-sonnet-4-20250514",  # complex UI work
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["test_worker"] = RoleCapabilityDeclaration(
        role_id="test_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.TEST_GENERATION],
        preferred_capabilities=[CapabilityTag.CODING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",           # cheap test gen
            "openai/gpt-4o",                   # balanced
            "anthropic/claude-sonnet-4-20250514",  # complex test logic
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["debug_worker"] = RoleCapabilityDeclaration(
        role_id="debug_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.DEBUGGING],
        preferred_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cheap: log reads
            "openai/gpt-4o",       # balanced: stack trace
            "anthropic/claude-sonnet-4-20250514",  # deep regressions
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["refactor_worker"] = RoleCapabilityDeclaration(
        role_id="refactor_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.CODING],
        preferred_capabilities=[CapabilityTag.REPO_SCALE_REFACTOR, CapabilityTag.BACKEND_API],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",           # cheap refactor
            "anthropic/claude-sonnet-4-20250514",  # balanced/complex
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2", "openrouter/moonshotai/kimi-k2"],
        audit_required=True,
    )

    decls["integration_worker"] = RoleCapabilityDeclaration(
        role_id="integration_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.CODING, CapabilityTag.TOOL_CALLING],
        preferred_capabilities=[CapabilityTag.BACKEND_API, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Security worker — MUST use high_reasoning trusted model ----
    decls["security_code_worker"] = RoleCapabilityDeclaration(
        role_id="security_code_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.SECURITY_REVIEW, CapabilityTag.HIGH_REASONING],
        preferred_capabilities=[CapabilityTag.SECRETS_REVIEW, CapabilityTag.FINAL_REVIEW],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi", "deepseek", "xai"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",  # balanced security
            "anthropic/claude-opus-4-20250514",    # critical security
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.CRITICAL,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["performance_worker"] = RoleCapabilityDeclaration(
        role_id="performance_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.CODING],
        preferred_capabilities=[CapabilityTag.BACKEND_API, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # perf reads
            "openai/gpt-4o",                   # optimization
            "anthropic/claude-sonnet-4-20250514",  # profiling
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["dependency_worker"] = RoleCapabilityDeclaration(
        role_id="dependency_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.CHEAP_FAST],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # dep reads
            "openai/gpt-4o",                   # conflict resolution
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["git_commit_worker"] = RoleCapabilityDeclaration(
        role_id="git_commit_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.CHEAP_FAST],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # commit msg gen + secret scan (cheap)
            "openai/gpt-4o",       # edge cases
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["system_architecture_worker"] = RoleCapabilityDeclaration(
        role_id="system_architecture_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.HIGH_REASONING, CapabilityTag.PLANNING],
        preferred_capabilities=[CapabilityTag.CODING, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["contract_design_worker"] = RoleCapabilityDeclaration(
        role_id="contract_design_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.BACKEND_API, CapabilityTag.PLANNING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["integration_architecture_worker"] = RoleCapabilityDeclaration(
        role_id="integration_architecture_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.HIGH_REASONING, CapabilityTag.PLANNING],
        preferred_capabilities=[CapabilityTag.BACKEND_API, CapabilityTag.TOOL_CALLING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["scalability_worker"] = RoleCapabilityDeclaration(
        role_id="scalability_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.PLANNING, CapabilityTag.HIGH_REASONING],
        preferred_capabilities=[CapabilityTag.BACKEND_API],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["unit_test_worker"] = RoleCapabilityDeclaration(
        role_id="unit_test_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.TEST_GENERATION],
        preferred_capabilities=[CapabilityTag.CHEAP_FAST, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",  # cheap test gen
            "openai/gpt-4o",           # complex test logic
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["integration_test_worker"] = RoleCapabilityDeclaration(
        role_id="integration_test_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.TEST_GENERATION, CapabilityTag.CODING],
        preferred_capabilities=[CapabilityTag.BACKEND_API, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "deepseek/deepseek-chat",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["regression_test_worker"] = RoleCapabilityDeclaration(
        role_id="regression_test_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.TEST_GENERATION, CapabilityTag.DEBUGGING],
        preferred_capabilities=[CapabilityTag.CODING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["doctor_check_worker"] = RoleCapabilityDeclaration(
        role_id="doctor_check_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.CHEAP_FAST],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # health checks are structured reads
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["acceptance_evidence_worker"] = RoleCapabilityDeclaration(
        role_id="acceptance_evidence_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.SUMMARIZATION, CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # evidence collection is cheap
            "openai/gpt-4o",       # synthesis
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Secret safety — pattern matching (cheap deterministic) ----
    decls["secret_safety_worker"] = RoleCapabilityDeclaration(
        role_id="secret_safety_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.CHEAP_FAST],
        preferred_capabilities=[CapabilityTag.SECRETS_REVIEW],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # pattern matching = cheap
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["policy_gate_worker"] = RoleCapabilityDeclaration(
        role_id="policy_gate_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.JSON_RELIABILITY, CapabilityTag.EXTRACTION],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # policy reads
            "anthropic/claude-sonnet-4-20250514",  # hard gates
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["risk_classification_worker"] = RoleCapabilityDeclaration(
        role_id="risk_classification_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cheap structured classification
            "openai/gpt-4o",       # borderline cases
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["approval_scope_worker"] = RoleCapabilityDeclaration(
        role_id="approval_scope_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.CHEAP_FAST],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # scope classification = cheap
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["local_research_worker"] = RoleCapabilityDeclaration(
        role_id="local_research_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.RESEARCH],
        preferred_capabilities=[CapabilityTag.SUMMARIZATION, CapabilityTag.EXTRACTION],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",   # context retrieval
            "openai/gpt-4o",        # synthesis
            "perplexity/sonar-pro", # if web context needed
        ],
        escalation_model="perplexity/sonar-pro",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["documentation_worker"] = RoleCapabilityDeclaration(
        role_id="documentation_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.SUMMARIZATION],
        preferred_capabilities=[CapabilityTag.CHEAP_FAST, CapabilityTag.STRUCTURED_OUTPUT],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # formatting/simple docs = cheap
            "openai/gpt-4o",       # complex docs generation
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    # ---- Release packaging worker (HIGH RISK) ----
    decls["release_packaging_worker"] = RoleCapabilityDeclaration(
        role_id="release_packaging_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.DEPLOY_REVIEW, CapabilityTag.HIGH_REASONING],
        preferred_capabilities=[CapabilityTag.PLANNING],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.CRITICAL,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["runtime_ops_worker"] = RoleCapabilityDeclaration(
        role_id="runtime_ops_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.PLANNING, CapabilityTag.TOOL_CALLING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",              # health reads
            "openai/gpt-4o",                   # ops actions
            "anthropic/claude-sonnet-4-20250514",  # infra changes
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["cost_analysis_worker"] = RoleCapabilityDeclaration(
        role_id="cost_analysis_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.CHEAP_FAST],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # cost analysis = cheap reads/math
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["data_worker"] = RoleCapabilityDeclaration(
        role_id="data_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.EXTRACTION],
        preferred_capabilities=[CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # data reads
            "openai/gpt-4o",       # transforms
            "anthropic/claude-sonnet-4-20250514",  # schema changes
        ],
        escalation_model="anthropic/claude-sonnet-4-20250514",
        cost_ceiling="medium",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["nus_learning_worker"] = RoleCapabilityDeclaration(
        role_id="nus_learning_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION],
        preferred_capabilities=[CapabilityTag.STRUCTURED_OUTPUT, CapabilityTag.CHEAP_FAST],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # NUS data reads = cheap
            "openai/gpt-4o",       # model updates
        ],
        escalation_model="openai/gpt-4o",
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["retrieval_worker"] = RoleCapabilityDeclaration(
        role_id="retrieval_worker",
        role_type="worker",
        required_capabilities=[CapabilityTag.EXTRACTION, CapabilityTag.CHEAP_FAST],
        preferred_capabilities=[CapabilityTag.JSON_RELIABILITY],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o-mini",  # retrieval = always cheap extraction
        ],
        escalation_model="openai/gpt-4o-mini",  # never escalate retrieval workers
        cost_ceiling="cheap",
        latency_preference=LatencyClass.FAST,
        risk_threshold=RiskThreshold.LOW,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["batch_integration_manager"] = RoleCapabilityDeclaration(
        role_id="batch_integration_manager",
        role_type="agent",
        required_capabilities=[CapabilityTag.CODING, CapabilityTag.STRUCTURED_OUTPUT],
        preferred_capabilities=[CapabilityTag.JSON_RELIABILITY, CapabilityTag.TOOL_CALLING],
        forbidden_provider_classes=["ollama", "offline_fallback"],
        fallback_chain=[
            "openai/gpt-4o",
            "anthropic/claude-sonnet-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="high",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.MEDIUM,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    decls["integration_review_manager"] = RoleCapabilityDeclaration(
        role_id="integration_review_manager",
        role_type="agent",
        required_capabilities=[CapabilityTag.CODING, CapabilityTag.SECURITY_REVIEW, CapabilityTag.HIGH_REASONING],
        preferred_capabilities=[CapabilityTag.FINAL_REVIEW],
        forbidden_provider_classes=["ollama", "offline_fallback", "kimi"],
        fallback_chain=[
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-opus-4-20250514",
        ],
        escalation_model="anthropic/claude-opus-4-20250514",
        cost_ceiling="any",
        latency_preference=LatencyClass.MEDIUM,
        risk_threshold=RiskThreshold.HIGH,
        benchmark_required_for=["kimi/kimi-k2"],
        audit_required=True,
    )

    return decls


# Singleton declarations registry
_DECLARATIONS: Optional[Dict[str, RoleCapabilityDeclaration]] = None


def get_role_declarations() -> Dict[str, RoleCapabilityDeclaration]:
    global _DECLARATIONS
    if _DECLARATIONS is None:
        _DECLARATIONS = _build_role_declarations()
    return _DECLARATIONS


# ---------------------------------------------------------------------------
# Routing decision
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision9K:
    """Audit-visible routing decision record."""
    role_id: str
    task_description: str
    task_classification: str
    required_capabilities: List[str]
    chosen_provider: str
    chosen_model_id: str
    route_reason: str
    why_cheaper_rejected: str
    fallback_reason: Optional[str]
    escalation_reason: Optional[str]
    estimated_cost_class: str
    risk_level: str
    benchmark_required: bool
    kimi_eligible: bool
    offline_fallback_active: bool
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "role_id": self.role_id,
            "task_description": self.task_description[:200],
            "task_classification": self.task_classification,
            "required_capabilities": self.required_capabilities,
            "chosen_provider": self.chosen_provider,
            "chosen_model_id": self.chosen_model_id,
            "route_reason": self.route_reason,
            "why_cheaper_rejected": self.why_cheaper_rejected,
            "fallback_reason": self.fallback_reason,
            "escalation_reason": self.escalation_reason,
            "estimated_cost_class": self.estimated_cost_class,
            "risk_level": self.risk_level,
            "benchmark_required": self.benchmark_required,
            "kimi_eligible": self.kimi_eligible,
            "offline_fallback_active": self.offline_fallback_active,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Specialized Router
# ---------------------------------------------------------------------------

class SpecializedRouter:
    """Dynamic capability-based routing engine.

    Selects the best model for each role based on:
    - required/preferred capability tags
    - provider availability and health
    - benchmark status (Kimi requires benchmark proof)
    - fallback chain when primary unavailable
    - audit-visible decision record

    PA/front-door: always routes to GPT/OpenAI stable models.
    Ollama/local: only when all cloud providers fail or explicit offline mode.
    Kimi: only when benchmark_status == ACCEPTED.
    Security/billing/IAM/deploy/final_review: Anthropic Claude only.
    """

    def __init__(self, catalog: Optional[ProviderCatalog9K] = None) -> None:
        self._catalog = catalog or get_provider_catalog()
        self._declarations = get_role_declarations()

    def _get_declaration(self, role_id: str) -> RoleCapabilityDeclaration:
        return self._declarations.get(role_id, self._build_default_declaration(role_id))

    def _build_default_declaration(self, role_id: str) -> RoleCapabilityDeclaration:
        """Default declaration for unknown roles — inherit dynamic routing policy.

        PA/front-door roles (jarvis_pa, cos_gm) get a stable 1-3 GPT/OpenAI chain.
        All other roles get an EMPTY fallback_chain so routing comes entirely from
        score_candidates() across the full catalog at runtime.

        This is the Plan 9K future-proof rule: any new role added later is
        automatically eligible to use the full catalog without hardcoding models.
        """
        from openjarvis.plan9.inheritance_policy import get_default_policy
        policy = get_default_policy()
        is_pa = role_id in ("jarvis_pa", "cos_gm")
        return policy.build_default_declaration(role_id, role_type="unknown", is_pa=is_pa)

    def select(
        self,
        role_id: str,
        task_description: str = "",
        task_classification: str = "normal",
        force_fallback: bool = False,
        override_reason: str = "",
    ) -> RoutingDecision9K:
        """Select the best model for a role/task. Returns audit-visible decision."""
        decl = self._get_declaration(role_id)
        kimi_benchmarked = self._catalog.kimi_benchmarked()

        tried: List[str] = []
        fallback_reason: Optional[str] = None
        escalation_reason: Optional[str] = None
        why_cheaper_rejected = ""

        candidate_models = self._build_candidate_list(decl, kimi_benchmarked, force_fallback)

        for model_id in candidate_models:
            model = self._catalog.get_model(model_id)
            if model is None:
                tried.append(f"{model_id}:not_in_catalog")
                continue
            if not model.is_available:
                tried.append(f"{model_id}:unavailable")
                fallback_reason = f"{model_id} is marked unavailable; trying next"
                continue

            # Check forbidden classes
            provider_id = model.provider_id
            if any(fc in [provider_id, "offline_fallback"] and model.is_offline_fallback
                   for fc in decl.forbidden_provider_classes):
                tried.append(f"{model_id}:forbidden_offline")
                why_cheaper_rejected += f" | {model_id} rejected: offline_fallback forbidden"
                continue
            if provider_id in decl.forbidden_provider_classes:
                tried.append(f"{model_id}:forbidden_provider({provider_id})")
                why_cheaper_rejected += f" | {model_id} rejected: provider {provider_id!r} forbidden"
                continue

            # Check Kimi benchmark gate
            if model.is_kimi and not kimi_benchmarked:
                tried.append(f"{model_id}:kimi_not_benchmarked")
                why_cheaper_rejected += f" | {model_id} rejected: Kimi requires benchmark proof (not yet accepted)"
                continue

            # Check offline fallback restriction (not for force_fallback)
            if model.is_offline_fallback and not force_fallback:
                tried.append(f"{model_id}:offline_fallback_not_active")
                why_cheaper_rejected += f" | {model_id} rejected: offline_fallback only allowed in fallback mode"
                continue

            # Check capability requirements
            missing = [
                t for t in decl.required_capabilities
                if not model.has_capability(t)
            ]
            if missing:
                tried.append(f"{model_id}:missing_caps({[t.value for t in missing]})")
                why_cheaper_rejected += f" | {model_id} rejected: missing required caps {[t.value for t in missing]}"
                continue

            # Passed all checks — select this model
            route_reason = self._build_route_reason(
                model, decl, tried, kimi_benchmarked, force_fallback,
                override_reason=override_reason,
            )

            return RoutingDecision9K(
                role_id=role_id,
                task_description=task_description,
                task_classification=task_classification,
                required_capabilities=[t.value for t in decl.required_capabilities],
                chosen_provider=model.provider_id,
                chosen_model_id=model.model_id,
                route_reason=route_reason,
                why_cheaper_rejected=why_cheaper_rejected.strip(" |"),
                fallback_reason=fallback_reason,
                escalation_reason=escalation_reason,
                estimated_cost_class=self._estimate_cost_class(model),
                risk_level=decl.risk_threshold.value,
                benchmark_required=bool(decl.benchmark_required_for),
                kimi_eligible=kimi_benchmarked,
                offline_fallback_active=force_fallback,
            )

        # No model found in normal chain — try offline fallback last resort
        if not force_fallback:
            fallback_result = self.select(
                role_id=role_id,
                task_description=task_description,
                task_classification=task_classification,
                force_fallback=True,
                override_reason="All cloud providers exhausted; offline fallback activated",
            )
            fallback_result.fallback_reason = (
                f"All cloud models exhausted (tried: {tried[:5]}). "
                "Offline fallback activated."
            )
            fallback_result.escalation_reason = "provider_outage_or_quota_failure"
            return fallback_result

        # Absolute last resort — should never reach here in production
        return RoutingDecision9K(
            role_id=role_id,
            task_description=task_description,
            task_classification=task_classification,
            required_capabilities=[t.value for t in decl.required_capabilities],
            chosen_provider="openai",
            chosen_model_id="openai/gpt-4o-mini",
            route_reason="LAST_RESORT: all providers and fallbacks exhausted",
            why_cheaper_rejected=why_cheaper_rejected,
            fallback_reason="all_providers_exhausted",
            escalation_reason="all_providers_exhausted",
            estimated_cost_class="cheap",
            risk_level=decl.risk_threshold.value,
            benchmark_required=False,
            kimi_eligible=False,
            offline_fallback_active=True,
        )

    def _build_candidate_list(
        self,
        decl: RoleCapabilityDeclaration,
        kimi_benchmarked: bool,
        force_fallback: bool,
    ) -> List[str]:
        """Build ordered list of model candidates for dynamic selection.

        Order:
          1. Local/offline fallback models (only when force_fallback=True)
          2. Role's declared priority hints (fallback_chain) — curator's best choices
          3. Dynamic expansion: ALL other eligible catalog models scored by capability,
             cost, latency, risk — selected from the FULL catalog, not a static list
          4. Escalation model (last resort)

        This means routing is NOT limited to the declared fallback_chain. If a new
        provider/model enters the catalog with the right capabilities, it becomes
        automatically eligible — no code change required.
        """
        seen: set = set()
        candidates: List[str] = []

        def _add(mid: str) -> None:
            if mid and mid not in seen:
                seen.add(mid)
                candidates.append(mid)

        if force_fallback:
            for m in self._catalog.all_models:
                if m.is_offline_fallback:
                    _add(m.model_id)

        # Priority hints (curator-declared order, tried first)
        for model_id in decl.fallback_chain:
            _add(model_id)

        # Dynamic expansion: full catalog scoring
        # This is the key Plan 9K requirement: non-PA roles are NOT fixed to one model.
        dynamic = self._catalog.score_candidates(
            required_caps=decl.required_capabilities,
            preferred_caps=decl.preferred_capabilities,
            forbidden_providers=decl.forbidden_provider_classes,
            risk_threshold=decl.risk_threshold.value,
            cost_ceiling=decl.cost_ceiling,
            exclude_model_ids=list(seen),
            include_fallback=force_fallback,
        )
        for model_id in dynamic:
            _add(model_id)

        # Escalation model always available as final backstop
        if decl.escalation_model:
            _add(decl.escalation_model)

        return candidates

    def _build_route_reason(
        self,
        model: ModelEntry9K,
        decl: RoleCapabilityDeclaration,
        tried: List[str],
        kimi_benchmarked: bool,
        force_fallback: bool,
        override_reason: str = "",
    ) -> str:
        parts = [
            f"role={decl.role_id}",
            f"provider={model.provider_id}",
            f"model={model.model_id}",
            f"required_caps={[t.value for t in decl.required_capabilities]}",
        ]
        if tried:
            parts.append(f"tried_before={tried[:3]}")
        if not kimi_benchmarked:
            parts.append("kimi_not_eligible(benchmark_required)")
        if force_fallback:
            parts.append("offline_fallback_mode=True")
        if override_reason:
            parts.append(f"override={override_reason!r}")
        if model.is_kimi:
            parts.append("kimi_eligible=True(benchmark_accepted)")
        cap_match = [t.value for t in decl.preferred_capabilities if model.has_capability(t)]
        if cap_match:
            parts.append(f"preferred_caps_matched={cap_match}")
        return "; ".join(parts)

    def _estimate_cost_class(self, model: ModelEntry9K) -> str:
        if model.is_offline_fallback:
            return "free"
        cost = model.input_cost_per_mtok
        if cost == 0.0:
            return "free"
        if cost <= 0.30:
            return "cheap"
        if cost <= 3.00:
            return "medium"
        return "high"

    def explain(
        self,
        role_id: str,
        task_description: str = "",
        task_classification: str = "normal",
        force_fallback: bool = False,
    ) -> Dict:
        """Explain why a model would be selected for a role/task."""
        decision = self.select(
            role_id, task_description, task_classification,
            force_fallback=force_fallback,
        )
        decl = self._get_declaration(role_id)
        return {
            "decision": decision.to_dict(),
            "role_declaration": decl.to_dict(),
            "catalog_model": (
                self._catalog.get_model(decision.chosen_model_id).to_dict()
                if self._catalog.get_model(decision.chosen_model_id)
                else None
            ),
        }

    def routing_status(self) -> Dict:
        """Return overall routing system status."""
        catalog = self._catalog
        decls = self._declarations
        summary = catalog.catalog_summary()
        return {
            "provider_count": catalog.provider_count(),
            "model_count": catalog.model_count(),
            "non_fallback_model_count": len(catalog.non_fallback_models()),
            "kimi_model_count": len(catalog.kimi_models()),
            "kimi_benchmarked": catalog.kimi_benchmarked(),
            "role_declaration_count": len(decls),
            "pa_front_door_model": "openai/gpt-4o",
            "pa_stable_models": PA_STABLE_MODELS,
            "catalog_summary": summary,
            "dynamic_selection": (
                "Router scores ALL eligible catalog models per role. "
                "fallback_chain provides priority ordering hints; "
                "dynamic expansion finds additional eligible models from full catalog."
            ),
            "fallback_policy": (
                "Ollama/local models are fallback-only (provider_outage | quota_failure | offline | debug_override). "
                "Kimi requires benchmark acceptance. PA uses GPT/OpenAI stable route."
            ),
        }


# Singleton
_ROUTER: Optional[SpecializedRouter] = None


def get_specialized_router() -> SpecializedRouter:
    global _ROUTER
    if _ROUTER is None:
        _ROUTER = SpecializedRouter()
    return _ROUTER


__all__ = [
    "RiskThreshold",
    "RoleCapabilityDeclaration",
    "RoutingDecision9K",
    "SpecializedRouter",
    "get_role_declarations",
    "get_specialized_router",
]
