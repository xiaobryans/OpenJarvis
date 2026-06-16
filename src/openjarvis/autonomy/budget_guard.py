"""Jarvis Runtime Budget / Token Spend Guard.

Enforces Bryan's Pay-On-Demand Cost-Control Law:
  - Local configurable budget ceilings (per-run and per-day)
  - Soft limit: warn + log but allow
  - Hard limit: stop + require explicit approval before continuing
  - Token/cost estimate tracking (model-based pricing table)
  - Execution log entry for every cost decision
  - Doctor/readiness visibility

Budget config stored at: ~/.openjarvis/budget.json
Spend log stored at: ~/.openjarvis/spend_log.jsonl

Hard rules:
  - Never block local non-LLM diagnostics (read-only checks free)
  - Hard limit stop returns HOLD status — not a silent failure
  - All limits are local only — no cloud sync
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_CONFIG_DIR = Path.home() / ".openjarvis"
_BUDGET_FILE = _CONFIG_DIR / "budget.json"
_SPEND_LOG = _CONFIG_DIR / "spend_log.jsonl"

# ---------------------------------------------------------------------------
# Default budget config
# ---------------------------------------------------------------------------

_DEFAULT_BUDGET: Dict[str, Any] = {
    "per_run_soft_limit_usd": 0.10,
    "per_run_hard_limit_usd": 0.50,
    "per_day_soft_limit_usd": 1.00,
    "per_day_hard_limit_usd": 5.00,
    "warn_on_soft_breach": True,
    "stop_on_hard_breach": True,
    "non_llm_diagnostics_exempt": True,
}

# Model pricing table (USD per 1K tokens, input/output)
_MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "o1-mini": {"input": 0.003, "output": 0.012},
    "default": {"input": 0.002, "output": 0.006},
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SpendEntry:
    entry_id: str
    timestamp: float
    model: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float
    action: str
    approved: bool
    decision: str  # "allowed", "soft_warn", "hard_stop", "exempt"
    run_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BudgetStatus:
    config: Dict[str, Any]
    today_spend_usd: float
    run_spend_usd: float
    today_soft_ok: bool
    today_hard_ok: bool
    run_soft_ok: bool
    run_hard_ok: bool
    overall_ok: bool
    verdict: str  # "ok", "soft_warn", "hard_stop"
    entries_today: int
    checked_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Config load/save
# ---------------------------------------------------------------------------


def load_budget_config() -> Dict[str, Any]:
    """Load budget config from file, returning defaults if missing."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not _BUDGET_FILE.exists():
        return dict(_DEFAULT_BUDGET)
    try:
        data = json.loads(_BUDGET_FILE.read_text(encoding="utf-8"))
        cfg = dict(_DEFAULT_BUDGET)
        cfg.update(data)
        return cfg
    except Exception:
        return dict(_DEFAULT_BUDGET)


def save_budget_config(config: Dict[str, Any]) -> bool:
    """Persist budget config."""
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _BUDGET_FILE.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    """Estimate cost in USD for a model call."""
    pricing = _MODEL_PRICING.get(model, _MODEL_PRICING["default"])
    cost = (prompt_tokens / 1000) * pricing["input"] + (
        completion_tokens / 1000
    ) * pricing["output"]
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Spend log
# ---------------------------------------------------------------------------


def _load_today_entries() -> List[SpendEntry]:
    """Load today's spend log entries."""
    entries: List[SpendEntry] = []
    if not _SPEND_LOG.exists():
        return entries
    today_start = time.time() - (time.time() % 86400)
    try:
        for line in _SPEND_LOG.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            if d.get("timestamp", 0) >= today_start:
                entries.append(
                    SpendEntry(
                        entry_id=d.get("entry_id", ""),
                        timestamp=d.get("timestamp", 0),
                        model=d.get("model", ""),
                        prompt_tokens=d.get("prompt_tokens", 0),
                        completion_tokens=d.get("completion_tokens", 0),
                        estimated_cost_usd=d.get("estimated_cost_usd", 0.0),
                        action=d.get("action", ""),
                        approved=d.get("approved", False),
                        decision=d.get("decision", ""),
                        run_id=d.get("run_id", ""),
                    )
                )
    except Exception:
        pass
    return entries


def _append_spend_entry(entry: SpendEntry) -> None:
    """Append a spend entry to the log."""
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with _SPEND_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Budget check — core function
# ---------------------------------------------------------------------------


def check_budget(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    action: str = "llm_call",
    is_diagnostic: bool = False,
    run_id: str = "",
) -> Dict[str, Any]:
    """Check whether a proposed LLM call is within budget.

    Returns:
      ok: True if allowed (soft or hard)
      verdict: "ok", "soft_warn", "hard_stop", "exempt"
      estimated_cost_usd: float
      decision_reason: str
    """
    import uuid
    cfg = load_budget_config()
    estimated = estimate_cost(model, prompt_tokens, completion_tokens)

    # Diagnostic/non-LLM calls are exempt
    if is_diagnostic and cfg.get("non_llm_diagnostics_exempt", True):
        entry = SpendEntry(
            entry_id=str(uuid.uuid4()),
            timestamp=time.time(),
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=0.0,
            action=action,
            approved=True,
            decision="exempt",
            run_id=run_id,
        )
        _append_spend_entry(entry)
        return {
            "ok": True,
            "verdict": "exempt",
            "estimated_cost_usd": 0.0,
            "decision_reason": "Non-LLM diagnostic exempt from budget",
        }

    today_entries = _load_today_entries()
    today_spend = sum(e.estimated_cost_usd for e in today_entries)
    run_entries = [e for e in today_entries if e.run_id == run_id] if run_id else []
    run_spend = sum(e.estimated_cost_usd for e in run_entries)

    per_run_hard = cfg["per_run_hard_limit_usd"]
    per_run_soft = cfg["per_run_soft_limit_usd"]
    per_day_hard = cfg["per_day_hard_limit_usd"]
    per_day_soft = cfg["per_day_soft_limit_usd"]

    projected_run = run_spend + estimated
    projected_day = today_spend + estimated

    if cfg.get("stop_on_hard_breach", True):
        if projected_run > per_run_hard:
            verdict = "hard_stop"
            reason = (
                f"Per-run hard limit ${per_run_hard:.2f} would be exceeded "
                f"(projected ${projected_run:.4f}). Requires explicit approval."
            )
        elif projected_day > per_day_hard:
            verdict = "hard_stop"
            reason = (
                f"Per-day hard limit ${per_day_hard:.2f} would be exceeded "
                f"(projected ${projected_day:.4f}). Requires explicit approval."
            )
        elif projected_run > per_run_soft or projected_day > per_day_soft:
            verdict = "soft_warn"
            reason = (
                f"Soft limit approached: run=${projected_run:.4f}/"
                f"${per_run_soft:.2f}, day=${projected_day:.4f}/${per_day_soft:.2f}"
            )
        else:
            verdict = "ok"
            reason = f"Within budget: run=${projected_run:.4f}, day=${projected_day:.4f}"
    else:
        verdict = "ok"
        reason = "Hard stop disabled in config"

    ok = verdict != "hard_stop"
    entry = SpendEntry(
        entry_id=str(uuid.uuid4()),
        timestamp=time.time(),
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated if ok else 0.0,
        action=action,
        approved=ok,
        decision=verdict,
        run_id=run_id,
    )
    _append_spend_entry(entry)

    return {
        "ok": ok,
        "verdict": verdict,
        "estimated_cost_usd": estimated,
        "today_spend_usd": today_spend,
        "run_spend_usd": run_spend,
        "decision_reason": reason,
        "per_run_hard_limit": per_run_hard,
        "per_day_hard_limit": per_day_hard,
    }


# ---------------------------------------------------------------------------
# Budget status (for doctor/readiness)
# ---------------------------------------------------------------------------


def get_budget_status(run_id: str = "") -> BudgetStatus:
    """Current budget status without making a call."""
    cfg = load_budget_config()
    today_entries = _load_today_entries()
    today_spend = sum(e.estimated_cost_usd for e in today_entries)
    run_entries = [e for e in today_entries if e.run_id == run_id] if run_id else []
    run_spend = sum(e.estimated_cost_usd for e in run_entries)

    today_soft_ok = today_spend <= cfg["per_day_soft_limit_usd"]
    today_hard_ok = today_spend <= cfg["per_day_hard_limit_usd"]
    run_soft_ok = run_spend <= cfg["per_run_soft_limit_usd"]
    run_hard_ok = run_spend <= cfg["per_run_hard_limit_usd"]

    if not today_hard_ok or not run_hard_ok:
        verdict = "hard_stop"
    elif not today_soft_ok or not run_soft_ok:
        verdict = "soft_warn"
    else:
        verdict = "ok"

    return BudgetStatus(
        config=cfg,
        today_spend_usd=round(today_spend, 6),
        run_spend_usd=round(run_spend, 6),
        today_soft_ok=today_soft_ok,
        today_hard_ok=today_hard_ok,
        run_soft_ok=run_soft_ok,
        run_hard_ok=run_hard_ok,
        overall_ok=verdict != "hard_stop",
        verdict=verdict,
        entries_today=len(today_entries),
    )


def reset_run_spend(run_id: str) -> None:
    """Clear run_id spend entries (for tests)."""
    pass  # Spend log is append-only; run isolation via run_id filter


__all__ = [
    "load_budget_config",
    "save_budget_config",
    "estimate_cost",
    "check_budget",
    "get_budget_status",
    "BudgetStatus",
    "SpendEntry",
]
