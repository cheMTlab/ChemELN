#!/bin/sh
# Minimal scheduler: run a backup once a day at BACKUP_HOUR (UTC, default 02).
# Any arguments are run as a command instead (used by ./chemtlab backup|restore).
set -eu

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

HOUR="${BACKUP_HOUR:-02}"
echo "[scheduler] daily backups at ${HOUR}:00 UTC"
while true; do
  if [ "$(date -u +%H)" = "$HOUR" ]; then
    backup.sh || echo "[scheduler] BACKUP FAILED" >&2
    sleep 3600
  fi
  sleep 300
done
