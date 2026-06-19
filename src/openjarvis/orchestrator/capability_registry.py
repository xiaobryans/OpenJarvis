"""Execution Capability Registry.

Classifies every Jarvis action by:
  - action_name: unique action identifier
  - capability_type: category (local_analysis, planning, coding, validation,
    governance, nus, communication, system)
  - risk_level: low | medium | high | blocked
  - approval_required: True if Bryan must explicitly approve before execution
  - rollback_support: none | plan_only | full
  - provider_key_required: list of env var keys required (empty = no provider needed)
  - current_status: available | blocked | planned | degraded
  - blocker: exact blocker classification if not available

Design rules:
  - No action is silently available without evidence.
  - Blocked actions report exact blocker type.
  - Provider-blocked actions require API keys; fallback is dry-run planning only.
  - US13 voice is permanently blocked_safety.
  - Dangerous actions are permanently blocked.
  - This registry is the ground truth for what Jarvis can execute.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_BLOCKED = "blocked"

ROLLBACK_NONE = "none"
ROLLBACK_PLAN_ONLY = "plan_only"
ROLLBACK_FULL = "full"

STATUS_AVAILABLE = "available"
STATUS_BLOCKED = "blocked"
STATUS_PLANNED = "planned"
STATUS_DEGRADED = "degraded"

# Blocker classification codes (matches JARVIS_COMPLETION_GAP_REGISTER.md)
BLOCKER_IMPLEMENTATION = "BLOCKED_IMPLEMENTATION"
BLOCKER_PROVIDER = "BLOCKED_PROVIDER"
BLOCKER_CREDENTIALS = "BLOCKED_CREDENTIALS"
BLOCKER_SAFETY = "BLOCKED_SAFETY"
BLOCKER_USER_AUTHORIZATION = "BLOCKED_USER_AUTHORIZATION"
BLOCKER_HARDWARE = "BLOCKED_HARDWARE"


# ---------------------------------------------------------------------------
# ExecutionCapabilityRecord
# ---------------------------------------------------------------------------

@dataclass
class ExecutionCapabilityRecord:
    """Single action capability record.

    Every action Jarvis can potentially perform must have one of these.
    """
    action_name: str
    capability_type: str
    risk_level: str
    approval_required: bool
    rollback_support: str
    provider_keys_required: List[str]
    current_status: str
    blocker: Optional[str] = None
    blocker_type: Optional[str] = None
    description: str = ""
    fallback_behavior: str = ""

    def is_available(self) -> bool:
        return self.current_status == STATUS_AVAILABLE

    def is_blocked(self) -> bool:
        return self.current_status == STATUS_BLOCKED

    def requires_provider(self) -> bool:
        return len(self.provider_keys_required) > 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_name": self.action_name,
            "capability_type": self.capability_type,
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "rollback_support": self.rollback_support,
            "provider_keys_required": self.provider_keys_required,
            "current_status": self.current_status,
            "blocker": self.blocker,
            "blocker_type": self.blocker_type,
            "description": self.description,
            "fallback_behavior": self.fallback_behavior,
        }


# ---------------------------------------------------------------------------
# ExecutionCapabilityRegistry
# ---------------------------------------------------------------------------

class ExecutionCapabilityRegistry:
    """Registry of all Jarvis execution capabilities.

    Usage:
        registry = get_capability_registry()
        rec = registry.get("local_file_read")
        if rec.is_available():
            ...
        summary = registry.get_status_summary()
    """

    def __init__(self) -> None:
        self._records: Dict[str, ExecutionCapabilityRecord] = {}
        self._build_registry()

    def _build_registry(self) -> None:
        """Populate the registry with all known Jarvis actions."""
        records = [
            # ----------------------------------------------------------------
            # Local analysis / read-only (no provider needed)
            # ----------------------------------------------------------------
            ExecutionCapabilityRecord(
                action_name="local_file_read",
                capability_type="local_analysis",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Read local files for analysis. No writes.",
                fallback_behavior="Always available for local repos.",
            ),
            ExecutionCapabilityRecord(
                action_name="local_analysis",
                capability_type="local_analysis",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Inspect targeted files only, keyword/pattern search.",
                fallback_behavior="Always available.",
            ),
            ExecutionCapabilityRecord(
                action_name="doctor_run",
                capability_type="validation",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Run Jarvis doctor checks (42+ checks, read-only).",
                fallback_behavior="Always available; returns not_configured for missing services.",
            ),
            ExecutionCapabilityRecord(
                action_name="local_validation",
                capability_type="validation",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Run local tests and type-checks (pytest, tsc).",
                fallback_behavior="Available if test runner installed.",
            ),
            ExecutionCapabilityRecord(
                action_name="nus_dry_run",
                capability_type="nus",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Read NUS learning store and generate scorecard. Dry-run only.",
                fallback_behavior="Degrades gracefully if NUS store empty.",
            ),
            ExecutionCapabilityRecord(
                action_name="routing_dry_run",
                capability_type="planning",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Plan task routing without executing. Returns ActivationPlan.",
                fallback_behavior="Always available.",
            ),
            ExecutionCapabilityRecord(
                action_name="policy_check",
                capability_type="governance",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Evaluate governance policy for a proposed action.",
                fallback_behavior="Always available; blocks unknown actions.",
            ),
            ExecutionCapabilityRecord(
                action_name="risk_assessment",
                capability_type="governance",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Classify action risk before execution.",
                fallback_behavior="Always available.",
            ),
            ExecutionCapabilityRecord(
                action_name="connector_dry_run",
                capability_type="local_analysis",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Simulate connector action without real send.",
                fallback_behavior="Dry-run only; no external side effects.",
            ),
            # ----------------------------------------------------------------
            # Coding / file mutation (local, no external provider for safe subset)
            # ----------------------------------------------------------------
            ExecutionCapabilityRecord(
                action_name="coding_task_classify",
                capability_type="coding",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Classify a coding task (safe vs unsafe, complexity, scope).",
                fallback_behavior="Keyword-based classification; no LLM required.",
            ),
            ExecutionCapabilityRecord(
                action_name="coding_file_inspect",
                capability_type="coding",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Inspect targeted files for a coding task (read-only).",
                fallback_behavior="Always available for local repos.",
            ),
            ExecutionCapabilityRecord(
                action_name="coding_patch_propose",
                capability_type="coding",
                risk_level=RISK_MEDIUM,
                approval_required=True,
                rollback_support=ROLLBACK_PLAN_ONLY,
                provider_keys_required=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
                current_status=STATUS_DEGRADED,
                blocker="No LLM provider configured for code generation. Structured dry-run plan available.",
                blocker_type=BLOCKER_PROVIDER,
                description="Propose safe patch for a coding task. Requires LLM for generation; Bryan approves before write.",
                fallback_behavior="Without LLM: dry-run plan with file targets only. With LLM: full diff proposed.",
            ),
            ExecutionCapabilityRecord(
                action_name="coding_test_run",
                capability_type="coding",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Run targeted tests after a coding change.",
                fallback_behavior="Available if pytest installed.",
            ),
            ExecutionCapabilityRecord(
                action_name="coding_diff_report",
                capability_type="coding",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Report diff and evidence for a proposed or applied change.",
                fallback_behavior="Always available (git diff).",
            ),
            ExecutionCapabilityRecord(
                action_name="coding_repair_loop",
                capability_type="coding",
                risk_level=RISK_MEDIUM,
                approval_required=False,
                rollback_support=ROLLBACK_PLAN_ONLY,
                provider_keys_required=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
                current_status=STATUS_DEGRADED,
                blocker="Repair loop requires LLM for re-generation. Bounded retry without LLM = limited.",
                blocker_type=BLOCKER_PROVIDER,
                description="Retry failed coding change up to 3 times with different approach.",
                fallback_behavior="Without LLM: re-run tests only. With LLM: re-generate patch.",
            ),
            ExecutionCapabilityRecord(
                action_name="coding_rollback",
                capability_type="coding",
                risk_level=RISK_LOW,
                approval_required=True,
                rollback_support=ROLLBACK_FULL,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Rollback a coding change via git checkout/restore.",
                fallback_behavior="Always available if git initialized.",
            ),
            # ----------------------------------------------------------------
            # NUS / learning
            # ----------------------------------------------------------------
            ExecutionCapabilityRecord(
                action_name="nus_feedback_read",
                capability_type="nus",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Read NUS scorecard and failure patterns for activation decisions.",
                fallback_behavior="Graceful degradation if NUS store empty.",
            ),
            ExecutionCapabilityRecord(
                action_name="nus_outcome_record",
                capability_type="nus",
                risk_level=RISK_LOW,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_AVAILABLE,
                description="Record task outcome to NUS learning store.",
                fallback_behavior="No-op if store unavailable.",
            ),
            # ----------------------------------------------------------------
            # LLM-gated actions
            # ----------------------------------------------------------------
            ExecutionCapabilityRecord(
                action_name="llm_orchestration_openai",
                capability_type="planning",
                risk_level=RISK_MEDIUM,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=["OPENAI_API_KEY"],
                current_status=STATUS_BLOCKED,
                blocker="OPENAI_API_KEY not configured. Set in ~/.jarvis/cloud-keys.env.",
                blocker_type=BLOCKER_PROVIDER,
                description="Use GPT-4 for LLM-reviewed orchestration decisions.",
                fallback_behavior="Dry-run keyword-based planning without LLM review.",
            ),
            ExecutionCapabilityRecord(
                action_name="llm_orchestration_anthropic",
                capability_type="planning",
                risk_level=RISK_MEDIUM,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=["ANTHROPIC_API_KEY"],
                current_status=STATUS_BLOCKED,
                blocker="ANTHROPIC_API_KEY not configured. Set in ~/.jarvis/cloud-keys.env.",
                blocker_type=BLOCKER_PROVIDER,
                description="Use Claude for LLM-reviewed orchestration decisions.",
                fallback_behavior="Dry-run keyword-based planning without LLM review.",
            ),
            ExecutionCapabilityRecord(
                action_name="llm_orchestration_openrouter",
                capability_type="planning",
                risk_level=RISK_MEDIUM,
                approval_required=False,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=["OPENROUTER_API_KEY"],
                current_status=STATUS_BLOCKED,
                blocker="OPENROUTER_API_KEY not configured. Set in ~/.jarvis/cloud-keys.env.",
                blocker_type=BLOCKER_PROVIDER,
                description="Use OpenRouter for multi-model routing.",
                fallback_behavior="Dry-run planning only.",
            ),
            # ----------------------------------------------------------------
            # Permanently blocked (hard gates)
            # ----------------------------------------------------------------
            ExecutionCapabilityRecord(
                action_name="auto_push",
                capability_type="governance",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker="Permanently blocked. No auto-push without explicit Bryan authorization.",
                blocker_type=BLOCKER_SAFETY,
                description="Automatic git push. PERMANENTLY BLOCKED.",
                fallback_behavior="Never executed. Requires explicit human git push.",
            ),
            ExecutionCapabilityRecord(
                action_name="auto_merge",
                capability_type="governance",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker="Permanently blocked.",
                blocker_type=BLOCKER_SAFETY,
                description="Automatic git merge. PERMANENTLY BLOCKED.",
                fallback_behavior="Never executed.",
            ),
            ExecutionCapabilityRecord(
                action_name="production_deploy",
                capability_type="governance",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker="Permanently blocked.",
                blocker_type=BLOCKER_SAFETY,
                description="Production deployment (AWS/Vercel/Supabase). PERMANENTLY BLOCKED.",
                fallback_behavior="Never executed without explicit Bryan authorization.",
            ),
            ExecutionCapabilityRecord(
                action_name="external_send",
                capability_type="governance",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker="Permanently blocked. No real Slack/email/Telegram sends.",
                blocker_type=BLOCKER_SAFETY,
                description="Real outbound send (Slack, email, Telegram). PERMANENTLY BLOCKED.",
                fallback_behavior="Dry-run simulation only.",
            ),
            ExecutionCapabilityRecord(
                action_name="secret_access",
                capability_type="governance",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker="Permanently blocked.",
                blocker_type=BLOCKER_SAFETY,
                description="Access live secrets or credentials. PERMANENTLY BLOCKED.",
                fallback_behavior="Never executed.",
            ),
            ExecutionCapabilityRecord(
                action_name="us13_voice",
                capability_type="governance",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker="US13 HOLD/UNSAFE/PARKED. Multiple implementation blockers.",
                blocker_type=BLOCKER_SAFETY,
                description="Voice activation (US13). HOLD/UNSAFE/PARKED.",
                fallback_behavior="Never activated without explicit Bryan reopen authorization.",
            ),
        ]
        for rec in records:
            self._records[rec.action_name] = rec

    def get(self, action_name: str) -> Optional[ExecutionCapabilityRecord]:
        """Return capability record for the given action, or None if unknown."""
        return self._records.get(action_name)

    def get_or_blocked(self, action_name: str) -> ExecutionCapabilityRecord:
        """Return record; if action unknown, return a blocked unknown record."""
        rec = self._records.get(action_name)
        if rec is None:
            return ExecutionCapabilityRecord(
                action_name=action_name,
                capability_type="unknown",
                risk_level=RISK_BLOCKED,
                approval_required=True,
                rollback_support=ROLLBACK_NONE,
                provider_keys_required=[],
                current_status=STATUS_BLOCKED,
                blocker=f"Action '{action_name}' not registered in capability registry.",
                blocker_type=BLOCKER_IMPLEMENTATION,
                description="Unknown action.",
                fallback_behavior="Refused until registered.",
            )
        return rec

    def all_available(self) -> List[ExecutionCapabilityRecord]:
        """Return all available (non-blocked) capabilities."""
        return [r for r in self._records.values() if r.is_available()]

    def all_blocked(self) -> List[ExecutionCapabilityRecord]:
        """Return all permanently or currently blocked capabilities."""
        return [r for r in self._records.values() if r.is_blocked()]

    def all_by_type(self, capability_type: str) -> List[ExecutionCapabilityRecord]:
        """Return all capabilities of a given type."""
        return [r for r in self._records.values() if r.capability_type == capability_type]

    def requires_provider(self, action_name: str) -> bool:
        """True if action requires a provider API key."""
        rec = self._records.get(action_name)
        return rec.requires_provider() if rec else False

    def check_provider_status(self) -> Dict[str, Any]:
        """Check which provider-gated capabilities are blocked vs available."""
        import os
        provider_status: Dict[str, Any] = {}
        key_env_vars = {
            "OPENAI_API_KEY": "openai",
            "ANTHROPIC_API_KEY": "anthropic",
            "OPENROUTER_API_KEY": "openrouter",
        }
        for env_var, provider_name in key_env_vars.items():
            cloud_keys_path = os.path.expanduser("~/.jarvis/cloud-keys.env")
            present = bool(os.environ.get(env_var))
            if not present and os.path.exists(cloud_keys_path):
                with open(cloud_keys_path) as f:
                    for line in f:
                        if line.strip().startswith(f"{env_var}="):
                            present = bool(line.strip()[len(env_var) + 1:])
                            break
            provider_status[provider_name] = {
                "env_var": env_var,
                "present": present,
                "status": "available" if present else "BLOCKED_PROVIDER",
            }
        return provider_status

    def get_status_summary(self) -> Dict[str, Any]:
        """Return a summary of all capabilities grouped by status."""
        available = [r.action_name for r in self._records.values() if r.is_available()]
        blocked = [
            {"action": r.action_name, "blocker_type": r.blocker_type, "blocker": r.blocker}
            for r in self._records.values() if r.is_blocked()
        ]
        degraded = [
            {"action": r.action_name, "blocker": r.blocker}
            for r in self._records.values()
            if r.current_status == STATUS_DEGRADED
        ]
        planned = [
            r.action_name for r in self._records.values()
            if r.current_status == STATUS_PLANNED
        ]
        provider_status = self.check_provider_status()
        return {
            "total_actions": len(self._records),
            "available_count": len(available),
            "blocked_count": len(blocked),
            "degraded_count": len(degraded),
            "planned_count": len(planned),
            "available_actions": available,
            "blocked_actions": blocked,
            "degraded_actions": degraded,
            "planned_actions": planned,
            "provider_status": provider_status,
        }

    def get_blockers_for_daily_driver(self) -> List[Dict[str, Any]]:
        """Return the exact blockers that prevent daily-driver 4/5 execution."""
        blockers = []
        for rec in self._records.values():
            if rec.is_blocked() and rec.blocker_type != BLOCKER_SAFETY:
                blockers.append({
                    "action": rec.action_name,
                    "blocker_type": rec.blocker_type,
                    "blocker": rec.blocker,
                    "fallback_behavior": rec.fallback_behavior,
                })
            elif rec.current_status == STATUS_DEGRADED:
                blockers.append({
                    "action": rec.action_name,
                    "blocker_type": rec.blocker_type,
                    "blocker": rec.blocker,
                    "fallback_behavior": rec.fallback_behavior,
                    "degraded": True,
                })
        return blockers


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: Optional[ExecutionCapabilityRegistry] = None


def get_capability_registry() -> ExecutionCapabilityRegistry:
    """Return the module-level ExecutionCapabilityRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = ExecutionCapabilityRegistry()
    return _registry


__all__ = [
    "ExecutionCapabilityRecord",
    "ExecutionCapabilityRegistry",
    "get_capability_registry",
    "RISK_LOW", "RISK_MEDIUM", "RISK_HIGH", "RISK_BLOCKED",
    "ROLLBACK_NONE", "ROLLBACK_PLAN_ONLY", "ROLLBACK_FULL",
    "STATUS_AVAILABLE", "STATUS_BLOCKED", "STATUS_PLANNED", "STATUS_DEGRADED",
    "BLOCKER_IMPLEMENTATION", "BLOCKER_PROVIDER", "BLOCKER_CREDENTIALS",
    "BLOCKER_SAFETY", "BLOCKER_USER_AUTHORIZATION", "BLOCKER_HARDWARE",
]
