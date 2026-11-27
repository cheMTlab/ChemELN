# Backup sidecar: nightly encrypted, deduplicated backups of the database and file store (restic).
FROM postgres:17-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends restic ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY backup.sh restore.sh scheduler.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh /usr/local/bin/scheduler.sh

ENTRYPOINT ["scheduler.sh"]
