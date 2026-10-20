from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
import time
from threading import Lock

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

load_dotenv()

from . import database
from .ai import (
    AIServiceError,
    ai_status,
    cache_entries,
    generate_content,
    revise_content,
)
from .observability import metrics
from .models import (
    CompletionUpdate,
    EventInput,
    ExpenseUpdate,
    Plan,
    PlanContent,
    RevisionRequest,
    VendorUpdate,
)
from .services import finalize_plan, merge_user_state


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize_database()
    yield


app = FastAPI(
    title="Festiva AI",
    description="Budget-aware, personalized event planning API.",
    version="1.0.0",
    lifespan=lifespan,
)
origins = [
    item.strip()
    for item in os.getenv(
        "FESTIVA_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)


class RequestSizeLimitMiddleware:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/"):
            await self.application(scope, receive, send)
            return

        lengths = [
            value for name, value in scope.get("headers", []) if name.lower() == b"content-length"
        ]
        if lengths:
            try:
                if int(lengths[0]) > 64 * 1024:
                    await JSONResponse(
                        status_code=413, content={"detail": "Request is too large."}
                    )(scope, receive, send)
                    return
            except ValueError:
                await JSONResponse(
                    status_code=400, content={"detail": "Invalid request size."}
                )(scope, receive, send)
                return

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            if message["type"] != "http.request":
                continue
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > 64 * 1024:
                await JSONResponse(
                    status_code=413, content={"detail": "Request is too large."}
                )(scope, receive, send)
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body = b"".join(chunks)
        delivered = False

        async def replay_body():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.application(scope, replay_body, send)


app.add_middleware(RequestSizeLimitMiddleware)
_rate_lock = Lock()
_requests_by_ip: dict[str, list[float]] = {}
_ai_rate_lock = Lock()
_ai_requests_by_ip: dict[str, list[float]] = {}
_plan_write_lock = Lock()
AI_WINDOW_SECONDS = 600
AI_REQUESTS_PER_WINDOW = 10


def _reserve_ai_request(request: Request) -> None:
    """Apply a separate, tighter budget to calls that may reach Gemini."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    with _ai_rate_lock:
        recent = [
            stamp
            for stamp in _ai_requests_by_ip.get(client_ip, [])
            if now - stamp < AI_WINDOW_SECONDS
        ]
        if len(recent) >= AI_REQUESTS_PER_WINDOW:
            retry_after = max(
                1, int(AI_WINDOW_SECONDS - (now - recent[0])) + 1
            )
            raise HTTPException(
                status_code=429,
                detail=(
                    "Too many plan generations from this address. Wait a few "
                    "minutes and retry."
                ),
                headers={"Retry-After": str(retry_after)},
            )
        recent.append(now)
        _ai_requests_by_ip[client_ip] = recent


@app.middleware("http")
async def request_limits(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with _rate_lock:
            recent = [stamp for stamp in _requests_by_ip.get(client_ip, []) if now - stamp < 60]
            if len(recent) >= 120:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Wait a minute and retry."},
                    headers={"Retry-After": "60"},
                )
            recent.append(now)
            _requests_by_ip[client_ip] = recent
    return await call_next(request)


@app.exception_handler(AIServiceError)
async def ai_error_handler(_: Request, exc: AIServiceError):
    headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
    return JSONResponse(
        status_code=exc.http_status,
        content={"detail": str(exc), "category": exc.category},
        headers=headers,
    )


@app.get("/api/health")
def health():
    status_info = ai_status()
    ready = status_info["ai_mode"] == "demo" or (
        status_info["ai_mode"] == "live" and status_info["provider_configured"]
    )
    return {"status": "ok" if ready else "degraded", **status_info}


@app.get("/api/diagnostics")
def diagnostics():
    """Aggregate operational counters. Never includes prompts, plans, or keys."""
    return {
        "status": "ok",
        "ai": ai_status(),
        "database": {"plans": database.count_plans()},
        "cache": {"generation_entries": cache_entries()},
        "metrics": metrics.snapshot(),
    }


@app.get("/api/plans", response_model=list[Plan])
def read_plans():
    return database.list_plans()


@app.post("/api/plans", response_model=Plan, status_code=status.HTTP_201_CREATED)
def create_plan(event: EventInput, request: Request):
    _reserve_ai_request(request)
    content, mode = generate_content(event)
    plan = finalize_plan(content, event, mode)
    return database.save_plan(plan)


@app.get("/api/plans/{plan_id}", response_model=Plan)
def read_plan(plan_id: str):
    plan = database.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return plan


@app.post("/api/plans/{plan_id}/revise", response_model=Plan)
def revise_plan(plan_id: str, request: RevisionRequest, http_request: Request):
    previous = database.get_plan(plan_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    _reserve_ai_request(http_request)
    try:
        event, content, mode = revise_content(previous, request.instructions)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422, detail="The requested revision contains invalid event details."
        ) from exc
    # Re-read under the write lock so a checklist or spend update made while
    # Gemini was generating is not lost by this save.
    with _plan_write_lock:
        latest = database.get_plan(plan_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="Plan not found.")
        content = merge_user_state(latest, content)
        plan = finalize_plan(content, event, mode, existing=latest)
        return database.save_plan(plan)


def _update_plan(plan_id: str, update_content) -> Plan:
    with _plan_write_lock:
        plan = database.get_plan(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found.")
        updated = update_content(plan)
        updated = updated.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        return database.save_plan(updated)


@app.patch("/api/plans/{plan_id}/tasks/{task_id}", response_model=Plan)
def update_task(plan_id: str, task_id: str, update: CompletionUpdate):
    def apply(plan: Plan) -> Plan:
        if not any(task.id == task_id for task in plan.prep_tasks):
            raise HTTPException(status_code=404, detail="Preparation task not found.")
        tasks = [
            task.model_copy(update={"completed": update.completed})
            if task.id == task_id
            else task
            for task in plan.prep_tasks
        ]
        return plan.model_copy(update={"prep_tasks": tasks})

    return _update_plan(plan_id, apply)


@app.patch("/api/plans/{plan_id}/vendors/{vendor_id}", response_model=Plan)
def update_vendor(plan_id: str, vendor_id: str, update: VendorUpdate):
    def apply(plan: Plan) -> Plan:
        if not any(vendor.id == vendor_id for vendor in plan.vendors):
            raise HTTPException(status_code=404, detail="Vendor checklist item not found.")
        changes = {
            field: getattr(update, field)
            for field in update.model_fields_set
        }
        if not changes:
            raise HTTPException(status_code=422, detail="Provide a vendor field to update.")
        vendors = [
            vendor.model_copy(update=changes)
            if vendor.id == vendor_id
            else vendor
            for vendor in plan.vendors
        ]
        return plan.model_copy(update={"vendors": vendors})

    return _update_plan(plan_id, apply)


@app.patch("/api/plans/{plan_id}/expenses/{expense_id}", response_model=Plan)
def update_expense(plan_id: str, expense_id: str, update: ExpenseUpdate):
    def apply(plan: Plan) -> Plan:
        if not any(item.id == expense_id for item in plan.expenses):
            raise HTTPException(status_code=404, detail="Expense not found.")
        changes: dict[str, object] = {}
        if "actual_amount" in update.model_fields_set:
            changes["actual_amount"] = update.actual_amount
        if update.status is not None:
            changes["status"] = update.status
        if not changes:
            raise HTTPException(status_code=422, detail="Provide an expense field to update.")
        expenses = [
            item.model_copy(
                update=changes
            )
            if item.id == expense_id
            else item
            for item in plan.expenses
        ]
        content = PlanContent(
            overview=plan.overview,
            theme_options=plan.theme_options,
            expenses=expenses,
            prep_tasks=plan.prep_tasks,
            schedule=plan.schedule,
            vendors=plan.vendors,
            ideas=plan.ideas,
            savings=plan.savings,
            assumptions=plan.assumptions,
        )
        return finalize_plan(content, plan.event, plan.ai_mode, existing=plan)

    return _update_plan(plan_id, apply)
