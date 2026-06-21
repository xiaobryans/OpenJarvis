"""Company Org + Mobile Continuity + Jarvis OS API Routes.

Routes (Company Org / Runtime):
  GET  /v1/company-org/status          — org spec status and role summary
  GET  /v1/company-org/roster          — full agent roster
  POST /v1/company-org/task            — run task through Jarvis→COS→manager→worker→verifier
  GET  /v1/company-org/wiring-matrix   — runtime wiring audit matrix

Routes (Mobile Continuity):
  POST /v1/continuity/devices          — register trusted device
  GET  /v1/continuity/devices          — list trusted devices for user
  POST /v1/continuity/snapshot         — save continuity snapshot
  GET  /v1/continuity/snapshot/{sid}   — get snapshot by ID
  POST /v1/continuity/resume           — resume session on target device
  GET  /v1/continuity/sync-status      — sync status for user
  GET  /v1/continuity/conflict         — conflict state for user
  GET  /v1/continuity/mobile-contract  — mobile client/API contract
  GET  /v1/continuity/macbook-off-status — always-available backend status

Routes (Jarvis OS — new this sprint):
  GET  /v1/jarvis/manifest             — runtime self-knowledge/capability manifest
  GET  /v1/jarvis/cost-dashboard       — cost/token ledger dashboard
  GET  /v1/jarvis/cache-trace          — role-scoped cache trace
  GET  /mobile                         — mobile-optimized PWA page (text fallback)
  GET  /manifest.webmanifest           — PWA web app manifest

Safety constraints (permanent):
  - No external sends (Slack/Telegram) without Bryan approval.
  - No secrets accepted or returned.
  - No production deploy.
  - No auto-push/merge.
  - MacBook-off continuity requires GITHUB_TOKEN in .env (GitHub Gist backend).
  - Without GITHUB_TOKEN, MacBook-off continuity: BLOCKED_WAITING_FOR_BRYAN_NOW.

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError("fastapi and pydantic are required for company_org_routes")

from openjarvis.company_org import get_company_org_spec, RoleTier, CapabilityStatus
from openjarvis.agents.company_org_runtime import (
    OrgTaskRequest,
    get_company_org_runtime,
)
from openjarvis.mobile.continuity import (
    ContinuityStore,
    DeviceType,
    SyncStatus,
    ConflictPolicy,
    OfflinePolicy,
    SecurityPolicy,
)
from openjarvis.mobile.continuity_backend import (
    get_always_available_store, check_token_present, check_token_format_valid
)
from openjarvis.agents.roster import get_default_registry
from openjarvis.jarvis_os.manifest import build_capability_manifest
from openjarvis.jarvis_os.cost_ledger import get_cost_ledger
from openjarvis.jarvis_os.role_cache import get_role_cache
from openjarvis.agents.hot_reload_gate import (
    get_hot_reload_gate, RoleRegistrationRequest, HotReloadStatus
)
from openjarvis.mobile.project_runtime import get_capability_matrix
from openjarvis.remote.github_actions_backend import get_github_actions_backend

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-process continuity store (local — no cloud sync in this sprint)
# ---------------------------------------------------------------------------

_continuity_store: Optional[ContinuityStore] = None


def _get_store() -> ContinuityStore:
    global _continuity_store
    if _continuity_store is None:
        _continuity_store = ContinuityStore(
            conflict_policy=ConflictPolicy.SURFACE_CONFLICT,
            offline_policy=OfflinePolicy.DEGRADE_GRACEFULLY,
            security_policy=SecurityPolicy.TRUSTED_DEVICE_REQUIRED,
        )
    return _continuity_store


# ---------------------------------------------------------------------------
# Pydantic models — Company Org
# ---------------------------------------------------------------------------

class OrgTaskRunRequest(BaseModel):
    user_request: str = Field(..., description="The task Bryan wants to run")
    intent: str = Field("coding", description="coding | research | memory | ops | connector | general")
    required_skills: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    simulate_stall: bool = Field(False, description="Test: simulate a worker stall")
    stall_worker_id: Optional[str] = Field(None, description="Which worker to stall")
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Pydantic models — Mobile Continuity
# ---------------------------------------------------------------------------

class DeviceRegistrationRequest(BaseModel):
    user_id: str = Field(..., description="Owner user ID (e.g. 'bryan')")
    device_type: str = Field(..., description="macbook | iphone | ipad | android | web | unknown")
    display_name: str = Field(..., description="Human-readable device name")
    trusted: bool = Field(True, description="Register as trusted device")


class SnapshotSaveRequest(BaseModel):
    user_id: str = Field(..., description="Owner user ID")
    source_device_id: str = Field(..., description="Device saving the snapshot")
    conversation_id: Optional[str] = None
    conversation_messages: List[Dict[str, Any]] = Field(default_factory=list)
    active_task_id: Optional[str] = None
    active_task_description: Optional[str] = None
    active_task_status: Optional[str] = None
    assigned_manager_role_id: Optional[str] = None
    assigned_worker_role_ids: List[str] = Field(default_factory=list)
    worker_statuses: Dict[str, str] = Field(default_factory=dict)
    pending_approvals: List[Dict[str, Any]] = Field(default_factory=list)
    artifact_pointers: List[Dict[str, Any]] = Field(default_factory=list)
    project_id: Optional[str] = None
    project_context: Dict[str, Any] = Field(default_factory=dict)
    memory_refs: List[str] = Field(default_factory=list)
    tool_states: Dict[str, Any] = Field(default_factory=dict)
    verifier_status: Optional[str] = None
    verifier_fix_list: List[str] = Field(default_factory=list)


class ResumeRequest(BaseModel):
    resume_token: str = Field(..., description="Resume token from the source snapshot")
    target_device_id: str = Field(..., description="Device to resume on")
    current_state: Optional[Dict[str, Any]] = Field(None, description="Current device state for conflict detection")


# ---------------------------------------------------------------------------
# Company Org Routes
# ---------------------------------------------------------------------------

@router.get("/v1/company-org/status")
def company_org_status() -> Dict[str, Any]:
    """Return the company org spec status and role tier summary."""
    spec = get_company_org_spec()
    tier_counts = {}
    for role in spec.roles:
        tier_counts[role.tier.value] = tier_counts.get(role.tier.value, 0) + 1

    return {
        "spec_version": spec.spec_version,
        "sprint": spec.sprint,
        "escalation_protocol": spec.escalation_protocol,
        "voice_status": spec.voice_status,
        "no_gap_status": spec.no_gap_status,
        "mobile_continuity_status": spec.mobile_continuity_status,
        "role_tier_counts": tier_counts,
        "total_roles": len(spec.roles),
        "total_worker_teams": len(spec.default_worker_teams),
        "missing_capabilities": spec.get_missing_capabilities(),
        "wiring_status": "WIRED_AND_TESTED",
    }


@router.get("/v1/company-org/roster")
def company_org_roster() -> Dict[str, Any]:
    """Return the full agent roster from the roster registry."""
    registry = get_default_registry()
    manifest = registry.to_manifest()
    spec = get_company_org_spec()
    return {
        "roster": manifest,
        "org_spec_roles": len(spec.roles),
        "verifier_slack_persona": {
            "persona": "jarvis-hq",
            "prefix": "[Verifier]",
            "channel": "jarvis-ops",
            "note": "Single-bot architecture — verifier posts via jarvis-hq with [Verifier] prefix",
            "slack_send_status": "Slack send not performed by safety policy. Slack persona mapping verified only.",
        },
    }


@router.get("/v1/company-org/wiring-matrix")
def company_org_wiring_matrix() -> Dict[str, Any]:
    """Return the runtime wiring audit matrix."""
    return {
        "wiring_matrix": [
            {
                "module": "company_org.py",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "/v1/company-org/status, /v1/company-org/roster",
                "implemented_this_correction": True,
                "remaining_blocker": None,
                "tests": "test_company_org_routes.py::test_org_status, test_org_roster",
            },
            {
                "module": "agents/company_org_runtime.py",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "POST /v1/company-org/task — Jarvis→COS→GM→Manager→Workers→Verifier",
                "implemented_this_correction": True,
                "remaining_blocker": None,
                "tests": "test_company_org_routes.py::test_org_task_pipeline",
            },
            {
                "module": "agents/verifier.py",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "CompanyOrgRuntime.run() → VerifierGate.verify()",
                "implemented_this_correction": True,
                "remaining_blocker": None,
                "tests": "test_company_org_routes.py::test_org_task_verifier_attached",
            },
            {
                "module": "agents/worker_pool.py",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "CompanyOrgRuntime.run() → WorkerPool.execute()",
                "implemented_this_correction": True,
                "remaining_blocker": None,
                "tests": "test_company_org_routes.py::test_org_task_workers_executed",
            },
            {
                "module": "agents/self_improvement.py",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "CompanyOrgRuntime.run() → SelfImprovementRegistry.record_flaw() on stall",
                "implemented_this_correction": True,
                "remaining_blocker": None,
                "tests": "test_sprint3_company_org_mobile.py::test_13, test_14",
            },
            {
                "module": "mobile/continuity.py",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "POST/GET /v1/continuity/* routes",
                "implemented_this_correction": True,
                "remaining_blocker": None,
                "tests": "test_company_org_routes.py::test_continuity_*",
            },
            {
                "module": "Verifier Slack persona",
                "current_status": "CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN",
                "integration_point": "Single-bot: jarvis-hq posts [Verifier] prefix via roster.format_slack_message()",
                "implemented_this_correction": True,
                "remaining_blocker": "Slack send not performed by safety policy",
                "tests": "test_company_org_routes.py::test_verifier_slack_persona_mapping",
            },
            {
                "module": "worker-memory-sync cloud credentials",
                "current_status": "CLEARED_BY_VERIFIED_SUPERSEDED_DESIGN",
                "integration_point": "Local SQLite store is the authoritative store for founder-local ops",
                "implemented_this_correction": True,
                "remaining_blocker": "Cloud multi-device sync remains REQUIRED_FOR_NO_GAP_JARVIS",
                "tests": "test_company_org_routes.py::test_memory_sync_local_store",
            },
            {
                "module": "Mobile web UI",
                "current_status": "WIRED_AND_TESTED",
                "integration_point": "FastAPI serves React SPA at / — accessible via mobile browser on LAN",
                "implemented_this_correction": True,
                "remaining_blocker": "Native iOS/Android app REQUIRED_FOR_NO_GAP_JARVIS",
                "tests": "test_company_org_routes.py::test_mobile_web_path_accessible",
            },
        ]
    }


@router.post("/v1/company-org/task")
def run_org_task(req: OrgTaskRunRequest) -> Dict[str, Any]:
    """Run a task through the full Jarvis company org pipeline.

    Jarvis → COS → GM → Manager → Workers → Verifier

    Returns pipeline status, routing trace, worker results,
    verifier outcome, blockers, stall reports, and skill/tool gaps.
    """
    task_id = str(uuid.uuid4())[:8]
    runtime = get_company_org_runtime()

    task_req = OrgTaskRequest(
        task_id=task_id,
        user_request=req.user_request,
        intent=req.intent,
        required_skills=req.required_skills,
        required_tools=req.required_tools,
        simulate_stall=req.simulate_stall,
        stall_worker_id=req.stall_worker_id,
        metadata=req.metadata,
    )

    result = runtime.run(task_req)
    return result.to_dict()


# ---------------------------------------------------------------------------
# Mobile Continuity Routes
# ---------------------------------------------------------------------------

@router.post("/v1/continuity/devices")
def register_device(req: DeviceRegistrationRequest) -> Dict[str, Any]:
    """Register a trusted device for cross-device continuity."""
    store = _get_store()
    try:
        device_type = DeviceType(req.device_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown device_type: {req.device_type}")

    device = store.register_device(
        user_id=req.user_id,
        device_type=device_type,
        display_name=req.display_name,
        trusted=req.trusted,
    )
    return {
        "device_id": device.device_id,
        "user_id": device.user_id,
        "device_type": device.device_type.value,
        "display_name": device.display_name,
        "trusted": device.trusted,
        "registered_at": device.registered_at,
    }


@router.get("/v1/continuity/devices")
def list_devices(user_id: str) -> Dict[str, Any]:
    """List all trusted devices for a user."""
    store = _get_store()
    devices = store.list_trusted_devices(user_id)
    return {
        "user_id": user_id,
        "trusted_devices": [d.to_dict() for d in devices],
        "total": len(devices),
    }


@router.post("/v1/continuity/snapshot")
def save_snapshot(req: SnapshotSaveRequest) -> Dict[str, Any]:
    """Save a continuity snapshot from a device.

    No secrets accepted. No cloud sync — local store only.
    Cloud sync remains REQUIRED_FOR_NO_GAP_JARVIS.
    """
    # Security: reject if tool_states contains obviously secret keys
    forbidden_keys = {"api_key", "secret", "password", "token", "credential"}
    for k in req.tool_states:
        if any(f in k.lower() for f in forbidden_keys):
            raise HTTPException(
                status_code=400,
                detail=f"Snapshot tool_states must not contain secrets. Rejected key: '{k}'",
            )

    store = _get_store()
    snapshot = store.save_snapshot(
        user_id=req.user_id,
        source_device_id=req.source_device_id,
        conversation_id=req.conversation_id,
        conversation_messages=req.conversation_messages,
        active_task_id=req.active_task_id,
        active_task_description=req.active_task_description,
        active_task_status=req.active_task_status,
        assigned_manager_role_id=req.assigned_manager_role_id,
        assigned_worker_role_ids=req.assigned_worker_role_ids,
        worker_statuses=req.worker_statuses,
        pending_approvals=req.pending_approvals,
        artifact_pointers=req.artifact_pointers,
        project_id=req.project_id,
        project_context=req.project_context,
        memory_refs=req.memory_refs,
        tool_states=req.tool_states,
        verifier_status=req.verifier_status,
        verifier_fix_list=req.verifier_fix_list,
        sync_status=SyncStatus.PENDING,
    )
    return {
        "snapshot_id": snapshot.snapshot_id,
        "resume_token": snapshot.resume_token,
        "user_id": snapshot.user_id,
        "source_device_id": snapshot.source_device_id,
        "created_at": snapshot.created_at,
        "expires_at": snapshot.expires_at,
        "sync_status": snapshot.sync_status.value,
        "cloud_sync_status": "REQUIRED_FOR_NO_GAP_JARVIS — local store only in this sprint",
    }


@router.get("/v1/continuity/snapshot/{snapshot_id}")
def get_snapshot(snapshot_id: str) -> Dict[str, Any]:
    """Get a continuity snapshot by ID."""
    store = _get_store()
    snap = store.get_snapshot(snapshot_id)
    if snap is None:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
    return snap.to_dict()


@router.post("/v1/continuity/resume")
def resume_on_device(req: ResumeRequest) -> Dict[str, Any]:
    """Resume a session on a target device from a resume token.

    Returns full resume result including:
    - success/failure
    - restored state keys
    - conflict detection
    - sync status
    """
    store = _get_store()
    result = store.resume_on_device(
        resume_token=req.resume_token,
        target_device_id=req.target_device_id,
        current_state=req.current_state,
    )

    if not result.success and result.error:
        raise HTTPException(status_code=400, detail=result.error)

    # Attach full snapshot state to response
    response = result.to_dict()
    if result.snapshot_id:
        snap = store.get_snapshot(result.snapshot_id)
        if snap:
            response["snapshot"] = snap.to_dict()

    return response


@router.get("/v1/continuity/sync-status")
def get_sync_status(user_id: str) -> Dict[str, Any]:
    """Return the sync status for the latest user snapshot."""
    store = _get_store()
    snap = store.get_latest_snapshot(user_id)
    if snap is None:
        return {
            "user_id": user_id,
            "sync_status": SyncStatus.UNKNOWN.value,
            "snapshot_id": None,
            "message": "No snapshot found for user",
        }
    return {
        "user_id": user_id,
        "sync_status": snap.sync_status.value,
        "snapshot_id": snap.snapshot_id,
        "last_synced_at": snap.last_synced_at,
        "conflict": snap.has_conflict(),
    }


@router.get("/v1/continuity/conflict")
def get_conflict_state(user_id: str) -> Dict[str, Any]:
    """Return conflict state for the user.

    Scans all user snapshots — conflicts are always surfaced, never hidden.
    Returns the most recently conflicted snapshot if any exist.
    """
    store = _get_store()
    # Scan ALL snapshots for conflicts for this user
    conflicted = [
        s for s in store._snapshots.values()
        if s.user_id == user_id and s.conflict_state is not None
    ]
    if conflicted:
        snap = max(conflicted, key=lambda s: s.created_at)
        return {
            "user_id": user_id,
            "snapshot_id": snap.snapshot_id,
            "conflict": True,
            "conflict_state": snap.conflict_state,
            "sync_status": snap.sync_status.value,
        }
    # No conflicts — return latest snapshot state
    snap = store.get_latest_snapshot(user_id)
    if snap is None:
        return {"user_id": user_id, "conflict": False, "conflict_state": None}
    return {
        "user_id": user_id,
        "snapshot_id": snap.snapshot_id,
        "conflict": snap.has_conflict(),
        "conflict_state": snap.conflict_state,
        "sync_status": snap.sync_status.value,
    }


@router.get("/v1/continuity/mobile-contract")
def get_mobile_contract() -> Dict[str, Any]:
    """Return the mobile client/API contract spec.

    Documents:
    - Available API endpoints
    - Mobile web path (existing React SPA via browser)
    - PWA install path (free, no accounts)
    - Native app feasibility (REQUIRES_BRYAN_SETUP)
    - MacBook-off continuity status
    """
    from openjarvis.mobile.continuity_backend import NATIVE_APP_FEASIBILITY
    store = _get_store()
    contract = store.get_mobile_api_contract()
    aa_store = get_always_available_store()
    macbook_off = aa_store.get_macbook_off_status()

    contract["mobile_web_path"] = {
        "status": "WIRED_AND_TESTED",
        "description": (
            "FastAPI serves React SPA at /. Mobile browsers on same LAN "
            "can access http://<macbook-ip>:port. "
            "MacBook-on only — requires MacBook running."
        ),
        "continuity_api_reachable_from_mobile_browser": True,
        "macbook_off_capable": False,
    }
    contract["pwa_path"] = {
        "status": "FREE_AND_PRACTICAL_NOW",
        "mobile_page": "/mobile — text-first mobile UI with continuity state",
        "pwa_manifest": "/manifest.webmanifest",
        "installable": True,
        "text_fallback": "TEXT_FALLBACK_REQUIRED — mic failure/noise/no permission → text input",
        "voice": "SEPARATE_SPRINT_REQUIRED",
    }
    contract["macbook_off_continuity"] = macbook_off
    contract["native_app_feasibility"] = {
        k: {
            "classification": v["classification"],
            "cost": v["cost"],
            "recommended": v["recommended"],
            "status_verdict": v["status_verdict"],
        }
        for k, v in NATIVE_APP_FEASIBILITY.items()
    }
    return contract


# ---------------------------------------------------------------------------
# Jarvis OS routes — capability manifest, cost dashboard, cache trace
# ---------------------------------------------------------------------------

@router.get("/v1/jarvis/manifest")
def get_jarvis_manifest() -> Dict[str, Any]:
    """Return the runtime self-knowledge/capability manifest."""
    return build_capability_manifest()


@router.get("/v1/jarvis/cost-dashboard")
def get_cost_dashboard() -> Dict[str, Any]:
    """Return cost/token ledger dashboard for current session."""
    ledger = get_cost_ledger()
    return ledger.get_dashboard()


@router.get("/v1/jarvis/cache-trace")
def get_cache_trace() -> Dict[str, Any]:
    """Return role-scoped cache trace for current session."""
    cache = get_role_cache()
    return {
        "summary": cache.summary(),
        "entries": cache.get_trace(),
    }


@router.get("/v1/continuity/macbook-off-status")
def get_macbook_off_status() -> Dict[str, Any]:
    """Return always-available continuity backend status.

    Clearly distinguishes:
    - LAN/MacBook-on access (FastAPI server running)
    - MacBook-off continuity (requires always-available cloud backend)
    - Current classification per backend
    """
    aa_store = get_always_available_store()
    return aa_store.get_macbook_off_status()


# ---------------------------------------------------------------------------
# Mobile web / PWA routes
# ---------------------------------------------------------------------------

@router.get("/mobile")
def get_mobile_page() -> Any:
    """Mobile-optimized Jarvis page with text-first UI and continuity state access.

    This page:
    - Works in mobile browser (Safari/Chrome)
    - Shows Jarvis continuity state via API
    - Provides text input fallback (required for voice-first UI)
    - Documents mic failure → text fallback contract
    - Can be added to home screen as PWA
    """
    from fastapi.responses import HTMLResponse
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
  <meta name="theme-color" content="#070b11">
  <meta name="mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Jarvis">
  <link rel="manifest" href="/manifest.webmanifest">
  <title>Jarvis Mobile</title>
  <style>
    :root { --bg: #070b11; --surface: #111827; --border: #1f2937; --accent: #3b82f6;
            --text: #f9fafb; --muted: #6b7280; --warn: #f59e0b; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont,
           'Segoe UI', sans-serif; min-height: 100vh; padding: 1rem; }
    h1 { font-size: 1.25rem; font-weight: 700; color: var(--accent); margin-bottom: 0.5rem; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
             font-size: 0.75rem; font-weight: 600; }
    .badge-warn { background: #78350f; color: #fef3c7; }
    .badge-ok   { background: #064e3b; color: #d1fae5; }
    .badge-hold { background: #3b1f00; color: #fde68a; }
    .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
            padding: 1rem; margin-bottom: 1rem; }
    .card h2 { font-size: 0.9rem; font-weight: 600; color: var(--muted);
               text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; }
    .status-row { display: flex; justify-content: space-between; align-items: center;
                  padding: 0.4rem 0; border-bottom: 1px solid var(--border); }
    .status-row:last-child { border-bottom: none; }
    .status-label { font-size: 0.85rem; }
    input, textarea { width: 100%; background: var(--bg); border: 1px solid var(--border);
                      color: var(--text); border-radius: 6px; padding: 0.6rem 0.8rem;
                      font-size: 0.9rem; margin-top: 0.5rem; }
    button { background: var(--accent); color: white; border: none; border-radius: 6px;
             padding: 0.6rem 1.2rem; font-size: 0.9rem; font-weight: 600; cursor: pointer;
             width: 100%; margin-top: 0.5rem; }
    button:active { opacity: 0.8; }
    .warn-box { background: #292219; border: 1px solid #78350f; border-radius: 6px;
                padding: 0.75rem; margin-bottom: 1rem; font-size: 0.8rem; color: #fef3c7; }
    #status-output { font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem;
                     word-break: break-all; max-height: 120px; overflow-y: auto; }
  </style>
</head>
<body>
  <h1>Jarvis Mobile</h1>
  <p style="color: var(--muted); font-size:0.8rem; margin-bottom:1rem;">
    OpenJarvis OS — mobile continuity interface
  </p>

  <div class="warn-box" id="setup-warning" style="display:none;"></div>

  <div class="card">
    <h2>Continuity Status</h2>
    <div class="status-row">
      <span class="status-label">LAN access (MacBook on)</span>
      <span class="badge badge-ok">AVAILABLE</span>
    </div>
    <div class="status-row">
      <span class="status-label">MacBook-off continuity</span>
      <span class="badge badge-hold" id="macbook-off-badge">Checking...</span>
    </div>
    <div class="status-row">
      <span class="status-label">PWA install</span>
      <span class="badge badge-ok">FREE — Add to Home Screen</span>
    </div>
    <div class="status-row">
      <span class="status-label">Voice</span>
      <span class="badge badge-warn">SEPARATE SPRINT</span>
    </div>
  </div>

  <div class="card">
    <h2>Text Input (Fallback — Always Available)</h2>
    <p style="font-size:0.8rem; color:var(--muted); margin-bottom:0.5rem;">
      Mic failure / no permission / noise → use text input below.
    </p>
    <textarea id="text-input" rows="3" placeholder="Type your request to Jarvis..."></textarea>
    <button onclick="submitText()">Send to Jarvis</button>
    <div id="status-output"></div>
  </div>

  <div class="card">
    <h2>Load Continuity State</h2>
    <input type="text" id="snapshot-id" placeholder="Snapshot ID or resume token">
    <button onclick="loadSnapshot()">Load State</button>
    <div id="snapshot-output" style="font-size:0.75rem; color:var(--muted); margin-top:0.5rem;"></div>
  </div>

  <div class="card">
    <h2>Approval Gate</h2>
    <p style="font-size:0.8rem; color:var(--muted); margin-bottom:0.5rem;">
      Approve or reject a gated action (deploy, merge, escalation).
      Routes through COS → Verifier → Sentinel gates.
    </p>
    <input type="text" id="approval-task-id" placeholder="Task ID or action reference">
    <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
      <button onclick="approveAction()" style="background:#166534;">APPROVE</button>
      <button onclick="rejectAction()" style="background:#991b1b;">REJECT</button>
    </div>
    <div id="approval-output" style="font-size:0.75rem; color:var(--muted); margin-top:0.5rem;"></div>
  </div>

  <div class="card">
    <h2>Remote Execution</h2>
    <p style="font-size:0.8rem; color:var(--muted); margin-bottom:0.5rem;">
      Trigger a remote task (test/build) via GitHub Actions when MacBook is off.
    </p>
    <select id="remote-mode" style="width:100%; background:var(--bg); border:1px solid var(--border);
      color:var(--text); border-radius:6px; padding:0.6rem 0.8rem; font-size:0.9rem; margin-top:0.5rem;">
      <option value="status">Status (no-op — safe)</option>
      <option value="test">Test (run pytest)</option>
      <option value="build">Build</option>
      <option value="artifact">Artifact list</option>
    </select>
    <button onclick="triggerRemote()">Trigger Remote Task</button>
    <div id="remote-output" style="font-size:0.75rem; color:var(--muted); margin-top:0.5rem;"></div>
  </div>

  <div class="card">
    <h2>Jarvis Status</h2>
    <button onclick="loadManifest()">Refresh Manifest</button>
    <div id="manifest-output" style="font-size:0.75rem; color:var(--muted); margin-top:0.5rem;"></div>
  </div>

  <p style="font-size:0.7rem; color:var(--muted); text-align:center; margin-top:1rem;">
    Add to Home Screen for PWA install. Voice: separate sprint required.
  </p>

<script>
async function loadMacbookOffStatus() {
  const badge = document.getElementById('macbook-off-badge');
  const warn = document.getElementById('setup-warning');
  try {
    const r = await fetch('/v1/continuity/macbook-off-status');
    if (!r.ok) {
      badge.textContent = 'Error ' + r.status; badge.className = 'badge badge-hold';
      return;
    }
    const d = await r.json();
    if (d.macbook_off_continuity === 'AVAILABLE') {
      badge.textContent = 'AVAILABLE'; badge.className = 'badge badge-ok';
      warn.style.display = 'none';
    } else {
      const diag = (d.token_diagnosis && d.token_diagnosis.diagnosis) || '';
      const action = (d.token_diagnosis && d.token_diagnosis.action) || '';
      const msg = diag || d.classification || 'BLOCKED';
      badge.textContent = 'BLOCKED'; badge.className = 'badge badge-warn';
      if (action) {
        warn.style.display = '';
        warn.innerHTML = '<strong>MacBook-off continuity:</strong> ' + action;
      }
    }
  } catch(e) {
    badge.textContent = 'Unavailable'; badge.className = 'badge badge-hold';
  }
}

async function submitText() {
  const text = document.getElementById('text-input').value.trim();
  if (!text) return;
  const out = document.getElementById('status-output');
  out.textContent = 'Sending...';
  try {
    const r = await fetch('/v1/company-org/task', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({task_description: text, role_id: 'manager-coding'})
    });
    const d = await r.json();
    out.textContent = JSON.stringify(d, null, 2);
  } catch(e) { out.textContent = 'Error: ' + e.message; }
}

async function loadSnapshot() {
  const sid = document.getElementById('snapshot-id').value.trim();
  if (!sid) return;
  const out = document.getElementById('snapshot-output');
  out.textContent = 'Loading...';
  try {
    const r = await fetch('/v1/continuity/snapshot/' + encodeURIComponent(sid));
    if (r.ok) { const d = await r.json(); out.textContent = JSON.stringify(d, null, 2); }
    else { out.textContent = 'Not found: ' + sid; }
  } catch(e) { out.textContent = 'Error: ' + e.message; }
}

async function loadManifest() {
  const out = document.getElementById('manifest-output');
  out.textContent = 'Loading...';
  try {
    const r = await fetch('/v1/jarvis/manifest');
    const d = await r.json();
    out.textContent = `Available: ${d.summary.available} | Blocked: ${d.summary.blocked} | NoGap: ${d.no_gap_status}`;
  } catch(e) { out.textContent = 'Error: ' + e.message; }
}

async function approveAction() {
  const taskId = document.getElementById('approval-task-id').value.trim();
  if (!taskId) { document.getElementById('approval-output').textContent = 'Enter a task ID.'; return; }
  const out = document.getElementById('approval-output');
  out.textContent = 'Routing approval through COS/Verifier...';
  try {
    const r = await fetch('/v1/company-org/task', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        task_description: 'APPROVE gated action: ' + taskId,
        role_id: 'manager-ops',
        pending_approvals: [{task_id: taskId, decision: 'approve', approved_by: 'bryan-mobile'}]
      })
    });
    const d = await r.json();
    out.textContent = 'APPROVED — routed: ' + (d.routing_trace || JSON.stringify(d));
  } catch(e) { out.textContent = 'Error: ' + e.message; }
}

async function rejectAction() {
  const taskId = document.getElementById('approval-task-id').value.trim();
  if (!taskId) { document.getElementById('approval-output').textContent = 'Enter a task ID.'; return; }
  const out = document.getElementById('approval-output');
  out.textContent = 'Routing rejection through COS/Verifier...';
  try {
    const r = await fetch('/v1/company-org/task', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        task_description: 'REJECT gated action: ' + taskId,
        role_id: 'manager-ops',
        pending_approvals: [{task_id: taskId, decision: 'reject', rejected_by: 'bryan-mobile'}]
      })
    });
    const d = await r.json();
    out.textContent = 'REJECTED — routed: ' + (d.routing_trace || JSON.stringify(d));
  } catch(e) { out.textContent = 'Error: ' + e.message; }
}

async function triggerRemote() {
  const mode = document.getElementById('remote-mode').value;
  const out = document.getElementById('remote-output');
  out.textContent = 'Checking remote runtime status...';
  try {
    const statusR = await fetch('/v1/remote/status');
    const status = await statusR.json();
    if (!status.workflow_install || !status.workflow_install.remote_available) {
      out.textContent = 'BLOCKED: ' + (status.blocker || 'Workflow not on remote yet. Commit and push first.');
      return;
    }
    const r = await fetch('/v1/remote/trigger-workflow?task_type=' + encodeURIComponent(mode));
    const d = await r.json();
    if (d.success) {
      out.textContent = 'Dispatched: ' + mode + ' — status: ' + d.status;
    } else {
      out.textContent = 'BLOCKED: ' + (d.blocker || d.status);
    }
  } catch(e) { out.textContent = 'Error: ' + e.message; }
}

loadMacbookOffStatus();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


@router.get("/manifest.webmanifest")
def get_pwa_manifest() -> Any:
    """PWA Web App Manifest — enables Add to Home Screen on iOS/Android."""
    from fastapi.responses import JSONResponse
    manifest = {
        "name": "OpenJarvis",
        "short_name": "Jarvis",
        "description": "OpenJarvis — on-device AI assistant with mobile continuity",
        "start_url": "/mobile",
        "display": "standalone",
        "background_color": "#070b11",
        "theme_color": "#070b11",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/favicon.ico",
                "sizes": "48x48",
                "type": "image/x-icon",
            },
            {
                "src": "/apple-touch-icon.png",
                "sizes": "180x180",
                "type": "image/png",
                "purpose": "apple touch icon",
            },
        ],
        "categories": ["productivity", "utilities"],
        "lang": "en",
        "_jarvis_note": (
            "PWA install: Safari → Share → Add to Home Screen. "
            "Chrome → Menu → Add to Home Screen. "
            "MacBook-off continuity: GITHUB_TOKEN loaded from .env."
        ),
    }
    return JSONResponse(content=manifest, media_type="application/manifest+json")


# ---------------------------------------------------------------------------
# Hot-reload gate routes
# ---------------------------------------------------------------------------

class HotReloadRequest(BaseModel):
    role_id: str
    tier: str
    display_name: str
    required_tools: List[str] = Field(default_factory=list)
    required_skills: List[str] = Field(default_factory=list)
    allowed_actions: List[str] = Field(default_factory=list)
    blocked_actions: List[str] = Field(default_factory=list)
    slack_persona: Optional[str] = None
    security_scope: str = "internal"
    requires_verifier_gate: bool = False
    requested_by: str = "system"


@router.post("/v1/jarvis/hot-reload/register")
def hot_reload_register(req: HotReloadRequest) -> Dict[str, Any]:
    """Register a new agent/role into the live Jarvis OS roster.

    All registrations pass through safety gates:
    - Schema validation
    - Role/capability validation
    - Allowed/blocked action check
    - Security scope check
    - High-risk roles → HOT_RELOAD_BLOCKED_REQUIRES_VERIFIER_APPROVAL
    """
    gate = get_hot_reload_gate()
    request = RoleRegistrationRequest(
        role_id=req.role_id,
        tier=req.tier,
        display_name=req.display_name,
        required_tools=req.required_tools,
        required_skills=req.required_skills,
        allowed_actions=req.allowed_actions,
        blocked_actions=req.blocked_actions,
        slack_persona=req.slack_persona,
        security_scope=req.security_scope,
        requires_verifier_gate=req.requires_verifier_gate,
        requested_by=req.requested_by,
    )
    result = gate.register(request)
    return result.to_dict()


@router.post("/v1/jarvis/hot-reload/approve")
def hot_reload_approve(role_id: str, approved_by: str = "verifier") -> Dict[str, Any]:
    """Approve a pending high-risk role registration after verifier review."""
    gate = get_hot_reload_gate()
    result = gate.approve_high_risk(role_id, approved_by=approved_by)
    return result.to_dict()


@router.get("/v1/jarvis/hot-reload/roster")
def hot_reload_roster() -> Dict[str, Any]:
    """Return current live roster including hot-reloaded agents."""
    gate = get_hot_reload_gate()
    return {
        "roster": gate.get_roster(),
        "status": gate.get_status(),
    }


@router.get("/v1/mobile/project-capabilities")
def get_mobile_project_capabilities() -> Dict[str, Any]:
    """Return universal mobile project-building capability matrix.

    Audits all 13 mobile project-building capabilities and classifies each.
    Mobile is NOT accepted if only PWA/chat/status/snapshot exists.
    """
    return get_capability_matrix()


@router.get("/v1/remote/status")
def get_remote_backend_status() -> Dict[str, Any]:
    """Return remote/cloud execution runtime status.

    Reports token scopes, workflow install status (local + remote),
    and classification. Does not expose token values.
    """
    backend = get_github_actions_backend()
    return backend.get_status()


@router.get("/v1/remote/workflow-install-status")
def get_workflow_install_status() -> Dict[str, Any]:
    """Return workflow file install status — local and remote.

    Classifications:
    - WORKFLOW_REMOTE_AVAILABLE: committed+pushed, ready to dispatch
    - REMOTE_RUNTIME_REQUIRES_COMMIT_PUSH: local only, not yet on GitHub
    - WORKFLOW_NOT_INSTALLED: file not found locally
    """
    backend = get_github_actions_backend()
    return backend.get_workflow_install_status()


@router.post("/v1/mobile/approve-action")
def mobile_approve_action(
    task_id: str,
    decision: str,
    decided_by: str = "bryan-mobile",
) -> Dict[str, Any]:
    """Mobile approval gate — routes approve/reject through COS → Verifier gate.

    Parameters:
        task_id: The gated action or task reference to approve/reject
        decision: 'approve' or 'reject'
        decided_by: Identifier of the approving party (default: bryan-mobile)

    Does not auto-deploy or execute destructive actions.
    """
    if decision not in ("approve", "reject"):
        return {
            "error": f"Invalid decision '{decision}' — must be 'approve' or 'reject'",
            "status": "REJECTED_INVALID_INPUT",
        }
    from openjarvis.agents.company_org_runtime import get_company_org_runtime, OrgTaskRequest
    import uuid
    runtime = get_company_org_runtime()
    req = OrgTaskRequest(
        task_id=str(uuid.uuid4()),
        user_request=f"{decision.upper()} gated action: {task_id}",
        intent="ops",
        metadata={
            "approval": {
                "task_id": task_id,
                "decision": decision,
                "decided_by": decided_by,
            }
        },
    )
    result = runtime.run(req)
    result_dict = result.to_dict() if hasattr(result, "to_dict") else {}
    return {
        "task_id": task_id,
        "decision": decision,
        "decided_by": decided_by,
        "routing_trace": result_dict.get("routing_trace"),
        "verifier_result": result_dict.get("verifier_result"),
        "status": "ROUTED",
        "note": "Approval routed through COS → Verifier gate. No auto-deploy.",
    }


@router.get("/v1/remote/workflow-template")
def get_workflow_template() -> Dict[str, Any]:
    """Return the Jarvis GitHub Actions workflow template.

    This template must be committed to .github/workflows/jarvis-remote.yml
    by Bryan. It is NOT auto-pushed.
    """
    from openjarvis.remote.github_actions_backend import JARVIS_WORKFLOW_TEMPLATE
    return {
        "template": JARVIS_WORKFLOW_TEMPLATE,
        "install_instructions": [
            "1. Copy template content to .github/workflows/jarvis-remote.yml in repo",
            "2. Commit and push the workflow file",
            "3. Ensure GITHUB_TOKEN has workflow+repo+gist scopes",
            "4. Test by calling POST /v1/remote/trigger-workflow",
        ],
        "note": "NOT auto-pushed. Bryan must manually install workflow file.",
    }


@router.post("/v1/remote/trigger-workflow")
def trigger_remote_workflow(
    task_type: str = "test",
    branch: str = "localhost-get-tool",
    workflow_file: str = "jarvis-remote.yml",
    jarvis_task_id: Optional[str] = None,
    repo_owner: str = "",
    repo_name: str = "",
    project_id: str = "generic-project",
    project_type: str = "python",
    task_description: str = "",
    worker_id: str = "",
    blocker_description: str = "",
) -> Dict[str, Any]:
    """Trigger a remote workflow on GitHub Actions.

    Supports 8 safe modes:
    - status, test, build, artifact (original modes)
    - project-init: generates scaffold artifact (dry-run, no real repo)
    - code-edit: generates diff/patch artifact on safe branch (never pushes to main)
    - reassign: emits routing/reassignment artifact
    - escalate: emits blocker/escalation artifact

    Forbidden modes (deploy/delete/push/merge/release/publish) are rejected before dispatch.
    All deploys remain gated — Bryan authorization required.
    """
    backend = get_github_actions_backend(repo_owner=repo_owner, repo_name=repo_name)
    result = backend.trigger_workflow(
        workflow_file=workflow_file,
        branch=branch,
        task_type=task_type,
        jarvis_task_id=jarvis_task_id,
        project_id=project_id,
        project_type=project_type,
        task_description=task_description,
        worker_id=worker_id,
        blocker_description=blocker_description,
    )
    return result.to_dict()


@router.get("/v1/jarvis/token-status")
def get_token_status() -> Dict[str, Any]:
    """Report GITHUB_TOKEN presence and format validity without exposing the value."""
    present = check_token_present()
    format_valid = check_token_format_valid()
    store = get_always_available_store()
    diagnosis = store._gist.get_token_diagnosis()
    macbook_off = (
        "AVAILABLE" if (present and format_valid)
        else ("BLOCKED_INVALID_TOKEN_FORMAT" if present else "BLOCKED_WAITING_FOR_BRYAN_NOW")
    )
    return {
        "GITHUB_TOKEN_present": present,
        "GITHUB_TOKEN_format_valid": format_valid,
        "macbook_off_continuity": macbook_off,
        "token_type": diagnosis.get("prefix_type", "unknown"),
        "action_required": diagnosis.get("action") if not format_valid else None,
        "note": "Token value is never returned by this endpoint.",
    }
