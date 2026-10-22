from types import SimpleNamespace
from urllib.parse import urlparse

import pytest

from app import database
from app.models import EventInput, utc_now
from app.services import demo_content, finalize_plan

OWNER_A = "a" * 32
OWNER_B = "b" * 32


class FakeBlob:
    class BlobNotFoundError(Exception):
        pass

    def __init__(self):
        self.files: dict[str, bytes] = {}
        self.reads: list[str] = []

    def put_blob(
        self,
        pathname,
        body,
        *,
        access,
        content_type,
        allow_overwrite,
        cache_control_max_age,
    ):
        assert access == "private"
        assert content_type == "application/json"
        assert allow_overwrite is True
        assert cache_control_max_age == 0
        self.files[pathname] = body

    def head_blob(self, pathname):
        if pathname not in self.files:
            raise self.BlobNotFoundError()
        return SimpleNamespace(url=f"https://fake.blob/{pathname}")

    def get_blob(self, url_or_pathname, *, access):
        assert access == "private"
        self.reads.append(url_or_pathname)
        pathname = url_or_pathname
        if pathname.startswith("https://fake.blob/"):
            pathname = urlparse(pathname).path.lstrip("/")
        if pathname not in self.files:
            raise self.BlobNotFoundError()
        return SimpleNamespace(body=self.files[pathname])

    def query_blobs(self, *, prefix):
        for pathname in sorted(self.files):
            if pathname.startswith(prefix):
                yield SimpleNamespace(
                    pathname=pathname,
                    url=f"https://fake.blob/{pathname}",
                )


@pytest.fixture
def fake_blob(monkeypatch):
    blob = FakeBlob()
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "test-token")
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("BLOB_STORE_ID", raising=False)
    monkeypatch.setattr(database, "_blob", lambda: blob)
    return blob


@pytest.fixture
def event(valid_event):
    return EventInput.model_validate(valid_event)


def test_blob_backend_round_trips_and_overwrites_plans(fake_blob, event):
    assert database.storage_backend() == "vercel-blob"
    database.initialize_database()
    assert database.count_plans() == 0

    plan = finalize_plan(demo_content(event), event, "demo")
    database.save_plan(plan, OWNER_A)

    assert database.count_plans() == 1
    fetched = database.get_plan(plan.id, OWNER_A)
    assert fetched is not None
    assert fetched.id == plan.id
    assert fetched.estimated_total == plan.estimated_total
    assert [item.id for item in database.list_plans(OWNER_A)] == [plan.id]

    updated = plan.model_copy(
        update={"overview": "Updated durable overview for the same plan.", "updated_at": utc_now()}
    )
    database.save_plan(updated, OWNER_A)
    fetched = database.get_plan(plan.id, OWNER_A)
    assert fetched is not None
    assert fetched.overview == "Updated durable overview for the same plan."
    assert database.count_plans() == 1

    blob_path = database._plan_pathname(plan.id, OWNER_A)
    assert blob_path == f"plans/{OWNER_A}/{plan.id}.json"
    assert blob_path in fake_blob.files
    assert fake_blob.reads
    assert all("cache=0" in url for url in fake_blob.reads)
    assert all("v=" not in url for url in fake_blob.reads)


def test_blob_backend_isolates_owners(fake_blob, event):
    plan_a = finalize_plan(demo_content(event), event, "demo")
    plan_b = finalize_plan(demo_content(event), event, "demo")
    database.save_plan(plan_a, OWNER_A)
    database.save_plan(plan_b, OWNER_B)

    assert [plan.id for plan in database.list_plans(OWNER_A)] == [plan_a.id]
    assert [plan.id for plan in database.list_plans(OWNER_B)] == [plan_b.id]
    assert database.get_plan(plan_b.id, OWNER_A) is None
    assert database.get_plan(plan_a.id, OWNER_B) is None
    assert database.count_plans() == 2
    assert f"plans/{OWNER_A}/{plan_a.id}.json" in fake_blob.files
    assert f"plans/{OWNER_B}/{plan_b.id}.json" in fake_blob.files


def test_blob_backend_rejects_unsafe_plan_ids(fake_blob, event):
    plan = finalize_plan(demo_content(event), event, "demo")
    database.save_plan(plan, OWNER_A)

    assert database.get_plan("../other", OWNER_A) is None
    assert database.get_plan("a/b", OWNER_A) is None
    with pytest.raises(ValueError):
        database._plan_pathname("../other", OWNER_A)
    with pytest.raises(ValueError):
        database._plan_pathname(plan.id, "../owner")


def test_sqlite_owner_cannot_be_taken_over_by_same_plan_id(
    tmp_path, monkeypatch, event
):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("BLOB_STORE_ID", raising=False)
    monkeypatch.setenv("FESTIVA_DB_PATH", str(tmp_path / "plans.db"))
    database.initialize_database()

    plan_a = finalize_plan(demo_content(event), event, "demo")
    database.save_plan(plan_a, OWNER_A)
    takeover = plan_a.model_copy(
        update={"overview": "A different owner attempted this payload.", "updated_at": utc_now()}
    )
    database.save_plan(takeover, OWNER_B)

    fetched_a = database.get_plan(plan_a.id, OWNER_A)
    assert fetched_a is not None
    assert fetched_a.overview == plan_a.overview
    assert database.get_plan(plan_a.id, OWNER_B) is None
    assert [plan.id for plan in database.list_plans(OWNER_B)] == []


def test_blob_backend_can_use_vercel_oidc_credentials(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.delenv("VERCEL_BLOB_READ_WRITE_TOKEN", raising=False)
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("BLOB_STORE_ID", "store_example")

    assert database.storage_backend() == "vercel-blob"

    monkeypatch.delenv("VERCEL")
    assert database.storage_backend() == "sqlite"
