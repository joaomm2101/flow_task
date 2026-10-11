#!/bin/bash
# Dump the application database from the compose stack into backups/ and keep the newest KEEP
# files (default 14). Run it from cron, e.g. daily at 03:00:
#   0 3 * * * cd /path/to/project && scripts/backup.sh
#
# A dump holds password hashes and personal data, so:
#   - the backups/ directory is 700 and every file 600;
#   - set BACKUP_AGE_RECIPIENT=<age public key> to encrypt with `age` (https://age-encryption.org),
#     producing flowtask-<utc>.sql.gz.age; keep the private key OFF this server;
#   - the file only appears once the dump finished, so a failed run never leaves a partial backup.
set -euo pipefail
cd "$(dirname "$0")/.."
KEEP="${KEEP:-14}"

umask 077   # before mkdir: the directory and everything in it stay private
mkdir -p backups
chmod 700 backups

base="backups/flowtask-$(date -u +%Y%m%dT%H%M%SZ)"
partial="$base.partial"
trap 'rm -f "$partial"' EXIT

if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
  command -v age >/dev/null || { echo "BACKUP_AGE_RECIPIENT is set but 'age' is not installed" >&2; exit 1; }
  file="$base.sql.gz.age"
  docker compose exec -T db pg_dump -U postgres flowtask | gzip | age -r "$BACKUP_AGE_RECIPIENT" > "$partial"
else
  file="$base.sql.gz"
  docker compose exec -T db pg_dump -U postgres flowtask | gzip > "$partial"
  gzip -t "$partial"  # refuse to keep a corrupt dump
fi
[ -s "$partial" ] || { echo "backup is empty, aborting" >&2; exit 1; }

chmod 600 "$partial"
mv "$partial" "$file"
trap - EXIT
echo "backup written: $file ($(du -h "$file" | cut -f1))"

ls -1t backups/flowtask-*.sql.gz backups/flowtask-*.sql.gz.age 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f --
