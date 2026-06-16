"""Jarvis Real Dogfood Loop — daily evidence snapshot.

Captures:
  - Daily readiness snapshot
  - Connector status snapshot
  - Queue status snapshot
  - Memory status snapshot
  - Cost/budget status snapshot
  - Action/approval summary
  - Blockers list
  - Local report file (no external posting without approval)

Output: ~/.openjarvis/dogfood_report_YYYYMMDD.json

Hard rules:
  - No external posting unless explicitly approved
  - Snapshots are read-only — no state mutations
  - No secret values in report
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPORT_DIR = Path.home() / ".openjarvis"


# ---------------------------------------------------------------------------
# Snapshot collectors
# ---------------------------------------------------------------------------


def _snapshot_readiness() -> Dict[str, Any]:
    try:
        from openjarvis.doctor.checks import run_all_checks
        checks = run_all_checks()
        pass_count = sum(1 for c in checks if c.status == "pass")
        fail_count = sum(1 for c in checks if c.status == "fail")
        warn_count = sum(1 for c in checks if c.status == "warn")
        return {
            "total_checks": len(checks),
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "not_configured": len(checks) - pass_count - fail_count - warn_count,
            "failed_checks": [c.check_id for c in checks if c.status == "fail"],
        }
    except Exception as exc:
        return {"error": str(exc)}


def _snapshot_connectors() -> Dict[str, Any]:
    try:
        from openjarvis.autonomy.connector_health import (
            check_all_connectors,
            HealthStatus,
        )
        results = check_all_connectors(force=False)
        return {
            name: {
                "status": entry.status,
                "failure_reason": entry.failure_reason,
                "last_checked": entry.last_checked,
            }
            for name, entry in results.items()
        }
    except Exception as exc:
        return {"error": str(exc)}


def _snapshot_queue() -> Dict[str, Any]:
    try:
        from openjarvis.autonomy.job_queue import queue_stats
        return queue_stats()
    except Exception as exc:
        return {"error": str(exc)}


def _snapshot_memory() -> Dict[str, Any]:
    try:
        from openjarvis.memory.backup import get_memory_backup_status
        return get_memory_backup_status()
    except Exception as exc:
        return {"error": str(exc)}


def _snapshot_budget() -> Dict[str, Any]:
    try:
        from openjarvis.autonomy.budget_guard import get_budget_status
        s = get_budget_status()
        return {
            "verdict": s.verdict,
            "today_spend_usd": s.today_spend_usd,
            "run_spend_usd": s.run_spend_usd,
            "today_hard_ok": s.today_hard_ok,
            "entries_today": s.entries_today,
            "per_day_hard_limit": s.config.get("per_day_hard_limit_usd"),
        }
    except Exception as exc:
        return {"error": str(exc)}


def _snapshot_approvals() -> Dict[str, Any]:
    try:
        from openjarvis.autonomy.voice_pipeline import get_approval_audit_log
        log = get_approval_audit_log()
        return {
            "total_logged": len(log),
            "recent": log[-5:] if log else [],
        }
    except Exception as exc:
        return {"error": str(exc)}


def _collect_blockers(
    readiness: Dict[str, Any],
    connectors: Dict[str, Any],
    budget: Dict[str, Any],
) -> List[str]:
    blockers: List[str] = []
    if "failed_checks" in readiness:
        for c in readiness.get("failed_checks", []):
            blockers.append(f"readiness_check_fail: {c}")
    if "error" not in connectors:
        for name, info in connectors.items():
            if info.get("status") not in ("healthy", "unknown"):
                reason = info.get("failure_reason", "")
                blockers.append(f"connector_{name}: {info['status']} — {reason}")
    if budget.get("verdict") == "hard_stop":
        blockers.append(f"budget_hard_stop: today_spend=${budget.get('today_spend_usd', 0):.4f}")
    return blockers


# ---------------------------------------------------------------------------
# Main dogfood report
# ---------------------------------------------------------------------------


def run_dogfood_snapshot(
    project_id: str = "omnix",
    save_report: bool = True,
) -> Dict[str, Any]:
    """Run a complete dogfood snapshot. Read-only. No external posting."""
    started_at = time.time()
    date_str = time.strftime("%Y%m%d")

    readiness = _snapshot_readiness()
    connectors = _snapshot_connectors()
    queue = _snapshot_queue()
    memory = _snapshot_memory()
    budget = _snapshot_budget()
    approvals = _snapshot_approvals()
    blockers = _collect_blockers(readiness, connectors, budget)

    report: Dict[str, Any] = {
        "project_id": project_id,
        "snapshot_date": date_str,
        "generated_at": started_at,
        "generated_at_human": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(started_at)),
        "readiness": readiness,
        "connectors": connectors,
        "queue": queue,
        "memory": memory,
        "budget": budget,
        "approvals": approvals,
        "blockers": blockers,
        "blocker_count": len(blockers),
        "external_posting": "disabled — no external posts without explicit approval",
        "elapsed_seconds": round(time.time() - started_at, 3),
    }

    if save_report:
        _save_report(report, date_str)

    return report


def _save_report(report: Dict[str, Any], date_str: str) -> str:
    path = _REPORT_DIR / f"dogfood_report_{date_str}.json"
    try:
        _REPORT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def get_latest_dogfood_report() -> Optional[Dict[str, Any]]:
    """Read the most recent dogfood report. Returns None if none exist."""
    reports = sorted(_REPORT_DIR.glob("dogfood_report_*.json"), reverse=True)
    if not reports:
        return None
    try:
        return json.loads(reports[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def get_dogfood_status() -> Dict[str, Any]:
    """Doctor/readiness status for dogfood loop."""
    latest = get_latest_dogfood_report()
    if latest:
        age = time.time() - latest.get("generated_at", 0)
        return {
            "active": True,
            "latest_report_date": latest.get("snapshot_date"),
            "latest_report_age_hours": round(age / 3600, 1),
            "latest_blocker_count": latest.get("blocker_count", 0),
            "latest_blockers": latest.get("blockers", []),
            "external_posting_disabled": True,
        }
    return {
        "active": True,
        "latest_report_date": None,
        "note": "No dogfood report yet — run run_dogfood_snapshot()",
        "external_posting_disabled": True,
    }


__all__ = [
    "run_dogfood_snapshot",
    "get_latest_dogfood_report",
    "get_dogfood_status",
]
