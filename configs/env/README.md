# Secrets

Real `.env.*` files are gitignored. Only `.env.*.example` templates are committed.

## Where each secret comes from

| Variable | Owner / Source |
|---|---|
| `POSTGRES_*`, `DATABASE_URL*` | Generated locally (dev) / managed by infra (prod) |
| `POSTGRES_HOST` | `postgres` inside compose; the prod hostname behind your DB |
| `DAGSTER_POSTGRES_DB` | Logical Postgres DB used by Dagster's run/event/schedule storage. Created by `configs/infra/postgres/init/01-create-dagster-db.sh` on first start. |
| `DAGSTER_HOME` | Container path for Dagster's instance dir (`/app/dagster_home`); the named volume `dagster-home` persists state across restarts. |
| `REDIS_URL` | Generated locally (dev) / managed by infra (prod) |
| `QDRANT_URL`, `QDRANT_API_KEY` | Local container (dev) / Qdrant Cloud or self-hosted (prod) |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | MinIO admin credentials. **Rotate before deploying to prod.** Same values feed `S3_ACCESS_KEY_ID` / `S3_SECRET_ACCESS_KEY`. |
| `S3_ENDPOINT_URL` | `http://minio:9000` — the bundled MinIO service. Same value in dev and prod (object store is MinIO everywhere). |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | MinIO root credentials (must match `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`). |
| `S3_REGION` | `us-east-1` — required by the AWS SDK; MinIO ignores it but the field is mandatory. |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_API_AUDIENCE` | Azure Portal → App Registration for this app |
| `SENTRY_DSN` | Sentry project settings |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Internal OTEL collector address |
| `GRAFANA_PASSWORD` | Generated, stored in your secrets manager |

## Adding a new secret

1. Add it to **both** `.env.dev.example` and `.env.prod.example` with a placeholder value.
2. Add a row to the table above explaining where the value comes from.
3. Add it to the corresponding Pydantic settings field in `server/app/settings.py`.
4. Reference it from code using the typed settings, never `os.environ` directly.

## Rotation

If a secret is exposed:
1. Rotate immediately at the source (OpenAI, Azure, MinIO admin console, etc.).
2. Update the production `.env.prod`.
3. Trigger a redeploy.
4. Audit access logs for the period the secret was live.
