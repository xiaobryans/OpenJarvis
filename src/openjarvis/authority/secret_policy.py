"""Plan 8 — Secret/Credential Access Policy.

Enforces:
  - Never print secrets
  - Never commit secrets
  - Never expose tokens in UI/logs
  - Require approval for credential-backed high-risk actions
  - Use existing credential stores only (keychain, .env, aws_config, gh_cli, oauth_store)
  - Secret access auditable by name/scope, not value

This module provides:
  - SecretPolicy: static policy rules
  - SecretAccessRequest: audit record for credential access
  - SecretPolicyChecker: enforces policy before credential access
  - secret_scan_string: detect obvious token patterns in strings
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional


# ---------------------------------------------------------------------------
# Allowed credential stores
# ---------------------------------------------------------------------------


class CredentialStore(str, Enum):
    OS_KEYCHAIN = "os_keychain"         # macOS Keychain / Linux Secret Service
    DOT_ENV = "dot_env"                 # Local .env file (non-committed)
    AWS_CONFIG = "aws_config"           # ~/.aws/credentials or environment
    GH_CLI = "gh_cli"                   # gh CLI token store
    OAUTH_STORE = "oauth_store"         # Local OAuth token store
    ENV_VAR = "env_var"                 # Environment variable (runtime only)


ALLOWED_CREDENTIAL_STORES: FrozenSet[CredentialStore] = frozenset({
    CredentialStore.OS_KEYCHAIN,
    CredentialStore.DOT_ENV,
    CredentialStore.AWS_CONFIG,
    CredentialStore.GH_CLI,
    CredentialStore.OAUTH_STORE,
    CredentialStore.ENV_VAR,
})

FORBIDDEN_CREDENTIAL_STORES: FrozenSet[str] = frozenset({
    "hardcoded",            # Never hardcode in source
    "git_committed",        # Never commit to git
    "log_output",           # Never write to logs
    "ui_response",          # Never expose in UI response
    "chat_message",         # Never paste in chat
})


# ---------------------------------------------------------------------------
# Secret scan patterns
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "github_personal_token"),
    (re.compile(r"gho_[A-Za-z0-9]{36}"), "github_oauth_token"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "openai_api_key"),
    (re.compile(r"xoxb-[A-Za-z0-9\-]+"), "slack_bot_token"),
    (re.compile(r"AKIA[A-Z0-9]{16}"), "aws_access_key_id"),
    (re.compile(r"(?:Bearer|bearer)\s+[A-Za-z0-9\-._~+/]+=*"), "bearer_token"),
    (re.compile(r"(?:password|passwd)\s*=\s*\S+", re.IGNORECASE), "password_assignment"),
    (re.compile(r"(?:api_key|apikey|api-key)\s*=\s*\S+", re.IGNORECASE), "api_key_assignment"),
    (re.compile(r"(?:secret|token)\s*=\s*['\"]?\S+['\"]?", re.IGNORECASE), "secret_assignment"),
]


@dataclass
class SecretScanResult:
    """Result of scanning a string for secret patterns."""

    clean: bool
    findings: List[Dict[str, str]]  # [{pattern_name, match_preview}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clean": self.clean,
            "findings": self.findings,
        }


def secret_scan_string(text: str, max_preview: int = 20) -> SecretScanResult:
    """Scan a string for obvious secret patterns.

    Returns SecretScanResult with clean=True if no patterns found.
    match_preview is truncated to avoid logging actual secret values.
    """
    findings = []
    for pattern, name in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            raw = m.group(0)
            preview = raw[:max_preview] + "..." if len(raw) > max_preview else raw
            findings.append({"pattern_name": name, "match_preview": preview})
    return SecretScanResult(clean=len(findings) == 0, findings=findings)


def redact_secrets(text: str) -> str:
    """Replace any detected secret patterns in a string with '<redacted>'."""
    for pattern, _ in _SECRET_PATTERNS:
        text = pattern.sub("<redacted>", text)
    return text


# ---------------------------------------------------------------------------
# SecretAccessRequest — audit record for credential access
# ---------------------------------------------------------------------------


@dataclass
class SecretAccessRequest:
    """Audit record for a credential/secret access request.

    Records NAME and SCOPE of access, never the value.
    """

    request_id: str
    requester: str              # agent_id or "user"
    credential_name: str        # e.g. "SLACK_BOT_TOKEN", "OPENAI_API_KEY"
    credential_store: str       # CredentialStore value
    access_scope: str           # read-only | write | admin
    action_context: str         # why this credential is needed
    tier: int                   # required tier for this access
    approved: bool = False
    approval_id: Optional[str] = None
    denied_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "requester": self.requester,
            "credential_name": self.credential_name,
            "credential_store": self.credential_store,
            "access_scope": self.access_scope,
            "action_context": self.action_context,
            "tier": self.tier,
            "approved": self.approved,
            "approval_id": self.approval_id,
            "denied_reason": self.denied_reason,
        }


# ---------------------------------------------------------------------------
# SecretPolicyChecker
# ---------------------------------------------------------------------------


class SecretPolicyChecker:
    """Enforces secret/credential access policy before any credential use.

    Rules (non-negotiable):
    1. Never print, log, or expose secret values.
    2. Never commit secrets to git.
    3. Use only allowed credential stores.
    4. Tier 4+ actions with credential access require explicit approval.
    5. Audit every credential access by name/scope, never by value.
    """

    # Minimum tier required for credential access by scope
    _MIN_TIER_FOR_SCOPE: Dict[str, int] = {
        "read_only": 3,
        "write": 4,
        "admin": 5,
    }

    def check_access(
        self,
        credential_name: str,
        store: str,
        scope: str,
        tier: int,
        *,
        requester: str = "",
    ) -> Dict[str, Any]:
        """Check if credential access is permitted under current tier and policy.

        Returns dict with allowed, reason, and required actions.
        """
        # Validate store
        allowed_stores = {s.value for s in ALLOWED_CREDENTIAL_STORES}
        if store not in allowed_stores:
            return {
                "allowed": False,
                "reason": (
                    f"Credential store '{store}' is not in allowed stores: {sorted(allowed_stores)}. "
                    "Never hardcode credentials or commit them to git."
                ),
                "hard_block": True,
            }

        # Validate scope
        min_tier = self._MIN_TIER_FOR_SCOPE.get(scope, 5)
        if tier < min_tier:
            return {
                "allowed": False,
                "reason": (
                    f"Credential '{credential_name}' with scope '{scope}' requires Tier {min_tier}. "
                    f"Current tier: {tier}. Step-up approval required."
                ),
                "requires_tier": min_tier,
                "hard_block": False,
            }

        # Tier 4+ always needs approval record
        requires_approval = tier >= 4

        return {
            "allowed": True,
            "reason": (
                f"Credential '{credential_name}' from '{store}' with scope '{scope}' "
                f"is permitted at Tier {tier}."
            ),
            "requires_approval": requires_approval,
            "audit_note": (
                f"Access to '{credential_name}' (store={store}, scope={scope}) "
                f"audited for requester='{requester}'. Value NOT logged."
            ),
            "hard_block": False,
        }

    def validate_no_secrets_in_text(self, text: str) -> Dict[str, Any]:
        """Scan text for accidental secret exposure.

        Returns dict with clean=True if safe, findings list if not.
        """
        result = secret_scan_string(text)
        if result.clean:
            return {"clean": True, "findings": []}
        return {
            "clean": False,
            "findings": result.findings,
            "error": (
                f"Secret pattern detected in text ({len(result.findings)} finding(s)). "
                "This text must NOT be logged, stored, or sent to the UI."
            ),
        }


# ---------------------------------------------------------------------------
# Static policy manifest
# ---------------------------------------------------------------------------

SECRET_POLICY_MANIFEST: Dict[str, Any] = {
    "never_print_secrets": True,
    "never_commit_secrets": True,
    "never_expose_in_ui_or_logs": True,
    "audit_by_name_scope_not_value": True,
    "require_approval_for_high_risk_credential_actions": True,
    "allowed_stores": [s.value for s in ALLOWED_CREDENTIAL_STORES],
    "forbidden_stores": sorted(FORBIDDEN_CREDENTIAL_STORES),
    "min_tier_for_credential_read": 3,
    "min_tier_for_credential_write": 4,
    "min_tier_for_credential_admin": 5,
    "token_patterns_scanned": [name for _, name in _SECRET_PATTERNS],
}


__all__ = [
    "ALLOWED_CREDENTIAL_STORES",
    "CredentialStore",
    "SECRET_POLICY_MANIFEST",
    "SecretAccessRequest",
    "SecretPolicyChecker",
    "SecretScanResult",
    "redact_secrets",
    "secret_scan_string",
]
