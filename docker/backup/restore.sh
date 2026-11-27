#!/bin/sh
# Restore a snapshot (default: latest). DESTRUCTIVE: replaces the current database and files.
# Stop backend and worker first:  ./chemtlab restore [snapshot-id]
set -eu

SNAPSHOT="${1:-latest}"
export PGHOST=db PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD" PGDATABASE="$POSTGRES_DB"

TARGET=/tmp/chemtlab-restore
rm -rf "$TARGET" && mkdir -p "$TARGET"

echo "[restore] extracting snapshot $SNAPSHOT"
restic restore "$SNAPSHOT" --tag chemtlab --target "$TARGET"

echo "[restore] restoring database"
pg_restore --clean --if-exists --no-owner --dbname="$PGDATABASE" \
  "$TARGET/tmp/chemtlab-backup/chemtlab.dump"

echo "[restore] restoring files"
rm -rf /data/media/*
cp -a "$TARGET/data/media/." /data/media/

rm -rf "$TARGET"
echo "[restore] done"
