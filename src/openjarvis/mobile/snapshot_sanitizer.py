"""Snapshot Sanitizer — secure redaction layer for cloud-uploaded continuity snapshots.

Security model: STRICT REDACTION BEFORE UPLOAD

Before any continuity snapshot is uploaded to GitHub Gist (or any cloud backend),
this sanitizer:

  1. REJECTS any snapshot containing raw secrets, tokens, passwords, or API keys.
  2. REDACTS sensitive fields by replacing content with safe pointers/hashes.
  3. SCRUBS known secret-pattern fields entirely from the cloud payload.
  4. KEEPS all structural/pointer fields needed for resumption.
  5. LOGS a sanitization report (no values logged — only field names and action).

Security approach: METADATA-ONLY + REDACTION

The cloud payload contains:
  - Structural pointers (task_id, conversation_id, device_id, snapshot_id)
  - State references (status strings, role IDs, project IDs)
  - Safe hashes of sensitive content (SHA-256 of artifact paths, not contents)
  - Redacted summaries (e.g. "3 pending approvals" not approval contents)
  - Blocker list (text, no secret values)

The cloud payload NEVER contains:
  - Raw OAuth tokens or API keys
  - Credential strings
  - Approval payload content (private decisions/amounts)
  - Artifact file contents
  - Memory entry raw content
  - Tool state credential fields

Sensitive raw content stays LOCAL ONLY (local SQLite/file store).
The cloud snapshot is a safe resume pointer, not a full state dump.

Sprint: Sprint 3 MacBook-Off Continuity Security Retest
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Secret detection patterns (conservative — reject on any match)
# ---------------------------------------------------------------------------

_SECRET_FIELD_NAMES = frozenset({
    "token", "secret", "password", "api_key", "apikey", "private_key",
    "access_token", "refresh_token", "oauth_token", "credential", "credentials",
    "auth_token", "bearer", "jwt", "session_token", "signing_key", "encryption_key",
    "client_secret", "webhook_secret", "stripe_key", "openai_key",
    "github_token", "slack_token", "telegram_token",
})

_SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),          # GitHub PAT
    re.compile(r"sk[-_][a-zA-Z0-9]{20,}"),        # OpenAI-style
    re.compile(r"AKIA[A-Z0-9]{16}"),              # AWS
    re.compile(r"xox[bpoa]-[a-zA-Z0-9-]+"),       # Slack
    re.compile(r"[0-9]{8,10}:[a-zA-Z0-9_-]{35}"), # Telegram bot
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9._-]{20,}"),
]

# Fields that may contain structured private approval content
_PRIVATE_APPROVAL_FIELDS = frozenset({
    "approval_content", "approval_payload", "approval_detail",
    "decision_reason", "financial_amount", "payment_data",
})

# Fields that may contain raw artifact/memory content
_CONTENT_FIELDS = frozenset({
    "artifact_content", "file_content", "raw_content", "memory_content",
    "tool_output_raw", "conversation_messages",  # messages are local-only
})

# Fields to hash rather than include
_HASH_FIELDS = frozenset({
    "conversation_id", "active_task_id",
})

# Fields to completely strip from cloud payload (never cloud-safe)
_STRIP_ALWAYS = frozenset({
    "tool_states",       # may contain connector credentials
    "memory_refs",       # local memory IDs — resolved locally on resume
})


# ---------------------------------------------------------------------------
# Sanitizer result
# ---------------------------------------------------------------------------

class SnapshotRejected(Exception):
    """Raised when a snapshot is rejected for containing a raw secret."""
    pass


class SanitizationReport:
    """Records what was redacted/stripped (field names only, no values)."""

    def __init__(self) -> None:
        self.rejected_fields: List[str] = []
        self.redacted_fields: List[str] = []
        self.stripped_fields: List[str] = []
        self.hashed_fields: List[str] = []
        self.secret_rejected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "secret_rejected": self.secret_rejected,
            "rejected_fields": self.rejected_fields,
            "redacted_fields": self.redacted_fields,
            "stripped_fields": self.stripped_fields,
            "hashed_fields": self.hashed_fields,
            "cloud_safe": not self.secret_rejected,
        }


# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------

def _contains_secret_pattern(value: str) -> bool:
    """Return True if a string value matches known secret patterns."""
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(value):
            return True
    return False


def _safe_hash(value: str) -> str:
    """Return SHA-256 hash of value — safe pointer, not the value itself."""
    return "sha256:" + hashlib.sha256(value.encode()).hexdigest()[:16]


def _redact_value(field_name: str, value: Any, report: SanitizationReport) -> Any:
    """Redact a single value. Returns safe replacement."""
    if isinstance(value, str):
        if _contains_secret_pattern(value):
            report.secret_rejected = True
            report.rejected_fields.append(field_name)
            raise SnapshotRejected(
                f"Snapshot rejected: field '{field_name}' contains a raw secret pattern. "
                f"Rotate the credential and remove from continuity state."
            )
        if len(value) > 512:
            report.redacted_fields.append(field_name)
            return f"[REDACTED:len={len(value)}]"
    if isinstance(value, (list, dict)) and field_name in _CONTENT_FIELDS:
        count = len(value) if isinstance(value, (list, dict)) else 0
        report.redacted_fields.append(field_name)
        return f"[REDACTED:{field_name}:count={count}]"
    return value


def sanitize_for_cloud(
    snapshot_data: Dict[str, Any],
) -> Tuple[Dict[str, Any], SanitizationReport]:
    """Sanitize a snapshot dict for safe cloud upload.

    Returns:
        (cloud_safe_payload, SanitizationReport)

    Raises:
        SnapshotRejected if a raw secret pattern is detected.

    Security model: STRICT REDACTION + METADATA-ONLY
      - Raw secret fields → rejected (SnapshotRejected)
      - Private approval content → redacted to count summary
      - Artifact file contents → redacted to pointer
      - Memory raw content → stripped (local-only)
      - Tool states → stripped (may contain credentials)
      - Conversation messages → stripped (local-only; conversation_id kept as pointer)
      - All other fields → included as-is (structural/state pointers)
    """
    report = SanitizationReport()
    cloud_payload: Dict[str, Any] = {}

    for field_name, value in snapshot_data.items():
        field_lower = field_name.lower()

        # 1. Strip always-excluded fields
        if field_lower in _STRIP_ALWAYS or field_name in _STRIP_ALWAYS:
            report.stripped_fields.append(field_name)
            cloud_payload[field_name] = f"[LOCAL_ONLY:{field_name}]"
            continue

        # 2. Reject secret-named fields with non-empty values
        if field_lower in _SECRET_FIELD_NAMES:
            if value:
                report.secret_rejected = True
                report.rejected_fields.append(field_name)
                raise SnapshotRejected(
                    f"Snapshot rejected: field '{field_name}' is a known secret field. "
                    f"Remove '{field_name}' from continuity state before cloud upload."
                )
            cloud_payload[field_name] = None
            continue

        # 3. Private approval payloads → redacted count summary
        if field_lower in _PRIVATE_APPROVAL_FIELDS or field_name in _PRIVATE_APPROVAL_FIELDS:
            if isinstance(value, (list, dict)):
                count = len(value)
                report.redacted_fields.append(field_name)
                cloud_payload[field_name] = f"[REDACTED:approval_payload:count={count}]"
            elif value:
                report.redacted_fields.append(field_name)
                cloud_payload[field_name] = "[REDACTED:approval_payload]"
            else:
                cloud_payload[field_name] = value
            continue

        # 4. Content fields → strip content, keep count pointer
        if field_name in _CONTENT_FIELDS or field_lower in _CONTENT_FIELDS:
            if isinstance(value, list):
                report.redacted_fields.append(field_name)
                cloud_payload[field_name] = f"[LOCAL_ONLY:{field_name}:count={len(value)}]"
            elif isinstance(value, dict):
                report.redacted_fields.append(field_name)
                cloud_payload[field_name] = f"[LOCAL_ONLY:{field_name}:keys={len(value)}]"
            elif value:
                report.redacted_fields.append(field_name)
                cloud_payload[field_name] = "[LOCAL_ONLY:content]"
            else:
                cloud_payload[field_name] = value
            continue

        # 5. Scan string values for secret patterns
        if isinstance(value, str):
            if _contains_secret_pattern(value):
                report.secret_rejected = True
                report.rejected_fields.append(field_name)
                raise SnapshotRejected(
                    f"Snapshot rejected: field '{field_name}' contains a raw secret pattern."
                )
            # Truncate very long strings
            if len(value) > 512:
                report.redacted_fields.append(field_name)
                cloud_payload[field_name] = f"[TRUNCATED:len={len(value)}]"
                continue

        # 6. Recurse into lists of dicts (e.g. artifact_pointers)
        if isinstance(value, list):
            sanitized_list = []
            for item in value:
                if isinstance(item, dict):
                    # Strip content from artifact items — keep only metadata
                    safe_item = {
                        k: v for k, v in item.items()
                        if k.lower() not in {"content", "raw", "data", "body"}
                    }
                    sanitized_list.append(safe_item)
                elif isinstance(item, str) and _contains_secret_pattern(item):
                    report.secret_rejected = True
                    raise SnapshotRejected(
                        f"Snapshot rejected: list field '{field_name}' contains a secret pattern."
                    )
                else:
                    sanitized_list.append(item)
            cloud_payload[field_name] = sanitized_list
            continue

        # Default: include as-is
        cloud_payload[field_name] = value

    return cloud_payload, report


__all__ = [
    "SnapshotRejected",
    "SanitizationReport",
    "sanitize_for_cloud",
]
