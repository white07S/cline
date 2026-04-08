# Top-level task runner. See README.md for prerequisites.
# Run `just` with no args to list all recipes.

set shell := ["bash", "-cu"]
set dotenv-load := false

default:
    @just --list

# ──────────────────────────────────────────────────────────────────
# Bootstrap
# ──────────────────────────────────────────────────────────────────

# Install all dependencies (server + client) and pre-commit hooks.
bootstrap: _bootstrap-server _bootstrap-client _bootstrap-hooks
    @echo "Bootstrap complete. Copy configs/env/.env.dev.example -> configs/env/.env.dev and fill it in."

_bootstrap-server:
    cd server && uv sync --all-extras

_bootstrap-client:
    cd client && bun install

_bootstrap-hooks:
    pre-commit install

# ──────────────────────────────────────────────────────────────────
# Dev: full stack via docker compose
# ──────────────────────────────────────────────────────────────────

# Bring up the full dev stack (postgres, redis, qdrant, api, worker, client).
dev:
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

# Tear down dev stack and remove volumes.
dev-down:
    docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v

# Tail logs of one service. Usage: just logs s=api
logs s="api":
    docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f {{s}}

# ──────────────────────────────────────────────────────────────────
# Dev: run individual services locally (no docker)
# ──────────────────────────────────────────────────────────────────

# Run the FastAPI server locally with hot reload.
api:
    cd server && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run a Celery worker locally.
worker:
    cd server && uv run celery -A app.workers.celery_app worker --loglevel=info

# Run the Vite dev server locally.
client:
    cd client && bun run dev

# ──────────────────────────────────────────────────────────────────
# Database / migrations
# ──────────────────────────────────────────────────────────────────

# Create a new alembic revision via autogenerate. Usage: just db-revision m="add users table"
db-revision m:
    cd server && uv run alembic revision --autogenerate -m "{{m}}"

# Apply all pending migrations.
db-upgrade:
    cd server && uv run alembic upgrade head

# Revert the most recent migration.
db-downgrade:
    cd server && uv run alembic downgrade -1

# Show migration history.
db-history:
    cd server && uv run alembic history

# ──────────────────────────────────────────────────────────────────
# Type sharing: server openapi -> client TS types
# ──────────────────────────────────────────────────────────────────

# Generate client TS types from the server's OpenAPI schema.
openapi:
    cd server && uv run python -m app.scripts.dump_openapi > ../client/src/api/openapi.json
    cd client && bunx openapi-typescript src/api/openapi.json -o src/api/types.gen.ts

# ──────────────────────────────────────────────────────────────────
# Lint, format, typecheck, test
# ──────────────────────────────────────────────────────────────────

lint: lint-client lint-server

lint-client:
    cd client && bunx biome check . && bunx eslint .

lint-server:
    cd server && uv run ruff check .

fmt: fmt-client fmt-server

fmt-client:
    cd client && bunx biome format --write .

fmt-server:
    cd server && uv run ruff format .

typecheck: typecheck-client typecheck-server

typecheck-client:
    cd client && bunx tsc --noEmit

typecheck-server:
    cd server && uv run mypy app

test: test-client test-server

test-client:
    cd client && bun run test

test-server:
    cd server && uv run pytest

# Run end-to-end tests (requires the dev stack to be running).
e2e:
    cd client && bunx playwright test

# ──────────────────────────────────────────────────────────────────
# Production
# ──────────────────────────────────────────────────────────────────

prod-up:
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

prod-down:
    docker compose -f docker-compose.yml -f docker-compose.prod.yml down

prod-logs s="api":
    docker compose -f docker-compose.yml -f docker-compose.prod.yml logs -f {{s}}
