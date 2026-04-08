# Secrets

Real `.env.*` files are gitignored. Only `.env.*.example` templates are committed.

## Where each secret comes from

| Variable | Owner / Source |
|---|---|
| `POSTGRES_*`, `DATABASE_URL*` | Generated locally (dev) / managed by infra (prod) |
| `REDIS_URL` | Generated locally (dev) / managed by infra (prod) |
| `QDRANT_URL`, `QDRANT_API_KEY` | Local container (dev) / Qdrant Cloud or self-hosted (prod) |
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
1. Rotate immediately at the source (OpenAI, Azure, etc.).
2. Update the production `.env.prod`.
3. Trigger a redeploy.
4. Audit access logs for the period the secret was live.
