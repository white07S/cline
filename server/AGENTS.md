# `server/` — agent guide

FastAPI service + Celery workers for the data platform. Async-first, fully typed, custom RAG.

## Stack

| Concern | Choice |
|---|---|
| Runtime | Python 3.13 |
| Package manager | **uv** (not Poetry / pip-tools) |
| Web framework | FastAPI + uvicorn (standalone, no gunicorn — uvicorn ≥0.30 has native worker management) |
| Validation / models | Pydantic v2 |
| Settings | pydantic-settings + pyyaml (`yaml.safe_load`) — YAML is the source of truth |
| ORM | SQLAlchemy 2.x (**async** style only — `AsyncSession`, `select()`, mapped classes) |
| Migrations | Alembic — autogenerate when possible, hand-written when autogenerate is wrong (renames, data migrations) |
| Task queue | Celery (Redis broker, Postgres result backend via `db+postgresql://...`) |
| Vector store | Qdrant via `qdrant-client` (async) |
| LLM | `openai` SDK directly. **No LangChain / LlamaIndex / Instructor.** |
| Logging | **structlog** with stdlib bridge, JSONL in prod, ConsoleRenderer in dev |
| Observability | OpenTelemetry (FastAPI + Celery + SQLAlchemy + httpx + Redis instrumentation) → OTEL Collector |
| Errors | Sentry SDK (`sentry_sdk[fastapi]`) — enabled in prod |
| Rate limiting | slowapi |
| Request IDs | asgi-correlation-id (header → contextvar → log record) |
| Metrics | prometheus-fastapi-instrumentator (`/metrics`) |
| Tests | pytest + pytest-asyncio + httpx AsyncClient |
| Lint / format | ruff (lint + format) |
| Typecheck | mypy (strict) |

## Layout

```
server/
├── pyproject.toml             # uv-managed
├── uv.lock
├── Dockerfile                 # multi-stage (dev, prod)
├── alembic.ini
├── alembic/
│   ├── env.py                 # async-aware
│   ├── script.py.mako
│   └── versions/
└── app/
    ├── main.py                # FastAPI factory; app = create_app()
    ├── settings.py            # Pydantic Settings; loads configs/server.yml
    ├── logging.py             # structlog setup
    ├── observability.py       # OTEL + Sentry init
    ├── middleware/
    │   ├── correlation.py     # request-id propagation
    │   └── ratelimit.py       # slowapi wiring
    ├── api/
    │   ├── router.py          # mounts versioned routers
    │   ├── deps.py            # FastAPI dependencies (db session, current user)
    │   └── v1/
    │       ├── health.py
    │       └── ...            # add endpoints here
    ├── db/
    │   ├── base.py            # async engine + sessionmaker
    │   └── models/            # SQLAlchemy 2.x typed models
    ├── services/              # business logic (ingestion, pipelines, rag, llm, embeddings)
    ├── vectorstore/
    │   └── qdrant.py
    ├── workers/
    │   ├── celery_app.py
    │   └── tasks/
    ├── scripts/
    │   └── dump_openapi.py    # used by `just openapi`
    └── tests/
        ├── conftest.py
        ├── unit/
        └── integration/
```

## Universal best practices (mandatory)

These restate the rules from the root `README.md`. Every PR is reviewed against them.

### 1. Typesafe code, Pydantic everywhere

**Never use `dict[str, Any]`, `Any`, or untyped dicts for structured data.**

Every payload that crosses a boundary — HTTP request/response, DB row, Celery task arg, LLM call, vector store payload, config file, internal service call — has an explicit Pydantic model. Nested objects are nested models, **not raw dicts**.

```python
# ❌ NEVER
def create_user(payload: dict) -> dict: ...
def fetch_chunks(...) -> list[dict[str, Any]]: ...
def run_pipeline(args: dict[str, Any]) -> None: ...

# ✅ ALWAYS
class CreateUserIn(BaseModel):
    email: EmailStr
    name: str

class CreateUserOut(BaseModel):
    id: UUID
    email: EmailStr
    created_at: datetime

def create_user(payload: CreateUserIn) -> CreateUserOut: ...

class Chunk(BaseModel):
    id: UUID
    document_id: UUID
    text: str
    score: float
    metadata: ChunkMetadata          # nested model, not a dict

def fetch_chunks(...) -> list[Chunk]: ...
```

The only places `Any` is acceptable:
- Generic library boundaries you don't control (and even then, narrow it at the wrapper).
- `**kwargs` forwarding to a typed callable (rare; prefer explicit args).

mypy is configured strict. CI fails on `Any` leaks and missing return types.

### 2. No silent error bypass

```python
# ❌ NEVER
try:
    result = call_openai(...)
except Exception:
    return None       # silent fallback — bug becomes invisible

try:
    result = call_openai(...)
except Exception:
    pass              # even worse

# ✅ ALWAYS
try:
    result = call_openai(...)
except openai.RateLimitError as e:
    log.warning("openai_rate_limited", attempt=attempt, retry_after=e.retry_after)
    raise        # let the retry decorator handle it

except openai.APIError as e:
    log.exception("openai_api_error", request_id=e.request_id)
    raise OpenAIServiceError("LLM call failed") from e
```

Catch only the **specific** exceptions you can meaningfully handle. Re-raise everything else, with context. Never `except Exception:` without a log + re-raise.

### 3. Explicit error handling at every boundary

- HTTP boundary → custom exception handlers in `app/main.py` map domain errors to HTTP responses (with proper status codes).
- DB boundary → wrap `IntegrityError` / `OperationalError` into domain errors.
- LLM boundary → wrap `openai.*Error` into `LLMError` subclasses.
- Vector store → wrap `qdrant_client.http.exceptions.*` into `VectorStoreError`.
- Celery task boundary → use `bind=True`, log + raise. Use `task_acks_late=True` so failed tasks are redelivered.

Each domain has its own exception hierarchy in `app/services/<domain>/errors.py`.

### 4. Async vs concurrent — be deliberate

This is a recurring confusion source. The rules:

- **Async** = "I might be waiting on I/O — let the event loop run other tasks meanwhile." Use `async def` for any function that does I/O (DB, HTTP, OpenAI, Qdrant, Redis).
- **Concurrent** = "Multiple things actually run at the same time." Achieved with `asyncio.gather`, `asyncio.TaskGroup`, or Celery workers.
- **Sequential async** is the default. Reach for `gather` only when:
  1. The operations are genuinely independent (no data dependency between them).
  2. The downstream system can handle the parallel load (rate limits, connection pool size).
  3. You have a comment explaining *why* it's concurrent.

```python
# ❌ Reflex parallelism — looks fast, often breaks rate limits
results = await asyncio.gather(*[call_openai(p) for p in prompts])

# ✅ Bounded, explicit
async def embed_all(texts: list[str]) -> list[Embedding]:
    """Embed N texts with bounded concurrency to respect OpenAI rate limits."""
    semaphore = asyncio.Semaphore(settings.openai.max_concurrent_calls)
    async def _one(text: str) -> Embedding:
        async with semaphore:
            return await embed(text)
    return await asyncio.gather(*[_one(t) for t in texts])
```

When the work is **CPU-bound** (chunking large docs, parsing PDFs), don't use asyncio — push it to a Celery task running in a worker process. The event loop is single-threaded; CPU-bound work in `async def` blocks every other request on that worker.

### 5. Ask, don't guess

If a schema is ambiguous, an external API contract is unclear, or a config field's intent is unknown — **stop and ask**. Guessing creates code that "works" until it silently doesn't. Examples of the kind of thing to ask about, not guess:

- Does this field need to be nullable in the DB?
- Should this Celery task be idempotent (it gets retried on failure)?
- What's the expected token budget for this prompt?
- Is this user-facing or internal?

## Patterns

### Settings access

```python
from app.settings import get_settings

settings = get_settings()                        # cached singleton
print(settings.database.pool_size)               # typed, autocompletes
```

Never `os.environ.get(...)` directly. Never read YAML at the call site. The Settings model is the only entry point.

### Logging

```python
from app.logging import get_logger

log = get_logger(__name__)
log.info("user_created", user_id=str(user.id), email=user.email)
log.exception("openai_call_failed", attempt=attempt)
```

Use **structured key-value pairs**, not f-strings. No `f"User {user.id} created"` — that loses queryability in Loki.

### DB session

```python
from app.api.deps import get_db_session

@router.post("/users")
async def create_user(payload: CreateUserIn, db: AsyncSession = Depends(get_db_session)) -> CreateUserOut: ...
```

The `get_db_session` dependency manages commit/rollback automatically — don't call `db.commit()` in route code.

### Celery tasks

```python
from app.workers.celery_app import celery_app

@celery_app.task(name="ingest.process_document", bind=True, max_retries=3)
def process_document(self, doc_id: str) -> None:
    """Idempotent — safe to retry. Reads doc by id, splits, embeds, upserts."""
    ...
```

Task arguments must be **JSON-serializable Pydantic models or primitives**. Pass IDs, not ORM instances. Tasks are idempotent by default — design accordingly.

## Testing

- Unit tests: `tests/unit/` — no DB, no network. Use Pydantic models directly.
- Integration tests: `tests/integration/` — uses real Postgres + Redis (CI service containers, see `.github/workflows/ci.yml`).
- Always `pytest-asyncio` mode `auto` so test functions are awaitable.
- HTTP tests use `httpx.AsyncClient(transport=ASGITransport(app=app))`.
- **Do not mock the database** in integration tests — mocks drift. Hit a real Postgres.

## Migrations

```bash
just db-revision m="add documents table"   # autogenerate
# Inspect alembic/versions/<hash>_add_documents_table.py
# Edit if autogenerate is wrong (renames, data migrations)
just db-upgrade
```

Hand-written migrations are required for:
- **Renames** — autogenerate sees `drop col + add col`, loses data
- **Data backfills** — autogenerate doesn't write data migrations
- **Constraint changes that need a specific lock strategy** — e.g., `NOT NULL` on a 50M-row table

## Common gotchas

- **uvicorn `--reload` requires single worker.** The dev compose runs `--reload`, so dev is single-process by design.
- **`asgi-correlation-id` must come BEFORE the routes** in middleware order.
- **OpenTelemetry instrumentation must run before any FastAPI/SQLAlchemy import** when using auto-instrumentation. We do explicit instrumentation in `app/observability.py` to avoid this.
- **Celery task discovery**: tasks must be imported from `celery_app.py` (or via `include=`) or they won't register.
- **`task_acks_late=True`** means a task is only ack'd after success. If a worker dies mid-task, the broker redelivers — the task **must be idempotent**.
