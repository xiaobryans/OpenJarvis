"""MissionRouter — deterministic skeleton for mission decomposition and routing.

Planning method: keyword_deterministic
No LLM required for this skeleton.  The router uses keyword matching against
the objective string to select specialist agents and estimate task risk.

When a real LLM planning layer is introduced (Mega Sprint 2+), this module
can be replaced while preserving the same Mission/Task/MissionEvent contracts
and the same persistence/event-bus wiring.

Approval policy (non-negotiable, no override):
  - deployment tasks always require approval
  - email tasks always require approval
  - HIGH or CRITICAL risk tasks require approval
  - security_risk tasks always require approval
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from openjarvis.core.events import EventType, get_event_bus
from openjarvis.governance.policies import requires_approval as _gov_requires_approval
from openjarvis.mission.agent_registry import SpecialistRegistry
from openjarvis.mission.models import (
    Mission,
    MissionEvent,
    MissionStatus,
    RiskLevel,
    Task,
    TaskStatus,
)
from openjarvis.mission.store import MissionStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Planning method identifier
# ---------------------------------------------------------------------------

PLANNING_METHOD = "keyword_deterministic"

# ---------------------------------------------------------------------------
# Keyword routing table: (keyword, agent_id, title_template, risk_level)
#
# First match per agent_id wins (deduplication is done by the planner).
# ---------------------------------------------------------------------------

_KEYWORD_RULES: List[Tuple[str, str, str, RiskLevel]] = [
    ("research", "research", "Research: {obj}", RiskLevel.LOW),
    ("investigate", "research", "Investigate: {obj}", RiskLevel.LOW),
    ("find information", "research", "Gather information: {obj}", RiskLevel.LOW),
    ("analyze", "research", "Analyze: {obj}", RiskLevel.LOW),
    ("summarize", "research", "Summarize: {obj}", RiskLevel.LOW),
    ("architect", "architect", "Architecture design: {obj}", RiskLevel.LOW),
    ("system design", "architect", "System design: {obj}", RiskLevel.LOW),
    ("design", "architect", "Design: {obj}", RiskLevel.LOW),
    ("code", "coding", "Implement: {obj}", RiskLevel.MEDIUM),
    ("coding", "coding", "Implement: {obj}", RiskLevel.MEDIUM),
    ("implement", "coding", "Implement: {obj}", RiskLevel.MEDIUM),
    ("fix", "coding", "Fix: {obj}", RiskLevel.MEDIUM),
    ("bug", "coding", "Debug: {obj}", RiskLevel.MEDIUM),
    ("build", "coding", "Build: {obj}", RiskLevel.MEDIUM),
    ("refactor", "coding", "Refactor: {obj}", RiskLevel.MEDIUM),
    ("develop", "coding", "Develop: {obj}", RiskLevel.MEDIUM),
    ("test", "testing_bug", "Test: {obj}", RiskLevel.LOW),
    ("verify", "testing_bug", "Verify: {obj}", RiskLevel.LOW),
    ("validate", "testing_bug", "Validate: {obj}", RiskLevel.LOW),
    ("security", "security_risk", "Security assessment: {obj}", RiskLevel.HIGH),
    ("vulnerability", "security_risk", "Vulnerability scan: {obj}", RiskLevel.HIGH),
    ("risk assessment", "security_risk", "Risk assessment: {obj}", RiskLevel.HIGH),
    ("audit", "security_risk", "Audit: {obj}", RiskLevel.HIGH),
    ("deploy", "deployment", "Deploy: {obj}", RiskLevel.CRITICAL),
    ("release", "deployment", "Release: {obj}", RiskLevel.CRITICAL),
    ("publish", "deployment", "Publish: {obj}", RiskLevel.CRITICAL),
    ("rollout", "deployment", "Rollout: {obj}", RiskLevel.CRITICAL),
    ("qa", "qa", "QA review: {obj}", RiskLevel.LOW),
    ("quality", "qa", "Quality review: {obj}", RiskLevel.LOW),
    ("acceptance", "qa", "Acceptance check: {obj}", RiskLevel.LOW),
    ("document", "docs_report", "Documentation: {obj}", RiskLevel.LOW),
    ("report", "docs_report", "Report: {obj}", RiskLevel.LOW),
    ("changelog", "docs_report", "Changelog: {obj}", RiskLevel.LOW),
    ("handoff", "docs_report", "Handoff notes: {obj}", RiskLevel.LOW),
    ("browser", "browser", "Browser task: {obj}", RiskLevel.MEDIUM),
    ("scrape", "browser", "Scrape: {obj}", RiskLevel.MEDIUM),
    ("navigate", "browser", "Navigate: {obj}", RiskLevel.MEDIUM),
    ("email", "email", "Email: {obj}", RiskLevel.HIGH),
    ("send email", "email", "Send email: {obj}", RiskLevel.HIGH),
    ("reminder", "reminders", "Set reminder: {obj}", RiskLevel.LOW),
    ("schedule", "reminders", "Schedule: {obj}", RiskLevel.LOW),
    ("remind", "reminders", "Reminder: {obj}", RiskLevel.LOW),
]

# Agents that ALWAYS require explicit approval regardless of risk level
_ALWAYS_APPROVAL_AGENTS = frozenset({"deployment", "email", "security_risk"})

# Minimum risk level that requires approval
_RISK_ORDER = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}
_APPROVAL_RISK_THRESHOLD = RiskLevel.HIGH


def _requires_approval(risk: RiskLevel, agent_id: str) -> bool:
    """Delegates to governance policy — single authoritative source for approval rules."""
    return _gov_requires_approval(risk.value, agent_id)


# ---------------------------------------------------------------------------
# MissionPlan result
# ---------------------------------------------------------------------------


@dataclass
class MissionPlan:
    """Returned by MissionRouter.create_mission()."""

    mission: Mission
    tasks: List[Task]
    events: List[MissionEvent]
    planning_method: str = PLANNING_METHOD


# ---------------------------------------------------------------------------
# MissionRouter
# ---------------------------------------------------------------------------


class MissionRouter:
    """Accept an objective → create a Mission + Tasks → assign agents → emit events.

    This is the skeleton implementation.  It does NOT execute tasks or call
    any external service.  No task is ever marked completed by this router.
    """

    def __init__(
        self,
        store: Optional[MissionStore] = None,
        *,
        emit_to_bus: bool = True,
    ) -> None:
        self._store = store or MissionStore()
        self._emit_to_bus = emit_to_bus

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_mission(
        self,
        objective: str,
        *,
        owner: str = "Bryan",
        title: str = "",
    ) -> MissionPlan:
        """Create a Mission, decompose into Tasks, assign agents, emit events.

        Returns a MissionPlan with the persisted Mission, Tasks, and Events.
        No task is marked completed.  High-risk/privileged tasks are marked
        awaiting_approval.
        """
        objective = objective.strip()
        if not objective:
            raise ValueError("objective must not be empty")

        effective_title = title.strip() or objective[:80]

        # 1. Create mission record
        mission = Mission(
            title=effective_title,
            objective=objective,
            owner=owner,
            status=MissionStatus.PLANNING,
        )

        events: List[MissionEvent] = []

        # 2. Emit mission_created
        events.append(
            self._make_event(
                EventType.MISSION_CREATED,
                mission_id=mission.id,
                message=f"Mission created: {effective_title}",
                payload={"objective": objective, "owner": owner},
            )
        )

        # 3. Decompose objective into task specs
        task_specs = self._plan_tasks(objective)
        tasks: List[Task] = []

        for priority_idx, (task_title, agent_id, description, risk) in enumerate(
            task_specs, start=1
        ):
            needs_approval = _requires_approval(risk, agent_id)
            task_status = (
                TaskStatus.AWAITING_APPROVAL if needs_approval else TaskStatus.ASSIGNED
            )

            task = Task(
                mission_id=mission.id,
                title=task_title,
                description=description,
                assigned_agent_id=agent_id,
                status=task_status,
                priority=priority_idx,
                risk_level=risk,
            )
            tasks.append(task)
            mission.linked_task_ids.append(task.id)

            # Emit task_created
            events.append(
                self._make_event(
                    EventType.TASK_CREATED,
                    mission_id=mission.id,
                    task_id=task.id,
                    agent_id=agent_id,
                    message=f"Task created: {task_title}",
                    payload={"risk_level": risk.value, "agent_id": agent_id},
                )
            )

            # Emit task_assigned or task_awaiting_approval
            if needs_approval:
                events.append(
                    self._make_event(
                        EventType.TASK_AWAITING_APPROVAL,
                        mission_id=mission.id,
                        task_id=task.id,
                        agent_id=agent_id,
                        severity="warning",
                        message=(
                            f"Task awaiting approval: {task_title} "
                            f"(risk={risk.value}, agent={agent_id})"
                        ),
                        payload={"requires_approval": True, "risk_level": risk.value},
                    )
                )
            else:
                events.append(
                    self._make_event(
                        EventType.TASK_ASSIGNED,
                        mission_id=mission.id,
                        task_id=task.id,
                        agent_id=agent_id,
                        message=f"Task assigned: {task_title} → {agent_id}",
                        payload={"risk_level": risk.value},
                    )
                )

        # 4. Compute mission-level risk (max of task risks)
        if tasks:
            mission.risk_level = max(tasks, key=lambda t: _RISK_ORDER[t.risk_level]).risk_level

        # 5. Set mission status
        has_approval_needed = any(t.status == TaskStatus.AWAITING_APPROVAL for t in tasks)
        mission.status = (
            MissionStatus.AWAITING_APPROVAL if has_approval_needed else MissionStatus.RUNNING
        )
        mission.summary = (
            f"Decomposed into {len(tasks)} task(s) via {PLANNING_METHOD}. "
            f"{'Some tasks require approval.' if has_approval_needed else 'All tasks assigned.'}"
        )

        # 6. Emit mission_status_changed
        events.append(
            self._make_event(
                EventType.MISSION_STATUS_CHANGED,
                mission_id=mission.id,
                message=f"Mission status → {mission.status.value}",
                payload={
                    "status": mission.status.value,
                    "task_count": len(tasks),
                    "tasks_awaiting_approval": sum(
                        1 for t in tasks if t.status == TaskStatus.AWAITING_APPROVAL
                    ),
                    "planning_method": PLANNING_METHOD,
                },
            )
        )

        # 7. Link event ids
        mission.linked_event_ids = [e.event_id for e in events]
        mission.updated_at = time.time()

        # 8. Persist everything
        self._store.save_mission(mission)
        for task in tasks:
            self._store.save_task(task)
        for event in events:
            self._store.save_event(event)

        logger.info(
            "Mission %s created: %d tasks, status=%s, planning_method=%s",
            mission.id,
            len(tasks),
            mission.status.value,
            PLANNING_METHOD,
        )

        return MissionPlan(mission=mission, tasks=tasks, events=events)

    # ------------------------------------------------------------------
    # Internal planning logic
    # ------------------------------------------------------------------

    def _plan_tasks(
        self, objective: str
    ) -> List[Tuple[str, str, str, RiskLevel]]:
        """Return list of (title, agent_id, description, risk) tuples.

        Uses keyword_deterministic matching.  Deduplicates by agent_id (first
        match wins).  Always includes research as a fallback, architect when
        coding is present, QA when coding is present, and docs_report at end.
        """
        obj_lower = objective.lower()
        obj_short = objective[:60]
        seen_agents: set = set()
        planned: List[Tuple[str, str, str, RiskLevel]] = []

        for keyword, agent_id, title_tpl, risk in _KEYWORD_RULES:
            if keyword in obj_lower and agent_id not in seen_agents:
                spec = SpecialistRegistry.get(agent_id)
                if spec is None:
                    continue
                title = title_tpl.format(obj=obj_short)
                desc = (
                    f"Assigned to {spec.display_name}. "
                    f"Objective: {objective}. "
                    f"Risk level: {risk.value}."
                )
                planned.append((title, agent_id, desc, risk))
                seen_agents.add(agent_id)

        # Fallback: no keyword matched → default to research
        if not planned:
            spec = SpecialistRegistry.get("research")
            if spec:
                planned.append((
                    f"Research: {obj_short}",
                    "research",
                    (
                        f"No specific keywords matched. Defaulting to research "
                        f"for: {objective}"
                    ),
                    RiskLevel.LOW,
                ))
                seen_agents.add("research")

        # Always add architect before coding if coding is planned
        if "coding" in seen_agents and "architect" not in seen_agents:
            spec = SpecialistRegistry.get("architect")
            if spec:
                planned.insert(0, (
                    f"Architecture review: {obj_short}",
                    "architect",
                    f"Review architecture before coding: {objective}",
                    RiskLevel.LOW,
                ))
                seen_agents.add("architect")

        # Always add QA after coding if neither testing_bug nor qa is planned
        if (
            "coding" in seen_agents
            and "testing_bug" not in seen_agents
            and "qa" not in seen_agents
        ):
            spec = SpecialistRegistry.get("qa")
            if spec:
                planned.append((
                    f"QA review: {obj_short}",
                    "qa",
                    f"QA sign-off after implementation: {objective}",
                    RiskLevel.LOW,
                ))
                seen_agents.add("qa")

        # Always add docs_report at the end
        if "docs_report" not in seen_agents:
            spec = SpecialistRegistry.get("docs_report")
            if spec:
                planned.append((
                    f"Document outcomes: {obj_short}",
                    "docs_report",
                    f"Document and report final outcomes: {objective}",
                    RiskLevel.LOW,
                ))

        return planned

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------

    def _make_event(
        self,
        event_type: EventType,
        *,
        mission_id: str,
        task_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        severity: str = "info",
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> MissionEvent:
        evt = MissionEvent(
            mission_id=mission_id,
            task_id=task_id,
            agent_id=agent_id,
            event_type=event_type.value,
            severity=severity,
            message=message,
            payload=payload or {},
        )
        if self._emit_to_bus:
            try:
                bus = get_event_bus()
                bus.publish(
                    event_type,
                    data={
                        "mission_id": mission_id,
                        "task_id": task_id,
                        "agent_id": agent_id,
                        "message": message,
                    },
                )
            except Exception as exc:
                logger.debug("Event bus publish skipped: %s", exc)
        return evt


__all__ = ["MissionPlan", "MissionRouter", "PLANNING_METHOD"]
