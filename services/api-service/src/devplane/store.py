"""Durable SQLite store for projects, tasks, and runs."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from .models import ProjectRecord, RunRecord, TaskRecord

ModelT = TypeVar("ModelT", bound=BaseModel)


class DevPlaneStore:
    """Persist control-plane records as JSON payloads keyed by id."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                """)
            conn.commit()

    def _upsert_model(self, table: str, record_id: str, model: BaseModel) -> None:
        payload = model.model_dump_json()
        updated_at = getattr(model, "updated_at", None)
        updated_value = (
            updated_at.isoformat() if hasattr(updated_at, "isoformat") else ""
        )
        with self._lock, self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {table} (id, updated_at, payload)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (record_id, updated_value, payload),
            )
            conn.commit()

    def _get_model(
        self, table: str, record_id: str, model_type: type[ModelT]
    ) -> ModelT | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                f"SELECT payload FROM {table} WHERE id = ?",
                (record_id,),
            ).fetchone()
        if row is None:
            return None
        return model_type.model_validate_json(str(row["payload"]))

    def _list_models(self, table: str, model_type: type[ModelT]) -> list[ModelT]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                f"SELECT payload FROM {table} ORDER BY updated_at DESC, id DESC"
            ).fetchall()
        return [model_type.model_validate_json(str(row["payload"])) for row in rows]

    def save_project(self, project: ProjectRecord) -> None:
        self._upsert_model("projects", project.project_id, project)

    def get_project(self, project_id: str) -> ProjectRecord | None:
        return self._get_model("projects", project_id, ProjectRecord)

    def list_projects(self) -> list[ProjectRecord]:
        return self._list_models("projects", ProjectRecord)

    def save_task(self, task: TaskRecord) -> None:
        self._upsert_model("tasks", task.task_id, task)

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self._get_model("tasks", task_id, TaskRecord)

    def list_tasks(self) -> list[TaskRecord]:
        return self._list_models("tasks", TaskRecord)

    def save_run(self, run: RunRecord) -> None:
        self._upsert_model("runs", run.run_id, run)

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._get_model("runs", run_id, RunRecord)

    def list_runs(self) -> list[RunRecord]:
        return self._list_models("runs", RunRecord)
