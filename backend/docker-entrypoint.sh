#!/bin/sh
# Runs before the API server starts: wait for the database, migrate, collect static files.
set -e

if [ "${CHEMTLAB_SKIP_MIGRATE:-false}" != "true" ]; then
  echo "Waiting for database..."
  for i in $(seq 1 30); do
    python manage.py check --database default >/dev/null 2>&1 && break
    sleep 2
  done
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput >/dev/null
fi

exec "$@"
