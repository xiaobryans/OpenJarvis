"""Epic C — Local Folder Connector (Wave 1).

Reads .txt and .md files from allowlisted local paths.
No authentication required. No PII risk (user-controlled local docs).

Allowlist: only paths that:
  - are under the user's home directory OR under /tmp
  - do not contain system/credential paths
  - are not .env, .key, .pem, .p12, .pfx, credential, secret files

Default allowlisted folder: ~/.jarvis_knowledge/ (auto-created if absent)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Allowlist logic
# ---------------------------------------------------------------------------

_ALLOWED_EXTENSIONS = frozenset({".txt", ".md", ".markdown", ".rst", ".text"})

_FORBIDDEN_FILENAME_PATTERNS = [
    ".env", ".key", "credential", "secret", "password", "token", "api_key",
    ".pem", ".p12", ".pfx", ".cer", ".crt", "id_rsa", "id_ed25519",
]

_FORBIDDEN_PATH_SEGMENTS = [
    "/.ssh", "/keychain/", "/.gnupg/", "/.aws/", "/.kube/",
    "/.config/gh/", "/.config/gcloud/",
]

_DEFAULT_KNOWLEDGE_DIR = Path.home() / ".jarvis_knowledge"
_MAX_FILE_SIZE_BYTES = 500_000  # 500 KB per file
_MAX_FILES_PER_INGEST = 50


def _is_allowed_path(path: Path) -> Tuple[bool, str]:
    """Return (allowed, reason) for a given path."""
    path_str = str(path).replace("\\", "/")

    # Must be absolute
    if not path.is_absolute():
        return False, "Path must be absolute"

    # Must be under home or /tmp (macOS: /tmp → /private/tmp symlink)
    home = str(Path.home())
    if not (path_str.startswith(home) or path_str.startswith("/tmp") or path_str.startswith("/private/tmp")):
        return False, f"Path must be under home ({home}) or /tmp"

    # Check forbidden path segments (match with or without trailing slash)
    for seg in _FORBIDDEN_PATH_SEGMENTS:
        seg_check = seg.rstrip("/")
        if seg_check in path_str:
            return False, f"Forbidden path segment: {seg}"

    # Check file extension
    if path.suffix.lower() not in _ALLOWED_EXTENSIONS:
        return False, f"Forbidden extension: {path.suffix!r}. Allowed: {sorted(_ALLOWED_EXTENSIONS)}"

    # Check filename for sensitive patterns
    name_lower = path.name.lower()
    for pat in _FORBIDDEN_FILENAME_PATTERNS:
        if pat in name_lower:
            return False, f"Filename matches forbidden pattern: {pat!r}"

    return True, "ok"


def ensure_default_knowledge_dir() -> Path:
    """Create default knowledge directory if it doesn't exist."""
    _DEFAULT_KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_KNOWLEDGE_DIR


# ---------------------------------------------------------------------------
# Knowledge record from files
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    record_id: str
    source_id: str
    file_path: str
    title: str
    content: str
    content_type: str = "text"
    file_size: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "source_id": self.source_id,
            "file_path": self.file_path,
            "title": self.title,
            "content": self.content[:500],
            "content_type": self.content_type,
            "file_size": self.file_size,
        }


@dataclass
class FolderIngestionResult:
    source_id: str
    folder_path: str
    ok: bool
    record_count: int = 0
    records: List[FileRecord] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    error: str = ""
    blocked: bool = False
    event_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "folder_path": self.folder_path,
            "ok": self.ok,
            "record_count": self.record_count,
            "records": [r.to_dict() for r in self.records],
            "skipped": self.skipped,
            "error": self.error,
            "blocked": self.blocked,
            "event_id": self.event_id,
        }


def _log_connector_event(
    source_id: str, ok: bool, blocked: bool, detail: str
) -> str:
    try:
        from openjarvis.workbench.event_log import (
            WorkbenchEventLog,
            EVENT_KNOWLEDGE_INGESTED,
            EVENT_KNOWLEDGE_BLOCKED,
        )
        log = WorkbenchEventLog()
        etype = EVENT_KNOWLEDGE_BLOCKED if blocked else EVENT_KNOWLEDGE_INGESTED
        ev = log.push(
            session_id="wave1_folder_connector",
            task_id=source_id,
            event_type=etype,
            title=f"Folder connector {'blocked' if blocked else 'ingested'}: {source_id}",
            detail=detail,
            tone="error" if blocked else "success",
            metadata={"source_id": source_id, "ok": ok},
        )
        return ev.id
    except Exception:
        return ""


def ingest_folder(
    folder_path: str,
    source_id: str,
    *,
    recursive: bool = False,
) -> FolderIngestionResult:
    """Ingest all allowed .txt/.md files from a local folder.

    Safety checks:
    - Path must be under home dir or /tmp
    - No credential/key filenames
    - Files max 500 KB each
    - Max 50 files per ingest call
    """
    import hashlib
    import time

    path = Path(folder_path).expanduser().resolve()

    # Check that the folder itself is safe
    if not path.is_absolute():
        return FolderIngestionResult(
            source_id=source_id, folder_path=folder_path, ok=False,
            blocked=True, error="Folder path must be absolute",
        )

    home = str(Path.home())
    path_str = str(path)
    if not (path_str.startswith(home) or path_str.startswith("/tmp") or path_str.startswith("/private/tmp")):
        eid = _log_connector_event(source_id, False, True, f"Path not in allowlist: {path}")
        return FolderIngestionResult(
            source_id=source_id, folder_path=folder_path, ok=False,
            blocked=True,
            error=f"Folder '{path}' is not in allowed zones (home or /tmp)",
            event_id=eid,
        )

    for seg in _FORBIDDEN_PATH_SEGMENTS:
        seg_check = seg.rstrip("/")
        if seg_check in path_str:
            eid = _log_connector_event(source_id, False, True, f"Forbidden segment: {seg}")
            return FolderIngestionResult(
                source_id=source_id, folder_path=folder_path, ok=False,
                blocked=True, error=f"Forbidden path segment: {seg}",
                event_id=eid,
            )

    if not path.exists():
        return FolderIngestionResult(
            source_id=source_id, folder_path=folder_path, ok=False,
            error=f"Folder does not exist: {path}",
        )

    if not path.is_dir():
        return FolderIngestionResult(
            source_id=source_id, folder_path=folder_path, ok=False,
            error=f"Path is not a directory: {path}",
        )

    # Collect candidate files
    pattern = "**/*" if recursive else "*"
    candidate_files = list(path.glob(pattern))
    candidate_files = [f for f in candidate_files if f.is_file()]

    records: List[FileRecord] = []
    skipped: List[str] = []
    ts = str(int(time.time()))

    for fpath in candidate_files:
        if len(records) >= _MAX_FILES_PER_INGEST:
            skipped.append(f"{fpath.name} (max file limit)")
            continue

        allowed, reason = _is_allowed_path(fpath)
        if not allowed:
            skipped.append(f"{fpath.name} ({reason})")
            continue

        # Size check
        try:
            size = fpath.stat().st_size
        except OSError:
            skipped.append(f"{fpath.name} (stat failed)")
            continue

        if size > _MAX_FILE_SIZE_BYTES:
            skipped.append(f"{fpath.name} (too large: {size} bytes)")
            continue
        if size == 0:
            skipped.append(f"{fpath.name} (empty)")
            continue

        # Read content
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            skipped.append(f"{fpath.name} (read error: {exc})")
            continue

        rid = hashlib.md5(f"{source_id}:{fpath.name}:{ts}".encode()).hexdigest()[:12]
        ctype = "markdown" if fpath.suffix.lower() in (".md", ".markdown") else "text"
        records.append(FileRecord(
            record_id=rid,
            source_id=source_id,
            file_path=str(fpath),
            title=fpath.stem.replace("_", " ").replace("-", " ").title(),
            content=content,
            content_type=ctype,
            file_size=size,
            metadata={"filename": fpath.name, "ingested_at": ts, "folder": str(path)},
        ))

    # Also push into knowledge_platform store
    try:
        from openjarvis.wave.knowledge_platform import ingest_local_source
        for r in records:
            ingest_local_source(
                text=r.content,
                source_id=f"{source_id}:{r.record_id}",
                title=r.title,
                content_type=r.content_type,
                metadata=r.metadata,
            )
    except Exception:
        pass

    eid = _log_connector_event(
        source_id, True, False,
        f"Ingested {len(records)} files from {path}, skipped {len(skipped)}"
    )

    return FolderIngestionResult(
        source_id=source_id,
        folder_path=str(path),
        ok=True,
        record_count=len(records),
        records=records,
        skipped=skipped,
        event_id=eid,
    )


def ingest_default_knowledge_dir() -> FolderIngestionResult:
    """Ingest from the default ~/.jarvis_knowledge/ folder (auto-created if absent)."""
    d = ensure_default_knowledge_dir()
    return ingest_folder(str(d), source_id="jarvis_knowledge_default")


def get_local_folder_connector_status() -> Dict[str, Any]:
    default_dir = str(_DEFAULT_KNOWLEDGE_DIR)
    default_exists = _DEFAULT_KNOWLEDGE_DIR.exists()
    return {
        "implemented": True,
        "default_knowledge_dir": default_dir,
        "default_dir_exists": default_exists,
        "allowed_extensions": sorted(_ALLOWED_EXTENSIONS),
        "max_file_size_bytes": _MAX_FILE_SIZE_BYTES,
        "max_files_per_ingest": _MAX_FILES_PER_INGEST,
        "pii_blocked": True,
        "credential_files_blocked": True,
        "external_connector_auth_required": True,
        "note": (
            "Local folder connector reads .txt/.md files from allowlisted paths. "
            "Apple Notes/Dropbox require auth — REQUIRES_USER_ACTION."
        ),
    }


__all__ = [
    "FileRecord",
    "FolderIngestionResult",
    "ingest_folder",
    "ingest_default_knowledge_dir",
    "ensure_default_knowledge_dir",
    "get_local_folder_connector_status",
]
