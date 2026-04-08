"""Dagster code location for the data platform.

The top-level `Definitions` object is exposed by `app.orchestration.definitions`
and loaded by both `dagster-webserver` and `dagster-daemon` via `-m`.

Layout:
  app/orchestration/
    definitions.py    # the only Definitions(...) — single source of truth
    resources.py      # typed resources (S3, settings)
    assets/           # one module per logical asset group
"""
