# `configs/` — agent guide

This folder is the **single source of truth for all configuration**, both application config and infrastructure config. Anything that is "knobs you can turn without a code change" lives here.

## Two layers, by design

| Layer | Where | What goes here | Format |
|---|---|---|---|
| **Non-secret config** | `configs/*.yml`, `configs/infra/**` | Behavior knobs, model names, timeouts, retry counts, DB pool sizes, vector dims, log levels, infra service configs | YAML (one format across the whole repo) |
| **Secrets** | `configs/env/.env.{dev,prod}` | API keys, DB passwords, OAuth client secrets, JWT signing keys | dotenv, gitignored |

**Never** put secrets in `*.yml`. **Never** put non-secret config in `.env`. Splitting them this way means YAML can be safely committed and reviewed; secrets stay out of git entirely.

## Why YAML (not TOML)

We use YAML for **all** application config so the repo has one config format, not two. The infra configs in `configs/infra/` (Loki, Prometheus, Grafana, OTEL Collector, Tempo, Promtail) are forced to YAML by their consuming tools, so picking YAML for our app configs eliminates a class of "which format does this file use?" friction. The trade-off — YAML's well-known footguns (Norway problem, type coercion, significant whitespace) — is paid once via:

- **`yaml.safe_load`** everywhere — never `yaml.load` (no tag-based code execution).
- **Pydantic validation** at the boundary — every YAML key flows into a typed Pydantic model that rejects wrong types loudly. The Norway problem can't bite if `enabled: bool` rejects the string `"no"`.
- **Quote string-typed values** that look ambiguous: `"on"`, `"off"`, `"yes"`, `"no"`, version strings, country codes. Reviewers should flag unquoted versions of these.

## File layout

```
configs/
├── server.yml              # Base server config (loaded everywhere)
├── server.dev.yml          # Dev overrides (merged on top of server.yml)
├── server.prod.yml         # Prod overrides
├── logging.yml             # structlog sinks, levels, JSON renderer settings
├── qdrant.yml              # Qdrant collection definitions (name, dim, distance, HNSW params)
├── openai.yml              # OpenAI model names, retry/timeout, embedding models
├── rag.yml                 # RAG behavior: chunk size, overlap, top_k, rerank
├── s3.yml                  # Object store: region, addressing, logical bucket names (no secrets)
├── dagster.yaml            # Dagster instance config (Postgres-backed run/event storage)
├── env/
│   ├── .env.dev.example    # Template — copy to .env.dev and fill in
│   ├── .env.prod.example   # Template — copy to .env.prod and fill in
│   └── README.md           # Which secret each variable holds and where to get it
└── infra/                  # Per-service infra configs (mounted into containers)
    ├── postgres/init/      # Bootstrap SQL/shell scripts (e.g., create dagster db)
    ├── nginx/
    ├── prometheus/
    ├── grafana/
    ├── loki/
    ├── promtail/
    ├── otel-collector/
    └── tempo/
```

## How YAML configs are loaded

The server uses `pydantic-settings` + `pyyaml` (`yaml.safe_load` only — never `yaml.load`). The loading order is:

1. Read `configs/server.yml` (base)
2. Merge `configs/server.{env}.yml` (env override) — `env` is `dev` or `prod`, taken from `APP_ENV`
3. Override individual fields from environment variables (so secrets in `.env` always win)

The schema is **fully typed** by a Pydantic `Settings` class in `server/app/settings.py`. **There is no untyped config access anywhere in the server code** — every field has a type, a default (where appropriate), and validation. If you add a new YAML key, you must also add it to the Pydantic model in the same PR.

## Universal best practices (apply to every file in this repo)

These restate the rules from the root `README.md`. They apply equally to config files: configs cross a boundary into typed code, so they must be reviewed with the same rigor.

### 1. Typesafe everywhere

- Every YAML file has a corresponding **Pydantic model** in `server/app/settings.py` (or a sub-module). No exceptions.
- **Never** read a config value via `dict[str, Any]` or `getattr` on an untyped object. If you find yourself wanting to, the right move is to add the field to the Pydantic model.
- Nested YAML mappings map to nested Pydantic models. Don't flatten.

```yaml
# Good — maps to a nested Pydantic model
database:
  url: "postgresql+asyncpg://..."
  pool_size: 20
  max_overflow: 10
  ssl:
    enabled: true
    ca_file: "/etc/ssl/ca.pem"
```

```python
# server/app/settings.py
class DatabaseSSLSettings(BaseModel):
    enabled: bool = False
    ca_file: Path | None = None

class DatabaseSettings(BaseModel):
    url: PostgresDsn
    pool_size: int = 10
    max_overflow: int = 5
    ssl: DatabaseSSLSettings = DatabaseSSLSettings()
```

### 2. No silent error bypass

Config loading errors must **fail loudly at startup**, before the app accepts any requests. Never `try/except` around a missing config field and substitute a default — if a field is required, declare it required in the Pydantic model and let validation raise.

### 3. Explicit error handling

If a YAML field is optional, mark it `Optional` in the Pydantic model with an explicit default. Don't rely on `getattr` or `.get(..., default)` patterns at the call site.

### 4. Async vs concurrent

N/A for static config files, but: configs influence concurrency (worker counts, pool sizes, queue concurrency). Document **why** each value is chosen, not just the value. A magic `concurrency: 4` in a YAML file is a future bug.

### 5. Ask, don't guess

If you're adding a config field and you're not sure where it belongs (`server.yml` vs `dagster.yaml` vs `rag.yml`), or whether it's a secret or non-secret, **ask**. Configs are sticky — moving them later breaks every deployed environment.

## Adding a new config field — checklist

1. Decide: secret or non-secret? Secret → `.env.*.example`. Non-secret → the right `*.yml`.
2. Add the field to the Pydantic model in `server/app/settings.py` (with type and default).
3. Add a comment in the YAML/env file explaining **what** it does and **why** the default is what it is.
4. If it's a secret, also document it in `configs/env/README.md` (where to get the value, who owns it).
5. Add a test in `server/tests/unit/test_settings.py` that asserts the field is loaded correctly.

## Adding a new infra service config

Per-service configs live under `configs/infra/<service>/`. The service is wired into `docker-compose.prod.yml` (or `docker-compose.dev.yml` if it's a dev tool) with a read-only bind mount. Pin the image version. Add a healthcheck if the service supports one.
