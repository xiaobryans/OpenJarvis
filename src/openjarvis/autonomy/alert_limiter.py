"""Jarvis Alert Noise / Rate Limiter.

Implements:
  - Per-channel rate limits (max N alerts per time window)
  - Alert deduplication (same message within cooldown window = suppressed)
  - Quiet hours / DND config (no alerts during configured hours)
  - Escalation levels: info < warn < critical < incident
  - Incident/freeze mode: suppress all non-critical alerts
  - No public alerts, no uncontrolled send loops

Config stored at: ~/.openjarvis/alert_config.json
Alert log stored at: ~/.openjarvis/alert_log.jsonl

Hard rules:
  - NEVER automatically send real alerts
  - Rate limiter is advisory — actual sending requires connector approval flow
  - Incident mode blocks all info/warn alerts
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_DIR = Path.home() / ".openjarvis"
_ALERT_CONFIG = _CONFIG_DIR / "alert_config.json"
_ALERT_LOG = _CONFIG_DIR / "alert_log.jsonl"

_DEFAULT_CONFIG: Dict[str, Any] = {
    "channels": {
        "slack": {
            "max_per_hour": 10,
            "max_per_minute": 2,
            "cooldown_seconds": 60,
            "quiet_hours_start": 22,
            "quiet_hours_end": 8,
            "quiet_hours_tz": "local",
        },
        "telegram": {
            "max_per_hour": 10,
            "max_per_minute": 2,
            "cooldown_seconds": 60,
            "quiet_hours_start": 22,
            "quiet_hours_end": 8,
            "quiet_hours_tz": "local",
        },
    },
    "incident_mode": False,
    "freeze_mode": False,
    "escalation_levels": ["info", "warn", "critical", "incident"],
    "min_level_in_quiet_hours": "critical",
    "dedup_window_seconds": 300,
}


class AlertLevel:
    INFO = "info"
    WARN = "warn"
    CRITICAL = "critical"
    INCIDENT = "incident"


_LEVEL_ORDER = {AlertLevel.INFO: 0, AlertLevel.WARN: 1, AlertLevel.CRITICAL: 2, AlertLevel.INCIDENT: 3}


@dataclass
class AlertDecision:
    allowed: bool
    reason: str
    channel: str
    level: str
    dedup_key: str
    suppressed_by: Optional[str] = None  # "rate_limit", "quiet_hours", "dedup", "freeze", "incident_mode"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_alert_config() -> Dict[str, Any]:
    if not _ALERT_CONFIG.exists():
        return dict(_DEFAULT_CONFIG)
    try:
        data = json.loads(_ALERT_CONFIG.read_text(encoding="utf-8"))
        cfg = dict(_DEFAULT_CONFIG)
        cfg.update(data)
        return cfg
    except Exception:
        return dict(_DEFAULT_CONFIG)


def save_alert_config(config: Dict[str, Any]) -> bool:
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _ALERT_CONFIG.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def set_incident_mode(active: bool) -> None:
    cfg = load_alert_config()
    cfg["incident_mode"] = active
    save_alert_config(cfg)


def set_freeze_mode(active: bool) -> None:
    cfg = load_alert_config()
    cfg["freeze_mode"] = active
    save_alert_config(cfg)


# ---------------------------------------------------------------------------
# Alert log
# ---------------------------------------------------------------------------


def _load_recent_log(channel: str, window_seconds: int) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    if not _ALERT_LOG.exists():
        return entries
    cutoff = time.time() - window_seconds
    try:
        for line in _ALERT_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("channel") == channel and d.get("timestamp", 0) >= cutoff:
                entries.append(d)
    except Exception:
        pass
    return entries


def _append_alert_log(entry: Dict[str, Any]) -> None:
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with _ALERT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Dedup key
# ---------------------------------------------------------------------------


def make_dedup_key(channel: str, level: str, message: str) -> str:
    """Generate dedup key from channel+level+message hash."""
    digest = hashlib.sha256(f"{channel}:{level}:{message}".encode()).hexdigest()[:16]
    return f"{channel}:{level}:{digest}"


# ---------------------------------------------------------------------------
# Core rate-limit / suppression check
# ---------------------------------------------------------------------------


def check_alert(
    channel: str,
    level: str,
    message: str,
    record: bool = False,
) -> AlertDecision:
    """Check whether an alert is allowed.

    record=True: also append to alert log if allowed.

    Returns AlertDecision — never sends alert directly.
    """
    cfg = load_alert_config()
    dedup_key = make_dedup_key(channel, level, message)

    # Freeze mode: block everything
    if cfg.get("freeze_mode"):
        decision = AlertDecision(
            allowed=False,
            reason="Freeze mode active — all alerts suppressed",
            channel=channel,
            level=level,
            dedup_key=dedup_key,
            suppressed_by="freeze",
        )
        return decision

    # Incident mode: only incident/critical pass
    if cfg.get("incident_mode"):
        if _LEVEL_ORDER.get(level, 0) < _LEVEL_ORDER[AlertLevel.CRITICAL]:
            return AlertDecision(
                allowed=False,
                reason="Incident mode: only critical/incident alerts allowed",
                channel=channel,
                level=level,
                dedup_key=dedup_key,
                suppressed_by="incident_mode",
            )

    # Quiet hours check
    channel_cfg = cfg.get("channels", {}).get(channel, {})
    if channel_cfg:
        hour = int(time.strftime("%H"))
        q_start = channel_cfg.get("quiet_hours_start", 22)
        q_end = channel_cfg.get("quiet_hours_end", 8)
        if q_start is None or q_end is None:
            in_quiet = False
        else:
            in_quiet = (hour >= q_start) or (hour < q_end)
        min_level = cfg.get("min_level_in_quiet_hours", AlertLevel.CRITICAL)
        if in_quiet and _LEVEL_ORDER.get(level, 0) < _LEVEL_ORDER.get(min_level, 2):
            return AlertDecision(
                allowed=False,
                reason=f"Quiet hours ({q_start:02d}:00-{q_end:02d}:00) — level {level} below minimum {min_level}",
                channel=channel,
                level=level,
                dedup_key=dedup_key,
                suppressed_by="quiet_hours",
            )

    # Dedup check
    dedup_window = cfg.get("dedup_window_seconds", 300)
    recent = _load_recent_log(channel, dedup_window)
    for entry in recent:
        if entry.get("dedup_key") == dedup_key and entry.get("allowed"):
            return AlertDecision(
                allowed=False,
                reason=f"Duplicate alert suppressed (cooldown {dedup_window}s)",
                channel=channel,
                level=level,
                dedup_key=dedup_key,
                suppressed_by="dedup",
            )

    # Rate limit — per hour
    if channel_cfg:
        max_per_hour = channel_cfg.get("max_per_hour", 10)
        hour_entries = _load_recent_log(channel, 3600)
        allowed_hour = [e for e in hour_entries if e.get("allowed")]
        if len(allowed_hour) >= max_per_hour:
            return AlertDecision(
                allowed=False,
                reason=f"Rate limit: {max_per_hour}/hr exceeded ({len(allowed_hour)} sent)",
                channel=channel,
                level=level,
                dedup_key=dedup_key,
                suppressed_by="rate_limit",
            )

        max_per_minute = channel_cfg.get("max_per_minute", 2)
        minute_entries = _load_recent_log(channel, 60)
        allowed_minute = [e for e in minute_entries if e.get("allowed")]
        if len(allowed_minute) >= max_per_minute:
            return AlertDecision(
                allowed=False,
                reason=f"Rate limit: {max_per_minute}/min exceeded ({len(allowed_minute)} sent)",
                channel=channel,
                level=level,
                dedup_key=dedup_key,
                suppressed_by="rate_limit",
            )

    decision = AlertDecision(
        allowed=True,
        reason="Alert allowed — within rate limits",
        channel=channel,
        level=level,
        dedup_key=dedup_key,
        suppressed_by=None,
    )

    if record and decision.allowed:
        _append_alert_log({
            "timestamp": time.time(),
            "channel": channel,
            "level": level,
            "dedup_key": dedup_key,
            "allowed": True,
        })

    return decision


def get_alert_stats(channel: Optional[str] = None, window_seconds: int = 3600) -> Dict[str, Any]:
    """Stats for doctor/readiness."""
    cfg = load_alert_config()
    channels = [channel] if channel else list(cfg.get("channels", {}).keys())
    stats: Dict[str, Any] = {}
    for ch in channels:
        recent = _load_recent_log(ch, window_seconds)
        allowed = [e for e in recent if e.get("allowed")]
        stats[ch] = {
            "sent_in_window": len(allowed),
            "window_seconds": window_seconds,
            "max_per_hour": cfg.get("channels", {}).get(ch, {}).get("max_per_hour", 10),
        }
    return {
        "incident_mode": cfg.get("incident_mode", False),
        "freeze_mode": cfg.get("freeze_mode", False),
        "channels": stats,
    }


def get_alert_limiter_status() -> Dict[str, Any]:
    """Doctor/readiness status."""
    cfg = load_alert_config()
    return {
        "active": True,
        "incident_mode": cfg.get("incident_mode", False),
        "freeze_mode": cfg.get("freeze_mode", False),
        "channels_configured": list(cfg.get("channels", {}).keys()),
        "dedup_window_seconds": cfg.get("dedup_window_seconds", 300),
        "escalation_levels": cfg.get("escalation_levels", []),
        "quiet_hours_enabled": True,
    }


__all__ = [
    "AlertLevel",
    "AlertDecision",
    "load_alert_config",
    "save_alert_config",
    "set_incident_mode",
    "set_freeze_mode",
    "check_alert",
    "make_dedup_key",
    "get_alert_stats",
    "get_alert_limiter_status",
]
