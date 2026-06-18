"""Epic E — Optimization Platform (Wave 2).

Analyzes Jarvis workflows, events, cost/routing metadata, validation outcomes,
and capability status to produce scorecards and recommendations.

Rules:
- Local-first, no external keys required.
- Read-only analysis only — never auto-modifies code, auto-commits, or deploys.
- Recommendations that imply file writes, deploys, external sends, or production
  actions are approval-gated.
- Produces proposals only — NUS 1 (auto-upgrade) is separate and locked.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REC_LEVEL_INFO = "info"
REC_LEVEL_WARN = "warning"
REC_LEVEL_CRITICAL = "critical"

REC_CATEGORY_COST = "cost"
REC_CATEGORY_ROUTING = "model_routing"
REC_CATEGORY_VALIDATION = "validation"
REC_CATEGORY_FAILURE = "failure_detection"
REC_CATEGORY_READINESS = "readiness"
REC_CATEGORY_SAFETY = "safety"

# Actions that require approval before acting on a recommendation
_APPROVAL_REQUIRED_ACTIONS = frozenset({
    "file_write", "git_commit", "deploy", "external_send",
    "browser_action", "production_change", "self_upgrade",
})

# Safe actions that can be presented without approval
_SAFE_RECOMMENDATION_ACTIONS = frozenset({
    "review", "log", "report", "notify_founder", "adjust_config_local",
    "rerun_test", "update_docs",
})


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class OptimizationRecommendation:
    rec_id: str
    category: str
    level: str  # info | warning | critical
    title: str
    detail: str
    action: str  # what the recommendation proposes
    approval_required: bool = False
    blocked: bool = False
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rec_id": self.rec_id,
            "category": self.category,
            "level": self.level,
            "title": self.title,
            "detail": self.detail,
            "action": self.action,
            "approval_required": self.approval_required,
            "blocked": self.blocked,
            "evidence": self.evidence,
        }


@dataclass
class WorkflowScorecard:
    scorecard_id: str
    generated_at: float
    overall_score: float  # 0.0 – 1.0
    cost_score: float
    routing_score: float
    validation_score: float
    failure_score: float
    readiness_score: float
    recommendations: List[OptimizationRecommendation] = field(default_factory=list)
    summary: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scorecard_id": self.scorecard_id,
            "generated_at": self.generated_at,
            "overall_score": round(self.overall_score, 3),
            "cost_score": round(self.cost_score, 3),
            "routing_score": round(self.routing_score, 3),
            "validation_score": round(self.validation_score, 3),
            "failure_score": round(self.failure_score, 3),
            "readiness_score": round(self.readiness_score, 3),
            "recommendation_count": len(self.recommendations),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Cost analysis
# ---------------------------------------------------------------------------

def _analyze_cost(ledger_summary: Optional[Dict[str, Any]] = None) -> tuple:
    """Analyze cost entries. Returns (score, recommendations)."""
    recs: List[OptimizationRecommendation] = []
    score = 1.0

    try:
        if ledger_summary is None:
            from openjarvis.workbench.cost_ledger import CostLedger
            ledger = CostLedger()
            ledger_summary = ledger.get_summary() if hasattr(ledger, "get_summary") else {}
    except Exception:
        ledger_summary = {}

    total_cost = ledger_summary.get("total_cost_usd", 0.0)
    entry_count = ledger_summary.get("entry_count", 0)

    # High cost warning
    if total_cost > 5.0:
        score -= 0.3
        recs.append(OptimizationRecommendation(
            rec_id="cost_high_total",
            category=REC_CATEGORY_COST,
            level=REC_LEVEL_WARN,
            title="High total API cost detected",
            detail=f"Total cost ${total_cost:.4f} exceeds $5.00 threshold.",
            action="review",
            evidence={"total_cost_usd": total_cost, "entry_count": entry_count},
        ))
    elif total_cost > 1.0:
        score -= 0.1
        recs.append(OptimizationRecommendation(
            rec_id="cost_moderate",
            category=REC_CATEGORY_COST,
            level=REC_LEVEL_INFO,
            title="Moderate API cost — monitor burn rate",
            detail=f"Total cost ${total_cost:.4f}. Consider Composer 2.5 for simple tasks.",
            action="review",
            evidence={"total_cost_usd": total_cost},
        ))
    else:
        recs.append(OptimizationRecommendation(
            rec_id="cost_ok",
            category=REC_CATEGORY_COST,
            level=REC_LEVEL_INFO,
            title="Cost within acceptable range",
            detail=f"Total cost ${total_cost:.4f} is within budget.",
            action="log",
            evidence={"total_cost_usd": total_cost},
        ))

    return max(0.0, score), recs


# ---------------------------------------------------------------------------
# Model routing analysis
# ---------------------------------------------------------------------------

def _analyze_routing() -> tuple:
    """Analyze model routing usage. Returns (score, recommendations)."""
    recs: List[OptimizationRecommendation] = []
    score = 1.0

    try:
        from openjarvis.workbench.model_router import ModelRouter
        router = ModelRouter()
        # Use available API to inspect routing stats if available
        stats = getattr(router, "get_stats", lambda: {})()
        if not stats:
            # No stats available — treat as neutral
            recs.append(OptimizationRecommendation(
                rec_id="routing_no_stats",
                category=REC_CATEGORY_ROUTING,
                level=REC_LEVEL_INFO,
                title="Model routing stats unavailable",
                detail="No routing history found. First-run baseline.",
                action="log",
            ))
            return score, recs

        opus_pct = stats.get("opus_percentage", 0.0)
        if opus_pct > 0.5:
            score -= 0.2
            recs.append(OptimizationRecommendation(
                rec_id="routing_opus_overuse",
                category=REC_CATEGORY_ROUTING,
                level=REC_LEVEL_WARN,
                title="Opus model overused",
                detail=f"Opus used in {opus_pct*100:.0f}% of calls. Recommend Sonnet 4.6 for medium tasks.",
                action="review",
                evidence=stats,
            ))
        else:
            recs.append(OptimizationRecommendation(
                rec_id="routing_ok",
                category=REC_CATEGORY_ROUTING,
                level=REC_LEVEL_INFO,
                title="Model routing within guidelines",
                detail="Model tier usage looks appropriate.",
                action="log",
                evidence=stats,
            ))
    except Exception as exc:
        recs.append(OptimizationRecommendation(
            rec_id="routing_error",
            category=REC_CATEGORY_ROUTING,
            level=REC_LEVEL_INFO,
            title="Model routing analysis unavailable",
            detail=str(exc),
            action="log",
        ))

    return max(0.0, score), recs


# ---------------------------------------------------------------------------
# Validation profile analysis
# ---------------------------------------------------------------------------

def _analyze_validation() -> tuple:
    """Analyze validation profile outcomes. Returns (score, recommendations)."""
    recs: List[OptimizationRecommendation] = []
    score = 1.0

    try:
        from openjarvis.workbench.validation_profiles import list_validation_profiles
        profiles = list_validation_profiles()

        failing = [p for p in profiles if p.get("last_result") == "fail"]
        if failing:
            score -= 0.3 * min(1.0, len(failing) / max(1, len(profiles)))
            recs.append(OptimizationRecommendation(
                rec_id="validation_profiles_failing",
                category=REC_CATEGORY_VALIDATION,
                level=REC_LEVEL_WARN,
                title=f"{len(failing)} validation profile(s) failing",
                detail=f"Profiles with failures: {[p.get('id') for p in failing[:3]]}",
                action="rerun_test",
                evidence={"failing_count": len(failing), "total": len(profiles)},
            ))
        else:
            recs.append(OptimizationRecommendation(
                rec_id="validation_ok",
                category=REC_CATEGORY_VALIDATION,
                level=REC_LEVEL_INFO,
                title="All validation profiles passing",
                detail=f"{len(profiles)} profile(s) checked.",
                action="log",
                evidence={"profile_count": len(profiles)},
            ))
    except Exception:
        recs.append(OptimizationRecommendation(
            rec_id="validation_unavailable",
            category=REC_CATEGORY_VALIDATION,
            level=REC_LEVEL_INFO,
            title="Validation profile analysis unavailable",
            detail="Validation profiles module not accessible.",
            action="log",
        ))

    return max(0.0, score), recs


# ---------------------------------------------------------------------------
# Repeated failure detection
# ---------------------------------------------------------------------------

def _analyze_failures() -> tuple:
    """Detect repeated failures from event log. Returns (score, recommendations)."""
    recs: List[OptimizationRecommendation] = []
    score = 1.0

    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        recent_events = getattr(log, "list_events", lambda **kw: [])(limit=100)

        fail_events = [
            e for e in recent_events
            if isinstance(e, dict) and e.get("tone") in ("error", "warning")
        ]
        if hasattr(fail_events[0] if fail_events else None, "to_dict"):
            fail_events = [e.to_dict() for e in fail_events]

        # Count failures by task
        task_fails: Dict[str, int] = {}
        for ev in fail_events:
            tid = ev.get("task_id", "unknown")
            task_fails[tid] = task_fails.get(tid, 0) + 1

        repeated = {tid: cnt for tid, cnt in task_fails.items() if cnt >= 3}
        if repeated:
            score -= min(0.5, 0.1 * len(repeated))
            recs.append(OptimizationRecommendation(
                rec_id="failure_repeated",
                category=REC_CATEGORY_FAILURE,
                level=REC_LEVEL_WARN,
                title=f"Repeated failures detected in {len(repeated)} task(s)",
                detail=f"Tasks with 3+ failures: {list(repeated.keys())[:3]}",
                action="review",
                evidence={"repeated_failures": repeated},
            ))
        else:
            recs.append(OptimizationRecommendation(
                rec_id="failure_ok",
                category=REC_CATEGORY_FAILURE,
                level=REC_LEVEL_INFO,
                title="No repeated task failures detected",
                detail=f"Analyzed {len(recent_events)} recent events.",
                action="log",
                evidence={"event_count": len(recent_events)},
            ))
    except Exception as exc:
        recs.append(OptimizationRecommendation(
            rec_id="failure_analysis_error",
            category=REC_CATEGORY_FAILURE,
            level=REC_LEVEL_INFO,
            title="Failure analysis unavailable",
            detail=str(exc),
            action="log",
        ))

    return max(0.0, score), recs


# ---------------------------------------------------------------------------
# Readiness / risk analysis
# ---------------------------------------------------------------------------

def _analyze_readiness() -> tuple:
    """Analyze capability readiness. Returns (score, recommendations)."""
    recs: List[OptimizationRecommendation] = []
    score = 1.0

    try:
        from openjarvis.workbench.capabilities_registry import get_capabilities_summary
        summary = get_capabilities_summary()
        caps = summary.get("capabilities", [])

        not_ready = [c for c in caps if c.get("status") not in ("ready", "degraded")]
        requires_setup = [c for c in not_ready if c.get("status") == "requires_setup"]
        not_impl = [c for c in not_ready if c.get("status") == "not_implemented"]

        if requires_setup:
            score -= 0.1 * min(1.0, len(requires_setup) / max(1, len(caps)))
            recs.append(OptimizationRecommendation(
                rec_id="readiness_requires_setup",
                category=REC_CATEGORY_READINESS,
                level=REC_LEVEL_INFO,
                title=f"{len(requires_setup)} capability/ies require setup",
                detail=f"Setup needed: {[c.get('capability_id') for c in requires_setup[:3]]}",
                action="review",
                evidence={"requires_setup": [c.get("capability_id") for c in requires_setup]},
            ))

        if not_impl:
            # Future waves — expected, not a problem
            recs.append(OptimizationRecommendation(
                rec_id="readiness_not_impl",
                category=REC_CATEGORY_READINESS,
                level=REC_LEVEL_INFO,
                title=f"{len(not_impl)} capability/ies not yet implemented (future waves)",
                detail="Wave 3–4 items correctly marked not_implemented.",
                action="log",
            ))

        ready_count = len([c for c in caps if c.get("status") == "ready"])
        recs.append(OptimizationRecommendation(
            rec_id="readiness_ready_count",
            category=REC_CATEGORY_READINESS,
            level=REC_LEVEL_INFO,
            title=f"{ready_count}/{len(caps)} capabilities ready",
            detail=f"Platform readiness: {ready_count}/{len(caps)}",
            action="log",
            evidence={"ready": ready_count, "total": len(caps)},
        ))

    except Exception as exc:
        recs.append(OptimizationRecommendation(
            rec_id="readiness_error",
            category=REC_CATEGORY_READINESS,
            level=REC_LEVEL_INFO,
            title="Readiness analysis unavailable",
            detail=str(exc),
            action="log",
        ))

    return max(0.0, score), recs


# ---------------------------------------------------------------------------
# Event logging
# ---------------------------------------------------------------------------

def _log_optimization_event(event_type: str, ok: bool, detail: str) -> str:
    try:
        from openjarvis.workbench.event_log import WorkbenchEventLog
        log = WorkbenchEventLog()
        ev = log.push(
            session_id="wave2_optimization",
            task_id=f"optimization:{event_type}",
            event_type=event_type,
            title=f"Optimization: {event_type}",
            detail=detail,
            tone="success" if ok else "warning",
            metadata={"ok": ok},
        )
        return ev.id
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Main scorecard generator
# ---------------------------------------------------------------------------

def generate_scorecard(
    ledger_summary: Optional[Dict[str, Any]] = None,
) -> WorkflowScorecard:
    """Generate a full workflow optimization scorecard.

    Reads from: cost ledger, model router, validation profiles,
    event log (failures), capabilities registry.

    Returns: WorkflowScorecard with scores and recommendations.
    Never modifies code, never auto-commits, never deploys.
    """
    import uuid as _uuid

    scorecard_id = _uuid.uuid4().hex[:12]
    ts = time.time()

    cost_score, cost_recs = _analyze_cost(ledger_summary)
    routing_score, routing_recs = _analyze_routing()
    val_score, val_recs = _analyze_validation()
    fail_score, fail_recs = _analyze_failures()
    ready_score, ready_recs = _analyze_readiness()

    all_recs = cost_recs + routing_recs + val_recs + fail_recs + ready_recs

    # Gate recommendations that imply unsafe actions
    for rec in all_recs:
        if rec.action in _APPROVAL_REQUIRED_ACTIONS:
            rec.approval_required = True

    overall = (cost_score + routing_score + val_score + fail_score + ready_score) / 5.0

    warns = [r for r in all_recs if r.level == REC_LEVEL_WARN]
    crits = [r for r in all_recs if r.level == REC_LEVEL_CRITICAL]
    summary = (
        f"Overall score {overall:.0%}. "
        f"{len(crits)} critical, {len(warns)} warnings, "
        f"{len(all_recs) - len(crits) - len(warns)} informational recommendations."
    )

    eid = _log_optimization_event("optimization_scorecard", True,
                                   f"Scorecard {scorecard_id}: score={overall:.3f}")

    sc = WorkflowScorecard(
        scorecard_id=scorecard_id,
        generated_at=ts,
        overall_score=overall,
        cost_score=cost_score,
        routing_score=routing_score,
        validation_score=val_score,
        failure_score=fail_score,
        readiness_score=ready_score,
        recommendations=all_recs,
        summary=summary,
        evidence={"event_id": eid},
    )
    return sc


def get_recommendations_by_category(category: str) -> List[OptimizationRecommendation]:
    """Generate a scorecard and return recommendations for a specific category."""
    sc = generate_scorecard()
    return [r for r in sc.recommendations if r.category == category]


def get_optimization_platform_status() -> Dict[str, Any]:
    return {
        "epic": "epic_e",
        "wave": 2,
        "status": "ready",
        "implemented": True,
        "scorecard_implemented": True,
        "cost_analysis_implemented": True,
        "routing_analysis_implemented": True,
        "validation_analysis_implemented": True,
        "failure_detection_implemented": True,
        "readiness_analysis_implemented": True,
        "auto_modify_disabled": True,
        "auto_commit_disabled": True,
        "auto_deploy_disabled": True,
        "approval_gated_actions": sorted(_APPROVAL_REQUIRED_ACTIONS),
        "note": (
            "Wave 2 Epic E: Local optimization platform. Produces scorecards and recommendations. "
            "No autonomous self-modification. NUS 1 (auto-upgrade) is separate and locked."
        ),
    }


__all__ = [
    "OptimizationRecommendation",
    "WorkflowScorecard",
    "generate_scorecard",
    "get_recommendations_by_category",
    "get_optimization_platform_status",
    "REC_LEVEL_INFO",
    "REC_LEVEL_WARN",
    "REC_LEVEL_CRITICAL",
    "REC_CATEGORY_COST",
    "REC_CATEGORY_ROUTING",
    "REC_CATEGORY_VALIDATION",
    "REC_CATEGORY_FAILURE",
    "REC_CATEGORY_READINESS",
]
