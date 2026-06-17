"""ModelRouter — configurable tiered model routing for Jarvis Coding Workbench.

Tiers
-----
  local        Zero cost. Direct tool execution, git CLI, grep. No external calls.
  cheap        Low-cost cloud models: DeepSeek-Chat, Qwen-72B, Gemini-Flash.
  mid          Mid-tier: GPT-4o-mini, Claude-Haiku, Gemini-Pro.
  premium      High-trust: Claude-Opus, GPT-4o, Claude-Sonnet.

Routing Policy
--------------
  Read-only (git status/diff/log, file_read, file_search)   → local
  Simple file ops, analysis, search                         → cheap
  Ordinary implementation, debugging, tests                 → mid
  Architecture, security, final review, risky recovery      → premium
  Explicit high_trust flag                                  → premium

Budget Caps
-----------
  Configured via env or BudgetConfig.
  daily_premium_cap_usd:   max premium spend per calendar day (default $1.00)
  session_premium_cap_usd: max premium spend per session (default $0.50)
  When cap exceeded → auto-downgrade to mid or HOLD.
  Bryan explicit approval required to override.

Escalation Loop
---------------
  1. cheap/local worker attempts task.
  2. If validation fails or terminal error → escalation decision:
      a. retry with same tier (transient)
      b. escalate to premium (complex failure)
      c. HOLD (budget exceeded or unsafe)
  3. Reason logged to routing_log.

Provider Config
---------------
  Configured via environment variables (no secrets hardcoded):
    JARVIS_CHEAP_MODEL      default "deepseek/deepseek-chat"
    JARVIS_MID_MODEL        default "openai/gpt-4o-mini"
    JARVIS_PREMIUM_MODEL    default "anthropic/claude-opus-4-5"
    JARVIS_OPENROUTER_KEY   OpenRouter API key (optional)
    JARVIS_DAILY_PREMIUM_CAP  float, USD
    JARVIS_SESSION_PREMIUM_CAP float, USD
    JARVIS_MODEL_ADAPTER    "mock" | "openrouter" | "ollama" | "local"

No secrets are hardcoded, printed, logged, or committed.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".openjarvis" / "model_routing.db"


# ---------------------------------------------------------------------------
# Tiers and routing constants
# ---------------------------------------------------------------------------


class ModelTier(str, Enum):
    LOCAL = "local"
    CHEAP = "cheap"
    MID = "mid"
    PREMIUM = "premium"


# Tool routing policy: tool_id → minimum tier
_TOOL_TIER_POLICY: Dict[str, ModelTier] = {
    "git_status":   ModelTier.LOCAL,
    "git_diff":     ModelTier.LOCAL,
    "git_log":      ModelTier.LOCAL,
    "git_branch":   ModelTier.LOCAL,
    "file_read":    ModelTier.LOCAL,
    "file_search":  ModelTier.LOCAL,
    "file_write":   ModelTier.CHEAP,
    "shell_exec":   ModelTier.CHEAP,
    "git_commit":   ModelTier.PREMIUM,
    "git_push":     ModelTier.PREMIUM,
    "file_delete":  ModelTier.PREMIUM,
}

# Task category → tier
_TASK_CATEGORY_TIERS: Dict[str, ModelTier] = {
    "read_only":      ModelTier.LOCAL,
    "search":         ModelTier.LOCAL,
    "analysis":       ModelTier.CHEAP,
    "file_edit":      ModelTier.CHEAP,
    "debugging":      ModelTier.MID,
    "implementation": ModelTier.MID,
    "test_writing":   ModelTier.MID,
    "architecture":   ModelTier.PREMIUM,
    "security":       ModelTier.PREMIUM,
    "final_review":   ModelTier.PREMIUM,
    "risky_recovery": ModelTier.PREMIUM,
}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class BudgetConfig:
    """Budget caps — all values in USD."""

    daily_premium_cap_usd: float = 1.00
    session_premium_cap_usd: float = 0.50
    daily_mid_cap_usd: float = 2.00
    session_mid_cap_usd: float = 1.00

    @classmethod
    def from_env(cls) -> "BudgetConfig":
        return cls(
            daily_premium_cap_usd=float(os.environ.get("JARVIS_DAILY_PREMIUM_CAP", "1.00")),
            session_premium_cap_usd=float(os.environ.get("JARVIS_SESSION_PREMIUM_CAP", "0.50")),
            daily_mid_cap_usd=float(os.environ.get("JARVIS_DAILY_MID_CAP", "2.00")),
            session_mid_cap_usd=float(os.environ.get("JARVIS_SESSION_MID_CAP", "1.00")),
        )


@dataclass
class ProviderConfig:
    """Provider config loaded from env — no secrets hardcoded."""

    cheap_model: str = "deepseek/deepseek-chat"
    mid_model: str = "openai/gpt-4o-mini"
    premium_model: str = "anthropic/claude-opus-4-5"
    adapter: str = "mock"  # "mock" | "openrouter" | "ollama" | "local"
    # API key fetched from env at call time — never stored in code or logs
    _openrouter_key_env: str = "JARVIS_OPENROUTER_KEY"

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        return cls(
            cheap_model=os.environ.get("JARVIS_CHEAP_MODEL", "deepseek/deepseek-chat"),
            mid_model=os.environ.get("JARVIS_MID_MODEL", "openai/gpt-4o-mini"),
            premium_model=os.environ.get("JARVIS_PREMIUM_MODEL", "anthropic/claude-opus-4-5"),
            adapter=os.environ.get("JARVIS_MODEL_ADAPTER", "mock"),
        )

    def model_for_tier(self, tier: ModelTier) -> str:
        if tier == ModelTier.LOCAL:
            return "local"
        if tier == ModelTier.CHEAP:
            return self.cheap_model
        if tier == ModelTier.MID:
            return self.mid_model
        return self.premium_model

    def __repr__(self) -> str:
        return (
            f"ProviderConfig(adapter={self.adapter!r}, "
            f"cheap_model={self.cheap_model!r}, mid_model={self.mid_model!r}, "
            f"premium_model={self.premium_model!r})"
        )

    @property
    def openrouter_key(self) -> str:
        """Read API key from env at call time. Never stored in instance fields."""
        return os.environ.get(self._openrouter_key_env, "")


# ---------------------------------------------------------------------------
# Routing decision
# ---------------------------------------------------------------------------


@dataclass
class RoutingDecision:
    subtask_id: str
    tool_id: str
    assigned_tier: ModelTier
    assigned_model: str
    reason: str
    session_id: str
    task_id: str
    created_at: float = field(default_factory=time.time)
    escalation_from: Optional[ModelTier] = None
    budget_check: str = "ok"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "tool_id": self.tool_id,
            "assigned_tier": self.assigned_tier.value,
            "assigned_model": self.assigned_model,
            "reason": self.reason,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "created_at": self.created_at,
            "escalation_from": self.escalation_from.value if self.escalation_from else None,
            "budget_check": self.budget_check,
        }


# ---------------------------------------------------------------------------
# Model adapter protocol + implementations
# ---------------------------------------------------------------------------


class ModelAdapter(Protocol):
    """Protocol for model adapters."""

    def call(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Call model. Returns {content, input_tokens, output_tokens, cost_usd}."""
        ...


class MockModelAdapter:
    """Dry-run/mock adapter — never makes real API calls. Used in tests."""

    def call(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        input_tokens = len(prompt.split())
        output_tokens = min(max_tokens, 20)
        return {
            "content": f"[MOCK:{model}] Task acknowledged. Dry-run response.",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": 0.0,
            "model": model,
            "adapter": "mock",
        }


class OpenRouterAdapter:
    """OpenRouter adapter — reads key from env at call time, never stores it."""

    def call(
        self,
        model: str,
        prompt: str,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        import os
        api_key = os.environ.get("JARVIS_OPENROUTER_KEY", "")
        if not api_key:
            return {
                "content": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "model": model,
                "adapter": "openrouter",
                "error": "JARVIS_OPENROUTER_KEY not set — model call skipped",
            }
        try:
            import urllib.request
            import json as _json
            payload = _json.dumps({
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            }).encode()
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://openjarvis.ai",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = _json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return {
                "content": content,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "cost_usd": 0.0,
                "model": model,
                "adapter": "openrouter",
            }
        except Exception as exc:
            logger.warning("OpenRouter call failed: %s", exc)
            return {
                "content": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "model": model,
                "adapter": "openrouter",
                "error": str(exc),
            }


def _make_adapter(adapter_name: str) -> ModelAdapter:
    if adapter_name == "openrouter":
        return OpenRouterAdapter()
    return MockModelAdapter()


# ---------------------------------------------------------------------------
# EscalationDecision
# ---------------------------------------------------------------------------


class EscalationAction(str, Enum):
    RETRY_SAME = "retry_same"
    ESCALATE = "escalate"
    HOLD = "hold"


@dataclass
class EscalationDecision:
    action: EscalationAction
    reason: str
    new_tier: Optional[ModelTier] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "new_tier": self.new_tier.value if self.new_tier else None,
        }


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------


class ModelRouter:
    """Configurable tiered model router for Jarvis Coding Workbench.

    Usage::

        router = ModelRouter.from_env()
        decision = router.route(
            subtask_id="abc",
            tool_id="file_write",
            description="Write fixture file",
            session_id="s1",
            task_id="t1",
        )
        result = router.call_model(decision, prompt="Write foo.py content...")
    """

    def __init__(
        self,
        provider_config: Optional[ProviderConfig] = None,
        budget_config: Optional[BudgetConfig] = None,
        db_path: Optional[str] = None,
        adapter_override: Optional[ModelAdapter] = None,
    ) -> None:
        self._provider = provider_config or ProviderConfig.from_env()
        self._budget = budget_config or BudgetConfig.from_env()
        db = Path(db_path) if db_path else _DEFAULT_DB
        db.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._adapter = adapter_override or _make_adapter(self._provider.adapter)

    @classmethod
    def from_env(
        cls,
        db_path: Optional[str] = None,
        adapter_override: Optional[ModelAdapter] = None,
    ) -> "ModelRouter":
        return cls(
            provider_config=ProviderConfig.from_env(),
            budget_config=BudgetConfig.from_env(),
            db_path=db_path,
            adapter_override=adapter_override,
        )

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS routing_log (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                subtask_id TEXT NOT NULL,
                tool_id TEXT NOT NULL,
                assigned_tier TEXT NOT NULL,
                assigned_model TEXT NOT NULL,
                reason TEXT NOT NULL,
                escalation_from TEXT,
                budget_check TEXT NOT NULL DEFAULT 'ok',
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_routing_session ON routing_log (session_id);
            CREATE INDEX IF NOT EXISTS idx_routing_task ON routing_log (task_id);

            CREATE TABLE IF NOT EXISTS model_call_log (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                subtask_id TEXT NOT NULL,
                model TEXT NOT NULL,
                tier TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_usd REAL NOT NULL DEFAULT 0.0,
                success INTEGER NOT NULL DEFAULT 1,
                error TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_call_session ON model_call_log (session_id);
            CREATE INDEX IF NOT EXISTS idx_call_task ON model_call_log (task_id);
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route(
        self,
        subtask_id: str,
        tool_id: str,
        description: str,
        session_id: str,
        task_id: str,
        high_trust: bool = False,
        category: Optional[str] = None,
        escalation_from: Optional[ModelTier] = None,
    ) -> RoutingDecision:
        """Assign a model tier to a subtask and log the decision."""
        tier, reason = self._decide_tier(
            tool_id=tool_id,
            description=description,
            high_trust=high_trust,
            category=category,
            escalation_from=escalation_from,
        )

        # Budget check
        budget_check, tier = self._apply_budget_cap(tier, session_id, task_id)
        if budget_check != "ok":
            reason = f"{reason} | BUDGET: {budget_check}"

        model = self._provider.model_for_tier(tier)
        decision = RoutingDecision(
            subtask_id=subtask_id,
            tool_id=tool_id,
            assigned_tier=tier,
            assigned_model=model,
            reason=reason,
            session_id=session_id,
            task_id=task_id,
            escalation_from=escalation_from,
            budget_check=budget_check,
        )
        self._log_routing(decision)
        logger.info(
            "ROUTE: subtask=%s tool=%s tier=%s model=%s reason=%s",
            subtask_id[:8], tool_id, tier.value, model, reason,
        )
        return decision

    def _decide_tier(
        self,
        tool_id: str,
        description: str,
        high_trust: bool,
        category: Optional[str],
        escalation_from: Optional[ModelTier],
    ) -> tuple[ModelTier, str]:
        """Return (tier, reason) for a subtask.

        Priority (highest first):
          1. high_trust flag
          2. escalation_from
          3. explicit category
          4. description heuristics
          5. tool_id policy
          6. default cheap
        """
        if high_trust:
            return ModelTier.PREMIUM, "high_trust=True: explicitly requested premium"

        # Escalation — bump one tier up
        if escalation_from is not None:
            escalated = _escalate_tier(escalation_from)
            return escalated, f"escalation from {escalation_from.value} after failure"

        # Category-based policy (explicit override takes precedence over tool)
        if category and category in _TASK_CATEGORY_TIERS:
            tier = _TASK_CATEGORY_TIERS[category]
            return tier, f"category_policy: {category} → {tier.value}"

        # Description heuristics (checked before tool policy so context can escalate)
        desc_lower = description.lower()
        if any(w in desc_lower for w in ("architect", "security", "final review", "complex", "critical")):
            return ModelTier.PREMIUM, "description_heuristic: premium keywords"
        if any(w in desc_lower for w in ("debug", "implement", "test", "fix")):
            return ModelTier.MID, "description_heuristic: mid-tier keywords"
        if any(w in desc_lower for w in ("read", "search", "inspect", "list", "status", "diff", "log")):
            return ModelTier.LOCAL, "description_heuristic: read-only keywords"

        # Tool-based policy
        if tool_id in _TOOL_TIER_POLICY:
            tier = _TOOL_TIER_POLICY[tool_id]
            return tier, f"tool_policy: {tool_id} → {tier.value}"

        return ModelTier.CHEAP, "default: cheap tier"

    def _apply_budget_cap(
        self,
        tier: ModelTier,
        session_id: str,
        task_id: str,
    ) -> tuple[str, ModelTier]:
        """Check budget caps. Returns (budget_check_status, effective_tier)."""
        if tier not in (ModelTier.PREMIUM, ModelTier.MID):
            return "ok", tier

        if tier == ModelTier.PREMIUM:
            session_spent = self._session_spent(session_id, ModelTier.PREMIUM)
            daily_spent = self._daily_spent(ModelTier.PREMIUM)

            if session_spent >= self._budget.session_premium_cap_usd:
                logger.warning(
                    "BUDGET CAP: premium session cap $%.2f reached (spent $%.4f) — downgrading to mid",
                    self._budget.session_premium_cap_usd, session_spent,
                )
                return f"premium_session_cap_exceeded(${session_spent:.4f}>=${self._budget.session_premium_cap_usd:.2f})", ModelTier.MID

            if daily_spent >= self._budget.daily_premium_cap_usd:
                logger.warning(
                    "BUDGET CAP: premium daily cap $%.2f reached (spent $%.4f) — downgrading to mid",
                    self._budget.daily_premium_cap_usd, daily_spent,
                )
                return f"premium_daily_cap_exceeded(${daily_spent:.4f}>=${self._budget.daily_premium_cap_usd:.2f})", ModelTier.MID

        if tier == ModelTier.MID:
            session_spent = self._session_spent(session_id, ModelTier.MID)
            daily_spent = self._daily_spent(ModelTier.MID)

            if session_spent >= self._budget.session_mid_cap_usd:
                logger.warning(
                    "BUDGET CAP: mid session cap $%.2f reached (spent $%.4f) — downgrading to cheap",
                    self._budget.session_mid_cap_usd, session_spent,
                )
                return f"mid_session_cap_exceeded(${session_spent:.4f}>=${self._budget.session_mid_cap_usd:.2f})", ModelTier.CHEAP

            if daily_spent >= self._budget.daily_mid_cap_usd:
                return f"mid_daily_cap_exceeded(${daily_spent:.4f}>=${self._budget.daily_mid_cap_usd:.2f})", ModelTier.CHEAP

        return "ok", tier

    def _session_spent(self, session_id: str, tier: ModelTier) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) AS total FROM model_call_log WHERE session_id=? AND tier=?",
            (session_id, tier.value),
        ).fetchone()
        return float(row["total"])

    def _daily_spent(self, tier: ModelTier) -> float:
        day_start = time.time() - (time.time() % 86400)
        row = self._conn.execute(
            "SELECT COALESCE(SUM(cost_usd),0) AS total FROM model_call_log WHERE tier=? AND created_at>=?",
            (tier.value, day_start),
        ).fetchone()
        return float(row["total"])

    def _log_routing(self, d: RoutingDecision) -> None:
        entry_id = uuid.uuid4().hex[:16]
        self._conn.execute(
            """INSERT INTO routing_log
               (id, session_id, task_id, subtask_id, tool_id, assigned_tier,
                assigned_model, reason, escalation_from, budget_check, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, d.session_id, d.task_id, d.subtask_id, d.tool_id,
             d.assigned_tier.value, d.assigned_model, d.reason,
             d.escalation_from.value if d.escalation_from else None,
             d.budget_check, d.created_at),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Model calls
    # ------------------------------------------------------------------

    def call_model(
        self,
        decision: RoutingDecision,
        prompt: str,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """Call the assigned model and log token/cost usage."""
        if decision.assigned_tier == ModelTier.LOCAL:
            return {
                "content": "[LOCAL] No model call — handled by direct tool execution.",
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "model": "local",
                "adapter": "local",
            }

        result = self._adapter.call(
            model=decision.assigned_model,
            prompt=prompt,
            max_tokens=max_tokens,
        )
        self._log_call(decision, result)
        return result

    def _log_call(self, decision: RoutingDecision, result: Dict[str, Any]) -> None:
        entry_id = uuid.uuid4().hex[:16]
        self._conn.execute(
            """INSERT INTO model_call_log
               (id, session_id, task_id, subtask_id, model, tier,
                input_tokens, output_tokens, cost_usd, success, error, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entry_id, decision.session_id, decision.task_id, decision.subtask_id,
             decision.assigned_model, decision.assigned_tier.value,
             result.get("input_tokens", 0), result.get("output_tokens", 0),
             result.get("cost_usd", 0.0),
             0 if result.get("error") else 1,
             result.get("error"),
             time.time()),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Escalation loop
    # ------------------------------------------------------------------

    def decide_escalation(
        self,
        decision: RoutingDecision,
        error: str,
        attempt: int = 1,
    ) -> EscalationDecision:
        """Decide what to do after a task failure at the given tier."""
        tier = decision.assigned_tier

        # Check if at premium already → HOLD
        if tier == ModelTier.PREMIUM:
            return EscalationDecision(
                action=EscalationAction.HOLD,
                reason=f"Already at premium tier. Error: {error[:80]}. Cannot escalate further.",
            )

        # Check premium budget before escalating
        session_spent = self._session_spent(decision.session_id, ModelTier.PREMIUM)
        if session_spent >= self._budget.session_premium_cap_usd:
            return EscalationDecision(
                action=EscalationAction.HOLD,
                reason=f"Premium budget cap ${self._budget.session_premium_cap_usd:.2f} reached. Cannot escalate. Error: {error[:60]}",
            )

        # Transient errors → retry same tier
        transient_keywords = ("timeout", "rate limit", "429", "503", "connection")
        if any(k in error.lower() for k in transient_keywords):
            return EscalationDecision(
                action=EscalationAction.RETRY_SAME,
                reason=f"Transient error at {tier.value}: {error[:60]}",
                new_tier=tier,
            )

        # Persistent failure → escalate
        next_tier = _escalate_tier(tier)
        return EscalationDecision(
            action=EscalationAction.ESCALATE,
            reason=f"Persistent failure at {tier.value}: {error[:60]}. Escalating to {next_tier.value}.",
            new_tier=next_tier,
        )

    # ------------------------------------------------------------------
    # Budget approval override (Bryan-only)
    # ------------------------------------------------------------------

    def approve_premium_override(
        self,
        session_id: str,
        additional_cap_usd: float,
        approver: str = "Bryan",
    ) -> None:
        """Explicitly approve additional premium budget for a session."""
        logger.info(
            "PREMIUM_OVERRIDE: session=%s +$%.2f approved by %s",
            session_id, additional_cap_usd, approver,
        )
        self._budget.session_premium_cap_usd += additional_cap_usd
        self._budget.daily_premium_cap_usd += additional_cap_usd

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def get_routing_log(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM routing_log WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_call_log(self, session_id: str) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM model_call_log WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def session_cost_summary(self, session_id: str) -> Dict[str, Any]:
        rows = self._conn.execute(
            "SELECT tier, SUM(cost_usd) AS cost, SUM(input_tokens+output_tokens) AS tokens, COUNT(*) AS calls "
            "FROM model_call_log WHERE session_id=? GROUP BY tier",
            (session_id,),
        ).fetchall()
        total = sum(r["cost"] for r in rows)
        by_tier = {r["tier"]: {"cost_usd": round(r["cost"], 6), "tokens": r["tokens"], "calls": r["calls"]} for r in rows}
        return {
            "session_id": session_id,
            "total_cost_usd": round(total, 6),
            "by_tier": by_tier,
            "budget": {
                "session_premium_cap_usd": self._budget.session_premium_cap_usd,
                "daily_premium_cap_usd": self._budget.daily_premium_cap_usd,
            },
        }

    def get_provider_config_summary(self) -> Dict[str, Any]:
        """Return provider config with key MASKED — no secrets."""
        has_key = bool(self._provider.openrouter_key)
        return {
            "adapter": self._provider.adapter,
            "cheap_model": self._provider.cheap_model,
            "mid_model": self._provider.mid_model,
            "premium_model": self._provider.premium_model,
            "openrouter_key_configured": has_key,
            "openrouter_key_value": "MASKED",
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escalate_tier(tier: ModelTier) -> ModelTier:
    order = [ModelTier.LOCAL, ModelTier.CHEAP, ModelTier.MID, ModelTier.PREMIUM]
    idx = order.index(tier)
    return order[min(idx + 1, len(order) - 1)]


__all__ = [
    "ModelRouter",
    "ModelTier",
    "BudgetConfig",
    "ProviderConfig",
    "RoutingDecision",
    "EscalationDecision",
    "EscalationAction",
    "MockModelAdapter",
    "OpenRouterAdapter",
    "_TOOL_TIER_POLICY",
    "_TASK_CATEGORY_TIERS",
]
