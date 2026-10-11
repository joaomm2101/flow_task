#!/bin/bash
# Restore a dump made by backup.sh into a *fresh* flowtask database. DESTRUCTIVE: it drops the
# current contents, so it asks for confirmation.
#   scripts/restore.sh backups/flowtask-20260101T030000Z.sql.gz
#   scripts/restore.sh --yes <file>     # skip the confirmation (automation/CI)
set -euo pipefail
cd "$(dirname "$0")/.."
assume_yes=false
if [ "${1:-}" = "--yes" ]; then assume_yes=true; shift; fi
file="${1:?usage: scripts/restore.sh [--yes] <backup.sql.gz>}"
[ -f "$file" ] || { echo "no such file: $file" >&2; exit 1; }
gzip -t "$file"
if [ "$assume_yes" != true ]; then
  read -r -p "This REPLACES the current flowtask database with $file. Type 'restore' to continue: " answer
  [ "$answer" = "restore" ] || { echo "aborted"; exit 1; }
fi
docker compose stop app
docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 -d postgres \
  -c "DROP DATABASE IF EXISTS flowtask WITH (FORCE)" -c "CREATE DATABASE flowtask OWNER flowtask"
gunzip -c "$file" | docker compose exec -T db psql -U postgres -v ON_ERROR_STOP=1 -d flowtask
docker compose exec -T db psql -U postgres -d flowtask -c "GRANT ALL ON SCHEMA public TO flowtask" >/dev/null
docker compose start app
echo "restored from $file"
