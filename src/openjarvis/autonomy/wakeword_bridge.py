"""Jarvis Wake-Word Bridge — launches isolated worker + receives triggers.

Main-venv side of the wake-word bridge. Spawns the worker process using
the .wake_worker_venv Python, connects to its socket, and fires callbacks
when a wake-word trigger arrives.

Usage (in main Jarvis process):
    from openjarvis.autonomy.wakeword_bridge import WakeWordBridge
    bridge = WakeWordBridge()
    bridge.register_callback(lambda ev: print("Wake word:", ev))
    status = bridge.start()   # starts worker subprocess + socket reader
    bridge.stop()             # graceful shutdown

Safety:
  - Worker runs in isolated .wake_worker_venv (Python 3.12 + onnxruntime).
  - Communication via Unix socket or localhost TCP only.
  - No public endpoints. No audio data transmitted.
  - Worker is a daemon subprocess — dies with parent process.
"""
from __future__ import annotations

import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).parent.parent.parent.parent  # OpenJarvis root
_WORKER_VENV = _REPO_ROOT / ".wake_worker_venv"
_WORKER_PYTHON = _WORKER_VENV / "bin" / "python"
_WORKER_SCRIPT = Path(__file__).parent / "wakeword_worker.py"

_SOCKET_PATH = os.environ.get("JARVIS_WAKEWORD_SOCKET", "/tmp/jarvis_wakeword.sock")
_TCP_PORT = int(os.environ.get("JARVIS_WAKEWORD_PORT", "19876"))
_WORKER_STARTUP_TIMEOUT = float(os.environ.get("JARVIS_WAKEWORD_STARTUP_TIMEOUT", "8.0"))

# ---------------------------------------------------------------------------
# Trigger event
# ---------------------------------------------------------------------------


@dataclass
class WakeWordTriggerEvent:
    model: str
    score: float
    ts: float
    source: str = "true_wakeword"
    raw: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------


class WakeWordBridge:
    """Launches wake-word worker and receives trigger events."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._running = False
        self._callbacks: List[Callable[[WakeWordTriggerEvent], None]] = []
        self._last_trigger: Optional[float] = None
        self._trigger_count = 0
        self._conn: Optional[socket.socket] = None
        self._error: Optional[str] = None

    def register_callback(self, cb: Callable[[WakeWordTriggerEvent], None]) -> None:
        with self._lock:
            self._callbacks.append(cb)

    def is_available(self) -> bool:
        """Check if worker venv + script exist."""
        return _WORKER_PYTHON.exists() and _WORKER_SCRIPT.exists()

    def start(self) -> Dict[str, Any]:
        """Start worker subprocess and socket reader thread."""
        with self._lock:
            if self._running:
                return {"ok": True, "already_running": True}

        if not self.is_available():
            msg = (
                f"Worker venv not found at {_WORKER_VENV}. "
                "Run: uv venv .wake_worker_venv --python 3.12 && "
                "uv pip install --python .wake_worker_venv/bin/python openwakeword sounddevice"
            )
            with self._lock:
                self._error = msg
            logger.error(msg)
            return {"ok": False, "error": msg}

        env = os.environ.copy()
        env["JARVIS_WAKEWORD_SOCKET"] = _SOCKET_PATH

        try:
            proc = subprocess.Popen(
                [str(_WORKER_PYTHON), str(_WORKER_SCRIPT)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            with self._lock:
                self._process = proc

            # Wait for socket to appear
            deadline = time.time() + _WORKER_STARTUP_TIMEOUT
            while time.time() < deadline:
                if os.path.exists(_SOCKET_PATH):
                    break
                if proc.poll() is not None:
                    out = ""
                    try:
                        out = proc.stdout.read(2000) if proc.stdout else ""
                    except Exception:
                        pass
                    msg = f"Worker exited early (rc={proc.returncode}): {out}"
                    with self._lock:
                        self._error = msg
                    logger.error(msg)
                    return {"ok": False, "error": msg}
                time.sleep(0.1)

            if not os.path.exists(_SOCKET_PATH):
                # Try TCP fallback
                conn = self._connect_tcp()
            else:
                conn = self._connect_unix()

            if conn is None:
                msg = "Could not connect to worker socket after startup"
                with self._lock:
                    self._error = msg
                return {"ok": False, "error": msg}

            with self._lock:
                self._conn = conn
                self._running = True
                self._error = None

            t = threading.Thread(target=self._reader_loop, daemon=True)
            t.start()
            with self._lock:
                self._reader_thread = t

            logger.info("WakeWordBridge started — worker pid=%d", proc.pid)
            return {
                "ok": True,
                "worker_pid": proc.pid,
                "socket": _SOCKET_PATH if os.path.exists(_SOCKET_PATH) else f"tcp:127.0.0.1:{_TCP_PORT}",
            }

        except Exception as exc:
            with self._lock:
                self._error = str(exc)
            logger.error("WakeWordBridge.start failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def _connect_unix(self) -> Optional[socket.socket]:
        for _ in range(10):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(_SOCKET_PATH)
                return s
            except OSError:
                time.sleep(0.2)
        return None

    def _connect_tcp(self) -> Optional[socket.socket]:
        for _ in range(10):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect(("127.0.0.1", _TCP_PORT))
                return s
            except OSError:
                time.sleep(0.2)
        return None

    def _reader_loop(self) -> None:
        """Read newline-delimited JSON triggers from worker socket."""
        buf = ""
        while True:
            with self._lock:
                conn = self._conn
                running = self._running
            if not running or conn is None:
                break
            try:
                data = conn.recv(4096)
                if not data:
                    logger.warning("Worker socket closed")
                    break
                buf += data.decode("utf-8", errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if line:
                        self._dispatch(line)
            except OSError:
                break
        with self._lock:
            self._running = False

    def _dispatch(self, raw_line: str) -> None:
        try:
            d = json.loads(raw_line)
        except Exception:
            logger.debug("Non-JSON from worker: %s", raw_line[:100])
            return
        if d.get("event") != "wake_word":
            return
        ev = WakeWordTriggerEvent(
            model=d.get("model", ""),
            score=float(d.get("score", 0)),
            ts=float(d.get("ts", time.time())),
            raw=d,
        )
        with self._lock:
            self._trigger_count += 1
            self._last_trigger = ev.ts
            cbs = list(self._callbacks)
        for cb in cbs:
            try:
                cb(ev)
            except Exception as exc:
                logger.warning("Callback raised: %s", exc)

    def stop(self) -> None:
        with self._lock:
            self._running = False
            if self._conn:
                try:
                    self._conn.close()
                except OSError:
                    pass
                self._conn = None
            if self._process:
                try:
                    self._process.terminate()
                except ProcessLookupError:
                    pass
                self._process = None

    def status(self) -> Dict[str, Any]:
        with self._lock:
            proc = self._process
            return {
                "true_wakeword_engine": "openwakeword",
                "true_wakeword_model": os.environ.get("JARVIS_WAKEWORD_MODEL", "hey_jarvis_v0.1"),
                "worker_available": self.is_available(),
                "worker_running": self._running,
                "worker_pid": proc.pid if proc and proc.poll() is None else None,
                "worker_venv": str(_WORKER_VENV),
                "worker_python": str(_WORKER_PYTHON),
                "trigger_count": self._trigger_count,
                "last_trigger": self._last_trigger,
                "error": self._error,
                "socket_path": _SOCKET_PATH,
                "tcp_port": _TCP_PORT,
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


_BRIDGE = WakeWordBridge()


def get_bridge() -> WakeWordBridge:
    return _BRIDGE


def get_worker_status() -> Dict[str, Any]:
    """Return worker availability + readiness without starting it."""
    available = _BRIDGE.is_available()
    if not available:
        return {
            "true_wakeword_status": "TRUE_WAKEWORD_BLOCKED_BY_DEPENDENCY_OR_PLATFORM",
            "worker_available": False,
            "blocker": (
                f"Worker venv not found at {_WORKER_VENV}. "
                "Run: uv venv .wake_worker_venv --python 3.12 && "
                "uv pip install --python .wake_worker_venv/bin/python openwakeword sounddevice"
            ),
        }
    return {
        "true_wakeword_status": "openwakeword_available",
        "worker_available": True,
        "worker_venv": str(_WORKER_VENV),
        "worker_python": str(_WORKER_PYTHON),
        "model": os.environ.get("JARVIS_WAKEWORD_MODEL", "hey_jarvis_v0.1"),
        "phrases": ["hey jarvis"],
        "socket_path": _SOCKET_PATH,
        "tcp_port": _TCP_PORT,
        "note": (
            "Isolated worker (Python 3.12 + onnxruntime 1.23.2). "
            "Call WakeWordBridge.start() to activate."
        ),
    }
