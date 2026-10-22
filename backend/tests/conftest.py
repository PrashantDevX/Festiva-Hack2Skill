from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app import ai
from app import main as main_module
from app.main import app
from app.models import (
    AIExpense,
    AIIdea,
    AIPlanContent,
    AIPrepTask,
    AIScheduleItem,
    AIVendor,
)
from app.services import demo_content

_AI_ENV_VARS = (
    "FESTIVA_AI_MODE",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GEMINI_MODEL",
    "GEMINI_TIMEOUT_SECONDS",
    "FESTIVA_AI_MAX_OUTPUT_TOKENS",
    "FESTIVA_AI_TEMPERATURE",
    "FESTIVA_AI_CACHE_TTL_SECONDS",
)


@pytest.fixture(autouse=True)
def isolate_ai_state(monkeypatch):
    """Keep tests independent from a developer's real .env and prior calls."""
    for name in _AI_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setenv(
        "FESTIVA_SESSION_SECRET",
        "test-session-secret-that-is-long-enough-for-hmac",
    )
    ai.reset_ai_state()
    main_module._requests_by_ip.clear()
    main_module._ai_requests_by_ip.clear()
    yield
    ai.reset_ai_state()
    main_module._requests_by_ip.clear()
    main_module._ai_requests_by_ip.clear()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FESTIVA_AI_MODE", "demo")
    monkeypatch.setenv("FESTIVA_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_event():
    return {
        "description": "A relaxed birthday celebration with close family and floral decor.",
        "event_type": "Birthday",
        "event_date": (date.today() + timedelta(days=45)).isoformat(),
        "location": "Vijayawada",
        "guest_count": 80,
        "budget": 40000,
        "currency": "INR",
        "preferences": "Floral decorations and a family-friendly atmosphere",
        "dietary_needs": "Vegetarian",
        "special_requirements": "",
    }


@pytest.fixture
def demo_ai_payload():
    """Serialize a demo plan using the AI-only schema (no user state)."""

    def build(event) -> str:
        content = demo_content(event)
        return AIPlanContent(
            overview=content.overview,
            clarifying_questions=content.clarifying_questions,
            theme_options=content.theme_options,
            expenses=[
                AIExpense(
                    category=item.category,
                    item=item.item,
                    estimated_amount=item.estimated_amount,
                    note=item.note,
                )
                for item in content.expenses
            ],
            prep_tasks=[
                AIPrepTask(title=item.title, priority=item.priority)
                for item in content.prep_tasks
            ],
            schedule=[
                AIScheduleItem(time=item.time, title=item.title, detail=item.detail)
                for item in content.schedule
            ],
            vendors=[
                AIVendor(category=item.category, requirement=item.requirement)
                for item in content.vendors
            ],
            ideas=[
                AIIdea(
                    title=item.title,
                    description=item.description,
                    rationale=item.rationale,
                    estimated_impact=item.estimated_impact,
                )
                for item in content.ideas
            ],
            savings=content.savings,
            assumptions=content.assumptions,
        ).model_dump_json()

    return build
