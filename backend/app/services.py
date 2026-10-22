import difflib
import re
from datetime import date, timedelta
from uuid import uuid4

from .models import (
    EventInput,
    Expense,
    Plan,
    PlanContent,
    PrepTask,
    Vendor,
    utc_now,
)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _similar(left: str, right: str, threshold: float = 0.72) -> bool:
    left_key, right_key = _normalize(left), _normalize(right)
    if left_key == right_key:
        return True
    return difflib.SequenceMatcher(None, left_key, right_key).ratio() >= threshold


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = _normalize(value)
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


MISSING_DATE_QUESTION = (
    "What date do you have in mind? Preparation deadlines depend on the event date."
)


def normalize_generated_content(content: PlanContent, event: EventInput) -> PlanContent:
    """Remove model-authored user state and enforce deterministic planning rules.

    IDs, completion flags, actual spending, vendor contact details, quotations,
    and booking states are owned by the application and the user. A generated
    plan starts from a clean, clearly estimated state.
    """
    expenses = [
        expense.model_copy(
            update={"actual_amount": None, "status": "estimated"}
        )
        for expense in content.expenses
    ]
    prep_tasks = [
        task.model_copy(update={"completed": False})
        for task in content.prep_tasks
    ]
    vendors = [
        vendor.model_copy(
            update={
                "vendor_name": "",
                "contact": "",
                "quotation": None,
                "status": "to_research",
                "completed": False,
                "notes": "",
            }
        )
        for vendor in content.vendors
    ]
    questions = list(content.clarifying_questions)
    if event.event_date is None and not any(
        "date" in question.lower() for question in questions
    ):
        questions.append(MISSING_DATE_QUESTION)
    return content.model_copy(
        update={
            "expenses": expenses,
            "prep_tasks": prep_tasks,
            "vendors": vendors,
            "clarifying_questions": questions[:8],
            "theme_options": _dedupe(content.theme_options)[:5],
            "savings": _dedupe(content.savings)[:8],
            "assumptions": _dedupe(content.assumptions)[:8],
        }
    )


def _merge_tasks(existing: list[PrepTask], generated: list[PrepTask]) -> list[PrepTask]:
    used_ids: set[str] = set()
    merged: list[PrepTask] = []
    for task in generated:
        match = next(
            (
                old
                for old in existing
                if old.id not in used_ids and _similar(old.title, task.title)
            ),
            None,
        )
        if match is None:
            merged.append(task)
            continue
        used_ids.add(match.id)
        merged.append(
            task.model_copy(update={"id": match.id, "completed": match.completed})
        )

    # A model that drops a completed task must not erase the user's work.
    merged.extend(old for old in existing if old.id not in used_ids and old.completed)
    return merged


def _merge_vendors(existing: list[Vendor], generated: list[Vendor]) -> list[Vendor]:
    used_ids: set[str] = set()
    merged: list[Vendor] = []
    for vendor in generated:
        exact = next(
            (
                old
                for old in existing
                if old.id not in used_ids
                and _normalize(old.category) == _normalize(vendor.category)
            ),
            None,
        )
        match = exact or next(
            (
                old
                for old in existing
                if old.id not in used_ids
                and _similar(old.category, vendor.category, threshold=0.8)
            ),
            None,
        )
        if match is None:
            merged.append(vendor)
            continue
        used_ids.add(match.id)
        merged.append(
            vendor.model_copy(
                update={
                    "id": match.id,
                    "vendor_name": match.vendor_name,
                    "contact": match.contact,
                    "quotation": match.quotation,
                    "status": match.status,
                    "completed": match.completed,
                    "notes": match.notes,
                }
            )
        )

    # Preserve researched vendor details even if the model changed the category
    # wording enough to miss similarity matching.
    merged.extend(
        old for old in existing if old.id not in used_ids and old.has_user_state()
    )
    return merged


def _merge_expenses(existing: list[Expense], generated: list[Expense]) -> list[Expense]:
    used_ids: set[str] = set()
    merged: list[Expense] = []
    for expense in generated:
        exact = next(
            (
                old
                for old in existing
                if old.id not in used_ids
                and _similar(old.item, expense.item)
                and _similar(old.category, expense.category, threshold=0.8)
            ),
            None,
        )
        match = exact or next(
            (
                old
                for old in existing
                if old.id not in used_ids
                and _similar(old.category, expense.category, threshold=0.8)
            ),
            None,
        )
        if match is None:
            merged.append(expense)
            continue
        used_ids.add(match.id)
        merged.append(
            expense.model_copy(
                update={
                    "id": match.id,
                    "actual_amount": match.actual_amount,
                    "status": match.status,
                }
            )
        )

    # Actual spend and quotation status are user-owned records.
    merged.extend(
        old for old in existing if old.id not in used_ids and old.has_user_state()
    )
    return merged


def merge_user_state(existing: Plan, generated: PlanContent) -> PlanContent:
    """Preserve user decisions when a live model revises the plan.

    Model output is untrusted. The model may rephrase titles, so matching uses a
    normalized title plus a conservative similarity score. Unmatched items keep
    their generated defaults and therefore never inherit another item's state.
    """
    return generated.model_copy(
        update={
            "prep_tasks": _merge_tasks(existing.prep_tasks, generated.prep_tasks),
            "vendors": _merge_vendors(existing.vendors, generated.vendors),
            "expenses": _merge_expenses(existing.expenses, generated.expenses),
        }
    )


def finalize_plan(
    content: PlanContent,
    event: EventInput,
    ai_mode: str,
    existing: Plan | None = None,
) -> Plan:
    """Calculate authoritative totals and align deadlines to the event date."""
    rounded_expenses = content.model_copy(
        update={
            "expenses": [
                expense.model_copy(
                    update={
                        "estimated_amount": round(expense.estimated_amount, 2),
                        "actual_amount": (
                            round(expense.actual_amount, 2)
                            if expense.actual_amount is not None
                            else None
                        ),
                    }
                )
                for expense in content.expenses
            ]
        }
    )
    estimated_total = round(
        sum(item.estimated_amount for item in rounded_expenses.expenses), 2
    )
    actual_total = round(
        sum(item.actual_amount or 0 for item in rounded_expenses.expenses), 2
    )
    remaining = round(event.budget - estimated_total, 2)
    timeline_notice = None
    tasks = rounded_expenses.prep_tasks

    if event.event_date is None:
        timeline_notice = "Add an event date to assign calendar deadlines."
        tasks = [task.model_copy(update={"deadline": None}) for task in tasks]
    elif event.event_date < date.today():
        timeline_notice = (
            "This event date is in the past. Review and reschedule the remaining tasks."
        )
        tasks = [task.model_copy(update={"deadline": None}) for task in tasks]
    else:
        offsets = [90, 60, 30, 14, 7, 3, 1, 0]
        tasks = [
            task.model_copy(
                update={
                    "deadline": max(
                        date.today(),
                        event.event_date
                        - timedelta(days=offsets[min(len(offsets) - 1, index)]),
                    )
                }
            )
            for index, task in enumerate(tasks)
        ]
        if event.event_date - date.today() <= timedelta(days=7):
            timeline_notice = (
                "Your event is within a week. Confirm bookings, dietary needs, "
                "transport, and event-day timings now."
            )

    content_update = rounded_expenses.model_copy(update={"prep_tasks": tasks})
    return Plan(
        **content_update.model_dump(),
        id=existing.id if existing else uuid4().hex,
        created_at=existing.created_at if existing else utc_now(),
        updated_at=utc_now(),
        event=event,
        estimated_total=estimated_total,
        actual_total=actual_total,
        remaining_budget=remaining,
        over_budget=estimated_total > event.budget or actual_total > event.budget,
        timeline_notice=timeline_notice,
        ai_mode=ai_mode,
    )


def _demo_expenses(event: EventInput) -> list[dict[str, object]]:
    allocations = [
        ("Venue", "Venue and setup", 0.20),
        ("Food", "Food and refreshments", 0.35),
        ("Decor", "Decorations, florals, and lighting", 0.14),
        ("Photography", "Photography and keepsakes", 0.10),
        ("Entertainment", "Music, activities, and hosting", 0.08),
        ("Other", "Invitations, transport, and contingency", 0.13),
    ]
    expenses: list[dict[str, object]] = []
    running = 0.0
    for index, (category, item, share) in enumerate(allocations):
        amount = (
            round(event.budget - running, 2)
            if index == len(allocations) - 1
            else round(event.budget * share, 2)
        )
        running += amount
        expenses.append(
            {
                "category": category,
                "item": item,
                "estimated_amount": amount,
                "note": "Planning estimate; request a real quotation.",
            }
        )
    return expenses


def _demo_themes(event: EventInput) -> list[str]:
    preferred_style = event.preferences.strip()
    event_name = event.event_type.lower()
    themes = [
        f"{preferred_style[:70]} inspired {event_name}"
        if preferred_style
        else f"Personalized {event_name} celebration",
        "Warm, relaxed gathering with a clear guest journey",
    ]
    if event.dietary_needs:
        themes.append("Inclusive table with clearly labelled dietary options")
    return themes


def _demo_assumptions(event: EventInput) -> list[str]:
    preferred_style = event.preferences.strip()
    assumptions = [
        "All amounts are planning estimates, not quotations or confirmations.",
        "Vendor checklist entries are categories to research, not verified businesses.",
        f"Plan assumes {event.guest_count} guests and a working budget of "
        f"{event.currency} {event.budget:,.0f}.",
    ]
    if preferred_style:
        assumptions.append(f"Preferences recorded: {preferred_style[:250]}.")
    if event.dietary_needs:
        assumptions.append(f"Dietary requirements recorded: {event.dietary_needs[:250]}.")
    if event.special_requirements:
        assumptions.append(
            f"Special requirements recorded: {event.special_requirements[:250]}."
        )
    return assumptions


def _demo_questions(event: EventInput) -> list[str]:
    questions: list[str] = []
    if event.event_date is None:
        questions.append(MISSING_DATE_QUESTION)
    if not event.dietary_needs:
        questions.append("Do any guests have dietary needs or allergies to plan for?")
    return questions


def demo_content(event: EventInput) -> PlanContent:
    """Create a transparent, deterministic demo plan from the submitted event."""
    event_name = event.event_type.lower()
    date_phrase = (
        f" on {event.event_date.isoformat()}" if event.event_date else " on a date to be decided"
    )
    return PlanContent(
        overview=(
            f"A practical {event_name} for {event.guest_count} guests in "
            f"{event.location}{date_phrase}, shaped around a "
            f"{event.currency} {event.budget:,.0f} budget and your stated preferences. "
            "The plan prioritizes guest comfort, clear next steps, and written quotes "
            "before any commitment."
        ),
        clarifying_questions=_demo_questions(event)[:8],
        theme_options=_demo_themes(event)[:5],
        expenses=_demo_expenses(event),
        prep_tasks=[
            {"title": "Confirm venue capacity, accessibility, and included setup", "priority": "high"},
            {"title": "Shortlist caterers and request written quotes for the guest count", "priority": "high"},
            {"title": "Choose a theme and confirm decoration requirements", "priority": "medium"},
            {"title": "Send invitations and collect dietary and accessibility needs", "priority": "medium"},
            {"title": "Confirm suppliers, deposits, and cancellation terms", "priority": "high"},
            {"title": "Share the event-day schedule with helpers and vendors", "priority": "high"},
            {"title": "Prepare a final contingency and cleanup plan", "priority": "low"},
        ],
        schedule=[
            {"time": "Before arrival", "title": "Venue and vendor check-in", "detail": "Walk the space, confirm setup, and test sound and lighting."},
            {"time": "Guest arrival", "title": "Welcome and settling in", "detail": "Allow a relaxed arrival window with clear signage and seating."},
            {"time": "Main moment", "title": "Celebration, meal, and remarks", "detail": "Adjust timing to your venue, traditions, and guest needs."},
            {"time": "Open time", "title": "Music, activities, and photos", "detail": "Keep one flexible block for conversation and group photos."},
            {"time": "Closing", "title": "Thank guests and wrap up", "detail": "Confirm transport, vendor collection, and cleanup responsibilities."},
        ],
        vendors=[
            {"category": "Venue", "requirement": "Compare capacity, accessibility, parking, and included setup."},
            {"category": "Catering", "requirement": f"Request a menu quote for {event.guest_count} guests and stated dietary needs."},
            {"category": "Decor", "requirement": "Request a scope and itemized quote that fits the budget and theme."},
            {"category": "Photography", "requirement": "Compare coverage hours, deliverables, and cancellation terms."},
            {"category": "Music and hosting", "requirement": "Confirm equipment, playlist input, and event-day timing."},
        ],
        ideas=[
            {
                "title": "Make the welcome personal",
                "description": f"Add a welcome moment that reflects your {event_name} and the preferences you shared.",
                "rationale": "Uses the event type and details from your brief rather than assuming a tradition.",
                "estimated_impact": "Low-cost; customize to your venue.",
            },
            {
                "title": "Plan an inclusive menu",
                "description": f"Ask guests for dietary needs and discuss {event.dietary_needs or 'suitable options'} with the caterer.",
                "rationale": "Makes meal planning responsive to the requirements you provide.",
                "estimated_impact": "Confirm any price difference with the caterer.",
            },
            {
                "title": "Create one memorable decor focal point",
                "description": f"Choose a single photo-friendly backdrop or table moment that carries the {event_name} theme.",
                "rationale": "Concentrates decoration spending where guests will notice it most.",
                "estimated_impact": "Can be built from rented or reused pieces.",
            },
            {
                "title": "Give guests something to do together",
                "description": "Add a short, optional activity such as a memory wall, playlist request, or group photo challenge.",
                "rationale": "Encourages connection without a costly production.",
                "estimated_impact": "Low-cost; needs a small amount of hosting time.",
            },
        ],
        savings=[
            "Compare at least three itemized quotations before booking.",
            "Prioritize guest comfort and one or two high-impact details over many upgrades.",
            "Keep a contingency line and confirm taxes, delivery, and setup fees.",
            "Reuse or rent statement decor instead of buying single-use items.",
        ],
        assumptions=_demo_assumptions(event)[:8],
    )


def adjust_demo_plan(plan: Plan, instructions: str) -> tuple[EventInput, PlanContent]:
    """Handle explicit demo revisions while keeping unrelated plan details."""
    event = plan.event
    text = instructions.lower()
    budget_match = re.search(r"(?:budget|spend|limit)[^\d]{0,30}([\d,]+)", text)
    guest_match = re.search(r"(?:guest|people|attendees)[^\d]{0,30}([\d,]+)", text)
    date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", instructions)
    updates: dict[str, object] = {}
    expenses = plan.expenses
    if budget_match:
        value = float(budget_match.group(1).replace(",", ""))
        if value > 0:
            updates["budget"] = value
            expenses = [
                item.model_copy(
                    update={
                        "estimated_amount": round(
                            value * item.estimated_amount / max(plan.estimated_total, 1), 2
                        )
                    }
                )
                for item in plan.expenses
            ]
            difference = round(value - sum(item.estimated_amount for item in expenses), 2)
            expenses[-1] = expenses[-1].model_copy(
                update={"estimated_amount": expenses[-1].estimated_amount + difference}
            )
    if guest_match:
        guest_count = int(guest_match.group(1).replace(",", ""))
        updates["guest_count"] = guest_count
        vendors = [
            vendor.model_copy(
                update={
                    "requirement": vendor.requirement.replace(
                        str(event.guest_count), str(guest_count)
                    )
                }
            )
            for vendor in plan.vendors
        ]
    else:
        vendors = plan.vendors
    if date_match:
        updates["event_date"] = date_match.group(1)
    if not budget_match and not guest_match and not date_match:
        updates["preferences"] = (event.preferences + " " + instructions).strip()
    event = EventInput.model_validate(event.model_copy(update=updates).model_dump())
    overview = plan.overview
    if not budget_match and not guest_match and not date_match:
        overview = f"{overview} Revision requested: {instructions}"
    content = plan.content().model_copy(
        update={
            "overview": overview,
            "expenses": expenses,
            "vendors": vendors,
        }
    )
    return event, content
