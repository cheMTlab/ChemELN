#!/bin/sh
# CheMTlab installer for a Linux server/VM with Docker.
#   git clone https://github.com/<org>/chemtlab.git && cd chemtlab && ./install.sh
# Creates .env with strong random secrets, builds and starts the stack, creates the first admin.
set -eu
cd "$(dirname "$0")"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

command -v docker >/dev/null 2>&1 || die "Docker is not installed. See https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required ('docker compose')."

secret() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "${1:-40}"; }

if [ -f .env ]; then
  say ".env already exists, keeping your configuration."
else
  printf "Domain name for CheMTlab (e.g. chemtlab.chem.example.ac.uk): "
  read -r DOMAIN
  [ -n "$DOMAIN" ] || die "A domain is required."
  printf "Administrator email: "
  read -r ADMIN_EMAIL
  printf "Backup folder on this server (NAS mount recommended) [./backups]: "
  read -r BACKUP_DIR
  BACKUP_DIR="${BACKUP_DIR:-./backups}"

  DB_PASS="$(secret 32)"
  RESTIC_PASS="$(secret 40)"

  sed \
    -e "s|^CHEMTLAB_DOMAIN=.*|CHEMTLAB_DOMAIN=${DOMAIN}|" \
    -e "s|^CHEMTLAB_ADMIN_EMAIL=.*|CHEMTLAB_ADMIN_EMAIL=${ADMIN_EMAIL}|" \
    -e "s|^DJANGO_DEBUG=.*|DJANGO_DEBUG=false|" \
    -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(secret 60)|" \
    -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=${DOMAIN},backend|" \
    -e "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://${DOMAIN}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${DB_PASS}|" \
    -e "s|^DATABASE_URL=.*|DATABASE_URL=postgres://chemtlab:${DB_PASS}@db:5432/chemtlab|" \
    -e "s|^CHEMTLAB_BACKUP_DIR=.*|CHEMTLAB_BACKUP_DIR=${BACKUP_DIR}|" \
    -e "s|^RESTIC_PASSWORD=.*|RESTIC_PASSWORD=${RESTIC_PASS}|" \
    -e "s|^DEFAULT_FROM_EMAIL=.*|DEFAULT_FROM_EMAIL=${ADMIN_EMAIL}|" \
    .env.example > .env
  chmod 600 .env
  mkdir -p "$BACKUP_DIR"

  say "Configuration written to .env"
  printf '\n\033[1;33mIMPORTANT:\033[0m store this backup password somewhere safe, OFF this server.\n'
  printf 'Without it your backups cannot be restored:\n\n    %s\n\n' "$RESTIC_PASS"
  printf "Press Enter once you have saved it... "
  read -r _
fi

say "Building and starting CheMTlab (this takes a few minutes the first time)..."
docker compose up -d --build

say "Waiting for the API to become healthy..."
i=0
until docker compose exec -T backend python manage.py doctor >/dev/null 2>&1; do
  i=$((i + 1)); [ "$i" -gt 60 ] && die "Backend did not become healthy. Check: ./chemtlab logs backend"
  sleep 3
done

say "Create the first administrator account:"
docker compose exec backend python manage.py createsuperuser

DOMAIN="$(grep '^CHEMTLAB_DOMAIN=' .env | cut -d= -f2)"
say "Done! Open https://${DOMAIN}"
say "Admin CLI: ./chemtlab help   |   Docs: docs/install.md"
