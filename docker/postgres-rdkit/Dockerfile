# PostgreSQL 17 with the RDKit cartridge (substructure/similarity search in SQL).
# Debian trixie ships postgresql-17-rdkit in its main archive.
FROM postgres:17-trixie

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-17-rdkit \
    && rm -rf /var/lib/apt/lists/*

COPY init-rdkit.sql /docker-entrypoint-initdb.d/10-rdkit.sql
