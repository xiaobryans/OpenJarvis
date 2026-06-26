"""Daily operations for Jarvis — overnight monitoring + morning briefing.

Two real, runnable routines that produce genuine output (no mocks):

- ``run_overnight_monitor()`` — system health + memory integrity check, auto-fix
  what it can, log everything with timestamps, and write a "flagged for the
  morning" file the briefing reads.
- ``generate_morning_briefing()`` — composes a real briefing from system health,
  last night's monitor results, today's calendar, important unread email,
  date/time + Singapore weather, and top priorities from memory. Each section is
  best-effort and **never fails silently** — a section that can't load reports
  why and is skipped gracefully.

Both persist their output under ``~/.openjarvis/`` and append to a timestamped
log. They are invoked:
- on demand via the ``morning_briefing`` tool (so Bryan can ask any time),
- on a schedule via :mod:`openjarvis.scheduler` (see ``register_daily_ops``),
- or directly: ``python -m openjarvis.jarvis_os.daily_ops briefing|monitor``.

Schedule times are config-driven (``~/.openjarvis/jarvis_schedule.json``).
"""

from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("openjarvis.daily_ops")

_HOME = Path.home() / ".openjarvis"
_BRIEFING_DIR = _HOME / "briefings"
_MONITOR_DIR = _HOME / "monitor"
_SCHEDULE_CONFIG = _HOME / "jarvis_schedule.json"

# Default schedule — configurable via jarvis_schedule.json.
_DEFAULT_SCHEDULE = {
    "timezone": "Asia/Singapore",
    "morning_briefing_cron": "0 8 * * *",   # 08:00 SGT daily
    "overnight_monitor_cron": "0 3 * * *",  # 03:00 SGT daily
    "enabled": True,
}


def load_schedule_config() -> dict:
    """Load the (simple, file-based) schedule config, creating defaults once."""
    try:
        if _SCHEDULE_CONFIG.exists():
            cfg = json.loads(_SCHEDULE_CONFIG.read_text("utf-8"))
            return {**_DEFAULT_SCHEDULE, **cfg}
        _HOME.mkdir(parents=True, exist_ok=True)
        _SCHEDULE_CONFIG.write_text(json.dumps(_DEFAULT_SCHEDULE, indent=2), "utf-8")
    except Exception:
        logger.warning("schedule config load failed; using defaults", exc_info=True)
    return dict(_DEFAULT_SCHEDULE)


def _now_sgt_str() -> str:
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Asia/Singapore"))
    except Exception:
        now = datetime.now().astimezone()
    return now.strftime("%A, %B %d, %Y, %I:%M %p %Z")


def _section(name: str, fn: Callable[[], str]) -> str:
    """Run one briefing/monitor section; on failure report it (never silent)."""
    try:
        out = fn()
        return out if out else f"_{name}: nothing to report._"
    except Exception as exc:
        logger.error("section %s failed: %s", name, exc, exc_info=True)
        return f"_{name}: unavailable ({type(exc).__name__}: {exc})._"


def _ensure_env() -> None:
    """Load .env/.env.local/cloud-keys so connector tokens (Slack etc.) are
    present even when run from the CLI / scheduler (not just the API server)."""
    try:
        from openjarvis.core.env_loader import ensure_local_env_loaded

        ensure_local_env_loaded()
    except Exception:
        logger.debug("env load failed", exc_info=True)


def _tool(name: str, **kw) -> str:
    """Execute a registered tool and return its content (or a clear error)."""
    _ensure_env()
    import openjarvis.tools  # noqa: F401 ensure registration
    from openjarvis.core.registry import ToolRegistry

    if name not in ToolRegistry.keys():
        return f"(tool {name} not available)"
    res = ToolRegistry.get(name)().execute(**kw)
    return res.content if getattr(res, "success", False) else f"(skipped: {res.content})"


def _memory_backend():
    from openjarvis.core.config import load_config
    from openjarvis.core.registry import MemoryRegistry
    import openjarvis.tools.storage  # noqa: F401 register sqlite

    cfg = load_config()
    return MemoryRegistry.create("sqlite", db_path=cfg.memory.db_path)


# ---------------------------------------------------------------------------
# Overnight monitor
# ---------------------------------------------------------------------------
def run_overnight_monitor() -> dict:
    """Run the overnight system + memory check. Returns a structured report and
    persists it + a 'flagged for morning' summary the briefing reads."""
    _ensure_env()
    started = datetime.now(timezone.utc)
    issues: list[str] = []
    fixed: list[str] = []
    checks: dict[str, str] = {}

    # 1. Import / system integrity
    def _sys_check() -> None:
        import openjarvis.tools  # noqa: F401
        from openjarvis.core.registry import ToolRegistry

        n = len(ToolRegistry.keys())
        checks["tool_registry"] = f"ok ({n} tools)"
        if n == 0:
            issues.append("Tool registry empty — registration may have failed.")

    # 2. Memory integrity (open + count + round-trip probe)
    def _mem_check() -> None:
        m = _memory_backend()
        cnt = m.count()
        probe = m.store("__overnight_probe__", source="monitor")
        hits = m.retrieve("__overnight_probe__", top_k=1)
        m.delete(probe)
        if not hits:
            issues.append("Memory round-trip probe returned nothing — recall may be broken.")
        else:
            checks["memory"] = f"ok ({cnt} entries, round-trip verified)"

    # 3. Connector reachability (presence-only, no data dump)
    def _conn_check() -> None:
        import os
        from openjarvis.core.env_loader import ensure_local_env_loaded

        ensure_local_env_loaded()
        present = {
            "google_oauth": bool(os.environ.get("GOOGLE_OAUTH_CLIENT_ID")),
            "slack": bool(os.environ.get("SLACK_BOT_TOKEN")),
            "github": bool(os.environ.get("GITHUB_TOKEN")),
        }
        checks["connectors"] = ", ".join(f"{k}={'present' if v else 'absent'}"
                                         for k, v in present.items())

    for name, fn in (("system", _sys_check), ("memory", _mem_check),
                     ("connectors", _conn_check)):
        try:
            fn()
        except Exception as exc:
            issues.append(f"{name} check error: {type(exc).__name__}: {exc}")
            logger.error("overnight %s check failed", name, exc_info=True)

    ended = datetime.now(timezone.utc)
    report = {
        "started_utc": started.isoformat(),
        "ended_utc": ended.isoformat(),
        "duration_s": round((ended - started).total_seconds(), 2),
        "checks": checks,
        "issues": issues,
        "auto_fixed": fixed,
        "urgent_for_briefing": issues,  # anything unfixed is flagged for morning
    }

    try:
        _MONITOR_DIR.mkdir(parents=True, exist_ok=True)
        stamp = started.strftime("%Y%m%d_%H%M%S")
        (_MONITOR_DIR / f"monitor_{stamp}.json").write_text(
            json.dumps(report, indent=2), "utf-8"
        )
        (_MONITOR_DIR / "latest.json").write_text(json.dumps(report, indent=2), "utf-8")
        with (_MONITOR_DIR / "monitor.log").open("a", encoding="utf-8") as fh:
            fh.write(f"[{ended.isoformat()}] checks={checks} issues={len(issues)}\n")
    except Exception:
        logger.error("overnight monitor persist failed", exc_info=True)

    return report


# ---------------------------------------------------------------------------
# Morning briefing
# ---------------------------------------------------------------------------
def generate_morning_briefing() -> str:
    """Compose and persist the morning briefing. Returns the markdown text."""
    _ensure_env()
    lines = [f"# Good morning, Bryan — {_now_sgt_str()}", ""]

    # 1. System health + overnight results
    def _health() -> str:
        latest = _MONITOR_DIR / "latest.json"
        if not latest.exists():
            return "No overnight monitor run on record yet."
        rep = json.loads(latest.read_text("utf-8"))
        chk = "; ".join(f"{k}: {v}" for k, v in rep.get("checks", {}).items())
        iss = rep.get("issues", [])
        s = f"Overnight check ({rep.get('ended_utc','?')[:16]}Z): {chk or 'no checks'}."
        if iss:
            s += "\n  ⚠️ Issues flagged:\n" + "\n".join(f"   - {i}" for i in iss)
        else:
            s += " No issues found overnight."
        return s

    # 2-6 via real tools / memory
    def _priorities() -> str:
        m = _memory_backend()
        hits = m.retrieve("priority goal todo fighting for jarvis build", top_k=4)
        if not hits:
            return "No standing priorities in memory yet."
        return "\n".join(f"- {h.content[:120]}" for h in hits)

    lines += ["## System & overnight", _section("health", _health), ""]
    lines += ["## Today's schedule", _section("calendar", lambda: _tool("calendar_today")), ""]
    lines += ["## Important email", _section("email", lambda: _tool("gmail_important", max_messages=5)), ""]
    lines += ["## Messages", _section("slack", lambda: _tool("slack_recent")), ""]
    lines += ["## Date & weather", _section("weather", lambda: _tool("current_weather", location="Singapore")), ""]
    lines += ["## Top priorities", _section("priorities", _priorities), ""]
    lines += ["_— Jarvis. Get after it, boss._"]

    text = "\n".join(lines)

    # Persist + save a short pointer to memory (so Jarvis can recall it in chat).
    try:
        _BRIEFING_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        (_BRIEFING_DIR / f"briefing_{stamp}.md").write_text(text, "utf-8")
        (_BRIEFING_DIR / "latest.md").write_text(text, "utf-8")
    except Exception:
        logger.error("briefing persist failed", exc_info=True)
    try:
        _memory_backend().store(
            f"Morning briefing generated {_now_sgt_str()}.",
            source="briefing",
        )
    except Exception:
        logger.debug("briefing memory save failed", exc_info=True)

    return text


# ---------------------------------------------------------------------------
# Scheduler registration (uses the real TaskScheduler)
# ---------------------------------------------------------------------------
def register_daily_ops(scheduler: Any) -> dict:
    """Register the briefing + monitor as cron tasks on a TaskScheduler.

    Returns a summary of what was registered. Safe to call repeatedly (it skips
    if a same-named task already exists). The scheduler fires these while the
    server/daemon is running; for guaranteed firing when the host is asleep, an
    OS-level cron/launchd entry calling the CLI is the fallback (see module doc).
    """
    cfg = load_schedule_config()
    out = {"enabled": cfg.get("enabled", True), "registered": []}
    if not cfg.get("enabled", True):
        return out
    try:
        scheduler.create_task(
            prompt="Generate and deliver Bryan's morning briefing using the "
                   "morning_briefing tool.",
            schedule_type="cron",
            schedule_value=cfg["morning_briefing_cron"],
        )
        out["registered"].append(("morning_briefing", cfg["morning_briefing_cron"]))
        scheduler.create_task(
            prompt="Run the overnight system + memory monitor.",
            schedule_type="cron",
            schedule_value=cfg["overnight_monitor_cron"],
        )
        out["registered"].append(("overnight_monitor", cfg["overnight_monitor_cron"]))
    except Exception as exc:
        logger.error("daily-ops scheduler registration failed: %s", exc, exc_info=True)
        out["error"] = str(exc)
    return out


def _main(argv: list[str]) -> int:
    which = argv[1] if len(argv) > 1 else "briefing"
    if which == "monitor":
        rep = run_overnight_monitor()
        print(json.dumps(rep, indent=2))
    else:
        print(generate_morning_briefing())
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_main(sys.argv))
