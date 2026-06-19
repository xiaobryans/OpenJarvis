"""Universal Mobile Project-Building Runtime — capability audit and classification.

NEW LOCKED REQUIREMENT:
Mobile means full MacBook-equivalent Jarvis capability from phone, not basic chat/status.

Bryan must be able to start or continue ANY project from his phone through Jarvis
and trigger real coding/test/build/review/approval work — even when the MacBook is off.

OMNIX is only one example project. Jarvis must support any project/new project.

IMPORTANT DISTINCTION:
  - PWA/chat/status/snapshot continuity = NOT enough
  - Cloud memory sync alone = NOT enough
  - LAN-only MacBook server access = NOT enough
  - "Universal mobile project-building" requires a real always-available
    remote/cloud execution backend for coding/build/test/project work.

CURRENT AUDIT RESULTS (all capabilities classified honestly):

  Phase 1 (LAN/MacBook-on only — WIRED_AND_TESTED):
    - Mobile browser → FastAPI → company org runtime → local worker pool
    - Text input fallback, PWA installable
    - All routing/COS/manager/verifier/sentinel callable

  Phase 2 (MacBook-off — REQUIRED_FOR_NO_GAP_JARVIS):
    - Remote/cloud execution runtime (GitHub Actions recommended — free tier)
    - GITHUB_TOKEN with workflow scope (currently invalid token)
    - Repo access from cloud runtime
    - Build/test artifact storage
    - Diff/log/artifact viewing via remote
    - Approval gate via mobile → remote backend

  Each mobile project-building capability is classified below.

Sprint: Sprint 3 Consolidated Final Retest
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class MobileCapabilityStatus(str, Enum):
    WIRED_AND_TESTED = "WIRED_AND_TESTED"
    PARTIALLY_WIRED = "PARTIALLY_WIRED"
    REQUIRED_FOR_NO_GAP_JARVIS = "REQUIRED_FOR_NO_GAP_JARVIS"
    BLOCKED_WAITING_FOR_BRYAN_NOW = "BLOCKED_WAITING_FOR_BRYAN_NOW"
    BLOCKED_EXTERNAL_PROVIDER = "BLOCKED_EXTERNAL_PROVIDER"
    BLOCKED_RUNTIME_CREDENTIALS = "BLOCKED_RUNTIME_CREDENTIALS"
    BLOCKED_SECURITY = "BLOCKED_SECURITY"


@dataclass
class MobileCapability:
    capability: str
    description: str
    status: MobileCapabilityStatus
    macbook_on_status: MobileCapabilityStatus
    macbook_off_status: MobileCapabilityStatus
    blocker: Optional[str]
    path: str
    evidence: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "description": self.description,
            "status": self.status.value,
            "macbook_on": self.macbook_on_status.value,
            "macbook_off": self.macbook_off_status.value,
            "blocker": self.blocker,
            "path": self.path,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Universal mobile project-building capability matrix
# ---------------------------------------------------------------------------

MOBILE_PROJECT_CAPABILITIES: List[MobileCapability] = [

    MobileCapability(
        capability="start_new_project",
        description="Phone can start a brand-new project through Jarvis (name, tech stack, repo init)",
        status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_on_status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: POST /v1/company-org/task with 'start project' intent routes to manager "
            "but no repo init / git init / scaffold command runs (worker is simulated, not real shell). "
            "MacBook-off: requires remote execution runtime."
        ),
        path="POST /v1/company-org/task → manager-coding → worker-repo-inspector (simulated)",
        evidence="src/openjarvis/agents/company_org_runtime.py",
    ),

    MobileCapability(
        capability="continue_existing_project",
        description="Phone can resume any existing project with full context (task, agent, artifact, memory state)",
        status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_on_status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_off_status=MobileCapabilityStatus.BLOCKED_RUNTIME_CREDENTIALS,
        blocker=(
            "MacBook-on: continuity snapshot + resume token path is wired and tested. "
            "MacBook-off: requires valid GITHUB_TOKEN (currently invalid) + remote execution runtime."
        ),
        path="GET /v1/continuity/snapshot/{id} → ContinuityStore → restore state",
        evidence="src/openjarvis/mobile/continuity.py",
    ),

    MobileCapability(
        capability="trigger_coding_task",
        description="Phone can send a coding request (fix bug, add feature, refactor) to the Jarvis pipeline",
        status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_on_status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: POST /v1/company-org/task routes to manager-coding and runs simulated workers. "
            "Real file edits require real shell execution — not implemented in workers. "
            "MacBook-off: requires remote execution runtime (GitHub Actions or equivalent)."
        ),
        path="POST /v1/company-org/task → COS → manager-coding → workers",
        evidence="src/openjarvis/agents/company_org_runtime.py",
    ),

    MobileCapability(
        capability="trigger_code_review",
        description="Phone can trigger code diff review / PR review through Jarvis",
        status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_on_status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: Jarvis can route 'code review' task to manager-coding. "
            "Real diff generation requires git access (local only). "
            "GitHub PR reviews possible via GitHub API if GITHUB_TOKEN valid with repo scope."
        ),
        path="POST /v1/company-org/task → manager-coding → worker-repo-inspector",
        evidence=None,
    ),

    MobileCapability(
        capability="trigger_tests",
        description="Phone can trigger test runs and get results",
        status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_on_status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: worker-test-runner is simulated — pytest command not actually run. "
            "MacBook-off: requires remote execution runtime (GitHub Actions free tier can run tests). "
            "GitHub Actions approach: trigger workflow via API → poll for results."
        ),
        path="POST /v1/company-org/task → manager-coding → worker-test-runner (simulated only)",
        evidence="src/openjarvis/agents/worker_pool.py",
    ),

    MobileCapability(
        capability="trigger_builds",
        description="Phone can trigger builds (npm build, cargo build, docker build, etc.)",
        status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_on_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "Build execution requires a real shell runtime. "
            "GitHub Actions free tier: 2000 min/month, can run builds. "
            "Requires GITHUB_TOKEN with workflow scope + workflow files in repo."
        ),
        path="NOT_IMPLEMENTED — requires remote execution runtime",
        evidence=None,
    ),

    MobileCapability(
        capability="trigger_packaging_release_checks",
        description="Phone can trigger packaging/release readiness checks",
        status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_on_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker="Requires remote execution runtime with repo access.",
        path="NOT_IMPLEMENTED — requires remote execution runtime",
        evidence=None,
    ),

    MobileCapability(
        capability="view_diffs_logs_artifacts",
        description="Phone can view diffs, build logs, test output, and artifact summaries",
        status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_on_status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: artifact pointers in continuity snapshot restored from Gist. "
            "GITHUB_TOKEN now has repo scope — GitHub PR diffs/commit diffs available via API. "
            "Build logs: available from GitHub Actions API after run completes (once runtime live). "
            "No rendered diff view in mobile UI yet."
        ),
        path="GET /v1/continuity/snapshot/{id} → artifact_pointers; GitHub API (repo scope available)",
        evidence="src/openjarvis/mobile/continuity.py",
    ),

    MobileCapability(
        capability="approve_reject_gated_actions",
        description="Phone can approve or reject gated actions (deploy, merge, delete, etc.)",
        status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_on_status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: POST /v1/mobile/approve-action + APPROVE/REJECT buttons on /mobile page "
            "route through COS → Verifier gate. WIRED_AND_TESTED. "
            "MacBook-off: approval action routing requires remote runtime to be live."
        ),
        path="POST /v1/mobile/approve-action → CompanyOrgRuntime → COS → verifier gate",
        evidence="src/openjarvis/server/company_org_routes.py",
    ),

    MobileCapability(
        capability="monitor_managers_workers_verifier_sentinel",
        description="Phone can view current agent state, stalls, blockers, verifier status",
        status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_on_status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_off_status=MobileCapabilityStatus.BLOCKED_RUNTIME_CREDENTIALS,
        blocker=(
            "MacBook-on: GET /v1/company-org/status, /roster, /wiring-matrix, /v1/jarvis/manifest. "
            "MacBook-off: requires valid GITHUB_TOKEN for cloud snapshot + remote backend."
        ),
        path="GET /v1/company-org/status + /v1/jarvis/manifest",
        evidence="src/openjarvis/server/company_org_routes.py",
    ),

    MobileCapability(
        capability="reassign_escalate_stuck_workers",
        description="Phone can trigger stall reassignment or escalate blockers to COS/Jarvis",
        status=MobileCapabilityStatus.PARTIALLY_WIRED,
        macbook_on_status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "MacBook-on: stall detection + COS escalation wired in company_org_runtime. "
            "Mobile can trigger via POST /v1/company-org/task with simulate_stall=False. "
            "MacBook-off: requires remote execution backend to receive the command."
        ),
        path="POST /v1/company-org/task → stall detected → pool.check_stalls() → COS.escalate_blocker()",
        evidence="src/openjarvis/agents/company_org_runtime.py",
    ),

    MobileCapability(
        capability="macbook_off_full_parity",
        description="All above capabilities work when MacBook is completely off",
        status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_on_status=MobileCapabilityStatus.WIRED_AND_TESTED,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "Requires: (1) valid GITHUB_TOKEN for cloud snapshot sync, "
            "(2) remote execution runtime (GitHub Actions or always-on server), "
            "(3) repo access from runtime, (4) build/test/artifact pipeline in runtime."
        ),
        path="NOT_IMPLEMENTED — universal mobile runtime required",
        evidence=None,
    ),

    MobileCapability(
        capability="remote_cloud_execution_runtime",
        description="Always-available backend that can run code, tests, builds for any project",
        status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_on_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        macbook_off_status=MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS,
        blocker=(
            "Designed but not yet implemented. "
            "Cheapest free path: GitHub Actions (2000 min/month free). "
            "Requires: GITHUB_TOKEN with workflow scope, workflow YAML files in repo."
        ),
        path="src/openjarvis/remote/github_actions_backend.py — DESIGNED_NOT_DEPLOYED",
        evidence="src/openjarvis/remote/github_actions_backend.py",
    ),
]


def get_capability_matrix() -> Dict[str, Any]:
    """Return full universal mobile project-building capability matrix."""
    all_caps = [c.to_dict() for c in MOBILE_PROJECT_CAPABILITIES]
    wired = [c for c in MOBILE_PROJECT_CAPABILITIES
             if c.status == MobileCapabilityStatus.WIRED_AND_TESTED]
    required = [c for c in MOBILE_PROJECT_CAPABILITIES
                if c.status == MobileCapabilityStatus.REQUIRED_FOR_NO_GAP_JARVIS]
    partial = [c for c in MOBILE_PROJECT_CAPABILITIES
               if c.status == MobileCapabilityStatus.PARTIALLY_WIRED]
    blocked = [c for c in MOBILE_PROJECT_CAPABILITIES
               if c.status in (
                   MobileCapabilityStatus.BLOCKED_RUNTIME_CREDENTIALS,
                   MobileCapabilityStatus.BLOCKED_EXTERNAL_PROVIDER,
                   MobileCapabilityStatus.BLOCKED_WAITING_FOR_BRYAN_NOW,
                   MobileCapabilityStatus.BLOCKED_SECURITY,
               )]

    mobile_accepted = len(required) == 0 and len(blocked) == 0

    return {
        "universal_mobile_project_building": (
            "WIRED_AND_TESTED" if mobile_accepted
            else "REQUIRED_FOR_NO_GAP_JARVIS"
        ),
        "mobile_accepted": mobile_accepted,
        "note": (
            "Mobile is NOT accepted if only PWA/chat/status/snapshot exists. "
            "Remote/cloud execution runtime required for full MacBook-off parity."
        ),
        "summary": {
            "wired_and_tested": len(wired),
            "partially_wired": len(partial),
            "required_for_no_gap": len(required),
            "blocked": len(blocked),
            "total": len(MOBILE_PROJECT_CAPABILITIES),
        },
        "capabilities": all_caps,
    }


__all__ = [
    "MobileCapabilityStatus",
    "MobileCapability",
    "MOBILE_PROJECT_CAPABILITIES",
    "get_capability_matrix",
]
