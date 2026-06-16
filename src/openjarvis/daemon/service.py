from __future__ import annotations

import atexit
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

SYSTEMD_TEMPLATE = """\
[Unit]
Description=OpenJarvis Gateway Daemon
After=network.target

[Service]
Type=simple
ExecStart={python} -m openjarvis.daemon.gateway
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
"""

LAUNCHD_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openjarvis.gateway</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>openjarvis.daemon.gateway</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
"""


def generate_systemd_service(output: Path | None = None) -> str:
    content = SYSTEMD_TEMPLATE.format(python=sys.executable)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    return content


def generate_launchd_plist(output: Path | None = None) -> str:
    content = LAUNCHD_TEMPLATE.format(python=sys.executable)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    return content


# ---------------------------------------------------------------------------
# RuntimeLifecycleManager — PID file, health probe, graceful shutdown
# ---------------------------------------------------------------------------


_DEFAULT_PID_DIR = Path.home() / ".openjarvis"
_DEFAULT_PID_FILE = _DEFAULT_PID_DIR / "gateway.pid"


class RuntimeLifecycleManager:
    """Manages daemon PID file, startup health probe, and graceful shutdown.

    Usage:
        mgr = RuntimeLifecycleManager()
        mgr.start()   # writes PID file, registers atexit/signal handlers
        ...
        mgr.stop()    # removes PID file, fires shutdown callbacks

    Health probe:
        mgr.health()  # returns {'ok': bool, 'pid': int, 'uptime_seconds': float}

    Shutdown callbacks:
        mgr.on_shutdown(fn)  # register fn() to call on graceful stop
    """

    def __init__(
        self,
        pid_file: Optional[Path] = None,
        probe_modules: Optional[List[str]] = None,
    ) -> None:
        self._pid_file = pid_file or _DEFAULT_PID_FILE
        self._probe_modules = probe_modules or [
            "openjarvis.tools.jarvis_registry",
            "openjarvis.governance.constitution",
            "openjarvis.autonomy.modes",
        ]
        self._started_at: Optional[float] = None
        self._shutdown_callbacks: List[Callable[[], None]] = []
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> Dict[str, Any]:
        """Write PID file and register signal/atexit handlers.

        Returns health probe result.
        """
        self._write_pid()
        atexit.register(self.stop)
        self._register_signals()
        self._started_at = time.time()
        self._running = True
        return self.health()

    def stop(self) -> None:
        """Graceful stop: fire shutdown callbacks and remove PID file."""
        if not self._running:
            return
        self._running = False
        for cb in self._shutdown_callbacks:
            try:
                cb()
            except Exception:
                pass
        self._remove_pid()

    def on_shutdown(self, fn: Callable[[], None]) -> None:
        """Register a callback to invoke on graceful shutdown."""
        self._shutdown_callbacks.append(fn)

    # ------------------------------------------------------------------
    # Health probe
    # ------------------------------------------------------------------

    def health(self) -> Dict[str, Any]:
        """Return runtime health: uptime, PID file status, module probe."""
        pid = os.getpid()
        uptime = time.time() - self._started_at if self._started_at else 0.0
        pid_file_ok = self._pid_file.exists() and self._pid_file.read_text().strip() == str(pid)

        probe_failures: List[str] = []
        for mod in self._probe_modules:
            try:
                __import__(mod)
            except Exception as exc:
                probe_failures.append(f"{mod}: {exc}")

        return {
            "ok": pid_file_ok and not probe_failures,
            "pid": pid,
            "pid_file": str(self._pid_file),
            "pid_file_ok": pid_file_ok,
            "uptime_seconds": round(uptime, 1),
            "probe_failures": probe_failures,
            "running": self._running,
        }

    # ------------------------------------------------------------------
    # PID file helpers
    # ------------------------------------------------------------------

    def _write_pid(self) -> None:
        try:
            self._pid_file.parent.mkdir(parents=True, exist_ok=True)
            self._pid_file.write_text(str(os.getpid()))
        except OSError:
            pass

    def _remove_pid(self) -> None:
        try:
            if self._pid_file.exists():
                self._pid_file.unlink()
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _register_signals(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                signal.signal(sig, self._handle_signal)
            except (OSError, ValueError):
                pass

    def _handle_signal(self, signum: int, frame: Any) -> None:
        self.stop()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def read_pid(pid_file: Optional[Path] = None) -> Optional[int]:
        """Read PID from file. Returns None if file absent or invalid."""
        target = pid_file or _DEFAULT_PID_FILE
        try:
            return int(target.read_text().strip())
        except Exception:
            return None

    @staticmethod
    def is_running(pid_file: Optional[Path] = None) -> bool:
        """Check if a process with the stored PID is alive."""
        pid = RuntimeLifecycleManager.read_pid(pid_file)
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False


__all__ = [
    "RuntimeLifecycleManager",
    "generate_launchd_plist",
    "generate_systemd_service",
]
