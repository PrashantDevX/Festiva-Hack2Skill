from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.models import EventInput, PrepTask
from app.services import (
    demo_content,
    finalize_plan,
    merge_user_state,
    normalize_generated_content,
)


def test_demo_budget_allocations_are_recalculated_independently(valid_event):
    event = EventInput.model_validate(valid_event)
    plan = finalize_plan(demo_content(event), event, "demo")

    assert sum(item.estimated_amount for item in plan.expenses) == plan.estimated_total
    assert plan.estimated_total == event.budget
    assert plan.remaining_budget == 0
    assert plan.actual_total == 0
    assert not plan.over_budget


def test_budget_overrun_is_detected(valid_event):
    valid_event["budget"] = 100
    event = EventInput.model_validate(valid_event)
    content = demo_content(event).model_copy(
        update={
            "expenses": [
                demo_content(event).expenses[0].model_copy(update={"estimated_amount": 125})
            ]
        }
    )
    plan = finalize_plan(content, event, "demo")

    assert plan.estimated_total == 125
    assert plan.remaining_budget == -25
    assert plan.over_budget


def test_actual_spending_can_trigger_budget_overrun(valid_event):
    valid_event["budget"] = 100
    event = EventInput.model_validate(valid_event)
    content = demo_content(event)
    content.expenses[0].actual_amount = 101

    plan = finalize_plan(content, event, "demo")

    assert plan.estimated_total == 100
    assert plan.actual_total == 101
    assert plan.over_budget


def test_timeline_deadlines_are_ordered_and_not_before_today(valid_event):
    event = EventInput.model_validate(valid_event)
    plan = finalize_plan(demo_content(event), event, "demo")
    deadlines = [task.deadline for task in plan.prep_tasks]

    assert all(deadline is not None for deadline in deadlines)
    assert deadlines == sorted(deadlines)
    assert all(deadline >= date.today() for deadline in deadlines if deadline)


def test_missing_and_past_dates_are_explained(valid_event):
    valid_event["event_date"] = None
    event_without_date = EventInput.model_validate(valid_event)
    without_date = finalize_plan(demo_content(event_without_date), event_without_date, "demo")
    assert without_date.timeline_notice
    assert all(task.deadline is None for task in without_date.prep_tasks)
    assert without_date.clarifying_questions

    valid_event["event_date"] = (date.today() - timedelta(days=1)).isoformat()
    past_event = EventInput.model_validate(valid_event)
    past = finalize_plan(demo_content(past_event), past_event, "demo")
    assert "past" in (past.timeline_notice or "").lower()
    assert all(task.deadline is None for task in past.prep_tasks)


def test_generated_content_starts_without_user_owned_state(valid_event):
    valid_event["event_date"] = None
    event = EventInput.model_validate(valid_event)
    content = demo_content(event)
    content.expenses[0].actual_amount = 999
    content.expenses[0].status = "confirmed"
    content.prep_tasks[0].completed = True
    content.vendors[0].vendor_name = "Invented business"
    content.vendors[0].status = "booked"

    normalized = normalize_generated_content(content, event)

    assert all(item.actual_amount is None for item in normalized.expenses)
    assert all(item.status == "estimated" for item in normalized.expenses)
    assert all(not task.completed for task in normalized.prep_tasks)
    assert all(vendor.vendor_name == "" for vendor in normalized.vendors)
    assert all(vendor.status == "to_research" for vendor in normalized.vendors)
    assert any("what date" in question.lower() for question in normalized.clarifying_questions)


def test_merge_user_state_preserves_matching_decisions_only(valid_event):
    event = EventInput.model_validate(valid_event)
    original = finalize_plan(demo_content(event), event, "demo")
    original = original.model_copy(
        update={
            "prep_tasks": [
                original.prep_tasks[0].model_copy(update={"completed": True}),
                *original.prep_tasks[1:],
            ],
            "expenses": [
                original.expenses[0].model_copy(
                    update={"actual_amount": 1234, "status": "confirmed"}
                ),
                *original.expenses[1:],
            ],
        }
    )
    generated = normalize_generated_content(demo_content(event), event)
    generated = generated.model_copy(
        update={
            "prep_tasks": [
                *generated.prep_tasks,
                PrepTask(title="Buy a last-minute cake", priority="low"),
            ]
        }
    )

    merged = merge_user_state(original, generated)

    assert merged.prep_tasks[0].completed is True
    assert merged.prep_tasks[0].id == original.prep_tasks[0].id
    assert merged.prep_tasks[-1].title == "Buy a last-minute cake"
    assert merged.prep_tasks[-1].completed is False
    assert merged.prep_tasks[-1].id not in {
        task.id for task in original.prep_tasks
    }
    assert merged.expenses[0].actual_amount == 1234
    assert merged.expenses[0].status == "confirmed"
    assert merged.expenses[0].id == original.expenses[0].id
    assert merged.vendors[0].id == original.vendors[0].id


def test_merge_keeps_user_owned_items_the_model_drops(valid_event):
    event = EventInput.model_validate(valid_event)
    original = finalize_plan(demo_content(event), event, "demo")
    original = original.model_copy(
        update={
            "prep_tasks": [
                original.prep_tasks[0].model_copy(update={"completed": True}),
                *original.prep_tasks[1:],
            ],
            "vendors": [
                original.vendors[0].model_copy(
                    update={"vendor_name": "Saved venue", "status": "quoted"}
                ),
                *original.vendors[1:],
            ],
            "expenses": [
                original.expenses[0].model_copy(
                    update={"actual_amount": 2500, "status": "confirmed"}
                ),
                *original.expenses[1:],
            ],
        }
    )
    generated = normalize_generated_content(demo_content(event), event)
    generated = generated.model_copy(
        update={
            "prep_tasks": generated.prep_tasks[1:],
            "vendors": generated.vendors[1:],
            "expenses": generated.expenses[1:],
        }
    )

    merged = merge_user_state(original, generated)

    assert any(
        task.id == original.prep_tasks[0].id and task.completed
        for task in merged.prep_tasks
    )
    assert any(
        vendor.id == original.vendors[0].id and vendor.vendor_name == "Saved venue"
        for vendor in merged.vendors
    )
    assert any(
        expense.id == original.expenses[0].id
        and expense.actual_amount == 2500
        and expense.status == "confirmed"
        for expense in merged.expenses
    )


def test_merge_keeps_notes_only_vendor_and_status_only_expense(valid_event):
    event = EventInput.model_validate(valid_event)
    original = finalize_plan(demo_content(event), event, "demo")
    original = original.model_copy(
        update={
            "vendors": [
                original.vendors[0].model_copy(
                    update={"notes": "Ask about the accessible entrance.", "status": "contacted"}
                ),
                *original.vendors[1:],
            ],
            "expenses": [
                original.expenses[0].model_copy(update={"status": "quoted"}),
                *original.expenses[1:],
            ],
        }
    )
    generated = normalize_generated_content(demo_content(event), event)
    generated = generated.model_copy(
        update={
            "vendors": generated.vendors[1:],
            "expenses": generated.expenses[1:],
        }
    )

    merged = merge_user_state(original, generated)

    assert any(
        vendor.id == original.vendors[0].id
        and vendor.notes == "Ask about the accessible entrance."
        and vendor.status == "contacted"
        for vendor in merged.vendors
    )
    assert any(
        expense.id == original.expenses[0].id
        and expense.status == "quoted"
        and expense.actual_amount is None
        for expense in merged.expenses
    )


@pytest.mark.parametrize(
    "field,value",
    [("guest_count", 0), ("budget", 0), ("currency", "rupees"), ("description", "short")],
)
def test_event_form_rejects_invalid_values(valid_event, field, value):
    valid_event[field] = value
    with pytest.raises(ValidationError):
        EventInput.model_validate(valid_event)
