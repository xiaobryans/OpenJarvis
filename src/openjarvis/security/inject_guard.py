"""Jarvis Prompt-Injection Protection — source trust layer.

Classifies content by trust level and prevents untrusted content from
overriding system/governance rules.

Trust levels:
  trusted      — Jarvis internal, verified operator input
  semi_trusted — Bryan-controlled repos, known local paths
  untrusted    — web, remote repos, connector messages, browser/screen content
  quarantined  — content that triggered injection patterns

Source provenance tags:
  source_type: "web", "repo_file", "doc", "connector_message",
               "browser_content", "screen_content", "operator_input", "internal"

Hard rules:
  - Untrusted content cannot override system/governance instructions
  - Quarantined content is flagged and isolated — never executed
  - Provenance tag always attached before processing
  - No fake clean status for suspicious content
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Trust levels and source types
# ---------------------------------------------------------------------------


class TrustLevel:
    TRUSTED = "trusted"
    SEMI_TRUSTED = "semi_trusted"
    UNTRUSTED = "untrusted"
    QUARANTINED = "quarantined"


class SourceType:
    OPERATOR_INPUT = "operator_input"
    INTERNAL = "internal"
    REPO_FILE = "repo_file"
    DOC = "doc"
    WEB = "web"
    CONNECTOR_MESSAGE = "connector_message"
    BROWSER_CONTENT = "browser_content"
    SCREEN_CONTENT = "screen_content"
    UNKNOWN = "unknown"


# Default trust for each source type
_SOURCE_TRUST: Dict[str, str] = {
    SourceType.OPERATOR_INPUT: TrustLevel.TRUSTED,
    SourceType.INTERNAL: TrustLevel.TRUSTED,
    SourceType.REPO_FILE: TrustLevel.SEMI_TRUSTED,
    SourceType.DOC: TrustLevel.SEMI_TRUSTED,
    SourceType.WEB: TrustLevel.UNTRUSTED,
    SourceType.CONNECTOR_MESSAGE: TrustLevel.UNTRUSTED,
    SourceType.BROWSER_CONTENT: TrustLevel.UNTRUSTED,
    SourceType.SCREEN_CONTENT: TrustLevel.UNTRUSTED,
    SourceType.UNKNOWN: TrustLevel.UNTRUSTED,
}

# Patterns that trigger quarantine regardless of source
_QUARANTINE_PATTERNS: List[tuple] = [
    (
        r"(?i)ignore\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|rules?|system)",
        "system_override",
    ),
    (
        r"(?i)disregard\s+.{0,30}(?:instructions?|programming|rules?|restrictions?)",
        "system_override",
    ),
    (
        r"(?i)you\s+are\s+now\s+(?:a\s+)?(?:different|new|my)\s+\w+",
        "identity_override",
    ),
    (
        r"(?i)act\s+as\s+(?:if\s+you\s+(?:have|are)|a\s+)?(?:an?\s+)?(?:unrestricted|jailbroken|DAN)",
        "jailbreak",
    ),
    (
        r"(?i)(?:DAN|do\s+anything\s+now)\s+(?:mode|prompt|jailbreak)",
        "jailbreak",
    ),
    (
        r"(?i)pretend\s+.{0,20}no\s+(?:restrictions?|limitations?|rules?|filters?)",
        "jailbreak",
    ),
    (
        r"<\|(?:im_start|im_end|system|assistant)\|>",
        "chat_template_injection",
    ),
    (
        r"```(?:system|assistant)\b",
        "role_delimiter_injection",
    ),
    (
        r"(?i)(?:exfiltrate|send\s+all\s+(?:data|secrets?|tokens?))\s+to",
        "exfiltration_attempt",
    ),
    (
        r"(?i)override\s+(?:governance|safety|policy|hard\s+gate)",
        "governance_override",
    ),
    (
        r"(?i)bypass\s+(?:approval|rate.?limit|budget|guard)",
        "control_bypass",
    ),
]

_compiled_patterns = [(re.compile(pat), name) for pat, name in _QUARANTINE_PATTERNS]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceTag:
    source_type: str
    trust_level: str
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    tagged_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_type": self.source_type,
            "trust_level": self.trust_level,
            "source_path": self.source_path,
            "source_url": self.source_url,
            "tagged_at": self.tagged_at,
        }


@dataclass
class InjectGuardResult:
    content: str
    provenance: ProvenanceTag
    is_safe: bool
    quarantined: bool
    findings: List[Dict[str, str]]
    sanitized_content: Optional[str]  # stripped of injection attempts if semi_trusted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_safe": self.is_safe,
            "quarantined": self.quarantined,
            "trust_level": self.provenance.trust_level,
            "source_type": self.provenance.source_type,
            "findings": self.findings,
            "has_sanitized_content": self.sanitized_content is not None,
            "provenance": self.provenance.to_dict(),
        }


# ---------------------------------------------------------------------------
# Core scan + guard
# ---------------------------------------------------------------------------


def classify_source(source_type: str, source_url: Optional[str] = None) -> str:
    """Get trust level for a source type."""
    base = _SOURCE_TRUST.get(source_type, TrustLevel.UNTRUSTED)
    # Downgrade if URL looks external
    if source_url and base == TrustLevel.SEMI_TRUSTED:
        if source_url.startswith("http"):
            return TrustLevel.UNTRUSTED
    return base


def tag_content(
    content: str,
    source_type: str,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    trust_override: Optional[str] = None,
) -> ProvenanceTag:
    """Attach provenance tag to content."""
    trust = trust_override or classify_source(source_type, source_url)
    return ProvenanceTag(
        source_type=source_type,
        trust_level=trust,
        source_path=source_path,
        source_url=source_url,
    )


def scan_for_injection(content: str) -> List[Dict[str, str]]:
    """Scan content for injection patterns. Returns list of findings."""
    findings: List[Dict[str, str]] = []
    for pattern, name in _compiled_patterns:
        match = pattern.search(content)
        if match:
            findings.append({
                "pattern": name,
                "match_start": str(match.start()),
                "match_end": str(match.end()),
                "snippet": content[max(0, match.start() - 10): match.end() + 10],
            })
    return findings


def guard_content(
    content: str,
    source_type: str,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    trust_override: Optional[str] = None,
) -> InjectGuardResult:
    """Full guard: tag, scan, quarantine if needed.

    Trusted sources: scan but allow with warning
    Semi-trusted: scan + sanitize if injection found
    Untrusted: scan + quarantine on any finding; sanitize if no findings
    """
    provenance = tag_content(
        content, source_type, source_path, source_url, trust_override
    )
    findings = scan_for_injection(content)
    trust = provenance.trust_level

    if trust == TrustLevel.TRUSTED:
        # Trusted: allow, but flag findings as warnings
        return InjectGuardResult(
            content=content,
            provenance=provenance,
            is_safe=True,
            quarantined=False,
            findings=findings,
            sanitized_content=None,
        )

    if findings:
        if trust == TrustLevel.SEMI_TRUSTED:
            # Semi-trusted: sanitize injection patterns
            sanitized = _sanitize(content)
            return InjectGuardResult(
                content=content,
                provenance=provenance,
                is_safe=False,
                quarantined=False,
                findings=findings,
                sanitized_content=sanitized,
            )
        else:
            # Untrusted: quarantine
            provenance.trust_level = TrustLevel.QUARANTINED
            return InjectGuardResult(
                content=content,
                provenance=provenance,
                is_safe=False,
                quarantined=True,
                findings=findings,
                sanitized_content=None,
            )

    # No findings
    return InjectGuardResult(
        content=content,
        provenance=provenance,
        is_safe=True,
        quarantined=False,
        findings=[],
        sanitized_content=None,
    )


def _sanitize(content: str) -> str:
    """Replace injection patterns with [SANITIZED] placeholder."""
    result = content
    for pattern, name in _compiled_patterns:
        result = pattern.sub(f"[SANITIZED:{name}]", result)
    return result


# ---------------------------------------------------------------------------
# Governance check — untrusted content cannot override system rules
# ---------------------------------------------------------------------------


def enforce_governance_boundary(
    content: str,
    source_type: str,
    system_instruction: str = "",
) -> Dict[str, Any]:
    """Ensure untrusted content cannot override system/governance instructions.

    Returns allowed=True/False with reason.
    """
    result = guard_content(content, source_type)
    trust = result.provenance.trust_level

    if trust == TrustLevel.QUARANTINED:
        return {
            "allowed": False,
            "reason": "Content quarantined — injection patterns detected from untrusted source",
            "trust_level": trust,
            "findings": result.findings,
        }

    if trust == TrustLevel.UNTRUSTED and result.findings:
        return {
            "allowed": False,
            "reason": "Untrusted content with injection patterns — blocked",
            "trust_level": trust,
            "findings": result.findings,
        }

    # Check if content tries to override governance
    governance_override_patterns = [
        r"(?i)override\s+(?:governance|policy|hard.?gate|safety|constitution)",
        r"(?i)disable\s+(?:approval|guard|limit|budget)",
        r"(?i)skip\s+(?:approval|confirmation|auth)",
    ]
    for pat in governance_override_patterns:
        if re.search(pat, content):
            return {
                "allowed": False,
                "reason": "Content attempts to override governance rules — blocked",
                "trust_level": trust,
                "findings": [{"pattern": "governance_override_attempt", "content_snippet": content[:100]}],
            }

    return {
        "allowed": True,
        "reason": "Content passed governance boundary check",
        "trust_level": trust,
        "findings": result.findings,
    }


def get_inject_guard_status() -> Dict[str, Any]:
    """Doctor/readiness status for inject guard."""
    return {
        "active": True,
        "pattern_count": len(_QUARANTINE_PATTERNS),
        "trust_levels": [TrustLevel.TRUSTED, TrustLevel.SEMI_TRUSTED, TrustLevel.UNTRUSTED, TrustLevel.QUARANTINED],
        "source_types_classified": list(_SOURCE_TRUST.keys()),
        "governance_boundary_enforced": True,
        "sanitization_available": True,
    }


__all__ = [
    "TrustLevel",
    "SourceType",
    "ProvenanceTag",
    "InjectGuardResult",
    "classify_source",
    "tag_content",
    "scan_for_injection",
    "guard_content",
    "enforce_governance_boundary",
    "get_inject_guard_status",
]
