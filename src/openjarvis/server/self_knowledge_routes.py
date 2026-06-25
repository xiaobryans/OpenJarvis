"""Self-Knowledge Routes — Jarvis capability awareness and status endpoints.

Routes:
  GET /v1/jarvis/capabilities  — what can Jarvis do right now?
  GET /v1/jarvis/status        — current Jarvis system status
  GET /v1/jarvis/roadmap       — current roadmap and plan state

Design rules:
  - No secret values.
  - Honest partial/blocked state reporting — no fake AVAILABLE.
  - Plan 3 voice/TTS explicitly reported as PARKED.
  - Returns human-readable descriptions for "what can you do?" queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

try:
    from fastapi import APIRouter
except ImportError:
    raise ImportError("fastapi required for self-knowledge routes")

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jarvis-self-knowledge"])


# ---------------------------------------------------------------------------
# Static capability manifest
# ---------------------------------------------------------------------------

_CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "chat",
        "name": "Text-first intelligent chat",
        "status": "available",
        "description": "Answer questions, plan tasks, write code, research topics, and assist with decisions in a unified text conversation.",
        "plan": "Plan 1",
    },
    {
        "id": "memory",
        "name": "Unified memory search",
        "status": "available",
        "description": "Remember context from prior sessions; search and retrieve from memory namespaces.",
        "plan": "Plan 1",
    },
    {
        "id": "cloud_routing",
        "name": "Cloud-first routing",
        "status": "available",
        "description": "Routes requests to Fargate workers for long-running or compute-intensive tasks.",
        "plan": "Plan 1",
    },
    {
        "id": "connectors",
        "name": "Connector integrations",
        "status": "partial",
        "description": "GitHub, Slack, Telegram, Notion, Google OAuth connectors. Cloud env tokens needed for full Fargate deployment.",
        "plan": "Plan 2",
        "blocker": "Fargate env vars not yet deployed for all connectors",
    },
    {
        "id": "mobile_parity",
        "name": "Mobile/MacBook-off parity",
        "status": "available",
        "description": "Core parity endpoints available for mobile access. PWA manifest present.",
        "plan": "Plan 2",
    },
    {
        "id": "approval_gates",
        "name": "Approval and delegation gates",
        "status": "available",
        "description": "Six-tier authority model. Actions require explicit approval at Tier 3+. Emergency stop supported.",
        "plan": "Plan 2 / Plan 8",
    },
    {
        "id": "skills",
        "name": "Skill registry",
        "status": "available",
        "description": "Skill discovery, cataloging, enable/disable, and third-party skill intake with vetting.",
        "plan": "Plan 1 / Plan 4",
    },
    {
        "id": "rules",
        "name": "Rules engine",
        "status": "available",
        "description": "User-defined and system rules governing Jarvis behavior. CRUD, conflict detection, scope-aware evaluation.",
        "plan": "Plan 4",
    },
    {
        "id": "life_os",
        "name": "Life-Business OS",
        "status": "available",
        "description": "Personal tasks, goals, reminders, daily summaries, approval workflow.",
        "plan": "Plan 4-5",
    },
    {
        "id": "expert_roles",
        "name": "Expert role orchestration",
        "status": "available",
        "description": "Internal expert roles (coding, product, research, security, etc.) selected behind the scenes. Single Jarvis PA voice.",
        "plan": "Plan 6",
    },
    {
        "id": "doctor",
        "name": "Self-diagnostic doctor",
        "status": "available",
        "description": "19 health checks across all system categories. Readiness report with PASS/WARN/FAIL per category.",
        "plan": "Plan 1",
    },
    {
        "id": "automation_policy",
        "name": "Automation ladder",
        "status": "available",
        "description": "7-level automation policy with hard gates. 14 action classes always blocked. Standing approval.",
        "plan": "Post-Plan-2",
    },
    {
        "id": "voice_tts",
        "name": "Voice / Wake / TTS",
        "status": "parked",
        "description": "Voice, wake-word, and TTS capabilities are PARKED until Jarvis is text-first stable. Not implemented.",
        "plan": "Plan 3 — PARKED",
        "blocker": "Plan 3 explicitly parked by Bryan. Text-first priority.",
    },
    {
        "id": "ios_native",
        "name": "Native iOS / Productization",
        "status": "partial",
        "description": (
            "PWA fully implemented (Plan 2). Tauri desktop scaffold present at frontend/src-tauri/ "
            "(macOS/Windows/Linux only). Native iOS target not yet initialized — requires "
            "'tauri ios init' and Apple Developer Account enrollment (external gate). "
            "See GET /v1/productization/status for full breakdown."
        ),
        "plan": "Plan 4-5",
        "external_gate": "Apple Developer Account enrollment",
    },
    {
        "id": "expert_role_wiring",
        "name": "Expert role routing in Jarvis PA",
        "status": "available",
        "description": "RoleSelector is wired into the frontdoor submit path. Expert roles are selected internally behind one Jarvis PA voice.",
        "plan": "Plan 4-6",
    },
    {
        "id": "delegation_queue",
        "name": "Life-Business OS delegation queue",
        "status": "available",
        "description": (
            "Unified delegation/approval queue aggregating life-os tasks, agent actions, "
            "and mission tasks pending approval. Approve/reject through existing gated routes. "
            "See GET /v1/delegation/queue."
        ),
        "plan": "Plan 4-5",
    },
    {
        "id": "system_status",
        "name": "Unified system / connector status",
        "status": "available",
        "description": (
            "Presence-only status for all connectors (Gmail, Calendar, Drive, Slack, Telegram, "
            "Notion, GitHub, S3) and system components (Fargate, mobile/PWA/iOS, skills/rules, "
            "expert roles). See GET /v1/system/status."
        ),
        "plan": "Plan 4-6",
    },
    {
        "id": "routines",
        "name": "Recurring routines / scheduled tasks",
        "status": "partial",
        "description": (
            "Scheduler module exists (cron/interval/once with SQLite persistence). "
            "Recurring task visibility at GET /v1/routines. "
            "Automated execution requires scheduler to be started via CLI. "
            "No fake recurring automations claimed as fully running."
        ),
        "plan": "Final Phase A",
        "note": "Visibility only in current release — automated execution is CLI-controlled.",
    },
    {
        "id": "follow_up_center",
        "name": "Follow-Up Center",
        "status": "available",
        "description": (
            "Unified follow-up visibility aggregating life-os tasks (waiting_followup status "
            "or active follow_up_state) and goal follow-up queue items. "
            "Safe mark-done and snooze actions preserve existing approval gates. "
            "No connector credentials required. See GET /v1/follow-up-center."
        ),
        "plan": "Phase B1",
    },
    {
        "id": "routines_command_center",
        "name": "Routines / Cadence Command Center",
        "status": "available",
        "description": (
            "Unified visibility of all scheduled routines (cron/interval/once). "
            "Summary by type and status. Scheduler module available but not auto-started. "
            "No fake automation claims. See GET /v1/routines/summary."
        ),
        "plan": "Phase B2",
    },
    {
        "id": "memory_os",
        "name": "Memory OS deepening",
        "status": "available",
        "description": (
            "Memory namespace dashboard, entry counts, search availability, "
            "cloud sync presence (honest — not claimed live without proof). "
            "See GET /v1/memory/dashboard."
        ),
        "plan": "Phase B3",
    },
    {
        "id": "command_center",
        "name": "Task / Project / Goal Command Center",
        "status": "available",
        "description": (
            "Unified aggregated view of life-os tasks, long-horizon goals, and projects. "
            "Read-only, approval gates preserved. "
            "See GET /v1/command-center."
        ),
        "plan": "Phase B4",
    },
    {
        "id": "expert_org",
        "name": "Expert Organization routing status",
        "status": "available",
        "description": (
            "Routing audit for expert role selection. One Jarvis PA identity confirmed. "
            "Internal routing only — no multi-personality output. "
            "See GET /v1/expert-roles/routing-status."
        ),
        "plan": "Phase B5",
    },
    {
        "id": "skills_plugin_expansion",
        "name": "Skills / Plugin Expansion Pack",
        "status": "available",
        "description": (
            "Expanded skill catalog summary, permission/risk matrix, dry-run intake validation, "
            "and intake review queue. Third-party marketplace integration requires external gate. "
            "See GET /v1/skills/catalog/summary, GET /v1/skills/permissions."
        ),
        "plan": "Phase B7",
    },
    {
        "id": "connector_workflow_expansion",
        "name": "Connector Workflow Expansion",
        "status": "partial",
        "description": (
            "Per-connector workflow capability matrix (Gmail, Slack, Telegram, GitHub, Notion, Google Calendar). "
            "Status based on env var presence. Live workflows blocked until credentials are configured. "
            "All live actions require approval gates. See GET /v1/connector-workflows."
        ),
        "plan": "Phase B8",
        "blocker": "Connector credentials required for live execution (external gate).",
    },
    {
        "id": "proactive_operator",
        "name": "Proactive Operator Layer",
        "status": "available",
        "description": (
            "Proactive suggestions from existing local data (pending approvals, failed routines, stale items). "
            "Suggestions only — no autonomous execution. Approval gates fully preserved. "
            "See GET /v1/proactive/suggestions."
        ),
        "plan": "Phase B9",
    },
    {
        "id": "business_admin_operator",
        "name": "Business / Admin Operator Expansion",
        "status": "available",
        "description": (
            "Admin task categories, research/analysis, company-building templates, communications drafting. "
            "External action requires connector credentials + approval gates. No fake completed work. "
            "See GET /v1/business-admin/dashboard."
        ),
        "plan": "Phase B10",
    },
    {
        "id": "observability_reliability",
        "name": "Observability / Reliability / Cost Controls",
        "status": "available",
        "description": (
            "Local component health summary, reliability metrics, audit log access. "
            "Cost tracking requires provider billing API (external gate — not yet live). "
            "No secrets in any response. See GET /v1/observability/health-summary."
        ),
        "plan": "Phase B11",
    },
    {
        "id": "long_horizon_goals",
        "name": "Long-Horizon Goal Execution Foundation",
        "status": "available",
        "description": (
            "Goal checkpoint tracking, execution plan timelines, pause/resume/cancel state. "
            "All execution steps require explicit approval. No autonomous execution. "
            "See GET /v1/long-horizon/goals."
        ),
        "plan": "Phase B12",
    },
    {
        "id": "finance_admin_os",
        "name": "Personal Finance / Admin OS",
        "status": "available",
        "description": (
            "Finance and admin task categories, budget/bill tracking templates, "
            "document drafting, tax compliance checklists. "
            "No live financial execution. See GET /v1/finance-admin/dashboard."
        ),
        "plan": "Phase B13",
    },
    {
        "id": "research_os",
        "name": "Research / Learning / Company-Building OS",
        "status": "available",
        "description": (
            "Research queue, learning plans, company-building project templates. "
            "Local task/goal/memory integration. No fake web research. "
            "See GET /v1/research-os/dashboard."
        ),
        "plan": "Phase B14",
    },
    {
        "id": "browser_operator",
        "name": "Browser / Web Operator Foundation",
        "status": "partial",
        "description": (
            "Browser operator capability matrix, dry-run action plans, safety gates. "
            "No live browser control. All actions require approval. "
            "See GET /v1/browser-operator/status."
        ),
        "plan": "Phase B15",
        "blocker": "Browser automation library not yet integrated (external gate).",
    },
    {
        "id": "memory_graph",
        "name": "Advanced Memory + Knowledge Graph",
        "status": "partial",
        "description": (
            "Memory namespace metadata, entity extraction and knowledge graph planned but not yet implemented. "
            "Local SQLite storage. Cloud sync requires Fargate credentials. "
            "See GET /v1/memory-graph/status."
        ),
        "plan": "Phase B16",
        "blocker": "Entity extraction and knowledge graph not yet implemented.",
    },
    {
        "id": "multi_device",
        "name": "Multi-Device / Phone-Controlled Workbench",
        "status": "partial",
        "description": (
            "Device/session status, capability matrix, workbench queue. "
            "Desktop local session active. Mobile PWA and cloud execution require Tailscale + Fargate. "
            "See GET /v1/multi-device/status."
        ),
        "plan": "Phase B17",
        "blocker": "Mobile PWA and cloud execution require Tailscale + Fargate deployment.",
    },
    {
        "id": "marketplace",
        "name": "Skills Marketplace / Third-Party Plugin Ecosystem",
        "status": "partial",
        "description": (
            "Local skill registry view, plugin review matrix, dry-run review. "
            "No live marketplace. Manual security vetting required for all third-party plugins. "
            "See GET /v1/marketplace/status."
        ),
        "plan": "Phase B18",
        "blocker": "Live marketplace requires vetted plugin registry and security review pipeline.",
    },
    {
        "id": "org_mode",
        "name": "Team / Multi-User / Organization Mode Foundation",
        "status": "partial",
        "description": (
            "Org mode capability matrix, role model planning, dry-run invitation. "
            "Single-user mode only. Multi-user/org requires production auth (external gate). "
            "See GET /v1/org-mode/status."
        ),
        "plan": "Phase B19",
        "blocker": "Multi-user auth and RBAC not yet implemented (external gate).",
    },
    {
        "id": "device_controller",
        "name": "Robotics / Device Controller Foundation",
        "status": "partial",
        "description": (
            "Device controller capability matrix, dry-run command plans, safety gates. "
            "Simulator mode only. No physical device control. All commands require Tier 4 approval. "
            "See GET /v1/device-controller/status."
        ),
        "plan": "Phase B20",
        "blocker": "Device integration libraries not yet deployed (external gate).",
    },
    {
        "id": "autonomous_org_kernel",
        "name": "Autonomous Jarvis Organization Kernel",
        "status": "available",
        "description": (
            "Internal team registry, capability matrix, mission routing. "
            "One Jarvis PA identity enforced. No autonomous external execution without approval. "
            "See GET /v1/autonomous-org/status."
        ),
        "plan": "Phase C1",
    },
    {
        "id": "mission_control_c",
        "name": "Long-Horizon Mission Control (Phase C)",
        "status": "available",
        "description": (
            "Mission dashboard, milestone/checkpoint tracking, dependency graph, risk assessment. "
            "No unapproved execution. See GET /v1/mission-control/dashboard."
        ),
        "plan": "Phase C2",
    },
    {
        "id": "review_governance",
        "name": "Multi-Agent Review / Governance / Arbitration",
        "status": "available",
        "description": (
            "Reviewer lanes, decision records, arbitration proposals. "
            "Approval gates always active. No auto-approve. "
            "See GET /v1/review-governance/status."
        ),
        "plan": "Phase C3",
    },
    {
        "id": "product_readiness",
        "name": "Product / Multi-User Readiness Layer",
        "status": "partial",
        "description": (
            "Readiness matrix, tenancy/auth gap analysis, data isolation checklist. "
            "Multi-user not live. Single-user core ready. "
            "See GET /v1/product-readiness/matrix."
        ),
        "plan": "Phase C4",
        "blocker": "Multi-user auth and RBAC require external implementation.",
    },
    {
        "id": "marketplace_governance_c",
        "name": "Plugin / Marketplace Governance Layer (Phase C)",
        "status": "available",
        "description": (
            "Plugin review workflow, permission/risk scoring, version/rollback policy. "
            "Manual review required. No live marketplace. "
            "See GET /v1/marketplace-governance/status."
        ),
        "plan": "Phase C5",
    },
    {
        "id": "enterprise_governance",
        "name": "Enterprise-Grade Audit / Observability / Cost / Reliability",
        "status": "available",
        "description": (
            "Audit summary, reliability SLO metadata, cost/token tracking, incident status. "
            "Secret-safe. Live billing integration not deployed. "
            "See GET /v1/enterprise-governance/audit-summary."
        ),
        "plan": "Phase C6",
    },
    {
        "id": "scale_control",
        "name": "Cross-Device / Cloud / Workbench Scale Control Plane",
        "status": "partial",
        "description": (
            "Device/cloud capability matrix, MacBook-off readiness, queue status, parity status. "
            "Desktop active. Mobile PWA and Fargate require external deployment. "
            "See GET /v1/scale-control/status."
        ),
        "plan": "Phase C7",
        "blocker": "Mobile PWA and Fargate cloud execution require external deployment.",
    },
    {
        "id": "company_os_c",
        "name": "Autonomous Business / Company OS Scale Layer (Phase C)",
        "status": "available",
        "description": (
            "Company operating dashboard, research/admin/product/coding/legal/finance lanes. "
            "No live business execution. Local task/goal integration. "
            "See GET /v1/company-os/dashboard."
        ),
        "plan": "Phase C8",
    },
    {
        "id": "safety_simulation",
        "name": "Safety / Policy / Rollback / Simulation Framework",
        "status": "available",
        "description": (
            "Dry-run action simulations, rollback matrix, policy checks, blast-radius estimates. "
            "No real execution. Destructive actions always blocked. "
            "See GET /v1/safety-simulation/status."
        ),
        "plan": "Phase C9",
    },
    {
        "id": "control_tower",
        "name": "Phase C Control Tower + Core OS Completion Gate",
        "status": "available",
        "description": (
            "Consolidated phase/gate status across A/B/C, next decisions, completion score. "
            "No fake acceptance. Bryan decides all acceptances. "
            "See GET /v1/control-tower/status."
        ),
        "plan": "Phase C10",
    },
    # ── Phase C11-C20 ──────────────────────────────────────────────────────────
    {
        "id": "execution_readiness",
        "name": "Autonomous Execution Readiness Manager",
        "status": "available",
        "description": (
            "Execution readiness matrix across all action-bearing systems. "
            "Safe/unsafe/missing-gate classification. No real execution without approval. "
            "See GET /v1/execution-readiness/status."
        ),
        "plan": "Phase C11",
    },
    {
        "id": "action_planner",
        "name": "Cross-System Action Planner",
        "status": "available",
        "description": (
            "Multi-step cross-system plans with dependency ordering and owner approval checkpoints. "
            "Dry-run only. No real execution. See GET /v1/action-planner/systems."
        ),
        "plan": "Phase C12",
    },
    {
        "id": "policy_compiler",
        "name": "Approval Policy Compiler + Authority Matrix",
        "status": "available",
        "description": (
            "Authority matrix by domain, risk tiers, hard gate mapping. "
            "Approval gates never weakened. See GET /v1/policy-compiler/authority-matrix."
        ),
        "plan": "Phase C13",
    },
    {
        "id": "connector_readiness",
        "name": "Live Connector Readiness Verification Layer",
        "status": "available",
        "description": (
            "GitHub, Slack, Telegram, Tavily: LIVE_VERIFIED via read-only probes (Jun 25 2026). "
            "Gmail/AWS/S3/Fargate/Tailscale: presence-only. Notion: blocked (Bryan: retry later). "
            "See GET /v1/connector-readiness/status."
        ),
        "plan": "Phase C14",
        "blocker": "Notion blocked. Gmail/AWS/Fargate presence-only (not live-probed).",
        "live_verified": ["GitHub", "Slack", "Telegram", "Tavily"],
        "bryan_cleared": ["Gmail", "Slack", "Telegram", "GitHub", "Tavily", "AWS", "S3", "Fargate", "Tailscale"],
    },
    {
        "id": "ios_readiness",
        "name": "Native iOS / Mobile App Readiness Gate",
        "status": "available",
        "description": (
            "tauri ios init completed Jun 25 2026 — Xcode project at gen/apple/openjarvis-desktop.xcodeproj. "
            "Xcode 16.4, iOS Rust targets, CocoaPods, Apple certs all cleared. "
            "Native app distribution requires Xcode signing + TestFlight + Bryan auth. "
            "See GET /v1/ios-readiness/status."
        ),
        "plan": "Phase C15",
        "blocker": "Native iOS distribution (TestFlight/App Store) requires Bryan authorization.",
        "prerequisites_cleared": True,
        "tauri_ios_init_completed": True,
    },
    {
        "id": "signing_readiness",
        "name": "macOS Signing / Notarization Readiness Gate",
        "status": "available",
        "description": (
            "macOS app signed + notarized Jun 25 2026 via build-sign-personal.sh --notarize. "
            "spctl: accepted (source=Notarized Developer ID). stapler: validated. "
            "Developer ID Application: Bryan Aw (TQL4A44WDJ). "
            "See GET /v1/signing-readiness/status."
        ),
        "plan": "Phase C16",
        "blocker": "Installed app smoke requires Bryan to open/use packaged app.",
        "prerequisites_cleared": True,
        "actual_signing_completed": True,
        "actual_notarization_completed": True,
    },
    {
        "id": "cloud_readiness",
        "name": "Cloud / Fargate / Tailscale Execution Readiness Gate",
        "status": "partial",
        "description": (
            "AWS, S3, Fargate, Tailscale cleared by Bryan (presence-only). "
            "No live cloud execution in this sprint. Deployment requires Bryan authorization. "
            "See GET /v1/cloud-readiness/status."
        ),
        "plan": "Phase C17",
        "blocker": "Live cloud deployment requires Docker image + ECS task definition + Bryan authorization.",
        "prerequisites_cleared": True,
    },
    {
        "id": "final_smoke",
        "name": "Core OS Final Smoke Orchestrator",
        "status": "partial",
        "description": (
            "Smoke checklist API with endpoint health, frontend coverage, installed-app, and daily-driver slots. "
            "Manual proof required for all items. Auto-pass blocked. "
            "See GET /v1/final-smoke/checklist."
        ),
        "plan": "Phase C18",
        "blocker": "Installed app smoke and daily-driver held pending latest accepted build.",
    },
    {
        "id": "daily_driver",
        "name": "Daily-Driver Certification Harness",
        "status": "partial",
        "description": (
            "Certification checklist, blocker log, manual usage session tracker. "
            "Cannot auto-certify. Bryan sign-off required. "
            "See GET /v1/daily-driver/status."
        ),
        "plan": "Phase C19",
        "blocker": "No daily-driver sessions recorded yet. Held pending latest build.",
    },
    {
        "id": "core_completion",
        "name": "Jarvis Core OS Completion + Phase D Decision Gate",
        "status": "available",
        "description": (
            "Consolidated C11-C20 completion gate: phase status, readiness classification, Phase D options. "
            "No fake 100%. Bryan decides all. See GET /v1/core-completion/status."
        ),
        "plan": "Phase C20",
    },
]

_ROADMAP: List[Dict[str, Any]] = [
    {"plan": "Plan 1", "name": "Dual-Platform Jarvis Neural Command Center", "status": "ACCEPTED"},
    {"plan": "Plan 2", "name": "Full Mobile MacBook-Off Parity Runtime", "status": "ACCEPTED"},
    {"plan": "Post-Plan-2", "name": "Claude Code Automation Expansion", "status": "ACCEPTED"},
    {"plan": "Phase X", "name": "Universal Jarvis Decoupling (OMNIX → optional adapter)", "status": "ACCEPTED"},
    {"plan": "Plan 3", "name": "Voice / Wake / TTS", "status": "PARKED — text-first priority"},
    {"plan": "Plan 4-6", "name": "Text-First Jarvis OS Mega-Sprint", "status": "ACCEPTED"},
    {"plan": "Plan 4-6 B3/B5/B6", "name": "iOS/Productization + UI Surfaces + RoleSelector Wiring", "status": "ACCEPTED"},
    {"plan": "Plan 4-6 B7", "name": "Delegation Queue UI + Connector Status Polish", "status": "ACCEPTED"},
    {"plan": "Plan 4", "name": "Skills / Rules / Third-Party Skill Intake", "status": "COMPLETE"},
    {"plan": "Plan 5", "name": "Life-Business OS + Trusted Delegation + iOS", "status": "COMPLETE"},
    {"plan": "Plan 6", "name": "Chat Intelligence + Expert Roles + UI/UX Polish", "status": "COMPLETE"},
    {"plan": "Final Phase A", "name": "Production Certification + Daily-Driver Readiness", "status": "IN_PROGRESS"},
    {"plan": "Phase B1", "name": "Follow-Up Center + Life-Business OS Expansion", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B2", "name": "Routines / Cadence Command Center", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B3", "name": "Memory OS Deepening", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B4", "name": "Task / Project / Goal Command Center", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B5", "name": "Expert Organization Expansion", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B6", "name": "Desktop + Mobile UI/UX Product Polish", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B7", "name": "Skills / Plugin Expansion Pack", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B8", "name": "Connector Workflow Expansion", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B9", "name": "Proactive Operator Layer", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B10", "name": "Business / Admin Operator Expansion", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B11", "name": "Observability / Reliability / Cost Controls", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B12", "name": "Long-Horizon Goal Execution Foundation", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B13", "name": "Personal Finance / Admin OS", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B14", "name": "Research / Learning / Company-Building OS", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B15", "name": "Browser / Web Operator Foundation", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B16", "name": "Advanced Memory + Knowledge Graph", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B17", "name": "Multi-Device / Phone-Controlled Workbench", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B18", "name": "Skills Marketplace / Plugin Ecosystem", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B19", "name": "Team / Multi-User / Organization Mode", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase B20", "name": "Robotics / Device Controller Foundation", "status": "ACCEPTED_ON_HOLD"},
    {"plan": "Phase C1", "name": "Autonomous Jarvis Organization Kernel", "status": "ACCEPTED"},
    {"plan": "Phase C2", "name": "Long-Horizon Mission Control", "status": "ACCEPTED"},
    {"plan": "Phase C3", "name": "Multi-Agent Review / Governance / Arbitration", "status": "ACCEPTED"},
    {"plan": "Phase C4", "name": "Product / Multi-User Readiness Layer", "status": "ACCEPTED"},
    {"plan": "Phase C5", "name": "Plugin / Marketplace Governance Layer", "status": "ACCEPTED"},
    {"plan": "Phase C6", "name": "Enterprise-Grade Audit / Observability", "status": "ACCEPTED"},
    {"plan": "Phase C7", "name": "Cross-Device / Cloud Scale Control Plane", "status": "ACCEPTED"},
    {"plan": "Phase C8", "name": "Autonomous Business / Company OS Scale", "status": "ACCEPTED"},
    {"plan": "Phase C9", "name": "Safety / Policy / Rollback / Simulation", "status": "ACCEPTED"},
    {"plan": "Phase C10", "name": "Control Tower / Core OS Completion Gate", "status": "ACCEPTED"},
    {"plan": "Phase C11", "name": "Autonomous Execution Readiness Manager", "status": "ACCEPTED"},
    {"plan": "Phase C12", "name": "Cross-System Action Planner", "status": "ACCEPTED"},
    {"plan": "Phase C13", "name": "Approval Policy Compiler + Authority Matrix", "status": "ACCEPTED"},
    {"plan": "Phase C14", "name": "Live Connector Readiness Verification", "status": "ACCEPTED"},
    {"plan": "Phase C15", "name": "Native iOS / Mobile App Readiness Gate", "status": "ACCEPTED"},
    {"plan": "Phase C16", "name": "macOS Signing / Notarization Readiness Gate", "status": "ACCEPTED"},
    {"plan": "Phase C17", "name": "Cloud / Fargate / Tailscale Execution Readiness", "status": "ACCEPTED"},
    {"plan": "Phase C18", "name": "Core OS Final Smoke Orchestrator", "status": "ACCEPTED"},
    {"plan": "Phase C19", "name": "Daily-Driver Certification Harness", "status": "ACCEPTED"},
    {"plan": "Phase C20", "name": "Core OS Completion + Phase D Decision Gate", "status": "ACCEPTED"},
    {"plan": "Final Phase A Live Gate Closure", "name": "Live Manual Gate Closure Sprint", "status": "IN_PROGRESS"},
]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/v1/jarvis/capabilities")
async def get_capabilities(status: str = "") -> Dict[str, Any]:
    """Return what Jarvis can do right now.

    Honest partial/blocked/parked reporting — no fake AVAILABLE claims.
    """
    caps = _CAPABILITIES
    if status:
        caps = [c for c in caps if c.get("status") == status]
    available = [c for c in _CAPABILITIES if c.get("status") == "available"]
    partial = [c for c in _CAPABILITIES if c.get("status") == "partial"]
    parked = [c for c in _CAPABILITIES if c.get("status") == "parked"]
    not_started = [c for c in _CAPABILITIES if c.get("status") == "not_started"]
    return {
        "capabilities": caps,
        "summary": {
            "total": len(_CAPABILITIES),
            "available": len(available),
            "partial": len(partial),
            "parked": len(parked),
            "not_started": len(not_started),
        },
        "identity": "Jarvis — one unified PA voice",
        "text_first": True,
        "voice_status": "PARKED",
    }


@router.get("/v1/jarvis/status")
async def get_jarvis_status() -> Dict[str, Any]:
    """Current Jarvis system status snapshot."""
    available_count = sum(1 for c in _CAPABILITIES if c.get("status") == "available")
    total_count = len(_CAPABILITIES)
    return {
        "name": "Jarvis",
        "identity": "One unified PA voice — text-first",
        "plan_state": {
            "plan_1": "ACCEPTED",
            "plan_2": "ACCEPTED",
            "post_plan2_automation": "ACCEPTED",
            "phase_x_decoupling": "ACCEPTED",
            "plan_3_voice": "PARKED",
            "plan_4_6_mega_sprint": "ACCEPTED",
            "final_phase_a": "IN_PROGRESS",
            "phase_b1_follow_up_center": "IN_PROGRESS",
            "phase_b2_routines": "IN_PROGRESS",
            "phase_b3_memory_os": "IN_PROGRESS",
            "phase_b4_command_center": "IN_PROGRESS",
            "phase_b5_expert_org": "IN_PROGRESS",
            "phase_b6_ui_polish": "IN_PROGRESS",
            "phase_b7_skills_expansion": "IN_PROGRESS",
            "phase_b8_connector_workflows": "IN_PROGRESS",
            "phase_b9_proactive_operator": "IN_PROGRESS",
            "phase_b10_business_admin": "IN_PROGRESS",
            "phase_b11_observability": "IN_PROGRESS",
            "phase_b12_long_horizon": "IN_PROGRESS",
            "phase_b13_finance_admin": "IN_PROGRESS",
            "phase_b14_research_os": "IN_PROGRESS",
            "phase_b15_browser_operator": "IN_PROGRESS",
            "phase_b16_memory_graph": "IN_PROGRESS",
            "phase_b17_multi_device": "IN_PROGRESS",
            "phase_b18_marketplace": "IN_PROGRESS",
            "phase_b19_org_mode": "IN_PROGRESS",
            "phase_b20_device_controller": "IN_PROGRESS",
            "phase_c1_autonomous_org": "ACCEPTED",
            "phase_c2_mission_control": "ACCEPTED",
            "phase_c3_review_governance": "ACCEPTED",
            "phase_c4_product_readiness": "ACCEPTED",
            "phase_c5_marketplace_governance": "ACCEPTED",
            "phase_c6_enterprise_governance": "ACCEPTED",
            "phase_c7_scale_control": "ACCEPTED",
            "phase_c8_company_os": "ACCEPTED",
            "phase_c9_safety_simulation": "ACCEPTED",
            "phase_c10_control_tower": "ACCEPTED",
            "phase_c11_execution_readiness": "ACCEPTED",
            "phase_c12_action_planner": "ACCEPTED",
            "phase_c13_policy_compiler": "ACCEPTED",
            "phase_c14_connector_readiness": "ACCEPTED",
            "phase_c15_ios_readiness": "ACCEPTED",
            "phase_c16_signing_readiness": "ACCEPTED",
            "phase_c17_cloud_readiness": "ACCEPTED",
            "phase_c18_final_smoke": "ACCEPTED",
            "phase_c19_daily_driver": "ACCEPTED",
            "phase_c20_core_completion": "ACCEPTED",
            "phase_b1_to_b20": "ACCEPTED_ON_HOLD",
            "phase_c1_to_c10": "ACCEPTED",
            "phase_c11_to_c20": "ACCEPTED",
            "final_phase_a_live_gate_closure": "IN_PROGRESS",
        },
        "capability_summary": {
            "available": available_count,
            "total": total_count,
        },
        "text_first": True,
        "voice_parked": True,
        "mobile_parity": "available",
        "approval_gates": "active",
        "fake_claims": False,
    }


@router.get("/v1/jarvis/roadmap")
async def get_roadmap() -> Dict[str, Any]:
    """Current Jarvis roadmap and plan acceptance state."""
    return {
        "roadmap": _ROADMAP,
        "active_sprint": "FINAL_PHASE_A_INSTALLED_APP_UI_UNIFICATION_CORRECTIVE_SPRINT",
        "next": "Installed-app UI corrective sprint in progress. UI unified: mission mode with status strip, system mode demoted to secondary rail. Rebuild+notarize pending. Installed-app-smoke visual needs Bryan proof after rebuild. Daily-driver cert needs Bryan sessions. Plan 3 voice parked. Phase B accepted, on hold.",
        "note": "Only Bryan can mark plans as ACCEPTED.",
    }


__all__ = ["router"]
