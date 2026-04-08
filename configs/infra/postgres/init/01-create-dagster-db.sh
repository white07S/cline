#!/usr/bin/env bash
# Postgres entrypoint init hook. Runs ONCE on first container startup, after
# the main database (POSTGRES_DB) has been created. Creates a separate
# `dagster` database for Dagster's run/event/schedule storage so its tables
# don't pollute the application schema.
#
# This file is mounted read-only into /docker-entrypoint-initdb.d/ by compose.
# Postgres ignores it on subsequent starts (the data dir already exists).
set -euo pipefail

DAGSTER_DB="${DAGSTER_POSTGRES_DB:-dagster}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE $DAGSTER_DB OWNER $POSTGRES_USER'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DAGSTER_DB')\\gexec
EOSQL
