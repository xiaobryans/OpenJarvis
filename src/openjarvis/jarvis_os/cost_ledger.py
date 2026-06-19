"""Jarvis OS Cost/Token Ledger — role-aware cost tracking for all pipeline runs.

Tracks:
  - Token/cost estimates per task and per role
  - Model/provider used (estimated if unavailable)
  - Role: Jarvis/COS/GM/manager/worker/verifier
  - Cache hit/miss (cache hits reduce cost)
  - Retries and rework
  - Wasted-token indicators
  - Expensive task warnings and approval requirements

Rules:
  - Do not fake provider costs if unavailable; mark as [ESTIMATE] clearly.
  - Real token counts require actual LLM response metadata.
  - If metadata unavailable, record as estimate with zero confidence.
  - Expensive task threshold: > $0.10 per pipeline run.
  - Approval required for tasks exceeding expensive_threshold_usd.

Sprint: Full No-Gap Jarvis — Combined Sprint 3 FINAL HOLD Correction
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Approximate cost tiers (USD per 1K tokens, blended estimate — NOT verified live)
_MODEL_COST_TIERS: Dict[str, float] = {
    "local": 0.0,
    "composer-2.5-fast": 0.0002,
    "sonnet-4.6": 0.003,
    "opus-4.7": 0.015,
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.0025,
    "claude-haiku": 0.00025,
    "claude-sonnet": 0.003,
    "gemini-flash": 0.00015,
    "unknown": 0.001,    # conservative unknown estimate
}

EXPENSIVE_THRESHOLD_USD = 0.10   # flag tasks exceeding this


# ---------------------------------------------------------------------------
# Ledger entry
# ---------------------------------------------------------------------------

@dataclass
class CostEntry:
    entry_id: str
    task_id: str
    role_id: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    is_estimate: bool
    cache_hit: bool
    retry_count: int
    rework_tokens: int
    provider: str
    description: str
    created_at: float = field(default_factory=time.time)
    wasted_tokens: int = 0
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "task_id": self.task_id,
            "role_id": self.role_id,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "is_estimate": self.is_estimate,
            "cost_label": "[ESTIMATE]" if self.is_estimate else "[VERIFIED]",
            "cache_hit": self.cache_hit,
            "retry_count": self.retry_count,
            "rework_tokens": self.rework_tokens,
            "provider": self.provider,
            "description": self.description,
            "wasted_tokens": self.wasted_tokens,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Cost Ledger
# ---------------------------------------------------------------------------

class JarvisCostLedger:
    """Role-aware cost/token ledger for all Jarvis pipeline runs.

    Callers should record entries for each role that executes.
    All cost figures without real token metadata are marked [ESTIMATE].
    """

    def __init__(self) -> None:
        self._entries: List[CostEntry] = []

    def record(
        self,
        task_id: str,
        role_id: str,
        *,
        model: str = "unknown",
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: Optional[float] = None,
        is_estimate: bool = True,
        cache_hit: bool = False,
        retry_count: int = 0,
        rework_tokens: int = 0,
        provider: str = "unknown",
        description: str = "",
    ) -> CostEntry:
        """Record a cost entry. If cost_usd not provided, estimate from token tier."""
        tier_rate = _MODEL_COST_TIERS.get(model.lower(), _MODEL_COST_TIERS["unknown"])
        total_tokens = input_tokens + output_tokens
        estimated_cost = cost_usd if cost_usd is not None else (total_tokens / 1000) * tier_rate

        requires_approval = estimated_cost > EXPENSIVE_THRESHOLD_USD

        entry = CostEntry(
            entry_id=str(uuid.uuid4())[:8],
            task_id=task_id,
            role_id=role_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimated_cost,
            is_estimate=is_estimate or cost_usd is None,
            cache_hit=cache_hit,
            retry_count=retry_count,
            rework_tokens=rework_tokens,
            provider=provider,
            description=description,
            wasted_tokens=rework_tokens,
            requires_approval=requires_approval,
        )
        self._entries.append(entry)
        return entry

    def get_task_summary(self, task_id: str) -> Dict[str, Any]:
        task_entries = [e for e in self._entries if e.task_id == task_id]
        total_cost = sum(e.cost_usd for e in task_entries)
        total_tokens = sum(e.input_tokens + e.output_tokens for e in task_entries)
        cache_hits = sum(1 for e in task_entries if e.cache_hit)
        retries = sum(e.retry_count for e in task_entries)
        requires_approval = total_cost > EXPENSIVE_THRESHOLD_USD

        return {
            "task_id": task_id,
            "total_cost_usd": round(total_cost, 6),
            "total_tokens": total_tokens,
            "cache_hits": cache_hits,
            "total_retries": retries,
            "requires_approval": requires_approval,
            "expensive_warning": (
                f"Task cost {total_cost:.4f} USD exceeds threshold {EXPENSIVE_THRESHOLD_USD} USD"
                if requires_approval else None
            ),
            "all_estimates": all(e.is_estimate for e in task_entries),
            "entries": [e.to_dict() for e in task_entries],
        }

    def get_role_summary(self, role_id: str) -> Dict[str, Any]:
        role_entries = [e for e in self._entries if e.role_id == role_id]
        return {
            "role_id": role_id,
            "total_cost_usd": round(sum(e.cost_usd for e in role_entries), 6),
            "total_tokens": sum(e.input_tokens + e.output_tokens for e in role_entries),
            "cache_hits": sum(1 for e in role_entries if e.cache_hit),
            "entry_count": len(role_entries),
        }

    def get_dashboard(self) -> Dict[str, Any]:
        """Return full cost dashboard — callable from route/doctor."""
        total_cost = sum(e.cost_usd for e in self._entries)
        roles_used = list({e.role_id for e in self._entries})
        any_expensive = any(e.requires_approval for e in self._entries)

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_entries": len(self._entries),
            "roles_tracked": roles_used,
            "expensive_tasks": [e.task_id for e in self._entries if e.requires_approval],
            "expensive_warning": any_expensive,
            "approval_required_for_expensive": True,
            "all_cost_labels": "[ESTIMATE]" if all(e.is_estimate for e in self._entries) else "MIXED",
            "by_role": {
                role: self.get_role_summary(role)["total_cost_usd"]
                for role in roles_used
            },
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_LEDGER: Optional[JarvisCostLedger] = None


def get_cost_ledger() -> JarvisCostLedger:
    global _LEDGER
    if _LEDGER is None:
        _LEDGER = JarvisCostLedger()
    return _LEDGER


__all__ = [
    "CostEntry",
    "JarvisCostLedger",
    "EXPENSIVE_THRESHOLD_USD",
    "get_cost_ledger",
]
