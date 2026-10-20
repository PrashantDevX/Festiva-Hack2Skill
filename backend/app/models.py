from datetime import date, datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventInput(StrictModel):
    description: str = Field(min_length=10, max_length=4000)
    event_type: str = Field(min_length=2, max_length=60)
    event_date: date | None = None
    location: str = Field(min_length=2, max_length=160)
    guest_count: int = Field(gt=0, le=100000)
    budget: float = Field(gt=0, le=100000000)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    preferences: str = Field(default="", max_length=1500)
    dietary_needs: str = Field(default="", max_length=500)
    special_requirements: str = Field(default="", max_length=1000)

    @field_validator("description", "event_type", "location")
    @classmethod
    def reject_blank_strings(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be blank.")
        return value

    @field_validator("preferences", "dietary_needs", "special_requirements")
    @classmethod
    def strip_optional_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class Expense(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    category: str = Field(min_length=2, max_length=60)
    item: str = Field(min_length=2, max_length=160)
    estimated_amount: float = Field(ge=0, le=100000000)
    actual_amount: float | None = Field(default=None, ge=0, le=100000000)
    status: Literal["estimated", "quoted", "confirmed"] = "estimated"
    note: str = Field(default="", max_length=300)


class PrepTask(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(min_length=2, max_length=160)
    deadline: date | None = None
    priority: Literal["high", "medium", "low"] = "medium"
    completed: bool = False


class ScheduleItem(StrictModel):
    time: str = Field(min_length=2, max_length=40)
    title: str = Field(min_length=2, max_length=160)
    detail: str = Field(default="", max_length=300)


class Vendor(StrictModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    category: str = Field(min_length=2, max_length=80)
    requirement: str = Field(min_length=2, max_length=240)
    vendor_name: str = Field(default="", max_length=120)
    contact: str = Field(default="", max_length=160)
    quotation: float | None = Field(default=None, ge=0, le=100000000)
    status: Literal["to_research", "contacted", "quoted", "booked"] = "to_research"
    completed: bool = False
    notes: str = Field(default="", max_length=500)


class Idea(StrictModel):
    title: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=2, max_length=400)
    rationale: str = Field(default="", max_length=300)
    estimated_impact: str = Field(default="", max_length=160)


class PlanContent(StrictModel):
    overview: str = Field(min_length=10, max_length=1200)
    clarifying_questions: list[str] = Field(default_factory=list, max_length=8)
    theme_options: list[str] = Field(min_length=1, max_length=5)
    expenses: list[Expense] = Field(min_length=1, max_length=30)
    prep_tasks: list[PrepTask] = Field(min_length=1, max_length=30)
    schedule: list[ScheduleItem] = Field(min_length=1, max_length=20)
    vendors: list[Vendor] = Field(min_length=1, max_length=20)
    ideas: list[Idea] = Field(min_length=1, max_length=20)
    savings: list[str] = Field(default_factory=list, max_length=10)
    assumptions: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("clarifying_questions", "theme_options", "savings", "assumptions")
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(values):
            raise ValueError("List items cannot be blank.")
        return cleaned


# --- AI output schema -------------------------------------------------------
# The model only supplies planning content. User-controlled state (IDs,
# completion flags, actual spend, vendor contact details, booking status) is
# deliberately excluded so a model response cannot overwrite it.


class AIExpense(StrictModel):
    category: str = Field(
        min_length=2, max_length=60, description="Short expense category."
    )
    item: str = Field(
        min_length=2, max_length=160, description="Specific expense line item."
    )
    estimated_amount: float = Field(
        ge=0,
        le=100000000,
        description="Planning estimate in the event currency. Never a quotation.",
    )
    note: str = Field(
        default="",
        max_length=300,
        description="Optional estimate caveat or assumption.",
    )


class AIPrepTask(StrictModel):
    title: str = Field(
        min_length=2, max_length=160, description="Actionable preparation task."
    )
    priority: Literal["high", "medium", "low"] = Field(
        default="medium", description="Task priority."
    )


class AIScheduleItem(StrictModel):
    time: str = Field(
        min_length=2, max_length=40, description="Clock time or schedule phase."
    )
    title: str = Field(min_length=2, max_length=160, description="Schedule item title.")
    detail: str = Field(
        default="", max_length=300, description="Short event-day detail."
    )


class AIVendor(StrictModel):
    category: str = Field(
        min_length=2, max_length=80, description="Vendor category to research."
    )
    requirement: str = Field(
        min_length=2,
        max_length=240,
        description="What to ask or verify. Do not invent a business or a booking.",
    )


class AIIdea(StrictModel):
    title: str = Field(min_length=2, max_length=120, description="Idea title.")
    description: str = Field(
        min_length=2, max_length=400, description="Personalized idea."
    )
    rationale: str = Field(
        default="", max_length=300, description="Why it fits this event."
    )
    estimated_impact: str = Field(
        default="", max_length=160, description="Rough cost/effort impact."
    )


class AIPlanContent(StrictModel):
    overview: str = Field(
        min_length=10,
        max_length=1200,
        description="Concise, personalized event overview.",
    )
    clarifying_questions: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Only essential missing details; never invent a date.",
    )
    theme_options: list[str] = Field(
        min_length=1, max_length=5, description="Theme or concept options."
    )
    expenses: list[AIExpense] = Field(
        min_length=1,
        max_length=20,
        description="Itemized planning estimates covering the whole budget.",
    )
    prep_tasks: list[AIPrepTask] = Field(
        min_length=1, max_length=20, description="Preparation tasks."
    )
    schedule: list[AIScheduleItem] = Field(
        min_length=1, max_length=15, description="Event-day schedule."
    )
    vendors: list[AIVendor] = Field(
        min_length=1,
        max_length=15,
        description="Vendor categories and requirements to research.",
    )
    ideas: list[AIIdea] = Field(
        min_length=1,
        max_length=12,
        description="Personalized theme, decor, menu, and activity ideas.",
    )
    savings: list[str] = Field(
        default_factory=list, max_length=8, description="Cost-saving alternatives."
    )
    assumptions: list[str] = Field(
        default_factory=list,
        max_length=8,
        description="Assumptions and uncertainty notes.",
    )

    @field_validator("clarifying_questions", "theme_options", "savings", "assumptions")
    @classmethod
    def reject_blank_list_items(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if len(cleaned) != len(values):
            raise ValueError("List items cannot be blank.")
        return cleaned

    def to_plan_content(self) -> PlanContent:
        """Add application-owned defaults after strict model validation."""
        return PlanContent(
            overview=self.overview.strip(),
            clarifying_questions=self.clarifying_questions,
            theme_options=self.theme_options,
            expenses=[
                Expense(
                    category=item.category.strip(),
                    item=item.item.strip(),
                    estimated_amount=item.estimated_amount,
                    note=item.note.strip(),
                )
                for item in self.expenses
            ],
            prep_tasks=[
                PrepTask(title=item.title.strip(), priority=item.priority)
                for item in self.prep_tasks
            ],
            schedule=[
                ScheduleItem(
                    time=item.time.strip(),
                    title=item.title.strip(),
                    detail=item.detail.strip(),
                )
                for item in self.schedule
            ],
            vendors=[
                Vendor(
                    category=item.category.strip(),
                    requirement=item.requirement.strip(),
                )
                for item in self.vendors
            ],
            ideas=[
                Idea(
                    title=item.title.strip(),
                    description=item.description.strip(),
                    rationale=item.rationale.strip(),
                    estimated_impact=item.estimated_impact.strip(),
                )
                for item in self.ideas
            ],
            savings=self.savings,
            assumptions=self.assumptions,
        )


class RevisionOutput(StrictModel):
    event: EventInput
    plan: AIPlanContent


class Plan(PlanContent):
    id: str
    created_at: datetime
    updated_at: datetime
    event: EventInput
    estimated_total: float
    actual_total: float
    remaining_budget: float
    over_budget: bool
    timeline_notice: str | None = None
    ai_mode: Literal["live", "demo"]

    def content(self) -> PlanContent:
        """Return only the model-generated content, excluding user-owned state."""
        return PlanContent.model_validate(
            {key: getattr(self, key) for key in PlanContent.model_fields}
        )


class RevisionRequest(StrictModel):
    instructions: str = Field(min_length=3, max_length=1500)

    @field_validator("instructions")
    @classmethod
    def reject_blank_instructions(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Enter a revision instruction.")
        return value


class CompletionUpdate(StrictModel):
    completed: bool


class VendorUpdate(StrictModel):
    completed: bool | None = None
    vendor_name: str | None = Field(default=None, max_length=120)
    contact: str | None = Field(default=None, max_length=160)
    quotation: float | None = Field(default=None, ge=0, le=100000000)
    status: Literal["to_research", "contacted", "quoted", "booked"] | None = None
    notes: str | None = Field(default=None, max_length=500)


class ExpenseUpdate(StrictModel):
    actual_amount: float | None = Field(default=None, ge=0, le=100000000)
    status: Literal["estimated", "quoted", "confirmed"] | None = None


class PlanRecord(StrictModel):
    plan: Plan


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
