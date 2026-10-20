# Festiva AI

Festiva AI turns an event brief into a budget-aware, date-conscious celebration plan. It supports weddings, birthdays, anniversaries, college events, and community celebrations.

**Live deployment:** <https://festiva-ai.vercel.app> — live Gemini mode using `gemini-3.5-flash-lite`. Live generation and revision have been verified both locally and against production. Demo mode remains available and is labeled everywhere it appears.

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
              └── Vercel Blob (production) / SQLite (local)
```

- **Frontend:** React, TypeScript, and Vite. The UI creates plans, refines them, tracks tasks/vendors/actual spend, lists saved plans, and exports JSON. It calls the backend through the Vite `/api` proxy in development.
- **Backend:** FastAPI with Pydantic request/response models. Routes validate input, call the AI service, then hand the generated content to deterministic business logic.
- **AI layer:** official `google-genai` SDK using the Interactions API. Gemini supplies **planning content only**. The application owns all IDs, completion flags, actual spending, vendor contact details, booking status, totals, and deadlines.
- **Persistence:** durable private Vercel Blob storage in production; SQLite with WAL mode and a busy timeout for local development and tests. `FESTIVA_DB_PATH` selects the local SQLite file. The SQLite schema is created at startup; there is no migration tool yet.

### Request flow

```text
Event form
  -> FastAPI validation
  -> AI generation (Gemini or deterministic demo)
  -> strict schema validation
  -> normalize generated content (drop model-authored user state)
  -> deterministic totals + deadline alignment
  -> Vercel Blob (production) or SQLite (local)
  -> UI
```

For revisions, the backend sends only planning content plus a compact summary of user decisions. After validation it deterministically merges completed tasks, vendor details, quotations, statuses, and actual spend back into the result, and re-appends user-owned items the model dropped. A model cannot erase those decisions, silently drop the event date, or change the currency without an explicit currency request.

## Gemini integration

| Item | Value |
|---|---|
| Provider | Google Gemini via the official `google-genai` SDK (`>=2.31,<3`; installed and tested with `2.31.0`) |
| API | Interactions API (`client.interactions.create`) |
| Default model | `gemini-3.5-flash-lite` |
| Model configuration | `GEMINI_MODEL` (server-side, validated before use) |
| Output mode | Structured JSON through `response_format` plus strict Pydantic validation |
| State | `store=False` (stateless API request; no provider-side conversation retained) |
| Thinking | `thinking_level="low"` for plan generation |
| Output cap | `FESTIVA_AI_MAX_OUTPUT_TOKENS=4096` by default |
| Timeout | `GEMINI_TIMEOUT_SECONDS=45` by default (bounded to 5–120 seconds) |

Official documentation used (checked **2026-10-21**):

- Models: <https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite>
- Pricing and free tier: <https://ai.google.dev/gemini-api/docs/pricing>
- Interactions API: <https://ai.google.dev/gemini-api/docs/interactions-overview>
- Structured output: <https://ai.google.dev/gemini-api/docs/structured-output>
- Rate limits: <https://ai.google.dev/gemini-api/docs/rate-limits>
- SDKs: <https://ai.google.dev/gemini-api/docs/libraries>

### Free-tier caveat

The official pricing page checked on 2026-10-21 lists standard **Free Tier** input and output for Gemini 3.5 Flash Lite as free of charge. Google states that free-tier content may be used to improve Google products. Exact RPM/RPD limits are shown per project in AI Studio rather than as a single published number, and they differ by model. The project defaults to **`gemini-3.5-flash-lite`** for higher free-tier daily headroom; `GEMINI_MODEL` can override it. The application does **not** hardcode or claim specific quota figures.

## Requirements and evidence

| Requirement / metric | Implementation | Evidence |
|---|---|---|
| Event creation, missing-date clarification, personalization | `frontend/src/App.tsx`, `backend/app/main.py`, `backend/app/ai.py` | API workflow tests; form validation tests |
| GenAI planning and revision | `backend/app/ai.py` | Official Gemini SDK path; mocked live-mode tests plus successful live generation/revision runs |
| Independently calculated budget | `backend/app/services.py` | Unit tests for totals, remaining balance, actual spend, overruns |
| Event-date-aware preparation | `backend/app/services.py` | Timeline ordering, missing-date, and past-date tests |
| Persistent plans and checklists | `backend/app/database.py`, `backend/app/main.py` | Durable Blob-backed API in production; SQLite-backed API and E2E workflow locally |
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
   GEMINI_MODEL=gemini-3.5-flash-lite
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
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Gemini model ID. Validated before a request. |
| `GEMINI_TIMEOUT_SECONDS` | `45` | Per-request SDK timeout, bounded to 5–120 seconds. |
| `FESTIVA_AI_MAX_OUTPUT_TOKENS` | `4096` | Model output cap, bounded to 512–8192. |
| `FESTIVA_AI_TEMPERATURE` | `0.5` | Generation temperature, bounded to 0–1. |
| `FESTIVA_AI_CACHE_TTL_SECONDS` | `3600` | In-process generation cache TTL; `0` disables caching. |
| `FESTIVA_DB_PATH` | `festiva.db` | Local SQLite database path. Ignored when Blob credentials are present. |
| `BLOB_READ_WRITE_TOKEN` | — | Optional private Vercel Blob credential. When present, plans use Blob instead of SQLite. The Blob store connection adds it in production. |
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
- SQLite stores plan data unencrypted on disk locally; the private Blob store requires authentication but is not application-level encrypted. Do not store sensitive personal data without reviewing the provider's security model.
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
| `python -m pytest -q` | **45 passed**, 1 third-party Starlette/httpx deprecation warning |
| `npm --prefix frontend run build` | **passed** (TypeScript check + Vite production bundle) |
| `npm --prefix frontend run test:e2e` | **1 passed** (8.9s) in Microsoft Edge against isolated demo API/database |
| `npm --prefix frontend audit --audit-level=moderate` | **0 vulnerabilities** |
| Live Gemini generation + revision (`gemini-3.5-flash-lite`) | **2/2 succeeded**; see the measured usage below |
| Vercel entrypoint local smoke (`uvicorn main:app`) | `/api/health` OK, `/` served the built SPA, unknown `/api/*` returned JSON `404`, demo plan created |
| Deployed production API (live Gemini) | create, immediate PATCH→GET/list, and revision succeeded; ₹75,000 plan revised to ₹67,500 with task state preserved |
| Production health | `live`, `ok`, `gemini-3.5-flash-lite`, key configured |
| `backend/scripts/verify_gemini.py` without a key | **exit 2**, clear message, **no network request** (verified before the key was added) |

**Measured live Gemini run (2026-10-21):**

| Metric | Value |
|---|---|
| Model | `gemini-3.5-flash-lite` |
| Requests / successes / failures | 2 / 2 / 0 |
| Generation content | 4 expenses, 3 tasks, 2 vendors, 1 idea |
| Budget | estimated `75,000 INR` against `75,000 INR` budget |
| Revision | budget `67,500 INR`, estimated `67,500 INR`, tasks preserved |
| Input / output / thought / total tokens | `1,137 / 1,745 / 0 / 2,882` |
| Average latency | `3,752.5 ms` (`7,505 ms` total for 2 calls) |
| Schema validation failures / transient retries / quota events | `0 / 0 / 0` |

This local run went through the actual HTTP API and the Vercel entrypoint (`POST /api/plans`, then `POST /api/plans/{id}/revise`), not just the script. The earlier `verify_gemini.py --revision` run also passed 2/2 with `1,094 / 1,582 / 2,676` tokens and `4,109.5 ms` average latency.

**Production verification (2026-10-21, across the final two deployments, <https://festiva-ai.vercel.app>):**

| Metric | Value |
|---|---|
| Health | `live`, `ok`, `gemini-3.5-flash-lite`, provider configured |
| Storage diagnostics | `backend=vercel-blob`, `plans=1` |
| Create plan | **201**; 4 expenses, 3 tasks, 2 vendors, 1 idea; estimated `75,000 INR` |
| Create usage | input / output / total `310 / 810 / 1,120` tokens; `15,444 ms` |
| Revision | **200**; budget `67,500 INR`, estimated `67,500 INR`, tasks and completion flags preserved |
| Revision usage | input / output / total `846 / 876 / 1,722` tokens; `3,200 ms` |
| Immediate PATCH → GET and list | completion toggled both ways; every read matched the write |
| Persistence across redeploy | plan created before the redeploy remained readable afterward with `backend=vercel-blob` |
| Schema validation failures / transient retries / quota events | `0 / 0 / 0` |

The production URL is live; the metrics above are from requests made against it. Quota limits and verified-vendor data are not claimed. The key is stored as a Vercel **Sensitive** environment variable and is not printed or committed.

During live testing, three integration defects were found and fixed: the Interactions SDK reports HTTP status via `status_code` rather than `code` (now mapped), schema cleaning must preserve property names such as `title`, and Flash Lite rejects the full schema when array `minItems`/`maxItems` are present (those bounds remain enforced by Pydantic).

### Live verification procedure

With a key configured in `.env`:

```powershell
.\.venv\Scripts\python.exe backend\scripts\verify_gemini.py
.\.venv\Scripts\python.exe backend\scripts\verify_gemini.py --revision
```

The script forces live mode, makes one real structured generation (and optionally one revision), prints only aggregate usage metadata, and exits non-zero on failure. If you run it, record its actual output as the live evidence; do not assume success from the mocks.

## Vercel deployment

**Published on Vercel (production):**

- Stable alias: <https://festiva-ai.vercel.app>
- Latest deployment: <https://festiva-g13utpvkr-prashant-singhs-projects-4b5930a2.vercel.app> (`dpl_6RjaVzAQQucb9j6vbXWBYhB75N5T`)
- Vercel project: `prashant-singhs-projects-4b5930a2/festiva-ai`
- Production environment variables are stored in Vercel; `GEMINI_API_KEY` is marked **Sensitive** and is not in the repository.
- Build used Python 3.13, installed runtime dependencies with `uv`, built the Vite bundle, and completed successfully.

### What is configured

| File | Purpose |
|---|---|
| `main.py` | Vercel entrypoint; re-exports `backend.app.main:app`. |
| `vercel.json` | Runs `npm --prefix frontend ci && npm --prefix frontend run build`; allows 60s for the Python function; excludes development files from the bundle. |
| `requirements.txt` | Runtime dependencies for Vercel (development-only `pytest` omitted). |
| `.python-version` | Pins Python 3.13. |
| `.vercelignore` | Keeps `.env`, `.venv`, `node_modules`, tests, and local databases out of the upload. |
| `backend/app/main.py` | Serves `frontend/dist` through FastAPI (`app.frontend`) and keeps unknown `/api/*` paths as JSON `404`s. |
| `backend/app/database.py` | Uses **Vercel Blob** when `BLOB_READ_WRITE_TOKEN` (or Vercel OIDC + `BLOB_STORE_ID`) is present; otherwise SQLite. |

### Redeploy

```powershell
vercel --prod
```

Production variables currently set: `GEMINI_API_KEY` (sensitive), `BLOB_READ_WRITE_TOKEN` (sensitive, added by the Blob store connection), `FESTIVA_AI_MODE=live`, `GEMINI_MODEL=gemini-3.5-flash-lite`, `GEMINI_TIMEOUT_SECONDS=15`, `FESTIVA_AI_MAX_OUTPUT_TOKENS=4096`, `FESTIVA_AI_TEMPERATURE=0.5`, `FESTIVA_AI_CACHE_TTL_SECONDS=3600`. `FESTIVA_DB_PATH` is not set in production.

To rotate the key or change settings:

```powershell
vercel env rm GEMINI_API_KEY production
vercel env add GEMINI_API_KEY production
vercel env add GEMINI_MODEL production --value "gemini-3.5-flash-lite" --yes
vercel --prod
```

Do not put the key in `vercel.json`, source files, or a committed `.env`.

`GEMINI_TIMEOUT_SECONDS=15` is recommended on Vercel so up to two transient retries finish inside the 60s function limit. The frontend and API are same-origin on Vercel, so the default CORS list does not block browser requests; set `FESTIVA_ALLOWED_ORIGINS` to the production origin only if you call the API cross-origin.

### Durable plan storage

Production uses a private **Vercel Blob** store (`festiva-plans`, region `iad1`) connected to the project. Each plan is stored as `plans/{id}.json`; reads and writes go through the Blob SDK, so saved plans survive cold starts and are visible to every function instance.

- Reliable read-after-write: private Blob reads normally pass through the CDN, which can return the previous object after an overwrite. The Python SDK does not yet expose the JavaScript SDK's `useCache: false`, so the storage layer constructs delivered URLs with `cache=0`, the same origin-read bypass used internally by the JavaScript SDK. Unit tests assert every plan read includes it, and a real write→read test against the provisioned store passed.
- `BLOB_READ_WRITE_TOKEN` is a sensitive production variable. Locally the app falls back to SQLite, which keeps tests and offline development independent of Vercel.
- Create, read, list, count, overwrite, and unsafe-ID rejection are covered by tests with an in-memory Blob fake, plus real Blob round-trip and consistency checks against the provisioned store.
- Listing is capped at 100 plans, matching the previous SQLite behavior.
- Blob has no atomic compare-and-set for uploads, so concurrent edits to the *same* plan are last-write-wins. Creating different plans does not overwrite other plans. Add per-user auth and optimistic concurrency before multi-user production use.

The generation cache, rate-limit counters, and write locks remain process-local; serverless instances do not share them.

### Remaining production requirements

1. Authentication, per-user plan ownership/authorization, and HTTPS.
2. Shared cache and rate-limit store (Redis or similar).
3. Monitoring/alerting for error categories, latency, and quota events.
4. A backup/export and retention policy for the Blob store before storing irreplaceable user data.
5. Confirm the AI Studio RPM/RPD for `gemini-3.5-flash-lite` and set alerts before sharing the URL widely.

## Changed files

- `backend/app/ai.py` — official Gemini Interactions API integration, structured schema, cache/single-flight, retries, error mapping, revision guards.
- `backend/app/models.py` — AI-only output schemas separated from persisted/user-owned state; `Plan.content()`.
- `backend/app/services.py` — normalization, user-state merge, deterministic budget/timeline logic, improved demo revision.
- `backend/app/cache.py` — new thread-safe TTL cache.
- `backend/app/observability.py` — new aggregate AI metrics.
- `backend/app/main.py` — health/diagnostics, AI error handler with `Retry-After`, AI-specific rate limiting.
- `backend/app/database.py` — SQLite locally; durable private Vercel Blob storage in production; plan count and backend reporting.
- `backend/__init__.py` — package marker for the Vercel entrypoint.
- `backend/tests/conftest.py`, `test_ai.py`, `test_api.py`, `test_services.py`, `test_database.py` — updated/expanded coverage (45 tests).
- `backend/scripts/verify_gemini.py` — operator live-verification script; `--model` override.
- `backend/requirements.txt` — added `google-genai` and `vercel-blob`.
- `main.py`, `requirements.txt`, `vercel.json`, `.python-version`, `.vercelignore` — Vercel entrypoint, runtime dependencies, build/function configuration, Python pin, upload exclusions.
- `.env.example`, `pytest.ini`, `.gitignore` — configuration and test-root support.
- `frontend/src/types.ts`, `api.ts`, `App.tsx`, `style.css` — Gemini labels, request timeout/error metadata, duplicate-request guards, accessibility/readability improvements.
- `frontend/playwright.config.ts` — prefers the repository virtualenv Python for E2E.
- `README.md` — this document.

## Remaining gaps and next steps

1. **Authentication and ownership:** add user accounts, per-user plan authorization, and session/CSRF protection before any public use.
2. **Scale-out:** move the generation cache and rate-limit counters to Redis (or similar) so instances share them.
3. **Observability:** export metrics to a monitoring system and add alerts for quota, schema failures, and latency.
4. **Blob operations:** add a backup/export and retention policy, and clean up the verification plans currently in the store.
5. **Accessibility verification:** run automated audits and manual keyboard/screen-reader/zoom checks.
6. **Frontend tests:** add component/unit tests for duplicate-request guards and error states; the current browser test covers one full workflow.
7. **Provider variations:** exercise 429/quota, timeout, and malformed-output behavior against the live API; current mapping is verified with deterministic mocks plus the successful live path.
8. **AI quality evaluation:** add a small, reviewed prompt/response evaluation set for budget coherence, inclusion, and cultural neutrality.
9. **Provider limits:** confirm the project's actual RPM/RPD in AI Studio. The default model is `gemini-3.5-flash-lite` for higher daily headroom; `GEMINI_MODEL` can switch back to another Flash model.

No verified-vendor data is claimed. The live Gemini metrics above are from actual verification runs; quota limits are not claimed because they are project-specific.
