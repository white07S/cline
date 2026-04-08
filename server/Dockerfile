# Multi-stage Dockerfile for the FastAPI server + Celery worker.
# Both api and worker use the same image; the command differs.

# ── Base ──────────────────────────────────────────────────────────
FROM python:3.13-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=0 \
    UV_LINK_MODE=copy

# System deps for asyncpg / psycopg / openssl.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

WORKDIR /app

# ── Dev ──────────────────────────────────────────────────────────
# Used by docker-compose.dev.yml. Bind-mounts source over /app for hot reload.
FROM base AS dev

# Critical: install the venv OUTSIDE /app, because docker-compose.dev.yml bind-mounts
# ./server over /app at runtime — anything we put under /app would be masked.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

# Install all deps including dev group. We do this BEFORE the source
# bind mount so the layer cache survives source changes.
COPY pyproject.toml ./
RUN uv sync --all-extras --no-install-project

# Source is bind-mounted at runtime by compose. Default command is
# overridden in compose; this is just a sane fallback.
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]

# ── Builder (prod stage 1) ───────────────────────────────────────
FROM base AS builder

COPY pyproject.toml uv.lock* ./
# Install only runtime deps. The frozen lock guarantees reproducibility.
RUN uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

# ── Prod ─────────────────────────────────────────────────────────
FROM python:3.13-slim-bookworm AS prod

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Non-root user.
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app

# Copy the venv + source from builder.
COPY --from=builder --chown=app:app /app /app
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/healthz || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
