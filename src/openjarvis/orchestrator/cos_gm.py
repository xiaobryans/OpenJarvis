"""COS/GM Orchestrator — Chief of Staff / General Manager layer.

Sits between the Jarvis front door and the domain managers/workers.
Receives a UniversalTaskRequest, classifies intent/risk/complexity,
calls the DynamicActivationPlanner, creates a structured decision record,
attaches governance/validation plan, and returns a FrontDoorResult.

Design rules (non-negotiable):
  - Receives universal Jarvis front-door request; never OMNIX-specific input.
  - project_context is optional — personal tasks and non-project tasks work.
  - No fixed worker-count formulas.
  - Structured decision record always emitted; no raw chain-of-thought.
  - NUS applies: all hierarchy levels emit decision records.
  - Dangerous actions remain permanently blocked.
  - US13 voice remains HOLD/UNSAFE/PARKED — not activated here.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from openjarvis.orchestrator.contracts import (
    ProjectContext,
    TaskRoutingRequest,
    RISK_LOW,
    RISK_HIGH,
    RISK_BLOCKED,
    COMPLEXITY_SIMPLE,
    COMPLEXITY_COMPLEX,
)
from openjarvis.orchestrator.activation import get_activation_planner

logger = logging.getLogger(__name__)

# Permanently blocked actions — COS/GM enforces these before delegating
_ALWAYS_BLOCKED_ACTIONS = frozenset({
    "auto_push",
    "auto_merge",
    "production_deploy",
    "external_send",
    "secret_access",
    "bypass_governance",
    "bypass_safety_gate",
    "us13_voice_activation",
})

_RISK_KEYWORDS = {
    "deploy": RISK_HIGH,
    "production": RISK_HIGH,
    "delete": RISK_HIGH,
    "drop": RISK_HIGH,
    "override": RISK_HIGH,
    "bypass": RISK_BLOCKED,
    "secret": RISK_HIGH,
    "credential": RISK_HIGH,
}

_COMPLEXITY_KEYWORDS_COMPLEX = frozenset({
    "architecture", "migration", "refactor", "multi-file", "cross-system",
    "schema", "upgrade bundle", "integration",
})
_COMPLEXITY_KEYWORDS_MODERATE = frozenset({
    "feature", "fix", "update", "test", "review", "analyze",
})


class CosGmOrchestrator:
    """Chief of Staff / General Manager orchestration layer.

    Receives any UniversalTaskRequest and produces a FrontDoorResult by:
      1. Classifying intent/risk/complexity
      2. Checking always-blocked actions
      3. Calling DynamicActivationPlanner
      4. Creating structured decision record
      5. Attaching governance and validation plan
      6. Returning unified FrontDoorResult
    """

    def handle(self, request: "UniversalTaskRequest") -> "FrontDoorResult":  # type: ignore[name-defined]
        """Route any request through COS/GM to the activation planner."""
        # Import here to avoid circular imports
        from openjarvis.frontdoor.frontdoor import FrontDoorResult, UniversalTaskRequest

        start = time.time()

        # 1. Check always-blocked actions
        requested = request.metadata.get("requested_actions", [])
        blocked = [a for a in requested if a in _ALWAYS_BLOCKED_ACTIONS]
        if blocked:
            return FrontDoorResult.create(
                request_id=request.request_id,
                status="blocked",
                summary=(
                    f"COS/GM blocked request: {blocked} are permanently blocked. "
                    "No production deploy, auto-push, auto-merge, external send, "
                    "secret access, governance bypass, or voice activation."
                ),
                blocked_actions=blocked,
                project_context=request.project_context,
                nus_learning_tags=["cos_gm:blocked_action"],
                elapsed_ms=(time.time() - start) * 1000,
            )

        # 2. Classify intent/risk/complexity from request
        effective_risk, effective_complexity = self._classify(request)

        # 3. Build TaskRoutingRequest
        routing_req = TaskRoutingRequest.create(
            user_request_summary=request.user_input,
            intent=request.intent,
            risk_level=effective_risk,
            complexity_level=effective_complexity,
            domains_required=request.domains_required,
            required_skills=request.required_skills,
            required_tools=request.required_tools,
            validation_required=request.validation_required,
            context_budget=request.context_budget,
            cost_budget=request.cost_budget,
            latency_requirement=request.latency_requirement,
            autonomy_profile=request.autonomy_profile,
            session_id=request.session_id,
            project_context=request.project_context,
            metadata=request.metadata,
        )

        # 4. Activate managers/workers via DynamicActivationPlanner
        planner = get_activation_planner()
        plan = planner.plan(routing_req)

        # 5. Build governance and validation commentary
        project_label = (
            request.project_context.display_name
            if request.project_context
            else "no_project_context"
        )
        model_gap_dicts = [g.to_dict() for g in plan.model_provider_gaps]

        # 6. Build NUS tags including project context
        nus_tags = list(plan.nus_learning_tags) + [
            f"cos_gm:routed",
            f"project:{request.project_context.project_id if request.project_context and request.project_context.project_id else 'none'}",
        ]

        summary = (
            f"COS/GM activated {len(plan.selected_managers)} manager(s) and "
            f"{len(plan.selected_workers)} worker(s) for request '{request.intent}' "
            f"[project={project_label}, risk={effective_risk}, complexity={effective_complexity}]. "
            f"decision_record={plan.structured_decision_record_id}."
        )

        return FrontDoorResult.create(
            request_id=request.request_id,
            status="planned",
            summary=summary,
            activation_plan_id=plan.plan_id,
            selected_managers=plan.selected_managers,
            selected_workers=plan.selected_workers,
            structured_decision_record_id=plan.structured_decision_record_id,
            project_context=request.project_context,
            model_provider_gaps=model_gap_dicts,
            blocked_actions=list(_ALWAYS_BLOCKED_ACTIONS),
            nus_learning_tags=nus_tags,
            elapsed_ms=(time.time() - start) * 1000,
        )

    def _classify(
        self, request: "UniversalTaskRequest"  # type: ignore[name-defined]
    ) -> tuple[str, str]:
        """Classify risk and complexity from request metadata.

        Does not override explicit values from the request — only elevates if
        keywords indicate higher risk/complexity than declared.
        """
        risk = request.risk_level
        complexity = request.complexity_level

        text = (request.user_input + " " + request.intent).lower()

        # Elevate risk if keywords found
        for keyword, keyword_risk in _RISK_KEYWORDS.items():
            if keyword in text:
                if keyword_risk == RISK_BLOCKED:
                    risk = RISK_BLOCKED
                    break
                elif keyword_risk == RISK_HIGH and risk == RISK_LOW:
                    risk = RISK_HIGH

        # Elevate complexity
        if any(kw in text for kw in _COMPLEXITY_KEYWORDS_COMPLEX):
            if complexity == COMPLEXITY_SIMPLE:
                complexity = COMPLEXITY_COMPLEX
        elif any(kw in text for kw in _COMPLEXITY_KEYWORDS_MODERATE):
            if complexity == COMPLEXITY_SIMPLE:
                from openjarvis.orchestrator.contracts import COMPLEXITY_MODERATE
                complexity = COMPLEXITY_MODERATE

        return risk, complexity

    def get_status(self) -> Dict[str, Any]:
        """Return COS/GM status summary."""
        planner = get_activation_planner()
        return {
            "cos_gm_orchestrator": "active",
            "always_blocked_actions": sorted(_ALWAYS_BLOCKED_ACTIONS),
            "activation_planner": planner.get_status() if hasattr(planner, "get_status") else "available",
            "us13_voice": "HOLD/UNSAFE/PARKED",
            "no_raw_chain_of_thought": True,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_orchestrator: Optional[CosGmOrchestrator] = None


def get_cos_gm_orchestrator() -> CosGmOrchestrator:
    """Return the module-level CosGmOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CosGmOrchestrator()
    return _orchestrator
