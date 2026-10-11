#!/bin/bash
# Restore a dump made by backup.sh into a *fresh* flowtask database. DESTRUCTIVE: it drops the
# current contents, so it asks for confirmation.
#   scripts/restore.sh backups/flowtask-20260101T030000Z.sql.gz
set -euo pipefail
cd "$(dirname "$0")/.."
file="${1:?usage: scripts/restore.sh <backup.sql.gz>}"
[ -f "$file" ] || { echo "no such file: $file" >&2; exit 1; }
gzip -t "$file"
read -r -p "This REPLACES the current flowtask database with $file. Type 'restore' to continue: " answer
[ "$answer" = "restore" ] || { echo "aborted"; exit 1; }
docker compose stop app
docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 -d postgres \
  -c "DROP DATABASE IF EXISTS flowtask WITH (FORCE)" -c "CREATE DATABASE flowtask OWNER flowtask"
gunzip -c "$file" | docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 -d flowtask
docker compose exec -T db psql -U postgres -d flowtask -c "GRANT ALL ON SCHEMA public TO flowtask" >/dev/null
docker compose start app
echo "restored from $file"
