import pytest

from app import auth
from app import main as main_module


def test_plan_routes_issue_hardened_anonymous_session_cookie(client):
    response = client.get("/api/plans")

    assert response.status_code == 200
    assert response.json() == []
    cookie = response.headers.get("set-cookie", "").lower()
    assert "festiva_session=" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "max-age=604800" in cookie
    assert "; secure" not in cookie
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]


def test_cross_user_reads_updates_and_revisions_are_blocked(
    client, valid_event, monkeypatch
):
    created = client.post("/api/plans", json=valid_event).json()
    plan_id = created["id"]
    task_id = created["prep_tasks"][0]["id"]
    vendor_id = created["vendors"][0]["id"]
    expense_id = created["expenses"][0]["id"]
    owner_cookies = dict(client.cookies)

    client.cookies.clear()
    assert client.get("/api/plans").json() == []
    assert client.get(f"/api/plans/{plan_id}").status_code == 404
    assert (
        client.patch(
            f"/api/plans/{plan_id}/tasks/{task_id}", json={"completed": True}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/plans/{plan_id}/vendors/{vendor_id}",
            json={"completed": True},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/plans/{plan_id}/expenses/{expense_id}",
            json={"actual_amount": 500},
        ).status_code
        == 404
    )

    def must_not_call_ai(*args, **kwargs):
        raise AssertionError("Cross-user revision must not reach the AI provider.")

    monkeypatch.setattr(main_module, "revise_content", must_not_call_ai)
    assert (
        client.post(
            f"/api/plans/{plan_id}/revise",
            json={"instructions": "Change the budget."},
        ).status_code
        == 404
    )

    client.cookies.clear()
    for name, value in owner_cookies.items():
        client.cookies.set(name, value)
    restored = client.get(f"/api/plans/{plan_id}")
    assert restored.status_code == 200
    assert restored.json()["id"] == plan_id


def test_tampered_session_cookie_is_replaced_and_cannot_read_plans(
    client, valid_event
):
    created = client.post("/api/plans", json=valid_event)
    assert created.status_code == 201
    original = client.cookies.get("festiva_session")
    assert original

    client.cookies.clear()
    tampered = original[:-3] + ("A" if original[-3] != "A" else "B") + original[-2:]
    response = client.get(
        "/api/plans",
        headers={"Cookie": f"festiva_session={tampered}"},
    )

    assert response.status_code == 200
    assert response.json() == []
    replacement = response.cookies.get("festiva_session")
    assert replacement
    assert replacement != original
    assert "set-cookie" in response.headers


def test_cross_origin_mutation_is_rejected(client, valid_event):
    blocked = client.post(
        "/api/plans",
        json=valid_event,
        headers={"Origin": "https://evil.example"},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "Cross-origin request blocked."
    assert client.get("/api/plans").json() == []


def test_same_origin_mutation_is_allowed(client, valid_event):
    response = client.post(
        "/api/plans",
        json=valid_event,
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 201


def test_plan_routes_fail_closed_without_production_session_secret(
    client, monkeypatch
):
    monkeypatch.delenv("FESTIVA_SESSION_SECRET", raising=False)
    monkeypatch.setenv("VERCEL", "1")

    response = client.get("/api/plans")

    assert response.status_code == 503
    assert response.json()["detail"] == "Session service is not configured."


def test_production_rejects_short_session_secret(monkeypatch):
    monkeypatch.setenv("FESTIVA_SESSION_SECRET", "too-short")
    monkeypatch.setenv("VERCEL", "1")

    with pytest.raises(auth.SessionConfigError):
        auth.issue_session()


def test_session_tokens_are_tamper_evident():
    owner_id, token = auth.issue_session()
    assert auth.validate_session(token) == owner_id
    assert auth.validate_session(token + "x") is None
    altered_owner = ("A" if owner_id[0] != "A" else "B") + owner_id[1:]
    assert auth.validate_session(altered_owner + token[len(owner_id) :]) is None
