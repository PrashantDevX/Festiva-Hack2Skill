from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time
from threading import Lock

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

load_dotenv()

from . import auth, database
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

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.initialize_database()
    if (
        os.getenv("VERCEL")
        and database.storage_backend() == "sqlite"
        and not os.getenv("FESTIVA_DB_PATH")
    ):
        logger.warning(
            "Vercel detected without Blob storage or FESTIVA_DB_PATH; using "
            "ephemeral /tmp/festiva.db. Plans may not persist across instances."
        )
    if os.getenv("VERCEL") and not auth.session_configured():
        logger.error(
            "FESTIVA_SESSION_SECRET is missing or shorter than 32 characters. "
            "Plan routes will return 503 until it is configured."
        )
    yield


app = FastAPI(
    title="Festiva AI",
    description="Budget-aware, personalized event planning API.",
    version="1.0.0",
    lifespan=lifespan,
)
origins = [
    item.strip().rstrip("/")
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


_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_plan_path(path: str) -> bool:
    return path == "/api/plans" or path.startswith("/api/plans/")


def _origin_is_allowed(request: Request, origin: str) -> bool:
    normalized = origin.rstrip("/")
    if normalized in origins:
        return True
    host = request.headers.get("host", "").strip()
    if not host:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    scheme = (
        forwarded_proto.split(",")[0].strip()
        if forwarded_proto
        else request.url.scheme
    )
    return normalized == f"{scheme}://{host}"


def _request_is_https(request: Request) -> bool:
    if os.getenv("VERCEL"):
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return (
        request.url.scheme == "https"
        or forwarded_proto.split(",")[0].strip() == "https"
    )


def _harden_response(response, path: str):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Referrer-Policy", "strict-origin-when-cross-origin"
    )
    response.headers.setdefault(
        "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'self'",
    )
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def security_and_session(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and request.method in _UNSAFE_METHODS:
        origin = request.headers.get("origin")
        if origin and not _origin_is_allowed(request, origin):
            return _harden_response(
                JSONResponse(
                    status_code=403,
                    content={"detail": "Cross-origin request blocked."},
                ),
                path,
            )

    new_token: str | None = None
    if _is_plan_path(path) and request.method != "OPTIONS":
        owner_id = auth.validate_session(
            request.cookies.get(auth.SESSION_COOKIE)
        )
        if owner_id is None:
            try:
                owner_id, new_token = auth.issue_session()
            except auth.SessionConfigError:
                logger.error(
                    "Anonymous session configuration is missing or invalid."
                )
                return _harden_response(
                    JSONResponse(
                        status_code=503,
                        content={
                            "detail": "Session service is not configured."
                        },
                    ),
                    path,
                )
        request.state.owner_id = owner_id

    response = await call_next(request)

    if new_token is not None:
        response.set_cookie(
            auth.SESSION_COOKIE,
            new_token,
            max_age=auth.SESSION_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax",
            secure=_request_is_https(request),
            path="/",
        )
    return _harden_response(response, path)


def _require_owner(request: Request) -> str:
    owner_id = getattr(request.state, "owner_id", None)
    if not isinstance(owner_id, str) or not owner_id:
        raise HTTPException(
            status_code=401, detail="A browser session is required."
        )
    return owner_id


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
        "auth": {
            "mode": "anonymous-signed-session",
            "configured": auth.session_configured(),
        },
        "database": {
            "backend": database.storage_backend(),
            "plans": database.count_plans(),
        },
        "cache": {"generation_entries": cache_entries()},
        "metrics": metrics.snapshot(),
    }


@app.get("/api/plans", response_model=list[Plan])
def read_plans(request: Request):
    return database.list_plans(_require_owner(request))


@app.post("/api/plans", response_model=Plan, status_code=status.HTTP_201_CREATED)
def create_plan(event: EventInput, request: Request):
    owner_id = _require_owner(request)
    _reserve_ai_request(request)
    content, mode = generate_content(event)
    plan = finalize_plan(content, event, mode)
    return database.save_plan(plan, owner_id)


@app.get("/api/plans/{plan_id}", response_model=Plan)
def read_plan(plan_id: str, request: Request):
    plan = database.get_plan(plan_id, _require_owner(request))
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found.")
    return plan


@app.post("/api/plans/{plan_id}/revise", response_model=Plan)
def revise_plan(plan_id: str, request: RevisionRequest, http_request: Request):
    owner_id = _require_owner(http_request)
    previous = database.get_plan(plan_id, owner_id)
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
        latest = database.get_plan(plan_id, owner_id)
        if latest is None:
            raise HTTPException(status_code=404, detail="Plan not found.")
        content = merge_user_state(latest, content)
        plan = finalize_plan(content, event, mode, existing=latest)
        return database.save_plan(plan, owner_id)


def _update_plan(plan_id: str, owner_id: str, update_content) -> Plan:
    with _plan_write_lock:
        plan = database.get_plan(plan_id, owner_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Plan not found.")
        updated = update_content(plan)
        updated = updated.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        return database.save_plan(updated, owner_id)


@app.patch("/api/plans/{plan_id}/tasks/{task_id}", response_model=Plan)
def update_task(
    plan_id: str, task_id: str, update: CompletionUpdate, request: Request
):
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

    return _update_plan(plan_id, _require_owner(request), apply)


@app.patch("/api/plans/{plan_id}/vendors/{vendor_id}", response_model=Plan)
def update_vendor(
    plan_id: str, vendor_id: str, update: VendorUpdate, request: Request
):
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

    return _update_plan(plan_id, _require_owner(request), apply)


@app.patch("/api/plans/{plan_id}/expenses/{expense_id}", response_model=Plan)
def update_expense(
    plan_id: str, expense_id: str, update: ExpenseUpdate, request: Request
):
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

    return _update_plan(plan_id, _require_owner(request), apply)


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
async def api_not_found(path: str):
    """Keep unknown API paths as JSON 404s instead of the SPA fallback."""
    raise HTTPException(status_code=404, detail="API route not found.")


_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    if hasattr(app, "frontend"):
        app.frontend("/", directory=str(_FRONTEND_DIST))
    else:  # compatibility with older FastAPI releases
        from fastapi.staticfiles import StaticFiles

        app.mount(
            "/",
            StaticFiles(directory=str(_FRONTEND_DIST), html=True),
            name="frontend",
        )
