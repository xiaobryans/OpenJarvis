"""NUS 1B — Cross-session learning persistence.

Provides a safe local persistence layer (JSONL) for learning records.
All writes are to a controlled safe directory path only.

Hard safety constraints:
  - Rejects unsafe / secret paths (.env, .ssh, .aws, .git, credentials, etc.)
  - Never stores raw secret-looking values
  - Redacts suspicious values before persistence
  - No external DB, no cloud, no secrets
  - No auto-commit, no deploy, no external sends
  - Tests must use temp dirs

Default store location: ~/.openjarvis/nus/
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

NUS1B_STORE_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

_BLOCKED_PATH_PATTERNS = re.compile(
    r"(\.env|\.env\.local|credentials|\.ssh|\.aws|\.git|secrets|api_key|api_secret"
    r"|password|passwd|token|private_key|id_rsa|id_ed25519|pgpass|\.netrc"
    r"|keychain|vault|\.htpasswd)",
    re.IGNORECASE,
)

_DEFAULT_STORE_DIR = Path.home() / ".openjarvis" / "nus"


def _is_safe_path(path: Path) -> bool:
    """Return True if the path is safe for NUS persistence writes."""
    path_str = str(path)
    if _BLOCKED_PATH_PATTERNS.search(path_str):
        return False
    # Must be within the user's home dir or /tmp for tests
    try:
        home = Path.home()
        resolved = path.resolve()
        is_home_child = str(resolved).startswith(str(home))
        is_tmp = (
            str(resolved).startswith("/tmp")
            or str(resolved).startswith("/var/folders")
            or str(resolved).startswith("/private/var/folders")
            or str(resolved).startswith("/private/tmp")
        )
        return is_home_child or is_tmp
    except Exception:
        return False


def _assert_safe_path(path: Path) -> None:
    if not _is_safe_path(path):
        raise ValueError(
            f"NUS persistence path rejected (unsafe/secret path): {path}. "
            "Use ~/.openjarvis/nus/ or a temp dir for tests."
        )


# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

_SECRET_KEY_PATTERN = re.compile(
    r"(^api[_\-]?key$|^secret$|^password$|^passwd$|^token$|^auth$|^auth_token$"
    r"|^credential$|^credentials$|^private[_\-]?key$|^access[_\-]?key$|^bearer$"
    r"|^secret[_\-]key$|^api[_\-]secret$|^client[_\-]secret$)",
    re.IGNORECASE,
)

_SECRET_VALUE_PATTERN = re.compile(
    r"^(sk[-_]|pk[-_]|Bearer |eyJ|AKIA|[A-Za-z0-9/+]{40,}={0,2})$"
)


def redact_suspicious(obj: Any, depth: int = 0) -> Any:
    """Recursively redact suspicious secret-looking values from a dict/list."""
    if depth > 8:
        return "[TRUNCATED]"
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEY_PATTERN.search(k):
                result[k] = "[REDACTED]"
            elif isinstance(v, str) and _SECRET_VALUE_PATTERN.match(v.strip()):
                result[k] = "[REDACTED]"
            else:
                result[k] = redact_suspicious(v, depth + 1)
        return result
    if isinstance(obj, list):
        return [redact_suspicious(i, depth + 1) for i in obj]
    if isinstance(obj, str) and _SECRET_VALUE_PATTERN.match(obj.strip()):
        return "[REDACTED]"
    return obj


# ---------------------------------------------------------------------------
# PersistedRecord — envelope for any JSONL record
# ---------------------------------------------------------------------------


@dataclass
class PersistedRecord:
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    record_type: str = ""
    created_at: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "record_type": self.record_type,
            "created_at": self.created_at,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PersistedRecord":
        return cls(
            record_id=d.get("record_id", uuid.uuid4().hex[:16]),
            record_type=d.get("record_type", ""),
            created_at=d.get("created_at", time.time()),
            payload=d.get("payload", {}),
        )


# ---------------------------------------------------------------------------
# LearningStore
# ---------------------------------------------------------------------------


class LearningStore:
    """Safe cross-session persistence for NUS learning records.

    Stores records as JSONL in ~/.openjarvis/nus/ (or a provided safe dir).
    Rejects unsafe/secret paths. Redacts suspicious values before writes.
    """

    OUTCOMES_FILE = "task_outcomes.jsonl"
    SIGNALS_FILE = "learning_signals.jsonl"
    PATTERNS_FILE = "failure_patterns.jsonl"
    SNAPSHOTS_FILE = "learning_snapshots.jsonl"
    RECOMMENDATIONS_FILE = "recommendations.jsonl"

    def __init__(self, store_dir: Optional[Path] = None) -> None:
        self._dir = Path(store_dir) if store_dir else _DEFAULT_STORE_DIR
        _assert_safe_path(self._dir)
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.warning("LearningStore: could not create dir %s: %s", self._dir, exc)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                      #
    # ------------------------------------------------------------------ #

    def _path(self, filename: str) -> Path:
        return self._dir / filename

    def _append_record(self, filename: str, record_type: str, payload: Dict[str, Any]) -> str:
        """Append a redacted PersistedRecord to a JSONL file. Returns record_id."""
        rec = PersistedRecord(
            record_type=record_type,
            payload=redact_suspicious(payload),
        )
        try:
            fpath = self._path(filename)
            with fpath.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec.to_dict()) + "\n")
        except Exception as exc:
            logger.warning("LearningStore: write failed for %s: %s", filename, exc)
        return rec.record_id

    def _load_records(self, filename: str, limit: int = 500) -> List[PersistedRecord]:
        """Load up to `limit` most-recent records from a JSONL file."""
        fpath = self._path(filename)
        if not fpath.exists():
            return []
        records: List[PersistedRecord] = []
        try:
            lines = fpath.read_text(encoding="utf-8").splitlines()
            for line in lines[-limit:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(PersistedRecord.from_dict(json.loads(line)))
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("LearningStore: read failed for %s: %s", filename, exc)
        return records

    # ------------------------------------------------------------------ #
    # Public API                                                            #
    # ------------------------------------------------------------------ #

    def append_outcome(self, outcome_dict: Dict[str, Any]) -> str:
        """Persist a task outcome record."""
        return self._append_record(self.OUTCOMES_FILE, "task_outcome", outcome_dict)

    def append_signal(self, signal_dict: Dict[str, Any]) -> str:
        """Persist a learning signal."""
        return self._append_record(self.SIGNALS_FILE, "learning_signal", signal_dict)

    def append_failure_pattern(self, pattern_dict: Dict[str, Any]) -> str:
        """Persist a failure pattern record."""
        return self._append_record(self.PATTERNS_FILE, "failure_pattern", pattern_dict)

    def save_snapshot(self, snapshot_dict: Dict[str, Any]) -> str:
        """Persist a learning snapshot."""
        return self._append_record(self.SNAPSHOTS_FILE, "learning_snapshot", snapshot_dict)

    def append_recommendation(self, rec_dict: Dict[str, Any]) -> str:
        """Persist a recommendation record."""
        return self._append_record(self.RECOMMENDATIONS_FILE, "recommendation", rec_dict)

    def load_recent_outcomes(self, limit: int = 200) -> List[Dict[str, Any]]:
        return [r.payload for r in self._load_records(self.OUTCOMES_FILE, limit=limit)]

    def load_recent_signals(self, limit: int = 200) -> List[Dict[str, Any]]:
        return [r.payload for r in self._load_records(self.SIGNALS_FILE, limit=limit)]

    def load_recent_patterns(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [r.payload for r in self._load_records(self.PATTERNS_FILE, limit=limit)]

    def load_recent_snapshots(self, limit: int = 10) -> List[Dict[str, Any]]:
        return [r.payload for r in self._load_records(self.SNAPSHOTS_FILE, limit=limit)]

    def load_recent_recommendations(self, limit: int = 100) -> List[Dict[str, Any]]:
        return [r.payload for r in self._load_records(self.RECOMMENDATIONS_FILE, limit=limit)]

    def summarize(self) -> Dict[str, Any]:
        """Return a summary of persisted record counts (no payloads)."""
        summary: Dict[str, int] = {}
        for label, fname in [
            ("outcomes", self.OUTCOMES_FILE),
            ("signals", self.SIGNALS_FILE),
            ("failure_patterns", self.PATTERNS_FILE),
            ("snapshots", self.SNAPSHOTS_FILE),
            ("recommendations", self.RECOMMENDATIONS_FILE),
        ]:
            fpath = self._path(fname)
            if fpath.exists():
                try:
                    lines = fpath.read_text(encoding="utf-8").splitlines()
                    summary[label] = sum(1 for l in lines if l.strip())
                except Exception:
                    summary[label] = -1
            else:
                summary[label] = 0
        return {
            "store_dir": str(self._dir),
            "store_version": NUS1B_STORE_VERSION,
            "record_counts": summary,
        }

    @property
    def store_dir(self) -> Path:
        return self._dir
