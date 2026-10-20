import os
import sqlite3
from contextlib import closing
from pathlib import Path

from .models import Plan


def database_path() -> str:
    return os.getenv("FESTIVA_DB_PATH", "festiva.db")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database() -> None:
    path = Path(database_path())
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as connection:
        with connection:
            if str(path) != ":memory:":
                connection.execute("PRAGMA journal_mode = WAL")
                connection.execute("PRAGMA synchronous = NORMAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS plans (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )


def save_plan(plan: Plan) -> Plan:
    payload = plan.model_dump_json()
    with closing(connect()) as connection:
        with connection:
            connection.execute(
                """
                INSERT INTO plans (id, created_at, updated_at, payload)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    payload = excluded.payload
                """,
                (plan.id, plan.created_at.isoformat(), plan.updated_at.isoformat(), payload),
            )
    return plan


def list_plans() -> list[Plan]:
    with closing(connect()) as connection:
        rows = connection.execute(
            "SELECT payload FROM plans ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()
    return [Plan.model_validate_json(row["payload"]) for row in rows]


def get_plan(plan_id: str) -> Plan | None:
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT payload FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
    return Plan.model_validate_json(row["payload"]) if row else None


def count_plans() -> int:
    with closing(connect()) as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM plans").fetchone()
    return int(row["total"]) if row else 0
