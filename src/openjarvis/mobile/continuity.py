"""Jarvis Mobile Continuity — Cross-device session foundation.

Bryan must be able to start work on MacBook, shut it off, and continue on
mobile with the same Jarvis state without manual prompt transfer; and vice versa.

Implements:
  1. User/device identity model
  2. Device model (MacBook, mobile, etc.)
  3. Continuity snapshot (full state capture)
  4. Resume token / resume pointer
  5. Sync status
  6. Conflict policy (surface conflict, never hide it)
  7. Offline/degraded policy
  8. Security policy for trusted devices
  9. Mobile client/API contract
  10. Cross-device snapshot save and resume

IMPORTANT — what is NOT complete yet:
  - Full native mobile UI (React Native / iOS / Android app)
  - Real mobile push notification integration
  - Real device pairing UX
  These are classified REQUIRED_FOR_NO_GAP_JARVIS.

This module provides the backend session/snapshot contract only.

Sprint: Full No-Gap Jarvis — Combined Sprint 3
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Device types
# ---------------------------------------------------------------------------

class DeviceType(str, Enum):
    MACBOOK = "macbook"
    IPHONE = "iphone"
    IPAD = "ipad"
    ANDROID = "android"
    WEB = "web"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Device model
# ---------------------------------------------------------------------------

@dataclass
class DeviceModel:
    """A registered trusted device."""

    device_id: str
    user_id: str
    device_type: DeviceType
    display_name: str
    trusted: bool
    registered_at: float = field(default_factory=time.time)
    last_seen_at: Optional[float] = None
    security_token_hash: Optional[str] = None   # hashed token, never raw

    def touch(self) -> None:
        self.last_seen_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "device_type": self.device_type.value,
            "display_name": self.display_name,
            "trusted": self.trusted,
            "registered_at": self.registered_at,
            "last_seen_at": self.last_seen_at,
        }


# ---------------------------------------------------------------------------
# Sync status
# ---------------------------------------------------------------------------

class SyncStatus(str, Enum):
    SYNCED = "synced"
    PENDING = "pending"
    CONFLICT = "conflict"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------

class ConflictPolicy(str, Enum):
    SURFACE_CONFLICT = "surface_conflict"   # always surface — never hide
    LAST_WRITE_WINS = "last_write_wins"
    MANUAL_RESOLUTION = "manual_resolution"


class OfflinePolicy(str, Enum):
    QUEUE_AND_SYNC_ON_RECONNECT = "queue_and_sync_on_reconnect"
    READ_ONLY_OFFLINE = "read_only_offline"
    DEGRADE_GRACEFULLY = "degrade_gracefully"


class SecurityPolicy(str, Enum):
    TRUSTED_DEVICE_REQUIRED = "trusted_device_required"
    TOKEN_REQUIRED = "token_required"
    OWNER_ONLY = "owner_only"


# ---------------------------------------------------------------------------
# Continuity snapshot
# ---------------------------------------------------------------------------

@dataclass
class ContinuitySnapshot:
    """Full cross-device continuity state snapshot.

    Contains all required state for seamless MacBook ↔ mobile resume.
    """

    snapshot_id: str
    user_id: str
    source_device_id: str
    resume_token: str                       # opaque resume pointer

    # Active conversation / thread
    conversation_id: Optional[str]
    conversation_messages: List[Dict[str, Any]]   # last N messages

    # Active task / workflow
    active_task_id: Optional[str]
    active_task_description: Optional[str]
    active_task_status: Optional[str]

    # Manager / worker assignment
    assigned_manager_role_id: Optional[str]
    assigned_worker_role_ids: List[str]
    worker_statuses: Dict[str, str]          # worker_role_id → status

    # Pending approvals
    pending_approvals: List[Dict[str, Any]]

    # Artifacts / files
    artifact_pointers: List[Dict[str, Any]]  # {"task_id": ..., "path": ..., "type": ...}

    # Project context
    project_id: Optional[str]
    project_context: Dict[str, Any]

    # Memory references
    memory_refs: List[str]                   # memory entry IDs relevant to current task

    # Tool / connector state
    tool_states: Dict[str, Any]              # safe subset — no secrets

    # Sync / conflict
    sync_status: SyncStatus
    conflict_state: Optional[Dict[str, Any]]  # None = no conflict

    # Verifier status
    verifier_status: Optional[str]
    verifier_fix_list: List[str]

    # Cache / cost / capability references (one-system integration)
    cache_state_ref: Optional[str] = None       # reference to role-scoped cache entry
    cost_task_ref: Optional[str] = None         # task_id for cost ledger lookup
    capability_status_ref: Optional[str] = None # e.g. "no_gap=HOLD"
    blocker_list: List[str] = field(default_factory=list)  # active blockers at snapshot time

    # Session metadata
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    last_synced_at: Optional[float] = None

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def has_conflict(self) -> bool:
        return self.conflict_state is not None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "user_id": self.user_id,
            "source_device_id": self.source_device_id,
            "resume_token": self.resume_token,
            "conversation_id": self.conversation_id,
            "conversation_messages": self.conversation_messages,
            "active_task_id": self.active_task_id,
            "active_task_description": self.active_task_description,
            "active_task_status": self.active_task_status,
            "assigned_manager_role_id": self.assigned_manager_role_id,
            "assigned_worker_role_ids": self.assigned_worker_role_ids,
            "worker_statuses": self.worker_statuses,
            "pending_approvals": self.pending_approvals,
            "artifact_pointers": self.artifact_pointers,
            "project_id": self.project_id,
            "project_context": self.project_context,
            "memory_refs": self.memory_refs,
            "tool_states": self.tool_states,
            "sync_status": self.sync_status.value,
            "conflict_state": self.conflict_state,
            "verifier_status": self.verifier_status,
            "verifier_fix_list": self.verifier_fix_list,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_synced_at": self.last_synced_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContinuitySnapshot":
        return cls(
            snapshot_id=data["snapshot_id"],
            user_id=data["user_id"],
            source_device_id=data["source_device_id"],
            resume_token=data["resume_token"],
            conversation_id=data.get("conversation_id"),
            conversation_messages=data.get("conversation_messages", []),
            active_task_id=data.get("active_task_id"),
            active_task_description=data.get("active_task_description"),
            active_task_status=data.get("active_task_status"),
            assigned_manager_role_id=data.get("assigned_manager_role_id"),
            assigned_worker_role_ids=data.get("assigned_worker_role_ids", []),
            worker_statuses=data.get("worker_statuses", {}),
            pending_approvals=data.get("pending_approvals", []),
            artifact_pointers=data.get("artifact_pointers", []),
            project_id=data.get("project_id"),
            project_context=data.get("project_context", {}),
            memory_refs=data.get("memory_refs", []),
            tool_states=data.get("tool_states", {}),
            sync_status=SyncStatus(data.get("sync_status", SyncStatus.UNKNOWN.value)),
            conflict_state=data.get("conflict_state"),
            verifier_status=data.get("verifier_status"),
            verifier_fix_list=data.get("verifier_fix_list", []),
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            last_synced_at=data.get("last_synced_at"),
        )


# ---------------------------------------------------------------------------
# Resume result
# ---------------------------------------------------------------------------

@dataclass
class ResumeResult:
    """Result of attempting to resume from a continuity snapshot."""

    success: bool
    snapshot_id: Optional[str]
    device_id: str
    conflict_detected: bool
    conflict_description: Optional[str]
    sync_status: SyncStatus
    restored_state_keys: List[str]
    missing_state_keys: List[str]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "snapshot_id": self.snapshot_id,
            "device_id": self.device_id,
            "conflict_detected": self.conflict_detected,
            "conflict_description": self.conflict_description,
            "sync_status": self.sync_status.value,
            "restored_state_keys": self.restored_state_keys,
            "missing_state_keys": self.missing_state_keys,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Continuity store
# ---------------------------------------------------------------------------

class ContinuityStore:
    """Manages device registration, snapshot save/load, and cross-device resume.

    This is the backend contract. Mobile UI integration is REQUIRED_FOR_NO_GAP_JARVIS.

    Policies:
      - Conflicts are always surfaced — never hidden.
      - Expired snapshots are rejected.
      - Untrusted devices cannot resume protected snapshots.
      - No secrets in snapshot (tool_states must be scrubbed before save).
    """

    REQUIRED_SNAPSHOT_KEYS = [
        "conversation_id",
        "active_task_id",
        "active_task_status",
        "sync_status",
        "worker_statuses",
    ]

    def __init__(
        self,
        conflict_policy: ConflictPolicy = ConflictPolicy.SURFACE_CONFLICT,
        offline_policy: OfflinePolicy = OfflinePolicy.DEGRADE_GRACEFULLY,
        security_policy: SecurityPolicy = SecurityPolicy.TRUSTED_DEVICE_REQUIRED,
        snapshot_ttl_seconds: int = 86400,   # 24h default
    ) -> None:
        self._conflict_policy = conflict_policy
        self._offline_policy = offline_policy
        self._security_policy = security_policy
        self._snapshot_ttl = snapshot_ttl_seconds

        self._devices: Dict[str, DeviceModel] = {}
        self._snapshots: Dict[str, ContinuitySnapshot] = {}
        self._resume_tokens: Dict[str, str] = {}   # token → snapshot_id

    # ------------------------------------------------------------------
    # Device management
    # ------------------------------------------------------------------

    def register_device(
        self,
        user_id: str,
        device_type: DeviceType,
        display_name: str,
        trusted: bool = True,
    ) -> DeviceModel:
        device_id = f"device-{str(uuid.uuid4())[:8]}"
        device = DeviceModel(
            device_id=device_id,
            user_id=user_id,
            device_type=device_type,
            display_name=display_name,
            trusted=trusted,
        )
        self._devices[device_id] = device
        return device

    def get_device(self, device_id: str) -> Optional[DeviceModel]:
        return self._devices.get(device_id)

    def list_trusted_devices(self, user_id: str) -> List[DeviceModel]:
        return [d for d in self._devices.values() if d.user_id == user_id and d.trusted]

    # ------------------------------------------------------------------
    # Snapshot save
    # ------------------------------------------------------------------

    def save_snapshot(
        self,
        user_id: str,
        source_device_id: str,
        *,
        conversation_id: Optional[str] = None,
        conversation_messages: Optional[List[Dict[str, Any]]] = None,
        active_task_id: Optional[str] = None,
        active_task_description: Optional[str] = None,
        active_task_status: Optional[str] = None,
        assigned_manager_role_id: Optional[str] = None,
        assigned_worker_role_ids: Optional[List[str]] = None,
        worker_statuses: Optional[Dict[str, str]] = None,
        pending_approvals: Optional[List[Dict[str, Any]]] = None,
        artifact_pointers: Optional[List[Dict[str, Any]]] = None,
        project_id: Optional[str] = None,
        project_context: Optional[Dict[str, Any]] = None,
        memory_refs: Optional[List[str]] = None,
        tool_states: Optional[Dict[str, Any]] = None,
        verifier_status: Optional[str] = None,
        verifier_fix_list: Optional[List[str]] = None,
        sync_status: SyncStatus = SyncStatus.PENDING,
    ) -> ContinuitySnapshot:
        """Save a continuity snapshot for cross-device resume."""

        device = self._devices.get(source_device_id)
        if device:
            device.touch()

        snapshot_id = f"snap-{str(uuid.uuid4())[:8]}"
        resume_token = str(uuid.uuid4())

        snapshot = ContinuitySnapshot(
            snapshot_id=snapshot_id,
            user_id=user_id,
            source_device_id=source_device_id,
            resume_token=resume_token,
            conversation_id=conversation_id,
            conversation_messages=conversation_messages or [],
            active_task_id=active_task_id,
            active_task_description=active_task_description,
            active_task_status=active_task_status,
            assigned_manager_role_id=assigned_manager_role_id,
            assigned_worker_role_ids=assigned_worker_role_ids or [],
            worker_statuses=worker_statuses or {},
            pending_approvals=pending_approvals or [],
            artifact_pointers=artifact_pointers or [],
            project_id=project_id,
            project_context=project_context or {},
            memory_refs=memory_refs or [],
            tool_states=tool_states or {},
            sync_status=sync_status,
            conflict_state=None,
            verifier_status=verifier_status,
            verifier_fix_list=verifier_fix_list or [],
            expires_at=time.time() + self._snapshot_ttl,
        )

        self._snapshots[snapshot_id] = snapshot
        self._resume_tokens[resume_token] = snapshot_id

        return snapshot

    # ------------------------------------------------------------------
    # Snapshot load
    # ------------------------------------------------------------------

    def get_snapshot(self, snapshot_id: str) -> Optional[ContinuitySnapshot]:
        return self._snapshots.get(snapshot_id)

    def get_snapshot_by_token(self, resume_token: str) -> Optional[ContinuitySnapshot]:
        snapshot_id = self._resume_tokens.get(resume_token)
        if snapshot_id:
            return self._snapshots.get(snapshot_id)
        return None

    def get_latest_snapshot(self, user_id: str) -> Optional[ContinuitySnapshot]:
        user_snaps = [
            s for s in self._snapshots.values()
            if s.user_id == user_id and not s.is_expired()
        ]
        if not user_snaps:
            return None
        return max(user_snaps, key=lambda s: s.created_at)

    # ------------------------------------------------------------------
    # Cross-device resume
    # ------------------------------------------------------------------

    def resume_on_device(
        self,
        resume_token: str,
        target_device_id: str,
        *,
        current_state: Optional[Dict[str, Any]] = None,
    ) -> ResumeResult:
        """Resume a session on a target device from a resume token.

        Checks:
        1. Token valid and not expired
        2. Device is trusted
        3. Conflict detection (if current_state provided)
        4. Surfaces conflict — never hides it
        """
        snapshot = self.get_snapshot_by_token(resume_token)

        if snapshot is None:
            return ResumeResult(
                success=False,
                snapshot_id=None,
                device_id=target_device_id,
                conflict_detected=False,
                conflict_description=None,
                sync_status=SyncStatus.UNKNOWN,
                restored_state_keys=[],
                missing_state_keys=self.REQUIRED_SNAPSHOT_KEYS,
                error="Invalid or unknown resume token.",
            )

        if snapshot.is_expired():
            return ResumeResult(
                success=False,
                snapshot_id=snapshot.snapshot_id,
                device_id=target_device_id,
                conflict_detected=False,
                conflict_description=None,
                sync_status=SyncStatus.DEGRADED,
                restored_state_keys=[],
                missing_state_keys=self.REQUIRED_SNAPSHOT_KEYS,
                error=f"Snapshot {snapshot.snapshot_id} is expired.",
            )

        # Trust check
        target_device = self._devices.get(target_device_id)
        if self._security_policy == SecurityPolicy.TRUSTED_DEVICE_REQUIRED:
            if target_device is None or not target_device.trusted:
                return ResumeResult(
                    success=False,
                    snapshot_id=snapshot.snapshot_id,
                    device_id=target_device_id,
                    conflict_detected=False,
                    conflict_description=None,
                    sync_status=SyncStatus.UNKNOWN,
                    restored_state_keys=[],
                    missing_state_keys=self.REQUIRED_SNAPSHOT_KEYS,
                    error=f"Device '{target_device_id}' is not registered as trusted.",
                )

        # Conflict detection
        conflict_detected = False
        conflict_description = None
        if current_state and self._conflict_policy == ConflictPolicy.SURFACE_CONFLICT:
            # Check if target device has a newer snapshot than the resume source
            device_snaps = [
                s for s in self._snapshots.values()
                if s.source_device_id == target_device_id
                and s.user_id == snapshot.user_id
                and s.created_at > snapshot.created_at
            ]
            if device_snaps:
                conflict_detected = True
                conflict_description = (
                    f"Device '{target_device_id}' has {len(device_snaps)} snapshot(s) "
                    f"newer than the resume snapshot '{snapshot.snapshot_id}'. "
                    "Conflict must be resolved before resuming."
                )
                snapshot.conflict_state = {
                    "newer_device_snapshots": [s.snapshot_id for s in device_snaps],
                    "description": conflict_description,
                }

        # Compute what's restored vs missing
        snap_dict = snapshot.to_dict()
        restored = [k for k in self.REQUIRED_SNAPSHOT_KEYS if snap_dict.get(k) is not None]
        missing = [k for k in self.REQUIRED_SNAPSHOT_KEYS if snap_dict.get(k) is None]

        # Update device touch
        if target_device:
            target_device.touch()

        snapshot.last_synced_at = time.time()
        snapshot.sync_status = SyncStatus.CONFLICT if conflict_detected else SyncStatus.SYNCED

        return ResumeResult(
            success=True,
            snapshot_id=snapshot.snapshot_id,
            device_id=target_device_id,
            conflict_detected=conflict_detected,
            conflict_description=conflict_description,
            sync_status=snapshot.sync_status,
            restored_state_keys=restored,
            missing_state_keys=missing,
        )

    # ------------------------------------------------------------------
    # Mobile client API contract
    # ------------------------------------------------------------------

    def get_mobile_api_contract(self) -> Dict[str, Any]:
        """Return the mobile client/API contract spec.

        This is the contract that a native mobile app must implement.
        Full native mobile UI is REQUIRED_FOR_NO_GAP_JARVIS.
        """
        return {
            "contract_version": "1.0.0",
            "status": "BACKEND_ONLY — mobile UI REQUIRED_FOR_NO_GAP_JARVIS",
            "endpoints": [
                {
                    "name": "POST /continuity/snapshot",
                    "description": "Save continuity snapshot from current device",
                    "auth": "trusted_device_token",
                    "body": "ContinuitySnapshot",
                },
                {
                    "name": "GET /continuity/resume/{resume_token}",
                    "description": "Retrieve snapshot for cross-device resume",
                    "auth": "trusted_device_token",
                    "response": "ContinuitySnapshot",
                },
                {
                    "name": "GET /continuity/latest",
                    "description": "Get latest snapshot for the authenticated user",
                    "auth": "trusted_device_token",
                    "response": "ContinuitySnapshot",
                },
                {
                    "name": "POST /devices/register",
                    "description": "Register a new trusted device",
                    "auth": "owner_token",
                    "body": "DeviceRegistrationRequest",
                },
            ],
            "conflict_policy": self._conflict_policy.value,
            "offline_policy": self._offline_policy.value,
            "security_policy": self._security_policy.value,
            "mobile_ui_status": "REQUIRED_FOR_NO_GAP_JARVIS",
            "mobile_ui_remaining": [
                "React Native / iOS / Android native app",
                "Real mobile push notifications",
                "Device pairing UX",
                "Mobile-specific approval UI",
            ],
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_STORE: Optional[ContinuityStore] = None


def get_continuity_store() -> ContinuityStore:
    global _STORE
    if _STORE is None:
        _STORE = ContinuityStore()
    return _STORE


__all__ = [
    "DeviceType",
    "DeviceModel",
    "SyncStatus",
    "ConflictPolicy",
    "OfflinePolicy",
    "SecurityPolicy",
    "ContinuitySnapshot",
    "ResumeResult",
    "ContinuityStore",
    "get_continuity_store",
]
