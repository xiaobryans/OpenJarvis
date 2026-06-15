"""Jarvis Autonomy Package — project-aware autonomy modes, watchdogs, and alerts.

Exports:
  - AutonomyMode, AutonomyPolicy   (modes.py)
  - WatchdogRunner, WatchdogResult  (watchdogs.py)
  - AlertStore, AlertRecord         (alerts.py)
"""

from openjarvis.autonomy.modes import AutonomyMode, AutonomyModeEntry, AutonomyPolicy
from openjarvis.autonomy.watchdogs import WatchdogResult, WatchdogRunner, WatchdogSeverity, WatchdogStatus
from openjarvis.autonomy.alerts import AlertRecord, AlertSeverity, AlertStatus, AlertStore, get_alert_store

__all__ = [
    "AlertRecord",
    "AlertSeverity",
    "AlertStatus",
    "AlertStore",
    "AutonomyMode",
    "AutonomyModeEntry",
    "AutonomyPolicy",
    "WatchdogResult",
    "WatchdogRunner",
    "WatchdogSeverity",
    "WatchdogStatus",
    "get_alert_store",
]
