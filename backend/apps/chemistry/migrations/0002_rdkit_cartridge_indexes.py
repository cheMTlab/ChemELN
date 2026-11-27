"""Index compound structures with the RDKit PostgreSQL cartridge.

PostgreSQL only; does nothing elsewhere. If the cartridge is missing or an index cannot be
created, structure search still works through the slower Python fallback, and
`manage.py doctor` reports it.
"""

import logging

from django.db import migrations

logger = logging.getLogger(__name__)

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS rdkit",
    "CREATE INDEX IF NOT EXISTS chemistry_compound_mol_gist ON chemistry_compound "
    "USING gist (mol_from_smiles(smiles::cstring)) WHERE smiles <> ''",
    "CREATE INDEX IF NOT EXISTS chemistry_compound_mfp_gist ON chemistry_compound "
    "USING gist (morganbv_fp(mol_from_smiles(smiles::cstring))) WHERE smiles <> ''",
]


def forwards(apps, schema_editor):
    conn = schema_editor.connection
    if conn.vendor != "postgresql":
        return
    for sql in STATEMENTS:
        try:
            with conn.cursor() as cur:
                cur.execute("SAVEPOINT rdkit_idx")
                cur.execute(sql)
                cur.execute("RELEASE SAVEPOINT rdkit_idx")
        except Exception as exc:  # noqa: BLE001
            with conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT rdkit_idx")
            logger.warning("RDKit cartridge step skipped (%s): %s", sql.split(" ON ")[0], exc)


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cur:
        cur.execute("DROP INDEX IF EXISTS chemistry_compound_mol_gist")
        cur.execute("DROP INDEX IF EXISTS chemistry_compound_mfp_gist")


class Migration(migrations.Migration):
    dependencies = [("chemistry", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
