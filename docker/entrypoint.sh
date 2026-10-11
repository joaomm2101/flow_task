#!/bin/sh
# Apply database migrations, then run the app. Set RUN_MIGRATIONS=false when several
# replicas start at once and migrations are run as a separate step.
set -eu

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    (cd /srv/app && alembic upgrade head)
fi

# Access logs come from the app (JSON, with request ids), so uvicorn's own are off.
# NB: the login rate limiter is per worker, so the effective limit is roughly
# WEB_CONCURRENCY times higher; see the README.
exec uvicorn app.main:app \
    --host 0.0.0.0 --port 8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --no-access-log \
    --proxy-headers --forwarded-allow-ips "${FORWARDED_ALLOW_IPS:-127.0.0.1}"
