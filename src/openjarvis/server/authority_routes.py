"""Plan 8 — Authority/Trusted Delegation API Routes.

Exposes Plan 8 state for Bryan and UI integration:

  GET  /v1/authority/status           — current tier, emergency stop, summary
  GET  /v1/authority/tiers            — full tier matrix
  GET  /v1/authority/approvals/pending  — pending approvals
  GET  /v1/authority/approvals/active   — active (granted) approvals
  GET  /v1/authority/approvals/revoked  — revoked/denied approvals
  POST /v1/authority/approvals/{id}/grant  — grant a pending approval
  POST /v1/authority/approvals/{id}/deny   — deny a pending approval
  POST /v1/authority/approvals/{id}/revoke — revoke a granted approval
  GET  /v1/authority/emergency-stop     — emergency stop status
  POST /v1/authority/emergency-stop/set — activate emergency stop
  POST /v1/authority/emergency-stop/clear — clear emergency stop
  GET  /v1/authority/audit             — recent audit entries
  GET  /v1/authority/audit/blocked     — blocked action audit entries
  POST /v1/authority/classify          — classify action risk
  POST /v1/authority/preview           — generate action preview + dry-run
  GET  /v1/authority/spend/summary     — spend summary
  GET  /v1/authority/secret-policy     — secret policy manifest
  POST /v1/authority/secret-policy/scan — scan text for secret patterns

No secret values are ever returned by these routes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, Body, HTTPException
    from pydantic import BaseModel
except ImportError:
    raise ImportError("fastapi and pydantic are required for authority routes")

from openjarvis.authority.action_preview import build_preview
from openjarvis.authority.approval_engine import ApprovalEngine, ApprovalStatus
from openjarvis.authority.audit_store import AuditStore
from openjarvis.authority.emergency import (
    clear_emergency_stop,
    get_emergency_status,
    is_emergency_stop_active,
    set_emergency_stop,
)
from openjarvis.authority.risk_classifier import classify_action, classify_risk_matrix
from openjarvis.authority.secret_policy import SECRET_POLICY_MANIFEST, secret_scan_string
from openjarvis.authority.spend_guard import SpendGuard
from openjarvis.authority.tiers import AuthorityTier, tier_matrix

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------

_approval_engine: Optional[ApprovalEngine] = None
_audit_store: Optional[AuditStore] = None
_spend_guard: Optional[SpendGuard] = None


def _get_approval_engine() -> ApprovalEngine:
    global _approval_engine
    if _approval_engine is None:
        _approval_engine = ApprovalEngine()
    return _approval_engine


def _get_audit_store() -> AuditStore:
    global _audit_store
    if _audit_store is None:
        _audit_store = AuditStore()
    return _audit_store


def _get_spend_guard() -> SpendGuard:
    global _spend_guard
    if _spend_guard is None:
        _spend_guard = SpendGuard()
    return _spend_guard


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class ClassifyRequest(BaseModel):
    action_type: str


class PreviewRequest(BaseModel):
    action_type: str
    description: str = ""
    target_system: str = ""
    files: List[str] = []
    resources: List[str] = []
    accounts: List[str] = []
    diff_summary: str = ""
    cost_estimate: float = 0.0
    cost_estimate_source: str = "unknown"
    rollback_plan: str = ""
    rollback_supported: bool = True
    rollback_method: str = "manual"
    created_by: str = "user"
    run_dry_run: bool = True


class EmergencyStopRequest(BaseModel):
    activated_by: str = "owner"
    reason: str = ""


class EmergencyClearRequest(BaseModel):
    cleared_by: str = "owner"


class GrantRequest(BaseModel):
    expires_in_seconds: Optional[int] = 3600


class DenyRequest(BaseModel):
    reason: str = ""


class RevokeRequest(BaseModel):
    reason: str = ""


class ScanRequest(BaseModel):
    text: str


class ApprovalRequest(BaseModel):
    action_type: str
    requester: str = "user"
    tier: int = 0
    risk_level: str = "low"
    action_preview: str = ""
    affected_systems: List[str] = []
    affected_files: List[str] = []
    affected_accounts: List[str] = []
    estimated_spend: float = 0.0
    rollback_plan: str = ""
    scope: str = ""
    expires_in_seconds: Optional[int] = 3600


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/authority/status")
async def get_authority_status() -> Dict[str, Any]:
    """Return current Plan 8 authority status."""
    engine = _get_approval_engine()
    engine.expire_stale()
    pending = engine.list_pending()
    active = engine.list_active()
    emstop = get_emergency_status()
    audit = _get_audit_store()

    return {
        "plan_8_version": "plan8-trusted-delegation-v1",
        "emergency_stop_active": emstop.get("active", False),
        "emergency_stop_status": emstop,
        "pending_approvals_count": len(pending),
        "active_approvals_count": len(active),
        "recent_audit_count": audit.count(),
        "authority_tier_max": AuthorityTier.TIER_5.value,
        "blocked_by_emergency_stop": emstop.get("active", False),
        "status": "emergency_stop_active" if emstop.get("active") else "operational",
    }


@router.get("/v1/authority/tiers")
async def get_tier_matrix() -> Dict[str, Any]:
    """Return the full permission tier matrix."""
    return {
        "tiers": tier_matrix(),
        "tier_count": len(AuthorityTier),
    }


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


@router.get("/v1/authority/approvals/pending")
async def list_pending_approvals() -> Dict[str, Any]:
    engine = _get_approval_engine()
    engine.expire_stale()
    records = engine.list_pending()
    return {
        "approvals": [r.to_dict() for r in records],
        "count": len(records),
    }


@router.get("/v1/authority/approvals/active")
async def list_active_approvals() -> Dict[str, Any]:
    engine = _get_approval_engine()
    records = engine.list_active()
    return {
        "approvals": [r.to_dict() for r in records],
        "count": len(records),
    }


@router.get("/v1/authority/approvals/revoked")
async def list_revoked_approvals() -> Dict[str, Any]:
    engine = _get_approval_engine()
    records = engine.list_revoked()
    return {
        "approvals": [r.to_dict() for r in records],
        "count": len(records),
    }


@router.post("/v1/authority/approvals/request")
async def request_approval(body: ApprovalRequest) -> Dict[str, Any]:
    """Create an approval record for a proposed action."""
    engine = _get_approval_engine()
    audit = _get_audit_store()
    profile = classify_action(body.action_type)
    tier = body.tier if body.tier > 0 else profile.recommended_tier
    risk_level = body.risk_level if body.risk_level != "low" else profile.risk_label

    record = engine.request_approval(
        action_type=body.action_type,
        requester=body.requester,
        tier=tier,
        risk_level=risk_level,
        action_preview=body.action_preview,
        affected_systems=body.affected_systems,
        affected_files=body.affected_files,
        affected_accounts=body.affected_accounts,
        estimated_spend=body.estimated_spend,
        rollback_plan=body.rollback_plan,
        scope=body.scope,
        expires_in_seconds=body.expires_in_seconds,
    )
    audit.record(
        action_type="approval_requested",
        actor=body.requester,
        tier=tier,
        risk_level=risk_level,
        approval_decision=record.status.value,
        execution_status="success",
        affected_resource=body.action_type,
        approval_id=record.approval_id,
        audit_trace_id=record.audit_trace_id,
        context={"mode": record.mode.value, "scope": body.scope},
    )
    return record.to_dict()


@router.post("/v1/authority/approvals/{approval_id}/grant")
async def grant_approval(approval_id: str, body: GrantRequest) -> Dict[str, Any]:
    engine = _get_approval_engine()
    audit = _get_audit_store()
    pending = engine.get(approval_id)
    success = engine.grant(approval_id, expires_in_seconds=body.expires_in_seconds)
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found or not in PENDING state")
    updated = engine.get(approval_id)
    audit.record(
        action_type="approval_granted",
        actor="owner",
        tier=updated.tier if updated else 0,
        risk_level=updated.risk_level if updated else "low",
        approval_decision="granted",
        execution_status="success",
        affected_resource=pending.action_type if pending else "",
        approval_id=approval_id,
        audit_trace_id=updated.audit_trace_id if updated else "",
    )
    return {"status": "granted", "approval_id": approval_id, "record": updated.to_dict() if updated else {}}


@router.post("/v1/authority/approvals/{approval_id}/deny")
async def deny_approval(approval_id: str, body: DenyRequest) -> Dict[str, Any]:
    engine = _get_approval_engine()
    audit = _get_audit_store()
    pending = engine.get(approval_id)
    success = engine.deny(approval_id, reason=body.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")
    audit.record(
        action_type="approval_denied",
        actor="owner",
        tier=pending.tier if pending else 0,
        risk_level=pending.risk_level if pending else "low",
        approval_decision="denied",
        execution_status="blocked",
        affected_resource=pending.action_type if pending else "",
        approval_id=approval_id,
        error_info=body.reason,
        audit_trace_id=pending.audit_trace_id if pending else "",
    )
    return {"status": "denied", "approval_id": approval_id}


@router.post("/v1/authority/approvals/{approval_id}/revoke")
async def revoke_approval(approval_id: str, body: RevokeRequest) -> Dict[str, Any]:
    engine = _get_approval_engine()
    success = engine.revoke(approval_id, reason=body.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"status": "revoked", "approval_id": approval_id}


# ---------------------------------------------------------------------------
# Emergency stop
# ---------------------------------------------------------------------------


@router.get("/v1/authority/emergency-stop")
async def get_emergency_stop_status() -> Dict[str, Any]:
    """Return emergency stop status."""
    return get_emergency_status()


@router.post("/v1/authority/emergency-stop/set")
async def activate_emergency_stop(body: EmergencyStopRequest) -> Dict[str, Any]:
    """Activate the global emergency stop. Blocks all Tier 2+ actions."""
    result = set_emergency_stop(activated_by=body.activated_by, reason=body.reason)

    # Also revoke all active approvals
    engine = _get_approval_engine()
    revoked_count = engine.revoke_all_active(reason="emergency_stop")
    logger.warning(
        "EMERGENCY STOP activated by %s. Reason: %s. Revoked %d active approvals.",
        body.activated_by, body.reason, revoked_count,
    )

    # Audit log
    audit = _get_audit_store()
    audit.record(
        action_type="emergency_stop_activated",
        actor=body.activated_by,
        tier=0,
        risk_level="critical",
        approval_decision="auto_allow",
        execution_status="success",
        affected_resource="global",
    )

    return {
        **result,
        "revoked_approvals_count": revoked_count,
    }


@router.post("/v1/authority/emergency-stop/clear")
async def deactivate_emergency_stop(body: EmergencyClearRequest) -> Dict[str, Any]:
    """Clear the global emergency stop (owner only)."""
    result = clear_emergency_stop(cleared_by=body.cleared_by)

    audit = _get_audit_store()
    audit.record(
        action_type="emergency_stop_cleared",
        actor=body.cleared_by,
        tier=0,
        risk_level="high",
        approval_decision="owner_cleared",
        execution_status="success",
        affected_resource="global",
    )

    logger.info("EMERGENCY STOP cleared by %s.", body.cleared_by)
    return result


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


@router.get("/v1/authority/audit")
async def get_recent_audit(limit: int = 50) -> Dict[str, Any]:
    """Return recent audit entries (no secrets in output)."""
    audit = _get_audit_store()
    entries = audit.list_recent(min(limit, 200))
    return {
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
        "total_count": audit.count(),
    }


@router.get("/v1/authority/audit/blocked")
async def get_blocked_audit(limit: int = 50) -> Dict[str, Any]:
    """Return audit entries for blocked actions."""
    audit = _get_audit_store()
    entries = audit.list_blocked(min(limit, 200))
    return {
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
    }


# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------


@router.post("/v1/authority/classify")
async def classify_action_risk(body: ClassifyRequest) -> Dict[str, Any]:
    """Classify an action type and return its risk profile + recommended tier."""
    profile = classify_action(body.action_type)
    return profile.to_dict()


@router.get("/v1/authority/risk-matrix")
async def get_risk_matrix() -> Dict[str, Any]:
    """Return the full risk classification matrix."""
    return {
        "matrix": classify_risk_matrix(),
        "count": len(classify_risk_matrix()),
    }


# ---------------------------------------------------------------------------
# Action preview
# ---------------------------------------------------------------------------


@router.post("/v1/authority/preview")
async def generate_action_preview(body: PreviewRequest) -> Dict[str, Any]:
    """Generate a full action preview (and optional dry-run) for a proposed action."""
    # First classify the action
    profile = classify_action(body.action_type)

    preview = build_preview(
        action_type=body.action_type,
        description=body.description,
        target_system=body.target_system,
        files=body.files,
        resources=body.resources,
        accounts=body.accounts,
        diff_summary=body.diff_summary,
        cost_estimate=body.cost_estimate,
        cost_estimate_source=body.cost_estimate_source,
        rollback_plan=body.rollback_plan,
        rollback_supported=body.rollback_supported,
        rollback_method=body.rollback_method,
        tier=profile.recommended_tier,
        risk_level=profile.risk_label,
        created_by=body.created_by,
        run_dry_run=body.run_dry_run,
    )

    return {
        "preview": preview.to_dict(),
        "risk_profile": profile.to_dict(),
    }


# ---------------------------------------------------------------------------
# Spend
# ---------------------------------------------------------------------------


@router.get("/v1/authority/spend/summary")
async def get_spend_summary() -> Dict[str, Any]:
    """Return current session and daily spend summary."""
    return _get_spend_guard().summary()


# ---------------------------------------------------------------------------
# Secret policy
# ---------------------------------------------------------------------------


@router.get("/v1/authority/secret-policy")
async def get_secret_policy() -> Dict[str, Any]:
    """Return the secret/credential access policy manifest."""
    return SECRET_POLICY_MANIFEST


@router.post("/v1/authority/secret-policy/scan")
async def scan_for_secrets(body: ScanRequest) -> Dict[str, Any]:
    """Scan text for obvious secret patterns.

    Returns clean=True if no patterns detected.
    WARNING: Do not pass actual secret values — this is for validation only.
    The text is scanned but the actual matches are never logged in full.
    """
    result = secret_scan_string(body.text)
    return result.to_dict()


__all__ = ["router"]
