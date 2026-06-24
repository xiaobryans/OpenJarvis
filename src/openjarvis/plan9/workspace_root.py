"""Resolve OpenJarvis coding workspace root for local and cloud runtimes."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional


def _has_pyproject(path: Path) -> bool:
    return (path / "pyproject.toml").is_file()


def _walk_up_for_pyproject(start: Path, *, max_levels: int = 8) -> Optional[Path]:
    cur = start.resolve()
    if cur.is_file():
        cur = cur.parent
    for _ in range(max_levels):
        if _has_pyproject(cur):
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


@lru_cache(maxsize=1)
def workspace_root() -> Path:
    """Return repo/workspace root containing pyproject.toml.

    Priority:
      1. OPENJARVIS_ROOT / JARVIS_REPO_ROOT env (cloud container sets /app)
      2. Walk up from this module (dev editable install under src/)
      3. Walk up from cwd (jarvis serve launched from repo)
    """
    for key in ("OPENJARVIS_ROOT", "JARVIS_REPO_ROOT"):
        raw = os.environ.get(key, "").strip()
        if raw:
            candidate = Path(raw).expanduser().resolve()
            if _has_pyproject(candidate):
                return candidate

    from_module = _walk_up_for_pyproject(Path(__file__).resolve())
    if from_module is not None:
        return from_module

    from_cwd = _walk_up_for_pyproject(Path.cwd())
    if from_cwd is not None:
        return from_cwd

    # Last resort — legacy layout (may be wrong in wheel-only installs).
    return Path(__file__).resolve().parent.parent.parent.parent


def workspace_allowlist_roots() -> tuple[str, ...]:
    return ("src/", "tests/", "docs/", "configs/")


def workspace_prefix_allowed(raw: str) -> bool:
    if ".." in raw or raw.startswith("/"):
        return False
    for blocked in (".env", ".git/", "id_rsa", "id_ed25519", ".ssh/", "secrets/"):
        if blocked in raw:
            return False
    allowed = workspace_allowlist_roots() + ("pyproject.toml", "README")
    return any(raw.startswith(p) for p in allowed)


def git_tracked_files(
    root: Optional[Path] = None,
    *,
    allowed_roots: Optional[tuple[str, ...]] = None,
    max_files: int = 2000,
) -> List[Dict]:
    """Return metadata for git-tracked files in allowlisted paths.

    Uses ``git ls-files`` — works in cloud containers (no local rglob needed).
    Never returns file content. Returns path, size_bytes, extension only.
    Returns empty list if git is unavailable or the repo has no tracked files.
    """
    base = root or workspace_root()
    roots = allowed_roots or workspace_allowlist_roots()

    try:
        result = subprocess.run(
            ["git", "ls-files", "--", *roots],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(base),
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    files: List[Dict] = []
    for line in result.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        full = base / rel
        entry: Dict = {"path": rel, "extension": Path(rel).suffix, "git_tracked": True}
        try:
            stat = full.stat()
            entry["size_bytes"] = stat.st_size
            entry["modified_ts"] = int(stat.st_mtime)
        except OSError:
            entry["size_bytes"] = None
            entry["modified_ts"] = None
        files.append(entry)
        if len(files) >= max_files:
            break

    return files


def git_is_available(root: Optional[Path] = None) -> bool:
    """Return True if git is installed and the workspace is a git repo."""
    base = root or workspace_root()
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5, cwd=str(base),
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def workspace_sync_summary(root: Optional[Path] = None) -> dict:
    """Return honest workspace sync status for Plan 2C parity reporting.

    Reports:
    - git_tracked_count: files enumerable via git ls-files (cloud-readable)
    - modified_count: locally modified tracked files not yet pushed
    - untracked_count: files not under git (local-only; QUEUED_MAC_ONLY class)
    - git_available: whether git ls-files is usable in this runtime

    Never returns file paths, usernames, content, or credentials.
    All counts are integers; no file names are returned here.
    """
    base = root or workspace_root()
    git_ok = git_is_available(base)

    git_tracked_count = 0
    modified_count = 0
    untracked_count = 0

    if git_ok:
        allowed = workspace_allowlist_roots()
        try:
            ls = subprocess.run(
                ["git", "ls-files", "--", *allowed],
                capture_output=True, text=True, timeout=15, cwd=str(base),
            )
            if ls.returncode == 0:
                git_tracked_count = sum(1 for l in ls.stdout.splitlines() if l.strip())
        except (OSError, subprocess.TimeoutExpired):
            pass

        try:
            st = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=10, cwd=str(base),
            )
            if st.returncode == 0:
                for line in st.stdout.splitlines():
                    if len(line) >= 2:
                        code = line[:2]
                        if "?" in code:
                            untracked_count += 1
                        elif code.strip():
                            modified_count += 1
        except (OSError, subprocess.TimeoutExpired):
            pass

    return {
        "git_available": git_ok,
        "git_tracked_count": git_tracked_count,
        "modified_count": modified_count,
        "untracked_count": untracked_count,
        "cloud_indexable": git_tracked_count if git_ok else 0,
        "local_only_class": "QUEUED_MAC_ONLY",
        "permanent_exception": (
            "Untracked/Mac-only files are a permanent QUEUED_MAC_ONLY exception "
            "per Plan 9 acceptance — not expected to be cloud-synced."
        ),
    }


def workspace_index_summary(root: Optional[Path] = None) -> dict:
    """Metadata-only index counts for workspace status surfaces."""
    base = root or workspace_root()
    counts: dict[str, int] = {}
    total = 0
    for prefix in workspace_allowlist_roots():
        d = base / prefix.rstrip("/")
        if not d.is_dir():
            counts[prefix] = 0
            continue
        n = sum(1 for p in d.rglob("*") if p.is_file())
        counts[prefix] = n
        total += n
    for name in ("pyproject.toml", "README.md"):
        if (base / name).is_file():
            total += 1
    return {
        "workspace_root": str(base),
        "indexed_file_count": total,
        "prefix_counts": counts,
        "pyproject_present": (base / "pyproject.toml").is_file(),
    }
