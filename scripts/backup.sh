#!/bin/bash
# Dump the application database from the compose stack to backups/flowtask-<utc>.sql.gz and
# keep the newest KEEP files (default 14). Run it from cron, e.g. daily at 03:00:
#   0 3 * * * cd /path/to/project && scripts/backup.sh
set -euo pipefail
cd "$(dirname "$0")/.."
KEEP="${KEEP:-14}"
mkdir -p backups
umask 077
file="backups/flowtask-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
docker compose exec -T db pg_dump -U postgres flowtask  # keeps ownership so the app role can use the restored tables | gzip > "$file"
gzip -t "$file"  # refuse to keep a corrupt dump
echo "backup written: $file ($(du -h "$file" | cut -f1))"
ls -1t backups/flowtask-*.sql.gz | tail -n +"$((KEEP + 1))" | xargs -r rm -f --
