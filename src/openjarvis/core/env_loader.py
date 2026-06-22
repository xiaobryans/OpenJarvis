"""Canonical local env/secrets loader for OpenJarvis.

Loads provider keys from project-root `.env`, `.env.local`, and
`~/.openjarvis/cloud-keys.env` into ``os.environ`` without overriding keys
already set in the process environment.

Never logs, prints, or returns secret values.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_LOADED = False
_KEY_SOURCES: Dict[str, str] = {}

# Plan 9K provider keys and accepted aliases (first name is canonical report name)
PROVIDER_KEY_ALIASES: Dict[str, Tuple[str, ...]] = {
    "OPENROUTER_API_KEY": ("OPENROUTER_API_KEY",),
    "AIMLAPI_API_KEY": ("AIMLAPI_API_KEY", "AIMLAPI_KEY"),
    "ZAI_API_KEY": ("ZAI_API_KEY", "GLM_API_KEY"),
    "KIMI_API_KEY": ("KIMI_API_KEY", "MOONSHOT_API_KEY"),
}

_CLOUD_KEYS_FILE = Path.home() / ".openjarvis" / "cloud-keys.env"


def find_project_root(start: Optional[Path] = None) -> Path:
    """Walk upward from *start* to locate the repo root (contains pyproject.toml)."""
    cur = (start or Path(__file__)).resolve()
    if cur.is_file():
        cur = cur.parent
    for parent in [cur, *cur.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    # Fallback: src/openjarvis/core/env_loader.py → four levels up
    return Path(__file__).resolve().parent.parent.parent.parent


def _strip_env_value(raw: str) -> str:
    val = raw.strip()
    if not val:
        return ""
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def _parse_env_file(path: Path, source_label: str) -> int:
    """Parse KEY=VALUE lines into os.environ (missing keys only). Returns count set."""
    if not path.is_file():
        return 0
    count = 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = _strip_env_value(val)
        if key not in os.environ and value:
            os.environ[key] = value
            _KEY_SOURCES[key] = source_label
            count += 1
        elif key in os.environ and key not in _KEY_SOURCES:
            _KEY_SOURCES[key] = "process_env"
    return count


def load_local_env(*, project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Load local env files. Idempotent. Never overrides existing process env.

    Load order (first wins for each key — later files only fill gaps):
      1. process environment (already present — never touched)
      2. project ``.env``
      3. project ``.env.local``
      4. ``~/.openjarvis/cloud-keys.env``

    Returns a safe summary dict (no secret values).
    """
    global _LOADED
    root = project_root or find_project_root()
    files_loaded: List[str] = []
    keys_set = 0

    for rel, label in (
        (".env", "dotenv"),
        (".env.local", "dotenv_local"),
    ):
        p = root / rel
        n = _parse_env_file(p, label)
        if n:
            files_loaded.append(str(p))
            keys_set += n

    n = _parse_env_file(_CLOUD_KEYS_FILE, "cloud_keys_env")
    if n:
        files_loaded.append(str(_CLOUD_KEYS_FILE))
        keys_set += n

    _LOADED = True
    return {
        "project_root": str(root),
        "files_loaded": files_loaded,
        "keys_set_this_call": keys_set,
        "already_loaded": _LOADED,
    }


def ensure_local_env_loaded(*, project_root: Optional[Path] = None) -> None:
    """Load local env files once per process if not already done."""
    if not _LOADED:
        load_local_env(project_root=project_root)


def _resolve_key(names: Tuple[str, ...]) -> Tuple[bool, str, str]:
    """Return (present, canonical_name, source)."""
    for name in names:
        if os.environ.get(name, "").strip():
            src = _KEY_SOURCES.get(name, "process_env")
            return True, name, src
    return False, names[0], "not_found"


def provider_key_status_table() -> Dict[str, Dict[str, Any]]:
    """Safe provider-key presence report for Plan 9K providers."""
    ensure_local_env_loaded()
    report: Dict[str, Dict[str, Any]] = {}
    for canonical, aliases in PROVIDER_KEY_ALIASES.items():
        present, resolved_name, source = _resolve_key(aliases)
        entry: Dict[str, Any] = {
            "env_var": resolved_name,
            "status": "PRESENT" if present else "MISSING",
            "source": source if present else "not_found",
            "alternate_env_vars": list(aliases[1:]),
        }
        report[canonical] = entry
    return report


def all_tracked_keys_present() -> bool:
    """True if every canonical provider key group has at least one alias set."""
    return all(v["status"] == "PRESENT" for v in provider_key_status_table().values())


__all__ = [
    "PROVIDER_KEY_ALIASES",
    "all_tracked_keys_present",
    "ensure_local_env_loaded",
    "find_project_root",
    "load_local_env",
    "provider_key_status_table",
]
