"""Jarvis Universal Front Door.

Architecture:
    Bryan → JarvisFrontDoor → CosGmOrchestrator → managers/workers → response

Design rules (non-negotiable):
  - NOT OMNIX-only. Any project, personal task, or non-project request is valid.
  - OMNIX is one optional FrontDoorAdapter, not the default or root.
  - project_context is always optional; orchestration proceeds without it.
  - Structured FrontDoorResult only — no raw chain-of-thought.
  - All dangerous actions remain blocked (no auto-push, auto-merge, production deploy).
  - US13 voice remains HOLD/UNSAFE/PARKED — not activated here.
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openjarvis.orchestrator.contracts import (
    ProjectContext,
    TaskRoutingRequest,
    RISK_LOW,
    COMPLEXITY_SIMPLE,
    LATENCY_NORMAL,
)


# ---------------------------------------------------------------------------
# UniversalTaskRequest — the single input type for any Bryan request
# ---------------------------------------------------------------------------

@dataclass
class UniversalTaskRequest:
    """A universal request from Bryan to Jarvis.

    Valid for any context:
      - OMNIX coding work
      - OpenJarvis self-improvement
      - Personal tasks
      - Research tasks
      - Automation workflows
      - Business ideas
      - Operations tasks
      - Any future project

    None of these require OMNIX-specific fields.
    project_context is always optional.
    """
    request_id: str
    user_input: str
    intent: str
    project_context: Optional[ProjectContext] = None
    risk_level: str = RISK_LOW
    complexity_level: str = COMPLEXITY_SIMPLE
    domains_required: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    validation_required: bool = True
    context_budget: int = 8000
    cost_budget: float = 0.10
    latency_requirement: str = LATENCY_NORMAL
    autonomy_profile: str = "safe_autopilot"
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        user_input: str,
        intent: str,
        project_context: Optional[ProjectContext] = None,
        risk_level: str = RISK_LOW,
        complexity_level: str = COMPLEXITY_SIMPLE,
        domains_required: Optional[List[str]] = None,
        required_skills: Optional[List[str]] = None,
        required_tools: Optional[List[str]] = None,
        validation_required: bool = True,
        context_budget: int = 8000,
        cost_budget: float = 0.10,
        latency_requirement: str = LATENCY_NORMAL,
        autonomy_profile: str = "safe_autopilot",
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "UniversalTaskRequest":
        """Create a new UniversalTaskRequest. project_context is always optional."""
        return cls(
            request_id=uuid.uuid4().hex,
            user_input=user_input,
            intent=intent,
            project_context=project_context,
            risk_level=risk_level,
            complexity_level=complexity_level,
            domains_required=domains_required or [],
            required_skills=required_skills or [],
            required_tools=required_tools or [],
            validation_required=validation_required,
            context_budget=context_budget,
            cost_budget=cost_budget,
            latency_requirement=latency_requirement,
            autonomy_profile=autonomy_profile,
            session_id=session_id,
            metadata=metadata or {},
        )

    def to_task_routing_request(self) -> TaskRoutingRequest:
        """Convert to TaskRoutingRequest for the activation planner."""
        return TaskRoutingRequest.create(
            user_request_summary=self.user_input,
            intent=self.intent,
            risk_level=self.risk_level,
            complexity_level=self.complexity_level,
            domains_required=self.domains_required,
            required_skills=self.required_skills,
            required_tools=self.required_tools,
            validation_required=self.validation_required,
            context_budget=self.context_budget,
            cost_budget=self.cost_budget,
            latency_requirement=self.latency_requirement,
            autonomy_profile=self.autonomy_profile,
            session_id=self.session_id,
            project_context=self.project_context,
            metadata=self.metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_input": self.user_input,
            "intent": self.intent,
            "project_context": self.project_context.to_dict() if self.project_context else None,
            "risk_level": self.risk_level,
            "complexity_level": self.complexity_level,
            "domains_required": self.domains_required,
            "required_skills": self.required_skills,
            "required_tools": self.required_tools,
            "validation_required": self.validation_required,
            "context_budget": self.context_budget,
            "cost_budget": self.cost_budget,
            "latency_requirement": self.latency_requirement,
            "autonomy_profile": self.autonomy_profile,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# FrontDoorResult — unified structured result
# ---------------------------------------------------------------------------

@dataclass
class FrontDoorResult:
    """Unified structured result from the Jarvis front door.

    No raw chain-of-thought. Only structured decision fields.
    Dangerous actions are always blocked and reported explicitly.
    """
    result_id: str
    request_id: str
    status: str
    summary: str
    activation_plan_id: Optional[str] = None
    selected_managers: List[str] = field(default_factory=list)
    selected_workers: List[str] = field(default_factory=list)
    structured_decision_record_id: Optional[str] = None
    project_context: Optional[ProjectContext] = None
    model_provider_gaps: List[Dict[str, Any]] = field(default_factory=list)
    blocked_actions: List[str] = field(default_factory=list)
    nus_learning_tags: List[str] = field(default_factory=list)
    elapsed_ms: float = 0.0
    no_raw_chain_of_thought: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        request_id: str,
        status: str,
        summary: str,
        activation_plan_id: Optional[str] = None,
        selected_managers: Optional[List[str]] = None,
        selected_workers: Optional[List[str]] = None,
        structured_decision_record_id: Optional[str] = None,
        project_context: Optional[ProjectContext] = None,
        model_provider_gaps: Optional[List[Dict[str, Any]]] = None,
        blocked_actions: Optional[List[str]] = None,
        nus_learning_tags: Optional[List[str]] = None,
        elapsed_ms: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "FrontDoorResult":
        return cls(
            result_id=uuid.uuid4().hex[:12],
            request_id=request_id,
            status=status,
            summary=summary,
            activation_plan_id=activation_plan_id,
            selected_managers=selected_managers or [],
            selected_workers=selected_workers or [],
            structured_decision_record_id=structured_decision_record_id,
            project_context=project_context,
            model_provider_gaps=model_provider_gaps or [],
            blocked_actions=blocked_actions or [],
            nus_learning_tags=nus_learning_tags or [],
            elapsed_ms=elapsed_ms,
            metadata=metadata or {},
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "request_id": self.request_id,
            "status": self.status,
            "summary": self.summary,
            "activation_plan_id": self.activation_plan_id,
            "selected_managers": self.selected_managers,
            "selected_workers": self.selected_workers,
            "structured_decision_record_id": self.structured_decision_record_id,
            "project_context": self.project_context.to_dict() if self.project_context else None,
            "model_provider_gaps": self.model_provider_gaps,
            "blocked_actions": self.blocked_actions,
            "nus_learning_tags": self.nus_learning_tags,
            "elapsed_ms": self.elapsed_ms,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# FrontDoorAdapter — ABC for project-specific adapters
# ---------------------------------------------------------------------------

class FrontDoorAdapter(ABC):
    """Abstract base for project-specific front door adapters.

    OMNIX plugs in as an OmnixFrontDoorAdapter.
    Future projects (OpenJarvis self-improvement, personal, research) plug in here.
    The JarvisFrontDoor always works without any adapter — adapters are optional enrichment.
    """

    @property
    @abstractmethod
    def adapter_id(self) -> str:
        """Unique adapter identifier (e.g. 'omnix', 'openjarvis')."""

    @abstractmethod
    def can_handle(self, request: UniversalTaskRequest) -> bool:
        """Return True if this adapter applies to the given request."""

    def enrich(self, request: UniversalTaskRequest) -> UniversalTaskRequest:
        """Optionally enrich the request before orchestration. Default: pass-through."""
        return request

    def post_process(
        self,
        request: UniversalTaskRequest,
        result: FrontDoorResult,
    ) -> FrontDoorResult:
        """Optionally post-process the result. Default: pass-through."""
        return result


# ---------------------------------------------------------------------------
# JarvisFrontDoor — universal entry point
# ---------------------------------------------------------------------------

class JarvisFrontDoor:
    """Universal entry point for all Bryan requests.

    Routes any request — OMNIX, OpenJarvis, personal, research, automation,
    or any future project — through the COS/GM orchestration layer.

    No OMNIX hardcoding. Adapters are optional enrichment layers.
    """

    # Always-blocked actions regardless of request/project
    _ALWAYS_BLOCKED = frozenset({
        "auto_push",
        "auto_merge",
        "production_deploy",
        "external_send",
        "secret_access",
        "bypass_governance",
        "bypass_safety_gate",
        "us13_voice",
    })

    def __init__(self, adapters: Optional[List[FrontDoorAdapter]] = None) -> None:
        self._adapters: List[FrontDoorAdapter] = adapters or []

    def register_adapter(self, adapter: FrontDoorAdapter) -> None:
        """Register a project-specific adapter. OMNIX, OpenJarvis, etc."""
        for existing in self._adapters:
            if existing.adapter_id == adapter.adapter_id:
                return  # already registered
        self._adapters.append(adapter)

    def handle(self, request: UniversalTaskRequest) -> FrontDoorResult:
        """Process any Bryan request through the universal front door.

        Flow:
          1. Start orchestrator trace (trace_id assigned here)
          2. Emit FRONT_DOOR trace event
          3. Check always-blocked actions
          4. Find matching adapter (if any) and enrich request
          5. Route through CosGmOrchestrator (with trace_id propagated)
          6. Emit ROUTING trace event
          7. Return structured FrontDoorResult
        """
        start = time.time()

        # 1. Start runtime trace for this request
        trace_id: Optional[str] = None
        try:
            from openjarvis.orchestrator.runtime_trace import (
                start_trace, EVENT_FRONT_DOOR, EVENT_ROUTING, EVENT_BLOCKER,
            )
            trace = start_trace(request.request_id)
            trace_id = trace.trace_id
            trace.add_event(
                EVENT_FRONT_DOOR,
                component="jarvis_front_door",
                summary=f"Front door received request intent='{request.intent}'",
                payload={
                    "request_id": request.request_id,
                    "intent": request.intent,
                    "has_project_context": request.project_context is not None,
                    "project_id": (
                        request.project_context.project_id
                        if request.project_context else None
                    ),
                    "adapters_registered": len(self._adapters),
                },
            )
        except Exception:
            trace_id = None

        # Propagate trace_id into request metadata
        if trace_id:
            request.metadata["trace_id"] = trace_id

        # 2. Check always-blocked
        blocked = [a for a in request.metadata.get("requested_actions", [])
                   if a in self._ALWAYS_BLOCKED]
        if blocked:
            try:
                from openjarvis.orchestrator.runtime_trace import (
                    get_trace, EVENT_BLOCKER, EVENT_FINAL_RESPONSE,
                )
                t = get_trace(trace_id) if trace_id else None
                if t:
                    t.add_event(
                        EVENT_BLOCKER,
                        component="jarvis_front_door",
                        summary=f"Front door blocked: {blocked}",
                        payload={"blocked_actions": blocked},
                    )
                    t.add_event(
                        EVENT_FINAL_RESPONSE,
                        component="jarvis_front_door",
                        summary="Response: blocked",
                        payload={"status": "blocked"},
                    )
            except Exception:
                pass
            return FrontDoorResult.create(
                request_id=request.request_id,
                status="blocked",
                summary=f"Request blocked: {blocked} are permanently blocked.",
                blocked_actions=blocked,
                project_context=request.project_context,
                elapsed_ms=(time.time() - start) * 1000,
                metadata={"trace_id": trace_id},
            )

        # 3. Adapter enrichment (optional — request works without adapters)
        enriched = request
        matching_adapter: Optional[FrontDoorAdapter] = None
        for adapter in self._adapters:
            if adapter.can_handle(request):
                enriched = adapter.enrich(request)
                matching_adapter = adapter
                break

        # 4. Emit routing event
        try:
            from openjarvis.orchestrator.runtime_trace import get_trace, EVENT_ROUTING
            t = get_trace(trace_id) if trace_id else None
            if t:
                t.add_event(
                    EVENT_ROUTING,
                    component="jarvis_front_door",
                    summary=f"Routing to COS/GM (adapter={matching_adapter.adapter_id if matching_adapter else 'none'})",
                    payload={"adapter": matching_adapter.adapter_id if matching_adapter else None},
                )
        except Exception:
            pass

        # 5. Route through CosGmOrchestrator
        from openjarvis.orchestrator.cos_gm import CosGmOrchestrator, get_cos_gm_orchestrator
        orchestrator = get_cos_gm_orchestrator()
        result = orchestrator.handle(enriched)

        # 6. Post-process via adapter (optional)
        if matching_adapter is not None:
            result = matching_adapter.post_process(enriched, result)

        result.elapsed_ms = (time.time() - start) * 1000
        if trace_id and "trace_id" not in result.metadata:
            result.metadata["trace_id"] = trace_id
        return result


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_front_door: Optional[JarvisFrontDoor] = None


def get_jarvis_front_door() -> JarvisFrontDoor:
    """Return the module-level JarvisFrontDoor singleton."""
    global _front_door
    if _front_door is None:
        _front_door = JarvisFrontDoor()
    return _front_door
