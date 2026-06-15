"""Jarvis Persistent Ops — persistent runner plan, dry-run, and install plan.

SAFETY CONTRACT:
  - No daemon, launch agent, cron job, or startup service is installed
    by any function in this module.
  - generate_install_plan() generates a plan only — never executes it.
  - run_once() executes only safe Level 1-4 actions when dry_run=False.
  - dry_run_schedule() simulates a schedule without any real execution.
  - Install requires explicit post-plan approval — not granted by any
    US8 prompt, argument, or standing policy.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_JARVIS_DIR = Path.home() / ".jarvis"
_RUNNER_LOG_PATH = _JARVIS_DIR / "persistent_runner.log"
_INSTALL_PLAN_PATH = _JARVIS_DIR / "runner_install_plan.json"
_IS_MACOS = platform.system() == "Darwin"


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------


class RunnerStatus:
    NOT_INSTALLED = "not_installed"
    PLANNED = "planned"
    DRY_RUN_ONLY = "dry_run_only"
    INSTALLED = "installed"


# ---------------------------------------------------------------------------
# Safe once-run actions (Level 1-4 only)
# ---------------------------------------------------------------------------

_SAFE_ONCE_ACTIONS = [
    {
        "action": "watchdog.run_project_pack",
        "description": "Run all 8 watchdogs for project",
        "automation_level": 1,
        "requires_approval": False,
    },
    {
        "action": "doctor.run",
        "description": "Run all diagnostic checks",
        "automation_level": 1,
        "requires_approval": False,
    },
    {
        "action": "alert.daily_digest",
        "description": "Generate daily alert digest (draft only, no send)",
        "automation_level": 2,
        "requires_approval": False,
    },
    {
        "action": "project.sources.validate_all",
        "description": "Validate all project source links (read-only)",
        "automation_level": 1,
        "requires_approval": False,
    },
]


# ---------------------------------------------------------------------------
# Runner status check
# ---------------------------------------------------------------------------


def get_runner_status() -> Dict[str, Any]:
    """Check if any persistent runner is installed. Honest — never returns installed unless proven."""
    launchd_plist = Path.home() / "Library" / "LaunchAgents" / "com.jarvis.runner.plist"
    launchd_installed = _IS_MACOS and launchd_plist.exists()

    cron_installed = False
    try:
        r = subprocess.run(
            ["crontab", "-l"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode == 0 and "jarvis" in r.stdout.lower():
            cron_installed = True
    except Exception:
        pass

    installed = launchd_installed or cron_installed

    return {
        "runner_status": RunnerStatus.INSTALLED if installed else RunnerStatus.NOT_INSTALLED,
        "installed": installed,
        "launchd_plist_exists": launchd_installed,
        "launchd_plist_path": str(launchd_plist),
        "cron_entry_exists": cron_installed,
        "log_path": str(_RUNNER_LOG_PATH),
        "note": "No persistent runner installed by Jarvis. All automation is run-on-demand only.",
    }


# ---------------------------------------------------------------------------
# Run once (safe Level 1-4 only)
# ---------------------------------------------------------------------------


def run_once(project_id: str = "omnix", dry_run: bool = True) -> Dict[str, Any]:
    """Run safe Level 1-4 actions once.

    dry_run=True (default): simulate only, no real execution.
    dry_run=False: execute watchdog/doctor/digest actions via ToolRegistry.

    Never installs any daemon or persistent runner.
    """
    results = []
    for action in _SAFE_ONCE_ACTIONS:
        if dry_run:
            results.append({
                **action,
                "status": "would_run",
                "dry_run": True,
                "executed": False,
            })
        else:
            try:
                output = _execute_safe_action(action["action"], project_id)
                results.append({
                    **action,
                    "status": "executed",
                    "dry_run": False,
                    "executed": True,
                    "output_summary": _summarize_output(output),
                })
            except Exception as exc:
                results.append({
                    **action,
                    "status": "error",
                    "dry_run": False,
                    "executed": False,
                    "error": str(exc),
                })

    _append_log_entry(project_id, dry_run, results)

    return {
        "project_id": project_id,
        "dry_run": dry_run,
        "actions": results,
        "ran_at": time.time(),
        "note": "run_once does not install any persistent runner or daemon.",
    }


def _execute_safe_action(action: str, project_id: str) -> Any:
    from openjarvis.tools.catalog import initialize_catalog
    from openjarvis.tools.gateway import ToolExecutionGateway
    initialize_catalog()
    gw = ToolExecutionGateway()
    result = gw.execute(action, {"project_id": project_id}, project_id=project_id)
    if result is not None and hasattr(result, "output"):
        return result.output
    return {}


def _summarize_output(output: Any) -> str:
    if output is None:
        return "no output"
    if isinstance(output, dict):
        return f"keys={list(output.keys())[:5]}"
    return str(output)[:100]


def _append_log_entry(
    project_id: str, dry_run: bool, results: List[Dict[str, Any]]
) -> None:
    try:
        _JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "ts": time.time(),
            "project_id": project_id,
            "dry_run": dry_run,
            "action_count": len(results),
            "executed_count": sum(1 for r in results if r.get("executed")),
        }
        with open(_RUNNER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Schedule plan (describe only — no install)
# ---------------------------------------------------------------------------


def generate_schedule_plan(
    project_id: str = "omnix",
    cadence_minutes: int = 60,
) -> Dict[str, Any]:
    """Generate a persistent runner schedule plan. Does NOT install anything."""
    python_path = shutil.which("python3") or shutil.which("python") or "/usr/bin/python3"
    repo_path = str(Path(__file__).parent.parent.parent.parent)

    plan: Dict[str, Any] = {
        "plan_type": "schedule",
        "runner_status": RunnerStatus.PLANNED,
        "project_id": project_id,
        "cadence_minutes": cadence_minutes,
        "planned_actions": _SAFE_ONCE_ACTIONS,
        "log_path": str(_RUNNER_LOG_PATH),
        "stop_command": (
            "launchctl unload ~/Library/LaunchAgents/com.jarvis.runner.plist"
            if _IS_MACOS else "remove crontab entry"
        ),
        "install_requires_explicit_approval": True,
        "note": (
            "PLAN ONLY — nothing installed. "
            "Run ops.install_plan for generated steps, "
            "then provide explicit approval before any install."
        ),
        "generated_at": time.time(),
    }

    if _IS_MACOS:
        plist_path = str(
            Path.home() / "Library" / "LaunchAgents" / "com.jarvis.runner.plist"
        )
        plan["macos_launchd"] = {
            "plist_path": plist_path,
            "label": "com.jarvis.runner",
            "program": python_path,
            "arguments": [
                "-m", "openjarvis.cli.run_once",
                f"--project={project_id}",
            ],
            "start_interval_seconds": cadence_minutes * 60,
            "working_directory": repo_path,
            "standard_out_path": str(_JARVIS_DIR / "runner_stdout.log"),
            "standard_error_path": str(_JARVIS_DIR / "runner_stderr.log"),
        }
    else:
        plan["cron"] = {
            "expression": (
                f"*/{cadence_minutes} * * * * "
                f"{python_path} -m openjarvis.cli.run_once "
                f"--project={project_id}"
            ),
        }

    return plan


# ---------------------------------------------------------------------------
# Install plan (generate only — absolutely no install)
# ---------------------------------------------------------------------------


def generate_install_plan(
    project_id: str = "omnix",
    cadence_minutes: int = 60,
) -> Dict[str, Any]:
    """Generate install plan as a reviewable JSON file. Does NOT install anything.

    Bryan must review the generated plan and explicitly approve installation
    before any daemon/cron/launch agent is created.
    """
    schedule = generate_schedule_plan(project_id, cadence_minutes)
    install_steps: List[Dict[str, Any]] = []

    if _IS_MACOS and "macos_launchd" in schedule:
        ld = schedule["macos_launchd"]
        args_xml = "\n        ".join(
            f"<string>{a}</string>" for a in ld["arguments"]
        )
        plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>{ld['label']}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{ld['program']}</string>
        {args_xml}
    </array>
    <key>StartInterval</key>
    <integer>{ld['start_interval_seconds']}</integer>
    <key>WorkingDirectory</key>
    <string>{ld['working_directory']}</string>
    <key>StandardOutPath</key>
    <string>{ld['standard_out_path']}</string>
    <key>StandardErrorPath</key>
    <string>{ld['standard_error_path']}</string>
    <key>RunAtLoad</key><false/>
</dict>
</plist>"""
        install_steps = [
            {
                "step": 1,
                "description": f"Write plist to {ld['plist_path']}",
                "command": f"cat > {ld['plist_path']}  # (see plist_content)",
                "plist_content": plist_content,
                "requires_approval": True,
                "not_executed": True,
            },
            {
                "step": 2,
                "description": "Load launch agent",
                "command": f"launchctl load {ld['plist_path']}",
                "requires_approval": True,
                "not_executed": True,
            },
        ]
    else:
        cron = schedule.get("cron", {})
        install_steps = [
            {
                "step": 1,
                "description": "Add cron entry",
                "command": (
                    f"(crontab -l; echo '{cron.get('expression', '')}') | crontab -"
                ),
                "requires_approval": True,
                "not_executed": True,
            },
        ]

    plan: Dict[str, Any] = {
        "install_plan": install_steps,
        "stop_plan": [
            {
                "step": 1,
                "description": "Unload and remove launch agent",
                "command": schedule.get("stop_command", ""),
                "not_executed": True,
            }
        ],
        "installed": False,
        "approval_required": True,
        "explicit_approval_message": (
            "Review steps above. Reply 'APPROVE JARVIS RUNNER INSTALL' "
            "to proceed with installation."
        ),
        "note": (
            "Nothing has been installed. This plan must be reviewed and "
            "explicitly approved before any persistent runner is created."
        ),
        "generated_at": time.time(),
    }

    try:
        _JARVIS_DIR.mkdir(parents=True, exist_ok=True)
        with open(_INSTALL_PLAN_PATH, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
        plan["plan_file"] = str(_INSTALL_PLAN_PATH)
    except Exception:
        pass

    return plan


# ---------------------------------------------------------------------------
# Dry-run schedule
# ---------------------------------------------------------------------------


def dry_run_schedule(
    project_id: str = "omnix",
    cadence_minutes: int = 60,
) -> Dict[str, Any]:
    """Simulate what a scheduled run would do. No real execution."""
    now = time.time()
    simulated_runs = []
    for i in range(3):
        run_time = now + i * cadence_minutes * 60
        simulated_runs.append({
            "run_index": i + 1,
            "simulated_at": run_time,
            "actions": [
                {
                    "action": a["action"],
                    "would_execute": True,
                    "automation_level": a["automation_level"],
                    "simulated": True,
                }
                for a in _SAFE_ONCE_ACTIONS
            ],
            "simulated": True,
        })
    return {
        "project_id": project_id,
        "cadence_minutes": cadence_minutes,
        "simulated_runs": simulated_runs,
        "runner_status": RunnerStatus.DRY_RUN_ONLY,
        "installed": False,
        "note": "Dry run only — nothing executed, no daemon installed.",
        "generated_at": now,
    }


# ---------------------------------------------------------------------------
# Stop plan
# ---------------------------------------------------------------------------


def generate_stop_plan() -> Dict[str, Any]:
    """Generate stop/uninstall plan. Does not execute."""
    runner = get_runner_status()
    if not runner["installed"]:
        return {
            "runner_installed": False,
            "note": "No persistent runner installed. Nothing to stop.",
        }
    plist_path = runner.get("launchd_plist_path", "")
    return {
        "runner_installed": True,
        "stop_steps": [
            {
                "step": 1,
                "description": "Unload launchd agent",
                "command": f"launchctl unload {plist_path}",
                "not_executed": True,
            },
            {
                "step": 2,
                "description": "Remove plist file",
                "command": f"rm {plist_path}",
                "not_executed": True,
            },
        ],
        "approval_required": True,
        "note": "Stop plan generated — not executed. Requires explicit approval.",
    }


__all__ = [
    "RunnerStatus",
    "get_runner_status",
    "run_once",
    "generate_schedule_plan",
    "generate_install_plan",
    "dry_run_schedule",
    "generate_stop_plan",
]
