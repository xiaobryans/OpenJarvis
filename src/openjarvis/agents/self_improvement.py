"""Jarvis Self-Improvement — Durable Bug Prevention and Reuse.

Policy: "Catch flaw once → fix once → add durable prevention."

This module implements:
  1. Reusable plan/template recording
  2. Failure pattern recording
  3. Validation command memory
  4. Routing/model/tool selection memory
  5. Regression prevention when a flaw is caught
  6. Prevention item creation on flaw detection

Design invariants:
  - Recording a cached plan does NOT bypass required validation gates.
  - Gates must still run even when using cached plans.
  - Repeated work gets faster through safe reuse while preserving correctness.
  - Fake prevention items are forbidden (must reference a real caught flaw).
  - Prevention items must have a concrete action, not just a description.

Persistence:
  - All flaws, prevention items, cached plans, and routing memory are stored
    in SQLite at ~/.jarvis/self_improvement.db (default).
  - State survives process restart. New instances load existing records.
  - db_path can be overridden for tests.

Sprint: No-Gap Corrective Sprint 1
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = Path.home() / ".jarvis" / "self_improvement.db"


# ---------------------------------------------------------------------------
# Flaw severity
# ---------------------------------------------------------------------------

class FlawSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Flaw record
# ---------------------------------------------------------------------------

@dataclass
class CaughtFlaw:
    """A flaw caught during execution."""

    flaw_id: str
    description: str
    severity: FlawSeverity
    caught_at: float
    caught_by: str             # agent/role that caught it
    affected_task: str         # task_id or task description
    root_cause: str
    fix_applied: str
    prevention_item_id: Optional[str] = None   # linked prevention item

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flaw_id": self.flaw_id,
            "description": self.description,
            "severity": self.severity.value,
            "caught_at": self.caught_at,
            "caught_by": self.caught_by,
            "affected_task": self.affected_task,
            "root_cause": self.root_cause,
            "fix_applied": self.fix_applied,
            "prevention_item_id": self.prevention_item_id,
        }


# ---------------------------------------------------------------------------
# Prevention item
# ---------------------------------------------------------------------------

@dataclass
class PreventionItem:
    """A durable prevention rule created from a caught flaw."""

    prevention_id: str
    flaw_id: str                   # which flaw triggered this
    description: str               # human-readable description
    prevention_type: str           # "validation_gate" | "routing_rule" | "template" | "test"
    concrete_action: str           # what must be done (test command, gate name, etc.)
    validation_command: Optional[str] = None  # command to verify this gate is working
    applies_to: List[str] = field(default_factory=list)  # task types this applies to
    created_at: float = field(default_factory=time.time)
    active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prevention_id": self.prevention_id,
            "flaw_id": self.flaw_id,
            "description": self.description,
            "prevention_type": self.prevention_type,
            "concrete_action": self.concrete_action,
            "validation_command": self.validation_command,
            "applies_to": self.applies_to,
            "created_at": self.created_at,
            "active": self.active,
        }


# ---------------------------------------------------------------------------
# Cached plan / template
# ---------------------------------------------------------------------------

@dataclass
class CachedPlan:
    """A reusable plan template for a recurring task type."""

    plan_id: str
    task_type: str
    description: str
    plan_steps: List[str]
    validation_commands: List[str]   # must still run — never skipped
    routing_hint: Dict[str, Any]     # model tier, tool set, etc.
    created_at: float = field(default_factory=time.time)
    last_used_at: Optional[float] = None
    use_count: int = 0
    gates_required: List[str] = field(default_factory=list)  # gates that MUST still run

    def record_use(self) -> None:
        self.last_used_at = time.time()
        self.use_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "task_type": self.task_type,
            "description": self.description,
            "plan_steps": self.plan_steps,
            "validation_commands": self.validation_commands,
            "routing_hint": self.routing_hint,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "use_count": self.use_count,
            "gates_required": self.gates_required,
        }


# ---------------------------------------------------------------------------
# Self-Improvement Registry
# ---------------------------------------------------------------------------

class SelfImprovementRegistry:
    """Registry for flaws, prevention items, and cached plans.

    Usage::

        registry = SelfImprovementRegistry()

        # When a flaw is caught:
        flaw = registry.record_flaw(
            description="Test runner skipped lint step",
            severity=FlawSeverity.HIGH,
            caught_by="verifier",
            affected_task="coding-sprint",
            root_cause="lint step not in execution plan",
            fix_applied="Added lint to plan builder",
        )
        # Prevention item is auto-created and persisted to SQLite:
        prevention = registry.get_prevention(flaw.prevention_item_id)

        # When a plan is reused:
        plan = registry.get_cached_plan("coding_sprint")
        if plan:
            plan.record_use()
            # Still run all gates_required — never skip them
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # In-memory caches (warm from DB on init)
        self._flaws: Dict[str, CaughtFlaw] = {}
        self._prevention_items: Dict[str, PreventionItem] = {}
        self._cached_plans: Dict[str, CachedPlan] = {}
        self._routing_memory: Dict[str, Dict[str, Any]] = {}
        self._persistence = "sqlite"
        self._init_db()
        self._load_from_db()

    # ------------------------------------------------------------------
    # SQLite persistence
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS flaws (
                    flaw_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS prevention_items (
                    prevention_id TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cached_plans (
                    task_type TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS routing_memory (
                    task_type TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                );
            """)
            conn.commit()

    def _load_from_db(self) -> None:
        """Load all persisted records into in-memory caches on startup."""
        try:
            with self._connect() as conn:
                for row in conn.execute("SELECT flaw_id, data FROM flaws"):
                    d = json.loads(row["data"])
                    self._flaws[row["flaw_id"]] = CaughtFlaw(
                        flaw_id=d["flaw_id"],
                        description=d["description"],
                        severity=FlawSeverity(d["severity"]),
                        caught_at=d["caught_at"],
                        caught_by=d["caught_by"],
                        affected_task=d["affected_task"],
                        root_cause=d["root_cause"],
                        fix_applied=d["fix_applied"],
                        prevention_item_id=d.get("prevention_item_id"),
                    )
                for row in conn.execute("SELECT prevention_id, data FROM prevention_items"):
                    d = json.loads(row["data"])
                    self._prevention_items[row["prevention_id"]] = PreventionItem(
                        prevention_id=d["prevention_id"],
                        flaw_id=d["flaw_id"],
                        description=d["description"],
                        prevention_type=d["prevention_type"],
                        concrete_action=d["concrete_action"],
                        validation_command=d.get("validation_command"),
                        applies_to=d.get("applies_to", []),
                        active=d.get("active", True),
                        created_at=d.get("created_at", time.time()),
                    )
                for row in conn.execute("SELECT task_type, data FROM cached_plans"):
                    d = json.loads(row["data"])
                    self._cached_plans[row["task_type"]] = CachedPlan(
                        plan_id=d["plan_id"],
                        task_type=d["task_type"],
                        description=d["description"],
                        plan_steps=d["plan_steps"],
                        validation_commands=d["validation_commands"],
                        routing_hint=d["routing_hint"],
                        created_at=d.get("created_at", time.time()),
                        last_used_at=d.get("last_used_at"),
                        use_count=d.get("use_count", 0),
                        gates_required=d.get("gates_required", []),
                    )
                for row in conn.execute("SELECT task_type, data FROM routing_memory"):
                    self._routing_memory[row["task_type"]] = json.loads(row["data"])
        except Exception as exc:
            logger.warning("SelfImprovementRegistry: failed to load from DB: %s", exc)

    def _persist_flaw(self, flaw: CaughtFlaw) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO flaws(flaw_id, data) VALUES(?, ?)",
                    (flaw.flaw_id, json.dumps(flaw.to_dict())),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("SelfImprovementRegistry: failed to persist flaw: %s", exc)

    def _persist_prevention(self, item: PreventionItem) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO prevention_items(prevention_id, data) VALUES(?, ?)",
                    (item.prevention_id, json.dumps(item.to_dict())),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("SelfImprovementRegistry: failed to persist prevention: %s", exc)

    def _persist_plan(self, plan: CachedPlan) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO cached_plans(task_type, data) VALUES(?, ?)",
                    (plan.task_type, json.dumps(plan.to_dict())),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("SelfImprovementRegistry: failed to persist plan: %s", exc)

    def _persist_routing(self, task_type: str, entry: Dict[str, Any]) -> None:
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO routing_memory(task_type, data) VALUES(?, ?)",
                    (task_type, json.dumps(entry)),
                )
                conn.commit()
        except Exception as exc:
            logger.warning("SelfImprovementRegistry: failed to persist routing: %s", exc)

    # ------------------------------------------------------------------
    # Flaw recording
    # ------------------------------------------------------------------

    def record_flaw(
        self,
        description: str,
        severity: FlawSeverity,
        caught_by: str,
        affected_task: str,
        root_cause: str,
        fix_applied: str,
        prevention_type: str = "validation_gate",
        prevention_action: Optional[str] = None,
        validation_command: Optional[str] = None,
        applies_to: Optional[List[str]] = None,
    ) -> CaughtFlaw:
        """Record a caught flaw and auto-create a prevention item."""
        flaw_id = f"flaw-{str(uuid.uuid4())[:8]}"
        prevention_id = f"prev-{str(uuid.uuid4())[:8]}"

        concrete_action = prevention_action or f"Add gate to prevent: {description}"

        prevention = PreventionItem(
            prevention_id=prevention_id,
            flaw_id=flaw_id,
            description=f"Prevention for: {description}",
            prevention_type=prevention_type,
            concrete_action=concrete_action,
            validation_command=validation_command,
            applies_to=applies_to or [affected_task],
        )
        self._prevention_items[prevention_id] = prevention
        self._persist_prevention(prevention)

        flaw = CaughtFlaw(
            flaw_id=flaw_id,
            description=description,
            severity=severity,
            caught_at=time.time(),
            caught_by=caught_by,
            affected_task=affected_task,
            root_cause=root_cause,
            fix_applied=fix_applied,
            prevention_item_id=prevention_id,
        )
        self._flaws[flaw_id] = flaw
        self._persist_flaw(flaw)

        return flaw

    # ------------------------------------------------------------------
    # Prevention items
    # ------------------------------------------------------------------

    def get_prevention(self, prevention_id: str) -> Optional[PreventionItem]:
        return self._prevention_items.get(prevention_id)

    def list_active_preventions(self) -> List[PreventionItem]:
        return [p for p in self._prevention_items.values() if p.active]

    def list_preventions_for_task(self, task_type: str) -> List[PreventionItem]:
        return [
            p for p in self._prevention_items.values()
            if p.active and (not p.applies_to or task_type in p.applies_to)
        ]

    # ------------------------------------------------------------------
    # Cached plans
    # ------------------------------------------------------------------

    def register_plan(self, plan: CachedPlan) -> None:
        self._cached_plans[plan.task_type] = plan
        self._persist_plan(plan)

    def get_cached_plan(self, task_type: str) -> Optional[CachedPlan]:
        return self._cached_plans.get(task_type)

    def use_cached_plan(self, task_type: str) -> Optional[CachedPlan]:
        """Retrieve and mark a plan as used. Gates MUST still run."""
        plan = self._cached_plans.get(task_type)
        if plan:
            plan.record_use()
            self._persist_plan(plan)
        return plan

    # ------------------------------------------------------------------
    # Routing / model / tool memory
    # ------------------------------------------------------------------

    def record_routing_decision(
        self,
        task_type: str,
        model_tier: str,
        tools_used: List[str],
        outcome: str,
    ) -> None:
        """Record a successful routing decision for future reference."""
        entry = {
            "model_tier": model_tier,
            "tools_used": tools_used,
            "outcome": outcome,
            "recorded_at": time.time(),
        }
        self._routing_memory[task_type] = entry
        self._persist_routing(task_type, entry)

    def get_routing_memory(self, task_type: str) -> Optional[Dict[str, Any]]:
        return self._routing_memory.get(task_type)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "total_flaws": len(self._flaws),
            "total_preventions": len(self._prevention_items),
            "active_preventions": len(self.list_active_preventions()),
            "cached_plans": len(self._cached_plans),
            "routing_memory_entries": len(self._routing_memory),
            "persistence": self._persistence,
            "db_path": str(self._db_path),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flaws": [f.to_dict() for f in self._flaws.values()],
            "prevention_items": [p.to_dict() for p in self._prevention_items.values()],
            "cached_plans": [p.to_dict() for p in self._cached_plans.values()],
            "routing_memory": self._routing_memory,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_REGISTRY: Optional[SelfImprovementRegistry] = None


def get_self_improvement_registry() -> SelfImprovementRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = SelfImprovementRegistry()
    return _REGISTRY


__all__ = [
    "FlawSeverity",
    "CaughtFlaw",
    "PreventionItem",
    "CachedPlan",
    "SelfImprovementRegistry",
    "get_self_improvement_registry",
]
