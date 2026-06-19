"""Chief of Staff (COS) Skill — callable runtime orchestration layer.

The COS sits between Jarvis and the GM. Responsibilities:
  1. prioritization — rank incoming requests by urgency, cost, impact
  2. routing — decide which manager handles each task
  3. manager selection — choose from roster based on capability match
  4. parallel/sequential decision — decide execution order
  5. blocker escalation — surface blockers to Jarvis, not silently absorb them
  6. cost/risk balancing — flag expensive or risky tasks before dispatch
  7. verifier assignment — determine when verifier gate is required
  8. no-hidden-gap policy enforcement — never silently defer required work
  9. handoff creation — structured handoff records for task delegation
  10. status reporting — callable status at any point in pipeline

The COS is callable in the runtime flow, not just documented.

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# COS enums
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    CRITICAL = "CRITICAL"    # immediate execution, blocks all else
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    DEFERRED = "DEFERRED"


class ExecutionMode(str, Enum):
    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    SINGLE = "single"


class EscalationReason(str, Enum):
    BLOCKER = "BLOCKER"
    COST_THRESHOLD = "COST_THRESHOLD"
    RISK_THRESHOLD = "RISK_THRESHOLD"
    MISSING_CAPABILITY = "MISSING_CAPABILITY"
    POLICY_VIOLATION = "POLICY_VIOLATION"


# ---------------------------------------------------------------------------
# COS data models
# ---------------------------------------------------------------------------

@dataclass
class RoutingDecision:
    request_id: str
    task_description: str
    selected_manager: str
    priority: Priority
    execution_mode: ExecutionMode
    requires_verifier: bool
    estimated_cost_class: str   # "low" | "medium" | "high"
    risk_flags: List[str]
    blockers: List[str]
    rationale: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "task_description": self.task_description,
            "selected_manager": self.selected_manager,
            "priority": self.priority.value,
            "execution_mode": self.execution_mode.value,
            "requires_verifier": self.requires_verifier,
            "estimated_cost_class": self.estimated_cost_class,
            "risk_flags": self.risk_flags,
            "blockers": self.blockers,
            "rationale": self.rationale,
            "created_at": self.created_at,
        }


@dataclass
class Handoff:
    handoff_id: str
    from_role: str
    to_role: str
    task_id: str
    task_description: str
    context_summary: str
    artifacts: List[str]
    blockers: List[str]
    status: str = "PENDING"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "handoff_id": self.handoff_id,
            "from_role": self.from_role,
            "to_role": self.to_role,
            "task_id": self.task_id,
            "task_description": self.task_description,
            "context_summary": self.context_summary,
            "artifacts": self.artifacts,
            "blockers": self.blockers,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass
class Escalation:
    escalation_id: str
    reason: EscalationReason
    task_id: str
    details: str
    escalated_to: str = "jarvis"
    resolved: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "escalation_id": self.escalation_id,
            "reason": self.reason.value,
            "task_id": self.task_id,
            "details": self.details,
            "escalated_to": self.escalated_to,
            "resolved": self.resolved,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Manager capability index
# ---------------------------------------------------------------------------

MANAGER_CAPABILITIES: Dict[str, List[str]] = {
    "manager-coding": [
        "code", "test", "build", "lint", "repo", "git", "refactor",
        "debug", "compile", "typing", "sprint", "implementation",
    ],
    "manager-research": [
        "research", "search", "web", "scrape", "summarize", "compare",
        "analyze", "document", "report", "wave",
    ],
    "manager-memory": [
        "memory", "recall", "context", "obsidian", "cache", "session",
        "continuity", "state", "snapshot",
    ],
    "manager-connector": [
        "slack", "email", "gmail", "calendar", "drive", "github",
        "notion", "integration", "sync", "webhook",
    ],
    "manager-ops-safety": [
        "safety", "security", "secret", "sentinel", "audit", "policy",
        "compliance", "ops", "monitor", "alert",
    ],
}


# ---------------------------------------------------------------------------
# COS Skill
# ---------------------------------------------------------------------------

class COSSkill:
    """Chief of Staff skill — callable in pipeline.

    Call COS.route(task) to get a RoutingDecision.
    Call COS.create_handoff(...) to create a structured handoff.
    Call COS.escalate(...) to escalate a blocker to Jarvis.
    Call COS.status() for current pipeline status.
    """

    EXPENSIVE_COST_KEYWORDS = ["deploy", "production", "stripe", "billing", "delete", "destroy"]
    HIGH_RISK_KEYWORDS = ["secret", "credential", "password", "api_key", "token"]
    VERIFIER_REQUIRED_KEYWORDS = [
        "release", "ship", "certified", "accept", "complete", "no-gap",
        "deploy", "publish",
    ]

    def __init__(self) -> None:
        self._routing_history: List[RoutingDecision] = []
        self._handoffs: List[Handoff] = []
        self._escalations: List[Escalation] = []
        self._blockers: List[str] = []

    # --- 1. Prioritization ---
    def prioritize(self, task_description: str) -> Priority:
        desc = task_description.lower()
        if any(k in desc for k in ["critical", "urgent", "block", "broken", "down"]):
            return Priority.CRITICAL
        if any(k in desc for k in ["release", "ship", "deploy", "security"]):
            return Priority.HIGH
        if any(k in desc for k in ["fix", "bug", "error", "fail"]):
            return Priority.HIGH
        if any(k in desc for k in ["later", "backlog", "optional", "low"]):
            return Priority.LOW
        return Priority.NORMAL

    # --- 2 & 3. Routing / Manager selection ---
    def select_manager(self, task_description: str) -> str:
        desc = task_description.lower()
        best_manager = "manager-coding"   # default
        best_score = 0
        for manager, keywords in MANAGER_CAPABILITIES.items():
            score = sum(1 for kw in keywords if kw in desc)
            if score > best_score:
                best_score = score
                best_manager = manager
        return best_manager

    # --- 4. Parallel/sequential decision ---
    def decide_execution_mode(self, task_count: int, has_dependencies: bool) -> ExecutionMode:
        if task_count == 1:
            return ExecutionMode.SINGLE
        if has_dependencies:
            return ExecutionMode.SEQUENTIAL
        return ExecutionMode.PARALLEL

    # --- 5. Blocker escalation ---
    def escalate_blocker(self, task_id: str, details: str) -> Escalation:
        esc = Escalation(
            escalation_id=str(uuid.uuid4())[:8],
            reason=EscalationReason.BLOCKER,
            task_id=task_id,
            details=details,
        )
        self._escalations.append(esc)
        self._blockers.append(f"[{task_id}] {details}")
        return esc

    # --- 6. Cost/risk balancing ---
    def assess_risk(self, task_description: str) -> Dict[str, Any]:
        desc = task_description.lower()
        expensive = any(k in desc for k in self.EXPENSIVE_COST_KEYWORDS)
        high_risk = any(k in desc for k in self.HIGH_RISK_KEYWORDS)
        risk_flags = []
        if expensive:
            risk_flags.append("EXPENSIVE_ACTION_DETECTED")
        if high_risk:
            risk_flags.append("SENSITIVE_CREDENTIAL_KEYWORD_DETECTED")
        return {
            "estimated_cost_class": "high" if expensive else "medium" if high_risk else "low",
            "risk_flags": risk_flags,
        }

    # --- 7. Verifier assignment ---
    def requires_verifier(self, task_description: str) -> bool:
        desc = task_description.lower()
        return any(k in desc for k in self.VERIFIER_REQUIRED_KEYWORDS)

    # --- 8. No-hidden-gap enforcement ---
    def enforce_no_hidden_gap(self, claimed_complete: List[str], actual_blockers: List[str]) -> List[str]:
        """Return list of hidden gaps where completion was claimed but blockers exist."""
        hidden_gaps = []
        for claim in claimed_complete:
            for blocker in actual_blockers:
                if any(word in blocker.lower() for word in claim.lower().split()):
                    hidden_gaps.append(
                        f"HIDDEN_GAP: '{claim}' claimed complete but blocker exists: '{blocker}'"
                    )
        return hidden_gaps

    # --- Main: route() ---
    def route(
        self,
        task_description: str,
        task_count: int = 1,
        has_dependencies: bool = False,
        claimed_complete: Optional[List[str]] = None,
        actual_blockers: Optional[List[str]] = None,
    ) -> RoutingDecision:
        """Route a task. Returns a RoutingDecision."""
        request_id = str(uuid.uuid4())[:8]
        manager = self.select_manager(task_description)
        priority = self.prioritize(task_description)
        mode = self.decide_execution_mode(task_count, has_dependencies)
        needs_verifier = self.requires_verifier(task_description)
        risk = self.assess_risk(task_description)

        blockers = []
        if actual_blockers:
            blockers.extend(actual_blockers)

        # Enforce no-hidden-gap
        hidden_gaps = []
        if claimed_complete and actual_blockers:
            hidden_gaps = self.enforce_no_hidden_gap(claimed_complete, actual_blockers)
            if hidden_gaps:
                blockers.extend(hidden_gaps)
                esc = Escalation(
                    escalation_id=str(uuid.uuid4())[:8],
                    reason=EscalationReason.POLICY_VIOLATION,
                    task_id=request_id,
                    details="; ".join(hidden_gaps),
                )
                self._escalations.append(esc)

        decision = RoutingDecision(
            request_id=request_id,
            task_description=task_description,
            selected_manager=manager,
            priority=priority,
            execution_mode=mode,
            requires_verifier=needs_verifier,
            estimated_cost_class=risk["estimated_cost_class"],
            risk_flags=risk["risk_flags"],
            blockers=blockers,
            rationale=(
                f"Manager '{manager}' selected by keyword match. "
                f"Priority: {priority.value}. Mode: {mode.value}. "
                f"Verifier: {'required' if needs_verifier else 'not required'}."
            ),
        )
        self._routing_history.append(decision)
        return decision

    # --- 9. Handoff creation ---
    def create_handoff(
        self,
        from_role: str,
        to_role: str,
        task_id: str,
        task_description: str,
        context_summary: str,
        artifacts: Optional[List[str]] = None,
        blockers: Optional[List[str]] = None,
    ) -> Handoff:
        handoff = Handoff(
            handoff_id=str(uuid.uuid4())[:8],
            from_role=from_role,
            to_role=to_role,
            task_id=task_id,
            task_description=task_description,
            context_summary=context_summary,
            artifacts=artifacts or [],
            blockers=blockers or [],
        )
        self._handoffs.append(handoff)
        return handoff

    # --- 10. Status reporting ---
    def status(self) -> Dict[str, Any]:
        return {
            "routing_history_count": len(self._routing_history),
            "handoff_count": len(self._handoffs),
            "escalation_count": len(self._escalations),
            "active_blockers": self._blockers,
            "recent_routing": (
                self._routing_history[-1].to_dict()
                if self._routing_history else None
            ),
            "recent_escalations": [e.to_dict() for e in self._escalations[-3:]],
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_COS: Optional[COSSkill] = None


def get_cos_skill() -> COSSkill:
    global _COS
    if _COS is None:
        _COS = COSSkill()
    return _COS


__all__ = [
    "Priority",
    "ExecutionMode",
    "EscalationReason",
    "RoutingDecision",
    "Handoff",
    "Escalation",
    "COSSkill",
    "get_cos_skill",
]
