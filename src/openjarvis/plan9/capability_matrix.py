"""Plan 9 — Full Cross-Device Capability Matrix.

Replaces / extends the Plan 7 MobileCapabilityMatrix with Plan 9 classifications
that cover ALL discovered managers, workers, agents, teams, and operator domains.

Plan 9 status classifications:
  CLOUD_LIVE          — available from mobile/cloud without MacBook
  LOCAL_LIVE          — available on MacBook/local only
  CROSS_DEVICE_LIVE   — available on both mobile/cloud AND MacBook/local
  QUEUED_MAC_ONLY     — only runs on MacBook; queued when offline
  APPROVAL_REQUIRED   — capability exists but requires Bryan approval to execute
  PARKED              — explicitly parked to a future plan
  MISSING             — not yet implemented
  UNSAFE              — would violate hard gates or security policy
  UNKNOWN_NEEDS_PROOF — status cannot be verified without runtime evidence

Voice/wake/TTS: PARKED (Plan 10)
Apple signing/updater: PARKED (Plan 11)
/Applications/OpenJarvis.app reinstall: QUEUED_MAC_ONLY (accepted permanent exception)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Status classifications
# ---------------------------------------------------------------------------

class CapabilityStatus(str, Enum):
    CLOUD_LIVE = "CLOUD_LIVE"
    LOCAL_LIVE = "LOCAL_LIVE"
    CROSS_DEVICE_LIVE = "CROSS_DEVICE_LIVE"
    QUEUED_MAC_ONLY = "QUEUED_MAC_ONLY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    PARKED = "PARKED"
    MISSING = "MISSING"
    UNSAFE = "UNSAFE"
    UNKNOWN_NEEDS_PROOF = "UNKNOWN_NEEDS_PROOF"


# ---------------------------------------------------------------------------
# Capability entry
# ---------------------------------------------------------------------------

@dataclass
class Plan9CapabilityEntry:
    capability_id: str
    display_name: str
    domain: str                          # manager / worker / system area
    status: CapabilityStatus
    cloud_route: Optional[str] = None    # API route for cloud/mobile
    local_route: Optional[str] = None    # CLI or local path
    parked_until: Optional[str] = None   # "Plan 10", "Plan 11", etc.
    missing_reason: Optional[str] = None
    approval_gate: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "capability_id": self.capability_id,
            "display_name": self.display_name,
            "domain": self.domain,
            "status": self.status.value,
            "cloud_route": self.cloud_route,
            "local_route": self.local_route,
            "parked_until": self.parked_until,
            "missing_reason": self.missing_reason,
            "approval_gate": self.approval_gate,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Full Plan 9 Capability Matrix
# ---------------------------------------------------------------------------

@dataclass
class Plan9CapabilityMatrix:
    entries: List[Plan9CapabilityEntry] = field(default_factory=list)

    def get(self, capability_id: str) -> Optional[Plan9CapabilityEntry]:
        for e in self.entries:
            if e.capability_id == capability_id:
                return e
        return None

    def by_status(self, status: CapabilityStatus) -> List[Plan9CapabilityEntry]:
        return [e for e in self.entries if e.status == status]

    def by_domain(self, domain: str) -> List[Plan9CapabilityEntry]:
        return [e for e in self.entries if e.domain == domain]

    def all_live(self) -> List[Plan9CapabilityEntry]:
        live = {CapabilityStatus.CLOUD_LIVE, CapabilityStatus.LOCAL_LIVE, CapabilityStatus.CROSS_DEVICE_LIVE}
        return [e for e in self.entries if e.status in live]

    def gaps(self) -> List[Plan9CapabilityEntry]:
        """Capabilities that are not yet live and not intentionally parked."""
        non_live = {CapabilityStatus.MISSING, CapabilityStatus.UNKNOWN_NEEDS_PROOF}
        return [e for e in self.entries if e.status in non_live]

    def parked(self) -> List[Plan9CapabilityEntry]:
        return [e for e in self.entries if e.status == CapabilityStatus.PARKED]

    def summary(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.status.value] = counts.get(e.status.value, 0) + 1
        return counts

    def to_list(self) -> List[Dict]:
        return [e.to_dict() for e in self.entries]


# ---------------------------------------------------------------------------
# Factory — all discovered managers, workers, and system domains
# ---------------------------------------------------------------------------

def get_plan9_capability_matrix() -> Plan9CapabilityMatrix:
    """Return the full Plan 9 capability matrix.

    Covers every discovered manager, worker, agent, team, and operator domain.
    Status is the honest current classification — not aspirational.
    """
    CL = CapabilityStatus.CLOUD_LIVE
    LL = CapabilityStatus.LOCAL_LIVE
    CD = CapabilityStatus.CROSS_DEVICE_LIVE
    QM = CapabilityStatus.QUEUED_MAC_ONLY
    AR = CapabilityStatus.APPROVAL_REQUIRED
    PK = CapabilityStatus.PARKED
    MS = CapabilityStatus.MISSING
    UK = CapabilityStatus.UNKNOWN_NEEDS_PROOF

    entries = [
        # ===================================================================
        # CORE JARVIS RUNTIME
        # ===================================================================
        Plan9CapabilityEntry("jarvis_chat", "Jarvis Chat (text)", "core_runtime", CD,
            cloud_route="/v1/chat/completions", local_route="jarvis chat",
            notes="ECS Fargate cloud + local both live"),
        Plan9CapabilityEntry("jarvis_health", "Jarvis Health Check", "core_runtime", CD,
            cloud_route="/health", local_route="jarvis doctor",
            notes="Both cloud and local report health"),
        Plan9CapabilityEntry("jarvis_mobile_ui", "Jarvis Mobile UI", "core_runtime", CD,
            cloud_route="/mobile", local_route="http://localhost:8000/mobile",
            notes="Served from cloud ECS and local server"),
        Plan9CapabilityEntry("jarvis_auth", "Jarvis Auth Gate", "core_runtime", CD,
            cloud_route="/v1/*", notes="Bearer token required on cloud"),

        # ===================================================================
        # CODING MANAGER — coding_manager
        # ===================================================================
        Plan9CapabilityEntry("coding_task_submit", "Submit Coding Task", "coding_manager", CD,
            cloud_route="/v1/frontdoor/submit", local_route="jarvis run",
            notes="Universal front door handles coding intent on cloud"),
        Plan9CapabilityEntry("coding_workspace", "Cloud Coding Workspace", "coding_manager", CD,
            cloud_route="/v1/coding/workspace", notes="Plan 9 cloud coding workspace"),
        Plan9CapabilityEntry("coding_file_read", "Read Repo Files (Cloud)", "coding_manager", CD,
            cloud_route="/v1/coding/files/read",
            notes="Cloud-safe file read via indexed repo"),
        Plan9CapabilityEntry("coding_file_edit", "Edit Repo Files (Cloud)", "coding_manager", CL,
            cloud_route="/v1/coding/files/edit",
            notes="Cloud edit with diff staging; MacBook local also available"),
        Plan9CapabilityEntry("coding_diff_stage", "Stage Diff (Cloud)", "coding_manager", CD,
            cloud_route="/v1/coding/diff/stage"),
        Plan9CapabilityEntry("coding_branch_create", "Create Branch (Cloud)", "coding_manager", CD,
            cloud_route="/v1/coding/branch/create", approval_gate="bryan_approval",
            notes="Branch creation approved by Bryan"),

        # ===================================================================
        # ARCHITECTURE MANAGER — architecture_manager
        # ===================================================================
        Plan9CapabilityEntry("architecture_review", "Architecture Review", "architecture_manager", CD,
            cloud_route="/v1/frontdoor/submit", notes="System arch review via orchestrator"),
        Plan9CapabilityEntry("architecture_plan", "Architecture Plan", "architecture_manager", CD,
            cloud_route="/v1/frontdoor/submit"),

        # ===================================================================
        # TESTING & VALIDATION MANAGER — testing_validation_manager
        # ===================================================================
        Plan9CapabilityEntry("test_run_targeted", "Run Targeted Tests (Cloud)", "testing_validation_manager", CD,
            cloud_route="/v1/testing/run",
            notes="Cloud test runner for targeted pytest"),
        Plan9CapabilityEntry("test_build_check", "Run Build/Lint Checks (Cloud)", "testing_validation_manager", CD,
            cloud_route="/v1/testing/lint"),
        Plan9CapabilityEntry("test_artifact_capture", "Capture Test Artifacts", "testing_validation_manager", CD,
            cloud_route="/v1/testing/artifacts"),

        # ===================================================================
        # CODE REVIEW MANAGER — code_review_manager
        # ===================================================================
        Plan9CapabilityEntry("code_review_diff", "Review Diff (Cloud)", "code_review_manager", CD,
            cloud_route="/v1/review/diff"),
        Plan9CapabilityEntry("code_review_pr", "PR Review", "code_review_manager", CD,
            cloud_route="/v1/review/pr"),

        # ===================================================================
        # DEBUGGING MANAGER — debugging_manager
        # ===================================================================
        Plan9CapabilityEntry("debug_log_read", "Read Debug Logs (Cloud)", "debugging_manager", CD,
            cloud_route="/v1/debugging/logs"),
        Plan9CapabilityEntry("debug_trace_read", "Read Trace Output", "debugging_manager", CD,
            cloud_route="/v1/debugging/traces"),

        # ===================================================================
        # RESEARCH MANAGER — research_manager
        # ===================================================================
        Plan9CapabilityEntry("research_web", "Web Research", "research_manager", CD,
            cloud_route="/api/research",
            notes="Full deep research via cloud"),
        Plan9CapabilityEntry("research_local_context", "Local Context Research", "research_manager", CD,
            cloud_route="/v1/research/context"),

        # ===================================================================
        # MEMORY & KNOWLEDGE MANAGER — memory_knowledge_manager
        # ===================================================================
        Plan9CapabilityEntry("memory_read", "Memory Read (Cloud)", "memory_knowledge_manager", CD,
            cloud_route="/v1/memory/retrieve", local_route="jarvis memory"),
        Plan9CapabilityEntry("memory_write", "Memory Write (Cloud)", "memory_knowledge_manager", CD,
            cloud_route="/v1/memory/store"),
        Plan9CapabilityEntry("memory_sync", "Memory Sync (Cloud↔Local)", "memory_knowledge_manager", CD,
            cloud_route="/v1/memory/sync",
            notes="Cloud S3 + local store synced"),
        Plan9CapabilityEntry("memory_continuity_snapshot", "Continuity Snapshot", "memory_knowledge_manager", CD,
            cloud_route="/v1/continuity/snapshot"),
        Plan9CapabilityEntry("memory_continuity_resume", "Continuity Resume", "memory_knowledge_manager", CD,
            cloud_route="/v1/continuity/resume"),

        # ===================================================================
        # DOCUMENTATION MANAGER — documentation_manager
        # ===================================================================
        Plan9CapabilityEntry("docs_generate", "Generate Docs (Cloud)", "documentation_manager", CD,
            cloud_route="/v1/frontdoor/submit"),
        Plan9CapabilityEntry("docs_update", "Update Docs (Cloud)", "documentation_manager", CD,
            cloud_route="/v1/frontdoor/submit"),

        # ===================================================================
        # PRODUCT & UX MANAGER — product_ux_manager
        # ===================================================================
        Plan9CapabilityEntry("ui_capability_status", "Capability Status in UI", "product_ux_manager", CD,
            cloud_route="/v1/capabilities/status",
            notes="Plan 9 capability-aware UI surface"),
        Plan9CapabilityEntry("ui_parity_dashboard", "Parity Dashboard", "product_ux_manager", CD,
            cloud_route="/v1/parity/status"),

        # ===================================================================
        # OPERATIONS & AUTOMATION MANAGER — operations_automation_manager
        # ===================================================================
        Plan9CapabilityEntry("ops_automation_run", "Run Automation (Cloud)", "operations_automation_manager", CD,
            cloud_route="/v1/frontdoor/submit"),
        Plan9CapabilityEntry("ops_scheduler", "Scheduler (Cloud)", "operations_automation_manager", CD,
            cloud_route="/v1/scheduler"),

        # ===================================================================
        # GOVERNANCE & SAFETY MANAGER — governance_safety_manager
        # ===================================================================
        Plan9CapabilityEntry("governance_gate_check", "Governance Gate Check", "governance_safety_manager", CD,
            cloud_route="/v1/governance/gate-check", local_route="jarvis approval classify"),
        Plan9CapabilityEntry("governance_audit_log", "Audit Log (Cloud)", "governance_safety_manager", CD,
            cloud_route="/v1/governance/audit"),
        Plan9CapabilityEntry("governance_secret_scan", "Secret Scan", "governance_safety_manager", CD,
            cloud_route="/v1/governance/secret-scan", local_route="jarvis secret-scan"),
        Plan9CapabilityEntry("governance_approval_pending", "Approval Pending (Cloud)", "governance_safety_manager", CD,
            cloud_route="/v1/approvals/pending"),
        Plan9CapabilityEntry("governance_approval_act", "Approve/Deny (Cloud)", "governance_safety_manager", CD,
            cloud_route="/v1/approvals/{id}/approve"),

        # ===================================================================
        # RELEASE & PACKAGING MANAGER — release_packaging_manager
        # ===================================================================
        Plan9CapabilityEntry("release_build_image", "Build Docker Image", "release_packaging_manager", AR,
            approval_gate="bryan_approval",
            notes="Cloud CI/CD build with Bryan approval"),
        Plan9CapabilityEntry("release_deploy_cloud", "Deploy to ECS/Cloud", "release_packaging_manager", AR,
            approval_gate="bryan_approval",
            notes="Hard-gated. Bryan must approve each production deploy"),
        Plan9CapabilityEntry("release_app_install_mac", "Reinstall /Applications/OpenJarvis.app", "release_packaging_manager", QM,
            local_route="/Applications/OpenJarvis.app",
            notes="Accepted permanent Plan 9 exception — MacBook-only"),
        Plan9CapabilityEntry("apple_signing_updater", "Apple Signing / Auto-updater", "release_packaging_manager", PK,
            parked_until="Plan 11",
            notes="Parked. Will not be addressed in Plan 9."),

        # ===================================================================
        # DATA MANAGER — data_manager
        # ===================================================================
        Plan9CapabilityEntry("data_read", "Data Read (Cloud)", "data_manager", CD,
            cloud_route="/v1/data/read"),
        Plan9CapabilityEntry("data_transform", "Data Transform", "data_manager", CD,
            cloud_route="/v1/data/transform"),

        # ===================================================================
        # COST & ROUTING MANAGER — cost_routing_manager
        # ===================================================================
        Plan9CapabilityEntry("model_route_explain", "Model Route Explain", "cost_routing_manager", CD,
            cloud_route="/v1/model-route/explain", local_route="jarvis model-route explain"),
        Plan9CapabilityEntry("cost_ledger_read", "Cost Ledger Read", "cost_routing_manager", CD,
            cloud_route="/v1/cost/ledger"),

        # ===================================================================
        # NUS LEARNING MANAGER — nus_learning_manager
        # ===================================================================
        Plan9CapabilityEntry("nus_scorecard", "NUS Scorecard (Cloud)", "nus_learning_manager", CD,
            cloud_route="/v1/nus/scorecard"),
        Plan9CapabilityEntry("nus_routing_recommendation", "NUS Routing Recommendation", "nus_learning_manager", CD,
            cloud_route="/v1/nus/routing/recommend"),

        # ===================================================================
        # CONNECTOR & AUTH MANAGER — connector_auth_manager
        # ===================================================================
        Plan9CapabilityEntry("connector_status", "Connector Status (Cloud)", "connector_auth_manager", CD,
            cloud_route="/v1/connectors/status"),
        Plan9CapabilityEntry("connector_gmail", "Gmail Connector", "connector_auth_manager", CD,
            cloud_route="/v1/connectors/gmail",
            notes="Cloud-safe OAuth; MacBook credential migration may be needed"),
        Plan9CapabilityEntry("connector_calendar", "Google Calendar Connector", "connector_auth_manager", CD,
            cloud_route="/v1/connectors/calendar"),
        Plan9CapabilityEntry("connector_slack", "Slack Connector", "connector_auth_manager", CD,
            cloud_route="/v1/connectors/slack"),
        Plan9CapabilityEntry("connector_github", "GitHub Connector", "connector_auth_manager", CD,
            cloud_route="/v1/connectors/github"),
        Plan9CapabilityEntry("connector_gdrive", "Google Drive Connector", "connector_auth_manager", UK,
            notes="Status needs runtime proof on cloud"),
        Plan9CapabilityEntry("connector_notion", "Notion Connector", "connector_auth_manager", UK,
            notes="Status needs runtime proof on cloud"),

        # ===================================================================
        # RUNTIME OPS MANAGER — runtime_ops_manager
        # ===================================================================
        Plan9CapabilityEntry("runtime_ops_health", "Runtime Ops Health (Cloud)", "runtime_ops_manager", CD,
            cloud_route="/health"),
        Plan9CapabilityEntry("runtime_ops_recovery", "Runtime Recovery", "runtime_ops_manager", CD,
            cloud_route="/v1/runtime/recovery"),
        Plan9CapabilityEntry("runtime_mode_report", "Runtime Mode Report", "runtime_ops_manager", CD,
            cloud_route="/health", notes="engine/mode reported in health response"),

        # ===================================================================
        # CLOUD OPERATOR CAPABILITIES (Sections 12-15)
        # ===================================================================
        Plan9CapabilityEntry("cloud_coding_workspace", "Cloud Coding Workspace", "cloud_operator", CD,
            cloud_route="/v1/coding/workspace",
            notes="Inspect/search/read/edit/diff — no MacBook required"),
        Plan9CapabilityEntry("cloud_test_runner", "Cloud Test Runner", "cloud_operator", CD,
            cloud_route="/v1/testing/run",
            notes="Targeted pytest on cloud runner"),
        Plan9CapabilityEntry("cloud_commit_workflow", "Mobile Commit/Push Workflow", "cloud_operator", AR,
            cloud_route="/v1/git/commit", approval_gate="bryan_approval",
            notes="Diff review → commit → push → secret scan; Bryan approval required"),
        Plan9CapabilityEntry("cloud_deploy_operator", "Cloud Deploy Operator", "cloud_operator", AR,
            cloud_route="/v1/deploy/plan", approval_gate="bryan_approval",
            notes="Dry-run plan + Bryan approval before any production deploy"),

        # ===================================================================
        # MEMORY PARITY (Section 16)
        # ===================================================================
        Plan9CapabilityEntry("memory_cloud_parity", "Cloud Memory Parity", "memory_parity", CD,
            cloud_route="/v1/memory",
            notes="Cloud S3 memory + local store — consistent cross-device state"),
        Plan9CapabilityEntry("memory_local_sync", "Local Memory Sync", "memory_parity", CD,
            notes="Synced via cloud sync engine"),
        Plan9CapabilityEntry("memory_audit_trail", "Memory Audit Trail", "memory_parity", CD,
            cloud_route="/v1/memory/audit"),

        # ===================================================================
        # CONNECTOR PARITY (Section 17)
        # ===================================================================
        Plan9CapabilityEntry("connector_cloud_parity", "Cloud Connector Parity", "connector_parity", CD,
            cloud_route="/v1/connectors",
            notes="All connectors accessible from cloud without MacBook"),

        # ===================================================================
        # FILE MIRROR / INDEX (Section 18)
        # ===================================================================
        Plan9CapabilityEntry("file_mirror_index", "Cloud-Safe File Mirror/Index", "file_mirror", CD,
            cloud_route="/v1/files/index",
            notes="Allowlisted files indexed for cloud access — no blind Mac exposure"),
        Plan9CapabilityEntry("file_mirror_read", "Cloud File Read", "file_mirror", CD,
            cloud_route="/v1/files/read"),
        Plan9CapabilityEntry("file_mirror_local_only", "Mac-Only Unsynced Files", "file_mirror", QM,
            notes="Local-only files queue as Mac-worker tasks"),

        # ===================================================================
        # MAC WORKER QUEUE (Section 19)
        # ===================================================================
        Plan9CapabilityEntry("mac_worker_queue", "Mac Worker Queue", "mac_worker", QM,
            cloud_route="/v1/mac-worker/queue",
            notes="Mobile queues Mac-only tasks; executed when MacBook online"),
        Plan9CapabilityEntry("mac_worker_status", "Mac Worker Queue Status", "mac_worker", CD,
            cloud_route="/v1/mac-worker/status",
            notes="Queue status visible on both mobile and MacBook"),
        Plan9CapabilityEntry("mac_app_control", "Mac App Control (Finder/Settings)", "mac_worker", QM,
            notes="Mac-only. Cannot be cloud-native."),
        Plan9CapabilityEntry("mac_keychain_credentials", "Keychain Credentials", "mac_worker", QM,
            notes="Local Keychain only; must migrate to cloud-safe secrets store for cloud access"),

        # ===================================================================
        # VOICE / WAKE / TTS (PARKED)
        # ===================================================================
        Plan9CapabilityEntry("voice_wake_tts", "Voice / Wake Word / TTS", "voice", PK,
            parked_until="Plan 10",
            notes="Parked. Will not be addressed in Plan 9. Do not reopen."),

        # ===================================================================
        # CAPABILITY-AWARE UI (Section 20)
        # ===================================================================
        Plan9CapabilityEntry("capability_status_api", "Capability Status API", "ui_api", CD,
            cloud_route="/v1/capabilities/status",
            notes="Returns Plan 9 status for each capability — surfaced in mobile and MacBook UI"),
        Plan9CapabilityEntry("parity_status_mobile", "Mobile Parity Status View", "ui_api", CD,
            cloud_route="/v1/parity/status"),
        Plan9CapabilityEntry("parity_status_macbook", "MacBook Parity Status View", "ui_api", CD,
            local_route="jarvis parity status"),

        # ===================================================================
        # AUTHORITY / APPROVAL / AUDIT (Section 21)
        # ===================================================================
        Plan9CapabilityEntry("authority_classification", "Authority Classification", "authority_audit", CD,
            cloud_route="/v1/authority/classify", local_route="jarvis approval classify"),
        Plan9CapabilityEntry("audit_log", "Audit Event Log", "authority_audit", CD,
            cloud_route="/v1/audit", local_route="jarvis audit show"),
        Plan9CapabilityEntry("rollback_plan", "Rollback Plan", "authority_audit", CD,
            cloud_route="/v1/rollback/plan", local_route="jarvis rollback plan"),
    ]

    return Plan9CapabilityMatrix(entries=entries)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_MATRIX: Optional[Plan9CapabilityMatrix] = None


def get_matrix() -> Plan9CapabilityMatrix:
    global _MATRIX
    if _MATRIX is None:
        _MATRIX = get_plan9_capability_matrix()
    return _MATRIX
