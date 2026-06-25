"""Jarvis US8 Catalog — Ultra Sprint 8 tool pack.

51 new tools across 8 phases:

Phase B — Project onboarding (3):
  project.onboarding_status, project.link_wizard_state, project.source_config_needed

Phase C — Automation policy (8):
  automation.policy.get, automation.policy.evaluate,
  automation.approval.request, automation.approval.approve,
  automation.approval.reject, automation.approval.list,
  automation.autopilot.run_once, automation.autopilot.status

Phase D — Voice (9):
  voice.status, voice.listen_status, voice.wake_word_status,
  voice.parse_approval, voice.approval_challenge, voice.approval_confirm,
  voice.command_preview, voice.tts_test, voice.stt_test

Phase E — Desktop (9):
  desktop.permissions_status, desktop.operator_status,
  desktop.open_app_plan, desktop.focus_app_plan,
  desktop.screenshot_status, desktop.safe_demo,
  browser.operator_status, browser.open_url_plan, browser.read_only_plan

Phase F — Mobile (6):
  mobile.pending_approvals, mobile.approval_payload,
  mobile.safe_access_instructions,
  telegram.command_preview, telegram.approval_preview, telegram.command_status

Phase G — Ops (6):
  ops.runner_status, ops.run_once, ops.schedule_plan,
  ops.install_plan, ops.stop_plan, ops.dry_run_schedule

Phase H — Connectors (10):
  slack.connector_status, slack.draft_test_send,
  telegram.connector_status, telegram.draft_test_send,
  web.search_status,
  github.connector_status, github.local_remote_info,
  openclaw.workspace_status, openclaw.handoff_read, openclaw.link_status

All 51 tools are AVAILABLE.
Governance: no real sends, no token printing, no destructive actions.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from openjarvis.tools.jarvis_registry import ToolRegistry, ToolSpec, ToolStatus

logger = logging.getLogger(__name__)


# ===========================================================================
# PHASE B — Project onboarding executors
# ===========================================================================


def _exec_project_onboarding_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.projects.source_links import ProjectSourceRegistry
    from openjarvis.governance.constitution import ProjectRegistry

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    linkage = ProjectSourceRegistry.get_linkage_status(project_id)

    try:
        project = ProjectRegistry.get(project_id)
        project_name = project.name if project else project_id
    except Exception:
        project_name = project_id

    is_placeholder = linkage.get("linkage_status") == "placeholder"
    is_not_configured = linkage.get("linkage_status") == "not_configured"

    status_message = ""
    if is_placeholder:
        status_message = (
            f"OMNIX is registered but local_repo points to the Jarvis/OpenJarvis codebase. "
            "Real OMNIX source is not configured."
        )
    elif is_not_configured:
        status_message = "No sources configured for this project."
    else:
        status_message = f"Project linkage status: {linkage.get('linkage_status')}"

    config_needed = []
    if is_placeholder or is_not_configured:
        config_needed = [
            {
                "step": 1,
                "field": "JARVIS_PROJECT_OMNIX_REPO_PATH",
                "description": "Real local OMNIX repo path (not the Jarvis codebase)",
                "example": "/path/to/real/omnix/repo",
                "tool": "project.link_local_repo",
            },
            {
                "step": 2,
                "field": "JARVIS_PROJECT_OMNIX_GITHUB_REMOTE",
                "description": "OMNIX GitHub owner/repo remote URL",
                "example": "https://github.com/owner/omnix",
                "tool": "project.link_runtime_endpoint",
            },
            {
                "step": 3,
                "field": "OPENCLAW_WORKSPACE_PATH",
                "description": "OpenClaw workspace path (read-only)",
                "example": "/path/to/openclaw/workspace",
                "tool": "project.link_openclaw_workspace",
            },
            {
                "step": 4,
                "field": "OPENCLAW_HANDOFF_PATH",
                "description": "OpenClaw handoff file or directory",
                "example": "/path/to/openclaw/handoff.md",
                "tool": "project.link_openclaw_workspace",
            },
        ]

    return {
        "project_id": project_id,
        "project_name": project_name,
        "status_message": status_message,
        "linkage_status": linkage.get("linkage_status", "unknown"),
        "primary_operational": linkage.get("primary_operational", 0),
        "primary_total": linkage.get("primary_total", 4),
        "config_needed": config_needed,
        "readiness_impact": (
            "HOLD — project_linkage category fails when no real source is linked"
            if (is_placeholder or is_not_configured) else "pass"
        ),
    }


def _exec_project_link_wizard_state(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceRegistry,
        ProjectSourceLinkType,
        ProjectSourceStatus,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    links = ProjectSourceRegistry.list_for_project(project_id)
    link_map = {lnk.link_type: lnk for lnk in links}

    steps = []
    source_types = [
        (ProjectSourceLinkType.LOCAL_REPO, "Local repo path", True),
        (ProjectSourceLinkType.GITHUB_REMOTE, "GitHub remote URL", False),
        (ProjectSourceLinkType.OPENCLAW_WORKSPACE, "OpenClaw workspace path", False),
        (ProjectSourceLinkType.OPENCLAW_HANDOFF, "OpenClaw handoff path", False),
        (ProjectSourceLinkType.HANDOFF_FILE, "Handoff file", False),
        (ProjectSourceLinkType.MEMORY_NAMESPACE, "Memory namespace", False),
    ]

    for stype, label, is_primary in source_types:
        link = link_map.get(stype)
        step_status = ProjectSourceStatus.NOT_CONFIGURED
        path_or_url = ""
        if link:
            step_status = link.status
            path_or_url = link.path_or_url
        steps.append({
            "source_type": stype,
            "label": label,
            "is_primary": is_primary,
            "status": step_status,
            "path_or_url": path_or_url,
            "is_linked": step_status in (
                ProjectSourceStatus.LINKED,
                ProjectSourceStatus.READY_READ_ONLY,
            ),
        })

    linked_count = sum(1 for s in steps if s["is_linked"])
    primary_linked = sum(1 for s in steps if s["is_linked"] and s["is_primary"])

    return {
        "project_id": project_id,
        "wizard_complete": primary_linked >= 1,
        "linked_count": linked_count,
        "primary_linked": primary_linked,
        "steps": steps,
        "next_step": next(
            (s for s in steps if not s["is_linked"] and s["is_primary"]),
            next((s for s in steps if not s["is_linked"]), None),
        ),
    }


def _exec_project_source_config_needed(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.projects.source_links import (
        ProjectSourceRegistry,
        ProjectSourceStatus,
        make_future_project_source_template,
    )

    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    linkage = ProjectSourceRegistry.get_linkage_status(project_id)

    template = make_future_project_source_template("new_project")

    missing_steps = []
    for src in linkage.get("sources", []):
        if src.get("status") in (
            ProjectSourceStatus.NOT_CONFIGURED,
            ProjectSourceStatus.PLACEHOLDER,
            ProjectSourceStatus.MISSING,
        ):
            missing_steps.append({
                "source_type": src.get("link_type", ""),
                "status": src.get("status", ""),
                "path_or_url": src.get("path_or_url", ""),
                "action": f"project.link_{src.get('link_type', 'local_repo')} — provide real path",
            })

    return {
        "project_id": project_id,
        "linkage_status": linkage.get("linkage_status", "unknown"),
        "config_needed": missing_steps,
        "future_project_template": template,
        "omnix_specific_instruction": (
            "Provide real local OMNIX repo path or GitHub remote. "
            "Current local_repo points to the Jarvis/OpenJarvis codebase — not a valid OMNIX source."
        ) if linkage.get("linkage_status") == "placeholder" else None,
    }


# ===========================================================================
# PHASE C — Automation policy executors
# ===========================================================================


def _exec_automation_policy_get(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    return AutomationPolicy.get_policy_summary()


def _exec_automation_policy_evaluate(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    action_class = inputs.get("action_class", "")
    description = inputs.get("description", "")
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    if not action_class:
        return {"error": "action_class is required"}
    return AutomationPolicy.evaluate(action_class, description, project_id)


def _exec_automation_approval_request(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    action_class = inputs.get("action_class", "")
    description = inputs.get("description", "")
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    ttl = int(inputs.get("ttl_seconds", 300))
    if not action_class:
        return {"error": "action_class is required"}
    try:
        record = AutomationPolicy.request_approval(
            action_class, description, project_id, ttl_seconds=ttl
        )
        return {
            "ok": True,
            "approval": record.to_dict(),
        }
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


def _exec_automation_approval_approve(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    approval_id = inputs.get("approval_id", "")
    decided_by = inputs.get("decided_by", "bryan")
    phrase = inputs.get("confirmation_phrase", "")
    if not approval_id:
        return {"ok": False, "error": "approval_id is required"}
    try:
        record = AutomationPolicy.approve(approval_id, decided_by, phrase)
        return {"ok": True, "approval": record.to_dict()}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


def _exec_automation_approval_reject(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    approval_id = inputs.get("approval_id", "")
    decided_by = inputs.get("decided_by", "bryan")
    if not approval_id:
        return {"ok": False, "error": "approval_id is required"}
    try:
        record = AutomationPolicy.reject(approval_id, decided_by)
        return {"ok": True, "approval": record.to_dict()}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


def _exec_automation_approval_list(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    records = AutomationPolicy.list_pending(project_id)
    return {
        "project_id": project_id,
        "pending_count": len(records),
        "approvals": [r.to_dict() for r in records],
    }


def _exec_automation_autopilot_run_once(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    return AutomationPolicy.run_autopilot_once(project_id)


def _exec_automation_autopilot_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    from openjarvis.autonomy.modes import AutonomyPolicy
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    autonomy = AutonomyPolicy.get_status(project_id)
    pending = AutomationPolicy.list_pending(project_id)
    return {
        "project_id": project_id,
        "autonomy_mode": autonomy.get("mode"),
        "can_auto_execute_safe": autonomy.get("can_propose", False),
        "pending_approvals": len(pending),
        "autopilot_level": "level_1_4_only",
        "note": "Autopilot operates on Level 1-4 safe actions only. Hard gates always blocked.",
    }


# ===========================================================================
# PHASE D — Voice executors
# ===========================================================================


def _exec_voice_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import get_voice_status
    return get_voice_status()


def _exec_voice_listen_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import get_wake_word_status, get_stt_status
    wake = get_wake_word_status()
    stt = get_stt_status()
    return {
        "is_listening": wake.get("is_listening", False),
        "wake_word_engine": wake.get("wake_word_status"),
        "wake_phrases": wake.get("phrases", []),
        "stt_engine": stt.get("stt_status"),
        "push_to_talk_available": stt.get("is_configured", False),
        "microphone_permission_required": True,
        "status_note": (
            "Wake-word is not_configured — "
            "install openwakeword or pvporcupine to enable always-on detection."
            if wake.get("wake_word_status") == "not_configured"
            else wake.get("blocker", "")
        ),
    }


def _exec_voice_wake_word_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import get_wake_word_status
    return get_wake_word_status()


def _exec_voice_parse_approval(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import parse_voice_approval
    text = inputs.get("text", "")
    if not text:
        return {"error": "text is required"}
    return parse_voice_approval(text)


def _exec_voice_approval_challenge(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import issue_approval_challenge
    action_class = inputs.get("action_class", "")
    description = inputs.get("description", "")
    if not action_class:
        return {"error": "action_class is required"}
    try:
        challenge = issue_approval_challenge(action_class, description)
        return {"ok": True, "challenge": challenge.to_dict()}
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}


def _exec_voice_approval_confirm(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import confirm_voice_approval
    challenge_id = inputs.get("challenge_id", "")
    spoken = inputs.get("spoken_response", "")
    phrase = inputs.get("confirmation_phrase", "")
    if not challenge_id:
        return {"error": "challenge_id is required"}
    return confirm_voice_approval(challenge_id, spoken, phrase)


def _exec_voice_command_preview(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import preview_command
    text = inputs.get("text", "")
    if not text:
        return {"error": "text is required"}
    return preview_command(text)


def _exec_voice_tts_test(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import tts_test
    text = inputs.get("text", "Jarvis is ready.")
    return tts_test(text)


def _exec_voice_stt_test(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.voice_pipeline import stt_test
    return stt_test()


# ===========================================================================
# PHASE E — Desktop executors
# ===========================================================================


def _exec_desktop_permissions_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import get_desktop_permissions_status
    return get_desktop_permissions_status()


def _exec_desktop_operator_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import get_desktop_permissions_status
    perms = get_desktop_permissions_status()
    return {
        "operator_status": perms["operator_status"],
        "platform": perms["platform"],
        "accessibility": perms["permissions"]["accessibility"]["status"],
        "screen_recording": perms["permissions"]["screen_recording"]["status"],
        "microphone": perms["permissions"]["microphone"]["status"],
        "actions_available": perms["actions_available"],
        "setup_instructions": perms.get("setup_instructions"),
    }


def _exec_desktop_open_app_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import plan_open_app
    app_name = inputs.get("app_name", "")
    if not app_name:
        return {"error": "app_name is required"}
    return plan_open_app(app_name)


def _exec_desktop_focus_app_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import plan_focus_app
    app_name = inputs.get("app_name", "")
    if not app_name:
        return {"error": "app_name is required"}
    return plan_focus_app(app_name)


def _exec_desktop_screenshot_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import check_screenshot_status
    return check_screenshot_status()


def _exec_desktop_safe_demo(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import desktop_safe_demo
    return desktop_safe_demo()


def _exec_browser_operator_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import get_browser_operator_status
    return get_browser_operator_status()


def _exec_browser_open_url_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import plan_browser_open_url
    url = inputs.get("url", "")
    if not url:
        return {"error": "url is required"}
    return plan_browser_open_url(url)


def _exec_browser_read_only_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.desktop_operator import browser_read_only_plan
    url = inputs.get("url", "")
    if not url:
        return {"error": "url is required"}
    return browser_read_only_plan(url)


# ===========================================================================
# PHASE F — Mobile executors
# ===========================================================================


def _exec_mobile_pending_approvals(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.automation_policy import AutomationPolicy
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    records = AutomationPolicy.list_pending(project_id)
    return {
        "project_id": project_id,
        "pending_count": len(records),
        "approvals": [r.to_dict() for r in records],
        "mobile_note": "View this endpoint from your mobile browser or Telegram.",
    }


def _exec_mobile_approval_payload(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    action = inputs.get("action", "")
    approval_id = inputs.get("approval_id", "")
    return {
        "payload_format": {
            "action": action or "<action_class>",
            "approval_id": approval_id or "<uuid>",
            "decided_by": "bryan",
            "decision": "approve | reject",
            "confirmation_phrase": "<phrase if high-risk>",
        },
        "telegram_command": f"/approve {approval_id}" if approval_id else "/approve <approval_id>",
        "rest_endpoint": "POST /v1/automation/approvals/{approval_id}/approve",
        "mobile_note": "Use this payload format to approve/reject from mobile.",
    }


def _exec_mobile_safe_access_instructions(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_telegram_status
    tg = get_telegram_status()
    return {
        "access_paths": {
            "telegram": {
                "status": tg["status"],
                "configured": tg["configured"],
                "how": (
                    "Configure JARVIS_TELEGRAM_BOT_TOKEN and JARVIS_TELEGRAM_CHAT_ID. "
                    "Then send commands to the bot from your Telegram account."
                    if not tg["configured"]
                    else "Telegram configured. Send commands to the bot from your mobile app."
                ),
                "commands": ["/status", "/alerts", "/approve <id>", "/reject <id>"],
                "missing": tg["missing_env_vars"],
            },
            "tailnet": {
                "status": "manual_setup",
                "how": (
                    "Install Tailscale on both your Mac and mobile. "
                    "Access the Jarvis backend at http://<tailnet-hostname>:8000 "
                    "from any Tailscale-connected device. "
                    "No public exposure — tailnet only."
                ),
                "public_exposure": False,
                "tailscale_funnel": "blocked",
            },
            "local_network": {
                "status": "available_on_same_network",
                "how": (
                    "Access Jarvis backend at http://<mac-local-ip>:8000 "
                    "while on the same Wi-Fi network."
                ),
            },
        },
        "mobile_status_url": "GET /v1/mobile/status",
        "mobile_approvals_url": "GET /v1/mobile/pending_approvals",
        "what_works_now": (
            "Local network access, tailnet access (requires Tailscale setup)"
        ),
        "what_needs_config": tg["missing_env_vars"],
    }


def _exec_telegram_command_preview(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_telegram_command_status
    command = inputs.get("command", "/status")
    return get_telegram_command_status(command)


def _exec_telegram_approval_preview(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_telegram_approval_preview
    action = inputs.get("action", "")
    description = inputs.get("description", "")
    return get_telegram_approval_preview(action, description)


def _exec_telegram_command_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_telegram_status
    tg = get_telegram_status()
    return {
        "telegram_status": tg["status"],
        "commands_available": tg["configured"],
        "available_commands": (
            ["/status", "/alerts", "/approve <id>", "/reject <id>", "/watchdogs"]
            if tg["configured"] else []
        ),
        "missing": tg["missing_env_vars"],
        "real_send_allowed": False,
        "send_requires": tg["send_requires"],
    }


# ===========================================================================
# PHASE G — Ops executors
# ===========================================================================


def _exec_ops_runner_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.persistent_ops import get_runner_status
    return get_runner_status()


def _exec_ops_run_once(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.persistent_ops import run_once
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    dry_run = inputs.get("dry_run", True)
    return run_once(project_id, dry_run=dry_run)


def _exec_ops_schedule_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.persistent_ops import generate_schedule_plan
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    cadence = int(inputs.get("cadence_minutes", 60))
    return generate_schedule_plan(project_id, cadence)


def _exec_ops_install_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.persistent_ops import generate_install_plan
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    cadence = int(inputs.get("cadence_minutes", 60))
    return generate_install_plan(project_id, cadence)


def _exec_ops_stop_plan(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.persistent_ops import generate_stop_plan
    return generate_stop_plan()


def _exec_ops_dry_run_schedule(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.persistent_ops import dry_run_schedule
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    cadence = int(inputs.get("cadence_minutes", 60))
    return dry_run_schedule(project_id, cadence)


# ===========================================================================
# PHASE H — Connector executors
# ===========================================================================


def _exec_slack_connector_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_slack_status
    return get_slack_status()


def _exec_slack_draft_test_send(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import draft_slack_test_send
    message = inputs.get("message", "Jarvis test message")
    return draft_slack_test_send(message)


def _exec_telegram_connector_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_telegram_status
    return get_telegram_status()


def _exec_telegram_draft_test_send(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import draft_telegram_test_send
    message = inputs.get("message", "Jarvis test message")
    return draft_telegram_test_send(message)


def _exec_web_search_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_web_search_status
    return get_web_search_status()


def _exec_github_connector_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_github_status
    return get_github_status()


def _exec_github_local_remote_info(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_github_local_remote_info
    return get_github_local_remote_info()


def _exec_openclaw_workspace_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_openclaw_status
    return get_openclaw_status()


def _exec_openclaw_handoff_read(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import read_openclaw_handoff_summary
    return read_openclaw_handoff_summary()


def _exec_openclaw_link_status(
    inputs: Dict[str, Any], ctx: Dict[str, Any]
) -> Dict[str, Any]:
    from openjarvis.autonomy.connector_diagnostics import get_openclaw_status
    from openjarvis.projects.source_links import (
        ProjectSourceRegistry,
        ProjectSourceLinkType,
    )
    project_id = inputs.get("project_id") or ctx.get("project_id") or "default"
    oc_env = get_openclaw_status()
    links = ProjectSourceRegistry.list_for_project(project_id)
    openclaw_links = [
        lnk for lnk in links
        if lnk.link_type in (
            ProjectSourceLinkType.OPENCLAW_WORKSPACE,
            ProjectSourceLinkType.OPENCLAW_HANDOFF,
        )
    ]
    return {
        "project_id": project_id,
        "openclaw_env_status": oc_env["status"],
        "registered_sources": [lnk.to_dict() for lnk in openclaw_links],
        "workspace_env_set": oc_env["workspace_path_set"],
        "handoff_env_set": oc_env["handoff_path_set"],
        "missing_env_vars": oc_env["missing_env_vars"],
        "unblock_path": (
            "Set OPENCLAW_WORKSPACE_PATH and OPENCLAW_HANDOFF_PATH, "
            "then call project.link_openclaw_workspace"
        ) if oc_env["status"] == "not_configured" else None,
    }


# ===========================================================================
# Tool definitions
# ===========================================================================

_US8_TOOL_DEFS = [
    # ------------------------------------------------------------------ Phase B
    (
        ToolSpec(
            tool_id="project.onboarding_status",
            display_name="Project Onboarding Status",
            description=(
                "Show OMNIX linkage status: placeholder detection, exact config needed, "
                "readiness impact. Founder-friendly onboarding view."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_onboarding_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_onboarding_status,
    ),
    (
        ToolSpec(
            tool_id="project.link_wizard_state",
            display_name="Project Link Wizard State",
            description=(
                "Show step-by-step wizard state for linking a project's sources. "
                "Shows which sources are linked, missing, or placeholder."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_link_wizard_state",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_link_wizard_state,
    ),
    (
        ToolSpec(
            tool_id="project.source_config_needed",
            display_name="Project Source Config Needed",
            description=(
                "Show exact configuration steps needed to link a project's sources. "
                "Includes future project template and OMNIX-specific instructions."
            ),
            category="project",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:projects"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_project_source_config_needed",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_project_source_config_needed,
    ),
    # ------------------------------------------------------------------ Phase C
    (
        ToolSpec(
            tool_id="automation.policy.get",
            display_name="Get Automation Policy",
            description=(
                "Get full automation policy summary: 7 levels, standing policies, "
                "hard-gate action classes, auto-allowed classes."
            ),
            category="automation",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_policy_get",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_policy_get,
    ),
    (
        ToolSpec(
            tool_id="automation.policy.evaluate",
            display_name="Evaluate Automation Policy",
            description=(
                "Evaluate an action_class against the automation policy: "
                "returns level, standing_policy, requires_approval, can_proceed, blocked."
            ),
            category="automation",
            input_schema={
                "type": "object",
                "required": ["action_class"],
                "properties": {
                    "action_class": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_policy_evaluate",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_policy_evaluate,
    ),
    (
        ToolSpec(
            tool_id="automation.approval.request",
            display_name="Request Action Approval",
            description=(
                "Request approval for an action that requires explicit approval. "
                "Creates approval record with challenge token and TTL."
            ),
            category="automation",
            input_schema={
                "type": "object",
                "required": ["action_class"],
                "properties": {
                    "action_class": {"type": "string"},
                    "description": {"type": "string"},
                    "project_id": {"type": "string"},
                    "ttl_seconds": {"type": "integer"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["write:automation"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_approval_request",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_approval_request,
    ),
    (
        ToolSpec(
            tool_id="automation.approval.approve",
            display_name="Approve Action",
            description=(
                "Approve a pending approval request. "
                "Requires approval_id. High-risk actions require confirmation_phrase."
            ),
            category="automation",
            input_schema={
                "type": "object",
                "required": ["approval_id"],
                "properties": {
                    "approval_id": {"type": "string"},
                    "decided_by": {"type": "string"},
                    "confirmation_phrase": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["write:automation"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_approval_approve",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_approval_approve,
    ),
    (
        ToolSpec(
            tool_id="automation.approval.reject",
            display_name="Reject Action",
            description="Reject a pending approval request by approval_id.",
            category="automation",
            input_schema={
                "type": "object",
                "required": ["approval_id"],
                "properties": {
                    "approval_id": {"type": "string"},
                    "decided_by": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["write:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_approval_reject",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_approval_reject,
    ),
    (
        ToolSpec(
            tool_id="automation.approval.list",
            display_name="List Pending Approvals",
            description="List all pending approval requests for a project.",
            category="automation",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_approval_list",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_approval_list,
    ),
    (
        ToolSpec(
            tool_id="automation.autopilot.run_once",
            display_name="Autopilot Run Once",
            description=(
                "Simulate running pre-approved safe Level 1-4 actions once. "
                "Always simulated — no real execution without explicit approval."
            ),
            category="automation",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_autopilot_run_once",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_autopilot_run_once,
    ),
    (
        ToolSpec(
            tool_id="automation.autopilot.status",
            display_name="Autopilot Status",
            description=(
                "Get autopilot status: autonomy mode, pending approvals, "
                "safe action level in effect."
            ),
            category="automation",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_automation_autopilot_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_automation_autopilot_status,
    ),
    # ------------------------------------------------------------------ Phase D
    (
        ToolSpec(
            tool_id="voice.status",
            display_name="Voice Status",
            description=(
                "Full voice pipeline status: wake-word engine, STT, TTS, "
                "configuration state. Honest — not_configured unless proven."
            ),
            category="voice",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_status,
    ),
    (
        ToolSpec(
            tool_id="voice.listen_status",
            display_name="Voice Listen Status",
            description=(
                "Check whether wake-word detection is active and listening. "
                "Reports is_listening=False unless engine is actually running."
            ),
            category="voice",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_listen_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_listen_status,
    ),
    (
        ToolSpec(
            tool_id="voice.wake_word_status",
            display_name="Wake Word Status",
            description=(
                "Check wake-word engine (openwakeword/pvporcupine) status. "
                "Reports exact blockers and install commands if not configured."
            ),
            category="voice",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_wake_word_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_wake_word_status,
    ),
    (
        ToolSpec(
            tool_id="voice.parse_approval",
            display_name="Voice Parse Approval",
            description=(
                "Parse a text/voice string for approval intent. "
                "Returns approve/reject/hold/unknown with confidence."
            ),
            category="voice",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_parse_approval",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_parse_approval,
    ),
    (
        ToolSpec(
            tool_id="voice.approval_challenge",
            display_name="Issue Voice Approval Challenge",
            description=(
                "Issue a voice approval challenge for a pending action. "
                "Returns challenge_id and token. Expires in 2 minutes."
            ),
            category="voice",
            input_schema={
                "type": "object",
                "required": ["action_class"],
                "properties": {
                    "action_class": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["write:voice"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_approval_challenge",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_approval_challenge,
    ),
    (
        ToolSpec(
            tool_id="voice.approval_confirm",
            display_name="Confirm Voice Approval",
            description=(
                "Confirm or reject a voice approval challenge by challenge_id. "
                "Parses spoken_response for approve/reject intent."
            ),
            category="voice",
            input_schema={
                "type": "object",
                "required": ["challenge_id"],
                "properties": {
                    "challenge_id": {"type": "string"},
                    "spoken_response": {"type": "string"},
                    "confirmation_phrase": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["write:voice"],
            risk_level="medium",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_approval_confirm",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_approval_confirm,
    ),
    (
        ToolSpec(
            tool_id="voice.command_preview",
            display_name="Voice Command Preview",
            description=(
                "Preview what a voice command would do before executing. "
                "Routes through governance — no real execution."
            ),
            category="voice",
            input_schema={
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_command_preview",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_command_preview,
    ),
    (
        ToolSpec(
            tool_id="voice.tts_test",
            display_name="TTS Test",
            description=(
                "Test text-to-speech. On macOS, actually speaks via 'say' command. "
                "On other platforms, returns draft output."
            ),
            category="voice",
            input_schema={
                "type": "object",
                "properties": {"text": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_tts_test",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_tts_test,
    ),
    (
        ToolSpec(
            tool_id="voice.stt_test",
            display_name="STT Test",
            description=(
                "Check STT engine readiness. Does NOT record audio. "
                "Reports configured engine or exact blockers."
            ),
            category="voice",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:voice"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_voice_stt_test",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_voice_stt_test,
    ),
    # ------------------------------------------------------------------ Phase E
    (
        ToolSpec(
            tool_id="desktop.permissions_status",
            display_name="Desktop Permissions Status",
            description=(
                "Get macOS Accessibility, Screen Recording, and Microphone "
                "permission status. Read-only programmatic checks."
            ),
            category="desktop",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_desktop_permissions_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_desktop_permissions_status,
    ),
    (
        ToolSpec(
            tool_id="desktop.operator_status",
            display_name="Desktop Operator Status",
            description=(
                "Get overall desktop operator status: available/not_configured/"
                "blocked_by_macos_privacy/not_macos."
            ),
            category="desktop",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_desktop_operator_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_desktop_operator_status,
    ),
    (
        ToolSpec(
            tool_id="desktop.open_app_plan",
            display_name="Open App Plan",
            description=(
                "Generate a plan to open an application. Dry-run only. "
                "No execution — requires explicit approval to run."
            ),
            category="desktop",
            input_schema={
                "type": "object",
                "required": ["app_name"],
                "properties": {"app_name": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_desktop_open_app_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_desktop_open_app_plan,
    ),
    (
        ToolSpec(
            tool_id="desktop.focus_app_plan",
            display_name="Focus App Plan",
            description=(
                "Generate a plan to focus an application via AppleScript. "
                "Dry-run only. Requires Accessibility permission and explicit approval."
            ),
            category="desktop",
            input_schema={
                "type": "object",
                "required": ["app_name"],
                "properties": {"app_name": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_desktop_focus_app_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_desktop_focus_app_plan,
    ),
    (
        ToolSpec(
            tool_id="desktop.screenshot_status",
            display_name="Screenshot Status",
            description=(
                "Check if taking a screenshot is possible. "
                "Does not take a screenshot — checks Screen Recording permission only."
            ),
            category="desktop",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_desktop_screenshot_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_desktop_screenshot_status,
    ),
    (
        ToolSpec(
            tool_id="desktop.safe_demo",
            display_name="Desktop Safe Demo",
            description=(
                "Demonstrate desktop operator capabilities without executing. "
                "Shows what is available vs blocked based on current permissions."
            ),
            category="desktop",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_desktop_safe_demo",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_desktop_safe_demo,
    ),
    (
        ToolSpec(
            tool_id="browser.operator_status",
            display_name="Browser Operator Status",
            description=(
                "Report browser operator readiness and governance boundaries. "
                "form_submit/purchase/account_mutation are always_blocked."
            ),
            category="browser",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_browser_operator_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_browser_operator_status,
    ),
    (
        ToolSpec(
            tool_id="browser.open_url_plan",
            display_name="Browser Open URL Plan",
            description=(
                "Generate a plan to open a URL in the browser. Dry-run. "
                "No execution. Blocks file:// and javascript:// schemes."
            ),
            category="browser",
            input_schema={
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_browser_open_url_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_browser_open_url_plan,
    ),
    (
        ToolSpec(
            tool_id="browser.read_only_plan",
            display_name="Browser Read-Only Plan",
            description=(
                "Plan for read-only browser page inspection. "
                "No form interaction, purchase, or account mutation. "
                "Requires Screen Recording permission."
            ),
            category="browser",
            input_schema={
                "type": "object",
                "required": ["url"],
                "properties": {"url": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:desktop"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_browser_read_only_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_browser_read_only_plan,
    ),
    # ------------------------------------------------------------------ Phase F
    (
        ToolSpec(
            tool_id="mobile.pending_approvals",
            display_name="Mobile Pending Approvals",
            description=(
                "List pending approvals in mobile-readable format. "
                "Shows approval_id, action, challenge_token, expiry."
            ),
            category="mobile",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mobile_pending_approvals",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mobile_pending_approvals,
    ),
    (
        ToolSpec(
            tool_id="mobile.approval_payload",
            display_name="Mobile Approval Payload",
            description=(
                "Format the mobile approval payload for approve/reject actions. "
                "Shows exact REST endpoint and Telegram command format."
            ),
            category="mobile",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "approval_id": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["read:automation"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mobile_approval_payload",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mobile_approval_payload,
    ),
    (
        ToolSpec(
            tool_id="mobile.safe_access_instructions",
            display_name="Mobile Safe Access Instructions",
            description=(
                "Show how to access Jarvis from mobile: "
                "Telegram bot, tailnet, local network. "
                "No public exposure. No Tailscale Funnel."
            ),
            category="mobile",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:mobile"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_mobile_safe_access_instructions",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_mobile_safe_access_instructions,
    ),
    (
        ToolSpec(
            tool_id="telegram.command_preview",
            display_name="Telegram Command Preview",
            description=(
                "Preview what a Telegram command would do. No execution. "
                "Shows connector_status and required config."
            ),
            category="telegram",
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:telegram"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_command_preview",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_telegram_command_preview,
    ),
    (
        ToolSpec(
            tool_id="telegram.approval_preview",
            display_name="Telegram Approval Preview",
            description=(
                "Preview what a Telegram approval message would look like. "
                "Draft only — send_status=not_sent always."
            ),
            category="telegram",
            input_schema={
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["read:telegram"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_approval_preview",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_telegram_approval_preview,
    ),
    (
        ToolSpec(
            tool_id="telegram.command_status",
            display_name="Telegram Command Status",
            description=(
                "Status of Telegram command handling: "
                "configured/not_configured, available commands, missing env vars."
            ),
            category="telegram",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:telegram"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_command_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_telegram_command_status,
    ),
    # ------------------------------------------------------------------ Phase G
    (
        ToolSpec(
            tool_id="ops.runner_status",
            display_name="Ops Runner Status",
            description=(
                "Check if any persistent runner (launchd/cron) is installed. "
                "Honest — returns not_installed unless proven otherwise."
            ),
            category="ops",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:ops"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_ops_runner_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_ops_runner_status,
    ),
    (
        ToolSpec(
            tool_id="ops.run_once",
            display_name="Ops Run Once",
            description=(
                "Run safe Level 1-4 actions once. "
                "dry_run=True (default) — simulates only. "
                "Never installs a daemon or persistent runner."
            ),
            category="ops",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "dry_run": {"type": "boolean"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["execute:ops"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_ops_run_once",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_ops_run_once,
    ),
    (
        ToolSpec(
            tool_id="ops.schedule_plan",
            display_name="Ops Schedule Plan",
            description=(
                "Generate a persistent runner schedule plan. "
                "PLAN ONLY — nothing is installed."
            ),
            category="ops",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "cadence_minutes": {"type": "integer"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["read:ops"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_ops_schedule_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_ops_schedule_plan,
    ),
    (
        ToolSpec(
            tool_id="ops.install_plan",
            display_name="Ops Install Plan",
            description=(
                "Generate reviewable install plan for a persistent runner. "
                "NEVER installs anything. Requires explicit approval after review."
            ),
            category="ops",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "cadence_minutes": {"type": "integer"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["read:ops"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_ops_install_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_ops_install_plan,
    ),
    (
        ToolSpec(
            tool_id="ops.stop_plan",
            display_name="Ops Stop Plan",
            description=(
                "Generate stop/uninstall plan for a persistent runner. "
                "NEVER executes. Requires explicit approval."
            ),
            category="ops",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:ops"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_ops_stop_plan",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_ops_stop_plan,
    ),
    (
        ToolSpec(
            tool_id="ops.dry_run_schedule",
            display_name="Ops Dry-Run Schedule",
            description=(
                "Simulate 3 scheduled runs. Shows what actions would run and when. "
                "No real execution — no daemon installed."
            ),
            category="ops",
            input_schema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "cadence_minutes": {"type": "integer"},
                },
            },
            output_schema={"type": "object"},
            required_permissions=["read:ops"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_ops_dry_run_schedule",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_ops_dry_run_schedule,
    ),
    # ------------------------------------------------------------------ Phase H
    (
        ToolSpec(
            tool_id="slack.connector_status",
            display_name="Slack Connector Status",
            description=(
                "Check Slack connector readiness. "
                "Token presence validated without printing. "
                "Returns configured/not_configured/degraded/ready_pending_test_approval."
            ),
            category="slack",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_slack_connector_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_slack_connector_status,
    ),
    (
        ToolSpec(
            tool_id="slack.draft_test_send",
            display_name="Slack Draft Test Send",
            description=(
                "Draft a Slack test message. "
                "send_status=not_sent ALWAYS. "
                "Requires approval + Bryan-controlled channel to send."
            ),
            category="slack",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_slack_draft_test_send",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_slack_draft_test_send,
    ),
    (
        ToolSpec(
            tool_id="telegram.connector_status",
            display_name="Telegram Connector Status",
            description=(
                "Check Telegram connector readiness. "
                "Token presence validated without printing. "
                "Returns configured/not_configured/degraded/ready_pending_test_approval."
            ),
            category="telegram",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_connector_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_telegram_connector_status,
    ),
    (
        ToolSpec(
            tool_id="telegram.draft_test_send",
            display_name="Telegram Draft Test Send",
            description=(
                "Draft a Telegram test message. "
                "send_status=not_sent ALWAYS. "
                "Requires approval + Bryan-controlled chat to send."
            ),
            category="telegram",
            input_schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_telegram_draft_test_send",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_telegram_draft_test_send,
    ),
    (
        ToolSpec(
            tool_id="web.search_status",
            display_name="Web Search Status",
            description=(
                "Check web search connector readiness. "
                "No fake available status — only configured if a provider key is set."
            ),
            category="web",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_web_search_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_web_search_status,
    ),
    (
        ToolSpec(
            tool_id="github.connector_status",
            display_name="GitHub Connector Status",
            description=(
                "Check GitHub connector readiness. "
                "Read-only. Reports git availability, token presence, "
                "local remote URLs."
            ),
            category="github",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_github_connector_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_github_connector_status,
    ),
    (
        ToolSpec(
            tool_id="github.local_remote_info",
            display_name="GitHub Local Remote Info",
            description=(
                "Get local git remote information. "
                "Read-only, no network call. "
                "Returns origin and fork remote URLs."
            ),
            category="github",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_github_local_remote_info",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_github_local_remote_info,
    ),
    (
        ToolSpec(
            tool_id="openclaw.workspace_status",
            display_name="OpenClaw Workspace Status",
            description=(
                "Check OpenClaw workspace and handoff readiness. "
                "Read-only path validation. "
                "Returns configured/not_configured/degraded."
            ),
            category="openclaw",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_openclaw_workspace_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_openclaw_workspace_status,
    ),
    (
        ToolSpec(
            tool_id="openclaw.handoff_read",
            display_name="OpenClaw Handoff Read",
            description=(
                "Read OpenClaw handoff file summary. "
                "Read-only. No mutations. "
                "Returns first 200 chars, line count, size."
            ),
            category="openclaw",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_openclaw_handoff_read",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_openclaw_handoff_read,
    ),
    (
        ToolSpec(
            tool_id="openclaw.link_status",
            display_name="OpenClaw Link Status",
            description=(
                "Full OpenClaw linkage status: env vars, registered source links, "
                "unblock path. Read-only."
            ),
            category="openclaw",
            input_schema={
                "type": "object",
                "properties": {"project_id": {"type": "string"}},
            },
            output_schema={"type": "object"},
            required_permissions=["read:connectors"],
            risk_level="low",
            project_scope=[],
            enabled=True,
            configured=True,
            approval_required=False,
            owning_agent_id="manager",
            executor_ref="_exec_openclaw_link_status",
            implementation_status=ToolStatus.AVAILABLE,
        ),
        _exec_openclaw_link_status,
    ),
]


# ===========================================================================
# Registration
# ===========================================================================


def _is_us8_initialized() -> bool:
    return ToolRegistry.get("automation.policy.get") is not None


def initialize_us8_catalog() -> None:
    """Register all US8 tools. Safe to call multiple times — idempotent."""
    if _is_us8_initialized():
        return
    for spec, executor in _US8_TOOL_DEFS:
        ToolRegistry.register(spec, executor=executor)
    stats = ToolRegistry.stats()
    logger.info(
        "US8 catalog initialized: total=%d available=%d unavailable=%d",
        stats["total_registered"],
        stats["available"],
        stats["unavailable"],
    )


__all__ = ["initialize_us8_catalog"]
