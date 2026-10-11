#!/bin/sh
# Runs once, when the database volume is first created. The application connects as an
# unprivileged role that owns only its own database (no SUPERUSER/CREATEDB/CREATEROLE);
# the postgres superuser is kept for administration and backups.
set -eu
psql -v ON_ERROR_STOP=1 -v app_password="$APP_DB_PASSWORD" --username "$POSTGRES_USER" --dbname postgres <<'SQL'
CREATE ROLE flowtask LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE flowtask OWNER flowtask;
REVOKE ALL ON DATABASE flowtask FROM PUBLIC;
SQL
