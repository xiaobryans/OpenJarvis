"""Jarvis Connector Health Monitor.

Tracks health status for all connectors:
  Slack, Telegram, Tavily/Web, GitHub, OpenClaw, OMNIX

Statuses: healthy / degraded / blocked / not_configured
Each entry: last_checked timestamp, failure_reason (no secrets), consecutive_failures

Low-frequency by default — no polling loops, manual trigger only.
Doctor/readiness integration: reports per-connector status.

Hard rules:
  - Never include token values in failure_reason
  - No automated polling without explicit invocation
  - no_spam: min_check_interval enforced per connector
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.autonomy.connector_diagnostics import (
    get_github_status,
    get_openclaw_status,
    get_slack_status,
    get_telegram_status,
    get_web_search_status,
)

_HEALTH_STORE = Path.home() / ".openjarvis" / "connector_health.json"
_MIN_CHECK_INTERVAL = 300  # seconds between checks per connector
_DEGRADED_ESCALATION_THRESHOLD = 3  # consecutive failures before escalating to blocked


class HealthStatus:
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"


@dataclass
class ConnectorHealthEntry:
    connector: str
    status: str
    last_checked: float
    failure_reason: Optional[str] = None
    consecutive_failures: int = 0
    last_success: Optional[float] = None
    check_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Load / save health store
# ---------------------------------------------------------------------------


def _load_health() -> Dict[str, ConnectorHealthEntry]:
    if not _HEALTH_STORE.exists():
        return {}
    try:
        data = json.loads(_HEALTH_STORE.read_text(encoding="utf-8"))
        result = {}
        for k, v in data.items():
            result[k] = ConnectorHealthEntry(
                connector=v["connector"],
                status=v["status"],
                last_checked=v["last_checked"],
                failure_reason=v.get("failure_reason"),
                consecutive_failures=v.get("consecutive_failures", 0),
                last_success=v.get("last_success"),
                check_count=v.get("check_count", 0),
            )
        return result
    except Exception:
        return {}


def _save_health(entries: Dict[str, ConnectorHealthEntry]) -> None:
    try:
        _HEALTH_STORE.parent.mkdir(parents=True, exist_ok=True)
        _HEALTH_STORE.write_text(
            json.dumps({k: v.to_dict() for k, v in entries.items()}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Individual connector health checks (local diagnostics only — no API calls)
# ---------------------------------------------------------------------------


def _check_slack_health() -> tuple[str, Optional[str]]:
    s = get_slack_status()
    if s["status"] == "ready_pending_test_approval":
        return HealthStatus.HEALTHY, None
    if s["status"] == "configured":
        return HealthStatus.HEALTHY, None
    if s["status"] == "degraded":
        return HealthStatus.DEGRADED, "Missing: " + ", ".join(s.get("missing_env_vars", []))
    return HealthStatus.NOT_CONFIGURED, "Slack bot token not configured"


def _check_telegram_health() -> tuple[str, Optional[str]]:
    s = get_telegram_status()
    if s["status"] in ("ready_pending_test_approval", "configured"):
        return HealthStatus.HEALTHY, None
    if s["status"] == "degraded":
        return HealthStatus.DEGRADED, "Missing: " + ", ".join(s.get("missing_env_vars", []))
    return HealthStatus.NOT_CONFIGURED, "Telegram bot token not configured"


def _check_tavily_health() -> tuple[str, Optional[str]]:
    s = get_web_search_status()
    if s["status"] == "configured":
        return HealthStatus.HEALTHY, None
    return HealthStatus.NOT_CONFIGURED, "No web search API key configured"


def _check_github_health() -> tuple[str, Optional[str]]:
    s = get_github_status()
    if s.get("git_available"):
        return HealthStatus.HEALTHY, None
    return HealthStatus.NOT_CONFIGURED, "git not found on PATH"


def _check_openclaw_health() -> tuple[str, Optional[str]]:
    s = get_openclaw_status()
    if s["status"] == "configured":
        return HealthStatus.HEALTHY, None
    if s["status"] == "degraded":
        return HealthStatus.DEGRADED, s.get("summary", "OpenClaw path issues")
    return HealthStatus.NOT_CONFIGURED, "OpenClaw workspace not configured"


def _check_omnix_health() -> tuple[str, Optional[str]]:
    from openjarvis.projects.source_links import _load_openjarvis_env as _load_env
    _load_env()
    path = os.environ.get("JARVIS_PROJECT_OMNIX_REPO_PATH", "")
    if path and Path(path).exists():
        return HealthStatus.HEALTHY, None
    if path:
        return HealthStatus.DEGRADED, f"OMNIX repo path set but not found: {path}"
    return HealthStatus.NOT_CONFIGURED, "JARVIS_PROJECT_OMNIX_REPO_PATH not set"


_CHECKER_MAP = {
    "slack": _check_slack_health,
    "telegram": _check_telegram_health,
    "tavily": _check_tavily_health,
    "github": _check_github_health,
    "openclaw": _check_openclaw_health,
    "omnix": _check_omnix_health,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_connector_health(
    connector: str,
    force: bool = False,
) -> ConnectorHealthEntry:
    """Check health of a single connector. Respects min_check_interval."""
    health = _load_health()
    existing = health.get(connector)
    now = time.time()

    if not force and existing:
        if now - existing.last_checked < _MIN_CHECK_INTERVAL:
            return existing  # return cached, not too frequent

    checker = _CHECKER_MAP.get(connector)
    if not checker:
        entry = ConnectorHealthEntry(
            connector=connector,
            status=HealthStatus.UNKNOWN,
            last_checked=now,
            failure_reason=f"No health checker registered for '{connector}'",
        )
    else:
        try:
            status, reason = checker()
            prev_failures = existing.consecutive_failures if existing else 0
            if status in (HealthStatus.HEALTHY,):
                consec = 0
                last_success = now
            else:
                consec = prev_failures + 1
                last_success = existing.last_success if existing else None
            entry = ConnectorHealthEntry(
                connector=connector,
                status=status,
                last_checked=now,
                failure_reason=reason,
                consecutive_failures=consec,
                last_success=last_success,
                check_count=(existing.check_count if existing else 0) + 1,
            )
        except Exception as exc:
            entry = ConnectorHealthEntry(
                connector=connector,
                status=HealthStatus.DEGRADED,
                last_checked=now,
                failure_reason=f"Health check raised exception: {type(exc).__name__}",
                consecutive_failures=(existing.consecutive_failures if existing else 0) + 1,
            )

        # Escalate to blocked if consecutive failures exceed threshold
        if (
            entry.status == HealthStatus.DEGRADED
            and entry.consecutive_failures >= _DEGRADED_ESCALATION_THRESHOLD
        ):
            entry.status = HealthStatus.BLOCKED
            entry.failure_reason = (
                f"{entry.failure_reason or 'degraded'} "
                f"[escalated: {entry.consecutive_failures} consecutive failures]"
            )

    health[connector] = entry
    _save_health(health)
    return entry


def check_all_connectors(force: bool = False) -> Dict[str, ConnectorHealthEntry]:
    """Check all registered connectors."""
    return {
        name: check_connector_health(name, force=force)
        for name in _CHECKER_MAP
    }


def get_connector_health_report() -> Dict[str, Any]:
    """Full health report for doctor/readiness."""
    health = _load_health()
    report: Dict[str, Any] = {}
    for name, entry in health.items():
        report[name] = {
            "status": entry.status,
            "last_checked": entry.last_checked,
            "failure_reason": entry.failure_reason,
            "consecutive_failures": entry.consecutive_failures,
            "check_count": entry.check_count,
        }
    # Report unchecked connectors
    for name in _CHECKER_MAP:
        if name not in report:
            report[name] = {"status": HealthStatus.UNKNOWN, "last_checked": None, "note": "Not yet checked"}
    unhealthy = [
        k for k, v in report.items()
        if v.get("status") not in (HealthStatus.HEALTHY, HealthStatus.UNKNOWN)
    ]
    return {
        "connectors": report,
        "total": len(_CHECKER_MAP),
        "unhealthy": unhealthy,
        "unhealthy_count": len(unhealthy),
        "min_check_interval_seconds": _MIN_CHECK_INTERVAL,
    }


def clear_health_cache(db_path: Optional[Path] = None) -> None:
    """Clear cached health data (for tests)."""
    target = db_path or _HEALTH_STORE
    if target.exists():
        target.unlink()


def get_degraded_connectors(include_blocked: bool = True) -> List[str]:
    """Return connectors in degraded or blocked state from cache.

    Uses cached data only — does not re-check connectors.
    """
    health = _load_health()
    statuses = {HealthStatus.DEGRADED}
    if include_blocked:
        statuses.add(HealthStatus.BLOCKED)
    return [name for name, entry in health.items() if entry.status in statuses]


def get_connector_degradation_summary() -> Dict[str, Any]:
    """Return degradation summary: counts, worst connectors, escalation threshold."""
    health = _load_health()
    by_status: Dict[str, int] = {}
    worst: List[Dict[str, Any]] = []
    for name, entry in health.items():
        by_status[entry.status] = by_status.get(entry.status, 0) + 1
        if entry.status in (HealthStatus.DEGRADED, HealthStatus.BLOCKED):
            worst.append({
                "connector": name,
                "status": entry.status,
                "consecutive_failures": entry.consecutive_failures,
                "failure_reason": entry.failure_reason,
            })
    worst.sort(key=lambda x: x["consecutive_failures"], reverse=True)
    return {
        "by_status": by_status,
        "degraded_or_blocked": worst,
        "degraded_count": by_status.get(HealthStatus.DEGRADED, 0),
        "blocked_count": by_status.get(HealthStatus.BLOCKED, 0),
        "escalation_threshold": _DEGRADED_ESCALATION_THRESHOLD,
        "total_tracked": len(health),
    }


def reset_connector_failures(connector: str) -> bool:
    """Reset consecutive_failures for a connector to 0 and set status healthy.

    Use after manual remediation to clear escalated blocked state.
    """
    health = _load_health()
    if connector not in health:
        return False
    entry = health[connector]
    entry.consecutive_failures = 0
    entry.status = HealthStatus.HEALTHY
    entry.failure_reason = None
    entry.last_success = time.time()
    _save_health(health)
    return True


__all__ = [
    "HealthStatus",
    "ConnectorHealthEntry",
    "check_connector_health",
    "check_all_connectors",
    "get_connector_health_report",
    "get_connector_degradation_summary",
    "get_degraded_connectors",
    "reset_connector_failures",
    "clear_health_cache",
]
