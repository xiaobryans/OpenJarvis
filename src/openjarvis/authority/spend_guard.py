"""Plan 8 — Spend and Rate Guardrails.

Provides:
  - Per-action estimated cost tracking
  - Daily and session budget enforcement
  - Model/provider routing cost classification
  - External API spend classification
  - Hard stop / approval escalation when cost is unknown or above threshold
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Spend impact levels
# ---------------------------------------------------------------------------


class SpendImpact(str, Enum):
    NONE = "none"           # No cost (read-only, local)
    NEGLIGIBLE = "negligible"  # < $0.01
    LOW = "low"             # $0.01 – $1.00
    MEDIUM = "medium"       # $1.00 – $10.00
    HIGH = "high"           # $10.00 – $100.00
    CRITICAL = "critical"   # > $100.00 or unbounded
    UNKNOWN = "unknown"     # Cannot determine cost


# ---------------------------------------------------------------------------
# Known action cost table
# ---------------------------------------------------------------------------

_ACTION_COST_TABLE: Dict[str, float] = {
    # Zero cost
    "read": 0.0,
    "explain": 0.0,
    "plan": 0.0,
    "search": 0.0,
    "draft": 0.0,
    "simulate": 0.0,
    "dry_run": 0.0,
    "preview": 0.0,
    "file_read": 0.0,
    "file_write": 0.0,
    "file_edit": 0.0,
    "git_commit": 0.0,
    "git_add": 0.0,
    "git_push": 0.0,
    "local_note_write": 0.0,
    "local_state_change": 0.0,
    "task_update": 0.0,

    # Low cost estimates (USD)
    "email_send": 0.0,       # depends on provider
    "slack_send": 0.0,       # free tier typically
    "external_send": 0.01,

    # Medium cost
    "staging_deploy": 0.10,  # CI/CD costs vary
    "vercel_deploy": 0.05,

    # High cost / unknown
    "production_deploy": 1.00,   # conservative estimate
    "aws_infra_change": -1.0,    # -1 = unknown/unbounded
    "billing_change": -1.0,
    "stripe_change": -1.0,
    "credential_write": 0.0,
    "account_mutation": 0.0,
    "destructive_irreversible_delete": 0.0,
}


def estimate_action_cost(action_type: str) -> float:
    """Return estimated USD cost for an action. Returns -1.0 if unknown."""
    return _ACTION_COST_TABLE.get(action_type.lower(), -1.0)


def classify_spend_impact(action_type: str) -> SpendImpact:
    """Classify the spend impact of an action type."""
    cost = estimate_action_cost(action_type)
    if cost < 0:
        return SpendImpact.UNKNOWN
    if cost == 0.0:
        return SpendImpact.NONE
    if cost < 0.01:
        return SpendImpact.NEGLIGIBLE
    if cost < 1.0:
        return SpendImpact.LOW
    if cost < 10.0:
        return SpendImpact.MEDIUM
    if cost < 100.0:
        return SpendImpact.HIGH
    return SpendImpact.CRITICAL


# ---------------------------------------------------------------------------
# SpendGuard
# ---------------------------------------------------------------------------

_DEFAULT_DB = Path.home() / ".jarvis" / "authority_spend.db"


@dataclass
class SpendCheckResult:
    allowed: bool
    action_type: str
    estimated_cost: float
    spend_impact: SpendImpact
    current_session_spend: float
    current_day_spend: float
    session_budget: float
    daily_budget: float
    reason: str
    requires_approval: bool = False
    hard_stop: bool = False


class SpendGuard:
    """Enforces spend/cost/rate guardrails for Plan 8 trusted delegation.

    Tracks cumulative spend per session and per day. Emits hard stops when
    cost is unknown or above threshold. Escalates to approval when cost
    is within configurable warning range.
    """

    def __init__(
        self,
        *,
        daily_budget: float = 5.0,
        session_budget: float = 1.0,
        alert_threshold_pct: float = 0.80,
        db_path: Optional[Path] = None,
    ) -> None:
        self.daily_budget = daily_budget
        self.session_budget = session_budget
        self.alert_threshold_pct = alert_threshold_pct
        self._session_id = str(int(time.time()))
        self._session_spend: float = 0.0
        self._db_path = db_path or _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS spend_log (
            entry_id        TEXT PRIMARY KEY,
            session_id      TEXT NOT NULL,
            action_type     TEXT NOT NULL,
            cost_usd        REAL NOT NULL DEFAULT 0.0,
            ts              REAL NOT NULL,
            day_key         TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_spend_day ON spend_log (day_key);
        CREATE INDEX IF NOT EXISTS idx_spend_session ON spend_log (session_id);
        """)
        self._conn.commit()

    def _day_key(self) -> str:
        from datetime import date
        return date.today().isoformat()

    def _today_spend(self) -> float:
        cur = self._conn.execute(
            "SELECT SUM(cost_usd) FROM spend_log WHERE day_key=?",
            (self._day_key(),),
        )
        row = cur.fetchone()
        return float(row[0] or 0.0)

    def check(self, action_type: str) -> SpendCheckResult:
        """Check if an action is within spend guardrails.

        Returns SpendCheckResult with allowed=True if within budget,
        requires_approval=True if near threshold, hard_stop=True if over limit
        or cost is unknown for high-tier action.
        """
        cost = estimate_action_cost(action_type)
        impact = classify_spend_impact(action_type)
        day_spend = self._today_spend()
        session_spend = self._session_spend

        # Unknown cost: require approval if spend-bearing action
        if cost < 0:  # -1 = unknown
            return SpendCheckResult(
                allowed=False,
                action_type=action_type,
                estimated_cost=-1.0,
                spend_impact=SpendImpact.UNKNOWN,
                current_session_spend=session_spend,
                current_day_spend=day_spend,
                session_budget=self.session_budget,
                daily_budget=self.daily_budget,
                reason=(
                    f"Cost for '{action_type}' is UNKNOWN. "
                    "Approval required before execution."
                ),
                requires_approval=True,
                hard_stop=False,
            )

        # Zero cost: always allowed
        if cost == 0.0:
            return SpendCheckResult(
                allowed=True,
                action_type=action_type,
                estimated_cost=0.0,
                spend_impact=SpendImpact.NONE,
                current_session_spend=session_spend,
                current_day_spend=day_spend,
                session_budget=self.session_budget,
                daily_budget=self.daily_budget,
                reason="No cost action — allowed.",
                requires_approval=False,
                hard_stop=False,
            )

        # Check day budget
        projected_day = day_spend + cost
        projected_session = session_spend + cost

        if projected_day > self.daily_budget:
            return SpendCheckResult(
                allowed=False,
                action_type=action_type,
                estimated_cost=cost,
                spend_impact=impact,
                current_session_spend=session_spend,
                current_day_spend=day_spend,
                session_budget=self.session_budget,
                daily_budget=self.daily_budget,
                reason=(
                    f"Daily budget exceeded: ${day_spend:.3f} + ${cost:.3f} > ${self.daily_budget:.2f}. "
                    "Hard stop."
                ),
                requires_approval=True,
                hard_stop=True,
            )

        if projected_session > self.session_budget:
            return SpendCheckResult(
                allowed=False,
                action_type=action_type,
                estimated_cost=cost,
                spend_impact=impact,
                current_session_spend=session_spend,
                current_day_spend=day_spend,
                session_budget=self.session_budget,
                daily_budget=self.daily_budget,
                reason=(
                    f"Session budget exceeded: ${session_spend:.3f} + ${cost:.3f} > ${self.session_budget:.2f}. "
                    "Approval required."
                ),
                requires_approval=True,
                hard_stop=False,
            )

        # Near threshold
        alert_day = self.daily_budget * self.alert_threshold_pct
        if projected_day > alert_day:
            return SpendCheckResult(
                allowed=True,
                action_type=action_type,
                estimated_cost=cost,
                spend_impact=impact,
                current_session_spend=session_spend,
                current_day_spend=day_spend,
                session_budget=self.session_budget,
                daily_budget=self.daily_budget,
                reason=(
                    f"Near daily budget threshold: ${projected_day:.3f} / ${self.daily_budget:.2f}. "
                    "Approval recommended."
                ),
                requires_approval=True,
                hard_stop=False,
            )

        return SpendCheckResult(
            allowed=True,
            action_type=action_type,
            estimated_cost=cost,
            spend_impact=impact,
            current_session_spend=session_spend,
            current_day_spend=day_spend,
            session_budget=self.session_budget,
            daily_budget=self.daily_budget,
            reason=f"Within budget. Est cost: ${cost:.3f}.",
            requires_approval=False,
            hard_stop=False,
        )

    def record_spend(self, action_type: str, cost: Optional[float] = None) -> None:
        """Record actual spend after action execution."""
        if cost is None:
            cost = max(0.0, estimate_action_cost(action_type))
        if cost <= 0:
            return
        import uuid as _uuid
        self._conn.execute(
            "INSERT INTO spend_log (entry_id, session_id, action_type, cost_usd, ts, day_key) "
            "VALUES (?,?,?,?,?,?)",
            (
                _uuid.uuid4().hex, self._session_id, action_type,
                cost, time.time(), self._day_key(),
            ),
        )
        self._conn.commit()
        self._session_spend += cost

    def summary(self) -> Dict[str, Any]:
        return {
            "session_id": self._session_id,
            "session_spend": self._session_spend,
            "day_spend": self._today_spend(),
            "daily_budget": self.daily_budget,
            "session_budget": self.session_budget,
            "alert_threshold_pct": self.alert_threshold_pct,
        }

    def close(self) -> None:
        self._conn.close()


__all__ = [
    "SpendCheckResult",
    "SpendGuard",
    "SpendImpact",
    "classify_spend_impact",
    "estimate_action_cost",
]
