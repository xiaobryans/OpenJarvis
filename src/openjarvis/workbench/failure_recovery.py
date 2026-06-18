"""US17 Failure Recovery — stop-on-blocker guidance and recovery playbooks.

Provides structured recovery guidance for known failure modes without
duplicating repair_loop (bounded retry) or CodingManager stop-on-blocker logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Failure type constants
FAILURE_VALIDATION = "validation_failed"
FAILURE_STOP_ON_BLOCKER = "stop_on_blocker"
FAILURE_AUTO_BROWSER_UNAVAILABLE = "auto_browser_unavailable"
FAILURE_MODEL_UNAVAILABLE = "model_provider_unavailable"
FAILURE_GITHUB_CI_UNAVAILABLE = "github_ci_unavailable"
FAILURE_COST_BUDGET = "cost_budget_exceeded"
FAILURE_VOICE_PARKED = "voice_parked_disabled"
FAILURE_STALE_PROCESS = "stale_process_port_conflict"
FAILURE_APPROVAL_PENDING = "approval_pending"
FAILURE_DIFF_REJECTED = "diff_rejected"
FAILURE_TERMINAL_BLOCKED = "terminal_command_blocked"
FAILURE_DEPLOY_BLOCKED = "production_deploy_blocked"


@dataclass
class RecoveryGuidance:
    failure_type: str
    stop: bool
    retry_allowed: bool
    rollback_steps: List[str]
    recovery_steps: List[str]
    user_action_required: bool
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_type": self.failure_type,
            "stop": self.stop,
            "retry_allowed": self.retry_allowed,
            "rollback_steps": self.rollback_steps,
            "recovery_steps": self.recovery_steps,
            "user_action_required": self.user_action_required,
            "summary": self.summary,
        }


_RECOVERY_PLAYBOOK: Dict[str, Dict[str, Any]] = {
    FAILURE_VALIDATION: {
        "stop": False,
        "retry_allowed": True,
        "rollback_steps": ["git checkout -- .", "Review diff before retry"],
        "recovery_steps": [
            "Read validation output for failing test/file",
            "Fix the specific failure (bounded repair loop max 3 attempts)",
            "Re-run validation profile: GET /v1/workbench/validation-profiles",
            "Do not re-verify accepted checkpoints unless touched",
        ],
        "user_action_required": False,
        "summary": "Validation failed — bounded repair then re-validate",
    },
    FAILURE_STOP_ON_BLOCKER: {
        "stop": True,
        "retry_allowed": False,
        "rollback_steps": ["Review event log for blocker reason", "git status --short"],
        "recovery_steps": [
            "Inspect blocker in Workbench event log",
            "Resolve root cause before continuing subtask chain",
            "Re-plan with stop_on_blocker=True if risk remains",
        ],
        "user_action_required": True,
        "summary": "Stop-on-blocker engaged — halt chain until blocker resolved",
    },
    FAILURE_AUTO_BROWSER_UNAVAILABLE: {
        "stop": True,
        "retry_allowed": True,
        "rollback_steps": [],
        "recovery_steps": [
            "Check: curl http://127.0.0.1:3000/healthz",
            "If down: cd .external/auto-browser && docker compose up -d",
            "Set JARVIS_AUTO_BROWSER_ENABLED=1 and JARVIS_AUTO_BROWSER_MCP_URL=http://127.0.0.1:3000",
            "Rerun: GET /v1/workbench/auto-browser/status",
        ],
        "user_action_required": True,
        "summary": "Auto Browser server unreachable — start Docker stack",
    },
    FAILURE_MODEL_UNAVAILABLE: {
        "stop": True,
        "retry_allowed": True,
        "rollback_steps": [],
        "recovery_steps": [
            "Check JARVIS_OPENROUTER_KEY or local Ollama status",
            "ModelRouter falls back to MockModelAdapter when no key (dry-run safe)",
            "For live calls: set provider env and rerun GET /v1/workbench/provider-config",
        ],
        "user_action_required": True,
        "summary": "Model provider unavailable — configure or use mock/dry-run",
    },
    FAILURE_GITHUB_CI_UNAVAILABLE: {
        "stop": False,
        "retry_allowed": True,
        "rollback_steps": [],
        "recovery_steps": [
            "Run: gh auth login",
            "Verify: gh auth status",
            "Rerun: GET /v1/workbench/ci-status",
        ],
        "user_action_required": True,
        "summary": "GitHub CLI not authenticated — gh auth required for live CI",
    },
    FAILURE_COST_BUDGET: {
        "stop": True,
        "retry_allowed": False,
        "rollback_steps": [],
        "recovery_steps": [
            "Review cost summary: GET /v1/workbench/cost/{session_id}",
            "Premium tier blocked when session/daily cap exceeded",
            "Bryan explicit approval required to override budget cap",
        ],
        "user_action_required": True,
        "summary": "Cost budget exceeded — premium tier blocked",
    },
    FAILURE_VOICE_PARKED: {
        "stop": True,
        "retry_allowed": False,
        "rollback_steps": [],
        "recovery_steps": [
            "US13 voice HOLD/UNSAFE — do not use hands-free voice for validation",
            "Voice capability must remain disabled until US13 backlog complete",
            "Use Workbench/terminal paths instead",
        ],
        "user_action_required": False,
        "summary": "Voice parked — use non-voice paths",
    },
    FAILURE_STALE_PROCESS: {
        "stop": True,
        "retry_allowed": True,
        "rollback_steps": [],
        "recovery_steps": [
            "Check for stale backend on port 8000/3000: lsof -i :8000",
            "Kill stale process if safe: kill <pid>",
            "Restart Jarvis server cleanly",
            "Do not attach to stale backend servers (US13 rule)",
        ],
        "user_action_required": True,
        "summary": "Stale process/port conflict — restart backend cleanly",
    },
    FAILURE_APPROVAL_PENDING: {
        "stop": True,
        "retry_allowed": False,
        "rollback_steps": [],
        "recovery_steps": [
            "Review pending approvals: GET /v1/workbench/terminal/pending",
            "Approve via POST /v1/workbench/approve or /terminal/approve",
            "Never bypass approval gates",
        ],
        "user_action_required": True,
        "summary": "Approval pending — manager must approve before execution",
    },
    FAILURE_DIFF_REJECTED: {
        "stop": True,
        "retry_allowed": True,
        "rollback_steps": ["git checkout -- .", "git clean -fd (only if Bryan approves)"],
        "recovery_steps": [
            "Diff review rejected — changes NOT applied (by design)",
            "Review reject reason in DiffReviewStore audit log",
            "Re-plan and regenerate diff if needed",
        ],
        "user_action_required": False,
        "summary": "Diff rejected — no silent apply; re-plan if needed",
    },
    FAILURE_TERMINAL_BLOCKED: {
        "stop": True,
        "retry_allowed": False,
        "rollback_steps": [],
        "recovery_steps": [
            "Command blocked by safety policy — review blocked_reason in result",
            "Use approval flow if command is legitimately needed",
            "Never bypass always-blocked patterns (rm -rf /, pipe-to-shell, etc.)",
        ],
        "user_action_required": True,
        "summary": "Terminal command blocked by safety policy",
    },
    FAILURE_DEPLOY_BLOCKED: {
        "stop": True,
        "retry_allowed": False,
        "rollback_steps": [],
        "recovery_steps": [
            "Production deploy is hard-gated — requires explicit Bryan approval",
            "No Vercel/AWS/Supabase deploy without approval",
        ],
        "user_action_required": True,
        "summary": "Production deploy blocked — hard gate",
    },
}


def get_recovery_guidance(failure_type: str, **context: Any) -> RecoveryGuidance:
    """Return structured recovery guidance for a failure type."""
    playbook = _RECOVERY_PLAYBOOK.get(failure_type)
    if not playbook:
        return RecoveryGuidance(
            failure_type=failure_type,
            stop=True,
            retry_allowed=False,
            rollback_steps=["Review logs and event log for session"],
            recovery_steps=[f"Unknown failure type: {failure_type} — inspect manually"],
            user_action_required=True,
            summary=f"Unknown failure: {failure_type}",
        )
    return RecoveryGuidance(
        failure_type=failure_type,
        stop=playbook["stop"],
        retry_allowed=playbook["retry_allowed"],
        rollback_steps=list(playbook["rollback_steps"]),
        recovery_steps=list(playbook["recovery_steps"]),
        user_action_required=playbook["user_action_required"],
        summary=playbook["summary"],
    )


def diagnose_subsystem_failures() -> Dict[str, Any]:
    """Probe subsystems and return failure recovery status for each."""
    results: Dict[str, Any] = {}

    # Auto Browser
    try:
        from openjarvis.workbench.auto_browser_provider import health_check
        hc = health_check()
        if hc.get("overall") != "ready":
            g = get_recovery_guidance(FAILURE_AUTO_BROWSER_UNAVAILABLE)
            results["auto_browser"] = {"status": "unavailable", "recovery": g.to_dict()}
        else:
            results["auto_browser"] = {"status": "ready"}
    except Exception as exc:
        results["auto_browser"] = {"status": "error", "error": str(exc)}

    # GitHub/CI
    try:
        from openjarvis.workbench.repo_index import ci_visibility_status
        ci = ci_visibility_status(".")
        if not ci.get("gh_cli_authenticated"):
            g = get_recovery_guidance(FAILURE_GITHUB_CI_UNAVAILABLE)
            results["github_ci"] = {"status": "requires_setup", "recovery": g.to_dict()}
        else:
            results["github_ci"] = {"status": "ready"}
    except Exception as exc:
        results["github_ci"] = {"status": "error", "error": str(exc)}

    # Voice parked
    g = get_recovery_guidance(FAILURE_VOICE_PARKED)
    results["voice"] = {"status": "parked", "recovery": g.to_dict()}

    # Model provider
    try:
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter
        router = ModelRouter(adapter_override=MockModelAdapter())
        cfg = router.get_provider_config_summary()
        if cfg.get("openrouter_key_value") == "not_set":
            g = get_recovery_guidance(FAILURE_MODEL_UNAVAILABLE)
            results["model_provider"] = {"status": "mock_only", "recovery": g.to_dict()}
        else:
            results["model_provider"] = {"status": "configured"}
    except Exception as exc:
        results["model_provider"] = {"status": "error", "error": str(exc)}

    return results


def get_failure_recovery_summary() -> Dict[str, Any]:
    """US17 failure recovery status for doctor/readiness."""
    subsystems = diagnose_subsystem_failures()
    playbook_count = len(_RECOVERY_PLAYBOOK)
    return {
        "us17_failure_recovery": "ready",
        "playbook_entries": playbook_count,
        "subsystems": subsystems,
        "stop_on_blocker": True,
        "bounded_repair_max_attempts": 3,
    }


__all__ = [
    "RecoveryGuidance",
    "FAILURE_VALIDATION",
    "FAILURE_STOP_ON_BLOCKER",
    "FAILURE_AUTO_BROWSER_UNAVAILABLE",
    "FAILURE_MODEL_UNAVAILABLE",
    "FAILURE_GITHUB_CI_UNAVAILABLE",
    "FAILURE_COST_BUDGET",
    "FAILURE_VOICE_PARKED",
    "FAILURE_STALE_PROCESS",
    "get_recovery_guidance",
    "diagnose_subsystem_failures",
    "get_failure_recovery_summary",
]
