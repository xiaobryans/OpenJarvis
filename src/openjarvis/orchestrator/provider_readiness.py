"""Provider / Key / Blocker Readiness Dashboard.

Backend for the daily-driver provider readiness surface. Checks which
providers are configured, which capabilities are blocked by missing keys,
and what Bryan must do to unblock each item.

Design rules:
  - Never exposes key values — only presence (True/False).
  - Checks environment first, then ~/.jarvis/cloud-keys.env.
  - Never writes credentials.
  - No external network calls (pure local config check).
  - Returns structured ProviderReadinessReport usable by doctor, status routes,
    and CLI dashboard.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

_PROVIDER_DEFS: List[Dict[str, Any]] = [
    {
        "provider_id": "openai",
        "display_name": "OpenAI (GPT-4)",
        "env_var": "OPENAI_API_KEY",
        "capabilities_unlocked": [
            "llm_orchestration_openai",
            "coding_patch_propose",
            "coding_repair_loop",
        ],
        "capabilities_blocked_without": [
            "Real LLM orchestration (GPT-4)",
            "Coding patch generation",
            "Repair loop with code re-generation",
        ],
        "bryan_action": "Set OPENAI_API_KEY=sk-... in ~/.jarvis/cloud-keys.env",
        "fallback_without": "Dry-run keyword-based planning only; no LLM code generation.",
        "priority": "high",
    },
    {
        "provider_id": "anthropic",
        "display_name": "Anthropic (Claude)",
        "env_var": "ANTHROPIC_API_KEY",
        "capabilities_unlocked": [
            "llm_orchestration_anthropic",
            "coding_patch_propose",
            "coding_repair_loop",
        ],
        "capabilities_blocked_without": [
            "Claude-based orchestration",
            "Claude-assisted coding",
        ],
        "bryan_action": "Set ANTHROPIC_API_KEY=sk-ant-... in ~/.jarvis/cloud-keys.env",
        "fallback_without": "Dry-run planning only; no Claude orchestration.",
        "priority": "high",
    },
    {
        "provider_id": "openrouter",
        "display_name": "OpenRouter (multi-model routing)",
        "env_var": "OPENROUTER_API_KEY",
        "capabilities_unlocked": [
            "llm_orchestration_openrouter",
            "multi_model_routing",
        ],
        "capabilities_blocked_without": [
            "Multi-model routing across providers",
            "Cost-optimized model selection",
        ],
        "bryan_action": "Set OPENROUTER_API_KEY=sk-or-... in ~/.jarvis/cloud-keys.env",
        "fallback_without": "Single-provider planning only.",
        "priority": "medium",
    },
]

_CLOUD_KEYS_PATH = Path.home() / ".jarvis" / "cloud-keys.env"


def _read_cloud_keys_env() -> Dict[str, bool]:
    """Read ~/.jarvis/cloud-keys.env and return {key: present (bool)}.
    Never returns key values — only whether each known key is non-empty.
    """
    known_keys = {p["env_var"] for p in _PROVIDER_DEFS}
    result: Dict[str, bool] = {}
    if not _CLOUD_KEYS_PATH.exists():
        return result
    try:
        for line in _CLOUD_KEYS_PATH.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip()
                if k in known_keys:
                    result[k] = bool(v)
    except Exception:
        pass
    return result


def _key_present(env_var: str, cloud_keys: Dict[str, bool]) -> bool:
    """Return True if key is in environment or cloud-keys.env (non-empty)."""
    if os.environ.get(env_var):
        return True
    return cloud_keys.get(env_var, False)


# ---------------------------------------------------------------------------
# ProviderStatus / ProviderReadinessReport
# ---------------------------------------------------------------------------

@dataclass
class ProviderStatus:
    provider_id: str
    display_name: str
    env_var: str
    present: bool
    status: str  # "available" | "BLOCKED_PROVIDER"
    capabilities_unlocked: List[str]
    capabilities_blocked_without: List[str]
    bryan_action: str
    fallback_without: str
    priority: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "env_var": self.env_var,
            "present": self.present,
            "status": self.status,
            "capabilities_unlocked": self.capabilities_unlocked,
            "capabilities_blocked_without": self.capabilities_blocked_without,
            "bryan_action": self.bryan_action if not self.present else "—",
            "fallback_without": self.fallback_without,
            "priority": self.priority,
        }


@dataclass
class BlockerRecord:
    """A single blocked capability with its blocker classification and Bryan action."""
    capability: str
    blocker_type: str  # BLOCKED_PROVIDER | BLOCKED_CREDENTIALS | BLOCKED_SAFETY | etc.
    blocker_detail: str
    bryan_action: str
    fallback_behavior: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability": self.capability,
            "blocker_type": self.blocker_type,
            "blocker_detail": self.blocker_detail,
            "bryan_action": self.bryan_action,
            "fallback_behavior": self.fallback_behavior,
        }


@dataclass
class ProviderReadinessReport:
    """Structured provider/key/blocker status. No secret values exposed."""
    providers: List[ProviderStatus]
    blockers: List[BlockerRecord]
    any_llm_available: bool
    cloud_keys_file_exists: bool
    cloud_keys_file_path: str
    llm_in_loop_status: str  # "available" | "BLOCKED_PROVIDER"
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "providers": [p.to_dict() for p in self.providers],
            "blockers": [b.to_dict() for b in self.blockers],
            "any_llm_available": self.any_llm_available,
            "cloud_keys_file_exists": self.cloud_keys_file_exists,
            "cloud_keys_file_path": self.cloud_keys_file_path,
            "llm_in_loop_status": self.llm_in_loop_status,
            "summary": self.summary,
        }


def get_provider_readiness() -> ProviderReadinessReport:
    """Build and return the current provider/key/blocker readiness report.

    Checks env and ~/.jarvis/cloud-keys.env. Never exposes key values.
    """
    cloud_keys = _read_cloud_keys_env()
    providers: List[ProviderStatus] = []
    blockers: List[BlockerRecord] = []
    any_available = False

    for defn in _PROVIDER_DEFS:
        env_var = defn["env_var"]
        present = _key_present(env_var, cloud_keys)
        if present:
            any_available = True
        status = "available" if present else "BLOCKED_PROVIDER"
        ps = ProviderStatus(
            provider_id=defn["provider_id"],
            display_name=defn["display_name"],
            env_var=env_var,
            present=present,
            status=status,
            capabilities_unlocked=defn["capabilities_unlocked"],
            capabilities_blocked_without=defn["capabilities_blocked_without"],
            bryan_action=defn["bryan_action"],
            fallback_without=defn["fallback_without"],
            priority=defn["priority"],
        )
        providers.append(ps)
        if not present:
            for cap in defn["capabilities_blocked_without"]:
                blockers.append(BlockerRecord(
                    capability=cap,
                    blocker_type="BLOCKED_PROVIDER",
                    blocker_detail=f"{env_var} not configured.",
                    bryan_action=defn["bryan_action"],
                    fallback_behavior=defn["fallback_without"],
                ))

    # Add permanent safety blockers (always present regardless of keys)
    _SAFETY_BLOCKERS = [
        ("Auto-push / auto-merge", "BLOCKED_SAFETY",
         "Permanently blocked hard gate.", "No action — permanent.", "Manual git operations only."),
        ("Production deploy", "BLOCKED_SAFETY",
         "Permanently blocked hard gate.", "No action — permanent.", "No production deploys without explicit Bryan authorization."),
        ("Real external sends (Slack/email/Telegram)", "BLOCKED_SAFETY",
         "Permanently blocked hard gate.", "No action — permanent.", "Dry-run simulation only."),
        ("US13 voice activation", "BLOCKED_SAFETY",
         "US13 HOLD/UNSAFE/PARKED.", "Authorize Voice sprint + provide STT/TTS keys.", "Voice unavailable."),
    ]
    for cap, btype, detail, action, fallback in _SAFETY_BLOCKERS:
        blockers.append(BlockerRecord(
            capability=cap,
            blocker_type=btype,
            blocker_detail=detail,
            bryan_action=action,
            fallback_behavior=fallback,
        ))

    llm_status = "available" if any_available else "BLOCKED_PROVIDER"
    avail_count = sum(1 for p in providers if p.present)
    summary = (
        f"{avail_count}/{len(providers)} LLM providers configured. "
        f"{'Real LLM-in-loop available.' if any_available else 'All LLM providers BLOCKED_PROVIDER — dry-run planning only.'} "
        f"Cloud keys file: {'present' if _CLOUD_KEYS_PATH.exists() else 'missing'} "
        f"({_CLOUD_KEYS_PATH})."
    )

    return ProviderReadinessReport(
        providers=providers,
        blockers=blockers,
        any_llm_available=any_available,
        cloud_keys_file_exists=_CLOUD_KEYS_PATH.exists(),
        cloud_keys_file_path=str(_CLOUD_KEYS_PATH),
        llm_in_loop_status=llm_status,
        summary=summary,
    )


__all__ = [
    "ProviderStatus",
    "BlockerRecord",
    "ProviderReadinessReport",
    "get_provider_readiness",
]
