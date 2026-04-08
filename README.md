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

This brings up the full stack with hot reload. Host ports use the 5xxxx / 1xxxx
range to avoid colliding with anything else you may already be running on the
standard ports — the in-container ports are unchanged, so service-to-service
calls inside the compose network still use defaults.

### Dev — exposed services

| Service | URL / endpoint | Container port | Notes |
|---|---|---|---|
| Client (Vite dev server) | http://localhost:5173 | 5173 | hot reload via bind mount |
| API (FastAPI + uvicorn) | http://localhost:18000 | 8000 | `--reload` enabled |
| API docs (Swagger) | http://localhost:18000/docs | 8000 | |
| API redoc | http://localhost:18000/redoc | 8000 | |
| API liveness | http://localhost:18000/api/v1/healthz | 8000 | shallow process check |
| API readiness | http://localhost:18000/api/v1/readyz | 8000 | DB / Redis / Qdrant / S3 reachability |
| API metrics | http://localhost:18000/metrics | 8000 | Prometheus format (not scraped in dev) |
| Dagster UI (webserver) | http://localhost:13000 | 3000 | runs/assets/schedules/sensors |
| Dagster daemon | _no UI_ | — | background process; logs via `docker logs dp-dagster-daemon` |
| Postgres | `postgresql://app:app@localhost:55432/app` | 5432 | shared by API + Dagster (separate logical DB) |
| Redis | `redis://localhost:56379` | 6379 | rate limiting + app cache |
| Qdrant HTTP / dashboard | http://localhost:6333 / http://localhost:6333/dashboard | 6333 | vector store |
| Qdrant gRPC | `localhost:6334` | 6334 | preferred transport from server |
| MinIO S3 endpoint | http://localhost:19000 | 9000 | S3 protocol — `minioadmin` / `minioadmin` |
| MinIO console | http://localhost:19001 | 9001 | web UI — `minioadmin` / `minioadmin` |

**Not in dev compose** (intentionally): nginx, otel-collector, Prometheus,
Grafana, Loki, Promtail, Tempo, cAdvisor, redis-exporter, postgres-exporter.
The full observability stack is prod-only — running it locally just adds
overhead and noise. OTEL exporting is disabled in `configs/server.dev.yml` so
the SDK doesn't try to push spans to a non-existent collector.

### Prod — exposed services

In prod, **only nginx is exposed publicly** (`80` / `443`). Everything else
sits behind nginx on the internal compose network. Grafana exposes its own port
for operators on the management network. Use SSH tunneling or a VPN to reach
the rest.

| Service | URL / how to reach | Host port | Notes |
|---|---|---|---|
| Public site (client) | https://your.domain/ | 443 | nginx serves the built `client/dist/` |
| Public API | https://your.domain/api/ | 443 | nginx → `api` replicas |
| Public API docs | https://your.domain/api/docs | 443 | gated by auth in prod |
| nginx HTTP (redirects) | http://your.domain/ | 80 | 301 → https |
| API replicas | _internal only_ | — | `dp-api` service, N replicas behind nginx |
| Dagster webserver | _internal only_ | — | tunnel to `dp-dagster-webserver:3000` |
| Dagster daemon | _no UI_ | — | singleton process |
| Postgres | _internal only_ | — | not bound to host; reach via `docker exec dp-postgres psql` |
| Redis | _internal only_ | — | not bound to host |
| Qdrant | _internal only_ | — | not bound to host |
| MinIO | _internal only_ | — | not bound to host |
| Grafana | http://host:3000 | 3000 | dashboards + alerting; default admin/admin (override via env) |
| Prometheus | _internal only_ | — | scraped by Grafana; tunnel to `dp-prometheus:9090` to inspect |
| Loki | _internal only_ | — | log aggregation; tunnel to `dp-loki:3100` |
| Tempo | _internal only_ | — | trace storage; tunnel to `dp-tempo:3200` |
| OTEL collector | _internal only_ | — | OTLP gRPC `:4317`, HTTP `:4318` — `api` and Dagster export here |
| cAdvisor | _internal only_ | — | container metrics for Prometheus |
| redis-exporter | _internal only_ | — | Redis metrics for Prometheus |
| postgres-exporter | _internal only_ | — | Postgres metrics for Prometheus |

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
