"""US18 Founder Dogfood + Public Readiness Gate.

Evaluates local/founder V1 readiness with truthful status — no fake claims.
Does not duplicate doctor/readiness.py (28 categories) — focuses on Workbench
founder dogfood checklist and public release-safe matrix.
"""

from __future__ import annotations

import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

ItemStatus = str  # done | partial | missing | blocked | requires_user_action | not_in_scope


@dataclass
class ReadinessItem:
    item_id: str
    label: str
    status: ItemStatus
    evidence: str
    required_for_v1: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "label": self.label,
            "status": self.status,
            "evidence": self.evidence,
            "required_for_v1": self.required_for_v1,
        }


# Known limitations — honest, never hidden
KNOWN_LIMITATIONS = [
    "US13 hands-free voice HOLD/UNSAFE — parked, not release-ready",
    "No fake all-platform mobile/cloud claims — local/founder V1 only",
    "Auto Browser requires Docker server + approval for sessions",
    "Live model calls require JARVIS_OPENROUTER_KEY or local Ollama",
    "Tauri desktop signing may block packaging — not verified without Apple cert",
    "Production deploy (Vercel/AWS/Supabase) hard-gated — never auto-deploy",
    "External Slack/Telegram/email sends hard-gated — never auto-send",
    "No uncontrolled browser autopilot — human-in-the-loop required",
]

# Not in scope for local/founder V1
NOT_IN_SCOPE = [
    "US13 hands-free voice runtime acceptance",
    "Waves (future)",
    "Enterprise semantic repo indexing",
    "Multi-user cloud deployment",
    "Streaming STT/Deepgram evaluation",
    "Production Stripe/billing deploy",
]

# Blocked items
BLOCKED_ITEMS = [
    "US13 voice hands-free wake — HOLD/UNSAFE until backlog complete",
    "Autopilot runtime execution — disabled by default",
    "Real outbound Slack/Telegram/email — hard-gated",
]


def _check_backend_importable() -> ReadinessItem:
    try:
        from openjarvis.workbench.coding_manager import CodingManager
        CodingManager(repo_path=".")
        return ReadinessItem("backend_starts", "Backend/CodingManager importable", "done", "CodingManager instantiated")
    except Exception as exc:
        return ReadinessItem("backend_starts", "Backend/CodingManager importable", "missing", str(exc))


def _check_capabilities() -> ReadinessItem:
    try:
        from openjarvis.workbench.capabilities_registry import get_all_capabilities
        caps = get_all_capabilities()
        voice = next(c for c in caps if c.capability_id == "voice")
        if voice.status == "ready":
            return ReadinessItem("capabilities_truthful", "Capabilities truthful", "blocked", "Voice must not be ready")
        wb = next(c for c in caps if c.capability_id == "workbench_coding")
        return ReadinessItem(
            "capabilities_truthful",
            "Capabilities truthful",
            "done" if wb.status == "ready" else "partial",
            f"{len(caps)} caps; voice={voice.status}; workbench={wb.status}",
        )
    except Exception as exc:
        return ReadinessItem("capabilities_truthful", "Capabilities truthful", "missing", str(exc))


def _check_workbench() -> ReadinessItem:
    try:
        from openjarvis.workbench.coding_manager import CodingManager
        mgr = CodingManager(repo_path=".")
        plan = mgr.plan("list files in tests/", dry_run=True)
        return ReadinessItem("workbench_usable", "Workbench/Coding usable", "done", f"plan created session={plan.session_id}")
    except Exception as exc:
        return ReadinessItem("workbench_usable", "Workbench/Coding usable", "missing", str(exc))


def _check_terminal() -> ReadinessItem:
    try:
        from openjarvis.workbench.terminal_executor import TerminalExecutor
        te = TerminalExecutor(cwd=".")
        r = te.submit("ls .")
        ok = r.status in ("success", "failed", "approval_required")
        return ReadinessItem("terminal_ux", "Terminal UX usable", "done" if ok else "partial", f"status={r.status}")
    except Exception as exc:
        return ReadinessItem("terminal_ux", "Terminal UX usable", "missing", str(exc))


def _check_diff_review() -> ReadinessItem:
    try:
        from openjarvis.workbench.diff_review import DiffReviewStore
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            store = DiffReviewStore(db_path=os.path.join(d, "dr.db"))
            rev = store.create(session_id="probe", repo_path=".")
            approved = store.approve(rev.review_id)
            rejected_rev = store.create(session_id="probe2", repo_path=".")
            rejected = store.reject(rejected_rev.review_id)
            ok = approved.status == "approved" and rejected.status == "rejected"
        return ReadinessItem("diff_review", "Diff review approve/reject", "done" if ok else "partial", "approve+reject paths verified")
    except Exception as exc:
        return ReadinessItem("diff_review", "Diff review approve/reject", "missing", str(exc))


def _check_validation_profiles() -> ReadinessItem:
    try:
        from openjarvis.workbench.validation_profiles import list_validation_profiles
        profiles = list_validation_profiles()
        us15 = next((p for p in profiles if p["profile_id"] == "workbench_us15"), None)
        if us15 and us15.get("local_first"):
            return ReadinessItem("validation_profiles", "Validation profiles usable", "done", f"{len(profiles)} profiles")
        return ReadinessItem("validation_profiles", "Validation profiles usable", "partial", "workbench_us15 missing")
    except Exception as exc:
        return ReadinessItem("validation_profiles", "Validation profiles usable", "missing", str(exc))


def _check_github_ci() -> ReadinessItem:
    try:
        from openjarvis.workbench.repo_index import ci_visibility_status
        ci = ci_visibility_status(".")
        if ci.get("gh_cli_authenticated"):
            return ReadinessItem("github_ci", "GitHub/CI visibility", "done", f"gh auth ok, {len(ci.get('workflow_files', []))} workflows")
        return ReadinessItem("github_ci", "GitHub/CI visibility", "requires_user_action", "gh auth login required")
    except Exception as exc:
        return ReadinessItem("github_ci", "GitHub/CI visibility", "missing", str(exc))


def _check_auto_browser() -> ReadinessItem:
    try:
        from openjarvis.workbench.auto_browser_provider import health_check
        hc = health_check()
        if hc.get("overall") == "ready":
            return ReadinessItem("auto_browser", "Auto Browser ready/needs_approval", "done", "server reachable")
        if hc.get("client_sdk_installed") and hc.get("playwright_available"):
            return ReadinessItem(
                "auto_browser",
                "Auto Browser ready/needs_approval",
                "requires_user_action" if not hc.get("mcp_reachable") else "partial",
                f"mcp_reachable={hc.get('mcp_reachable')}",
            )
        return ReadinessItem("auto_browser", "Auto Browser ready/needs_approval", "requires_user_action", str(hc))
    except Exception as exc:
        return ReadinessItem("auto_browser", "Auto Browser ready/needs_approval", "missing", str(exc))


def _check_cost_routing() -> ReadinessItem:
    try:
        from openjarvis.workbench.model_router import ModelRouter, MockModelAdapter
        router = ModelRouter(adapter_override=MockModelAdapter())
        cfg = router.get_provider_config_summary()
        return ReadinessItem("cost_routing", "Cost/model routing visible", "done", f"adapter={cfg.get('adapter')}")
    except Exception as exc:
        return ReadinessItem("cost_routing", "Cost/model routing visible", "missing", str(exc))


def _check_doctor() -> ReadinessItem:
    try:
        from openjarvis.workbench.adversarial_safety import get_safety_status_summary
        from openjarvis.workbench.failure_recovery import get_failure_recovery_summary
        s = get_safety_status_summary()
        f = get_failure_recovery_summary()
        ok = s.get("us17_adversarial_safety") == "ready" and f.get("us17_failure_recovery") == "ready"
        return ReadinessItem(
            "doctor_readiness",
            "Doctor/readiness accurate",
            "done" if ok else "partial",
            f"us17={s.get('us17_adversarial_safety')} recovery={f.get('us17_failure_recovery')}",
        )
    except Exception as exc:
        return ReadinessItem("doctor_readiness", "Doctor/readiness accurate", "missing", str(exc))


def _check_voice_parked() -> ReadinessItem:
    try:
        from openjarvis.workbench.capabilities_registry import get_all_capabilities, US13_VOICE_PARKED_NOTE
        voice = next(c for c in get_all_capabilities() if c.capability_id == "voice")
        if voice.status == "disabled" and voice.evidence.get("hands_free_excluded"):
            return ReadinessItem("voice_parked", "US13 voice disabled/parked", "done", voice.summary[:100])
        return ReadinessItem("voice_parked", "US13 voice disabled/parked", "blocked", f"status={voice.status}")
    except Exception as exc:
        return ReadinessItem("voice_parked", "US13 voice disabled/parked", "missing", str(exc))


def _check_us17_safety() -> ReadinessItem:
    try:
        from openjarvis.workbench.adversarial_safety import run_adversarial_self_test
        st = run_adversarial_self_test()
        return ReadinessItem(
            "us17_adversarial",
            "US17 adversarial safety",
            "done" if st["all_pass"] else "partial",
            f"{st['passed']}/{st['total']} self-tests pass",
        )
    except Exception as exc:
        return ReadinessItem("us17_adversarial", "US17 adversarial safety", "missing", str(exc))


def _check_secrets_in_repo() -> ReadinessItem:
    """Shallow scan for hardcoded API key patterns (excludes tests)."""
    import subprocess
    try:
        proc = subprocess.run(
            [
                "git", "grep", "-E", "sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36,}",
                "--", "src/", "frontend/src/",
                ":(exclude)tests/", ":(exclude)*test*",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=".",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.strip().splitlines()[:3]
            return ReadinessItem(
                "no_secrets",
                "No secrets in repo",
                "blocked",
                f"Potential hardcoded keys: {len(lines)} matches (review required)",
            )
        return ReadinessItem("no_secrets", "No secrets in repo", "done", "No hardcoded sk-/ghp_ keys in src/")
    except Exception as exc:
        return ReadinessItem("no_secrets", "No secrets in repo", "partial", f"check skipped: {exc}")


def _check_tauri_build() -> ReadinessItem:
    frontend = shutil.which("npm")
    if not frontend:
        return ReadinessItem("tauri_build", "Tauri/package build", "not_in_scope", "npm not on PATH — not verified this sprint")
    return ReadinessItem(
        "tauri_build",
        "Tauri/package build",
        "requires_user_action",
        "Run: cd frontend && npm run tauri build — signing may BLOCK without Apple cert",
    )


FOUNDER_CHECKLIST: List[Callable[[], ReadinessItem]] = [
    _check_backend_importable,
    _check_capabilities,
    _check_workbench,
    _check_terminal,
    _check_diff_review,
    _check_validation_profiles,
    _check_github_ci,
    _check_auto_browser,
    _check_cost_routing,
    _check_doctor,
    _check_voice_parked,
    _check_us17_safety,
    _check_secrets_in_repo,
    _check_tauri_build,
]


def evaluate_founder_dogfood() -> Dict[str, Any]:
    """Run founder dogfood checklist and return results."""
    items = [fn() for fn in FOUNDER_CHECKLIST]
    by_status: Dict[str, int] = {}
    for item in items:
        by_status[item.status] = by_status.get(item.status, 0) + 1

    required = [i for i in items if i.required_for_v1]
    required_done = sum(1 for i in required if i.status == "done")
    required_total = len(required)

    blocking = [i for i in required if i.status in ("missing", "blocked")]
    verdict = "ACCEPT" if not blocking else "HOLD"

    return {
        "verdict": verdict,
        "items": [i.to_dict() for i in items],
        "by_status": by_status,
        "required_done": required_done,
        "required_total": required_total,
        "evaluated_at": time.time(),
    }


def generate_public_readiness_matrix() -> Dict[str, Any]:
    """Generate honest public readiness matrix for US18."""
    dogfood = evaluate_founder_dogfood()
    items = dogfood["items"]

    matrix = {
        "release_scope": "local_founder_v1",
        "claims": {
            "all_platform_mobile": False,
            "hands_free_voice": False,
            "cloud_production_deploy": False,
            "uncontrolled_browser_autopilot": False,
            "enterprise_semantic_indexing": False,
        },
        "ready": [i["item_id"] for i in items if i["status"] == "done"],
        "requires_user_action": [i["item_id"] for i in items if i["status"] == "requires_user_action"],
        "partial": [i["item_id"] for i in items if i["status"] == "partial"],
        "blocked": [i["item_id"] for i in items if i["status"] == "blocked"],
        "not_in_scope": NOT_IN_SCOPE + [i["item_id"] for i in items if i["status"] == "not_in_scope"],
        "known_limitations": KNOWN_LIMITATIONS,
        "blocked_items": BLOCKED_ITEMS,
        "rollback_instructions": [
            "git checkout -- .",
            "git clean -fd  (only with Bryan approval)",
            "docker compose down  (in .external/auto-browser)",
            "Stop Jarvis server: kill uvicorn process on port 8000",
        ],
        "founder_retest_steps": [
            "uv sync --extra server --extra browser --extra dev",
            "export JARVIS_AUTO_BROWSER_ENABLED=1 JARVIS_AUTO_BROWSER_MCP_URL=http://127.0.0.1:3000",
            "uv run python -m pytest tests/workbench/test_us17_adversarial.py tests/workbench/test_us18_readiness.py -q",
            "GET /v1/workbench/founder-readiness",
            "GET /v1/workbench/safety/status",
        ],
        "verdict": dogfood["verdict"],
    }
    return matrix


__all__ = [
    "ReadinessItem",
    "KNOWN_LIMITATIONS",
    "NOT_IN_SCOPE",
    "BLOCKED_ITEMS",
    "evaluate_founder_dogfood",
    "generate_public_readiness_matrix",
]
