import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Plan


BLOB_PLAN_PREFIX = "plans/"
_PLAN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def database_path() -> str:
    configured = os.getenv("FESTIVA_DB_PATH", "").strip()
    if configured:
        return configured
    if os.getenv("VERCEL"):
        # Vercel Functions have a read-only filesystem except /tmp, which is
        # ephemeral and per instance. Blob storage is used when configured;
        # this path is only the fallback.
        return "/tmp/festiva.db"
    return "festiva.db"


def _blob_configured() -> bool:
    if os.getenv("BLOB_READ_WRITE_TOKEN") or os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN"):
        return True
    return bool(
        os.getenv("BLOB_STORE_ID")
        and (os.getenv("VERCEL") or os.getenv("VERCEL_OIDC_TOKEN"))
    )


def storage_backend() -> str:
    return "vercel-blob" if _blob_configured() else "sqlite"


def _blob():
    # Imported lazily so local/test runs can use SQLite without the package.
    from vercel.blob import sync as blob

    return blob


def _plan_pathname(plan_id: str) -> str:
    if not _PLAN_ID_PATTERN.fullmatch(plan_id):
        raise ValueError("Invalid plan id.")
    return f"{BLOB_PLAN_PREFIX}{plan_id}.json"


def _origin_read_url(url: str) -> str:
    """Ask Vercel Blob to bypass the CDN and read the latest private object."""
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["cache"] = "0"
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


def _read_blob_path(blob, pathname: str):
    # Private Blob reads pass through the CDN, which can serve the previous
    # version after an overwrite. The JavaScript SDK's ``useCache: false`` maps
    # to ``cache=0``; the Python SDK does not expose that option yet, so apply
    # the same query parameter to the delivered URL.
    metadata = blob.head_blob(pathname)
    return blob.get_blob(_origin_read_url(metadata.url), access="private")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(database_path(), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def _initialize_sqlite() -> None:
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


def initialize_database() -> None:
    if _blob_configured():
        # Blob storage has no schema to create.
        return
    _initialize_sqlite()


def _save_plan_blob(plan: Plan) -> Plan:
    blob = _blob()
    blob.put_blob(
        _plan_pathname(plan.id),
        plan.model_dump_json().encode("utf-8"),
        access="private",
        content_type="application/json",
        allow_overwrite=True,
        cache_control_max_age=0,
    )
    return plan


def _list_plans_blob() -> list[Plan]:
    blob = _blob()
    plans: list[Plan] = []
    for item in blob.query_blobs(prefix=BLOB_PLAN_PREFIX):
        if not item.pathname.endswith(".json"):
            continue
        try:
            result = blob.get_blob(_origin_read_url(item.url), access="private")
        except blob.BlobNotFoundError:
            continue
        plans.append(Plan.model_validate_json(result.body))
    plans.sort(key=lambda plan: plan.updated_at, reverse=True)
    return plans[:100]


def _get_plan_blob(plan_id: str) -> Plan | None:
    if not _PLAN_ID_PATTERN.fullmatch(plan_id):
        return None
    blob = _blob()
    try:
        result = _read_blob_path(blob, _plan_pathname(plan_id))
    except blob.BlobNotFoundError:
        return None
    return Plan.model_validate_json(result.body)


def _count_plans_blob() -> int:
    blob = _blob()
    return sum(
        1
        for item in blob.query_blobs(prefix=BLOB_PLAN_PREFIX)
        if item.pathname.endswith(".json")
    )


def _save_plan_sqlite(plan: Plan) -> Plan:
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


def _list_plans_sqlite() -> list[Plan]:
    with closing(connect()) as connection:
        rows = connection.execute(
            "SELECT payload FROM plans ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()
    return [Plan.model_validate_json(row["payload"]) for row in rows]


def _get_plan_sqlite(plan_id: str) -> Plan | None:
    with closing(connect()) as connection:
        row = connection.execute(
            "SELECT payload FROM plans WHERE id = ?", (plan_id,)
        ).fetchone()
    return Plan.model_validate_json(row["payload"]) if row else None


def _count_plans_sqlite() -> int:
    with closing(connect()) as connection:
        row = connection.execute("SELECT COUNT(*) AS total FROM plans").fetchone()
    return int(row["total"]) if row else 0


def save_plan(plan: Plan) -> Plan:
    if _blob_configured():
        return _save_plan_blob(plan)
    return _save_plan_sqlite(plan)


def list_plans() -> list[Plan]:
    if _blob_configured():
        return _list_plans_blob()
    return _list_plans_sqlite()


def get_plan(plan_id: str) -> Plan | None:
    if _blob_configured():
        return _get_plan_blob(plan_id)
    return _get_plan_sqlite(plan_id)


def count_plans() -> int:
    if _blob_configured():
        return _count_plans_blob()
    return _count_plans_sqlite()
