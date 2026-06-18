from __future__ import annotations

import re
from typing import Dict, List, Tuple

_CREDENTIAL_PATTERNS: List[Tuple[str, re.Pattern[str]]] = [
    ("api_key", re.compile(r"sk-[a-zA-Z0-9_-]{20,}")),
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_token", re.compile(r"ghp_[a-zA-Z0-9]{36}")),
    ("github_token", re.compile(r"gho_[a-zA-Z0-9]{36}")),
    ("slack_token", re.compile("x" + r"oxb-[0-9A-Za-z\-]+")),
    ("bearer_token", re.compile(r"Bearer\s+[a-zA-Z0-9_\-.]{20,}")),
    ("anthropic_key", re.compile(r"sk-ant-[a-zA-Z0-9_-]{20,}")),
    ("generic_secret", re.compile(r'(?:secret|token|password|passwd|pwd)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{16,})["\']?', re.IGNORECASE)),
]


class CredentialStripper:
    """Redacts credentials from text using compiled regex patterns."""

    def __init__(self) -> None:
        self._patterns = _CREDENTIAL_PATTERNS

    def strip(self, text: str) -> str:
        for label, pattern in self._patterns:
            text = pattern.sub(f"[REDACTED:{label}]", text)
        return text


def redact_log_text(text: str) -> str:
    """Redact known secret patterns from log text before export.

    Safe for log export bundles. Pure Python — no Rust dependency.
    Returns the redacted string.
    """
    return CredentialStripper().strip(text)


def secret_scan_text(text: str) -> List[Dict[str, str]]:
    """Scan text for secret patterns and return a list of findings.

    Each finding is a dict with keys: pattern_name, match_preview.
    match_preview shows the first 6 chars of the match followed by '…'
    so the caller can identify the finding without exposing the secret.

    Safe for artifact-level secret scanning. No Rust dependency.
    """
    findings: List[Dict[str, str]] = []
    for label, pattern in _CREDENTIAL_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0)
            preview = raw[:6] + "…" if len(raw) > 6 else raw[:3] + "…"
            findings.append({"pattern_name": label, "match_preview": preview})
    return findings


def wrap_tool_output(tool_name: str, content: str, success: bool = True) -> str:
    status = "success" if success else "error"
    header = f'<tool_result name="{tool_name}" status="{status}">'
    return f"{header}\n{content}\n</tool_result>"
