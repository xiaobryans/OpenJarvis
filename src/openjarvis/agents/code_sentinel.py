"""Code Sentinel — verifier/security/release gate for Jarvis pipeline.

Responsibilities:
  1. changed-file review policy — only review what changed
  2. stale artifact detection — flag artifacts older than TTL
  3. secret scan requirement — flag secret-like patterns
  4. unsafe action detection — flag destructive/irreversible ops
  5. validation-command requirement — ensure commands are documented
  6. unsupported claim rejection — reject ACCEPT claims without evidence
  7. durable prevention item creation — create prevention records for issues
  8. rollback/fix-list output — exact fixes needed
  9. no broad audit unless justified — enforce targeted access
  10. integration with verifier and company runtime

The sentinel is stateless per call but records findings.

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Sentinel enums
# ---------------------------------------------------------------------------

class SentinelSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SentinelFindingType(str, Enum):
    STALE_ARTIFACT = "STALE_ARTIFACT"
    SECRET_DETECTED = "SECRET_DETECTED"
    UNSAFE_ACTION = "UNSAFE_ACTION"
    UNSUPPORTED_CLAIM = "UNSUPPORTED_CLAIM"
    MISSING_VALIDATION_COMMAND = "MISSING_VALIDATION_COMMAND"
    BROAD_AUDIT_WITHOUT_JUSTIFICATION = "BROAD_AUDIT_WITHOUT_JUSTIFICATION"
    POLICY_VIOLATION = "POLICY_VIOLATION"


# ---------------------------------------------------------------------------
# Finding and Prevention
# ---------------------------------------------------------------------------

@dataclass
class SentinelFinding:
    finding_id: str
    finding_type: SentinelFindingType
    severity: SentinelSeverity
    description: str
    file_path: Optional[str]
    fix: str
    blocks_release: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "finding_type": self.finding_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "file_path": self.file_path,
            "fix": self.fix,
            "blocks_release": self.blocks_release,
            "created_at": self.created_at,
        }


@dataclass
class PreventionItem:
    prevention_id: str
    trigger: str               # what finding triggered this
    rule: str                  # the durable rule to prevent recurrence
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prevention_id": self.prevention_id,
            "trigger": self.trigger,
            "rule": self.rule,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Secret patterns (conservative — no real secrets stored here)
# ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    r"sk[-_][a-zA-Z0-9]{20,}",          # OpenAI-style
    r"ghp_[a-zA-Z0-9]{36}",             # GitHub PAT
    r"AKIA[A-Z0-9]{16}",                # AWS access key
    r"(?i)password\s*=\s*['\"][^'\"]+['\"]",
    r"(?i)api[_-]?key\s*=\s*['\"][^'\"]+['\"]",
    r"(?i)secret\s*=\s*['\"][^'\"]+['\"]",
]

_UNSAFE_ACTIONS = [
    "git push --force",
    "git push -f",
    "DROP TABLE",
    "DROP DATABASE",
    "rm -rf",
    "git reset --hard",
    "--no-verify",
    "force_push",
    "destroy_",
    "delete_production",
]

_UNSUPPORTED_CLAIM_PATTERNS = [
    r"FULL_NO_GAP_JARVIS_COMPLETE",
    r"NO_GAP_JARVIS_CERTIFIED",
    r"VOICE_DAILY_DRIVER_ACCEPT",
    r"NATIVE_APP_ACCEPT",
    r"PUBLIC_RELEASE_ACCEPT",
    r"VOICE_PUBLIC_READY_ACCEPT",
]

STALE_ARTIFACT_TTL_SECONDS = 86400 * 7   # 7 days


# ---------------------------------------------------------------------------
# Code Sentinel
# ---------------------------------------------------------------------------

class CodeSentinel:
    """Code Sentinel — runs on changed files and claims only.

    Enforces targeted access: only review what changed.
    Does NOT run broad audits unless justified.
    """

    def __init__(self) -> None:
        self._findings: List[SentinelFinding] = []
        self._preventions: List[PreventionItem] = []

    def _add_finding(
        self,
        finding_type: SentinelFindingType,
        severity: SentinelSeverity,
        description: str,
        fix: str,
        file_path: Optional[str] = None,
        blocks_release: bool = True,
    ) -> SentinelFinding:
        f = SentinelFinding(
            finding_id=str(uuid.uuid4())[:8],
            finding_type=finding_type,
            severity=severity,
            description=description,
            file_path=file_path,
            fix=fix,
            blocks_release=blocks_release,
        )
        self._findings.append(f)
        # Create durable prevention item for critical/high
        if severity in (SentinelSeverity.CRITICAL, SentinelSeverity.HIGH):
            self._preventions.append(PreventionItem(
                prevention_id=str(uuid.uuid4())[:8],
                trigger=description,
                rule=fix,
            ))
        return f

    # --- 1. Changed-file review ---
    def review_changed_files(self, changed_files: List[str]) -> List[SentinelFinding]:
        """Review only the changed files listed. No broad scan."""
        findings = []
        for path in changed_files:
            if any(skip in path for skip in [".git", "node_modules", ".venv", "__pycache__"]):
                continue
            # Stale artifact check (by name pattern)
            if any(path.endswith(ext) for ext in [".pyc", ".cache", ".tmp"]):
                f = self._add_finding(
                    SentinelFindingType.STALE_ARTIFACT,
                    SentinelSeverity.LOW,
                    f"Compiled artifact in changed files: {path}",
                    f"Remove {path} and add to .gitignore",
                    file_path=path,
                    blocks_release=False,
                )
                findings.append(f)
        return findings

    # --- 2. Stale artifact detection ---
    def check_stale_artifact(
        self,
        artifact_path: str,
        artifact_created_at: float,
        *,
        ttl_seconds: int = STALE_ARTIFACT_TTL_SECONDS,
    ) -> Optional[SentinelFinding]:
        age = time.time() - artifact_created_at
        if age > ttl_seconds:
            return self._add_finding(
                SentinelFindingType.STALE_ARTIFACT,
                SentinelSeverity.MEDIUM,
                f"Artifact '{artifact_path}' is {int(age/3600)}h old — may be stale",
                f"Re-generate or delete '{artifact_path}'. Verify still referenced.",
                file_path=artifact_path,
                blocks_release=False,
            )
        return None

    # --- 3. Secret scan ---
    def scan_for_secrets(self, content: str, file_path: str = "<unknown>") -> List[SentinelFinding]:
        findings = []
        for pattern in _SECRET_PATTERNS:
            if re.search(pattern, content):
                f = self._add_finding(
                    SentinelFindingType.SECRET_DETECTED,
                    SentinelSeverity.CRITICAL,
                    f"Potential secret pattern matched in {file_path}: /{pattern}/",
                    f"Remove secret from {file_path}. Move to .env. Add .env to .gitignore. "
                    f"Rotate the credential if committed.",
                    file_path=file_path,
                    blocks_release=True,
                )
                findings.append(f)
        return findings

    # --- 4. Unsafe action detection ---
    def check_unsafe_action(self, command_or_code: str) -> List[SentinelFinding]:
        findings = []
        for unsafe in _UNSAFE_ACTIONS:
            if unsafe.lower() in command_or_code.lower():
                f = self._add_finding(
                    SentinelFindingType.UNSAFE_ACTION,
                    SentinelSeverity.CRITICAL,
                    f"Unsafe action detected: '{unsafe}' in command/code",
                    f"Remove or require explicit Bryan approval before executing '{unsafe}'",
                    blocks_release=True,
                )
                findings.append(f)
        return findings

    # --- 5. Validation command requirement ---
    def require_validation_command(self, claims: List[str], validation_commands: List[str]) -> Optional[SentinelFinding]:
        if claims and not validation_commands:
            return self._add_finding(
                SentinelFindingType.MISSING_VALIDATION_COMMAND,
                SentinelSeverity.HIGH,
                f"Claims made ({claims}) without validation commands documented",
                "Add exact validation commands (e.g. pytest, tsc, git diff --check) with expected output",
                blocks_release=True,
            )
        return None

    # --- 6. Unsupported claim rejection ---
    def reject_unsupported_claims(self, text: str) -> List[SentinelFinding]:
        findings = []
        for pattern in _UNSUPPORTED_CLAIM_PATTERNS:
            if re.search(pattern, text):
                f = self._add_finding(
                    SentinelFindingType.UNSUPPORTED_CLAIM,
                    SentinelSeverity.CRITICAL,
                    f"Forbidden claim '{pattern}' found without verified evidence",
                    f"Remove '{pattern}' claim. It can only be set after verified evidence. "
                    f"Use HOLD verdict until evidence exists.",
                    blocks_release=True,
                )
                findings.append(f)
        return findings

    # --- Full gate ---
    def run_gate(
        self,
        changed_files: Optional[List[str]] = None,
        claims: Optional[List[str]] = None,
        validation_commands: Optional[List[str]] = None,
        content_to_scan: Optional[str] = None,
        command_to_check: Optional[str] = None,
        justification_for_broad_audit: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run full sentinel gate. Returns findings and verdict."""
        pre_count = len(self._findings)

        if changed_files:
            self.review_changed_files(changed_files)

        if content_to_scan:
            self.scan_for_secrets(content_to_scan, "<input>")

        if command_to_check:
            self.check_unsafe_action(command_to_check)

        if claims:
            self.require_validation_command(claims, validation_commands or [])
            self.reject_unsupported_claims(" ".join(claims))

        if changed_files and len(changed_files) > 50 and not justification_for_broad_audit:
            self._add_finding(
                SentinelFindingType.BROAD_AUDIT_WITHOUT_JUSTIFICATION,
                SentinelSeverity.MEDIUM,
                f"{len(changed_files)} files reviewed without justification — violates targeted-access rule",
                "Narrow scope to changed files only, or provide explicit justification",
                blocks_release=False,
            )

        new_findings = self._findings[pre_count:]
        blocking = [f for f in new_findings if f.blocks_release]
        verdict = "PASS" if not blocking else "BLOCKED"

        return {
            "verdict": verdict,
            "new_findings": len(new_findings),
            "blocking_findings": len(blocking),
            "findings": [f.to_dict() for f in new_findings],
            "fix_list": [f.fix for f in blocking],
            "prevention_items": [p.to_dict() for p in self._preventions],
            "rollback_required": any(
                f.finding_type == SentinelFindingType.SECRET_DETECTED for f in blocking
            ),
        }

    def get_all_findings(self) -> List[Dict[str, Any]]:
        return [f.to_dict() for f in self._findings]


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_SENTINEL: Optional[CodeSentinel] = None


def get_code_sentinel() -> CodeSentinel:
    global _SENTINEL
    if _SENTINEL is None:
        _SENTINEL = CodeSentinel()
    return _SENTINEL


__all__ = [
    "SentinelSeverity",
    "SentinelFindingType",
    "SentinelFinding",
    "PreventionItem",
    "CodeSentinel",
    "get_code_sentinel",
]
