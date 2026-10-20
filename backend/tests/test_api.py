from app import main as main_module
from app.ai import AIServiceError


def test_generation_persistence_checklists_and_expenses(client, valid_event):
    response = client.post("/api/plans", json=valid_event)
    assert response.status_code == 201
    plan = response.json()
    plan_id = plan["id"]
    assert plan["ai_mode"] == "demo"
    assert plan["estimated_total"] == valid_event["budget"]

    task = plan["prep_tasks"][0]
    updated = client.patch(
        f"/api/plans/{plan_id}/tasks/{task['id']}", json={"completed": True}
    )
    assert updated.status_code == 200
    assert updated.json()["prep_tasks"][0]["completed"] is True

    vendor = plan["vendors"][0]
    updated = client.patch(
        f"/api/plans/{plan_id}/vendors/{vendor['id']}", json={"completed": True}
    )
    assert updated.status_code == 200
    assert updated.json()["vendors"][0]["completed"] is True

    expense = plan["expenses"][0]
    updated = client.patch(
        f"/api/plans/{plan_id}/expenses/{expense['id']}",
        json={"actual_amount": 825, "status": "quoted"},
    )
    assert updated.json()["actual_total"] == 825
    assert updated.json()["expenses"][0]["actual_amount"] == 825
    assert updated.json()["expenses"][0]["status"] == "quoted"

    cleared = client.patch(
        f"/api/plans/{plan_id}/expenses/{expense['id']}",
        json={"actual_amount": None},
    )
    assert cleared.json()["actual_total"] == 0

    retrieved = client.get(f"/api/plans/{plan_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["vendors"][0]["completed"] is True
    listed = client.get("/api/plans")
    assert len(listed.json()) == 1


def test_natural_language_revision_preserves_checklist_progress(client, valid_event):
    created = client.post("/api/plans", json=valid_event).json()
    plan_id = created["id"]
    task_id = created["prep_tasks"][0]["id"]
    client.patch(f"/api/plans/{plan_id}/tasks/{task_id}", json={"completed": True})

    revised = client.post(
        f"/api/plans/{plan_id}/revise",
        json={"instructions": "Reduce the budget to ₹30,000 and increase guest count to 120"},
    )
    assert revised.status_code == 200
    plan = revised.json()
    assert plan["event"]["budget"] == 30000
    assert plan["event"]["guest_count"] == 120
    assert plan["estimated_total"] == 30000
    assert plan["prep_tasks"][0]["completed"] is True
    assert "120 guests" in plan["vendors"][1]["requirement"]


def test_event_validation_and_unknown_plan(client, valid_event):
    invalid = {**valid_event, "guest_count": 0}
    assert client.post("/api/plans", json=invalid).status_code == 422
    assert client.get("/api/plans/missing").status_code == 404
    assert client.patch("/api/plans/missing/tasks/nope", json={"completed": True}).status_code == 404


def test_health_reports_demo_mode_without_claiming_live_provider(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "ai_mode": "demo",
        "provider": "google-gemini",
        "model": "gemini-3.5-flash-lite",
        "provider_configured": False,
    }


def test_health_degrades_when_live_key_is_missing(client, monkeypatch):
    monkeypatch.setenv("FESTIVA_AI_MODE", "live")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ai_mode"] == "live"
    assert response.json()["provider_configured"] is False


def test_health_reports_invalid_mode_without_crashing(client, monkeypatch):
    monkeypatch.setenv("FESTIVA_AI_MODE", "production")

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["ai_mode"] == "invalid"
    assert response.json()["provider_configured"] is False


def test_diagnostics_are_aggregate_and_never_include_the_key(
    client, valid_event, monkeypatch
):
    monkeypatch.setenv("GEMINI_API_KEY", "super-secret-value")
    created = client.post("/api/plans", json=valid_event)
    assert created.status_code == 201

    response = client.get("/api/diagnostics")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ai"]["provider"] == "google-gemini"
    assert payload["ai"]["provider_configured"] is True
    assert payload["database"]["backend"] == "sqlite"
    assert payload["database"]["plans"] == 1
    assert payload["cache"]["generation_entries"] == 0
    assert "generations" in payload["metrics"]
    assert "super-secret-value" not in response.text
    assert "api_key" not in response.text.lower()


def test_vendor_details_and_booking_status_are_editable_and_persisted(client, valid_event):
    created = client.post("/api/plans", json=valid_event).json()
    vendor = created["vendors"][0]
    response = client.patch(
        f"/api/plans/{created['id']}/vendors/{vendor['id']}",
        json={
            "vendor_name": "Garden venue candidate",
            "contact": "planner@example.test",
            "quotation": 12500,
            "status": "quoted",
            "notes": "Estimate only; confirm setup fees.",
            "completed": True,
        },
    )

    assert response.status_code == 200
    saved = response.json()["vendors"][0]
    assert saved["vendor_name"] == "Garden venue candidate"
    assert saved["contact"] == "planner@example.test"
    assert saved["quotation"] == 12500
    assert saved["status"] == "quoted"
    assert saved["completed"] is True
    assert client.get(f"/api/plans/{created['id']}").json()["vendors"][0]["notes"] == (
        "Estimate only; confirm setup fees."
    )


def test_live_provider_configuration_failure_does_not_save_a_plan(
    client, valid_event, monkeypatch
):
    monkeypatch.setenv("FESTIVA_AI_MODE", "live")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = client.post("/api/plans", json=valid_event)

    assert response.status_code == 503
    assert response.json()["category"] == "config"
    assert "not configured" in response.json()["detail"]
    assert client.get("/api/plans").json() == []


def test_quota_error_is_returned_with_retry_after_and_saves_nothing(
    client, valid_event, monkeypatch
):
    def quota(*args, **kwargs):
        raise AIServiceError(
            "Gemini rate limit or daily quota reached. Wait for the quota to reset.",
            category="quota",
            http_status=429,
            retry_after=42,
        )

    monkeypatch.setattr(main_module, "generate_content", quota)

    response = client.post("/api/plans", json=valid_event)

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "42"
    assert response.json()["category"] == "quota"
    assert client.get("/api/plans").json() == []


def test_ai_endpoints_have_a_tighter_rate_limit(client, valid_event, monkeypatch):
    monkeypatch.setattr(main_module, "AI_REQUESTS_PER_WINDOW", 2)

    assert client.post("/api/plans", json=valid_event).status_code == 201
    assert client.post("/api/plans", json=valid_event).status_code == 201
    blocked = client.post("/api/plans", json=valid_event)

    assert blocked.status_code == 429
    assert "Too many plan generations" in blocked.json()["detail"]
    assert int(blocked.headers["Retry-After"]) >= 1


def test_oversized_request_body_is_rejected_before_validation(client):
    response = client.post(
        "/api/plans",
        content=b'{"event":"' + b"x" * (65 * 1024) + b'"}',
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
