# Data Platform

A data platform for **data ingestion → AI pipelines → chat with data**.
Custom RAG, no LangChain. Built for production from day one.

## Stack at a glance

| Layer | Tech |
|---|---|
| **Client** | React 19 + Vite 8 (Rolldown) + Bun + TypeScript + Tailwind v4 + TanStack Router/Query/Form + Zod + Axios + MSAL |
| **Server** | Python 3.13 + uv + FastAPI + async SQLAlchemy 2.x + Alembic + Pydantic v2 + structlog |
| **Orchestration** | Dagster (assets, schedules, sensors) — webserver + daemon, Postgres-backed |
| **Object store** | MinIO (S3-compatible) via aioboto3 — same service in dev and prod |
| **Data** | Postgres 16, Redis 7, Qdrant 1.12 |
| **LLM** | OpenAI SDK directly (no framework) |
| **Observability** | OpenTelemetry → Tempo (traces) + Prometheus (metrics) + Loki (logs) + Grafana, Sentry for errors |
| **Edge** | nginx (TLS termination, reverse proxy, load balancing) |
| **Lint/format** | Biome (JS/TS) + minimal ESLint for `react-hooks` rules, Ruff + mypy (Python) |
| **Tests** | Vitest + Testing Library + Playwright (client), pytest + pytest-asyncio + httpx (server) |
| **Task runner** | `just` |

See [`client/AGENTS.md`](client/AGENTS.md), [`server/AGENTS.md`](server/AGENTS.md), and [`configs/AGENTS.md`](configs/AGENTS.md) for the per-folder rules and patterns every contributor (human or AI) must follow.

## Repository layout

```
.
├── client/                 # Vite + React + Bun
├── server/                 # FastAPI + Dagster code location + uv
├── configs/                # All YAML configs + per-service infra configs
│   ├── *.yml               # App config (server, logging, qdrant, openai, rag, s3)
│   ├── dagster.yaml        # Dagster instance config (Postgres-backed run/event storage)
│   ├── env/                # .env.*.example templates (real .env files are gitignored)
│   └── infra/              # postgres/init, nginx, prometheus, grafana, loki, otel-collector, tempo
├── .github/workflows/      # CI
├── docker-compose.yml      # Base: postgres, redis, qdrant, minio
├── docker-compose.dev.yml  # Dev: api, dagster (webserver+daemon), client with hot reload
├── docker-compose.prod.yml # Prod: replicas, nginx, full monitoring stack
├── justfile                # Top-level task runner
└── README.md
```

## Prerequisites

Install once:

- **Docker** + Docker Compose (24+)
- **uv** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Bun** — `curl -fsSL https://bun.sh/install | bash`
- **just** — `brew install just` (or see https://github.com/casey/just)
- **pre-commit** — `uv tool install pre-commit`

## First-time setup

```bash
just bootstrap        # installs server (uv) + client (bun) deps, sets up pre-commit
cp configs/env/.env.dev.example configs/env/.env.dev
# edit configs/env/.env.dev — fill in OPENAI_API_KEY, AZURE_*, etc.
```

## Run everything (dev)

```bash
just dev              # docker compose up: postgres, redis, qdrant, minio, api, dagster, client
```

This brings up the full stack with hot reload:

| Service | URL |
|---|---|
| Client (Vite dev server) | http://localhost:5173 |
| API (FastAPI + uvicorn) | http://localhost:18000 |
| API docs | http://localhost:18000/docs |
| Dagster UI (webserver) | http://localhost:13000 |
| Postgres | localhost:55432 |
| Redis | localhost:56379 |
| Qdrant dashboard | http://localhost:6333/dashboard |
| MinIO console | http://localhost:19001 (minioadmin/minioadmin) |
| MinIO S3 endpoint | http://localhost:19000 |
| Grafana (prod profile only) | http://localhost:3000 (admin/admin) |

## Run a single service locally (without docker)

```bash
just api                  # uvicorn with reload, reads configs/server.dev.yml
just dagster-webserver    # Dagster UI on http://localhost:3000
just dagster-daemon       # Dagster schedules / sensors / run launcher
just client               # bun run dev
```

## Database

```bash
just db-revision m="add users table"   # alembic autogenerate
just db-upgrade                         # apply migrations
just db-downgrade                       # revert one
```

Both **autogenerate** and **hand-written** migrations are supported. Hand-written is required when:
- Renaming columns (autogenerate sees drop+add, loses data)
- Data migrations (backfill, reshape)
- Anything involving constraints that need a specific lock strategy

## Type safety pipeline

The server is the source of truth for API types. Run after any server schema change:

```bash
just openapi          # dumps server openapi.json + generates client/src/api/types.gen.ts
```

This guarantees the client and server stay in sync. **Never hand-write types that the server already exposes.**

## Tests

```bash
just test             # client (vitest) + server (pytest)
just e2e              # playwright against the dev stack
```

## Linting & formatting

```bash
just lint             # biome + ruff
just fmt              # auto-format everything
just typecheck        # tsc + mypy
```

Pre-commit hooks run all of the above on staged files. They will block your commit if anything fails — fix the underlying issue, do not bypass with `--no-verify`.

## Production deployment

```bash
just prod-up          # docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Production stack adds:
- nginx (TLS termination, load balancer for `api` replicas)
- Multiple `api` replicas (uvicorn with `--workers N` per replica)
- `dagster-webserver` and `dagster-daemon` (single replica each — Dagster's daemon must be a singleton)
- Full observability stack (Prometheus + Grafana + Loki + Tempo + OTEL Collector + cAdvisor + redis_exporter + postgres_exporter)
- Sentry SDK enabled in `api` and Dagster processes

## Universal best practices

These apply to **every file in this repo** — server, client, and configs:

1. **Typesafe code everywhere.** No `any` (TS) or `dict[str, Any]` (Python) for structured data. Every payload that crosses a boundary has an explicit Pydantic model (server) or Zod schema + inferred TypeScript type (client). Nested objects must be typed models, not raw dicts.
2. **No silent error bypass.** Errors are raised, never swallowed. `try/except` without re-raise is a code-review block. Catch only what you can meaningfully recover from, and log + re-raise everything else.
3. **Explicit error handling.** Every external boundary (HTTP, DB, LLM, vector store, message queue) has explicit error types and explicit failure modes. No bare `except:`.
4. **Async vs concurrent is a deliberate choice.** Don't reach for `asyncio.gather` or `Promise.all` reflexively. Document *why* something is concurrent (e.g., "fan out 10 independent embedding calls") vs sequential ("each step depends on the previous"). When in doubt, sequential is the safer default.
5. **Ask, don't guess.** If the structure or intent of something is unclear — a schema, a config, a requirement — stop and ask. Guessing creates silent bugs that are expensive to find later.

These rules are non-negotiable. Both `client/AGENTS.md` and `server/AGENTS.md` restate them with language-specific examples.

## License

TBD
