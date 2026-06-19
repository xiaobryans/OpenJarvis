"""Orchestrator Runtime Trace Events.

Structured observability for the full Jarvis orchestration pipeline:
  Bryan → front-door → COS/GM → manager-activation → worker-execution
  → validation → NUS-feedback → blocker → final-response

Each event carries a trace_id (set at front-door entry) that flows through
the entire pipeline, enabling end-to-end request correlation.

Design rules:
  - Lightweight: in-memory event list; no external dependency required.
  - Structured: every event has a typed event_type and structured payload.
  - No raw CoT: decision summaries only, never raw model output.
  - Thread-safe singleton per process.
  - Survives individual component failures (graceful degradation).
  - Reuses existing core/events.py EventBus where possible; does not replace it.
  - Extends workbench/event_log.py concept to orchestrator level.
  - Persists completed traces to ~/.jarvis/traces/ as JSONL (bounded retention).
  - Disk writes are best-effort; failure does not break in-memory operation.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Disk persistence path — private, bounded
_TRACES_DIR = Path.home() / ".jarvis" / "traces"
_MAX_TRACE_FILES = 500  # retained files on disk


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EVENT_FRONT_DOOR = "front_door"
EVENT_ROUTING = "routing"
EVENT_COS_GM = "cos_gm"
EVENT_MANAGER_ACTIVATION = "manager_activation"
EVENT_WORKER_EXECUTION = "worker_execution"
EVENT_VALIDATION = "validation"
EVENT_NUS_FEEDBACK = "nus_feedback"
EVENT_BLOCKER = "blocker"
EVENT_FINAL_RESPONSE = "final_response"

ALL_EVENT_TYPES = frozenset({
    EVENT_FRONT_DOOR,
    EVENT_ROUTING,
    EVENT_COS_GM,
    EVENT_MANAGER_ACTIVATION,
    EVENT_WORKER_EXECUTION,
    EVENT_VALIDATION,
    EVENT_NUS_FEEDBACK,
    EVENT_BLOCKER,
    EVENT_FINAL_RESPONSE,
})


# ---------------------------------------------------------------------------
# RuntimeTraceEvent
# ---------------------------------------------------------------------------

@dataclass
class RuntimeTraceEvent:
    """Single structured trace event from the orchestration pipeline."""
    trace_id: str
    event_type: str
    timestamp_ms: float
    component: str
    summary: str
    payload: Dict[str, Any] = field(default_factory=dict)
    no_raw_chain_of_thought: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "event_type": self.event_type,
            "timestamp_ms": self.timestamp_ms,
            "component": self.component,
            "summary": self.summary,
            "payload": self.payload,
            "no_raw_chain_of_thought": self.no_raw_chain_of_thought,
        }


# ---------------------------------------------------------------------------
# OrchestratorTrace — per-request trace container
# ---------------------------------------------------------------------------

@dataclass
class OrchestratorTrace:
    """All events for a single request, correlated by trace_id."""
    trace_id: str
    request_id: str
    start_time_ms: float = field(default_factory=lambda: time.time() * 1000)
    events: List[RuntimeTraceEvent] = field(default_factory=list)

    def add_event(
        self,
        event_type: str,
        component: str,
        summary: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> RuntimeTraceEvent:
        evt = RuntimeTraceEvent(
            trace_id=self.trace_id,
            event_type=event_type,
            timestamp_ms=time.time() * 1000,
            component=component,
            summary=summary,
            payload=payload or {},
        )
        self.events.append(evt)
        return evt

    def elapsed_ms(self) -> float:
        return time.time() * 1000 - self.start_time_ms

    def event_types_seen(self) -> List[str]:
        return [e.event_type for e in self.events]

    def get_by_type(self, event_type: str) -> List[RuntimeTraceEvent]:
        return [e for e in self.events if e.event_type == event_type]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "start_time_ms": self.start_time_ms,
            "elapsed_ms": self.elapsed_ms(),
            "event_count": len(self.events),
            "event_types_seen": self.event_types_seen(),
            "events": [e.to_dict() for e in self.events],
        }


# ---------------------------------------------------------------------------
# RuntimeTraceStore — in-memory store of recent traces
# ---------------------------------------------------------------------------

class RuntimeTraceStore:
    """In-memory + disk store for orchestrator traces.

    In-memory: keeps last N traces for fast lookup and replay.
    Disk: persists completed traces to ~/.jarvis/traces/ as JSONL files
          (one file per trace). Bounded to _MAX_TRACE_FILES files.
          Disk writes are best-effort — failures degrade gracefully.
    """

    def __init__(self, max_traces: int = 200, persist: bool = True) -> None:
        self._traces: Dict[str, OrchestratorTrace] = {}
        self._order: List[str] = []
        self._max = max_traces
        self._persist = persist

    def create_trace(self, request_id: str, trace_id: Optional[str] = None) -> OrchestratorTrace:
        """Create a new trace for a request. Returns the OrchestratorTrace."""
        tid = trace_id or uuid.uuid4().hex[:16]
        trace = OrchestratorTrace(trace_id=tid, request_id=request_id)
        self._traces[tid] = trace
        self._order.append(tid)
        # Evict oldest if over limit
        while len(self._order) > self._max:
            old = self._order.pop(0)
            self._traces.pop(old, None)
        return trace

    def persist_trace(self, trace_id: str) -> bool:
        """Persist a completed trace to disk. Returns True on success.

        Writes to ~/.jarvis/traces/<trace_id>.jsonl (one event per line).
        Best-effort — disk failures never raise to callers.
        Enforces _MAX_TRACE_FILES retention limit by removing oldest files.
        """
        if not self._persist:
            return False
        trace = self._traces.get(trace_id)
        if trace is None:
            return False
        try:
            _TRACES_DIR.mkdir(parents=True, exist_ok=True)
            trace_file = _TRACES_DIR / f"{trace_id}.jsonl"
            lines: List[str] = []
            # Header line: trace metadata
            header = {
                "record_type": "trace_header",
                "trace_id": trace.trace_id,
                "request_id": trace.request_id,
                "start_time_ms": trace.start_time_ms,
                "elapsed_ms": trace.elapsed_ms(),
                "event_count": len(trace.events),
            }
            lines.append(json.dumps(header))
            # One line per event
            for evt in trace.events:
                lines.append(json.dumps(evt.to_dict()))
            trace_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
            # Enforce retention limit
            self._enforce_retention()
            return True
        except Exception as exc:
            logger.debug("Trace persistence failed (non-fatal): %s", exc)
            return False

    def load_trace_from_disk(self, trace_id: str) -> Optional[OrchestratorTrace]:
        """Load a trace from disk by trace_id. Returns None if not found.

        Used for cross-restart replay. In-memory traces are preferred.
        """
        if trace_id in self._traces:
            return self._traces[trace_id]
        trace_file = _TRACES_DIR / f"{trace_id}.jsonl"
        if not trace_file.exists():
            return None
        try:
            lines = trace_file.read_text(encoding="utf-8").splitlines()
            if not lines:
                return None
            header = json.loads(lines[0])
            trace = OrchestratorTrace(
                trace_id=header["trace_id"],
                request_id=header["request_id"],
                start_time_ms=header.get("start_time_ms", 0.0),
            )
            for line in lines[1:]:
                if not line.strip():
                    continue
                evt_data = json.loads(line)
                evt = RuntimeTraceEvent(
                    trace_id=evt_data["trace_id"],
                    event_type=evt_data["event_type"],
                    timestamp_ms=evt_data["timestamp_ms"],
                    component=evt_data["component"],
                    summary=evt_data["summary"],
                    payload=evt_data.get("payload", {}),
                )
                trace.events.append(evt)
            return trace
        except Exception as exc:
            logger.debug("Trace load from disk failed: %s", exc)
            return None

    def _enforce_retention(self) -> None:
        """Remove oldest trace files if over _MAX_TRACE_FILES."""
        try:
            files = sorted(_TRACES_DIR.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
            while len(files) > _MAX_TRACE_FILES:
                files.pop(0).unlink(missing_ok=True)
        except Exception:
            pass

    def list_persisted_traces(self) -> List[str]:
        """Return list of trace_ids available on disk."""
        if not _TRACES_DIR.exists():
            return []
        try:
            return [f.stem for f in sorted(
                _TRACES_DIR.glob("*.jsonl"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )]
        except Exception:
            return []

    def get_persistence_status(self) -> Dict[str, Any]:
        """Return disk persistence status for doctor checks."""
        exists = _TRACES_DIR.exists()
        count = 0
        if exists:
            try:
                count = sum(1 for _ in _TRACES_DIR.glob("*.jsonl"))
            except Exception:
                pass
        return {
            "persist_enabled": self._persist,
            "traces_dir": str(_TRACES_DIR),
            "traces_dir_exists": exists,
            "persisted_trace_count": count,
            "max_files": _MAX_TRACE_FILES,
        }

    def get(self, trace_id: str) -> Optional[OrchestratorTrace]:
        return self._traces.get(trace_id)

    def get_by_request(self, request_id: str) -> Optional[OrchestratorTrace]:
        for trace in self._traces.values():
            if trace.request_id == request_id:
                return trace
        return None

    def recent(self, n: int = 10) -> List[OrchestratorTrace]:
        """Return the N most recent traces."""
        ids = self._order[-n:]
        return [self._traces[tid] for tid in reversed(ids) if tid in self._traces]

    def replay_log(self, trace_id: str) -> Optional[Dict[str, Any]]:
        """Return a structured replay log for debugging. None if trace not found."""
        trace = self._traces.get(trace_id)
        if trace is None:
            return None
        return {
            "replay_log": True,
            "trace_id": trace.trace_id,
            "request_id": trace.request_id,
            "total_elapsed_ms": trace.elapsed_ms(),
            "pipeline_steps": [
                {
                    "step": i + 1,
                    "event_type": e.event_type,
                    "component": e.component,
                    "summary": e.summary,
                    "elapsed_from_start_ms": e.timestamp_ms - trace.start_time_ms,
                }
                for i, e in enumerate(trace.events)
            ],
        }

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_traces_stored": len(self._traces),
            "max_traces": self._max,
            "recent_trace_ids": self._order[-5:],
            "persistence": self.get_persistence_status(),
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[RuntimeTraceStore] = None


def get_trace_store() -> RuntimeTraceStore:
    """Return the module-level RuntimeTraceStore singleton."""
    global _store
    if _store is None:
        _store = RuntimeTraceStore()
    return _store


def start_trace(request_id: str, trace_id: Optional[str] = None) -> OrchestratorTrace:
    """Start a new trace for a request. Called at front-door entry."""
    return get_trace_store().create_trace(request_id, trace_id=trace_id)


def get_trace(trace_id: str) -> Optional[OrchestratorTrace]:
    """Retrieve an existing trace by trace_id. Checks memory then disk."""
    store = get_trace_store()
    # Memory first
    trace = store.get(trace_id)
    if trace is not None:
        return trace
    # Fall back to disk
    return store.load_trace_from_disk(trace_id)


def persist_trace(trace_id: str) -> bool:
    """Persist a completed trace to disk. Best-effort."""
    return get_trace_store().persist_trace(trace_id)


__all__ = [
    "RuntimeTraceEvent",
    "OrchestratorTrace",
    "RuntimeTraceStore",
    "get_trace_store",
    "start_trace",
    "get_trace",
    "persist_trace",
    "EVENT_FRONT_DOOR",
    "EVENT_ROUTING",
    "EVENT_COS_GM",
    "EVENT_MANAGER_ACTIVATION",
    "EVENT_WORKER_EXECUTION",
    "EVENT_VALIDATION",
    "EVENT_NUS_FEEDBACK",
    "EVENT_BLOCKER",
    "EVENT_FINAL_RESPONSE",
    "ALL_EVENT_TYPES",
]
