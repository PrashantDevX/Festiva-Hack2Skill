# Festiva AI

Festiva AI turns an event brief into a budget-aware, date-conscious celebration plan. It supports weddings, birthdays, anniversaries, college events, and community celebrations.

The repository is a working local-first application. It is **not deployed**, and no live Gemini response has been verified in this environment because no `GEMINI_API_KEY` is available. The demo mode is fully functional and is labeled everywhere it appears.

## Architecture

```text
React + TypeScript (Vite)
        │  same-origin /api
        ▼
FastAPI + Pydantic
        │
        ├── Gemini Interactions API (live mode, server-side key)
        │     └── structured JSON -> strict Pydantic validation
        │
        ├── deterministic planner (demo mode)
        │
        └── deterministic budget/timeline/user-state layer
              └── SQLite (WAL)
```

- **Frontend:** React, TypeScript, and Vite. The UI creates plans, refines them, tracks tasks/vendors/actual spend, lists saved plans, and exports JSON. It calls the backend through the Vite `/api` proxy in development.
- **Backend:** FastAPI with Pydantic request/response models. Routes validate input, call the AI service, then hand the generated content to deterministic business logic.
- **AI layer:** official `google-genai` SDK using the Interactions API. Gemini supplies **planning content only**. The application owns all IDs, completion flags, actual spending, vendor contact details, booking status, totals, and deadlines.
- **Persistence:** SQLite with WAL mode and a busy timeout. `FESTIVA_DB_PATH` selects the file. The schema is created at startup; there is no migration tool yet.

### Request flow

```text
Event form
  -> FastAPI validation
  -> AI generation (Gemini or deterministic demo)
  -> strict schema validation
  -> normalize generated content (drop model-authored user state)
  -> deterministic totals + deadline alignment
  -> SQLite
  -> UI
```

For revisions, the backend sends only planning content plus a compact summary of user decisions. After validation it deterministically merges completed tasks, vendor details, quotations, statuses, and actual spend back into the result, and re-appends user-owned items the model dropped. A model cannot erase those decisions, silently drop the event date, or change the currency without an explicit currency request.

## Gemini integration

| Item | Value |
|---|---|
| Provider | Google Gemini via the official `google-genai` SDK (`>=2.31,<3`; installed and tested with `2.31.0`) |
| API | Interactions API (`client.interactions.create`) |
| Default model | `gemini-3.8-flash` |
| Model configuration | `GEMINI_MODEL` (server-side, validated before use) |
| Output mode | Structured JSON through `response_format` plus strict Pydantic validation |
| State | `store=False` (stateless API request; no provider-side conversation retained) |
| Thinking | `thinking_level="low"` for plan generation |
| Output cap | `FESTIVA_AI_MAX_OUTPUT_TOKENS=4096` by default |
| Timeout | `GEMINI_TIMEOUT_SECONDS=45` by default (bounded to 5–120 seconds) |

Official documentation used (checked **2026-10-21**):

- Models: <https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash>
- Pricing and free tier: <https://ai.google.dev/gemini-api/docs/pricing>
- Interactions API: <https://ai.google.dev/gemini-api/docs/interactions-overview>
- Structured output: <https://ai.google.dev/gemini-api/docs/structured-output>
- Rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
- SDKs: <https://ai.google.dev/gemini-api/docs/libraries>

### Free-tier caveat

The official pricing page checked on 2026-10-21 lists standard **Free Tier** input and output for Gemini 3.8 Flash as free of charge. Google states that free-tier content may be used to improve Google products. Exact RPM/RPD limits are shown per project in AI Studio rather than as a single published number. This project therefore does **not** hardcode or claim specific free-tier quota figures.

## Requirements and evidence

| Requirement / metric | Implementation | Evidence |
|---|---|---|
| Event creation, missing-date clarification, personalization | `frontend/src/App.tsx`, `backend/app/main.py`, `backend/app/ai.py` | API workflow tests; form validation tests |
| GenAI planning and revision | `backend/app/ai.py` | Official Gemini SDK path; mocked live-mode tests; live call not verified without a key |
| Independently calculated budget | `backend/app/services.py` | Unit tests for totals, remaining balance, actual spend, overruns |
| Event-date-aware preparation | `backend/app/services.py` | Timeline ordering, missing-date, and past-date tests |
| Persistent plans and checklists | `backend/app/database.py`, `backend/app/main.py` | SQLite-backed API and E2E workflow |
| Save, retrieve, revise, export | `backend/app/main.py`, `frontend/src/App.tsx` | Persisted plan API, E2E revision, JSON export |
| Preserve user decisions on revision | `backend/app/services.py`, `backend/app/ai.py` | Unit tests for completed tasks, vendor details, actual spend, date, currency |
| Safe AI failures | `backend/app/ai.py`, `backend/app/main.py` | Tests for missing key, bad model, 429, timeout, malformed output |
| Efficient AI usage | `backend/app/ai.py`, `backend/app/cache.py` | TTL cache, single-flight lock, bounded retries, token metrics |
| Accessible, responsive workspace | `frontend/src/App.tsx`, `frontend/src/style.css` | Skip link, labels, focus styles, status announcements, reduced motion, responsive layout |
| Security and reliability | `backend/app/ai.py`, `backend/app/main.py` | Server-only key, input bounds, body limit, rate limits, strict validation, safe errors |

## Requirements

- Python 3.11+ (this environment used Python 3.13.2)
- Node.js 20+ (this environment used Node 24.15.0)
- A Gemini API key for live mode (optional; demo mode needs no key)

## Run locally

1. Create a Python environment and install backend dependencies:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r backend\requirements.txt
   ```

2. Configure the backend:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env`:

   ```dotenv
   FESTIVA_AI_MODE=live
   GEMINI_API_KEY=your-server-side-key
   GEMINI_MODEL=gemini-3.8-flash
   ```

   Keep `.env` private. It is ignored by `.gitignore`. The key is read only by the backend; no `VITE_*` variable is used for it.

   To run without a key, leave `FESTIVA_AI_MODE=demo`. Demo mode is deterministic local logic, not GenAI, and the UI says so.

3. Start the API:

   ```powershell
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload
   ```

4. In another terminal, install and start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

5. Open the Vite URL. Vite proxies `/api` to `http://127.0.0.1:8000`. FastAPI's interactive docs are at `http://127.0.0.1:8000/docs`. Operational counters are at `/api/diagnostics`.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `FESTIVA_AI_MODE` | `demo` | `demo` or `live`. Invalid values are reported as configuration errors; live mode fails explicitly if the key is missing. |
| `GEMINI_API_KEY` | — | Server-only Gemini API key. Never exposed to the browser or logs. |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Gemini model ID. Validated before a request. |
| `GEMINI_TIMEOUT_SECONDS` | `45` | Per-request SDK timeout, bounded to 5–120 seconds. |
| `FESTIVA_AI_MAX_OUTPUT_TOKENS` | `4096` | Model output cap, bounded to 512–8192. |
| `FESTIVA_AI_TEMPERATURE` | `0.5` | Generation temperature, bounded to 0–1. |
| `FESTIVA_AI_CACHE_TTL_SECONDS` | `3600` | In-process generation cache TTL; `0` disables caching. |
| `FESTIVA_DB_PATH` | `festiva.db` | SQLite database path. |
| `FESTIVA_ALLOWED_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact browser origins allowed by CORS. |

## Reliability and cost controls

- **Generation cache:** identical normalized event input + model + prompt version is cached in-process for one hour (maximum 32 entries). A repeat request costs no Gemini call. Identical concurrent requests are serialized with a lock, so the second request waits for and then reuses the first result.
- **No duplicate client requests:** the frontend guards every mutating action with a per-item pending key and disables the active control while a request is in flight. This prevents double-clicks from creating duplicate plans or duplicate revisions.
- **Bounded retries:** the SDK's own retries are disabled (`attempts=1`) and the application performs at most two retries for transient failures with exponential backoff and jitter. A quota response is retried at most once, only when `Retry-After` is present and short.
- **Structured schema retry:** a malformed or schema-invalid model response gets exactly one correction attempt. A second failure becomes a safe `502` error; there is no silent template fallback.
- **Provider-safe schema:** the schema hint is generated from the Pydantic models, then inlined and reduced to the JSON Schema subset Gemini structured output reliably accepts (no `$ref`/`$defs`, `anyOf`, `format`, `pattern`, or exclusive numeric bounds). Pydantic still enforces the full rules locally, so stricter validation is never lost.
- **Serialized writes:** revisions and checklist/spend PATCHes take a process-local write lock and re-read the latest plan before saving, so concurrent updates cannot silently overwrite each other. A revision also re-merges user state from the latest plan after generation.
- **Deterministic calculations:** budget totals, remaining balance, over-budget state, actual spend, deadline ordering, and date notices are computed by application code, never trusted from the model.
- **Minimal context:** the generation prompt sends only the event brief. Revisions send planning content and a compact user-state summary, not raw database rows.
- **Aggregate metrics:** token counts, latency, retry counts, cache hits/misses, schema failures, and quota events are recorded without prompts, plans, event details, or credentials.

### Error handling

| Condition | API result |
|---|---|
| Missing `GEMINI_API_KEY` in live mode | `503`, `category: config`, actionable message; nothing is saved |
| Invalid `FESTIVA_AI_MODE` or `GEMINI_MODEL` | `503`, `category: config` |
| Unsupported model / `404` | `503`, `category: model` |
| Invalid key / `401` or `403` | `503`, `category: auth` |
| Rate limit or daily quota (`429`) | `429`, `category: quota`, `Retry-After` when the provider supplies it |
| Timeout or transport failure | Bounded retries, then `503`, `category: timeout` |
| Transient provider error | Bounded retries, then `503` |
| Empty or schema-invalid output after one retry | `502`, `category: invalid_output`; saved plan unchanged |
| Missing plan / task / vendor / expense | `404` |
| Oversized request body | `413` before validation |
| Too many general requests | `429` after 120 requests/minute/IP |
| Too many AI actions | `429` after 10 generation/revision actions/10 minutes/IP |

## Security and privacy

- The Gemini key is read from server environment variables only. It is never sent to the browser, embedded in the bundle, printed by the verification script, or included in diagnostics.
- Event text and revisions are delimited and explicitly labeled as untrusted data in the system prompt. The prompt tells the model to ignore instructions embedded in that data.
- Provider exceptions are mapped to fixed application messages; raw provider details and request content are not returned to the client.
- Responses are validated against strict Pydantic models with `extra="forbid"`. Unknown or user-state fields from model output are rejected/removed.
- CORS allows only the configured exact origins. API mutations use POST/PATCH, and request bodies are capped at 64 KB.
- SQLite stores plan data unencrypted on disk. Do not use sensitive personal data on a shared machine.
- The application has **no authentication or per-user authorization**. Anyone who can reach the API can list and modify saved plans. Keep it local or place it behind an authenticated gateway before any public deployment.
- Free-tier Gemini content may be used by Google to improve products, as described in the official pricing documentation. Review this before sending sensitive data.

## Accessibility

- Skip-to-content link and a focusable main landmark.
- Visible `:focus-visible` outlines for buttons, inputs, textareas, selects, and links.
- Semantic form labels, `aria-label`s for icon-only controls, and screen-reader-only names for dense budget controls.
- `role="status"` announcements for generation/revision progress and saved notices; `role="alert"` for errors.
- `aria-current="page"` on the selected saved plan, `aria-busy` on in-flight forms, and a progress bar with values.
- A text summary of budget totals for screen-reader users.
- Responsive layouts, larger body text, and reduced-motion support.
- Manual screen-reader, zoom, and automated accessibility audits have **not** been performed; these remain verification gaps.

## Tests and actual results

Run backend tests from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Run frontend checks:

```powershell
npm --prefix frontend run build
npm --prefix frontend run test:e2e
npm --prefix frontend audit --audit-level=moderate
```

The E2E test starts an isolated demo-mode API and Vite server, exercises the browser workflow, and removes its temporary SQLite database. It prefers `.venv` Python and falls back to `python`; override with `FESTIVA_PYTHON` if needed. Ports 8000 and 5173 must be free.

### Latest local verification (2026-10-21)

| Check | Result |
|---|---|
| `python -m pytest -q` | **39 passed**, 1 third-party Starlette/httpx deprecation warning |
| `npm --prefix frontend run build` | **passed** (TypeScript check + Vite production bundle) |
| `npm --prefix frontend run test:e2e` | **1 passed** (7.0s) in Microsoft Edge against isolated demo API/database |
| `npm --prefix frontend audit --audit-level=moderate` | **0 vulnerabilities** |
| Local HTTP smoke test | Health/demo status OK; created a ₹50,000 plan; toggled a task; revised to ₹40,000; preserved task completion; diagnostics reported 1 plan, 1 generation, 1 revision |
| `backend/scripts/verify_gemini.py` without a key | **exit 2**, clear message, **no network request** |
| Real Gemini generation/revision | **not run**: `GEMINI_API_KEY` is not present in this environment |

No live Gemini response, token count, latency, quota figure, deployment URL, or verified-vendor data is claimed.

### Live verification procedure

With a key configured in `.env`:

```powershell
.\.venv\Scripts\python.exe backend\scripts\verify_gemini.py
.\.venv\Scripts\python.exe backend\scripts\verify_gemini.py --revision
```

The script forces live mode, makes one real structured generation (and optionally one revision), prints only aggregate usage metadata, and exits non-zero on failure. If you run it, record its actual output as the live evidence; do not assume success from the mocks.

## Deployment status (not deployed)

The repository has no hosting target, credentials, or live URL. The Vite proxy is development-only. A real deployment needs:

1. The API and static bundle served from the same origin (or a gateway that proxies `/api`).
2. A persistent disk for SQLite, or a managed database with migrations before scaling.
3. `FESTIVA_ALLOWED_ORIGINS` set to the exact frontend origin and HTTPS enabled.
4. Authentication, per-user plan ownership/authorization, and rate limiting at the edge.
5. A shared cache and shared rate-limit store if more than one API worker/instance is used.
6. Monitoring/alerting for error categories, latency, and quota events.

## Changed files

- `backend/app/ai.py` — official Gemini Interactions API integration, structured schema, cache/single-flight, retries, error mapping, revision guards.
- `backend/app/models.py` — AI-only output schemas separated from persisted/user-owned state; `Plan.content()`.
- `backend/app/services.py` — normalization, user-state merge, deterministic budget/timeline logic, improved demo revision.
- `backend/app/cache.py` — new thread-safe TTL cache.
- `backend/app/observability.py` — new aggregate AI metrics.
- `backend/app/main.py` — health/diagnostics, AI error handler with `Retry-After`, AI-specific rate limiting.
- `backend/app/database.py` — WAL/busy timeout and plan count.
- `backend/tests/conftest.py`, `test_ai.py`, `test_api.py`, `test_services.py` - updated/expanded coverage (39 tests).
- `backend/scripts/verify_gemini.py` — new operator live-verification script.
- `backend/requirements.txt` — added `google-genai`.
- `.env.example`, `pytest.ini`, `.gitignore` — configuration and test-root support.
- `frontend/src/types.ts`, `api.ts`, `App.tsx`, `style.css` — Gemini labels, request timeout/error metadata, duplicate-request guards, accessibility/readability improvements.
- `frontend/playwright.config.ts` — prefers the repository virtualenv Python for E2E.
- `README.md` — this document.

## Remaining gaps and next steps

1. **Live Gemini call:** supply a real key and run `verify_gemini.py`; record actual model, latency, token usage, and any quota behavior.
2. **Authentication and ownership:** add user accounts, per-user plan authorization, and session/CSRF protection before any public use.
3. **Scale-out:** move the generation cache and rate-limit counters to Redis (or similar), and replace SQLite with a managed database plus migrations.
4. **Deployment:** containerize or configure a host, set exact origins/HTTPS, add a health check, and record the real URL.
5. **Observability:** export metrics to a monitoring system and add alerts for quota, schema failures, and latency.
6. **Accessibility verification:** run automated audits and manual keyboard/screen-reader/zoom checks.
7. **Frontend tests:** add component/unit tests for duplicate-request guards and error states; the current browser test covers one full workflow.
8. **Provider variations:** test the live path with a real key, including 429/quota and timeout behavior; current mapping is verified with deterministic mocks.
9. **AI quality evaluation:** add a small, reviewed prompt/response evaluation set for budget coherence, inclusion, and cultural neutrality.

No live-provider response, deployment URL, or verified-vendor data is claimed.
