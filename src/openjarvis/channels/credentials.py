"""Shared credential loader for Jarvis ops modules.

Loads credentials from approved sources in priority order:
  1. os.environ (already-set shell vars win)
  2. ~/.jarvis/cloud-keys.env  (sprint-configured Jarvis keys)
  3. ~/.openjarvis/cloud-keys.env  (legacy openjarvis config with JARVIS_ prefixes)

Alias mapping:
  JARVIS_SLACK_BOT_TOKEN      → SLACK_BOT_TOKEN
  OPENCLAW_SLACK_BOT_TOKEN    → SLACK_BOT_TOKEN
  JARVIS_TELEGRAM_BOT_TOKEN   → TELEGRAM_BOT_TOKEN
  JARVIS_TELEGRAM_CHAT_ID     → TELEGRAM_BRYAN_CHAT_ID
  JARVIS_TELEGRAM_BOT_USERNAME → (informational, not mapped)

Never prints secret values. Never logs secret values. Never stores secrets
in memory, Obsidian, Slack, Telegram, traces, or logs.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Credential file paths (in priority order)
# ---------------------------------------------------------------------------

_CLOUD_KEYS_PRIMARY = Path.home() / ".jarvis" / "cloud-keys.env"
_CLOUD_KEYS_LEGACY = Path.home() / ".openjarvis" / "cloud-keys.env"

# ---------------------------------------------------------------------------
# Alias map: env-file key → canonical key used by ops modules
# ---------------------------------------------------------------------------

_ALIAS_MAP: Dict[str, str] = {
    "JARVIS_SLACK_BOT_TOKEN": "SLACK_BOT_TOKEN",
    "OPENCLAW_SLACK_BOT_TOKEN": "SLACK_BOT_TOKEN",
    "JARVIS_TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
    "JARVIS_TELEGRAM_CHAT_ID": "TELEGRAM_BRYAN_CHAT_ID",
}


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file and return key→value dict. Never logs values."""
    result: Dict[str, str] = {}
    if not path.exists():
        return result
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    except OSError:
        logger.debug("credentials: could not read %s", path)
    return result


def load_credential(key: str) -> Tuple[str, str]:
    """Return (value, source) for *key*, checking alias map and all credential sources.

    Returns ("", "MISSING") when the credential is not found anywhere.
    Never returns the secret value in log messages.
    """
    # 1. Check os.environ (already-loaded shell env wins)
    val = os.environ.get(key, "")
    if val:
        return val, "os.environ"

    # 2. Check primary cloud-keys file
    primary = _parse_env_file(_CLOUD_KEYS_PRIMARY)
    val = primary.get(key, "")
    if val:
        return val, str(_CLOUD_KEYS_PRIMARY)

    # 3. Check legacy cloud-keys file for exact key
    legacy = _parse_env_file(_CLOUD_KEYS_LEGACY)
    val = legacy.get(key, "")
    if val:
        return val, str(_CLOUD_KEYS_LEGACY)

    # 4. Check aliases in primary then legacy
    for alias, canonical in _ALIAS_MAP.items():
        if canonical == key:
            val = primary.get(alias, "") or legacy.get(alias, "")
            if val:
                src = str(_CLOUD_KEYS_PRIMARY if alias in primary and primary[alias] else _CLOUD_KEYS_LEGACY)
                return val, f"alias:{alias}->{key} from {src}"

    # 5. Check OPENCLAW_* pattern in .env in cwd
    dot_env = Path(".env")
    if dot_env.exists():
        dot = _parse_env_file(dot_env)
        val = dot.get(key, "")
        if val:
            return val, ".env"
        for alias, canonical in _ALIAS_MAP.items():
            if canonical == key:
                val = dot.get(alias, "")
                if val:
                    return val, f"alias:{alias}->{key} from .env"

    return "", "MISSING"


def get_slack_bot_token() -> Tuple[str, str]:
    """Return (SLACK_BOT_TOKEN, source). Never logs the value."""
    return load_credential("SLACK_BOT_TOKEN")


def get_telegram_bot_token() -> Tuple[str, str]:
    """Return (TELEGRAM_BOT_TOKEN, source). Never logs the value."""
    return load_credential("TELEGRAM_BOT_TOKEN")


def get_telegram_bryan_chat_id() -> Tuple[str, str]:
    """Return (TELEGRAM_BRYAN_CHAT_ID, source). Never logs the value."""
    return load_credential("TELEGRAM_BRYAN_CHAT_ID")


def probe_credential(key: str) -> Dict[str, str]:
    """Return a safe status dict for a credential — length only, never the value."""
    val, source = load_credential(key)
    return {
        "key": key,
        "status": "SET" if val else "MISSING",
        "length": str(len(val)) if val else "0",
        "source": source if val else "not_found",
    }


def probe_all_ops_credentials() -> Dict[str, Dict[str, str]]:
    """Return safe status probes for all ops-module credentials."""
    keys = [
        "SLACK_BOT_TOKEN",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_BRYAN_CHAT_ID",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "GITHUB_TOKEN",
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
    ]
    return {k: probe_credential(k) for k in keys}
