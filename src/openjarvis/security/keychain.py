"""Jarvis Secrets Manager — macOS Keychain + env-file fallback.

Provides a unified secrets access layer:
  1. Primary: macOS Keychain (via `security` CLI, always available on macOS)
  2. Fallback: ~/.openjarvis/cloud-keys.env (existing env file — never deleted)

Hard rules:
  - NEVER print secret values in any output, log, or exception message
  - NEVER commit secrets
  - Redact all display/doctor output to show only key name + PRESENT/MISSING
  - Migration from env file to keychain is opt-in, never automatic

Keychain service name: "openjarvis"
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

_SERVICE = "openjarvis"
_ENV_FILE = Path.home() / ".openjarvis" / "cloud-keys.env"

# Keys that Jarvis manages
JARVIS_KNOWN_KEYS: List[str] = [
    "JARVIS_SLACK_BOT_TOKEN",
    "JARVIS_SLACK_CHANNEL_ID",
    "JARVIS_SLACK_TEST_CHANNEL_ID",
    "JARVIS_TELEGRAM_BOT_TOKEN",
    "JARVIS_TELEGRAM_BOT_USERNAME",
    "JARVIS_TELEGRAM_CHAT_ID",
    "TAVILY_API_KEY",
    "JARVIS_PROJECT_OMNIX_REPO_PATH",
    "OPENCLAW_WORKSPACE_PATH",
    "OPENCLAW_HANDOFF_PATH",
    "PICOVOICE_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "GITHUB_TOKEN",
    "DEEPGRAM_API_KEY",
    "JARVIS_WAKEWORD_ACCESS_KEY",
]


# ---------------------------------------------------------------------------
# Backend availability
# ---------------------------------------------------------------------------


def is_keychain_available() -> bool:
    """True if macOS Keychain (`security` CLI) is accessible."""
    return platform.system() == "Darwin" and shutil.which("security") is not None


def get_backend_status() -> Dict[str, Any]:
    """Report secrets backend availability — values redacted."""
    keychain_ok = is_keychain_available()
    env_ok = _ENV_FILE.exists()
    return {
        "keychain_available": keychain_ok,
        "env_file_exists": env_ok,
        "env_file_path": str(_ENV_FILE),
        "active_backend": "keychain" if keychain_ok else "env_file",
        "note": "Values never displayed. Key names only.",
    }


# ---------------------------------------------------------------------------
# Keychain read/write (macOS `security` command)
# ---------------------------------------------------------------------------


def _keychain_get(key: str) -> Optional[str]:
    """Retrieve a secret from macOS Keychain. Returns None if not found."""
    if not is_keychain_available():
        return None
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", _SERVICE, "-a", key, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
        return None
    except Exception:
        return None


def _keychain_set(key: str, value: str) -> bool:
    """Store a secret in macOS Keychain. Returns True on success."""
    if not is_keychain_available():
        return False
    try:
        # Delete existing entry first (ignore error if not found)
        subprocess.run(
            ["security", "delete-generic-password", "-s", _SERVICE, "-a", key],
            capture_output=True,
            timeout=5,
        )
        result = subprocess.run(
            [
                "security", "add-generic-password",
                "-s", _SERVICE, "-a", key, "-w", value,
            ],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def _keychain_delete(key: str) -> bool:
    """Delete a secret from macOS Keychain. Returns True on success."""
    if not is_keychain_available():
        return False
    try:
        result = subprocess.run(
            ["security", "delete-generic-password", "-s", _SERVICE, "-a", key],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Env file read
# ---------------------------------------------------------------------------


def _env_file_load() -> Dict[str, str]:
    """Load key→value pairs from env file. Returns empty dict if missing."""
    data: Dict[str, str] = {}
    if not _ENV_FILE.exists():
        return data
    try:
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    except Exception:
        pass
    return data


# ---------------------------------------------------------------------------
# Unified get_secret — keychain first, env fallback, os.environ last
# ---------------------------------------------------------------------------


def get_secret(key: str) -> Optional[str]:
    """Retrieve a secret. Never log or display the value."""
    # 1. os.environ (already loaded)
    val = os.environ.get(key)
    if val:
        return val
    # 2. Keychain
    if is_keychain_available():
        val = _keychain_get(key)
        if val:
            return val
    # 3. env file
    data = _env_file_load()
    return data.get(key) or None


def secret_present(key: str) -> bool:
    """Check presence without exposing value."""
    return bool(get_secret(key))


# ---------------------------------------------------------------------------
# Migration: env file → Keychain (opt-in, never automatic)
# ---------------------------------------------------------------------------


def migrate_env_to_keychain(keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Migrate env file secrets to macOS Keychain.

    Only runs if keychain is available.
    Returns per-key MIGRATED/SKIPPED/FAILED — never the value.
    """
    if not is_keychain_available():
        return {
            "ok": False,
            "blocker": "macOS Keychain not available on this platform",
            "results": {},
        }
    env_data = _env_file_load()
    target_keys = keys or JARVIS_KNOWN_KEYS
    results: Dict[str, str] = {}
    for k in target_keys:
        v = env_data.get(k)
        if not v:
            results[k] = "SKIPPED_NOT_IN_ENV"
            continue
        ok = _keychain_set(k, v)
        results[k] = "MIGRATED" if ok else "FAILED"
    migrated = sum(1 for s in results.values() if s == "MIGRATED")
    failed = sum(1 for s in results.values() if s == "FAILED")
    return {
        "ok": failed == 0,
        "migrated": migrated,
        "failed": failed,
        "results": results,
        "note": "Values not shown. Check presence with secret_present().",
    }


# ---------------------------------------------------------------------------
# Doctor/readiness presence report — values always redacted
# ---------------------------------------------------------------------------


def get_secrets_presence_report(keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Report key presence for doctor/readiness. All values redacted."""
    target = keys or JARVIS_KNOWN_KEYS
    presence: Dict[str, str] = {}
    for k in target:
        presence[k] = "PRESENT" if secret_present(k) else "MISSING"
    missing = [k for k, v in presence.items() if v == "MISSING"]
    backend = get_backend_status()
    return {
        "backend": backend["active_backend"],
        "keychain_available": backend["keychain_available"],
        "env_file_exists": backend["env_file_exists"],
        "keys_checked": len(target),
        "keys_present": len(target) - len(missing),
        "keys_missing": len(missing),
        "missing_keys": missing,
        "presence": presence,
        "values_redacted": True,
    }


# ---------------------------------------------------------------------------
# Redaction helper — ensure no secret value leaks into logs/output
# ---------------------------------------------------------------------------


def redact_dict(data: Dict[str, Any], sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return a copy of data with all sensitive values replaced by [REDACTED]."""
    redact = set(sensitive_keys or JARVIS_KNOWN_KEYS)
    redact_lower = {k.lower() for k in redact}
    redact_lower.update({"token", "key", "secret", "password", "credential"})

    def _redact_value(k: str, v: Any) -> Any:
        k_lower = k.lower()
        if any(r in k_lower for r in redact_lower):
            return "[REDACTED]"
        if isinstance(v, dict):
            return {ik: _redact_value(ik, iv) for ik, iv in v.items()}
        return v

    return {k: _redact_value(k, v) for k, v in data.items()}


def assert_no_secret_leak(
    output: Any,
    keys: Optional[List[str]] = None,
) -> bool:
    """Assert that no known secret value appears in output string.

    Returns True if safe, raises AssertionError with key name (not value) if leaking.
    """
    target = keys or JARVIS_KNOWN_KEYS
    output_str = json.dumps(output) if not isinstance(output, str) else output
    for k in target:
        v = get_secret(k)
        if v and len(v) > 3 and v in output_str:
            raise AssertionError(
                f"Secret leak detected: key '{k}' value found in output. "
                "NEVER print secret values."
            )
    return True


__all__ = [
    "is_keychain_available",
    "get_backend_status",
    "get_secret",
    "secret_present",
    "migrate_env_to_keychain",
    "get_secrets_presence_report",
    "redact_dict",
    "assert_no_secret_leak",
    "JARVIS_KNOWN_KEYS",
]
