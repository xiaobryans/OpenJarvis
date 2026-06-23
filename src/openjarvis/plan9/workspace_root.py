"""Resolve OpenJarvis coding workspace root for local and cloud runtimes."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional


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
