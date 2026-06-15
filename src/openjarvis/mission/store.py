"""SQLite-backed persistence for missions, tasks, and mission events.

Follows the same WAL-mode pattern as agents/manager.py and
tools/approval_store.py.  All writes are committed immediately.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

from openjarvis.mission.models import (
    AgentStatus,
    Mission,
    MissionEvent,
    MissionStatus,
    RiskLevel,
    SpecialistAgentSpec,
    Task,
    TaskStatus,
)

_DEFAULT_DB = str(Path.home() / ".openjarvis" / "missions.db")

_DDL = """
CREATE TABLE IF NOT EXISTS missions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT '',
    objective   TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'queued',
    owner       TEXT NOT NULL DEFAULT 'Bryan',
    risk_level  TEXT NOT NULL DEFAULT 'low',
    summary     TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS mission_tasks (
    id                TEXT PRIMARY KEY,
    mission_id        TEXT NOT NULL REFERENCES missions(id),
    title             TEXT NOT NULL DEFAULT '',
    description       TEXT NOT NULL DEFAULT '',
    assigned_agent_id TEXT NOT NULL DEFAULT '',
    status            TEXT NOT NULL DEFAULT 'pending',
    priority          INTEGER NOT NULL DEFAULT 5,
    dependencies      TEXT NOT NULL DEFAULT '[]',
    risk_level        TEXT NOT NULL DEFAULT 'low',
    result            TEXT NOT NULL DEFAULT '',
    summary           TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL,
    updated_at        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS mission_events (
    event_id    TEXT PRIMARY KEY,
    mission_id  TEXT NOT NULL,
    task_id     TEXT,
    agent_id    TEXT,
    event_type  TEXT NOT NULL DEFAULT '',
    severity    TEXT NOT NULL DEFAULT 'info',
    message     TEXT NOT NULL DEFAULT '',
    payload     TEXT NOT NULL DEFAULT '{}',
    created_at  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_mission_events_mission_id
    ON mission_events(mission_id);

CREATE INDEX IF NOT EXISTS ix_mission_tasks_mission_id
    ON mission_tasks(mission_id);
"""


class MissionStore:
    """Thread-safe SQLite store for missions, tasks, and mission events."""

    def __init__(self, db_path: str = "") -> None:
        path = db_path or _DEFAULT_DB
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_DDL)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Missions
    # ------------------------------------------------------------------

    def save_mission(self, mission: Mission) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO missions
               (id, title, objective, status, owner, risk_level, summary,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mission.id,
                mission.title,
                mission.objective,
                mission.status.value,
                mission.owner,
                mission.risk_level.value,
                mission.summary,
                mission.created_at,
                mission.updated_at,
            ),
        )
        self._conn.commit()

    def get_mission(self, mission_id: str) -> Optional[Mission]:
        row = self._conn.execute(
            "SELECT id, title, objective, status, owner, risk_level, summary, "
            "created_at, updated_at FROM missions WHERE id = ?",
            (mission_id,),
        ).fetchone()
        if not row:
            return None
        m = Mission(
            id=row[0],
            title=row[1],
            objective=row[2],
            status=MissionStatus(row[3]),
            owner=row[4],
            risk_level=RiskLevel(row[5]),
            summary=row[6],
            created_at=row[7],
            updated_at=row[8],
        )
        m.linked_task_ids = [
            r[0]
            for r in self._conn.execute(
                "SELECT id FROM mission_tasks WHERE mission_id = ?",
                (mission_id,),
            ).fetchall()
        ]
        m.linked_event_ids = [
            r[0]
            for r in self._conn.execute(
                "SELECT event_id FROM mission_events WHERE mission_id = ?",
                (mission_id,),
            ).fetchall()
        ]
        return m

    def list_missions(self, *, limit: int = 100) -> List[Mission]:
        rows = self._conn.execute(
            "SELECT id, title, objective, status, owner, risk_level, summary, "
            "created_at, updated_at FROM missions "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            Mission(
                id=r[0],
                title=r[1],
                objective=r[2],
                status=MissionStatus(r[3]),
                owner=r[4],
                risk_level=RiskLevel(r[5]),
                summary=r[6],
                created_at=r[7],
                updated_at=r[8],
            )
            for r in rows
        ]

    def update_mission_status(self, mission_id: str, status: MissionStatus) -> None:
        self._conn.execute(
            "UPDATE missions SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, time.time(), mission_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    def save_task(self, task: Task) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO mission_tasks
               (id, mission_id, title, description, assigned_agent_id,
                status, priority, dependencies, risk_level, result, summary,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id,
                task.mission_id,
                task.title,
                task.description,
                task.assigned_agent_id,
                task.status.value,
                task.priority,
                json.dumps(task.dependencies),
                task.risk_level.value,
                task.result,
                task.summary,
                task.created_at,
                task.updated_at,
            ),
        )
        self._conn.commit()

    def get_task(self, task_id: str) -> Optional[Task]:
        row = self._conn.execute(
            "SELECT id, mission_id, title, description, assigned_agent_id, "
            "status, priority, dependencies, risk_level, result, summary, "
            "created_at, updated_at FROM mission_tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if not row:
            return None
        return Task(
            id=row[0],
            mission_id=row[1],
            title=row[2],
            description=row[3],
            assigned_agent_id=row[4],
            status=TaskStatus(row[5]),
            priority=row[6],
            dependencies=json.loads(row[7]) if row[7] else [],
            risk_level=RiskLevel(row[8]),
            result=row[9],
            summary=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    def list_tasks(self, mission_id: str) -> List[Task]:
        rows = self._conn.execute(
            "SELECT id, mission_id, title, description, assigned_agent_id, "
            "status, priority, dependencies, risk_level, result, summary, "
            "created_at, updated_at FROM mission_tasks "
            "WHERE mission_id = ? ORDER BY priority ASC, created_at ASC",
            (mission_id,),
        ).fetchall()
        return [
            Task(
                id=r[0],
                mission_id=r[1],
                title=r[2],
                description=r[3],
                assigned_agent_id=r[4],
                status=TaskStatus(r[5]),
                priority=r[6],
                dependencies=json.loads(r[7]) if r[7] else [],
                risk_level=RiskLevel(r[8]),
                result=r[9],
                summary=r[10],
                created_at=r[11],
                updated_at=r[12],
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Mission Events
    # ------------------------------------------------------------------

    def save_event(self, event: MissionEvent) -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO mission_events
               (event_id, mission_id, task_id, agent_id, event_type,
                severity, message, payload, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id,
                event.mission_id,
                event.task_id,
                event.agent_id,
                event.event_type,
                event.severity,
                event.message,
                json.dumps(event.payload),
                event.created_at,
            ),
        )
        self._conn.commit()

    def list_events(self, mission_id: str, *, limit: int = 200) -> List[MissionEvent]:
        rows = self._conn.execute(
            "SELECT event_id, mission_id, task_id, agent_id, event_type, "
            "severity, message, payload, created_at "
            "FROM mission_events WHERE mission_id = ? "
            "ORDER BY created_at ASC LIMIT ?",
            (mission_id, limit),
        ).fetchall()
        return [
            MissionEvent(
                event_id=r[0],
                mission_id=r[1],
                task_id=r[2],
                agent_id=r[3],
                event_type=r[4],
                severity=r[5],
                message=r[6],
                payload=json.loads(r[7]) if r[7] else {},
                created_at=r[8],
            )
            for r in rows
        ]

    def list_all_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """Cross-mission query: all tasks with the given status, ordered by created_at ASC.

        Used for the approval queue (awaiting_approval) and similar cross-mission views.
        """
        rows = self._conn.execute(
            "SELECT id, mission_id, title, description, assigned_agent_id, "
            "status, priority, dependencies, risk_level, result, summary, "
            "created_at, updated_at FROM mission_tasks "
            "WHERE status = ? ORDER BY created_at ASC",
            (status.value,),
        ).fetchall()
        return [
            Task(
                id=r[0],
                mission_id=r[1],
                title=r[2],
                description=r[3],
                assigned_agent_id=r[4],
                status=TaskStatus(r[5]),
                priority=r[6],
                dependencies=json.loads(r[7]) if r[7] else [],
                risk_level=RiskLevel(r[8]),
                result=r[9],
                summary=r[10],
                created_at=r[11],
                updated_at=r[12],
            )
            for r in rows
        ]

    def update_task_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        result: str = "",
    ) -> bool:
        """Update a task's status and updated_at timestamp.

        Returns True if the task existed and was updated, False if not found.
        """
        cur = self._conn.execute(
            "UPDATE mission_tasks SET status = ?, result = ?, updated_at = ? WHERE id = ?",
            (new_status.value, result, time.time(), task_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def list_recent_events(self, *, limit: int = 100) -> List[MissionEvent]:
        """Cross-mission events ordered by created_at DESC (newest first).

        Used for the global event feed on the Mission Control dashboard.
        """
        rows = self._conn.execute(
            "SELECT event_id, mission_id, task_id, agent_id, event_type, "
            "severity, message, payload, created_at "
            "FROM mission_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            MissionEvent(
                event_id=r[0],
                mission_id=r[1],
                task_id=r[2],
                agent_id=r[3],
                event_type=r[4],
                severity=r[5],
                message=r[6],
                payload=json.loads(r[7]) if r[7] else {},
                created_at=r[8],
            )
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()


__all__ = ["MissionStore"]
