"""NUS 1B — Recommendation Registry and Lifecycle.

Provides structured recommendation objects and lifecycle management:
  - Create recommendations from NUS 1A scorecards / failure patterns / signals
  - Classify and validate recommendations
  - Lifecycle: draft → ready/needs_approval/blocked → approved/rejected → executed_dry_run
  - Dry-run safe recommendations (no risky external actions, no code/file mutation)
  - Block dangerous recommendations
  - Persist recommendations across sessions via LearningStore

Hard safety constraints:
  - No real execution of code edits, deploys, sends, secrets, or browser automation
  - Dry-run = no risky external action, no code/file mutation except safe temp state
  - All dangerous actions blocked at classification
  - Medium-risk actions require explicit approval
  - No auto-commit, no deploy, no external sends
  - US13 voice HOLD/UNSAFE/PARKED
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NUS1B_REC_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Approval policy categories
# ---------------------------------------------------------------------------

POLICY_AUTO_LOCAL_READ = "auto_allowed_local_read"
POLICY_AUTO_LOCAL_ANALYSIS = "auto_allowed_local_analysis"
POLICY_AUTO_VALIDATION = "auto_allowed_validation"
POLICY_NEEDS_APPROVAL_FILE_WRITE = "needs_approval_file_write"
POLICY_NEEDS_APPROVAL_EXTERNAL_PROVIDER = "needs_approval_external_provider"
POLICY_NEEDS_APPROVAL_BROWSER = "needs_approval_browser"
POLICY_NEEDS_APPROVAL_SEND = "needs_approval_send"
POLICY_BLOCKED_SECRET_ACCESS = "blocked_secret_access"
POLICY_BLOCKED_SELF_MODIFICATION = "blocked_self_modification"
POLICY_BLOCKED_AUTO_COMMIT = "blocked_auto_commit"
POLICY_BLOCKED_AUTO_PUSH = "blocked_auto_push"
POLICY_BLOCKED_DEPLOY = "blocked_deploy"
POLICY_BLOCKED_SAFETY_POLICY_CHANGE = "blocked_safety_policy_change"

_BLOCKED_POLICIES = frozenset({
    POLICY_BLOCKED_SECRET_ACCESS,
    POLICY_BLOCKED_SELF_MODIFICATION,
    POLICY_BLOCKED_AUTO_COMMIT,
    POLICY_BLOCKED_AUTO_PUSH,
    POLICY_BLOCKED_DEPLOY,
    POLICY_BLOCKED_SAFETY_POLICY_CHANGE,
})

_APPROVAL_POLICIES = frozenset({
    POLICY_NEEDS_APPROVAL_FILE_WRITE,
    POLICY_NEEDS_APPROVAL_EXTERNAL_PROVIDER,
    POLICY_NEEDS_APPROVAL_BROWSER,
    POLICY_NEEDS_APPROVAL_SEND,
})

_AUTO_POLICIES = frozenset({
    POLICY_AUTO_LOCAL_READ,
    POLICY_AUTO_LOCAL_ANALYSIS,
    POLICY_AUTO_VALIDATION,
})

# ---------------------------------------------------------------------------
# Risk / confidence / status constants
# ---------------------------------------------------------------------------

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_CRITICAL = "critical"

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

STATUS_DRAFT = "draft"
STATUS_READY = "ready"
STATUS_NEEDS_APPROVAL = "needs_approval"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_BLOCKED = "blocked"
STATUS_EXECUTED_DRY_RUN = "executed_dry_run"
STATUS_SUPERSEDED = "superseded"

# ---------------------------------------------------------------------------
# Required action types
# ---------------------------------------------------------------------------

ACTION_LOCAL_READ = "local_read"
ACTION_LOCAL_ANALYSIS = "local_analysis"
ACTION_LOCAL_VALIDATION = "local_validation"
ACTION_FILE_WRITE = "file_write"
ACTION_CODE_EDIT = "code_edit"
ACTION_EXTERNAL_PROVIDER_SETUP = "external_provider_setup"
ACTION_BROWSER_AUTOMATION = "browser_automation"
ACTION_EXTERNAL_SEND = "external_send"
ACTION_SECRET_ACCESS = "secret_access"
ACTION_SELF_MODIFICATION = "self_modification"
ACTION_AUTO_COMMIT = "auto_commit"
ACTION_AUTO_PUSH = "auto_push"
ACTION_DEPLOY = "deploy"
ACTION_SAFETY_POLICY_CHANGE = "safety_policy_change"

# Mapping from required_action_type → approval_policy
_ACTION_TO_POLICY: Dict[str, str] = {
    ACTION_LOCAL_READ: POLICY_AUTO_LOCAL_READ,
    ACTION_LOCAL_ANALYSIS: POLICY_AUTO_LOCAL_ANALYSIS,
    ACTION_LOCAL_VALIDATION: POLICY_AUTO_VALIDATION,
    ACTION_FILE_WRITE: POLICY_NEEDS_APPROVAL_FILE_WRITE,
    ACTION_CODE_EDIT: POLICY_BLOCKED_SELF_MODIFICATION,
    ACTION_EXTERNAL_PROVIDER_SETUP: POLICY_NEEDS_APPROVAL_EXTERNAL_PROVIDER,
    ACTION_BROWSER_AUTOMATION: POLICY_NEEDS_APPROVAL_BROWSER,
    ACTION_EXTERNAL_SEND: POLICY_NEEDS_APPROVAL_SEND,
    ACTION_SECRET_ACCESS: POLICY_BLOCKED_SECRET_ACCESS,
    ACTION_SELF_MODIFICATION: POLICY_BLOCKED_SELF_MODIFICATION,
    ACTION_AUTO_COMMIT: POLICY_BLOCKED_AUTO_COMMIT,
    ACTION_AUTO_PUSH: POLICY_BLOCKED_AUTO_PUSH,
    ACTION_DEPLOY: POLICY_BLOCKED_DEPLOY,
    ACTION_SAFETY_POLICY_CHANGE: POLICY_BLOCKED_SAFETY_POLICY_CHANGE,
}


def resolve_approval_policy(required_action_type: str) -> str:
    return _ACTION_TO_POLICY.get(required_action_type, POLICY_NEEDS_APPROVAL_FILE_WRITE)


# ---------------------------------------------------------------------------
# Recommendation dataclass
# ---------------------------------------------------------------------------


@dataclass
class Recommendation:
    """A structured NUS 1B recommendation object."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    source: str = ""
    category: str = ""
    title: str = ""
    summary: str = ""
    rationale: str = ""
    affected_area: str = ""
    risk_level: str = RISK_LOW
    confidence: str = CONFIDENCE_MEDIUM
    expected_benefit: str = ""
    required_action_type: str = ACTION_LOCAL_ANALYSIS
    approval_policy: str = POLICY_AUTO_LOCAL_ANALYSIS
    status: str = STATUS_DRAFT
    evidence: Dict[str, Any] = field(default_factory=dict)
    rollback_plan: str = ""
    validation_plan: str = ""
    related_failure_patterns: List[str] = field(default_factory=list)
    related_scorecard_ids: List[str] = field(default_factory=list)
    rejection_reason: Optional[str] = None
    dry_run_result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "rationale": self.rationale,
            "affected_area": self.affected_area,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "expected_benefit": self.expected_benefit,
            "required_action_type": self.required_action_type,
            "approval_policy": self.approval_policy,
            "status": self.status,
            "evidence": self.evidence,
            "rollback_plan": self.rollback_plan,
            "validation_plan": self.validation_plan,
            "related_failure_patterns": self.related_failure_patterns,
            "related_scorecard_ids": self.related_scorecard_ids,
            "rejection_reason": self.rejection_reason,
            "dry_run_result": self.dry_run_result,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Recommendation":
        return cls(
            id=d.get("id", uuid.uuid4().hex[:16]),
            created_at=d.get("created_at", time.time()),
            updated_at=d.get("updated_at", time.time()),
            source=d.get("source", ""),
            category=d.get("category", ""),
            title=d.get("title", ""),
            summary=d.get("summary", ""),
            rationale=d.get("rationale", ""),
            affected_area=d.get("affected_area", ""),
            risk_level=d.get("risk_level", RISK_LOW),
            confidence=d.get("confidence", CONFIDENCE_MEDIUM),
            expected_benefit=d.get("expected_benefit", ""),
            required_action_type=d.get("required_action_type", ACTION_LOCAL_ANALYSIS),
            approval_policy=d.get("approval_policy", POLICY_AUTO_LOCAL_ANALYSIS),
            status=d.get("status", STATUS_DRAFT),
            evidence=d.get("evidence", {}),
            rollback_plan=d.get("rollback_plan", ""),
            validation_plan=d.get("validation_plan", ""),
            related_failure_patterns=d.get("related_failure_patterns", []),
            related_scorecard_ids=d.get("related_scorecard_ids", []),
            rejection_reason=d.get("rejection_reason"),
            dry_run_result=d.get("dry_run_result"),
        )


# ---------------------------------------------------------------------------
# RecommendationRegistry
# ---------------------------------------------------------------------------


class RecommendationRegistry:
    """Manages the lifecycle of NUS 1B recommendations.

    Safety: all dangerous action types are blocked at creation.
    Medium-risk actions require explicit approval.
    Safe local actions can proceed to dry-run.
    """

    def __init__(self, store: Optional[Any] = None) -> None:
        self._recommendations: Dict[str, Recommendation] = {}
        self._store = store

    # ------------------------------------------------------------------ #
    # Creation                                                              #
    # ------------------------------------------------------------------ #

    def create(
        self,
        source: str,
        category: str,
        title: str,
        summary: str,
        rationale: str = "",
        affected_area: str = "",
        risk_level: str = RISK_LOW,
        confidence: str = CONFIDENCE_MEDIUM,
        expected_benefit: str = "",
        required_action_type: str = ACTION_LOCAL_ANALYSIS,
        evidence: Optional[Dict[str, Any]] = None,
        rollback_plan: str = "",
        validation_plan: str = "",
        related_failure_patterns: Optional[List[str]] = None,
        related_scorecard_ids: Optional[List[str]] = None,
    ) -> Recommendation:
        """Create and classify a recommendation. Returns the created object."""
        policy = resolve_approval_policy(required_action_type)

        if policy in _BLOCKED_POLICIES:
            status = STATUS_BLOCKED
        elif policy in _APPROVAL_POLICIES:
            status = STATUS_NEEDS_APPROVAL
        else:
            status = STATUS_READY

        rec = Recommendation(
            source=source,
            category=category,
            title=title,
            summary=summary,
            rationale=rationale,
            affected_area=affected_area,
            risk_level=risk_level,
            confidence=confidence,
            expected_benefit=expected_benefit,
            required_action_type=required_action_type,
            approval_policy=policy,
            status=status,
            evidence=evidence or {},
            rollback_plan=rollback_plan,
            validation_plan=validation_plan,
            related_failure_patterns=related_failure_patterns or [],
            related_scorecard_ids=related_scorecard_ids or [],
        )

        self._recommendations[rec.id] = rec
        self._log_event("recommendation_created", f"Created: {rec.id} status={rec.status}")
        self._persist(rec)
        return rec

    # ------------------------------------------------------------------ #
    # Lifecycle transitions                                                  #
    # ------------------------------------------------------------------ #

    def validate(self, rec_id: str) -> Dict[str, Any]:
        """Validate a recommendation. Returns validation result dict."""
        rec = self._recommendations.get(rec_id)
        if not rec:
            return {"ok": False, "reason": "recommendation not found"}
        if rec.status == STATUS_BLOCKED:
            return {"ok": False, "reason": "recommendation is blocked — cannot validate"}
        if not rec.title or not rec.summary:
            return {"ok": False, "reason": "missing required fields: title, summary"}
        return {"ok": True, "rec_id": rec_id, "status": rec.status}

    def approve(self, rec_id: str, approved_by: str = "founder") -> Dict[str, Any]:
        """Mark a needs_approval recommendation as approved."""
        rec = self._recommendations.get(rec_id)
        if not rec:
            return {"ok": False, "reason": "recommendation not found"}
        if rec.status == STATUS_BLOCKED:
            self._log_event("recommendation_blocked", f"Approve rejected — blocked: {rec_id}")
            return {"ok": False, "reason": "blocked recommendations cannot be approved"}
        if rec.status not in (STATUS_NEEDS_APPROVAL, STATUS_READY, STATUS_DRAFT):
            return {"ok": False, "reason": f"cannot approve from status={rec.status}"}
        rec.status = STATUS_APPROVED
        rec.updated_at = time.time()
        rec.evidence["approved_by"] = approved_by
        self._log_event("recommendation_approved", f"Approved: {rec_id} by {approved_by}")
        self._persist(rec)
        return {"ok": True, "rec_id": rec_id, "status": rec.status}

    def reject(self, rec_id: str, reason: str = "", rejected_by: str = "founder") -> Dict[str, Any]:
        """Reject a recommendation."""
        rec = self._recommendations.get(rec_id)
        if not rec:
            return {"ok": False, "reason": "recommendation not found"}
        rec.status = STATUS_REJECTED
        rec.rejection_reason = reason
        rec.updated_at = time.time()
        rec.evidence["rejected_by"] = rejected_by
        self._log_event("recommendation_rejected", f"Rejected: {rec_id} reason={reason}")
        self._persist(rec)
        return {"ok": True, "rec_id": rec_id, "status": rec.status}

    def execute_dry_run(self, rec_id: str) -> Dict[str, Any]:
        """Execute a safe dry-run for an approved or ready recommendation.

        Dry-run = no risky external action, no code/file mutation.
        Only auto_allowed_* policy recommendations can proceed.
        """
        rec = self._recommendations.get(rec_id)
        if not rec:
            return {"ok": False, "reason": "recommendation not found"}

        if rec.status in (STATUS_REJECTED, STATUS_SUPERSEDED):
            return {"ok": False, "reason": f"cannot dry-run from status={rec.status}"}

        if rec.status == STATUS_BLOCKED:
            self._log_event("recommendation_blocked", f"Dry-run blocked: {rec_id}")
            return {"ok": False, "reason": "blocked — dry-run not allowed"}

        if rec.approval_policy in _BLOCKED_POLICIES:
            self._log_event("recommendation_blocked", f"Dry-run policy blocked: {rec_id}")
            return {"ok": False, "reason": f"policy={rec.approval_policy} — blocked"}

        if rec.approval_policy in _APPROVAL_POLICIES and rec.status != STATUS_APPROVED:
            return {
                "ok": False,
                "reason": f"requires approval before dry-run (status={rec.status})",
            }

        if rec.approval_policy not in _AUTO_POLICIES and rec.status not in (
            STATUS_APPROVED, STATUS_READY
        ):
            return {
                "ok": False,
                "reason": f"cannot dry-run from status={rec.status}",
            }

        dry_run_result = {
            "dry_run": True,
            "rec_id": rec_id,
            "title": rec.title,
            "action_type": rec.required_action_type,
            "policy": rec.approval_policy,
            "executed_at": time.time(),
            "result": "simulated_ok",
            "note": "NUS 1B dry-run only — no real execution",
        }
        rec.status = STATUS_EXECUTED_DRY_RUN
        rec.dry_run_result = dry_run_result
        rec.updated_at = time.time()
        self._log_event("recommendation_dry_run_executed", f"Dry-run: {rec_id}")
        self._persist(rec)
        return {"ok": True, **dry_run_result}

    def supersede(self, rec_id: str, successor_id: str) -> Dict[str, Any]:
        """Mark a recommendation as superseded by a newer one."""
        rec = self._recommendations.get(rec_id)
        if not rec:
            return {"ok": False, "reason": "recommendation not found"}
        rec.status = STATUS_SUPERSEDED
        rec.updated_at = time.time()
        rec.evidence["superseded_by"] = successor_id
        self._persist(rec)
        return {"ok": True, "rec_id": rec_id, "status": rec.status}

    # ------------------------------------------------------------------ #
    # Queries                                                               #
    # ------------------------------------------------------------------ #

    def get(self, rec_id: str) -> Optional[Recommendation]:
        return self._recommendations.get(rec_id)

    def list_all(self) -> List[Recommendation]:
        return list(self._recommendations.values())

    def list_by_status(self, status: str) -> List[Recommendation]:
        return [r for r in self._recommendations.values() if r.status == status]

    def count_by_status(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for r in self._recommendations.values():
            counts[r.status] = counts.get(r.status, 0) + 1
        return counts

    # ------------------------------------------------------------------ #
    # Factory: from NUS 1A artifacts                                        #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_scorecard(
        cls, scorecard_dict: Dict[str, Any], store: Optional[Any] = None
    ) -> "RecommendationRegistry":
        """Build a registry pre-populated from a NUS 1A scorecard."""
        registry = cls(store=store)
        risk = scorecard_dict.get("risk_level", RISK_LOW)
        action = scorecard_dict.get("recommended_action", "none")
        if action and action != "none":
            registry.create(
                source="nus1a_scorecard",
                category="scorecard_action",
                title=f"Scorecard recommended action: {action}",
                summary=f"Risk={risk}. Action: {action}.",
                rationale="Generated from NUS 1A AgentScorecard.",
                risk_level=risk,
                required_action_type=ACTION_LOCAL_ANALYSIS,
                evidence={"scorecard_id": scorecard_dict.get("scorecard_id")},
                related_scorecard_ids=[scorecard_dict.get("scorecard_id", "")],
            )
        return registry

    @classmethod
    def from_failure_patterns(
        cls, patterns: List[Dict[str, Any]], store: Optional[Any] = None
    ) -> "RecommendationRegistry":
        """Build a registry pre-populated from NUS 1A failure patterns."""
        registry = cls(store=store)
        for p in patterns:
            registry.create(
                source="nus1a_failure_pattern",
                category="failure_remediation",
                title=f"Address failure pattern: {p.get('category', 'unknown')}",
                summary=p.get("recommendation", "Review and address the detected failure pattern."),
                rationale=f"Pattern detected {p.get('count', 0)} times. Severity={p.get('severity', 'low')}.",
                risk_level=p.get("severity", RISK_LOW),
                required_action_type=ACTION_LOCAL_ANALYSIS,
                evidence={"pattern_id": p.get("pattern_id"), "count": p.get("count")},
                related_failure_patterns=[p.get("pattern_id", "")],
            )
        return registry

    # ------------------------------------------------------------------ #
    # Internal                                                              #
    # ------------------------------------------------------------------ #

    def _persist(self, rec: Recommendation) -> None:
        if self._store:
            try:
                self._store.append_recommendation(rec.to_dict())
            except Exception as exc:
                logger.debug("Recommendation persist failed: %s", exc)

    def _log_event(self, event_type: str, detail: str) -> None:
        try:
            from openjarvis.workbench.event_log import WorkbenchEventLog
            log = WorkbenchEventLog()
            log.push(
                session_id="nus1b",
                task_id="recommendation_registry",
                event_type=event_type,
                title=f"NUS 1B: {event_type}",
                detail=detail,
                tone="info",
                dry_run=False,
            )
        except Exception as exc:
            logger.debug("NUS 1B event log skipped: %s", exc)
