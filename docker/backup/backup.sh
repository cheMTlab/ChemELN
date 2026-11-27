#!/bin/sh
# One backup run: dump the database, snapshot dump + file store into restic, apply retention.
set -eu

: "${RESTIC_REPOSITORY:?}" "${RESTIC_PASSWORD:?}"
export PGHOST=db PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" PGDATABASE="$POSTGRES_DB"

STAGING=/tmp/chemtlab-backup
rm -rf "$STAGING" && mkdir -p "$STAGING"

restic snapshots >/dev/null 2>&1 || restic init

echo "[backup] dumping database"
pg_dump --format=custom --file="$STAGING/chemtlab.dump"

echo "[backup] creating snapshot"
restic backup --tag chemtlab "$STAGING" /data/media

echo "[backup] applying retention policy"
restic forget --tag chemtlab --prune \
  --keep-daily "${BACKUP_KEEP_DAILY:-14}" \
  --keep-weekly "${BACKUP_KEEP_WEEKLY:-8}" \
  --keep-monthly "${BACKUP_KEEP_MONTHLY:-12}"

if [ "${1:-}" = "--verify" ]; then
  echo "[backup] verifying repository integrity"
  restic check --read-data-subset=5%
fi

rm -rf "$STAGING"
echo "[backup] done"
